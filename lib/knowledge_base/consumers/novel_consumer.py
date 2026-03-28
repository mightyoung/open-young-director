# -*- encoding: utf-8 -*-
"""Novel Consumer - transforms raw scene data into novel text."""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseConsumer

logger = logging.getLogger(__name__)


class NovelConsumer(BaseConsumer):
    """Novel consumer - generates novel text from raw scene data.

    Transforms FILM_DRAMA scene data (beats, character interactions,
    scene descriptions, narration) into coherent novel text.

    Output format:
        str: Generated novel text in Chinese
    """

    @property
    def consumer_type(self) -> str:
        """Return consumer type."""
        return "novel"

    async def query(self, scene_id: str, **kwargs) -> Dict[str, Any]:
        """Query raw scene data for novel generation.

        Args:
            scene_id: The scene identifier
            **kwargs: Additional query parameters

        Returns:
            Raw scene data dictionary with beats, character states,
            scene descriptions, and narration pieces
        """
        if self.scene_store is None:
            raise ValueError("scene_store not configured")

        # Get scene data from store
        scene_data = await self.scene_store.get_scene(scene_id)

        if not scene_data:
            raise ValueError(f"Scene not found: {scene_id}")

        return scene_data

    async def generate(self, raw_data: Dict[str, Any], **kwargs) -> str:
        """Generate novel text from raw scene data.

        Uses the LLM client to transform beats, character interactions,
        and scene descriptions into cohesive novel text.

        Args:
            raw_data: Raw scene data containing:
                - beats: List of plot beats with character interactions
                - character_states: Character emotional/physical states
                - scene_descriptions: Visual scene descriptions
                - narration_pieces: Narration fragments
                - emotional_arc: Scene emotional arc
            **kwargs: Additional generation parameters:
                - style: Writing style (default: "literary")
                - perspective: Narrative perspective (default: "third_limited")
                - word_count_target: Target word count

        Returns:
            str: Generated novel text in Chinese
        """
        if self.llm_client is None:
            raise ValueError("llm_client not configured")

        # Extract components from raw data
        beats = raw_data.get("beats", [])
        character_states = raw_data.get("character_states", {})
        scene_descriptions = raw_data.get("scene_descriptions", [])
        narration_pieces = raw_data.get("narration_pieces", [])
        emotional_arc = raw_data.get("emotional_arc", {})
        chapter_info = raw_data.get("chapter_info", {})
        background = raw_data.get("background", "")

        # Build generation prompt
        prompt = self._build_novel_prompt(
            beats=beats,
            character_states=character_states,
            scene_descriptions=scene_descriptions,
            narration_pieces=narration_pieces,
            emotional_arc=emotional_arc,
            chapter_info=chapter_info,
            background=background,
            **kwargs,
        )

        # Generate novel text
        messages = [{"role": "user", "content": prompt}]
        novel_text = self.llm_client.generate(messages)

        return novel_text

    def _build_novel_prompt(
        self,
        beats: List[Dict],
        character_states: Dict[str, List],
        scene_descriptions: List[str],
        narration_pieces: List[str],
        emotional_arc: Dict,
        chapter_info: Dict,
        background: str,
        **kwargs,
    ) -> str:
        """Build the novel generation prompt.

        Args:
            beats: Plot beats with character interactions
            character_states: Character state changes
            scene_descriptions: Visual scene descriptions
            narration_pieces: Narration fragments
            emotional_arc: Emotional arc data
            chapter_info: Chapter metadata
            background: Story background
            **kwargs: Additional parameters

        Returns:
            Formatted prompt string
        """
        style = kwargs.get("style", "literary")
        perspective = kwargs.get("perspective", "third_limited")
        word_count = kwargs.get("word_count_target", 3000)

        # Format beats
        beats_text = self._format_beats(beats)

        # Format character states
        chars_text = self._format_character_states(character_states)

        # Format scene descriptions
        scenes_text = "\n".join(f"- {desc}" for desc in scene_descriptions[:5])

        # Format narration pieces
        narration_text = "\n".join(f"- {n}" for n in narration_pieces[:5])

        # Format emotional arc
        arc_text = ""
        if emotional_arc:
            arc_text = f"""
情感弧线:
- 起始状态: {emotional_arc.get('start_state', '未知')}
- 高潮状态: {emotional_arc.get('peak_state', '未知')}
- 结束状态: {emotional_arc.get('end_state', '未知')}
"""

        # Build chapter context
        chapter_context = ""
        if chapter_info:
            chapter_context = f"""
章节信息:
- 章节号: {chapter_info.get('chapter_number', '未知')}
- 章节标题: {chapter_info.get('title', '未知')}
"""

        prompt = f"""<identity>
你是一个资深玄幻小说作者，擅长描写修仙、古风题材。
你的文字流畅优美，情节紧凑，人物鲜活。
</identity>

<context>
{chapter_context}

故事背景:
{background}

情感弧线:
{arc_text}
</context>

<source_material>
场景描述:
{scenes_text}

叙述片段:
{narration_text}

角色状态变化:
{chars_text}

情节发展:
{beats_text}
</source_material>

<requirements>
写作风格: {style}
叙事视角: {perspective}
目标字数: 约{word_count}字

重要规则:
1. 直接输出小说正文，不要输出任何思考过程或说明
2. 使用「」标注对话，使用（）标注心理活动
3. 描写要细腻，但不要冗余
4. 保持人物性格一致性
5. 遵循情节发展的逻辑顺序
6. 不要使用占位符如"[此处描写...]"或"[待补充]"
7. 场景转换时使用空行分隔
</requirements>

请根据以上素材，创作小说正文:
"""
        return prompt

    def _format_beats(self, beats: List[Dict]) -> str:
        """Format plot beats for prompt.

        Args:
            beats: List of plot beat dictionaries

        Returns:
            Formatted beats text
        """
        if not beats:
            return "（无具体情节）"

        lines = []
        for i, beat in enumerate(beats, 1):
            beat_type = beat.get("beat_type", "unknown")
            description = beat.get("description", "")
            characters = beat.get("expected_chars", [])

            char_str = "、".join(characters) if characters else "无"
            lines.append(f"{i}. [{beat_type}] {description} (出场: {char_str})")

        return "\n".join(lines)

    def _format_character_states(
        self, character_states: Dict[str, List]
    ) -> str:
        """Format character states for prompt.

        Args:
            character_states: Dict of character_name -> states list

        Returns:
            Formatted character states text
        """
        if not character_states:
            return "（无角色状态信息）"

        lines = []
        for char_name, states in character_states.items():
            lines.append(f"\n{char_name}:")
            for state in states[:3]:  # Limit to 3 states per character
                emotional = state.get("emotional_state", "未知")
                physical = state.get("physical_state", "未知")
                dialogue_context = state.get("dialogue_context", "")
                lines.append(f"  - 情绪: {emotional}, 状态: {physical}")
                if dialogue_context:
                    lines.append(f"    对话情境: {dialogue_context}")

        return "\n".join(lines) if lines else "（无角色状态信息）"
