"""Enums and constants for FILM_DRAMA mode."""

from enum import Enum


class MessageType(Enum):
    """Handoff message types for agent communication."""
    # Director -> Character: Scene assignment
    HANDOFF = "handoff"
    # Character -> Director: Scene completion
    RESPONSE = "response"
    # Director -> Character: Modification request
    REVISE = "revise"
    # Character -> Character: Direct interaction (simulated by Director)
    DIALOGUE = "dialogue"
    # Director -> All: Scene setup
    SETUP = "setup"
    # Director -> All: Scene wrap
    WRAP = "wrap"
    # Any -> Any: Heartbeat/ping
    PING = "ping"
    # Director -> Non-main: Simulate NPC response
    NPC_SIMULATE = "npc_simulate"
    # Character -> Director: Request clarification
    CLARIFY = "clarify"


class AgentRole(Enum):
    """Agent roles in FILM_DRAMA mode."""
    DIRECTOR = "director"
    MAIN_CHARACTER = "main_character"  # 韩林、柳如烟、叶尘等
    SUPPORTING_CHARACTER = "supporting_character"  # 太虚宗主等
    NPC_SIMULATED = "npc_simulated"  # Director模拟的非主要角色


class SceneStatus(Enum):
    """Scene processing status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BeatType(Enum):
    """Plot beat types for scene structuring."""
    OPENING = "opening"  # 开场
    DEVELOPMENT = "development"  # 发展
    CONFLICT = "conflict"  # 冲突
    CLIMAX = "climax"  # 高潮
    RESOLUTION = "resolution"  # 解决
    TRANSITION = "transition"  # 过渡
