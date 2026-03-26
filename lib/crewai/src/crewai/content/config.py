"""内容生成配置模型"""

from dataclasses import dataclass, field
from typing import Optional, List

class ReviewLevel:
    """审查级别"""
    LIGHT = "light"
    STANDARD = "standard"
    STRICT = "strict"

class OutputFormat:
    """输出格式"""
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    JSON = "json"

@dataclass
class CritiqueConfig:
    """审查配置"""
    level: str = "standard"
    enable_consistency_check: bool = True
    enable_pacing_check: bool = True
    enable_ooc_check: bool = True
    enable_high_point_check: bool = True
    enable_continuity_check: bool = True
    max_issues_per_review: int = 10

@dataclass
class RevisionConfig:
    """修改配置"""
    max_iterations: int = 3
    min_quality_threshold: float = 0.7
    enable_auto_revision: bool = False
    revision_focus: List[str] = field(default_factory=list)

@dataclass
class ExportConfig:
    """导出配置"""
    format: str = "markdown"
    include_metadata: bool = True
    include_toc: bool = False
    platform_specific: bool = True

@dataclass
class NovelConfig:
    """小说特有配置"""
    enable_dianting: bool = True
    dianting_threshold: float = 0.6
    enable_chapter_ending_check: bool = True
    enable_shuanggan_pattern: bool = True
    enable_repetitive_check: bool = True
    max_chapter_words: int = 3000
    min_chapter_words: int = 1000

@dataclass
class ScriptConfig:
    """剧本特有配置"""
    enable_beat_sheet: bool = True
    enable_cinematography: bool = True
    format: str = "screenplay"
    target_duration_minutes: int = 120

@dataclass
class BlogConfig:
    """博客特有配置"""
    enable_hook: bool = True
    hook_types: List[str] = field(default_factory=list)
    enable_seo: bool = True
    seo_keywords: List[str] = field(default_factory=list)
    enable_thumbnail: bool = False
    target_ctr: float = 0.05

@dataclass
class PodcastConfig:
    """播客特有配置"""
    enable_cold_open: bool = True
    enable_segments: bool = True
    enable_ad_reads: bool = False
    target_duration_minutes: int = 30
    show_notes_enabled: bool = True

@dataclass
class ContentGenerationConfig:
    """内容生成总配置"""
    critique: CritiqueConfig = field(default_factory=CritiqueConfig)
    revision: RevisionConfig = field(default_factory=RevisionConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    novel: NovelConfig = field(default_factory=NovelConfig)
    script: ScriptConfig = field(default_factory=ScriptConfig)
    blog: BlogConfig = field(default_factory=BlogConfig)
    podcast: PodcastConfig = field(default_factory=PodcastConfig)
    verbose: bool = True
    max_execution_time: int = 300
    temperature: float = 0.7

__all__ = [
    "ReviewLevel",
    "OutputFormat",
    "CritiqueConfig",
    "RevisionConfig",
    "ExportConfig",
    "NovelConfig",
    "ScriptConfig",
    "BlogConfig",
    "PodcastConfig",
    "ContentGenerationConfig",
]
