# -*- encoding: utf-8 -*-
"""Consumer Orchestrator - orchestrates multiple consumers for parallel execution.

The orchestrator manages multiple consumers and executes them in parallel
for a given scene, collecting results from all downstream consumers.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from .base import BaseConsumer, ConsumptionRecord

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for ConsumerOrchestrator.

    Attributes:
        max_concurrent: Maximum concurrent consumer executions
        timeout_seconds: Timeout for each consumer execution
        stop_on_error: Whether to stop other consumers if one fails
        enable_caching: Whether to cache consumption results
    """

    max_concurrent: int = 4
    timeout_seconds: int = 300
    stop_on_error: bool = False
    enable_caching: bool = True


@dataclass
class OrchestratorResult:
    """Result of orchestrator execution.

    Attributes:
        scene_id: The input scene ID
        results: Dict of consumer_type -> consumption result
        errors: Dict of consumer_type -> error message
        total_duration_ms: Total execution time
        success: Whether all consumers succeeded
    """

    scene_id: str
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scene_id": self.scene_id,
            "results": {
                k: v if not hasattr(v, "to_dict") else v.to_dict()
                for k, v in self.results.items()
            },
            "errors": self.errors,
            "total_duration_ms": self.total_duration_ms,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
        }

    def get_result(self, consumer_type: str) -> Optional[Any]:
        """Get result for a specific consumer type.

        Args:
            consumer_type: The consumer type identifier

        Returns:
            The result or None if not found/error
        """
        if consumer_type in self.errors:
            return None
        return self.results.get(consumer_type, {}).get("result")

    def is_successful(self, consumer_type: str) -> bool:
        """Check if a specific consumer succeeded.

        Args:
            consumer_type: The consumer type identifier

        Returns:
            True if the consumer succeeded
        """
        return consumer_type not in self.errors and consumer_type in self.results


