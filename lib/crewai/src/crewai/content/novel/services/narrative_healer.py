"""NarrativeHealer - Handles failed narrative tasks and orchestrates retries.

Inspired by Claude Code's self-healing loop. Analyzes critique results and
constructs precise 'Fix-up' prompts to rescue failing chapters.
"""

from typing import Any, Dict, List
from crewai.agent import Agent


class NarrativeHealer:
    """Agent for diagnosing and repairing narrative generation failures."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说创作自愈专家",
            goal="分析章节写作失败的原因，制定精准的‘手术级’修复方案，确保生成质量达标。",
            backstory="""你是一个顶尖的急诊主编。当一个章节因为‘文笔太干’、‘逻辑不通’或‘卖点未落地’
            而被审查系统判为不及格时，你会介入。你擅长将复杂的审查意见转化为简单的、
            Agent 能够理解并执行的‘修复指令’。你追求的是一次修复成功。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def diagnose_and_prescribe(self, failed_content: str, critique_issues: List[Any]) -> str:
        """Create a targeted prompt for the next revision attempt."""
        
        issue_summary = "\n".join([str(i) for i in critique_issues])
        
        prompt = f"""请作为自愈专家，诊断以下章节的失败原因并给出修复处方。

【审查发现的致命问题】：
{issue_summary}

【失败的原文采样】：
{failed_content[:2000]}

任务：
1. 分析为什么前一次尝试失败了（是理解偏离？还是执行力不足？）。
2. 制定一份‘手术方案’：明确告诉下一轮 Agent 必须修改哪几段，必须加入哪些特定的细节。
3. 生成一个极其强硬的‘修复指令 (Fix-up Directive)’。

直接输出修复指令，供下一轮写作 Agent 使用。"""

        result = self.agent.kickoff(messages=prompt)
        return str(result.raw if hasattr(result, 'raw') else result).strip()
