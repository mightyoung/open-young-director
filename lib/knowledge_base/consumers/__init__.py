# -*- encoding: utf-8 -*-
"""Consumers package for downstream content generation.

Consumers transform raw scene data from FILM_DRAMA mode into various formats:
- NovelConsumer: Novel text generation
- PodcastConsumer: Audio script generation
- VideoConsumer: Video script and storyboard generation
- MusicConsumer: Background music prompt generation

Usage:
    from knowledge_base.consumers import ConsumerOrchestrator, NovelConsumer

    orchestrator = ConsumerOrchestrator(scene_store)
    orchestrator.register(NovelConsumer(llm_client))
    orchestrator.register(PodcastConsumer(llm_client))

    results = await orchestrator.consume_all(scene_id)
"""

from .base import BaseConsumer, ConsumptionRecord
from .novel_consumer import NovelConsumer
from .podcast_consumer import PodcastConsumer, Speaker
from .video_consumer import VideoConsumer, VideoScene
from .music_consumer import MusicConsumer, MusicCue
from .orchestrator import (
    ConsumerOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
    create_orchestrator,
)
from .scene_store import SceneStore, StoredScene, get_scene_store

__all__ = [
    # Base
    "BaseConsumer",
    "ConsumptionRecord",
    # Consumers
    "NovelConsumer",
    "PodcastConsumer",
    "Speaker",
    "VideoConsumer",
    "VideoScene",
    "MusicConsumer",
    "MusicCue",
    # Orchestrator
    "ConsumerOrchestrator",
    "OrchestratorConfig",
    "OrchestratorResult",
    "create_orchestrator",
    # Storage
    "SceneStore",
    "StoredScene",
    "get_scene_store",
]
