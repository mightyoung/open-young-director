"""世界观构建Crew"""

from typing import Dict, Any, Optional, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.novel.agents.world_agent import WorldAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class WorldCrew(BaseContentCrew):
    """世界观构建Crew

    负责构建小说的世界观，包括：
    - 世界/位面设定
    - 主要势力
    - 关键地点
    - 力量体系

    使用示例:
        crew = WorldCrew(config=ContentConfig(...))
        result = crew.kickoff()
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents"""
        return {
            "world_builder": WorldAgent(llm=self.config.get("llm")),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        return {
            "build_world": Task(
                description=f"根据主题'{self.config.get('topic')}'和风格'{self.config.get('style')}'构建完整的世界观",
                agent=self.agents["world_builder"].agent,
                expected_output="包含世界名称、势力、地点、力量体系等完整世界观设定的JSON",
            ),
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew

        return Crew(
            agents=[self.agents["world_builder"].agent],
            tasks=[self.tasks["build_world"]],
            verbose=self.verbose,
        )

    def build(self) -> Dict[str, Any]:
        """直接构建世界观并返回结果

        Returns:
            dict: 世界观数据
        """
        # Access self.agents first to populate self._agents
        agents = self.agents
        # Use WorldAgent's build() method directly to get the dict
        return agents["world_builder"].build(
            self.config.get("topic", ""),
            self.config.get("style", ""),
        )
