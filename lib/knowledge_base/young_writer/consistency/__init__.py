# -*- encoding: utf-8 -*-
"""Consistency management for video generation.

This package provides tools for maintaining visual consistency
across video generation:

- CharacterProfile: Unified character appearance descriptions
- SceneProfile: Unified scene/environment descriptions
- Storyboard: Planned shot sequences
- ConsistencyManager: Main class for managing profiles and generating prompts

Usage:
    from consistency import ConsistencyManager

    manager = ConsistencyManager(project_id="xxx")
    manager.load_or_create_profiles()

    # Generate storyboard
    storyboard = manager.generate_storyboard(
        chapter=1,
        content="...",
        characters=["林渊", "赵无极"],
    )

    # Enhance prompts
    enhanced = manager.enhance_prompt(
        scene_description="林渊站在庙中",
        characters=["林渊"],
        shot_type="close_up",
        emotion="determined",
    )
"""

from .models import (
    CharacterProfile,
    SceneProfile,
    Shot,
    Storyboard,
    SHOT_TYPES,
    CAMERA_MOVEMENTS,
)
from .manager import ConsistencyManager

__all__ = [
    "CharacterProfile",
    "SceneProfile",
    "Shot",
    "Storyboard",
    "ConsistencyManager",
    "SHOT_TYPES",
    "CAMERA_MOVEMENTS",
]
