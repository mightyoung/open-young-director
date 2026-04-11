"""HumanReviewGate — per-stage approval gate for pipeline checkpoints.

Enables pausing the pipeline after any stage to wait for human review
and approval before proceeding. Supports three modes:
  - Automatic pass-through (disabled_stages)
  - Auto-approve with logging (auto_approve=True)
  - Callback-based approval (callback provided)
  - Save-and-pause for manual review (callback=None)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HumanReviewGate:
    """Immutable gate for per-stage human review.

    Attributes:
        enabled_stages: Frozenset of stage names that require approval
            (e.g., {"outline", "evaluate", "volume"}). Stages not in this
            set automatically pass without blocking.
        auto_approve: If True, log but don't block; proceed automatically.
        callback: Optional callable(stage_name: str, state_summary: dict) -> bool.
            If provided, called for approval decision. Return True to proceed,
            False to pause. If None, state is saved and method returns False
            (caller must pause and resume later).
    """

    enabled_stages: frozenset[str]
    auto_approve: bool = False
    callback: Callable[[str, dict], bool] | None = None

    def check(self, stage_name: str, state: Any) -> bool:
        """Check whether stage should be approved to proceed.

        Args:
            stage_name: Name of the stage (e.g., "outline", "writing").
            state: Pipeline state object (typically PipelineState).

        Returns:
            True if approved (or not gated); False if waiting for manual approval.
        """
        # Stage not in enabled_stages — auto-pass
        if stage_name not in self.enabled_stages:
            return True

        # Stage is gated; check approval mode
        if self.auto_approve:
            logger.info(
                "HumanReviewGate: auto-approving stage %r (auto_approve=True)",
                stage_name,
            )
            return True

        if self.callback:
            summary = self._state_to_dict(state)
            approved = self.callback(stage_name, summary)
            logger.info(
                "HumanReviewGate: callback approved stage %r: %s", stage_name, approved
            )
            return approved

        # No callback and not auto_approve — must pause
        logger.info(
            "HumanReviewGate: pausing at stage %r (awaiting manual approval)",
            stage_name,
        )
        return False

    def format_review_prompt(self, stage_name: str, state: Any) -> str:
        """Format a human-readable summary of stage output for review.

        Args:
            stage_name: Name of the stage.
            state: Pipeline state object.

        Returns:
            Human-readable multi-line summary string.
        """
        summary = self._state_to_dict(state)
        lines = [
            f"=== Review Gate: {stage_name} ===",
            f"Current stage: {summary.get('current_stage', 'unknown')}",
        ]

        # Add any stage-specific keys from the state dict
        for key, value in summary.items():
            if key != "current_stage" and value is not None:
                # Truncate large values to keep prompt readable
                value_str = str(value)
                if len(value_str) > 200:
                    value_str = value_str[:200] + "..."
                lines.append(f"{key}: {value_str}")

        return "\n".join(lines)

    @staticmethod
    def _state_to_dict(state: Any) -> dict[str, Any]:
        """Extract state as a dict, handling both dataclass and dict inputs."""
        if isinstance(state, dict):
            return state
        # Assume it's a dataclass or has __dict__
        if hasattr(state, "__dict__"):
            return {k: v for k, v in state.__dict__.items() if not k.startswith("_")}
        return {}
