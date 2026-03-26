"""Memory types for entity memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EntityType(Enum):
    """实体类型枚举"""
    CHARACTER = "character"  # 角色
    ITEM = "item"  # 物品/法器
    LOCATION = "location"  # 地点
    FACTION = "faction"  # 势力/组织
    CONCEPT = "concept"  # 概念/功法


class RelationType(Enum):
    """关系类型枚举"""
    FRIEND = "friend"  # 朋友
    ENEMY = "enemy"  # 敌人
    OWNER = "owner"  # 拥有者
    LOCATED_AT = "located_at"  # 位于
    MEMBER_OF = "member_of"  # 成员
    ALLIES = "allies"  # 同盟
    RIVAL = "rival"  # 竞争对手
    PARTNER = "partner"  # 合作伙伴
    PARENT = "parent"  # 父母
    CHILD = "child"  # 子女
    SIBLING = "sibling"  # 兄弟姐妹
    LOVE = "love"  # 爱情
    HATE = "hate"  # 仇恨
    SERVES = "serves"  # 效忠于
    POSSESSES = "possesses"  # 持有
    LOCATED_IN = "located_in"  # 所在


class ConsistencySeverity(Enum):
    """一致性严重程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Relationship:
    """实体关系"""
    target_id: str
    relation_type: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Relationship:
        """从字典创建"""
        return cls(
            target_id=data["target_id"],
            relation_type=data["relation_type"],
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Entity:
    """实体"""
    id: str
    name: str
    type: str  # EntityType value
    description: str
    properties: Dict[str, Any] = field(default_factory=dict)
    relationships: List[Relationship] = field(default_factory=list)
    first_mentioned: str = ""  # 首次出现的文本
    aliases: List[str] = field(default_factory=list)  # 别名/代称
    created_at: Optional[str] = None  # ISO timestamp

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "properties": self.properties,
            "relationships": [r.to_dict() for r in self.relationships],
            "first_mentioned": self.first_mentioned,
            "aliases": self.aliases,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Entity:
        """从字典创建"""
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            description=data["description"],
            properties=data.get("properties", {}),
            relationships=[
                Relationship.from_dict(r) for r in data.get("relationships", [])
            ],
            first_mentioned=data.get("first_mentioned", ""),
            aliases=data.get("aliases", []),
            created_at=data.get("created_at"),
        )

    def get_relationship(
        self,
        target_id: str
    ) -> Optional[Relationship]:
        """获取与指定实体的关系"""
        for rel in self.relationships:
            if rel.target_id == target_id:
                return rel
        return None

    def has_relationship_type(
        self,
        relation_type: str
    ) -> bool:
        """检查是否有指定类型的关系"""
        return any(rel.relation_type == relation_type for rel in self.relationships)


@dataclass
class ConsistencyIssue:
    """一致性问题"""
    entity_id: str
    property: str
    expected: Any
    actual: Any
    severity: str = ConsistencySeverity.HIGH.value
    description: str = ""
    chapter: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entity_id": self.entity_id,
            "property": self.property,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
            "description": self.description,
            "chapter": self.chapter,
        }


@dataclass
class Event:
    """事件"""
    id: str
    timestamp: str  # 故事内时间线
    description: str
    involved_entities: List[str] = field(default_factory=list)  # 涉及的实体ID列表
    consequences: List[str] = field(default_factory=list)  # 后续影响
    chapter: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "description": self.description,
            "involved_entities": self.involved_entities,
            "consequences": self.consequences,
            "chapter": self.chapter,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        """从字典创建"""
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            description=data["description"],
            involved_entities=data.get("involved_entities", []),
            consequences=data.get("consequences", []),
            chapter=data.get("chapter", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ContinuityIssue:
    """连续性问题"""
    event_id: str
    entity_id: str
    issue_type: str  # state_conflict, timeline_conflict, etc.
    description: str
    severity: str = ConsistencySeverity.MEDIUM.value
    chapter: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "entity_id": self.entity_id,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity,
            "chapter": self.chapter,
        }


@dataclass
class EntityState:
    """实体状态快照"""
    entity_id: str
    chapter: int
    properties: Dict[str, Any]
    location: Optional[str] = None
    status: str = "active"  # active, deceased, missing, unknown

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "entity_id": self.entity_id,
            "chapter": self.chapter,
            "properties": self.properties,
            "location": self.location,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EntityState:
        """从字典创建"""
        return cls(
            entity_id=data["entity_id"],
            chapter=data["chapter"],
            properties=data.get("properties", {}),
            location=data.get("location"),
            status=data.get("status", "active"),
        )


__all__ = [
    "EntityType",
    "RelationType",
    "ConsistencySeverity",
    "Relationship",
    "Entity",
    "ConsistencyIssue",
    "Event",
    "ContinuityIssue",
    "EntityState",
]
