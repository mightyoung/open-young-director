"""TTS Provider Factory - Create TTS provider instances.

Usage:
    from crewai.content.short_drama.video.tts.factory import create_tts_provider

    # From string name
    provider = create_tts_provider("minimax")

    # With config
    provider = create_tts_provider("minimax", api_key="xxx", output_dir="./output")

    # Async usage
    result = await provider.synthesize("韩林眼中闪过一丝惊讶", voice_id="male-chenl")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from crewai.content.short_drama.video.tts.base import TTSProviderProtocol

if TYPE_CHECKING:
    pass


def create_tts_provider(
    provider: str | None = None,
    **kwargs,
) -> TTSProviderProtocol:
    """Create a TTS provider instance by name.

    Args:
        provider: Provider name ("minimax", "elevenlabs").
                  Defaults to TTS_PROVIDER env var or "minimax".
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        TTSProviderProtocol instance.

    Raises:
        ValueError: If the provider name is not recognized.
    """
    if provider is None:
        provider = os.environ.get("TTS_PROVIDER", "minimax").lower()

    provider = provider.lower()

    if provider == "minimax":
        from crewai.content.short_drama.video.tts.providers.minimax_tts import (
            MiniMaxTTSProvider,
        )

        return MiniMaxTTSProvider(**kwargs)

    elif provider in ("elevenlabs", "eleven_labs"):
        from crewai.content.short_drama.video.tts.providers.elevenlabs_tts import (
            ElevenLabsTTSProvider,
        )

        return ElevenLabsTTSProvider(**kwargs)

    else:
        raise ValueError(
            f"Unknown TTS provider: {provider!r}. "
            f"Supported: minimax, elevenlabs"
        )


def list_tts_providers() -> list[str]:
    """Return a list of available TTS provider names."""
    return ["minimax", "elevenlabs"]


__all__ = ["create_tts_provider", "list_tts_providers"]
