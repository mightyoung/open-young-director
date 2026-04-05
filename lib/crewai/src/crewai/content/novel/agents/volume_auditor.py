"""VolumeAuditor - Uses long-context LLMs to perform a total audit of a full volume.

Unlike incremental checkers, this agent reads the ENTIRE written volume at once
to identify deep logical inconsistencies, character drift, and plot holes 
that only become visible in the full narrative arc.
"""

from typing import Any, List, Dict
import logging
from crewai.agent import Agent

logger = logging.getLogger(__name__)


class VolumeAuditor:
    """Agent for deep, long-context narrative auditing."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="全书因果律监察长",
            goal="通过一次性审阅全卷内容，揪出跨度极大的逻辑漏洞、吃书行为和细微的人设崩坏，确保全书因果逻辑坚不可摧。",
            backstory="""你拥有‘全知视角’。你能一次性记住几十万字的细节。
            你不在意某章的错别字，你盯着的是：第10章主角受的伤在第50章是否还有余毒？
            第20章提到的伏笔在第80章回收时，细节是否严丝合缝？
            你是防止‘神作变烂尾’的最后一道逻辑防线。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def audit_full_volume(self, full_text: str, current_bible: Any) -> Dict[str, Any]:
        """Perform a total audit of the volume text against the Bible."""
        
        bible_facts = str(current_bible.world_rules) + str(current_bible.characters)
        
        prompt = f"""请作为监察长，执行全卷因果律深度审计。

【核心设定集 (Source of Truth)】：
{bible_facts[:5000]}

【全卷正文（全量输入）】：
{full_text}

审计任务：
1. 【跨章节吃书检测】：找出正文中与设定集或前文描述自相矛盾的地方（特别是跨度超过10章的细节）。
2. 【人设稳定性】：检测角色在长达一卷的跨度内，性格是否发生了无逻辑的突变。
3. 【伏笔空转】：找出那些在大纲中标记为‘已回收’但实际文字表现力不足、或逻辑不能自洽的伏笔。
4. 【数值崩坏】：检查修为、金钱、距离等数值在全卷中是否保持逻辑递进。

请输出审计报告（JSON）：
{{
    "total_health_score": 0-100,
    "critical_plot_holes": [
        {{"chapter": 10, "issue": "主角伤势消失过快", "fix_suggestion": "在11章开头增加服药描写"}}
    ],
    "character_consistency_report": "角色一致性评估",
    "retcon_directives": "如果需要修改已写好的章节，请给出具体的微调指令"
}}
只返回 JSON。"""

        # 注意：此处需要调用支持超长上下文的 LLM
        result = self.agent.kickoff(messages=prompt)
        return self._parse_json(result)

    def _parse_json(self, result: Any) -> Dict:
        import json
        import re
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return {}
        return {}
