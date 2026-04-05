from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class ReviewContext:
    """审查上下文 - 包含审查所需的所有上下文信息"""

    title: str = ""
    genre: str = ""
    target_audience: str = ""
    style_guide: str = ""
    previous_chapters_summary: str = ""
    # 【情节连贯】前章结尾的具体场景信息（地点+人物状态+情绪+未解决悬念）
    previous_chapter_ending: str = ""
    character_profiles: Dict[str, str] = field(default_factory=dict)
    world_rules: Dict[str, str] = field(default_factory=dict)
    writing_goals: str = ""
    pacing_notes: str = ""
    tension_arc: str = ""
    bible_section: Optional[Any] = None

    # Optional metadata
    chapter_number: Optional[int] = None
    word_count_target: Optional[int] = None
    current_word_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "title": self.title,
            "genre": self.genre,
            "target_audience": self.target_audience,
            "style_guide": self.style_guide,
            "previous_chapters_summary": self.previous_chapters_summary,
            "previous_chapter_ending": self.previous_chapter_ending,
            "character_profiles": self.character_profiles,
            "world_rules": self.world_rules,
            "writing_goals": self.writing_goals,
            "pacing_notes": self.pacing_notes,
            "tension_arc": self.tension_arc,
            "chapter_number": self.chapter_number,
            "word_count_target": self.word_count_target,
            "current_word_count": self.current_word_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewContext":
        """从字典创建"""
        return cls(
            title=data.get("title", ""),
            genre=data.get("genre", ""),
            target_audience=data.get("target_audience", ""),
            style_guide=data.get("style_guide", ""),
            previous_chapters_summary=data.get("previous_chapters_summary", ""),
            previous_chapter_ending=data.get("previous_chapter_ending", ""),
            character_profiles=data.get("character_profiles", {}),
            world_rules=data.get("world_rules", {}),
            writing_goals=data.get("writing_goals", ""),
            pacing_notes=data.get("pacing_notes", ""),
            tension_arc=data.get("tension_arc", ""),
            chapter_number=data.get("chapter_number"),
            word_count_target=data.get("word_count_target"),
            current_word_count=data.get("current_word_count"),
        )

    def get_context_string(self) -> str:
        """获取格式化的上下文字符串"""
        parts = []

        if self.title:
            parts.append(f"标题: {self.title}")
        if self.genre:
            parts.append(f"类型: {self.genre}")
        if self.target_audience:
            parts.append(f"目标受众: {self.target_audience}")
        if self.style_guide:
            parts.append(f"风格指南: {self.style_guide}")
        if self.writing_goals:
            parts.append(f"写作目标: {self.writing_goals}")
        if self.pacing_notes:
            parts.append(f"节奏笔记: {self.pacing_notes}")
        if self.tension_arc:
            parts.append(f"张力曲线: {self.tension_arc}")

        if self.character_profiles:
            parts.append("\n角色设定:")
            for name, profile in self.character_profiles.items():
                parts.append(f"  - {name}: {profile}")

        if self.world_rules:
            parts.append("\n世界观规则:")
            for rule, description in self.world_rules.items():
                parts.append(f"  - {rule}: {description}")

        if self.previous_chapters_summary:
            parts.append(f"\n前章概要:\n{self.previous_chapters_summary}")

        if self.previous_chapter_ending:
            parts.append(f"\n前章结尾场景（连贯性检查用）:\n{self.previous_chapter_ending}")

        return "\n".join(parts)
