"""Foreshadowing tracking board for novel pipeline memory system."""
import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ForeshadowEntry:
    """A single foreshadowing element."""

    id: str
    setup_chapter: int
    setup_content: str
    expected_payoff_chapter: int
    status: str = "open"  # open, hinted, harvested, expired
    hint_chapters: list[int] = field(default_factory=list)
    payoff_content: str = ""

    def to_dict(self) -> dict:
        """Convert entry to dictionary for serialization."""
        return {
            "id": self.id,
            "setup_chapter": self.setup_chapter,
            "setup_content": self.setup_content,
            "expected_payoff_chapter": self.expected_payoff_chapter,
            "status": self.status,
            "hint_chapters": self.hint_chapters,
            "payoff_content": self.payoff_content,
        }


@dataclass
class ForeshadowingBoard:
    """Manages foreshadowing elements across the novel."""

    entries: list[ForeshadowEntry] = field(default_factory=list)
    _next_id: int = 1

    def plant(self, chapter_num: int, content: str, expected_payoff: int) -> str:
        """Plant a new foreshadowing. Returns the ID.

        Args:
            chapter_num: Chapter where foreshadowing is planted
            content: Description of the foreshadowing
            expected_payoff: Target chapter for payoff/resolution

        Returns:
            str: Unique foreshadowing ID (e.g., "F001")
        """
        fid = f"F{self._next_id:03d}"
        self._next_id += 1
        entry = ForeshadowEntry(
            id=fid,
            setup_chapter=chapter_num,
            setup_content=content,
            expected_payoff_chapter=expected_payoff,
        )
        self.entries.append(entry)
        logger.info(
            f"Planted foreshadowing {fid} at chapter {chapter_num}, "
            f"payoff at {expected_payoff}"
        )
        return fid

    def hint(self, fid: str, chapter_num: int) -> None:
        """Record a hint/reminder for an existing foreshadowing.

        Args:
            fid: Foreshadowing ID to hint
            chapter_num: Chapter where hint appears
        """
        for e in self.entries:
            if e.id == fid and e.status == "open":
                e.hint_chapters.append(chapter_num)
                e.status = "hinted"
                logger.info(f"Added hint to foreshadowing {fid} at chapter {chapter_num}")
                return

    def harvest(self, fid: str, chapter_num: int, payoff_content: str = "") -> None:
        """Mark a foreshadowing as harvested/resolved.

        Args:
            fid: Foreshadowing ID to harvest
            chapter_num: Chapter where payoff occurs
            payoff_content: Description of how foreshadowing was resolved
        """
        for e in self.entries:
            if e.id == fid:
                e.status = "harvested"
                e.payoff_content = payoff_content
                logger.info(f"Harvested foreshadowing {fid} at chapter {chapter_num}")
                return

    def get_active(self, current_chapter: int | None = None) -> list[ForeshadowEntry]:
        """Get all open/hinted foreshadowing entries.

        Args:
            current_chapter: Optional chapter to sort by proximity to payoff

        Returns:
            list[ForeshadowEntry]: Active foreshadowing entries
        """
        active = [e for e in self.entries if e.status in ("open", "hinted")]
        if current_chapter:
            active.sort(
                key=lambda e: abs(e.expected_payoff_chapter - current_chapter)
            )
        return active

    def get_overdue(self, current_chapter: int) -> list[ForeshadowEntry]:
        """Get foreshadowing entries past their expected payoff chapter.

        Args:
            current_chapter: Current chapter number

        Returns:
            list[ForeshadowEntry]: Overdue foreshadowing entries
        """
        return [
            e
            for e in self.entries
            if e.status in ("open", "hinted")
            and e.expected_payoff_chapter < current_chapter
        ]

    def get_due_soon(
        self, current_chapter: int, window: int = 3
    ) -> list[ForeshadowEntry]:
        """Get foreshadowing entries due within the next N chapters.

        Args:
            current_chapter: Current chapter number
            window: Chapter window to check ahead

        Returns:
            list[ForeshadowEntry]: Due soon foreshadowing entries
        """
        return [
            e
            for e in self.entries
            if e.status in ("open", "hinted")
            and current_chapter <= e.expected_payoff_chapter <= current_chapter + window
        ]

    def format_for_prompt(self, current_chapter: int) -> str:
        """Format active foreshadowing for injection into writing prompt.

        Args:
            current_chapter: Current chapter being written

        Returns:
            str: Formatted foreshadowing summary for LLM context
        """
        lines = []
        due_soon = self.get_due_soon(current_chapter)
        overdue = self.get_overdue(current_chapter)

        if overdue:
            lines.append("【过期未回收伏笔 - 请尽快处理！】")
            for e in overdue:
                lines.append(
                    f"- [{e.id}] 第{e.setup_chapter}章埋下: {e.setup_content} "
                    f"(原计划第{e.expected_payoff_chapter}章回收)"
                )

        if due_soon:
            lines.append("【即将到期伏笔 - 建议本章回收】")
            for e in due_soon:
                lines.append(
                    f"- [{e.id}] 第{e.setup_chapter}章埋下: {e.setup_content} "
                    f"(计划第{e.expected_payoff_chapter}章回收)"
                )

        other_active = [
            e for e in self.get_active() if e not in due_soon and e not in overdue
        ]
        if other_active:
            lines.append("【其他活跃伏笔】")
            for e in other_active[:5]:
                lines.append(f"- [{e.id}] 第{e.setup_chapter}章: {e.setup_content}")

        return "\n".join(lines) if lines else "当前无活跃伏笔"

    def save(self, path: str) -> None:
        """Save board to JSON file.

        Args:
            path: File path to save to
        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "next_id": self._next_id,
            "entries": [e.to_dict() for e in self.entries],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved foreshadowing board to {path}")

    @classmethod
    def load(cls, path: str) -> "ForeshadowingBoard":
        """Load board from JSON file.

        Args:
            path: File path to load from

        Returns:
            ForeshadowingBoard: Loaded board or empty board if file doesn't exist
        """
        if not os.path.exists(path):
            logger.info(f"No foreshadowing board found at {path}, starting fresh")
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        board = cls(_next_id=data.get("next_id", 1))
        for e in data.get("entries", []):
            board.entries.append(ForeshadowEntry(**e))
        logger.info(f"Loaded foreshadowing board from {path} with {len(board.entries)} entries")
        return board
