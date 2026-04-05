"""RelationshipEvolver - Tracks and quantifies emotional bonds between characters.

Analyzes dialogue, subtext, and actions to update the 'Emotional Value' and 
'Relationship State' in the Production Bible.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class RelationshipEvolver:
    """Agent for tracking emotional arcs and relationship dynamics."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说情感曲线分析师",
            goal="通过分析角色互动，实时量化其情感羁绊的升温或降温，确保人物关系演进自然合理。",
            backstory="""你是一个洞察人性的心理学家和文学评论家。
            你不仅看角色说了什么，更看他们没说什么。
            如果一对宿敌在本章展现出了英雄相惜的苗头，
            你会敏锐地捕捉到这种‘关系值’的微妙上升。
            你负责维护一份动态的情感地图，防止角色关系出现无理由的断层。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def extract_relationship_updates(self, chapter_content: str, current_bible: Any) -> Dict[str, Any]:
        """Analyze chapter and propose updates to character relationships.

        Returns:
            Dict: {
                "char_a": {
                    "char_b": {
                        "value_delta": int,
                        "new_bond_type": str,
                        "interaction_summary": str
                    }
                }
            }
        """
        # Get active characters to reduce LLM scope
        chars = list(current_bible.characters.keys())
        
        prompt = f"""请作为情感曲线分析师，评估以下章节中角色关系的变化。

【已知角色列表】：{", ".join(chars)}

【章节内容（采样核心互动）】：
{chapter_content[:4000]}

任务：
1. 识别文中发生实质互动的角色对。
2. 评估情感值变化（Emotional Value Delta）：
   - 范围：-20 (关系剧烈恶化) 到 +20 (关系剧烈升温)。
   - 依据：对白张力、牺牲行为、信任交付、背叛暗示等。
3. 总结本次互动的核心性质（Interaction Summary）。
4. 检查是否触发了‘关系定性’的转变（如：从‘熟人’变成‘生死之交’）。

请以 JSON 格式输出更新（仅输出有变化的对）：
{{
    "char_name_1": {{
        "char_name_2": {{
            "value_delta": 5,
            "interaction_summary": "在遗迹中并肩作战，产生了初步的信任。",
            "new_bond_type": "战友"
        }}
    }}
}}
只返回合法 JSON。"""

        result = self.agent.kickoff(messages=prompt)
        return self._parse_json(result)

    def _parse_json(self, result: Any) -> Dict:
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return {}
        return {}
