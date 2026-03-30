"""Summary stage service - handles chapter summary generation."""
import logging
from typing import Any, tuple
from crewai.content.novel.services.base_stage_service import BaseStageService
from crewai.content.exceptions import ExecutionResult


logger = logging.getLogger(__name__)


class SummaryStageService(BaseStageService):
    """章节概要阶段服务。

    职责：
    1. 章节概要并行生成 (ChapterSummaryCrew)
    2. 保存 chapter_summaries 到 pipeline_state

    输入：
    - volume_outlines: 来自 volume 阶段
    - world_data: 来自 outline 阶段
    - bible: Production Bible

    输出：
    - chapter_summaries: 章节概要列表
    """

    def execute(self, context: dict) -> tuple[list, ExecutionResult]:
        """执行章节概要生成阶段。

        Args:
            context: 包含 volume_outlines, world_data, bible 等

        Returns:
            tuple: (chapter_summaries_list, execution_result)
        """
        self._completed_stages = []
        volume_outlines = context.get("volume_outlines", [])
        world_data = context.get("world_data", {})
        bible = context.get("bible")

        try:
            num_volumes = len(volume_outlines) if volume_outlines else 1
            max_concurrent = self.config.get("max_concurrent_volumes", 3)

            if num_volumes >= 2:
                # 并行生成多卷章节概要
                chapter_summaries = self._generate_parallel(
                    volume_outlines, world_data, max_concurrent, bible
                )
            else:
                # 串行生成
                chapter_summaries = self._generate_single(
                    volume_outlines, world_data, bible
                )

            self.add_completed_stage("summary")

            # 保存到 pipeline_state
            self.pipeline_state.set_chapter_summaries(chapter_summaries)
            self.pipeline_state.set_stage("summary")

            return chapter_summaries, self.build_execution_result()

        except Exception as e:
            logger.exception(f"Summary stage failed: {e}")
            self.add_failure(
                stage="summary",
                reason=str(e),
                details={"error_type": type(e).__name__},
                recoverable=True,
            )
            return [], self.build_execution_result()

    def _generate_parallel(self, volume_outlines: list, world_data: dict, max_concurrency: int, bible) -> list:
        """并行生成章节概要。"""
        from crewai.content.novel.crews.chapter_summary_crew import ChapterSummaryCrew

        crew = ChapterSummaryCrew(config=self.config, verbose=self.config.get("verbose", True))
        return crew.generate_parallel(
            volume_outlines,
            world_data,
            bible=bible,
            max_concurrency=max_concurrency,
        )

    def _generate_single(self, volume_outlines: list, world_data: dict, bible) -> list:
        """生成单卷章节概要。"""
        from crewai.content.novel.crews.chapter_summary_crew import ChapterSummaryCrew

        crew = ChapterSummaryCrew(config=self.config, verbose=self.config.get("verbose", True))
        return crew.generate(volume_outlines, world_data, bible=bible)
