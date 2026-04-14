"""Agents package for novel generation system.

This package intentionally uses lazy exports so importing ``agents.foo`` does not
eagerly initialize every heavy runtime dependency in the package.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    # Core agents
    "get_config_manager",
    "get_novel_generator",
    "get_chapter_manager",
    "get_derivative_generator",
    "get_feedback_loop",
    "NovelOrchestrator",
    "RealityChecker",
    "ValidationResult",
    "RealityCheckerConfig",
    "get_reality_checker",
    # Protocols
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
    # Novel workflow
    "NovelWorkflowOrchestrator",
    "NovelWorkflowConfig",
    "NovelPipelineStep",
    "create_novel_workflow",
    "STANDARD_NOVEL_PIPELINE",
]

_EXPORTS = {
    "get_config_manager": (".config_manager", "get_config_manager"),
    "get_novel_generator": (".novel_generator", "get_novel_generator"),
    "get_chapter_manager": (".chapter_manager", "get_chapter_manager"),
    "get_derivative_generator": (".derivative_generator", "get_derivative_generator"),
    "get_feedback_loop": (".feedback_loop", "get_feedback_loop"),
    "NovelOrchestrator": (".novel_orchestrator", "NovelOrchestrator"),
    "RealityChecker": (".reality_checker", "RealityChecker"),
    "ValidationResult": (".reality_checker", "ValidationResult"),
    "RealityCheckerConfig": (".reality_checker", "RealityCheckerConfig"),
    "get_reality_checker": (".reality_checker", "get_reality_checker"),
    "AgentHandoff": (".protocols", "AgentHandoff"),
    "HandoffResult": (".protocols", "HandoffResult"),
    "QualityGateError": (".protocols", "QualityGateError"),
    "handoff_to_agent": (".protocols", "handoff_to_agent"),
    "WorkflowOrchestrator": (".protocols", "WorkflowOrchestrator"),
    "PipelineConfig": (".protocols", "PipelineConfig"),
    "PipelineResult": (".protocols", "PipelineResult"),
    "ContextManager": (".protocols", "ContextManager"),
    "ExecutionContext": (".protocols", "ExecutionContext"),
    "ContextPropagation": (".protocols", "ContextPropagation"),
    "NovelWorkflowOrchestrator": (".novel_workflow_orchestrator", "NovelWorkflowOrchestrator"),
    "NovelWorkflowConfig": (".novel_workflow_orchestrator", "NovelWorkflowConfig"),
    "NovelPipelineStep": (".novel_workflow_orchestrator", "NovelPipelineStep"),
    "create_novel_workflow": (".novel_workflow_orchestrator", "create_novel_workflow"),
    "STANDARD_NOVEL_PIPELINE": (".novel_workflow_orchestrator", "STANDARD_NOVEL_PIPELINE"),
}


def __getattr__(name: str) -> Any:
    module_info = _EXPORTS.get(name)
    if module_info is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = module_info
    try:
        module = import_module(module_name, __name__)
        value = getattr(module, attr_name)
    except ModuleNotFoundError:
        value = None

    globals()[name] = value
    return value
