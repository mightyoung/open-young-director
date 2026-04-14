"""Novel Generator using multi-agent orchestration."""

from dataclasses import dataclass, field
from datetime import datetime
import logging
import re
from typing import Any

from writing_options import build_writing_guidance, normalize_writing_options


logger = logging.getLogger(__name__)

ABRUPT_TRANSITION_MARKERS = (
    "翌日",
    "次日",
    "第二天",
    "第三天",
    "三天后",
    "数日后",
    "几日后",
    "半个月后",
    "一个月后",
    "数月后",
    "半年后",
    "一年后",
)

TRANSITION_BRIDGE_SIGNALS = (
    "赶往",
    "来到",
    "返回",
    "回到",
    "抵达",
    "奔赴",
    "路上",
    "沿途",
    "于是",
    "因此",
    "随后",
    "不久",
    "与此同时",
    "一路",
)

HIGH_CONFIDENCE_LOCATION_SUFFIXES = (
    "城",
    "镇",
    "街",
    "巷",
    "村",
    "山",
    "峰",
    "谷",
    "崖",
    "洞",
    "林",
    "湖",
    "河",
    "海",
    "岛",
    "宫",
    "殿",
    "阁",
    "楼",
    "院",
    "府",
    "宅",
    "门",
    "宗",
    "台",
    "营",
    "关",
    "坊",
    "园",
    "寨",
    "栈",
    "庙",
    "厅",
    "室",
    "牢",
)

CONSEQUENCE_MARKERS = (
    "追杀",
    "追兵",
    "重伤",
    "伤势",
    "危机",
    "爆炸",
    "昏迷",
    "决裂",
    "生死",
    "濒死",
    "逃亡",
    "反噬",
    "崩塌",
    "暴露",
    "通缉",
    "血战",
)

CONSEQUENCE_ACKNOWLEDGEMENT_MARKERS = (
    "余波",
    "后遗症",
    "疗伤",
    "包扎",
    "恢复",
    "风波",
    "残局",
    "代价",
    "尚未",
    "仍在",
    "未散",
)

OPENING_LOCATION_PREFIX_MARKERS = (
    "晨雾笼罩",
    "夜色笼罩",
    "暮色笼罩",
    "薄雾笼罩",
    "雾气笼罩",
    "雨幕笼罩",
    "风雪笼罩",
    "钟声回荡在",
    "灯火照着",
)

DISMISSIVE_CONTINUITY_MARKERS = (
    "从未发生",
    "像没发生",
    "仿佛没发生",
    "若无其事",
    "全然不顾",
    "抛在脑后",
)

MOTION_CONTINUITY_MARKERS = (
    "离开",
    "摆脱",
    "准备",
    "赶往",
    "赶到",
    "前往",
    "转移",
    "连夜",
    "一路",
)


@dataclass
class GeneratedChapter:
    """Represents a generated chapter."""
    number: int
    title: str
    content: str
    word_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    plot_summary: dict[str, Any] | None = None
    consistency_report: dict[str, Any] | None = None
    generation_time: str = ""
    # FILM_DRAMA mode data - includes scenes, cast, beats, narrative structure
    orchestrator_result: dict[str, Any] | None = None


