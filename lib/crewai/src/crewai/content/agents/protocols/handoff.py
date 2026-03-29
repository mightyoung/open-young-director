# -*- encoding: utf-8 -*-
"""Agent handoff protocol for standardized agent-to-agent collaboration.

Key concepts:
- AgentHandoff: Dataclass containing all handoff information
- Quality gates: RealityChecker validates before handoff completion
- Full context propagation: Complete outputs (not summaries) passed along

Usage:
    handoff = AgentHandoff(
        from_agent="director",
        to_agent="character",
        content=scene_content,
        context={"chapter": 1},
        quality_gate=True
    )
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class HandoffStatus(Enum):
    """Status of an agent handoff."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    FAILED = "failed"
    COMPLETED = "completed"


@dataclass
class AgentHandoff:
    """Represents a standardized handoff between two agents.

    Attributes:
        from_agent: Name of the agent handing off
        to_agent: Name of the agent receiving the handoff
        content: The actual content being passed (not a summary)
        context: Additional context for the handoff
        quality_gate: Whether to validate via RealityChecker
        metadata: Additional metadata (timestamps, status, etc.)
    """
    from_agent: str
    to_agent: str
    content: Any  # Full content, not summary
    context: Dict[str, Any] = field(default_factory=dict)
    quality_gate: bool = True
    status: HandoffStatus = HandoffStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    validated_at: Optional[str] = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        """Generate ID if not provided."""
        if "handoff_id" not in self.metadata:
            import uuid
            self.metadata["handoff_id"] = f"hnd_{uuid.uuid4().hex[:8]}"

    @property
    def handoff_id(self) -> str:
        """Get the handoff ID."""
        return self.metadata.get("handoff_id", "")

    def mark_in_progress(self) -> None:
        """Mark handoff as in progress."""
        self.status = HandoffStatus.IN_PROGRESS
        logger.debug(f"[Handoff:{self.handoff_id}] {self.from_agent} -> {self.to_agent} IN_PROGRESS")

    def mark_validated(self, validation_result: Optional[Dict[str, Any]] = None) -> None:
        """Mark handoff as validated by quality gate."""
        self.status = HandoffStatus.VALIDATED
        self.validated_at = datetime.now().isoformat()
        if validation_result:
            self.metadata["validation_result"] = validation_result
        logger.info(f"[Handoff:{self.handoff_id}] {self.from_agent} -> {self.to_agent} VALIDATED")

    def mark_completed(self, result: Any = None) -> None:
        """Mark handoff as completed."""
        self.status = HandoffStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        if result is not None:
            self.metadata["result"] = result
        logger.info(f"[Handoff:{self.handoff_id}] {self.from_agent} -> {self.to_agent} COMPLETED")

    def mark_failed(self, error: str) -> None:
        """Mark handoff as failed."""
        self.status = HandoffStatus.FAILED
        self.metadata["error"] = error
        logger.error(f"[Handoff:{self.handoff_id}] {self.from_agent} -> {self.to_agent} FAILED: {error}")


@dataclass
class HandoffResult:
    """Result of a completed handoff.

    Attributes:
        handoff: The handoff that was executed
        output: The output from the receiving agent
        validation: Validation result if quality gate was enabled
        error: Error message if handoff failed
    """
    handoff: AgentHandoff
    output: Any = None
    validation: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    success: bool = True

    @property
    def is_success(self) -> bool:
        """Check if handoff was successful."""
        return self.success and self.handoff.status == HandoffStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "handoff_id": self.handoff.handoff_id,
            "from_agent": self.handoff.from_agent,
            "to_agent": self.handoff.to_agent,
            "status": self.handoff.status.value,
            "success": self.success,
            "output": str(self.output)[:500] if self.output else None,
            "validation": self.validation,
            "error": self.error,
            "created_at": self.handoff.created_at,
            "completed_at": self.handoff.completed_at,
        }