class ConsumerOrchestrator:
    """Orchestrates multiple consumers for parallel scene consumption.

    The orchestrator registers multiple consumers and executes them in parallel
    when consume_all() is called, collecting results from all downstream
    consumers.

    Architecture:
        FILM-DRAMA (generates raw data)
            ↓ (via SceneStore persistence)
            ↓ (event notification)
        ConsumerOrchestrator
            ↓ (parallel execution)
            ├── NovelConsumer → Novel text
            ├── PodcastConsumer → Audio script
            ├── VideoConsumer → Video script
            └── MusicConsumer → Music prompts

    Usage:
        from knowledge_base.consumers import (
            ConsumerOrchestrator,
            NovelConsumer,
            PodcastConsumer,
            SceneStore,
        )

        # Setup
        scene_store = SceneStore()
        orchestrator = ConsumerOrchestrator(scene_store)
        orchestrator.register(NovelConsumer(llm_client))
        orchestrator.register(PodcastConsumer(llm_client))

        # Execute
        result = await orchestrator.consume_all(scene_id)
        if result.success:
            novel = result.get_result("novel")
            podcast = result.get_result("podcast")
    """

    def __init__(
        self,
        scene_store: Any = None,
        config: Optional[OrchestratorConfig] = None,
    ):
        """Initialize the orchestrator.

        Args:
            scene_store: SceneStore instance for scene data access
            config: Orchestrator configuration
        """
        self.scene_store = scene_store
        self.config = config or OrchestratorConfig()
        self.consumers: Dict[str, BaseConsumer] = {}
        self._consumption_history: List[OrchestratorResult] = []

        logger.info("[Orchestrator] ConsumerOrchestrator initialized")

    def register(self, consumer: BaseConsumer) -> None:
        """Register a consumer with the orchestrator.

        Args:
            consumer: A BaseConsumer subclass instance

        Raises:
            ValueError: If consumer_type is already registered
        """
        consumer_type = consumer.consumer_type

        if consumer_type in self.consumers:
            raise ValueError(
                f"Consumer type '{consumer_type}' already registered. "
                f"Use replace() to overwrite."
            )

        # Inject scene_store if consumer doesn't have one
        if consumer.scene_store is None and self.scene_store is not None:
            consumer.scene_store = self.scene_store

        self.consumers[consumer_type] = consumer
        logger.info(f"[Orchestrator] Registered consumer: {consumer_type}")

    def replace(self, consumer: BaseConsumer) -> None:
        """Replace an existing consumer or register if not exists.

        Args:
            consumer: A BaseConsumer subclass instance
        """
        consumer_type = consumer.consumer_type

        # Inject scene_store if consumer doesn't have one
        if consumer.scene_store is None and self.scene_store is not None:
            consumer.scene_store = self.scene_store

        self.consumers[consumer_type] = consumer
        logger.info(f"[Orchestrator] Replaced consumer: {consumer_type}")

    def unregister(self, consumer_type: str) -> bool:
        """Unregister a consumer by type.

        Args:
            consumer_type: The consumer type to remove

        Returns:
            True if consumer was removed, False if not found
        """
        if consumer_type in self.consumers:
            del self.consumers[consumer_type]
            logger.info(f"[Orchestrator] Unregistered consumer: {consumer_type}")
            return True
        return False

    def get_consumer(self, consumer_type: str) -> Optional[BaseConsumer]:
        """Get a registered consumer by type.

        Args:
            consumer_type: The consumer type identifier

        Returns:
            The consumer instance or None
        """
        return self.consumers.get(consumer_type)

    def list_consumers(self) -> List[str]:
        """List all registered consumer types.

        Returns:
            List of consumer type identifiers
        """
        return list(self.consumers.keys())

    async def consume_all(
        self,
        scene_id: str,
        consumer_types: Optional[List[str]] = None,
        **kwargs,
    ) -> OrchestratorResult:
        """Execute all registered consumers in parallel for a scene.

        Args:
            scene_id: The scene identifier
            consumer_types: Optional list of specific consumer types to run.
                          If None, all registered consumers will run.
            **kwargs: Additional parameters passed to each consumer

        Returns:
            OrchestratorResult with all consumer results
        """
        import time

        start_time = time.perf_counter()
        result = OrchestratorResult(scene_id=scene_id)

        # Determine which consumers to run
        if consumer_types:
            consumers_to_run = {
                ct: self.consumers[ct]
                for ct in consumer_types
                if ct in self.consumers
            }
            missing = set(consumer_types) - set(consumers_to_run.keys())
            if missing:
                logger.warning(f"[Orchestrator] Unknown consumer types: {missing}")
        else:
            consumers_to_run = self.consumers

        if not consumers_to_run:
            logger.warning(f"[Orchestrator] No consumers registered for scene {scene_id}")
            result.success = False
            result.errors["orchestrator"] = "No consumers registered"
            return result

        logger.info(
            f"[Orchestrator] Starting consumption for scene {scene_id} "
            f"with consumers: {list(consumers_to_run.keys())}"
        )

        # Create tasks for parallel execution
        tasks = {
            consumer_type: consumer.consume(scene_id, **kwargs)
            for consumer_type, consumer in consumers_to_run.items()
        }

        # Execute with concurrency limit
        if len(tasks) > self.config.max_concurrent:
            # Use semaphore to limit concurrency
            semaphore = asyncio.Semaphore(self.config.max_concurrent)

            async def limited_consume(consumer_type: str, coro):
                async with semaphore:
                    return consumer_type, await coro

            results = await asyncio.gather(
                *[limited_consume(ct, coro) for ct, coro in tasks.items()],
                return_exceptions=True,
            )
        else:
            results = await asyncio.gather(
                *tasks.values(),
                return_exceptions=True,
            )

        # Process results
        consumer_types_list = list(tasks.keys())
        for i, res in enumerate(results):
            consumer_type = consumer_types_list[i]

            if isinstance(res, Exception):
                error_msg = str(res)
                logger.error(f"[Orchestrator] {consumer_type} failed: {error_msg}")
                result.errors[consumer_type] = error_msg
                result.success = False
            else:
                # Check if consume() returned an error in the record
                record = res.get("record")
                if record and not record.success:
                    result.errors[consumer_type] = record.error or "Unknown error"
                    result.success = False
                    logger.error(
                        f"[Orchestrator] {consumer_type} consumption failed: {record.error}"
                    )
                else:
                    result.results[consumer_type] = res

        result.total_duration_ms = (time.perf_counter() - start_time) * 1000

        # Store in history
        self._consumption_history.append(result)

        logger.info(
            f"[Orchestrator] Consumption complete for scene {scene_id}: "
            f"success={result.success}, duration={result.total_duration_ms:.0f}ms"
        )

        return result

    async def consume_single(
        self,
        scene_id: str,
        consumer_type: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute a single consumer for a scene.

        Args:
            scene_id: The scene identifier
            consumer_type: The specific consumer type to run
            **kwargs: Additional parameters

        Returns:
            The consumer result dict

        Raises:
            ValueError: If consumer type is not registered
        """
        consumer = self.consumers.get(consumer_type)
        if consumer is None:
            raise ValueError(f"Consumer type not registered: {consumer_type}")

        return await consumer.consume(scene_id, **kwargs)

    def get_history(
        self,
        scene_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[OrchestratorResult]:
        """Get consumption history.

        Args:
            scene_id: Optional scene ID to filter by
            limit: Maximum number of results

        Returns:
            List of OrchestratorResult objects
        """
        if scene_id:
            return [
                r for r in self._consumption_history[-limit:]
                if r.scene_id == scene_id
            ]
        return self._consumption_history[-limit:]

    def get_latest_result(self, scene_id: str) -> Optional[OrchestratorResult]:
        """Get the latest result for a scene.

        Args:
            scene_id: The scene identifier

        Returns:
            Latest OrchestratorResult or None
        """
        scene_results = [
            r for r in reversed(self._consumption_history)
            if r.scene_id == scene_id
        ]
        return scene_results[0] if scene_results else None

    def clear_history(self) -> None:
        """Clear consumption history."""
        self._consumption_history.clear()
        logger.info("[Orchestrator] History cleared")


# Factory function for quick setup
def create_orchestrator(
    scene_store: Any,
    llm_client: Any,
    consumer_types: Optional[List[str]] = None,
    config: Optional[OrchestratorConfig] = None,
) -> ConsumerOrchestrator:
    """Create and populate an orchestrator with default consumers.

    Args:
        scene_store: SceneStore instance
        llm_client: LLM client for all consumers
        consumer_types: List of consumer types to include.
                       Defaults to all: ["novel", "podcast", "video", "music"]
        config: Orchestrator configuration

    Returns:
        Configured ConsumerOrchestrator instance
    """
    from .novel_consumer import NovelConsumer
    from .podcast_consumer import PodcastConsumer
    from .video_consumer import VideoConsumer
    from .music_consumer import MusicConsumer

    orchestrator = ConsumerOrchestrator(scene_store, config)

    # Default to all consumers if none specified
    if consumer_types is None:
        consumer_types = ["novel", "podcast", "video", "music"]

    consumer_classes = {
        "novel": NovelConsumer,
        "podcast": PodcastConsumer,
        "video": VideoConsumer,
        "music": MusicConsumer,
    }

    for ct in consumer_types:
        if ct in consumer_classes:
            consumer = consumer_classes[ct](llm_client=llm_client)
            orchestrator.register(consumer)

    return orchestrator
