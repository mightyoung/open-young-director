"""大纲生成Crew"""

from typing import Dict, Any, Optional, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.novel.agents.world_agent import WorldAgent
from crewai.content.novel.agents.plot_agent import PlotAgent
from crewai.content.novel.agents.reference_agent import ReferenceAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutlineCrew(BaseContentCrew):
    """大纲生成Crew

    负责生成完整的章节大纲，使用Strand Weave结构：
    - 第一步：搜索经典名著，提取参考骨架（ReferenceService）
    - 第二步：构建世界观（调用WorldAgent）
    - 第三步：规划整体情节和章节安排（PlotAgent）

    使用示例:
        crew = OutlineCrew(config=ContentConfig(...))
        result = crew.kickoff()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reference_service = None

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents并注入项目宪法"""
        from crewai.content.novel.agents.world_agent import WorldAgent
        from crewai.content.novel.agents.plot_agent import PlotAgent
        from crewai.content.novel.agents.reference_agent import ReferenceAgent

        llm = self.config.get("llm")
        # 提取全局宪法
        global_rules = self.config.get("global_writer_rules", "")
        
        world_builder = WorldAgent(llm=llm)
        plot_planner = PlotAgent(llm=llm)
        reference_agent = ReferenceAgent(llm=llm)

        if global_rules:
            world_builder.agent.backstory += f"\n{global_rules}"
            plot_planner.agent.backstory += f"\n{global_rules}"
            import logging
            logging.getLogger(__name__).info("Framework Rules injected into Outline Agents.")

        return {
            "world_builder": world_builder,
            "plot_planner": plot_planner,
            "reference_agent": reference_agent,
        }

    @property
    def reference_service(self):
        """获取参考骨架服务（延迟初始化）"""
        if self._reference_service is None:
            from crewai.content.novel.services.reference_service import ReferenceService
            self._reference_service = ReferenceService(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._reference_service

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        topic = self.config.get("topic", "")
        style = self.config.get("style", "")
        num_volumes = self.config.get("num_volumes", 3)
        chapters_per_volume = self.config.get("chapters_per_volume", 10)
        target_words = self.config.get("target_words", 300000)
        total_chapters = num_volumes * chapters_per_volume

        # Get skeleton context for injection into task prompts
        skeleton_context = self.config.get("reference_skeleton_context", "")
        skeleton_section = f"\n\n## 参考经典名著骨架\n\n{skeleton_context}\n\n" if skeleton_context else ""

        # Create tasks dict first to avoid circular reference
        tasks_dict = {
            "build_world": Task(
                description=f"为'{topic}'主题构建完整世界观。{skeleton_section}请在构建世界观时参考上述经典名著的：主题方向、风格元素、世界观设定（如仙侠世界的修炼体系、社会结构等）。",
                agent=self.agents["world_builder"].agent,
                expected_output="包含世界名称、势力、地点、力量体系等完整世界观设定的JSON",
            ),
            "plan_plot": Task(
                description=f"设计{num_volumes}卷{total_chapters}章的整体情节结构（每卷{chapters_per_volume}章）。{skeleton_section}请融入经典名著骨架中的叙事模式和结构、主干情节、角色原型等。",
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
        topic = self.config.get("topic", "")
        style = self.config.get("style", "")

        # Step 0: 搜索经典名著，提取参考骨架
        reference_skeletons = []
        try:
            reference_skeletons = self.reference_service.research_and_extract(
                topic=topic,
                style=style,
                max_results=3,
            )
        except Exception as e:
            # Reference search is optional, continue without it
            import logging
            logging.warning(f"Reference search failed: {e}")

        # Format skeletons for prompt context
        skeleton_context = self.reference_service.format_skeleton_for_prompt(reference_skeletons)

        # Pass skeleton context to agents via config
        self.config["reference_skeleton_context"] = skeleton_context

        # 直接调用底层 Crew kickoff，获取完整的 CrewOutput（含 tasks_output）
        crew = self._create_workflow()
        crew_result = crew.kickoff()

        # 从任务输出中提取world数据（避免重复构建）
        world_data = {}
        raw_world = ""
        import logging
        logger = logging.getLogger(__name__)
        if hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
            logger.warning(f"[DEBUG] tasks_output count: {len(crew_result.tasks_output)}")
            # 第一个任务是build_world
            first_task_output = crew_result.tasks_output[0]
            logger.warning(f"[DEBUG] first_task_output type: {type(first_task_output)}")
            logger.warning(f"[DEBUG] first_task_output has raw: {hasattr(first_task_output, 'raw')}")
            # 获取原始输出字符串
            if hasattr(first_task_output, 'raw'):
                raw_world = first_task_output.raw
            elif hasattr(first_task_output, 'output'):
                raw_world = str(first_task_output.output)
            else:
                raw_world = str(first_task_output)

            logger.warning(f"[DEBUG] raw_world length: {len(raw_world) if raw_world else 0}")
            logger.warning(f"[DEBUG] raw_world first 200 chars: {raw_world[:200] if raw_world else 'EMPTY'}")

            # 使用WorldAgent的解析逻辑解析world数据
            world_agent = self._agents.get("world_builder")
            if world_agent and hasattr(world_agent, '_parse_result'):
                world_data = world_agent._parse_result(raw_world)
                logger.warning(f"[DEBUG] world_data name: {world_data.get('name', 'UNKNOWN')}")
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

        # 解析plot数据（使用 crew_result 的原始输出）
        # crew_result.tasks_output 可能不包含正确的plot数据，尝试从 crew_result.raw 获取
        raw_plot = ""
        import json
        import re

        # 首先尝试从 crew_result.raw 获取（这是最终组合输出）
        if hasattr(crew_result, 'raw') and crew_result.raw:
            raw_output = crew_result.raw
            logger.warning(f"[DEBUG] Trying crew_result.raw, length: {len(raw_output)}")

            # Look for JSON with volumes
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_output)
            if json_match:
                json_str = json_match.group(1)
                # P1 Fix: Strip thinking tags before JSON parsing (MiniMax outputs <think> tags)
                json_str = json_str.replace("OKEN", "")
                json_str = re.sub(r'<think>[\s\S]*?</think>', '', json_str)
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict) and 'volumes' in parsed and parsed['volumes']:
                        raw_plot = raw_output
                        logger.warning(f"[DEBUG] Found plot in crew_result.raw JSON code block, volumes: {len(parsed['volumes'])}")
                except json.JSONDecodeError:
                    pass

        # 如果上面没找到，尝试从 tasks_output 查找
        if not raw_plot and hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
            for idx, task_output in enumerate(crew_result.tasks_output):
                raw_output = ""
                if hasattr(task_output, 'raw'):
                    raw_output = task_output.raw or ""
                elif hasattr(task_output, 'output'):
                    raw_output = str(task_output.output)
                else:
                    raw_output = str(task_output)

                logger.warning(f"[DEBUG] Task {idx} raw length: {len(raw_output)}, first 100: {raw_output[:100]}")

                # Try to find and parse JSON in the output
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_output)
                if json_match:
                    json_str = json_match.group(1)
                    logger.warning(f"[DEBUG] Task {idx} found JSON code block, length: {len(json_str)}")
                else:
                    json_match = re.search(r'\{[\s\S]*\}', raw_output)
                    if json_match:
                        json_str = json_match.group()
                        logger.warning(f"[DEBUG] Task {idx} found JSON object, length: {len(json_str)}")
                    else:
                        logger.warning(f"[DEBUG] Task {idx} no JSON found")
                        continue

                # P1 Fix: Strip thinking tags before JSON parsing (MiniMax outputs <think> tags)
                json_str = re.sub(r'<think>[\s\S]*?</think>', '', json_str)

                try:
                    parsed = json.loads(json_str)
                    logger.warning(f"[DEBUG] Task {idx} parsed keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
                    if isinstance(parsed, dict) and 'volumes' in parsed and parsed['volumes']:
                        raw_plot = raw_output
                        logger.warning(f"[DEBUG] Found valid plot JSON in tasks_output[{idx}], volumes: {len(parsed['volumes'])}")
                        break
                except json.JSONDecodeError as e:
                    logger.warning(f"[DEBUG] Task {idx} JSON parse error: {e}")

        # Fallback: 如果都没找到，使用空字符串让 _parse_result 处理
        if not raw_plot:
            logger.warning("[DEBUG] No plot data found in tasks_output, will use fallback")

        # DEBUG: Log raw_plot for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[DEBUG] raw_plot length: {len(raw_plot) if raw_plot else 0}")
        if raw_plot:
            logger.warning(f"[DEBUG] raw_plot first 200 chars: {raw_plot[:200]}")

        plot_agent = self._agents.get("plot_planner")
        if plot_agent and hasattr(plot_agent, '_parse_result'):
            plot_data = plot_agent._parse_result(raw_plot)

            # DEBUG: Log parsed plot_data
            logger.warning(f"[DEBUG] plot_data volumes count: {len(plot_data.get('volumes', []))}")
        else:
            # Fallback: 尝试直接解析JSON
            import json
            import re
            try:
                json_match = re.search(r'\{[\s\S]*\}', raw_plot)
                if json_match:
                    plot_data = json.loads(json_match.group())
                else:
                    plot_data = {"main_strand": {"name": "主线", "description": raw_plot, "main_events": [], "tension_arc": []}, "sub_strands": [], "foreshadowing_strands": [], "emotional_strands": [], "weave_points": [], "high_points": [], "volumes": []}
            except Exception:
                plot_data = {"main_strand": {"name": "主线", "description": raw_plot, "main_events": [], "tension_arc": []}, "sub_strands": [], "foreshadowing_strands": [], "emotional_strands": [], "weave_points": [], "high_points": []}

        return {
            "world": world_data,
            "plot": plot_data,
            "reference_skeletons": [s.to_dict() for s in reference_skeletons] if reference_skeletons else [],
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
