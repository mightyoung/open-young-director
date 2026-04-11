"""WritingStage — 整章一次性生成，WRITER.md 硬注入，滑动窗口上下文。

Design principles enforced here:
1. 整章一次生成 — single LLM call per chapter, no beat-by-beat fragmentation.
2. WRITER.md 硬注入 — constitution is prepended to every system prompt.
3. 字数目标在 prompt 中 — target word count stated explicitly in the user prompt.
4. 立即落盘 + 释放 — chapter saved to disk immediately, content cleared from RAM.
5. 滑动窗口上下文 — last N chapters' endings (~800 chars each) for continuity.
6. 规则检查（不循环）— forbidden-word scan after generation; log only, no retry.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from crewai.content.novel.pipeline.artifact_store import artifact_store_from_config
from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Characters to take from the tail of each prior chapter for sliding context
_CONTEXT_TAIL_CHARS: int = 800

# Maximum characters of world_data summary to inject into system prompt
_WORLD_SUMMARY_MAX_CHARS: int = 1200

# Maximum characters of foreshadowing context to inject
_FORESHADOWING_MAX_CHARS: int = 600

# Forbidden words as stated in WRITER.md §1 (pre-compiled for speed)
_BUILTIN_FORBIDDEN_WORDS: tuple[str, ...] = (
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

# How often (every N chapters) to run state.snip_history()
_SNIP_EVERY_N: int = 5


@dataclass
class WritingStage(StageRunner):
    """Whole-chapter writing stage.

    Reads:
        state.chapter_summaries — list of chapter summary dicts
        state.world_data        — world-building dict
        state.bible_serialized  — optional Production Bible dict
        state.config            — pipeline config (genre, style, state_path, …)

    Writes:
        state.chapters          — appends one dict per chapter written
        disk                    — calls state.save() after each chapter
    """

    name: str = "writing"
    words_per_chapter: int = 5000
    context_window_size: int = 3  # last N chapters used for sliding context

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self, state: PipelineState) -> PipelineState:
        """Write all pending chapters and persist state after each one."""
        if not self.validate_input(state):
            raise ValueError(
                f"[{self.name}] Input validation failed: chapter_summaries must be non-empty"
            )

        writer_constitution = self._load_writer_md(state)
        genre = state.config.get("genre", state.config.get("style", "玄幻"))
        artifact_store = artifact_store_from_config(state.config)

        for summary in state.chapter_summaries:
            chapter_num = summary.get("chapter_num", 0)

            # Skip chapters that are already written (resume support)
            if self._is_chapter_written(state, chapter_num):
                logger.info("[%s] Chapter %d already written, skipping", self.name, chapter_num)
                continue

            logger.info("[%s] Writing chapter %d …", self.name, chapter_num)

            # Build context windows
            sliding_context = self._build_sliding_context(state, chapter_num)
            bible_context = self._build_bible_context(state, summary)

            # Build prompts
            system_prompt = self._build_system_prompt(
                writer_constitution=writer_constitution,
                genre=genre,
                world_data=state.world_data,
                bible_context=bible_context,
            )
            user_prompt = self._build_user_prompt(
                summary=summary,
                sliding_context=sliding_context,
                target_words=self.words_per_chapter,
            )

            # Single LLM call — whole chapter at once
            chapter_text = self._call_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=8192,
                temperature=0.8,
            )

            # Persist draft artifact to disk immediately after generation
            artifact_store.save_artifact(chapter_num, "draft", chapter_text)

            # Rule check — no retry loop, log only
            issues = self._check_rules(chapter_text, writer_constitution)
            if issues:
                logger.warning(
                    "[%s] Chapter %d: %d style issue(s) detected: %s",
                    self.name,
                    chapter_num,
                    len(issues),
                    issues[:3],
                )
                # Persist review artifact (JSON list of issue strings)
                artifact_store.save_artifact(
                    chapter_num, "review", json.dumps(issues, ensure_ascii=False, indent=2)
                )

            # Build output dict
            chapter_output: dict[str, Any] = {
                "chapter_num": chapter_num,
                "title": summary.get("title", f"第{chapter_num}章"),
                "content": chapter_text,
                "word_count": len(chapter_text),
                "key_events": summary.get("main_events", []),
                "character_appearances": summary.get("character_appearances", []),
                "setting": summary.get("setting", ""),
                "notes": "",
                "review_issues": issues,
            }

            # Persist chapter into state and flush to disk immediately
            state.chapters.append(chapter_output)
            state_path = state.config.get("state_path", "pipeline_state.json")
            state.save(state_path)

            logger.info(
                "[%s] Chapter %d written: %d chars, %d issue(s) — saved to %s",
                self.name,
                chapter_num,
                len(chapter_text),
                len(issues),
                state_path,
            )

            # Release content from RAM (it's on disk now)
            chapter_output["content"] = "[SAVED to disk]"

            # Periodic history compaction to keep memory footprint bounded
            if chapter_num % _SNIP_EVERY_N == 0:
                state.snip_history(keep_last_n=self.context_window_size)

        state.current_stage = "writing"
        return state

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_input(self, state: PipelineState) -> bool:
        """Require at least one chapter summary before writing."""
        if not state.chapter_summaries:
            logger.error(
                "[%s] validate_input failed: state.chapter_summaries is empty", self.name
            )
            return False
        return True

    # ------------------------------------------------------------------
    # WRITER.md loader
    # ------------------------------------------------------------------

    def _load_writer_md(self, state: PipelineState) -> str:
        """Load WRITER.md constitution text.

        Search order:
        1. state.config["writer_md_path"] — explicit override
        2. Walk up from this file's location to find WRITER.md at project root
        3. Return empty string if not found (graceful degradation)
        """
        # 1. Explicit config override
        explicit_path = state.config.get("writer_md_path", "")
        if explicit_path and os.path.isfile(explicit_path):
            return self._read_file(explicit_path)

        # 2. Walk up the directory tree from this source file
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(10):  # cap traversal depth
            candidate = os.path.join(current, "WRITER.md")
            if os.path.isfile(candidate):
                return self._read_file(candidate)
            parent = os.path.dirname(current)
            if parent == current:  # reached filesystem root
                break
            current = parent

        logger.warning(
            "[%s] WRITER.md not found; writing without style constitution", self.name
        )
        return ""

    @staticmethod
    def _read_file(path: str) -> str:
        """Read a text file, returning empty string on any error."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            logger.warning("Could not read file %s: %s", path, exc)
            return ""

    # ------------------------------------------------------------------
    # Context builders
    # ------------------------------------------------------------------

    def _build_sliding_context(self, state: PipelineState, chapter_num: int) -> str:
        """Return the last N chapters' endings as a continuity window.

        Each prior chapter contributes at most _CONTEXT_TAIL_CHARS characters
        taken from its tail.  Chapters whose content has been archived ("[SAVED
        to disk]") are silently skipped.
        """
        written = [
            ch for ch in state.chapters
            if isinstance(ch, dict) and ch.get("chapter_num", 0) < chapter_num
        ]
        # Sort by chapter number and take the last N
        written.sort(key=lambda c: c.get("chapter_num", 0))
        window = written[-self.context_window_size:]

        if not window:
            return ""

        parts: list[str] = []
        for ch in window:
            content: str = ch.get("content", "")
            if not content or content.startswith("["):
                # Content already archived — nothing useful to extract
                continue
            tail = content[-_CONTEXT_TAIL_CHARS:]
            parts.append(f"【第{ch['chapter_num']}章结尾】\n{tail}")

        return "\n\n".join(parts)

    def _build_bible_context(self, state: PipelineState, summary: dict) -> str:
        """Extract relevant character and foreshadowing context from the Production Bible."""
        if not state.bible_serialized:
            return ""

        bible = state.bible_serialized
        chapter_num = summary.get("chapter_num", 0)
        appearing = set(summary.get("character_appearances", []))

        # --- Characters ---
        char_lines: list[str] = []
        for name, profile in (bible.get("characters") or {}).items():
            if appearing and name not in appearing:
                continue
            if not isinstance(profile, dict):
                continue
            role = profile.get("role", "")
            personality = profile.get("personality", "")[:80]
            hidden_agenda = profile.get("hidden_agenda", "")[:80]
            cultivation = profile.get("cultivation_realm", "")
            char_line = f"- {name}（{role}）: {personality}"
            if hidden_agenda:
                char_line += f" | 隐藏动机: {hidden_agenda}"
            if cultivation:
                char_line += f" | 境界: {cultivation}"
            char_lines.append(char_line)

        character_context = "\n".join(char_lines)

        # --- Active foreshadowing ---
        foreshadow_lines: list[str] = []
        for entry in (bible.get("foreshadowing_registry") or {}).values():
            if not isinstance(entry, dict):
                continue
            if not entry.get("is_active", True):
                continue
            setup_ch = entry.get("setup_chapter", 0)
            payoff_ch = entry.get("payoff_chapter", 999)
            if setup_ch <= chapter_num <= payoff_ch:
                desc = entry.get("setup_description", "")[:120]
                foreshadow_lines.append(f"- {desc}")

        foreshadowing_context = "\n".join(foreshadow_lines)

        parts = []
        if character_context:
            parts.append(f"=== 角色设定 ===\n{character_context}")
        if foreshadowing_context:
            foreshadow_trimmed = foreshadowing_context[:_FORESHADOWING_MAX_CHARS]
            parts.append(f"=== 伏笔提醒 ===\n{foreshadow_trimmed}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(
        self,
        writer_constitution: str,
        genre: str,
        world_data: dict,
        bible_context: str,
    ) -> str:
        """Assemble the system prompt with the constitution hard-injected."""
        sections: list[str] = []

        sections.append(f"你是一位擅长{genre}的网络文学作家。")

        if writer_constitution:
            sections.append(f"=== 创作宪法 ===\n{writer_constitution}")

        # World summary — keep it concise to leave room for chapter content
        world_summary = self._summarise_world(world_data)
        if world_summary:
            sections.append(f"=== 世界观设定 ===\n{world_summary}")

        if bible_context:
            sections.append(bible_context)

        return "\n\n".join(sections)

    def _summarise_world(self, world_data: dict) -> str:
        """Produce a compact world summary for system prompt injection."""
        if not world_data:
            return ""

        lines: list[str] = []

        name = world_data.get("name", "")
        if name:
            lines.append(f"世界名称：{name}")

        description = world_data.get("description", "")
        if description:
            lines.append(description[:300])

        main_conflict = world_data.get("main_conflict", "")
        if main_conflict:
            lines.append(f"核心冲突：{main_conflict[:200]}")

        power_system = world_data.get("power_system", {})
        if isinstance(power_system, dict):
            ps_name = power_system.get("name", "")
            levels = power_system.get("levels", [])
            if ps_name or levels:
                lines.append(f"力量体系：{ps_name} | 等级：{', '.join(str(l) for l in levels[:6])}")
        elif isinstance(power_system, str) and power_system:
            lines.append(f"力量体系：{power_system[:150]}")

        result = "\n".join(lines)
        return result[:_WORLD_SUMMARY_MAX_CHARS]

    def _build_user_prompt(
        self,
        summary: dict,
        sliding_context: str,
        target_words: int,
    ) -> str:
        """Build the per-chapter user prompt from the chapter summary."""
        chapter_num = summary.get("chapter_num", 0)
        title = summary.get("title", f"第{chapter_num}章")
        main_events = summary.get("main_events", [])
        character_appearances = summary.get("character_appearances", [])
        tension_level = summary.get("tension_level", "")
        hook = summary.get("hook", "")
        ending_hook = summary.get("ending_hook", "")
        climax = summary.get("climax", "")
        setting = summary.get("setting", "")

        # Format key events list
        events_str = ""
        if main_events:
            events_str = "\n".join(f"  - {ev}" for ev in main_events)

        parts: list[str] = []

        if sliding_context:
            parts.append(f"=== 前文连接 ===\n{sliding_context}")

        chapter_header = f"请撰写第{chapter_num}章：{title}"
        chapter_header += f"\n\n目标字数：约{target_words}字（不得少于{int(target_words * 0.85)}字）"

        if setting:
            chapter_header += f"\n主要场景：{setting}"

        if character_appearances:
            chapter_header += f"\n出场角色：{', '.join(character_appearances)}"

        if tension_level:
            chapter_header += f"\n张力级别：{tension_level}"

        parts.append(chapter_header)

        if hook:
            parts.append(f"开场钩子：{hook}")

        if events_str:
            parts.append(f"本章必须包含的情节点：\n{events_str}")

        if climax:
            parts.append(f"高潮点：{climax}")

        if ending_hook:
            parts.append(f"结尾悬念：{ending_hook}")

        character_archetypes = summary.get("character_archetypes", [])
        if character_archetypes:
            archetypes_str = "、".join(str(a) for a in character_archetypes)
            parts.append(
                f"\n=== 角色原型 ===\n本章角色应体现以下原型：{archetypes_str}\n"
            )

        parts.append(
            "写作要求：\n"
            "1. 严格遵守创作宪法中的禁词和表达规则\n"
            "2. 情感必须通过物理反应（心跳加速、手心出汗、喉头发紧）表达，禁止直接使用情感名词\n"
            "3. 角色行为必须符合其 hidden_agenda 设定\n"
            "4. 结尾留下悬念，为下一章做铺垫\n"
            "5. 直接输出章节正文，不要重复章节标题或序号"
        )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Rule checker
    # ------------------------------------------------------------------

    def _check_rules(self, text: str, writer_constitution: str) -> list[str]:
        """Scan generated text for forbidden words.

        Returns a list of issue strings (empty list = no issues).
        Does NOT trigger a retry — caller logs and continues.
        """
        issues: list[str] = []

        # Always check the built-in forbidden list from WRITER.md
        for word in _BUILTIN_FORBIDDEN_WORDS:
            count = text.count(word)
            if count:
                issues.append(f"禁词「{word}」出现{count}次")

        # Additionally scan the constitution for extra forbidden words if provided
        if writer_constitution:
            extra_forbidden = self._extract_forbidden_words(writer_constitution)
            for word in extra_forbidden:
                if word in _BUILTIN_FORBIDDEN_WORDS:
                    continue  # already checked above
                count = text.count(word)
                if count:
                    issues.append(f"禁词「{word}」出现{count}次（宪法条款）")

        return issues

    @staticmethod
    def _extract_forbidden_words(constitution: str) -> list[str]:
        """Parse forbidden word list from WRITER.md content.

        Looks for patterns like: 禁词表：[word1, word2, ...]
        or comma/space separated lists following 禁词 keywords.
        """
        words: list[str] = []

        # Pattern: 【禁词表】：[突然, 居然, ...]  or 禁词表：[...]
        match = re.search(r"禁词[表单]?[：:]\s*[\[【]([^\]】]+)[\]】]", constitution)
        if match:
            raw = match.group(1)
            for token in re.split(r"[,，、\s]+", raw):
                token = token.strip()
                if token:
                    words.append(token)

        return words

    # ------------------------------------------------------------------
    # Resume helper
    # ------------------------------------------------------------------

    @staticmethod
    def _is_chapter_written(state: PipelineState, chapter_num: int) -> bool:
        """Return True if this chapter already exists in state.chapters."""
        for ch in state.chapters:
            existing_num = (
                ch.get("chapter_num") if isinstance(ch, dict) else getattr(ch, "chapter_num", None)
            )
            if existing_num == chapter_num:
                return True
        return False