class NovelGeneratorAgent:
    """Agent for generating novel chapters using orchestration."""

    def __init__(self, config_manager, novel_orchestrator=None, llm_client=None):
        self.config_manager = config_manager
        self.orchestrator = novel_orchestrator
        self.llm_client = llm_client

        self.outline_loader = None
        self.outline_enforcer = None

        self._load_outline_loader()

    def _load_outline_loader(self):
        """Load outline loader and enforcer."""
        try:
            from agents.outline_loader import OutlineEnforcer, OutlineLoader

            project = self.config_manager.current_project
            if project:
                outline_dir = f"lib/knowledge_base/novels/{project.title}/outline"
                self.outline_loader = OutlineLoader(outline_dir)
                self.outline_enforcer = OutlineEnforcer(self.outline_loader)
                logger.info("OutlineLoader initialized for novel generation")
        except Exception as e:
            logger.warning(f"Could not initialize OutlineLoader: {e}")

    def generate_chapter(
        self,
        chapter_number: int,
        context: dict[str, Any],
        previous_summary: str = "",
        writing_options: dict[str, str] | None = None,
    ) -> GeneratedChapter:
        """Generate a single chapter."""
        outline_info = self._get_chapter_outline(chapter_number)

        if not outline_info:
            logger.warning(f"No outline found for chapter {chapter_number}")
            outline_info = {
                "title": f"第{chapter_number}章",
                "summary": "",
                "key_events": [],
            }

        title = outline_info.get("title", f"第{chapter_number}章")
        outline_summary = outline_info.get("summary", "")
        # P0 FIX: Include magic_line (魔帝线) in the outline so it's not lost
        magic_line = outline_info.get("magic_line", "")
        if magic_line:
            outline_summary = f"{outline_summary}；【暗线】{magic_line}"

        # Get target word count from config
        target_word_count = self._get_target_word_count()
        min_word_count = int(target_word_count * 0.8)  # Allow 20% tolerance

        # Generate with word count validation and retry
        max_retries = 2
        content = None
        orchestrator_result = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(f"[Generator] Retry {attempt}/{max_retries} for chapter {chapter_number}, previous word count was too low")

            result = self._generate_content(
                chapter_number=chapter_number,
                title=title,
                outline=outline_summary,
                previous_summary=previous_summary,
                context=context,
                retry_attempt=attempt,
                writing_options=writing_options,
            )

            content = result["content"]
            # Capture orchestrator_result from first attempt (only used on retry_attempt == 0)
            if attempt == 0 and result.get("orchestrator_result"):
                orchestrator_result = result["orchestrator_result"]

            word_count = self._count_words(content)
            logger.info(f"[Generator] Chapter {chapter_number} attempt {attempt+1}: {word_count} chars (target: {target_word_count})")

            if word_count >= min_word_count:
                logger.info(f"[Generator] Word count {word_count} meets target {target_word_count}")
                break
            if attempt < max_retries:
                logger.warning(f"[Generator] Word count {word_count} below target {target_word_count}, will retry")

        word_count = self._count_words(content)

        chapter = GeneratedChapter(
            number=chapter_number,
            title=title,
            content=content,
            word_count=word_count,
            metadata={
                "outline_summary": outline_summary,
                "key_events": outline_info.get("key_events", []),
                "magic_line": magic_line,
                "character_appearances": outline_info.get("characters", []),
                "writing_options": normalize_writing_options(writing_options),
                "generation_time": datetime.now().isoformat(),
            },
            plot_summary={
                "l1_one_line_summary": outline_summary[:100] if outline_summary else "",
                "l2_brief_summary": outline_summary,
                "l3_key_plot_points": outline_info.get("key_events", []),
                "magic_line": magic_line,
            },
            generation_time=datetime.now().isoformat(),
            orchestrator_result=orchestrator_result,
        )

        chapter.consistency_report = self._check_consistency(chapter, previous_summary, context)

        return chapter

    def _get_target_word_count(self) -> int:
        """Get target word count from config."""
        try:
            if self.config_manager and self.config_manager.generation:
                return self.config_manager.generation.chapter_word_count
        except Exception:
            pass
        return 3000  # Default fallback

    def _get_chapter_outline(self, chapter_number: int) -> dict[str, Any] | None:
        """Get chapter outline from loader."""
        if not self.outline_enforcer:
            return None

        try:
            return self.outline_enforcer.get_chapter_outline(chapter_number)
        except Exception as e:
            logger.warning(f"Could not get chapter outline: {e}")
            return None

    def _generate_content(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        context: dict[str, Any],
        retry_attempt: int = 0,
        writing_options: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Generate chapter content using LLM or orchestrator.

        Returns:
            Dict with:
                - content: str - the generated chapter content
                - orchestrator_result: Optional[Dict] - full result from orchestrator (FILM_DRAMA mode)
        """
        default_result = {"content": "", "orchestrator_result": None}

        if not self.llm_client:
            content = self._generate_fallback_content(
                chapter_number, title, outline, previous_summary, context
            )
            return {"content": content, "orchestrator_result": None}

        project = self.config_manager.current_project
        genre = project.genre if project else "玄幻"
        target_word_count = self._get_target_word_count()

        # P1 FIX: Try using orchestrator (FILM_DRAMA mode) first when available
        if self.orchestrator is not None and retry_attempt == 0:
            # Only use orchestrator on first attempt
            try:
                logger.info(f"[Generator] Using orchestrator for chapter {chapter_number}")
                orchestrator_result = self.orchestrator.orchestrate_chapter(
                    chapter_number=chapter_number,
                    chapter_outline=outline,
                    context=context,
                )
                if orchestrator_result and orchestrator_result.get("content"):
                    content = orchestrator_result["content"]
                    if len(content) > 500:
                        logger.info(f"[Generator] Orchestrator generated {len(content)} chars for chapter {chapter_number}")
                        return {"content": content, "orchestrator_result": orchestrator_result}
                    logger.warning(f"[Generator] Orchestrator content too short ({len(content)} chars), falling back to direct LLM")
            except Exception as e:
                logger.warning(f"[Generator] Orchestrator failed, falling back to direct LLM: {e}")

        # Fallback: direct LLM generation
        # Extract previous chapters from context
        previous_chapters = context.get("previous_chapters", [])
        chapter_dir = context.get("chapter_dir", "")
        world_name = context.get("world_name", "")
        character_names = context.get("character_names", [])
        protagonist_constraint = context.get("protagonist_constraint", "")
        volume_guidance = context.get("volume_guidance", "")

        prompt = self._build_generation_prompt(
            chapter_number, title, outline, previous_summary, genre,
            previous_chapters=previous_chapters, chapter_dir=chapter_dir,
            world_name=world_name, character_names=character_names,
            target_word_count=target_word_count,
            retry_attempt=retry_attempt,
            protagonist_constraint=protagonist_constraint,
            volume_guidance=volume_guidance,
            writing_options=writing_options,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            # Increase max_tokens for retry to allow longer output
            max_tokens = 15000 if retry_attempt > 0 else 12000
            content = self.llm_client.generate(messages, temperature=0.8, max_tokens=max_tokens)

            if len(content) < 500:
                logger.warning(f"Generated content too short ({len(content)} chars), using fallback")
                content = self._generate_fallback_content(
                    chapter_number, title, outline, previous_summary, context
                )

            return {"content": content, "orchestrator_result": None}

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            content = self._generate_fallback_content(
                chapter_number, title, outline, previous_summary, context
            )
            return {"content": content, "orchestrator_result": None}

    def _build_generation_prompt(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        genre: str,
        previous_chapters: list[dict] = None,
        chapter_dir: str = "",
        world_name: str = "",
        character_names: list[str] = None,
        target_word_count: int = 3000,
        retry_attempt: int = 0,
        protagonist_constraint: str = "",
        volume_guidance: str = "",
        writing_options: dict[str, str] | None = None,
    ) -> str:
        """Build generation prompt for kimi-cli (coding agent style).

        kimi-cli is a coding agent, not a pure text generator.
        We need to frame the request like a code generation task.

        Uses progressive disclosure to provide previous chapter information:
        - Level 1: Brief summary (always included)
        - Level 2: Key events and character states (if available)
        - Level 3: File path for kimi-cli to read actual content (for chapters 1-2 back)
        """
        previous_chapters = previous_chapters or []
        character_names = character_names or []
        guidance = build_writing_guidance(writing_options)
        normalized_options = guidance["normalized"]

        # Build previous chapters context with progressive disclosure
        prev_context = self._build_previous_chapters_context(
            previous_chapters, chapter_dir, chapter_number
        )

        # Build world constraints section
        world_constraints = ""
        if world_name:
            world_constraints += f"\n- 宗门名称: {world_name}（必须严格使用，不得更改）"
        if character_names:
            world_constraints += f"\n- 主要人物: {', '.join(character_names)}"

        # Add retry warning if this is a retry due to insufficient word count
        retry_warning = ""
        if retry_attempt > 0:
            retry_warning = f"""
【重要提醒 - 第{retry_attempt + 1}次生成】
上次生成的字数不足！本次生成必须确保输出中文字数达到 {target_word_count} 字以上。
请务必：
1. 充分展开情节细节，使用丰富的场景描写
2. 让人物有足够的对话和心理描写
3. 不跳过任何重要的情节点
字数要求：最少 {target_word_count} 字！
"""
        else:
            retry_warning = f"""
【字数要求】
本章必须达到 {target_word_count} 字以上。
请确保：
1. 充足的情节展开和场景描写
2. 生动的人物对话和内心活动
3. 完整的起承转合结构
"""

        prompt = f"""你是一个专业的中文玄幻小说写作助手。请根据以下信息创作小说章节。

## 章节信息
- 章节号: 第{chapter_number}章
- 标题: {title}
- 目标字数: {target_word_count}+字（必须达到）
- 题材: {genre}
{world_constraints}
{retry_warning}

## 本章大纲
{outline}

## 前情提要（渐进式披露）
{prev_context}

## 主角身份强制约束
{protagonist_constraint}

**【重要】** 上述约束必须严格遵守，不得违反。

## 本卷修订指令
{volume_guidance or "无额外修订指令，按既有大纲与前文自然推进。"}

## 写作要求
1. {guidance['perspective']}
2. 情节必须与前文连贯，承接"前情提要"中的具体细节
3. 详细的心理描写
4. 自然的人物对话，符合角色性格
5. 环境描写营造氛围
6. 高潮部分要有冲击力
7. **重要**: 如果"详细前文"中提到了具体物品、地点、人物关系，创作时必须保持一致
8. **重要**: 必须使用上述宗门名称和人物名称，不得使用其他同名或相似名称

## 风格参数
- 基础风格: {normalized_options['style']}
- {guidance['style']}
{chr(10).join(f"- {item}" for item in guidance['details'])}

## 输出格式
直接输出小说正文，不输出任何问题或解释。开头格式：{title}

"""
        return prompt

    def _build_previous_chapters_context(
        self,
        previous_chapters: list[dict],
        chapter_dir: str,
        current_chapter: int,
    ) -> str:
        """Build progressive disclosure context for previous chapters.

        Level 1: Key events + character states (always included directly)
        Level 2: Immediate previous chapter FULL content (for natural continuation)
        Level 3: Earlier chapters' paths (for reference if needed)
        """
        if not previous_chapters:
            return "(无前文，这是第一章)"

        lines = []
        lines.append("=" * 60)
        lines.append("【前情提要 - 渐进式披露机制】")
        lines.append("=" * 60)

        # Process chapters in reverse order (most recent first)
        prev_chapters_reversed = list(reversed(previous_chapters))

        for idx, prev in enumerate(prev_chapters_reversed):
            ch_num = prev.get("number", 0)
            title = prev.get("title", f"第{ch_num}章")
            content = prev.get("content", "")
            key_events = prev.get("key_events", [])
            character_states = prev.get("character_states", {})
            file_path = prev.get("file_path", "")

            is_immediate_prev = (idx == 0)  # Most recent chapter

            lines.append(f"\n【第{ch_num}章 · {title}】")
            lines.append("-" * 50)

            if is_immediate_prev:
                # Level 2: Include FULL content for immediate previous chapter
                lines.append("【完整内容 - 请务必阅读以确保情节连贯】")
                # Extract just the novel body (skip header/metadata)
                body_content = self._extract_chapter_body(content)
                lines.append(body_content[:3000])  # First 3000 chars
                if len(body_content) > 3000:
                    lines.append(f"\n... (内容过长，请阅读完整文件: {file_path})")

            # Level 1: Key events (for all chapters)
            if key_events:
                lines.append("\n关键事件:")
                for evt in key_events[:8]:
                    lines.append(f"  • {evt}")

            # Level 1: Character states
            if character_states:
                lines.append("\n角色状态:")
                for char, state in list(character_states.items())[:5]:
                    lines.append(f"  • {char}: {state}")

            # Level 3: Reference for earlier chapters
            if not is_immediate_prev and file_path:
                lines.append(f"\n[参考文件] {file_path}")

        lines.append("\n" + "=" * 60)
        lines.append("【情节连贯性检查清单】")
        lines.append("=" * 60)
        lines.append("""
在创作本章前，请确认你已:
□ 阅读了第{}章的完整内容
□ 理解了上章结尾时主角的具体位置、状态、情绪
□ 清楚了本章大纲中要求的关键情节点
□ 记住了人物关系和已发生事件的时间顺序

创作要求:
1. 本章开头必须精确承接上章结尾场景，禁止跳过或改变上章结局
2. 人物状态、物品归属、修为等级必须与前文完全一致
3. 如需引入新物品/人物，必须在情节中合理铺垫其来源
4. 禁止在没有任何铺垫的情况下改变主角已建立的特性
""".format(previous_chapters[-1].get("number", "N") if previous_chapters else "N"))

        return "\n".join(lines)

    def _extract_chapter_body(self, content: str) -> str:
        """Extract just the novel body from chapter content, skipping metadata."""
        import re
        lines = content.split("\n")
        body_lines = []
        in_body = False

        # Patterns that indicate prompt meta-text (should skip even after ---)
        # Only match complete prompt instruction lines, not normal text
        prompt_meta_patterns = [
            r"^我已经阅读了",
            r"^现在我将根据",
            r"^我将根据",
            r"^承接第.*章",
            r"^衔接上文",
            r"^根据前情提要创作",
            r"^根据上文创作",
        ]

        for line in lines:
            # Skip header and metadata
            if line.startswith("---") and not in_body:
                in_body = True
                continue
            if line.startswith("*（本章完）*"):
                break
            if not in_body and line.startswith("#"):
                continue
            if not in_body and line.startswith(">"):
                continue
            if not in_body and line.startswith("**"):
                continue

            # Skip prompt meta-text lines even after --- separator
            if in_body and any(re.match(pattern, line.strip()) for pattern in prompt_meta_patterns):
                continue

            if in_body or not line.startswith("#"):
                body_lines.append(line)

        return "\n".join(body_lines).strip()

    def _generate_fallback_content(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        context: dict[str, Any],
    ) -> str:
        """Generate fallback content when LLM is unavailable."""
        return f"""
# {title}

这一章的场景正在构思中。

## 情节概要
{outline}

## 备注
自动生成内容占位符，实际内容需要通过API生成。
""".strip()

    def _count_words(self, content: str) -> int:
        """Count Chinese characters as words."""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
        return chinese_chars

    def _normalize_text_for_match(self, text: str) -> str:
        """Normalize text for lightweight deterministic matching."""
        return re.sub(r"\s+", "", text or "")

    def _extract_previous_chapter_tail(self, context: dict[str, Any] | None) -> str:
        """Return the tail of the previous chapter when available."""
        if not context:
            return ""

        previous_chapters = context.get("previous_chapters", []) or []
        if not previous_chapters:
            return ""

        previous_content = str(previous_chapters[-1].get("content", "") or "")
        return previous_content[-400:]

    def _extract_location_anchor(self, text: str) -> str:
        """Extract a conservative location anchor from the provided text."""
        raw_text = text or ""
        normalized = self._normalize_text_for_match(raw_text)
        if not normalized:
            return ""

        suffix_pattern = "|".join(re.escape(item) for item in HIGH_CONFIDENCE_LOCATION_SUFFIXES)
        for prefix in OPENING_LOCATION_PREFIX_MARKERS:
            match = re.search(
                rf"{re.escape(prefix)}([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
                normalized,
            )
            if match:
                return match.group(1)
        patterns = (
            rf"^(?:[\u4e00-\u9fff]{{1,4}}的)?([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))(?:内|中|外|上|下|前|里)",
            rf"(?:在|于)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"(?:回到|返回|抵达|来到|赶到|赶往|奔赴|进入|踏入|冲进|躲进|潜入)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"(?:这里仍是|仍是|依旧是)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"^([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))(?:内|中|外|上|下|前|里)",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                return match.group(1)
        return ""

    def _location_anchors_conflict(self, previous_anchor: str, current_anchor: str) -> bool:
        """Check whether two extracted anchors represent different scenes."""
        if not previous_anchor or not current_anchor:
            return False
        if previous_anchor == current_anchor:
            return False
        if previous_anchor in current_anchor or current_anchor in previous_anchor:
            return False
        return True

    def _summary_prepares_current_location(self, previous_summary: str, current_anchor: str) -> bool:
        """Check whether the prior summary already establishes the upcoming destination."""
        normalized_summary = self._normalize_text_for_match(previous_summary)
        if not normalized_summary or not current_anchor:
            return False
        return current_anchor in normalized_summary and any(
            marker in normalized_summary for marker in MOTION_CONTINUITY_MARKERS
        )

    def _has_bridge_signal(self, opening: str) -> bool:
        """Detect whether the opening already contains an explicit transition bridge."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        return any(marker in normalized for marker in TRANSITION_BRIDGE_SIGNALS)

    def _extract_time_jump_marker(self, opening: str) -> str:
        """Return the first strong time-jump marker found in the opening."""
        normalized = self._normalize_text_for_match(opening)
        for marker in ABRUPT_TRANSITION_MARKERS:
            if marker in normalized:
                return marker
        return ""

    def _extract_consequence_marker(self, previous_context: str) -> str:
        """Return the first strong unresolved consequence marker from prior context."""
        normalized = self._normalize_text_for_match(previous_context)
        for marker in CONSEQUENCE_MARKERS:
            if marker in normalized:
                return marker
        return ""

    def _opening_acknowledges_consequence(self, opening: str, consequence_marker: str) -> bool:
        """Check whether the current opening acknowledges the prior consequence."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        if consequence_marker and consequence_marker in normalized:
            return True
        if (
            consequence_marker in {"追兵", "追杀", "逃亡"}
            and self._has_bridge_signal(normalized)
            and any(marker in normalized for marker in MOTION_CONTINUITY_MARKERS)
        ):
            return True
        return any(marker in normalized for marker in CONSEQUENCE_ACKNOWLEDGEMENT_MARKERS)

    def _opening_dismisses_prior_consequence(self, opening: str) -> bool:
        """Detect shallow mention patterns that explicitly dismiss prior consequences."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        return any(marker in normalized for marker in DISMISSIVE_CONTINUITY_MARKERS)

    def _build_smoothness_issue(
        self,
        category: str,
        previous_evidence: str,
        current_evidence: str,
        missing_link: str,
    ) -> dict[str, str]:
        """Create a stable issue payload for blocking smoothness failures."""
        return {
            "category": category,
            "previous_evidence": previous_evidence,
            "current_evidence": current_evidence,
            "missing_transition_or_causal_link": missing_link,
            "message": (
                f"顺畅性问题[{category}] 上一章线索「{previous_evidence or '无'}」"
                f" 与当前开篇「{current_evidence or '无'}」之间缺少{missing_link}。"
            ),
        }

    def _check_transition_continuity(
        self,
        content: str,
        previous_summary: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Check deterministic chapter-to-chapter smoothness boundaries."""
        opening = self._normalize_text_for_match(content[:600])
        previous_tail = self._extract_previous_chapter_tail(context)
        previous_context = self._normalize_text_for_match(f"{previous_summary}\n{previous_tail}")

        # Chapter 1 or empty prior context: skip continuity gate.
        if not previous_context:
            return []

        issues: list[dict[str, str]] = []
        has_bridge_signal = self._has_bridge_signal(opening)
        previous_anchor = self._extract_location_anchor(previous_tail) or self._extract_location_anchor(previous_summary)
        current_anchor = self._extract_location_anchor(opening)

        if (
            previous_anchor
            and current_anchor
            and self._location_anchors_conflict(previous_anchor, current_anchor)
            and not self._summary_prepares_current_location(previous_summary, current_anchor)
            and not has_bridge_signal
        ):
            issues.append(
                self._build_smoothness_issue(
                    category="地点跳切无承接",
                    previous_evidence=previous_anchor,
                    current_evidence=current_anchor,
                    missing_link="地点转换或行动路径交代",
                )
            )

        time_jump_marker = self._extract_time_jump_marker(opening)
        if time_jump_marker and not has_bridge_signal:
            issues.append(
                self._build_smoothness_issue(
                    category="时间跳跃无锚点",
                    previous_evidence=previous_anchor or previous_summary[:40],
                    current_evidence=time_jump_marker,
                    missing_link="时间变化后的状态承接",
                )
            )

        consequence_marker = self._extract_consequence_marker(previous_context)
        consequence_acknowledged = self._opening_acknowledges_consequence(opening, consequence_marker)
        if consequence_marker and (
            not consequence_acknowledged or self._opening_dismisses_prior_consequence(opening)
        ):
            issues.append(
                self._build_smoothness_issue(
                    category="上一章后果未被承接",
                    previous_evidence=consequence_marker,
                    current_evidence=opening[:40],
                    missing_link="上一章后果的回应或延续",
                )
            )

        issue_categories = {issue["category"] for issue in issues}
        if len(issue_categories) >= 2:
            issues.append(
                self._build_smoothness_issue(
                    category="表面流畅但因果断裂",
                    previous_evidence=" / ".join(sorted(issue_categories)),
                    current_evidence=opening[:40],
                    missing_link="地点/时间/后果之间的因果桥接",
                )
            )

        return issues

    def _build_rewrite_guidance(self, report: dict[str, Any]) -> str:
        """Build focused rewrite guidance for smoothness-related failures."""
        guidance = [
            "保留本章既有关键事件，不要靠删除冲突来伪造顺畅。",
            "开头前 2-3 句必须尽快交代谁、在哪、何时，并补上与上一章的承接。",
        ]

        blocking_issues = report.get("blocking_issues", []) if isinstance(report, dict) else []
        joined_issues = " ".join(str(item) for item in blocking_issues)
        if "地点跳切无承接" in joined_issues:
            guidance.append("补足地点变化的过渡动作、路径或抵达说明。")
        if "时间跳跃无锚点" in joined_issues:
            guidance.append("交代时间跨度后的状态变化、缺失时段影响或切换原因。")
        if "上一章后果未被承接" in joined_issues:
            guidance.append("明确回应上一章遗留的危机、伤势、追击或未完成动作。")
        if "表面流畅但因果断裂" in joined_issues:
            guidance.append("把事件顺序改写为因果推进，避免只用时间顺序硬接。")

        return " ".join(guidance)

    def _check_consistency(
        self,
        chapter: GeneratedChapter,
        previous_summary: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check consistency of generated chapter and auto-extract character states."""
        content = chapter.content
        character_states = {}
        character_consistency = []
        plot_consistency = []
        recommendations = []

        # P2 FIX: Auto-extract character states from content
        # Match actual content format: quoted dialogue + attribution, or narration with character name
        import re

        # P1 FIX: Dynamic character names from context (fallback to minimal set)
        if context:
            known_char_names = context.get("known_char_names", [])
        else:
            known_char_names = []
        if not known_char_names:
            # Fallback: minimal set that should always be present in this novel
            known_char_names = {
                "韩林", "柳如烟", "叶尘",
            }

        # P1 FIX: Extended dialogue suffixes (all common Chinese dialogue verbs)
        dialogue_suffixes = r'(?:的|声音|说道|问道|回答|喊道|轻声道|冷笑道|怒道|叹道|低声道|低语道|喃喃道|沉声道|厉声道|朗声道|颤声道|哽咽道|哭诉道|怒吼道|暴喝道|冷声道|淡声道|平静道|缓缓道|郑重道|轻叹道|悲叹道|惨笑道|嗤笑道|高声道|扬声道|宣判道|陈述道|补充道|提醒道|告诫道|警告道|解释道|说明道|断言道|坚称道|声称道|争辩道|抗辩道|认命道|绝望道|茫然道|恍惚道|清醒道|断续道)'

        # Extended suffix pattern for char name extraction
        char_name_suffix_pattern = r'([\u4e00-\u9fff]{2,4})' + dialogue_suffixes

        # Pattern 1a: Double quotes "" (non-greedy) followed by attribution
        # e.g., "好。"测灵台上的声音 -> dialogue="好", attribution="测灵台上的声音"
        quoted_dialogue_pattern = re.compile(
            r'"([^"]+?)"\s*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r')',
            re.DOTALL
        )
        # Pattern 1b: Chinese corner brackets 『』
        quoted_dialogue_pattern_alt1 = re.compile(
            r'『([^』]+?)』\s*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r')',
            re.DOTALL
        )
        # Pattern 1c: Chinese corner brackets 「」
        quoted_dialogue_pattern_alt2 = re.compile(
            r'「([^」]+?)」\s*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r')',
            re.DOTALL
        )
        # Pattern 1d: Dash-bounded dialogue "——对话——"
        quoted_dialogue_pattern_dash = re.compile(
            r'[""'']?——([^——]+?)——[""'']?(?:\\s)*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r')?',
            re.DOTALL
        )
        # Pattern 1e: Colon format "角色："对话"" or 角色："对话"
        quoted_dialogue_pattern_colon = re.compile(
            r'([\u4e00-\u9fff]{2,4})[：:]"([^"]+?)"\s*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r')?',
            re.DOTALL
        )

        for pattern in [quoted_dialogue_pattern, quoted_dialogue_pattern_alt1, quoted_dialogue_pattern_alt2]:
            for match in pattern.finditer(content):
                dialogue = match.group(1)[:40]
                attribution = match.group(2)
                char_match = re.search(char_name_suffix_pattern, attribution)
                if char_match:
                    char_name = char_match.group(1)
                    if char_name in known_char_names and char_name not in character_states:
                        character_states[char_name] = f"「{dialogue}」"

        # Pattern 1d: Dash-bounded
        for match in quoted_dialogue_pattern_dash.finditer(content):
            dialogue = match.group(1)[:40]
            attribution = match.group(2) if match.group(2) else ""
            if attribution:
                char_match = re.search(char_name_suffix_pattern, attribution)
                if char_match:
                    char_name = char_match.group(1)
                    if char_name in known_char_names and char_name not in character_states:
                        character_states[char_name] = f"「{dialogue}」"
            else:
                # Try to find character name before the dash
                start = max(0, match.start() - 10)
                prefix = content[start:match.start()]
                for char_name in known_char_names:
                    if char_name in prefix and char_name not in character_states:
                        character_states[char_name] = f"「{dialogue}」"
                        break

        # Pattern 1e: Colon format
        for match in quoted_dialogue_pattern_colon.finditer(content):
            char_name = match.group(1)
            dialogue = match.group(2)[:40]
            if char_name in known_char_names and char_name not in character_states:
                character_states[char_name] = f"「{dialogue}」"

        # Pattern 2: Character name followed by narration (with extended verb/action list)
        # e.g., 韩林深吸一口气，迈步走向...
        # e.g., 柳如烟当众撕毁婚书...
        char_action_pattern = re.compile(
            r'([\u4e00-\u9fff]{2,4})(?:深吸一口气|缓步|缓缓|目光|看着|听着|心中|说道|问道|回答|喊道|轻声|冷笑|怒视|转身|停下|抬起头|低下头|握紧|松开|举起|放下|迈步|抬眸|皱眉|微笑|叹息|摇头|点头|睁大|眯起|愣住|回过神来|颤了颤|咬紧|跪下|站起身|坐起身|躺下|闭上眼|睁开眼|转过身|回过头|垂下头|昂起头|板着脸|沉下脸|挤出笑|冷冷地|缓缓地|静静地|默默地|呆呆地|悄悄|轻声|高声|低声|朗声|沉声|厉声|哽咽|颤抖|平静|从容|镇定|冷笑|轻笑|大笑|苦笑|傻笑|狞笑|微笑|暗笑|讨好|赔笑|皮笑肉不笑)',
            re.DOTALL
        )
        for match in char_action_pattern.finditer(content):
            char_name = match.group(1)
            if char_name in known_char_names and char_name not in character_states:
                start = max(0, match.start() - 5)
                end = min(len(content), match.end() + 30)
                snippet = content[start:end].replace("\n", " ").strip()
                character_states[char_name] = snippet[:80]

        # Pattern 3: Find known character names that appear in content
        for char_name in known_char_names:
            if char_name not in character_states and char_name in content:
                occurrences = list(re.finditer(re.escape(char_name), content))
                if occurrences:
                    for occ in occurrences[:3]:
                        start = max(0, occ.start() - 10)
                        end = min(len(content), occ.end() + 20)
                        snippet = content[start:end].replace("\n", " ").strip()
                        if len(snippet) > 3 and not snippet.startswith(("...", "……")):
                            character_states[char_name] = snippet[:80]
                            break

        # Check outline key events against content
        key_events = chapter.metadata.get("key_events", [])
        outline_summary = chapter.metadata.get("outline_summary", "")
        magic_line = chapter.metadata.get("magic_line", "")

        missing_events = []
        for event in key_events:
            if len(event) < 4:
                continue
            if event not in content:
                missing_events.append(event)

        # Score based on completeness
        event_score = 1.0 if len(missing_events) == 0 else max(0, 1.0 - len(missing_events) / max(len(key_events), 1))
        char_score = min(1.0, len(character_states) / 3) if character_states else 0.5
        overall_score = round((event_score * 0.6 + char_score * 0.4) * 10, 1)

        if missing_events:
            recommendations.append(f"缺少关键事件: {'; '.join(missing_events[:3])}")

        if not character_states:
            recommendations.append("未能提取角色状态，请检查角色对话格式")
            overall_score = max(overall_score, 5.0)

        continuity_issues = self._check_transition_continuity(content, previous_summary, context)
        blocking_issues = [issue["message"] for issue in continuity_issues]
        issue_types = ["scene_or_timeline_disconnect"] if blocking_issues else []
        invalid = bool(blocking_issues or missing_events)
        rewrite_guidance = ""

        if blocking_issues:
            overall_score = min(overall_score, 4.8)
            recommendations.extend(blocking_issues)
            rewrite_guidance = self._build_rewrite_guidance(
                {"blocking_issues": blocking_issues, "missing_events": missing_events}
            )
            recommendations.append(f"顺畅性重写建议: {rewrite_guidance}")

        return {
            "character_consistency": character_consistency,
            "character_states": character_states,
            "plot_consistency": plot_consistency,
            "missing_events": missing_events,
            "overall_score": overall_score,
            "recommendations": recommendations,
            "blocking_issues": blocking_issues,
            "issue_types": issue_types,
            "invalid": invalid,
            "smoothness_details": continuity_issues,
            "rewrite_guidance": rewrite_guidance,
        }


def get_novel_generator(config_manager, novel_orchestrator=None, llm_client=None) -> NovelGeneratorAgent:
    """Get a NovelGeneratorAgent instance."""
    return NovelGeneratorAgent(
        config_manager=config_manager,
        novel_orchestrator=novel_orchestrator,
        llm_client=llm_client,
    )
