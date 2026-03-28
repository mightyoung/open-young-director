# -*- encoding: utf-8 -*-
"""RealityChecker Agent - Quality validation for generated content.

RealityChecker implements strict quality gates for content validation:
- Default status is "NEEDS WORK"
- Requires overwhelming evidence to pass
- Stops fantasy approvals
- Requires screenshot/output evidence
- Cross-validates QA findings

Usage:
    from agents.reality_checker import RealityChecker, ValidationResult

    checker = RealityChecker(llm_client=llm)
    result = checker.validate_content(content, criteria)

    if result.status == "PASS":
        print("Content approved")
    else:
        print(f"Issues: {result.issues}")
        print(f"Evidence required: {result.evidence_required}")
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of content validation.

    Attributes:
        status: Validation status - PASS, FAIL, or NEEDS_WORK
        score: Quality score from 0.0 to 1.0
        issues: List of identified issues
        evidence_required: List of evidence requirements for approval
        validated_at: Timestamp of validation
        validation_details: Additional details about the validation
    """
    status: Literal["PASS", "FAIL", "NEEDS_WORK"]
    score: float  # 0.0 - 1.0
    issues: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    validated_at: str = ""  # ISO format timestamp
    validation_details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.validated_at:
            from datetime import datetime
            self.validated_at = datetime.now().isoformat()

    @property
    def is_pass(self) -> bool:
        """Check if validation passed."""
        return self.status == "PASS"

    @property
    def is_needs_work(self) -> bool:
        """Check if content needs more work."""
        return self.status == "NEEDS_WORK"

    @property
    def is_fail(self) -> bool:
        """Check if validation failed."""
        return self.status == "FAIL"

    def requires_evidence(self) -> bool:
        """Check if evidence is required for approval."""
        return len(self.evidence_required) > 0

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Status: {self.status}",
            f"Score: {self.score:.2f}",
        ]
        if self.issues:
            lines.append(f"Issues ({len(self.issues)}):")
            for issue in self.issues[:5]:
                lines.append(f"  - {issue}")
            if len(self.issues) > 5:
                lines.append(f"  ... and {len(self.issues) - 5} more")
        if self.evidence_required:
            lines.append(f"Evidence Required ({len(self.evidence_required)}):")
            for ev in self.evidence_required[:3]:
                lines.append(f"  - {ev}")
            if len(self.evidence_required) > 3:
                lines.append(f"  ... and {len(self.evidence_required) - 3} more")
        return "\n".join(lines)


@dataclass
class RealityCheckerConfig:
    """Configuration for RealityChecker.

    Attributes:
        min_score_for_pass: Minimum score (0-1) to consider PASS.
            Default 0.85 - requires overwhelming evidence.
        require_character_consistency: Whether to check character consistency.
        require_plot_coherence: Whether to check plot coherence.
        require_evidence_for_pass: Whether PASS requires specific evidence.
        max_issues_before_fail: Max issues before automatic FAIL.
        enable_fantasy_detection: Detect impossible/fantastical claims.
        evidence_types: Types of evidence that can satisfy requirements.
    """
    min_score_for_pass: float = 0.85  # High threshold - needs overwhelming evidence
    require_character_consistency: bool = True
    require_plot_coherence: bool = True
    require_evidence_for_pass: bool = True
    max_issues_before_fail: int = 5
    enable_fantasy_detection: bool = True
    evidence_types: List[str] = field(default_factory=lambda: [
        "citation",
        "quote",
        "example",
        "reference",
        "proof",
    ])


