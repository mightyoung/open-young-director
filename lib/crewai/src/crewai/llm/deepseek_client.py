"""DeepSeek LLM adapter for the young-writer novel generation pipeline.

Provides a lightweight httpx-based client for DeepSeek's OpenAI-compatible
chat completion API — no openai SDK dependency required.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL: str = "https://api.deepseek.com"
_DEFAULT_MODEL: str = "deepseek-chat"
_DEFAULT_TIMEOUT: float = 60.0
_MAX_RETRIES: int = 3
_RETRY_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

# Rough average bytes-per-token for UTF-8 text (conservative estimate).
_BYTES_PER_TOKEN: float = 3.5


class DeepSeekAPIError(Exception):
    """Raised when the DeepSeek API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"DeepSeek API error {status_code}: {message}")
        self.status_code = status_code


class DeepSeekRateLimitError(DeepSeekAPIError):
    """Raised when the API signals rate limiting (HTTP 429)."""


class DeepSeekTimeoutError(Exception):
    """Raised when a request exceeds the configured timeout."""


@dataclass
class DeepSeekClient:
    """Thin, httpx-based adapter for DeepSeek's OpenAI-compatible chat API.

    Constructor args override env vars ``DEEPSEEK_API_KEY`` / ``DEEPSEEK_BASE_URL``.
    """

    api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.environ.get("DEEPSEEK_BASE_URL", _DEFAULT_BASE_URL)
    )
    model: str = _DEFAULT_MODEL
    api_base: str | None = None
    api_version: str | None = None
    temperature: float | None = None
    max_tokens: int | float | None = None
    max_completion_tokens: int | None = None
    logprobs: int | None = None
    timeout: float = _DEFAULT_TIMEOUT
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    top_p: float | None = None
    n: int | None = None
    stop: str | list[str] | None = None
    logit_bias: dict[int, float] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None
    top_logprobs: int | None = None
    callbacks: list[Any] | None = None
    reasoning_effort: str | None = None
    stream: bool = False
    prefer_upload: bool = False
    additional_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError(
                "DeepSeek API key is required. "
                "Pass api_key= or set DEEPSEEK_API_KEY in the environment."
            )
        self.base_url = self.base_url.rstrip("/")
        if self.api_base is None:
            self.api_base = self.base_url

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def set_seed(self, seed: int) -> None:
        """Set a deterministic seed that is forwarded with every request."""
        self.seed = seed

    def count_tokens(self, text: str) -> int:
        """Estimate token count using a bytes-per-token heuristic (no API call)."""
        return max(1, int(len(text.encode("utf-8")) / _BYTES_PER_TOKEN))

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Send a synchronous chat completion request with exponential-backoff retry."""
        payload = self._build_payload(messages, max_tokens, temperature)
        last_error: Exception = RuntimeError("No attempts made")

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                return self._parse_response(response)
            except (DeepSeekRateLimitError, DeepSeekTimeoutError, httpx.TimeoutException) as exc:
                last_error = exc
                if delay is None:
                    break
                logger.warning(
                    "DeepSeek request failed (attempt %d/%d): %s — retrying in %.0fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)
            except DeepSeekAPIError:
                raise

        raise last_error

    async def achat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Async variant of :meth:`chat`; same retry semantics via ``httpx.AsyncClient``."""
        payload = self._build_payload(messages, max_tokens, temperature)
        last_error: Exception = RuntimeError("No attempts made")

        for attempt, delay in enumerate((*_RETRY_DELAYS, None)):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._headers(),
                        json=payload,
                    )
                return self._parse_response(response)
            except (DeepSeekRateLimitError, DeepSeekTimeoutError, httpx.TimeoutException) as exc:
                last_error = exc
                if delay is None:
                    break
                logger.warning(
                    "DeepSeek async request failed (attempt %d/%d): %s — retrying in %.0fs",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            except DeepSeekAPIError:
                raise

        raise last_error

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        return payload

    def _parse_response(self, response: httpx.Response) -> str:
        if response.status_code == 429:
            raise DeepSeekRateLimitError(429, response.text)
        if response.status_code == 408 or response.status_code == 504:
            raise DeepSeekTimeoutError(
                f"Gateway timeout from DeepSeek (HTTP {response.status_code})"
            )
        if response.status_code >= 500:
            raise DeepSeekAPIError(response.status_code, response.text)
        if response.status_code >= 400:
            raise DeepSeekAPIError(response.status_code, response.text)

        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError) as exc:
            raise DeepSeekAPIError(
                response.status_code,
                f"Unexpected response shape: {data}",
            ) from exc
