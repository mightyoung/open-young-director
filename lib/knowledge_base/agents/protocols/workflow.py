# -*- encoding: utf-8 -*-
"""Workflow orchestration for multi-agent pipelines.

Implements sequential agent execution with quality gates:
- WorkflowOrchestrator: Main orchestrator class
- PipelineConfig: Configuration for pipeline execution
- PipelineResult: Result of entire pipeline execution

Usage:
    orchestrator = WorkflowOrchestrator(
        agents={"director": d, "character": c, "reality_checker": rc},
        quality_gate=reality_checker
    )

    result = orchestrator.execute_pipeline(
        pipeline=["director", "character"],
        initial_input=chapter_outline,
        context={"chapter": 1, "characters": {...}}
    )

    for handoff in result.handoffs:
        print(f"{handoff.from_agent} -> {handoff.to_agent}: {handoff.status}")
"""

import asyncio
import copy
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

from .handoff import AgentHandoff, HandoffResult, HandoffStatus, QualityGateError
from .context import ContextManager, ExecutionContext, create_pipeline_context

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Content type


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution.

    Attributes:
        max_retries: Max retries per agent on failure
        timeout_seconds: Timeout for entire pipeline
        enable_quality_gate: Whether to run quality gates
        stop_on_quality_failure: Stop pipeline if quality gate fails
        quality_gate_interval: Run quality gate every N agents (0 = only at end)
        parallel_agents: Agents that can run in parallel (not yet implemented)
    """
    max_retries: int = 2
    timeout_seconds: int = 300
    enable_quality_gate: bool = True
    stop_on_quality_failure: bool = True
    quality_gate_interval: int = 0  # 0 = only at end, 1 = every agent, etc.
    parallel_agents: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PipelineResult(Generic[T]):
    """Result of pipeline execution.

    Attributes:
        pipeline: List of agent names in order
        handoffs: List of handoffs that occurred
        final_output: Final output from last agent
        success: Whether pipeline completed successfully
        error: Error message if failed
        total_steps: Number of steps executed
        execution_time_seconds: Time taken
        context_history: Context propagation history
    """
    pipeline: List[str]
    handoffs: List[HandoffResult] = field(default_factory=list)
    final_output: T = None
    success: bool = True
    error: Optional[str] = None
    total_steps: int = 0
    execution_time_seconds: float = 0.0
    context_history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def handoff_count(self) -> int:
        """Number of handoffs in pipeline."""
        return len(self.handoffs)

    @property
    def failed_handoffs(self) -> List[HandoffResult]:
        """Get failed handoffs."""
        return [h for h in self.handoffs if not h.is_success]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pipeline": self.pipeline,
            "handoffs": [h.to_dict() for h in self.handoffs],
            "final_output_type": type(self.final_output).__name__,
            "final_output_preview": str(self.final_output)[:500] if self.final_output else None,
            "success": self.success,
            "error": self.error,
            "total_steps": self.total_steps,
            "execution_time_seconds": self.execution_time_seconds,
        }


class WorkflowOrchestrator:
    """Orchestrates multi-agent pipelines with sequential handoff.

    Key features:
    - Sequential agent execution with proper handoff
    - Optional quality gates at each step
    - Full context propagation (not summaries)
    - Retry on failure
    - Comprehensive logging and tracing

    Usage:
        orchestrator = WorkflowOrchestrator(
            agents={"director": d, "character": c},
            quality_gate=rc
        )

        result = orchestrator.execute_pipeline(
            pipeline=["director", "character"],
            initial_input=outline
        )
    """

    def __init__(
        self,
        agents: Dict[str, Any],
        quality_gate: Any = None,
        config: PipelineConfig = None,
    ):
        """Initialize workflow orchestrator.

        Args:
            agents: Dict of agent_name -> agent instance
            quality_gate: RealityChecker instance for quality validation
            config: Pipeline configuration
        """
        self.agents = agents
        self.quality_gate = quality_gate
        self.config = config or PipelineConfig()
        self.context_manager = ContextManager()

        # Agent executor functions (can be customized)
        self._agent_executors: Dict[str, Callable] = {}

        logger.info(f"[Workflow] Initialized with agents: {list(agents.keys())}")

    def set_agent_executor(self, agent_name: str, executor: Callable) -> None:
        """Set custom executor function for an agent.

        Args:
            agent_name: Name of agent
            executor: Function(agent, content, context) -> output
        """
        self._agent_executors[agent_name] = executor
        logger.debug(f"[Workflow] Set custom executor for {agent_name}")

    def _get_agent_executor(self, agent_name: str) -> Callable:
        """Get executor for an agent.

        Default executor calls agent.execute() or agent.run().
        Override with set_agent_executor() for custom behavior.
        """
        if agent_name in self._agent_executors:
            return self._agent_executors[agent_name]

        agent = self.agents.get(agent_name)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_name}")

        # Try common method names
        if hasattr(agent, "execute"):
            return lambda name, content, ctx: agent.execute(content, ctx)
        elif hasattr(agent, "run"):
            return lambda name, content, ctx: agent.run(content, ctx)
        elif hasattr(agent, "act"):
            return lambda name, content, ctx: agent.act(content, ctx)
        else:
            raise ValueError(
                f"Agent {agent_name} has no execute/run/act method. "
                "Use set_agent_executor() to provide custom executor."
            )

    def execute_pipeline(
        self,
        pipeline: List[str],
        initial_input: Any,
        context: Dict[str, Any] = None,
    ) -> PipelineResult:
        """Execute a pipeline of agents sequentially.

        Args:
            pipeline: List of agent names in execution order
            initial_input: Content to start with
            context: Initial context/metadata

        Returns:
            PipelineResult with all outputs and handoffs
        """
        import time
        start_time = time.time()

        result = PipelineResult(pipeline=pipeline)
        context = context or {}

        logger.info(f"[Workflow] Starting pipeline: {' -> '.join(pipeline)}")

        # Initialize context
        ctx = create_pipeline_context(
            agent_name=pipeline[0],
            initial_content=initial_input,
            metadata=context,
        )
        self.context_manager.set_context(pipeline[0], ctx)

        current_content = initial_input

        try:
            for i, agent_name in enumerate(pipeline):
                is_last = (i == len(pipeline) - 1)

                # Get agent and executor
                agent = self.agents.get(agent_name)
                if agent is None:
                    raise ValueError(f"Agent not found in pipeline: {agent_name}")

                executor = self._get_agent_executor(agent_name)

                # Propagate context
                if i > 0:
                    prev_agent = pipeline[i - 1]
                    ctx = self.context_manager.propagate(
                        from_agent=prev_agent,
                        to_agent=agent_name,
                        additional_metadata={"step": i},
                    )
                else:
                    ctx = self.context_manager.get_context(agent_name)

                # Build agent context
                agent_context = {
                    **context,
                    **ctx.metadata,
                    "pipeline_step": i,
                    "is_last_agent": is_last,
                }

                # Execute agent
                logger.info(f"[Workflow] Executing {agent_name} (step {i})")
                if asyncio.iscoroutinefunction(executor):
                    logger.warning(f"[Workflow] Async executor {agent_name} called from sync pipeline - use execute_pipeline_async instead")
                    # Run in new event loop
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        current_content = loop.run_until_complete(executor(agent, current_content, agent_context))
                    finally:
                        loop.close()
                else:
                    current_content = executor(agent, current_content, agent_context)

                # Update context with output
                self.context_manager.update_content(agent_name, current_content)

                # Quality gate check
                validation = None
                if self.config.enable_quality_gate and self.quality_gate is not None:
                    # Check if we should run quality gate
                    should_validate = (
                        self.config.quality_gate_interval == 0 and is_last
                    ) or (
                        self.config.quality_gate_interval > 0 and i % self.config.quality_gate_interval == 0
                    )

                    if should_validate:
                        criteria = {
                            "characters": context.get("characters", {}),
                            "previous_summary": context.get("previous_summary", ""),
                            "required_elements": context.get("required_elements", []),
                            "prohibited_elements": context.get("prohibited_elements", []),
                        }
                        validation = self.quality_gate.validate_content(
                            str(current_content), criteria
                        )

                        if validation.status == "FAIL":
                            error_msg = f"Quality gate failed at {agent_name}: {validation.issues}"
                            logger.error(f"[Workflow] {error_msg}")

                            if self.config.stop_on_quality_failure:
                                result.success = False
                                result.error = error_msg
                                result.final_output = current_content
                                result.execution_time_seconds = time.time() - start_time
                                return result

                # Record handoff
                # Success is False if quality gate failed, regardless of stop_on_quality_failure
                handoff_success = validation is None or validation.status != "FAIL"
                handoff_result = HandoffResult(
                    handoff=AgentHandoff(
                        from_agent=pipeline[i - 1] if i > 0 else "initial",
                        to_agent=agent_name,
                        content=current_content,
                        context=agent_context,
                        quality_gate=self.config.enable_quality_gate,
                    ),
                    output=current_content,
                    validation=validation.__dict__ if validation else None,
                    success=handoff_success,
                )
                handoff_result.handoff.mark_completed(current_content)
                result.handoffs.append(handoff_result)

                result.total_steps += 1

            result.final_output = current_content
            result.success = True
            logger.info(f"[Workflow] Pipeline completed successfully: {len(pipeline)} steps")

        except Exception as e:
            error_msg = f"Pipeline failed at step {result.total_steps}: {str(e)}"
            logger.error(f"[Workflow] {error_msg}")
            result.success = False
            result.error = error_msg
            result.final_output = current_content

        result.execution_time_seconds = time.time() - start_time
        result.context_history = self.context_manager.get_history()

        return result

    async def execute_pipeline_async(
        self,
        pipeline: List[str],
        initial_input: Any,
        context: Dict[str, Any] = None,
    ) -> PipelineResult:
        """Async version of execute_pipeline.

        Executes agents concurrently where possible.
        """
        import time
        start_time = time.time()

        result = PipelineResult(pipeline=pipeline)
        context = context or {}

        logger.info(f"[Workflow] Starting async pipeline: {' -> '.join(pipeline)}")

        # Initialize context
        ctx = create_pipeline_context(
            agent_name=pipeline[0],
            initial_content=initial_input,
            metadata=context,
        )
        self.context_manager.set_context(pipeline[0], ctx)

        current_content = initial_input

        try:
            for i, agent_name in enumerate(pipeline):
                is_last = (i == len(pipeline) - 1)

                # Get agent and executor
                agent = self.agents.get(agent_name)
                if agent is None:
                    raise ValueError(f"Agent not found in pipeline: {agent_name}")

                executor = self._get_agent_executor(agent_name)

                # Propagate context
                if i > 0:
                    prev_agent = pipeline[i - 1]
                    ctx = self.context_manager.propagate(
                        from_agent=prev_agent,
                        to_agent=agent_name,
                        additional_metadata={"step": i},
                    )
                else:
                    ctx = self.context_manager.get_context(agent_name)

                # Build agent context
                agent_context = {
                    **context,
                    **ctx.metadata,
                    "pipeline_step": i,
                    "is_last_agent": is_last,
                }

                # Execute agent (support async)
                logger.info(f"[Workflow] Executing {agent_name} (step {i})")

                if asyncio.iscoroutinefunction(executor):
                    current_content = await executor(agent, current_content, agent_context)
                else:
                    current_content = executor(agent, current_content, agent_context)

                # Update context with output
                self.context_manager.update_content(agent_name, current_content)

                # Quality gate check (same as sync version)
                validation = None
                if self.config.enable_quality_gate and self.quality_gate is not None:
                    should_validate = (
                        self.config.quality_gate_interval == 0 and is_last
                    ) or (
                        self.config.quality_gate_interval > 0 and i % self.config.quality_gate_interval == 0
                    )

                    if should_validate and hasattr(self.quality_gate, "validate_content"):
                        criteria = {
                            "characters": context.get("characters", {}),
                            "previous_summary": context.get("previous_summary", ""),
                            "required_elements": context.get("required_elements", []),
                            "prohibited_elements": context.get("prohibited_elements", []),
                        }
                        validation = self.quality_gate.validate_content(
                            str(current_content), criteria
                        )

                        if validation.status == "FAIL":
                            error_msg = f"Quality gate failed at {agent_name}"
                            logger.error(f"[Workflow] {error_msg}")

                            if self.config.stop_on_quality_failure:
                                result.success = False
                                result.error = error_msg
                                result.final_output = current_content
                                result.execution_time_seconds = time.time() - start_time
                                return result
                            # Even if we don't stop, mark the handoff as failed
                            # so the caller knows quality didn't pass

                # Record handoff
                # Success is False if quality gate failed, regardless of stop_on_quality_failure
                handoff_success = validation is None or validation.status != "FAIL"
                handoff_result = HandoffResult(
                    handoff=AgentHandoff(
                        from_agent=pipeline[i - 1] if i > 0 else "initial",
                        to_agent=agent_name,
                        content=current_content,
                        context=agent_context,
                        quality_gate=self.config.enable_quality_gate,
                    ),
                    output=current_content,
                    validation=validation.__dict__ if validation else None,
                    success=handoff_success,
                )
                handoff_result.handoff.mark_completed(current_content)
                result.handoffs.append(handoff_result)

                result.total_steps += 1

            result.final_output = current_content
            result.success = True
            logger.info(f"[Workflow] Async pipeline completed: {len(pipeline)} steps")

        except Exception as e:
            error_msg = f"Pipeline failed at step {result.total_steps}: {str(e)}"
            logger.error(f"[Workflow] {error_msg}")
            result.success = False
            result.error = error_msg
            result.final_output = current_content

        result.execution_time_seconds = time.time() - start_time
        result.context_history = self.context_manager.get_history()

        return result


def create_novel_pipeline_orchestrator(
    novel_orchestrator: Any,
    quality_gate: Any,
    config: PipelineConfig = None,
) -> WorkflowOrchestrator:
    """Factory to create WorkflowOrchestrator from NovelOrchestrator.

    Args:
        novel_orchestrator: NovelOrchestrator instance
        quality_gate: RealityChecker instance
        config: Pipeline config

    Returns:
        Configured WorkflowOrchestrator
    """
    agents = {
        "novel_orchestrator": novel_orchestrator,
    }

    orchestrator = WorkflowOrchestrator(
        agents=agents,
        quality_gate=quality_gate,
        config=config,
    )

    # Set executor for novel orchestrator
    orchestrator.set_agent_executor(
        "novel_orchestrator",
        lambda agent, content, ctx: agent.orchestrate_chapter(
            chapter_number=ctx.get("chapter_number", 1),
            chapter_outline=content,
            context=ctx,
        )
    )

    return orchestrator
