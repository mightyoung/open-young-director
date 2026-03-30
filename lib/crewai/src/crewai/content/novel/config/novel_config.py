"""Novel generation typed configuration."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NovelConfig:
    """小说生成的显式类型配置。

    替代隐式 dict 配置，提供强类型检查和清晰的接口契约。
    """

    # Required fields
    topic: str = ""

    # Style and genre
    style: str = "urban"  # urban/xianxia/doushi/modern
    genre: str = ""  # Defaults to style if empty

    # Word count and chapters
    target_words: int = 100000
    num_chapters: int = 0  # 0 = auto-calculate based on target_words

    # Volume configuration
    num_volumes: int = 3
    max_concurrent_volumes: int = 3

    # LLM configuration
    llm: Optional[Any] = None

    # Output
    output_dir: str = "./novel_output"

    # Writing modes
    use_orchestrator: bool = True
    max_subagent_concurrent: int = 5
    max_concurrent_scenes: int = 3

    # Feature flags
    enable_verification: bool = True
    enable_evolution: bool = True
    review_each_chapter: bool = False
    approval_mode: bool = False

    # Seed for deterministic replay
    seed: Optional[str] = None
    seed_variant: Optional[str] = None

    def __post_init__(self):
        """Post-initialization processing."""
        # Auto-calculate num_chapters if not set
        if self.num_chapters <= 0:
            self.num_chapters = max(1, self.target_words // 10000)
        # Default genre to style if empty
        if not self.genre:
            self.genre = self.style

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 NovelCrew 兼容）。

        Returns:
            dict: 兼容 NovelCrew 的配置字典
        """
        return {
            "topic": self.topic,
            "style": self.style,
            "genre": self.genre,
            "target_words": self.target_words,
            "num_chapters": self.num_chapters,
            "num_volumes": self.num_volumes,
            "max_concurrent_volumes": self.max_concurrent_volumes,
            "llm": self.llm,
            "output_dir": self.output_dir,
            "use_orchestrator": self.use_orchestrator,
            "max_subagent_concurrent": self.max_subagent_concurrent,
            "max_concurrent_scenes": self.max_concurrent_scenes,
            "enable_verification": self.enable_verification,
            "enable_evolution": self.enable_evolution,
            "review_each_chapter": self.review_each_chapter,
            "approval_mode": self.approval_mode,
            "seed": self.seed,
            "seed_variant": self.seed_variant,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NovelConfig":
        """从字典创建配置。

        Args:
            data: 配置字典

        Returns:
            NovelConfig: 实例
        """
        return cls(
            topic=data.get("topic", ""),
            style=data.get("style", "urban"),
            genre=data.get("genre", data.get("style", "")),
            target_words=data.get("target_words", 100000),
            num_chapters=data.get("num_chapters", 0),
            num_volumes=data.get("num_volumes", 3),
            max_concurrent_volumes=data.get("max_concurrent_volumes", 3),
            llm=data.get("llm"),
            output_dir=data.get("output_dir", "./novel_output"),
            use_orchestrator=data.get("use_orchestrator", True),
            max_subagent_concurrent=data.get("max_subagent_concurrent", 5),
            max_concurrent_scenes=data.get("max_concurrent_scenes", 3),
            enable_verification=data.get("enable_verification", True),
            enable_evolution=data.get("enable_evolution", True),
            review_each_chapter=data.get("review_each_chapter", False),
            approval_mode=data.get("approval_mode", False),
            seed=data.get("seed"),
            seed_variant=data.get("seed_variant"),
        )


@dataclass
class ScriptConfig:
    """脚本生成的显式类型配置。"""

    topic: str = ""
    script_format: str = "film"  # film/tv/web series
    target_duration: int = 120  # minutes
    num_acts: int = 3
    style: str = "drama"
    llm: Optional[Any] = None
    output_dir: str = "./script_output"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "script_format": self.script_format,
            "target_duration": self.target_duration,
            "num_acts": self.num_acts,
            "style": self.style,
            "llm": self.llm,
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScriptConfig":
        return cls(
            topic=data.get("topic", ""),
            script_format=data.get("script_format", "film"),
            target_duration=data.get("target_duration", 120),
            num_acts=data.get("num_acts", 3),
            style=data.get("style", "drama"),
            llm=data.get("llm"),
            output_dir=data.get("output_dir", "./script_output"),
        )


@dataclass
class BlogConfig:
    """博客生成的显式类型配置。"""

    topic: str = ""
    target_platforms: list[str] = field(default_factory=lambda: ["medium"])
    include_keywords: list[str] = field(default_factory=list)
    title_style: str = "seo"  # seo/clickbait/technical
    llm: Optional[Any] = None
    output_dir: str = "./blog_output"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "target_platforms": self.target_platforms,
            "include_keywords": self.include_keywords,
            "title_style": self.title_style,
            "llm": self.llm,
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlogConfig":
        return cls(
            topic=data.get("topic", ""),
            target_platforms=data.get("target_platforms", ["medium"]),
            include_keywords=data.get("include_keywords", []),
            title_style=data.get("title_style", "seo"),
            llm=data.get("llm"),
            output_dir=data.get("output_dir", "./blog_output"),
        )


@dataclass
class PodcastConfig:
    """播客生成的显式类型配置。"""

    topic: str = ""
    duration_minutes: int = 30
    hosts: int = 2
    style: str = "conversational"
    include_interview: bool = False
    include_ads: bool = False
    llm: Optional[Any] = None
    output_dir: str = "./podcast_output"

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "duration_minutes": self.duration_minutes,
            "hosts": self.hosts,
            "style": self.style,
            "include_interview": self.include_interview,
            "include_ads": self.include_ads,
            "llm": self.llm,
            "output_dir": self.output_dir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PodcastConfig":
        return cls(
            topic=data.get("topic", ""),
            duration_minutes=data.get("duration_minutes", 30),
            hosts=data.get("hosts", 2),
            style=data.get("style", "conversational"),
            include_interview=data.get("include_interview", False),
            include_ads=data.get("include_ads", False),
            llm=data.get("llm"),
            output_dir=data.get("output_dir", "./podcast_output"),
        )
