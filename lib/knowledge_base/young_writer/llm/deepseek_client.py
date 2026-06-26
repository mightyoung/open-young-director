"""DeepSeek API client using the OpenAI-compatible chat completions API."""

from __future__ import annotations

import logging
import os
import time
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
        empty_content_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-v4-flash")
        self.temperature = float(os.getenv("DEEPSEEK_TEMPERATURE", str(temperature)))
        self.max_tokens = int(os.getenv("DEEPSEEK_MAX_TOKENS", str(max_tokens)))
        self.timeout = timeout
        self.empty_content_retries = int(
            os.getenv("DEEPSEEK_EMPTY_CONTENT_RETRIES", str(empty_content_retries))
        )
        self.retry_delay = float(
            os.getenv("DEEPSEEK_RETRY_DELAY", str(retry_delay))
        )

        if not self.api_key:
            logger.warning("DEEPSEEK_API_KEY not set")

    def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text with DeepSeek chat completions."""
        attempt_count = max(1, self.empty_content_retries + 1)
        last_error: Exception | None = None
        for attempt in range(1, attempt_count + 1):
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
                    error_msg = self._format_api_error(response)
                    logger.error(
                        "DeepSeek API error (%s): %s",
                        response.status_code,
                        error_msg,
                    )
                    raise RuntimeError(
                        f"DeepSeek API error ({response.status_code}): {error_msg}"
                    )

                result = response.json()
                choices = result.get("choices") or []
                content = (
                    choices[0].get("message", {}).get("content", "")
                    if choices
                    else ""
                )
                if content:
                    return content

                last_error = RuntimeError("DeepSeek API returned empty content")
                if attempt >= attempt_count:
                    raise last_error
                logger.warning(
                    "DeepSeek returned empty content on attempt %s/%s; retrying",
                    attempt,
                    attempt_count,
                )
                time.sleep(self.retry_delay * attempt)
            except Exception as exc:
                last_error = exc
                if isinstance(exc, RuntimeError) and "empty content" in str(exc):
                    logger.warning(
                        "DeepSeek empty-content failure on final attempt %s/%s",
                        attempt,
                        attempt_count,
                    )
                else:
                    logger.exception("DeepSeek API request failed")
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("DeepSeek API request failed without a concrete error")

    def _format_api_error(self, response: httpx.Response) -> str:
        """Return a concise provider error without exposing credentials."""
        raw_text = str(getattr(response, "text", "") or "").strip()
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = str(error.get("message") or "").strip()
                error_type = str(error.get("type") or "").strip()
                code = str(error.get("code") or "").strip()
                parts = [part for part in [message, error_type, code] if part]
                if parts:
                    return " | ".join(parts)
        return raw_text[:500] if raw_text else "empty error response"
