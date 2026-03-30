"""Approval coordinator - handles human feedback and approval workflow."""
import logging
from typing import Any, Optional
from crewai.content.novel.human_feedback import (
    HumanFeedback,
    ApprovalDecision,
    ApprovalWorkflow,
)
from crewai.content.exceptions import ExecutionResult, ExecutionStatus


logger = logging.getLogger(__name__)


class ApprovalCoordinator:
    """审批工作流协调器。

    职责：
    1. 管理审批状态
    2. 处理用户反馈
    3. 决定是继续还是暂停等待审批

    使用方式：
    - 在每个阶段完成后调用 request_approval()
    - 如果返回 paused，则 kickoff() 返回待审批输出
    - 用户审批后调用 submit_feedback() 继续
    """

    def __init__(self, pipeline_state: Any, llm: Any = None):
        self.pipeline_state = pipeline_state
        self.llm = llm
        self._workflow: Optional[ApprovalWorkflow] = None

    def enable(self) -> None:
        """启用审批模式。"""
        self.pipeline_state.enable_approval_mode()
        self._workflow = ApprovalWorkflow(self.pipeline_state, llm=self.llm)
        logger.info("Approval mode enabled")

    @property
    def is_enabled(self) -> bool:
        """是否启用了审批模式。"""
        return self.pipeline_state.approval_mode

    def request_approval(self, stage: str, content: dict) -> "ApprovalResult":
        """请求对某个阶段的审批。

        Args:
            stage: 阶段名 (outline/volume/summary/chapter)
            content: 该阶段生成的内容

        Returns:
            ApprovalResult: 包含是否暂停以及相关元数据
        """
        if not self.is_enabled:
            return ApprovalResult(paused=False)

        # 保存当前状态
        self.pipeline_state.set_stage_status(stage, "pending")

        # 保存待审批内容
        state_path = f".novel_pipeline_{stage}_pending.json"
        self.pipeline_state.save(state_path)

        return ApprovalResult(
            paused=True,
            stage=stage,
            state_path=state_path,
            content_summary=self._summarize_content(stage, content),
            feedback_options={
                "approve": f"通过当前 {stage}，继续下一阶段",
                "revise": f"需要修改，请提供修改意见",
                "reject": f"拒绝，重新生成",
            },
        )

    def submit_feedback(self, feedback: HumanFeedback) -> None:
        """提交用户反馈并继续流程。

        Args:
            feedback: 用户反馈
        """
        self.pipeline_state.add_pending_feedback(feedback.to_dict())
        logger.info(f"Feedback submitted for stage '{feedback.stage}': {feedback.decision}")

    def get_pending_feedback(self) -> Optional[dict]:
        """获取待处理的反馈。"""
        return self.pipeline_state.get_pending_feedback()

    def clear_pending_feedback(self) -> None:
        """清除待处理的反馈。"""
        self.pipeline_state.clear_pending_feedback()

    def _summarize_content(self, stage: str, content: dict) -> dict:
        """生成内容摘要。"""
        if stage == "outline":
            return {
                "world_name": content.get("world_data", {}).get("name", ""),
                "has_plot": bool(content.get("plot_data", {}).get("main_strand")),
            }
        elif stage == "volume":
            return {"volume_count": len(content.get("volume_outlines", []))}
        elif stage == "summary":
            return {"summary_count": len(content.get("chapter_summaries", []))}
        elif stage == "chapter":
            return {"chapter_num": content.get("chapter_num")}
        return {}


class ApprovalResult:
    """审批结果。

    Attributes:
        paused: 是否暂停等待审批
        stage: 当前阶段名
        state_path: 状态文件路径
        content_summary: 内容摘要
        feedback_options: 可用的反馈选项
    """

    def __init__(
        self,
        paused: bool,
        stage: str = None,
        state_path: str = None,
        content_summary: dict = None,
        feedback_options: dict = None,
    ):
        self.paused = paused
        self.stage = stage
        self.state_path = state_path
        self.content_summary = content_summary or {}
        self.feedback_options = feedback_options or {}

    def to_metadata(self) -> dict:
        """转换为 metadata 字典。"""
        if not self.paused:
            return {"approval_required": False}

        return {
            "approval_required": True,
            "stage": self.stage,
            "stage_status": "pending_approval",
            "pipeline_state_path": self.state_path,
            "content_summary": self.content_summary,
            "feedback_options": self.feedback_options,
        }
