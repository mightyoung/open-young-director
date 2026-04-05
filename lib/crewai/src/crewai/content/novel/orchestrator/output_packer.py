"""Output packing utilities for novel pipeline."""

import logging
import os
import time
from typing import Any

from crewai.content.base import BaseCrewOutput


logger = logging.getLogger(__name__)


def generate_pending_state_path(
    stage: str,
    topic: str = "unknown",
    output_dir: str | None = None,
) -> str:
    """Generate a unique pending state file path.

    This is the SINGLE SOURCE OF TRUTH for pending state file path generation.
    All code that generates pending state paths MUST use this function.

    Args:
        stage: Stage name (outline/volume/summary/chapter)
        topic: Topic/seed for unique naming
        output_dir: Optional output directory for state file

    Returns:
        str: Full path to the pending state file
    """
    topic_part = "".join(c if c.isalnum() else "_" for c in str(topic))
    timestamp = int(time.time())
    state_filename = f".novel_pipeline_{topic_part}_{stage}_{timestamp}_pending.json"
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, state_filename)
    return state_filename


class OutputPacker:
    """Packs pipeline outputs into BaseCrewOutput format.

    Handles:
    - State output (stop_at mode)
    - Approval output (approval_mode pause points)
    - Stage content summarization
    """

    @staticmethod
    def pack_state_output(
        pipeline_summary: dict,
        execution_time: float,
    ) -> BaseCrewOutput:
        """Pack pipeline state as output (for stop_at mode).

        Args:
            pipeline_summary: Summary dict with stage info
            execution_time: Time taken

        Returns:
            BaseCrewOutput with stopped state
        """
        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"完成阶段: {pipeline_summary.get('stage', 'unknown')}"],
            execution_time=execution_time,
            metadata={
                "pipeline_state": pipeline_summary,
                "stopped": True,
            },
        )

    @staticmethod
    def pack_approval_output(
        pipeline_state: Any,
        stage: str,
        content: dict,
        execution_time: float,
        output_dir: str | None = None,
    ) -> BaseCrewOutput:
        """Pack approval state as output (for approval_mode pause points).

        This method DELEGATES to ApprovalService for consistent behavior.
        All approval output generation should use this method or ApprovalService directly.

        Args:
            pipeline_state: PipelineState instance for saving
            stage: Current stage name
            content: Stage content
            execution_time: Time taken
            output_dir: Optional output directory for state file. If not provided,
                       defaults to cwd for backwards compatibility.

        Returns:
            BaseCrewOutput with pending approval state
        """
        # P1: Delegate to ApprovalService for consistent approval handling
        from crewai.content.novel.services.approval_service import ApprovalService

        service = ApprovalService.get_instance()
        return service.request_approval(
            stage=stage,
            content=content,
            pipeline_state=pipeline_state,
            output_dir=output_dir,
            execution_time=execution_time,
        )

    @staticmethod
    def pack_fallback_approval_output(
        stage: str,
        content: dict,
        execution_time: float,
        topic: str = "unknown",
        output_dir: str | None = None,
    ) -> BaseCrewOutput:
        """Pack approval output when pipeline_state is not available.

        This is a fallback for degraded mode when pipeline_state is None.
        State cannot be saved in this case.

        Args:
            stage: Current stage name
            content: Stage content
            execution_time: Time taken
            topic: Topic for path generation
            output_dir: Optional output directory

        Returns:
            BaseCrewOutput with pending approval state (but no saved state)
        """
        state_path = generate_pending_state_path(stage, topic, output_dir)
        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"等待审批: {stage}"],
            execution_time=execution_time,
            metadata={
                "approval_required": True,
                "stage": stage,
                "stage_status": "pending_approval",
                "pipeline_state_path": state_path,
                "content_summary": OutputPacker.summarize_stage_content(stage, content),
                "feedback_options": {
                    "approve": "通过当前内容，继续下一阶段",
                    "revise": "需要修改，请提供修改意见",
                    "reject": "拒绝，重新生成",
                    "reinstruct": "重新指令，大幅修改",
                    "skip": "跳过此阶段",
                },
            },
        )

    @staticmethod
    def summarize_stage_content(stage: str, content: dict) -> dict:
        """Generate summary of stage content for display to user.

        Args:
            stage: Stage name
            content: Stage content dict

        Returns:
            Summary dict
        """
        if stage == "outline":
            return {
                "world_name": content.get("world_data", {}).get("name", ""),
                "world_summary": str(content.get("world_data", {}))[:200] + "...",
                "plot_summary": str(content.get("plot_data", {}))[:200] + "...",
            }
        if stage == "volume":
            volumes = content.get("volume_outlines", [])
            return {
                "volumes_count": len(volumes),
                "volume_titles": [v.get("title", "") for v in volumes[:3]],
            }
        if stage == "summary":
            summaries = content.get("chapter_summaries", [])
            return {
                "chapters_count": len(summaries),
                "chapter_titles": [s.get("title", "") for s in summaries[:5]],
            }
        if stage == "chapter":
            chapter_output = content.get("chapter_output")
            return {
                "chapter_num": content.get("chapter_num"),
                "chapter_title": getattr(chapter_output, "title", "") if chapter_output else "",
                "word_count": getattr(chapter_output, "word_count", 0) if chapter_output else 0,
                "key_events": getattr(chapter_output, "key_events", []) if chapter_output else [],
            }
        return {}