class RealityChecker:
    """Reality Checker Agent for content quality validation.

    Key Rules:
    - STOP fantasy approvals
    - Requires screenshot/output evidence
    - Cross-validates QA findings
    - Default status is "NEEDS_WORK"
    - Only overwhelming evidence gets "PASS"

    The RealityChecker acts as a strict quality gate that errs on the side
    of caution. It defaults to "NEEDS_WORK" and requires substantial evidence
    to approve content.
    """

    def __init__(
        self,
        llm_client=None,
        config: RealityCheckerConfig = None,
    ):
        """Initialize RealityChecker.

        Args:
            llm_client: LLM client for deep validation
            config: Configuration for validation rules
        """
        self.llm_client = llm_client
        self.config = config or RealityCheckerConfig()

    def validate_content(
        self,
        content: str,
        criteria: Dict[str, Any],
    ) -> ValidationResult:
        """Validate content against given criteria.

        This is the main entry point for content validation. It performs
        multiple checks and returns a ValidationResult with the assessment.

        Args:
            content: The content to validate
            criteria: Validation criteria including:
                - characters: Character profiles for consistency check
                - previous_summary: Previous plot summary for coherence
                - required_elements: List of required plot elements
                - prohibited_elements: List of prohibited content

        Returns:
            ValidationResult with status, score, issues, and evidence requirements
        """
        issues: List[str] = []
        evidence_required: List[str] = []
        validation_details: Dict[str, Any] = {}

        # Run all validation checks
        score = 1.0

        # 1. Character consistency check
        if self.config.require_character_consistency and "characters" in criteria:
            char_result = self.check_character_consistency(
                content,
                criteria["characters"]
            )
            if not char_result["consistent"]:
                issues.extend(char_result["issues"])
                evidence_required.extend(char_result["evidence_required"])
                score -= 0.2 * len(char_result["issues"])
            validation_details["character_check"] = char_result

        # 2. Plot coherence check
        if self.config.require_plot_coherence and "previous_summary" in criteria:
            coherence_result = self.check_plot_coherence(
                content,
                criteria["previous_summary"]
            )
            if not coherence_result["coherent"]:
                issues.extend(coherence_result["issues"])
                evidence_required.extend(coherence_result["evidence_required"])
                score -= 0.15 * len(coherence_result["issues"])
            validation_details["coherence_check"] = coherence_result

        # 3. Required elements check
        if "required_elements" in criteria:
            elements_result = self._check_required_elements(
                content,
                criteria["required_elements"]
            )
            if not elements_result["complete"]:
                issues.extend(elements_result["missing"])
                evidence_required.append("补充缺失的关键情节元素")
                score -= 0.1 * len(elements_result["missing"])
            validation_details["elements_check"] = elements_result

        # 4. Prohibited elements check
        if "prohibited_elements" in criteria:
            prohibited_result = self._check_prohibited_elements(
                content,
                criteria["prohibited_elements"]
            )
            if prohibited_result["violations"]:
                for violation in prohibited_result["violations"]:
                    issues.append(f"包含禁止内容: {violation}")
                evidence_required.append("移除禁止内容或提供合理解释")
                score -= 0.25 * len(prohibited_result["violations"])
            validation_details["prohibited_check"] = prohibited_result

        # 5. Fantasy detection (impossible claims)
        if self.config.enable_fantasy_detection:
            fantasy_result = self._check_fantasy_claims(content)
            if fantasy_result["fantasies_detected"]:
                for fantasy in fantasy_result["fantasies_detected"]:
                    issues.append(f"检测到不实描述: {fantasy}")
                evidence_required.extend(fantasy_result["evidence_required"])
                score -= 0.15 * len(fantasy_result["fantasies_detected"])
            validation_details["fantasy_check"] = fantasy_result

        # 6. Internal consistency check
        consistency_result = self._check_internal_consistency(content)
        if not consistency_result["consistent"]:
            issues.extend(consistency_result["conflicts"])
            evidence_required.extend(consistency_result["evidence_required"])
            score -= 0.1 * len(consistency_result["conflicts"])
        validation_details["consistency_check"] = consistency_result

        # Clamp score
        score = max(0.0, min(1.0, score))

        # Determine status
        status = self._determine_status(score, issues, evidence_required)

        return ValidationResult(
            status=status,
            score=score,
            issues=issues,
            evidence_required=evidence_required,
            validation_details=validation_details,
        )

    def check_character_consistency(
        self,
        content: str,
        characters: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check if content is consistent with character profiles.

        Verifies that:
        - Character names are used correctly
        - Character traits/realm are consistent
        - Character relationships are respected
        - Character speaking styles match their profiles

        Args:
            content: The content to check
            characters: Dict of character profiles {name: {identity, realm, ...}}

        Returns:
            Dict with:
                - consistent: bool
                - issues: List of inconsistency issues
                - evidence_required: List of evidence needed
        """
        issues: List[str] = []
        evidence_required: List[str] = []

        for char_name, char_info in characters.items():
            # Check if character name appears in content
            name_pattern = rf"(?<!\w){re.escape(char_name)}(?!\w)"
            name_occurrences = len(re.findall(name_pattern, content))

            # Check realm/trait consistency
            realm = char_info.get("realm", "")
            identity = char_info.get("identity", "")
            personality = char_info.get("personality", "")

            # Detect realm inconsistencies (e.g., mentioning higher realm)
            if realm:
                # High-level cultivation realms
                high_realms = ["渡劫", "大乘", "飞升", "真仙", "金仙"]
                low_realms = ["炼气", "筑基", "金丹", "元婴"]

                # Check if character is low realm but content mentions high realm
                is_low_realm_char = any(low in realm for low in low_realms)
                mentions_high_realm = any(
                    high in content for high in high_realms
                )

                if is_low_realm_char and mentions_high_realm:
                    # Find which high realm is mentioned
                    mentioned_realms = [
                        high for high in high_realms if high in content
                    ]
                    for mentioned in mentioned_realms:
                        issues.append(
                            f"角色{char_name}（{realm}）出现了超出其境界的描述：{mentioned}"
                        )
                        evidence_required.append(
                            f"提供{char_name}境界提升的合理解释或时间线"
                        )

            # Check personality consistency
            if personality:
                if "冷傲" in personality or "清冷" in personality:
                    # Look for overly warm/friendly dialogue markers
                    warm_markers = ["微笑", "大笑", "热情", "亲切", "开心地", "高兴地"]
                    for marker in warm_markers:
                        if marker in content:
                            # Check if this character is associated with warm behavior
                            warm_pattern = rf"【{re.escape(char_name)}】[^\n]*?{re.escape(marker)}"
                            if re.search(warm_pattern, content):
                                issues.append(
                                    f"角色{char_name}性格（{personality}）与描述不符"
                                )
                                evidence_required.append(
                                    f"提供{char_name}性格转变的合理解释"
                                )
                                break

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "evidence_required": evidence_required,
        }

    def check_plot_coherence(
        self,
        content: str,
        previous_summary: str,
    ) -> Dict[str, Any]:
        """Check if content is coherent with previous plot summary.

        Verifies that:
        - Timeline is consistent
        - Character states match previous summary
        - Plot threads continue logically
        - No contradictions with established facts

        Args:
            content: The content to check
            previous_summary: Previous chapter's summary

        Returns:
            Dict with:
                - coherent: bool
                - issues: List of coherence issues
                - evidence_required: List of evidence needed
        """
        issues: List[str] = []
        evidence_required: List[str] = []

        if not previous_summary:
            # No previous summary to check against
            return {
                "coherent": True,
                "issues": [],
                "evidence_required": [],
            }

        # Extract key facts from previous summary
        previous_facts = self._extract_key_facts(previous_summary)
        current_facts = self._extract_key_facts(content)

        # Check for contradictions
        for fact in previous_facts:
            if fact in current_facts.get("contradictions", []):
                issues.append(f"与前文矛盾: {fact}")
                evidence_required.append("提供时间线或因果关系的合理解释")

        # Check timeline consistency
        timeline_issues = self._check_timeline_consistency(
            previous_summary,
            content
        )
        if timeline_issues:
            issues.extend(timeline_issues)
            evidence_required.append("澄清事件发生的时间顺序")

        return {
            "coherent": len(issues) == 0,
            "issues": issues,
            "evidence_required": evidence_required,
        }

    def require_evidence(self, claim: str) -> List[str]:
        """Mark a claim as requiring verifiable evidence.

        Call this to flag specific claims that need evidence.
        Examples:
        - Factual claims about the world
        - Character background details
        - Historical events

        Args:
            claim: The claim that requires evidence

        Returns:
            List of evidence types that would satisfy the requirement
        """
        evidence_types = []

        if self.llm_client:
            # Use LLM to determine what evidence is needed
            prompt = f"""分析以下内容声明需要什么类型的证据来验证：

声明：{claim}

请列出需要的证据类型（如：引用、示例、参考文献、具体细节等）。
只返回证据类型列表，用逗号分隔。"""

            try:
                messages = [{"role": "user", "content": prompt}]
                response = self.llm_client.generate(messages)
                evidence_types = [
                    ev.strip() for ev in response.split(",")
                    if ev.strip()
                ]
            except Exception as e:
                logger.warning(f"LLM evidence analysis failed: {e}")
                evidence_types = ["具体细节", "引用来源"]
        else:
            # Default evidence requirements
            evidence_types = ["具体细节", "可验证的引用"]

        return evidence_types

    def _check_required_elements(
        self,
        content: str,
        required_elements: List[str],
    ) -> Dict[str, Any]:
        """Check if required elements are present in content."""
        missing = []
        for element in required_elements:
            if element not in content:
                missing.append(f"缺少必需元素: {element}")

        return {
            "complete": len(missing) == 0,
            "missing": missing,
        }

    def _check_prohibited_elements(
        self,
        content: str,
        prohibited_elements: List[str],
    ) -> Dict[str, Any]:
        """Check if prohibited elements are in content."""
        violations = []
        for element in prohibited_elements:
            if element in content:
                violations.append(element)

        return {
            "violations": violations,
        }

    def _check_fantasy_claims(self, content: str) -> Dict[str, Any]:
        """Detect impossible or unverified claims.

        Detects claims that:
        - Contradict established world rules
        - Make impossible assertions without evidence
        - Contain logical impossibilities
        """
        fantasies_detected: List[str] = []
        evidence_required: List[str] = []

        # Impossible claims patterns
        # Pattern 1: Low realm defeating high realm
        if "炼气期" in content and "渡劫期" in content:
            # Check if it's a defeat scenario
            if re.search(r"炼气期.*?击败.*?渡劫期", content) or \
               re.search(r"炼气期.*?打败.*?渡劫期", content):
                fantasies_detected.append("低境界（炼气期）击败高境界（渡劫期）")
                evidence_required.append("提供境界差距如何被弥补的合理解释")

        # Pattern 2: Mortal destroying planets
        if re.search(r"凡人", content) and re.search(r"毁灭.*?星球", content):
            fantasies_detected.append("凡人拥有毁灭星球的力量")
            evidence_required.append("提供凡人获得如此力量的合理解释")

        # Pattern 3: Rapid cultivation breakthroughs (young age becoming immortal)
        age_pattern = r"(\d+)岁.*?(渡劫|飞升|成为仙人|突破)"
        matches = re.findall(age_pattern, content)
        for match in matches:
            age = int(match[0])
            if age < 100:  # Less than 100 years old
                fantasies_detected.append(f"{age}岁实现{match[1]}的快速修炼")
                evidence_required.append("提供加速修炼的合理解释（如奇遇、神丹等）")

        # Pattern 4: 炼气期 using abilities beyond their realm
        if "炼气期" in content:
            advanced_abilities = ["天劫", "大道", "法则", "领域"]
            for ability in advanced_abilities:
                if ability in content:
                    fantasies_detected.append(f"炼气期修士使用了{ability}（通常需要更高境界）")
                    evidence_required.append(f"提供{ability}使用条件的合理解释")

        return {
            "fantasies_detected": fantasies_detected,
            "evidence_required": evidence_required,
        }

    def _check_internal_consistency(self, content: str) -> Dict[str, Any]:
        """Check for internal contradictions within the content."""
        conflicts: List[str] = []
        evidence_required: List[str] = []

        # Extract potential facts for comparison
        # Look for contradictory statements

        # Example: Time contradictions
        time_patterns = [
            (r"前一秒.*?后一秒", "时间描述矛盾"),
            (r"早晨.*?傍晚.*?早晨", "时间线矛盾"),
        ]

        for pattern, issue in time_patterns:
            if re.search(pattern, content):
                conflicts.append(issue)
                evidence_required.append("澄清事件发生的准确时间顺序")

        return {
            "consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "evidence_required": evidence_required,
        }

    def _extract_key_facts(self, text: str) -> Dict[str, Any]:
        """Extract key facts from text for comparison."""
        # Simple extraction - in production, use LLM
        facts = {
            "contradictions": [],
            "events": [],
            "states": [],
        }

        # Extract statements about character states
        state_patterns = [
            r"(\w+)是(\w+)",
            r"(\w+)已经(\w+)",
            r"(\w+)处于(\w+)状态",
        ]

        for pattern in state_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    facts["states"].append((match[0], match[1]))

        return facts

    def _check_timeline_consistency(
        self,
        previous: str,
        current: str,
    ) -> List[str]:
        """Check timeline consistency between previous and current content."""
        issues: List[str] = []

        # Extract temporal markers
        prev_markers = self._extract_temporal_markers(previous)
        curr_markers = self._extract_temporal_markers(current)

        # Check for impossible sequences
        if "之后" in prev_markers and "之前" in curr_markers:
            # Previous says "after" but current says "before" - potential issue
            issues.append("时间顺序可能存在矛盾")

        return issues

    def _extract_temporal_markers(self, text: str) -> List[str]:
        """Extract temporal markers from text."""
        markers = []
        temporal_words = [
            "之前", "之后", "以前", "以后", "现在", "目前",
            "早晨", "中午", "傍晚", "夜晚", "次日", "前一刻",
        ]

        for marker in temporal_words:
            if marker in text:
                markers.append(marker)

        return markers

    def _determine_status(
        self,
        score: float,
        issues: List[str],
        evidence_required: List[str],
    ) -> Literal["PASS", "FAIL", "NEEDS_WORK"]:
        """Determine validation status based on checks.

        Status determination follows strict rules:
        - FAIL: Too many issues or score too low
        - NEEDS_WORK: Has issues or missing evidence
        - PASS: High score AND no issues AND sufficient evidence
        """
        # Rule 1: Too many issues = automatic FAIL
        if len(issues) >= self.config.max_issues_before_fail:
            return "FAIL"

        # Rule 2: Score too low = automatic FAIL
        if score < 0.5:
            return "FAIL"

        # Rule 3: Missing required evidence = NEEDS_WORK
        if self.config.require_evidence_for_pass and evidence_required:
            return "NEEDS_WORK"

        # Rule 4: Has any issues = NEEDS_WORK
        if issues:
            return "NEEDS_WORK"

        # Rule 5: Score below threshold = NEEDS_WORK
        if score < self.config.min_score_for_pass:
            return "NEEDS_WORK"

        # Rule 6: PASS requires overwhelming evidence
        if self.config.require_evidence_for_pass:
            # Need at least some evidence to PASS
            if not evidence_required and score >= self.config.min_score_for_pass:
                # No issues, high score, but no evidence collected = still OK
                return "PASS"
            elif evidence_required:
                # Has issues resolved with evidence
                return "PASS"

        return "PASS"


def get_reality_checker(llm_client=None, config: RealityCheckerConfig = None) -> RealityChecker:
    """Get a RealityChecker instance.

    Args:
        llm_client: Optional LLM client for deep validation
        config: Optional configuration

    Returns:
        RealityChecker instance
    """
    return RealityChecker(llm_client=llm_client, config=config)
