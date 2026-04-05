"""TropeCrusher - Identifies and subverts overused web-novel clichés.

Takes a chapter outline and identifies predictable plot points, then forces 
a logic inversion or a narrative twist to maintain originality and 'God-tier' quality.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class TropeCrusher:
    """Agent for identifying and subverting predictable narrative patterns."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="网文套路粉碎机",
            goal="识别并彻底颠覆陈腐的小说桥段，将平庸的‘样板戏’升级为让人意想不到的神反转。",
            backstory="""你是一个阅片无数、读过千万本网文的资深主编。
            你对‘跳崖必捡宝’、‘临阵必突破’、‘反派必话多’等套路极度过敏。
            你的任务是盯着作者的大纲，凡是让你能猜到后续三章剧情的桥段，
            你都要粗暴地将其粉碎，并提出一个符合底层逻辑但完全超乎想象的新走向。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def subvert_outline(self, chapter_outline: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze an outline and force a subversion of at least one key event."""
        
        prompt = f"""请作为套路粉碎机，审视以下第 {chapter_outline.get('chapter_num')} 章的初步大纲。

【大纲内容】：
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

【前情提要】：
{context[:1000]}

任务：
1. 【识别毒点】：指出大纲中哪些地方落入了平庸的套路（样板戏化、降智化、可预测）。
2. 【逻辑反转】：选择其中一个最平庸的点进行‘底层反转’。
   - 要求：反转必须符合世界观和角色人设，而不是为了反转而反转。
   - 目标：让读者在大呼‘卧槽’的同时，又觉得‘这太合理了’。
3. 【修改大纲】：输出修改后的 `main_events` 和 `signature_specs`。

请以 JSON 格式输出建议：
{{
    "identified_cliches": ["套路1", "套路2"],
    "subversion_logic": "你是如何进行逻辑反转的说明",
    "updated_main_events": ["新事件1", "新事件2", "新事件3"],
    "updated_signature_specs": ["新奇观1", "新奇观2"]
}}
只返回 JSON。"""

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
