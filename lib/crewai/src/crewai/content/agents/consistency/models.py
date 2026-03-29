# -*- encoding: utf-8 -*-
"""Data models for video generation consistency management.

This module provides data classes for:
- CharacterProfile: Unified character appearance descriptions
- SceneProfile: Unified scene/environment descriptions
- Shot: Individual camera shots
- Storyboard: Complete shot sequence planning

Usage:
    from consistency.models import CharacterProfile, SceneProfile, Storyboard

    character = CharacterProfile(
        name="林渊",
        age_appearance="16-17岁少年",
        face="清瘦、剑眉星目",
        clothing="灰色布袍"
    )

    scene = SceneProfile(
        name="青云宗",
        architecture="白玉石阶、汉白玉牌坊",
        color_palette="青灰色主调"
    )

    storyboard = Storyboard(chapter=1, total_duration=18)
    storyboard.add_shot(Shot(
        time_range="0-3s",
        description="航拍俯视青云宗全貌"
    ))
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class CharacterProfile:
    """Character appearance profile for consistent video generation.

    Attributes:
        character_id: Unique identifier (usually the character name)
        name: Character name in Chinese
        age_appearance: Age and visual appearance description
        face: Facial features description
        hair: Hairstyle description
        clothing: Clothing description (including sect/role specific)
        build: Body type description
        accessories: Any accessories (jewelry, weapons, etc.)
        expression_range: Map of emotional states to face expressions
        physical_traits: Special physical traits (scars, marks, etc.)
        negative: Things to avoid in generation
        metadata: Additional metadata
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    character_id: str
    name: str
    age_appearance: str = ""
    face: str = ""
    hair: str = ""
    clothing: str = ""
    build: str = ""
    accessories: str = ""
    expression_range: Dict[str, str] = field(default_factory=dict)
    physical_traits: str = ""
    negative: str = "不要：女性化、肥胖、现代服装、高科技元素"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_prompt_segment(self, emotion: Optional[str] = None) -> str:
        """Convert character profile to a prompt segment for video generation.

        Args:
            emotion: Specific emotion to use (e.g., "angry", "sad"). If None,
                    uses default expression.

        Returns:
            String suitable for injection into video prompt.
        """
        parts = [f"character: {self.name}"]

        if self.age_appearance:
            parts.append(f"appearance: {self.age_appearance}")
        if self.face:
            parts.append(f"face: {self.face}")
        if self.hair:
            parts.append(f"hairstyle: {self.hair}")
        if self.clothing:
            parts.append(f"clothing: {self.clothing}")
        if self.build:
            parts.append(f"build: {self.build}")
        if self.accessories:
            parts.append(f"accessories: {self.accessories}")

        if emotion and emotion in self.expression_range:
            parts.append(f"expression: {self.expression_range[emotion]}")
        elif "default" in self.expression_range:
            parts.append(f"expression: {self.expression_range['default']}")

        parts.append(f"negative: {self.negative}")

        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "character_id": self.character_id,
            "name": self.name,
            "age_appearance": self.age_appearance,
            "face": self.face,
            "hair": self.hair,
            "clothing": self.clothing,
            "build": self.build,
            "accessories": self.accessories,
            "expression_range": self.expression_range,
            "physical_traits": self.physical_traits,
            "negative": self.negative,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CharacterProfile":
        """Create from dictionary."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at)
        if updated_at:
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            character_id=data["character_id"],
            name=data["name"],
            age_appearance=data.get("age_appearance", ""),
            face=data.get("face", ""),
            hair=data.get("hair", ""),
            clothing=data.get("clothing", ""),
            build=data.get("build", ""),
            accessories=data.get("accessories", ""),
            expression_range=data.get("expression_range", {}),
            physical_traits=data.get("physical_traits", ""),
            negative=data.get("negative", ""),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )


@dataclass
class SceneProfile:
    """Scene/environment profile for consistent video generation.

    Attributes:
        scene_id: Unique identifier (usually the location name)
        name: Scene name in Chinese
        location_type: Type of location (e.g., "仙门宗门", "山洞", "城镇")
        architecture: Architectural style description
        interior: Interior details if applicable
        exterior: Exterior details
        color_palette: Main colors and palette
        atmosphere: General mood/atmosphere description
        lighting: Lighting conditions (time of day, type)
        key_props: List of important props/objects in scene
        flora: Plants and vegetation
        fauna: Animals or creatures (optional)
        negative: Things to avoid in generation
        metadata: Additional metadata
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    scene_id: str
    name: str
    location_type: str = ""
    architecture: str = ""
    interior: str = ""
    exterior: str = ""
    color_palette: str = ""
    atmosphere: str = ""
    lighting: Dict[str, str] = field(default_factory=dict)
    key_props: List[str] = field(default_factory=list)
    flora: str = ""
    fauna: str = ""
    negative: str = "不要：现代建筑、塑料、金属质感、未来元素"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_prompt_segment(self, time_of_day: Optional[str] = None) -> str:
        """Convert scene profile to a prompt segment for video generation.

        Args:
            time_of_day: Specific time (e.g., "morning", "night"). If None,
                        uses default or first available.

        Returns:
            String suitable for injection into video prompt.
        """
        parts = [f"location: {self.name}"]

        if self.location_type:
            parts.append(f"type: {self.location_type}")
        if self.architecture:
            parts.append(f"architecture: {self.architecture}")
        if self.exterior:
            parts.append(f"exterior: {self.exterior}")
        if self.interior:
            parts.append(f"interior: {self.interior}")
        if self.color_palette:
            parts.append(f"colors: {self.color_palette}")
        if self.atmosphere:
            parts.append(f"atmosphere: {self.atmosphere}")

        # Time-specific lighting
        if time_of_day and time_of_day in self.lighting:
            parts.append(f"lighting: {self.lighting[time_of_day]}")
        elif self.lighting:
            default_time = list(self.lighting.keys())[0] if self.lighting else None
            if default_time:
                parts.append(f"lighting: {self.lighting[default_time]}")

        if self.key_props:
            props_str = ", ".join(self.key_props[:5])  # Limit to 5 props
            parts.append(f"props: {props_str}")

        parts.append(f"negative: {self.negative}")

        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "location_type": self.location_type,
            "architecture": self.architecture,
            "interior": self.interior,
            "exterior": self.exterior,
            "color_palette": self.color_palette,
            "atmosphere": self.atmosphere,
            "lighting": self.lighting,
            "key_props": self.key_props,
            "flora": self.flora,
            "fauna": self.fauna,
            "negative": self.negative,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SceneProfile":
        """Create from dictionary."""
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at)
        if updated_at:
            updated_at = datetime.fromisoformat(updated_at)

        return cls(
            scene_id=data["scene_id"],
            name=data["name"],
            location_type=data.get("location_type", ""),
            architecture=data.get("architecture", ""),
            interior=data.get("interior", ""),
            exterior=data.get("exterior", ""),
            color_palette=data.get("color_palette", ""),
            atmosphere=data.get("atmosphere", ""),
            lighting=data.get("lighting", {}),
            key_props=data.get("key_props", []),
            flora=data.get("flora", ""),
            fauna=data.get("fauna", ""),
            negative=data.get("negative", ""),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )


