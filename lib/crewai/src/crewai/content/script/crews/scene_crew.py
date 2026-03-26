"""场景Crew - 管理单个场景的写作"""

from typing import Dict, List, Any, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.script.script_types import SceneOutput

if TYPE_CHECKING:
    from crewai.llm import LLM


class SceneCrew(BaseContentCrew):
    """场景Crew - 管理单个场景的写作

    负责将Beat转化为具体的场景描述，包括动作、场景设置等。

    使用示例:
        crew = SceneCrew(config=scene_config)
        result = crew.kickoff()
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents"""
        config = self.config

        scene_writer = Agent(
            role="场景作家",
            goal="将Beat转化为生动的场景描述",
            backstory="""你是一位专业的剧本场景作家，擅长用简洁有力的动作描写
            和场景设置来推动故事发展。你的场景描写注重视觉化呈现，
            让读者能够在脑海中形成清晰的画面。""",
            verbose=self.verbose,
            llm=self.config.get("llm") if isinstance(self.config, dict) else None,
        )

        return {"scene_writer": scene_writer}

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        config = self.config

        write_scene_task = Task(
            description=self._build_scene_prompt(),
            agent=self.agents["scene_writer"],
            expected_output="完整的场景描写，包括动作、对话（如果需要）、场景设置"
        )

        return {"write_scene": write_scene_task}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai.crew import Crew

        crew = Crew(
            agents=list(self.agents.values()),
            tasks=list(self.tasks.values()),
            verbose=self.verbose,
        )
        return crew

    def _build_scene_prompt(self) -> str:
        """构建场景写作提示"""
        config = self.config
        beat = config.get("beat", {})
        beat_number = beat.get("number", 0)
        beat_name = beat.get("name", "")
        beat_description = beat.get("description", "")
        scene_purpose = beat.get("scene_purpose", "")

        location = config.get("location", "待定")
        time_of_day = config.get("time_of_day", "日")
        characters = config.get("characters", [])

        prompt = f"""请为以下场景编写具体的场景描写：

场景信息:
- Beat编号: {beat_number}
- Beat名称: {beat_name}
- Beat描述: {beat_description}
- 场景目的: {scene_purpose}
- 场景地点: {location}
- 时间: {time_of_day}
- 出场角色: {', '.join(characters)}

要求:
1. 使用专业的场景描写格式
2. 先写动作/场景描述，再安排对话
3. 每个动作描写不超过3行
4. 对话格式：角色名（大写）- 对白内容
5. 标注场景的视觉重点（如有）

请输出完整的场景描写："""

        return prompt

    def _parse_output(self, result: Any) -> SceneOutput:
        """解析Crew输出为SceneOutput"""
        config = self.config
        beat = config.get("beat", {})

        return SceneOutput(
            scene_number=config.get("scene_number", 0),
            beat_number=beat.get("number", 0),
            location=config.get("location", ""),
            time_of_day=config.get("time_of_day", ""),
            characters=config.get("characters", []),
            action=str(result),
            dialogue_count=str(result).count("-") if str(result).count("-") > 0 else 0,
            estimated_duration=config.get("estimated_duration", 5),
            visual_notes=""
        )


__all__ = ["SceneCrew"]
