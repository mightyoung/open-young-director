"""Seed mechanism for deterministic replay and incremental regeneration.

This module provides:
- SeedConfig: Records seed source and generation parameters
- ReplayPlan: Determines which stages need regeneration
- DirtyTracker: Tracks data changes
- set_llm_seed(): Sets seed on LLM with fallback support

Based on LangGraph checkpoint design principles:
- Checkpoint = state's recoverable snapshot
- Task = memoized execution unit
- Replay = deterministic replay based on checkpoint
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# SeedConfig
# =============================================================================


@dataclass
class SeedConfig:
    """Seed configuration - records seed source and generation parameters.

    Attributes:
        seed: The actual seed value (32-char hex string)
        topic: Original topic
        genre: Original genre
        style: Original style
        variant: Optional variant identifier for generating different variants
        version: Seed version number
    """

    seed: str = ""
    topic: str = ""
    genre: str = ""
    style: str = ""
    variant: Optional[str] = None
    version: int = 1

    def generate_seed(self) -> str:
        """Generate seed from parameters.

        Returns:
            32-character hex seed string
        """
        combined = f"{self.topic}|{self.genre}|{self.style}|{self.variant or 'default'}"
        hash_digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        self.seed = hash_digest[:32]
        return self.seed

    def matches(self, other: SeedConfig) -> bool:
        """Check if configurations are compatible (core parameters match).

        Variant differences are allowed since they generate different outputs
        from the same core story.

        Args:
            other: Another SeedConfig to compare

        Returns:
            True if core parameters match
        """
        return (
            self.topic == other.topic
            and self.genre == other.genre
            and self.style == other.style
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeedConfig:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def from_legacy(cls, seed: str, topic: str = "", genre: str = "", style: str = "") -> SeedConfig:
        """Create SeedConfig from legacy seed format.

        Args:
            seed: The legacy seed string
            topic: Topic (from metadata if available)
            genre: Genre
            style: Style

        Returns:
            SeedConfig instance
        """
        return cls(
            seed=seed,
            topic=topic,
            genre=genre,
            style=style,
        )


# =============================================================================
# ReplayPlan
# =============================================================================


@dataclass
class ReplayPlan:
    """Replay plan determining which stages need regeneration.

    Based on LangGraph's principle: completed tasks are cached and skipped,
    only incomplete/failed tasks are re-executed.
    """

    # Whether to regenerate everything
    regenerate_all: bool = False
    # Whether to replay everything using cache (no regeneration needed)
    replay_all: bool = False
    # Which stage to start regeneration from (world/outline/chapters)
    regenerate_from: Optional[str] = None
    # Which stage data to preserve
    preserve: list[str] = field(default_factory=list)
    # Which chapters need regeneration
    dirty_chapters: Optional[list[int]] = None

    def should_regenerate_world(self) -> bool:
        """Check if world stage needs regeneration."""
        return self.regenerate_all or self.regenerate_from == "world"

    def should_regenerate_outline(self) -> bool:
        """Check if outline stage needs regeneration."""
        return self.regenerate_all or self.regenerate_from in ("world", "outline")

    def should_regenerate_chapters(self) -> bool:
        """Check if chapters stage needs regeneration."""
        if self.regenerate_all or self.regenerate_from in ("world", "outline", "chapters"):
            return True
        return bool(self.dirty_chapters)

    def get_chapters_to_regenerate(self) -> Optional[list[int]]:
        """Get list of chapters to regenerate, or None for all.

        Returns:
            List of chapter indices to regenerate, or None for all
        """
        if self.regenerate_all or not self.dirty_chapters:
            return None
        return self.dirty_chapters

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplayPlan:
        """Create from dictionary."""
        return cls(**data)


# =============================================================================
# DirtyTracker
# =============================================================================


class DirtyTracker:
    """Tracks data field changes.

    Used to determine which parts of the pipeline state need
    to be regenerated based on user modifications.
    """

    def __init__(self):
        self._dirty_fields: dict[str, bool] = {}
        self._original_values: dict[str, Any] = {}

    def mark_dirty(self, field: str) -> None:
        """Mark a field as dirty (modified).

        Args:
            field: Field name to mark
        """
        if field not in self._original_values:
            self._original_values[field] = None  # Placeholder
        self._dirty_fields[field] = True

    def mark_clean(self, field: str) -> None:
        """Mark a field as clean (not needing regeneration).

        Args:
            field: Field name to mark
        """
        self._dirty_fields[field] = False

    def is_dirty(self, field: str) -> bool:
        """Check if a field is dirty.

        Args:
            field: Field name to check

        Returns:
            True if field is dirty
        """
        return self._dirty_fields.get(field, False)

    def get_dirty_fields(self) -> list[str]:
        """Get all dirty field names.

        Returns:
            List of field names that are dirty
        """
        return [f for f, is_dirty in self._dirty_fields.items() if is_dirty]

    def clear(self) -> None:
        """Clear all dirty tracking."""
        self._dirty_fields.clear()
        self._original_values.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dirty_fields": self._dirty_fields,
            "original_values": self._original_values,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DirtyTracker:
        """Create from dictionary."""
        tracker = cls()
        tracker._dirty_fields = data.get("dirty_fields", {})
        tracker._original_values = data.get("original_values", {})
        return tracker


# =============================================================================
# LLM Seed Setting
# =============================================================================


def set_llm_seed(llm: Any, seed: str) -> bool:
    """Set seed on LLM with fallback support.

    Tries multiple methods to set the seed:
    1. Direct attribute: llm.seed
    2. Method call: llm.set_seed()
    3. Config dict: llm.config["seed"]

    Args:
        llm: LLM instance
        seed: 32-character hex seed string

    Returns:
        True if seed was successfully set, False otherwise
    """
    if not llm:
        return False

    # Convert hex seed to int (mod 2^32 for API compatibility)
    try:
        llm_seed = int(seed, 16) % (2**32)
    except ValueError:
        logger.warning(f"Invalid seed format: {seed}")
        return False

    # Method 1: Direct attribute
    if hasattr(llm, "seed"):
        try:
            llm.seed = llm_seed
            logger.info(f"LLM seed set via attribute: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via attribute: {e}")

    # Method 2: Method call
    if hasattr(llm, "set_seed"):
        try:
            llm.set_seed(llm_seed)
            logger.info(f"LLM seed set via method: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via method: {e}")

    # Method 3: Config dict
    if hasattr(llm, "config") and isinstance(llm.config, dict):
        try:
            llm.config["seed"] = llm_seed
            logger.info(f"LLM seed set via config: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via config: {e}")

    # Method 4: kwargs (for some LLM implementations)
    if hasattr(llm, "kwargs") and isinstance(llm.kwargs, dict):
        try:
            llm.kwargs["seed"] = llm_seed
            logger.info(f"LLM seed set via kwargs: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via kwargs: {e}")

    logger.warning(f"LLM does not support seed setting")
    return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "SeedConfig",
    "ReplayPlan",
    "DirtyTracker",
    "set_llm_seed",
]
