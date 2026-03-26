"""广告口播Agent"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class AdReadAgent:
    """播客广告口播Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="广告文案策划专家",
            goal="创作自然流畅的广告口播内容",
            backstory="你是一位经验丰富的广告文案专家，擅长将广告内容自然地融入播客，让听众不会感到突兀，同时有效传达品牌信息。",
            llm=llm,
            verbose=True,
        )

    def generate_ad_read(
        self,
        sponsor_name: str,
        sponsor_description: str,
        ad_type: str = "mid_roll",
        target_duration_seconds: int = 60,
    ) -> dict:
        """
        生成广告口播内容

        Args:
            sponsor_name: 赞助商名称
            sponsor_description: 赞助商描述/产品介绍
            ad_type: 广告位置 (pre_roll, mid_roll, post_roll)
            target_duration_seconds: 目标时长（秒）

        Returns:
            dict: 包含广告脚本、时长的字典
        """
        # 约150字/分钟
        target_words = int(target_duration_seconds / 60 * 150)

        prompt = f"""为赞助商生成广告口播内容。

赞助商名称: {sponsor_name}
赞助商/产品描述: {sponsor_description}
广告位置: {ad_type}
目标时长: {target_duration_seconds}秒（约{target_words}字）

请提供:
1. 广告口播脚本 - 自然流畅，适合口语表达
2. 行动号召 - 鼓励听众行动的语句
3. 优惠码或链接提示（可选）

请用JSON格式返回:
{{
    "sponsor_name": "{sponsor_name}",
    "script": "广告口播脚本内容",
    "call_to_action": "行动号召",
    "duration_seconds": {target_duration_seconds},
    "placement": "{ad_type}"
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result, sponsor_name, ad_type, target_duration_seconds)

    def generate_multiple_ads(
        self,
        sponsors: list[dict],
    ) -> list[dict]:
        """
        生成多个广告口播

        Args:
            sponsors: 赞助商列表，每个元素包含name, description, type, duration

        Returns:
            list[dict]: 广告口播列表
        """
        ads = []
        for sponsor in sponsors:
            ad = self.generate_ad_read(
                sponsor_name=sponsor.get("name", "赞助商"),
                sponsor_description=sponsor.get("description", ""),
                ad_type=sponsor.get("type", "mid_roll"),
                target_duration_seconds=sponsor.get("duration", 60),
            )
            ads.append(ad)
        return ads

    def _parse_result(
        self, result, sponsor_name: str, placement: str, duration: int
    ) -> dict:
        """解析LLM输出"""
        import json

        try:
            if hasattr(result, "raw"):
                data = json.loads(result.raw)
            elif isinstance(result, str):
                data = json.loads(result)
            else:
                data = json.loads(str(result))
        except json.JSONDecodeError:
            return {
                "sponsor_name": sponsor_name,
                "script": "本节目由{}赞助".format(sponsor_name),
                "call_to_action": "了解更多请访问官方网站",
                "duration_seconds": duration,
                "placement": placement,
            }

        data["sponsor_name"] = data.get("sponsor_name", sponsor_name)
        data["placement"] = data.get("placement", placement)
        data["duration_seconds"] = data.get("duration_seconds", duration)
        return data
