"""预热环节Agent"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class PreShowAgent:
    """播客预热环节Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客策划专家",
            goal="设计吸引听众的开场预热内容",
            backstory="你是一位资深播客制作人，擅长在开头抓住听众注意力，通过热点话题和有趣的问题迅速建立听众期待。",
            llm=llm,
            verbose=True,
        )

    def generate_preshow(
        self,
        topic: str,
        hosts: int,
        target_audience: str = "普通听众",
    ) -> dict:
        """
        生成预热内容

        Args:
            topic: 播客主题
            hosts: 主持人数量
            target_audience: 目标受众

        Returns:
            dict: 包含热点话题引入、期待值建立、节目背景的字典
        """
        prompt = f"""为播客主题'{topic}'生成预热内容。

主持人数量: {hosts}
目标受众: {target_audience}

请提供:
1. 热点话题引入 - 一个与主题相关的当前热点问题
2. 听众期待值建立 - 3个听众会喜欢的亮点预告
3. 节目背景介绍 - 简要说明本期节目内容

请用JSON格式返回:
{{
    "hot_topic_intro": "热点话题引入内容",
    "audience_expectations": ["期待1", "期待2", "期待3"],
    "show_background": "节目背景介绍"
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
                "hot_topic_intro": "正在讨论一个有趣的话题",
                "audience_expectations": ["精彩内容即将呈现"],
                "show_background": "本期节目将深入探讨该主题",
            }