class QualityGateError(Exception):
    """Exception raised when content fails quality gate validation.

    Attributes:
        issues: List of issues found during validation
        evidence_required: List of evidence requirements
        validation_result: The raw validation result
    """

    def __init__(
        self,
        message: str,
        issues: List[str] = None,
        evidence_required: List[str] = None,
        validation_result: Dict[str, Any] = None
    ):
        super().__init__(message)
        self.issues = issues or []
        self.evidence_required = evidence_required or []
        self.validation_result = validation_result or {}

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.issues:
            parts.append(f"Issues ({len(self.issues)}): {', '.join(self.issues[:3])}")
        if self.evidence_required:
            parts.append(f"Evidence required: {', '.join(self.evidence_required[:2])}")
        return " | ".join(parts)


async def handoff_to_agent(
    from_agent: str,
    to_agent: str,
    content: Any,
    context: Dict[str, Any],
    quality_gate: "RealityChecker" = None,
    agent_executor: callable = None,
    quality_gate_enabled: bool = True,
) -> HandoffResult:
    """Execute a standardized handoff between two agents.

    This function implements the core handoff protocol:
    1. Create handoff record
    2. Execute receiving agent with content
    3. Validate via quality gate if enabled
    4. Return result

    Args:
        from_agent: Name of handing off agent
        to_agent: Name of receiving agent
        content: Content to pass (full output, not summary)
        context: Execution context
        quality_gate: RealityChecker instance for validation
        agent_executor: Callable that executes the agent (agent, content, context) -> output
        quality_gate_enabled: Whether to run quality gate

    Returns:
        HandoffResult with output and validation info

    Raises:
        QualityGateError: If quality gate validation fails
    """
    import asyncio

    # Create handoff record
    handoff = AgentHandoff(
        from_agent=from_agent,
        to_agent=to_agent,
        content=content,
        context=context,
        quality_gate=quality_gate_enabled,
    )
    handoff.mark_in_progress()

    try:
        # Execute receiving agent
        if agent_executor is None:
            raise ValueError("agent_executor must be provided")

        # Run agent execution (could be sync or async)
        if asyncio.iscoroutinefunction(agent_executor):
            output = await agent_executor(to_agent, content, context)
        else:
            output = agent_executor(to_agent, content, context)

        handoff.mark_completed(output)

        # Quality gate validation
        validation_result = None
        if quality_gate_enabled and quality_gate is not None:
            # Build validation criteria from context
            criteria = {
                "characters": context.get("characters", {}),
                "previous_summary": context.get("previous_summary", ""),
                "required_elements": context.get("required_elements", []),
                "prohibited_elements": context.get("prohibited_elements", []),
            }

            # Validate content
            validation_result = quality_gate.validate_content(str(content), criteria)

            if validation_result.status == "FAIL":
                handoff.mark_failed(f"Quality gate failed: {validation_result.status}")
                raise QualityGateError(
                    f"Content from {from_agent} failed quality gate for {to_agent}",
                    issues=validation_result.issues,
                    evidence_required=validation_result.evidence_required,
                    validation_result=validation_result.__dict__,
                )
            elif validation_result.status == "NEEDS_WORK":
                logger.warning(
                    f"[Handoff:{handoff.handoff_id}] Quality gate NEEDS_WORK: "
                    f"{len(validation_result.issues)} issues"
                )

            handoff.mark_validated(validation_result.__dict__)

        return HandoffResult(
            handoff=handoff,
            output=output,
            validation=validation_result.__dict__ if validation_result else None,
            success=True,
        )

    except QualityGateError:
        raise
    except Exception as e:
        error_msg = f"Agent execution failed: {str(e)}"
        handoff.mark_failed(error_msg)
        logger.error(f"[Handoff:{handoff.handoff_id}] {error_msg}")
        return HandoffResult(
            handoff=handoff,
            error=error_msg,
            success=False,
        )


# Type alias for RealityChecker (avoid circular import)
RealityChecker = Any  # Will be imported at runtime
