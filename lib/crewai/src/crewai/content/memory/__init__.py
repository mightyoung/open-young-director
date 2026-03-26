"""Entity memory system for content generation.

This module provides entity tracking, relationship management,
and continuity verification for multi-agent content generation systems.
"""

from crewai.content.memory.memory_types import (
    ConsistencyIssue,
    ConsistencySeverity,
    ContinuityIssue,
    Entity,
    EntityState,
    EntityType,
    Event,
    RelationType,
    Relationship,
)
from crewai.content.memory.entity_memory import EntityMemory
from crewai.content.memory.entity_extractor import EntityExtractor
from crewai.content.memory.continuity_tracker import ContinuityTracker

__all__ = [
    # Types
    "EntityType",
    "RelationType",
    "ConsistencySeverity",
    "Relationship",
    "Entity",
    "ConsistencyIssue",
    "Event",
    "ContinuityIssue",
    "EntityState",
    # Core classes
    "EntityMemory",
    "EntityExtractor",
    "ContinuityTracker",
]
