"""EpisodeOutlineAgent - 生成本集大纲

负责将章节内容或上一集结尾转换为短剧集大纲，
包含场景规划和关键情节点。
"""

from typing import TYPE_CHECKING

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class EpisodeOutlineAgent:
    """EpisodeOutlineAgent - 集大纲生成专家

    负责：
    1. 分析章节内容，提取关键情节点
    2. 规划场景结构（开场、发展、高潮、结尾）
    3. 分配角色出场顺序
    4. 确定每场的时间、地点、情绪基调

    使用示例:
        agent = EpisodeOutlineAgent(llm=llm_client)
        outline = agent.generate_outline(
            chapter_text="...",
            bible=short_drama_bible,
            episode_num=1,
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化 Agent

        Args:
            llm: 语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="短剧集大纲策划专家",
            goal="生成结构清晰、情节紧凑的短剧集大纲",
            backstory="""你是一位资深的短视频编剧，擅长在极短时间内讲述完整的故事。
            你对短剧/抖音剧情号的内容形式有深入研究，能够：
            - 在3-5分钟内呈现完整的故事弧线（起承转合）
            - 精准控制每个场景的时长和情绪节奏
            - 设计强冲突、高潮迭起的剧情
            - 合理分配角色出场，最大化戏剧效果
            你深知短视频观众的注意力有限，因此每个镜头、每句台词都必须推动情节发展。""",
            verbose=verbose,
            llm=llm,
        )

    def generate_outline(
        self,
        chapter_text: str,
        bible,
        episode_num: int,
        series_title: str = "",
        episode_context: str = "",
    ) -> dict:
        """生成本集大纲

        Args:
            chapter_text: 章节原文
            bible: ShortDramaBible
            episode_num: 集号
            series_title: 系列标题
            episode_context: 剧情承接（上一集结尾）

        Returns:
            dict: 包含集大纲的字典
        """
        prompt = self._build_outline_prompt(
            chapter_text=chapter_text,
            bible=bible,
            episode_num=episode_num,
            series_title=series_title,
            episode_context=episode_context,
        )
        result = self.agent.kickoff(messages=prompt)
        return self._parse_outline_result(result)

    def _build_outline_prompt(
        self,
        chapter_text: str,
        bible,
        episode_num: int,
        series_title: str,
        episode_context: str,
    ) -> str:
        """构建大纲生成提示词"""

        # 构建角色信息
        characters_info = []
        for name, profile in bible.relevant_characters.items():
            chars = []
            if hasattr(profile, 'personality') and profile.personality:
                chars.append(f"性格：{profile.personality}")
            if hasattr(profile, 'role') and profile.role:
                chars.append(f"角色：{profile.role}")
            if hasattr(profile, 'speech_pattern') and profile.speech_pattern:
                chars.append(f"说话风格：{profile.speech_pattern}")
            characters_info.append(f"- {name}：{'；'.join(chars) if chars else '主要角色'}")

        characters_str = "\n".join(characters_info) if characters_info else "无特定角色"

        # 构建世界观信息
        world_info = bible.world_rules_summary

        prompt = f"""# 短剧集大纲生成（增强版：支持多集串联）

【本集剧情承接】
{episode_context or '无（第一集）'}

【系列标题】
{series_title}

【本集集号】
第{episode_num}集

【小说原文】
---
{chapter_text[:3000]}
---

【世界观设定】
{world_info}

【本集出场角色】
{characters_str}

【短剧集大纲要求】

请按以下要求生成短剧集大纲：

1. **时长规划**：每集时长 2-5 分钟，总镜头数 10-20 个
2. **场景结构**：建议 3-6 个场景，每个场景 20-60 秒
3. **情节节奏**：
   - 开头（0-30秒）：建立冲突或悬念，**必须承接上一集尾帧**
   - 发展（30秒-2分钟）：矛盾升级
   - 高潮（2-3分钟）：核心冲突爆发
   - 结尾（3-5分钟）：**必须留下悬念尾帧，为下一集铺垫**
4. **镜头设计**：每个场景包含 2-5 个镜头
5. **尾帧设计**：最后一个场景必须设计强悬念尾帧，包含：
   - 角色状态（表情、动作、位置）
   - 背景环境
   - 光线色调
   - 情绪氛围

请以JSON格式返回：
{{
    "episode_num": {episode_num},
    "title": "集标题",
    "episode_summary": "本集概要（100字内）",
    "end_frame": {{
        "character_state": "尾帧角色状态描述",
        "background": "尾帧背景环境",
        "lighting": "尾帧光线色调",
        "mood": "尾帧情绪氛围"
    }},
    "scene_plan": [
        {{
            "scene_number": 1,
            "location": "地点",
            "time_of_day": "时间段",
            "description": "场景描述",
            "key_actions": ["关键动作1", "关键动作2"],
            "characters": ["角色1", "角色2"],
            "emotion": "情绪基调",
            "duration_estimate": 45,
            "is_opening": true,
            "is_ending": false
        }}
    ]
}}

注意：
- 所有角色名必须与【本集出场角色】中的名称一致
- 场景描述应简洁，适合拍摄
- 每个场景的 duration_estimate 单位为秒
- is_opening=true 表示需要承接上一集尾帧
- is_ending=true 表示需要设计悬念尾帧"""
        return prompt

    def _parse_outline_result(self, result) -> dict:
        """解析大纲生成结果"""
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
                return data

        except Exception as e:
            import logging
            logging.warning(f"Failed to parse outline: {e}")

        # Fallback
        return {
            "episode_num": 1,
            "title": "默认标题",
            "episode_summary": "剧情概要",
            "end_frame": {
                "character_state": "默认状态",
                "background": "默认背景",
                "lighting": "默认光线",
                "mood": "平静"
            },
            "scene_plan": [],
        }


__all__ = ["EpisodeOutlineAgent"]
