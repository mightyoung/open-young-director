"""Unified LLM provider factory for configurable novel generation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

from young_writer.llm.deepseek_client import DeepSeekClient
from young_writer.llm.doubao_client import DoubaoClient
from young_writer.llm.kimi_client import KimiClient
from young_writer.llm.minimax_client import MiniMaxClient


SUPPORTED_PROVIDERS = ("kimi", "doubao", "minimax", "deepseek")


def _require_provider_credentials(provider: str, config: dict[str, Any]) -> None:
    """Fail before generation when the selected provider cannot authenticate."""
    if provider == "kimi":
        if config.get("api_key") or config.get("use_cli") or os.getenv("KIMI_API_KEY"):
            return
        raise ValueError("Kimi provider requires KIMI_API_KEY or use_cli=true")
    if provider == "doubao" and not (config.get("api_key") or os.getenv("DOUBAO_API_KEY")):
        raise ValueError("Doubao provider requires DOUBAO_API_KEY")
    if provider == "minimax" and not (
        config.get("api_key") or os.getenv("MINIMAX_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    ):
        raise ValueError("MiniMax provider requires MINIMAX_API_KEY or ANTHROPIC_API_KEY")
    if provider == "deepseek" and not (config.get("api_key") or os.getenv("DEEPSEEK_API_KEY")):
        raise ValueError("DeepSeek provider requires DEEPSEEK_API_KEY")


@dataclass
class UnifiedLLMClient:
    """Normalize provider interfaces used across the novel generation flow."""

    provider_name: str
    client: Any
    model_name: str
    system_prompt: str = ""

    def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if self.provider_name == "doubao":
            system_prompt, prompt = self._flatten_messages(messages)
            return self.client.generate(
                prompt=prompt,
                system=system_prompt or self.system_prompt or None,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return self.client.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def chat(self, prompt: str | None = None, messages: list[dict[str, Any]] | None = None) -> str:
        payload = messages or [{"role": "user", "content": prompt or ""}]
        return self.generate(payload)

    def read_file(self, file_path: str) -> str:
        if hasattr(self.client, "read_file"):
            return self.client.read_file(file_path)
        return ""

    def generate_novel_content(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        context_lines = []
        if context:
            context_lines.append("上下文:")
            for key, value in context.items():
                context_lines.append(f"- {key}: {value}")
        full_prompt = "\n".join([prompt, *context_lines]).strip()
        return self.generate([{"role": "user", "content": full_prompt}])
    def _flatten_messages(self, messages: list[dict[str, Any]]) -> tuple[str, str]:
        system_parts: list[str] = []
        prompt_parts: list[str] = []
        for message in messages:
            role = str(message.get("role", "user"))
            content = self._stringify_content(message.get("content", ""))
            if role == "system":
                system_parts.append(content)
                continue
            prompt_parts.append(f"{role.upper()}:\n{content}")
        return "\n\n".join(system_parts).strip(), "\n\n".join(prompt_parts).strip()

    def _stringify_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                else:
                    parts.append(str(block))
            return "\n".join(part for part in parts if part)
        return str(content)


def build_llm_client(provider_name: str, config: dict[str, Any]) -> UnifiedLLMClient:
    """Build a normalized provider client from persisted config."""
    provider = provider_name.lower().strip()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider_name}")

    model_name = str(config.get("model_name") or config.get("model") or "")
    temperature = float(config.get("temperature", 0.7))
    max_tokens = int(config.get("max_tokens", 8192))
    _require_provider_credentials(provider, config)

    if provider == "kimi":
        client = KimiClient(
            api_key=config.get("api_key") or None,
            base_url=config.get("base_url") or None,
            model_name=model_name or None,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cli=bool(config.get("use_cli", False)),
        )
        resolved_model = model_name or getattr(client, "model_name", getattr(client, "model", ""))
        return UnifiedLLMClient(provider_name=provider, client=client, model_name=resolved_model)

    if provider == "doubao":
        client = DoubaoClient(
            api_key=config.get("api_key") or None,
            api_host=config.get("api_host") or None,
            model=model_name or None,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        resolved_model = model_name or getattr(client, "model", "")
        return UnifiedLLMClient(
            provider_name=provider,
            client=client,
            model_name=resolved_model,
            system_prompt=str(config.get("system_prompt", "")),
        )

    if provider == "deepseek":
        client = DeepSeekClient(
            api_key=config.get("api_key") or None,
            base_url=config.get("base_url") or None,
            model=model_name or None,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        resolved_model = model_name or getattr(client, "model", "")
        return UnifiedLLMClient(
            provider_name=provider,
            client=client,
            model_name=resolved_model,
            system_prompt=str(config.get("system_prompt", "")),
        )

    client = MiniMaxClient(
        api_key=config.get("api_key") or None,
        base_url=config.get("base_url") or None,
        model=model_name or None,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=str(config.get("system_prompt", "")) or None,
    )
    resolved_model = model_name or getattr(client, "model", "")
    return UnifiedLLMClient(
        provider_name=provider,
        client=client,
        model_name=resolved_model,
        system_prompt=str(config.get("system_prompt", "")),
    )
