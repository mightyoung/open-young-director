"""开场介绍Agent"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class IntroAgent:
    """播客开场介绍Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客开场主持专家",
            goal="创作吸引人的播客开场介绍",
            backstory="你是一位经验丰富的播客主持人，擅长用简洁有力的开场白吸引听众，让观众立刻想要继续收听。",
            llm=llm,
            verbose=True,
        )

    def generate_intro(
        self,
        topic: str,
        hosts: int,
        hosts_names: list[str] = None,
        format_type: str = "narrative",
    ) -> dict:
        """
        生成开场介绍

        Args:
            topic: 播客主题
            hosts: 主持人数量
            hosts_names: 主持人名字列表
            format_type: 播客格式 (interview, narrative, panel, solo)

        Returns:
            dict: 包含开场白、主持人介绍的字典
        """
        names_str = ", ".join(hosts_names) if hosts_names else f"{hosts}位主持人"
        names_prompt = (
            f"主持人: {names_str}"
            if hosts_names
            else f"本期有{hosts}位主持人参与讨论"
        )

        prompt = f"""为播客节目生成开场介绍。

主题: {topic}
{names_prompt}
格式类型: {format_type}

请提供:
1. 开场白 - 吸引听众继续收听的开场语句
2. 主持人介绍 - 简短的主持人背景介绍
3. 节目预告 - 本期内容的简要预览

请用JSON格式返回:
{{
    "opening_statement": "开场白内容，约50字",
    "host_introductions": "主持人介绍内容，约80字",
    "episode_preview": "节目预告内容，约60字"
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
                "opening_statement": "欢迎收听本期节目",
                "host_introductions": "今天我们来深入探讨这个话题",
                "episode_preview": "精彩内容即将开始",
            }
