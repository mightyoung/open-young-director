"""Approval service - single source of truth for approval workflow.

This module provides a unified interface for all approval-related operations:
- Requesting approval (saving state and generating output)
- Submitting feedback
- Managing approval history

All approval output generation MUST go through ApprovalService to ensure
consistent behavior and avoid code duplication.
"""

import logging
from typing import Any, Optional

from crewai.content.base import BaseCrewOutput
from crewai.content.novel.orchestrator.output_packer import generate_pending_state_path


if False:
    from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)


class ApprovalService:
    """Single entry point for approval workflow.

    Responsibilities:
    - Generate pending state file paths (via generate_pending_state_path)
    - Save pipeline state for approval
    - Pack approval output (BaseCrewOutput with approval metadata)
    - Manage approval records

    This class does NOT handle:
    - Approval decision processing (handled by NovelCrew)
    - Approval workflow state machine (handled by ApprovalWorkflow)
    """

    # Class-level instance for convenience
    _instance: Optional["ApprovalService"] = None

    @classmethod
    def get_instance(cls) -> "ApprovalService":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def request_approval(
        self,
        stage: str,
        content: dict,
        pipeline_state: "PipelineState",
        output_dir: str | None = None,
        execution_time: float = 0.0,
    ) -> BaseCrewOutput:
        """Request approval for a stage.

        This is the SINGLE method for requesting approval. All code paths
        that need to pause for approval MUST use this method.

        Args:
            stage: Stage name (outline/volume/summary/chapter)
            content: Stage content for review
            pipeline_state: PipelineState instance for saving
            output_dir: Optional output directory for state file
            execution_time: Time taken for the operation

        Returns:
            BaseCrewOutput with approval_required=True in metadata
        """
        # Update stage status
        pipeline_state.set_stage_status(stage, "pending")

        # Generate state file path
        topic_slug = self._get_topic_slug(pipeline_state)
        state_path = generate_pending_state_path(stage, topic_slug, output_dir)

        # Save state
        pipeline_state.save(state_path)
        logger.info(f"Approval state saved to {state_path}")

        # Pack and return output
        return self._pack_approval_output(
            stage=stage,
            content=content,
            state_path=state_path,
            execution_time=execution_time,
        )

    def _get_topic_slug(self, pipeline_state: "PipelineState") -> str:
        """Extract topic slug from pipeline state."""
        seed_config = getattr(pipeline_state, "seed_config", None)
        if seed_config:
            topic = getattr(seed_config, "topic", None)
            if topic:
                return str(topic)
        return "unknown"

    def _pack_approval_output(
        self,
        stage: str,
        content: dict,
        state_path: str,
        execution_time: float,
    ) -> BaseCrewOutput:
        """Pack approval output.

        Internal method that creates BaseCrewOutput with approval metadata.
        """
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.orchestrator.output_packer import OutputPacker

        content_summary = OutputPacker.summarize_stage_content(stage, content)

        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"等待审批: {stage}"],
            execution_time=execution_time,
            metadata={
                "approval_required": True,
                "stage": stage,
                "stage_status": "pending_approval",
                "pipeline_state_path": state_path,
                "content_summary": content_summary,
                "feedback_options": {
                    "approve": "通过当前内容，继续下一阶段",
                    "revise": "需要修改，请提供修改意见",
                    "reject": "拒绝，重新生成",
                    "reinstruct": "重新指令，大幅修改",
                    "skip": "跳过此阶段",
                },
            },
        )

    def pack_chapter_approval_output(
        self,
        chapter_num: int,
        chapter_output: Any,
        state_path: str,
        execution_time: float,
    ) -> BaseCrewOutput:
        """Pack chapter approval output.

        P1: Single entry point for chapter approval output generation.
        Ensures consistent approval metadata across all chapter approval paths.

        Args:
            chapter_num: Chapter number
            chapter_output: ChapterOutput instance
            state_path: Path where pipeline state was saved
            execution_time: Time taken so far

        Returns:
            BaseCrewOutput with chapter approval metadata
        """
        from crewai.content.base import BaseCrewOutput

        content = {
            "chapter_output": chapter_output,
            "chapter_num": chapter_num,
        }
        content_summary = {
            "chapter_num": chapter_num,
            "chapter_title": chapter_output.title if chapter_output else None,
        }

        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"等待审批: chapter_{chapter_num}"],
            execution_time=execution_time,
            metadata={
                "approval_required": True,
                "stage": "chapter",
                "stage_status": "pending_approval",
                "pipeline_state_path": state_path,
                "pending_chapter": chapter_num,
                "content_summary": content_summary,
                # P1: Chapter-specific feedback options
                "feedback_options": {
                    "approve": "通过当前章节，继续下一章",
                    "revise": "需要修改，请提供修改意见",
                    "reject": "拒绝，重新生成",
                },
                # Structured failure semantics
                "status": "partial",
                "failure_reason": "chapter_pending_approval",
                "failure_details": {
                    "chapter_num": chapter_num,
                    "recoverable": True,
                },
            },
        )

    def add_approval_record(
        self,
        pipeline_state: "PipelineState",
        stage: str,
        decision: str,
        feedback: str | None = None,
    ) -> None:
        """Add an approval record to pipeline state.

        Args:
            pipeline_state: PipelineState to update
            stage: Stage that was approved
            decision: Approval decision (approve/revise/reject/reinstruct/skip)
            feedback: Optional feedback text
        """
        pipeline_state.add_approval_record({
            "stage": stage,
            "decision": decision,
            "feedback": feedback,
        })


# Module-level convenience function
def request_approval(
    stage: str,
    content: dict,
    pipeline_state: "PipelineState",
    output_dir: str | None = None,
) -> BaseCrewOutput:
    """Convenience function for requesting approval.

    Delegates to ApprovalService.get_instance().request_approval().

    This is the RECOMMENDED entry point for requesting approval.
    """
    return ApprovalService.get_instance().request_approval(
        stage=stage,
        content=content,
        pipeline_state=pipeline_state,
        output_dir=output_dir,
    )
