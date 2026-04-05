"""Agent collaboration protocols for standardized handoff and workflow orchestration.

This module implements the agency-agents collaboration patterns:
- Sequential handoff: Output becomes next agent's input
- Quality gates: RealityChecker validates at critical checkpoints
- Context propagation: Full output (not summaries) passed between agents

Usage:
    from agents.protocols import AgentHandoff, WorkflowOrchestrator, ContextManager

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

# Re-export from crewai.content.agents.protocols (single source of truth)
from crewai.content.agents.protocols.handoff import AgentHandoff, HandoffResult, QualityGateError, handoff_to_agent
from crewai.content.agents.protocols.workflow import WorkflowOrchestrator, PipelineConfig, PipelineResult
from crewai.content.agents.protocols.context import ContextManager, ExecutionContext, ContextPropagation

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
