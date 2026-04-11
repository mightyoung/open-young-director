"""ChapterConnector — inter-chapter continuity summary generator.

After each chapter is written, :meth:`ChapterConnector.generate_summary` makes a
single low-temperature LLM call to extract structured continuity information that
the *next* chapter needs.  Summaries are persisted to disk and can be reloaded by
the writing stage to replace the raw sliding-window context.

This is NOT a pipeline stage (does not subclass StageRunner).  It is a utility
called by external code (e.g. WritingStage or the pipeline runner) immediately
after a chapter is saved to disk.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from crewai.llm.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

# LLM settings for factual extraction — low temperature, moderate token budget
_EXTRACTION_TEMPERATURE: float = 0.3
_EXTRACTION_MAX_TOKENS: int = 2048

# Sub-directory inside output_dir where summary files are stored
_SUMMARIES_SUBDIR: str = "summaries"

# Maximum chapter-content characters sent to the LLM (avoid huge contexts)
_MAX_CONTENT_CHARS: int = 12_000

_SYSTEM_PROMPT = """\
你是一位小说连续性编辑助理，专职提取章节中对后续写作有用的关键信息。
请以客观、准确的态度分析章节内容，只提取实际发生的事实，不要添加任何推测或创作。
严格按照要求的 JSON 格式输出，不要添加任何解释文字或 markdown 代码围栏。\
"""

_USER_PROMPT_TEMPLATE = """\
你是一位小说编辑助理。请分析以下章节内容，提取关键连续性信息。

=== 章节内容 ===
{chapter_content}

