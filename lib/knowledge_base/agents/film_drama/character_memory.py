"""CharacterMemoryQueue for tracking emotional/state across beats."""

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class EmotionalState:
    """Character's emotional state at a point in time."""
    beat_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    emotions: Dict[str, bool] = field(default_factory=dict)
    conflict_active: bool = False
    tension_level: float = 0.0  # 0.0-1.0
    summary: str = ""  # Brief summary of current state


# Capacity limits to prevent unbounded growth
MAX_STATES_PER_CHARACTER = 50
MAX_KEY_MOMENTS_PER_CHARACTER = 20


@dataclass
class CharacterMemory:
    """Memory for a single character across the scene."""
    character_name: str
    states: List[EmotionalState] = field(default_factory=list)
    key_moments: List[str] = field(default_factory=list)  # Beat IDs that were significant
    relationship_updates: Dict[str, str] = field(default_factory=dict)

    def add_state(self, state: EmotionalState) -> None:
        """Add a new emotional state."""
        self.states.append(state)
        # Enforce capacity limit
        while len(self.states) > MAX_STATES_PER_CHARACTER:
            self.states.pop(0)
        logger.debug(f"[Memory] {self.character_name} state updated: {state.emotions}")

    def get_current_state(self) -> Optional[EmotionalState]:
        """Get the most recent state."""
        return self.states[-1] if self.states else None

    def get_state_history(self) -> List[EmotionalState]:
        """Get full state history."""
        return list(self.states)


class CharacterMemoryQueue:
    """Queue for tracking character emotional states across beats.

    Provides:
    - Per-character emotional state tracking
    - State history for continuity
    - Key moment marking
    - Relationship updates
    """

    def __init__(self):
        self._character_memories: Dict[str, CharacterMemory] = {}
        self._global_tension: float = 0.0
        self._async_lock = asyncio.Lock()  # For async methods
        self._sync_lock = threading.Lock()  # For sync methods

    def get_or_create_memory(self, character_name: str) -> CharacterMemory:
        """Get or create memory for a character."""
        if character_name not in self._character_memories:
            self._character_memories[character_name] = CharacterMemory(
                character_name=character_name
            )
        return self._character_memories[character_name]

    async def record_state_async(
        self,
        character_name: str,
        beat_id: str,
        emotions: Dict[str, bool],
        conflict_active: bool = False,
        tension_level: float = 0.0,
        summary: str = "",
    ) -> None:
        """Record character emotional state (async thread-safe version)."""
        async with self._async_lock:
            memory = self.get_or_create_memory(character_name)
            state = EmotionalState(
                beat_id=beat_id,
                emotions=emotions,
                conflict_active=conflict_active,
                tension_level=tension_level,
                summary=summary,
            )
            memory.add_state(state)
            logger.debug(
                f"[Memory] Recorded state for {character_name} at beat {beat_id}: "
                f"tension={tension_level:.2f}"
            )

    def record_state(
        self,
        character_name: str,
        beat_id: str,
        emotions: Dict[str, bool],
        conflict_active: bool = False,
        tension_level: float = 0.0,
        summary: str = "",
    ) -> None:
        """Record character emotional state (sync, thread-safe via lock)."""
        with self._sync_lock:
            memory = self.get_or_create_memory(character_name)
            state = EmotionalState(
                beat_id=beat_id,
                emotions=emotions,
                conflict_active=conflict_active,
                tension_level=tension_level,
                summary=summary,
            )
            memory.add_state(state)
            logger.debug(
                f"[Memory] Recorded state for {character_name} at beat {beat_id}: "
                f"tension={tension_level:.2f}"
            )

    def mark_key_moment(self, character_name: str, beat_id: str, description: str) -> None:
        """Mark a beat as a key moment for a character."""
        memory = self.get_or_create_memory(character_name)
        memory.key_moments.append(f"[{beat_id}] {description}")
        # Enforce capacity limit
        while len(memory.key_moments) > MAX_KEY_MOMENTS_PER_CHARACTER:
            memory.key_moments.pop(0)
        logger.debug(f"[Memory] {character_name} key moment: {description}")

    def update_relationship(
        self,
        character_name: str,
        other_character: str,
        relationship_status: str,
    ) -> None:
        """Record a relationship update."""
        memory = self.get_or_create_memory(character_name)
        memory.relationship_updates[other_character] = relationship_status
        logger.debug(
            f"[Memory] {character_name} -> {other_character}: {relationship_status}"
        )

    def get_current_tension(self, character_name: str) -> float:
        """Get current tension level for a character."""
        memory = self._character_memories.get(character_name)
        if not memory:
            return 0.0
        current = memory.get_current_state()
        return current.tension_level if current else 0.0

    def get_all_tensions(self) -> Dict[str, float]:
        """Get tension levels for all characters."""
        return {
            char_name: self.get_current_tension(char_name)
            for char_name in self._character_memories
        }

    async def update_global_tension_async(self, delta: float) -> None:
        """Update global tension level (async thread-safe version)."""
        async with self._async_lock:
            self._global_tension = max(0.0, min(1.0, self._global_tension + delta))
            logger.debug(f"[Memory] Global tension: {self._global_tension:.2f}")

    def update_global_tension(self, delta: float) -> None:
        """Update global tension level (sync, thread-safe via lock)."""
        with self._sync_lock:
            self._global_tension = max(0.0, min(1.0, self._global_tension + delta))
        logger.debug(f"[Memory] Global tension: {self._global_tension:.2f}")

    def get_global_tension(self) -> float:
        """Get global scene tension."""
        return self._global_tension

    def get_context_for_character(
        self,
        character_name: str,
        include_history: bool = False,
    ) -> Dict[str, Any]:
        """Get memory context for a character.

        Used when building prompts for the character agent.
        """
        memory = self._character_memories.get(character_name)
        if not memory:
            return {
                "character_name": character_name,
                "current_emotions": {},
                "conflict_active": False,
                "tension_level": 0.0,
                "global_tension": self._global_tension,
            }

        current = memory.get_current_state()

        context = {
            "character_name": character_name,
            "current_emotions": current.emotions if current else {},
            "conflict_active": current.conflict_active if current else False,
            "tension_level": current.tension_level if current else 0.0,
            "global_tension": self._global_tension,
            "key_moments": memory.key_moments[-3:] if memory.key_moments else [],
            "relationship_updates": memory.relationship_updates,
        }

        if include_history:
            context["state_history"] = [
                {
                    "beat_id": s.beat_id,
                    "emotions": s.emotions,
                    "tension": s.tension_level,
                    "summary": s.summary,
                }
                for s in memory.states[-5:]  # Last 5 states
            ]

        return context

    def get_scene_summary(self) -> Dict[str, Any]:
        """Get a summary of the scene state for all characters."""
        return {
            "global_tension": self._global_tension,
            "character_states": {
                char_name: {
                    "tension": self.get_current_tension(char_name),
                    "emotions": (
                        memory.get_current_state().emotions
                        if memory.get_current_state()
                        else {}
                    ),
                    "key_moments_count": len(memory.key_moments),
                }
                for char_name, memory in self._character_memories.items()
            },
        }

    def clear(self) -> None:
        """Clear all memory (for new scene)."""
        self._character_memories.clear()
        self._global_tension = 0.0
        logger.debug("[Memory] All memories cleared")
