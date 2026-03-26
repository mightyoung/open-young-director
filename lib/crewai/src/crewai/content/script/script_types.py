"""脚本输出类型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# 导入共享角色描述类型
from crewai.content.character.character_types import (
    CharacterProfile,
)


# ============================================================================
# 场景描述类型 (Scene Description Types)
# ============================================================================

@dataclass
class SceneEnvironment:
    """场景环境"""
    location_name: str = ""  # 地点名称
    location_type: str = ""  # indoor, outdoor, virtual, etc.
    specific_place: str = ""  # 具体场所 (咖啡馆、办公室)
    time_period: str = ""  # 时代背景
    season: str = ""  # 季节
    weather: str = ""  # 天气
    time_of_day: str = ""  # 时间 (凌晨、上午、黄昏)


@dataclass
class SceneAtmosphere:
    """场景氛围"""
    mood: str = ""  # 整体基调 (紧张、温馨、阴森)
    emotional_tone: str = ""  # 情感基调
    temperature: str = ""  # 冷暖
    lighting_quality: str = ""  # 光线 (明亮、昏暗、霓虹)
    lighting_color: str = ""  # 光线色彩
    sound_ambience: str = ""  # 声音环境
    sensory_details: List[str] = field(default_factory=list)  # 感官细节


@dataclass
class SceneLayout:
    """场景布局"""
    spatial_description: str = ""  # 空间描述
    key_objects: List[str] = field(default_factory=list)  # 关键物品
    prop_details: List[str] = field(default_factory=list)  # 道具细节
    spatial_relationships: str = ""  # 空间关系
    camera_suggestion: str = ""  # 镜头建议


@dataclass
class Beat:
    """单个Beat（场景转折点）"""
    number: int
    name: str
    description: str
    scene_purpose: str = ""  # 谁想要什么？障碍是什么？
    turning_point: bool = False


@dataclass
class BeatSheet:
    """分镜表"""
    act: str = ""  # Act I, Act IIa, etc.
    beats: List[Beat] = field(default_factory=list)
    total_runtime_estimate: int = 0  # 分钟


@dataclass
class SceneOutput:
    """场景输出 (增强版)"""
    scene_number: int = 0
    beat_number: int = 0
    location: str = ""  # 场景地点
    time_of_day: str = ""  # 日/夜
    characters: List[str] = field(default_factory=list)  # 出场角色
    action: str = ""  # 动作/场景描述

    # 增强字段
    environment: SceneEnvironment = field(default_factory=SceneEnvironment)
    atmosphere: SceneAtmosphere = field(default_factory=SceneAtmosphere)
    layout: SceneLayout = field(default_factory=SceneLayout)

    # 原有字段
    dialogue_count: int = 0  # 对白数量
    estimated_duration: int = 0  # 预估时长（分钟）
    visual_notes: str = ""  # 视觉提示

    # 新增字段
    transition_in: str = ""  # 转场进入
    transition_out: str = ""  # 转场离开
    symbolic_elements: List[str] = field(default_factory=list)  # 象征元素


@dataclass
class DialogueBlock:
    """对白块"""
    speaker: str = ""
    content: str = ""
    emotion: str = ""  # 情绪提示
    subtext: str = ""  # 潜台词


@dataclass
class SceneDialogue:
    """场景对白"""
    scene_number: int = 0
    location: str = ""
    time_of_day: str = ""
    dialogues: List[DialogueBlock] = field(default_factory=list)


@dataclass
class ScriptMetadata:
    """脚本元数据"""
    format: str = ""  # film, tv, short, stage
    genre: str = ""
    target_runtime: int = 0  # 分钟
    target_audience: str = ""
    rating: str = ""  # PG, PG-13, R, etc.


@dataclass
class ScriptOutput:
    """脚本输出"""
    title: str = ""
    logline: str = ""  # 一句话概括
    beat_sheets: List[BeatSheet] = field(default_factory=list)
    scenes: List[SceneOutput] = field(default_factory=list)
    dialogues: List[SceneDialogue] = field(default_factory=list)
    metadata: Optional[ScriptMetadata] = None
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# 短剧类型 (Short Drama Types)
# ============================================================================

@dataclass
class ShortDramaEpisode:
    """短剧单集"""
    episode_number: int = 0
    title: str = ""
    logline: str = ""  # 一句话概括
    synopsis: str = ""  # 剧情简介
    scenes: List[SceneOutput] = field(default_factory=list)
    key_conflicts: List[str] = field(default_factory=list)  # 核心冲突
    character_focus: List[str] = field(default_factory=list)  # 重点角色
    emotional_arc: List[str] = field(default_factory=list)  # 情感弧线
    climax_hint: str = ""  # 悬念提示
    call_to_action: str = ""  # 行动号召


@dataclass
class ShortDramaSeries:
    """短剧系列"""
    title: str = ""
    genre: str = ""
    format: str = ""  # short_drama, micro_drama
    target_platform: str = ""  # 抖音、快手、微视
    target_audience: str = ""
    total_episodes: int = 0
    episodes: List[ShortDramaEpisode] = field(default_factory=list)
    overall_theme: str = ""
    series_arc: str = ""  # 系列主线
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    # Shared character types
    "CharacterProfile",
    # Scene description types
    "SceneEnvironment",
    "SceneAtmosphere",
    "SceneLayout",
    # Beat types
    "Beat",
    "BeatSheet",
    # Scene types
    "SceneOutput",
    # Dialogue types
    "DialogueBlock",
    "SceneDialogue",
    # Script types
    "ScriptMetadata",
    "ScriptOutput",
    # Short drama types
    "ShortDramaEpisode",
    "ShortDramaSeries",
]
