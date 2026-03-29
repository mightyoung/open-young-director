"""TTS Provider Protocol - Abstract interface for text-to-speech providers.

This module defines the TTSProviderProtocol ABC and TTSResult dataclass
that all TTS providers (MiniMax, ElevenLabs, etc.) must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class TTSResult:
    """Result of a TTS synthesis task.

    Attributes:
        task_id: Unique identifier for the synthesis task.
        audio_url: URL of the generated audio (if available).
        audio_path: Local path to the downloaded audio file.
        duration_seconds: Duration of the audio in seconds.
        status: Current status - one of: pending, completed, failed.
        error: Error message if synthesis failed.
    """
    task_id: str
    audio_url: Optional[str] = None
    audio_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    status: str = "pending"  # pending | completed | failed
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Check if synthesis was successful."""
        return self.status == "completed" and (self.audio_url is not None or self.audio_path is not None)

    @property
    def is_terminal(self) -> bool:
        """Check if result is in a terminal state."""
        return self.status in ("completed", "failed")


class TTSProviderProtocol(ABC):
    """Abstract interface for TTS (Text-to-Speech) providers.

    All TTS providers (MiniMax, ElevenLabs, etc.) must implement this interface.

    Example:
        ```python
        provider = create_tts_provider("minimax")
        result = await provider.synthesize(
            text="韩林眼中闪过一丝惊讶",
            voice_id="male-chenl",
            speed=1.0
        )
        audio_path = await provider.download(result, "output.mp3")
        ```
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'minimax', 'elevenlabs')."""
        ...

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech from text.

        Args:
            text: The text to synthesize.
            voice_id: Voice identifier (provider-specific).
            speed: Speech speed multiplier (0.5-2.0 typically).
            **kwargs: Provider-specific extra parameters.

        Returns:
            TTSResult with task_id and status="completed" or "failed".
            For synchronous providers, status="completed" immediately.
        """
        ...

    @abstractmethod
    async def download(
        self,
        result: TTSResult,
        output_path: str,
    ) -> str:
        """Download synthesized audio to local storage.

        Args:
            result: A completed TTSResult.
            output_path: Local file path to save the audio.

        Returns:
            The local file path of the downloaded audio.

        Raises:
            ValueError: If the result is not successful or has no audio_url.
        """
        ...


__all__ = ["TTSProviderProtocol", "TTSResult"]
