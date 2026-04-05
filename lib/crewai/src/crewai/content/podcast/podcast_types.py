"""播客内容生成类型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class SegmentOutput:
    """播客段落输出 (增强版)"""
    segment_num: int = 0
    title: str = ""
    content: str = ""
    duration_minutes: float = 0.0
    key_points: List[str] = field(default_factory=list)
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    speaker_notes: Optional[str] = None

    # 增强字段
    talking_style: str = ""  # 说话风格建议
    energy_level: str = "medium"  # low/medium/high
    guest_interaction: Optional[str] = None  # 与嘉宾互动提示
    background_music_suggestion: str = ""  # 背景音乐建议
    audience_engagement_tips: List[str] = field(default_factory=list)  # 观众互动技巧


@dataclass
class InterviewOutput:
    """访谈环节输出"""
    guest_intro: str = ""
    questions: List[str] = field(default_factory=list)
    talking_points: List[str] = field(default_factory=list)
    conclusion: str = ""
    guest_name: Optional[str] = None
    guest_background: Optional[str] = None


@dataclass
class AdReadOutput:
    """广告口播输出"""
    sponsor_name: str = ""
    script: str = ""
    duration_seconds: int = 0
    placement: str = ""  # "pre_roll", "mid_roll", "post_roll"


@dataclass
class ShowNotesOutput:
    """节目笔记输出"""
    title: str = ""
    description: str = ""
    timestamps: List[Dict[str, Any]] = field(default_factory=list)
    guest_info: Optional[str] = None
    links: List[str] = field(default_factory=list)
    social_media: List[str] = field(default_factory=list)


@dataclass
class PodcastOutput:
    """播客完整输出

    status字段:
    - "complete": 所有启用的section都成功生成
    - "partial": 部分section生成失败（见failed_sections）
    - "failed": 整体生成失败
    """
    title: str = ""
    status: str = "complete"  # complete/partial/failed
    preshow: Optional[str] = None  # None means generation failed or section disabled
    intro: Optional[str] = None    # None means generation failed or section disabled
    outro: Optional[str] = None    # None means generation failed or section disabled
    shownotes: ShowNotesOutput = field(default_factory=ShowNotesOutput)
    total_duration_minutes: float = 0.0
    segments: List[SegmentOutput] = field(default_factory=list)
    interview: Optional[InterviewOutput] = None  # None means not enabled or failed
    ad_reads: List[AdReadOutput] = field(default_factory=list)  # empty means not enabled or failed
    metadata: Dict[str, Any] = field(default_factory=dict)  # failed_sections: dict[str, str] on partial failure


__all__ = [
    "SegmentOutput",
    "InterviewOutput",
    "AdReadOutput",
    "ShowNotesOutput",
    "PodcastOutput",
]
