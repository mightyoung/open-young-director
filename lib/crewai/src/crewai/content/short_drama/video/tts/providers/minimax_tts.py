"""MiniMax TTS Provider - Text-to-Speech via MiniMax API.

Reuses MiniMaxMediaExecutor from knowledge_base.media.minimax_executor.py.

Supported voices:
- female-shaonv (female young, default)
- male-chenl (male deep)
- female-tianmei
- male-yuanfeng
- male-bai (male narrator)

Models:
- speech-02-hd: High definition speech (default)
- speech-2.6-hd: Enhanced quality

Speed: 0.5-2.0
Emotion: happy, sad, angry, fearful, disgusted, surprised, neutral
         (only for older models, NOT for Speech-02-HD / Speech-2.6-HD)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from crewai.content.short_drama.video.tts.base import TTSProviderProtocol, TTSResult

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


class MiniMaxTTSProvider(TTSProviderProtocol):
    """MiniMax text-to-speech provider.

    Wraps MiniMaxMediaExecutor to conform to TTSProviderProtocol.
    """

    # Popular MiniMax voice IDs
    DEFAULT_VOICES = {
        "female-shaonv": "Female young (default)",
        "male-chenl": "Male deep voice",
        "female-tianmei": "Female sweet",
        "male-yuanfeng": "Male standard",
        "male-bai": "Male narrator",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        output_dir: Optional[str] = None,
        model: str = "speech-02-hd",
        default_voice: str = "female-shaonv",
        default_speed: float = 1.0,
        **kwargs,
    ):
        """Initialize MiniMax TTS provider.

        Args:
            api_key: MiniMax API key. Defaults to MINIMAX_API_KEY env var.
            api_host: API host URL.
            output_dir: Directory for downloaded audio files.
            model: Speech model to use.
            default_voice: Default voice ID.
            default_speed: Default speech speed.
            **kwargs: Ignored for compatibility.
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_host = api_host or os.environ.get(
            "MINIMAX_API_HOST", "https://api.minimaxi.com"
        )
        self.output_dir = Path(output_dir or "./output/audio")
        self.default_model = model
        self.default_voice = default_voice
        self.default_speed = default_speed
        self._executor: Optional["MiniMaxMediaExecutor"] = None

    @property
    def provider_name(self) -> str:
        return "minimax"

    def _get_executor(self) -> "MiniMaxMediaExecutor":
        if self._executor is None:
            self._executor = _get_executor(
                api_key=self.api_key,
                api_host=self.api_host,
                output_dir=str(self.output_dir),
            )
        return self._executor

    async def synthesize(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        model: Optional[str] = None,
        emotion: Optional[str] = None,
        output_format: str = "mp3",
        **kwargs,
    ) -> TTSResult:
        """Synthesize speech from text using MiniMax TTS.

        Args:
            text: The text to synthesize.
            voice_id: Voice ID (e.g., "female-shaonv", "male-chenl").
                      Use "default" to use the provider's default voice.
            speed: Speech speed (0.5-2.0).
            model: Speech model override.
            emotion: Emotional tone (happy, sad, angry, etc.).
                     Only for older models (speech-02-hd, speech-2.6-hd).
                     Do NOT use with Speech-02-HD (uppercase S).
            output_format: Audio format ("mp3", "wav", "pcm").
            **kwargs: Additional MiniMax parameters.

        Returns:
            TTSResult with audio_url.
        """
        if voice_id == "default":
            voice_id = self.default_voice

        model = model or self.default_model

        logger.info(
            f"[MiniMax TTS] synthesize: voice={voice_id}, "
            f"speed={speed}, model={model}, text={text[:40]}..."
        )

        try:
            result = await self._get_executor().generate_speech(
                text=text,
                voice_id=voice_id,
                model=model,
                speed=speed,
                emotion=emotion,
                output_format=output_format,
            )

            if result.get("success"):
                return TTSResult(
                    task_id="",  # MiniMax TTS is synchronous
                    audio_url=result.get("audio_url"),
                    status="completed",
                )
            else:
                return TTSResult(
                    task_id="",
                    status="failed",
                    error=result.get("error", "Unknown error"),
                )

        except Exception as e:
            logger.error(f"[MiniMax TTS] synthesize failed: {e}")
            return TTSResult(
                task_id="",
                status="failed",
                error=str(e),
            )

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
            ValueError: If result is not successful or has no audio_url.
            IOError: If the download fails.
        """
        if not result.is_success:
            raise ValueError(
                f"Cannot download: result status is {result.status!r}, "
                f"expected 'completed'"
            )
        if not result.audio_url:
            raise ValueError("Cannot download: no audio_url in result")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        download_result = await self._get_executor().download_file(
            url=result.audio_url,
            local_path=output_path,
        )

        if download_result["success"]:
            logger.info(
                f"[MiniMax TTS] downloaded: {download_result['local_path']}"
            )
            return download_result["local_path"]
        else:
            raise IOError(f"Download failed: {download_result['error']}")


__all__ = ["MiniMaxTTSProvider"]
