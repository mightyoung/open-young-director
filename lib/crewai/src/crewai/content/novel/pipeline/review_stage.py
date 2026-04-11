"""ReviewStage — lightweight, rule-based chapter review pass.

Checks each chapter for:
  1. 禁词扫描  — forbidden words / clichés
  2. 字数检查  — word count within 50 %–150 % of target
  3. 空章检查  — content not empty or too short (< 500 chars)
  4. 重复检查  — no paragraph repeated more than once

All checks are regex / rule-based.  No LLM calls.  No retries.
Issues are recorded as informational annotations; no rewrites are triggered.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.pipeline.stage_runner import StageRunner

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Forbidden words / clichés that editors flag in Chinese web-fiction.
FORBIDDEN_WORDS: tuple[str, ...] = (
    "突然",
    "居然",
    "竟然",
    "恐怖如斯",
    "倒吸一口冷气",
    "极其",
    "非常",
    "仿佛",
    "似乎",
    "某种",
    "令人惊讶的是",
)

#: Minimum fraction of the target word-count (50 %).
_WORD_COUNT_MIN_RATIO: float = 0.50

#: Maximum fraction of the target word-count (150 %).
_WORD_COUNT_MAX_RATIO: float = 1.50

#: Chapters shorter than this many characters are flagged as empty.
_MIN_CONTENT_LENGTH: int = 500

#: Paragraphs with more than this many occurrences are flagged as duplicate.
_MAX_PARAGRAPH_REPEATS: int = 1

#: Sentinel value written by WritingStage when a chapter was saved to disk.
_SAVED_TO_DISK_SENTINEL: str = "[SAVED to disk]"


@dataclass
class ReviewStage(StageRunner):
    """Lightweight rule-based review stage.

    Reads:  ``state.chapters``        — list of chapter dicts from WritingStage
            ``state.config``           — novel configuration (used for target word count
                                         and output_dir)
    Writes: ``chapter["review_issues"]`` — list of issue dicts added to each chapter
    """

    name: str = "review"

    # ------------------------------------------------------------------
    # Protocol
    # ------------------------------------------------------------------

    def validate_input(self, state: PipelineState) -> bool:
        """Require at least one chapter to be present."""
        if not state.chapters:
            logger.error("[%s] validate_input failed: state.chapters is empty", self.name)
            return False
        return True

    def run(self, state: PipelineState) -> PipelineState:
        """Run all checks across every chapter and annotate with issues.

        Args:
            state: Current pipeline state.

        Returns:
            Updated state with ``review_issues`` populated on each chapter dict.
        """
        output_dir: str = state.config.get("output_dir", "output")
        target_words: int = int(state.config.get("words_per_chapter_target", 5000))

        total_issues = 0
        chapters_checked = 0

        for chapter in state.chapters:
            if not isinstance(chapter, dict):
                # Guard against non-dict entries (e.g. ChapterOutput objects)
                logger.warning(
                    "[%s] Skipping non-dict chapter entry: %r", self.name, type(chapter)
                )
                continue

            content = self._resolve_content(chapter, output_dir)
            issues: list[dict[str, Any]] = []

            issues.extend(self._check_forbidden_words(content))
            issues.extend(self._check_word_count(content, target_words))
            issues.extend(self._check_empty(content))
            issues.extend(self._check_duplicate_paragraphs(content))

            # Annotate the chapter dict in-place.
            # We deliberately avoid creating a new dict to keep memory overhead low;
            # the list reference in state.chapters is unchanged.
            chapter["review_issues"] = issues
            total_issues += len(issues)
            chapters_checked += 1

        logger.info(
            "[%s] Review complete: %d chapters, %d total issues",
            self.name,
            chapters_checked,
            total_issues,
        )
        return state

    # ------------------------------------------------------------------
    # Content resolver
    # ------------------------------------------------------------------

    def _resolve_content(self, chapter: dict, output_dir: str) -> str:
        """Return the chapter text, loading from disk when necessary.

        When WritingStage saves a chapter to disk to conserve memory, it sets
        ``chapter["content"]`` to the sentinel ``"[SAVED to disk]"``.  This
        helper detects that sentinel and loads the actual text from::

            {output_dir}/chapters/chapter_{num}.txt

        Args:
            chapter: Chapter dict.
            output_dir: Root output directory (from pipeline config).

        Returns:
            Chapter content string (may be empty string on read error).
        """
        content: str = chapter.get("content", "") or ""

        if content.strip() == _SAVED_TO_DISK_SENTINEL:
            chapter_num = chapter.get("chapter_num") or chapter.get("number")
            if chapter_num is not None:
                disk_path = os.path.join(
                    output_dir, "chapters", f"chapter_{chapter_num}.txt"
                )
                try:
                    with open(disk_path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    logger.debug(
                        "[%s] Loaded chapter %s from disk: %s",
                        self.name,
                        chapter_num,
                        disk_path,
                    )
                except OSError as exc:
                    logger.warning(
                        "[%s] Could not load chapter %s from %s: %s",
                        self.name,
                        chapter_num,
                        disk_path,
                        exc,
                    )
                    content = ""
            else:
                logger.warning(
                    "[%s] Chapter has SAVED sentinel but no chapter_num; skipping disk load",
                    self.name,
                )

        return content

    # ------------------------------------------------------------------
    # Individual checkers
    # ------------------------------------------------------------------

    def _check_forbidden_words(self, content: str) -> list[dict[str, Any]]:
        """1. 禁词扫描 — flag each forbidden word found in content.

        Args:
            content: Chapter text.

        Returns:
            List of issue dicts, one per forbidden word that appears.
        """
        issues: list[dict[str, Any]] = []
        for word in FORBIDDEN_WORDS:
            count = content.count(word)
            if count > 0:
                issues.append({
                    "type": "forbidden_word",
                    "word": word,
                    "count": count,
                    "message": f"禁词「{word}」出现 {count} 次",
                })
        return issues

    def _check_word_count(
        self, content: str, target_words: int
    ) -> list[dict[str, Any]]:
        """2. 字数检查 — verify content length is within 50 %–150 % of target.

        Uses ``len(content)`` as a proxy for Chinese character count (each
        character ≈ one word for CJK text).

        Args:
            content: Chapter text.
            target_words: Target character count from novel config.

        Returns:
            List containing at most one issue dict.
        """
        actual = len(content)
        low = int(target_words * _WORD_COUNT_MIN_RATIO)
        high = int(target_words * _WORD_COUNT_MAX_RATIO)

        if not (low <= actual <= high):
            direction = "偏少" if actual < low else "偏多"
            return [{
                "type": "word_count",
                "actual": actual,
                "target": target_words,
                "acceptable_range": (low, high),
                "message": (
                    f"字数 {actual}，目标 {target_words}，"
                    f"允许范围 {low}–{high}，{direction}"
                ),
            }]
        return []

    def _check_empty(self, content: str) -> list[dict[str, Any]]:
        """3. 空章检查 — flag chapters with fewer than 500 characters.

        Args:
            content: Chapter text.

        Returns:
            List containing at most one issue dict.
        """
        if len(content) < _MIN_CONTENT_LENGTH:
            return [{
                "type": "empty_chapter",
                "actual_length": len(content),
                "min_length": _MIN_CONTENT_LENGTH,
                "message": (
                    f"章节内容过短（{len(content)} 字），"
                    f"最低要求 {_MIN_CONTENT_LENGTH} 字"
                ),
            }]
        return []

    def _check_duplicate_paragraphs(self, content: str) -> list[dict[str, Any]]:
        """4. 重复检查 — flag paragraphs that appear more than once.

        Paragraphs are split on blank lines or line breaks.  Very short lines
        (< 10 characters) are ignored to avoid false positives from decorators,
        scene separators, etc.

        Args:
            content: Chapter text.

        Returns:
            List of issue dicts, one per duplicated paragraph.
        """
        paragraphs = re.split(r"\n{2,}|\r\n{2,}", content)
        seen: dict[str, int] = {}
        for para in paragraphs:
            normalised = para.strip()
            if len(normalised) < 10:
                continue
            seen[normalised] = seen.get(normalised, 0) + 1

        issues: list[dict[str, Any]] = []
        for para_text, count in seen.items():
            if count > _MAX_PARAGRAPH_REPEATS:
                issues.append({
                    "type": "duplicate_paragraph",
                    "count": count,
                    "preview": para_text[:60] + ("…" if len(para_text) > 60 else ""),
                    "message": f"段落重复 {count} 次：「{para_text[:40]}…」",
                })
        return issues
