"""LLM Client Adapter - Wraps crewai LLM to match knowledge_base LLMClient interface."""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM


class LLMClientAdapter:
    """Adapter that wraps crewai's LLM to match knowledge_base's LLMClient protocol.

    This adapter allows knowledge_base components (NovelOrchestrator, DirectorAgent,
    etc.) to work with crewai's LLM configuration.
    """

    def __init__(self, llm: "LLM"):
        """Initialize the adapter with a crewai LLM instance.

        Args:
            llm: A crewai LLM instance
        """
        self._llm = llm
        self._model = getattr(llm, 'model', 'unknown')

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> "LLMResponse":
        """Send a chat request through the crewai LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
            temperature: Optional temperature setting
            max_tokens: Optional max tokens setting

        Returns:
            LLMResponse object with the model's response
        """
        # Build the full messages list
        full_messages = []

        # Add system prompt if provided
        if system_prompt:
            full_messages.append({
                "role": "system",
                "content": system_prompt
            })

        # Add the conversation messages
        full_messages.extend(messages)

        # Call the crewai LLM
        # crewai LLM supports direct .call() or we format for chat
        try:
            response = self._llm.chat(
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Return an LLMResponse-compatible object
            return LLMResponse(
                content=response.content if hasattr(response, 'content') else str(response),
                model=self._model,
                usage=getattr(response, 'usage', {}),
                raw_response=getattr(response, 'raw_response', {}),
            )
        except Exception as e:
            # Return error information instead of raising, allowing upper layers to handle
            return LLMResponse(
                content=f"[LLM Error: {str(e)}]",
                model=self._model,
                usage={},
                raw_response={"error": str(e)},
            )

    def close(self) -> None:
        """Close the LLM client (no-op for crewai LLM)."""
        # crewai LLM doesn't require explicit closing
        pass


class LLMResponse:
    """Response object matching knowledge_base's LLMResponse."""

    def __init__(
        self,
        content: str,
        model: str = "",
        usage: Optional[Dict[str, int]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.raw_response = raw_response or {}
