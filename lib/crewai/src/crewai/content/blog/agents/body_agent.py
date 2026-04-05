"""正文生成Agent"""
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class BodyContent:
    """博客正文内容"""
    body: str
    word_count: int
    outline: list[str]
    sections: list[dict]


class BodyAgent:
    """正文生成Agent - 创作完整博客正文"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="博客写作专家",
            goal="生成结构清晰、内容详实的博客正文",
            backstory="""你是一位资深博客写作者，擅长创作引人入胜的长文博客。
            你的文章结构清晰：开篇Hook吸引读者，中间内容充实有料，结尾有力总结。
            你善于使用小标题分割内容，使用列表和表格增强可读性。""",
            llm=llm,
            verbose=False
        )

    def generate_body(
        self,
        topic: str,
        title: str,
        hooks: list[str] = None,
        target_words: int = 2000,
        include_keywords: list[str] = None,
    ) -> BodyContent:
        """生成博客正文

        Args:
            topic: 主题
            title: 标题
            hooks: 钩子文本列表
            target_words: 目标字数
            include_keywords: 需要包含的关键词

        Returns:
            正文内容对象
        """
        hooks_str = "\n".join([f"- {h}" for h in hooks]) if hooks else "无"
        keywords_str = ", ".join(include_keywords) if include_keywords else "无"

        prompt = f"""为主题生成一篇结构清晰的博客正文。

主题: {topic}
标题: {title}
参考钩子:
{hooks_str}

目标字数: {target_words}字
需要包含的关键词: {keywords_str}

要求:
1. 文章结构: 开篇Hook → 正文(分段小标题) → 总结
2. 每个章节有清晰的小标题
3. 内容充实，深入浅出
4. 自然融入关键词
5. 字数控制在{target_words}字左右

请以JSON格式输出，格式如下:
{{
    "body": "完整正文内容（包含小标题）",
    "word_count": 2000,
    "outline": ["开篇", "章节1小标题", "章节2小标题", "总结"],
    "sections": [
        {{"heading": "开篇", "content": "...", "word_count": 300}},
        {{"heading": "章节1小标题", "content": "...", "word_count": 500}}
    ]
}}
"""
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _parse_result(self, result) -> BodyContent:
        """解析Agent输出"""
        try:
            text = str(result)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            data = json.loads(text)
            return BodyContent(
                body=data.get("body", str(result)),
                word_count=int(data.get("word_count", len(str(result)) // 4)),
                outline=data.get("outline", []),
                sections=data.get("sections", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return BodyContent(
                body=str(result),
                word_count=len(str(result)) // 4,
                outline=[],
                sections=[],
            )


__all__ = ["BodyAgent", "BodyContent"]
