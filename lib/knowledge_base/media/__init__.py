# -*- encoding: utf-8 -*-
"""Media generation module using MiniMax APIs.

This module provides actual media generation (video, image, audio, music)
by wrapping the MiniMaxMediaClient from crewai.comfy.minimax.

Usage:
    from knowledge_base.media import MiniMaxMediaExecutor

    executor = MiniMaxMediaExecutor()
    result = await executor.generate_image(prompt="a beautiful landscape")
"""

from .minimax_executor import (
    MiniMaxMediaExecutor,
    get_media_executor,
)
from .seedance_adapter import (
    Seedance2PromptAdapter,
    CharacterSpec,
    SceneSpec,
    FramePrompt,
    TimelineSegment,
    create_character_spec,
    create_scene_spec,
)

__all__ = [
    "MiniMaxMediaExecutor",
    "get_media_executor",
    "Seedance2PromptAdapter",
    "CharacterSpec",
    "SceneSpec",
    "FramePrompt",
    "TimelineSegment",
    "create_character_spec",
    "create_scene_spec",
]
