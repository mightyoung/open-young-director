# -*- encoding: utf-8 -*-
"""Context propagation management for agent collaboration.

Ensures full context (not summaries) is passed between agents:
- ExecutionContext: Immutable context snapshot for each agent
- ContextManager: Manages context propagation through pipeline
- ContextPropagation: Strategies for context updates

Usage:
    manager = ContextManager()
    manager.set_context("director", {"chapter": 1, "scene": {...}})

    # Propagate to next agent
    ctx = manager.propagate("director", "character", additional={"beat": 3})
"""

import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

MAX_HISTORY_SIZE = 100


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context snapshot for agent execution.

    Context is frozen to prevent accidental mutation during pipeline execution.
    Use ContextManager.create_updated() to create modified copies.

    Attributes:
        agent_name: Name of the agent this context is for
        pipeline_step: Current step in the pipeline
        content: The content being processed
        metadata: Additional metadata
        created_at: When this context was created
        parent_context_id: ID of parent context (for tracing)
    """
    agent_name: str
    pipeline_step: int
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_context_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_name": self.agent_name,
            "pipeline_step": self.pipeline_step,
            "content_type": type(self.content).__name__,
            "content_preview": str(self.content)[:200] if self.content else None,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "parent_context_id": self.parent_context_id,
        }


class ContextManager:
    """Manages context propagation through agent pipelines.

    Ensures full context is passed between agents, not summaries.
    Maintains context history for debugging and tracing.

    Usage:
        manager = ContextManager()

        # Set initial context
        manager.set_context("director", ExecutionContext(
            agent_name="director",
            pipeline_step=0,
            content=initial_input,
            metadata={"chapter": 1}
        ))

        # Propagate to next agent
        char_ctx = manager.propagate(
            from_agent="director",
            to_agent="character",
            additional_metadata={"beat": 1}
        )
    """

    def __init__(self):
        self._contexts: Dict[str, ExecutionContext] = {}
        self._history: List[Dict[str, Any]] = []
        self._context_id_counter = 0

    def _generate_context_id(self) -> str:
        """Generate unique context ID."""
        self._context_id_counter += 1
        return f"ctx_{self._context_id_counter:04d}"

    def set_context(self, agent_name: str, context: ExecutionContext) -> None:
        """Set context for an agent."""
        # Create a new context with generated ID
        new_context = ExecutionContext(
            agent_name=context.agent_name,
            pipeline_step=context.pipeline_step,
            content=context.content,
            metadata=copy.deepcopy(context.metadata),
            created_at=datetime.now().isoformat(),
            parent_context_id=context.parent_context_id,
        )
        self._contexts[agent_name] = new_context
        logger.debug(f"[Context] Set context for {agent_name}: {new_context.to_dict()}")

    def get_context(self, agent_name: str) -> Optional[ExecutionContext]:
        """Get context for an agent."""
        return self._contexts.get(agent_name)

    def propagate(
        self,
        from_agent: str,
        to_agent: str,
        additional_metadata: Dict[str, Any] = None,
        content: Any = None,
    ) -> ExecutionContext:
        """Propagate context from one agent to another.

        Creates a new ExecutionContext for the receiving agent with:
        - Full content from previous agent (not summary)
        - Accumulated metadata
        - Tracing information

        Args:
            from_agent: Source agent name
            to_agent: Target agent name
            additional_metadata: Additional metadata to merge
            content: Override content (uses from_agent's content if None)

        Returns:
            New ExecutionContext for to_agent
        """
        from_ctx = self._contexts.get(from_agent)
        if from_ctx is None:
            raise ValueError(f"No context found for agent: {from_agent}")

        # Build metadata
        metadata = copy.deepcopy(from_ctx.metadata)
        if additional_metadata:
            metadata.update(additional_metadata)

        # Track propagation
        metadata["propagation_history"] = metadata.get("propagation_history", [])
        metadata["propagation_history"].append({
            "from": from_agent,
            "to": to_agent,
            "timestamp": datetime.now().isoformat(),
        })

        # Create new context
        new_context = ExecutionContext(
            agent_name=to_agent,
            pipeline_step=from_ctx.pipeline_step + 1,
            content=content if content is not None else from_ctx.content,
            metadata=metadata,
            created_at=datetime.now().isoformat(),
            parent_context_id=self._generate_context_id(),
        )

        self._contexts[to_agent] = new_context

        # Record in history
        self._history.append({
            "from_agent": from_agent,
            "to_agent": to_agent,
            "from_context_id": from_ctx.metadata.get("context_id"),
            "to_context_id": new_context.metadata.get("context_id"),
            "timestamp": datetime.now().isoformat(),
        })

        # Limit history size to prevent unbounded growth
        while len(self._history) > MAX_HISTORY_SIZE:
            self._history.pop(0)

        logger.info(
            f"[Context] Propagated {from_agent} -> {to_agent} "
            f"(step {from_ctx.pipeline_step} -> {new_context.pipeline_step})"
        )

        return new_context

    def update_content(self, agent_name: str, content: Any) -> None:
        """Update content for an agent without changing other context."""
        ctx = self._contexts.get(agent_name)
        if ctx is None:
            raise ValueError(f"No context found for agent: {agent_name}")

        # Create updated context
        new_context = ExecutionContext(
            agent_name=ctx.agent_name,
            pipeline_step=ctx.pipeline_step,
            content=content,
            metadata=copy.deepcopy(ctx.metadata),
            created_at=datetime.now().isoformat(),
            parent_context_id=ctx.parent_context_id,
        )
        self._contexts[agent_name] = new_context
        logger.debug(f"[Context] Updated content for {agent_name}")

    def get_history(self) -> List[Dict[str, Any]]:
        """Get propagation history."""
        return copy.deepcopy(self._history)

    def get_full_context_chain(self) -> Dict[str, ExecutionContext]:
        """Get all contexts in the pipeline."""
        return copy.deepcopy(self._contexts)


class ContextPropagation:
    """Strategies for context propagation between agents.

    Defines how context changes as it moves through the pipeline.
    """

    @staticmethod
    def full_content_propagation(
        current_context: ExecutionContext,
        agent_output: Any,
    ) -> tuple[Any, Dict[str, Any]]:
        """Propagate full content to next agent.

        Returns:
            Tuple of (content, metadata) to pass to next agent
        """
        return agent_output, current_context.metadata

    @staticmethod
    def incremental_propagation(
        current_context: ExecutionContext,
        agent_output: Any,
    ) -> tuple[Any, Dict[str, Any]]:
        """Propagate only incremental changes.

        Use when content is large and only deltas should be passed.
        """
        metadata = copy.deepcopy(current_context.metadata)
        metadata["incremental"] = True
        metadata["previous_content_hash"] = hash(str(current_context.content))
        return agent_output, metadata

    @staticmethod
    def filtered_propagation(
        current_context: ExecutionContext,
        agent_output: Any,
        keep_keys: Set[str] = None,
    ) -> tuple[Any, Dict[str, Any]]:
        """Propagate only specific metadata keys.

        Args:
            current_context: Current execution context
            agent_output: Output from current agent
            keep_keys: Set of metadata keys to keep
        """
        if keep_keys is None:
            keep_keys = {"chapter", "scene_id", "characters"}

        filtered_metadata = {
            k: v for k, v in current_context.metadata.items()
            if k in keep_keys
        }
        filtered_metadata["propagation_type"] = "filtered"

        return agent_output, filtered_metadata


def create_pipeline_context(
    agent_name: str,
    initial_content: Any,
    metadata: Dict[str, Any] = None,
) -> ExecutionContext:
    """Factory function to create initial pipeline context.

    Args:
        agent_name: Name of first agent in pipeline
        initial_content: Content to start with
        metadata: Initial metadata

    Returns:
        ExecutionContext for first agent
    """
    return ExecutionContext(
        agent_name=agent_name,
        pipeline_step=0,
        content=initial_content,
        metadata=metadata or {},
    )
