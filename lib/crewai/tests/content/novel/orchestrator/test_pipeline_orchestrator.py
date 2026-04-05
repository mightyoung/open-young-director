"""Tests for PipelineOrchestrator."""

import pytest
from unittest.mock import MagicMock, patch

from crewai.content.novel.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from crewai.content.novel.orchestrator.stage_sequence import StageSequence
from crewai.content.novel.orchestrator.checkpoint_manager import CheckpointManager


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator."""

    def test_init_with_config(self):
        """Test initialization with config dict."""
        config = {"topic": "Test Novel", "style": "xianxia"}
        orchestrator = PipelineOrchestrator(config)
        assert orchestrator.config == config
        assert orchestrator.checkpoint_manager is not None

    def test_init_with_checkpoint_manager(self):
        """Test initialization with explicit checkpoint manager."""
        config = {"topic": "Test Novel"}
        checkpoint_manager = CheckpointManager(config)
        orchestrator = PipelineOrchestrator(config, checkpoint_manager=checkpoint_manager)
        assert orchestrator.checkpoint_manager is checkpoint_manager

    def test_checkpoint_manager_property(self):
        """Test checkpoint_manager property returns correct instance."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)
        assert isinstance(orchestrator.checkpoint_manager, CheckpointManager)

    def test_get_stage_indices_basic(self):
        """Test basic stage index computation."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        current_idx, target_idx, outline_idx = orchestrator.get_stage_indices("init", "outline")

        assert current_idx == 0  # init
        assert target_idx == 1   # outline
        assert outline_idx == 1  # outline

    def test_get_stage_indices_from_outline(self):
        """Test stage indices when resuming from outline."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        current_idx, target_idx, outline_idx = orchestrator.get_stage_indices("outline", "complete")

        assert current_idx == 1   # outline
        assert target_idx == 6   # complete
        assert outline_idx == 1   # outline

    def test_get_stage_indices_invalid_stage(self):
        """Test stage indices with invalid stage defaults to complete."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        current_idx, target_idx, _ = orchestrator.get_stage_indices("init", "invalid")

        assert target_idx == 6  # complete

    def test_should_execute_stage_outline(self):
        """Test should_execute_stage for outline stage."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # From init, should execute outline
        assert orchestrator.should_execute_stage("outline", current_idx=0, target_idx=6) is True

        # From outline, should NOT execute outline again
        assert orchestrator.should_execute_stage("outline", current_idx=1, target_idx=6) is False

        # From init, target is outline itself
        assert orchestrator.should_execute_stage("outline", current_idx=0, target_idx=1) is True

    def test_should_execute_stage_evaluation(self):
        """Test should_execute_stage for evaluation stage."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # From outline, should execute evaluation
        assert orchestrator.should_execute_stage("evaluation", current_idx=1, target_idx=6) is True

        # From evaluation, should NOT execute evaluation again
        assert orchestrator.should_execute_stage("evaluation", current_idx=2, target_idx=6) is False

    def test_should_execute_stage_volume(self):
        """Test should_execute_stage for volume stage."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # From init, should NOT directly execute volume (outline and evaluation come first)
        assert orchestrator.should_execute_stage("volume", current_idx=0, target_idx=6) is True

        # From evaluation, should execute volume
        assert orchestrator.should_execute_stage("volume", current_idx=2, target_idx=6) is True

    def test_should_execute_stage_beyond_target(self):
        """Test should_execute_stage when target is before stage."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # Target is outline, should not execute volume
        assert orchestrator.should_execute_stage("volume", current_idx=0, target_idx=1) is False

    def test_pack_stop_output(self):
        """Test packing output for stop_at mode."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        summary = {"world_name": "Test World", "plot_ready": True}
        result = orchestrator.pack_stop_output("outline", summary, 10.0)

        assert result.metadata["pipeline_state"]["stage"] == "outline"
        assert result.metadata["pipeline_state"]["world_name"] == "Test World"
        assert result.metadata["stopped"] is True

    def test_pack_approval_output(self):
        """Test packing output for approval mode."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        content = {"world_data": {"name": "Test"}, "plot_data": {}}
        result = orchestrator.pack_approval_output("outline", content, 5.0)

        assert result.metadata["stage"] == "outline"
        assert result.metadata["approval_required"] is True
        assert result.metadata["stage_status"] == "pending_approval"

    def test_get_next_stage(self):
        """Test getting next stage."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        assert orchestrator.get_next_stage("init") == "outline"
        assert orchestrator.get_next_stage("outline") == "evaluation"
        assert orchestrator.get_next_stage("evaluation") == "volume"
        assert orchestrator.get_next_stage("volume") == "summary"
        assert orchestrator.get_next_stage("summary") == "writing"
        assert orchestrator.get_next_stage("writing") == "complete"
        assert orchestrator.get_next_stage("complete") is None

    def test_is_stage_reached(self):
        """Test checking if stage has been reached."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # At init (idx 0)
        assert orchestrator.is_stage_reached(0, "init") is True
        assert orchestrator.is_stage_reached(0, "outline") is False

        # At outline (idx 1)
        assert orchestrator.is_stage_reached(1, "init") is True
        assert orchestrator.is_stage_reached(1, "outline") is True
        assert orchestrator.is_stage_reached(1, "evaluation") is False

        # At complete (idx 6)
        assert orchestrator.is_stage_reached(6, "complete") is True

    def test_get_all_stages(self):
        """Test getting all stages."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        stages = orchestrator.get_all_stages()
        assert stages == ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]
        assert len(stages) == 7


