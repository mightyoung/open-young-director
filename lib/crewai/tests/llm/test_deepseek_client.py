"""Unit tests for DeepSeek LLM client.

Tests cover initialization, API communication, error handling, retry logic,
and token counting using mocks to avoid external API calls.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest import mock

import httpx
import pytest

# Import deepseek_client directly from file to avoid circular imports
spec = importlib.util.spec_from_file_location(
    "crewai.llm.deepseek_client",
    Path(__file__).parent.parent.parent / "src" / "crewai" / "llm" / "deepseek_client.py",
)
deepseek_module = importlib.util.module_from_spec(spec)
sys.modules["crewai.llm.deepseek_client"] = deepseek_module
spec.loader.exec_module(deepseek_module)

DeepSeekAPIError = deepseek_module.DeepSeekAPIError
DeepSeekClient = deepseek_module.DeepSeekClient
DeepSeekRateLimitError = deepseek_module.DeepSeekRateLimitError
DeepSeekTimeoutError = deepseek_module.DeepSeekTimeoutError


class TestDeepSeekClientInit:
    """Tests for DeepSeekClient initialization."""

    def test_init_requires_api_key(self):
        """Test that creating DeepSeekClient without api_key raises ValueError."""
        with pytest.raises(ValueError, match="DeepSeek API key is required"):
            DeepSeekClient(api_key="")

    def test_init_requires_api_key_from_env(self):
        """Test that missing env var DEEPSEEK_API_KEY raises ValueError."""
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="DeepSeek API key is required"):
                DeepSeekClient()

    def test_init_from_env(self):
        """Test that DEEPSEEK_API_KEY env var is used."""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test_key_123"}):
            client = DeepSeekClient()
            assert client.api_key == "test_key_123"

    def test_init_api_key_explicit_overrides_env(self):
        """Test that explicit api_key parameter overrides env var."""
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env_key"}):
            client = DeepSeekClient(api_key="explicit_key")
            assert client.api_key == "explicit_key"

    def test_init_base_url_from_env(self):
        """Test that DEEPSEEK_BASE_URL env var is used."""
        with mock.patch.dict(
            os.environ,
            {"DEEPSEEK_API_KEY": "test_key", "DEEPSEEK_BASE_URL": "https://custom.api.com"},
        ):
            client = DeepSeekClient()
            assert client.base_url == "https://custom.api.com"

    def test_init_base_url_explicit_overrides_env(self):
        """Test that explicit base_url parameter overrides env var."""
        with mock.patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "test_key",
                "DEEPSEEK_BASE_URL": "https://env.api.com",
            },
        ):
            client = DeepSeekClient(base_url="https://explicit.api.com")
            assert client.base_url == "https://explicit.api.com"

    def test_init_defaults(self):
        """Test default values for model, timeout, and seed."""
        client = DeepSeekClient(api_key="test_key")
        assert client.model == "deepseek-chat"
        assert client.timeout == 60.0
        assert client.seed is None

    def test_init_custom_model_and_timeout(self):
        """Test custom model and timeout values."""
        client = DeepSeekClient(
            api_key="test_key",
            model="custom-model",
            timeout=30.0,
        )
        assert client.model == "custom-model"
        assert client.timeout == 30.0

    def test_init_accepts_compatibility_kwargs(self):
        """Test that compatibility kwargs from LLM fallback are accepted."""
        client = DeepSeekClient(
            api_key="test_key",
            api_base="https://compat.example.com",
            callbacks=[],
            temperature=0.5,
        )
        assert client.api_base == "https://compat.example.com"
        assert client.callbacks == []
        assert client.temperature == 0.5

    def test_base_url_trailing_slash_stripped(self):
        """Test that trailing slashes in base_url are removed."""
        client = DeepSeekClient(
            api_key="test_key",
            base_url="https://api.deepseek.com/",
        )
        assert client.base_url == "https://api.deepseek.com"

    def test_base_url_multiple_trailing_slashes_stripped(self):
        """Test that multiple trailing slashes are all removed."""
        client = DeepSeekClient(
            api_key="test_key",
            base_url="https://api.deepseek.com///",
        )
        assert client.base_url == "https://api.deepseek.com"


class TestDeepSeekClientSetters:
    """Tests for DeepSeekClient setter methods."""

    def test_set_seed(self):
        """Test that set_seed updates the seed attribute."""
        client = DeepSeekClient(api_key="test_key")
        assert client.seed is None

        client.set_seed(42)
        assert client.seed == 42

        client.set_seed(999)
        assert client.seed == 999


class TestDeepSeekClientCountTokens:
    """Tests for token counting."""

    def test_count_tokens_empty_string(self):
        """Test that empty string returns at least 1 token."""
        client = DeepSeekClient(api_key="test_key")
        count = client.count_tokens("")
        assert count == 1

    def test_count_tokens_single_word(self):
        """Test token count for a single word."""
        client = DeepSeekClient(api_key="test_key")
        count = client.count_tokens("hello")
        assert count >= 1

    def test_count_tokens_longer_text(self):
        """Test token count for longer text."""
        client = DeepSeekClient(api_key="test_key")
        text = "This is a longer piece of text that should result in more tokens."
        count = client.count_tokens(text)
        assert count > 1
        # Text is roughly 61 bytes, at 3.5 bytes per token, expect ~17 tokens
        assert count >= 10

    def test_count_tokens_unicode_text(self):
        """Test token count for Unicode text."""
        client = DeepSeekClient(api_key="test_key")
        text = "你好世界"  # "Hello world" in Chinese
        count = client.count_tokens(text)
        assert count >= 1

    def test_count_tokens_proportional_to_length(self):
        """Test that token count is roughly proportional to text length."""
        client = DeepSeekClient(api_key="test_key")
        short_text = "hello"
        long_text = "hello " * 100

        short_count = client.count_tokens(short_text)
        long_count = client.count_tokens(long_text)
        assert long_count > short_count


class TestDeepSeekClientBuildPayload:
    """Tests for payload building."""

    def test_build_payload_structure(self):
        """Test that payload has correct structure."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Hello"}]

        payload = client._build_payload(messages, max_tokens=512, temperature=0.8)

        assert payload["model"] == "deepseek-chat"
        assert payload["messages"] == messages
        assert payload["max_tokens"] == 512
        assert payload["temperature"] == 0.8
        assert "seed" not in payload

    def test_build_payload_with_seed(self):
        """Test that seed is included in payload when set."""
        client = DeepSeekClient(api_key="test_key")
        client.set_seed(42)
        messages = [{"role": "user", "content": "Hello"}]

        payload = client._build_payload(messages, max_tokens=512, temperature=0.8)

        assert payload["seed"] == 42

    def test_build_payload_custom_model(self):
        """Test payload with custom model."""
        client = DeepSeekClient(api_key="test_key", model="deepseek-reasoning")
        messages = [{"role": "user", "content": "Think about this"}]

        payload = client._build_payload(messages, max_tokens=2048, temperature=0.5)

        assert payload["model"] == "deepseek-reasoning"

    def test_build_payload_preserves_messages(self):
        """Test that messages are preserved exactly in payload."""
        client = DeepSeekClient(api_key="test_key")
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Tell me a story."},
        ]

        payload = client._build_payload(messages, max_tokens=1024, temperature=0.7)

        assert payload["messages"] == messages


