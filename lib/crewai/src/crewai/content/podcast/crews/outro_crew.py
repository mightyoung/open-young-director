"""结尾总结Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.outro_agent import OutroAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutroCrew(BaseContentCrew):
    """播客结尾总结Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建结尾总结Agent"""
        return {
            "outro_agent": OutroAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建结尾总结Task"""
        return {
            "outro_task": {
                "description": f"生成播客结尾总结: {self.config.topic}",
                "expected_output": "结尾总结（关键要点、下期预告、收尾语）",
                "agent": self.agents["outro_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["outro_task"]["description"],
                expected_output=self._tasks["outro_task"]["expected_output"],
                agent=self._tasks["outro_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["outro_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
