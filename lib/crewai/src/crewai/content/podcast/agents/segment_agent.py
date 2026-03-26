"""内容段落Agent - 生成播客主体内容"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class SegmentAgent:
    """播客内容段落Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客内容策划专家",
            goal="创作丰富深入的内容段落",
            backstory="你是一位内容深度策划专家，擅长将复杂话题分解成易于理解的段落，用生动的例子和故事让听众保持兴趣。",
            llm=llm,
            verbose=True,
        )

    def generate_segment(
        self,
        topic: str,
        segment_num: int,
        segment_theme: str,
        target_duration_minutes: float = 5.0,
        previous_segment_summary: str = "",
    ) -> dict:
        """
        生成播客内容段落

        Args:
            topic: 播客主题
            segment_num: 段落编号
            segment_theme: 段落主题
            target_duration_minutes: 目标时长（分钟）
            previous_segment_summary: 前一段落概要

        Returns:
            dict: 包含标题、内容、关键点的字典
        """
        # 播客脚本约150字/分钟
        target_words = int(target_duration_minutes * 150)

        prompt = f"""为播客主题'{topic}'生成第{segment_num}个内容段落。

段落主题: {segment_theme}
目标时长: {target_duration_minutes}分钟（约{target_words}字）
前一段落概要: {previous_segment_summary if previous_segment_summary else "（无）"}

请提供:
1. 段落标题
2. 完整播客脚本（自然对话风格，适合口语表达）
3. 3-5个关键讨论点
4. 过渡语（用于连接下一段落）

请用JSON格式返回:
{{
    "segment_num": {segment_num},
    "title": "段落标题",
    "content": "完整脚本内容，约{target_words}字",
    "key_points": ["关键点1", "关键点2", "关键点3"],
    "transition": "过渡语"
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result, segment_num)

    def generate_multiple_segments(
        self,
        topic: str,
        num_segments: int,
        segment_themes: list[str],
        target_duration_minutes: float = 5.0,
    ) -> list[dict]:
        """
        生成多个内容段落

        Args:
            topic: 播客主题
            num_segments: 段落数量
            segment_themes: 各段落主题列表
            target_duration_minutes: 每个段落目标时长

        Returns:
            list[dict]: 段落列表
        """
        segments = []
        previous_summary = ""

        for i in range(num_segments):
            segment_theme = segment_themes[i] if i < len(segment_themes) else f"第{i+1}个主题"
            segment = self.generate_segment(
                topic=topic,
                segment_num=i + 1,
                segment_theme=segment_theme,
                target_duration_minutes=target_duration_minutes,
                previous_segment_summary=previous_summary,
            )
            segments.append(segment)
            previous_summary = segment.get("title", f"第{i+1}段")

        return segments

    def _parse_result(self, result, segment_num: int) -> dict:
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
                "segment_num": segment_num,
                "title": f"第{segment_num}段",
                "content": "内容待补充",
                "key_points": [],
                "transition": "",
            }

        data["segment_num"] = data.get("segment_num", segment_num)
        return data
