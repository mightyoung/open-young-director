"""BackboneValidator: adoption-rate validator for classical backbone events.

Checks that a set of BackboneMapping objects (produced by BackboneMapper) covers
a sufficient fraction of the reference events extracted from classical_backbones.json.

Typical usage::

    validator = BackboneValidator(threshold=0.7, min_confidence=0.5)
    reference_events = BackboneValidator.load_reference_events(
        backbone_path="/path/to/classical_backbones.json",
        work_name="西游记",
    )
    result = validator.validate(mappings, reference_events)
    print(validator.format_report(result))
    for hint in validator.suggest_improvements(result):
        print(hint)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data contracts
# ---------------------------------------------------------------------------

_ARCHETYPE_SUGGESTIONS: dict[str, str] = {
    "hero_call":       '可将「召唤英雄」原型改编为主角收到任务/使命的开篇段落。',
    "mentor":          '可将「导师」原型改编为引导主角成长的关键人物或奇遇。',
    "threshold":       '可将「跨越门槛」原型改编为主角离开安全区、进入危险世界的转折。',
    "trial":           '可将「试炼」原型改编为主角面对强敌或内心考验的关键章节。',
    "revelation":      '可将「揭示真相」原型改编为颠覆读者预期的中期反转。',
    "transformation":  '可将「蜕变」原型改编为主角突破瓶颈、实力飞跃的高燃节点。',
    "atonement":       '可将「赎罪/和解」原型改编为主角与过去和解、化解宿怨的情感线。',
    "return":          '可将「归来」原型改编为主角荣归或重返故地的圆满收束。',
    "trickster":       '可将「恶作剧者」原型改编为搅动格局、打破平衡的搞笑/反派副线。',
    "shadow":          '可将「阴影」原型改编为主角内心恐惧的外化或隐藏反派的登场。',
    "ally":            '可将「同伴」原型改编为关键盟友在危难时刻伸出援手的场面。',
    "ordeal":          '可将「磨难」原型改编为九死一生、逼出主角潜能的生死关头。',
    "reward":          '可将「奖励」原型改编为主角历经苦难后获得秘宝或突破的爽感段落。',
    "road_back":       '可将「归途」原型改编为主角踏上终局决战前的最后准备。',
    "climax":          '可将「高潮决战」原型改编为全书最大冲突爆发的终极对决。',
    "resolution":      '可将「尾声」原型改编为余韵悠长的结局章节，留下开放式或升华感。',
}

_DEFAULT_SUGGESTION = "可将该事件改编为推动主线、深化主题或丰富人物弧线的关键场景。"


@dataclass
class BackboneMapping:
    """A single reference event → novel event mapping produced by BackboneMapper."""

    reference_event_name: str
    reference_event_content: str
    novel_event_name: str
    novel_chapter: int
    mapping_confidence: float  # 0.0 to 1.0
    spiritual_core: str  # thematic essence preserved


@dataclass
class ValidationResult:
    """Result of a backbone adoption validation run."""

    total_reference_events: int
    mapped_events: int
    adoption_rate: float  # 0.0 to 1.0
    passed: bool
    threshold: float
    unmapped_events: list[str]  # reference event names with no qualifying mapping
    low_confidence_mappings: list[BackboneMapping]  # 0 < confidence < min_confidence
    details: str  # human-readable one-liner


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


@dataclass
class BackboneValidator:
    """Validates that a novel outline adopts a sufficient fraction of reference backbone events.

    A mapping is considered "adopted" when its ``mapping_confidence`` is at or above
    ``min_confidence``.  The adoption rate is ``adopted_count / total_reference_events``.
    The validation passes when ``adoption_rate >= threshold``.

    Args:
        threshold:      Minimum required adoption rate (default 0.70 = 70 %).
        min_confidence: Minimum confidence for a mapping to count as adopted
                        (default 0.50).
    """

    threshold: float = 0.7
    min_confidence: float = 0.5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(
        self,
        mappings: list[BackboneMapping],
        reference_events: list[dict[str, Any]],
    ) -> ValidationResult:
        """Check backbone adoption rate against the configured threshold.

        Args:
            mappings:         List of BackboneMapping objects from BackboneMapper.
            reference_events: List of event dicts loaded from classical_backbones.json
                              (each has at least ``name`` and ``content`` keys).

        Returns:
            A :class:`ValidationResult` describing whether the outline passes.
        """
        total = len(reference_events)
        if total == 0:
            logger.warning("[backbone_validator] No reference events provided; skipping validation.")
            return ValidationResult(
                total_reference_events=0,
                mapped_events=0,
                adoption_rate=1.0,
                passed=True,
                threshold=self.threshold,
                unmapped_events=[],
                low_confidence_mappings=[],
                details="无参考事件，跳过骨架采纳率验证。",
            )

        # Index mappings by reference event name for O(1) look-up.
        # A reference event may appear in multiple mappings; keep the highest-confidence one.
        best_confidence: dict[str, float] = {}
        low_confidence: list[BackboneMapping] = []

        for m in mappings:
            key = m.reference_event_name
            prev = best_confidence.get(key, -1.0)
            if m.mapping_confidence > prev:
                best_confidence[key] = m.mapping_confidence

        # Identify mappings that are present but below the confidence bar.
        seen_ref_names: set[str] = {m.reference_event_name for m in mappings}
        for m in mappings:
            if 0.0 < m.mapping_confidence < self.min_confidence:
                low_confidence.append(m)

        # Remove duplicates from low_confidence (keep one entry per reference event).
        _seen: set[str] = set()
        deduped_low: list[BackboneMapping] = []
        for m in low_confidence:
            if m.reference_event_name not in _seen:
                deduped_low.append(m)
                _seen.add(m.reference_event_name)

        # Count adopted events (confidence >= min_confidence).
        ref_names_in_data: list[str] = [
            _extract_event_name(ev) for ev in reference_events
        ]
        unmapped: list[str] = []
        adopted_count = 0

        for ref_name in ref_names_in_data:
            conf = best_confidence.get(ref_name)
            if conf is not None and conf >= self.min_confidence:
                adopted_count += 1
            else:
                unmapped.append(ref_name)

        adoption_rate = adopted_count / total
        passed = adoption_rate >= self.threshold

        details = (
            f"共{total}个参考事件，已采纳{adopted_count}个"
            f"（采纳率{adoption_rate:.1%}），"
            + ("通过验证。" if passed else f"未达到阈值{self.threshold:.0%}，需补充映射。")
        )

        logger.info("[backbone_validator] %s", details)

        return ValidationResult(
            total_reference_events=total,
            mapped_events=adopted_count,
            adoption_rate=adoption_rate,
            passed=passed,
            threshold=self.threshold,
            unmapped_events=unmapped,
            low_confidence_mappings=deduped_low,
            details=details,
        )

    def format_report(self, result: ValidationResult) -> str:
        """Format a ValidationResult as a human-readable Chinese report.

        Args:
            result: The :class:`ValidationResult` to format.

        Returns:
            A multi-line string containing adoption rate, unmapped events, and
            low-confidence warnings.
        """
        lines: list[str] = []
        lines.append("=" * 50)
        lines.append("【骨架采纳率验证报告】")
        lines.append("=" * 50)

        # Summary row
        status_tag = "✓ 通过" if result.passed else "✗ 未通过"
        lines.append(
            f"状态      : {status_tag}"
        )
        lines.append(
            f"采纳率    : {result.adoption_rate:.1%}"
            f"  （{result.mapped_events} / {result.total_reference_events} 个参考事件）"
        )
        lines.append(
            f"合格阈值  : {result.threshold:.0%}"
        )
        lines.append(
            f"最低置信度: {self.min_confidence:.0%}"
        )
        lines.append("")

        # Unmapped events
        if result.unmapped_events:
            lines.append(f"▶ 未映射事件（共 {len(result.unmapped_events)} 个）：")
            for name in result.unmapped_events:
                lines.append(f"  - {name}")
        else:
            lines.append("▶ 所有参考事件均已映射。")
        lines.append("")

        # Low-confidence warnings
        if result.low_confidence_mappings:
            lines.append(f"⚠ 低置信度映射（共 {len(result.low_confidence_mappings)} 个，置信度 < {self.min_confidence:.0%}）：")
            for m in result.low_confidence_mappings:
                lines.append(
                    f"  - 参考事件「{m.reference_event_name}」→ 小说事件「{m.novel_event_name}」"
                    f"（第{m.novel_chapter}章，置信度 {m.mapping_confidence:.0%}）"
                )
                if m.spiritual_core:
                    lines.append(f"    精神内核: {m.spiritual_core}")
        else:
            lines.append("▶ 无低置信度映射。")
        lines.append("")

        # Footer
        lines.append(result.details)
        lines.append("=" * 50)
        return "\n".join(lines)

    def suggest_improvements(self, result: ValidationResult) -> list[str]:
        """Suggest actionable improvements for unmapped reference events.

        Generates a list of concrete adaptation hints based on the archetype
        associated with each unmapped event (if available) or a generic fallback.

        Args:
            result: The :class:`ValidationResult` containing unmapped events.

        Returns:
            A list of suggestion strings, one per unmapped event.
        """
        if not result.unmapped_events:
            return ["所有参考事件已充分映射，无需额外改进。"]

        suggestions: list[str] = []
        for event_name in result.unmapped_events:
            archetype_key = _infer_archetype_key(event_name)
            hint = _ARCHETYPE_SUGGESTIONS.get(archetype_key, _DEFAULT_SUGGESTION)
            suggestions.append(f"「{event_name}」: {hint}")

        # Add a general note when adoption rate is critically low.
        if result.adoption_rate < 0.5:
            suggestions.append(
                "整体采纳率不足50%，建议系统性回顾大纲结构，"
                "确保主干情节与参考骨架的核心叙事节奏对齐。"
            )

        return suggestions

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_reference_events(backbone_path: str, work_name: str) -> list[dict[str, Any]]:
        """Load backbone events for a specific work from classical_backbones.json.

        Args:
            backbone_path: Absolute path to ``classical_backbones.json``.
            work_name:     Key inside the JSON (e.g. "西游记").

        Returns:
            List of event dicts (``order``, ``name``, ``content``, ``archetype``).
            Returns an empty list if the work is not found.
        """
        with open(backbone_path, "r", encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        work = data.get(work_name, {})
        events: list[dict[str, Any]] = work.get("backbone_events", [])

        if not events:
            logger.warning(
                "[backbone_validator] No backbone_events found for work=%r in %s",
                work_name,
                backbone_path,
            )

        return events


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_event_name(event: dict[str, Any]) -> str:
    """Return the canonical name string from a backbone event dict."""
    return event.get("name") or event.get("event_name") or str(event.get("order", ""))


def _infer_archetype_key(event_name: str) -> str:
    """Map a reference event name to a known archetype key for suggestion lookup.

    Uses keyword matching against the event name (Chinese or English).
    Falls back to empty string when no match is found.
    """
    name_lower = event_name.lower()

    keyword_map: list[tuple[list[str], str]] = [
        (["召唤", "使命", "call", "mission", "任务"], "hero_call"),
        (["导师", "师父", "引导", "mentor", "guide"], "mentor"),
        (["出发", "离开", "门槛", "threshold", "departure"], "threshold"),
        (["试炼", "考验", "磨难", "trial", "ordeal", "test"], "trial"),
        (["揭示", "真相", "revelation", "reveal", "secret"], "revelation"),
        (["蜕变", "突破", "transformation", "breakthrough", "ascend"], "transformation"),
        (["赎罪", "和解", "atonement", "reconcile", "forgive"], "atonement"),
        (["归来", "回归", "return", "homecoming"], "return"),
        (["恶作剧", "搅局", "trickster", "chaos", "fool"], "trickster"),
        (["阴影", "恐惧", "shadow", "dark", "villain"], "shadow"),
        (["同伴", "盟友", "ally", "companion", "friend"], "ally"),
        (["奖励", "宝物", "reward", "treasure", "prize"], "reward"),
        (["归途", "road", "return journey", "最后准备"], "road_back"),
        (["高潮", "决战", "climax", "final battle", "boss"], "climax"),
        (["尾声", "结局", "resolution", "ending", "epilogue"], "resolution"),
    ]

    for keywords, archetype in keyword_map:
        if any(kw in name_lower for kw in keywords):
            return archetype

    return ""
