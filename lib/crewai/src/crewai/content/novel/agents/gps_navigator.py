"""GPSNavigator - Tracks character locations and travel logic across chapters.

Ensures characters move logically through the world and aren't in two places
at once during parallel branch generation.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class GPSNavigator:
    """Agent for monitoring character movements and spatiotemporal consistency."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说时空导航员",
            goal="精准追踪每一个角色的地理位置和移动路径，杜绝‘瞬间移动’和‘量子叠加态’（同一时间在两地）。",
            backstory="""你拥有一个全息世界沙盘。你手里记录着每一个地点的距离和角色的移动能力。
            如果一个练气期小修士在没有法宝的情况下，一章之内横跨了两个大洲，
            你会立即标记为‘设定崩坏’。你是长篇巨著逻辑严密性的最后守护者。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def track_movements(self, chapter_content: str, chapter_num: int, current_gps: Any) -> Dict[str, Any]:
        """Identify where characters are and if they moved in this chapter."""
        
        gps_summary = str(current_gps) if current_gps else "所有角色初始位置未知"
        
        prompt = f"""请作为时空导航员，审视第 {chapter_num} 章中角色的物理位置变动。

【当前全图位置记录】：
{gps_summary}

【第 {chapter_num} 章内容】：
{chapter_content[:3000]}

任务：
1. 识别本章中出现的每一个角色及其所在的具体【地点】。
2. 检查是否有角色发生了位置迁移（从 A 地移动到 B 地）。
3. 评估移动逻辑：
   - 考虑到角色的修为和世界观设定，这种移动是否合理？
   - 是否存在‘瞬间移动’或‘时间线错乱’？

请以 JSON 格式输出位置更新：
{{
    "character_name": {{
        "new_location": "地点名",
        "action": "arrived/departed/staying",
        "consistency_warning": "如果有逻辑问题请说明，否则为空"
    }}
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
