"""ContextBuilder — sliding-window context assembler for chapter writing.

Assembles optimal context for a given chapter within a token budget by
combining recent chapter endings, older chapter summaries, Production Bible
excerpts (characters, world rules, relationships), and active foreshadowing.

Usage::

    builder = ContextBuilder(token_budget=8000)
    ctx = builder.build_context(state, current_chapter_num=12, output_dir="output", llm=llm)
    prompt_text = builder.format_as_prompt(ctx)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Budget fractions per section (must sum ≤ 1.0)
_BUDGET_RECENT: float = 0.40
_BUDGET_SUMMARIES: float = 0.20
_BUDGET_BIBLE: float = 0.25
_BUDGET_FORESHADOW: float = 0.15

# Fallback chars-per-token estimate when no LLM token counter is available
_BYTES_PER_TOKEN: float = 3.5

# Tail chars from each recent chapter
_RECENT_TAIL_CHARS: int = 800


@dataclass
class ContextBuilder:
    """Assembles optimal context for chapter writing within a token budget.

    Attributes:
        token_budget: Maximum total tokens for the assembled context.
        recent_full_chapters: Number of most-recent chapters to include in full.
        summary_chars: Maximum characters from each older chapter summary.
    """

    token_budget: int = 8000
    recent_full_chapters: int = 3
    summary_chars: int = 800

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_context(
        self,
        state: PipelineState,
        current_chapter_num: int,
        output_dir: str,
        llm=None,
    ) -> dict:
        """Build context dict respecting the token budget.

        Returns dict with keys: ``previous_chapters``, ``bible_context``,
        ``foreshadowing``, ``location_map``, ``total_tokens``.
        """
        def _count(text: str) -> int:
            if llm is not None and hasattr(llm, "count_tokens"):
                return llm.count_tokens(text)
            return max(1, int(len(text.encode("utf-8")) / _BYTES_PER_TOKEN))

        recent = self._trim(_count, self._recent_chapters(state, current_chapter_num, output_dir),
                            int(self.token_budget * _BUDGET_RECENT))
        summaries = self._trim(_count, self._chapter_summaries(state, current_chapter_num, output_dir),
                               int(self.token_budget * _BUDGET_SUMMARIES))
        bible, location = self._bible_context(state, current_chapter_num)
        bible = self._trim(_count, bible, int(self.token_budget * _BUDGET_BIBLE))
        foreshadow = self._trim(_count, self._foreshadowing(state, current_chapter_num),
                                int(self.token_budget * _BUDGET_FORESHADOW))

        # Overall budget enforcement — trim in reverse priority
        total = sum(_count(t) for t in (recent, summaries, bible, foreshadow, location))
        if total > self.token_budget:
            foreshadow, bible, summaries, recent, location = self._enforce_budget(
                recent, summaries, bible, foreshadow, location, _count
            )
            total = sum(_count(t) for t in (recent, summaries, bible, foreshadow, location))

        logger.info(
            "[ContextBuilder] chapter=%d tokens=%d "
            "(recent=%d summaries=%d bible=%d foreshadow=%d location=%d)",
            current_chapter_num, total,
            _count(recent), _count(summaries), _count(bible),
            _count(foreshadow), _count(location),
        )
        return {
            "previous_chapters": recent,
            "bible_context": bible,
            "foreshadowing": foreshadow,
            "location_map": location,
            "total_tokens": total,
        }

    def format_as_prompt(self, context: dict) -> str:
        """Assemble context sections into a single prompt string with Chinese headers."""
        parts: list[str] = []
        if context.get("previous_chapters"):
            parts.append(f"=== 前文节选 ===\n{context['previous_chapters']}")
        if context.get("bible_context"):
            parts.append(f"=== 角色与世界设定 ===\n{context['bible_context']}")
        if context.get("location_map"):
            parts.append(f"=== 角色位置图 ===\n{context['location_map']}")
        if context.get("foreshadowing"):
            parts.append(f"=== 伏笔提醒 ===\n{context['foreshadowing']}")
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _recent_chapters(
        self, state: PipelineState, current_chapter_num: int, output_dir: str
    ) -> str:
        """Return the tail of the last N written chapters for continuity."""
        prior = sorted(
            (ch for ch in state.chapters
             if isinstance(ch, dict) and ch.get("chapter_num", 0) < current_chapter_num),
            key=lambda c: c.get("chapter_num", 0),
        )
        window = prior[-self.recent_full_chapters:]
        parts: list[str] = []
        for ch in window:
            content: str = ch.get("content", "")
            num: int = ch.get("chapter_num", 0)
            if not content or content.startswith("["):
                content = self._load_chapter(num, output_dir)
            if content:
                parts.append(f"【第{num}章结尾】\n{content[-_RECENT_TAIL_CHARS:]}")
        return "\n\n".join(parts)

    def _chapter_summaries(
        self, state: PipelineState, current_chapter_num: int, output_dir: str
    ) -> str:
        """Return word summaries for chapters older than the sliding window."""
        cutoff = current_chapter_num - self.recent_full_chapters
        if cutoff <= 0:
            return ""
        written_nums = sorted(
            ch.get("chapter_num", 0)
            for ch in state.chapters
            if isinstance(ch, dict) and 0 < ch.get("chapter_num", 0) < cutoff
        )
        parts: list[str] = []
        for num in written_nums:
            raw = self._load_summary(num, output_dir)
            text = raw.get("word_summary", raw.get("summary", raw.get("brief", "")))
            if text:
                parts.append(f"【第{num}章摘要】\n{text[:self.summary_chars]}")
        return "\n\n".join(parts)

    def _bible_context(
        self, state: PipelineState, current_chapter_num: int
    ) -> tuple[str, str]:
        """Extract characters, world rules, relationships, and GPS from the Bible.

        Returns (bible_context_str, location_map_str).
        """
        bible = state.bible_serialized
        if not bible:
            return "", ""

        # Characters appearing in this chapter (from chapter_summaries)
        appearing: set[str] = set()
        for s in state.chapter_summaries:
            if isinstance(s, dict) and s.get("chapter_num") == current_chapter_num:
                appearing.update(s.get("character_appearances", []))
                break

        # Characters
        char_lines: list[str] = []
        for name, profile in (bible.get("characters") or {}).items():
            if appearing and name not in appearing:
                continue
            if not isinstance(profile, dict):
                continue
            line = f"- {name}（{profile.get('role', '')}）: {profile.get('personality', '')[:100]}"
            if profile.get("hidden_agenda"):
                line += f" | 隐藏动机: {profile['hidden_agenda'][:100]}"
            if profile.get("cultivation_realm"):
                line += f" | 境界: {profile['cultivation_realm']}"
            if profile.get("faction"):
                line += f" | 门派: {profile['faction']}"
            char_lines.append(line)

        # Relationships (only between appearing characters)
        rel_lines: list[str] = []
        for name, profile in (bible.get("characters") or {}).items():
            if appearing and name not in appearing:
                continue
            if not isinstance(profile, dict):
                continue
            for target, rel in (profile.get("relationships") or {}).items():
                if appearing and target not in appearing:
                    continue
                if isinstance(rel, dict):
                    entry = f"- {name} ↔ {target}（{rel.get('bond_type', '')}，情感值{rel.get('emotional_value', 0)}）"
                    if rel.get("core_conflict"):
                        entry += f"：{rel['core_conflict'][:80]}"
                    rel_lines.append(entry)

        # World constraints (capped at 5)
        world_rules = bible.get("world_rules") or {}
        rule_lines: list[str] = []
        if isinstance(world_rules, dict):
            for c in (world_rules.get("world_constraints") or [])[:5]:
                rule_lines.append(f"- {str(c)[:120]}")

        sections: list[str] = []
        if char_lines:
            sections.append("【角色设定】\n" + "\n".join(char_lines))
        if rel_lines:
            sections.append("【人物关系】\n" + "\n".join(rel_lines))
        if rule_lines:
            sections.append("【世界规则】\n" + "\n".join(rule_lines))

        # Character GPS
        gps: dict = bible.get("character_gps") or {}
        loc_lines: list[str] = []
        for char_name, loc in gps.items():
            if appearing and char_name not in appearing:
                continue
            if isinstance(loc, dict):
                loc_lines.append(
                    f"- {char_name}：{loc.get('place_name', '')}（{loc.get('status', '')}，第{loc.get('arrival_chapter', '')}章抵达）"
                )

        return "\n\n".join(sections), "\n".join(loc_lines)

    def _foreshadowing(
        self, state: PipelineState, current_chapter_num: int
    ) -> str:
        """Return active foreshadowing entries for the current chapter."""
        bible = state.bible_serialized
        if not bible:
            return ""
        registry: dict = bible.get("foreshadowing_registry") or {}
        lines: list[str] = []
        for fid, entry in registry.items():
            if not isinstance(entry, dict) or not entry.get("is_active", True):
                continue
            setup_ch: int = entry.get("setup_chapter", 0)
            payoff_ch: int = entry.get("payoff_chapter", 9999)
            if setup_ch > current_chapter_num - 1:
                continue
            desc = entry.get("setup_description", "")[:120]
            near = 0 < (payoff_ch - current_chapter_num) <= 3
            if near:
                payoff_desc = entry.get("payoff_description", "")[:80]
                lines.append(
                    f"⚠️【即将回收 {fid}】第{setup_ch}章埋下：{desc}，"
                    f"预计第{payoff_ch}章回收（{payoff_desc}）"
                )
            else:
                lines.append(
                    f"【伏笔 {fid}】第{setup_ch}章埋下：{desc}，预计第{payoff_ch}章回收"
                )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Disk I/O helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_chapter(chapter_num: int, output_dir: str) -> str:
        """Load chapter text from ``{output_dir}/chapters/chapter_{num}.txt``."""
        path = os.path.join(output_dir, "chapters", f"chapter_{chapter_num}.txt")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            logger.debug("[ContextBuilder] Cannot load chapter %d: %s", chapter_num, exc)
            return ""

    @staticmethod
    def _load_summary(chapter_num: int, output_dir: str) -> dict:
        """Load summary JSON from ``{output_dir}/summaries/chapter_{num}_summary.json``."""
        path = os.path.join(output_dir, "summaries", f"chapter_{chapter_num}_summary.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("[ContextBuilder] Cannot load summary %d: %s", chapter_num, exc)
            return {}

    # ------------------------------------------------------------------
    # Budget helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _trim(count_fn, text: str, max_tokens: int) -> str:
        """Trim text to fit within max_tokens (estimated by count_fn)."""
        if not text or count_fn(text) <= max_tokens:
            return text
        # Quick estimate: shave from the front until we fit
        candidate = text[-int(max_tokens * _BYTES_PER_TOKEN):]
        while candidate and count_fn(candidate) > max_tokens:
            candidate = candidate[int(len(candidate) * 0.10):]
        return candidate

    def _enforce_budget(
        self,
        recent: str, summaries: str, bible: str,
        foreshadow: str, location: str,
        count_fn,
    ) -> tuple[str, str, str, str, str]:
        """Trim sections in reverse-priority order to fit total token budget.

        Priority (high → low): recent > summaries > bible > location > foreshadow.
        Returns (foreshadow, bible, summaries, recent, location).
        """
        budget = self.token_budget

        def _total() -> int:
            return sum(count_fn(t) for t in (recent, summaries, bible, foreshadow, location))

        # Step 1: drop foreshadow
        if _total() > budget:
            foreshadow = ""
        # Step 2: trim bible
        if _total() > budget:
            bible_budget = max(0, budget - count_fn(recent) - count_fn(summaries) - count_fn(location))
            bible = self._trim(count_fn, bible, bible_budget)
        # Step 3: trim summaries
        if _total() > budget:
            sum_budget = max(0, budget - count_fn(recent) - count_fn(bible) - count_fn(location))
            summaries = self._trim(count_fn, summaries, sum_budget)
        # Step 4: trim recent chapters (last resort)
        if _total() > budget:
            recent_budget = max(0, budget - count_fn(summaries) - count_fn(bible) - count_fn(location))
            recent = self._trim(count_fn, recent, recent_budget)

        return foreshadow, bible, summaries, recent, location
