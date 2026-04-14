"""Tests for configurable provider factory."""

from llm.provider_factory import build_llm_client


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


def test_build_minimax_client_supports_helper_methods(monkeypatch):
    class FakeMiniMaxClient:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]

        def generate(self, messages, temperature=None, max_tokens=None):
            return f"{messages[0]['content']}|{temperature}|{max_tokens}"

    monkeypatch.setattr("llm.provider_factory.MiniMaxClient", FakeMiniMaxClient)

    client = build_llm_client(
        "minimax",
        {
            "api_key": "demo-key",
            "base_url": "https://api.example.com/anthropic",
            "model_name": "MiniMax-M2.5",
            "temperature": 0.9,
            "max_tokens": 8192,
            "system_prompt": "",
        },
    )

    result = client.generate_scene_visualization(
        scene_setting="古城雨夜",
        time_of_day="夜晚",
        mood="压抑",
        key_elements=["旧城门", "火把"],
    )

    assert "古城雨夜" in result
