"""ForeshadowingChecker - Validates setup and payoff of plot threads.

Ensures that foreshadowing defined in the Production Bible is actually
implemented in the chapter text.
"""

from typing import Any
from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult


class ForeshadowingChecker:
    """Agent for checking foreshadowing consistency."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="伏笔校验专家",
            goal="确保小说中的埋坑（Foreshadowing Setup）和填坑（Payoff）动作准确无误。",
            backstory="""你是一个极其细心的编辑，专门负责长篇小说的逻辑闭环。
            你手里有一份‘伏笔清单’，你必须检查作者在指定章节是否完成了规定的伏笔任务。
            如果该埋的没埋，或者该填的没填，你必须严厉地指出并要求重写。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def check(self, chapter_content: str, bible_section: Any, chapter_num: int) -> ReviewCheckResult:
        """Check foreshadowing consistency.

        Args:
            chapter_content: The written chapter text
            bible_section: BibleSection for this volume
            chapter_num: Current chapter number

        Returns:
            ReviewCheckResult: Result of the check
        """
        if not bible_section or not hasattr(bible_section, 'open_foreshadowing') or not bible_section.open_foreshadowing:
            return ReviewCheckResult(check_type="foreshadowing", passed=True, score=10.0)

        # 筛选本章相关的伏笔任务
        tasks = []
        for fs in bible_section.open_foreshadowing:
            if getattr(fs, 'setup_chapter', 0) == chapter_num:
                tasks.append(f"【埋坑任务】：{getattr(fs, 'setup_description', '')}")
            elif getattr(fs, 'payoff_chapter', 0) == chapter_num:
                tasks.append(f"【填坑任务】：回收‘{getattr(fs, 'setup_description', '')}’，填坑要求：{getattr(fs, 'payoff_description', '')}")

        if not tasks:
            return ReviewCheckResult(check_type="foreshadowing", passed=True, score=10.0)

        task_str = "\n".join(f"- {t}" for t in tasks)
        prompt = f"""请对比以下‘伏笔任务清单’和‘章节内容’，检查作者是否完成了任务。

【本章伏笔任务】：
{task_str}

【章节内容】：
{chapter_content[:3000]}

请评估：
1. 所有的‘埋坑任务’是否都在文中有了对应的描写或暗示？
2. 所有的‘填坑任务’是否都得到了实质性的回应和收束？

如果未完成，请列出具体缺失的问题和修改建议。
输出格式：
Score: [0-10]
Issues:
- 问题1
- 问题2
Suggestions:
- 建议1
- 建议2
"""

        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _parse_result(self, result: Any) -> ReviewCheckResult:
        content = str(result.raw if hasattr(result, 'raw') else result)
        
        score = 10.0
        issues = []
        suggestions = []

        import re
        score_match = re.search(r'Score:\s*(\d+\.?\d*)', content)
        if score_match:
            score = float(score_match.group(1))

        issue_section = re.search(r'Issues:(.*?)(Suggestions:|$)', content, re.DOTALL)
        if issue_section:
            issues = [line.strip('- ').strip() for line in issue_section.group(1).strip().split('\n') if line.strip()]

        suggestion_section = re.search(r'Suggestions:(.*)', content, re.DOTALL)
        if suggestion_section:
            suggestions = [line.strip('- ').strip() for line in suggestion_section.group(1).strip().split('\n') if line.strip()]

        return ReviewCheckResult(
            check_type="foreshadowing",
            passed=score >= 7.0,
            issues=issues,
            suggestions=suggestions,
            score=score
        )
