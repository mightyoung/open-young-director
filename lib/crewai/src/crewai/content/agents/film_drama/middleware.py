"""Middleware for FILM_DRAMA character agent processing."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field

from .enums import BeatType

logger = logging.getLogger(__name__)


@dataclass
class MiddlewareResult:
    """Result from middleware processing."""
    modified_output: Optional[str] = None
    skip_agent: bool = False
    retry_requested: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class CharacterMiddleware(ABC):
    """Base class for character agent middleware.

    Middleware intercepts and processes character agent responses
    before they are stored or assembled into the final scene.

    Usage:
        middleware = EmotionalStateMiddleware()
        result = await middleware.process(
            character_name="韩林",
            beat=beat,
            output="角色对话...",
            context={...}
        )
    """

    name: str = "base"

    @abstractmethod
    async def process(
        self,
        character_name: str,
        beat,  # PlotBeat
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Process a character response.

        Args:
            character_name: Name of the character
            beat: Current plot beat
            output: The raw output from character agent
            context: Additional context (memory, tension, etc.)

        Returns:
            MiddlewareResult with potentially modified output
        """
        pass

    async def on_beat_start(
        self,
        character_name: str,
        beat,
        context: Dict[str, Any],
    ) -> None:
        """Called before processing a beat for a character."""
        pass

    async def on_beat_end(
        self,
        character_name: str,
        beat,
        result: MiddlewareResult,
        context: Dict[str, Any],
    ) -> None:
        """Called after processing a beat for a character."""
        pass


