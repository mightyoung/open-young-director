"""Approval Workflow Example - 审批工作流使用示例

本文件演示如何在 CREWAI 小说生成流程中使用人机协作审批模式。

使用流程:
1. 启动生成流程（approval_mode=True）
2. 在每个阶段暂停，等待审批
3. 用户提交反馈（approve/revise/reject）
4. 系统根据反馈继续生成

示例代码:
    from crewai.content.novel.crews.novel_crew import NovelCrew
    from crewai.content.novel.human_feedback import create_approval_feedback

    # 创建 Crew
    crew = NovelCrew(config={
        "topic": "修仙逆袭",
        "style": "xianxia",
        "num_chapters": 30,
        "target_words": 500000,
        "llm": llm_instance,
    })

    # 启动生成流程 - 在 outline 阶段暂停
    result = crew.kickoff(
        stop_at=None,
        approval_mode=True,  # 开启审批模式
    )

    # 检查是否需要审批
    if result.metadata.get("approval_required"):
        stage = result.metadata["stage"]
        print(f"需要审批阶段: {stage}")
        print(f"内容摘要: {result.metadata['content_summary']}")

        # 方式1: 快速通过
        if 用户确认通过():
            crew.approve(stage, result.metadata["pipeline_state_path"])

        # 方式2: 带反馈的修改
        elif 用户需要修改():
            crew.revise(
                stage,
                feedback_text="主角性格太懦弱,改成坚毅果敢",
                pipeline_state_path=result.metadata["pipeline_state_path"],
            )

        # 方式3: 使用 submit_feedback 提交结构化反馈
        elif 用户提交自定义反馈():
            from crewai.content.novel.human_feedback import HumanFeedback, ApprovalDecision
            feedback = HumanFeedback(
                stage=stage,
                decision=ApprovalDecision.REVISE,
                natural_language="主角背景需要修改，韩林应该是被逐出宗门的天才",
            )
            crew.submit_feedback(feedback, result.metadata["pipeline_state_path"])

## 逐章审批模式

启用 review_each_chapter=True 后，每章写完都会暂停等待审批:

    result = crew.kickoff(
        approval_mode=True,
        review_each_chapter=True,  # 每章暂停等待审批
    )

    # 捕获 PendingChapterApproval 异常
    try:
        chapters = result
    except PendingChapterApproval as e:
        print(f"第 {e.chapter_num} 章待审批")
        # 审批后继续
        crew.approve_chapter(e.chapter_num, e.pipeline_state_path)

"""

# 导入说明
"""
from crewai.content.novel.crews.novel_crew import NovelCrew, PendingChapterApproval
from crewai.content.novel.human_feedback import (
    HumanFeedback,
    FeedbackParser,
    ApprovalDecision,
    create_approval_feedback,
    ApprovalWorkflow,
)
from crewai.content.novel.feedback_applier import FeedbackApplier
"""

# 审批决策类型
"""
ApprovalDecision.APPROVE   - 通过，继续下一阶段
ApprovalDecision.REVISE    - 需要修改后重新生成
ApprovalDecision.REJECT    - 拒绝，重新生成
ApprovalDecision.REINSTRUCT - 重新指令（大幅修改）
ApprovalDecision.SKIP      - 跳过此阶段
"""

# PipelineState 审批相关方法
"""
pipeline_state.stage_statuses     - 各阶段审批状态字典
pipeline_state.approval_history   - 审批历史记录
pipeline_state.pending_feedback   - 待处理的反馈
pipeline_state.enable_approval_mode() - 启用审批模式
pipeline_state.set_stage_status(stage, status) - 设置阶段状态
pipeline_state.get_stage_status(stage) - 获取阶段状态
pipeline_state.is_stage_approved(stage) - 检查是否已批准
pipeline_state.needs_user_feedback(stage) - 检查是否需要用户反馈
"""

# FeedbackApplier - 基于反馈重新生成
"""
feedback_applier = FeedbackApplier(llm=llm_instance)

# 应用大纲反馈
new_outline = feedback_applier.apply_outline_feedback(
    original_outline=outline_data,
    feedback=structured_feedback,
)

# 应用分卷大纲反馈
new_volumes = feedback_applier.apply_volume_feedback(
    original_volumes=volume_outlines,
    feedback=structured_feedback,
)

# 应用章节概要反馈
new_summaries = feedback_applier.apply_chapter_summary_feedback(
    original_summaries=chapter_summaries,
    feedback=structured_feedback,
    chapter_num=5,  # 可选，只修改第5章
)
"""
