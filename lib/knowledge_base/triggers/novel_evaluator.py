"""Novel content evaluator - triggers per chapter generation.

This module provides the NovelEvaluator class which is the simplest evaluator:
it triggers on EVERY chapter completion to generate the next chapter.
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


class NovelEvaluator(ContentEvaluator):
    """Novel evaluator - triggers on every chapter completion.

    The NovelEvaluator is the simplest of all evaluators. For novels,
    each chapter is a self-contained narrative unit, so generation is
    triggered immediately on chapter completion (with cooldown to prevent
    double-triggering during generation).

    Configuration:
        cooldown_seconds: Cooldown after trigger (default 60)
        enabled: Whether novel generation is enabled (default True)
    """

    def __init__(self, config: Dict[str, Any]):
        default_config = {
            "cooldown_seconds": 60,  # 1 minute - prevents double-trigger
            "enabled": True,
        }
        merged = {**default_config, **config}
        super().__init__(merged)
        self._logger = logging.getLogger(__name__)

    def should_trigger(self) -> bool:
        """Trigger when at least one chapter is available and not in cooldown."""
        if not self._can_trigger():
            return False
        return len(self._materials) >= 1 and self.config.get("enabled", True)

    def evaluate(self) -> EvaluationResult:
        """Evaluate current state - always READY if materials exist."""
        if not self._materials:
            return EvaluationResult(
                status=self._status,
                should_trigger=False,
                confidence=0.0,
                materials=[],
                reason="No chapters collected yet",
            )

        return EvaluationResult(
            status=TriggerStatus.READY if self.config.get("enabled") else TriggerStatus.COLLECTING,
            should_trigger=self.should_trigger(),
            confidence=0.9,
            materials=self._materials,
            reason=f"Chapter {self._materials[-1].source_id} ready for generation",
        )

    def generate(self, materials: List[MaterialPacket]) -> Dict[str, Any]:
        """Trigger next chapter generation.

        For novels, this is the simplest case: take the latest chapter
        and trigger generation of the next chapter number.

        In production: calls NovelOrchestrator.generate_chapter(next_chapter_num).

        Args:
            materials: List of material packets (the latest is used).

        Returns:
            Dict with next chapter number and generation metadata.
        """
        if not materials:
            return {"error": "No materials to generate from"}

        self._mark_triggered()
        self._update_status(TriggerStatus.GENERATING)

        latest = materials[-1]
        # Extract chapter number from source_id (e.g., "ch001" -> 2)
        current_num = self._parse_chapter_number(latest.source_id)
        next_num = current_num + 1

        self._logger.info(
            f"NovelEval triggering chapter {next_num} generation "
            f"(after chapter {current_num})"
        )

        # In production: call NovelOrchestrator here
        task = {
            "task_type": "novel_chapter",
            "chapter_number": next_num,
            "triggered_by_chapter": current_num,
            "triggered_at": datetime.now().isoformat(),
        }

        # Clear the materials after triggering
        self._clear_materials()
        self._update_status(TriggerStatus.COLLECTING)

        return {"should_trigger": True, "status": "generated", **task}

    def _parse_chapter_number(self, source_id: str) -> int:
        """Parse chapter number from source_id string.

        Handles formats: "ch001", "001", "ch_001", 1
        """
        if not source_id:
            return 0
        # Try numeric
        try:
            return int(source_id)
        except ValueError:
            pass
        # Try chNNN pattern
        import re
        m = re.search(r'(\d+)', source_id)
        if m:
            return int(m.group(1))
        return 0

    def on_scene_extracted(self, scene_data: Dict[str, Any]) -> None:
        """Novel doesn't use scene events - no-op."""
        pass
