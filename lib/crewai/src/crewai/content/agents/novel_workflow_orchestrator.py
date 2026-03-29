# -*- encoding: utf-8 -*-
"""Novel workflow orchestrator using standardized agent collaboration protocols.

Integrates protocols into NovelOrchestrator for:
- Sequential handoff with quality gates
- Full context propagation between agents
- Comprehensive pipeline execution tracing

Usage:
    from crewai.content.agents.novel_workflow_orchestrator import NovelWorkflowOrchestrator

    orchestrator = NovelWorkflowOrchestrator.from_novel_orchestrator(novel_orch)
    result = orchestrator.execute_chapter_pipeline(
        chapter_outline="韩林与柳如烟在演武场相遇",
        context={"chapter": 1, "characters": {...}}
    )
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .novel_orchestrator import NovelOrchestrator
from .reality_checker import RealityChecker, RealityCheckerConfig
from .protocols.workflow import WorkflowOrchestrator, PipelineConfig, PipelineResult
from .protocols.context import ContextManager, ExecutionContext, create_pipeline_context
from .protocols.handoff import AgentHandoff, HandoffResult

logger = logging.getLogger(__name__)


@dataclass
class NovelPipelineStep:
    """Definition of a step in the novel generation pipeline.

    Attributes:
        agent_name: Name of agent for this step
        step_type: Type of step (plan, generate, validate, assemble)
        input_transform: Optional function to transform input
        output_transform: Optional function to transform output
    """
    agent_name: str
    step_type: str
    input_transform: Optional[callable] = None
    output_transform: Optional[callable] = None


# Standard novel generation pipeline steps
STANDARD_NOVEL_PIPELINE = [
    NovelPipelineStep(agent_name="director", step_type="plan"),
    NovelPipelineStep(agent_name="character", step_type="generate"),
    NovelPipelineStep(agent_name="reality_checker", step_type="validate"),
    NovelPipelineStep(agent_name="assembler", step_type="assemble"),
]


@dataclass
class NovelWorkflowConfig:
    """Configuration for novel workflow orchestration.

    Attributes:
        pipeline_steps: List of steps in the pipeline
        enable_quality_gate: Whether to run RealityChecker validation
        quality_gate_interval: Run quality gate every N agents (0=end only)
        stop_on_quality_failure: Stop pipeline if quality gate fails
        max_retries: Max retries per step on failure
    """
    pipeline_steps: List[NovelPipelineStep] = field(default_factory=STANDARD_NOVEL_PIPELINE)
    enable_quality_gate: bool = True
    quality_gate_interval: int = 2  # Validate every 2 steps
    stop_on_quality_failure: bool = True
    max_retries: int = 2
    timeout_seconds: int = 300


class NovelWorkflowOrchestrator:
    """Workflow orchestrator for novel generation using standardized protocols.

    Integrates with NovelOrchestrator to provide:
    - Standardized agent handoff protocol
    - Quality gates at critical checkpoints
    - Full context propagation (not summaries)

    ## Default Pipeline

    1. DirectorAgent: Plan scene structure
    2. CharacterAgent: Generate character dialogues
    3. RealityChecker: Validate quality
    4. Assembler: Combine into final output

    ## Usage

    ```python
    # Create from existing NovelOrchestrator
    workflow = NovelWorkflowOrchestrator.from_novel_orchestrator(
        novel_orchestrator,
        quality_gate=reality_checker
    )

    # Execute chapter pipeline
    result = workflow.execute_chapter_pipeline(
        chapter_outline="场景描述",
        context={"chapter": 1, "characters": {...}}
    )

    # Access results
    for handoff in result.handoffs:
        print(f"{handoff.from_agent} -> {handoff.to_agent}")
    ```
    """

    def __init__(
        self,
        novel_orchestrator: NovelOrchestrator,
        reality_checker: RealityChecker = None,
        config: NovelWorkflowConfig = None,
    ):
        """Initialize novel workflow orchestrator.

        Args:
            novel_orchestrator: Existing NovelOrchestrator instance
            reality_checker: RealityChecker for quality validation
            config: Workflow configuration
        """
        self.novel_orchestrator = novel_orchestrator
        self.reality_checker = reality_checker or novel_orchestrator._reality_checker
        self.config = config or NovelWorkflowConfig()

        # Create protocol-level orchestrator
        self._workflow_orchestrator: Optional[WorkflowOrchestrator] = None
        self._context_manager = ContextManager()

        # Agent registry
        self._agents: Dict[str, Any] = {
            "novel_orchestrator": novel_orchestrator,
        }

        # Add film_drama agents if available
        if hasattr(novel_orchestrator, "director_agent") and novel_orchestrator.director_agent:
            self._agents["director"] = novel_orchestrator.director_agent

        if hasattr(novel_orchestrator, "sub_agent_pool"):
            for i, agent in enumerate(novel_orchestrator.sub_agent_pool):
                self._agents[f"character_{i}"] = agent

        logger.info(
            f"[NovelWorkflow] Initialized with agents: {list(self._agents.keys())}"
        )

    @classmethod
    def from_novel_orchestrator(
        cls,
        novel_orchestrator: NovelOrchestrator,
        config: NovelWorkflowConfig = None,
    ) -> "NovelWorkflowOrchestrator":
        """Factory method to create from existing NovelOrchestrator.

        Args:
            novel_orchestrator: Existing NovelOrchestrator
            config: Optional workflow config

        Returns:
            NovelWorkflowOrchestrator instance
        """
        reality_checker = None
        if hasattr(novel_orchestrator, "_reality_checker"):
            reality_checker = novel_orchestrator._reality_checker

        return cls(
            novel_orchestrator=novel_orchestrator,
            reality_checker=reality_checker,
            config=config,
        )

    def _create_pipeline_config(self) -> PipelineConfig:
        """Create PipelineConfig from NovelWorkflowConfig."""
        return PipelineConfig(
            max_retries=self.config.max_retries,
            timeout_seconds=self.config.timeout_seconds,
            enable_quality_gate=self.config.enable_quality_gate,
            stop_on_quality_failure=self.config.stop_on_quality_failure,
            quality_gate_interval=self.config.quality_gate_interval,
        )

    def _get_agent_executor(self, step: NovelPipelineStep) -> callable:
        """Get executor function for a pipeline step.

        Args:
            step: The pipeline step

        Returns:
            Executor function (agent, content, context) -> output
        """
        agent_name = step.agent_name

        if agent_name == "director":
            return self._director_executor
        elif agent_name == "character":
            return self._character_executor
        elif agent_name == "reality_checker":
            return self._reality_checker_executor
        elif agent_name == "assembler":
            return self._assembler_executor
        elif agent_name == "novel_orchestrator":
            return self._novel_orchestrator_executor
        else:
            raise ValueError(f"Unknown agent: {agent_name}")

    def _director_executor(self, agent: Any, content: Any, context: Dict) -> Dict[str, Any]:
        """Execute DirectorAgent step."""
        if hasattr(agent, "plan_scene"):
            # P0 FIX: Extract protagonist constraint to prevent protagonist hallucination
            protagonist_constraint = context.get(
                "protagonist_constraint",
                "【强制约束】本章绝对主角：韩林\n"
                "- 韩林必须是主角，所有场景以韩林视角展开\n"
                "- 柳如烟是退婚对象\n"
                "- 叶尘是反派角色，不能设为主角\n"
                "- 禁止互换角色身份"
            )

            script = agent.plan_scene(
                chapter_number=context.get("chapter_number", 1),
                scene_outline=content,
                characters=context.get("characters", {}),
                location=context.get("location", "太虚宗"),
                time_of_day=context.get("time_of_day", "morning"),
                previous_context=context.get("previous_summary", ""),
                protagonist_constraint=protagonist_constraint,
            )
            return {
                "script": script,
                "scene": script.scene if hasattr(script, "scene") else None,
                "cast": script.cast if hasattr(script, "cast") else [],
            }
        return {"content": content}

    def _character_executor(self, agent: Any, content: Any, context: Dict) -> str:
        """Execute CharacterAgent step."""
        if hasattr(agent, "act"):
            # agent is a CharacterAgent
            return agent.act(content, context)
        elif hasattr(self.novel_orchestrator, "director_agent"):
            # Fallback to director's handoff mechanism
            director = self.novel_orchestrator.director_agent
            if hasattr(director, "execute_scene"):
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(director.execute_scene(content.get("script")))
                    return result
                finally:
                    loop.close()
        return str(content)

    def _reality_checker_executor(self, agent: Any, content: Any, context: Dict) -> Dict[str, Any]:
        """Execute RealityChecker validation step."""
        if self.reality_checker is None:
            return {"status": "PASS", "score": 1.0, "issues": []}

        # Build validation criteria
        criteria = {
            "characters": context.get("characters", {}),
            "previous_summary": context.get("previous_summary", ""),
            "required_elements": context.get("required_elements", []),
            "prohibited_elements": context.get("prohibited_elements", []),
        }

        # Validate the content
        validation_result = self.reality_checker.validate_content(
            str(content),
            criteria
        )

        return {
            "status": validation_result.status,
            "score": validation_result.score,
            "issues": validation_result.issues,
            "evidence_required": validation_result.evidence_required,
        }

    def _assembler_executor(self, agent: Any, content: Any, context: Dict) -> str:
        """Execute final assembly step."""
        if hasattr(self.novel_orchestrator, "director_agent"):
            director = self.novel_orchestrator.director_agent
            if hasattr(director, "assemble_scene_output"):
                return director.assemble_scene_output(content.get("script", content))
        return str(content)

    def _novel_orchestrator_executor(self, agent: Any, content: Any, context: Dict) -> Dict[str, Any]:
        """Execute NovelOrchestrator step."""
        return agent.orchestrate_chapter(
            chapter_number=context.get("chapter_number", 1),
            chapter_outline=content,
            context=context,
        )

    def execute_chapter_pipeline(
        self,
        chapter_outline: str,
        context: Dict[str, Any],
    ) -> PipelineResult:
        """Execute the novel generation pipeline for a chapter.

        Args:
            chapter_outline: Chapter outline/summary
            context: Execution context including characters, location, etc.

        Returns:
            PipelineResult with all outputs and handoffs
        """
        # Build agent pipeline
        agent_pipeline = [step.agent_name for step in self.config.pipeline_steps]

        # Create workflow orchestrator
        pipeline_config = self._create_pipeline_config()
        workflow = WorkflowOrchestrator(
            agents=self._agents,
            quality_gate=self.reality_checker,
            config=pipeline_config,
        )

        # Set executors for each step
        for step in self.config.pipeline_steps:
            workflow.set_agent_executor(step.agent_name, self._get_agent_executor(step))

        # Initialize context
        initial_context = {
            **context,
            "chapter_outline": chapter_outline,
        }

        # Execute pipeline
        result = workflow.execute_pipeline(
            pipeline=agent_pipeline,
            initial_input=chapter_outline,
            context=initial_context,
        )

        logger.info(
            f"[NovelWorkflow] Chapter {context.get('chapter_number', '?')} pipeline: "
            f"{'SUCCESS' if result.success else 'FAILED'} "
            f"({result.total_steps} steps, {result.execution_time_seconds:.2f}s)"
        )

        return result

    def execute_scene_pipeline(
        self,
        scene_outline: str,
        characters: Dict[str, Dict[str, Any]],
        context: Dict[str, Any],
    ) -> PipelineResult:
        """Execute pipeline for a single scene.

        Shorter pipeline optimized for scene-level generation.

        Args:
            scene_outline: Scene description
            characters: Character profiles
            context: Additional context

        Returns:
            PipelineResult for the scene
        """
        # Scene-level pipeline
        scene_config = NovelWorkflowConfig(
            pipeline_steps=[
                NovelPipelineStep(agent_name="director", step_type="plan"),
                NovelPipelineStep(agent_name="character", step_type="generate"),
                NovelPipelineStep(agent_name="reality_checker", step_type="validate"),
            ],
            enable_quality_gate=True,
            quality_gate_interval=1,  # Validate every step
            stop_on_quality_failure=False,  # Continue even if quality needs work
        )

        # Temporarily use scene config
        original_config = self.config
        self.config = scene_config

        try:
            result = self.execute_chapter_pipeline(
                chapter_outline=scene_outline,
                context={**context, "characters": characters},
            )
        finally:
            self.config = original_config

        return result

    def get_pipeline_dag(self) -> List[Dict[str, Any]]:
        """Get pipeline as DAG for visualization.

        Returns:
            List of step definitions with connections
        """
        dag = []
        for i, step in enumerate(self.config.pipeline_steps):
            dag.append({
                "id": i,
                "agent": step.agent_name,
                "type": step.step_type,
                "quality_gate": (
                    step.step_type == "validate" or
                    (self.config.enable_quality_gate and i % self.config.quality_gate_interval == 0)
                ),
                "next": [j for j in range(i + 1, len(self.config.pipeline_steps))],
            })
        return dag


def create_novel_workflow(
    novel_orchestrator: NovelOrchestrator,
    reality_checker: RealityChecker = None,
    pipeline_config: Dict[str, Any] = None,
) -> NovelWorkflowOrchestrator:
    """Factory function to create NovelWorkflowOrchestrator.

    Args:
        novel_orchestrator: NovelOrchestrator instance
        reality_checker: Optional RealityChecker (uses orchestrator's if not provided)
        pipeline_config: Optional pipeline configuration

    Returns:
        Configured NovelWorkflowOrchestrator
    """
    config = None
    if pipeline_config:
        steps = pipeline_config.get("steps", STANDARD_NOVEL_PIPELINE)
        config = NovelWorkflowConfig(
            pipeline_steps=[
                NovelPipelineStep(**s) if isinstance(s, dict) else s
                for s in steps
            ],
            enable_quality_gate=pipeline_config.get("enable_quality_gate", True),
            quality_gate_interval=pipeline_config.get("quality_gate_interval", 2),
            stop_on_quality_failure=pipeline_config.get("stop_on_quality_failure", True),
            max_retries=pipeline_config.get("max_retries", 2),
        )

    return NovelWorkflowOrchestrator(
        novel_orchestrator=novel_orchestrator,
        reality_checker=reality_checker,
        config=config,
    )
