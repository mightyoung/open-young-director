"""缩略图概念Agent"""
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class ThumbnailConcept:
    """缩略图概念"""
    variant: int
    concept: str  # 视觉概念描述
    suggested_elements: list[str]  # 建议元素
    color_scheme: str  # 配色方案
    text_overlay: str = None  # 文字叠加


class ThumbnailConceptAgent:
    """缩略图概念Agent - 生成视觉概念设计"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="视觉设计师",
            goal="生成吸引眼球的缩略图视觉概念",
            backstory="""你是一位视觉设计专家，擅长创作能吸引点击的缩略图概念。
            你了解各种视觉元素、配色方案和布局，能生成让人忍不住想点击的缩略图创意。""",
            llm=llm,
            verbose=False
        )

    def generate_concepts(
        self,
        topic: str,
        title: str,
        count: int = 3
    ) -> list[ThumbnailConcept]:
        """生成缩略图概念

        Args:
            topic: 主题
            title: 标题（用于文字叠加）
            count: 生成数量

        Returns:
            缩略图概念列表
        """
        prompt = f"""为以下内容生成{count}个缩略图视觉概念。

主题: {topic}
标题: {title}

要求:
1. 每个概念必须有独特的视觉创意
2. 包含具体的视觉元素建议
3. 指定配色方案
4. 考虑文字叠加位置
5. 概念应能激起用户好奇心和点击欲望

请以JSON格式输出，格式如下:
{{
    "concepts": [
        {{
            "variant": 1,
            "concept": "整体视觉概念描述",
            "suggested_elements": ["元素1", "元素2", "元素3"],
            "color_scheme": "配色方案描述",
            "text_overlay": "建议的文字叠加位置和内容"
        }}
    ]
}}
"""
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _parse_result(self, result) -> list[ThumbnailConcept]:
        """解析Agent输出"""
        concepts = []
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
            for c in data.get("concepts", []):
                concepts.append(ThumbnailConcept(
                    variant=c["variant"],
                    concept=c["concept"],
                    suggested_elements=c.get("suggested_elements", []),
                    color_scheme=c.get("color_scheme", "明亮配色"),
                    text_overlay=c.get("text_overlay")
                ))
        except (json.JSONDecodeError, KeyError, ValueError):
            concepts.append(ThumbnailConcept(
                variant=1,
                concept=str(result),
                suggested_elements=[],
                color_scheme="明亮配色"
            ))
        return concepts


__all__ = ["ThumbnailConcept", "ThumbnailConceptAgent"]
