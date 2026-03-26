from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from crewai.content.review.critique_agent import CritiqueAgent
from crewai.content.review.revision_agent import RevisionAgent
from crewai.content.review.polish_agent import PolishAgent
from crewai.content.review.review_result import ReviewResult
from crewai.content.review.review_context import ReviewContext

if TYPE_CHECKING:
    from crewai.llm import LLM


class ReviewPipeline:
    """编辑流水线 - 串联审查、修改、润色三个阶段

    这个流水线执行完整的内容编辑流程:
    1. 审查阶段 - CritiqueAgent发现问额
    2. 修改阶段 - RevisionAgent根据意见修改
    3. 润色阶段 - PolishAgent优化语言

    使用示例:
        pipeline = ReviewPipeline()
        result = pipeline.run(
            draft="草稿内容...",
            context=ReviewContext(title="我的小说")
        )
        print(result["polished_draft"])
    """

    def __init__(
        self,
        llm: Optional["LLM"] = None,
        verbose: bool = True,
        skip_polish: bool = False
    ):
        """初始化编辑流水线

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
            skip_polish: 是否跳过润色阶段（直接输出修改后的草稿）
        """
        self.critique_agent = CritiqueAgent(llm=llm, verbose=verbose)
        self.revision_agent = RevisionAgent(llm=llm, verbose=verbose)
        self.polish_agent = PolishAgent(llm=llm, verbose=verbose)
        self.skip_polish = skip_polish

    def run(self, draft: str, context: ReviewContext) -> dict:
        """运行完整的编辑流水线

        Args:
            draft: 原始草稿内容
            context: 审查上下文

        Returns:
            dict: 包含以下键的字典:
                - critique: 审查结果 (ReviewResult)
                - revised_draft: 修改后的草稿 (str)
                - polished_draft: 润色后的草稿 (str)
                - review_result: 审查结果对象
        """
        # 阶段1: 审查（添加错误处理，LLM失败时跳过）
        try:
            critique_result = self.critique_agent.critique(draft, context)
        except (ValueError, Exception) as e:
            # LLM返回空或网络错误时，跳过审查，使用空结果
            import logging
            logging.warning(f"审查阶段失败，使用空结果: {e}")
            critique_result = ReviewResult()
            critique_result.summary = "审查失败，跳过此阶段"
            critique_result.score = 10.0

        # 阶段2: 修改
        try:
            revised_draft = self.revision_agent.revise(draft, critique_result)
        except (ValueError, Exception) as e:
            import logging
            logging.warning(f"修改阶段失败，使用原始草稿: {e}")
            revised_draft = draft

        # 阶段3: 润色
        if self.skip_polish:
            polished_draft = revised_draft
        else:
            try:
                polished_draft = self.polish_agent.polish(revised_draft)
            except (ValueError, Exception) as e:
                import logging
                logging.warning(f"润色阶段失败，使用修改后草稿: {e}")
                polished_draft = revised_draft

        return {
            "critique": critique_result,
            "revised_draft": revised_draft,
            "polished_draft": polished_draft,
            "review_result": critique_result,
        }

    def critique_only(self, draft: str, context: ReviewContext) -> ReviewResult:
        """仅执行审查阶段

        Args:
            draft: 要审查的草稿
            context: 审查上下文

        Returns:
            ReviewResult: 审查结果
        """
        return self.critique_agent.critique(draft, context)

    def critique_and_revise(self, draft: str, context: ReviewContext) -> tuple[ReviewResult, str]:
        """执行审查和修改阶段

        Args:
            draft: 原始草稿
            context: 审查上下文

        Returns:
            tuple: (审查结果, 修改后的草稿)
        """
        critique_result = self.critique_agent.critique(draft, context)
        revised_draft = self.revision_agent.revise(draft, critique_result)
        return critique_result, revised_draft
