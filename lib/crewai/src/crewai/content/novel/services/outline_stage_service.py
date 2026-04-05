"""Outline stage service - handles world building and outline generation."""
import logging
from typing import Any, Tuple
from crewai.content.novel.services.base_stage_service import BaseStageService
from crewai.content.exceptions import ExecutionResult, ExecutionStatus


logger = logging.getLogger(__name__)


class OutlineStageService(BaseStageService):
    """大纲阶段服务。

    职责：
    1. 世界观构建 (WorldCrew)
    2. 情节规划 (PlotAgent)
    3. 大纲评估 (OutlineEvaluator) - 可选的 gate

    输出：
    - world_data: 世界观数据
    - plot_data: 情节数据
    """

    def execute(self, context: dict) -> tuple[dict, ExecutionResult]:
        """执行大纲生成阶段。

        Args:
            context: 包含 llm 等配置

        Returns:
            tuple: ({"world": {...}, "plot": {...}}, execution_result)
        """
        self._completed_stages = []
        llm = context.get("llm", self.llm)

        try:
            # 1. 生成世界观
            world_data = self._generate_world(llm)
            self.add_completed_stage("world")

            # 2. 生成情节大纲
            plot_data = self._generate_plot(world_data, llm)
            self.add_completed_stage("plot")

            # 3. 保存到 pipeline_state
            self.pipeline_state.set_outline_data({
                "world": world_data,
                "plot": plot_data,
            })
            self.pipeline_state.set_stage("outline")

            # 4. 可选：评估大纲
            if self.config.get("enable_outline_evaluation", False):
                eval_result = self._evaluate_outline(world_data, plot_data, llm)
                if not eval_result.passed:
                    self.add_failure(
                        stage="evaluation",
                        reason="Outline evaluation failed",
                        details={"score": eval_result.score, "issues": eval_result.issues},
                        recoverable=True,
                    )
                self.add_completed_stage("evaluation")
            else:
                self.add_completed_stage("evaluation")

            return {
                "world": world_data,
                "plot": plot_data,
            }, self.build_execution_result()

        except Exception as e:
            logger.exception(f"Outline stage failed: {e}")
            self.add_failure(
                stage="outline",
                reason=str(e),
                details={"error_type": type(e).__name__},
                recoverable=False,
            )
            return {}, self.build_execution_result()

    def _generate_world(self, llm) -> dict:
        """生成世界观。"""
        from crewai.content.novel.crews.outline_crew import OutlineCrew

        crew = OutlineCrew(config=self.config, verbose=self.config.get("verbose", True))
        outline_data = crew.generate_outline()
        return outline_data.get("world", {})

    def _generate_plot(self, world_data: dict, llm) -> dict:
        """生成情节大纲。"""
        from crewai.content.novel.agents.plot_agent import PlotAgent

        agent = PlotAgent(llm=llm, verbose=self.config.get("verbose", True))
        plot_data = agent.plan_plot(
            world_data=world_data,
            topic=self.topic,
            style=self.style,
        )
        return plot_data

    def _evaluate_outline(self, world_data: dict, plot_data: dict, llm) -> Any:
        """评估大纲质量。"""
        from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator

        evaluator = OutlineEvaluator(llm=llm, verbose=self.config.get("verbose", True))
        result = evaluator.check(world_data, plot_data, context={})
        return result
