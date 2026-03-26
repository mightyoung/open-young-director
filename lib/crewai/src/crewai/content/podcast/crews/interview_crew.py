"""访谈环节Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.interview_agent import InterviewAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class InterviewCrew(BaseContentCrew):
    """播客访谈环节Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建访谈Agent"""
        return {
            "interview_agent": InterviewAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建访谈Task"""
        return {
            "interview_task": {
                "description": f"生成播客访谈内容: {self.config.guest_name}",
                "expected_output": "访谈内容（嘉宾介绍、问题列表、讨论要点）",
                "agent": self.agents["interview_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["interview_task"]["description"],
                expected_output=self._tasks["interview_task"]["expected_output"],
                agent=self._tasks["interview_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["interview_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
