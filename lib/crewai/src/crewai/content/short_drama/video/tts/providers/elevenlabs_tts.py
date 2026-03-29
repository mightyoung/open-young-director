"""ElevenLabs TTS Provider - Stub implementation.

This is a placeholder/stub implementation for ElevenLabs text-to-speech.
To use ElevenLabs, implement actual API calls to https://api.elevenlabs.io/v1.

Supported voices: Any voice from ElevenLabs voice library.
Models: eleven_multilingual_v2, eleven_v2, etc.

Speed: 0.5-2.0 (via stability/pimilarity settings or API speed param)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from crewai.content.short_drama.video.tts.base import TTSProviderProtocol, TTSResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class ElevenLabsTTSProvider(TTSProviderProtocol):
    """ElevenLabs text-to-speech provider (stub).

    To complete this implementation, replace stub methods with actual
    ElevenLabs API calls. See: https://elevenlabs.io/api
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        output_dir: Optional[str] = None,
        model: str = "eleven_multilingual_v2",
        default_voice: str = "21m00Tcm4TlvDq8ikYAM",
        **kwargs,
    ):
        """Initialize ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key.
                     Defaults to ELEVENLABS_API_KEY env var.
            output_dir: Directory for downloaded audio files.
            model: Speech model to use.
            default_voice: Default voice ID.
            **kwargs: Ignored for compatibility.
        """
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self.output_dir = Path(output_dir or "./output/audio")
        self.default_model = model
        self.default_voice = default_voice

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    async def synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech using ElevenLabs (stub)."""
        logger.warning(
            "[ElevenLabs TTS] Provider is a stub - not yet implemented. "
            "Use MiniMax TTS provider for actual speech synthesis."
        )

        return TTSResult(
            task_id="",
            status="failed",
            error=(
                "ElevenLabs TTS provider is not yet implemented. "
                "Use --tts-provider minimax for speech synthesis."
            ),
        )

    async def download(
        self,
        result: TTSResult,
        output_path: str,
    ) -> str:
        """Download audio (stub)."""
        raise ValueError("ElevenLabs TTS provider not implemented")


__all__ = ["ElevenLabsTTSProvider"]
