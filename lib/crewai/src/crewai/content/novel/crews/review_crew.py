"""审查Crew"""

from __future__ import annotations

from typing import Dict, Any, Optional, TYPE_CHECKING, List

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.review.review_result import Issue

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.review.critique_agent import CritiqueAgent
    from crewai.content.review.revision_agent import RevisionAgent
    from crewai.content.review.polish_agent import PolishAgent
    from crewai.content.review.review_context import ReviewContext
    from crewai.content.review.review_result import ReviewResult
    from crewai.content.novel.agents.interiority_checker import InteriorityChecker
    from crewai.content.novel.agents.pov_checker import POVChecker


class ReviewCrew(BaseContentCrew):
    """审查Crew

    负责审查和修改章节内容：
    - 审查阶段：发现内容问题
    - 修改阶段：根据意见修改
    - 润色阶段：优化语言表达
    - 专项检查：内心独白、视角等

    使用示例:
        crew = ReviewCrew(config=ContentConfig(...))
        result = crew.review(chapter_content, context)
    """

    def __init__(self, config: Any, agents: Optional[Dict[str, Any]] = None, tasks: Optional[Dict[str, Any]] = None, verbose: bool = True):
        super().__init__(config, agents, tasks, verbose)
        self._critique_agent = None
        self._revision_agent = None
        self._polish_agent = None
        self._interiority_checker = None
        self._pov_checker = None

    def _lazy_init_agents(self):
        """延迟初始化agents（避免循环导入）"""
        if self._critique_agent is None:
            from crewai.content.review.critique_agent import CritiqueAgent
            from crewai.content.review.revision_agent import RevisionAgent
            from crewai.content.review.polish_agent import PolishAgent
            from crewai.content.novel.agents.interiority_checker import InteriorityChecker
            from crewai.content.novel.agents.pov_checker import POVChecker

            llm = self.config.get("llm") if self.config else None
            self._critique_agent = CritiqueAgent(llm=llm, verbose=self.verbose)
            self._revision_agent = RevisionAgent(llm=llm, verbose=self.verbose)
            self._polish_agent = PolishAgent(llm=llm, verbose=self.verbose)
            self._interiority_checker = InteriorityChecker(llm=llm, verbose=self.verbose)
            self._pov_checker = POVChecker(llm=llm, verbose=self.verbose)

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents - 延迟初始化"""
        self._lazy_init_agents()
        return {
            "critique": self._critique_agent,
            "revision": self._revision_agent,
            "polish": self._polish_agent,
            "interiority": self._interiority_checker,
            "pov": self._pov_checker,
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew

        self._lazy_init_agents()
        return Crew(
            agents=[
                self._critique_agent.agent,
                self._revision_agent.agent,
                self._polish_agent.agent,
            ],
            tasks=[],
            verbose=self.verbose,
        )

    def review(
        self,
        draft: str,
        context: ReviewContext,
        skip_polish: bool = False,
    ) -> dict:
        """完整审查流程

        Args:
            draft: 章节初稿
            context: 审查上下文
            skip_polish: 是否跳过润色

        Returns:
            dict: 包含critique, revised_draft, polished_draft的字典
        """
        self._lazy_init_agents()

        # 审查
        critique_result = self._critique_agent.critique(draft, context)

        # 执行专项检查（内心独白、视角等）
        interiority_result = self._interiority_checker.check(draft, context)
        pov_result = self._pov_checker.check(draft, context)

        # 将检查结果转换为Issue并添加到critique_result
        if interiority_result and interiority_result.has_issues():
            interiority_issues = self._convert_check_result_to_issues(
                interiority_result, "interiority", context
            )
            for issue in interiority_issues:
                critique_result.add_issue(issue)

        if pov_result and pov_result.has_issues():
            pov_issues = self._convert_check_result_to_issues(
                pov_result, "pov", context
            )
            for issue in pov_issues:
                critique_result.add_issue(issue)

        # 修改
        revised_draft = self._revision_agent.revise(draft, critique_result)

        # 润色
        if skip_polish:
            polished_draft = revised_draft
        else:
            polished_draft = self._polish_agent.polish(revised_draft)

        return {
            "critique": critique_result,
            "revised_draft": revised_draft,
            "polished_draft": polished_draft,
        }

    def _convert_check_result_to_issues(
        self, check_result: Any, issue_type: str, context: dict
    ) -> List[Issue]:
        """将检查结果转换为Issue列表

        Args:
            check_result: 检查结果 (ReviewCheckResult)
            issue_type: 问题类型 (interiority, pov)
            context: 上下文信息

        Returns:
            List[Issue]: 转换后的Issue列表
        """
        issues = []
        if check_result is None or not check_result.has_issues():
            return issues

        chapter_num = context.chapter_number or "?"

        for i, issue_desc in enumerate(check_result.issues):
            severity = "high" if check_result.score < 5.0 else "medium" if check_result.score < 7.0 else "low"
            issue = Issue(
                type=issue_type,
                description=issue_desc,
                location=f"第{chapter_num}章",
                severity=severity,
                suggestion=check_result.suggestions[i] if i < len(check_result.suggestions) else "",
            )
            issues.append(issue)

        return issues

    def check_interiority(self, chapter_content: str, context: dict) -> Any:
        """检查内心独白

        Args:
            chapter_content: 章节内容
            context: 上下文

        Returns:
            ReviewCheckResult: 检查结果
        """
        self._lazy_init_agents()
        return self._interiority_checker.check(chapter_content, context)

    def check_pov(self, chapter_content: str, context: dict) -> Any:
        """检查视角

        Args:
            chapter_content: 章节内容
            context: 上下文

        Returns:
            ReviewCheckResult: 检查结果
        """
        self._lazy_init_agents()
        return self._pov_checker.check(chapter_content, context)

    def critique_only(self, draft: str, context: ReviewContext) -> ReviewResult:
        """仅执行审查

        Args:
            draft: 草稿内容
            context: 审查上下文

        Returns:
            ReviewResult: 审查结果
        """
        self._lazy_init_agents()
        return self._critique_agent.critique(draft, context)

    def critique_and_revise(
        self,
        draft: str,
        context: ReviewContext,
        skip_polish: bool = False,
    ) -> tuple[ReviewResult, str, str]:
        """审查并修改（含润色）

        Args:
            draft: 草稿内容
            context: 审查上下文
            skip_polish: 是否跳过润色

        Returns:
            tuple: (审查结果, 修改后的草稿, 润色后的草稿)
        """
        import logging
        logger = logging.getLogger(__name__)

        self._lazy_init_agents()

        # 审查阶段 - 添加错误处理
        try:
            critique_result = self._critique_agent.critique(draft, context)
        except (ValueError, Exception) as e:
            logger.warning(f"审查失败，使用空结果: {e}")
            from crewai.content.review.review_result import ReviewResult
            critique_result = ReviewResult()
            critique_result.summary = "审查失败，跳过此阶段"
            critique_result.score = 10.0

        # 执行专项检查（内心独白、视角等）- 添加错误处理
        try:
            interiority_result = self._interiority_checker.check(draft, context)
        except (ValueError, Exception) as e:
            logger.warning(f"内心独白检查失败: {e}")
            interiority_result = None

        try:
            pov_result = self._pov_checker.check(draft, context)
        except (ValueError, Exception) as e:
            logger.warning(f"视角检查失败: {e}")
            pov_result = None

        # 将检查结果转换为Issue并添加到critique_result
        if interiority_result and interiority_result.has_issues():
            interiority_issues = self._convert_check_result_to_issues(
                interiority_result, "interiority", context
            )
            for issue in interiority_issues:
                critique_result.add_issue(issue)

        if pov_result and pov_result.has_issues():
            pov_issues = self._convert_check_result_to_issues(
                pov_result, "pov", context
            )
            for issue in pov_issues:
                critique_result.add_issue(issue)

        # 修改阶段 - 添加错误处理
        try:
            revised_draft = self._revision_agent.revise(draft, critique_result)
        except (ValueError, Exception) as e:
            logger.warning(f"修改失败，使用原始草稿: {e}")
            revised_draft = draft

        # 润色阶段 - 添加错误处理
        if skip_polish:
            polished_draft = revised_draft
        else:
            try:
                polished_draft = self._polish_agent.polish(revised_draft)
            except (ValueError, Exception) as e:
                logger.warning(f"润色失败，使用修改后草稿: {e}")
                polished_draft = revised_draft

        return critique_result, revised_draft, polished_draft
