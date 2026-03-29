"""FILM_DRAMA mode core data structures and enums.

This module provides the foundational data structures, enums, and personas
for the FILM_DRAMA multi-agent novel generation mode.

Usage:
    from crewai.content.agents.film_drama import (
        BeatType,
        Scene,
        DirectorScript,
        AgentPersona,
        get_persona,
    )
"""

from .enums import MessageType, AgentRole, SceneStatus, BeatType
from .data_structures import (
    CharacterInteraction,
    CharacterState,
    EmotionalArc,
    RawSceneData,
    HandoffMessage,
    PlotBeat,
    Scene,
    CharacterBible,
    DirectorScript,
)
from .personas import (
    AgentPersona,
    DIRECTOR_PERSONA,
    CHARACTER_PERSONA,
    ORCHESTRATOR_PERSONA,
    REVIEWER_PERSONA,
    NOVEL_CONSUMER_PERSONA,
    VIDEO_CONSUMER_PERSONA,
    PODCAST_CONSUMER_PERSONA,
    MUSIC_CONSUMER_PERSONA,
    PERSONAS_BY_ROLE,
    PERSONAS_BY_NAME,
    get_persona,
    get_persona_by_role,
    list_personas,
    render_system_prompt,
)
from .director_agent import DirectorAgent, DirectorConfig
from .character_agent import CharacterAgent
from .message_queue import InMemoryMessageQueue
from .middleware import MiddlewareChain

__all__ = [
    # Enums
    "MessageType",
    "AgentRole",
    "SceneStatus",
    "BeatType",
    # Data structures
    "CharacterInteraction",
    "CharacterState",
    "EmotionalArc",
    "RawSceneData",
    "HandoffMessage",
    "PlotBeat",
    "Scene",
    "CharacterBible",
    "DirectorScript",
    # Personas
    "AgentPersona",
    "DIRECTOR_PERSONA",
    "CHARACTER_PERSONA",
    "ORCHESTRATOR_PERSONA",
    "REVIEWER_PERSONA",
    "NOVEL_CONSUMER_PERSONA",
    "VIDEO_CONSUMER_PERSONA",
    "PODCAST_CONSUMER_PERSONA",
    "MUSIC_CONSUMER_PERSONA",
    "PERSONAS_BY_ROLE",
    "PERSONAS_BY_NAME",
    "get_persona",
    "get_persona_by_role",
    "list_personas",
    "render_system_prompt",
    # Agents
    "DirectorAgent",
    "DirectorConfig",
    "CharacterAgent",
    # Message queue and middleware
    "InMemoryMessageQueue",
    "MiddlewareChain",
]
