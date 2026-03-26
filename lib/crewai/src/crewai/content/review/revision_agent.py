from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from crewai.agent.core import Agent
from crewai.content.review.review_result import ReviewResult

if TYPE_CHECKING:
    from crewai.llm import LLM


class RevisionAgent:
    """修改Agent - 根据审查意见修改草稿

    这个Agent接收原始草稿和审查结果，然后根据审查意见逐条修改草稿。
    每个发现的问题都应该被妥善处理。

    使用示例:
        agent = RevisionAgent()
        revised = agent.revise(draft="原始草稿...", critique=review_result)
    """

    def __init__(self, llm: Optional["LLM"] = None, verbose: bool = True):
        """初始化修改Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="内容修改专家",
            goal="根据审查意见修改草稿，解决所有发现的问题",
            backstory="""你是一个经验丰富的内容修改专家，擅长根据反馈改进内容。
            你会仔细阅读每一条审查意见，然后针对性地修改草稿。
            你的修改原则是：
            1. 保留原文的优点和风格
            2. 针对性地解决每一个问题
            3. 尽量减少不必要的改动
            4. 确保修改后的一致性和连贯性

            你会在修改时考虑整体效果，而不是机械地逐条修改。""",
            verbose=verbose,
            llm=llm,
        )

    def revise(self, draft: str, critique: ReviewResult) -> str:
        """根据审查意见修改草稿

        Args:
            draft: 原始草稿内容
            critique: 审查结果，包含问题列表

        Returns:
            str: 修改后的草稿内容
        """
        if not critique.issues:
            # 没有问题，直接返回原文
            return draft

        prompt = self._build_revision_prompt(draft, critique)
        response = self.agent.kickoff(messages=prompt)
        return self._extract_revised_content(response, draft)

    def _build_revision_prompt(self, draft: str, critique: ReviewResult) -> str:
        """构建修改提示词"""
        issues_text = []
        for i, issue in enumerate(critique.issues, 1):
            issue_text = f"{i}. [{issue.type.upper()}] {issue.description}"
            if issue.location:
                issue_text += f"\n   位置: {issue.location}"
            if issue.suggestion:
                issue_text += f"\n   建议: {issue.suggestion}"
            issues_text.append(issue_text)

        issues_str = "\n".join(issues_text)

        return f"""请根据以下审查意见修改草稿：

审查发现的问题:
{issues_str}

原始草稿:
{draft}

修改要求:
1. 逐条解决每个审查问题
2. 保持原文的优点和整体风格
3. 确保修改后的内容连贯一致
4. 不要引入新的问题

请直接输出修改后的完整内容，不要说明修改了什么。"""
        return prompt

    def _extract_revised_content(self, response: str, original: str) -> str:
        """从响应中提取修改后的内容"""
        # 提取文本内容（处理 LiteAgentOutput 对象）
        if hasattr(response, 'raw'):
            response_text = response.raw
        elif hasattr(response, 'content'):
            response_text = str(response.content)
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)

        # 尝试提取markdown代码块中的内容
        import re

        # 查找 ```开头和```结尾之间的内容
        code_block_match = re.search(r"```[\w]*\n(.*?)```", response_text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()

        # 查找"修改后的内容:"或"修订版:"之后的内容
        revised_match = re.search(
            r"(?:修改后|修订版|修改版)[：:]\s*\n?(.*)",
            response_text,
            re.DOTALL
        )
        if revised_match:
            return revised_match.group(1).strip()

        # 如果响应比原文短很多，可能只是说明，直接返回原文
        if len(response_text) < len(original) * 0.5:
            return original

        # 否则返回完整响应
        return response_text.strip()
