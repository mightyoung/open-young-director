"""Chapter Snapshot - Per-Chapter PostPass data structures."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CharacterSnapshot:
    """角色快照 - 记录角色在特定章节的状态"""

    name: str
    status: str = "alive"  # alive, dead, injured, missing
    location: str = ""
    emotional_state: str = ""
    relationships: dict[str, str] = field(default_factory=dict)
    appearances: list[str] = field(default_factory=list)  # 出现的场景


@dataclass
class LocationSnapshot:
    """地点快照"""

    name: str
    description: str = ""
    characters_present: list[str] = field(default_factory=list)


@dataclass
class TimelineEntry:
    """时间线条目"""

    chapter: int
    day_number: int = 0
    time_of_day: str = ""  # morning, afternoon, evening, night
    description: str = ""
    location: str = ""


@dataclass
class ForeshadowingEntry:
    """伏笔条目"""

    planted_chapter: int
    description: str
    payoff_chapter: int = 0
    payoff_description: str = ""
    is_resolved: bool = False


@dataclass
class ChapterSnapshot:
    """章节快照 - 每章生成后创建"""

    chapter_num: int
    character_states: dict[str, CharacterSnapshot] = field(default_factory=dict)
    location_states: dict[str, LocationSnapshot] = field(default_factory=dict)
    timeline_entries: list[TimelineEntry] = field(default_factory=list)
    foreshadowing_planted: list[str] = field(default_factory=list)  # 埋下的伏笔
    new_characters: list[str] = field(default_factory=list)  # 本章新出现的角色
    key_events: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "chapter_num": self.chapter_num,
            "character_states": {
                name: {
                    "status": cs.status,
                    "location": cs.location,
                    "emotional_state": cs.emotional_state,
                    "relationships": cs.relationships,
                }
                for name, cs in self.character_states.items()
            },
            "new_characters": self.new_characters,
            "key_events": self.key_events,
        }


@dataclass
class GlobalStoryState:
    """全局故事状态 - 在整个生成过程中持久化"""

    characters: dict[str, CharacterSnapshot] = field(default_factory=dict)
    locations: dict[str, LocationSnapshot] = field(default_factory=dict)
    timeline: list[TimelineEntry] = field(default_factory=list)
    foreshadowing: dict[str, ForeshadowingEntry] = field(default_factory=dict)  # id -> entry
    chapter_snapshots: list[ChapterSnapshot] = field(default_factory=list)

    def add_chapter_snapshot(self, snapshot: ChapterSnapshot) -> None:
        """添加章节快照并更新全局状态"""
        self.chapter_snapshots.append(snapshot)
        # 更新角色状态
        for name, char_state in snapshot.character_states.items():
            self.characters[name] = char_state
        # 更新地点状态
        for name, loc_state in snapshot.location_states.items():
            self.locations[name] = loc_state
        # 添加时间线条目
        self.timeline.extend(snapshot.timeline_entries)

    def get_character_location(self, character_name: str) -> str | None:
        """获取角色当前位置"""
        if character_name in self.characters:
            return self.characters[character_name].location
        return None

    def is_character_alive(self, character_name: str) -> bool:
        """检查角色是否存活"""
        if character_name in self.characters:
            return self.characters[character_name].status == "alive"
        return True  # 未知的角色默认存活

    def plant_foreshadowing(self, chapter: int, description: str) -> str:
        """埋下伏笔，返回伏笔ID"""
        import uuid

        fid = str(uuid.uuid4())[:8]
        self.foreshadowing[fid] = ForeshadowingEntry(
            planted_chapter=chapter,
            description=description,
        )
        return fid

    def resolve_foreshadowing(self, fid: str, chapter: int, payoff_description: str) -> None:
        """回收伏笔"""
        if fid in self.foreshadowing:
            self.foreshadowing[fid].payoff_chapter = chapter
            self.foreshadowing[fid].payoff_description = payoff_description
            self.foreshadowing[fid].is_resolved = True
