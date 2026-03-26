"""角色描述类型定义 - 跨内容类型共享的角色描述体系"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


# ============================================================================
# 角色描述类型 (Character Description Types)
# ============================================================================

@dataclass
class PhysicalAppearance:
    """外形描述"""
    age_appearance: str = ""  # 外貌年龄
    build: str = ""  # 体型
    height: str = ""  # 身高
    hair: str = ""  # 发型发色
    eyes: str = ""  # 眼睛
    skin: str = ""  # 肤色
    distinctive_features: List[str] = field(default_factory=list)  # 标志性特征
    usual_attire: str = ""  # 常穿衣着
    posture: str = ""  # 姿态
    facial_expression: str = ""  # 常见表情


@dataclass
class PsychologicalProfile:
    """心理特征"""
    personality_type: str = ""  # MBTI/大五
    core_traits: List[str] = field(default_factory=list)  # 核心特质
    strengths: List[str] = field(default_factory=list)  # 优点
    weaknesses: List[str] = field(default_factory=list)  # 缺点
    fears: List[str] = field(default_factory=list)  # 恐惧
    desires: List[str] = field(default_factory=list)  # 欲望
    inner_conflict: str = ""  # 内心冲突
    emotional_wounds: List[str] = field(default_factory=list)  # 情感创伤


@dataclass
class BehavioralProfile:
    """行为特征"""
    speech_patterns: str = ""  # 说话方式
    mannerisms: List[str] = field(default_factory=list)  # 习惯性动作
    habits: List[str] = field(default_factory=list)  # 癖好
    body_language: str = ""  # 肢体语言
    vocabulary_level: str = ""  # 用词水平
    catchphrases: List[str] = field(default_factory=list)  # 口头禅


@dataclass
class BackgroundProfile:
    """背景描述"""
    birth_place: str = ""  # 出生地
    family_background: str = ""  # 家庭背景
    education: str = ""  # 教育程度
    occupation: str = ""  # 职业
    socioeconomic_status: str = ""  # 经济状况
    major_life_events: List[str] = field(default_factory=list)  # 重大人生事件
    cultural_background: str = ""  # 文化背景


@dataclass
class CharacterArc:
    """角色成长弧线"""
    starting_state: str = ""  # 起点状态
    catalyst_event: str = ""  # 催化事件
    major_conflict: str = ""  # 主要冲突
    transformation: str = ""  # 转变过程
    ending_state: str = ""  # 终点状态
    lessons_learned: List[str] = field(default_factory=list)  # 学到的教训


@dataclass
class CharacterRelationship:
    """人物关系"""
    character_name: str = ""
    relationship_type: str = ""  # friend, enemy, lover, family, mentor, etc.
    description: str = ""  # 关系描述
    history: str = ""  # 关系历史
    current_status: str = ""  # 当前状态
    dynamics: str = ""  # 互动动力


@dataclass
class CharacterProfile:
    """角色设定 (增强版)

    包含完整的角色描述体系：
    - 基础信息：姓名、定位
    - 外形描述：外貌、穿着、标志性特征
    - 心理特征：性格类型、优缺点、恐惧欲望
    - 行为特征：说话方式、习惯动作、口头禅
    - 背景描述：出生、教育、职业、人生重大事件
    - 角色弧线：起点→转变→终点
    - 人物关系：与其他角色的关系网
    """
    name: str = ""
    role: str = ""  # protagonist, antagonist, supporting
    backstory: str = ""  # 背景故事
    personality: str = ""  # 性格概述
    goals: List[str] = field(default_factory=list)  # 目标

    # 增强字段
    physical: PhysicalAppearance = field(default_factory=PhysicalAppearance)
    psychological: PsychologicalProfile = field(default_factory=PsychologicalProfile)
    behavioral: BehavioralProfile = field(default_factory=BehavioralProfile)
    background: BackgroundProfile = field(default_factory=BackgroundProfile)
    character_arc: CharacterArc = field(default_factory=CharacterArc)
    relationships: List[CharacterRelationship] = field(default_factory=list)

    # 额外字段
    values: List[str] = field(default_factory=list)  # 核心价值观
    secrets: List[str] = field(default_factory=list)  # 秘密
    quotes: List[str] = field(default_factory=list)  # 标志性台词

    def to_simple_dict(self) -> Dict[str, Any]:
        """转换为简化字典（兼容原有接口）"""
        return {
            "name": self.name,
            "role": self.role,
            "backstory": self.backstory,
            "personality": self.personality,
            "goals": self.goals,
            "relationships": {
                r.character_name: r.relationship_type
                for r in self.relationships
            },
        }


__all__ = [
    "PhysicalAppearance",
    "PsychologicalProfile",
    "BehavioralProfile",
    "BackgroundProfile",
    "CharacterArc",
    "CharacterRelationship",
    "CharacterProfile",
]
