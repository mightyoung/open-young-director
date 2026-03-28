# -*- encoding: utf-8 -*-
"""Tests for agent collaboration protocols.

Run with: pytest lib/knowledge_base/tests/agents/test_protocols.py -v
"""

import pytest
from dataclasses import dataclass
from typing import Any, Dict

# Import from protocols
from agents.protocols.handoff import (
    AgentHandoff,
    HandoffResult,
    HandoffStatus,
    QualityGateError,
)
from agents.protocols.context import (
    ContextManager,
    ExecutionContext,
    create_pipeline_context,
)
from agents.protocols.workflow import (
    WorkflowOrchestrator,
    PipelineConfig,
    PipelineResult,
)


# Mock agents for testing
class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str, output: Any = None, fail: bool = False):
        self.name = name
        self.output = output or f"output_from_{name}"
        self.fail = fail
        self.execute_count = 0

    def execute(self, content: Any, context: Dict) -> Any:
        """Execute the agent."""
        self.execute_count += 1
        if self.fail:
            raise RuntimeError(f"{self.name} failed")
        return f"{self.output}_{self.execute_count}"


class TestAgentHandoff:
    """Tests for AgentHandoff dataclass."""

    def test_create_handoff(self):
        """Test creating a basic handoff."""
        handoff = AgentHandoff(
            from_agent="director",
            to_agent="character",
            content={"scene": "test"},
            context={"chapter": 1},
        )

        assert handoff.from_agent == "director"
        assert handoff.to_agent == "character"
        assert handoff.content == {"scene": "test"}
        assert handoff.context == {"chapter": 1}
        assert handoff.status == HandoffStatus.PENDING
        assert handoff.quality_gate is True

    def test_handoff_status_transitions(self):
        """Test handoff status changes."""
        handoff = AgentHandoff(
            from_agent="a",
            to_agent="b",
            content="test",
        )

        handoff.mark_in_progress()
        assert handoff.status == HandoffStatus.IN_PROGRESS

        handoff.mark_validated()
        assert handoff.status == HandoffStatus.VALIDATED
        assert handoff.validated_at is not None

        handoff.mark_completed("result")
        assert handoff.status == HandoffStatus.COMPLETED
        assert handoff.completed_at is not None

    def test_handoff_failed(self):
        """Test failed handoff."""
        handoff = AgentHandoff(
            from_agent="a",
            to_agent="b",
            content="test",
        )

        handoff.mark_failed("Something went wrong")
        assert handoff.status == HandoffStatus.FAILED
        assert handoff.metadata["error"] == "Something went wrong"


class TestHandoffResult:
    """Tests for HandoffResult."""

    def test_successful_result(self):
        """Test successful handoff result."""
        handoff = AgentHandoff(
            from_agent="director",
            to_agent="character",
            content="scene_content",
        )
        handoff.mark_completed("response")

        result = HandoffResult(
            handoff=handoff,
            output="character_response",
            success=True,
        )

        assert result.is_success is True
        assert result.output == "character_response"
        assert result.error is None

    def test_failed_result(self):
        """Test failed handoff result."""
        handoff = AgentHandoff(
            from_agent="director",
            to_agent="character",
            content="scene_content",
        )
        handoff.mark_failed("execution failed")

        result = HandoffResult(
            handoff=handoff,
            error="execution failed",
            success=False,
        )

        assert result.is_success is False
        assert result.error == "execution failed"


class TestQualityGateError:
    """Tests for QualityGateError."""

    def test_quality_gate_error(self):
        """Test QualityGateError exception."""
        error = QualityGateError(
            "Content failed validation",
            issues=["Issue 1", "Issue 2"],
            evidence_required=["Evidence 1"],
            validation_result={"status": "FAIL"},
        )

        assert "Content failed validation" in str(error)
        assert error.issues == ["Issue 1", "Issue 2"]
        assert error.evidence_required == ["Evidence 1"]


