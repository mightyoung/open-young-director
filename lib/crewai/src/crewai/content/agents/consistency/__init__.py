"""Consistency management for video generation.

Provides character/scene consistency tracking and storyboard generation.
"""
from .models import (
    CharacterProfile,
    SceneProfile,
    Shot,
    Storyboard,
    SHOT_TYPES,
    CAMERA_MOVEMENTS,
)
from .manager import ConsistencyManager, DEFAULT_CHARACTER_TEMPLATES

__all__ = [
    "CharacterProfile",
    "SceneProfile",
    "Shot",
    "Storyboard",
    "SHOT_TYPES",
    "CAMERA_MOVEMENTS",
    "ConsistencyManager",
    "DEFAULT_CHARACTER_TEMPLATES",
]
