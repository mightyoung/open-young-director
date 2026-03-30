"""Volume stage service - handles volume outline generation."""
import logging
from typing import Any, tuple
from crewai.content.novel.services.base_stage_service import BaseStageService
from crewai.content.exceptions import ExecutionResult


logger = logging.getLogger(__name__)


class VolumeStageService(BaseStageService):
    """分卷大纲阶段服务。

    职责：
    1. 分卷大纲并行生成 (VolumeOutlineCrew)
    2. 保存 volume_outlines 到 pipeline_state

    输入：
    - plot_data: 来自 outline 阶段的情节数据
    - world_data: 来自 outline 阶段的世界观数据

    输出：
    - volume_outlines: 分卷大纲列表
    """

    def execute(self, context: dict) -> tuple[list, ExecutionResult]:
        """执行分卷大纲生成阶段。

        Args:
            context: 包含 plot_data, world_data, bible 等

        Returns:
            tuple: (volume_outlines_list, execution_result)
        """
        self._completed_stages = []
        plot_data = context.get("plot_data", {})
        world_data = context.get("world_data", {})
        bible = context.get("bible")

        try:
            num_volumes = self.config.get("num_volumes", 3)
            max_concurrent = self.config.get("max_concurrent_volumes", 3)

            if num_volumes >= 2:
                # 并行生成多卷大纲
                volume_outlines = self._generate_parallel(plot_data, world_data, max_concurrent, bible)
            else:
                # 串行生成单卷大纲
                volume_outlines = self._generate_single(plot_data, world_data, bible)

            self.add_completed_stage("volume")

            # 保存到 pipeline_state
            self.pipeline_state.set_volume_outlines(volume_outlines)
            self.pipeline_state.set_stage("volume")

            return volume_outlines, self.build_execution_result()

        except Exception as e:
            logger.exception(f"Volume stage failed: {e}")
            self.add_failure(
                stage="volume",
                reason=str(e),
                details={"error_type": type(e).__name__},
                recoverable=True,  # Volume can be regenerated
            )
            return [], self.build_execution_result()

    def _generate_parallel(self, plot_data: dict, world_data: dict, max_concurrency: int, bible) -> list:
        """并行生成分卷大纲。"""
        from crewai.content.novel.crews.volume_outline_crew import VolumeOutlineCrew

        crew = VolumeOutlineCrew(config=self.config, verbose=self.config.get("verbose", True))
        return crew.generate_parallel(
            plot_data,
            world_data,
            max_concurrency=max_concurrency,
            bible=bible,
            verify=True,
        )

    def _generate_single(self, plot_data: dict, world_data: dict, bible) -> list:
        """生成单卷大纲。"""
        from crewai.content.novel.crews.volume_outline_crew import VolumeOutlineCrew

        crew = VolumeOutlineCrew(config=self.config, verbose=self.config.get("verbose", True))
        return crew.generate(plot_data, world_data, bible=bible)
