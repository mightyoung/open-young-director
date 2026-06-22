"""Local agent collaboration protocols for young-writer."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable


class QualityGateError(RuntimeError):
    """Raised when a quality gate rejects a handoff."""


@dataclass
class AgentHandoff:
    """Payload passed from one agent step to the next."""

    from_agent: str
    to_agent: str
    content: Any
    context: dict[str, Any] = field(default_factory=dict)
    quality_gate: bool = False


@dataclass
class HandoffResult:
    """Result for a single handoff operation."""

    handoff: AgentHandoff
    success: bool
    output: Any = None
    error: str | None = None


@dataclass
class PipelineConfig:
    """Execution options for a local workflow pipeline."""

    max_retries: int = 2
    timeout_seconds: int = 300
    enable_tracing: bool = True
    enable_quality_gate: bool = True
    quality_gate_interval: int = 2
    stop_on_quality_failure: bool = True


@dataclass
class PipelineResult:
    """Aggregate result for a local workflow pipeline."""

    success: bool
    output: Any
    handoffs: list[HandoffResult] = field(default_factory=list)
    total_steps: int = 0
    execution_time_seconds: float = 0.0
    error: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionContext:
    """Mutable workflow execution context."""

    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextPropagation:
    """Snapshot of context passed between workflow steps."""

    source: str
    target: str
    context: dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """Small context helper retained for workflow compatibility."""

    def create_context(self, initial: dict[str, Any] | None = None) -> ExecutionContext:
        return ExecutionContext(dict(initial or {}))

    def propagate(
        self,
        source: str,
        target: str,
        context: dict[str, Any] | None = None,
    ) -> ContextPropagation:
        return ContextPropagation(source=source, target=target, context=dict(context or {}))


def handoff_to_agent(
    from_agent: str,
    to_agent: str,
    content: Any,
    context: dict[str, Any] | None = None,
    quality_gate: bool = False,
) -> AgentHandoff:
    """Create a handoff payload."""

    return AgentHandoff(
        from_agent=from_agent,
        to_agent=to_agent,
        content=content,
        context=dict(context or {}),
        quality_gate=quality_gate,
    )


class WorkflowOrchestrator:
    """Sequential local pipeline runner."""

    def __init__(
        self,
        agents: dict[str, Any],
        quality_gate: Any = None,
        config: PipelineConfig | None = None,
    ) -> None:
        self.agents = agents
        self.quality_gate = quality_gate
        self.config = config or PipelineConfig()
        self._executors: dict[str, Callable[[Any, Any, dict[str, Any]], Any]] = {}

    def set_agent_executor(
        self,
        agent_name: str,
        executor: Callable[[Any, Any, dict[str, Any]], Any],
    ) -> None:
        self._executors[agent_name] = executor

    def execute_pipeline(
        self,
        pipeline: list[str],
        initial_input: Any,
        context: dict[str, Any] | None = None,
    ) -> PipelineResult:
        start = monotonic()
        current = initial_input
        execution_context = dict(context or {})
        handoffs: list[HandoffResult] = []

        try:
            for index, agent_name in enumerate(pipeline):
                agent = self.agents.get(agent_name)
                executor = self._executors.get(agent_name)
                if executor is None:
                    raise ValueError(f"No executor registered for agent: {agent_name}")

                next_output = executor(agent, current, execution_context)
                previous_name = pipeline[index - 1] if index > 0 else "input"
                handoff = AgentHandoff(
                    from_agent=previous_name,
                    to_agent=agent_name,
                    content=current,
                    context=dict(execution_context),
                    quality_gate=bool(self.quality_gate),
                )
                handoffs.append(HandoffResult(handoff=handoff, success=True, output=next_output))
                if (
                    self.config.enable_quality_gate
                    and self.config.stop_on_quality_failure
                    and self._is_quality_failure(next_output)
                ):
                    return PipelineResult(
                        success=False,
                        output=next_output,
                        handoffs=handoffs,
                        total_steps=len(handoffs),
                        execution_time_seconds=monotonic() - start,
                        error="Quality gate failed",
                        context=execution_context,
                    )
                current = next_output

            return PipelineResult(
                success=True,
                output=current,
                handoffs=handoffs,
                total_steps=len(pipeline),
                execution_time_seconds=monotonic() - start,
                context=execution_context,
            )
        except Exception as exc:
            return PipelineResult(
                success=False,
                output=current,
                handoffs=handoffs,
                total_steps=len(handoffs),
                execution_time_seconds=monotonic() - start,
                error=str(exc),
                context=execution_context,
            )

    @staticmethod
    def _is_quality_failure(output: Any) -> bool:
        if not isinstance(output, dict):
            return False
        status = str(output.get("status", "")).upper()
        if status in {"FAIL", "FAILED", "ERROR", "REJECTED"}:
            return True
        return output.get("success") is False


__all__ = [
    "AgentHandoff",
    "HandoffResult",
    "QualityGateError",
    "handoff_to_agent",
    "WorkflowOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    "ContextManager",
    "ExecutionContext",
    "ContextPropagation",
]
