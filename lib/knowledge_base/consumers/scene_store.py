# -*- encoding: utf-8 -*-
"""Scene Store - persistence layer for scene data from FILM_DRAMA mode.

Provides a simple interface for storing and retrieving scene data
that is consumed by downstream consumers.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StoredScene:
    """A stored scene with metadata."""

    scene_id: str
    data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scene_id": self.scene_id,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }


class SceneStore:
    """In-memory scene store for raw scene data.

    Provides basic CRUD operations for scene data.
    Can be extended with persistent storage (SQLite, etc.).

    Usage:
        store = SceneStore()

        # Store scene data
        await store.save_scene("scene_1", raw_data)

        # Retrieve scene data
        scene_data = await store.get_scene("scene_1")

        # Check if scene exists
        exists = await store.scene_exists("scene_1")
    """

    def __init__(self):
        """Initialize the scene store."""
        self._scenes: Dict[str, StoredScene] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def save_scene(self, scene_id: str, data: Dict[str, Any]) -> bool:
        """Save or update a scene.

        Args:
            scene_id: Unique scene identifier
            data: Scene data dictionary

        Returns:
            True if saved successfully
        """
        async with self._global_lock:
            if scene_id in self._scenes:
                # Update existing
                scene = self._scenes[scene_id]
                scene.data = data
                scene.updated_at = datetime.now()
                scene.version += 1
            else:
                # Create new
                self._scenes[scene_id] = StoredScene(
                    scene_id=scene_id,
                    data=data,
                )

        logger.debug(f"[SceneStore] Saved scene: {scene_id}")
        return True

    async def get_scene(self, scene_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a scene by ID.

        Args:
            scene_id: The scene identifier

        Returns:
            Scene data dictionary or None if not found
        """
        scene = self._scenes.get(scene_id)
        if scene is None:
            logger.debug(f"[SceneStore] Scene not found: {scene_id}")
            return None

        return scene.data.copy()

    async def delete_scene(self, scene_id: str) -> bool:
        """Delete a scene.

        Args:
            scene_id: The scene identifier

        Returns:
            True if deleted, False if not found
        """
        async with self._global_lock:
            if scene_id in self._scenes:
                del self._scenes[scene_id]
                logger.debug(f"[SceneStore] Deleted scene: {scene_id}")
                return True
        return False

    async def scene_exists(self, scene_id: str) -> bool:
        """Check if a scene exists.

        Args:
            scene_id: The scene identifier

        Returns:
            True if scene exists
        """
        return scene_id in self._scenes

    async def list_scenes(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[str]:
        """List all scene IDs.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of scene IDs
        """
        scene_ids = sorted(self._scenes.keys())
        return scene_ids[offset : offset + limit]

    async def get_scenes_batch(
        self, scene_ids: List[str]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Retrieve multiple scenes at once.

        Args:
            scene_ids: List of scene identifiers

        Returns:
            Dict mapping scene_id -> scene_data (or None if not found)
        """
        result = {}
        for scene_id in scene_ids:
            result[scene_id] = await self.get_scene(scene_id)
        return result

    async def count_scenes(self) -> int:
        """Get total number of scenes.

        Returns:
            Number of stored scenes
        """
        return len(self._scenes)

    def clear(self) -> None:
        """Clear all stored scenes."""
        self._scenes.clear()
        logger.info("[SceneStore] All scenes cleared")


# Singleton instance
_store: Optional[SceneStore] = None


def get_scene_store() -> SceneStore:
    """Get the global SceneStore instance.

    Returns:
        SceneStore singleton instance
    """
    global _store
    if _store is None:
        _store = SceneStore()
    return _store
