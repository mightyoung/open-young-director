"""Multimodal agents for CrewAI ComfyUI integration.

This package provides specialized agents for generating multimedia content:
- VisualDirectorAgent: Scene illustrations and character portraits
- SoundDesignerAgent: Soundscapes, BGM, SFX, and narration
- VideoProducerAgent: Scene videos and character animations

Usage:
    from crewai.comfy.agents import VisualDirectorAgent, SoundDesignerAgent

    # Generate scene illustration
    visual_director = VisualDirectorAgent()
    result = visual_director.generate_scene_illustration(
        scene_description="韩林站在太虚宗演武场上",
        mood="epic",
    )

    # Generate background music
    sound_designer = SoundDesignerAgent()
    result = sound_designer.generate_background_music(
        mood="epic",
        duration=60,
    )
"""

from crewai.comfy.agents.visual_director import (
    VisualDirectorAgent,
    VisualDirectorConfig,
    SceneVisualRequirements,
)
from crewai.comfy.agents.sound_designer import (
    SoundDesignerAgent,
    SoundDesignerConfig,
    AudioRequirements,
)
from crewai.comfy.agents.video_producer import (
    VideoProducerAgent,
    VideoProducerConfig,
    VideoRequirements,
)

__all__ = [
    # Visual Director
    "VisualDirectorAgent",
    "VisualDirectorConfig",
    "SceneVisualRequirements",
    # Sound Designer
    "SoundDesignerAgent",
    "SoundDesignerConfig",
    "AudioRequirements",
    # Video Producer
    "VideoProducerAgent",
    "VideoProducerConfig",
    "VideoRequirements",
]
