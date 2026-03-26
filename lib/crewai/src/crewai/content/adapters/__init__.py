"""Adapters module for knowledge_base integration.

This module provides adapters to use knowledge_base's NovelOrchestrator
from within crewai's content generation framework.
"""

from .llm_adapter import LLMClientAdapter
from .knowledge_base_adapter import KnowledgeBaseAdapter, NovelOrchestratorAdapterConfig
from .data_converters import (
    convert_world_data_to_world_context,
    convert_chapter_outline,
    convert_chapter_memory_to_summary,
    convert_character_profiles_to_bibles,
)

# Lazy import to avoid circular import with novel_crew
# novel_crew -> novel_orchestrator_crew -> novel_types -> novel -> novel_crews -> novel_crew
def __getattr__(name: str):
    if name == "NovelOrchestratorCrew":
        from .novel_orchestrator_crew import NovelOrchestratorCrew
        return NovelOrchestratorCrew
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LLMClientAdapter",
    "KnowledgeBaseAdapter",
    "NovelOrchestratorAdapterConfig",
    "convert_world_data_to_world_context",
    "convert_chapter_outline",
    "convert_chapter_memory_to_summary",
    "convert_character_profiles_to_bibles",
    # Lazy loaded - access via __getattr__
    "NovelOrchestratorCrew",
]
