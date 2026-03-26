"""节目笔记Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.shownotes_agent import ShowNotesAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class ShowNotesCrew(BaseContentCrew):
    """播客节目笔记Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建节目笔记Agent"""
        return {
            "shownotes_agent": ShowNotesAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建节目笔记Task"""
        return {
            "shownotes_task": {
                "description": f"生成播客节目笔记: {self.config.topic}",
                "expected_output": "节目笔记（标题、描述、时间戳、链接）",
                "agent": self.agents["shownotes_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["shownotes_task"]["description"],
                expected_output=self._tasks["shownotes_task"]["expected_output"],
                agent=self._tasks["shownotes_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["shownotes_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
