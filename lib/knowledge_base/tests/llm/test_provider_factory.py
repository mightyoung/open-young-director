"""Tests for configurable provider factory."""

import pytest

from young_writer.llm.provider_factory import build_llm_client


def test_build_doubao_client_normalizes_messages(monkeypatch):
    captured = {}

    class FakeDoubaoClient:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def generate(self, prompt, system=None, temperature=None, max_tokens=None):
            captured["call"] = {
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            return "ok"

    monkeypatch.setattr("llm.provider_factory.DoubaoClient", FakeDoubaoClient)

    client = build_llm_client(
        "doubao",
        {
            "api_key": "demo-key",
            "api_host": "https://ark.example.com/api/v3",
            "model_name": "doubao-text-pro",
            "temperature": 0.5,
            "max_tokens": 2048,
            "system_prompt": "默认 system",
        },
    )

    result = client.generate(
        [
            {"role": "system", "content": "系统提示"},
            {"role": "user", "content": "第一段"},
            {"role": "assistant", "content": "中间回复"},
            {"role": "user", "content": "第二段"},
        ],
        temperature=0.2,
        max_tokens=512,
    )

    assert result == "ok"
    assert captured["init"]["model"] == "doubao-text-pro"
    assert "USER:\n第一段" in captured["call"]["prompt"]
    assert "ASSISTANT:\n中间回复" in captured["call"]["prompt"]
    assert captured["call"]["system"] == "系统提示"
    assert captured["call"]["temperature"] == 0.2
    assert captured["call"]["max_tokens"] == 512
def test_build_deepseek_client(monkeypatch):
    captured = {}

    class FakeDeepSeekClient:
        def __init__(self, **kwargs):
            captured["init"] = kwargs
            self.model = kwargs["model"]

        def generate(self, messages, temperature=None, max_tokens=None):
            captured["call"] = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            return "deepseek-ok"

    monkeypatch.setattr("llm.provider_factory.DeepSeekClient", FakeDeepSeekClient)

    client = build_llm_client(
        "deepseek",
        {
            "api_key": "demo-key",
            "base_url": "https://api.deepseek.com",
            "model_name": "deepseek-v4-flash",
            "temperature": 0.6,
            "max_tokens": 4096,
        },
    )

    result = client.generate(
        [{"role": "user", "content": "测试"}],
        temperature=0.2,
        max_tokens=512,
    )

    assert result == "deepseek-ok"
    assert client.provider_name == "deepseek"
    assert client.model_name == "deepseek-v4-flash"
    assert captured["init"]["base_url"] == "https://api.deepseek.com"
    assert captured["call"]["messages"][0]["content"] == "测试"


def test_selected_provider_missing_credentials_fails_fast(monkeypatch):
    monkeypatch.delenv("DOUBAO_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Doubao provider requires DOUBAO_API_KEY"):
        build_llm_client(
            "doubao",
            {
                "api_key": "",
                "api_host": "https://ark.example.com/api/v3",
                "model_name": "doubao-text-pro",
            },
        )


def test_deepseek_provider_missing_credentials_fails_fast(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DeepSeek provider requires DEEPSEEK_API_KEY"):
        build_llm_client(
            "deepseek",
            {
                "api_key": "",
                "base_url": "https://api.deepseek.com",
                "model_name": "deepseek-v4-flash",
            },
        )
