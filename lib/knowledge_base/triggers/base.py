"""Base classes for content evaluators and trigger system.

This module defines the core abstractions for the multi-modal trigger
architecture, including evaluator base class, status enum, and data classes.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriggerStatus(Enum):
    """Represents the current status of a content evaluator.

    Attributes:
        COLLECTING: Evaluator is collecting materials for evaluation.
        READY: Evaluator has sufficient materials and is ready to trigger.
        GENERATING: Content generation is in progress.
        COOLDOWN: Evaluator is in cooldown period after generation.
    """
    COLLECTING = "collecting"
    READY = "ready"
    GENERATING = "generating"
    COOLDOWN = "cooldown"


@dataclass
class MaterialPacket:
    """A packet of material data for content evaluation.

    Attributes:
        content: The raw content material (text, audio data, video data, etc.).
        content_type: Type of content (e.g., "text", "audio", "video").
        source: Source identifier (e.g., "chapter", "scene", "podcast_episode").
        source_id: Unique identifier for the source.
        metadata: Additional metadata about the material.
        timestamp: When the material was created/received.
    """
    content: Any
    content_type: str
    source: str
    source_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class EvaluationResult:
    """Result of a content evaluation.

    Attributes:
        status: Current trigger status after evaluation.
        should_trigger: Whether content generation should be triggered.
        confidence: Confidence score (0.0 to 1.0) for the decision.
        materials: List of material packets used in evaluation.
        reason: Human-readable reason for the decision.
        next_evaluation: When to schedule the next evaluation.
        metadata: Additional evaluation metadata.
    """
    status: TriggerStatus
    should_trigger: bool
    confidence: float
    materials: List[MaterialPacket]
    reason: str
    next_evaluation: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate confidence score
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


class ContentEvaluator(ABC):
    """Abstract base class for content evaluators.

    Content evaluators assess materials and determine when content generation
    should be triggered based on various criteria (completeness, quality, etc.).

    Attributes:
        config: Configuration dictionary for the evaluator.
        _materials: Internal storage for collected materials.
        _status: Current trigger status.
        _last_trigger_time: Timestamp of the last trigger event.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize the content evaluator.

        Args:
            config: Configuration dictionary containing:
                - cooldown_seconds: Cooldown period after triggering (default: 300)
                - min_materials: Minimum materials before evaluation (default: 1)
                - Other evaluator-specific settings.
        """
        self.config = config
        self._materials: List[MaterialPacket] = []
        self._status = TriggerStatus.COLLECTING
        self._last_trigger_time: Optional[datetime] = None
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @property
    def status(self) -> TriggerStatus:
        """Get the current trigger status."""
        return self._status

    @property
    def materials(self) -> List[MaterialPacket]:
        """Get a copy of collected materials."""
        return list(self._materials)

    @property
    def cooldown_seconds(self) -> int:
        """Get the cooldown period in seconds."""
        return self.config.get("cooldown_seconds", 300)

    @abstractmethod
    def evaluate(self) -> EvaluationResult:
        """Evaluate collected materials and determine if triggering is appropriate.

        This method must be implemented by subclasses to provide
        content-type-specific evaluation logic.

        Returns:
            EvaluationResult containing the evaluation decision.
        """
        pass

    @abstractmethod
    def should_trigger(self) -> bool:
        """Determine if content generation should be triggered.

        This method must be implemented by subclasses to provide
        content-type-specific trigger logic.

        Returns:
            True if generation should be triggered, False otherwise.
        """
        pass

    @abstractmethod
    def generate(self, materials: List[MaterialPacket]) -> Any:
        """Generate content using the provided materials.

        This method must be implemented by subclasses to provide
        content-type-specific generation logic.

        Args:
            materials: List of material packets to use for generation.

        Returns:
            Generated content (type depends on evaluator type).
        """
        pass

    def on_chapter_completed(self, chapter_data: Dict[str, Any]) -> None:
        """Handle chapter completion event with cooldown check.

        This method is called when a chapter is completed. It checks if
        the evaluator is in cooldown before accepting new materials.

        Args:
            chapter_data: Dictionary containing chapter information:
                - chapter_id: Unique chapter identifier
                - title: Chapter title
                - content: Chapter content
                - word_count: Number of words
                - Other chapter metadata.
        """
        if not self._can_trigger():
            self._logger.debug(
                f"Evaluator in cooldown, ignoring chapter: {chapter_data.get('chapter_id')}"
            )
            return

        # Create material packet from chapter data
        material = MaterialPacket(
            content=chapter_data.get("content", ""),
            content_type="text",
            source="chapter",
            source_id=str(chapter_data.get("chapter_id", "")),
            metadata={
                "title": chapter_data.get("title", ""),
                "word_count": chapter_data.get("word_count", 0),
            },
        )

        self._add_material(material)
        self._logger.info(f"Received chapter: {material.source_id}")

    def on_scene_extracted(self, scene_data: Dict[str, Any]) -> None:
        """Handle scene extracted event (base class no-op implementation).

        Subclasses can override this method to handle scene extraction events.

        Args:
            scene_data: Dictionary containing scene information.
        """
        # Base class does nothing - subclasses can override
        pass

    def _add_material(self, material: MaterialPacket) -> None:
        """Add a material to the internal storage.

        Args:
            material: MaterialPacket to add.
        """
        self._materials.append(material)
        self._logger.debug(f"Added material from {material.source}, total: {len(self._materials)}")

    def _can_trigger(self) -> bool:
        """Check if the evaluator can trigger (not in cooldown).

        Returns:
            True if not in cooldown period, False otherwise.
        """
        if self._last_trigger_time is None:
            return True

        elapsed = datetime.now() - self._last_trigger_time
        can_trigger = elapsed >= timedelta(seconds=self.cooldown_seconds)

        if not can_trigger:
            remaining = self.cooldown_seconds - elapsed.total_seconds()
            self._logger.debug(
                f"Evaluator in cooldown, {remaining:.1f}s remaining"
            )

        return can_trigger

    def _update_status(self, status: TriggerStatus) -> None:
        """Update the evaluator status.

        Args:
            status: New status to set.
        """
        old_status = self._status
        self._status = status
        self._logger.debug(f"Status changed: {old_status.value} -> {status.value}")

    def _mark_triggered(self) -> None:
        """Mark that a trigger event occurred and enter cooldown."""
        self._last_trigger_time = datetime.now()
        self._update_status(TriggerStatus.COOLDOWN)
        self._logger.info(f"Trigger marked at {self._last_trigger_time}")

    def _clear_materials(self) -> None:
        """Clear all collected materials."""
        self._materials.clear()
        self._logger.debug("Materials cleared")