# Shot type constants
SHOT_TYPES = {
    "establishing": "建立镜头",
    "wide": "全景",
    "full": "全身镜头",
    "medium": "中景",
    "medium_close": "中近景",
    "close_up": "特写",
    "extreme_close_up": "大特写",
    "over_shoulder": "过肩镜头",
    "pov": "主观镜头",
    "two_shot": "双人镜头",
    "insert": "插入镜头",
}

# Camera movement constants
CAMERA_MOVEMENTS = {
    "static": "固定镜头",
    "dolly_in": "推进",
    "dolly_out": "拉远",
    "push_in": "推进",
    "pull_out": "拉远",
    "pan_left": "左摇",
    "pan_right": "右摇",
    "tilt_up": "上摇",
    "tilt_down": "下摇",
    "tracking": "跟拍",
    "crane_up": "升镜头",
    "crane_down": "降镜头",
    "drone_shot": "航拍",
    "handheld": "手持晃动",
    "slow_motion": "慢动作",
    "fast_motion": "快动作",
    "rack_focus": "焦点切换",
}


@dataclass
class Shot:
    """Individual camera shot in a storyboard.

    Attributes:
        shot_number: Sequential shot number
        time_range: Time range string (e.g., "0-3s", "3-8s")
        shot_type: Type of shot (from SHOT_TYPES)
        description: Detailed description of what's shown
        camera: Camera movement (from CAMERA_MOVEMENTS)
        scene_ref: Reference to scene profile ID
        character_refs: List of character profile IDs appearing
        emotion: Target emotion/expression
        duration_seconds: Calculated duration
        vfx: Visual effects description
        transition: Transition to next shot (e.g., "cut", "dissolve")
        notes: Additional notes for generation
    """
    shot_number: int
    time_range: str
    shot_type: str = "medium"
    description: str = ""
    camera: str = "static"
    scene_ref: Optional[str] = None
    character_refs: List[str] = field(default_factory=list)
    emotion: Optional[str] = None
    duration_seconds: int = 0
    vfx: str = ""
    transition: str = "cut"
    notes: str = ""

    def __post_init__(self):
        """Calculate duration from time_range."""
        if self.duration_seconds == 0 and self.time_range:
            try:
                start, end = self.time_range.replace("s", "").split("-")
                self.duration_seconds = int(end) - int(start)
            except (ValueError, AttributeError):
                self.duration_seconds = 5  # default 5 seconds

    def to_prompt_segment(
        self,
        scene_profile: Optional[SceneProfile] = None,
        character_profiles: Optional[List[CharacterProfile]] = None,
    ) -> str:
        """Convert shot to a prompt segment.

        Args:
            scene_profile: Optional scene profile for scene details
            character_profiles: Optional list of character profiles

        Returns:
            String suitable for video generation prompt.
        """
        parts = []

        # Shot type and camera
        shot_type_cn = SHOT_TYPES.get(self.shot_type, self.shot_type)
        camera_cn = CAMERA_MOVEMENTS.get(self.camera, self.camera)
        parts.append(f"Shot {self.shot_number}: {shot_type_cn}, camera: {camera_cn}")

        # Description
        if self.description:
            parts.append(f"content: {self.description}")

        # Scene reference
        if scene_profile:
            parts.append(f"scene: {scene_profile.to_prompt_segment()}")

        # Character references
        if character_profiles:
            char_prompts = [cp.to_prompt_segment(self.emotion) for cp in character_profiles]
            parts.append(f"characters: {'; '.join(char_prompts)}")

        # VFX
        if self.vfx:
            parts.append(f"effects: {self.vfx}")

        # Transition
        if self.transition and self.transition != "cut":
            parts.append(f"transition: {self.transition}")

        return ". ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "shot_number": self.shot_number,
            "time_range": self.time_range,
            "shot_type": self.shot_type,
            "description": self.description,
            "camera": self.camera,
            "scene_ref": self.scene_ref,
            "character_refs": self.character_refs,
            "emotion": self.emotion,
            "duration_seconds": self.duration_seconds,
            "vfx": self.vfx,
            "transition": self.transition,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Shot":
        """Create from dictionary."""
        return cls(
            shot_number=data["shot_number"],
            time_range=data["time_range"],
            shot_type=data.get("shot_type", "medium"),
            description=data.get("description", ""),
            camera=data.get("camera", "static"),
            scene_ref=data.get("scene_ref"),
            character_refs=data.get("character_refs", []),
            emotion=data.get("emotion"),
            duration_seconds=data.get("duration_seconds", 0),
            vfx=data.get("vfx", ""),
            transition=data.get("transition", "cut"),
            notes=data.get("notes", ""),
        )


