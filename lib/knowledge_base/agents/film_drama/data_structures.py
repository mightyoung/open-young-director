"""Core data structures for FILM_DRAMA mode."""

from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class CharacterInteraction:
    """Character interaction within a plot beat."""
    character: str
    action: str  # Action description
    inner_thought: str  # Inner thought
    dialogue: str = ""  # Dialogue content
    emotion_change: str = ""  # Emotion change


@dataclass
class CharacterState:
    """Character state snapshot at a point in time."""
    character_name: str
    emotional_state: str  # Current emotional state
    physical_state: str  # Physical state
    dialogue_context: str  # Dialogue context
    relationships_snapshot: Dict[str, str] = field(default_factory=dict)  # Relationships with other characters at this moment


@dataclass
class EmotionalArc:
    """Emotional arc of a scene."""
    start_state: str  # Starting emotional state
    peak_state: str  # Climax emotional state
    end_state: str  # Ending emotional state
    key_moments: List[str] = field(default_factory=list)  # Emotional turning points


@dataclass
class RawSceneData:
    """Complete raw data passed to downstream consumers."""
    scene_id: str
    chapter_info: dict  # Chapter basic info
    background: str  # Background story
    beats: List[dict]  # Detailed data for each beat
    character_states: Dict[str, List[CharacterState]] = field(default_factory=dict)  # Character state changes
    scene_descriptions: List[str] = field(default_factory=list)  # Scene description list
    narration_pieces: List[str] = field(default_factory=list)  # Narration pieces
    emotional_arc: EmotionalArc = None  # Emotional arc

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database persistence."""
        return {
            "scene_id": self.scene_id,
            "chapter_info": self.chapter_info,
            "background": self.background,
            "beats": self.beats,
            "character_states": {
                char: [cs.__dict__ for cs in states]
                for char, states in self.character_states.items()
            },
            "scene_descriptions": self.scene_descriptions,
            "narration_pieces": self.narration_pieces,
            "emotional_arc": self.emotional_arc.__dict__ if self.emotional_arc else None,
        }


@dataclass
class HandoffMessage:
    """Message passed between agents during handoff."""
    id: str
    msg_type: str
    sender: str
    recipient: str
    scene_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "msg_type": self.msg_type,
            "sender": self.sender,
            "recipient": self.recipient,
            "scene_id": self.scene_id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
        }


@dataclass
class PlotBeat:
    """A single beat in a scene's plot progression."""
    beat_id: str
    beat_type: str  # BeatType enum value: OPENING/DEVELOPMENT/CONFLICT/CLIMAX/RESOLUTION/TRANSITION
    description: str  # What happens in this beat
    # New fields
    character_interactions: List[CharacterInteraction] = field(default_factory=list)  # Character interactions
    scene_description: str = ""  # Scene specific description
    narration: str = ""  # Narration for this beat
    expected_chars: List[str] = field(default_factory=list)  # Characters expected to participate
    sequence: int = 0  # Order in scene
    handoff_sequence: List[str] = field(default_factory=list)  # Agent handoff order

    def should_participate(self, char_name: str) -> bool:
        """Check if character should participate in this beat."""
        return char_name in self.expected_chars

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database persistence."""
        return {
            "beat_id": self.beat_id,
            "beat_type": self.beat_type,
            "description": self.description,
            "character_interactions": [ci.__dict__ for ci in self.character_interactions],
            "scene_description": self.scene_description,
            "narration": self.narration,
            "expected_chars": self.expected_chars,
            "sequence": self.sequence,
            "handoff_sequence": self.handoff_sequence,
        }


@dataclass
class Scene:
    """A scene being filmed in the production."""
    scene_id: str
    chapter: int
    location: str
    # New fields
    title: str = ""  # Chapter title
    background: str = ""  # Chapter background/story outline
    time_of_day: str = "morning"  # "morning", "afternoon", "night"
    beats: List[PlotBeat] = field(default_factory=list)
    emotional_arc: EmotionalArc = None  # Emotional arc (new)
    status: str = "pending"  # SceneStatus enum value
    narration: str = ""  # Total narration
    assigned_chars: List[str] = field(default_factory=list)
    current_beat_index: int = 0
    outputs: Dict[str, str] = field(default_factory=dict)  # char_name -> output

    def get_current_beat(self) -> Optional[PlotBeat]:
        """Get the current beat being processed."""
        if 0 <= self.current_beat_index < len(self.beats):
            return self.beats[self.current_beat_index]
        return None

    def advance_beat(self) -> bool:
        """Advance to next beat. Returns False if no more beats."""
        if self.current_beat_index < len(self.beats) - 1:
            self.current_beat_index += 1
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database persistence."""
        return {
            "scene_id": self.scene_id,
            "chapter": self.chapter,
            "location": self.location,
            "title": self.title,
            "background": self.background,
            "time_of_day": self.time_of_day,
            "beats": [beat.to_dict() for beat in self.beats],
            "emotional_arc": self.emotional_arc.__dict__ if self.emotional_arc else None,
            "status": self.status,
            "narration": self.narration,
            "assigned_chars": self.assigned_chars,
            "current_beat_index": self.current_beat_index,
            "outputs": self.outputs,
        }