请以 JSON 格式输出（直接输出 JSON，不要包含 ```json 围栏）：
{{
  "key_events": ["事件1", "事件2", ...],
  "character_changes": [{{"name": "角色名", "change_type": "情感/能力/关系/位置", "description": "变化描述"}}],
  "foreshadowing": {{"planted": ["新伏笔"], "harvested": ["已回收伏笔"]}},
  "cliffhanger": "本章结尾悬念",
  "location_updates": [{{"character": "角色", "from": "原位置", "to": "新位置"}}],
  "emotional_state": {{"角色名": "当前情绪状态"}},
  "word_summary": "500字以内的章节摘要，侧重对下一章有用的信息"
}}\
"""

# Required top-level keys in a valid summary dict
_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "key_events",
        "character_changes",
        "foreshadowing",
        "cliffhanger",
        "location_updates",
        "emotional_state",
        "word_summary",
    }
)


@dataclass
class ChapterConnector:
    """Generates inter-chapter continuity summaries.

    Args:
        llm: A configured :class:`~crewai.llm.deepseek_client.DeepSeekClient`
             instance shared with the rest of the pipeline.
    """

    llm: DeepSeekClient

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_summary(
        self,
        chapter_content: str,
        chapter_num: int,
        bible: dict | None = None,  # reserved for future bible-aware extraction
    ) -> dict[str, Any]:
        """Generate a structured continuity summary for *chapter_num*.

        Makes a single LLM call at temperature 0.3 (factual extraction).
        If JSON parsing fails, returns a minimal fallback dict containing only
        ``chapter_num`` and ``word_summary`` derived from the raw LLM text.

        Args:
            chapter_content: The full text of the chapter just written.
            chapter_num: 1-based chapter index (stored in the returned dict).
            bible: Optional Production Bible dict (currently unused but accepted
                   for forward compatibility).

        Returns:
            A dict with keys: ``chapter_num``, ``key_events``,
            ``character_changes``, ``foreshadowing``, ``cliffhanger``,
            ``location_updates``, ``emotional_state``, ``word_summary``.
        """
        # Truncate very long chapters to stay within a sensible context window
        content_slice = chapter_content[:_MAX_CONTENT_CHARS]
        if len(chapter_content) > _MAX_CONTENT_CHARS:
            logger.debug(
                "[ChapterConnector] Chapter %d content truncated from %d to %d chars",
                chapter_num,
                len(chapter_content),
                _MAX_CONTENT_CHARS,
            )

        user_prompt = _USER_PROMPT_TEMPLATE.format(chapter_content=content_slice)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        start = time.time()
        try:
            raw = self.llm.chat(
                messages,
                max_tokens=_EXTRACTION_MAX_TOKENS,
                temperature=_EXTRACTION_TEMPERATURE,
            )
        except Exception as exc:
            logger.error(
                "[ChapterConnector] LLM call failed for chapter %d: %s", chapter_num, exc
            )
            return self._minimal_fallback(chapter_num, str(exc))

        elapsed = time.time() - start
        logger.info(
            "[ChapterConnector] Chapter %d summary extracted in %.1fs (%d chars response)",
            chapter_num,
            elapsed,
            len(raw),
        )

        parsed = self._parse_summary(raw, chapter_num)
        return parsed

    def save_summary(self, summary: dict[str, Any], output_dir: str) -> None:
        """Persist *summary* to ``{output_dir}/summaries/chapter_{num}_summary.json``.

        Creates the summaries sub-directory if it does not exist.

        Args:
            summary: Dict as returned by :meth:`generate_summary`.
            output_dir: Root output directory for this novel project.
        """
        chapter_num: int = summary.get("chapter_num", 0)
        summaries_dir = os.path.join(output_dir, _SUMMARIES_SUBDIR)
        os.makedirs(summaries_dir, exist_ok=True)

        filename = f"chapter_{chapter_num}_summary.json"
        path = os.path.join(summaries_dir, filename)

        # Write to a temporary file first, then rename (atomic-ish on POSIX)
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except OSError as exc:
            logger.error(
                "[ChapterConnector] Failed to save summary for chapter %d to %s: %s",
                chapter_num,
                path,
                exc,
            )
            raise
        else:
            logger.info(
                "[ChapterConnector] Chapter %d summary saved → %s", chapter_num, path
            )

    @staticmethod
    def load_summary(chapter_num: int, output_dir: str) -> dict[str, Any] | None:
        """Load the persisted summary for *chapter_num* from disk.

        Args:
            chapter_num: Chapter index to load.
            output_dir: Root output directory for this novel project.

        Returns:
            The summary dict, or ``None`` if the file does not exist or cannot
            be parsed.
        """
        path = os.path.join(
            output_dir, _SUMMARIES_SUBDIR, f"chapter_{chapter_num}_summary.json"
        )
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                logger.warning(
                    "[ChapterConnector] Summary file %s is not a JSON object", path
                )
                return None
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "[ChapterConnector] Could not load summary from %s: %s", path, exc
            )
            return None

    def load_recent_summaries(
        self, current_chapter: int, count: int, output_dir: str
    ) -> list[dict[str, Any]]:
        """Load the *count* most recent summaries preceding *current_chapter*.

        Summaries are returned in ascending chapter order.  Missing files are
        silently skipped.

        Args:
            current_chapter: The chapter about to be written (excluded from results).
            count: Maximum number of prior summaries to return.
            output_dir: Root output directory for this novel project.

        Returns:
            List of summary dicts, ordered oldest → newest, length ≤ *count*.
        """
        if count <= 0 or current_chapter <= 1:
            return []

        # Walk backwards from current_chapter - 1 and collect up to `count` hits
        results: list[dict[str, Any]] = []
        for chapter_num in range(current_chapter - 1, 0, -1):
            if len(results) >= count:
                break
            summary = self.load_summary(chapter_num, output_dir)
            if summary is not None:
                results.append(summary)

        results.reverse()  # oldest first
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_summary(self, raw: str, chapter_num: int) -> dict[str, Any]:
        """Try to parse *raw* as a JSON continuity summary.

        Tries three strategies:
        1. Strip a ``json ... `` markdown fence and parse the interior.
        2. Find the first ``{ ... }`` block via regex and parse it.
        3. Parse the raw text directly.

        Falls back to :meth:`_minimal_fallback` on any parse error.
        """
        # Strategy 1: markdown code fence
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw, re.DOTALL)
        if fence_match:
            candidate = fence_match.group(1).strip()
            parsed = self._try_json_load(candidate)
            if parsed is not None:
                return self._normalise(parsed, chapter_num, raw)

        # Strategy 2: first top-level JSON object in the text
        obj_match = re.search(r"\{[\s\S]*\}", raw)
        if obj_match:
            parsed = self._try_json_load(obj_match.group())
            if parsed is not None:
                return self._normalise(parsed, chapter_num, raw)

        # Strategy 3: bare parse of the whole response
        parsed = self._try_json_load(raw.strip())
        if parsed is not None:
            return self._normalise(parsed, chapter_num, raw)

        logger.warning(
            "[ChapterConnector] JSON parse failed for chapter %d — using minimal fallback",
            chapter_num,
        )
        return self._minimal_fallback(chapter_num, raw)

    @staticmethod
    def _try_json_load(text: str) -> dict[str, Any] | None:
        """Return parsed dict or None (never raises)."""
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    @staticmethod
    def _normalise(data: dict[str, Any], chapter_num: int, raw_fallback: str) -> dict[str, Any]:
        """Coerce a successfully parsed dict into the canonical summary shape.

        Missing keys receive safe empty defaults so callers can always rely on
        the full schema without defensive ``dict.get`` chains.
        """
        foreshadowing_raw = data.get("foreshadowing", {})
        if not isinstance(foreshadowing_raw, dict):
            foreshadowing_raw = {}

        return {
            "chapter_num": chapter_num,
            "key_events": list(data.get("key_events") or []),
            "character_changes": list(data.get("character_changes") or []),
            "foreshadowing": {
                "planted": list(foreshadowing_raw.get("planted") or []),
                "harvested": list(foreshadowing_raw.get("harvested") or []),
            },
            "cliffhanger": str(data.get("cliffhanger") or ""),
            "location_updates": list(data.get("location_updates") or []),
            "emotional_state": dict(data.get("emotional_state") or {}),
            "word_summary": str(data.get("word_summary") or raw_fallback[:500]),
        }

    @staticmethod
    def _minimal_fallback(chapter_num: int, raw_text: str) -> dict[str, Any]:
        """Return a safe minimal summary when LLM output cannot be parsed."""
        return {
            "chapter_num": chapter_num,
            "key_events": [],
            "character_changes": [],
            "foreshadowing": {"planted": [], "harvested": []},
            "cliffhanger": "",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": raw_text[:500],
        }
