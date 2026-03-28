"""MiniMax LLM Client for novel generation.

Uses Anthropic SDK for MiniMax's Anthropic-compatible API.
Reference: https://platform.minimaxi.com/docs/api-reference/text-anthropic-api
"""

import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _get_default_system_prompt() -> str:
    """Get the default structured system prompt for novel writing.

    Uses layered modular structure: Identity/Capabilities/Rules/Communication.
    """
    return """<identity>
You are an elite Chinese novel writer, specializing in cultivation/fantasy genres.
You write like a human author, not a machine.
Match the user's input style in your responses.
</identity>

<capabilities>
- Craft compelling Chinese narratives with vivid characters
- Write dialogue that reflects each character's unique personality
- Describe scenes with rich sensory details
- Maintain consistent story logic and character development
- Output ONLY the story text - no analysis, no reasoning, no meta-comments
</capabilities>

<rules>
NEVER: Output any thinking process, reasoning steps, or analysis
NEVER: Include placeholders like "[此处描写...]" or "[待补充]"
NEVER: Add explanations like "以下是故事内容：" or "开始写作："
CRITICAL: Output only the raw story content in Chinese
IMPORTANT: Stay within the word count guidelines provided
</rules>

<communication>
1. Write in literary Chinese appropriate to the genre
2. Use dialogue tags sparingly and authentically (said, asked, replied)
3. Break paragraphs at natural scene/chapter beats
4. Use "..." for pauses and interruptions
5. Format: dialogue in「」or「」marks, thoughts in（）marks
</communication>

<output>
直接输出故事正文，不要输出任何思考过程、推理或说明。只输出故事文本。
</output>"""


