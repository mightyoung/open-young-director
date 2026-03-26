"""Entity extractor for automatic entity extraction from text."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from crewai.content.memory.memory_types import Entity, Relationship


class EntityExtractor:
    """实体提取器

    从文本中自动提取实体及其关系。
    支持使用LLM进行智能提取，也支持基于规则的正则表达式提取。
    """

    DEFAULT_ENTITY_PATTERNS: Dict[str, str] = {
        "character": r"(?:人物|角色|主角|配角|男子|女子|少年|少女|老人|小孩)[\s\"\"'\"']([^\"\"'\"'\n]{2,20})",
        "item": r"(?:宝物|法器|武器|丹药|秘籍|功法|剑|刀|书|卷轴)[\s\"\"'\"']([^\"\"'\"'\n]{2,20})",
        "location": r"(?:地方|地点|城市|宗门|门派|山洞|宫殿|森林|河流|山脉)[\s\"\"'\"']([^\"\"'\"'\n]{2,20})",
        "faction": r"(?:门派|宗门|家族|势力|组织|帮派|王朝|帝国)[\s\"\"'\"']([^\"\"'\"'\n]{2,20})",
    }

    def __init__(
        self,
        llm: Optional[Any] = None,
        agent_callback: Optional[Callable[[str], str]] = None
    ) -> None:
        """初始化实体提取器

        Args:
            llm: LLM实例，用于智能提取
            agent_callback: Agent回调函数，用于替代直接LLM调用
        """
        self.llm = llm
        self.agent_callback = agent_callback
        self.entity_counter = 0

    def extract(self, text: str) -> List[Entity]:
        """从文本中提取实体

        如果配置了LLM或回调函数，则使用智能提取，
        否则使用基于规则的提取。

        Args:
            text: 输入文本

        Returns:
            提取的实体列表
        """
        if self.llm or self.agent_callback:
            return self._extract_with_llm(text)
        return self._extract_with_rules(text)

    def _extract_with_rules(self, text: str) -> List[Entity]:
        """使用正则表达式规则提取实体

        Args:
            text: 输入文本

        Returns:
            提取的实体列表
        """
        entities: List[Entity] = []
        seen_names: Dict[str, str] = {}  # name -> entity_id

        for entity_type, pattern in self.DEFAULT_ENTITY_PATTERNS.items():
            matches = re.finditer(pattern, text)
            for match in matches:
                name = match.group(1).strip()
                if not name or len(name) < 2:
                    continue

                # 避免重复
                if name in seen_names:
                    continue

                self.entity_counter += 1
                entity_id = f"entity_{self.entity_counter}"

                entity = Entity(
                    id=entity_id,
                    name=name,
                    type=entity_type,
                    description=f"从文本中提取的{entity_type}实体",
                    first_mentioned=match.group(0),
                )

                entities.append(entity)
                seen_names[name] = entity_id

        return entities

    def _extract_with_llm(self, text: str) -> List[Entity]:
        """使用LLM智能提取实体

        Args:
            text: 输入文本

        Returns:
            提取的实体列表
        """
        prompt = self._build_extraction_prompt(text)

        if self.agent_callback:
            result = self.agent_callback(prompt)
        else:
            result = self._call_llm(prompt)

        return self._parse_llm_response(result)

    def _build_extraction_prompt(self, text: str) -> str:
        """构建提取提示词

        Args:
            text: 输入文本

        Returns:
            提示词
        """
        return f"""请从以下文本中提取所有实体：

{text}

实体类型:
- character: 角色/人物
- item: 物品/法器/武器
- location: 地点/场所
- faction: 势力/组织
- concept: 概念/功法/技能

对于每个实体，请提供:
1. 名称
2. 类型
3. 简短描述
4. 主要属性（如适用）
5. 与其他实体的关系（如适用）
6. 别名（如适用）

请以JSON格式返回，结构如下：
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "character|item|location|faction|concept",
      "description": "简短描述",
      "properties": {{}},
      "relationships": [
        {{
          "target_name": "目标实体名称",
          "relation_type": "关系类型",
          "description": "关系描述"
        }}
      ],
      "aliases": ["别名1", "别名2"]
    }}
  ]
}}

只返回有效的JSON，不要有其他文字。"""

    def _call_llm(self, prompt: str) -> str:
        """调用LLM

        Args:
            prompt: 提示词

        Returns:
            LLM响应
        """
        if self.llm is None:
            return "{}"

        try:
            response = self.llm.call(prompt)
            return response
        except Exception:
            return "{}"

    def _parse_llm_response(self, response: str) -> List[Entity]:
        """解析LLM响应

        Args:
            response: LLM响应文本

        Returns:
            实体列表
        """
        try:
            # 尝试提取JSON
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return []

            data = json.loads(json_match.group(0))
            entities = []

            for entity_data in data.get("entities", []):
                self.entity_counter += 1
                entity_id = f"entity_{self.entity_counter}"

                # 解析关系
                relationships = []
                for rel_data in entity_data.get("relationships", []):
                    relationships.append(Relationship(
                        target_id=rel_data.get("target_name", ""),
                        relation_type=rel_data.get("relation_type", ""),
                        description=rel_data.get("description", ""),
                    ))

                entity = Entity(
                    id=entity_id,
                    name=entity_data.get("name", ""),
                    type=entity_data.get("type", "concept"),
                    description=entity_data.get("description", ""),
                    properties=entity_data.get("properties", {}),
                    relationships=relationships,
                    aliases=entity_data.get("aliases", []),
                )

                entities.append(entity)

            return entities

        except (json.JSONDecodeError, KeyError):
            return []

    def extract_from_texts(self, texts: List[str]) -> List[Entity]:
        """从多个文本中提取实体

        Args:
            texts: 文本列表

        Returns:
            去重后的实体列表
        """
        all_entities: Dict[str, Entity] = {}

        for text in texts:
            entities = self.extract(text)
            for entity in entities:
                # 基于名称去重
                if entity.name not in all_entities:
                    all_entities[entity.name] = entity

        return list(all_entities.values())

    def resolve_relationships(
        self,
        entities: List[Entity],
        entity_name_to_id: Dict[str, str]
    ) -> List[Entity]:
        """将关系中的目标名称解析为实体ID

        Args:
            entities: 实体列表
            entity_name_to_id: 名称到ID的映射

        Returns:
            更新关系后的实体列表
        """
        for entity in entities:
            for relationship in entity.relationships:
                target_name = relationship.target_id
                if target_name in entity_name_to_id:
                    relationship.target_id = entity_name_to_id[target_name]

        return entities


__all__ = ["EntityExtractor"]