class TestPipelineOrchestratorIntegration:
    """Integration tests for PipelineOrchestrator with other components."""

    def test_orchestrator_with_stage_sequence(self):
        """Test PipelineOrchestrator works with StageSequence."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # Verify StageSequence is used correctly
        stages = StageSequence.STAGES
        orchestrator_stages = orchestrator.get_all_stages()

        assert orchestrator_stages == stages

        # Verify stage navigation
        assert orchestrator.get_next_stage("init") == "outline"
        current_idx = StageSequence.get_stage_index("init")
        next_stage = orchestrator.get_next_stage("init")
        next_idx = StageSequence.get_stage_index(next_stage)
        assert next_idx > current_idx

    def test_orchestrator_with_checkpoint_manager(self):
        """Test PipelineOrchestrator checkpoint integration."""
        config = {"topic": "Test Novel"}
        checkpoint_manager = CheckpointManager(config)
        orchestrator = PipelineOrchestrator(config, checkpoint_manager=checkpoint_manager)

        # Verify checkpoint manager is accessible
        assert orchestrator.checkpoint_manager is checkpoint_manager

        # Verify output_dir is computed correctly
        assert "novels/" in orchestrator.checkpoint_manager.output_dir

    def test_orchestrator_stage_execution_flow(self):
        """Test full stage execution flow simulation."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        # Simulate running from init to outline
        current_stage = "init"
        target_stage = "outline"

        current_idx, target_idx, outline_idx = orchestrator.get_stage_indices(current_stage, target_stage)

        # Verify we should execute outline
        assert orchestrator.should_execute_stage("outline", current_idx, target_idx) is True

        # Verify we should NOT execute other stages
        assert orchestrator.should_execute_stage("evaluation", current_idx, target_idx) is False
        assert orchestrator.should_execute_stage("volume", current_idx, target_idx) is False

        # Simulate reaching outline
        new_current_idx = StageSequence.get_stage_index("outline")
        assert orchestrator.is_stage_reached(new_current_idx, "outline") is True

    def test_orchestrator_full_pipeline_flow(self):
        """Test flow from init to complete."""
        config = {"topic": "Test Novel"}
        orchestrator = PipelineOrchestrator(config)

        stages_to_run = []
        current_idx = 0
        target_idx = StageSequence.get_stage_index("complete")

        # Simulate which stages would execute
        for stage in orchestrator.get_all_stages():
            if stage in ("init", "complete"):
                # init is the starting point, complete is the terminal state
                continue
            if orchestrator.should_execute_stage(stage, current_idx, target_idx):
                stages_to_run.append(stage)

        # All stages except init and complete should be in the list
        assert "outline" in stages_to_run
        assert "evaluation" in stages_to_run
        assert "volume" in stages_to_run
        assert "summary" in stages_to_run
        assert "writing" in stages_to_run
        assert len(stages_to_run) == 5
