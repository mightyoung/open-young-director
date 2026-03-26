"""大纲引擎 - 主入口"""

from typing import TYPE_CHECKING

from crewai.content.outline.chapter_outline import ChapterOutlineGenerator
from crewai.content.outline.outline_refiner import OutlineRefiner
from crewai.content.outline.outline_types import (
    ChapterOutline,
    OutlineOutput,
    WorldOutput,
)
from crewai.content.outline.world_builder import WorldBuilder


if TYPE_CHECKING:
    from crewai.llm import LLM


class OutlineEngine:
    """大纲引擎 - 生成完整故事大纲"""

    def __init__(self, llm: "LLM" = None):
        self.world_builder = WorldBuilder(llm)
        self.chapter_generator = ChapterOutlineGenerator(llm)
        self.refiner = OutlineRefiner(llm)

    def generate(
        self,
        theme: str,
        style: str,
        target_words: int,
        num_chapters: int,
    ) -> OutlineOutput:
        """
        生成完整大纲

        Args:
            theme: 故事主题
            style: 小说风格 (xianxia, doushi, etc.)
            target_words: 目标总字数
            num_chapters: 章节数量

        Returns:
            OutlineOutput: 完整大纲（世界观 + 章节大纲）
        """
        # 1. 构建世界观
        world = self.world_builder.build(theme, style)

        # 2. 生成章节大纲
        chapters: list[ChapterOutline] = []
        previous_summary = ""

        for i in range(num_chapters):
            chapter = self.chapter_generator.generate(
                world=world,
                chapter_num=i + 1,
                target_words=target_words // num_chapters,
                previous_summary=previous_summary,
            )
            chapters.append(chapter)

            # 更新previous_summary
            previous_summary = f"第{i+1}章: {chapter.title} - {chapter.main_conflict}"

        # 3. 优化大纲
        refined = self.refiner.refine(world, chapters)

        return refined

    def generate_chapters_only(
        self,
        world: WorldOutput,
        num_chapters: int,
        target_words_per_chapter: int,
    ) -> list[ChapterOutline]:
        """
        仅为已有世界观生成章节大纲

        Args:
            world: 已有的世界观
            num_chapters: 章节数量
            target_words_per_chapter: 每章目标字数

        Returns:
            List[ChapterOutline]: 章节大纲列表
        """
        chapters: list[ChapterOutline] = []
        previous_summary = ""

        for i in range(num_chapters):
            chapter = self.chapter_generator.generate(
                world=world,
                chapter_num=i + 1,
                target_words=target_words_per_chapter,
                previous_summary=previous_summary,
            )
            chapters.append(chapter)
            previous_summary = f"第{i+1}章: {chapter.title} - {chapter.main_conflict}"

        return chapters

    def group_chapters_by_weave_points(self, chapters: list[ChapterOutline]) -> list[list[int]]:
        """Group chapters by weave points for potential parallel execution.

        Chapters within the same group can be written in parallel (they share
        the same weave_point or are between weave points). Groups must be
        written sequentially to maintain continuity.

        Args:
            chapters: List of ChapterOutline objects

        Returns:
            List of chapter number groups, e.g., [[1, 2], [3, 4, 5], [6]]
        """
        if not chapters:
            return []

        groups = []
        current_group = []

        for ch in chapters:
            chapter_num = ch.number if hasattr(ch, 'number') else ch.get('number', 0)
            is_weave_point = getattr(ch, 'weave_point', False) or ch.get('weave_point', False)

            if is_weave_point:
                # Start new group
                if current_group:
                    groups.append(current_group)
                current_group = [chapter_num]
            else:
                current_group.append(chapter_num)

        if current_group:
            groups.append(current_group)

        return groups
