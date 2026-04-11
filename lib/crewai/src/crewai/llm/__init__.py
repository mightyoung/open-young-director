"""crewai.llm — lightweight LLM adapter layer for the young-writer pipeline."""

from crewai.llm.deepseek_client import (
    DeepSeekAPIError,
    DeepSeekClient,
    DeepSeekRateLimitError,
    DeepSeekTimeoutError,
)

# Base LLM class for compatibility with legacy code
class BaseLLM:
    """Base class for LLM implementations."""
    pass

class LLM(DeepSeekClient, BaseLLM):
    """LLM alias for DeepSeekClient for compatibility."""
    pass

__all__ = [
    "DeepSeekClient",
    "DeepSeekAPIError",
    "DeepSeekRateLimitError",
    "DeepSeekTimeoutError",
    "BaseLLM",
    "LLM",
]
