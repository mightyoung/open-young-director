"""广告口播Crew"""

from typing import TYPE_CHECKING, Dict, Any

from crewai.content.base import BaseContentCrew
from crewai.content.podcast.agents.ad_read_agent import AdReadAgent

if TYPE_CHECKING:
    from crewai.llm import LLM


class AdReadCrew(BaseContentCrew):
    """播客广告口播Crew"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        super().__init__(config=config, verbose=verbose)
        self._llm = llm

    def _create_agents(self) -> Dict[str, Any]:
        """创建广告口播Agent"""
        return {
            "ad_read_agent": AdReadAgent(llm=self._llm),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建广告口播Task"""
        return {
            "ad_read_task": {
                "description": f"生成广告口播: {self.config.sponsor_name}",
                "expected_output": "广告口播脚本和行动号召",
                "agent": self.agents["ad_read_agent"],
            }
        }

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew, Task

        tasks = [
            Task(
                description=self._tasks["ad_read_task"]["description"],
                expected_output=self._tasks["ad_read_task"]["expected_output"],
                agent=self._tasks["ad_read_task"]["agent"].agent,
            )
        ]

        crew = Crew(
            agents=[self.agents["ad_read_agent"].agent],
            tasks=tasks,
            verbose=self.verbose,
        )
        return crew
