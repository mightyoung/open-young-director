"""Shared LLM factory used by short_drama CLI subcommands.

Mirrors the pattern from create_content.py.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM


def create_llm_from_env() -> "LLM | None":
    """Create an LLM instance from environment variables.

    Checks MiniMax, DeepSeek, Gemini, Doubao, Kimi in priority order
    and returns the first configured one.

    Returns:
        LLM instance or None if no API key is configured.
    """
    # MiniMax (fast, good for China)
    minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    minimax_url = os.environ.get("MINIMAX_BASE_URL", "").strip()
    minimax_model = os.environ.get("MINIMAX_MODEL", "").strip()

    if minimax_key and minimax_url:
        from crewai.llm import LLM

        return LLM(
            model=minimax_model or "MiniMax-M2.7-highspeed",
            api_key=minimax_key,
            base_url=minimax_url,
        )

    # DeepSeek
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        from crewai.llm import LLM

        return LLM(model="deepseek/deepseek-chat", api_key=deepseek_key)

    # Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        from crewai.llm import LLM

        return LLM(model="gemini/gemini-2.5-flash", api_key=gemini_key)

    # Doubao
    doubao_key = os.environ.get("DOUBAO_API_KEY", "").strip()
    doubao_url = os.environ.get("DOUBAO_API_HOST", "").strip()
    doubao_model = os.environ.get("DOUBAO_MODEL", "").strip()

    if doubao_key and doubao_url:
        from crewai.llm import LLM

        return LLM(
            model=doubao_model or "doubao-seed-2-0-pro-260215",
            api_key=doubao_key,
            base_url=doubao_url,
        )

    # Kimi
    kimi_key = os.environ.get("KIMI_API_KEY", "").strip()
    kimi_model = os.environ.get("KIMI_MODEL_NAME", "").strip()

    if kimi_key:
        from crewai.llm import LLM

        return LLM(
            model=kimi_model or "moonshot-v1-8k",
            api_key=kimi_key,
            base_url="https://api.moonshot.cn/v1",
        )

    return None


def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json_output(result, output_dir: Path, filename: str) -> None:
    """Save result as JSON file."""
    import json

    output_file = output_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
