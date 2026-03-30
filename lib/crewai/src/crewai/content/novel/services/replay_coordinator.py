"""Replay coordinator - handles resume/replay logic based on seed."""
import logging
from typing import Any, Optional
from crewai.content.novel.seed_mechanism import SeedConfig


logger = logging.getLogger(__name__)


class ReplayPlan:
    """重放计划。

    描述了需要重新执行的阶段和需要保留的数据。
    """

    def __init__(
        self,
        regenerate_all: bool = False,
        regenerate_world: bool = False,
        regenerate_outline: bool = False,
        regenerate_chapters: bool = False,
        dirty_chapters: list = None,
        preserve: list = None,
    ):
        self.regenerate_all = regenerate_all
        self.regenerate_world = regenerate_world
        self.regenerate_outline = regenerate_outline
        self.regenerate_chapters = regenerate_chapters
        self.dirty_chapters = dirty_chapters or []
        self.preserve = preserve or []

    def should_regenerate_world(self) -> bool:
        return self.regenerate_world

    def should_regenerate_outline(self) -> bool:
        return self.regenerate_outline

    def should_regenerate_chapters(self) -> bool:
        return self.regenerate_chapters

    def __repr__(self) -> str:
        return (
            f"ReplayPlan(regenerate_all={self.regenerate_all}, "
            f"regenerate_world={self.regenerate_world}, "
            f"regenerate_outline={self.regenerate_outline}, "
            f"regenerate_chapters={self.regenerate_chapters}, "
            f"dirty_chapters={self.dirty_chapters})"
        )


class ReplayCoordinator:
    """重放协调器。

    职责：
    1. 根据 seed_config 计算重放计划
    2. 决定哪些阶段需要重新生成
    3. 管理 pipeline_state 的恢复逻辑

    使用方式：
    - 加载 pipeline_state 后调用 compute_replay_plan()
    - 根据返回的 ReplayPlan 修改 pipeline_state
    """

    def __init__(self, pipeline_state: Any):
        self.pipeline_state = pipeline_state

    def compute_replay_plan(self, seed_config: SeedConfig = None) -> ReplayPlan:
        """计算重放计划。

        Args:
            seed_config: Seed 配置

        Returns:
            ReplayPlan: 描述需要重新执行的阶段
        """
        if seed_config is None:
            # 没有 seed，全部重新生成
            return ReplayPlan(regenerate_all=True)

        saved_seed_config = self.pipeline_state.seed_config

        # 比较 seed_config 是否匹配
        if saved_seed_config is None:
            # 旧状态没有 seed_config，需要重新生成核心内容
            return ReplayPlan(regenerate_all=True)

        if not seed_config.matches(saved_seed_config):
            # Seed 不匹配，重新生成核心内容
            return ReplayPlan(regenerate_all=True)

        # Seed 匹配，检查脏章节
        dirty_chapters = self.pipeline_state.dirty_chapters
        if dirty_chapters:
            return ReplayPlan(
                regenerate_chapters=True,
                dirty_chapters=dirty_chapters,
                preserve=["world_data", "plot_data", "volume_outlines", "chapter_summaries"],
            )

        # Seed 匹配且没有脏章节，使用缓存状态
        return ReplayPlan()

    def prepare_pipeline_state_for_resume(self, replay_plan: ReplayPlan) -> None:
        """根据重放计划准备 pipeline_state。

        修改 self.pipeline_state 以反映重放计划。

        Args:
            replay_plan: 重放计划
        """
        if replay_plan.regenerate_all:
            # 清除所有数据，重新开始
            self.pipeline_state.world_data = {}
            self.pipeline_state.plot_data = {}
            self.pipeline_state.volume_outlines = []
            self.pipeline_state.chapter_summaries = []
            self.pipeline_state.chapters = []
            self.pipeline_state.current_stage = "init"
            logger.info("ReplayPlan: regenerating all core content")

        elif replay_plan.regenerate_world:
            # 只保留 outline 之前的数据
            self.pipeline_state.world_data = {}
            self.pipeline_state.plot_data = {}
            self.pipeline_state.current_stage = "init"
            logger.info("ReplayPlan: regenerating world and outline")

        elif replay_plan.regenerate_outline:
            # 只重新生成 plot
            self.pipeline_state.plot_data = {}
            self.pipeline_state.current_stage = "outline"
            logger.info("ReplayPlan: regenerating outline/plot")

        elif replay_plan.regenerate_chapters:
            # 标记脏章节需要重新生成
            self.pipeline_state.clear_dirty_chapters()
            logger.info(f"ReplayPlan: regenerating chapters {replay_plan.dirty_chapters}")
