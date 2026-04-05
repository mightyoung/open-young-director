"""PacingGovernor - Orchestrates narrative tension and flow across chapters.

Ensures the 'Narrative Heartbeat' remains healthy by balancing intense action
with necessary 'Breather' scenes, preventing reader fatigue.
"""

from typing import Any, List, Dict
from crewai.agent import Agent


class PacingGovernor:
    """Agent for adjusting chapter tone based on historical tension levels."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="叙事节奏指挥官",
            goal="通过分析历史张力，动态调整本章的写作基调，确保全书‘一张一弛’，节奏丝滑。",
            backstory="""你是一个经验丰富的金牌编剧。你深知观众的心理阈值。
            如果前三场戏都是大爆炸，第四场必须是静谧的谈心或伏笔的铺垫。
            你的任务是根据最近几章的张力数据，给本章下达明确的‘节奏指令’。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def calculate_adjustment(self, target_tension: int, pacing_state: Any) -> Dict[str, Any]:
        """Calculate tone adjustment based on pacing state.

        Args:
            target_tension: Original tension from outline (1-10)
            pacing_state: Current PacingState from Bible.

        Returns:
            Dict: {
                "adjusted_tension": int,
                "pacing_directive": str,
                "tone_instruction": str
            }
        """
        history = pacing_state.recent_tension_levels if pacing_state else []
        avg_tension = sum(history) / len(history) if history else 5
        
        prompt = f"""请作为节奏指挥官，为本章制定节奏策略。

【大纲预定张力】：{target_tension}/10
【最近5章张力历史】：{history} (平均: {avg_tension:.1f})

任务：
1. 如果历史张力持续处于 8 分以上，本章必须强制降压，无论大纲要求多少。
2. 如果连续低迷，本章必须注入冲突。
3. 制定具体的‘节奏补偿指令’。

请以 JSON 格式输出建议：
{{
    "adjusted_tension": 实际应执行的张力值,
    "pacing_directive": "BREATHER (喘息)/INTENSE (爆发)/BUILDUP (蓄势)",
    "tone_instruction": "给作者的具体基调建议（如：保持克制，描写日常中的暗流）"
}}
只返回 JSON。"""

        result = self.agent.kickoff(messages=prompt)
        # 解析逻辑（略）
        import json
        import re
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        
        return {
            "adjusted_tension": target_tension,
            "pacing_directive": "balanced",
            "tone_instruction": "保持自然叙事。"
        }
