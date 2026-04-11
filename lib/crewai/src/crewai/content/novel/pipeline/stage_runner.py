"""Base class for all pipeline stages."""

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from crewai.content.novel.pipeline_state import PipelineState
from crewai.llm.deepseek_client import DeepSeekClient  # noqa: F401 (re-exported)

logger = logging.getLogger(__name__)


@dataclass
class StageRunner:
    """Base class for pipeline stages.

    Subclasses must implement :meth:`run`.  The helpers ``_call_llm``,
    ``_load_prompt_template``, and ``_parse_json_response`` are available to
    all concrete stages so they do not need to duplicate boilerplate.
    """

    name: str
    llm: DeepSeekClient | None = None
    timeout: int = 300  # seconds per stage

    def run(self, state: PipelineState) -> PipelineState:
        """Execute stage synchronously.  Returns updated state (immutable pattern:
        callers should replace their reference with the returned value)."""
        raise NotImplementedError(f"{self.name} must implement run()")

    def validate_input(self, state: PipelineState) -> bool:
        """Check that prerequisites are met before :meth:`run` is called.

        Returns True by default; subclasses override to add stage-specific
        pre-conditions.
        """
        return True

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Convenience wrapper around :meth:`DeepSeekClient.chat` with logging."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        start = time.time()
        result = self.llm.chat(messages, max_tokens=max_tokens, temperature=temperature)
        elapsed = time.time() - start
        logger.info(
            "[%s] LLM call completed in %.1fs, %d chars", self.name, elapsed, len(result)
        )
        return result

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------

    def _load_prompt_template(self, filename: str) -> str:
        """Load a prompt template from the ``prompts/`` directory adjacent to this file."""
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        path = os.path.join(prompts_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Extract JSON from an LLM response, handling markdown code fences.

        Tries the following strategies in order:
        1. Strip a ```json ... ``` or ``` ... ``` fence and parse the interior.
        2. Parse the raw text directly.

        Raises :class:`json.JSONDecodeError` if neither strategy succeeds.
        """
        # Strategy 1: markdown code fence
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())

        # Strategy 2: raw text (may already be valid JSON)
        return json.loads(text.strip())