@dataclass
class Storyboard:
    """Complete storyboard with shot sequence.

    Attributes:
        chapter: Chapter number this storyboard is for
        total_duration: Total duration in seconds
        shots: List of Shot objects
        title: Optional title
        description: Overall description
        metadata: Additional metadata
        created_at: Creation timestamp
    """
    chapter: int
    total_duration: int = 0
    shots: List[Shot] = field(default_factory=list)
    title: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.total_duration == 0 and self.shots:
            self._recalculate_duration()

    def _recalculate_duration(self):
        """Recalculate total duration from shots."""
        if self.shots:
            try:
                last_shot = self.shots[-1]
                end = last_shot.time_range.split("-")[-1].replace("s", "")
                self.total_duration = int(end)
            except (ValueError, AttributeError):
                self.total_duration = sum(s.duration_seconds for s in self.shots)

    def add_shot(self, shot: Shot) -> None:
        """Add a shot and recalculate duration."""
        self.shots.append(shot)
        self._recalculate_duration()

    def get_shot(self, shot_number: int) -> Optional[Shot]:
        """Get shot by number."""
        for shot in self.shots:
            if shot.shot_number == shot_number:
                return shot
        return None

    def get_scene_shots(self, scene_ref: str) -> List[Shot]:
        """Get all shots for a specific scene."""
        return [s for s in self.shots if s.scene_ref == scene_ref]

    def get_character_shots(self, character_id: str) -> List[Shot]:
        """Get all shots featuring a specific character."""
        return [s for s in self.shots if character_id in s.character_refs]

    def to_full_prompt(
        self,
        scene_profiles: Optional[Dict[str, SceneProfile]] = None,
        character_profiles: Optional[Dict[str, CharacterProfile]] = None,
    ) -> str:
        """Generate full prompt from storyboard.

        Args:
            scene_profiles: Dict of scene_id -> SceneProfile
            character_profiles: Dict of character_id -> CharacterProfile

        Returns:
            Complete prompt for video generation.
        """
        prompt_parts = []

        # Title
        if self.title:
            prompt_parts.append(f"Story: {self.title}")

        # Description
        if self.description:
            prompt_parts.append(f"Summary: {self.description}")

        # Shots
        for shot in self.shots:
            scene = scene_profiles.get(shot.scene_ref) if scene_profiles else None
            chars = []
            if shot.character_refs and character_profiles:
                chars = [character_profiles[cid] for cid in shot.character_refs if cid in character_profiles]

            prompt_parts.append(f"[{shot.time_range}] " + shot.to_prompt_segment(scene, chars))

        # Total duration
        prompt_parts.append(f"Total duration: {self.total_duration}s")

        return " | ".join(prompt_parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chapter": self.chapter,
            "total_duration": self.total_duration,
            "title": self.title,
            "description": self.description,
            "shots": [s.to_dict() for s in self.shots],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Storyboard":
        """Create from dictionary."""
        shots = [Shot.from_dict(s) for s in data.get("shots", [])]
        created_at = data.get("created_at")
        if created_at:
            created_at = datetime.fromisoformat(created_at)

        return cls(
            chapter=data["chapter"],
            total_duration=data.get("total_duration", 0),
            shots=shots,
            title=data.get("title", ""),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            created_at=created_at,
        )
