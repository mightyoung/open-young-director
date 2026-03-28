from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from crewai.agent.core import Agent
from crewai.content.review.review_result import ReviewResult, Issue

if TYPE_CHECKING:
    from crewai.llm import LLM


class CritiqueAgent:
    """审查Agent - 发现问题但不修改

    这个Agent负责审查草稿，发现其中的问题并提供具体的修改建议。
    它不会修改内容，只会指出问题所在。

    使用示例:
        agent = CritiqueAgent()
        result = agent.critique(draft="草稿内容...", context=ReviewContext(title="我的小说"))
    """

    def __init__(self, llm: Optional["LLM"] = None, verbose: bool = True):
        """初始化审查Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="内容审查专家",
            goal="发现内容问题，提供具体修改建议，但不直接修改内容",
            backstory="""你是一个严格的内容审查专家，专注于发现创意内容中的问题。
            你有敏锐的眼光，能够发现一致性问题、节奏问题、角色行为问题、
            高潮点不足以及连续性错误。你的职责是发现问题并给出具体的修改建议，
            而不是修改内容本身。你会详细分析每个问题的位置和严重程度。""",
            verbose=verbose,
            llm=llm,
        )

    def critique(self, draft: str, context: "ReviewContext") -> ReviewResult:
        """审查草稿并返回问题列表

        Args:
            draft: 要审查的草稿内容
            context: 审查上下文，包含标题、角色设定等信息

        Returns:
            ReviewResult: 包含发现的问题列表和评分
        """
        prompt = self._build_critique_prompt(draft, context)
        try:
            response = self.agent.kickoff(messages=prompt)
            return self._parse_critique_response(response, draft)
        except ValueError as e:
            # LLM返回空响应时，使用空结果跳过审查
            import logging
            logging.warning(f"审查失败，使用空结果: {e}")
            result = ReviewResult()
            result.summary = "审查失败，跳过此阶段"
            result.score = 10.0
            return result

    def _build_critique_prompt(self, draft: str, context: "ReviewContext") -> str:
        """构建审查提示词"""
        context_str = context.get_context_string()

        return f"""请审查以下内容存在的问题：

{context_str}

待审查内容:
{draft}

审查维度:
1. 一致性 - 前后设定是否矛盾，角色行为是否符合已建立的人设
2. 节奏 - 是否拖沓或过快，高潮是否到位
3. 角色OOC - 角色行为是否符合其背景和性格设定
4. 高潮点 - 是否有足够的戏剧张力
5. 连续性 - 事件衔接是否合理，因果关系是否成立

请仔细阅读内容，并按上述维度逐一检查。只发现问题并给出修改建议，不要修改内容。

对于每个发现的问题，请说明：
- 问题类型（一致性/节奏/角色OOC/高潮点/连续性）
- 问题描述
- 所在位置（章节/段落）
- 严重程度（高/中/低）
- 修改建议

最后请给出整体评分（1-10分）"""
        return prompt

    def _parse_critique_response(self, response: str, draft: str) -> ReviewResult:
        """解析审查响应，提取问题列表"""
        # 提取文本内容（处理 LiteAgentOutput 对象）
        if hasattr(response, 'raw'):
            response_text = response.raw
        elif hasattr(response, 'content'):
            response_text = str(response.content)
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)

        result = ReviewResult()
        result.summary = response_text[:500] if len(response_text) > 500 else response_text

        # 尝试从响应中提取评分
        import re
        score_match = re.search(r"评分[：:]\s*(\d+(?:\.\d+)?)", response_text)
        if score_match:
            result.score = float(score_match.group(1))
        else:
            # 尝试其他评分模式
            score_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*10", response_text)
            if score_match:
                result.score = float(score_match.group(1))

        # 解析问题列表
        lines = response_text.split("\n")
        current_issue = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测问题类型标记
            issue_type = None
            if "一致性" in line or "一致" in line.lower():
                issue_type = "consistency"
            elif "节奏" in line:
                issue_type = "pacing"
            elif "角色" in line and ("OOC" in line or "不符合" in line or "行为" in line):
                issue_type = "ooc"
            elif "高潮" in line:
                issue_type = "high_point"
            elif "连续性" in line or "衔接" in line:
                issue_type = "continuity"

            if issue_type and (line.startswith("-") or line.startswith("*") or "问题" in line):
                if current_issue:
                    result.add_issue(current_issue)

                # 提取描述
                desc_match = re.search(r"[:：]\s*(.+)", line)
                description = desc_match.group(1) if desc_match else line
                current_issue = Issue(
                    type=issue_type,
                    description=description,
                    severity="medium"
                )

            # 检测严重程度
            if current_issue and any(x in line for x in ["严重", "高", "high", "重要"]):
                if "非常" in line or "极其" in line:
                    current_issue.severity = "high"
                elif "低" in line or "轻微" in line:
                    current_issue.severity = "low"

            # 检测位置
            if current_issue and any(x in line for x in ["位置", "位于", "段落", "章节"]):
                loc_match = re.search(r"[：:]\s*(.+)", line)
                if loc_match:
                    current_issue.location = loc_match.group(1)

            # 检测建议
            if current_issue and any(x in line for x in ["建议", "修改", "应该"]):
                sug_match = re.search(r"[：:]\s*(.+)", line)
                if sug_match:
                    current_issue.suggestion = sug_match.group(1)

        # 添加最后一个问题
        if current_issue:
            result.add_issue(current_issue)

        # 如果没有解析到问题，将整个响应作为摘要
        if not result.issues:
            result.summary = response

        return result
