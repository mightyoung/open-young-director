"""MiniMax Video Provider - T2V/I2V/S2V via MiniMax API.

Reuses MiniMaxMediaExecutor from knowledge_base.media.minimax_executor.py.

Supported models:
- T2V-01: Text-to-Video (default)
- T2V-01-Director: Director-aware T2V
- I2V-01: Image-to-Video (requires first_frame_image)
- S2V-01: Subject-to-Video (requires subject_image)
- MiniMax-Hailuo-02: Fast video model

Duration: 1-10 seconds
Aspect ratios: 16:9, 9:16, 1:1, 4:3, 3:4
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import aiohttp

from crewai.content.short_drama.video.base import (
    VideoGenerationResult,
    VideoProviderProtocol,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from knowledge_base.media.minimax_executor import MiniMaxMediaExecutor

_executor_instance: Optional["MiniMaxMediaExecutor"] = None


def _get_executor(
    api_key: str,
    api_host: str,
    output_dir: str,
) -> "MiniMaxMediaExecutor":
    """Get or create the MiniMaxMediaExecutor singleton."""
    global _executor_instance
    if _executor_instance is None:
        from knowledge_base.media.minimax_executor import MiniMaxMediaExecutor

        _executor_instance = MiniMaxMediaExecutor(
            api_key=api_key,
            api_host=api_host,
            output_dir=output_dir,
        )
    return _executor_instance


class MiniMaxVideoProvider(VideoProviderProtocol):
    """MiniMax video generation provider.

    Wraps MiniMaxMediaExecutor to conform to VideoProviderProtocol.

    Attributes:
        output_dir: Default directory for downloaded video files.
    """

    SUPPORTED_RATIOS = {"16:9", "9:16", "1:1", "4:3", "3:4"}
    MIN_DURATION = 1
    MAX_DURATION = 10

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        output_dir: Optional[str] = None,
        model: str = "T2V-01",
        resolution: str = "768P",
        **kwargs,
    ):
        """Initialize MiniMax video provider.

        Args:
            api_key: MiniMax API key. Defaults to MINIMAX_API_KEY env var.
            api_host: API host URL. Defaults to MINIMAX_API_HOST.
            output_dir: Directory to save downloaded videos.
            model: Default video model (T2V-01, I2V-01, etc.).
            resolution: Video resolution ("768P", "1080P").
            **kwargs: Ignored for API compatibility.
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_host = api_host or os.environ.get(
            "MINIMAX_API_HOST", "https://api.minimaxi.com"
        )
        self.output_dir = Path(output_dir or "./output/videos")
        self.default_model = model
        self.default_resolution = resolution
        self._executor: Optional["MiniMaxMediaExecutor"] = None

    @property
    def provider_name(self) -> str:
        return "minimax"

    def _get_executor(self) -> "MiniMaxMediaExecutor":
        """Get or create the executor instance."""
        if self._executor is None:
            self._executor = _get_executor(
                api_key=self.api_key,
                api_host=self.api_host,
                output_dir=str(self.output_dir),
            )
        return self._executor

    def _validate_params(self, duration: int, aspect_ratio: str) -> None:
        """Validate generation parameters."""
        if not self.MIN_DURATION <= duration <= self.MAX_DURATION:
            raise ValueError(
                f"Duration must be between {self.MIN_DURATION} and "
                f"{self.MAX_DURATION} seconds, got {duration}"
            )
        if aspect_ratio not in self.SUPPORTED_RATIOS:
            raise ValueError(
                f"Unsupported aspect ratio: {aspect_ratio!r}. "
                f"Supported: {self.SUPPORTED_RATIOS}"
            )

    async def generate(
        self,
        prompt: str,
        duration: int = 5,
        aspect_ratio: str = "16:9",
        model: Optional[str] = None,
        first_frame_image: Optional[str] = None,
        subject_image: Optional[str] = None,
        **kwargs,
    ) -> VideoGenerationResult:
        """Submit a video generation task to MiniMax.

        Args:
            prompt: Text description of the video.
            duration: Video duration in seconds (1-10).
            aspect_ratio: Output aspect ratio ("16:9", "9:16", "1:1").
            model: Video model override (default: T2V-01).
            first_frame_image: Image URL/path for I2V.
            subject_image: Image URL/path for S2V.
            **kwargs: Additional MiniMax parameters.

        Returns:
            VideoGenerationResult with task_id.
        """
        self._validate_params(duration, aspect_ratio)

        model = model or self.default_model
        logger.info(
            f"[MiniMax] generate: model={model}, duration={duration}s, "
            f"ratio={aspect_ratio}, prompt={prompt[:60]}..."
        )

        try:
            result = await self._get_executor().generate_video(
                prompt=prompt,
                model=model,
                first_frame_image=first_frame_image,
                subject_image=subject_image,
                duration=duration,
                resolution=self.default_resolution,
                wait_for_completion=False,
            )

            if result.get("success"):
                return VideoGenerationResult(
                    task_id=result.get("task_id", ""),
                    status="pending",
                    video_url=result.get("video_url"),
                )
            else:
                return VideoGenerationResult(
                    task_id=result.get("task_id", ""),
                    status="failed",
                    error=result.get("error", "Unknown error"),
                )

        except Exception as e:
            logger.error(f"[MiniMax] generate failed: {e}")
            return VideoGenerationResult(
                task_id="",
                status="failed",
                error=str(e),
            )

    async def wait(
        self,
        task_id: str,
        poll_interval: float = 3.0,
        timeout: float = 300.0,
    ) -> VideoGenerationResult:
        """Poll MiniMax API until video generation is complete.

        Args:
            task_id: Task ID from generate().
            poll_interval: Seconds between status polls.
            timeout: Maximum seconds to wait.

        Returns:
            VideoGenerationResult with status="completed" or "failed".

        Raises:
            TimeoutError: If polling exceeds timeout.
        """
        if not task_id:
            return VideoGenerationResult(
                task_id=task_id,
                status="failed",
                error="No task_id provided",
            )

        api_key = self.api_key or os.environ.get("MINIMAX_API_KEY", "")
        api_host = self.api_host
        query_url = f"{api_host}/v1/query/video_generation"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.monotonic()

        while time.monotonic() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        query_url,
                        params={"task_id": task_id},
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as resp:
                        if resp.status != 200:
                            logger.warning(
                                f"[MiniMax] query returned HTTP {resp.status}"
                            )
                            await asyncio.sleep(poll_interval)
                            continue

                        data = await resp.json()
                        base_resp = data.get("base_resp", {})
                        status_code = base_resp.get("status_code", 1)

                        if status_code == 2:  # SUCCESS
                            video_url = data.get("data", {}).get("video_url")
                            duration_sec = data.get("data", {}).get("duration")
                            return VideoGenerationResult(
                                task_id=task_id,
                                status="completed",
                                video_url=video_url,
                                duration_seconds=duration_sec,
                            )
                        elif status_code == 3:  # FAILED
                            return VideoGenerationResult(
                                task_id=task_id,
                                status="failed",
                                error=base_resp.get(
                                    "status_msg", "Generation failed"
                                ),
                            )
                        else:
                            # pending (0) or processing (1)
                            logger.debug(
                                f"[MiniMax] task {task_id}: status={status_code}, "
                                f"waiting {poll_interval}s..."
                            )
                            await asyncio.sleep(poll_interval)

            except asyncio.TimeoutError:
                logger.warning("[MiniMax] poll timeout, retrying...")
                await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.warning(f"[MiniMax] polling error: {e}")
                await asyncio.sleep(poll_interval)

        return VideoGenerationResult(
            task_id=task_id,
            status="failed",
            error=f"Timeout after {timeout}s",
        )

    async def download(
        self,
        result: VideoGenerationResult,
        output_path: str,
    ) -> str:
        """Download a completed MiniMax video to local storage.

        Args:
            result: A completed VideoGenerationResult.
            output_path: Local file path to save the video.

        Returns:
            The local file path of the downloaded video.

        Raises:
            ValueError: If result is not successful or has no video_url.
            IOError: If the download fails.
        """
        if not result.is_success:
            raise ValueError(
                f"Cannot download: result status is {result.status!r}, "
                f"expected 'completed'"
            )
        if not result.video_url:
            raise ValueError("Cannot download: no video_url in result")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        download_result = await self._get_executor().download_file(
            url=result.video_url,
            local_path=output_path,
        )

        if download_result["success"]:
            logger.info(f"[MiniMax] downloaded: {download_result['local_path']}")
            return download_result["local_path"]
        else:
            raise IOError(f"Download failed: {download_result['error']}")


__all__ = ["MiniMaxVideoProvider"]
