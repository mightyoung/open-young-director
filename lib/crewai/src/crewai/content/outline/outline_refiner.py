"""大纲优化器"""

from typing import TYPE_CHECKING, List
from crewai.agent import Agent

from crewai.content.outline.outline_types import OutlineOutput, WorldOutput, ChapterOutline

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutlineRefiner:
    """大纲优化器 - 确保一致性和质量"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="小说编辑专家",
            goal="审查并优化故事大纲",
            backstory="你是一个严格的小说编辑，擅长发现连贯性问题并提供改进建议。",
            llm=llm,
        )

    def refine(
        self,
        world: WorldOutput,
        chapters: List[ChapterOutline],
    ) -> OutlineOutput:
        """
        优化大纲

        Args:
            world: 世界观
            chapters: 章节大纲列表

        Returns:
            OutlineOutput: 优化后的大纲
        """
        chapters_text = self._format_chapters(chapters)

        prompt = f"""
请审查以下大纲的一致性和质量：

【世界观】
- 世界名称: {world.name}
- 主要冲突: {world.main_conflict}

【章节大纲】
{chapters_text}

请检查以下方面：
1. 伏笔是否有回收
2. 角色行为是否一致
3. 节奏是否有起伏
4. 高潮点分布是否合理
5. 章节之间衔接是否顺畅

如果发现问题，请给出具体修改建议。
"""
        result = self.agent.run(prompt)

        # 返回优化后的大纲（简化实现：不做实际修改）
        return OutlineOutput(
            world=world,
            chapters=chapters,
            metadata={"refinement_feedback": str(result)},
        )

    def _format_chapters(self, chapters: List[ChapterOutline]) -> str:
        """格式化章节列表"""
        lines = []
        for ch in chapters:
            lines.append(f"""
=== 第{ch.chapter_num}章: {ch.title} ===
钩子: {ch.hook}
冲突: {ch.main_conflict}
事件: {', '.join(ch.key_events)}
结尾: {ch.resolution}
""")
        return "\n".join(lines)
