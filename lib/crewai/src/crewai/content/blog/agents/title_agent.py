"""标题生成Agent"""
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class TitleOption:
    """标题选项"""
    variant: int
    title: str
    style: str  # sensational, curiosity, list, guide, question, number
    click_score: float  # 预估点击率 (1-10)
    seo_score: float  # SEO友好度 (1-10)


class TitleAgent:
    """标题生成Agent - 创作高点击率标题"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="标题创作专家",
            goal="生成5-10个高点击率、SEO友好的标题变体",
            backstory="""你是一位标题党大师，擅长创作让人忍不住点击的标题。
            你深谙各种标题类型：震惊体、好奇心、列表体、指南体、疑问体、数字体。
            你的标题既要吸引点击，又要SEO友好。""",
            llm=llm,
            verbose=False
        )

    def generate_titles(
        self,
        topic: str,
        count: int = 5,
        include_keywords: list[str] = None
    ) -> list[TitleOption]:
        """生成标题变体

        Args:
            topic: 主题
            count: 生成数量
            include_keywords: 需要包含的关键词

        Returns:
            标题选项列表
        """
        keywords_str = ", ".join(include_keywords) if include_keywords else "无特定关键词"

        prompt = f"""为以下主题生成{count}个标题变体，要求高点击率且SEO友好。

主题: {topic}
需要包含的关键词: {keywords_str}

要求:
1. 每个标题必须吸引点击
2. 标题类型多样: 震惊体、好奇心、列表体、指南体、疑问体、数字体
3. 兼顾SEO友好度
4. 每个标题标注点击率评分(1-10)和SEO评分(1-10)

请以JSON格式输出，格式如下:
{{
    "titles": [
        {{
            "variant": 1,
            "title": "标题文本",
            "style": "sensational/curiosity/list/guide/question/number",
            "click_score": 8.5,
            "seo_score": 7.0
        }}
    ]
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result)

    def _parse_result(self, result) -> list[TitleOption]:
        """解析Agent输出"""
        titles = []
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
            for t in data.get("titles", []):
                titles.append(TitleOption(
                    variant=t["variant"],
                    title=t["title"],
                    style=t["style"],
                    click_score=float(t["click_score"]),
                    seo_score=float(t["seo_score"])
                ))
        except (json.JSONDecodeError, KeyError, ValueError):
            titles.append(TitleOption(
                variant=1,
                title=str(result),
                style="curiosity",
                click_score=5.0,
                seo_score=5.0
            ))
        return titles


__all__ = ["TitleAgent", "TitleOption"]
