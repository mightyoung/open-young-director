"""Production Bible system for novel generation.

This module provides the Production Bible - a single source of truth for all story facts
when generating multiple volumes in parallel. The bible is built once before parallel
generation and ensures consistency across all volumes.

Exports:
    ProductionBible: Complete canonical bible containing all story facts
    ProductionBibleBuilder: Builds ProductionBible from world_data and plot_data
    BibleSection: Subset of bible relevant to a specific volume
"""

from crewai.content.novel.production_bible.bible_types import (
    BibleSection,
    CharacterProfile,
    ForeshadowingEntry,
    ProductionBible,
    TimelineEvent,
    WorldRules,
)
from crewai.content.novel.production_bible.bible_builder import ProductionBibleBuilder
from crewai.content.novel.production_bible.section_builder import BibleSectionBuilder
from crewai.content.novel.production_bible.outline_verifier import VolumeOutlineVerifier, VerificationIssue, VerificationResult

__all__ = [
    "ProductionBible",
    "ProductionBibleBuilder",
    "BibleSection",
    "CharacterProfile",
    "WorldRules",
    "TimelineEvent",
    "ForeshadowingEntry",
    "BibleSectionBuilder",
    "VolumeOutlineVerifier",
    "VerificationIssue",
    "VerificationResult",
]
