"""参考骨架提取Agent - 从经典名著中提取故事骨架"""

from typing import TYPE_CHECKING, List, Optional
from dataclasses import dataclass

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class ReferenceSkeleton:
    """经典名著骨架

    用于存储从经典名著中提取的故事骨架结构，
    可作为网络小说规划的参考。
    """
    source: str                           # 名著名称 (如《西游记》)
    source_url: str                      # 参考来源 URL
    theme: str                            # 主题提炼
    backbone_plot: List[str]              # 主干情节列表
    character_archetypes: List[dict]      # 角色原型
    structure_pattern: str                # 结构模式 (如"取经模式")
    key_conflicts: List[str]              # 核心冲突
    growth_arc: str                       # 成长弧线
    style_elements: List[str]             # 风格元素

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "source_url": self.source_url,
            "theme": self.theme,
            "backbone_plot": self.backbone_plot,
            "character_archetypes": self.character_archetypes,
            "structure_pattern": self.structure_pattern,
            "key_conflicts": self.key_conflicts,
            "growth_arc": self.growth_arc,
            "style_elements": self.style_elements,
        }


class ReferenceAgent:
    """参考骨架提取Agent

    从经典名著中提取故事骨架，为网络小说创作提供参考。

    使用示例:
        agent = ReferenceAgent()
        skeleton = agent.extract_skeleton(
            topic="西游记主题",
            search_results=["搜索结果1", "搜索结果2"]
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化参考骨架提取Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="故事分析专家",
            goal="从经典名著中提取可复用的故事骨架",
            backstory="""你是一个出色的故事架构师，精通各种经典名著的结构分析。
            你擅长从复杂的故事情节中提取核心骨架，识别角色原型、叙事模式、
            主干冲突和成长弧线。你能够将经典故事抽象为可复用的结构模块。""",
            verbose=verbose,
            llm=llm,
        )

    def extract_skeleton(
        self,
        topic: str,
        style: str,
        search_results: List[str],
    ) -> ReferenceSkeleton:
        """从搜索结果中提取故事骨架

        Args:
            topic: 小说主题
            style: 小说风格
            search_results: 搜索结果列表

        Returns:
            ReferenceSkeleton: 提取的骨架
        """
        prompt = self._build_extraction_prompt(topic, style, search_results)
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _build_extraction_prompt(
        self,
        topic: str,
        style: str,
        search_results: List[str],
    ) -> str:
        """构建骨架提取提示词"""
        search_content = "\n\n".join([f"--- 结果{i+1} ---\n{r}" for i, r in enumerate(search_results)])

        return f"""你是一个故事分析专家。请根据以下搜索结果，分析并提取经典名著的故事骨架。

小说主题: {topic}
小说风格: {style}

搜索结果:
{search_content}

请从这些资料中提取以下结构：

1. **名著名称**: 这部经典作品的名称
2. **主题提炼**: 故事的核心主题是什么
3. **主干情节** (3-7个): 按顺序列出核心事件，这是故事的骨干
4. **角色原型**: 主要角色类型（如英雄、导师、挑战者等）
5. **结构模式**: 故事的整体结构（如英雄之旅、取经模式、复仇模式等）
6. **核心冲突**: 贯穿全书的主要矛盾
7. **成长弧线**: 主角或其他重要角色如何成长变化
8. **风格元素**: 体现该类型/风格的关键元素

请直接返回JSON格式，不要包含任何markdown标记（如```、###等）。只返回纯JSON对象：
{{
    "source": "《XXX》",
    "source_url": "参考来源URL（如果有）",
    "theme": "主题描述",
    "backbone_plot": ["主干情节1", "主干情节2", "主干情节3"],
    "character_archetypes": [
        {{"type": "主角类型", "description": "描述"}},
        {{"type": "配角类型", "description": "描述"}}
    ],
    "structure_pattern": "模式名称",
    "key_conflicts": ["冲突1", "冲突2"],
    "growth_arc": "成长弧线描述",
    "style_elements": ["风格元素1", "风格元素2"]
}}

如果搜索结果中没有足够的信息，请基于你的知识补充完整的故事骨架。"""

    def _parse_result(self, result) -> ReferenceSkeleton:
        """解析LLM输出为ReferenceSkeleton"""
        import json
        import re

        try:
            raw_text = ""
            if hasattr(result, "raw"):
                raw_text = result.raw
            elif isinstance(result, str):
                raw_text = result
            else:
                raw_text = str(result)

            # Remove markdown code block markers if present
            json_text = raw_text.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                start_idx = 1 if lines[0].strip().startswith("```") else 0
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().endswith("```"):
                        break
                json_text = "\n".join(lines[start_idx:i])

            json_text = json_text.strip()

            # Try to find JSON object
            json_match = re.search(r"\{[\s\S]*\}", json_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(json_text)

            return ReferenceSkeleton(
                source=data.get("source", "未知来源"),
                source_url=data.get("source_url", ""),
                theme=data.get("theme", ""),
                backbone_plot=data.get("backbone_plot", []),
                character_archetypes=data.get("character_archetypes", []),
                structure_pattern=data.get("structure_pattern", ""),
                key_conflicts=data.get("key_conflicts", []),
                growth_arc=data.get("growth_arc", ""),
                style_elements=data.get("style_elements", []),
            )

        except (json.JSONDecodeError, Exception) as e:
            # Fallback to empty skeleton
            return ReferenceSkeleton(
                source="提取失败",
                source_url="",
                theme="",
                backbone_plot=[],
                character_archetypes=[],
                structure_pattern="",
                key_conflicts=[],
                growth_arc="",
                style_elements=[],
            )
