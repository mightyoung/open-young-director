"""Entity memory system for tracking entities and their relationships."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from crewai.content.memory.memory_types import (
    ConsistencyIssue,
    Entity,
    Relationship,
)

if TYPE_CHECKING:
    pass


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

        Args:
            entity_id: 实体ID

        Returns:
            实体被提及的历史记录列表
        """
        # 获取实体的所有关系变化
        entity = self.entities.get(entity_id)
        if not entity:
            return []

        history = []
        for rel in entity.relationships:
            history.append({
                "type": "relationship",
                "target_id": rel.target_id,
                "relation_type": rel.relation_type,
                "description": rel.description,
                "metadata": rel.metadata,
            })

        # 获取属性变化 (通过properties的历史记录)
        for key, value in entity.properties.items():
            history.append({
                "type": "property",
                "property": key,
                "value": value,
            })

        return history

    def merge_state(
        self,
        other: "EntityMemory",
        conflict_resolution: str = "latest"
    ) -> list[ConsistencyIssue]:
        """合并另一个EntityMemory的状态

        当两个EntityMemory有冲突时，根据策略解决:
        - "latest": 保留最新值
        - "keep_existing": 保留当前值
        - "merge": 合并冲突 (列表)

        Args:
            other: 要合并的EntityMemory
            conflict_resolution: 冲突解决策略

        Returns:
            解决的冲突列表
        """
        issues = []

        for entity_id, other_entity in other.entities.items():
            if entity_id not in self.entities:
                # 新实体，直接添加
                self.entities[entity_id] = other_entity
                self._update_index(other_entity)
                continue

            # 实体已存在，合并
            existing = self.entities[entity_id]
            conflicts = self._merge_entity(existing, other_entity, conflict_resolution)
            issues.extend(conflicts)

        return issues

    def _merge_entity(
        self,
        existing: Entity,
        incoming: Entity,
        resolution: str
    ) -> list[ConsistencyIssue]:
        """合并两个实体的状态"""
        issues = []

        # 合并属性
        for key, value in incoming.properties.items():
            if key in existing.properties:
                if existing.properties[key] != value:
                    if resolution == "latest":
                        existing.properties[key] = value
                    elif resolution == "merge" and isinstance(existing.properties[key], list):
                        existing.properties[key].append(value)
                    else:
                        issues.append(ConsistencyIssue(
                            entity_id=existing.id,
                            property=key,
                            expected=value,
                            actual=existing.properties[key],
                            severity="medium",
                            description=f"属性冲突: {key}"
                        ))
            else:
                existing.properties[key] = value

        # 合并关系 (去重)
        existing_rel_targets = {r.target_id for r in existing.relationships}
        for rel in incoming.relationships:
            if rel.target_id not in existing_rel_targets:
                existing.relationships.append(rel)

        return issues

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
            "entity_index": self.entity_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityMemory:
        """从字典导入"""
        memory = cls()
        for entity_data in data.get("entities", []):
            entity = Entity.from_dict(entity_data)
            memory.add_entity(entity)
        return memory

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
            memory = EntityMemory.from_dict(data)
            self.entities = memory.entities
            self.entity_index = memory.entity_index
            return True
        except Exception:
            return False

    def get_context_for_chapter(self, chapter: int) -> dict[str, Any]:
        """获取指定章节的上下文

        Args:
            chapter: 章节号

        Returns:
            包含该章节相关实体的上下文
        """
        # 获取该章节活跃的实体
        active_entities = []
        for entity in self.entities.values():
            # 实体的created_at应该在chapter之前
            if entity.created_at:
                active_entities.append(entity.to_dict())

        return {
            "chapter": chapter,
            "entities": active_entities,
            "entity_count": len(active_entities),
            "characters": [e.to_dict() for e in self.entities.values() if e.type == "character"],
            "locations": [e.to_dict() for e in self.entities.values() if e.type == "location"],
        }

    def extract_entities_from_text(
        self,
        text: str,
        llm: Any = None
    ) -> list[Entity]:
        """从文本中提取实体 (需要LLM支持)

        Args:
            text: 文本内容
            llm: LLM实例

        Returns:
            提取的实体列表
        """
        if llm is None:
            # 简单的正则匹配作为降级方案
            return self._extract_entities_regex(text)

        # TODO: 使用LLM进行实体提取
        # prompt = f"""从以下文本中提取实体，输出JSON格式:
        # {{"entities": [{{"name": "", "type": "", "description": ""}}]}}
        # 文本: {text}"""
        return []

    def _extract_entities_regex(self, text: str) -> list[Entity]:
        """使用正则表达式提取实体 (降级方案)"""
        import re
        entities = []

        # 简单的角色名提取 (中文名+常见姓氏)
        name_pattern = r'([A-Z][a-z]+|[\\u4e00-\\u9fa5]{2,4})(说|道|是|在|来|去)'
        names = re.findall(name_pattern, text)
        for name, _ in set(names):
            if len(name) >= 2:
                entities.append(Entity(
                    id=name,
                    name=name,
                    type="character",
                    description=f"从文本中提取的角色: {name}",
                ))

        return entities

    def integrate_with_unified_state(self, state: dict) -> None:
        """与UnifiedContentState集成

        从UnifiedContentState中提取实体并更新记忆。

        Args:
            state: UnifiedContentState字典
        """
        world_output = state.get("world_output", {})
        draft_output = state.get("draft_output", {})

        # 从world_output提取实体
        if "characters" in world_output:
            for char_data in world_output["characters"]:
                self.update_character(char_data.get("name", ""), char_data)

        if "locations" in world_output:
            for loc_data in world_output["locations"]:
                entity = Entity(
                    id=loc_data.get("name", ""),
                    name=loc_data.get("name", ""),
                    type="location",
                    description=loc_data.get("description", ""),
                    properties=loc_data.get("properties", {}),
                )
                self.add_entity(entity)

        # 从draft_output提取实体 (章节中提到的)
        chapters = draft_output.get("chapters", [])
        for chapter in chapters:
            if hasattr(chapter, 'entities'):
                for entity_data in chapter.entities:
                    self.update_character(entity_data.get("name", ""), entity_data)


__all__ = ["EntityMemory"]
