"""ContextCompactor - Inspired by Claude Code's MicroCompact mechanism.

Optimizes the Production Bible context sent to the LLM by trimming irrelevant
details based on the current chapter's outline and focus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CompactionReport:
    """Structured report for a compaction pass."""

    active_keywords: list[str] = field(default_factory=list)
    token_budget: int = 4000
    estimated_original_tokens: int = 0
    estimated_compacted_tokens: int = 0
    original_character_count: int = 0
    compacted_character_count: int = 0
    original_foreshadowing_count: int = 0
    compacted_foreshadowing_count: int = 0
    trimmed_character_count: int = 0
    trimmed_foreshadowing_count: int = 0
    was_budget_met: bool = True
    fallback_used: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def estimated_tokens_saved(self) -> int:
        return max(0, self.estimated_original_tokens - self.estimated_compacted_tokens)

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_keywords": list(self.active_keywords),
            "token_budget": self.token_budget,
            "estimated_original_tokens": self.estimated_original_tokens,
            "estimated_compacted_tokens": self.estimated_compacted_tokens,
            "estimated_tokens_saved": self.estimated_tokens_saved,
            "original_character_count": self.original_character_count,
            "compacted_character_count": self.compacted_character_count,
            "original_foreshadowing_count": self.original_foreshadowing_count,
            "compacted_foreshadowing_count": self.compacted_foreshadowing_count,
            "trimmed_character_count": self.trimmed_character_count,
            "trimmed_foreshadowing_count": self.trimmed_foreshadowing_count,
            "was_budget_met": self.was_budget_met,
            "fallback_used": self.fallback_used,
            "notes": list(self.notes),
        }


class ContextCompactor:
    """Service for dynamic context compression and relevance filtering."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.max_tokens_budget = self.config.get("context_budget_tokens", 4000)

    def compact_bible_section(self, bible_section: Any, chapter_outline: Dict[str, Any]) -> Any:
        """Backward-compatible wrapper that returns only the compacted section."""
        compacted, _ = self.compact_bible_section_with_report(bible_section, chapter_outline)
        return compacted

    def compact_bible_section_with_report(
        self,
        bible_section: Any,
        chapter_outline: Dict[str, Any],
    ) -> tuple[Any, CompactionReport]:
        """Create a 'Micro-Refined' version of the BibleSection for the LLM.
        
        Args:
            bible_section: The full BibleSection for the current volume.
            chapter_outline: The specific plan for this chapter.
            
        Returns:
            A tuple of (trimmed BibleSection, compaction report).
        """
        report = CompactionReport(token_budget=self.max_tokens_budget)
        if not bible_section:
            report.was_budget_met = False
            report.fallback_used = True
            report.notes.append("no_bible_section")
            return None, report

        # 1. 提取本章“活跃关键词”
        active_keywords = self._extract_active_keywords(chapter_outline)
        report.active_keywords = sorted(active_keywords)
        report.original_character_count = len(getattr(bible_section, "relevant_characters", {}) or {})
        report.original_foreshadowing_count = len(getattr(bible_section, "open_foreshadowing", []) or [])
        
        # 2. 筛选角色：只有出现在大纲中的角色保留全量，其他的保留摘要
        new_relevant_characters = {}
        for name, char in bible_section.relevant_characters.items():
            if name in active_keywords or char.role == "protagonist":
                new_relevant_characters[name] = char
            else:
                # 极致压缩：非活跃角色只保留姓名和角色定位
                from dataclasses import replace
                compact_char = replace(char, personality="", appearance="", backstory="[已压缩]", character_arc="")
                new_relevant_characters[name] = compact_char

        # 3. 筛选世界观：只保留与本章地点或关键词相关的规则
        # (此处逻辑可根据 world_rules 的具体结构进一步细化)
        
        # 4. 筛选伏笔：只保留 setup 或 payoff 在本章的伏笔
        new_open_foreshadowing = []
        ch_num = chapter_outline.get("chapter_num", 0)
        for fs in bible_section.open_foreshadowing:
            if fs.setup_chapter == ch_num or fs.payoff_chapter == ch_num:
                new_open_foreshadowing.append(fs)
            else:
                # 远处伏笔仅保留 ID 和极简描述，防止干扰
                pass

        # 构造压缩后的对象
        from dataclasses import replace
        compact_section = replace(
            bible_section,
            relevant_characters=new_relevant_characters,
            open_foreshadowing=new_open_foreshadowing
        )

        report.compacted_character_count = len(new_relevant_characters)
        report.compacted_foreshadowing_count = len(new_open_foreshadowing)
        report.trimmed_character_count = max(
            0,
            report.original_character_count - report.compacted_character_count,
        )
        report.trimmed_foreshadowing_count = max(
            0,
            report.original_foreshadowing_count - report.compacted_foreshadowing_count,
        )
        report.estimated_original_tokens = self._estimate_budget(
            bible_section,
            chapter_outline,
        )
        report.estimated_compacted_tokens = self._estimate_budget(
            compact_section,
            chapter_outline,
        )
        report.was_budget_met = report.estimated_compacted_tokens <= self.max_tokens_budget
        if not report.was_budget_met:
            report.notes.append("compact_section_still_over_budget")
        
        logger.info(f"Context Compacted: Trimmed {len(bible_section.relevant_characters) - len(new_relevant_characters)} inactive details.")
        return compact_section, report

    def _extract_active_keywords(self, outline: Dict[str, Any]) -> set:
        """From title and events, find who/what is active now."""
        text = str(outline.get("title", "")) + " " + " ".join(outline.get("main_events", []))
        # 简单的正则或分词提取（实际可使用更高级的模式匹配）
        import re
        words = set(re.findall(r'[\u4e00-\u9fa5]{2,4}', text))
        return words

    def _estimate_budget(self, bible_section: Any, chapter_outline: Dict[str, Any]) -> int:
        """Rough token estimate for a BibleSection and its chapter outline."""
        text_parts = [
            getattr(bible_section, "world_rules_summary", ""),
            " ".join(getattr(bible_section, "canonical_facts_this_volume", []) or []),
            " ".join(str(item) for item in (getattr(bible_section, "timeline_up_to_this_point", []) or [])),
            " ".join(getattr(chapter_outline, "main_events", []) or []),
            str(chapter_outline.get("title", "")),
        ]
        total_chars = sum(len(part) for part in text_parts if part)
        return max(1, total_chars // 4)
