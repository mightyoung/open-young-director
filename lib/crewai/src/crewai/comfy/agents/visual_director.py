"""Visual Director Agent for novel illustration generation.

This agent specializes in creating high-quality illustrations for novel scenes.
It works with the ComfyUI executor to generate images based on scene descriptions.

Usage:
    from crewai.comfy.agents.visual_director import VisualDirectorAgent

    director = VisualDirectorAgent()
    result = director.generate_scene_illustration(
        scene_description="韩林站在太虚宗演武场上，阳光照耀",
        characters=["韩林", "柳如烟"],
        mood="epic, dramatic",
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class VisualDirectorConfig:
    """Configuration for VisualDirectorAgent."""

    default_width: int = 1024
    default_height: int = 1024
    default_steps: int = 25
    default_cfg: float = 8.0
    style_preset: str = "chinese_fantasy"
    negative_prompt: str = "blurry, low quality, distorted, bad anatomy, watermark"


@dataclass
class SceneVisualRequirements:
    """Visual requirements extracted from a scene."""

    scene_id: str
    location: str
    time_of_day: str
    mood: str
    characters: list[str]
    key_elements: list[str]
    style_notes: str = ""


class VisualDirectorAgent:
    """Agent responsible for generating scene illustrations.

    This agent:
    1. Analyzes scene description and extracts visual requirements
    2. Builds optimized prompts for ComfyUI image generation
    3. Executes the workflow and returns image paths
    4. Can iterate on generations based on feedback
    """

    def __init__(
        self,
        config: VisualDirectorConfig | None = None,
        executor: Any | None = None,
    ):
        """Initialize the VisualDirectorAgent.

        Args:
            config: Visual director configuration
            executor: Optional ComfyWorkflowExecutor instance
        """
        self.config = config or VisualDirectorConfig()
        self.executor = executor
        self._initialized = False

    def _ensure_executor(self) -> Any:
        """Lazy-load the executor."""
        if self.executor is None:
            from crewai.comfy import ComfyWorkflowExecutor
            self.executor = ComfyWorkflowExecutor()
        return self.executor

    def analyze_scene(
        self,
        scene_description: str,
        characters: list[str] | None = None,
        location: str = "",
        time_of_day: str = "day",
        mood: str = "",
    ) -> SceneVisualRequirements:
        """Analyze a scene and extract visual requirements.

        Args:
            scene_description: Description of the scene
            characters: List of character names in the scene
            location: Location name
            time_of_day: Time of day (day, night, dawn, dusk)
            mood: Emotional mood of the scene

        Returns:
            SceneVisualRequirements with extracted visual data
        """
        import uuid

        # Extract key visual elements from description
        key_elements = self._extract_visual_elements(scene_description)

        # Build style notes based on genre and mood
        style_notes = self._build_style_notes(time_of_day, mood)

        return SceneVisualRequirements(
            scene_id=str(uuid.uuid4())[:8],
            location=location,
            time_of_day=time_of_day,
            mood=mood,
            characters=characters or [],
            key_elements=key_elements,
            style_notes=style_notes,
        )

    def _extract_visual_elements(self, description: str) -> list[str]:
        """Extract key visual elements from scene description."""
        elements = []

        # Common fantasy/Chinese fantasy elements
        fantasy_keywords = {
            "演武场": ["arena", "martial arts platform", "stone pillars"],
            "山峰": ["mountain peaks", "clouds", "misty"],
            "宫殿": ["palace", "golden roof", "pillars"],
            "森林": ["forest", "ancient trees", "mystical"],
            "夜空": ["night sky", "stars", "moonlight"],
            "阳光": ["sunlight", "bright", "warm"],
        }

        for keyword, visual_elements in fantasy_keywords.items():
            if keyword in description:
                elements.extend(visual_elements)

        return elements if elements else ["scene backdrop"]

    def _build_style_notes(self, time_of_day: str, mood: str) -> str:
        """Build style description based on time and mood."""
        time_styles = {
            "day": "bright, vibrant colors, sharp details",
            "night": "dark atmosphere, moonlight, soft glow",
            "dawn": "warm orange tones, misty, ethereal",
            "dusk": "purple and orange gradients, dramatic shadows",
        }

        style = time_styles.get(time_of_day, "detailed, cinematic")

        if mood:
            style += f", {mood}"

        return style

    def build_prompt(
        self,
        requirements: SceneVisualRequirements,
        include_characters: bool = True,
    ) -> tuple[str, str]:
        """Build positive and negative prompts for image generation.

        Args:
            requirements: Scene visual requirements
            include_characters: Whether to include character descriptions

        Returns:
            Tuple of (positive_prompt, negative_prompt)
        """
        # Build positive prompt
        prompt_parts = ["Chinese fantasy novel illustration, high quality"]

        # Add location and setting
        if requirements.location:
            prompt_parts.append(f"setting: {requirements.location}")

        # Add time of day
        prompt_parts.append(f"time: {requirements.time_of_day}")

        # Add mood
        if requirements.mood:
            prompt_parts.append(f"mood: {requirements.mood}")

        # Add key visual elements
        if requirements.key_elements:
            prompt_parts.append(f"elements: {', '.join(requirements.key_elements)}")

        # Add characters if specified
        if include_characters and requirements.characters:
            char_desc = ", ".join(requirements.characters)
            prompt_parts.append(f"characters: {char_desc}")

        # Add style notes
        if requirements.style_notes:
            prompt_parts.append(f"style: {requirements.style_notes}")

        positive_prompt = ", ".join(prompt_parts)

        # Negative prompt
        negative_prompt = self.config.negative_prompt

        return positive_prompt, negative_prompt

    def generate_scene_illustration(
        self,
        scene_description: str,
        characters: list[str] | None = None,
        location: str = "",
        time_of_day: str = "day",
        mood: str = "",
        width: int | None = None,
        height: int | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Generate an illustration for a scene.

        Args:
            scene_description: Description of the scene
            characters: Character names
            location: Location name
            time_of_day: Time of day
            mood: Scene mood
            width: Image width
            height: Image height
            **kwargs: Additional generation parameters

        Returns:
            Dict with generation results including image paths
        """
        from crewai.comfy import WorkflowBuilder

        # Analyze scene
        requirements = self.analyze_scene(
            scene_description=scene_description,
            characters=characters,
            location=location,
            time_of_day=time_of_day,
            mood=mood,
        )

        # Build prompts
        positive_prompt, negative_prompt = self.build_prompt(requirements)

        # Build workflow
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.image.build_text_to_image(
            prompt=positive_prompt,
            negative=negative_prompt,
            width=width or self.config.default_width,
            height=height or self.config.default_height,
            steps=kwargs.get("steps", self.config.default_steps),
            cfg=kwargs.get("cfg", self.config.default_cfg),
            model=kwargs.get("model", "sd_xl_base_1.0.safetensors"),
        )

        # Execute
        result = executor.execute(workflow)

        return {
            "scene_id": requirements.scene_id,
            "prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "requirements": {
                "location": requirements.location,
                "time_of_day": requirements.time_of_day,
                "mood": requirements.mood,
                "characters": requirements.characters,
            },
            "result": result,
        }

    def generate_character_portrait(
        self,
        character_name: str,
        character_description: str,
        pose: str = "standing",
        style: str = "chinese_fantasy",
    ) -> dict[str, Any]:
        """Generate a character portrait.

        Args:
            character_name: Name of the character
            character_description: Physical description
            pose: Character pose
            style: Art style

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        # Build prompt
        prompt = f"character portrait: {character_name}, {character_description}, {pose}, {style} style, high quality"

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.image.build_text_to_image(
            prompt=prompt,
            negative=self.config.negative_prompt,
            width=512,
            height=768,  # Portrait aspect ratio
            steps=self.config.default_steps,
        )

        result = executor.execute(workflow)

        return {
            "character_name": character_name,
            "prompt": prompt,
            "result": result,
        }

    def iterate_on_generation(
        self,
        previous_result: dict[str, Any],
        feedback: str,
    ) -> dict[str, Any]:
        """Iterate on a previous generation based on feedback.

        Args:
            previous_result: Result from previous generation
            feedback: Feedback for improvement

        Returns:
            New generation result
        """
        # Extract previous prompt and modify based on feedback
        previous_prompt = previous_result.get("prompt", "")

        # Build new prompt with feedback incorporated
        new_prompt = f"{previous_prompt}, {feedback}"

        from crewai.comfy import WorkflowBuilder

        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.image.build_text_to_image(
            prompt=new_prompt,
            negative=self.config.negative_prompt,
            width=previous_result.get("requirements", {}).get("width", self.config.default_width),
            height=previous_result.get("requirements", {}).get("height", self.config.default_height),
        )

        result = executor.execute(workflow)

        return {
            "previous_result": previous_result,
            "feedback": feedback,
            "new_prompt": new_prompt,
            "result": result,
        }
