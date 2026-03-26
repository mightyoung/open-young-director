"""节目笔记Agent - 生成shownotes和时间戳"""

from typing import TYPE_CHECKING
from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class ShowNotesAgent:
    """播客节目笔记Agent"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="播客内容编辑专家",
            goal="生成专业的节目笔记",
            backstory="你是一位专业的播客内容编辑，擅长整理节目内容为清晰的shownotes，包含时间戳、链接和要点摘要。",
            llm=llm,
            verbose=True,
        )

    def generate_shownotes(
        self,
        topic: str,
        segments: list[dict],
        guest_name: str = None,
        total_duration_minutes: float = 30.0,
    ) -> dict:
        """
        生成节目笔记

        Args:
            topic: 播客主题
            segments: 内容段落列表
            guest_name: 嘉宾姓名（可选）
            total_duration_minutes: 总时长（分钟）

        Returns:
            dict: 包含标题、描述、时间戳、链接的字典
        """
        segments_str = ""
        for seg in segments:
            title = seg.get("title", "未命名段落")
            content = seg.get("content", "")[:100]
            segments_str += f"- {title}: {content}...\n"

        prompt = f"""为播客节目生成shownotes（节目笔记）。

播客主题: {topic}
总时长: {total_duration_minutes}分钟
内容段落:
{segments_str if segments_str else "（无）"}
{"嘉宾: " + guest_name if guest_name else ""}

请提供:
1. 节目标题 - 吸引人的标题
2. 节目描述 - 简短的节目内容描述
3. 时间戳 - 每个段落的起始时间（格式: MM:SS）
4. 嘉宾信息（如果有）- 嘉宾的简单介绍
5. 相关链接 - 节目中提到的资源链接（占位符格式）

请用JSON格式返回:
{{
    "title": "节目标题",
    "description": "节目描述，约100字",
    "timestamps": [
        {{"time": "00:00", "title": "开场"}},
        {{"time": "02:30", "title": "段落1标题"}},
        {{"time": "10:00", "title": "段落2标题"}}
    ],
    "guest_info": "嘉宾介绍（如果有）",
    "links": ["相关链接1", "相关链接2"],
    "social_media": ["社交媒体话题标签"]
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result, topic)

    def generate_timestamps(
        self,
        segments: list[dict],
        total_duration_minutes: float = 30.0,
    ) -> list[dict]:
        """
        仅生成时间戳

        Args:
            segments: 内容段落列表
            total_duration_minutes: 总时长

        Returns:
            list[dict]: 时间戳列表
        """
        if not segments:
            return [{"time": "00:00", "title": "开场"}]

        # 平均分配时间
        num_segments = len(segments)
        segment_duration = total_duration_minutes / num_segments if num_segments > 0 else 5

        timestamps = []
        current_minutes = 0

        for i, seg in enumerate(segments):
            minutes = int(current_minutes)
            seconds = int((current_minutes - minutes) * 60)
            time_str = f"{minutes:02d}:{seconds:02d}"

            timestamps.append({
                "time": time_str,
                "title": seg.get("title", f"段落{i+1}"),
            })

            current_minutes += segment_duration

        return timestamps

    def _parse_result(self, result, topic: str) -> dict:
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
                "title": topic,
                "description": "本期播客精彩内容",
                "timestamps": [],
                "guest_info": None,
                "links": [],
                "social_media": [],
            }
