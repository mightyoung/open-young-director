"""Agents package for novel generation system."""

from .config_manager import get_config_manager
from .novel_generator import get_novel_generator
from .chapter_manager import get_chapter_manager
from .derivative_generator import get_derivative_generator
from .feedback_loop import get_feedback_loop
from .novel_orchestrator import NovelOrchestrator
from .reality_checker import RealityChecker, ValidationResult, RealityCheckerConfig, get_reality_checker

# Agent collaboration protocols
from .protocols import (
    AgentHandoff,
    HandoffResult,
    QualityGateError,
    handoff_to_agent,
    WorkflowOrchestrator,
    PipelineConfig,
    PipelineResult,
    ContextManager,
    ExecutionContext,
    ContextPropagation,
)

# Novel workflow orchestrator
from .novel_workflow_orchestrator import (
    NovelWorkflowOrchestrator,
    NovelWorkflowConfig,
    NovelPipelineStep,
    create_novel_workflow,
    STANDARD_NOVEL_PIPELINE,
)

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
