"""Video Provider Protocol - Abstract interface for video generation providers.

This module defines the VideoProviderProtocol ABC and VideoGenerationResult dataclass
that all video providers (MiniMax, Runway, Kling, etc.) must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VideoGenerationResult:
    """Result of a video generation task.

    Attributes:
        task_id: Unique identifier for the generation task.
        status: Current status - one of: pending, processing, completed, failed.
        video_url: URL of the generated video (if available).
        video_path: Local path to the downloaded video file (if saved locally).
        duration_seconds: Duration of the video in seconds.
        error: Error message if the generation failed.
    """
    task_id: str
    status: str  # pending | processing | completed | failed
    video_url: Optional[str] = None
    video_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if the generation was successful."""
        return self.status == "completed" and (self.video_url is not None or self.video_path is not None)

    @property
    def is_terminal(self) -> bool:
        """Check if the result is in a terminal state."""
        return self.status in ("completed", "failed")


class VideoProviderProtocol(ABC):
    """Abstract interface for video generation providers.

    All video providers (MiniMax T2V/I2V, Runway, Kling, etc.) must implement
    this interface.

    Example:
        ```python
        provider = create_video_provider("minimax")
        result = await provider.generate(
            prompt="A warrior standing on a cliff",
            duration=5,
            aspect_ratio="16:9"
        )
        completed = await provider.wait(result.task_id)
        await provider.download(completed, "output.mp4")
        ```
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'minimax', 'runway', 'kling')."""
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        **kwargs,
    ) -> VideoGenerationResult:
        """Submit a video generation task.

        Args:
            prompt: Text description of the video to generate.
            duration: Video duration in seconds (1-10 for most providers).
            aspect_ratio: Aspect ratio of the output video ("16:9", "9:16", "1:1").
            **kwargs: Provider-specific extra parameters.

        Returns:
            VideoGenerationResult with task_id and status="pending".
        """
        ...

    @abstractmethod
    async def wait(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        timeout: float = 300.0,
    ) -> VideoGenerationResult:
        """Poll until the video generation task is complete.

        Args:
            task_id: The task ID returned by generate().
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait before raising TimeoutError.

        Returns:
            VideoGenerationResult with status="completed" or "failed".

        Raises:
            TimeoutError: If the task does not complete within timeout seconds.
        """
        ...

    @abstractmethod
    async def download(
        self,
        result: VideoGenerationResult,
        output_path: str,
    ) -> str:
        """Download a completed video to local storage.

        Args:
            result: A completed VideoGenerationResult (status="completed").
            output_path: Local file path to save the video.

        Returns:
            The local file path of the downloaded video.

        Raises:
            ValueError: If the result is not completed or has no video_url.
        """
        ...


__all__ = ["VideoProviderProtocol", "VideoGenerationResult"]
