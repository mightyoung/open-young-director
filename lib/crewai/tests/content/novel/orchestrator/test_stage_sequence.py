"""Tests for StageSequence."""

import pytest
from crewai.content.novel.orchestrator.stage_sequence import StageSequence


class TestStageSequence:
    """Tests for StageSequence stage ordering utility."""

    def test_stages_order(self):
        """Test that stages are in correct order."""
        assert StageSequence.STAGES == [
            "init", "outline", "evaluation", "volume", "summary", "writing", "complete"
        ]

    def test_get_stage_index_valid(self):
        """Test getting index of valid stages."""
        assert StageSequence.get_stage_index("init") == 0
        assert StageSequence.get_stage_index("outline") == 1
        assert StageSequence.get_stage_index("evaluation") == 2
        assert StageSequence.get_stage_index("volume") == 3
        assert StageSequence.get_stage_index("summary") == 4
        assert StageSequence.get_stage_index("writing") == 5
        assert StageSequence.get_stage_index("complete") == 6

    def test_get_stage_index_invalid(self):
        """Test getting index of invalid stage returns 0."""
        assert StageSequence.get_stage_index("invalid") == 0
        assert StageSequence.get_stage_index("") == 0

    def test_should_execute_stage(self):
        """Test stage execution decision logic."""
        # Should execute stages between current and target (inclusive of target)
        assert StageSequence.should_execute_stage(0, 2, "outline") is True
        assert StageSequence.should_execute_stage(0, 2, "evaluation") is True
        assert StageSequence.should_execute_stage(1, 2, "evaluation") is True

        # Should not execute stages already passed
        assert StageSequence.should_execute_stage(2, 3, "outline") is False
        assert StageSequence.should_execute_stage(3, 5, "volume") is False

        # Should not execute stages beyond target
        assert StageSequence.should_execute_stage(0, 2, "volume") is False
        assert StageSequence.should_execute_stage(0, 2, "summary") is False

    def test_is_stage_reached(self):
        """Test stage reachability check."""
        assert StageSequence.is_stage_reached(0, "init") is True
        assert StageSequence.is_stage_reached(1, "init") is True
        assert StageSequence.is_stage_reached(1, "outline") is True
        assert StageSequence.is_stage_reached(2, "outline") is True
        assert StageSequence.is_stage_reached(1, "evaluation") is False

    def test_get_next_stage(self):
        """Test getting next stage."""
        assert StageSequence.get_next_stage("init") == "outline"
        assert StageSequence.get_next_stage("outline") == "evaluation"
        assert StageSequence.get_next_stage("evaluation") == "volume"
        assert StageSequence.get_next_stage("writing") == "complete"
        assert StageSequence.get_next_stage("complete") is None
