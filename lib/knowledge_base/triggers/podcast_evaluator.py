"""Podcast content evaluator with duration-based triggering.

This module implements the PodcastEvaluator which accumulates chapters
until a target listening duration is reached, then triggers podcast generation.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    ContentEvaluator,
    EvaluationResult,
    MaterialPacket,
    TriggerStatus,
)


class PodcastEvaluator(ContentEvaluator):
    """Podcast evaluator - triggers on accumulated listening duration.

    Accumulates chapters and estimates podcast listening duration.
    Triggers when:
    - Estimated duration >= target_duration_minutes, OR
    - Chapter count >= chapters_per_batch (hard cap)

    Configuration:
        target_duration_minutes: Target podcast duration (default 15 min)
        min_chapters: Minimum chapters before first trigger (default 2)
        max_chapters_per_batch: Maximum chapters per podcast batch (default 5)
        cooldown_seconds: Cooldown after trigger (default 600 = 10min)
        chars_per_minute: Estimated speaking rate (default 500 chars/min)
    """

    def __init__(self, config: Dict[str, Any]):
        default_config = {
            "target_duration_minutes": 15,
            "min_chapters": 2,
            "max_chapters_per_batch": 5,
            "cooldown_seconds": 600,  # 10 minutes
            "chars_per_minute": 500,   # ~500 Chinese chars per minute of speech
        }
        merged = {**default_config, **config}
        super().__init__(merged)
        self._logger = logging.getLogger(__name__)

    def _estimate_duration_minutes(self) -> float:
        """Estimate total podcast duration from collected materials."""
        total_chars = sum(len(m.content) for m in self._materials)
        return total_chars / self.config["chars_per_minute"]

    def _chapters_ready(self) -> List[MaterialPacket]:
        """Return materials ready for podcast generation (up to max batch)."""
        max_batch = self.config["max_chapters_per_batch"]
        return self._materials[:max_batch]

    def should_trigger(self) -> bool:
        """Trigger when duration threshold or chapter cap is reached."""
        if not self._can_trigger():
            return False

        if len(self._materials) < self.config["min_chapters"]:
            return False

        est_duration = self._estimate_duration_minutes()
        target = self.config["target_duration_minutes"]

        return (
            est_duration >= target
            or len(self._materials) >= self.config["max_chapters_per_batch"]
        )

    def evaluate(self) -> EvaluationResult:
        """Evaluate current chapter accumulation state."""
        est_duration = self._estimate_duration_minutes()
        chapter_count = len(self._materials)
        target = self.config["target_duration_minutes"]
        min_ch = self.config["min_chapters"]
        max_ch = self.config["max_chapters_per_batch"]

        if chapter_count < min_ch:
            return EvaluationResult(
                status=self._status,
                should_trigger=False,
                confidence=0.0,
                materials=self._materials,
                reason=f"Collecting chapters: {chapter_count}/{min_ch} minimum",
            )

        if est_duration < target and chapter_count < max_ch:
            self._update_status(TriggerStatus.COLLECTING)
            return EvaluationResult(
                status=self._status,
                should_trigger=False,
                confidence=est_duration / target,
                materials=self._materials,
                reason=f"Collecting duration: {est_duration:.1f}min / {target}min target. "
                       f"Chapter {chapter_count}/{max_ch} cap.",
            )

        # Ready to generate
        self._update_status(TriggerStatus.READY)
        return EvaluationResult(
            status=self._status,
            should_trigger=True,
            confidence=min(1.0, est_duration / target),
            materials=self._chapters_ready(),
            reason=f"Ready: {chapter_count} chapters, ~{est_duration:.1f}min duration. "
                   f"Will generate podcast batch.",
        )

    def generate(self, materials: List[MaterialPacket]) -> Dict[str, Any]:
        """Generate podcast content from accumulated chapters.

        Args:
            materials: List of chapter material packets.

        Returns:
            Dict with podcast task info.
        """
        self._mark_triggered()
        self._update_status(TriggerStatus.GENERATING)

        chapters_to_use = self._chapters_ready()
        total_chars = sum(len(m.content) for m in chapters_to_use)
        est_duration = total_chars / self.config["chars_per_minute"]

        # Build podcast task
        # In production: call PodcastConsumer here
        podcast_task = {
            "podcast_id": f"podcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "chapter_count": len(chapters_to_use),
            "chapter_ids": [m.source_id for m in chapters_to_use],
            "total_chars": total_chars,
            "estimated_duration_min": round(est_duration, 1),
            "generated_at": datetime.now().isoformat(),
        }

        self._logger.info(
            f"Generated podcast task: {podcast_task['podcast_id']}, "
            f"{len(chapters_to_use)} chapters, ~{est_duration:.1f}min"
        )

        # Remove used chapters from buffer
        for m in chapters_to_use:
            if m in self._materials:
                self._materials.remove(m)

        self._update_status(TriggerStatus.COLLECTING)

        return {"task": podcast_task, "chapters_used": len(chapters_to_use)}

    def on_scene_extracted(self, scene_data: Dict[str, Any]) -> None:
        """Podcast doesn't use scene events - no-op."""
        pass
