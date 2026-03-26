"""摄影指导Agent - 为每个场景生成视觉指导"""

from typing import List, Dict, TYPE_CHECKING

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class CinematographyAgent:
    """摄影指导Agent - 为场景生成视觉指导

    负责描述场景的视觉元素：摄影机角度、镜头运动、场景布置等。

    使用示例:
        agent = CinematographyAgent()
        visual_guide = agent.generate_visual_guide(
            scene={"location": "咖啡馆", "action": "两人对话"},
            style="电影"
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化摄影指导Agent

        Args:
            llm: 可选的语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="摄影指导",
            goal="为每个场景生成精确的视觉指导说明",
            backstory="""你是一位经验丰富的电影摄影师（DP/Cinematographer），
            精通各种镜头语言和视觉叙事技巧。你知道如何通过摄影机角度、镜头运动、
            光影设计来增强叙事效果。你的视觉指导能让编剧的文字转化为具体的画面。""",
            verbose=verbose,
            llm=llm,
        )

    def generate_visual_guide(
        self,
        scene: Dict,
        style: str = "电影",
        format_type: str = "film",
    ) -> Dict:
        """生成场景视觉指导

        Args:
            scene: 场景信息，包含location, action, characters等
            style: 视觉风格（如"电影"、"纪录片"）
            format_type: 格式类型（film, tv, short, stage）

        Returns:
            Dict: 包含以下键的字典:
                - camera_angle: 摄影机角度建议
                - lens: 镜头选择
                - movement: 镜头运动
                - lighting: 光影设计
                - blocking: 演员走位
                - visual_notes: 视觉提示
        """
        scene_str = self._format_scene(scene)
        prompt = f"""为以下场景生成详细的视觉指导：

{scene_str}

风格: {style}
格式: {format_type}

请从以下维度提供视觉指导：

1. 摄影机角度 (camera_angle):
   - 使用什么角度最能传达这个场景的情绪？
   - 仰视/俯视/平视/鸟瞰等

2. 镜头选择 (lens):
   - 推荐使用的焦段
   - 如广角、中焦、长焦等

3. 镜头运动 (movement):
   - 固定镜头还是运动镜头？
   - 如需要运动，推荐推、拉、摇、移、跟、升降等

4. 光影设计 (lighting):
   - 主光方向和性质
   - 氛围光/补光建议
   - 特殊光影效果

5. 演员走位 (blocking):
   - 演员在场景中的位置安排
   - 关键的位置关系和变化

请用中文输出，格式清晰。"""

        result = self.agent.run(prompt)
        return self._parse_result(result)

    def generate_sequence_visual_plan(
        self,
        scenes: List[Dict],
        overall_style: str = "电影",
    ) -> List[Dict]:
        """为场景序列生成整体视觉计划

        Args:
            scenes: 场景列表
            overall_style: 整体视觉风格

        Returns:
            List[Dict]: 每个场景的视觉指导列表
        """
        prompt = f"""为以下场景序列生成整体视觉计划：

风格主题: {overall_style}

场景列表:
"""
        for i, scene in enumerate(scenes, 1):
            prompt += f"\n{i}. {scene.get('location', '未知')} - {scene.get('action', '未知')[:50]}"

        prompt += """
\n\n请考虑场景之间的视觉连贯性和节奏变化。
确保相邻场景之间有足够的视觉差异以保持观众兴趣，
但又要保持整体风格一致性。

输出每个场景的：
- 主导氛围（暗淡/明亮/对比等）
- 摄影风格摘要
- 与前后场景的视觉关系"""

        result = self.agent.run(prompt)
        return self._parse_sequence_result(result, len(scenes))

    def _format_scene(self, scene: Dict) -> str:
        """格式化场景信息"""
        lines = []
        for key, value in scene.items():
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def _parse_result(self, result: str) -> Dict:
        """解析LLM输出"""
        guide = {
            "camera_angle": "",
            "lens": "",
            "movement": "",
            "lighting": "",
            "blocking": "",
            "visual_notes": "",
        }

        current_key = None
        lines = result.strip().split("\n")

        key_mapping = {
            "摄影机角度": "camera_angle",
            "角度": "camera_angle",
            "camera": "camera_angle",
            "镜头选择": "lens",
            "镜头": "lens",
            "lens": "lens",
            "镜头运动": "movement",
            "运动": "movement",
            "movement": "movement",
            "光影设计": "lighting",
            "光影": "lighting",
            "lighting": "lighting",
            "演员走位": "blocking",
            "走位": "blocking",
            "blocking": "blocking",
            "视觉提示": "visual_notes",
            "visual": "visual_notes",
        }

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否为键名行
            for cn_key, en_key in key_mapping.items():
                if line.startswith(cn_key) or f"{cn_key}:" in line or f"{cn_key}——" in line:
                    current_key = en_key
                    # 提取值
                    for sep in [":", "——", "："]:
                        if sep in line:
                            value = line.split(sep, 1)[1].strip()
                            guide[current_key] = value
                            break
                    break

        # 如果没有解析到，使用完整结果作为visual_notes
        if not any(guide.values()):
            guide["visual_notes"] = result

        return guide

    def _parse_sequence_result(self, result: str, num_scenes: int) -> List[Dict]:
        """解析序列视觉计划结果"""
        plans = []

        # 默认计划
        for i in range(num_scenes):
            plans.append({
                "camera_angle": "",
                "lens": "",
                "movement": "",
                "lighting": "",
                "blocking": "",
                "visual_notes": f"场景{i + 1}视觉计划",
            })

        # 简单解析：如果能提取信息就填充
        lines = result.strip().split("\n")
        scene_idx = -1

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测场景编号
            for i in range(1, num_scenes + 1):
                if line.startswith(f"{i}.") or f"场景{i}" in line:
                    scene_idx = i - 1
                    break

            if scene_idx >= 0 and scene_idx < num_scenes:
                if "主导" in line or "氛围" in line:
                    plans[scene_idx]["visual_notes"] = line

        return plans


__all__ = ["CinematographyAgent"]
