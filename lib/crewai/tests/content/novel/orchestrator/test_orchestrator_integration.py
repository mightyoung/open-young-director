"""Integration tests for orchestrator module."""

import pytest
from crewai.content.novel.orchestrator import StageSequence, OutputPacker, CheckpointManager


class TestOrchestratorIntegration:
    """Integration tests for orchestrator components working together."""

    def test_all_exports_importable(self):
        """Verify all orchestrator exports are importable."""
        from crewai.content.novel.orchestrator import StageSequence, OutputPacker, CheckpointManager
        assert StageSequence is not None
        assert OutputPacker is not None
        assert CheckpointManager is not None

    def test_stage_sequence_with_output_packer(self):
        """Test StageSequence and OutputPacker can be used together."""
        # Get stage index from StageSequence
        outline_idx = StageSequence.get_stage_index("outline")
        assert outline_idx == 1

        # Use OutputPacker with stage name
        summary = {"stage": "outline", "world_name": "Test"}
        result = OutputPacker.pack_state_output(summary, 10.0)
        assert result.metadata["pipeline_state"] == summary

    def test_checkpoint_manager_with_stage_sequence(self):
        """Test CheckpointManager can be used with stage info from StageSequence."""
        config = {"topic": "Test Novel"}
        manager = CheckpointManager(config)

        # Verify output_dir is computed correctly
        assert "novels/" in manager.output_dir

        # Verify stage index can be used for navigation
        current_idx = StageSequence.get_stage_index("outline")
        next_stage = StageSequence.get_next_stage("outline")
        assert next_stage == "evaluation"

    def test_stage_sequence_stages_match_output_packer(self):
        """Verify all stages in StageSequence work with OutputPacker."""
        stages = ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]

        for stage in stages:
            idx = StageSequence.get_stage_index(stage)
            assert idx >= 0

            # Verify OutputPacker can summarize content for each stage
            content = {"test": "data"}
            summary = OutputPacker.summarize_stage_content(stage, content)
            assert isinstance(summary, dict)

    def test_approval_output_uses_correct_stage(self):
        """Test approval output is created with correct stage info."""
        from unittest.mock import MagicMock

        mock_pipeline_state = MagicMock()
        content = {"world_data": {"name": "Test"}, "plot_data": {}}

        result = OutputPacker.pack_approval_output(
            mock_pipeline_state, "outline", content, 5.0
        )

        assert result.metadata["stage"] == "outline"
        assert result.metadata["approval_required"] is True
        assert result.metadata["stage_status"] == "pending_approval"