@dataclass
class CharacterBible:
    """Character profile and context for an agent."""
    name: str
    role: str  # AgentRole enum value
    identity: str
    realm: str  # Cultivation realm
    personality: str
    speaking_style: str
    backstory: str = ""
    objective_this_chapter: str = ""
    key_moments: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    visual_ref_path: Optional[str] = None
    current_state: Dict[str, Any] = field(default_factory=dict)

    def to_system_prompt(self, book_title: str = "太古魔帝传") -> str:
        """Generate system prompt for this character using structured XML-like format.

        Uses layered modular structure with Identity/Capabilities/Rules/Communication.
        """
        # Import here to avoid circular dependency at module level
        # Use importlib for dynamic import to work in kimi-cli subprocess context
        import importlib.util
        import sys
        from pathlib import Path

        # Find the prompts module by traversing from this file's location
        current_file = Path(__file__).resolve()
        prompts_path = current_file.parent.parent.parent / "llm" / "prompts.py"

        spec = importlib.util.spec_from_file_location("llm_prompts", prompts_path)
        prompts_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prompts_module)
        build_character_prompt = prompts_module.build_character_prompt

        return build_character_prompt(
            character_name=self.name,
            identity=self.identity,
            realm=self.realm,
            personality=self.personality,
            speaking_style=self.speaking_style,
            backstory=self.backstory,
            objective=self.objective_this_chapter,
            relationships=self.relationships,
            book_title=book_title,
        )


@dataclass
class DirectorScript:
    """The director's script for a scene."""
    scene: Scene
    cast: List[CharacterBible]
    non_main_char_requirements: Dict[str, str] = field(default_factory=dict)
    required_beats: List[str] = field(default_factory=list)
    tension_points: List[str] = field(default_factory=list)
    cliffhanger: str = ""
    # New: Complete raw data for downstream consumers
    raw_data: RawSceneData = None

    def get_char_bible(self, char_name: str) -> Optional[CharacterBible]:
        """Get character bible by name."""
        for cb in self.cast:
            if cb.name == char_name:
                return cb
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for database persistence."""
        return {
            "scene": self.scene.to_dict(),
            "cast": [cb.__dict__ for cb in self.cast],
            "non_main_char_requirements": self.non_main_char_requirements,
            "required_beats": self.required_beats,
            "tension_points": self.tension_points,
            "cliffhanger": self.cliffhanger,
            "raw_data": self.raw_data.to_dict() if self.raw_data else None,
        }

    def build_raw_data(self) -> RawSceneData:
        """Build RawSceneData from current state for downstream consumption."""
        scene_descriptions = []
        narration_pieces = []
        character_states: Dict[str, List[CharacterState]] = {}

        # Check for empty narration
        if not self.scene.narration:
            logger.warning(f"[DirectorScript] Empty narration for scene {self.scene.scene_id}")

        for beat in self.scene.beats:
            if beat.scene_description:
                scene_descriptions.append(beat.scene_description)
            if beat.narration:
                narration_pieces.append(beat.narration)
            for interaction in beat.character_interactions:
                if interaction.character not in character_states:
                    character_states[interaction.character] = []
                # Build CharacterState from CharacterInteraction
                char_state = CharacterState(
                    character_name=interaction.character,
                    emotional_state=interaction.emotion_change,
                    physical_state=interaction.action,
                    dialogue_context=interaction.dialogue,
                    relationships_snapshot={},
                )
                character_states[interaction.character].append(char_state)

        self.raw_data = RawSceneData(
            scene_id=self.scene.scene_id,
            chapter_info={
                "chapter": self.scene.chapter,
                "title": self.scene.title,
                "location": self.scene.location,
                "time_of_day": self.scene.time_of_day,
            },
            background=self.scene.background,
            beats=[beat.to_dict() for beat in self.scene.beats],
            character_states=character_states,
            scene_descriptions=scene_descriptions,
            narration_pieces=narration_pieces,
            emotional_arc=self.scene.emotional_arc,
        )
        return self.raw_data
