"""视频生成Prompt模块"""

from crewai.content.video.video_types import (
    VideoScenePrompt,
    VideoGenerationPrompt,
    ShortFormVideoPrompt,
)

# Seedance 2.0 适配器
from crewai.content.video.seedance_adapter import (
    Seedance2PromptAdapter,
    FramePrompt,
    TimelineSegment,
    CharacterSpec,
    SceneSpec,
    create_character_spec,
    create_scene_spec,
)

__all__ = [
    # Video types
    "VideoScenePrompt",
    "VideoGenerationPrompt",
    "ShortFormVideoPrompt",
    # Seedance 2.0 adapter
    "Seedance2PromptAdapter",
    "FramePrompt",
    "TimelineSegment",
    "CharacterSpec",
    "SceneSpec",
    "create_character_spec",
    "create_scene_spec",
]
