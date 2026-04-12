"""Kimi LLM client with backward-compatible helpers and retry support."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any, Optional

import httpx


logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 422}
RETRYABLE_ERRORS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.TimeoutException,
)


@dataclass
class KIMIResponse:
    """Normalized response payload returned by chat-like operations."""

    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)


class RetryCallback:
    """Observer hooks for retry lifecycle events."""

    def on_retry(self, attempt: int, delay: float, error: Exception) -> None:
        return None

    def on_success(self, attempts: int) -> None:
        return None

    def on_failure(self, error: Exception) -> None:
        return None


class KimiClient:
    """Client for Kimi HTTP API or local kimi-cli proxy."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        model_name: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        use_cli: bool = False,
        timeout: float = 120.0,
        retry_enabled: bool = True,
        retry_max_retries: int = 2,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 8.0,
        retry_callback: RetryCallback | Any | None = None,
    ) -> None:
        env_api_key = os.getenv("KIMI_API_KEY")
        self.api_key = api_key or env_api_key
        if not self.api_key and not use_cli:
            raise ValueError("KIMI API key is required")

        self.base_url = base_url or os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        self.model_name = model_name or model or os.getenv("KIMI_MODEL_NAME", "moonshot-v1-8k")
        self.model = self.model_name
        self.max_tokens = int(os.getenv("KIMI_MAX_TOKENS", str(max_tokens)))
        self.temperature = float(os.getenv("KIMI_TEMPERATURE", str(temperature)))
        self.timeout = timeout
        self.use_cli = use_cli
        self.retry_enabled = str(os.getenv("KIMI_RETRY_ENABLED", str(retry_enabled))).lower() == "true"
        self.retry_max_retries = int(os.getenv("KIMI_RETRY_MAX_RETRIES", str(retry_max_retries)))
        self.retry_base_delay = float(os.getenv("KIMI_RETRY_BASE_DELAY", str(retry_base_delay)))
        self.retry_max_delay = float(os.getenv("KIMI_RETRY_MAX_DELAY", str(retry_max_delay)))
        self.retry_callback = retry_callback or RetryCallback()
        self._is_coding_agent = "kimi.com/coding" in self.base_url
        self._client: httpx.Client | None = None
        self._cli_available = self._check_cli_available()

    def _check_cli_available(self) -> bool:
        try:
            result = subprocess.run(
                ["kimi-cli", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url.rstrip("/"),
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        merged_messages = list(messages)
        if system_prompt:
            merged_messages = [{"role": "system", "content": system_prompt}, *merged_messages]

        if self._is_coding_agent:
            return "/messages", {
                "model": self.model_name,
                "messages": [msg for msg in merged_messages if msg.get("role") != "system"],
                "system": system_prompt or "",
                "temperature": self.temperature if temperature is None else temperature,
                "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
            }

        return "/chat/completions", {
            "model": self.model_name,
            "messages": merged_messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": self.max_tokens if max_tokens is None else max_tokens,
        }

    def _parse_response(self, response: Any) -> KIMIResponse:
        data = response.json()
        if self._is_coding_agent:
            content_items = data.get("content", [])
            content = "\n".join(item.get("text", "") for item in content_items if item.get("type") == "text").strip()
            if not content:
                raise ValueError("Invalid KIMI response")
            return KIMIResponse(
                content=content,
                model=data.get("model", self.model_name),
                usage=data.get("usage", {}),
                raw_response=data,
            )

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("Invalid KIMI response")
        content = choices[0].get("message", {}).get("content", "")
        if not content:
            raise ValueError("Invalid KIMI response")
        return KIMIResponse(
            content=content,
            model=data.get("model", self.model_name),
            usage=data.get("usage", {}),
            raw_response=data,
        )

    def _should_retry(self, error: Exception) -> bool:
        if isinstance(error, RETRYABLE_ERRORS):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            if status_code in NON_RETRYABLE_STATUS_CODES:
                return False
            return status_code in RETRYABLE_STATUS_CODES
        return False

    def _retry_delay(self, attempt: int) -> float:
        return min(self.retry_base_delay * (2 ** (attempt - 1)), self.retry_max_delay)

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> KIMIResponse:
        if self.use_cli and self._cli_available:
            return KIMIResponse(
                content=self.generate(messages=messages, temperature=temperature, max_tokens=max_tokens),
                model=self.model_name,
                usage={},
                raw_response={},
            )

        endpoint, payload = self._build_payload(
            messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        client = self._ensure_client()
        attempts = self.retry_max_retries + 1 if self.retry_enabled else 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = client.post(endpoint, json=payload)
                response.raise_for_status()
                result = self._parse_response(response)
                self.retry_callback.on_success(attempt)
                return result
            except Exception as error:  # noqa: BLE001
                last_error = error
                if not self.retry_enabled or attempt >= attempts or not self._should_retry(error):
                    self.retry_callback.on_failure(error)
                    raise
                delay = self._retry_delay(attempt)
                self.retry_callback.on_retry(attempt, delay, error)
                time.sleep(delay)

        self.retry_callback.on_failure(last_error or RuntimeError("unknown retry error"))
        raise last_error or RuntimeError("unknown retry error")

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if self.use_cli and self._cli_available:
            return self._generate_via_cli(messages, temperature, max_tokens)
        return self.chat(messages=messages, temperature=temperature, max_tokens=max_tokens).content

    def _generate_via_cli(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: float | None = None,
    ) -> str:
        del temperature, max_tokens
        prompt = self._build_prompt(messages)
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(prompt)
            prompt_path = handle.name
        try:
            result = subprocess.run(
                ["kimi-cli", "--print", "--quiet", "--prompt-file", prompt_path],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).parent.parent),
            )
            if result.returncode != 0:
                raise RuntimeError(f"kimi-cli failed: {result.stderr}")
            return self._extract_cli_response(result.stdout.strip())
        finally:
            Path(prompt_path).unlink(missing_ok=True)

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user").capitalize()
            parts.append(f"{role}: {msg.get('content', '')}")
        return "\n\n".join(parts)

    def read_file(self, file_path: str) -> str:
        try:
            path = Path(file_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
            if path.parent.exists():
                for candidate in path.parent.glob(f"{path.stem}.*"):
                    if candidate.suffix == ".md":
                        return candidate.read_text(encoding="utf-8")
            return ""
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read file %s: %s", file_path, exc)
            return ""

    def _extract_cli_response(self, output: str) -> str:
        if self._is_html_response(output):
            return ""
        return output.strip()

    def _is_html_response(self, text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False
        return normalized.startswith("<!doctype html") or normalized.startswith("<html")

    def generate_novel_content(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        context_text = json.dumps(context or {}, ensure_ascii=False, indent=2)
        return self.chat(
            system_prompt="You are a novel writing assistant.",
            messages=[{"role": "user", "content": f"{prompt}\n\nContext:\n{context_text}"}],
        ).content

    def generate_character_description(
        self,
        *,
        character_name: str,
        character_role: str,
        cultivation_realm: str,
        personality: str,
        appearance: str,
        background: str,
    ) -> str:
        return self.chat(
            system_prompt="You write concise but vivid novel character descriptions.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"角色名: {character_name}\n角色定位: {character_role}\n境界: {cultivation_realm}\n"
                        f"性格: {personality}\n外貌: {appearance}\n背景: {background}"
                    ),
                }
            ],
        ).content

    def generate_scene_visualization(
        self,
        *,
        scene_setting: str,
        time_of_day: str,
        mood: str,
        key_elements: list[str],
    ) -> str:
        return self.chat(
            system_prompt="You create vivid scene visualization prompts for fiction.",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"场景: {scene_setting}\n时间: {time_of_day}\n氛围: {mood}\n"
                        f"关键元素: {', '.join(key_elements)}"
                    ),
                }
            ],
        ).content

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "KimiClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        self.close()


KIMIClient = KimiClient
_kimi_client: KimiClient | None = None
_client_instance: KimiClient | None = None


def init_kimi_client(**kwargs: Any) -> KimiClient:
    """Initialize and memoize the process-wide Kimi client."""
    global _kimi_client, _client_instance
    _kimi_client = KimiClient(**kwargs)
    _client_instance = _kimi_client
    return _kimi_client


def get_kimi_client(
    api_key: str | None = None,
    base_url: str = "https://api.kimi.com/coding/v1",
    model: str = "kimi-k2.5",
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> KimiClient:
    """Get the global Kimi client instance."""
    global _client_instance, _kimi_client
    if _client_instance is None:
        _client_instance = KimiClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cli=True,
        )
        _kimi_client = _client_instance
    return _client_instance
