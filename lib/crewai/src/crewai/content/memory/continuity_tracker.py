"""Continuity tracker for maintaining story consistency."""

from __future__ import annotations

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

    def check_continuity(self, new_event: Event) -> list[ContinuityIssue]:
        """检查新事件是否与历史一致

        Args:
            new_event: 新事件

        Returns:
            连续性问题列表
        """
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

        # 2. 找到最近的状态
        last_state = history[-1]
        current_location = event.description  # 从事件描述推断当前位置

        # 3. 如果实体有已知位置，检查是否矛盾
        if last_state.location and current_location:
            # 如果两个位置不同，检查是否有转移关键词
            if last_state.location != current_location:
                # 检查事件描述是否包含位置转移关键词
                transfer_keywords = ["离开", "前往", "到达", "进入", "回到", "穿越", "传送"]
                for keyword in transfer_keywords:
                    if keyword in event.description:
                        return True  # 有转移，合理
                return False  # 无转移却位置改变 = 不一致

        return True

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContinuityTracker:
        """从字典导入"""
        tracker = cls()
        for event_data in data.get("events", []):
            event = Event.from_dict(event_data)
            tracker.add_event(event)
        return tracker


__all__ = ["ContinuityTracker"]
