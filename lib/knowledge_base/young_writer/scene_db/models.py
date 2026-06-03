"""Data models for Scene persistence."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class SceneStatus(str, Enum):
    """Scene processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BeatType(str, Enum):
    """Plot beat types in narrative structure."""

    OPENING = "OPENING"
    DEVELOPMENT = "DEVELOPMENT"
    CONFLICT = "CONFLICT"
    CLIMAX = "CLIMAX"
    RESOLUTION = "RESOLUTION"
    TRANSITION = "TRANSITION"


class ConsumptionType(str, Enum):
    """Types of downstream content consumption."""

    NOVEL = "novel"
    PODCAST = "podcast"
    VIDEO = "video"
    MUSIC = "music"


@dataclass
class Scene:
    """Core scene entity representing a narrative scene."""

    id: UUID
    chapter: int
    title: Optional[str] = None
    background: Optional[str] = None
    location: Optional[str] = None
    time_of_day: str = "morning"
    emotional_arc: Optional[Dict[str, str]] = None
    narration: Optional[str] = None
    status: SceneStatus = SceneStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": str(self.id),
            "chapter": self.chapter,
            "title": self.title,
            "background": self.background,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "emotional_arc": self.emotional_arc,
            "narration": self.narration,
            "status": self.status.value if isinstance(self.status, SceneStatus) else self.status,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "updated_at": self.updated_at.isoformat() if isinstance(self.updated_at, datetime) else self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        """Create Scene from dictionary."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()

        status = data.get("status", "pending")
        if isinstance(status, str):
            status = SceneStatus(status)

        emotional_arc = data.get("emotional_arc")
        if isinstance(emotional_arc, str):
            import json
            emotional_arc = json.loads(emotional_arc)

        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            chapter=data["chapter"],
            title=data.get("title"),
            background=data.get("background"),
            location=data.get("location"),
            time_of_day=data.get("time_of_day", "morning"),
            emotional_arc=emotional_arc,
            narration=data.get("narration"),
            status=status,
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class PlotBeat:
    """Plot beat entity representing a narrative beat within a scene."""

    id: UUID
    scene_id: UUID
    beat_type: BeatType
    description: Optional[str] = None
    character_interactions: Optional[List[Dict[str, Any]]] = None
    scene_description: Optional[str] = None
    narration: Optional[str] = None
    sequence: Optional[int] = None
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        import json

        return {
            "id": str(self.id),
            "scene_id": str(self.scene_id),
            "beat_type": self.beat_type.value if isinstance(self.beat_type, BeatType) else self.beat_type,
            "description": self.description,
            "character_interactions": json.dumps(self.character_interactions) if self.character_interactions else None,
            "scene_description": self.scene_description,
            "narration": self.narration,
            "sequence": self.sequence,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotBeat":
        """Create PlotBeat from dictionary."""
        import json

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        beat_type = data.get("beat_type", "OPENING")
        if isinstance(beat_type, str):
            beat_type = BeatType(beat_type)

        character_interactions = data.get("character_interactions")
        if isinstance(character_interactions, str):
            character_interactions = json.loads(character_interactions)

        embedding = data.get("embedding")
        if embedding is not None and not isinstance(embedding, list):
            # Handle numpy array or other formats from psycopg2
            embedding = list(embedding) if embedding else None

        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            scene_id=UUID(data["scene_id"]) if isinstance(data["scene_id"], str) else data["scene_id"],
            beat_type=beat_type,
            description=data.get("description"),
            character_interactions=character_interactions,
            scene_description=data.get("scene_description"),
            narration=data.get("narration"),
            sequence=data.get("sequence"),
            embedding=embedding,
            created_at=created_at,
        )


@dataclass
class CharacterState:
    """Character state change within a plot beat."""

    id: UUID
    beat_id: UUID
    character_name: str
    emotional_state: Optional[str] = None
    dialogue_context: Optional[str] = None
    physical_action: Optional[str] = None
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": str(self.id),
            "beat_id": str(self.beat_id),
            "character_name": self.character_name,
            "emotional_state": self.emotional_state,
            "dialogue_context": self.dialogue_context,
            "physical_action": self.physical_action,
            "embedding": self.embedding,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterState":
        """Create CharacterState from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        embedding = data.get("embedding")
        if embedding is not None and not isinstance(embedding, list):
            embedding = list(embedding) if embedding else None

        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            beat_id=UUID(data["beat_id"]) if isinstance(data["beat_id"], str) else data["beat_id"],
            character_name=data["character_name"],
            emotional_state=data.get("emotional_state"),
            dialogue_context=data.get("dialogue_context"),
            physical_action=data.get("physical_action"),
            embedding=embedding,
            created_at=created_at,
        )


@dataclass
class ConsumptionRecord:
    """Record of downstream content consumption."""

    id: UUID
    scene_id: UUID
    consumer_type: ConsumptionType
    output_content: Optional[str] = None
    status: str = "pending"
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        import json

        return {
            "id": str(self.id),
            "scene_id": str(self.scene_id),
            "consumer_type": self.consumer_type.value if isinstance(self.consumer_type, ConsumptionType) else self.consumer_type,
            "output_content": self.output_content,
            "status": self.status,
            "metadata": json.dumps(self.metadata) if self.metadata else None,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsumptionRecord":
        """Create ConsumptionRecord from dictionary."""
        import json

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        consumer_type = data.get("consumer_type", "novel")
        if isinstance(consumer_type, str):
            consumer_type = ConsumptionType(consumer_type)

        metadata = data.get("metadata")
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            scene_id=UUID(data["scene_id"]) if isinstance(data["scene_id"], str) else data["scene_id"],
            consumer_type=consumer_type,
            output_content=data.get("output_content"),
            status=data.get("status", "pending"),
            metadata=metadata,
            created_at=created_at,
        )
