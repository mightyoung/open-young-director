"""Stage sequencing utilities for novel pipeline."""


class StageSequence:
    """Stage ordering and navigation for the novel generation pipeline.

    Stages in order:
        init -> outline -> evaluation -> volume -> summary -> writing -> complete

    Usage:
        idx = StageSequence.get_stage_index("outline")
        should_run = StageSequence.should_execute_stage(current_idx, target_idx, "evaluation")
    """

    STAGES = ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]

    @classmethod
    def get_stage_index(cls, stage: str) -> int:
        """Get the index of a stage in the pipeline.

        Args:
            stage: Stage name (e.g., "outline", "evaluation")

        Returns:
            Stage index, or 0 if stage not found
        """
        try:
            return cls.STAGES.index(stage)
        except ValueError:
            return 0

    @classmethod
    def should_execute_stage(
        cls,
        current_idx: int,
        target_idx: int,
        stage: str,
    ) -> bool:
        """Check if a stage should be executed given current position and target.

        Args:
            current_idx: Current stage index
            target_idx: Target stage index (stop_at)
            stage: Stage to check

        Returns:
            True if the stage should be executed
        """
        stage_idx = cls.get_stage_index(stage)
        return current_idx < stage_idx <= target_idx

    @classmethod
    def is_stage_reached(cls, current_idx: int, stage: str) -> bool:
        """Check if a stage has been reached.

        Args:
            current_idx: Current stage index
            stage: Stage to check

        Returns:
            True if the stage has been reached or passed
        """
        return current_idx >= cls.get_stage_index(stage)

    @classmethod
    def get_next_stage(cls, current: str) -> str | None:
        """Get the next stage after the current one.

        Args:
            current: Current stage name

        Returns:
            Next stage name, or None if at end
        """
        idx = cls.get_stage_index(current)
        if idx < len(cls.STAGES) - 1:
            return cls.STAGES[idx + 1]
        return None