class TestDeepSeekClientHeaders:
    """Tests for HTTP headers."""

    def test_headers_include_auth(self):
        """Test that headers include proper Authorization header."""
        client = DeepSeekClient(api_key="test_api_key_xyz")
        headers = client._headers()

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_api_key_xyz"

    def test_headers_include_content_type(self):
        """Test that headers include Content-Type."""
        client = DeepSeekClient(api_key="test_key")
        headers = client._headers()

        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"

    def test_headers_structure(self):
        """Test complete headers structure."""
        client = DeepSeekClient(api_key="my_key")
        headers = client._headers()

        assert len(headers) == 2
        assert isinstance(headers, dict)


class TestDeepSeekClientChatSuccess:
    """Tests for successful chat completions."""

    def test_chat_success_returns_content(self):
        """Test that successful chat returns the response content."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Hello"}]

        mock_response = {
            "choices": [{"message": {"content": "Hi there!"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            result = client.chat(messages)

            assert result == "Hi there!"
            mock_client.post.assert_called_once()

    def test_chat_includes_auth_header(self):
        """Test that chat request includes proper authorization."""
        client = DeepSeekClient(api_key="secret_key_123")
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            # Verify the call was made with correct headers
            call_args = mock_client.post.call_args
            assert call_args is not None
            assert "headers" in call_args.kwargs
            assert call_args.kwargs["headers"]["Authorization"] == "Bearer secret_key_123"

    def test_chat_uses_correct_endpoint(self):
        """Test that chat uses the correct API endpoint."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            # Verify endpoint is correct
            call_args = mock_client.post.call_args
            assert call_args is not None
            assert call_args[0][0] == "https://api.deepseek.com/chat/completions"

    def test_chat_includes_payload(self):
        """Test that chat sends correct payload."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Hello"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages, max_tokens=1024, temperature=0.5)

            call_args = mock_client.post.call_args
            assert call_args is not None
            payload = call_args.kwargs["json"]
            assert payload["model"] == "deepseek-chat"
            assert payload["messages"] == messages
            assert payload["max_tokens"] == 1024
            assert payload["temperature"] == 0.5

    def test_chat_default_parameters(self):
        """Test that chat uses default parameters."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["max_tokens"] == 4096
            assert payload["temperature"] == 0.7


