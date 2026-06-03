"""DeepSeek API client using the OpenAI-compatible chat completions API."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class DeepSeekClient:
    """Client for DeepSeek text generation."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-flash")
        self.temperature = float(os.getenv("DEEPSEEK_TEMPERATURE", str(temperature)))
        self.max_tokens = int(os.getenv("DEEPSEEK_MAX_TOKENS", str(max_tokens)))
        self.timeout = timeout

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set")

    def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text with DeepSeek chat completions."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": self.temperature
                        if temperature is None
                        else temperature,
                        "max_tokens": self.max_tokens
                        if max_tokens is None
                        else max_tokens,
                    },
                )
            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error("DeepSeek API error (%s): %s", response.status_code, error_msg)
                raise RuntimeError(f"DeepSeek API error: {error_msg}")

            result = response.json()
            choices = result.get("choices") or []
            content = choices[0].get("message", {}).get("content", "") if choices else ""
            if not content:
                raise RuntimeError("DeepSeek API returned empty content")
            return content
        except Exception:
            logger.exception("DeepSeek API request failed")
            raise
