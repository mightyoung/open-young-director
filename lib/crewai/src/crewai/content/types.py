from enum import Enum
from typing import Optional, List
from dataclasses import dataclass, field


class ContentTypeEnum(Enum):
    """内容类型枚举"""
    NOVEL = "novel"
    SCRIPT = "script"
    BLOG = "blog"
    PODCAST = "podcast"


class NovelStyle(Enum):
    """小说风格"""
    XIANXIA = "xianxia"  # 修仙
    DOUSHI = "doushi"  # 都市
    XINBAN = "xinban"  # 新搬
    YANQING = "yanqing"  # 言情
    ZHENTAN = "zhentan"  # 侦探
    KONGFU = "kongfu"  # 武侠
    KEHAN = "kehan"  # 科幻


class ScriptFormat(Enum):
    """剧本格式"""
    FILM = "film"  # 电影
    TV = "tv"  # 电视剧
    SHORT = "short"  # 短剧
    STAGE = "stage"  # 舞台剧


class BlogPlatform(Enum):
    """博客平台"""
    WECHAT = "wechat"  # 微信公众号
    WEIBO = "weibo"  # 微博
    XIAOHONGSHU = "xiaohongshu"  # 小红书
    DOUYIN = "douyin"  # 抖音
    BILIBILI = "bilibili"  # B站
    ZHIHU = "zhihu"  # 知乎
    JUEJIN = "juejin"  # 掘金
    TOUTIAO = "toutiao"  # 头条


class PodcastFormat(Enum):
    """播客格式"""
    INTERVIEW = "interview"  # 访谈
    NARRATIVE = "narrative"  # 叙事
    PANEL = "panel"  # 圆桌
    SOLO = "solo"  # 单人


@dataclass
class ContentConfig:
    """内容生成配置"""
    content_type: ContentTypeEnum
    style: Optional[object] = None
    platform: Optional[object] = None
    language: str = "zh"
    max_words: Optional[int] = None
    target_audience: Optional[str] = None


@dataclass
class ContentOutput:
    """内容输出"""
    content_type: ContentTypeEnum
    title: str
    body: str
    metadata: dict = field(default_factory=dict)
    quality_score: Optional[float] = None
    warnings: List[str] = field(default_factory=list)


__all__ = [
    "ContentTypeEnum",
    "NovelStyle",
    "ScriptFormat",
    "BlogPlatform",
    "PodcastFormat",
    "ContentConfig",
    "ContentOutput",
]
