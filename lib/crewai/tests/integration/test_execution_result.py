"""Tests for ExecutionResult and failure semantics."""
import pytest
from crewai.content.exceptions import (
    ExecutionStatus,
    StageFailure,
    ExecutionResult,
)


class TestExecutionStatus:
    """Tests for ExecutionStatus enum."""

    def test_status_values(self):
        """Test that status values are correct."""
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.PARTIAL.value == "partial"
        assert ExecutionStatus.FAILED.value == "failed"


class TestStageFailure:
    """Tests for StageFailure dataclass."""

    def test_create_failure(self):
        """Test creating a stage failure."""
        failure = StageFailure(
            stage="outline",
            reason="Evaluation failed",
            details={"score": 5.0},
            recoverable=True,
        )

        assert failure.stage == "outline"
        assert failure.reason == "Evaluation failed"
        assert failure.details == {"score": 5.0}
        assert failure.recoverable is True


class TestExecutionResult:
    """Tests for ExecutionResult dataclass."""

    def test_default_is_success(self):
        """Test that default execution result is success."""
        result = ExecutionResult()

        assert result.status == ExecutionStatus.SUCCESS
        assert result.failures == []
        assert result.completed_stages == []

    def test_add_failure_partial(self):
        """Test adding a recoverable failure makes status partial."""
        result = ExecutionResult()
        result.add_failure(
            stage="volume",
            reason="Volume generation failed",
            recoverable=True,
        )

        assert result.status == ExecutionStatus.PARTIAL
        assert len(result.failures) == 1
        assert result.failures[0].stage == "volume"

    def test_add_failure_not_recoverable(self):
        """Test adding non-recoverable failure makes status failed."""
        result = ExecutionResult()
        result.add_failure(
            stage="writing",
            reason="Writing crashed",
            recoverable=False,
        )

        assert result.status == ExecutionStatus.FAILED

    def test_add_completed_stage(self):
        """Test adding completed stages."""
        result = ExecutionResult()
        result.add_completed_stage("outline")
        result.add_completed_stage("volume")

        assert "outline" in result.completed_stages
        assert "volume" in result.completed_stages
        assert len(result.completed_stages) == 2

    def test_to_metadata(self):
        """Test conversion to metadata dict."""
        result = ExecutionResult()
        result.add_completed_stage("outline")
        result.add_failure(
            stage="volume",
            reason="Failed",
            details={"error": "timeout"},
            recoverable=True,
        )

        metadata = result.to_metadata()

        assert metadata["status"] == "partial"
        assert len(metadata["failures"]) == 1
        assert metadata["failures"][0]["stage"] == "volume"
        assert metadata["completed_stages"] == ["outline"]

    def test_is_success_property(self):
        """Test is_success property."""
        result = ExecutionResult()
        assert result.is_success is True

        result.status = ExecutionStatus.PARTIAL
        assert result.is_success is False

        result.status = ExecutionStatus.FAILED
        assert result.is_success is False

    def test_is_partial_property(self):
        """Test is_partial property."""
        result = ExecutionResult()
        assert result.is_partial is False

        result.status = ExecutionStatus.PARTIAL
        assert result.is_partial is True

    def test_is_failed_property(self):
        """Test is_failed property."""
        result = ExecutionResult()
        assert result.is_failed is False

        result.status = ExecutionStatus.FAILED
        assert result.is_failed is True
