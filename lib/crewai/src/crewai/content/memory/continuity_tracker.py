"""Continuity tracker for maintaining story consistency."""

from __future__ import annotations

import re
from typing import Any

from crewai.content.memory.memory_types import (
    ContinuityIssue,
    EntityState,
    Event,
)


class ContinuityTracker:
    """连续性追踪器

    追踪已发生的剧情事件，检测连续性冲突，提供上下文记忆。
    """

    def __init__(self) -> None:
        self.events: list[Event] = []
        self.entity_states: dict[str, dict[str, Any]] = {}  # entity_id -> current_state
        self.entity_state_history: dict[str, list[EntityState]] = {}  # entity_id -> state history
        self.event_index: dict[str, list[int]] = {}  # entity_id -> event indices

    def add_event(self, event: Event) -> None:
        """添加事件

        Args:
            event: 要添加的事件
        """
        self.events.append(event)

        # 更新实体状态索引
        for entity_id in event.involved_entities:
            if entity_id not in self.event_index:
                self.event_index[entity_id] = []
            self.event_index[entity_id].append(len(self.events) - 1)

        # 更新实体当前状态
        for entity_id in event.involved_entities:
            if entity_id not in self.entity_states:
                self.entity_states[entity_id] = {}
            # 初始化实体状态历史
            if entity_id not in self.entity_state_history:
                self.entity_state_history[entity_id] = []

        # 记录状态快照
        self._snapshot_entity_states(event)

    def _snapshot_entity_states(self, event: Event) -> None:
        """为事件创建实体状态快照"""
        for entity_id in event.involved_entities:
            if entity_id in self.entity_states:
                state = EntityState(
                    entity_id=entity_id,
                    chapter=event.chapter,
                    properties=dict(self.entity_states[entity_id]),
                    location=self.entity_states[entity_id].get("location"),
                    status=self.entity_states[entity_id].get("status", "active"),
                )
                self.entity_state_history[entity_id].append(state)

    def check_continuity(self, new_event: Event, bible: Any = None) -> list[ContinuityIssue]:
        """检查新事件是否与历史一致"""
        issues = []

        for entity_id in new_event.involved_entities:
            if entity_id not in self.entity_states:
                continue

            current_state = self.entity_states[entity_id]

            # 检查位置连续性
            if "location" in current_state:
                if not self._is_location_consistent(entity_id, new_event):
                    issues.append(ContinuityIssue(
                        event_id=new_event.id,
                        entity_id=entity_id,
                        issue_type="timeline_conflict",
                        description=f"实体 {entity_id} 的位置在时间线上存在矛盾",
                        severity="medium",
                        chapter=new_event.chapter,
                    ))

            # 检查状态连续性
            if "status" in current_state:
                if current_state["status"] == "deceased" and self._entity_appears_in_event(entity_id, new_event):
                    issues.append(ContinuityIssue(
                        event_id=new_event.id,
                        entity_id=entity_id,
                        issue_type="state_conflict",
                        description=f"实体 {entity_id} 已死亡，不应出现在新事件中",
                        severity="high",
                        chapter=new_event.chapter,
                    ))

        # 新增：战力平衡检查
        if bible and bible.world_rules:
            issues.extend(self._check_power_balance(new_event, bible))

        return issues

    def _check_power_balance(self, event: Event, bible: Any) -> list[ContinuityIssue]:
        """检测战斗结果是否符合等级设定"""
        issues = []
        text = event.description.lower()
        world_rules = bible.world_rules

        # 简单启发式：寻找胜负词
        win_keywords = ["击败", "重创", "斩杀", "胜过", "压制"]
        for kw in win_keywords:
            if kw in text:
                # 尝试提取对战双方
                parts = text.split(kw)
                if len(parts) >= 2:
                    winner_text = parts[0]
                    loser_text = parts[1]
                    
                    # 匹配已知实体
                    winner = next((e for e in event.involved_entities if e in winner_text), None)
                    loser = next((e for e in event.involved_entities if e in loser_text), None)
                    
                    if winner and loser:
                        w_state = self.get_entity_state(winner)
                        l_state = self.get_entity_state(loser)
                        
                        w_level = w_state.get("cultivation_realm") or bible.characters.get(winner).cultivation_realm if winner in bible.characters else None
                        l_level = l_state.get("cultivation_realm") or bible.characters.get(loser).cultivation_realm if loser in bible.characters else None
                        
                        w_rank = world_rules.get_level_index(w_level) if w_level else -1
                        l_rank = world_rules.get_level_index(l_level) if l_level else -1
                        
                        # 如果败者等级显著高于胜者且无合理解释，记录问题
                        if l_rank > w_rank and (l_rank - w_rank) >= 2:
                            issues.append(ContinuityIssue(
                                event_id=event.id,
                                entity_id=winner,
                                issue_type="power_imbalance",
                                description=f"战力崩坏：{winner}({w_level}) 击败了等级远高于自己的 {loser}({l_level})，缺乏合理解释。",
                                severity="high",
                                chapter=event.chapter,
                            ))
        return issues

    def _is_location_consistent(self, entity_id: str, event: Event) -> bool:
        """检查位置是否一致

        如果实体在之前的章节出现在A地点，现在出现在B地点，
        且事件描述中没有"离开""前往"等转移关键词，则不一致。
        """
        # 1. 获取该实体最近的状态
        history = self.entity_state_history.get(entity_id, [])
        if not history:
            return True  # 首次出现，肯定一致

        # 2. 获取实体当前存储的位置
        last_state = history[-1]
        last_location = last_state.location

        # 3. 从事件描述中提取新位置
        new_location = self._extract_location_from_text(event.description)

        # 4. 如果实体有已知位置，检查是否矛盾
        if last_location and new_location:
            if last_location != new_location:
                # 位置改变，检查是否有转移关键词
                transfer_keywords = ["离开", "前往", "到达", "进入", "回到", "穿越", "传送", "来到", "去往"]
                for keyword in transfer_keywords:
                    if keyword in event.description:
                        return True  # 有转移关键词，合理
                return False  # 无转移却位置改变 = 不一致

        return True

    def _extract_location_from_text(self, text: str) -> str | None:
        """从文本中提取位置信息

        简单的启发式提取：查找常见的位置标记词后面的地名
        """
        if not text:
            return None

        # 常见位置标记模式
        patterns = [
            r"在([^，。,，]+)",
            r"来到?([^，。,，]+)",
            r"前往([^，。,，]+)",
            r"到达([^，。,，]+)",
            r"进入([^，。,，]+)",
            r"回到([^，。,，]+)",
            r"位于([^，。,，]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def _entity_appears_in_event(self, entity_id: str, event: Event) -> bool:
        """检查实体是否出现在事件中"""
        return entity_id in event.involved_entities

    def get_relevant_context(
        self,
        entity_id: str,
        current_chapter: int
    ) -> dict[str, Any]:
        """获取实体的相关上下文

        Args:
            entity_id: 实体ID
            current_chapter: 当前章节

        Returns:
            包含历史事件、当前状态和最后提及的字典
        """
        # 获取该实体在之前章节中的事件
        past_events = [
            e for e in self.events
            if entity_id in e.involved_entities and e.chapter < current_chapter
        ]

        # 获取最后提及
        last_mention = past_events[-1].description if past_events else None

        return {
            "past_events": past_events,
            "current_state": self.entity_states.get(entity_id, {}),
            "last_mention": last_mention,
            "state_history": self.entity_state_history.get(entity_id, []),
        }

    def get_entity_state_at_chapter(
        self,
        entity_id: str,
        chapter: int
    ) -> EntityState | None:
        """获取实体在特定章节的状态

        Args:
            entity_id: 实体ID
            chapter: 章节号

        Returns:
            实体状态，如果不存在则返回None
        """
        history = self.entity_state_history.get(entity_id, [])

        # 找到最接近但不超过指定章节的状态
        result = None
        for state in history:
            if state.chapter <= chapter:
                result = state
            else:
                break

        return result

    def update_entity_state(
        self,
        entity_id: str,
        state_updates: dict[str, Any]
    ) -> None:
        """更新实体状态

        Args:
            entity_id: 实体ID
            state_updates: 状态更新
        """
        if entity_id not in self.entity_states:
            self.entity_states[entity_id] = {}

        self.entity_states[entity_id].update(state_updates)

    def get_entity_state(self, entity_id: str) -> dict[str, Any]:
        """获取实体当前状态

        Args:
            entity_id: 实体ID

        Returns:
            实体状态字典
        """
        return self.entity_states.get(entity_id, {})

    def get_events_at_chapter(self, chapter: int) -> list[Event]:
        """获取指定章节的所有事件

        Args:
            chapter: 章节号

        Returns:
            事件列表
        """
        return [e for e in self.events if e.chapter == chapter]

    def get_events_involving_entity(self, entity_id: str) -> list[Event]:
        """获取涉及指定实体的所有事件

        Args:
            entity_id: 实体ID

        Returns:
            事件列表
        """
        indices = self.event_index.get(entity_id, [])
        return [self.events[i] for i in indices if i < len(self.events)]

    def get_entity_timeline(self, entity_id: str) -> list[Event]:
        """获取实体的完整时间线

        Args:
            entity_id: 实体ID

        Returns:
            按时间排序的事件列表
        """
        return self.get_events_involving_entity(entity_id)

    def add_consequence(
        self,
        event_id: str,
        consequence: str
    ) -> bool:
        """为事件添加后果

        Args:
            event_id: 事件ID
            consequence: 后果描述

        Returns:
            是否成功添加
        """
        for event in self.events:
            if event.id == event_id:
                event.consequences.append(consequence)
                return True
        return False

    def get_consequences(self, event_id: str) -> list[str]:
        """获取事件的后果

        Args:
            event_id: 事件ID

        Returns:
            后果列表
        """
        for event in self.events:
            if event.id == event_id:
                return event.consequences
        return []

    def get_total_events(self) -> int:
        """获取事件总数"""
        return len(self.events)

    def get_events_by_chapter_range(
        self,
        start_chapter: int,
        end_chapter: int
    ) -> list[Event]:
        """获取指定章节范围内的事件

        Args:
            start_chapter: 起始章节
            end_chapter: 结束章节

        Returns:
            事件列表
        """
        return [
            e for e in self.events
            if start_chapter <= e.chapter <= end_chapter
        ]

    def clear(self) -> None:
        """清空所有追踪数据"""
        self.events.clear()
        self.entity_states.clear()
        self.entity_state_history.clear()
        self.event_index.clear()

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "events": [e.to_dict() for e in self.events],
            "entity_states": self.entity_states,
            "entity_state_history": {
                k: [s.to_dict() for s in v]
                for k, v in self.entity_state_history.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityTracker:
        """从字典导入"""
        tracker = cls()
        for event_data in data.get("events", []):
            event = Event.from_dict(event_data)
            tracker.add_event(event)
        # 恢复entity_states
        tracker.entity_states = data.get("entity_states", {})
        # 恢复entity_state_history
        for entity_id, history_data in data.get("entity_state_history", {}).items():
            tracker.entity_state_history[entity_id] = [
                EntityState.from_dict(s) for s in history_data
            ]
        return tracker

    def save_checkpoint(self, path: str) -> None:
        """保存checkpoint到文件

        Args:
            path: 保存路径
        """
        import json
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2, default=str)

    def load_checkpoint(self, path: str) -> bool:
        """从文件加载checkpoint

        Args:
            path: checkpoint路径

        Returns:
            是否成功加载
        """
        import json
        from pathlib import Path

        if not Path(path).exists():
            return False

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tracker = ContinuityTracker.from_dict(data)
            self.events = tracker.events
            self.entity_states = tracker.entity_states
            self.entity_state_history = tracker.entity_state_history
            self.event_index = tracker.event_index
            return True
        except Exception:
            return False

    def get_plot_threads(self, chapter: int) -> dict[str, list[str]]:
        """获取当前章节的剧情线追踪

        返回未解决的悬念和伏笔。

        Args:
            chapter: 章节号

        Returns:
            包含 active_hooks, unresolved_conflicts, pending_reveals 的字典
        """
        # 获取本章之后的事件中涉及的实体
        future_events = [e for e in self.events if e.chapter > chapter]

        # 收集所有涉及的实体
        involved_entities = set()
        for event in future_events:
            involved_entities.update(event.involved_entities)

        return {
            "active_hooks": [],  # TODO: 需要从dianting_checker集成
            "unresolved_conflicts": [],  # TODO: 需要从dianting_checker集成
            "pending_reveals": [],  # TODO: 需要从dianting_checker集成
            "entities_in_play": list(involved_entities),
        }

    def validate_timeline(self) -> list[ContinuityIssue]:
        """验证整个时间线的连续性

        Returns:
            发现的所有连续性问题列表
        """
        issues = []

        for i, event in enumerate(self.events):
            # 检查事件顺序
            if i > 0:
                prev_event = self.events[i - 1]
                if event.chapter < prev_event.chapter:
                    issues.append(ContinuityIssue(
                        event_id=event.id,
                        entity_id="",
                        issue_type="timeline_conflict",
                        description=f"事件 {event.id} 的章节号 ({event.chapter}) 早于前一个事件 ({prev_event.chapter})",
                        severity="high",
                        chapter=event.chapter,
                    ))

            # 检查实体状态一致性
            event_issues = self.check_continuity(event)
            issues.extend(event_issues)

        return issues


__all__ = ["ContinuityTracker"]
