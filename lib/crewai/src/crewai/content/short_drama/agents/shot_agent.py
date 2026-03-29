"""ShotAgent - 镜头分解专家

负责将集大纲中的每个场景分解为具体的镜头列表，
并生成每个镜头的 Seedance2 视频提示词。
"""

from typing import TYPE_CHECKING, Optional

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class ShotAgent:
    """ShotAgent - 镜头分解专家

    负责：
    1. 将场景分解为多个镜头
    2. 确定每个镜头的类型（establishing, close_up, etc.）
    3. 生成 Seedance2 五维 Prompt
    4. 分配配音词

    使用示例:
        agent = ShotAgent(llm=llm_client)
        shots = agent.decompose_scene(
            scene=scene_plan,
            bible=short_drama_bible,
            episode_num=1,
        )
    """

    # 镜头类型常量
    SHOT_TYPES = [
        "establishing",  # 建立镜头（开场全景）
        "wide",  # 宽景
        "medium",  # 中景
        "medium_close",  # 中近景
        "close_up",  # 特写
        "extreme_close_up",  # 大特写
        "over_shoulder",  # 过肩镜头
        "pov",  # 主观镜头
        "two_shot",  # 双人镜头
        "insert",  # 插入镜头
    ]

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化 Agent

        Args:
            llm: 语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="分镜头脚本专家",
            goal="将场景分解为精准、可执行的镜头列表",
            backstory="""你是一位专业的影视分镜头师，精通各种镜头语言。
            你能够：
            - 将剧本场景分解为具体的摄影机镜头
            - 合理运用镜头类型（特写、中景、全景等）表达情绪
            - 为每个镜头编写精准的视频生成 Prompt
            - 设计流畅的镜头衔接和转场

            你深知 AI 视频生成的特性，能够编写适合 AI 理解的视觉描述。""",
            verbose=verbose,
            llm=llm,
        )

    def decompose_scene(
        self,
        scene_plan: dict,
        bible,
        episode_num: int,
        scene_number: int,
    ) -> list[dict]:
        """将场景分解为镜头列表

        Args:
            scene_plan: 场景规划（来自 EpisodeOutline）
            bible: ShortDramaBible
            episode_num: 集号
            scene_number: 场景序号

        Returns:
            list[dict]: 镜头列表
        """
        prompt = self._build_shot_prompt(
            scene_plan=scene_plan,
            bible=bible,
            episode_num=episode_num,
            scene_number=scene_number,
        )
        result = self.agent.kickoff(messages=prompt)
        return self._parse_shot_result(result, scene_number)

    def _build_shot_prompt(
        self,
        scene_plan: dict,
        bible,
        episode_num: int,
        scene_number: int,
    ) -> str:
        """构建镜头分解提示词"""

        # 角色描述
        characters_info = []
        for name, profile in bible.relevant_characters.items():
            desc_parts = [name]
            if hasattr(profile, 'appearance') and profile.appearance:
                desc_parts.append(f"外貌：{profile.appearance}")
            if hasattr(profile, 'personality') and profile.personality:
                desc_parts.append(f"性格：{profile.personality}")
            characters_info.append("；".join(desc_parts))

        characters_str = "\n".join(f"- {c}" for c in characters_info)

        # 场景信息
        location = scene_plan.get("location", "未知")
        time_of_day = scene_plan.get("time_of_day", "白天")
        description = scene_plan.get("description", "")
        key_actions = scene_plan.get("key_actions", [])
        scene_chars = scene_plan.get("characters", [])
        emotion = scene_plan.get("emotion", "中性")
        duration_estimate = scene_plan.get("duration_estimate", 30)

        prompt = f"""# 分镜头脚本生成

【集号】第{episode_num}集
【场景序号】{scene_number}

【场景信息】
- 地点：{location}
- 时间段：{time_of_day}
- 场景描述：{description}
- 关键动作：{', '.join(key_actions) if key_actions else '无'}
- 出场角色：{', '.join(scene_chars) if scene_chars else '无'}
- 情绪基调：{emotion}
- 预计时长：{duration_estimate}秒

【角色外貌参考】
{characters_str or '无特定角色描述'}

【视觉风格】
{bible.visual_style}

【镜头分解要求】

请将上述场景分解为 {max(2, min(5, duration_estimate // 10))} 个镜头。

每个镜头要求：
- 时长：3-8秒
- 包含：镜头类型、动作描述、出场角色、情绪

镜头类型参考：
- establishing: 建立镜头（开场全景）
- wide: 宽景
- medium: 中景
- close_up: 特写
- extreme_close_up: 大特写
- over_shoulder: 过肩镜头
- two_shot: 双人镜头

请以JSON格式返回：
{{
    "shots": [
        {{
            "shot_number": 1,
            "scene_number": {scene_number},
            "duration_seconds": 5.0,
            "shot_type": "medium",
            "action": "镜头动作描述（10-30字）",
            "characters": ["角色1"],
            "voiceover_segment": "配音词（可选）",
            "emotion": "中性"
        }}
    ]
}}

注意：
- shot_number 在本集内连续编号
- action 描述要具体，适合 AI 视频生成
- characters 必须是列表格式
- emotion 应与场景基调一致"""
        return prompt

    def _parse_shot_result(self, result, scene_number: int) -> list[dict]:
        """解析镜头分解结果"""
        import json
        import re

        try:
            raw_text = ""
            if hasattr(result, "raw"):
                raw_text = result.raw
            elif isinstance(result, str):
                raw_text = result
            else:
                raw_text = str(result)

            # 去除 markdown 代码块
            json_text = raw_text.strip()
            if json_text.startswith("```"):
                lines = json_text.split("\n")
                start_idx = 1 if lines[0].strip().startswith("```") else 0
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().endswith("```"):
                        json_text = "\n".join(lines[start_idx:i])
                        break

            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', json_text)
            if json_match:
                data = json.loads(json_match.group())
                shots = data.get("shots", [])
                # 确保 scene_number 正确
                for shot in shots:
                    shot["scene_number"] = scene_number
                return shots

        except Exception as e:
            import logging
            logging.warning(f"Failed to parse shots: {e}")

        # Fallback
        return [{
            "shot_number": 1,
            "scene_number": scene_number,
            "duration_seconds": 5.0,
            "shot_type": "medium",
            "action": "默认动作",
            "characters": [],
            "voiceover_segment": "",
            "emotion": "中性",
        }]


__all__ = ["ShotAgent"]
