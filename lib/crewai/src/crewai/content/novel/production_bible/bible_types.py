"""Canonical data types for the Production Bible system.

This module defines the core dataclasses that form the single source of truth
for all story facts during parallel volume generation.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CharacterProfile:
    """Canonical character information stored in the bible."""

    name: str
    role: str  # protagonist, antagonist, supporting
    personality: str
    appearance: str
    core_desire: str
    fear: str
    backstory: str
    character_arc: str  # how they change across the story
    first_appearance: int  # chapter number
    cultivation_realm: Optional[str] = None
    faction: Optional[str] = None
    speech_pattern: Optional[str] = None  # how they talk
    relationships: dict[str, str] = field(default_factory=dict)  # name → relationship description


@dataclass
class WorldRules:
    """Canonical world physics and rules."""

    power_system_name: str  # e.g., "修仙灵力体系"
    cultivation_levels: list[str]  # ordered list, e.g., ["炼气", "筑基", "金丹"]
    level_abilities: dict[str, list[str]]  # level → abilities
    world_constraints: list[str]  # things that can't happen
    geography: dict[str, str] = field(default_factory=dict)  # location → characteristics
    factions: dict[str, str] = field(default_factory=dict)  # faction name → description


@dataclass
class TimelineEvent:
    """Canonical event in story timeline."""

    id: str
    chapter_range: tuple[int, int]  # (start, end) chapter
    volume_num: int
    description: str
    involved_characters: list[str]
    consequences: list[str]


@dataclass
class ForeshadowingEntry:
    """Tracks setup-payoff pairs across volumes."""

    setup_id: str
    setup_chapter: int
    setup_volume: int
    setup_description: str
    payoff_chapter: int
    payoff_volume: int
    payoff_description: str
    is_active: bool = True  # False once payoff is delivered


@dataclass
class ProductionBible:
    """Complete production bible - the single source of truth for all story facts.

    This is built ONCE at the start of the pipeline, before parallel volume generation.
    All parallel agents reference this bible, never their own version of facts.
    """

    characters: dict[str, CharacterProfile] = field(default_factory=dict)  # name → profile
    world_rules: Optional[WorldRules] = None
    timeline: list[TimelineEvent] = field(default_factory=list)
    foreshadowing_registry: dict[str, ForeshadowingEntry] = field(default_factory=dict)  # setup_id → entry
    canonical_relationships: dict[str, list[str]] = field(default_factory=dict)  # character → list of related characters
    volume_boundaries: dict[int, dict] = field(default_factory=dict)  # volume_num → {opening_state, closing_state}

    def get_character(self, name: str) -> Optional[CharacterProfile]:
        """Get a character profile by name."""
        return self.characters.get(name)

    def get_volume_boundary(self, volume_num: int) -> dict:
        """Get opening/closing state for a volume."""
        return self.volume_boundaries.get(volume_num, {})

    def get_foreshadowing_for_chapter(self, chapter: int) -> list[ForeshadowingEntry]:
        """Get all active foreshadowing entries covering a chapter."""
        return [
            f for f in self.foreshadowing_registry.values()
            if f.setup_chapter <= chapter <= f.payoff_chapter and f.is_active
        ]


@dataclass
class BibleSection:
    """A subset of the bible relevant to a specific volume.

    Each parallel volume generation task receives only its relevant section,
    preventing context overflow and ensuring focus.
    """

    volume_num: int
    relevant_characters: dict[str, CharacterProfile]  # characters appearing in this volume (name → profile)
    world_rules_summary: str  # abbreviated world rules
    timeline_up_to_this_point: list[TimelineEvent]  # events up to volume start
    open_foreshadowing: list[ForeshadowingEntry]  # setups that should be paid off in this volume
    relationship_states_at_start: dict[str, dict[str, str]]  # {character: {related_char: state}}
    canonical_facts_this_volume: list[str]  # hard facts that must not be contradicted
