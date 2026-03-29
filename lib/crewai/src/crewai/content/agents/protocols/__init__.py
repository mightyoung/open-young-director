"""Agent collaboration protocols for standardized handoff and workflow orchestration.

This module implements the agency-agents collaboration patterns:
- Sequential handoff: Output becomes next agent's input
- Quality gates: RealityChecker validates at critical checkpoints
- Context propagation: Full output (not summaries) passed between agents

Usage:
    from crewai.content.agents.protocols import AgentHandoff, WorkflowOrchestrator, ContextManager

    # Create handoff
    handoff = AgentHandoff(
        from_agent="director",
        to_agent="character",
        content=scene_content,
        context={"chapter": 1, "scene_id": "s1"},
        quality_gate=True
    )

    # Execute pipeline
    orchestrator = WorkflowOrchestrator(agents={"director": d, "character": c})
    results = orchestrator.execute_pipeline(["director", "character"], initial_input)
"""

from .handoff import AgentHandoff, HandoffResult, QualityGateError, handoff_to_agent
from .workflow import WorkflowOrchestrator, PipelineConfig, PipelineResult
from .context import ContextManager, ExecutionContext, ContextPropagation

__all__ = [
    # Handoff protocol
    "AgentHandoff",
    "HandoffResult",
    "QualityGateError",
    "handoff_to_agent",
    # Workflow orchestration
    "WorkflowOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    # Context management
    "ContextManager",
    "ExecutionContext",
    "ContextPropagation",
]
