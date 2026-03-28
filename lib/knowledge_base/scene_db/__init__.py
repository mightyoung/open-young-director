"""
Scene Database Module for Young-Writer

PostgreSQL + pgvector based Scene persistence layer for storing and
searching narrative scenes, plot beats, character states, and consumption records.

Usage:
    from scene_db import SceneStore, get_scene_store

    store = get_scene_store()
    scene = store.create_scene({
        "chapter": 1,
        "title": "开场",
        "background": "故事发生在一个未来城市",
        "location": "市中心",
        "time_of_day": "evening",
    })

    beat = store.add_beat(scene["id"], {
        "beat_type": "OPENING",
        "description": "主角登场",
        "narration": "夜幕降临，...",
        "embedding": [0.1, 0.2, ...],
    })
"""

from .models import (
    BeatType,
    CharacterState,
    ConsumptionRecord,
    ConsumptionType,
    PlotBeat,
    Scene,
    SceneStatus,
)
from .schema import init_schema
from .store import SceneStore, get_scene_store

__all__ = [
    # Core store
    "SceneStore",
    "get_scene_store",
    "init_schema",
    # Models
    "Scene",
    "PlotBeat",
    "CharacterState",
    "ConsumptionRecord",
    # Enums
    "SceneStatus",
    "BeatType",
    "ConsumptionType",
]
