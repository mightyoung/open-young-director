"""Preset workflows for common novel scenes.

This module provides pre-configured workflows for typical novel scenes:
- Battle scenes: Epic combat with dramatic lighting
- Romance scenes: Tender moments with warm tones
- Dialogue scenes: Conversational with subtle backgrounds
- Suspense scenes: Dark and mysterious atmosphere
- Tragedy scenes: Somber with muted colors
- Comedy scenes: Light and colorful

Usage:
    from crewai.comfy.presets import ScenePreset, get_preset

    preset = get_preset("battle")
    workflow = preset.build_workflow(scene_description="韩林vs叶尘")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScenePreset:
    """A pre-configured scene preset."""

    name: str
    display_name: str
    description: str
    image_prompt_template: str
    image_negative: str
    audio_mood: str
    video_mood: str

    # Image settings
    image_width: int = 1024
    image_height: int = 1024
    image_steps: int = 25
    image_cfg: float = 8.0

    # Audio settings
    audio_duration: int = 60

    # Video settings
    video_frames: int = 24


# Battle Scene Preset - Epic combat
BATTLE_PRESET = ScenePreset(
    name="battle",
    display_name="Battle Scene",
    description="Epic combat with dramatic lighting and powerful atmosphere",
    image_prompt_template=(
        "Chinese fantasy battle scene, {description}, "
        "dramatic lighting, epic scale, cinematic composition, "
        "energy effects, motion blur, high detail, 8k quality"
    ),
    image_negative="blurry, low quality, deformed, bad anatomy, watermark",
    image_width=1024,
    image_height=1024,
    image_steps=30,
    image_cfg=8.5,
    audio_mood="epic, intense, powerful",
    audio_duration=90,
    video_mood="epic, action",
    video_frames=32,
)

# Romance Scene Preset - Tender moments
ROMANCE_PRESET = ScenePreset(
    name="romance",
    display_name="Romance Scene",
    description="Tender romantic moment with warm tones and soft lighting",
    image_prompt_template=(
        "Chinese fantasy romance scene, {description}, "
        "warm lighting, soft focus, tender atmosphere, "
        "flower petals, gentle breeze, dreamy quality"
    ),
    image_negative="dark, gloomy, violent, low quality, deformed",
    image_width=1024,
    image_height=1024,
    image_steps=25,
    image_cfg=7.5,
    audio_mood="tender, melodic, romantic",
    audio_duration=120,
    video_mood="romantic, gentle",
    video_frames=24,
)

# Dialogue Scene Preset - Conversational
DIALOGUE_PRESET = ScenePreset(
    name="dialogue",
    display_name="Dialogue Scene",
    description="Character conversation with subtle background",
    image_prompt_template=(
        "Chinese fantasy dialogue scene, {description}, "
        "two characters talking, natural lighting, "
        "subtle background, cinematic framing, character focus"
    ),
    image_negative="crowded, chaotic, low quality, deformed",
    image_width=1024,
    image_height=768,
    image_steps=20,
    image_cfg=7.0,
    audio_mood="subtle, ambient, conversational",
    audio_duration=30,
    video_mood="dialogue, conversational",
    video_frames=24,
)

# Suspense Scene Preset - Dark mystery
SUSPENSE_PRESET = ScenePreset(
    name="suspense",
    display_name="Suspense Scene",
    description="Dark mysterious atmosphere with tension",
    image_prompt_template=(
        "Chinese fantasy suspense scene, {description}, "
        "dark atmosphere, mysterious lighting, fog and shadows, "
        "tense mood, cinematic, high contrast"
    ),
    image_negative="bright, cheerful, low quality, deformed",
    image_width=1024,
    image_height=1024,
    image_steps=28,
    image_cfg=8.0,
    audio_mood="dark, ominous, suspenseful",
    audio_duration=60,
    video_mood="suspenseful, mysterious",
    video_frames=24,
)

# Tragedy Scene Preset - Somber mood
TRAGEDY_PRESET = ScenePreset(
    name="tragedy",
    display_name="Tragedy Scene",
    description="Somber tragic moment with muted colors",
    image_prompt_template=(
        "Chinese fantasy tragedy scene, {description}, "
        "somber mood, muted colors, rain, fallen leaves, "
        "melancholic atmosphere, emotional, cinematic"
    ),
    image_negative="bright, cheerful, vibrant colors, low quality",
    image_width=1024,
    image_height=1024,
    image_steps=25,
    image_cfg=7.5,
    audio_mood="melancholic, sad, slow",
    audio_duration=120,
    video_mood="tragic, somber",
    video_frames=24,
)

# Comedy Scene Preset - Light and playful
COMEDY_PRESET = ScenePreset(
    name="comedy",
    display_name="Comedy Scene",
    description="Lighthearted moment with bright colors",
    image_prompt_template=(
        "Chinese fantasy comedy scene, {description}, "
        "bright lighting, vibrant colors, playful atmosphere, "
        "exaggerated expressions, lighthearted mood"
    ),
    image_negative="dark, gloomy, serious, low quality",
    image_width=1024,
    image_height=768,
    image_steps=20,
    image_cfg=7.0,
    audio_mood="light, playful, bouncy",
    audio_duration=60,
    video_mood="comedic, light",
    video_frames=24,
)

# Epic Scene Preset - Grand scale
EPIC_PRESET = ScenePreset(
    name="epic",
    display_name="Epic Scene",
    description="Grand scale scene with dramatic landscape",
    image_prompt_template=(
        "Chinese fantasy epic scene, {description}, "
        "grand scale, majestic landscape, dramatic sky, "
        "clouds, mountain peaks, ancient architecture, cinematic"
    ),
    image_negative="small scale, indoor, low quality, deformed",
    image_width=1024,
    image_height=1024,
    image_steps=30,
    image_cfg=8.0,
    audio_mood="grand, powerful, orchestral",
    audio_duration=180,
    video_mood="epic, grand",
    video_frames=32,
)

# Night Scene Preset - Moonlit atmosphere
NIGHT_PRESET = ScenePreset(
    name="night",
    display_name="Night Scene",
    description="Moonlit scene with peaceful atmosphere",
    image_prompt_template=(
        "Chinese fantasy night scene, {description}, "
        "moonlight, starry sky, peaceful atmosphere, "
        "soft glow, night colors, serene mood"
    ),
    image_negative="daytime, bright, sunny, low quality",
    image_width=1024,
    image_height=1024,
    image_steps=25,
    image_cfg=7.5,
    audio_mood="peaceful, quiet, ambient night",
    audio_duration=90,
    video_mood="night, serene",
    video_frames=24,
)


# Registry of all presets
SCENE_PRESETS: dict[str, ScenePreset] = {
    "battle": BATTLE_PRESET,
    "romance": ROMANCE_PRESET,
    "dialogue": DIALOGUE_PRESET,
    "suspense": SUSPENSE_PRESET,
    "tragedy": TRAGEDY_PRESET,
    "comedy": COMEDY_PRESET,
    "epic": EPIC_PRESET,
    "night": NIGHT_PRESET,
}


def get_preset(name: str) -> ScenePreset:
    """Get a preset by name.

    Args:
        name: Preset name (battle, romance, dialogue, etc.)

    Returns:
        ScenePreset instance

    Raises:
        ValueError: If preset not found
    """
    if name not in SCENE_PRESETS:
        available = ", ".join(SCENE_PRESETS.keys())
        raise ValueError(f"Unknown preset '{name}'. Available: {available}")
    return SCENE_PRESETS[name]


def list_presets() -> list[str]:
    """List all available preset names.

    Returns:
        List of preset names
    """
    return list(SCENE_PRESETS.keys())


def build_preset_workflow(
    preset_name: str,
    description: str,
    asset_type: str = "image",
) -> dict[str, Any]:
    """Build a workflow from a preset.

    Args:
        preset_name: Name of the preset to use
        description: Scene description to fill in template
        asset_type: Type of asset ("image", "audio", "video")

    Returns:
        Workflow dict ready for execution
    """
    from crewai.comfy import WorkflowBuilder

    preset = get_preset(preset_name)
    builder = WorkflowBuilder()

    # Build prompt from template
    prompt = preset.image_prompt_template.format(description=description)

    if asset_type == "image":
        return builder.image.build_text_to_image(
            prompt=prompt,
            negative=preset.image_negative,
            width=preset.image_width,
            height=preset.image_height,
            steps=preset.image_steps,
            cfg=preset.image_cfg,
        )
    elif asset_type == "audio":
        return builder.audio.build_background_music(
            mood=preset.audio_mood,
            duration=preset.audio_duration,
        )
    elif asset_type == "video":
        return builder.video.build_text_to_video(
            prompt=prompt,
            negative=preset.image_negative,
            frames=preset.video_frames,
        )

    raise ValueError(f"Unknown asset type: {asset_type}")


class PresetWorkflowBuilder:
    """Convenience class for building preset workflows.

    Usage:
        from crewai.comfy.presets import PresetWorkflowBuilder

        builder = PresetWorkflowBuilder()
        workflow = builder.build("battle", "韩林拔剑冲向敌人")
    """

    def __init__(self):
        self._builder = None

    @property
    def builder(self):
        if self._builder is None:
            from crewai.comfy import WorkflowBuilder
            self._builder = WorkflowBuilder()
        return self._builder

    def build(
        self,
        preset_name: str,
        description: str,
        asset_type: str = "image",
    ) -> dict[str, Any]:
        """Build a workflow using a preset.

        Args:
            preset_name: Name of preset
            description: Scene description
            asset_type: Type of asset

        Returns:
            Workflow dict
        """
        return build_preset_workflow(preset_name, description, asset_type)

    def build_image(self, preset_name: str, description: str) -> dict[str, Any]:
        """Build an image workflow."""
        return self.build(preset_name, description, "image")

    def build_audio(self, preset_name: str, description: str = "") -> dict[str, Any]:
        """Build an audio workflow."""
        preset = get_preset(preset_name)
        return self.builder.audio.build_background_music(
            mood=preset.audio_mood,
            duration=preset.audio_duration,
        )

    def build_video(self, preset_name: str, description: str) -> dict[str, Any]:
        """Build a video workflow."""
        return self.build(preset_name, description, "video")
