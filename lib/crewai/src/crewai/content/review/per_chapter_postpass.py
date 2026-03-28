"""Per-Chapter PostPass - 每章生成后的一致性检查."""

from dataclasses import dataclass, field
from typing import Any

from crewai.content.review.chapter_snapshot import (
    ChapterSnapshot,
    CharacterSnapshot,
    GlobalStoryState,
    LocationSnapshot,
    TimelineEntry,
)


@dataclass
class ConsistencyIssue:
    """连续性问题"""
    issue_type: str  # CHARACTER_STATUS, LOCATION_CONFLICT, TIMELINE_JUMP, etc.
    description: str
    severity: str = "medium"  # high, medium, low
    chapter: int = 0
    character: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.issue_type,
            "description": self.description,
            "severity": self.severity,
            "chapter": self.chapter,
            "character": self.character,
        }


@dataclass
class PostPassResult:
    """PostPass 结果"""
    chapter: int
    issues: list[ConsistencyIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    snapshot: ChapterSnapshot | None = None

    @property
    def has_high_severity_issues(self) -> bool:
        return any(i.severity == "high" for i in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter": self.chapter,
            "issues": [i.to_dict() for i in self.issues],
            "warnings": self.warnings,
            "has_high_severity_issues": self.has_high_severity_issues,
        }


class PerChapterPostPass:
    """Per-Chapter PostPass 处理器

    在每章生成后执行一致性检查，并创建章节快照。
    """

    def __init__(self, story_state: GlobalStoryState | None = None):
        self.story_state = story_state or GlobalStoryState()

    def process(
        self,
        chapter_num: int,
        chapter_content: str,
        chapter_outline: dict | None = None,
    ) -> PostPassResult:
        """处理章节，执行 PostPass

        Args:
            chapter_num: 章节号
            chapter_content: 章节内容
            chapter_outline: 章节大纲（可选）

        Returns:
            PostPassResult: 检查结果和快照
        """
        result = PostPassResult(chapter=chapter_num)

        # 1. 提取本章快照
        snapshot = self._extract_snapshot(chapter_num, chapter_content, chapter_outline)
        result.snapshot = snapshot

        # 2. 运行一致性检查
        issues = self._run_consistency_checks(snapshot, chapter_content)
        result.issues.extend(issues)

        # 3. 检查伏笔
        self._check_foreshadowing(snapshot, chapter_content, result)

        # 4. 更新全局状态
        self.story_state.add_chapter_snapshot(snapshot)

        return result

    def _extract_snapshot(
        self,
        chapter_num: int,
        content: str,
        outline: dict | None = None,
    ) -> ChapterSnapshot:
        """从章节内容提取快照"""
        snapshot = ChapterSnapshot(chapter_num=chapter_num)

        # 提取角色出现
        characters = self._extract_characters(content)
        for char_name in characters:
            snapshot.character_states[char_name] = CharacterSnapshot(
                name=char_name,
                location=self._extract_location_for_character(content, char_name),
            )

        # 提取新角色
        snapshot.new_characters = [
            c for c in characters
            if c not in self.story_state.characters
        ]

        # 提取关键事件
        snapshot.key_events = self._extract_key_events(content)

        # 提取位置
        locations = self._extract_locations(content)
        for loc_name in locations:
            chars_here = [
                c for c, cs in snapshot.character_states.items()
                if cs.location == loc_name
            ]
            snapshot.location_states[loc_name] = LocationSnapshot(
                name=loc_name,
                characters_present=chars_here,
            )

        return snapshot

    def _extract_characters(self, content: str) -> list[str]:
        """从内容中提取角色名（简单实现）"""
        # 实际应该用 NER 或 LLM 来提取
        # 这里用简单的启发式方法
        import re
        # 查找常见角色标记模式
        patterns = [
            r"([A-Z][a-z]+)",  # 英文名
            r"([\u4e00-\u9fa5]{2,4})(?:说|道|问|答|笑|怒|惊|叹|想|是|在)",  # 中文名+动词
        ]
        names = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            names.update(matches)
        return list(names)[:20]  # 限制数量

    def _extract_location_for_character(self, content: str, char_name: str) -> str:
        """提取角色的位置"""
        # 简单的模式匹配
        import re
        patterns = [
            rf"{char_name}在([^，。,，]+)",
            rf"{char_name}来到?([^，。,，]+)",
            rf"{char_name}前往([^，。,，]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_locations(self, content: str) -> list[str]:
        """提取位置列表"""
        # 简单实现
        import re
        patterns = [
            r"在([^，。]{2,10})的",
            r"来到?([^，。]{2,10})的",
            r"前往([^，。]{2,10})的",
        ]
        locations = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            locations.update(matches)
        return list(locations)

    def _extract_key_events(self, content: str) -> list[str]:
        """提取关键事件"""
        # 取前5个句号分隔的句子作为关键事件候选
        sentences = content.split("。")
        return [s.strip()[:50] for s in sentences[:5] if len(s.strip()) > 10]

    def _run_consistency_checks(
        self,
        snapshot: ChapterSnapshot,
        content: str,
    ) -> list[ConsistencyIssue]:
        """运行一致性检查"""
        issues = []

        # 1. 角色状态检查
        for char_name, char_state in snapshot.character_states.items():
            if char_name in self.story_state.characters:
                prev_state = self.story_state.characters[char_name]

                # 生死状态检查
                if prev_state.status == "dead" and char_state.status != "dead":
                    issues.append(ConsistencyIssue(
                        issue_type="CHARACTER_STATUS_CONFLICT",
                        description=f"角色 '{char_name}' 之前已死亡，但本章重新出现",
                        severity="high",
                        chapter=snapshot.chapter_num,
                        character=char_name,
                    ))

                # 位置连续性检查
                if prev_state.location and char_state.location:
                    if prev_state.location != char_state.location:
                        # 检查是否有转移关键词
                        if not self._has_location_transfer(content, char_name):
                            issues.append(ConsistencyIssue(
                                issue_type="LOCATION_CONFLICT",
                                description=f"角色 '{char_name}' 从 '{prev_state.location}' 突然转移到了 '{char_state.location}'，缺少过渡描述",
                                severity="medium",
                                chapter=snapshot.chapter_num,
                                character=char_name,
                            ))

        return issues

    def _has_location_transfer(self, content: str, char_name: str) -> bool:
        """检查内容中是否有该角色的位置转移描述"""
        import re
        transfer_keywords = ["离开", "前往", "到达", "进入", "回到", "穿越", "传送", "来到", "去往"]
        for keyword in transfer_keywords:
            if keyword in content:
                return True
        return False

    def _check_foreshadowing(
        self,
        snapshot: ChapterSnapshot,
        content: str,
        result: PostPassResult,
    ) -> None:
        """检查伏笔埋设和回收"""
        # 检查是否有伏笔回收
        for fid, entry in self.story_state.foreshadowing.items():
            if not entry.is_resolved:
                # 检查内容是否暗示了伏笔被回收
                if any(word in content for word in ["原来", "正如", "正如", "果然", "才明白"]):
                    if entry.description[:20] in content:
                        result.warnings.append(
                            f"伏笔可能在第{entry.planted_chapter}章埋下，在本章回收"
                        )
