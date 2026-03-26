"""开场介绍Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.intro_agent import IntroAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class IntroCrew(BaseContentCrew):
    """播客开场介绍Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建开场Agent"""
        return {
            "intro_agent": IntroAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建开场Task"""
        return {
            "intro_task": {
                "description": f"生成播客开场介绍: {self.config.topic}",
                "expected_output": "开场介绍（开场白、主持人介绍、节目预告）",
                "agent": self.agents["intro_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["intro_task"]["description"],
                expected_output=self._tasks["intro_task"]["expected_output"],
                agent=self._tasks["intro_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["intro_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
