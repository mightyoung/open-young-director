"""Tests for KIMIClient."""

import os
import time
from unittest.mock import MagicMock, Mock, patch, call

import httpx

import pytest

from llm.kimi_client import (
    KIMIClient,
    KIMIResponse,
    RetryCallback,
    RETRYABLE_ERRORS,
    RETRYABLE_STATUS_CODES,
    NON_RETRYABLE_STATUS_CODES,
)


class TestKIMIClientInit:
    """Test KIMIClient initialization."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        client = KIMIClient(api_key="test_key_123")

        assert client.api_key == "test_key_123"
        assert client.model_name == "moonshot-v1-8k"
        assert client.max_tokens == 8192
        assert client.temperature == 0.7

    def test_init_without_api_key_raises(self):
        """Test that initialization without API key raises ValueError."""
        def mock_getenv(key, default=None):
            if key == "KIMI_API_KEY":
                return None
            return default
        with patch("llm.kimi_client.os.getenv", side_effect=mock_getenv):
            with pytest.raises(ValueError, match="KIMI API key is required"):
                KIMIClient()

    def test_init_detects_coding_agent_url(self):
        """Test that initialization detects coding agent URL."""
        client = KIMIClient(
            api_key="test_key",
            base_url="https://api.kimi.com/coding",
        )

        assert client._is_coding_agent is True
        assert client.base_url == "https://api.kimi.com/coding"

    def test_init_standard_api_url(self):
        """Test initialization with standard API URL."""
        client = KIMIClient(
            api_key="test_key",
            base_url="https://api.moonshot.cn/v1",
        )

        assert client._is_coding_agent is False

    def test_init_env_overrides(self):
        """Test that environment variables override defaults."""
        env_vars = {
            "KIMI_API_KEY": "env_key",
            "KIMI_BASE_URL": "https://custom.api.com",
            "KIMI_MODEL_NAME": "custom-model",
            "KIMI_MAX_TOKENS": "16384",
            "KIMI_TEMPERATURE": "0.9",
            "KIMI_RETRY_ENABLED": "true",
            "KIMI_RETRY_MAX_RETRIES": "3",
            "KIMI_RETRY_BASE_DELAY": "1.0",
            "KIMI_RETRY_MAX_DELAY": "30.0",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            client = KIMIClient()

            assert client.api_key == "env_key"
            assert client.base_url == "https://custom.api.com"
            assert client.model_name == "custom-model"
            assert client.max_tokens == 16384
            assert client.temperature == 0.9


class TestKIMIClientChat:
    """Test chat method."""

    def test_chat_basic(self):
        """Test basic chat call with standard API."""
        client = KIMIClient(api_key="test_key", base_url="https://api.moonshot.cn/v1")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "测试回复"}}],
            "model": "moonshot-v1-8k",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            response = client.chat(messages=[{"role": "user", "content": "你好"}])

            assert isinstance(response, KIMIResponse)
            assert response.content == "测试回复"
            assert response.model == "moonshot-v1-8k"
            assert response.usage["total_tokens"] == 30

    def test_chat_with_system_prompt(self):
        """Test chat with system prompt."""
        client = KIMIClient(api_key="test_key", base_url="https://api.moonshot.cn/v1")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "回复"}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            client.chat(
                messages=[{"role": "user", "content": "问题"}],
                system_prompt="你是助手",
            )

            # Verify system message was prepended
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            messages = payload["messages"]
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "你是助手"

    def test_chat_with_temperature_override(self):
        """Test chat with temperature override."""
        client = KIMIClient(api_key="test_key", temperature=0.7)

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "回复"}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            client.chat(messages=[{"role": "user", "content": "问题"}], temperature=0.5)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["temperature"] == 0.5

    def test_chat_with_max_tokens_override(self):
        """Test chat with max_tokens override."""
        client = KIMIClient(api_key="test_key", max_tokens=8192)

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "回复"}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            client.chat(messages=[{"role": "user", "content": "问题"}], max_tokens=16384)

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["max_tokens"] == 16384

    def test_chat_invalid_response_raises(self):
        """Test that invalid response raises ValueError."""
        client = KIMIClient(api_key="test_key")

        mock_response = Mock()
        mock_response.json.return_value = {"choices": []}

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            with pytest.raises(ValueError, match="Invalid KIMI response"):
                client.chat(messages=[{"role": "user", "content": "问题"}])

    def test_chat_http_error_raises(self):
        """Test that HTTP errors are propagated."""
        client = KIMIClient(api_key="test_key")

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=Mock(status_code=500),
            )

            with pytest.raises(httpx.HTTPStatusError):
                client.chat(messages=[{"role": "user", "content": "问题"}])


class TestKIMIClientCodingAgent:
    """Test KIMIClient with Coding Agent API."""

    def test_chat_coding_agent_format(self):
        """Test chat uses Anthropic format for coding agent API."""
        client = KIMIClient(
            api_key="test_key",
            base_url="https://api.kimi.com/coding",
        )

        mock_response = Mock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Coding agent reply"}],
            "model": "kimi-coder",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            response = client.chat(messages=[{"role": "user", "content": "写代码"}])

            assert response.content == "Coding agent reply"

            # Verify /messages endpoint was called
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/messages"


class TestGenerateNovelContent:
    """Test generate_novel_content method."""

    def test_generate_novel_content(self):
        """Test novel content generation."""
        client = KIMIClient(api_key="test_key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "生成的玄幻小说内容..."}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            result = client.generate_novel_content(
                prompt="写一个修仙世界的场景",
                context={"genre": "玄幻"},
            )

            assert "生成的玄幻小说内容" in result

            # Verify system prompt was used
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            system_msg = payload["messages"][0]
            assert system_msg["role"] == "system"
            assert "novel" in system_msg["content"].lower()


class TestGenerateCharacterDescription:
    """Test generate_character_description method."""

    def test_generate_character_description(self):
        """Test character description generation."""
        client = KIMIClient(api_key="test_key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "林轩是一个..."}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            result = client.generate_character_description(
                character_name="林轩",
                character_role="protagonist",
                cultivation_realm="筑基境",
                personality="坚韧不拔",
                appearance="清秀少年",
                background="废物逆袭",
            )

            assert "林轩" in result

            # Verify prompt was sent
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            user_msg = payload["messages"][1]  # After system prompt
            assert "林轩" in user_msg["content"]
            assert "筑基境" in user_msg["content"]


class TestGenerateSceneVisualization:
    """Test generate_scene_visualization method."""

    def test_generate_scene_visualization(self):
        """Test scene visualization generation."""
        client = KIMIClient(api_key="test_key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "仙山云雾缭绕..."}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            result = client.generate_scene_visualization(
                scene_setting="仙山之巅",
                time_of_day="黎明",
                mood="神秘",
                key_elements=["云雾", "古松", "石碑"],
            )

            assert "仙山" in result

            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            user_msg = payload["messages"][1]
            assert "仙山之巅" in user_msg["content"]
            assert "黎明" in user_msg["content"]


class TestKIMIClientContextManager:
    """Test context manager functionality."""

    def test_context_manager(self):
        """Test using client as context manager."""
        client = KIMIClient(api_key="test_key")

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "回复"}}],
            "model": "moonshot-v1-8k",
            "usage": {},
        }

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = mock_response

            with client as c:
                result = c.chat(messages=[{"role": "user", "content": "测试"}])
                assert result.content == "回复"


class TestKIMIClientClose:
    """Test close method."""

    def test_close_client(self):
        """Test closing the HTTP client."""
        client = KIMIClient(api_key="test_key")

        mock_http_client = MagicMock()
        client._client = mock_http_client

        client.close()

        mock_http_client.close.assert_called_once()
        assert client._client is None

    def test_close_when_not_initialized(self):
        """Test closing when client is not initialized."""
        client = KIMIClient(api_key="test_key")
        assert client._client is None

        # Should not raise
        client.close()


class TestKIMIResponse:
    """Test KIMIResponse dataclass."""

    def test_kimi_response_creation(self):
        """Test creating KIMIResponse."""
        response = KIMIResponse(
            content="测试内容",
            model="moonshot-v1-8k",
            usage={"total_tokens": 100},
            raw_response={"raw": "data"},
        )

        assert response.content == "测试内容"
        assert response.model == "moonshot-v1-8k"
        assert response.usage["total_tokens"] == 100
        assert response.raw_response["raw"] == "data"


class TestInitKimiClient:
    """Test init_kimi_client factory function."""

    def test_init_kimi_client_basic(self):
        """Test init_kimi_client factory."""
        from llm.kimi_client import init_kimi_client, _kimi_client

        # Reset singleton
        import llm.kimi_client

        llm.kimi_client._kimi_client = None

        client = init_kimi_client(
            api_key="factory_key",
            model_name="test-model",
        )

        assert client.api_key == "factory_key"
        assert client.model_name == "test-model"
        assert llm.kimi_client._kimi_client is client

        # Cleanup
        llm.kimi_client._kimi_client = None


class TestRetryCallback:
    """Test RetryCallback class."""

    def test_on_retry_default_noop(self):
        """Test that default on_retry does nothing."""
        cb = RetryCallback()
        # Should not raise
        cb.on_retry(1, 1.0, Exception("test"))
        cb.on_success(1)
        cb.on_failure(Exception("test"))


class TestKIMIClientRetry:
    """Test retry functionality in KIMIClient."""

    def test_retry_on_connect_error(self):
        """Test that connection errors trigger retry and eventually succeed."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        # First two calls fail, third succeeds
        mock_responses = [
            Mock(side_effect=httpx.ConnectError("Connection refused")),
            Mock(side_effect=httpx.ConnectError("Connection refused")),
            Mock(json=lambda: {"choices": [{"message": {"content": "成功"}}], "model": "test", "usage": {}}),
        ]

        with patch.object(client, "_client") as mock_client:
            # Make post return different values on each call
            mock_response_fail = Mock()
            mock_response_fail.side_effect = httpx.ConnectError("Connection refused")

            mock_response_success = Mock()
            mock_response_success.json.return_value = {"choices": [{"message": {"content": "成功"}}], "model": "test", "usage": {}}
            mock_response_success.raise_for_status = Mock()

            mock_client.post.side_effect = [
                httpx.ConnectError("Connection refused"),
                httpx.ConnectError("Connection refused"),
                mock_response_success,
            ]

            start = time.time()
            response = client.chat(messages=[{"role": "user", "content": "test"}])
            elapsed = time.time() - start

            # Should have succeeded on third attempt
            assert response.content == "成功"
            # Should have slept between retries (at least base_delay)
            assert elapsed >= 0.02  # 2 * 0.01 base delay

    def test_no_retry_on_401(self):
        """Test that 401 errors are not retried."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        error_response = Mock()
        error_response.status_code = 401

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Unauthorized",
                request=Mock(),
                response=error_response,
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.chat(messages=[{"role": "user", "content": "test"}])

            assert exc_info.value.response.status_code == 401
            # Should only be called once (no retries)
            assert mock_client.post.call_count == 1

    def test_no_retry_on_403(self):
        """Test that 403 errors are not retried."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        error_response = Mock()
        error_response.status_code = 403

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Forbidden",
                request=Mock(),
                response=error_response,
            )

            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.chat(messages=[{"role": "user", "content": "test"}])

            assert exc_info.value.response.status_code == 403
            assert mock_client.post.call_count == 1

    def test_retry_on_429_then_success(self):
        """Test that 429 rate limit triggers retry and eventually succeeds."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        error_response_429 = Mock()
        error_response_429.status_code = 429

        success_response = Mock()
        success_response.json.return_value = {"choices": [{"message": {"content": "成功"}}], "model": "test", "usage": {}}
        success_response.raise_for_status = Mock()

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = [
                httpx.HTTPStatusError("Rate limited", request=Mock(), response=error_response_429),
                success_response,
            ]

            response = client.chat(messages=[{"role": "user", "content": "test"}])

            assert response.content == "成功"
            assert mock_client.post.call_count == 2

    def test_retry_on_500_then_success(self):
        """Test that 500 server error triggers retry and eventually succeeds."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        error_response_500 = Mock()
        error_response_500.status_code = 500

        success_response = Mock()
        success_response.json.return_value = {"choices": [{"message": {"content": "成功"}}], "model": "test", "usage": {}}
        success_response.raise_for_status = Mock()

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = [
                httpx.HTTPStatusError("Server error", request=Mock(), response=error_response_500),
                success_response,
            ]

            response = client.chat(messages=[{"role": "user", "content": "test"}])

            assert response.content == "成功"
            assert mock_client.post.call_count == 2

    def test_max_retries_exhausted_raises(self):
        """Test that after max retries, the last exception is raised."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.01)

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError("Always fails")

            with pytest.raises(httpx.ConnectError):
                client.chat(messages=[{"role": "user", "content": "test"}])

            # Should have tried 3 times (max_retries + 1)
            assert mock_client.post.call_count == 3

    def test_retry_callback_on_retry(self):
        """Test that RetryCallback.on_retry is called during retries."""
        callback = Mock()
        client = KIMIClient(
            api_key="test_key",
            retry_max_retries=2,
            retry_base_delay=0.01,
            retry_callback=callback,
        )

        with patch.object(client, "_client") as mock_client:
            # First 2 attempts fail, third succeeds
            mock_client.post.side_effect = [
                httpx.ConnectError("Fail 1"),
                httpx.ConnectError("Fail 2"),
                Mock(
                    json=lambda: {"choices": [{"message": {"content": "OK"}}], "model": "test", "usage": {}},
                    raise_for_status=Mock(),
                ),
            ]

            response = client.chat(messages=[{"role": "user", "content": "test"}])

            assert response.content == "OK"
            # on_retry called for attempts 1 and 2 (0-indexed: attempts 0 and 1)
            assert callback.on_retry.call_count == 2
            callback.on_success.assert_called_once_with(3)

    def test_retry_callback_on_success(self):
        """Test that RetryCallback.on_success is called after successful request."""
        callback = Mock()
        client = KIMIClient(
            api_key="test_key",
            retry_max_retries=1,
            retry_base_delay=0.01,
            retry_callback=callback,
        )

        success_response = Mock()
        success_response.json.return_value = {"choices": [{"message": {"content": "OK"}}], "model": "test", "usage": {}}
        success_response.raise_for_status = Mock()

        with patch.object(client, "_client") as mock_client:
            mock_client.post.return_value = success_response

            response = client.chat(messages=[{"role": "user", "content": "test"}])

            assert response.content == "OK"
            callback.on_success.assert_called_once_with(1)
            callback.on_failure.assert_not_called()

    def test_retry_disabled(self):
        """Test that when retry is disabled, errors propagate immediately."""
        client = KIMIClient(api_key="test_key", retry_enabled=False)

        with patch.object(client, "_client") as mock_client:
            # Use HTTPStatusError with status code that would normally be retried
            error_response = Mock()
            error_response.status_code = 500
            mock_client.post.side_effect = httpx.HTTPStatusError(
                "Server error",
                request=Mock(),
                response=error_response,
            )

            with pytest.raises(httpx.HTTPStatusError):
                client.chat(messages=[{"role": "user", "content": "test"}])

            # Should only be called once (no retries)
            assert mock_client.post.call_count == 1

    def test_retry_exponential_backoff_timing(self):
        """Test that exponential backoff delays increase correctly."""
        client = KIMIClient(api_key="test_key", retry_max_retries=2, retry_base_delay=0.05)

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError("Always fails")

            start = time.time()
            with pytest.raises(httpx.ConnectError):
                client.chat(messages=[{"role": "user", "content": "test"}])
            elapsed = time.time() - start

            # Expected delays: 0.05, 0.10 (2^1 * 0.05)
            # Total sleep should be >= 0.15
            assert elapsed >= 0.15
            assert mock_client.post.call_count == 3

    def test_retry_max_delay_cap(self):
        """Test that retry delay is capped at max_delay."""
        client = KIMIClient(
            api_key="test_key",
            retry_max_retries=2,
            retry_base_delay=1.0,
            retry_max_delay=1.5,
        )

        with patch.object(client, "_client") as mock_client:
            mock_client.post.side_effect = httpx.ConnectError("Always fails")

            start = time.time()
            with pytest.raises(httpx.ConnectError):
                client.chat(messages=[{"role": "user", "content": "test"}])
            elapsed = time.time() - start

            # With cap of 1.5, total sleep should be 1.0 + 1.5 = 2.5 (not 1.0 + 2.0 = 3.0)
            assert elapsed >= 2.4
            assert elapsed < 3.0


class TestRetryConstants:
    """Test retry-related constants."""

    def test_retryable_status_codes(self):
        """Test that expected status codes are retryable."""
        assert 429 in RETRYABLE_STATUS_CODES
        assert 500 in RETRYABLE_STATUS_CODES
        assert 502 in RETRYABLE_STATUS_CODES
        assert 503 in RETRYABLE_STATUS_CODES
        assert 504 in RETRYABLE_STATUS_CODES

    def test_non_retryable_status_codes(self):
        """Test that expected status codes are non-retryable."""
        assert 401 in NON_RETRYABLE_STATUS_CODES
        assert 403 in NON_RETRYABLE_STATUS_CODES
        assert 404 in NON_RETRYABLE_STATUS_CODES
        assert 422 in NON_RETRYABLE_STATUS_CODES

    def test_retryable_errors(self):
        """Test that expected errors are retryable."""
        assert issubclass(httpx.ConnectError, RETRYABLE_ERRORS) or any(
            issubclass(httpx.ConnectError, e) for e in RETRYABLE_ERRORS
        )

