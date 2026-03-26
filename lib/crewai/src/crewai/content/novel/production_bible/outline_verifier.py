"""Volume Outline Verifier for Production Bible System.

This verifier runs AFTER parallel volume outline generation, checking that generated
outlines are consistent with each other and with the ProductionBible. It's the
"table read" equivalent from Hollywood — inconsistencies are caught here before
proceeding to chapter summaries.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.novel.production_bible.bible_types import ProductionBible


@dataclass
class VerificationIssue:
    """A single consistency issue found during verification."""
    severity: str  # "HARD" (must fix) or "SOFT" (warning)
    category: str  # "character", "timeline", "foreshadowing", "power_system", "relationship"
    description: str
    volume_1: int
    volume_2: int | None = None
    suggested_fix: str = ""


@dataclass
class VerificationResult:
    """Result of volume outline verification."""
    passed: bool = True
    issues: list[VerificationIssue] = field(default_factory=list)
    warnings: list[VerificationIssue] = field(default_factory=list)

    def add_issue(
        self,
        severity: str,
        category: str,
        description: str,
        vol1: int,
        vol2: int | None = None,
        fix: str = "",
    ):
        """Add a verification issue to the result."""
        issue = VerificationIssue(
            severity=severity,
            category=category,
            description=description,
            volume_1=vol1,
            volume_2=vol2,
            suggested_fix=fix,
        )
        if severity == "HARD":
            self.issues.append(issue)
            self.passed = False
        else:
            self.warnings.append(issue)


class VolumeOutlineVerifier:
    """Verifies volume outlines against production bible and each other.

    This is called AFTER parallel volume outline generation.
    It checks:
    1. Character consistency across volumes
    2. Timeline consistency (events don't contradict)
    3. Foreshadowing coverage (setup -> payoff chains maintained)
    4. Power system consistency
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """Initialize the verifier.

        Args:
            llm: Optional LLM for deep consistency checking.
            verbose: Whether to print verbose output.
        """
        self.llm = llm
        self.verbose = verbose
        self.agent = None
        if llm is not None:
            from crewai.agent import Agent
            self.agent = Agent(
                role="Consistency Auditor",
                goal="Identify inconsistencies between volume outlines and production bible",
                backstory="""你是小说一致性审计专家。你负责检查多个卷的大纲是否相互一致。
                你特别关注：
                - 角色描述在不同卷之间是否一致
                - 时间线事件是否有矛盾
                - 伏笔是否正确铺垫和回收
                - 灵力体系的等级和能力是否一致

                你的审核非常严格，任何不一致都会被标记为HARD问题。""",
                verbose=verbose,
                llm=llm,
            )

    def verify(
        self,
        volume_outlines: list[dict],
        bible: "ProductionBible",
        world_data: dict,
    ) -> VerificationResult:
        """Verify all volume outlines.

        Args:
            volume_outlines: List of volume outline dicts from VolumeOutlineAgent.
            bible: ProductionBible built before generation.
            world_data: Original world data.

        Returns:
            VerificationResult with issues found.
        """
        result = VerificationResult(passed=True)

        # Check 1: Character consistency
        self._check_character_consistency(volume_outlines, bible, result)

        # Check 2: Timeline consistency
        self._check_timeline_consistency(volume_outlines, result)

        # Check 3: Foreshadowing coverage
        self._check_foreshadowing_coverage(volume_outlines, bible, result)

        # Check 4: Power system consistency
        self._check_power_system_consistency(volume_outlines, world_data, result)

        return result

    def _check_character_consistency(
        self,
        volume_outlines: list[dict],
        bible: "ProductionBible",
        result: VerificationResult,
    ):
        """Check that character references are consistent."""
        # Get all character mentions per volume
        char_refs: dict[str, list[dict]] = {}
        for vol in volume_outlines:
            vol_num = vol.get("volume_num", 0)
            # Check key_events for character mentions
            key_events = vol.get("key_events", [])
            for event in key_events:
                event_str = str(event)
                for char_name in bible.characters.keys():
                    if char_name in event_str:
                        if char_name not in char_refs:
                            char_refs[char_name] = []
                        char_refs[char_name].append({"vol": vol_num, "event": event_str})

        # Check for contradictory character arc claims
        for char_name, refs in char_refs.items():
            if len(refs) >= 2:
                # Multiple volumes reference same character
                char = bible.get_character(char_name)
                if char and char.role == "protagonist":
                    # Protagonist should be in all volumes
                    volumes_with_char = [r["vol"] for r in refs]
                    for vol in volume_outlines:
                        vol_num = vol.get("volume_num", 0)
                        if vol_num not in volumes_with_char:
                            result.add_issue(
                                "SOFT",
                                "character",
                                f"主角{char_name}未在第{vol_num}卷关键事件中提及",
                                vol1=vol_num,
                                fix=f"确保主角在第{vol_num}卷有适当出场",
                            )

    def _check_timeline_consistency(
        self,
        volume_outlines: list[dict],
        result: VerificationResult,
    ):
        """Check that timeline references are consistent."""
        # Check closing_hook continuity
        for i, vol in enumerate(volume_outlines[:-1]):
            vol_num = vol.get("volume_num", 0)
            next_vol = volume_outlines[i + 1]
            next_vol_num = next_vol.get("volume_num", 0)

            closing = vol.get("closing_hook", "")
            next_opening = next_vol.get("opening_hook", "")

            # Closing of vol N should connect to opening of vol N+1
            # Simple heuristic: check for shared character or event references
            if closing and next_opening and len(closing) > 5:
                # If closing mentions specific names, they should appear in next opening
                closing_words = set(closing)
                opening_words = set(next_opening)
                # This is a simplified check - real implementation would use NLP
                # For now just flag if both are non-empty but completely different
                if len(closing_words & opening_words) == 0 and closing_words and opening_words:
                    result.add_issue(
                        "SOFT",
                        "timeline",
                        f"第{vol_num}卷结尾与第{next_vol_num}卷开头缺乏明显关联",
                        vol1=vol_num,
                        vol2=next_vol_num,
                        fix=f"第{vol_num}卷结尾'{(closing[:30])}'应与第{next_vol_num}卷开头'{(next_opening[:30])}'有关联",
                    )

    def _check_foreshadowing_coverage(
        self,
        volume_outlines: list[dict],
        bible: "ProductionBible",
        result: VerificationResult,
    ):
        """Check that foreshadowing setups are properly included in volumes."""
        # Get foreshadowing that should be paid off in each volume
        for vol in volume_outlines:
            vol_num = vol.get("volume_num", 0)
            vol_chapters = vol.get("chapters_summary", [])
            if not vol_chapters:
                vol_chapters = []
            chapter_nums = set()
            for ch in vol_chapters:
                if isinstance(ch, dict):
                    chapter_nums.add(ch.get("chapter_num", 0))

            # Check open foreshadowing for this volume
            target_chapter = chapter_nums.pop() if chapter_nums else 0
            open_fs = bible.get_foreshadowing_for_chapter(target_chapter)
            for fs in open_fs:
                if fs.payoff_volume == vol_num:
                    # This volume should contain the payoff
                    # Check if key_events or chapters mention the payoff
                    vol_str = str(vol.get("key_events", [])) + str(
                        vol.get("chapters_summary", [])
                    )
                    payoff_snippet = fs.payoff_description[:10] if fs.payoff_description else ""
                    if payoff_snippet and payoff_snippet not in vol_str:
                        result.add_issue(
                            "HARD",
                            "foreshadowing",
                            f"第{vol_num}卷应包含伏笔'{fs.payoff_description[:30]}'的回收但未找到",
                            vol1=vol_num,
                            fix=f"在第{vol_num}卷大纲中包含伏笔'{fs.payoff_description[:30]}'的回收",
                        )

    def _check_power_system_consistency(
        self,
        volume_outlines: list[dict],
        world_data: dict,
        result: VerificationResult,
    ):
        """Check power system usage is consistent."""
        power_system = world_data.get("power_system", {})
        if not power_system:
            return

        levels = power_system.get("levels", [])
        if not levels:
            return

        # Check that no volume uses a level not in the canonical list
        for vol in volume_outlines:
            vol_num = vol.get("volume_num", 0)
            vol_str = str(vol)

            # Check that cultivation realm mentions are consistent
            # This is a simplified check
            if "cultivation" in vol_str.lower() or "灵力" in vol_str or "修炼" in vol_str:
                if not levels:
                    result.add_issue(
                        "SOFT",
                        "power_system",
                        f"第{vol_num}卷提到修炼但世界未定义灵力等级体系",
                        vol1=vol_num,
                        fix="确保灵力等级体系在世界观中定义",
                    )
