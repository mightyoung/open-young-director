"""DestinyRewriter - Performs macro-level plot optimization based on cumulative reader sentiment.

Operates at the Volume level. It can prune boring sub-plots, elevate popular 
'Seed Details' into major plot points, and rewrite future volume outlines
to maximize predicted audience engagement.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class DestinyRewriter:
    """Agent for macro-level narrative optimization and retconning."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说宏观命运重构师",
            goal="根据读者的实时反馈，动态修正尚未写作的后续剧情，斩断无聊支线，升格高燃伏笔，确保全书走向神作。",
            backstory="""你是一个拥有‘因果律剪刀’的顶级编剧总监。
            你从不拘泥于原始大纲。如果第一卷数据显示读者对某个配角极度反感，
            你会毫不犹豫地在第二卷让他领便当；如果某个随口一提的细节让读者疯狂讨论，
            你会立即修改未来的大纲，将其变成全书的核心神转折。
            你追求的是商业成功与文学逻辑的完美统一。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def optimize_future_path(self, current_bible: Any, future_volumes: List[Dict]) -> List[Dict]:
        """Analyze past sentiments and seeds to rewrite future volume plans."""
        
        # 提取过往反馈和即兴种子
        sentiment_summary = str(current_bible.reader_sentiments[-20:]) # 最近20章
        active_seeds = [s.description for s in current_bible.seeds_registry if not s.is_used]
        
        prompt = f"""请作为命运重构师，审视小说未来的走向并进行‘神级优化’。

【近期读者反馈摘要】：
{sentiment_summary}

【可用即兴伏笔种子】：
{active_seeds}

【原定后续分卷大纲】：
{json.dumps(future_volumes, ensure_ascii=False, indent=2)}

任务：
1. 【斩断与合并】：识别反馈不佳的剧情线，提出如何在接下来的分卷中将其快速收束或删除。
2. 【伏笔升格】：挑选 1-2 个‘即兴种子’，将其强行植入未来卷的大纲中，作为关键转折。
3. 【重塑节奏】：如果读者感到疲劳，调整未来卷的‘高潮分布’。

请输出优化后的后续分卷大纲（保持 JSON 结构）：
{{
    "optimization_logic": "说明你为何做此重大修改",
    "updated_volumes": [...]
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
