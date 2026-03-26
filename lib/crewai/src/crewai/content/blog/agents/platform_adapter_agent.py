"""平台适配Agent - 适配不同博客平台"""
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class PlatformContent:
    """平台适配内容"""
    platform: str
    title: str
    body: str
    excerpt: str | None = None
    tags: list[str] = None
    category: str | None = None
    cover_image_suggestion: str | None = None


class PlatformAdapterAgent:
    """平台适配Agent - 为不同平台定制内容"""

    PLATFORM_CONFIGS = {
        "wechat": {
            "name": "微信公众号",
            "max_title_length": 64,
            "max_body_length": 20000,
            "requires_excerpt": False,
            "supports_tags": True,
            "supports_category": True,
        },
        "medium": {
            "name": "Medium",
            "max_title_length": 100,
            "max_body_length": 50000,
            "requires_excerpt": True,
            "supports_tags": True,
            "supports_category": False,
        },
        "wordpress": {
            "name": "WordPress",
            "max_title_length": 70,
            "max_body_length": 100000,
            "requires_excerpt": True,
            "supports_tags": True,
            "supports_category": True,
        },
        "zhihu": {
            "name": "知乎",
            "max_title_length": 100,
            "max_body_length": 100000,
            "requires_excerpt": False,
            "supports_tags": True,
            "supports_category": True,
        },
        "juejin": {
            "name": "掘金",
            "max_title_length": 100,
            "max_body_length": 100000,
            "requires_excerpt": True,
            "supports_tags": True,
            "supports_category": True,
        },
        "xiaohongshu": {
            "name": "小红书",
            "max_title_length": 20,
            "max_body_length": 1000,
            "requires_excerpt": False,
            "supports_tags": True,
            "supports_category": False,
        },
    }

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="平台适配专家",
            goal="为不同平台定制最优化的内容格式",
            backstory="""你是一位内容平台适配专家，精通各种内容平台的特点和最佳实践。
            你了解微信公众号、Medium、WordPress、知乎、掘金、小红书等平台的内容规范和用户习惯。
            你的目标是为每个平台定制最适合的内容格式。""",
            llm=llm,
            verbose=False
        )

    def adapt(
        self,
        topic: str,
        title: str,
        body: str,
        platform: str,
        seo_tags: list[str] = None,
        cover_image: str = None
    ) -> PlatformContent:
        """适配内容到指定平台

        Args:
            topic: 主题
            title: 原始标题
            body: 正文内容
            platform: 目标平台 (wechat, medium, wordpress, zhihu, juejin, xiaohongshu)
            seo_tags: SEO标签
            cover_image: 封面图建议

        Returns:
            平台适配内容
        """
        platform_config = self.PLATFORM_CONFIGS.get(
            platform,
            self.PLATFORM_CONFIGS["medium"]
        )

        prompt = f"""将以下内容适配到{platform_config['name']}平台。

原始标题: {title}
主题: {topic}
正文: {body[:2000]}...

{platform_config['name']}平台规范:
- 最大标题长度: {platform_config['max_title_length']}字符
- 最大正文长度: {platform_config['max_body_length']}字符
- 需要摘要: {"是" if platform_config['requires_excerpt'] else "否"}
- 支持标签: {"是" if platform_config['supports_tags'] else "否"}
- 支持分类: {"是" if platform_config['supports_category'] else "否"}

请生成适配后的内容，包括:
1. 优化后的标题（如需要）
2. 平台特定的摘要（如需要）
3. 标签建议
4. 分类建议（如支持）
5. 封面图建议

请以JSON格式输出，格式如下:
{{
    "platform": "{platform}",
    "title": "优化后的标题",
    "body": "适配后的正文",
    "excerpt": "摘要（如需要）",
    "tags": ["标签1", "标签2"],
    "category": "分类（如支持）",
    "cover_image_suggestion": "封面图建议"
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result, platform, body)

    def adapt_multiple(
        self,
        topic: str,
        title: str,
        body: str,
        platforms: list[str],
        seo_tags: list[str] = None,
        cover_image: str = None
    ) -> dict[str, PlatformContent]:
        """适配内容到多个平台

        Args:
            topic: 主题
            title: 原始标题
            body: 正文内容
            platforms: 目标平台列表
            seo_tags: SEO标签
            cover_image: 封面图建议

        Returns:
            各平台适配内容字典
        """
        results = {}
        for platform in platforms:
            results[platform] = self.adapt(
                topic=topic,
                title=title,
                body=body,
                platform=platform,
                seo_tags=seo_tags,
                cover_image=cover_image
            )
        return results

    def _parse_result(
        self,
        result,
        platform: str,
        original_body: str
    ) -> PlatformContent:
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
            return PlatformContent(
                platform=data.get("platform", platform),
                title=data.get("title", ""),
                body=data.get("body", original_body),
                excerpt=data.get("excerpt"),
                tags=data.get("tags", []),
                category=data.get("category"),
                cover_image_suggestion=data.get("cover_image_suggestion")
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return PlatformContent(
                platform=platform,
                title=str(result)[:64],
                body=original_body
            )


__all__ = ["PlatformAdapterAgent", "PlatformContent"]
