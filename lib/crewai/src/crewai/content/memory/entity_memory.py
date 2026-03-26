"""Entity memory system for tracking entities and their relationships."""

from __future__ import annotations

from typing import Any

from crewai.content.memory.memory_types import (
    ConsistencyIssue,
    Entity,
    Relationship,
)


class EntityMemory:
    """实体记忆系统

    存储角色、物品、地点等实体信息，支持实体关系追踪和一致性检查。
    """

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.entity_index: dict[str, list[str]] = {}  # name/alias -> entity_ids

    def add_entity(self, entity: Entity) -> None:
        """添加实体

        Args:
            entity: 要添加的实体
        """
        self.entities[entity.id] = entity
        self._update_index(entity)

    def _update_index(self, entity: Entity) -> None:
        """更新实体索引"""
        # 索引主名称
        if entity.name not in self.entity_index:
            self.entity_index[entity.name] = []
        if entity.id not in self.entity_index[entity.name]:
            self.entity_index[entity.name].append(entity.id)

        # 索引别名
        for alias in entity.aliases:
            if alias not in self.entity_index:
                self.entity_index[alias] = []
            if entity.id not in self.entity_index[alias]:
                self.entity_index[alias].append(entity.id)

    def get_entity(self, name_or_id: str) -> Entity | None:
        """获取实体

        Args:
            name_or_id: 实体名称或ID

        Returns:
            实体对象，如果未找到则返回None
        """
        # 直接通过ID查找
        if name_or_id in self.entities:
            return self.entities[name_or_id]

        # 通过名称/别名查找
        ids = self.entity_index.get(name_or_id, [])
        if ids:
            return self.entities.get(ids[0])

        return None

    def get_entity_by_id(self, entity_id: str) -> Entity | None:
        """通过ID获取实体

        Args:
            entity_id: 实体ID

        Returns:
            实体对象，如果未找到则返回None
        """
        return self.entities.get(entity_id)

    def get_all_entities(self) -> list[Entity]:
        """获取所有实体"""
        return list(self.entities.values())

    def get_entities_by_type(self, entity_type: str) -> list[Entity]:
        """获取指定类型的所有实体

        Args:
            entity_type: 实体类型 (character, item, location, faction, concept)

        Returns:
            该类型的所有实体
        """
        return [
            entity for entity in self.entities.values()
            if entity.type == entity_type
        ]

    def get_related_entities(
        self,
        entity_id: str,
        relation_type: str | None = None
    ) -> list[Entity]:
        """获取相关实体

        Args:
            entity_id: 实体ID
            relation_type: 关系类型过滤 (可选)

        Returns:
            相关的实体列表
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return []

        related = []
        for rel in entity.relationships:
            if relation_type is None or rel.relation_type == relation_type:
                target = self.entities.get(rel.target_id)
                if target:
                    related.append(target)

        return related

    def add_relationship(
        self,
        source_id: str,
        relationship: Relationship
    ) -> bool:
        """添加关系

        Args:
            source_id: 源实体ID
            relationship: 要添加的关系

        Returns:
            是否成功添加
        """
        entity = self.entities.get(source_id)
        if not entity:
            return False

        entity.relationships.append(relationship)
        return True

    def remove_relationship(
        self,
        source_id: str,
        target_id: str
    ) -> bool:
        """移除关系

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID

        Returns:
            是否成功移除
        """
        entity = self.entities.get(source_id)
        if not entity:
            return False

        original_len = len(entity.relationships)
        entity.relationships = [
            r for r in entity.relationships if r.target_id != target_id
        ]
        return len(entity.relationships) < original_len

    def update_entity_property(
        self,
        entity_id: str,
        key: str,
        value: Any
    ) -> bool:
        """更新实体属性

        Args:
            entity_id: 实体ID
            key: 属性名
            value: 属性值

        Returns:
            是否成功更新
        """
        entity = self.entities.get(entity_id)
        if not entity:
            return False

        entity.properties[key] = value
        return True

    def check_consistency(
        self,
        new_text: str,
        entity_state: dict[str, Any]
    ) -> list[ConsistencyIssue]:
        """检查新内容与已有实体状态的一致性

        Args:
            new_text: 新文本内容
            entity_state: 预期的实体状态 {entity_id: {property: value}}

        Returns:
            一致性问题列表
        """
        issues = []
        for entity_id, expected_state in entity_state.items():
            entity = self.entities.get(entity_id)
            if not entity:
                continue

            # 检查属性冲突
            for prop, value in expected_state.items():
                if prop in entity.properties:
                    if entity.properties[prop] != value:
                        issues.append(ConsistencyIssue(
                            entity_id=entity_id,
                            property=prop,
                            expected=value,
                            actual=entity.properties[prop],
                            severity="high",
                            description=f"属性 {prop} 在实体 {entity.name} 中存在冲突"
                        ))

        return issues

    def get_entity_history(self, entity_id: str) -> list[dict[str, Any]]:
        """获取实体的历史记录

        这个方法的实现依赖于ContextMemory模块，
        目前返回空列表作为占位符。

        Args:
            entity_id: 实体ID

        Returns:
            实体被提及的历史记录列表
        """
        # TODO: 集成 ContextMemory 获取历史记录
        return []

    def search_entities(self, query: str) -> list[Entity]:
        """搜索实体

        Args:
            query: 搜索查询 (匹配名称、别名或描述)

        Returns:
            匹配的实体列表
        """
        query_lower = query.lower()
        results = []

        for entity in self.entities.values():
            # 匹配名称
            if query_lower in entity.name.lower():
                results.append(entity)
                continue

            # 匹配别名
            if any(query_lower in alias.lower() for alias in entity.aliases):
                results.append(entity)
                continue

            # 匹配描述
            if query_lower in entity.description.lower():
                results.append(entity)

        return results

    def get_entity_count(self) -> int:
        """获取实体总数"""
        return len(self.entities)

    def get_entity_count_by_type(self) -> dict[str, int]:
        """获取各类型实体数量"""
        counts: dict[str, int] = {}
        for entity in self.entities.values():
            counts[entity.type] = counts.get(entity.type, 0) + 1
        return counts

    def update_character(self, name: str, state: dict[str, Any]) -> Entity:
        """Update or create a character entity with state.

        Args:
            name: Character name
            state: Dict with keys like 'realm', 'status', 'location', 'description', etc.

        Returns:
            The updated or created Entity
        """
        entity = self.get_entity(name)

        if entity is None:
            # Create new character entity
            description = state.get("description", f"角色{name}")
            entity = Entity(
                id=name,
                name=name,
                type="character",
                description=description,
            )
            self.add_entity(entity)

        # Update all properties from state
        for key, value in state.items():
            self.update_entity_property(entity.id, key, value)

        return entity

    def remove_entity(self, entity_id: str) -> bool:
        """移除实体

        Args:
            entity_id: 实体ID

        Returns:
            是否成功移除
        """
        if entity_id not in self.entities:
            return False

        entity = self.entities[entity_id]

        # 从索引中移除
        for name in [entity.name] + entity.aliases:
            if name in self.entity_index:
                self.entity_index[name] = [
                    eid for eid in self.entity_index[name] if eid != entity_id
                ]
                if not self.entity_index[name]:
                    del self.entity_index[name]

        # 移除该实体相关的所有关系
        for other_entity in self.entities.values():
            other_entity.relationships = [
                r for r in other_entity.relationships if r.target_id != entity_id
            ]

        # 移除实体
        del self.entities[entity_id]
        return True

    def clear(self) -> None:
        """清空所有实体"""
        self.entities.clear()
        self.entity_index.clear()

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "entities": [e.to_dict() for e in self.entities.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityMemory:
        """从字典导入"""
        memory = cls()
        for entity_data in data.get("entities", []):
            entity = Entity.from_dict(entity_data)
            memory.add_entity(entity)
        return memory


__all__ = ["EntityMemory"]
