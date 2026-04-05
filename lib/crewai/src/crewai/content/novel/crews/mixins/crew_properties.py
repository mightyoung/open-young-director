"""NovelCrew crew properties mixin.

Provides lazy-loading properties for all sub-crews and agents.
Extracted from novel_crew.py for better separation of concerns.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from crewai.content.novel.agents.world_agent import WorldCrew
    from crewai.content.novel.agents.outline_agent import OutlineCrew
    from crewai.content.novel.agents.volume_outline_agent import VolumeOutlineCrew
    from crewai.content.novel.agents.chapter_summary_agent import ChapterSummaryCrew
    from crewai.content.novel.agents.writing_agent import WritingCrew
    from crewai.content.novel.agents.review_agent import ReviewCrew
    from crewai.content.novel.agents.plot_agent import PlotAgent
    from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator
    from crewai.content.novel.crews.novel_orchestrator_crew import NovelOrchestratorCrew
    from crewai.content.novel.pipeline_state import PipelineState


class CrewPropertiesMixin:
    """Mixin providing lazy-loading crew/agent properties.

    Subclasses must have:
    - config: dict
    - verbose: bool
    - _world_crew: WorldCrew | None
    - _outline_crew: OutlineCrew | None
    - _volume_outline_crew: VolumeOutlineCrew | None
    - _chapter_summary_crew: ChapterSummaryCrew | None
    - _writing_crew: WritingCrew | None
    - _review_crew: ReviewCrew | None
    - _plot_agent: PlotAgent | None
    - _outline_evaluator: OutlineEvaluator | None
    - _orchestrator_crew: NovelOrchestratorCrew | None
    - _pipeline_state: PipelineState | None
    - entity_memory: Any
    - continuity_tracker: Any
    """

    @property
    def world_crew(self) -> "WorldCrew":
        """获取世界观构建Crew"""
        if self._world_crew is None:
            from crewai.content.novel.agents.world_agent import WorldCrew
            self._world_crew = WorldCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._world_crew

    @property
    def outline_crew(self) -> "OutlineCrew":
        """获取大纲生成Crew"""
        if self._outline_crew is None:
            from crewai.content.novel.agents.outline_agent import OutlineCrew
            self._outline_crew = OutlineCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._outline_crew

    @property
    def volume_outline_crew(self) -> "VolumeOutlineCrew":
        """获取分卷大纲生成Crew"""
        if self._volume_outline_crew is None:
            from crewai.content.novel.agents.volume_outline_agent import VolumeOutlineCrew
            self._volume_outline_crew = VolumeOutlineCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._volume_outline_crew

    @property
    def chapter_summary_crew(self) -> "ChapterSummaryCrew":
        """获取章节概要生成Crew"""
        if self._chapter_summary_crew is None:
            from crewai.content.novel.agents.chapter_summary_agent import ChapterSummaryCrew
            self._chapter_summary_crew = ChapterSummaryCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._chapter_summary_crew

    @property
    def writing_crew(self) -> "WritingCrew":
        """获取写作Crew"""
        if self._writing_crew is None:
            from crewai.content.novel.agents.writing_agent import WritingCrew
            self._writing_crew = WritingCrew(
                config=self.config,
                entity_memory=self.entity_memory,
                continuity_tracker=self.continuity_tracker,
                verbose=self.verbose,
            )
        return self._writing_crew

    @property
    def review_crew(self) -> "ReviewCrew":
        """获取审查Crew"""
        if self._review_crew is None:
            from crewai.content.novel.agents.review_agent import ReviewCrew
            self._review_crew = ReviewCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._review_crew

    @property
    def orchestrator_crew(self) -> "NovelOrchestratorCrew":
        """获取基于知识库编排器的写作Crew（可选）"""
        if self._orchestrator_crew is None:
            from crewai.content.novel.crews.novel_orchestrator_crew import (
                NovelOrchestratorCrew,
                NovelOrchestratorAdapterConfig,
            )
            adapter_config = NovelOrchestratorAdapterConfig(
                max_subagent_concurrent=self.config.get("max_subagent_concurrent", 5),
                max_concurrent_scenes=self.config.get("max_concurrent_scenes", 3),
                enable_verification=self.config.get("enable_verification", True),
                enable_evolution=self.config.get("enable_evolution", True),
            )
            self._orchestrator_crew = NovelOrchestratorCrew(
                config=self.config,
                verbose=self.verbose,
                adapter_config=adapter_config,
            )
        return self._orchestrator_crew

    @property
    def plot_agent(self) -> "PlotAgent":
        """获取情节规划Agent"""
        if self._plot_agent is None:
            from crewai.content.novel.agents.plot_agent import PlotAgent
            self._plot_agent = PlotAgent(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._plot_agent

    @property
    def outline_evaluator(self) -> "OutlineEvaluator":
        """获取大纲评估器"""
        if self._outline_evaluator is None:
            from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator
            self._outline_evaluator = OutlineEvaluator(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._outline_evaluator

    @property
    def pipeline_state(self) -> "PipelineState":
        """获取流水线状态"""
        if self._pipeline_state is None:
            from crewai.content.novel.pipeline_state import PipelineState
            self._pipeline_state = PipelineState(
                config=dict(self.config) if hasattr(self.config, "keys") else {},
            )
        return self._pipeline_state