class TestExecutionContext:
    """Tests for ExecutionContext."""

    def test_create_context(self):
        """Test creating execution context."""
        ctx = ExecutionContext(
            agent_name="director",
            pipeline_step=0,
            content={"scene": "test"},
            metadata={"chapter": 1},
        )

        assert ctx.agent_name == "director"
        assert ctx.pipeline_step == 0
        assert ctx.content == {"scene": "test"}
        assert ctx.metadata["chapter"] == 1

    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = ExecutionContext(
            agent_name="director",
            pipeline_step=0,
            content="test content",
        )

        d = ctx.to_dict()
        assert d["agent_name"] == "director"
        assert d["pipeline_step"] == 0
        assert d["content_type"] == "str"


class TestContextManager:
    """Tests for ContextManager."""

    def test_set_and_get_context(self):
        """Test setting and getting context."""
        manager = ContextManager()

        ctx = create_pipeline_context("director", "initial_content", {"chapter": 1})
        manager.set_context("director", ctx)

        retrieved = manager.get_context("director")
        assert retrieved is not None
        assert retrieved.agent_name == "director"

    def test_propagate_context(self):
        """Test context propagation between agents."""
        manager = ContextManager()

        # Set initial context
        initial_ctx = create_pipeline_context(
            "director",
            "scene_outline",
            {"chapter": 1, "characters": {"韩林": {}}}
        )
        manager.set_context("director", initial_ctx)

        # Propagate to character
        char_ctx = manager.propagate(
            from_agent="director",
            to_agent="character",
            additional_metadata={"beat": 1}
        )

        assert char_ctx.agent_name == "character"
        assert char_ctx.pipeline_step == 1
        assert char_ctx.metadata["chapter"] == 1
        assert char_ctx.metadata["beat"] == 1
        assert "propagation_history" in char_ctx.metadata

    def test_propagation_history(self):
        """Test that propagation history is maintained."""
        manager = ContextManager()

        initial_ctx = create_pipeline_context("a", "content", {})
        manager.set_context("a", initial_ctx)

        manager.propagate("a", "b")
        manager.propagate("b", "c")

        history = manager.get_history()
        assert len(history) == 2
        assert history[0]["from_agent"] == "a"
        assert history[0]["to_agent"] == "b"


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_default_config(self):
        """Test default pipeline configuration."""
        config = PipelineConfig()

        assert config.max_retries == 2
        assert config.timeout_seconds == 300
        assert config.enable_quality_gate is True
        assert config.stop_on_quality_failure is True
        assert config.quality_gate_interval == 0

    def test_custom_config(self):
        """Test custom pipeline configuration."""
        config = PipelineConfig(
            max_retries=5,
            quality_gate_interval=1,
        )

        assert config.max_retries == 5
        assert config.quality_gate_interval == 1

    def test_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "max_retries": 3,
            "enable_quality_gate": False,
        }
        config = PipelineConfig.from_dict(data)

        assert config.max_retries == 3
        assert config.enable_quality_gate is False


