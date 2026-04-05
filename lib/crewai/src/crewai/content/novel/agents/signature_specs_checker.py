"""SignatureSpecsChecker - Ensures the unique selling points of a chapter are actually written.

This checker compares the 'signature_specs' from the outline with the generated text
to prevent the AI from falling back into generic genre tropes.
"""

from typing import Any, List
import re
from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult


class SignatureSpecsChecker:
    """Agent for verifying adherence to unique chapter specifications."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="核心卖点执行督导",
            goal="强制要求作者落实大纲中的独特设定，严厉打击‘挂羊头卖狗肉’的套路化写作。",
            backstory="""你是一个极其严苛的出版总监。你最痛恨作者在大纲里承诺了‘硬核科幻’，
            结果交稿时全是‘英雄救美’和‘放火球’。你的任务是逐字逐句检查文中是否真的出现了
            那些大纲里规定的‘核心奇观’和‘独特卖点’。如果没有，你必须判为不及格！""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def check(self, chapter_content: str, chapter_outline: dict) -> ReviewCheckResult:
        """Check if the chapter actually implements the required signature specs.

        Args:
            chapter_content: The written text.
            chapter_outline: The outline containing 'signature_specs'.

        Returns:
            ReviewCheckResult
        """
        specs = chapter_outline.get("signature_specs", [])
        if not specs:
            return ReviewCheckResult(check_type="signature_specs", passed=True, score=10.0)

        specs_str = "\n".join([f"- {s}" for s in specs])
        prompt = f"""请作为督导，核对以下【核心卖点】是否在【章节内容】中得到了落实。

【大纲要求的核心卖点/奇观描写】：
{specs_str}

【章节内容（采样前3000字）】：
{chapter_content[:3000]}

请评估：
1. 大纲要求的每一个卖点，是否在文中有了实质性的、细节丰富的描写（不少于300字）？
2. 作者是否只是提了一下名词（点到为止），而没有真正展开？如果是，请判为‘不及格’。
3. 文中是否出现了与卖点相符的特定词汇、逻辑或感官描写？

输出要求：
Score: [0-10] (如果任意一个核心卖点未落实，分值必须低于6)
Issues:
- 指出哪个卖点未落地，作者是怎么敷衍的。
Suggestions:
- 给出具体的描写方向，强制要求作者加入哪些特定的细节。
"""

        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _parse_result(self, result: Any) -> ReviewCheckResult:
        content = str(result.raw if hasattr(result, 'raw') else result)
        
        score = 10.0
        issues = []
        suggestions = []

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
            check_type="signature_specs",
            passed=score >= 7.0,
            issues=issues,
            suggestions=suggestions,
            score=score
        )
