"""大纲引擎类型定义"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ============================================================================
# 世界观增强类型 (World Building Types)
# ============================================================================

@dataclass
class Theme:
    """核心主题"""
    name: str = ""
    description: str = ""
    manifestation: str = ""  # 如何在故事中体现


@dataclass
class TimelineEvent:
    """时间线事件"""
    era: str = ""
    year: str = ""
    event: str = ""
    significance: str = ""


@dataclass
class WorldRule:
    """世界规则"""
    rule: str = ""
    explanation: str = ""
    story_impact: str = ""


@dataclass
class Faction:
    """势力"""
    name: str = ""
    description: str = ""
    goals: List[str] = field(default_factory=list)
    allies: List[str] = field(default_factory=list)
    enemies: List[str] = field(default_factory=list)
    leader: str = ""  # 领袖
    headquarters: str = ""  # 总部


@dataclass
class Location:
    """地点"""
    name: str = ""
    description: str = ""
    significance: str = ""
    climate: str = ""  # 气候
    population: str = ""  # 人口


@dataclass
class PowerSystem:
    """力量体系"""
    name: str = ""
    levels: List[str] = field(default_factory=list)
    special_abilities: List[str] = field(default_factory=list)
    cultivation_resources: List[str] = field(default_factory=list)  # 修炼资源


@dataclass
class WorldOutput:
    """世界观输出 (增强版)

    包含完整的世界构建体系：
    - 基础信息：名称、描述
    - 核心设定：主题、时间线、世界规则
    - 势力分布：主要势力、关系
    - 地理环境：关键地点
    - 力量体系：修炼等级、特殊能力
    - 历史背景：世界历史概述
    - 宇宙观：世界观/哲学
    """
    name: str = ""
    description: str = ""
    main_conflict: str = ""

    # 增强字段
    themes: List[Theme] = field(default_factory=list)  # 核心主题
    timeline: List[TimelineEvent] = field(default_factory=list)  # 时间线事件
    rules: List[WorldRule] = field(default_factory=list)  # 世界规则
    history: str = ""  # 世界历史概述
    cosmology: str = ""  # 世界观/宇宙观

    # 原有字段
    factions: List[Faction] = field(default_factory=list)
    key_locations: List[Location] = field(default_factory=list)
    power_system: Optional[PowerSystem] = None


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_num: int = 0
    volume_num: int = 0  # 所属卷号
    title: str = ""
    hook: str = ""
    main_conflict: str = ""
    resolution: str = ""
    word_target: int = 0
    key_events: List[str] = field(default_factory=list)
    character_developments: List[str] = field(default_factory=list)
    notes: str = ""

    # 新增字段
    subplots: List[str] = field(default_factory=list)  # 涉及的子情节
    tension_level: float = 5.0  # 张力等级 0-10
    climax_point: bool = False  # 是否为高潮章节


@dataclass
class VolumeOutline:
    """卷大纲 - 包含多章的卷级结构

    用于组织长篇故事，每卷有独立的主题和情节发展，
    卷内包含多个章节，卷与卷之间有递进关系。
    """
    volume_num: int = 0
    title: str = ""
    description: str = ""  # 卷概述/主题
    hook: str = ""  # 卷开场钩子
    main_conflict: str = ""  # 本卷主要冲突
    resolution: str = ""  # 本卷如何收束

    # 子结构
    chapters: List[ChapterOutline] = field(default_factory=list)  # 卷内章节

    # 卷级元数据
    word_target: int = 0  # 本卷总字数目标
    key_events: List[str] = field(default_factory=list)  # 本卷关键事件
    character_arcs: List[str] = field(default_factory=list)  # 本卷角色弧线

    # 张力曲线
    tension_arc: List[float] = field(default_factory=list)  # 0-10 张力变化
    climax_point: bool = False  # 是否为本卷高潮卷

    # 关联
    plot_strands: List[str] = field(default_factory=list)  # 本卷涉及的情节线
    subplots: List[str] = field(default_factory=list)  # 本卷子情节
    notes: str = ""  # 卷注释


@dataclass
class PlotStrandOutline:
    """情节线大纲"""
    strand_id: str = ""
    name: str = ""
    strand_type: str = "main"  # main, subplot_a, romance, etc.
    description: str = ""
    chapters_affected: List[int] = field(default_factory=list)  # 涉及的章节
    resolution: str = ""  # 如何收束


@dataclass
class CharacterArcOutline:
    """角色弧线大纲"""
    character_name: str = ""
    arc_description: str = ""  # 弧线描述
    starting_point: str = ""  # 起点
    ending_point: str = ""  # 终点
    key_development_chapters: List[int] = field(default_factory=list)  # 关键发展章节


@dataclass
class OutlineOutput:
    """大纲输出 (增强版)

    包含完整的故事规划体系：
    - 世界观
    - 卷大纲（含多章节）
    - 情节线系统
    - 角色弧线
    - 节奏注释
    """
    world: WorldOutput
    volumes: List[VolumeOutline] = field(default_factory=list)  # 卷大纲（每卷含多章）
    chapters: List[ChapterOutline] = field(default_factory=list)  # 所有章节（扁平列表，便于遍历）
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 增强字段
    plot_strands: List[PlotStrandOutline] = field(default_factory=list)  # 所有情节线
    main_conflict_arc: List[str] = field(default_factory=list)  # 主冲突弧线
    character_arcs: List[CharacterArcOutline] = field(default_factory=list)  # 角色弧线
    pacing_notes: str = ""  # 节奏注释
    series_overview: str = ""  # 系列概览（多部作品时）

    # 便捷方法
    def get_volume(self, volume_num: int) -> Optional[VolumeOutline]:
        """获取指定卷"""
        for volume in self.volumes:
            if volume.volume_num == volume_num:
                return volume
        return None

    def get_chapter(self, volume_num: int, chapter_num: int) -> Optional[ChapterOutline]:
        """获取指定卷中的指定章节"""
        volume = self.get_volume(volume_num)
        if volume:
            for chapter in volume.chapters:
                if chapter.chapter_num == chapter_num:
                    return chapter
        return None

    def get_all_chapters(self) -> List[ChapterOutline]:
        """获取扁平化的所有章节列表"""
        return self.chapters


__all__ = [
    # World building types
    "Theme",
    "TimelineEvent",
    "WorldRule",
    "Faction",
    "Location",
    "PowerSystem",
    "WorldOutput",
    # Volume types
    "VolumeOutline",
    # Chapter types
    "ChapterOutline",
    # Plot types
    "PlotStrandOutline",
    "CharacterArcOutline",
    # Outline types
    "OutlineOutput",
]
