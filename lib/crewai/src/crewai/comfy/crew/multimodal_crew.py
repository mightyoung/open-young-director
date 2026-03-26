"""Multimodal Crew for novel content generation.

This module provides a pre-configured CrewAI Crew with specialized
agents for generating multimodal content (images, audio, video) for novels.

Usage:
    from crewai.comfy.crew.multimodal_crew import MultimodalCrew

    crew = MultimodalCrew(
        visual_director=True,
        sound_designer=True,
        video_producer=False,
    )
    result = crew.kickoff({
        "chapter_content": "韩林站在太虚宗演武场上...",
        "scenes": [...],
    })
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MultimodalCrewConfig:
    """Configuration for the MultimodalCrew."""

    # Agent settings
    include_visual_director: bool = True
    include_sound_designer: bool = True
    include_video_producer: bool = False

    # Quality settings
    image_quality: str = "high"  # "standard", "high", "ultra"
    audio_quality: str = "high"
    video_quality: str = "high"

    # Generation settings
    max_images_per_scene: int = 2
    max_audio_per_scene: int = 1
    generate_soundscape: bool = True
    generate_bgm: bool = True

    # Parallel execution
    parallel_generation: bool = True
    max_concurrent: int = 3


class MultimodalCrew:
    """Pre-configured Crew for multimodal novel content generation.

    This crew coordinates:
    - VisualDirectorAgent: Scene illustrations, character portraits
    - SoundDesignerAgent: Soundscapes, BGM, SFX, narration
    - VideoProducerAgent: Scene videos, character animations
    """

    def __init__(
        self,
        config: Optional[MultimodalCrewConfig] = None,
        llm_client: Any = None,
    ):
        """Initialize the MultimodalCrew.

        Args:
            config: Crew configuration
            llm_client: Optional LLM client for agents
        """
        self.config = config or MultimodalCrewConfig()
        self.llm_client = llm_client

        # Initialize agents
        self.agents: dict[str, Any] = {}
        self._setup_agents()

    def _setup_agents(self) -> None:
        """Set up crew agents based on configuration."""
        from crewai.comfy.agents import (
            VisualDirectorAgent,
            SoundDesignerAgent,
            VideoProducerAgent,
        )

        if self.config.include_visual_director:
            self.agents["visual_director"] = VisualDirectorAgent()

        if self.config.include_sound_designer:
            self.agents["sound_designer"] = SoundDesignerAgent()

        if self.config.include_video_producer:
            self.agents["video_producer"] = VideoProducerAgent()

        logger.info(f"MultimodalCrew initialized with agents: {list(self.agents.keys())}")

    def generate_scene_assets(
        self,
        scene_description: str,
        scene_id: str,
        characters: list[str] | None = None,
        scene_type: str = "dialogue",
        mood: str = "",
    ) -> dict[str, Any]:
        """Generate all assets for a single scene.

        Args:
            scene_description: Description of the scene
            scene_id: Unique scene identifier
            characters: Character names in the scene
            scene_type: Type of scene (battle, dialogue, romance, etc.)
            mood: Emotional mood

        Returns:
            Dict with generated assets (images, audio, video)
        """
        results = {
            "scene_id": scene_id,
            "images": [],
            "audio": {},
            "video": None,
        }

        # Generate images
        if "visual_director" in self.agents and self.config.include_visual_director:
            vd = self.agents["visual_director"]

            # Generate main scene illustration
            img_result = vd.generate_scene_illustration(
                scene_description=scene_description,
                characters=characters,
                mood=mood,
            )
            results["images"].append(img_result)

            # Generate character portraits if specified
            if characters and self.config.max_images_per_scene > 1:
                for char in characters[:2]:  # Limit to 2 character portraits
                    portrait_result = vd.generate_character_portrait(
                        character_name=char,
                        character_description=scene_description,
                    )
                    results["images"].append(portrait_result)

        # Generate audio
        if "sound_designer" in self.agents and self.config.include_sound_designer:
            sd = self.agents["sound_designer"]

            # Generate soundscape
            if self.config.generate_soundscape:
                sound_result = sd.generate_soundscape(
                    scene_type=scene_type,
                    mood=mood,
                )
                results["audio"]["soundscape"] = sound_result

            # Generate BGM
            if self.config.generate_bgm:
                bgm_result = sd.generate_background_music(
                    mood=mood,
                )
                results["audio"]["bgm"] = bgm_result

        # Generate video
        if "video_producer" in self.agents and self.config.include_video_producer:
            vp = self.agents["video_producer"]
            video_result = vp.generate_scene_video(
                scene_description=scene_description,
                mood=mood,
            )
            results["video"] = video_result

        return results

    def kickoff(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute the crew workflow.

        Args:
            inputs: Dict with:
                - chapter_content: Full chapter text
                - scenes: List of scene dicts with description, characters, etc.
                - metadata: Optional metadata (chapter_number, title, etc.)

        Returns:
            Dict with all generated assets organized by scene
        """
        scenes = inputs.get("scenes", [])
        metadata = inputs.get("metadata", {})

        logger.info(f"Starting MultimodalCrew for {len(scenes)} scenes")

        all_results = {
            "chapter": metadata,
            "scenes": [],
            "summary": {
                "total_images": 0,
                "total_audio": 0,
                "total_video": 0,
            },
        }

        # Process each scene
        for scene in scenes:
            scene_id = scene.get("scene_id", f"scene_{len(all_results['scenes'])}")
            scene_result = self.generate_scene_assets(
                scene_description=scene.get("description", ""),
                scene_id=scene_id,
                characters=scene.get("characters", []),
                scene_type=scene.get("type", "dialogue"),
                mood=scene.get("mood", ""),
            )

            all_results["scenes"].append(scene_result)
            all_results["summary"]["total_images"] += len(scene_result["images"])
            all_results["summary"]["total_audio"] += len(scene_result["audio"])
            if scene_result["video"]:
                all_results["summary"]["total_video"] += 1

        logger.info(f"MultimodalCrew completed: {all_results['summary']}")
        return all_results


def create_novel_multimodal_crew(
    include_video: bool = False,
    quality: str = "high",
) -> MultimodalCrew:
    """Factory function to create a pre-configured multimodal crew.

    Args:
        include_video: Whether to include video producer
        quality: Quality preset ("standard", "high", "ultra")

    Returns:
        Configured MultimodalCrew instance
    """
    config = MultimodalCrewConfig(
        include_video_producer=include_video,
        image_quality=quality,
        audio_quality=quality,
        video_quality=quality,
    )
    return MultimodalCrew(config=config)
