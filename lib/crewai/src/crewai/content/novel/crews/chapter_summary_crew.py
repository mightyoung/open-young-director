"""章节概要Crew (Chapter Summary Crew)

管理章节概要的批量生成流程：
1. 接收 volume_outlines（分卷大纲列表）
2. 调用 ChapterSummaryAgent 为每卷生成章节概要（支持并行）
3. 返回所有章节概要列表

使用示例:
    crew = ChapterSummaryCrew(config=config)
    # 顺序生成
    summaries = crew.generate(volume_outlines, world_data)
    # 并行生成（推荐）
    summaries = crew.generate_parallel(volume_outlines, world_data)
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from crewai.content.base import BaseContentCrew
from crewai.content.novel.agents.chapter_summary_agent import ChapterSummaryAgent

if TYPE_CHECKING:
    from crewai.content.novel.production_bible.section_builder import BibleSectionBuilder
    from crewai.content.novel.production_bible.bible_types import ProductionBible, BibleSection

logger = logging.getLogger(__name__)


class ChapterSummaryCrew(BaseContentCrew):
    """章节概要Crew

    管理章节概要批量生成流程。支持顺序和并行两种生成模式。

    使用示例:
        crew = ChapterSummaryCrew(config=config)
        # 顺序生成（兼容旧代码）
        summaries = crew.generate(volume_outlines, world_data)
        # 并行生成（推荐，更快）
        summaries = crew.generate_parallel(volume_outlines, world_data)
    """

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents"""
        return {
            "chapter_summary": ChapterSummaryAgent(llm=self.config.get("llm")),
        }

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        return None

    def generate(
        self,
        volume_outlines: list[dict],
        world_data: dict,
        bible: "ProductionBible | None" = None,
    ) -> list[dict]:
        """生成所有章节概要（顺序， optionally with bible）

        Args:
            volume_outlines: 分卷大纲列表
            world_data: 世界观数据
            bible: Production Bible（可选），用于约束章节概要与 canon 一致

        Returns:
            list[dict]: 所有章节概要（按卷和章节编号排序）
        """
        if bible:
            section_builder = self._get_section_builder()
            all_summaries = []
            for volume_outline in volume_outlines:
                volume_num = volume_outline.get("volume_num", 1)
                bible_section = section_builder.build_section(bible, volume_num)
                summaries = self.agents["chapter_summary"].generate_for_volume_with_bible(
                    volume_outline, world_data, volume_num, bible_section
                )
                all_summaries.extend(summaries)
            return all_summaries
        return self.agents["chapter_summary"].generate_batch(volume_outlines, world_data)

    def _get_section_builder(self) -> "BibleSectionBuilder":
        """Get or create BibleSectionBuilder instance (lazy import to avoid circular deps)."""
        from crewai.content.novel.production_bible.section_builder import BibleSectionBuilder
        return BibleSectionBuilder()

    def generate_parallel(
        self,
        volume_outlines: list[dict],
        world_data: dict,
        bible: "ProductionBible | None" = None,
        max_concurrency: int = 3,
    ) -> list[dict]:
        """并行生成所有章节概要（推荐， optionally with bible context）

        使用多线程并发调用 LLM，同时为多个卷生成章节概要。
        适用于卷数较多（≥2卷）的场景。

        Args:
            volume_outlines: 分卷大纲列表
            world_data: 世界观数据
            bible: Production Bible（可选），用于约束章节概要与 canon 一致
            max_concurrency: 最大并发数（默认3）

        Returns:
            list[dict]: 所有章节概要（按卷和章节编号排序）
        """
        if len(volume_outlines) <= 1:
            return self.generate(volume_outlines, world_data, bible=bible)

        agent = self.agents["chapter_summary"]
        section_builder = self._get_section_builder() if bible else None

        def generate_single_volume(volume_outline: dict) -> list[dict]:
            volume_num = volume_outline.get("volume_num", 1)
            if bible and section_builder:
                bible_section = section_builder.build_section(bible, volume_num)
                return agent.generate_for_volume_with_bible(
                    volume_outline, world_data, volume_num, bible_section
                )
            else:
                return agent.generate_for_volume(volume_outline, world_data, volume_num)

        all_summaries: list[dict] = []
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            futures = {executor.submit(generate_single_volume, vol): vol for vol in volume_outlines}
            for future in futures:
                try:
                    summaries = future.result()
                    if summaries:
                        all_summaries.extend(summaries)
                except Exception as e:
                    logger.warning(f"Chapter summary generation failed for volume: {e}")
                    vol = futures[future]
                    all_summaries.extend(vol.get("chapters_summary", []))

        # Sort by volume_num then chapter_num
        all_summaries.sort(key=lambda s: (s.get("volume_num", 0), s.get("chapter_num", 0)))
        return all_summaries

    def generate_with_feedback(
        self,
        volume_outlines: list[dict],
        world_data: dict,
        original_summaries: list,
        feedback: dict,
        feedback_applier: Any = None,
        bible: "ProductionBible | None" = None,
        target_chapter: int | None = None,
    ) -> list[dict]:
        """根据反馈生成调整后的章节概要（顺序模式）

        Args:
            volume_outlines: 分卷大纲列表
            world_data: 世界观数据
            original_summaries: 原始章节概要
            feedback: 结构化反馈
            feedback_applier: FeedbackApplier 实例
            bible: Production Bible
            target_chapter: 可选，指定修改的章节号

        Returns:
            调整后的章节概要
        """
        if feedback_applier is None:
            from crewai.content.novel.feedback_applier import FeedbackApplier
            feedback_applier = FeedbackApplier(llm=self.config.get("llm"))

        return feedback_applier.apply_chapter_summary_feedback(
            original_summaries, feedback, target_chapter
        )

    def generate_parallel_with_feedback(
        self,
        volume_outlines: list[dict],
        world_data: dict,
        original_summaries: list,
        feedback: dict,
        feedback_applier: Any = None,
        max_concurrency: int = 3,
        bible: "ProductionBible | None" = None,
        target_chapter: int | None = None,
    ) -> list[dict]:
        """根据反馈生成调整后的章节概要（并行模式）

        Args:
            volume_outlines: 分卷大纲列表
            world_data: 世界观数据
            original_summaries: 原始章节概要
            feedback: 结构化反馈
            feedback_applier: FeedbackApplier 实例
            max_concurrency: 最大并发数
            bible: Production Bible
            target_chapter: 可选，指定修改的章节号

        Returns:
            调整后的章节概要
        """
        if feedback_applier is None:
            from crewai.content.novel.feedback_applier import FeedbackApplier
            feedback_applier = FeedbackApplier(llm=self.config.get("llm"))

        adjusted = feedback_applier.apply_chapter_summary_feedback(
            original_summaries, feedback, target_chapter
        )
        if adjusted == original_summaries:
            # 没有变化，直接重新生成
            return self.generate_parallel(
                volume_outlines, world_data,
                bible=bible,
                max_concurrency=max_concurrency,
            )
        return adjusted
