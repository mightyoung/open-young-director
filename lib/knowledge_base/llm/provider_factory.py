"""Unified LLM provider factory for configurable novel generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from llm.doubao_client import DoubaoClient
from llm.kimi_client import KimiClient
from llm.minimax_client import MiniMaxClient


SUPPORTED_PROVIDERS = ("kimi", "doubao", "minimax")


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
        prompt = (
            f"角色名: {character_name}\n"
            f"角色定位: {character_role}\n"
            f"境界: {cultivation_realm}\n"
            f"性格: {personality}\n"
            f"外貌: {appearance}\n"
            f"背景: {background}\n\n"
            "请输出简洁但具体的人物描述。"
        )
        return self.generate([{"role": "user", "content": prompt}])

    def generate_scene_visualization(
        self,
        *,
        scene_setting: str,
        time_of_day: str,
        mood: str,
        key_elements: list[str],
    ) -> str:
        prompt = (
            f"场景: {scene_setting}\n"
            f"时间: {time_of_day}\n"
            f"氛围: {mood}\n"
            f"关键元素: {', '.join(key_elements)}\n\n"
            "请输出适合小说衍生创作的场景可视化描述。"
        )
        return self.generate([{"role": "user", "content": prompt}])

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
