"""Sound Designer Agent for audio and soundscape generation.

This agent specializes in creating audio content for novels including:
- Scene soundscapes
- Sound effects
- Background music
- Audiobook narration

Usage:
    from crewai.comfy.agents.sound_designer import SoundDesignerAgent

    designer = SoundDesignerAgent()
    result = designer.generate_soundscape(
        scene_type="battle",
        mood="epic",
        duration=60,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SoundDesignerConfig:
    """Configuration for SoundDesignerAgent."""

    default_duration: int = 30
    default_bgm_duration: int = 120
    default_sfx_duration: int = 5
    audio_model: str = "audio_model.safetensors"


@dataclass
class AudioRequirements:
    """Audio requirements for a scene."""

    audio_type: str  # "soundscape", "bgm", "sfx", "narration"
    mood: str
    duration: int
    key_elements: list[str]
    scene_context: str = ""


class SoundDesignerAgent:
    """Agent responsible for generating audio content.

    This agent:
    1. Analyzes scene requirements for audio
    2. Generates appropriate audio content (BGM, SFX, soundscape)
    3. Can mix multiple audio sources
    4. Creates audiobook narration
    """

    def __init__(
        self,
        config: SoundDesignerConfig | None = None,
        executor: Any | None = None,
    ):
        """Initialize the SoundDesignerAgent.

        Args:
            config: Sound designer configuration
            executor: Optional ComfyWorkflowExecutor instance
        """
        self.config = config or SoundDesignerConfig()
        self.executor = executor
        self._initialized = False

    def _ensure_executor(self) -> Any:
        """Lazy-load the executor."""
        if self.executor is None:
            from crewai.comfy import ComfyWorkflowExecutor
            self.executor = ComfyWorkflowExecutor()
        return self.executor

    def analyze_audio_requirements(
        self,
        scene_type: str,
        mood: str,
        context: str = "",
    ) -> AudioRequirements:
        """Analyze scene to determine audio requirements.

        Args:
            scene_type: Type of scene (battle, dialogue, romance, etc.)
            mood: Emotional mood
            context: Additional context

        Returns:
            AudioRequirements with extracted audio data
        """
        audio_configs = {
            "battle": {
                "audio_type": "soundscape",
                "mood": "epic, intense",
                "duration": 60,
                "key_elements": ["drums", "orchestra", "sword clash", "energy"],
            },
            "dialogue": {
                "audio_type": "soundscape",
                "mood": "subtle, ambient",
                "duration": 30,
                "key_elements": ["soft wind", "distant murmurs", "footsteps"],
            },
            "romance": {
                "audio_type": "bgm",
                "mood": "tender, melodic",
                "duration": 120,
                "key_elements": ["piano", "strings", "gentle"],
            },
            "tense": {
                "audio_type": "soundscape",
                "mood": "dark, ominous",
                "duration": 45,
                "key_elements": ["low drone", "strings", "wind"],
            },
            "comedy": {
                "audio_type": "bgm",
                "mood": "light, playful",
                "duration": 60,
                "key_elements": ["woodwinds", "light percussion", "bouncy"],
            },
            "sad": {
                "audio_type": "bgm",
                "mood": "melancholic, slow",
                "duration": 120,
                "key_elements": ["violin", "piano", "soft strings"],
            },
            "epic": {
                "audio_type": "soundscape",
                "mood": "grand, powerful",
                "duration": 180,
                "key_elements": ["orchestra", "choir", "drums", "fanfare"],
            },
            "mystery": {
                "audio_type": "soundscape",
                "mood": "dark, suspenseful",
                "duration": 60,
                "key_elements": ["low strings", "mysterious tones", "distant sounds"],
            },
        }

        config = audio_configs.get(scene_type, audio_configs["dialogue"])

        return AudioRequirements(
            audio_type=config["audio_type"],
            mood=mood or config["mood"],
            duration=config["duration"],
            key_elements=config["key_elements"],
            scene_context=context,
        )

    def generate_soundscape(
        self,
        scene_type: str,
        mood: str = "",
        duration: int | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        """Generate a soundscape for a scene.

        Args:
            scene_type: Type of scene
            mood: Emotional mood
            duration: Duration in seconds
            context: Additional context

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        requirements = self.analyze_audio_requirements(scene_type, mood, context)

        # Build prompt from key elements
        elements_str = ", ".join(requirements.key_elements)
        prompt = f"sound effects: {elements_str}, {requirements.mood}"

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.audio.build_sound_effect(
            description=prompt,
            duration=duration or requirements.duration,
        )

        result = executor.execute(workflow)

        return {
            "audio_type": "soundscape",
            "scene_type": scene_type,
            "mood": requirements.mood,
            "prompt": prompt,
            "duration": duration or requirements.duration,
            "result": result,
        }

    def generate_background_music(
        self,
        mood: str,
        duration: int | None = None,
        style: str = "orchestral",
    ) -> dict[str, Any]:
        """Generate background music.

        Args:
            mood: Music mood
            duration: Duration in seconds
            style: Music style (orchestral, electronic, ambient, etc.)

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        duration = duration or self.config.default_bgm_duration

        # Build prompt
        prompt = f"background music, {mood} mood, {style} style"

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.audio.build_background_music(
            mood=prompt,
            duration=duration,
        )

        result = executor.execute(workflow)

        return {
            "audio_type": "bgm",
            "mood": mood,
            "style": style,
            "prompt": prompt,
            "duration": duration,
            "result": result,
        }

    def generate_sound_effect(
        self,
        description: str,
        duration: int | None = None,
    ) -> dict[str, Any]:
        """Generate a specific sound effect.

        Args:
            description: Description of the sound effect
            duration: Duration in seconds

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        duration = duration or self.config.default_sfx_duration

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.audio.build_sound_effect(
            description=description,
            duration=duration,
        )

        result = executor.execute(workflow)

        return {
            "audio_type": "sfx",
            "description": description,
            "duration": duration,
            "result": result,
        }

    def generate_audiobook_narration(
        self,
        text: str,
        voice_model: str = "default_voice.safetensors",
        include_narration_markers: bool = True,
    ) -> dict[str, Any]:
        """Generate audiobook narration from text.

        Args:
            text: Text to narrate
            voice_model: Voice model to use
            include_narration_markers: Whether to include narration markers

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        # Estimate duration based on text length (roughly 150 words per minute)
        word_count = len(text.split())
        estimated_duration = max(30, (word_count / 150) * 60)

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.audio.build_audiobook(
            text=text,
            voice_model=voice_model,
            duration=int(estimated_duration),
            narrator=include_narration_markers,
        )

        result = executor.execute(workflow)

        return {
            "audio_type": "narration",
            "word_count": word_count,
            "estimated_duration": estimated_duration,
            "voice_model": voice_model,
            "result": result,
        }

    def mix_audio(
        self,
        audio_sources: list[str],
        mix_type: str = "overlay",
    ) -> dict[str, Any]:
        """Mix multiple audio sources.

        Args:
            audio_sources: List of audio file paths
            mix_type: Type of mixing (overlay, sequence, crossfade)

        Returns:
            Dict with mixed audio result
        """
        from crewai.comfy import WorkflowBuilder

        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.audio.build_audio_mix(
            audio_sources=audio_sources,
            mix_type=mix_type,
        )

        result = executor.execute(workflow)

        return {
            "audio_type": "mix",
            "sources": audio_sources,
            "mix_type": mix_type,
            "result": result,
        }
