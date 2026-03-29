"""TTS providers."""

from crewai.content.short_drama.video.tts.providers.minimax_tts import MiniMaxTTSProvider
from crewai.content.short_drama.video.tts.providers.elevenlabs_tts import ElevenLabsTTSProvider

__all__ = ["MiniMaxTTSProvider", "ElevenLabsTTSProvider"]
