"""Compatibility layer for the public ``crewai.llm`` import path."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from crewai.llm.deepseek_client import (
    DeepSeekAPIError,
    DeepSeekClient,
    DeepSeekRateLimitError,
    DeepSeekTimeoutError,
)


def _load_legacy_llm_module():
    """Load the legacy ``crewai/llm.py`` implementation for backwards compatibility."""

    legacy_path = Path(__file__).resolve().parents[1] / "llm.py"
    spec = importlib.util.spec_from_file_location("crewai._legacy_llm", legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy LLM module from {legacy_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy_llm = _load_legacy_llm_module()

BaseLLM = _legacy_llm.BaseLLM
LLM = _legacy_llm.LLM
DEFAULT_CONTEXT_WINDOW_SIZE = _legacy_llm.DEFAULT_CONTEXT_WINDOW_SIZE
CONTEXT_WINDOW_USAGE_RATIO = _legacy_llm.CONTEXT_WINDOW_USAGE_RATIO
LLM_CONTEXT_WINDOW_SIZES = _legacy_llm.LLM_CONTEXT_WINDOW_SIZES
SUPPORTED_NATIVE_PROVIDERS = _legacy_llm.SUPPORTED_NATIVE_PROVIDERS

__all__ = [
    "BaseLLM",
    "LLM",
    "DEFAULT_CONTEXT_WINDOW_SIZE",
    "CONTEXT_WINDOW_USAGE_RATIO",
    "LLM_CONTEXT_WINDOW_SIZES",
    "SUPPORTED_NATIVE_PROVIDERS",
    "DeepSeekClient",
    "DeepSeekAPIError",
    "DeepSeekRateLimitError",
    "DeepSeekTimeoutError",
]