class MiniMaxClient:
    """Client for MiniMax LLM API using Anthropic SDK.

    API endpoint: https://api.minimaxi.com/anthropic
    Supported models: MiniMax-M2.7, MiniMax-M2.7-highspeed, MiniMax-M2.5, etc.
    """

    # Default system prompt - uses structured format with Identity/Capabilities/Rules
    DEFAULT_SYSTEM_PROMPT = _get_default_system_prompt()

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.minimaxi.com/anthropic",
        model: str = "MiniMax-M2.7-highspeed",
        temperature: float = 1.0,
        max_tokens: int = 8192,
        system_prompt: str = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("MINIMAX_API_KEY", "")
        self.base_url = (base_url or os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/anthropic")).rstrip("/")
        self.model = model or os.getenv("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

        # Initialize Anthropic client
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except ImportError:
            logger.warning("anthropic package not installed, using HTTP fallback")
            self._client = None

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
        system: str = None,
        retry_count: int = 3,
        retry_delay: float = 5.0,
    ) -> str:
        """Generate text from messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0, 1.0]
            max_tokens: Maximum tokens to generate
            system: System prompt (uses default if not provided)
            retry_count: Number of retries on rate limit
            retry_delay: Delay between retries in seconds

        Returns:
            Generated text string
        """
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY (or MINIMAX_API_KEY) not configured")

        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        system_prompt = system if system is not None else self.system_prompt

        import time
        last_error = None

        for attempt in range(retry_count):
            try:
                if self._client is not None:
                    # Use Anthropic SDK
                    response = self._client.messages.create(
                        model=self.model,
                        max_tokens=tokens,
                        temperature=temp,
                        system=system_prompt,
                        messages=self._format_messages(messages),
                    )
                    return self._extract_text_from_response(response)
                else:
                    # HTTP fallback
                    return self._generate_http(messages, temp, tokens, system_prompt)

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limit
                if '429' in error_str or 'rate' in error_str or 'limit' in error_str:
                    if attempt < retry_count - 1:
                        logger.warning(f"Rate limited, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue

                logger.error(f"MiniMax API error: {e}")
                if attempt >= retry_count - 1:
                    break

        raise last_error or RuntimeError("MiniMax API call failed")

    def _extract_text_from_response(self, response) -> str:
        """Extract text from Anthropic API response.

        Handles both text blocks and thinking blocks (for MiniMax models
        that return reasoning content). Prioritizes text blocks over
        thinking blocks since MiniMax API returns [thinking, text] order.
        """
        import re

        # Collect text and thinking content, prioritize text
        text_content = None
        thinking_content = None

        for block in response.content:
            block_type = getattr(block, 'type', None) or block.get('type')

            if block_type == 'text':
                text_content = block.text if hasattr(block, 'text') else block.get('text', '')

            elif block_type == 'thinking':
                thinking_content = block.thinking if hasattr(block, 'thinking') else block.get('thinking', '')

        # Return text block if available, otherwise extract from thinking
        if text_content:
            return text_content
        elif thinking_content:
            return self._extract_text_from_thinking(thinking_content)

        # Fallback: return empty string
        return ''

    def _extract_text_from_thinking(self, thinking: str) -> str:
        """Extract actual text response from thinking content.

        MiniMax's thinking content contains the reasoning process,
        but the actual response is usually at the end or embedded.
        """
        import re

        if not thinking:
            return ''

        # Find all Chinese text sequences (10+ characters - likely actual responses)
        chinese_patterns = re.findall(r'[\u4e00-\u9fff]{10,}', thinking)

        if chinese_patterns:
            # Return the last/longest sequence which is likely the actual response
            # (reasoning tends to be interspersed with English)
            return chinese_patterns[-1]

        # Fallback: try to find any substantial Chinese text
        all_chinese = re.findall(r'[\u4e00-\u9fff]+', thinking)
        if all_chinese:
            # Return the longest sequence
            return max(all_chinese, key=len)

        return thinking.strip()

    def _format_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Format messages for Anthropic API.

        Converts OpenAI-style messages to Anthropic format.
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Map roles
            if role == "system":
                # System messages handled separately
                continue
            elif role == "assistant":
                role = "assistant"
            else:
                role = "user"

            # Handle content - Anthropic supports text blocks
            if isinstance(content, str):
                formatted.append({"role": role, "content": content})
            elif isinstance(content, list):
                # Handle mixed content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "image":
                            # Skip images for now
                            pass
                    elif isinstance(block, str):
                        text_parts.append(block)
                formatted.append({"role": role, "content": "\n".join(text_parts)})
            else:
                formatted.append({"role": role, "content": str(content)})

        return formatted

    def _generate_http(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        system: str = None,
    ) -> str:
        """HTTP fallback for generation."""
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": self._format_messages(messages),
        }

        if system:
            payload["system"] = system

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Extract text from response content
            # IMPORTANT: Check text blocks FIRST, then thinking blocks as fallback
            # API returns blocks in order [thinking, text], so we must prioritize text
            content = data.get("content", [])
            text_block_content = None
            thinking_content = None

            for block in content:
                block_type = block.get("type")
                if block_type == "text":
                    text_block_content = block.get("text", "")
                elif block_type == "thinking":
                    thinking_content = block.get("thinking", "")

            # Return text block if available, otherwise extract from thinking
            if text_block_content:
                return text_block_content
            elif thinking_content:
                return self._extract_text_from_thinking(thinking_content)

            # Fallback
            return ""

    def read_file(self, file_path: str) -> str:
        """Read a file and return its content."""
        try:
            from pathlib import Path
            path = Path(file_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
            return ""
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return ""


_client_instance: Optional[MiniMaxClient] = None


def get_minimax_client(
    api_key: str = None,
    base_url: str = "https://api.minimaxi.com/anthropic",
    model: str = "MiniMax-M2.7-highspeed",
    temperature: float = 1.0,
    max_tokens: int = 8192,
) -> MiniMaxClient:
    """Get the global MiniMaxClient instance."""
    global _client_instance

    if _client_instance is None:
        _client_instance = MiniMaxClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return _client_instance
