"""FILM_DRAMA mode for multi-agent novel generation.

Architecture:
- DirectorAgent: Orchestrates scene generation
- CharacterAgents: Each main character gets its own agent
- MessageQueue: Async communication between agents

Usage:
    from agents.film_drama import DirectorAgent

    director = DirectorAgent(llm_client=llm)
    script = director.plan_scene(
        chapter_number=1,
        scene_outline="韩林与柳如烟在演武场相遇",
        characters={"韩林": {...}, "柳如烟": {...}},
        location="太虚宗演武场",
        time_of_day="morning"
    )
    result = await director.execute_scene(script)
    output = director.assemble_scene_output(script)
"""

from .enums import MessageType, AgentRole, SceneStatus, BeatType
from .data_structures import (
    HandoffMessage,
    PlotBeat,
    Scene,
    CharacterBible,
    DirectorScript,
)
from .message_queue import InMemoryMessageQueue, AgentMessageQueue
from .director_agent import DirectorAgent, DirectorConfig
from .character_agent import CharacterAgent
from .character_memory import CharacterMemoryQueue, CharacterMemory, EmotionalState
from .middleware import (
    MiddlewareChain,
    CharacterMiddleware,
    MiddlewareResult,
    EmotionalStateMiddleware,
    SubagentLimitMiddleware,
    ClarificationMiddleware,
    MemoryQueueMiddleware,
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

__all__ = [
    # Enums
    "MessageType",
    "AgentRole",
    "SceneStatus",
    "BeatType",
    # Data structures
    "HandoffMessage",
    "PlotBeat",
    "Scene",
    "CharacterBible",
    "DirectorScript",
    # Message queue
    "InMemoryMessageQueue",
    "AgentMessageQueue",
    # Agents
    "DirectorAgent",
    "DirectorConfig",
    "CharacterAgent",
    # Memory
    "CharacterMemoryQueue",
    "CharacterMemory",
    "EmotionalState",
    # Middleware
    "MiddlewareChain",
    "CharacterMiddleware",
    "MiddlewareResult",
    "EmotionalStateMiddleware",
    "SubagentLimitMiddleware",
    "ClarificationMiddleware",
    "MemoryQueueMiddleware",
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
]
