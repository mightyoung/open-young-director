"""SEO优化Agent - 多平台支持"""
from dataclasses import dataclass, field
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class SEOData:
    """SEO数据"""
    keywords: list[str] = field(default_factory=list)
    meta_description: str = ""
    tags: list[str] = field(default_factory=list)
    reading_time_minutes: int = 5
    word_count: int = 1000


class SEOAgent:
    """SEO优化Agent - 优化内容搜索引擎表现"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="SEO专家",
            goal="优化内容的搜索引擎排名和可见性",
            backstory="""你是一位SEO优化专家，精通各种搜索引擎优化技术。
            你了解关键词研究、Meta标签优化、内容结构优化技巧。
            你的目标是让内容获得更好的搜索排名和有机流量。""",
            llm=llm,
            verbose=False
        )

    def optimize(
        self,
        topic: str,
        title: str,
        body: str = "",
        target_keywords: list[str] = None,
        platform: str = "general"
    ) -> SEOData:
        """优化SEO

        Args:
            topic: 主题
            title: 标题
            body: 正文内容（可选）
            target_keywords: 目标关键词
            platform: 目标平台 (general, zhihu, juejin, wechat)

        Returns:
            SEO数据
        """
        keywords_str = ", ".join(target_keywords) if target_keywords else "无特定关键词"
        body_preview = body[:500] + "..." if len(body) > 500 else body

        prompt = f"""为以下内容进行SEO优化。

主题: {topic}
标题: {title}
正文预览: {body_preview}
目标关键词: {keywords_str}
目标平台: {platform}

请生成:
1. 核心关键词列表（5-10个）
2. Meta描述（150-160字符）
3. 标签列表（5-10个）
4. 预估阅读时间（基于字数）
5. 预估字数

请以JSON格式输出，格式如下:
{{
    "keywords": ["关键词1", "关键词2", ...],
    "meta_description": "Meta描述文本（150-160字符）",
    "tags": ["标签1", "标签2", ...],
    "reading_time_minutes": 5,
    "word_count": 2000
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result, body)

    def _parse_result(self, result, body: str = "") -> SEOData:
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
            return SEOData(
                keywords=data.get("keywords", []),
                meta_description=data.get("meta_description", ""),
                tags=data.get("tags", []),
                reading_time_minutes=data.get("reading_time_minutes", 5),
                word_count=data.get("word_count", len(body.split()) if body else 1000)
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return SEOData(
                keywords=[],
                meta_description=str(result)[:160],
                tags=[],
                reading_time_minutes=5,
                word_count=len(body.split()) if body else 1000
            )


__all__ = ["SEOAgent", "SEOData"]
