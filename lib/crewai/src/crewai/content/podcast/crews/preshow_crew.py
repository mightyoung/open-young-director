"""预热环节Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.preshow_agent import PreShowAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class PreShowCrew(BaseContentCrew):
    """播客预热环节Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建预热Agent"""
        return {
            "preshow_agent": PreShowAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建预热Task"""
        return {
            "preshow_task": {
                "description": f"生成播客预热内容: {self.config.topic}",
                "expected_output": "预热内容（热点话题引入、期待值建立、节目背景）",
                "agent": self.agents["preshow_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["preshow_task"]["description"],
                expected_output=self._tasks["preshow_task"]["expected_output"],
                agent=self._tasks["preshow_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["preshow_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
