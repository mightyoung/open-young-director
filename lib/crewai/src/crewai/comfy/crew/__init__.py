"""Crew package for multimodal novel content generation."""

from crewai.comfy.crew.multimodal_crew import (
    MultimodalCrew,
    MultimodalCrewConfig,
    create_novel_multimodal_crew,
)

__all__ = [
    "MultimodalCrew",
    "MultimodalCrewConfig",
    "create_novel_multimodal_crew",
]
