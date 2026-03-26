"""分镜表Agent - 将故事结构分解为场景Beats"""

from dataclasses import dataclass
from typing import List, TYPE_CHECKING

from crewai.agent import Agent

from crewai.content.script.script_types import Beat, BeatSheet

if TYPE_CHECKING:
    from crewai.llm import LLM


class BeatSheetAgent:
    """分镜表Agent：结构→场景过渡

    将高级故事结构分解为具体的场景转折点（Beats）。

    使用示例:
        agent = BeatSheetAgent()
        beat_sheets = agent.generate_beat_sheet(structure={"acts": [...]}, target_runtime=120)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化分镜表Agent

        Args:
            llm: 可选的语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="分镜规划师",
            goal="将故事结构分解为可执行的场景Beats",
            backstory="""你是一位资深编剧，擅长将故事结构分解为具体的场景转折点。
            你对节拍表（Beat Sheet）有深刻理解，能够将三幕结构或英雄之旅等叙事框架
            转化为具体的场景转折点。每个Beat都清晰地回答：这个场景谁想要什么？障碍是什么？""",
            verbose=verbose,
            llm=llm,
        )

    def generate_beat_sheet(
        self,
        structure: dict,
        target_runtime: int,
        num_acts: int = 3,
    ) -> List[BeatSheet]:
        """生成分镜表

        Args:
            structure: 故事结构，包含acts等信息
            target_runtime: 目标时长（分钟）
            num_acts: 幕数（默认3幕）

        Returns:
            List[BeatSheet]: 分镜表列表
        """
        structure_str = self._format_structure(structure)
        prompt = f"""基于以下故事结构，生成分镜表（Beat Sheet）：

{structure_str}

目标时长: {target_runtime}分钟
幕数: {num_acts}

请按以下格式输出分镜表。对于每个Act，列出具体的Beats：

Act结构说明:
- Act I: 建置（建立角色、世界、冲突）
- Act IIa: 上升（主角开始行动）
- Act IIb: 中点（重大转折）
- Act III: 结局（高潮与解决）

每个Beat需包含:
- number: 编号
- name: Beat名称
- description: 简要描述（1-2句话）
- scene_purpose: 谁想要什么？障碍是什么？
- turning_point: 是否为转折点（True/False）

请确保Beats之间有明确的戏剧弧线。"""

        result = self.agent.run(prompt)
        return self._parse_result(result, num_acts)

    def _format_structure(self, structure: dict) -> str:
        """格式化结构为可读字符串"""
        lines = []
        if "title" in structure:
            lines.append(f"标题: {structure['title']}")
        if "logline" in structure:
            lines.append(f"一句话概括: {structure['logline']}")
        if "acts" in structure:
            lines.append("\n故事结构:")
            for i, act in enumerate(structure["acts"], 1):
                lines.append(f"\n第{i}幕:")
                if isinstance(act, dict):
                    for key, value in act.items():
                        lines.append(f"  {key}: {value}")
                else:
                    lines.append(f"  {act}")
        return "\n".join(lines)

    def _parse_result(self, result: str, num_acts: int) -> List[BeatSheet]:
        """解析LLM输出为BeatSheet列表"""
        beat_sheets = []
        current_act = None
        current_beats = []

        lines = result.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测Act标记
            act_match = None
            for act_name in ["Act I", "Act IIa", "Act IIb", "Act III", "第一幕", "第二幕", "第三幕", "幕"]:
                if line.startswith(act_name) or f"{act_name}:" in line or f"{act_name}——" in line:
                    # 保存之前的Act
                    if current_act is not None:
                        beat_sheets.append(BeatSheet(
                            act=current_act,
                            beats=current_beats,
                            total_runtime_estimate=len(current_beats) * 5  # 估算
                        ))
                    current_act = line.split(":")[0].strip()
                    current_beats = []
                    break

            # 检测Beat标记
            beat_markers = ["Beat", "beat", "转折点", "场景"]
            for marker in beat_markers:
                if marker in line and ("-" in line or ":" in line):
                    parts = line.replace("-", ":").split(":")
                    if len(parts) >= 2:
                        try:
                            beat_num = len(current_beats) + 1
                            beat_name = parts[1].strip() if len(parts) > 1 else f"Beat {beat_num}"
                            beat_desc = parts[2].strip() if len(parts) > 2 else ""

                            # 检查是否为转折点
                            is_turning = "转折" in line or "turning" in line.lower()

                            current_beats.append(Beat(
                                number=beat_num,
                                name=beat_name,
                                description=beat_desc,
                                scene_purpose="",  # 需要从描述中提取
                                turning_point=is_turning
                            ))
                        except (ValueError, IndexError):
                            continue
                    break

        # 保存最后一个Act
        if current_act is not None:
            beat_sheets.append(BeatSheet(
                act=current_act,
                beats=current_beats,
                total_runtime_estimate=len(current_beats) * 5
            ))

        # 如果解析失败，返回默认结构
        if not beat_sheets:
            beat_sheets = self._create_default_beat_sheets(num_acts)

        return beat_sheets

    def _create_default_beat_sheets(self, num_acts: int) -> List[BeatSheet]:
        """创建默认分镜表（当解析失败时）"""
        act_names = ["Act I", "Act IIa", "Act IIb", "Act III"][:num_acts]
        return [
            BeatSheet(
                act=name,
                beats=[
                    Beat(
                        number=i + 1,
                        name=f"Beat {i + 1}",
                        description="",
                        scene_purpose="",
                        turning_point=False
                    )
                ],
                total_runtime_estimate=10
            )
            for i, name in enumerate(act_names)
        ]


__all__ = ["BeatSheetAgent"]
