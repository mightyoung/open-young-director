"""NovelOrchestratorCrew - Crewai entry point using knowledge_base's NovelOrchestrator.

This crew provides an alternative to WritingCrew that uses knowledge_base's
multi-agent orchestration (DirectorAgent + SubAgentPool + NovelWriterAgent)
instead of the single-agent DraftWriter approach.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.adapters.knowledge_base_adapter import (
    KnowledgeBaseAdapter,
    NovelOrchestratorAdapterConfig,
)

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.novel.novel_types import (
        NovelOutput,
        ChapterOutput,
        WritingContext,
    )

logger = logging.getLogger(__name__)


class NovelOrchestratorCrew(BaseContentCrew):
    """A crewai crew that uses knowledge_base's NovelOrchestrator for chapter generation.

    This provides an alternative to the standard WritingCrew + ReviewCrew pipeline,
    leveraging knowledge_base's:
    - DirectorAgent for plot orchestration
    - SubAgentPool for parallel character role-playing
    - NovelWriterAgent for novelization

    Usage:
        crew = NovelOrchestratorCrew(
            config={
                "topic": "修仙逆袭",
                "style": "xianxia",
                "llm": llm_instance,
            }
        )
        result = crew.kickoff()
    """

    def __init__(
        self,
        config: Any,
        agents: Optional[Dict[str, Any]] = None,
        tasks: Optional[Dict[str, Any]] = None,
        verbose: bool = True,
        adapter_config: Optional[NovelOrchestratorAdapterConfig] = None,
    ):
        """Initialize the NovelOrchestratorCrew.

        Args:
            config: Crew configuration dict
            agents: Optional pre-configured agents (unused, provided for compatibility)
            tasks: Optional pre-configured tasks (unused)
            verbose: Enable verbose logging
            adapter_config: Optional adapter configuration
        """
        super().__init__(config, agents, tasks, verbose)
        self._adapter: Optional[KnowledgeBaseAdapter] = None
        self._adapter_config = adapter_config or NovelOrchestratorAdapterConfig()

    def _create_agents(self) -> Dict[str, Any]:
        """Create agents - not used, we use the adapter."""
        return {}

    def _create_tasks(self) -> Dict[str, Any]:
        """Create tasks - not used, we use the adapter."""
        return {}

    def _create_workflow(self) -> Any:
        """Create workflow - not used."""
        return None

    @property
    def adapter(self) -> KnowledgeBaseAdapter:
        """Get or create the KnowledgeBaseAdapter."""
        if self._adapter is None:
            llm = self.config.get("llm")
            if llm is None:
                raise ValueError("llm must be provided in config")
            self._adapter = KnowledgeBaseAdapter(
                llm=llm,
                config=self._adapter_config,
            )
        return self._adapter

    def write_chapter(
        self,
        context: WritingContext,
        chapter_outline: Dict[str, Any],
    ) -> str:
        """Write a chapter using knowledge_base's NovelOrchestrator.

        This method adapts crewai's WritingContext to knowledge_base's format
        and delegates to the NovelOrchestrator.

        Args:
            context: WritingContext from NovelCrew
            chapter_outline: Chapter outline dict

        Returns:
            Generated chapter draft as string
        """
        # Extract world_data and character_profiles from context
        # In the typical flow, these come from previous steps
        world_data = self._extract_world_data_from_context(context)
        character_profiles = context.character_profiles

        # Generate chapter
        result = self.adapter.generate_chapter_with_memory(
            chapter=context.current_chapter_num,
            chapter_outline=chapter_outline,
            world_data=world_data,
            character_profiles=character_profiles,
        )

        return result["draft"]

    def _extract_world_data_from_context(self, context: WritingContext) -> Dict[str, Any]:
        """Extract world_data from WritingContext.

        Since crewai's WritingContext stores world_description as a string,
        we reconstruct a minimal world_data dict for knowledge_base.
        """
        return {
            "name": context.title,
            "description": context.world_description,
            "power_system": {
                "name": "默认修炼体系",
                "levels": ["炼气", "筑基", "金丹", "元婴", "化神"],
                "special_abilities": [],
            },
            "factions": [],
        }

    def kickoff(self) -> BaseCrewOutput:
        """Execute the orchestrator crew.

        Note: This method is typically called by NovelCrew, which handles
        the outer loop. This is here for standalone usage.

        Returns:
            BaseCrewOutput with empty content (use write_chapter instead)
        """
        import time
        start = time.time()

        logger.info("NovelOrchestratorCrew is designed to be used via NovelCrew.write_chapter()")
        logger.info("Standalone kickoff() returns empty output - use write_chapter() instead")

        return BaseCrewOutput(
            content=None,
            tasks_completed=["NovelOrchestratorCrew initialized"],
            execution_time=time.time() - start,
            metadata={"note": "Use write_chapter() for actual generation"},
        )

    def critique_and_revise(
        self,
        draft: str,
        context: Any,
    ) -> tuple[Any, str, str]:
        """Placeholder for critique/revise - not implemented in this adapter.

        For full critique/revise support, use the standard ReviewCrew instead.
        This method exists for API compatibility.
        """
        logger.warning("NovelOrchestratorCrew does not support critique_and_revise. Use ReviewCrew.")
        return (None, draft, draft)
