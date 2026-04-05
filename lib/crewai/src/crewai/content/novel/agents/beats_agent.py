"""BeatsAgent - Breaks down a chapter outline into granular narrative beats.

Inspired by NovelCrafter's 'Beats' system. This agent ensures each scene has 
precise instructions, preventing the LLM from skipping subtle character 
moments or rushing through pacing.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class BeatsAgent:
    """Agent for translating chapter outlines into actionable narrative beats."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="叙事节奏架构师",
            goal="将粗略的章节大纲拆解为极细颗粒度的‘叙事节奏点 (Beats)’，确保每一处情感转折和动作细节都有据可查。",
            backstory="""你是一个顶尖的电影编剧。你不仅看故事发生了什么，
            更在意故事‘怎么发生’。你会把一章的内容拆解为10-15个节拍，
            每一个节拍都包含了特定的动作、对话目标或感官焦点。
            你产出的 Beats 是后续写作 Agent 的绝对行动指南。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def generate_beats(self, chapter_outline: Dict[str, Any], context: str = "") -> List[str]:
        """Convert outline into a list of 10-15 granular beats."""
        
        prompt = f"""请作为叙事节奏架构师，将以下章节大纲拆解为‘叙事节奏点 (Beats)’。

【章节大纲】：
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

【背景前情】：
{context[:1000]}

任务要求：
1. 将本章拆解为 10-15 个具体的节拍。
2. 每个节拍应描述一个具体的：场景动作、对话重点、或心理转折。
3. 标注出本章大纲中的 ★Signature Specs 应在哪个节拍中进行特写。
4. 确保节拍之间逻辑连贯，一张一弛。

输出格式（JSON 列表）：
[
    "节拍1：描述...",
    "节拍2：描述...",
    "节拍3：【Signature Spec 特写】描述..."
]
只返回 JSON 列表。"""

        result = self.agent.kickoff(messages=prompt)
        return self._parse_json(result)

    def _parse_json(self, result: Any) -> List[str]:
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return []
        return []
