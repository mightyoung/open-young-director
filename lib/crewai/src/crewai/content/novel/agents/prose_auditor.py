"""ProseAuditor - Eliminates AI-style abstract descriptions and enforces sensory grounding.

Targets 'AI-isms' like 'extremely', 'somehow', 'it seemed' and ensures 
location-specific sensory anchors are used to build atmosphere.
"""

from typing import Any, List
import re
from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult


class ProseAuditor:
    """Agent for auditing prose quality and eliminating AI clichés."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="网文质感审计专家",
            goal="彻底消除‘AI腔’，将空洞的形容词转化为具有冲击力的感官描写和物理细节。",
            backstory="""你是一个对文字极度挑剔的资深编辑。你厌恶一切虚浮的描写。
            如果作者写‘他感到非常愤怒’，你会直接把稿子甩在他脸上，
            要求他写出‘指甲刺入掌心的痛楚’。你手里有一份‘AI常用词黑名单’，
            任何出现在名单上的词都会被你标记为‘文笔通缩’。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def audit(self, content: str, bible_section: Any) -> ReviewCheckResult:
        """Audit the prose for abstract 'AI-isms' and sensory grounding.

        Args:
            content: The written text.
            bible_section: Current bible section with sensory_anchors.

        Returns:
            ReviewCheckResult
        """
        # Build local sensory anchors for the prompt
        anchors_str = "无"
        if bible_section and hasattr(bible_section, 'world_rules') and bible_section.world_rules:
            # Simple heuristic: find location-based anchors
            anchors_str = str(getattr(bible_section.world_rules, 'sensory_anchors', {}))

        prompt = f"""请作为审计专家，对以下章节的【文笔质感】进行残酷的审美审计。

【审计重点】：
1. 【黑名单拦截】：严禁出现“极其、非常、恐怖、令人窒息、仿佛、似乎、某种、不可名状、居然、竟然”等AI常用垫话。
2. 【Show, Don't Tell】：禁止直接描述情感（如：他很害怕）。必须转化为物理细节（如：他屏住呼吸，能听到胸腔里杂乱的鼓点）。
3. 【感官锚定】：核对文中是否使用了该地点的感官锚点。
   - 建议锚点参考：{anchors_str}
4. 【词汇通缩】：检查是否存在大量重复的修饰词（如一章出现5次“气浪”）。

【章节内容（采样前3000字）】：
{content[:3000]}

输出要求：
Score: [0-10] (如果‘AI腔’明显或描写空洞，分值必须低于5)
Issues:
- 指出具体的‘AI腔’词汇或‘Tell, not Show’的平庸段落。
Suggestions:
- 提供至少3处具体的“物理化”改写建议。
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
            check_type="prose_quality",
            passed=score >= 7.0,
            issues=issues,
            suggestions=suggestions,
            score=score
        )
