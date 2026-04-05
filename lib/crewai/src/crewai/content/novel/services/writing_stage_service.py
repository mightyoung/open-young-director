"""Writing stage service - handles chapter writing and revision."""
import logging
from typing import Any, Tuple
from crewai.content.novel.services.base_stage_service import BaseStageService
from crewai.content.exceptions import ExecutionResult, ExecutionStatus


logger = logging.getLogger(__name__)


class WritingStageService(BaseStageService):
    """章节撰写阶段服务。

    职责：
    1. 章节撰写 (WritingCrew 或 NovelOrchestratorCrew)
    2. 章节审查 (ReviewCrew)
    3. 支持 review_each_chapter 模式
    4. 返回章节列表

    输入：
    - chapter_summaries: 章节概要列表
    - world_data: 世界观数据
    - bible: Production Bible

    输出：
    - chapters: 完成的章节列表
    """

    def execute(
        self,
        context: dict,
        review_each_chapter: bool = False,
    ) -> tuple[list, ExecutionResult]:
        """执行章节撰写阶段。

        Args:
            context: 包含 chapter_summaries, world_data, bible 等
            review_each_chapter: 是否每章写完后暂停等待确认

        Returns:
            tuple: (chapters_list, execution_result)
        """
        self._completed_stages = []
        chapter_summaries = context.get("chapter_summaries", [])
        world_data = context.get("world_data", {})
        bible = context.get("bible")

        try:
            # 使用 orchestrator 或 traditional writing crew
            if self.config.get("use_orchestrator", True):
                chapters = self._write_with_orchestrator(
                    world_data, chapter_summaries, bible, review_each_chapter
                )
            else:
                chapters = self._write_traditional(
                    world_data, chapter_summaries, review_each_chapter
                )

            self.add_completed_stage("writing")

            return chapters, self.build_execution_result()

        except Exception as e:
            logger.exception(f"Writing stage failed: {e}")
            self.add_failure(
                stage="writing",
                reason=str(e),
                details={"error_type": type(e).__name__},
                recoverable=False,  # Writing failures are not easily recoverable
            )
            return [], self.build_execution_result()

    def _write_with_orchestrator(
        self,
        world_data: dict,
        chapter_summaries: list,
        bible,
        review_each_chapter: bool,
    ) -> list:
        """使用 orchestrator 进行约束写作。"""
        from crewai.content.adapters.novel_orchestrator_crew import NovelOrchestratorCrew
        from crewai.content.adapters.knowledge_base_adapter import NovelOrchestratorAdapterConfig

        adapter_config = NovelOrchestratorAdapterConfig(
            max_subagent_concurrent=self.config.get("max_subagent_concurrent", 5),
            max_concurrent_scenes=self.config.get("max_concurrent_scenes", 3),
            enable_verification=self.config.get("enable_verification", True),
            enable_evolution=self.config.get("enable_evolution", True),
        )

        crew = NovelOrchestratorCrew(
            config=self.config,
            verbose=self.config.get("verbose", True),
            adapter_config=adapter_config,
        )

        return crew.write_chapters(
            world_data=world_data,
            chapter_summaries=chapter_summaries,
            bible=bible,
            review_each_chapter=review_each_chapter,
        )

    def _write_traditional(
        self,
        world_data: dict,
        chapter_summaries: list,
        review_each_chapter: bool,
    ) -> list:
        """使用传统 WritingCrew。"""
        from crewai.content.novel.crews.writing_crew import WritingCrew

        crew = WritingCrew(
            config=self.config,
            verbose=self.config.get("verbose", True),
        )

        return crew.write_chapters(
            world_data=world_data,
            chapter_summaries=chapter_summaries,
            review_each_chapter=review_each_chapter,
        )
