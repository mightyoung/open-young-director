"""Pipeline orchestrator for novel content generation.

Coordinates stage execution using:
- StageSequence: stage ordering and navigation
- CheckpointManager: atomic file I/O for state persistence
- OutputPacker: output formatting for different modes
"""

import logging
from typing import TYPE_CHECKING, Any

from crewai.content.novel.orchestrator.checkpoint_manager import CheckpointManager
from crewai.content.novel.orchestrator.output_packer import OutputPacker
from crewai.content.novel.orchestrator.stage_sequence import StageSequence


if TYPE_CHECKING:
    from crewai.content.base import BaseCrewOutput


logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Thin orchestrator that coordinates stage execution.

    Responsibilities:
    - Stage progression using StageSequence
    - Delegating to crews for actual work
    - Checkpoint management via CheckpointManager
    - Output packing via OutputPacker

    This class is NOT responsible for:
    - Crew creation/management (delegates to NovelCrew)
    - Approval workflow (handled by NovelCrew)
    - Pipeline state management (handled by PipelineState)
    """

    def __init__(
        self,
        config: dict,
        checkpoint_manager: CheckpointManager | None = None,
    ):
        """Initialize PipelineOrchestrator.

        Args:
            config: Novel configuration dict
            checkpoint_manager: Optional checkpoint manager (created if None)
        """
        self.config = config
        self._checkpoint_manager = checkpoint_manager or CheckpointManager(config)

    @property
    def checkpoint_manager(self) -> CheckpointManager:
        """Get the checkpoint manager."""
        return self._checkpoint_manager

    def get_stage_indices(
        self,
        current_stage: str,
        target_stage: str,
    ) -> tuple[int, int, int]:
        """Get stage indices for pipeline execution.

        Args:
            current_stage: Current pipeline stage
            target_stage: Target stage (or "complete")

        Returns:
            tuple: (current_idx, target_idx, outline_idx)
        """
        current_idx = StageSequence.get_stage_index(current_stage)
        if current_idx == 0 and current_stage != "init":
            current_idx = 0

        target_idx = StageSequence.get_stage_index(target_stage)
        if target_idx == 0 and target_stage != "init":
            target_idx = len(StageSequence.STAGES) - 1

        outline_idx = StageSequence.get_stage_index("outline")

        return current_idx, target_idx, outline_idx

    def should_execute_stage(
        self,
        stage: str,
        current_idx: int,
        target_idx: int,
    ) -> bool:
        """Check if a stage should be executed.

        Args:
            stage: Stage name
            current_idx: Current stage index
            target_idx: Target stage index

        Returns:
            bool: True if stage should execute
        """
        stage_idx = StageSequence.get_stage_index(stage)
        return current_idx < stage_idx <= target_idx

    def pack_stop_output(
        self,
        stage: str,
        summary: dict,
        execution_time: float,
    ) -> "BaseCrewOutput":
        """Pack output for stop_at mode.

        Args:
            stage: Current stage name
            summary: Stage-specific summary data
            execution_time: Execution time in seconds

        Returns:
            BaseCrewOutput: Packed output
        """
        summary["stage"] = stage
        return OutputPacker.pack_state_output(summary, execution_time)

    def pack_approval_output(
        self,
        stage: str,
        content: dict,
        execution_time: float,
        pipeline_state: Any = None,
        output_dir: str | None = None,
    ) -> "BaseCrewOutput":
        """Pack output for approval mode.

        Args:
            stage: Current stage name
            content: Stage content for approval
            execution_time: Execution time in seconds
            pipeline_state: Optional PipelineState for saving
            output_dir: Optional output directory for state file

        Returns:
            BaseCrewOutput: Packed approval output
        """
        if pipeline_state is not None:
            return OutputPacker.pack_approval_output(
                pipeline_state=pipeline_state,
                stage=stage,
                content=content,
                execution_time=execution_time,
                output_dir=output_dir,
            )

        # P1: Fallback when no pipeline_state - use shared fallback method
        return OutputPacker.pack_fallback_approval_output(
            stage=stage,
            content=content,
            execution_time=execution_time,
            topic="unknown",
            output_dir=output_dir,
        )

    def get_next_stage(self, current: str) -> str | None:
        """Get the next stage in the pipeline.

        Args:
            current: Current stage name

        Returns:
            str | None: Next stage name or None if complete
        """
        return StageSequence.get_next_stage(current)

    def is_stage_reached(self, current_idx: int, stage: str) -> bool:
        """Check if a stage has been reached.

        Args:
            current_idx: Current stage index
            stage: Stage name to check

        Returns:
            bool: True if stage has been reached
        """
        return StageSequence.is_stage_reached(current_idx, stage)

    def get_all_stages(self) -> list[str]:
        """Get all stage names in order.

        Returns:
            list[str]: All stage names
        """
        return StageSequence.STAGES.copy()
