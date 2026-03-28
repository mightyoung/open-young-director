"""大纲生成Crew"""

from typing import Dict, Any, Optional, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.novel.agents.world_agent import WorldAgent
from crewai.content.novel.agents.plot_agent import PlotAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutlineCrew(BaseContentCrew):
    """大纲生成Crew

    负责生成完整的章节大纲，使用Strand Weave结构：
    - 第一步：构建世界观（调用WorldAgent）
    - 第二步：规划整体情节和章节安排

    使用示例:
        crew = OutlineCrew(config=ContentConfig(...))
        result = crew.kickoff()
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents"""
        return {
            "world_builder": WorldAgent(llm=self.config.get("llm")),
            "plot_planner": PlotAgent(llm=self.config.get("llm")),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        topic = self.config.get("topic", "")
        style = self.config.get("style", "")
        num_volumes = self.config.get("num_volumes", 3)
        chapters_per_volume = self.config.get("chapters_per_volume", 10)
        target_words = self.config.get("target_words", 300000)
        total_chapters = num_volumes * chapters_per_volume

        # Create tasks dict first to avoid circular reference
        tasks_dict = {
            "build_world": Task(
                description=f"为'{topic}'主题构建完整世界观",
                agent=self.agents["world_builder"].agent,
                expected_output="包含世界名称、势力、地点、力量体系等完整世界观设定的JSON",
            ),
            "plan_plot": Task(
                description=f"设计{num_volumes}卷{total_chapters}章的整体情节结构（每卷{chapters_per_volume}章）",
                agent=self.agents["plot_planner"].agent,
                expected_output=f"包含{num_volumes}卷结构的Strand Weave情节规划，每卷含{chapters_per_volume}章",
                context=[],
            ),
        }

        # Set context after tasks dict is created to avoid recursion
        tasks_dict["plan_plot"].context = [tasks_dict["build_world"]]

        return tasks_dict

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew
        from crewai import Process

        # Extract actual Agent objects from wrapper agents
        actual_agents = [wrapper.agent for wrapper in self.agents.values()]

        return Crew(
            agents=actual_agents,
            tasks=list(self.tasks.values()),
            process=Process.sequential,
            verbose=self.verbose,
        )

    def _parse_output(self, result: Any) -> Any:
        """解析Crew输出 - 返回原始内容字符串供后续处理"""
        # result is a CrewOutput object
        if hasattr(result, 'raw'):
            return result.raw
        return str(result)

    def generate_outline(self) -> Dict[str, Any]:
        """生成大纲并返回结果

        Returns:
            dict: 包含world和plot的完整大纲
        """
        # 直接调用底层 Crew kickoff，获取完整的 CrewOutput（含 tasks_output）
        crew = self._create_workflow()
        crew_result = crew.kickoff()

        # 从任务输出中提取world数据（避免重复构建）
        world_data = {}
        raw_world = ""
        if hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
            # 第一个任务是build_world
            first_task_output = crew_result.tasks_output[0]
            # 获取原始输出字符串
            if hasattr(first_task_output, 'raw'):
                raw_world = first_task_output.raw
            elif hasattr(first_task_output, 'output'):
                raw_world = str(first_task_output.output)
            else:
                raw_world = str(first_task_output)

            # 使用WorldAgent的解析逻辑解析world数据
            world_agent = self._agents.get("world_builder")
            if world_agent and hasattr(world_agent, '_parse_result'):
                world_data = world_agent._parse_result(raw_world)
            else:
                # Fallback: 尝试直接解析JSON
                import json
                import re
                try:
                    json_match = re.search(r'\{[\s\S]*\}', raw_world)
                    if json_match:
                        world_data = json.loads(json_match.group())
                except Exception:
                    world_data = {"name": "默认世界", "description": raw_world}

        # 解析plot数据（使用 CrewOutput.raw）
        raw_plot = getattr(crew_result, 'raw', '') or str(crew_result)
        plot_agent = self._agents.get("plot_planner")
        if plot_agent and hasattr(plot_agent, '_parse_result'):
            plot_data = plot_agent._parse_result(raw_plot)
        else:
            # Fallback: 尝试直接解析JSON
            import json
            import re
            try:
                json_match = re.search(r'\{[\s\S]*\}', raw_plot)
                if json_match:
                    plot_data = json.loads(json_match.group())
                else:
                    plot_data = {"main_strand": {"name": "主线", "description": raw_plot, "main_events": [], "tension_arc": []}, "sub_strands": [], "foreshadowing_strands": [], "emotional_strands": [], "weave_points": [], "high_points": []}
            except Exception:
                plot_data = {"main_strand": {"name": "主线", "description": raw_plot, "main_events": [], "tension_arc": []}, "sub_strands": [], "foreshadowing_strands": [], "emotional_strands": [], "weave_points": [], "high_points": []}

        return {
            "world": world_data,
            "plot": plot_data,
        }

    def generate_outline_with_feedback(
        self,
        original_outline: dict,
        feedback: dict,
        feedback_applier: Any = None,
    ) -> dict:
        """根据反馈生成调整后的大纲

        Args:
            original_outline: 原始大纲
            feedback: 结构化反馈
            feedback_applier: FeedbackApplier 实例

        Returns:
            调整后的大纲
        """
        if feedback_applier is None:
            from crewai.content.novel.feedback_applier import FeedbackApplier
            feedback_applier = FeedbackApplier(llm=self.config.get("llm"))

        return feedback_applier.apply_outline_feedback(original_outline, feedback)
