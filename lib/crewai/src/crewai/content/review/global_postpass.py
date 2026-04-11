"""Global PostPass - Post-manuscript consistency verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crewai.content.memory.continuity_tracker import ContinuityTracker


@dataclass
class GlobalPostPassReport:
    """Global PostPass report"""
    character_death_issues: list[dict[str, Any]] = field(default_factory=list)
    hook_reveal_issues: list[dict[str, Any]] = field(default_factory=list)
    location_timeline_issues: list[dict[str, Any]] = field(default_factory=list)
    transition_issues: list[dict[str, Any]] = field(default_factory=list)
    overall_score: float = 100.0
    passed: bool = True

    def add_issue(self, issue_type: str, description: str, severity: str = "medium", chapter: int | None = None):
        """Add an issue to the appropriate list."""
        issue = {"description": description, "severity": severity, "chapter": chapter}
        if issue_type == "character_death":
            self.character_death_issues.append(issue)
        elif issue_type == "hook_reveal":
            self.hook_reveal_issues.append(issue)
        elif issue_type == "location_timeline":
            self.location_timeline_issues.append(issue)
        elif issue_type == "transition":
            self.transition_issues.append(issue)

        # Adjust score
        if severity == "high":
            self.overall_score -= 20.0
        elif severity == "medium":
            self.overall_score -= 10.0
        else:
            self.overall_score -= 5.0

        self.passed = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_death_issues": self.character_death_issues,
            "hook_reveal_issues": self.hook_reveal_issues,
            "location_timeline_issues": self.location_timeline_issues,
            "transition_issues": self.transition_issues,
            "overall_score": max(0.0, self.overall_score),
            "passed": self.passed,
        }


class GlobalPostPass:
    """Global PostPass - runs after all chapters are written.

    Performs consistency checks across the entire manuscript:
    - Character death: dead characters don't appear in later chapters
    - Hook/plant consistency: planted hooks are revealed at reasonable timing
    - Location timeline: location changes have narrative support
    - Transitions: chapter transitions are smooth
    """

    def __init__(self, continuity_tracker: ContinuityTracker | None = None):
        self.continuity_tracker = continuity_tracker

    def run(self, chapters: list[Any], world_data: dict[str, Any]) -> GlobalPostPassReport:
        """Run global post-pass checks.

        Args:
            chapters: List of ChapterOutput objects
            world_data: World building data

        Returns:
            GlobalPostPassReport with all issues found
        """
        report = GlobalPostPassReport()

        if not chapters:
            return report

        # 1. Character death consistency check
        self._check_character_deaths(chapters, report)

        # 2. Location timeline check
        self._check_location_timeline(chapters, report)

        # 3. Chapter transitions
        self._check_transitions(chapters, report)

        # 4. Plant/reveal (foreshadowing) check
        self._check_plant_reveal(chapters, world_data, report)

        return report

    def _check_character_deaths(self, chapters: list[Any], report: GlobalPostPassReport):
        """Check that dead characters don't appear in later chapters."""
        # Track when each character dies
        death_chapters: dict[str, int] = {}

        for chapter in chapters:
            chapter_num = chapter.chapter_num if hasattr(chapter, 'chapter_num') else chapter.get('chapter_num', 0)
            content = chapter.content if hasattr(chapter, 'content') else chapter.get('content', '')
            characters = chapter.character_appearances if hasattr(chapter, 'character_appearances') else chapter.get('character_appearances', [])

            if not characters:
                continue

            # Check for death keywords in this chapter
            death_keywords = ["死亡", "死去", "已死", "去世", "牺牲", "身亡", "被杀", "灭亡"]
            for char_name in characters:
                for keyword in death_keywords:
                    if keyword in content and char_name not in death_chapters:
                        death_chapters[char_name] = chapter_num

        # Now check each character that died appears only in their death chapter or earlier
        for char_name, death_ch in death_chapters.items():
            for chapter in chapters:
                chapter_num = chapter.chapter_num if hasattr(chapter, 'chapter_num') else chapter.get('chapter_num', 0)
                characters = chapter.character_appearances if hasattr(chapter, 'character_appearances') else chapter.get('character_appearances', [])

                if chapter_num > death_ch and char_name in characters:
                    report.add_issue(
                        "character_death",
                        f"角色 '{char_name}' 在第{death_ch}章已死亡，但出现在第{chapter_num}章",
                        severity="high",
                        chapter=chapter_num,
                    )

    def _check_location_timeline(self, chapters: list[Any], report: GlobalPostPassReport):
        """Check location changes have narrative support."""
        if not self.continuity_tracker:
            return

        chapter_texts = {
            self._chapter_number(chapter): self._chapter_content(chapter)
            for chapter in chapters
            if self._chapter_number(chapter) is not None
        }

        transfer_keywords = ("离开", "前往", "到达", "进入", "回到", "穿越", "传送", "来到", "去往")

        for entity_id, history in self.continuity_tracker.entity_state_history.items():
            if len(history) < 2:
                continue

            ordered_history = sorted(history, key=lambda state: state.chapter)
            for prev_state, curr_state in zip(ordered_history, ordered_history[1:]):
                prev_loc = prev_state.location
                curr_loc = curr_state.location
                if not prev_loc or not curr_loc or prev_loc == curr_loc:
                    continue

                chapter_num = curr_state.chapter
                current_text = chapter_texts.get(chapter_num, "")
                previous_text = chapter_texts.get(prev_state.chapter, "")

                if any(keyword in current_text for keyword in transfer_keywords):
                    continue
                if any(keyword in previous_text for keyword in transfer_keywords):
                    continue

                report.add_issue(
                    "location_timeline",
                    (
                        f"实体 '{entity_id}' 从 '{prev_loc}' 突然转移到 '{curr_loc}'，"
                        f"第{chapter_num}章缺少过渡描述"
                    ),
                    severity="medium",
                    chapter=chapter_num,
                )

    def _check_transitions(self, chapters: list[Any], report: GlobalPostPassReport):
        """Check chapter transitions are smooth."""
        for i in range(len(chapters) - 1):
            curr = chapters[i]
            next_ch = chapters[i + 1]

            curr_content = curr.content if hasattr(curr, 'content') else curr.get('content', '')
            next_content = next_ch.content if hasattr(next_ch, 'content') else next_ch.get('content', '')

            # Check last paragraph of current chapter
            last_para = curr_content[-300:] if curr_content else ""
            first_para = next_content[:300] if next_content else ""

            # Check for jarring transitions (both empty or both abrupt)
            if len(last_para) < 50 and len(first_para) < 50:
                report.add_issue(
                    "transition",
                    f"第{curr.chapter_num if hasattr(curr, 'chapter_num') else curr.get('chapter_num')}章结尾和第{next_ch.chapter_num if hasattr(next_ch, 'chapter_num') else next_ch.get('chapter_num')}章开头都过于简短，可能缺少过渡",
                    severity="low",
                    chapter=curr.chapter_num if hasattr(curr, 'chapter_num') else curr.get('chapter_num'),
                )

    def _check_plant_reveal(
        self,
        chapters: list[Any],
        world_data: dict[str, Any],
        report: GlobalPostPassReport,
    ) -> None:
        """Check foreshadowing plant/reveal consistency across all chapters.

        Detects:
        - Planted items never harvested (status still open/hinted at end)
        - Items harvested too soon (< 2 chapters after planting)
        - Items harvested too late (> 50 chapters after planting)
        """
        # Local import avoids circular dependency (novel.crews → global_postpass → novel.pipeline)
        from crewai.content.novel.pipeline.foreshadowing_board import (  # noqa: PLC0415
            ForeshadowEntry,
            ForeshadowingBoard,
        )

        # Accept a ForeshadowingBoard instance from world_data, or a list of raw entry dicts
        raw_board = world_data.get("foreshadowing_board")
        if raw_board is None:
            return

        if isinstance(raw_board, ForeshadowingBoard):
            entries: list[ForeshadowEntry] = raw_board.entries
        elif isinstance(raw_board, dict):
            entries = [ForeshadowEntry(**e) for e in raw_board.get("entries", [])]
        else:
            return

        if not entries:
            return

        last_chapter = max(
            (self._chapter_number(ch) or 0 for ch in chapters),
            default=0,
        )

        for entry in entries:
            # 1. Never harvested
            if entry.status in ("open", "hinted"):
                report.add_issue(
                    "hook_reveal",
                    (
                        f"伏笔 [{entry.id}] 第{entry.setup_chapter}章埋下"
                        f"「{entry.setup_content[:40]}」至第{last_chapter}章仍未回收"
                    ),
                    severity="medium",
                    chapter=entry.setup_chapter,
                )
                continue

            if entry.status != "harvested":
                continue

            # Determine actual payoff chapter from the expected field as best proxy
            # (ForeshadowEntry doesn't store actual_payoff_chapter; use expected_payoff_chapter)
            payoff_chapter = entry.expected_payoff_chapter
            gap = payoff_chapter - entry.setup_chapter

            # 2. Harvested too soon (< 2 chapters gap)
            if gap < 2:
                report.add_issue(
                    "hook_reveal",
                    (
                        f"伏笔 [{entry.id}] 第{entry.setup_chapter}章埋下，"
                        f"第{payoff_chapter}章即回收，间隔仅{gap}章（建议≥2章）"
                    ),
                    severity="low",
                    chapter=payoff_chapter,
                )

            # 3. Harvested too late (> 50 chapters gap)
            elif gap > 50:
                report.add_issue(
                    "hook_reveal",
                    (
                        f"伏笔 [{entry.id}] 第{entry.setup_chapter}章埋下，"
                        f"第{payoff_chapter}章才回收，间隔{gap}章（建议≤50章）"
                    ),
                    severity="medium",
                    chapter=payoff_chapter,
                )

    @staticmethod
    def _chapter_number(chapter: Any) -> int | None:
        if hasattr(chapter, "chapter_num"):
            return getattr(chapter, "chapter_num", None)
        if isinstance(chapter, dict):
            return chapter.get("chapter_num")
        return None

    @staticmethod
    def _chapter_content(chapter: Any) -> str:
        if hasattr(chapter, "content"):
            return getattr(chapter, "content", "") or ""
        if isinstance(chapter, dict):
            return chapter.get("content", "") or ""
        return ""


__all__ = ["GlobalPostPass", "GlobalPostPassReport"]
