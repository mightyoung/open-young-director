"""视频生成Prompt类型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# 导入共享角色描述类型
from crewai.content.character.character_types import (
    CharacterProfile,
)


# ============================================================================
# 视频场景Prompt (Video Scene Prompt)
# ============================================================================

@dataclass
class VideoScenePrompt:
    """视频场景Prompt

    用于生成AI视频的场景描述Prompt。
    包含视觉风格、镜头运动、光线等多维度描述。
    """
    scene_description: str = ""  # 场景描述
    visual_style: str = ""  # 视觉风格 (写实、动漫、水墨)
    camera_movement: str = ""  # 镜头运动 (推、拉、摇、移)
    lighting_style: str = ""  # 光线风格
    color_grading: str = ""  # 调色风格
    mood: str = ""  # 整体情绪
    key_visual_elements: List[str] = field(default_factory=list)  # 关键视觉元素
    text_overlay: Optional[str] = None  # 文字叠加
    duration_seconds: int = 0  # 预计时长
    transition: str = ""  # 转场方式


@dataclass
class VideoGenerationPrompt:
    """视频生成完整Prompt

    包含完整的视频生成所需的所有Prompt信息，
    支持多种格式（竖屏、横屏、方形）和时长。
    """
    title: str = ""
    concept: str = ""  # 核心概念
    target_audience: str = ""
    duration_seconds: int = 0
    format: str = "vertical"  # vertical, horizontal, square
    scenes: List[VideoScenePrompt] = field(default_factory=list)
    audio_description: str = ""  # 音频描述
    voiceover_script: Optional[str] = None  # 配音稿
    background_music: str = ""  # 背景音乐
    total_runtime_seconds: int = 0

    # 元数据
    platform: str = ""  # youtube, tiktok, instagram, etc.
    style_tags: List[str] = field(default_factory=list)  # 风格标签
    content_warnings: List[str] = field(default_factory=list)  # 内容警告

    def to_prompt_string(self) -> str:
        """转换为AI视频生成Prompt字符串

        将结构化的视频Prompt转换为可用的文本Prompt格式，
        用于输入到AI视频生成模型（如Sora、Runway等）。

        Returns:
            str: 格式化的Prompt字符串
        """
        lines = []

        # 标题
        if self.title:
            lines.append(f"# {self.title}")

        # 概念
        lines.append(f"\n## Concept / 概念")
        lines.append(self.concept)

        # 基本信息
        lines.append(f"\n## Video Specs / 视频规格")
        lines.append(f"- Duration: {self.duration_seconds}s")
        lines.append(f"- Format: {self.format}")
        if self.platform:
            lines.append(f"- Platform: {self.platform}")
        lines.append(f"- Target Audience: {self.target_audience}")

        # 场景
        lines.append(f"\n## Scenes / 场景")
        for i, scene in enumerate(self.scenes, 1):
            lines.append(f"\n### Scene {i} ({scene.duration_seconds}s)")
            lines.append(f"**Description**: {scene.scene_description}")
            if scene.visual_style:
                lines.append(f"**Visual Style**: {scene.visual_style}")
            if scene.camera_movement:
                lines.append(f"**Camera Movement**: {scene.camera_movement}")
            if scene.lighting_style:
                lines.append(f"**Lighting**: {scene.lighting_style}")
            if scene.color_grading:
                lines.append(f"**Color Grading**: {scene.color_grading}")
            if scene.mood:
                lines.append(f"**Mood**: {scene.mood}")
            if scene.key_visual_elements:
                lines.append(f"**Key Elements**: {', '.join(scene.key_visual_elements)}")
            if scene.transition:
                lines.append(f"**Transition**: {scene.transition}")

        # 音频
        if self.audio_description or self.voiceover_script:
            lines.append(f"\n## Audio / 音频")
            if self.audio_description:
                lines.append(f"**Sound Design**: {self.audio_description}")
            if self.background_music:
                lines.append(f"**Background Music**: {self.background_music}")
            if self.voiceover_script:
                lines.append(f"**Voiceover**: {self.voiceover_script}")

        # 风格标签
        if self.style_tags:
            lines.append(f"\n## Style Tags")
            lines.append(", ".join(self.style_tags))

        return "\n".join(lines)

    def get_scene_count(self) -> int:
        """获取场景数量"""
        return len(self.scenes)

    def get_total_duration(self) -> int:
        """计算总时长"""
        if self.total_runtime_seconds > 0:
            return self.total_runtime_seconds
        return sum(s.duration_seconds for s in self.scenes)


@dataclass
class ShortFormVideoPrompt:
    """短视频Prompt

    专门针对抖音、快手等短视频平台的Prompt格式，
    强调开头钩子、节奏控制和行动号召。
    """
    hook: str = ""  # 开场钩子 (0-3秒)
    main_content: str = ""  # 主体内容
    cta: str = ""  # 行动号召 (结尾)
    duration_seconds: int = 0
    format: str = "vertical"  # 竖屏

    # 节奏点
    beat_timestamps: List[float] = field(default_factory=list)  # 节奏点时间戳

    # 音乐
    music_suggestion: str = ""  # 音乐建议
    music_beat_match: bool = True  # 是否需要卡点

    def to_compact_prompt(self) -> str:
        """转换为紧凑Prompt格式"""
        parts = []

        if self.hook:
            parts.append(f"HOOK: {self.hook}")

        parts.append(f"CONTENT: {self.main_content}")

        if self.music_suggestion:
            parts.append(f"MUSIC: {self.music_suggestion} ({self.music_beat_match and 'beat-matched' or 'free-style'})")

        if self.cta:
            parts.append(f"CTA: {self.cta}")

        return " | ".join(parts)


__all__ = [
    # Shared character types
    "CharacterProfile",
    # Video types
    "VideoScenePrompt",
    "VideoGenerationPrompt",
    "ShortFormVideoPrompt",
]