class MiddlewareChain:
    """Chain of middleware processors for character responses."""

    def __init__(self):
        self._middlewares: List[CharacterMiddleware] = []

    def add(self, middleware: CharacterMiddleware) -> "MiddlewareChain":
        """Add a middleware to the chain."""
        self._middlewares.append(middleware)
        return self

    def add_many(self, middlewares: List[CharacterMiddleware]) -> "MiddlewareChain":
        """Add multiple middlewares to the chain."""
        self._middlewares.extend(middlewares)
        return self

    async def process(
        self,
        character_name: str,
        beat,
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Process output through middleware chain with retry support."""
        result = MiddlewareResult(modified_output=output)

        max_retries = 3
        for attempt in range(max_retries):
            for middleware in self._middlewares:
                try:
                    if hasattr(middleware, 'process'):
                        result = await middleware.process(
                            character_name=character_name,
                            beat=beat,
                            output=result.modified_output or output,
                            context=context,
                        )
                        if result.skip_agent:
                            logger.debug(
                                f"[Middleware] {middleware.name} skipped agent for {character_name}"
                            )
                            return result
                except Exception as e:
                    logger.error(f"[Middleware] {middleware.name} failed: {e}")
                    result.error = str(e)
                    # 如果是严重错误，可以选择中断处理链
                    if getattr(middleware, '_critical', False):
                        logger.critical(f"[Middleware] Critical failure in {middleware.name}, stopping chain")
                        return result  # 中断处理链

            # If no retry requested, we're done
            if not result.retry_requested:
                return result

            # If retry requested and we have more attempts, retry
            if attempt < max_retries - 1:
                logger.info(
                    f"[MiddlewareChain] Retrying {character_name} for beat {beat.beat_id} "
                    f"(attempt {attempt + 2}/{max_retries})"
                )
                # Clear retry flag to avoid infinite loop
                result.retry_requested = False
                # Mark as retry so middlewares like MemoryQueueMiddleware skip duplicate recording
                context["_is_retry"] = True

        return result

    async def on_beat_start(
        self,
        character_name: str,
        beat,
        context: Dict[str, Any],
    ) -> None:
        """Notify all middlewares of beat start."""
        for middleware in self._middlewares:
            try:
                await middleware.on_beat_start(character_name, beat, context)
            except Exception as e:
                logger.error(f"[Middleware] {middleware.name} on_beat_start failed: {e}")

    async def on_beat_end(
        self,
        character_name: str,
        beat,
        result: MiddlewareResult,
        context: Dict[str, Any],
    ) -> None:
        """Notify all middlewares of beat end."""
        for middleware in self._middlewares:
            try:
                await middleware.on_beat_end(character_name, beat, result, context)
            except Exception as e:
                logger.error(f"[Middleware] {middleware.name} on_beat_end failed: {e}")

    def reset(self) -> None:
        """Reset all middleware state. Call this between scenes."""
        for middleware in self._middlewares:
            try:
                if hasattr(middleware, 'clear_batch'):
                    middleware.clear_batch()
                if hasattr(middleware, 'clear_clarification'):
                    middleware.clear_clarification()
                if hasattr(middleware, 'reset'):
                    middleware.reset()
            except Exception as e:
                logger.error(f"[Middleware] {middleware.name} reset failed: {e}")


MAX_STATE_HISTORY = 50  # Maximum history entries per character


class EmotionalStateMiddleware(CharacterMiddleware):
    """Middleware that tracks and validates emotional consistency.

    Ensures character responses are emotionally consistent with their
    established emotional state and the beat type.
    """

    name = "emotional_state"

    def __init__(self):
        self._state_history: Dict[str, List[Dict[str, Any]]] = {}

    async def process(
        self,
        character_name: str,
        beat,
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Check emotional consistency and update state."""
        # Get emotional context from memory if available
        memory = context.get("memory", {})
        current_emotions = memory.get("current_emotions", {})
        conflict_active = memory.get("conflict_active", False)

        # Validate emotional consistency based on beat type
        modified = False
        warnings = []

        if beat.beat_type == BeatType.OPENING.value:
            # Opening beats should be calmer
            if current_emotions.get("愤怒") or current_emotions.get("恐惧"):
                warnings.append("Opening beat but character is angry/scared - may be inconsistent")

        elif beat.beat_type == BeatType.CONFLICT.value:
            # Conflict beats can heighten emotions
            if not conflict_active:
                warnings.append("Conflict beat starting - expect tension increase")

        elif beat.beat_type == BeatType.CLIMAX.value:
            # Climax should have peak tension
            if not any([
                current_emotions.get("愤怒"),
                current_emotions.get("恐惧"),
                current_emotions.get("喜悦"),  # triumph
            ]):
                warnings.append("Climax beat but no strong emotions detected")

        # Record emotional state for this response
        if character_name not in self._state_history:
            self._state_history[character_name] = []

        self._state_history[character_name].append({
            "beat_id": beat.beat_id,
            "beat_type": beat.beat_type,
            "emotions": current_emotions,
            "has_warnings": len(warnings) > 0,
        })

        # Trim history to prevent unbounded growth
        if len(self._state_history[character_name]) > MAX_STATE_HISTORY:
            self._state_history[character_name] = self._state_history[character_name][-MAX_STATE_HISTORY:]

        # Calculate severity based on warning count
        emotional_inconsistency = len(warnings) > 0
        severity = "low"
        if emotional_inconsistency:
            if len(warnings) >= 3:
                severity = "high"
            elif len(warnings) >= 1:
                severity = "medium"

        emotional_check = "failed" if emotional_inconsistency else "passed"

        return MiddlewareResult(
            modified_output=output,
            metadata={
                "emotional_check": emotional_check,
                "emotional_inconsistency": emotional_inconsistency,
                "warnings": warnings,
                "severity": severity,
                "conflict_active": conflict_active,
                "current_emotions": current_emotions,
            }
        )


class SubagentLimitMiddleware(CharacterMiddleware):
    """Middleware that enforces the ≤3 concurrent subagent limit.

    This is typically used at the Director level rather than per-character,
    but can also validate that the system respects the limit.
    """

    name = "subagent_limit"

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._current_batch: List[str] = []

    def clear_batch(self) -> None:
        """Clear the current batch. Call this at the end of each beat."""
        self._current_batch.clear()

    async def process(
        self,
        character_name: str,
        beat,
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Track concurrent processing and warn if limit exceeded."""
        self._current_batch.append(character_name)

        exceeded = len(self._current_batch) > self.max_concurrent

        if exceeded:
            logger.warning(
                f"[SubagentLimit] Batch size {len(self._current_batch)} "
                f"exceeds limit {self.max_concurrent}"
            )

        return MiddlewareResult(
            modified_output=output,
            metadata={
                "batch_size": len(self._current_batch),
                "limit": self.max_concurrent,
                "exceeded": exceeded,
            }
        )

    async def on_beat_end(
        self,
        character_name: str,
        beat,
        result: MiddlewareResult,
        context: Dict[str, Any],
    ) -> None:
        """Clear batch at end of beat processing."""
        # Reset for next beat - but batch is managed by DirectorAgent
        # so this is a no-op; call clear_batch() explicitly instead


class ClarificationMiddleware(CharacterMiddleware):
    """Middleware that handles CLARIFY message type for ambiguity.

    When a character's response is ambiguous or contradictory,
    this middleware can trigger a clarification request.
    """

    name = "clarification"

    def __init__(self, threshold: float = 0.3):
        self.threshold = threshold
        self._pending_clarifications: Dict[str, Dict[str, Any]] = {}

    async def process(
        self,
        character_name: str,
        beat,
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Check for ambiguous content that needs clarification."""
        # Skip if this character was already flagged for clarification on a previous
        # iteration of this middleware chain to prevent infinite retry loops
        if character_name in self._pending_clarifications:
            logger.debug(
                f"[Clarification] {character_name} already flagged, skipping to prevent loop"
            )
            return MiddlewareResult(
                modified_output=output,
                skip_agent=False,
                retry_requested=False,
                metadata={
                    "clarification_needed": False,
                    "reason": "already_pending",
                }
            )

        # Simple heuristics for ambiguity detection
        ambiguous_phrases = ["也许", "可能", "不确定", "说不清", "不太清楚"]
        has_ambiguity = any(phrase in output for phrase in ambiguous_phrases)

        # Check for contradictions with previous outputs
        previous_outputs = context.get("previous_outputs", {})
        contradictions = self._check_contradictions(
            character_name, output, previous_outputs
        )

        needs_clarification = has_ambiguity or contradictions

        if needs_clarification:
            issue = "ambiguous" if has_ambiguity else "contradiction"
            logger.warning(f"[Clarification] {character_name} output may have issues: {issue}")
            self._pending_clarifications[character_name] = {
                "beat_id": beat.beat_id,
                "reason": issue,
                "output": output,
            }
            return MiddlewareResult(
                modified_output=None,
                skip_agent=False,
                retry_requested=True,
                metadata={
                    "clarification_needed": True,
                    "issue": issue,
                    "original_output": output,
                }
            )

        return MiddlewareResult(
            modified_output=output,
            metadata={
                "clarification_needed": False,
                "reason": None,
            }
        )

    def _check_contradictions(
        self,
        character_name: str,
        output: str,
        previous_outputs: Dict[str, List[str]],
    ) -> bool:
        """Check if output contradicts previous outputs."""
        prev_list = previous_outputs.get(character_name, [])
        if not prev_list:
            return False

        last_output = prev_list[-1]

        # Simple contradiction detection
        positive_words = ["是", "同意", "支持", "会", "可以"]
        negative_words = ["不", "否", "反对", "不会", "不能"]

        has_positive = any(w in output for w in positive_words)
        has_negative = any(w in output for w in negative_words)
        last_positive = any(w in last_output for w in positive_words)
        last_negative = any(w in last_output for w in negative_words)

        # Contradiction if one is positive and other is negative
        if has_positive and last_negative:
            return True
        if has_negative and last_positive:
            return True

        return False

    def get_pending_clarifications(self) -> Dict[str, Dict[str, Any]]:
        """Get any pending clarification requests."""
        return dict(self._pending_clarifications)

    def clear_clarification(self, character_name: str) -> None:
        """Clear a pending clarification after it's resolved."""
        self._pending_clarifications.pop(character_name, None)

    def reset(self) -> None:
        """Clear all pending clarifications. Call this between scenes."""
        self._pending_clarifications.clear()


class MemoryQueueMiddleware(CharacterMiddleware):
    """Middleware that integrates with CharacterMemoryQueue.

    Records emotional states and updates memory based on responses.
    """

    name = "memory_queue"

    def __init__(self, memory_queue=None):
        self.memory_queue = memory_queue

    async def process(
        self,
        character_name: str,
        beat,
        output: str,
        context: Dict[str, Any],
    ) -> MiddlewareResult:
        """Record response to memory queue."""
        # Skip memory recording on retries to avoid duplicate entries
        if context.get("_is_retry"):
            return MiddlewareResult(modified_output=output)

        if not self.memory_queue:
            return MiddlewareResult(modified_output=output)

        # Extract emotional keywords from output
        emotions = self._extract_emotions(output)

        # Record to memory
        tension = self._estimate_tension_from_output(output, beat.beat_type)

        await self.memory_queue.record_state_async(
            character_name=character_name,
            beat_id=beat.beat_id,
            emotions=emotions,
            conflict_active=beat.beat_type == BeatType.CONFLICT.value,
            tension_level=tension,
            summary=f"{beat.beat_type}: {output[:50]}...",
        )

        return MiddlewareResult(
            modified_output=output,
            metadata={
                "emotions_recorded": emotions,
                "tension_recorded": tension,
            }
        )

    def _extract_emotions(self, output: str) -> Dict[str, bool]:
        """Extract emotional indicators from output text."""
        emotion_keywords = {
            "愤怒": ["怒", "气愤", "恼火", "可恶", "该死"],
            "悲伤": ["悲", "伤心", "心痛", "难过", "痛苦"],
            "喜悦": ["喜", "高兴", "开心", "兴奋", "太好了"],
            "恐惧": ["惧", "害怕", "担心", "不安", "忧虑"],
            "惊讶": ["惊", "惊讶", "意外", "没想到", "居然"],
        }

        emotions = {}
        for emotion, keywords in emotion_keywords.items():
            emotions[emotion] = any(kw in output for kw in keywords)

        return emotions

    def _estimate_tension_from_output(self, output: str, beat_type: str) -> float:
        """Estimate tension from output content."""
        base_tension = {
            BeatType.OPENING.value: 0.1,
            BeatType.DEVELOPMENT.value: 0.3,
            BeatType.CONFLICT.value: 0.6,
            BeatType.CLIMAX.value: 0.9,
            BeatType.RESOLUTION.value: 0.4,
            BeatType.TRANSITION.value: 0.2,
        }.get(beat_type, 0.3)

        # Increase for certain keywords
        tension_increasing = ["!", "！", "？", "激烈", "紧张", "危机"]
        if any(kw in output for kw in tension_increasing):
            base_tension = min(1.0, base_tension + 0.1)

        return base_tension
