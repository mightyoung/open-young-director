"""结尾总结Agent"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutroAgent:
    """播客结尾总结Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客结尾策划专家",
            goal="创作令人印象深刻的结尾总结",
            backstory="你是一位资深播客制作人，擅长用精炼的总结让听众回顾本期精华，并留下深刻印象和期待。",
            llm=llm,
            verbose=True,
        )

    def generate_outro(
        self,
        topic: str,
        key_takeaways: list[str],
        hosts_names: list[str] = None,
        call_to_action: str = "欢迎订阅和评论",
    ) -> dict:
        """
        生成播客结尾

        Args:
            topic: 播客主题
            key_takeaways: 本期关键要点列表
            hosts_names: 主持人名字列表
            call_to_action: 行动号召

        Returns:
            dict: 包含总结、预告、收尾语的字典
        """
        takeaways_str = "\n".join(f"- {t}" for t in key_takeaways)
        names_str = ", ".join(hosts_names) if hosts_names else "主持人"

        prompt = f"""为播客节目生成结尾总结。

主题: {topic}
关键要点:
{takeaways_str}
主持人: {names_str}

请提供:
1. 本期精华总结 - 3个最重要的收获
2. 下期预告（可选）- 简短的下一期内容预告
3. 收尾语 - 感谢听众的话语
4. 社交媒体互动 - 鼓励听众互动的方式

请用JSON格式返回:
{{
    "key_summary": ["总结1", "总结2", "总结3"],
    "next_episode_preview": "下期预告内容（可选）",
    "closing_statement": "收尾语",
    "social_media_prompt": "社交媒体互动语"
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
                "key_summary": ["本期精彩内容回顾"],
                "next_episode_preview": "",
                "closing_statement": "感谢收听",
                "social_media_prompt": "欢迎在评论区留言",
            }
