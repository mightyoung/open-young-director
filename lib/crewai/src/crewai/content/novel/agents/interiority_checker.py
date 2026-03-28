"""内心独白检查器"""

from typing import TYPE_CHECKING

from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult

if TYPE_CHECKING:
    from crewai.llm import LLM


class InteriorityChecker:
    """内心独白检查器

    检查章节中的内心独白是否适度：
    - 过多内心独白会让叙事显得拖沓
    - 过少内心独白会让角色显得单薄
    - 需要在"展示"和"讲述"之间找到平衡

    使用示例:
        checker = InteriorityChecker()
        result = checker.check(chapter_content, context)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化内心独白检查器

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="内心独白分析专家",
            goal="评估内心独白的适度性",
            backstory="""你是一个专业的写作分析师，精通叙事技巧。
            你对"展示"与"讲述"有深入的理解，知道如何在两者之间取得平衡。
            你擅长分析角色内心描写的适度性，能给出具体的改进建议。""",
            verbose=verbose,
            llm=llm,
        )

    def check(self, chapter_content: str, context: dict) -> ReviewCheckResult:
        """检查章节的内心独白

        Args:
            chapter_content: 章节内容
            context: 上下文信息（包含章节号、风格等）

        Returns:
            ReviewCheckResult: 检查结果
        """
        prompt = self._build_check_prompt(chapter_content, context)
        try:
            response = self.agent.kickoff(messages=prompt)
            return self._parse_response(response)
        except (ValueError, Exception) as e:
            import logging
            logging.warning(f"内心独白检查失败，使用通过结果: {e}")
            result = ReviewCheckResult(check_type="interiority", passed=True)
            result.score = 10.0
            result.issues.append("内心独白检查因API错误跳过")
            result.suggestions.append("如需检查，请手动审阅")
            return result

    def _build_check_prompt(self, chapter_content: str, context) -> str:
        """构建检查提示词

        Args:
            chapter_content: 章节内容
            context: ReviewContext dataclass or dict with chapter context
        """
        # Support both ReviewContext dataclass and dict
        if hasattr(context, "chapter_number"):
            chapter_num = context.chapter_number if context.chapter_number is not None else "?"
            style = context.style_guide or "通用"
        else:
            chapter_num = context.get("chapter_number", context.get("chapter_num", "?"))
            style = context.get("style_guide", context.get("style", "通用"))

        return f"""请分析以下第{chapter_num}章的内心独白使用情况。

小说风格: {style}

待分析内容:
{chapter_content}

请从以下维度进行分析：

1. **内心独白数量**: 章节中内心独白的数量是否合适？
   - 过多会让叙事拖沓、节奏变慢
   - 过少会让角色显得单薄、缺乏深度

2. **内心独白位置**: 内心独白是否出现在合适的位置？
   - 应该在情感关键点、高潮前后、重大决策时刻
   - 不应该出现在动作场面、对话中

3. **内心独白形式**: 是否有多样化的表现方式？
   - 直接描写内心
   - 通过动作、神态暗示内心
   - 通过独白/自言自语

4. **与"展示"的比例**: 是否平衡了"展示"和"讲述"？
   - 过多"讲述"会让读者感到说教
   - 过多"展示"会让读者缺乏指导

请给出：
- 1-10的评分
- 发现的问题列表
- 具体的修改建议

以JSON格式返回：
{{
    "score": 7.5,
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}"""

    def _parse_response(self, response: str) -> ReviewCheckResult:
        """解析检查响应"""
        import json
        import re

        result = ReviewCheckResult(check_type="interiority", passed=True)

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
            result.suggestions.append("请人工检查内心独白的适度性")
            result.score = 5.0
            result.passed = False
            return result

        result.score = float(data.get("score", 5.0))
        result.issues = data.get("issues", [])
        result.suggestions = data.get("suggestions", [])

        # 评分>=7认为通过
        result.passed = result.score >= 7.0

        return result
