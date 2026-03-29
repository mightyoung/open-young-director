"""Short Drama TTS - Text-to-Speech tools.

Exports:
- TTSProviderProtocol, TTSResult
- create_tts_provider, list_tts_providers
"""

from crewai.content.short_drama.video.tts.base import (
    TTSProviderProtocol,
    TTSResult,
)
from crewai.content.short_drama.video.tts.factory import (
    create_tts_provider,
    list_tts_providers,
)

__all__ = [
    "TTSProviderProtocol",
    "TTSResult",
    "create_tts_provider",
    "list_tts_providers",
]
