"""Event bus for scene and chapter event distribution.

This module implements a publish-subscribe event bus for distributing
scene and chapter events to registered content evaluators.
"""

import logging
from typing import Any, Callable, Dict, List

from .base import ContentEvaluator


class SceneEventBus:
    """Event bus for scene and chapter event distribution.

    The SceneEventBus implements a publish-subscribe mechanism that allows
    content evaluators to subscribe to specific event types and receive
    notifications when those events occur.

    Example:
        >>> bus = SceneEventBus()
        >>> evaluator = NovelEvaluator({})
        >>> bus.subscribe(evaluator)
        >>> bus.publish_chapter_completed({"chapter_id": 1, "content": "..."})
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: List[ContentEvaluator] = []
        self._logger = logging.getLogger(__name__)

    def subscribe(self, evaluator: ContentEvaluator) -> None:
        """Subscribe an evaluator to the event bus.

        Args:
            evaluator: ContentEvaluator instance to receive events.
        """
        if evaluator not in self._subscribers:
            self._subscribers.append(evaluator)
            self._logger.info(
                f"Subscribed evaluator: {evaluator.__class__.__name__}"
            )
        else:
            self._logger.warning(
                f"Evaluator {evaluator.__class__.__name__} already subscribed"
            )

    def unsubscribe(self, evaluator: ContentEvaluator) -> None:
        """Unsubscribe an evaluator from the event bus.

        Args:
            evaluator: ContentEvaluator instance to remove.
        """
        if evaluator in self._subscribers:
            self._subscribers.remove(evaluator)
            self._logger.info(
                f"Unsubscribed evaluator: {evaluator.__class__.__name__}"
            )
        else:
            self._logger.warning(
                f"Evaluator {evaluator.__class__.__name__} not found in subscribers"
            )

    def publish_chapter_completed(self, chapter_data: Dict[str, Any]) -> None:
        """Publish a chapter completed event to all subscribers.

        All registered evaluators will receive the chapter data and can
        process it according to their own logic.

        Args:
            chapter_data: Dictionary containing chapter information:
                - chapter_id: Unique chapter identifier
                - title: Chapter title
                - content: Chapter content
                - word_count: Number of words
                - Other chapter metadata.
        """
        self._logger.info(
            f"Publishing chapter completed: {chapter_data.get('chapter_id', 'unknown')}"
        )

        for evaluator in self._subscribers:
            try:
                evaluator.on_chapter_completed(chapter_data)
            except Exception as e:
                self._logger.error(
                    f"Error notifying evaluator {evaluator.__class__.__name__}: {e}",
                    exc_info=True
                )

    def publish_scene_extracted(self, scene_data: Dict[str, Any]) -> None:
        """Publish a scene extracted event to all subscribers.

        All registered evaluators will receive the scene data. Only
        evaluators that override on_scene_extracted() will process it.

        Args:
            scene_data: Dictionary containing scene information:
                - scene_id: Unique scene identifier
                - chapter_id: Parent chapter ID
                - content: Scene content
                - scene_type: Type of scene (e.g., "dialogue", "action")
                - Other scene metadata.
        """
        self._logger.info(
            f"Publishing scene extracted: {scene_data.get('scene_id', 'unknown')}"
        )

        for evaluator in self._subscribers:
            try:
                evaluator.on_scene_extracted(scene_data)
            except Exception as e:
                self._logger.error(
                    f"Error notifying evaluator {evaluator.__class__.__name__}: {e}",
                    exc_info=True
                )

    def get_subscriber_count(self) -> int:
        """Get the number of registered subscribers.

        Returns:
            Number of subscribed evaluators.
        """
        return len(self._subscribers)

    def clear_subscribers(self) -> None:
        """Remove all subscribers from the event bus."""
        count = len(self._subscribers)
        self._subscribers.clear()
        self._logger.info(f"Cleared {count} subscribers")
