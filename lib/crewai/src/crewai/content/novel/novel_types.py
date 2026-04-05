"""小说内容生成类型定义"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

# 导入共享角色描述类型
from crewai.content.character.character_types import (
    BackgroundProfile,
    BehavioralProfile,
    CharacterArc,
    CharacterProfile,
    CharacterRelationship,
    PhysicalAppearance,
    PsychologicalProfile,
)

if TYPE_CHECKING:
    from crewai.content.novel.production_bible.bible_types import BibleSection


@dataclass
class PlotStrand:
    """情节链 - Strand Weave结构中的单条线索

    支持多线索并行叙事，每条线索有独立的情节发展和张力曲线。
    strand_type: main(主线), subplot_a(子情节A), subplot_b(子情节B), romance(感情线), etc.
    """
    strand_id: str = ""
    name: str = ""
    description: str = ""
    strand_type: str = "main"  # main, subplot_a, subplot_b, romance, etc.
    main_events: list[str] = field(default_factory=list)
    tension_arc: list[float] = field(default_factory=list)  # 0-10 tension levels over time
    resolution: str = ""  # 线索如何收束
    starting_state: str = ""  # 起点状态
    ending_state: str = ""  # 终点状态
    key_turning_points: list[str] = field(default_factory=list)  # 关键转折点


@dataclass
class ChapterOutput:
    """章节输出"""
    chapter_num: int
    title: str
    content: str
    word_count: int
    key_events: list[str] = field(default_factory=list)
    character_appearances: list[str] = field(default_factory=list)
    setting: str = ""
    notes: str = ""


@dataclass
class NovelOutput:
    """小说完整输出"""
    title: str
    genre: str
    style: str
    world_output: Any  # WorldOutput from outline_types
    characters: list[CharacterProfile] = field(default_factory=list)
    chapters: list[ChapterOutput] = field(default_factory=list)
    total_word_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_chapter(self, num: int) -> ChapterOutput | None:
        """获取指定章节"""
        for chapter in self.chapters:
            if chapter.chapter_num == num:
                return chapter
        return None

    def get_all_text(self) -> str:
        """获取所有章节文本"""
        return "\n\n".join(
            f"第{chapter.chapter_num}章: {chapter.title}\n\n{chapter.content}"
            for chapter in self.chapters
        )

    def save_to_file(self, base_dir: str = "output") -> list[str]:
        """保存小说内容到文件

        Args:
            base_dir: 基础目录，默认是output

        Returns:
            保存的文件路径列表
        """
        import os

        # 创建小说目录
        safe_title = self.title.replace("/", "-").replace("\\", "-").replace(" ", "_")
        novel_dir = os.path.join(base_dir, safe_title)
        os.makedirs(novel_dir, exist_ok=True)

        saved_files = []

        # 保存世界观
        world_file = os.path.join(novel_dir, "序章-世界观.md")
        world_content = self._format_world_content()
        with open(world_file, "w", encoding="utf-8") as f:
            f.write(world_content)
        saved_files.append(world_file)

        # 保存各章节
        for chapter in self.chapters:
            chapter_file = os.path.join(
                novel_dir,
                f"第{chapter.chapter_num:02d}章-{chapter.title}.md"
            )
            chapter_content = self._format_chapter_content(chapter)
            with open(chapter_file, "w", encoding="utf-8") as f:
                f.write(chapter_content)
            saved_files.append(chapter_file)

        return saved_files

    def _format_world_content(self) -> str:
        """格式化世界观内容"""
        lines = []
        lines.append(f"# {self.title} - 世界观设定\n")

        if hasattr(self.world_output, '__dict__'):
            world_data = self.world_output.__dict__
        elif isinstance(self.world_output, dict):
            world_data = self.world_output
        else:
            world_data = {"content": str(self.world_output)}

        # 尝试提取主要字段
        if "name" in world_data:
            lines.append(f"## 世界名称\n{world_data['name']}\n\n")
        if "description" in world_data:
            lines.append(f"## 世界描述\n{world_data['description']}\n\n")
        if "main_conflict" in world_data:
            lines.append(f"## 主要冲突\n{world_data['main_conflict']}\n\n")
        if "factions" in world_data:
            lines.append("## 主要势力\n")
            for faction in world_data["factions"]:
                if isinstance(faction, dict):
                    lines.append(f"### {faction.get('name', '未知')}\n")
                    lines.append(f"{faction.get('description', '')}\n\n")
                else:
                    lines.append(f"- {faction}\n")
            lines.append("\n")
        if "key_locations" in world_data:
            lines.append("## 关键地点\n")
            for loc in world_data["key_locations"]:
                if isinstance(loc, dict):
                    lines.append(f"### {loc.get('name', '未知')}\n")
                    lines.append(f"{loc.get('description', '')}\n\n")
                else:
                    lines.append(f"- {loc}\n")
            lines.append("\n")
        if "power_system" in world_data:
            lines.append("## 力量体系\n")
            ps = world_data["power_system"]
            if isinstance(ps, dict):
                if "name" in ps:
                    lines.append(f"### {ps['name']}\n")
                if "levels" in ps:
                    lines.append("#### 等级\n")
                    for level in ps["levels"]:
                        lines.append(f"- {level}\n")
                if "special_abilities" in ps:
                    lines.append("#### 特殊能力\n")
                    for ability in ps["special_abilities"]:
                        lines.append(f"- {ability}\n")
            else:
                lines.append(f"{ps}\n")
            lines.append("\n")

        # 如果没有提取到任何结构化内容，直接输出原始内容
        if len(lines) == 1:
            lines.append(str(self.world_output))

        return "".join(lines)

    def _format_chapter_content(self, chapter: ChapterOutput) -> str:
        """格式化章节内容"""
        lines = []
        lines.append(f"# 第{chapter.chapter_num}章 {chapter.title}\n\n")
        lines.append(f"**字数**: {chapter.word_count}\n\n")
        lines.append(f"**设定**: {chapter.setting}\n\n")

        if chapter.character_appearances:
            lines.append(f"**出场角色**: {', '.join(chapter.character_appearances)}\n\n")

        if chapter.key_events:
            lines.append("**关键事件**:\n")
            for event in chapter.key_events:
                lines.append(f"- {event}\n")
            lines.append("\n")

        lines.append("---\n\n")
        lines.append(chapter.content)

        if chapter.notes:
            lines.append(f"\n\n---\n\n**备注**: {chapter.notes}")

        return "".join(lines)


@dataclass
class WritingContext:
    """写作上下文"""
    title: str
    genre: str
    style: str
    world_description: str
    character_profiles: dict[str, str] = field(default_factory=dict)
    previous_chapters_summary: str = ""
    # 【情节连贯】专用字段：前章结尾的具体场景信息（地点+人物状态+情绪+未解决悬念）
    previous_chapter_ending: str = ""
    chapter_outline: str = ""
    target_word_count: int = 0
    current_chapter_num: int = 1
    tension_arc: str = ""  # 格式化的高潮点描述
    bible_section: "BibleSection | None" = field(default=None)  # ProductionBible section for this volume
    character_persona_context: str = "" # New field: RAG-retrieved personality snapshots

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "genre": self.genre,
            "style": self.style,
            "world_description": self.world_description,
            "character_profiles": self.character_profiles,
            "previous_chapters_summary": self.previous_chapters_summary,
            "previous_chapter_ending": self.previous_chapter_ending,
            "chapter_outline": self.chapter_outline,
            "target_word_count": self.target_word_count,
            "current_chapter_num": self.current_chapter_num,
            "tension_arc": self.tension_arc,
        }


@dataclass
class ReviewCheckResult:
    """检查结果"""
    check_type: str  # interiority, pov, consistency, etc.
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    score: float = 0.0  # 0-10

    def has_issues(self) -> bool:
        """是否存在需要修复的问题"""
        return len(self.issues) > 0


__all__ = [
    # Character description types
    "PhysicalAppearance",
    "PsychologicalProfile",
    "BehavioralProfile",
    "BackgroundProfile",
    "CharacterArc",
    "CharacterRelationship",
    "CharacterProfile",
    # Plot types
    "PlotStrand",
    # Chapter types
    "ChapterOutput",
    # Novel output
    "NovelOutput",
    # Writing context
    "WritingContext",
    # Review types
    "ReviewCheckResult",
]
