"""内容段落Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.segment_agent import SegmentAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class SegmentCrew(BaseContentCrew):
    """播客内容段落Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建内容段落Agent"""
        return {
            "segment_agent": SegmentAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建内容段落Task"""
        return {
            "segment_task": {
                "description": f"生成播客内容段落: {self.config.topic}",
                "expected_output": "播客脚本段落（标题、内容、关键点）",
                "agent": self.agents["segment_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["segment_task"]["description"],
                expected_output=self._tasks["segment_task"]["expected_output"],
                agent=self._tasks["segment_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["segment_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
