"""视角检查器"""

from typing import TYPE_CHECKING

from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult

if TYPE_CHECKING:
    from crewai.llm import LLM


class POVChecker:
    """视角检查器 (Point of View Checker)

    检查叙事视角的一致性和正确性：
    - 第一人称视角 vs 第三人称视角
    - 视角切换是否混乱
    - 是否出现了"视角透视"错误（知道不该知道的信息）
    - 角色内心访问权限是否一致

    使用示例:
        checker = POVChecker()
        result = checker.check(chapter_content, context)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化视角检查器

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="叙事视角分析专家",
            goal="确保叙事视角的一致性和正确性",
            backstory="""你是一个专业的叙事学专家，精通各种叙事视角。
            你对第一人称、第三人称限定第三人称等视角有深入研究。
            你擅长发现视角透视错误和视角切换混乱的问题。""",
            verbose=verbose,
            llm=llm,
        )

    def check(self, chapter_content: str, context: dict) -> ReviewCheckResult:
        """检查章节的视角问题

        Args:
            chapter_content: 章节内容
            context: 上下文信息（包含视角类型、章节号等）

        Returns:
            ReviewCheckResult: 检查结果
        """
        prompt = self._build_check_prompt(chapter_content, context)
        response = self.agent.kickoff(messages=prompt)
        return self._parse_response(response)

    def _build_check_prompt(self, chapter_content: str, context) -> str:
        """构建检查提示词

        Args:
            chapter_content: 章节内容
            context: ReviewContext dataclass or dict with chapter context
        """
        # Support both ReviewContext dataclass and dict
        if hasattr(context, "chapter_number"):
            chapter_num = context.chapter_number if context.chapter_number is not None else "?"
            pov_type = getattr(context, "pov_type", "第三人称限定")
            if not pov_type:
                pov_type = "第三人称限定"
        else:
            chapter_num = context.get("chapter_number", context.get("chapter_num", "?"))
            pov_type = context.get("pov_type", "第三人称限定")

        return f"""请分析以下第{chapter_num}章的叙事视角问题。

视角类型: {pov_type}

待分析内容:
{chapter_content}

请检查以下常见视角问题：

1. **视角一致性**: 整章是否保持了设定的视角类型？
   - 第一人称视角使用"我"来叙述
   - 第三人称限定视角只描述主角的所见所闻所想

2. **视角切换混乱**: 是否有突兀的视角切换？
   - 正常的小幅切换（如通过主角眼睛观察配角内心）
   - 混乱的大幅切换（如突然切到另一个角色的完整内心独白）

3. **视角透视错误**: 是否出现了不该知道的信息？
   - 主角不应该知道其他角色的私下对话内容
   - 主角不应该知道远处的 события

4. **内心访问权限**: 角色内心描写是否符合视角限制？
   - 第三人称限定视角：只能深入主角内心
   - 第一人称视角：只能描述"我"的内心

请给出：
- 1-10的评分
- 发现的问题列表（包含位置和具体描述）
- 具体的修改建议

以JSON格式返回：
{{
    "score": 8.0,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}"""

    def _parse_response(self, response: str) -> ReviewCheckResult:
        """解析检查响应"""
        import json
        import re

        result = ReviewCheckResult(check_type="pov", passed=True)

        try:
            if hasattr(response, "raw"):
                data = json.loads(response.raw)
            elif isinstance(response, str):
                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = json.loads(response)
            else:
                data = json.loads(str(response))
        except (json.JSONDecodeError, Exception):
            result.issues.append("无法解析检查结果")
            result.suggestions.append("请人工检查视角一致性")
            result.score = 5.0
            result.passed = False
            return result

        result.score = float(data.get("score", 5.0))
        result.issues = data.get("issues", [])
        result.suggestions = data.get("suggestions", [])

        # 评分>=7认为通过
        result.passed = result.score >= 7.0

        return result
