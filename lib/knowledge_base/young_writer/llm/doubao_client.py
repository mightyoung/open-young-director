"""Doubao LLM Client for video prompt generation using Volcengine ARK API.

Uses the Doubao Seed 2.0 Pro model for enhanced video prompt generation
with the 五维控制坐标系 (Five-Dimensional Control Coordinate System) format.

Uses direct httpx calls instead of the Volcengine SDK to avoid model name normalization issues.

Usage:
    client = DoubaoClient(model="doubao-seed-2-0-pro-260215")
    result = client.generate("Generate a video prompt for a xianxia battle scene")
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class DoubaoClient:
    """Client for Doubao LLM via Volcengine ARK API.

    Uses direct httpx calls for API access to avoid SDK model name normalization issues.
    Supports Doubao Seed 2.0 Pro and other Doubao models.
    """

    def __init__(
        self,
        api_key: str = None,
        api_host: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        """Initialize Doubao client.

        Args:
            api_key: Doubao API key. Defaults to DOUBAO_API_KEY env var.
            api_host: API host URL. Defaults to DOUBAO_API_HOST env var.
            model: Model ID (e.g., "doubao-seed-2-0-pro-260215")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("DOUBAO_API_KEY", "")
        self.api_host = api_host or os.getenv("DOUBAO_API_HOST", "https://ark.cn-beijing.volces.com/api/v3")
        self.model = model or os.getenv("DOUBAO_MODEL", "doubao-seed-2-0-pro-260215")
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            logger.warning("DOUBAO_API_KEY not set")

    def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate text completion.

        Args:
            prompt: User prompt
            system: Optional system message
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated text string
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.api_host}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature or self.temperature,
                        "max_tokens": max_tokens or self.max_tokens,
                    },
                )

            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error(f"Doubao API error ({response.status_code}): {error_msg}")
                raise RuntimeError(f"API error: {error_msg}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Doubao API error: {e}")
            raise

    async def generate_async(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Async version of generate using httpx.AsyncClient."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_host}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature or self.temperature,
                        "max_tokens": max_tokens or self.max_tokens,
                    },
                )

            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error(f"Doubao API error ({response.status_code}): {error_msg}")
                raise RuntimeError(f"API error: {error_msg}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Doubao API error: {e}")
            raise
# Singleton instance
_doubao_client: Optional[DoubaoClient] = None


def get_doubao_client(
    api_key: str = None,
    api_host: str = None,
    model: str = None,
) -> DoubaoClient:
    """Get the global DoubaoClient instance.

    Args:
        api_key: Optional API key override
        api_host: Optional API host override
        model: Optional model override

    Returns:
        DoubaoClient singleton instance
    """
    global _doubao_client

    if _doubao_client is None:
        _doubao_client = DoubaoClient(
            api_key=api_key,
            api_host=api_host,
            model=model or "doubao-seed-2-0-pro-260215",
        )

    return _doubao_client
