# -*- encoding: utf-8 -*-
"""Base Consumer class for downstream content generation.

Abstract base class that defines the consumer interface for transforming
raw scene data from FILM_DRAMA mode into various content formats.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConsumptionRecord:
    """Record of a consumption operation."""

    scene_id: str
    consumer_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    raw_data_preview: str = ""
    result_preview: str = ""
    success: bool = True
    error: Optional[str] = None
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scene_id": self.scene_id,
            "consumer_type": self.consumer_type,
            "timestamp": self.timestamp.isoformat(),
            "success": self.success,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


class BaseConsumer(ABC):
    """Abstract base class for downstream consumers.

    Consumers transform raw scene data from FILM_DRAMA mode into
    various content formats (novel, podcast, video, music).

    Subclasses must implement:
    - consumer_type: Return the consumer type identifier
    - query: Fetch raw scene data
    - generate: Transform raw data into target format

    Example:
        class NovelConsumer(BaseConsumer):
            @property
            def consumer_type(self) -> str:
                return "novel"

            async def query(self, scene_id: str, **kwargs) -> dict:
                return await self.store.get_scene(scene_id)

            async def generate(self, raw_data: dict, **kwargs) -> str:
                # Transform raw data into novel text
                return novel_text
    """

    def __init__(
        self,
        llm_client: Any = None,
        scene_store: Any = None,
        consumption_records: Optional[Dict[str, ConsumptionRecord]] = None,
    ):
        """Initialize the consumer.

        Args:
            llm_client: LLM client for content generation (e.g., MiniMaxClient)
            scene_store: SceneStore instance for querying raw data
            consumption_records: Optional dict to store consumption history
        """
        self.llm_client = llm_client
        self.scene_store = scene_store
        self._consumption_records: Dict[str, ConsumptionRecord] = consumption_records or {}

    @property
    @abstractmethod
    def consumer_type(self) -> str:
        """Return the consumer type identifier.

        Returns:
            One of: novel, podcast, video, music
        """
        raise NotImplementedError

    @abstractmethod
    async def query(self, scene_id: str, **kwargs) -> Dict[str, Any]:
        """Query raw scene data from the scene store.

        Args:
            scene_id: The scene identifier
            **kwargs: Additional query parameters

        Returns:
            Raw scene data dictionary containing:
            - scene_id: Scene identifier
            - chapter_info: Chapter metadata
            - background: Story background
            - beats: Plot beats with character interactions
            - character_states: Character emotional/physical states
            - scene_descriptions: Visual scene descriptions
            - narration_pieces: Narration fragments
            - emotional_arc: Scene emotional arc
        """
        raise NotImplementedError

    @abstractmethod
    async def generate(self, raw_data: Dict[str, Any], **kwargs) -> Any:
        """Generate target content from raw scene data.

        Args:
            raw_data: Raw scene data from query()
            **kwargs: Additional generation parameters

        Returns:
            Generated content in the consumer's format.
            Concrete return types:
            - NovelConsumer: str (novel text)
            - PodcastConsumer: dict {title, script, duration_estimate, speakers}
            - VideoConsumer: dict {title, scenes, narration, music_suggestions}
            - MusicConsumer: dict {style, mood, tempo, instruments, prompt}
        """
        raise NotImplementedError

    async def consume(self, scene_id: str, **kwargs) -> Dict[str, Any]:
        """Execute the complete consumption pipeline.

        Pipeline: query -> generate -> record

        Args:
            scene_id: The scene identifier
            **kwargs: Additional parameters passed to query and generate

        Returns:
            dict with keys:
            - result: The generated content
            - record: ConsumptionRecord instance
            - scene_id: The input scene ID
        """
        import time

        start_time = time.perf_counter()
        record = ConsumptionRecord(
            scene_id=scene_id,
            consumer_type=self.consumer_type,
        )

        try:
            # Step 1: Query raw data
            logger.info(f"[{self.consumer_type}] Querying scene {scene_id}")
            raw_data = await self.query(scene_id, **kwargs)
            record.raw_data_preview = str(raw_data)[:200]

            # Step 2: Generate content
            logger.info(f"[{self.consumer_type}] Generating content")
            result = await self.generate(raw_data, **kwargs)
            record.result_preview = str(result)[:200]

            # Step 3: Record consumption
            record.success = True
            await self.record_consumption(scene_id, result)

            logger.info(f"[{self.consumer_type}] Consumption complete for scene {scene_id}")

        except Exception as e:
            logger.error(f"[{self.consumer_type}] Consumption failed: {e}")
            record.success = False
            record.error = str(e)

        finally:
            record.latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "result": result if record.success else None,
            "record": record,
            "scene_id": scene_id,
        }

    async def record_consumption(
        self, scene_id: str, result: Any
    ) -> ConsumptionRecord:
        """Record a successful consumption.

        Args:
            scene_id: The scene identifier
            result: The generated content

        Returns:
            The created ConsumptionRecord
        """
        record = ConsumptionRecord(
            scene_id=scene_id,
            consumer_type=self.consumer_type,
            success=True,
            result_preview=str(result)[:200],
        )
        self._consumption_records[scene_id] = record
        return record

    def get_consumption_history(self, scene_id: Optional[str] = None) -> list:
        """Get consumption history.

        Args:
            scene_id: If provided, get records for specific scene

        Returns:
            List of ConsumptionRecord objects
        """
        if scene_id:
            return [r for sid, r in self._consumption_records.items() if sid == scene_id]
        return list(self._consumption_records.values())

    def get_last_consumption(self, scene_id: str) -> Optional[ConsumptionRecord]:
        """Get the last consumption record for a scene.

        Args:
            scene_id: The scene identifier

        Returns:
            ConsumptionRecord or None if not found
        """
        return self._consumption_records.get(scene_id)
