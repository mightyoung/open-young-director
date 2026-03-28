"""Quality Gate for content quality validation after Consumer output.

QualityGate acts as a content quality gate that validates content produced
by Consumers (NovelConsumer, PodcastConsumer, VideoConsumer, MusicConsumer).

It integrates with RuleBasedEvaluator and LLMasJudgeEvaluator to provide
comprehensive quality assessment and supports three quality levels:
- PASS: Content meets quality standards, proceed directly
- REVIEW: Content needs human review before proceeding
- REJECT: Content fails quality standards, needs revision

Quality Thresholds:
- PASS: overall_score >= 0.75
- REVIEW: 0.6 <= overall_score < 0.75
- REJECT: overall_score < 0.6

Consumer-Specific Check Dimensions:
- NovelConsumer: coherence, character_consistency (weighted higher)
- VideoConsumer: dialogue_quality, plot_coherence (weighted higher)
- PodcastConsumer: dialogue_quality, language_quality (weighted higher)
- MusicConsumer: coherence, emotional_depth (weighted higher)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Type

from evaluation.evaluator import (
    EvaluationConfig,
    EvaluationResult,
    RuleBasedEvaluator,
    LLMasJudgeEvaluator,
    create_evaluator,
)
from evaluation.metrics import ContentMetrics


class GateDecision(Enum):
    """Quality gate decision levels."""
    PASS = "pass"      # Directly pass, proceed to next step
    REVIEW = "review"   # Needs human review before proceeding
    REJECT = "reject"   # Rejected, needs revision


# Quality thresholds
GATE_PASS_THRESHOLD = 0.75
GATE_REVIEW_THRESHOLD = 0.60


@dataclass
class QualityGateResult:
    """Result of quality gate check.

    Attributes:
        decision: The gate decision (PASS, REVIEW, or REJECT)
        scores: Dictionary of dimension scores
        issues: List of identified issues
        suggestions: List of improvement suggestions
        overall_score: Overall quality score (0.0 to 1.0)
        consumer_type: Type of consumer that produced the content
        evaluation_result: The underlying evaluation result
        retry_count: Number of retries attempted (for check_and_retry)
    """
    decision: GateDecision
    scores: Dict[str, float]
    issues: List[str]
    suggestions: List[str]
    overall_score: float
    consumer_type: str = ""
    evaluation_result: Optional[EvaluationResult] = None
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "decision": self.decision.value,
            "scores": self.scores,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "overall_score": self.overall_score,
            "consumer_type": self.consumer_type,
            "retry_count": self.retry_count,
        }

    @property
    def is_pass(self) -> bool:
        """Check if the decision is PASS."""
        return self.decision == GateDecision.PASS

    @property
    def is_review(self) -> bool:
        """Check if the decision is REVIEW."""
        return self.decision == GateDecision.REVIEW

    @property
    def is_reject(self) -> bool:
        """Check if the decision is REJECT."""
        return self.decision == GateDecision.REJECT


# Consumer type to critical dimensions mapping
# These dimensions are weighted higher for each consumer type
CONSUMER_CRITICAL_DIMENSIONS: Dict[str, List[str]] = {
    "novel": ["coherence", "character_consistency"],
    "video": ["dialogue_quality", "plot_coherence"],
    "podcast": ["dialogue_quality", "language_quality"],
    "music": ["coherence", "emotional_depth"],
}


@dataclass
class QualityGate:
    """Content quality gate for validating Consumer output.

    QualityGate validates content produced by Consumers and returns
    a GateDecision (PASS, REVIEW, or REJECT) based on quality thresholds.

    Example:
        >>> config = EvaluationConfig()
        >>> gate = QualityGate(config)
        >>> result = gate.check(content, "novel", context={"scene_id": "scene_001"})
        >>> if result.is_pass:
        ...     print("Content approved, proceed to next step")
        ... elif result.is_review:
        ...     print("Content needs human review")
        ... else:
        ...     print("Content needs revision")
    """

    def __init__(self, config: EvaluationConfig):
        """Initialize the quality gate.

        Args:
            config: Evaluation configuration containing thresholds and weights
        """
        self.config = config
        self.rule_evaluator = RuleBasedEvaluator(config)
        self._llm_evaluator: Optional[LLMasJudgeEvaluator] = None

    def _get_llm_evaluator(self, llm_client: Any = None) -> Optional[LLMasJudgeEvaluator]:
        """Get or create LLM evaluator if configured.

        Args:
            llm_client: Optional LLM client for evaluation

        Returns:
            LLMasJudgeEvaluator instance or None
        """
        if self.config.use_llm_judge and llm_client is not None:
            if self._llm_evaluator is None:
                self._llm_evaluator = LLMasJudgeEvaluator(llm_client, self.config)
            return self._llm_evaluator
        return None

    def check(
        self,
        content: Any,
        consumer_type: str,
        context: Optional[Dict[str, Any]] = None,
        llm_client: Any = None,
    ) -> QualityGateResult:
        """Check content quality and return gate decision.

        Args:
            content: The content to evaluate (usually string or dict from Consumer)
            consumer_type: Type of consumer ("novel", "podcast", "video", "music")
            context: Optional context information (e.g., scene_id, character_profiles)
            llm_client: Optional LLM client for hybrid evaluation

        Returns:
            QualityGateResult with decision, scores, issues, and suggestions
        """
        # Extract text content from various content types
        text_content = self._extract_content(content)

        if not text_content or len(text_content.strip()) < 50:
            return QualityGateResult(
                decision=GateDecision.REJECT,
                scores={},
                issues=["Content is too short or empty"],
                suggestions=["Provide more content for evaluation"],
                overall_score=0.0,
                consumer_type=consumer_type,
            )

        # Perform evaluation
        llm_evaluator = self._get_llm_evaluator(llm_client)
        if llm_evaluator is not None:
            eval_result = llm_evaluator.evaluate(text_content, context)
        else:
            eval_result = self.rule_evaluator.evaluate(text_content, context)

        # Extract scores
        scores = self._extract_scores(eval_result, consumer_type)

        # Compute overall score with consumer-specific weighting
        overall_score = self._compute_weighted_score(scores, consumer_type)

        # Determine gate decision
        decision = self._determine_decision(overall_score)

        # Generate issues and suggestions
        issues = self._identify_issues(scores, consumer_type, eval_result)
        suggestions = self._generate_suggestions(scores, consumer_type, issues)

        return QualityGateResult(
            decision=decision,
            scores=scores,
            issues=issues,
            suggestions=suggestions,
            overall_score=overall_score,
            consumer_type=consumer_type,
            evaluation_result=eval_result,
        )

    def check_and_retry(
        self,
        consumer: Any,  # BaseConsumer
        scene_id: str,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """Execute quality gate check with automatic retry on failure.

        This method runs the consumer's consume() method, checks the output
        through the quality gate, and retries if the quality is below threshold.

        Args:
            consumer: BaseConsumer instance (NovelConsumer, PodcastConsumer, etc.)
            scene_id: The scene identifier to process
            max_retries: Maximum number of retry attempts (default: 2)

        Returns:
            Dictionary containing:
            - result: The final content result (or None if all retries failed)
            - gate_result: The final QualityGateResult
            - scene_id: The input scene ID
            - success: Whether content passed quality gate
            - attempts: Number of attempts made
            - all_results: List of all gate results from each attempt
        """
        import asyncio

        all_results: List[QualityGateResult] = []
        current_content: Any = None

        for attempt in range(max_retries + 1):
            # Run consumer to generate content
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            consume_result = loop.run_until_complete(
                consumer.consume(scene_id)
            )

            if not consume_result.get("success", False):
                # Consumer failed
                failed_result = QualityGateResult(
                    decision=GateDecision.REJECT,
                    scores={},
                    issues=[f"Consumer failed: {consume_result.get('error', 'Unknown error')}"],
                    suggestions=["Check consumer configuration and scene data"],
                    overall_score=0.0,
                    consumer_type=consumer.consumer_type,
                    retry_count=attempt,
                )
                all_results.append(failed_result)
                continue

            current_content = consume_result.get("result")

            # Check quality
            gate_result = self.check(
                content=current_content,
                consumer_type=consumer.consumer_type,
                context={"scene_id": scene_id},
            )
            gate_result.retry_count = attempt
            all_results.append(gate_result)

            # If passed or REVIEW (which still allows proceeding), accept content
            if gate_result.decision == GateDecision.PASS:
                return {
                    "result": current_content,
                    "gate_result": gate_result,
                    "scene_id": scene_id,
                    "success": True,
                    "attempts": attempt + 1,
                    "all_results": all_results,
                }

            # If REVIEW, allow proceeding but note it needs review
            if gate_result.decision == GateDecision.REVIEW:
                return {
                    "result": current_content,
                    "gate_result": gate_result,
                    "scene_id": scene_id,
                    "success": True,  # Still success, but flagged for review
                    "attempts": attempt + 1,
                    "all_results": all_results,
                }

            # If REJECT and we have retries left, continue to next attempt
            if attempt < max_retries:
                # Log retry information (would use proper logging in production)
                print(f"Quality gate rejected content (attempt {attempt + 1}/{max_retries + 1}), retrying...")

        # All retries exhausted
        final_result = all_results[-1] if all_results else QualityGateResult(
            decision=GateDecision.REJECT,
            scores={},
            issues=["All retry attempts failed"],
            suggestions=["Review content manually or adjust quality thresholds"],
            overall_score=0.0,
            consumer_type=consumer.consumer_type,
            retry_count=max_retries,
        )

        return {
            "result": None,  # Return None since quality gate rejected
            "gate_result": final_result,
            "scene_id": scene_id,
            "success": False,
            "attempts": max_retries + 1,
            "all_results": all_results,
        }

    def _extract_content(self, content: Any) -> str:
        """Extract text content from various content types.

        Args:
            content: Content from consumer (str, dict, or other)

        Returns:
            Extracted text string
        """
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            # Handle different consumer output formats
            # NovelConsumer: returns str directly (already handled above)
            # PodcastConsumer: dict {title, script, duration_estimate, speakers}
            if "script" in content:
                return content["script"]
            # VideoConsumer: dict {title, scenes, narration, music_suggestions}
            if "narration" in content:
                return content["narration"]
            if "scenes" in content and isinstance(content["scenes"], list):
                return " ".join(str(s) for s in content["scenes"])
            # MusicConsumer: dict {style, mood, tempo, instruments, prompt}
            if "prompt" in content:
                return content["prompt"]
            # Fallback: try to stringify
            return str(content)
        else:
            return str(content)

    def _extract_scores(
        self,
        eval_result: EvaluationResult,
        consumer_type: str
    ) -> Dict[str, float]:
        """Extract and normalize scores from evaluation result.

        Args:
            eval_result: The evaluation result
            consumer_type: The consumer type for dimension naming

        Returns:
            Dictionary of dimension scores
        """
        if eval_result.metrics is not None:
            return {
                "coherence": eval_result.metrics.coherence_score,
                "character_consistency": eval_result.metrics.character_consistency_score,
                "dialogue_quality": eval_result.metrics.dialogue_quality_score,
                "plot_coherence": eval_result.metrics.plot_coherence_score,
                "emotional_depth": eval_result.metrics.emotional_depth_score,
                "language_quality": eval_result.metrics.language_quality_score,
            }

        # Fallback to details dict
        if eval_result.details:
            return {
                "coherence": eval_result.details.get("coherence", 0.0),
                "character_consistency": eval_result.details.get("character_consistency", 0.0),
                "dialogue_quality": eval_result.details.get("dialogue_quality", 0.0),
                "plot_coherence": eval_result.details.get("plot_coherence", 0.0),
                "emotional_depth": eval_result.details.get("emotional_depth", 0.0),
                "language_quality": eval_result.details.get("language_quality", 0.0),
            }

        return {}

    def _compute_weighted_score(
        self,
        scores: Dict[str, float],
        consumer_type: str
    ) -> float:
        """Compute overall score with consumer-specific dimension weighting.

        Args:
            scores: Dictionary of dimension scores
            consumer_type: The consumer type for weighting

        Returns:
            Weighted overall score
        """
        if not scores:
            return 0.0

        # Get base weights from config
        weights = self.config.weights.copy()

        # Adjust weights for consumer type
        critical_dims = CONSUMER_CRITICAL_DIMENSIONS.get(consumer_type, [])

        if critical_dims:
            # Boost critical dimensions by 1.5x, reduce others proportionally
            boost_factor = 1.5
            critical_weight = 0.1  # Additional weight for critical dims

            total_boost = 0.0
            for dim in critical_dims:
                if dim in weights:
                    weights[dim] = weights[dim] * boost_factor
                    total_boost += weights[dim] * critical_weight

            # Normalize weights to sum to 1.0
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v / total_weight for k, v in weights.items()}

        # Compute weighted sum
        overall = sum(
            scores.get(dim, 0.0) * weights.get(dim, 0.0)
            for dim in scores
        )

        return min(1.0, max(0.0, overall))

    def _determine_decision(self, overall_score: float) -> GateDecision:
        """Determine gate decision based on overall score.

        Args:
            overall_score: The overall quality score

        Returns:
            GateDecision enum value
        """
        if overall_score >= GATE_PASS_THRESHOLD:
            return GateDecision.PASS
        elif overall_score >= GATE_REVIEW_THRESHOLD:
            return GateDecision.REVIEW
        else:
            return GateDecision.REJECT

    def _identify_issues(
        self,
        scores: Dict[str, float],
        consumer_type: str,
        eval_result: EvaluationResult
    ) -> List[str]:
        """Identify specific issues from low-scoring dimensions.

        Args:
            scores: Dictionary of dimension scores
            consumer_type: The consumer type
            eval_result: The evaluation result for additional context

        Returns:
            List of identified issues
        """
        issues = []
        threshold = self.config.pass_threshold

        # Check each dimension against its threshold
        dimension_thresholds = {
            "coherence": self.config.coherence_threshold,
            "character_consistency": self.config.character_threshold,
            "dialogue_quality": self.config.dialogue_threshold,
            "plot_coherence": self.config.plot_threshold,
            "emotional_depth": self.config.emotional_threshold,
            "language_quality": self.config.language_threshold,
        }

        for dim, score in scores.items():
            dim_threshold = dimension_thresholds.get(dim, threshold)
            if score < dim_threshold:
                issues.append(f"{dim} score ({score:.2f}) is below threshold ({dim_threshold:.2f})")

        # Consumer-specific checks
        critical_dims = CONSUMER_CRITICAL_DIMENSIONS.get(consumer_type, [])
        for dim in critical_dims:
            if dim in scores and scores[dim] < 0.65:
                issues.append(f"Critical dimension '{dim}' for {consumer_type} content is low ({scores[dim]:.2f})")

        # Add any issues from evaluation result
        if eval_result.error:
            issues.append(f"Evaluation error: {eval_result.error}")

        return issues

    def _generate_suggestions(
        self,
        scores: Dict[str, float],
        consumer_type: str,
        issues: List[str]
    ) -> List[str]:
        """Generate improvement suggestions based on low-scoring dimensions.

        Args:
            scores: Dictionary of dimension scores
            consumer_type: The consumer type
            issues: List of identified issues

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Dimension-specific suggestions
        dimension_suggestions = {
            "coherence": [
                "Improve paragraph transitions with transition words",
                "Ensure logical flow between sentences and paragraphs",
                "Clarify time and space markers when scene changes occur",
            ],
            "character_consistency": [
                "Review character profiles and ensure consistent behavior",
                "Check that character speech patterns remain consistent",
                "Verify character actions align with their established traits",
            ],
            "dialogue_quality": [
                "Make dialogues more natural and character-specific",
                "Ensure dialogue tags (said, asked) are varied",
                "Use dialogue to reveal character and advance plot",
            ],
            "plot_coherence": [
                "Check for timeline consistency",
                "Add more cause-and-effect relationships",
                "Review plot transitions for smoothness",
            ],
            "emotional_depth": [
                "Add more emotional vocabulary",
                "Show emotions through actions and reactions",
                "Include varied emotional tones",
            ],
            "language_quality": [
                "Review for grammatical errors",
                "Vary sentence structure",
                "Check for repeated words or phrases",
            ],
        }

        # Generate suggestions based on low scores
        for dim, score in scores.items():
            if score < 0.7:
                dim_suggestions = dimension_suggestions.get(dim, [])
                suggestions.extend(dim_suggestions[:2])  # Add top 2 suggestions

        # Consumer-specific suggestions
        consumer_specific_suggestions = {
            "novel": [
                "Focus on narrative coherence and character consistency",
                "Ensure descriptions are vivid and consistent",
            ],
            "video": [
                "Emphasize dialogue clarity and plot coherence for visual medium",
                "Ensure scenes are clearly distinguished",
            ],
            "podcast": [
                "Prioritize dialogue quality and language clarity for audio",
                "Ensure script flows well when spoken",
            ],
            "music": [
                "Focus on emotional coherence throughout the piece",
                "Ensure the emotional arc is clear and consistent",
            ],
        }

        if consumer_type in consumer_specific_suggestions:
            suggestions.extend(consumer_specific_suggestions[consumer_type])

        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique_suggestions.append(s)

        return unique_suggestions[:10]  # Limit to top 10 suggestions


def create_quality_gate(config: EvaluationConfig = None) -> QualityGate:
    """Create a QualityGate instance with optional configuration.

    This is a convenience function to create a QualityGate with
    default or custom configuration.

    Args:
        config: Optional EvaluationConfig, uses default if not provided

    Returns:
        QualityGate instance

    Example:
        >>> gate = create_quality_gate()
        >>> result = gate.check(content, "novel")
        >>>
        >>> # With custom config
        >>> config = EvaluationConfig(pass_threshold=0.8)
        >>> gate = create_quality_gate(config)
    """
    return QualityGate(config or EvaluationConfig())
