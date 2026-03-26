"""世界观构建器"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

from crewai.content.outline.outline_types import WorldOutput, Faction, Location, PowerSystem

if TYPE_CHECKING:
    from crewai.llm import LLM


class WorldBuilder:
    """世界观构建Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="世界观构建专家",
            goal="创建完整、一致、有深度的故事世界观",
            backstory="你是一个富有想象力的世界构建专家，擅长创建独特的幻想世界。",
            llm=llm,
        )

    def build(self, theme: str, style: str) -> WorldOutput:
        """
        构建世界观

        Args:
            theme: 故事主题
            style: 小说风格 (xianxia, doushi, etc.)

        Returns:
            WorldOutput: 完整的世界观
        """
        prompt = f"""
请为以下主题构建完整的世界观：

主题: {theme}
风格: {style}

请构建:
1. 世界/位面名称和概述
2. 主要势力(至少3个)及关系
3. 关键地点(至少5个)
4. 力量体系(修炼等级等)
5. 主要冲突核心

确保各元素之间逻辑自洽。

请用以下JSON格式返回：
{{
    "name": "世界名称",
    "description": "世界概述",
    "main_conflict": "主要冲突",
    "factions": [
        {{
            "name": "势力名",
            "description": "势力描述",
            "goals": ["目标1", "目标2"],
            "allies": ["盟友势力"],
            "enemies": ["敌对势力"]
        }}
    ],
    "key_locations": [
        {{
            "name": "地点名",
            "description": "地点描述",
            "significance": "重要意义"
        }}
    ],
    "power_system": {{
        "name": "力量体系名称",
        "levels": ["等级1", "等级2"],
        "special_abilities": ["特殊能力"]
    }}
}}
"""
        result = self.agent.run(prompt)
        return self._parse_output(result)

    def _parse_output(self, result) -> WorldOutput:
        """解析LLM输出为WorldOutput"""
        import json

        try:
            if hasattr(result, "raw"):
                data = json.loads(result.raw)
            elif isinstance(result, str):
                data = json.loads(result)
            else:
                data = json.loads(str(result))
        except json.JSONDecodeError:
            # Fallback to default
            return WorldOutput(
                name="默认世界",
                description="一个神秘的世界",
                main_conflict="待定",
                factions=[],
                key_locations=[],
                power_system=None,
            )

        factions = [
            Faction(
                name=f.get("name", ""),
                description=f.get("description", ""),
                goals=f.get("goals", []),
                allies=f.get("allies", []),
                enemies=f.get("enemies", []),
            )
            for f in data.get("factions", [])
        ]

        locations = [
            Location(
                name=l.get("name", ""),
                description=l.get("description", ""),
                significance=l.get("significance", ""),
            )
            for l in data.get("key_locations", [])
        ]

        power_data = data.get("power_system")
        power_system = None
        if power_data:
            power_system = PowerSystem(
                name=power_data.get("name", ""),
                levels=power_data.get("levels", []),
                special_abilities=power_data.get("special_abilities", []),
            )

        return WorldOutput(
            name=data.get("name", "未知世界"),
            description=data.get("description", ""),
            main_conflict=data.get("main_conflict", ""),
            factions=factions,
            key_locations=locations,
            power_system=power_system,
        )
