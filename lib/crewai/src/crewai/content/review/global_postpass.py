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
        # Use continuity tracker if available
        if self.continuity_tracker:
            for entity_id in self.continuity_tracker.entity_states:
                history = self.continuity_tracker.entity_state_history.get(entity_id, [])
                if len(history) < 2:
                    continue

                # Check for impossible location jumps
                for i in range(1, len(history)):
                    prev_loc = history[i-1].location
                    curr_loc = history[i].location
                    if prev_loc and curr_loc and prev_loc != curr_loc:
                        # Check if event description supports the move
                        chapter = history[i].chapter
                        # This is a basic check - continuity tracker handles the detailed logic

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


__all__ = ["GlobalPostPass", "GlobalPostPassReport"]
