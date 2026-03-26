"""博客内容输出类型定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HookType(Enum):
    """钩子类型"""
    QUESTION = "question"  # 问题式
    STATEMENT = "statement"  # 声明式
    STATISTIC = "statistic"  # 数据式
    STORY = "story"  # 故事式
    CONTRAST = "contrast"  # 对比式
    PROVOCATION = "provocation"  # 挑衅式


class TitleStyle(Enum):
    """标题风格"""
    SENSATIONAL = "sensational"  # 震惊体
    Curiosity = "curiosity"  # 好奇心
    LIST = "list"  # 列表体
    GUIDE = "guide"  # 指南体
    QUESTION = "question"  # 疑问体
    NUMBER = "number"  # 数字体


@dataclass
class HookOption:
    """钩子选项"""
    variant: int
    hook_text: str
    hook_type: str  # question, statement, statistic, story, etc.
    engagement_score: float  # 预估参与度 (1-10)


@dataclass
class TitleOption:
    """标题选项"""
    variant: int
    title: str
    style: str  # sensational, curiosity, list, guide, question, number
    click_score: float  # 预估点击率 (1-10)
    seo_score: float  # SEO友好度 (1-10)


@dataclass
class ThumbnailConcept:
    """缩略图概念"""
    variant: int
    concept: str  # 视觉概念描述
    suggested_elements: list[str]  # 建议元素
    color_scheme: str  # 配色方案
    text_overlay: str | None = None  # 文字叠加


@dataclass
class SEOData:
    """SEO数据"""
    keywords: list[str]
    meta_description: str
    tags: list[str]
    reading_time_minutes: int
    word_count: int


@dataclass
class PlatformContent:
    """平台适配内容"""
    platform: str  # wechat, medium, wordpress, etc.
    title: str
    body: str
    excerpt: str | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    cover_image_suggestion: str | None = None


@dataclass
class BlogPost:
    """博客文章完整输出"""
    original_topic: str
    title: str
    hooks: list[HookOption]
    selected_hook: HookOption | None = None
    body: str = ""
    seo: SEOData | None = None
    thumbnail_concepts: list[ThumbnailConcept] = field(default_factory=list)
    selected_thumbnail: ThumbnailConcept | None = None
    platform_contents: dict[str, PlatformContent] = field(default_factory=dict)
    quality_score: float | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlogCrewOutput:
    """BlogCrew执行输出"""
    post: BlogPost
    tasks_completed: list[str]
    execution_time: float
    metadata: dict[str, Any]


__all__ = [
    "BlogCrewOutput",
    "BlogPost",
    "HookOption",
    "HookType",
    "PlatformContent",
    "SEOData",
    "ThumbnailConcept",
    "TitleOption",
    "TitleStyle",
]
