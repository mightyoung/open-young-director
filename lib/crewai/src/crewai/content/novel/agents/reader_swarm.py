"""ReaderSwarm - Simulates a diverse group of readers to provide sentiment feedback.

Contains multiple sub-personas (LogicNut, EmotionalFan, ActionJunkie) to evaluate
chapter quality from different audience perspectives.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class ReaderSwarm:
    """Agent for simulating audience reaction and sentiment analysis."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说读者陪审团",
            goal="模拟不同类型的真实读者对章节内容进行点评，识别爽点和毒点，预测读者留存率。",
            backstory="""你代表了网文圈最典型的三类读者：
            1. 【老书虫】：对设定和逻辑极其严苛，一旦发现战力崩坏或吃书，立马弃书。
            2. 【感性萌妹】：关注角色之间的情感互动和人物魅力，追求糖分和刀子。
            3. 【爽点暴徒】：追求极致的节奏和打脸快感，不能忍受主角吃亏太久。
            你的任务是综合这三类人的意见，给出一个真实的情感反馈。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def evaluate_chapter(self, chapter_content: str, chapter_num: int) -> Dict[str, Any]:
        """Simulate reader reactions for a chapter."""
        
        prompt = f"""请作为读者陪审团，阅读第 {chapter_num} 章，并给出真实评价。

【章节正文】：
{chapter_content[:4000]}

请分别以‘老书虫’、‘感性萌妹’和‘爽点暴徒’的身份给出：
1. 吐槽或赞美的评论。
2. 留存倾向（是否会继续追读）。
3. 识别本章最成功的‘爽点’或最失败的‘毒点’。

请以 JSON 格式输出评估结果：
{{
    "chapter_num": {chapter_num},
    "average_score": 0.8,
    "feedbacks": [
        {{"persona": "老书虫", "comment": "逻辑还算自洽，但那个法宝的来源稍微有点生硬。", "sentiment": 0.6}},
        {{"persona": "感性萌妹", "comment": "啊啊啊林逸看苏瑶的那个眼神，磕到了！", "sentiment": 0.9}},
        {{"persona": "爽点暴徒", "comment": "打得好！早该收拾那个人了，节奏起飞！", "sentiment": 1.0}}
    ],
    "predicted_churn_rate": "5% (极低)",
    "highlight_moment": "两人对视的瞬间"
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
