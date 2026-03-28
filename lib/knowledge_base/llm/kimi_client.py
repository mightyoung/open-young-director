"""Kimi LLM Client for novel generation.

Supports two modes:
1. CLI proxy mode: Uses kimi-cli subprocess as a proxy (for Kimi Code Plan)
2. Direct API mode: Direct API calls (for standard Moonshot API)

The client automatically detects which mode to use based on availability.
"""

import os
import logging
import subprocess
import json
import tempfile
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class KimiClient:
    """Client for Kimi LLM API.

    Supports two backends:
    - kimi-cli: Uses kimi-cli subprocess (for Kimi Code Plan subscriptions)
    - httpx: Direct API calls (for standard Moonshot API)
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.kimi.com/coding/v1",
        model: str = "kimi-k2.5",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        use_cli: bool = True,
    ):
        self.api_key = api_key or os.getenv("KIMI_API_KEY", "")
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.use_cli = use_cli

        # Check if kimi-cli is available
        self._cli_available = self._check_cli_available()

        if not self.api_key and not self._cli_available:
            logger.warning("KIMI_API_KEY not set and kimi-cli not available")

    def _check_cli_available(self) -> bool:
        """Check if kimi-cli is available."""
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

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate text from messages.

        Automatically chooses between CLI mode and direct API mode.
        """
        if self.use_cli and self._cli_available:
            return self._generate_via_cli(messages, temperature, max_tokens)
        else:
            return self._generate_via_api(messages, temperature, max_tokens)

    def _generate_via_cli(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate text using kimi-cli subprocess."""
        import uuid

        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        # Build prompt from messages (conversational format)
        prompt = self._build_prompt(messages)

        # Create a unique session ID for this request
        session_id = f"kb-{uuid.uuid4().hex[:8]}"

        try:
            # Use kimi-cli in print mode with a session
            cmd = [
                "kimi-cli",
                "--print",
                "--quiet",
                "--no-thinking",
                "--session", session_id,
                "--prompt", prompt,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(__file__).parent.parent),
            )

            if result.returncode != 0:
                logger.warning(f"kimi-cli returned {result.returncode}: {result.stderr}")
                # Fall back to API if CLI fails
                if self.api_key:
                    return self._generate_via_api(messages, temperature, max_tokens)
                raise RuntimeError(f"kimi-cli failed: {result.stderr}")

            output = result.stdout.strip()
            # kimi-cli outputs in text format, we need to extract the response
            return self._extract_cli_response(output)

        except subprocess.TimeoutExpired:
            logger.error("kimi-cli timed out")
            raise RuntimeError("kimi-cli timed out after 300 seconds")
        except Exception as e:
            logger.error(f"kimi-cli generation failed: {e}")
            if self.api_key:
                return self._generate_via_api(messages, temperature, max_tokens)
            raise

    def _build_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Build a prompt from OpenAI-style messages."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts)

    def read_file(self, file_path: str) -> str:
        """Read a file and return its content.

        This can be used by the novel generator to provide
        additional context when needed.
        """
        try:
            from pathlib import Path
            path = Path(file_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
            # Try globbing if path contains wildcards
            parent = Path(file_path).parent
            stem = Path(file_path).stem
            if parent.exists():
                for f in parent.glob(f"{stem}.*"):
                    if f.suffix == '.md':
                        return f.read_text(encoding="utf-8")
            return ""
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return ""

    def _extract_cli_response(self, output: str) -> str:
        """Extract response from kimi-cli output."""
        import re

        # Check if output is HTML (error page)
        if self._is_html_response(output):
            logger.warning("kimi-cli returned HTML error page, treating as empty response")
            return ""

        lines = output.split("\n")
        # Look for the last assistant message or the final response
        response_lines = []
        capture = False

        for line in lines:
            if line.startswith("Assistant:") or line.startswith("### assistant"):
                capture = True
                response_lines = [line.split(":", 1)[1].strip() if ":" in line else line]
            elif capture and lines and not lines[0].startswith("User:"):
                if line.strip() and not line.startswith("User:") and not line.startswith("Assistant:"):
                    response_lines.append(line)
                elif line.startswith("User:") or line.startswith("Assistant:"):
                    break

        if response_lines:
            raw_response = " ".join(response_lines).strip()
        else:
            # If no structured output, return the whole thing
            raw_response = output.strip() if output.strip() else output

        # Check again after extracting
        if self._is_html_response(raw_response):
            logger.warning("Extracted response is HTML, treating as empty")
            return ""

        # Filter out internal reasoning / thinking aloud patterns from kimi-cli
        filtered_lines = []
        skip_patterns = [
            r"^现在我已经",
            r"^让我开始",
            r"^我需要",
            r"^根据大纲",
            r"^实际上",
            r"^首先",
            r"^其次",
            r"^第\d+章：",
            r"^第\d+章$",
            r"^我已经阅读了",
            r"^现在我将根据",
            r"^我将根据",
            r"^承接第",
            r"^衔接上文",
        ]
        for line in raw_response.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip lines that are clearly internal reasoning
            if any(re.match(pattern, line) for pattern in skip_patterns):
                continue
            # Skip lines that look like thinking/analysis (but be more specific)
            if re.match(r"^.{0,10}(需要创作|开始创作|创作一个|保持)", line):
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines).strip()

    def _is_html_response(self, text: str) -> bool:
        """Check if text is an HTML error page response."""
        if not text:
            return False
        text = text.strip()
        # Check for HTML doctype or tags
        html_indicators = [
            "<!DOCTYPE html",
            "<html",
            "<head>",
            "<body>",
            "<title>404",
            "<title>403",
            "<title>Error",
            "<title>Not Found",
            "<title>Forbidden",
        ]
        lower_text = text.lower()
        # If more than 30% of non-whitespace chars are '<', it's likely HTML
        if lower_text.startswith("<"):
            angle_bracket_count = lower_text.count("<")
            non_whitespace = len([c for c in text if c.strip()])
            if angle_bracket_count / max(non_whitespace, 1) > 0.3:
                return True
        # Check for specific HTML error pages
        for indicator in html_indicators:
            if indicator.lower() in lower_text:
                return True
        return False

    def _generate_via_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate text via direct API call."""
        import httpx

        if not self.api_key:
            raise ValueError("KIMI_API_KEY not configured")

        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": tokens,
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                # Handle 403 Forbidden (Coding Agents only)
                if response.status_code == 403:
                    error_detail = response.text
                    if "Coding Agents" in error_detail or "coding" in error_detail.lower():
                        raise RuntimeError(
                            "Kimi API returned 403 Forbidden. "
                            "The Kimi Code Plan API only accepts requests from recognized coding agents. "
                            "Use kimi-cli or configure standard Moonshot API access."
                        )
                    raise RuntimeError(f"Kimi API returned 403: {error_detail}")

                response.raise_for_status()
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise RuntimeError(
                    "Kimi API returned 403 Forbidden. "
                    "The Kimi Code Plan API only accepts requests from recognized coding agents."
                )
            logger.error(f"Kimi API HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Kimi API call failed: {e}")
            raise


_client_instance: Optional[KimiClient] = None


def get_kimi_client(
    api_key: str = None,
    base_url: str = "https://api.kimi.com/coding/v1",
    model: str = "kimi-k2.5",
    temperature: float = 0.7,
    max_tokens: int = 8192,
) -> KimiClient:
    """Get the global KimiClient instance."""
    global _client_instance

    if _client_instance is None:
        _client_instance = KimiClient(
            api_key=api_key,
            base_url=base_url,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    return _client_instance
