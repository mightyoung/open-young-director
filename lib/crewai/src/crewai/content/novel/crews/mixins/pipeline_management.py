"""NovelCrew pipeline management mixin.

Provides pipeline state initialization, loading, and saving.
Extracted from novel_crew.py for better separation of concerns.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crewai.content.novel.seed_mechanism import SeedConfig
    from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)


class PipelineManagementMixin:
    """Mixin providing pipeline state management methods.

    Subclasses must have:
    - config: dict
    - _pipeline_state: PipelineState | None
    - _chapters_to_regenerate: set[int] | None
    """

    def load_pipeline_state(self, path: str) -> "PipelineState":
        """从磁盘加载流水线状态

        Args:
            path: 状态文件路径

        Returns:
            PipelineState: 加载的状态
        """
        from crewai.content.novel.pipeline_state import PipelineState
        self._pipeline_state = PipelineState.load(path)
        return self._pipeline_state

    def save_pipeline_state(self, path: str) -> None:
        """保存流水线状态到磁盘

        Args:
            path: 状态文件路径
        """
        self.pipeline_state.save(path)

    def _init_pipeline_state(
        self,
        pipeline_state_path: str | None,
        seed: str | None,
        seed_config: "SeedConfig | None",
    ) -> str:
        """初始化流水线状态，支持从断点恢复和确定性重放。

        Args:
            pipeline_state_path: 状态文件路径（用于断点续跑）
            seed: 确定性重放种子
            seed_config: seed 配置对象

        Returns:
            当前阶段名称 (current_stage)
        """
        from crewai.content.novel.pipeline_state import PipelineState

        if pipeline_state_path:
            try:
                loaded_state = PipelineState.load(pipeline_state_path)
                replay_plan = loaded_state.get_replay_plan(seed_config)
                approval_preserve = (
                    loaded_state.preserve_approval_history()
                    if not replay_plan.regenerate_all
                    else {}
                )

                if replay_plan.regenerate_all:
                    logger.warning(
                        f"Regenerating all: seed_config mismatch or no seed_config found. "
                        f"Will regenerate core content (world, outline, etc.)"
                    )
                    self._pipeline_state = PipelineState(
                        config=dict(self.config) if hasattr(self.config, "keys") else {}
                    )
                    self._pipeline_state.seed = seed
                    if seed_config:
                        self._pipeline_state.seed_config = seed_config
                elif replay_plan.should_regenerate_world():
                    logger.info(
                        f"Regenerating from world stage, preserving: {replay_plan.preserve}"
                    )
                    self._pipeline_state = loaded_state
                    self._pipeline_state.world_data = {}
                    self._pipeline_state.plot_data = {}
                    self._pipeline_state.current_stage = "init"
                elif replay_plan.should_regenerate_outline():
                    logger.info(
                        f"Regenerating from outline stage, preserving: {replay_plan.preserve}"
                    )
                    self._pipeline_state = loaded_state
                    self._pipeline_state.plot_data = {}
                    self._pipeline_state.current_stage = "outline"
                elif (
                    replay_plan.should_regenerate_chapters()
                    and replay_plan.dirty_chapters
                ):
                    logger.info(
                        f"Regenerating chapters: {replay_plan.dirty_chapters}"
                    )
                    self._pipeline_state = loaded_state
                    self._chapters_to_regenerate = set(replay_plan.dirty_chapters)
                    self.pipeline_state.dirty_chapters.update(
                        replay_plan.dirty_chapters
                    )
                else:
                    logger.info("Using cached state (no regeneration needed)")
                    self._pipeline_state = loaded_state

                if approval_preserve:
                    self._pipeline_state.restore_approval_history(approval_preserve)

            except FileNotFoundError:
                logger.info(
                    f"Pipeline state file not found: {pipeline_state_path}, starting fresh"
                )
                self._pipeline_state = PipelineState(
                    config=dict(self.config) if hasattr(self.config, "keys") else {}
                )
                self._pipeline_state.seed = seed
                if seed_config:
                    self._pipeline_state.seed_config = seed_config

        return self.pipeline_state.current_stage
