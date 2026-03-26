"""Video Producer Agent for video content generation.

This agent specializes in creating video content for novels including:
- Scene visualizations
- Character animations
- Story recap videos

Usage:
    from crewai.comfy.agents.video_producer import VideoProducerAgent

    producer = VideoProducerAgent()
    result = producer.generate_scene_video(
        scene_description="韩林拔剑冲向叶尘",
        duration=5,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VideoProducerConfig:
    """Configuration for VideoProducerAgent."""

    default_width: int = 512
    default_height: int = 512
    default_frames: int = 24
    default_duration: int = 3  # seconds
    default_steps: int = 20
    video_model: str = "sv3d.safetensors"


@dataclass
class VideoRequirements:
    """Video requirements for a scene."""

    scene_id: str
    prompt: str
    duration: int
    frames: int
    mood: str
    key_frames: list[str]


class VideoProducerAgent:
    """Agent responsible for generating video content.

    This agent:
    1. Analyzes scene for video requirements
    2. Generates text-to-video or image-to-video content
    3. Can compose multiple video clips
    4. Adds audio to videos
    """

    def __init__(
        self,
        config: VideoProducerConfig | None = None,
        executor: Any | None = None,
    ):
        """Initialize the VideoProducerAgent.

        Args:
            config: Video producer configuration
            executor: Optional ComfyWorkflowExecutor instance
        """
        self.config = config or VideoProducerConfig()
        self.executor = executor
        self._initialized = False

    def _ensure_executor(self) -> Any:
        """Lazy-load the executor."""
        if self.executor is None:
            from crewai.comfy import ComfyWorkflowExecutor
            self.executor = ComfyWorkflowExecutor()
        return self.executor

    def analyze_video_requirements(
        self,
        scene_description: str,
        mood: str = "",
        key_moments: list[str] | None = None,
    ) -> VideoRequirements:
        """Analyze scene to determine video requirements.

        Args:
            scene_description: Description of the scene
            mood: Emotional mood
            key_moments: Key moments to capture

        Returns:
            VideoRequirements with extracted video data
        """
        import uuid

        # Build prompt from description
        prompt_parts = ["Chinese fantasy novel video clip"]

        if mood:
            prompt_parts.append(f"mood: {mood}")

        # Add scene elements
        prompt_parts.append(scene_description[:200])

        prompt = ", ".join(prompt_parts)

        return VideoRequirements(
            scene_id=str(uuid.uuid4())[:8],
            prompt=prompt,
            duration=self.config.default_duration,
            frames=self.config.default_frames,
            mood=mood,
            key_frames=key_moments or [],
        )

    def generate_scene_video(
        self,
        scene_description: str,
        duration: int | None = None,
        frames: int | None = None,
        mood: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """Generate a video from scene description.

        Args:
            scene_description: Description of the scene
            duration: Duration in seconds
            frames: Number of frames
            mood: Emotional mood
            **kwargs: Additional generation parameters

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        requirements = self.analyze_video_requirements(scene_description, mood)

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.video.build_text_to_video(
            prompt=requirements.prompt,
            negative=kwargs.get("negative", "blurry, low quality"),
            width=kwargs.get("width", self.config.default_width),
            height=kwargs.get("height", self.config.default_height),
            frames=frames or self.config.default_frames,
            duration=duration or requirements.duration,
            steps=kwargs.get("steps", self.config.default_steps),
        )

        result = executor.execute(workflow)

        return {
            "scene_id": requirements.scene_id,
            "prompt": requirements.prompt,
            "duration": duration or requirements.duration,
            "frames": frames or requirements.frames,
            "result": result,
        }

    def generate_character_animation(
        self,
        character_name: str,
        character_image: str,
        action_description: str,
        duration: int = 3,
    ) -> dict[str, Any]:
        """Generate an animated video of a character.

        Args:
            character_name: Name of the character
            character_image: Path to character image
            action_description: Description of the action
            duration: Duration in seconds

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        # Build prompt
        prompt = f"character animation: {character_name}, {action_description}"

        # Execute
        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.video.build_image_to_video(
            prompt=prompt,
            input_image=character_image,
            frames=24,
            duration=duration,
        )

        result = executor.execute(workflow)

        return {
            "character_name": character_name,
            "prompt": prompt,
            "input_image": character_image,
            "duration": duration,
            "result": result,
        }

    def generate_story_recap_video(
        self,
        scene_descriptions: list[str],
        audio_path: str | None = None,
        transition: str = "dissolve",
    ) -> dict[str, Any]:
        """Generate a recap video from multiple scenes.

        Args:
            scene_descriptions: List of scene descriptions
            audio_path: Optional audio file path
            transition: Transition type

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        # Generate individual scene videos
        scene_videos = []
        for i, desc in enumerate(scene_descriptions):
            scene_req = self.analyze_video_requirements(desc)
            workflow = builder.video.build_text_to_video(
                prompt=scene_req.prompt,
                duration=3,
            )
            # Note: In real implementation, would execute and collect output paths
            scene_videos.append(f"scene_{i}.mp4")

        # Compose videos
        if len(scene_videos) > 1:
            compose_workflow = builder.video.build_video_compose(
                video_sources=scene_videos,
                transition=transition,
            )
            result = executor.execute(compose_workflow)
        else:
            result = {"scene_videos": scene_videos}

        # Add audio if provided
        if audio_path:
            audio_workflow = builder.video.build_video_with_audio(
                video_workflow=compose_workflow if len(scene_videos) > 1 else workflow,
                audio_path=audio_path,
            )
            result = executor.execute(audio_workflow)

        return {
            "scene_count": len(scene_descriptions),
            "scenes": scene_descriptions,
            "transition": transition,
            "has_audio": audio_path is not None,
            "result": result,
        }

    def add_audio_to_video(
        self,
        video_path: str,
        audio_path: str,
        audio_offset: float = 0.0,
        audio_volume: float = 1.0,
    ) -> dict[str, Any]:
        """Add audio to a video.

        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            audio_offset: Audio start offset in seconds
            audio_volume: Audio volume

        Returns:
            Dict with generation results
        """
        from crewai.comfy import WorkflowBuilder

        # Build a dummy video workflow with the input video
        video_workflow = {
            "1": {
                "class_type": "LoadVideo",
                "inputs": {"video": video_path},
            },
            "2": {
                "class_type": "SaveVideo",
                "inputs": {
                    "images": ["1", 0],
                    "filename_prefix": "temp_video",
                    "fps": 24,
                },
            },
        }

        executor = self._ensure_executor()
        builder = WorkflowBuilder()

        workflow = builder.video.build_video_with_audio(
            video_workflow=video_workflow,
            audio_path=audio_path,
            audio_offset=audio_offset,
            audio_volume=audio_volume,
        )

        result = executor.execute(workflow)

        return {
            "video_path": video_path,
            "audio_path": audio_path,
            "audio_offset": audio_offset,
            "result": result,
        }
