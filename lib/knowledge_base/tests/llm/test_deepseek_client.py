"""Tests for DeepSeekClient."""

from unittest.mock import Mock, patch

import pytest

from young_writer.llm.deepseek_client import DeepSeekClient


def test_deepseek_client_generates_chat_completion():
    client = DeepSeekClient(api_key="test-key")

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "生成成功"}}],
        "model": "deepseek-v4-flash",
    }

    with patch("llm.deepseek_client.httpx.Client") as client_cls:
        http_client = client_cls.return_value.__enter__.return_value
        http_client.post.return_value = mock_response

        result = client.generate(
            [{"role": "user", "content": "写一段小说"}],
            temperature=0.3,
            max_tokens=1024,
        )

    assert result == "生成成功"
    post_kwargs = http_client.post.call_args.kwargs
    assert post_kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert post_kwargs["json"]["model"] == "deepseek-v4-flash"
    assert post_kwargs["json"]["temperature"] == 0.3
    assert post_kwargs["json"]["max_tokens"] == 1024


def test_deepseek_client_raises_on_api_error():
    client = DeepSeekClient(api_key="test-key")

    mock_response = Mock()
    mock_response.status_code = 401
    mock_response.text = "unauthorized"

    with patch("llm.deepseek_client.httpx.Client") as client_cls:
        http_client = client_cls.return_value.__enter__.return_value
        http_client.post.return_value = mock_response

        with pytest.raises(RuntimeError, match="DeepSeek API error"):
            client.generate([{"role": "user", "content": "test"}])


def test_deepseek_client_formats_insufficient_balance_error():
    client = DeepSeekClient(api_key="test-key")
    mock_response = Mock()
    mock_response.status_code = 402
    mock_response.text = (
        '{"error":{"message":"Insufficient Balance","type":"unknown_error",'
        '"param":null,"code":"invalid_request_error"}}'
    )
    mock_response.json.return_value = {
        "error": {
            "message": "Insufficient Balance",
            "type": "unknown_error",
            "code": "invalid_request_error",
        }
    }

    with patch("llm.deepseek_client.httpx.Client") as client_cls:
        http_client = client_cls.return_value.__enter__.return_value
        http_client.post.return_value = mock_response

        with pytest.raises(RuntimeError) as exc_info:
            client.generate([{"role": "user", "content": "test"}])

    message = str(exc_info.value)
    assert "DeepSeek API error (402)" in message
    assert "Insufficient Balance" in message
    assert "invalid_request_error" in message


def test_deepseek_client_retries_on_empty_content():
    client = DeepSeekClient(api_key="test-key", empty_content_retries=2, retry_delay=0)

    empty_response = Mock()
    empty_response.status_code = 200
    empty_response.json.return_value = {
        "choices": [{"message": {"content": ""}}],
        "model": "deepseek-v4-flash",
    }

    ok_response = Mock()
    ok_response.status_code = 200
    ok_response.json.return_value = {
        "choices": [{"message": {"content": "重试成功"}}],
        "model": "deepseek-v4-flash",
    }

    with patch("llm.deepseek_client.httpx.Client") as client_cls:
        http_client = client_cls.return_value.__enter__.return_value
        http_client.post.side_effect = [empty_response, ok_response]

        result = client.generate([{"role": "user", "content": "test"}])

    assert result == "重试成功"
    assert http_client.post.call_count == 2


def test_deepseek_client_raises_after_empty_content_retries_exhausted():
    client = DeepSeekClient(api_key="test-key", empty_content_retries=1, retry_delay=0)

    empty_response = Mock()
    empty_response.status_code = 200
    empty_response.json.return_value = {
        "choices": [{"message": {"content": ""}}],
        "model": "deepseek-v4-flash",
    }

    with patch("llm.deepseek_client.httpx.Client") as client_cls:
        http_client = client_cls.return_value.__enter__.return_value
        http_client.post.side_effect = [empty_response, empty_response]

        with pytest.raises(RuntimeError, match="empty content"):
            client.generate([{"role": "user", "content": "test"}])

    assert http_client.post.call_count == 2