class TestDeepSeekClientRetryLogic:
    """Tests for retry behavior."""

    def test_chat_retry_on_429(self):
        """Test that 429 responses trigger retry."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response_success = {
            "choices": [{"message": {"content": "Success"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):  # Skip actual sleep delays
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                # First call returns 429, second returns 200
                mock_response_429 = mock.MagicMock(spec=httpx.Response)
                mock_response_429.status_code = 429
                mock_response_429.text = "Rate limited"

                mock_response_200 = mock.MagicMock(spec=httpx.Response)
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = mock_response_success

                mock_client.post.side_effect = [mock_response_429, mock_response_200]

                result = client.chat(messages)

                assert result == "Success"
                assert mock_client.post.call_count == 2

    def test_chat_retry_on_timeout(self):
        """Test that timeout responses trigger retry."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response_success = {
            "choices": [{"message": {"content": "Success"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                # First call times out (504), second returns 200
                mock_response_timeout = mock.MagicMock(spec=httpx.Response)
                mock_response_timeout.status_code = 504

                mock_response_200 = mock.MagicMock(spec=httpx.Response)
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = mock_response_success

                mock_client.post.side_effect = [mock_response_timeout, mock_response_200]

                result = client.chat(messages)

                assert result == "Success"
                assert mock_client.post.call_count == 2

    def test_chat_retry_on_http_timeout_exception(self):
        """Test that httpx.TimeoutException triggers retry."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response_success = {
            "choices": [{"message": {"content": "Success"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                mock_response_200 = mock.MagicMock(spec=httpx.Response)
                mock_response_200.status_code = 200
                mock_response_200.json.return_value = mock_response_success

                # First call raises TimeoutException, second succeeds
                mock_client.post.side_effect = [
                    httpx.TimeoutException("Timeout"),
                    mock_response_200,
                ]

                result = client.chat(messages)

                assert result == "Success"
                assert mock_client.post.call_count == 2

    def test_chat_exhausts_retries(self):
        """Test that retry exhaustion raises the last error."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                # All attempts return 429
                mock_response_429 = mock.MagicMock(spec=httpx.Response)
                mock_response_429.status_code = 429
                mock_response_429.text = "Rate limited"

                mock_client.post.side_effect = [
                    mock_response_429,
                    mock_response_429,
                    mock_response_429,
                    mock_response_429,
                ]

                with pytest.raises(DeepSeekRateLimitError):
                    client.chat(messages)

    def test_chat_no_retry_on_400_error(self):
        """Test that 400 errors do not trigger retry."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_400 = mock.MagicMock(spec=httpx.Response)
            mock_response_400.status_code = 400
            mock_response_400.text = "Bad request"

            mock_client.post.return_value = mock_response_400

            with pytest.raises(DeepSeekAPIError):
                client.chat(messages)

            # Should only be called once (no retry)
            assert mock_client.post.call_count == 1

    def test_chat_no_retry_on_500_error(self):
        """Test that non-retriable 5xx errors do not trigger retry."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_500 = mock.MagicMock(spec=httpx.Response)
            mock_response_500.status_code = 500
            mock_response_500.text = "Internal server error"

            mock_client.post.return_value = mock_response_500

            with pytest.raises(DeepSeekAPIError):
                client.chat(messages)

            # Should only be called once (no retry)
            assert mock_client.post.call_count == 1


class TestDeepSeekClientErrorHandling:
    """Tests for error handling and exception types."""

    def test_chat_raises_api_error_on_500(self):
        """Test that 500 response raises DeepSeekAPIError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_500 = mock.MagicMock(spec=httpx.Response)
            mock_response_500.status_code = 500
            mock_response_500.text = "Internal server error"

            mock_client.post.return_value = mock_response_500

            with pytest.raises(DeepSeekAPIError) as exc_info:
                client.chat(messages)

            assert exc_info.value.status_code == 500

    def test_chat_raises_api_error_on_400(self):
        """Test that 400 response raises DeepSeekAPIError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_400 = mock.MagicMock(spec=httpx.Response)
            mock_response_400.status_code = 400
            mock_response_400.text = "Bad request"

            mock_client.post.return_value = mock_response_400

            with pytest.raises(DeepSeekAPIError) as exc_info:
                client.chat(messages)

            assert exc_info.value.status_code == 400

    def test_chat_raises_rate_limit_error_on_429(self):
        """Test that 429 response raises DeepSeekRateLimitError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                mock_response_429 = mock.MagicMock(spec=httpx.Response)
                mock_response_429.status_code = 429
                mock_response_429.text = "Rate limited"

                # All attempts fail
                mock_client.post.side_effect = [
                    mock_response_429,
                    mock_response_429,
                    mock_response_429,
                    mock_response_429,
                ]

                with pytest.raises(DeepSeekRateLimitError):
                    client.chat(messages)

    def test_chat_raises_timeout_error_on_504(self):
        """Test that 504 response raises DeepSeekTimeoutError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                mock_response_504 = mock.MagicMock(spec=httpx.Response)
                mock_response_504.status_code = 504

                # All attempts fail
                mock_client.post.side_effect = [
                    mock_response_504,
                    mock_response_504,
                    mock_response_504,
                    mock_response_504,
                ]

                with pytest.raises(DeepSeekTimeoutError):
                    client.chat(messages)

    def test_chat_raises_timeout_error_on_408(self):
        """Test that 408 response raises DeepSeekTimeoutError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            with mock.patch("time.sleep"):
                mock_client = mock.MagicMock()
                mock_client_class.return_value.__enter__.return_value = mock_client

                mock_response_408 = mock.MagicMock(spec=httpx.Response)
                mock_response_408.status_code = 408

                # All attempts fail
                mock_client.post.side_effect = [
                    mock_response_408,
                    mock_response_408,
                    mock_response_408,
                    mock_response_408,
                ]

                with pytest.raises(DeepSeekTimeoutError):
                    client.chat(messages)

    def test_chat_raises_api_error_on_malformed_response(self):
        """Test that malformed response raises DeepSeekAPIError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = mock.MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            mock_response.json.return_value = {"unexpected": "structure"}

            mock_client.post.return_value = mock_response

            with pytest.raises(DeepSeekAPIError):
                client.chat(messages)

    def test_chat_raises_api_error_on_missing_content(self):
        """Test that response missing content raises DeepSeekAPIError."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = mock.MagicMock(spec=httpx.Response)
            mock_response.status_code = 200
            # Missing content field
            mock_response.json.return_value = {
                "choices": [{"message": {}}],
            }

            mock_client.post.return_value = mock_response

            with pytest.raises(DeepSeekAPIError):
                client.chat(messages)

    def test_api_error_status_code_preserved(self):
        """Test that DeepSeekAPIError preserves status code."""
        error = DeepSeekAPIError(502, "Bad gateway")
        assert error.status_code == 502


class TestDeepSeekClientCustomBaseUrl:
    """Tests for custom base URL handling."""

    def test_chat_with_custom_base_url(self):
        """Test that chat uses custom base URL."""
        client = DeepSeekClient(
            api_key="test_key",
            base_url="https://custom.api.com",
        )
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://custom.api.com/chat/completions"


class TestDeepSeekClientSeed:
    """Tests for seed handling."""

    def test_chat_includes_seed_when_set(self):
        """Test that seed is included in request when set."""
        client = DeepSeekClient(api_key="test_key")
        client.set_seed(12345)
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["seed"] == 12345

    def test_chat_excludes_seed_when_not_set(self):
        """Test that seed is not included when not set."""
        client = DeepSeekClient(api_key="test_key")
        messages = [{"role": "user", "content": "Test"}]

        mock_response = {
            "choices": [{"message": {"content": "Response"}}],
        }

        with mock.patch("httpx.Client") as mock_client_class:
            mock_client = mock.MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response_obj = mock.MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            client.chat(messages)

            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert "seed" not in payload


class TestDeepSeekClientParseResponse:
    """Tests for response parsing."""

    def test_parse_response_extracts_content(self):
        """Test that _parse_response extracts content correctly."""
        client = DeepSeekClient(api_key="test_key")

        mock_response = mock.MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}],
        }

        result = client._parse_response(mock_response)
        assert result == "Hello world"

    def test_parse_response_handles_empty_content(self):
        """Test that _parse_response handles empty content strings."""
        client = DeepSeekClient(api_key="test_key")

        mock_response = mock.MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}],
        }

        result = client._parse_response(mock_response)
        assert result == ""

    def test_parse_response_converts_to_string(self):
        """Test that _parse_response converts content to string."""
        client = DeepSeekClient(api_key="test_key")

        mock_response = mock.MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        # Return non-string content
        mock_response.json.return_value = {
            "choices": [{"message": {"content": 12345}}],
        }

        result = client._parse_response(mock_response)
        assert result == "12345"
        assert isinstance(result, str)

    def test_parse_response_first_choice(self):
        """Test that _parse_response uses first choice."""
        client = DeepSeekClient(api_key="test_key")

        mock_response = mock.MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": "First"}},
                {"message": {"content": "Second"}},
            ],
        }

        result = client._parse_response(mock_response)
        assert result == "First"
