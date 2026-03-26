"""访谈环节Agent"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class InterviewAgent:
    """播客访谈环节Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客访谈策划专家",
            goal="设计有深度有温度的访谈内容",
            backstory="你是一位资深播客主持人，擅长通过精心设计的问题引导嘉宾分享真实故事，让听众获得启发和共鸣。",
            llm=llm,
            verbose=True,
        )

    def generate_interview(
        self,
        topic: str,
        guest_name: str,
        guest_background: str,
        target_duration_minutes: float = 15.0,
    ) -> dict:
        """
        生成访谈环节内容

        Args:
            topic: 播客主题
            guest_name: 嘉宾姓名
            guest_background: 嘉宾背景介绍
            target_duration_minutes: 目标时长（分钟）

        Returns:
            dict: 包含嘉宾介绍、问题列表、讨论要点的字典
        """
        target_words = int(target_duration_minutes * 150)

        prompt = f"""为播客主题'{topic}'设计访谈环节。

嘉宾姓名: {guest_name}
嘉宾背景: {guest_background}
目标时长: {target_duration_minutes}分钟

请提供:
1. 嘉宾开场介绍 - 吸引听众的嘉宾简介
2. 访谈问题列表 - 4-6个有深度的问题
3. 讨论要点 - 每个问题预期的讨论方向
4. 访谈收尾 - 总结和感谢

请用JSON格式返回:
{{
    "guest_intro": "嘉宾开场介绍，约100字",
    "questions": ["问题1", "问题2", "问题3", "问题4"],
    "talking_points": [
        {{"question": "问题1", "points": ["讨论方向1", "讨论方向2"]}},
        {{"question": "问题2", "points": ["讨论方向1", "讨论方向2"]}}
    ],
    "conclusion": "访谈收尾语，约60字"
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result)

    def _parse_result(self, result) -> dict:
        """解析LLM输出"""
        import json

        try:
            if hasattr(result, "raw"):
                return json.loads(result.raw)
            elif isinstance(result, str):
                return json.loads(result)
            else:
                return json.loads(str(result))
        except json.JSONDecodeError:
            return {
                "guest_intro": f"欢迎{guest_name}",
                "questions": ["请介绍一下自己", "对这个话题的看法是什么"],
                "talking_points": [],
                "conclusion": "感谢分享",
            }
