"""Multi-modal trigger generation architecture.

This package provides the core components for a multi-modal content
generation trigger system that can evaluate and trigger content
generation based on various input types (novels, podcasts, videos).

Example:
    >>> from triggers import SceneEventBus, NovelEvaluator
    >>> bus = SceneEventBus()
    >>> evaluator = NovelEvaluator({"min_chapters": 2})
    >>> bus.subscribe(evaluator)
    >>> bus.publish_chapter_completed({"chapter_id": 1, "content": "..."})
"""

from .event_bus import SceneEventBus
from .base import (
    ContentEvaluator,
    TriggerStatus,
    MaterialPacket,
    EvaluationResult,
)
from .novel_evaluator import NovelEvaluator
from .podcast_evaluator import PodcastEvaluator
from .video_evaluator import VideoEvaluator
from .scene_extractor import SceneExtractor, ExtractedScene
from .config import TriggerConfigLoader, TriggerConfig, EvaluatorConfig

__all__ = [
    # Event Bus
    "SceneEventBus",
    # Base Classes
    "ContentEvaluator",
    "TriggerStatus",
    "MaterialPacket",
    "EvaluationResult",
    # Evaluators
    "NovelEvaluator",
    "PodcastEvaluator",
    "VideoEvaluator",
    # Utilities
    "SceneExtractor",
    "ExtractedScene",
    # Config
    "TriggerConfigLoader",
    "TriggerConfig",
    "EvaluatorConfig",
]