class TestWorkflowOrchestrator:
    """Tests for WorkflowOrchestrator."""

    def test_create_orchestrator(self):
        """Test creating workflow orchestrator."""
        agents = {
            "director": MockAgent("director"),
            "character": MockAgent("character"),
        }

        orchestrator = WorkflowOrchestrator(agents=agents)

        assert orchestrator.agents == agents
        assert orchestrator.config.enable_quality_gate is True

    def test_execute_simple_pipeline(self):
        """Test executing a simple pipeline."""
        agents = {
            "director": MockAgent("director", output="scene_plan"),
            "character": MockAgent("character", output="dialogue"),
        }

        orchestrator = WorkflowOrchestrator(agents=agents)
        result = orchestrator.execute_pipeline(
            pipeline=["director", "character"],
            initial_input="chapter_outline",
            context={"chapter": 1}
        )

        assert result.success is True
        assert result.total_steps == 2
        assert len(result.handoffs) == 2
        assert result.pipeline == ["director", "character"]

    def test_pipeline_with_quality_gate(self):
        """Test pipeline with quality gate enabled."""
        # Create mock reality checker
        class MockRealityChecker:
            def validate_content(self, content, criteria):
                class MockResult:
                    status = "PASS"
                    score = 0.95
                    issues = []
                    evidence_required = []
                return MockResult()

        agents = {
            "director": MockAgent("director"),
            "character": MockAgent("character"),
        }

        orchestrator = WorkflowOrchestrator(
            agents=agents,
            quality_gate=MockRealityChecker(),
            config=PipelineConfig(quality_gate_interval=1),
        )

        result = orchestrator.execute_pipeline(
            pipeline=["director", "character"],
            initial_input="outline",
        )

        assert result.success is True
        # Quality gate ran on each step
        for h in result.handoffs:
            assert h.validation is not None

    def test_pipeline_failure(self):
        """Test pipeline with failing agent."""
        agents = {
            "director": MockAgent("director"),
            "character": MockAgent("character", fail=True),
        }

        orchestrator = WorkflowOrchestrator(agents=agents)
        result = orchestrator.execute_pipeline(
            pipeline=["director", "character"],
            initial_input="outline",
        )

        assert result.success is False
        assert result.error is not None
        assert "character failed" in result.error

    def test_pipeline_execution_time(self):
        """Test that execution time is recorded."""
        agents = {
            "a": MockAgent("a"),
            "b": MockAgent("b"),
        }

        orchestrator = WorkflowOrchestrator(agents=agents)
        result = orchestrator.execute_pipeline(
            pipeline=["a", "b"],
            initial_input="test",
        )

        assert result.execution_time_seconds > 0


class TestPipelineResult:
    """Tests for PipelineResult."""

    def test_result_properties(self):
        """Test result properties."""
        handoff = AgentHandoff(from_agent="a", to_agent="b", content="test")
        handoff.mark_completed()

        result = PipelineResult(
            pipeline=["a", "b", "c"],
            handoffs=[
                HandoffResult(handoff=handoff, success=True),
            ],
            final_output="final",
            success=True,
            total_steps=3,
        )

        assert result.handoff_count == 1
        assert result.failed_handoffs == []
        assert result.success is True

    def test_result_with_failures(self):
        """Test result with failed handoffs."""
        h1 = AgentHandoff(from_agent="a", to_agent="b", content="t")
        h1.mark_completed()

        h2 = AgentHandoff(from_agent="b", to_agent="c", content="t")
        h2.mark_failed("error")

        result = PipelineResult(
            pipeline=["a", "b", "c"],
            handoffs=[
                HandoffResult(handoff=h1, success=True),
                HandoffResult(handoff=h2, success=False, error="error"),
            ],
            success=False,
        )

        assert len(result.failed_handoffs) == 1
        assert result.failed_handoffs[0].handoff.to_agent == "c"


# Integration tests
class TestProtocolIntegration:
    """Integration tests for protocol components."""

    def test_full_pipeline_with_context(self):
        """Test complete pipeline with context propagation."""
        manager = ContextManager()

        # Create initial context
        ctx = create_pipeline_context(
            "director",
            {"outline": "scene outline", "characters": {"韩林": {}}},
            {"chapter": 1}
        )
        manager.set_context("director", ctx)

        # Simulate pipeline
        agents = {
            "director": MockAgent("director", output={"scene": "planned"}),
            "character": MockAgent("character", output="dialogue"),
            "assembler": MockAgent("assembler", output="final_scene"),
        }

        orchestrator = WorkflowOrchestrator(
            agents=agents,
            config=PipelineConfig(enable_quality_gate=False),
        )

        result = orchestrator.execute_pipeline(
            pipeline=["director", "character", "assembler"],
            initial_input={"outline": "scene outline"},
            context={"chapter": 1, "characters": {"韩林": {}}},
        )

        assert result.success is True
        assert result.total_steps == 3
        assert manager.get_history() is not None
