"""章节大纲生成器"""

import json
from typing import TYPE_CHECKING
from crewai.agent import Agent

from crewai.content.outline.outline_types import ChapterOutline, WorldOutput

if TYPE_CHECKING:
    from crewai.llm import LLM


class ChapterOutlineGenerator:
    """章节大纲生成器"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="小说大纲专家",
            goal="生成引人入胜的章节大纲",
            backstory="你是一个经验丰富的网文作家，擅长设计扣人心弦的章节结构。",
            llm=llm,
        )

    def generate(
        self,
        world: WorldOutput,
        chapter_num: int,
        target_words: int,
        previous_summary: str = "",
    ) -> ChapterOutline:
        """
        生成单章大纲

        Args:
            world: 世界观
            chapter_num: 章节编号
            target_words: 目标字数
            previous_summary: 上一章概要

        Returns:
            ChapterOutline: 章节大纲
        """
        factions_str = ", ".join(f.name for f in world.factions) if world.factions else "待定"
        power_name = world.power_system.name if world.power_system else "无"

        prompt = f"""
请为第{chapter_num}章生成大纲：

【世界观背景】
- 世界名称: {world.name}
- 主要势力: {factions_str}
- 力量体系: {power_name}
- 世界设定: {world.description}

【上一章概要】
{previous_summary if previous_summary else "（无）"}

目标字数: {target_words}

请生成以下内容：
1. 章节标题
2. 开篇钩子（吸引读者继续阅读）
3. 主要冲突
4. 3-5个关键事件
5. 角色发展（本章中谁成长/变化）
6. 章节结尾处理

请用以下JSON格式返回：
{{
    "chapter_num": {chapter_num},
    "title": "章节标题",
    "hook": "开篇钩子",
    "main_conflict": "主要冲突",
    "key_events": ["事件1", "事件2", "事件3"],
    "character_developments": ["角色发展1", "角色发展2"],
    "resolution": "章节结尾处理",
    "word_target": {target_words},
    "notes": "备注（可选）"
}}
"""
        result = self.agent.run(prompt)
        return self._parse_output(result, chapter_num, target_words)

    def _parse_output(self, result, chapter_num: int, target_words: int) -> ChapterOutline:
        """解析LLM输出为ChapterOutline"""
        try:
            if hasattr(result, "raw"):
                data = json.loads(result.raw)
            elif isinstance(result, str):
                data = json.loads(result)
            else:
                data = json.loads(str(result))
        except json.JSONDecodeError:
            return ChapterOutline(
                chapter_num=chapter_num,
                title=f"第{chapter_num}章",
                hook="待补充",
                main_conflict="待补充",
                key_events=[],
                character_developments=[],
                resolution="待补充",
                word_target=target_words,
            )

        return ChapterOutline(
            chapter_num=data.get("chapter_num", chapter_num),
            title=data.get("title", f"第{chapter_num}章"),
            hook=data.get("hook", ""),
            main_conflict=data.get("main_conflict", ""),
            key_events=data.get("key_events", []),
            character_developments=data.get("character_developments", []),
            resolution=data.get("resolution", ""),
            word_target=data.get("word_target", target_words),
            notes=data.get("notes", ""),
        )
