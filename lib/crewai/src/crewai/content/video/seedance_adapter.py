# -*- encoding: utf-8 -*-
"""Seedance 2.0 Video Prompt Adapter (Enhanced)

基于五维控制坐标系的视频提示词生成器，专为Seedance 2.0优化。
集成 research_awesome_seedance.md 和 Seedance2-Storyboard-Generator 的最佳实践。

增强功能：
1. 精确时间轴控制（0-3s, 4-8s, 9-12s）
2. 多模态参考系统（@图片/@视频/@音频）
3. 多集串联尾帧衔接
4. Camera Language 关键词库

五维控制坐标系：
1. 绝对主体与物理动势
2. 环境场与情绪光影
3. 光学与摄影机调度
4. 时间轴与状态演变
5. 美学介质与底层渲染参数

Usage:
    from crewai.content.video import Seedance2PromptAdapter

    adapter = Seedance2PromptAdapter()

    # 生成提示词
    prompt = adapter.generate_prompt(
        scene_description="韩林立于演武场边缘，清晨薄雾中抬眸望向测灵台",
        characters=[char_spec],
        shot_type="establishing"
    )

    # 多集串联
    adapter.generate_continuity_prompt(
        current_shot_prompt=prompt,
        next_episode_end_frame=end_frame,
        episode_number=2
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class FramePrompt:
    """单帧提示词"""
    frame_type: str  # start_frame, key_frame, end_frame
    time_range: str  # 0-3s
    prompt_text: str


@dataclass
class TimelineSegment:
    """时间轴片段（增强版：每5秒一段，每段四层：画面+镜头运动+音效+情绪）

    基于 seedance-prompt-skill 的精确时间戳设计
    """
    time_range: str  # 0-5s
    description: str  # 画面内容描述（精确）
    camera: str = ""  # 镜头运动
    lens: str = ""  # 焦段
    mood: str = ""  # 情绪
    sound_effects: str = ""  # 音效描述
    dialogue: str = ""  # 对白描述
    lighting: str = ""  # 光线描述
    transition: str = ""  # 转场方式


@dataclass
class EndFrameDescription:
    """尾帧描述（用于shot间衔接，研究发现这是确保连贯性的关键）"""
    character_state: str  # 主体状态
    background: str  # 背景环境
    lighting: str  # 光线色调
    composition: str  # 构图方式
    mood: str  # 氛围情绪
    camera_state: str = ""  # 镜头状态（用于衔接）
    motion_state: str = ""  # 运动状态（用于衔接）


@dataclass
class ContinuityPrompt:
    """多集串联提示词（增强版：用于E1→E2衔接）"""
    previous_episode_end: EndFrameDescription  # 上一集尾帧
    current_episode_start: str  # 当前集开头描述
    transition_direction: str  # 镜头过渡方向
    connection_type: str  # 衔接类型：承接/淡入/跳切


# 素材编号系统（基于Seedance2-Storyboard-Generator研究）
ASSET_CODES = {
    "character": "C",  # 角色素材
    "scene": "S",  # 场景/地点素材
    "prop": "P",  # 道具/物品素材
    "effect": "FX",  # 特效/氛围素材
}


# =============================================================================
# Camera Language 关键词库（基于 seedance-prompt-skill 研究）
# =============================================================================

CAMERA_LANGUAGE = {
    "推近": {
        "keywords": ["推镜头", "缓慢推近", "急速推进", "zoom in", "dolly in"],
        "description": "镜头向前推进，拉近主体"
    },
    "拉远": {
        "keywords": ["拉镜头", "逐渐拉远", "向后移动", "zoom out", "dolly out"],
        "description": "镜头向后移动，远离主体"
    },
    "横移_左": {
        "keywords": ["左摇", "向左横移", "pan left", "slide left"],
        "description": "镜头向左横扫"
    },
    "横移_右": {
        "keywords": ["右摇", "向右横移", "pan right", "slide right"],
        "description": "镜头向右横扫"
    },
    "环绕": {
        "keywords": ["环绕镜头", "360度旋转", "旋转跟进", "orbiting", "crane"],
        "description": "环绕主体旋转拍摄"
    },
    "升降": {
        "keywords": ["升镜头", "降镜头", "俯冲", "仰升", "tilt up", "tilt down"],
        "description": "镜头上下升降"
    },
    "跟随": {
        "keywords": ["跟随镜头", "跟拍", "跟踪拍摄", "follow shot", "tracking"],
        "description": "跟随主体移动"
    },
    "希区柯克": {
        "keywords": ["希区柯克变焦", "dolly zoom", "vertigo effect"],
        "description": "希区柯克变焦效果"
    },
    "一镜到底": {
        "keywords": ["一镜到底", "长镜头", "long take", "one shot"],
        "description": "连续不间断拍摄"
    },
    "手持晃动": {
        "keywords": ["手持晃动", "纪录片风格", "handheld"],
        "description": "手持摄影的自然晃动"
    },
    "凝固时间": {
        "keywords": ["慢动作定格", "凝固瞬间", "slow motion", "freeze frame"],
        "description": "慢动作或定格"
    }
}


# 素材引用前缀映射（用于@语法）
ASSET_REFERENCE_PREFIX = {
    "character": "图片",  # @图片1[C01]
    "scene": "图片",      # @图片2[S01]
    "prop": "图片",       # @图片3[P01]
    "effect": "视频",     # @视频1[FX01]
    "audio": "音频",      # @音频1[BGM01]
}


@dataclass
class CharacterSpec:
    """角色规格（用于提示词生成）"""
    name: str
    age_appearance: str = ""
    face: str = ""
    hair: str = ""
    clothing: str = ""
    build: str = ""
    expression_range: Dict[str, str] = field(default_factory=dict)
    accessories: str = ""
    physical_traits: str = ""
    negative: str = ""

    def to_subject_description(self, emotion: Optional[str] = None) -> str:
        """转换为绝对主体描述"""
        parts = [self.name]
        if self.age_appearance:
            parts.append(self.age_appearance)
        if self.clothing:
            parts.append(self.clothing)
        if self.hair:
            parts.append(self.hair)
        if self.face:
            parts.append(self.face)
        if emotion and emotion in self.expression_range:
            parts.append(self.expression_range[emotion])
        elif "default" in self.expression_range:
            parts.append(self.expression_range["default"])
        return "，".join(parts)


@dataclass
class SceneSpec:
    """场景规格"""
    name: str
    location_type: str = ""
    architecture: str = ""
    exterior: str = ""
    color_palette: str = ""
    atmosphere: str = ""
    lighting: Dict[str, str] = field(default_factory=dict)
    key_props: List[str] = field(default_factory=list)

    def to_environment_description(self, time_of_day: str = "morning") -> str:
        """转换为环境场描述"""
        parts = [self.name]
        if self.location_type:
            parts.append(self.location_type)
        if self.architecture:
            parts.append(self.architecture)
        if self.exterior:
            parts.append(self.exterior)
        if self.color_palette:
            parts.append(self.color_palette)
        time_key = time_of_day.lower()
        if time_key in self.lighting:
            parts.append(self.lighting[time_key])
        elif self.lighting:
            first_time = list(self.lighting.keys())[0]
            parts.append(self.lighting[first_time])
        return "，".join(parts)


# =============================================================================
# Seedance 2.0 Prompt Adapter (Enhanced)
# =============================================================================


class Seedance2PromptAdapter:
    """Seedance 2.0 视频提示词适配器（增强版）

    基于五维控制坐标系生成精准的AI视频提示词，
    遵循"锁定已有参数，精准操控空白维度"原则。

    增强功能：
    - 精确时间轴控制（每5秒一段）
    - 多模态参考系统
    - 多集串联尾帧衔接
    - Camera Language 关键词库
    """

    # 镜头类型映射
    SHOT_TYPES = {
        "establishing": "航拍全景",
        "wide": "全景",
        "full": "全身镜头",
        "medium": "中景",
        "medium_close": "中近景",
        "close_up": "特写",
        "extreme_close_up": "大特写",
        "over_shoulder": "过肩镜头",
        "pov": "主观镜头",
        "two_shot": "双人镜头",
        "insert": "插入镜头",
    }

    # 焦段推荐
    LENS_FOCAL_LENGTHS = {
        "wide": "24mm",
        "medium": "35mm",
        "standard": "50mm",
        "portrait": "85mm",
        "close_up": "90mm",
        "extreme_close": "100mm macro",
    }

    # 渲染参数模板
    RENDER_PARAMS = "8K超清，电影级画质，精细渲染，无模糊，无水印"

    # Seedance 2.0 负面提示词
    NEGATIVE_PROMPT = (
        "CGI, 3D render, Unreal Engine, cartoon, anime, illustration, "
        "hand-drawn, painting, deformed characters, disproportionate body, "
        "facial distortion, broken fingers, extra limbs, floating characters, "
        "cutout feeling, inconsistent light and shadow, lens jump, sudden scene change, "
        "choppy motion, unnatural movement, glowing magic effect, floating sparkles, "
        "neon light, over-saturated colors, over-bloom, flat lighting, fake mist, "
        "blurry picture, out of focus, text, watermark, logo, UI elements, "
        "ugly face, distorted perspective, duplicate characters, messy composition"
    )

    def __init__(self, default_style: str = "高度写实风格"):
        """初始化适配器

        Args:
            default_style: 默认画面风格
        """
        self.default_style = default_style

    # =============================================================================
    # P1: 增强时间轴控制
    # =============================================================================

    def _format_timeline(self, segments: List[TimelineSegment]) -> str:
        """格式化时间轴（增强版：每时段四层：画面+镜头+音效+情绪）

        基于 seedance-prompt-skill 的精确时间戳设计
        """
        lines = []
        for seg in segments:
            # 每段四层：画面内容 + 镜头运动 + 音效 + 情绪
            line_parts = [f"{seg.time_range}：{seg.description}"]

            if seg.camera:
                line_parts.append(f"镜头：{seg.camera}")
            if seg.lens:
                line_parts.append(f"焦段：{seg.lens}")
            if seg.lighting:
                line_parts.append(f"光线：{seg.lighting}")
            if seg.mood:
                line_parts.append(f"情绪：{seg.mood}")
            if seg.sound_effects:
                line_parts.append(f"音效：{seg.sound_effects}")
            if seg.dialogue:
                line_parts.append(f"对白：\"{seg.dialogue}\"")
            if seg.transition:
                line_parts.append(f"转场：{seg.transition}")

            lines.append("，".join(line_parts))
        return "\n".join(lines)

    def generate_timeline_segments(
        self,
        scene_description: str,
        duration: int = 15,
        segment_duration: int = 5,
        camera_movement: str = "",
        sound_effects: str = "",
        dialogue: str = "",
    ) -> List[TimelineSegment]:
        """生成精确时间轴片段（增强版）

        基于 seedance-prompt-skill 的时间轴设计：
        - 每5秒一段（而非3秒）
        - 每段包含精确的画面描述

        Args:
            scene_description: 场景描述（会被分配到各段）
            duration: 总时长（秒）
            segment_duration: 每段时长（默认5秒）
            camera_movement: 相机运动
            sound_effects: 音效
            dialogue: 对白

        Returns:
            TimelineSegment列表
        """
        time_segments = duration // segment_duration
        timeline = []

        # 将场景描述分配到各时间段的模式
        # 模式1: 开头建立 → 中间发展 → 结尾高潮
        patterns = ["场景建立", "情节发展", "高潮爆发"]
        transitions = ["", "", "高潮定格"]

        for i in range(time_segments):
            start = i * segment_duration
            end = (i + 1) * segment_duration

            # 根据时间段选择模式
            if i == 0:
                desc = f"建立镜头：{scene_description[:50]}..."
                camera = "固定镜头" if not camera_movement else camera_movement
            elif i == time_segments - 1:
                desc = f"高潮：{scene_description}"
                camera = camera_movement
            else:
                desc = f"发展{i}：{scene_description[max(0, i*20):max(100, i*20+50)]}"
                camera = camera_movement

            timeline.append(TimelineSegment(
                time_range=f"{start}-{end}秒",
                description=desc,
                camera=camera,
                mood=patterns[i] if i < len(patterns) else "平稳",
                sound_effects=sound_effects,
                dialogue=dialogue if i == time_segments - 1 else "",
                transition=transitions[i] if i < len(transitions) else ""
            ))

        return timeline

    # =============================================================================
    # P2: 多模态参考系统
    # =============================================================================

    def generate_asset_reference(
        self,
        asset_type: str,
        asset_id: str,
        description: str = "",
        frame_type: str = "key_frame"
    ) -> str:
        """生成素材引用（基于 @ 语法）

        支持 seedance-prompt-skill 的多模态参考系统：
        - @图片1~9：角色/场景/道具参考
        - @视频1~3：镜头运动/动作/特效参考
        - @音频1~3：背景音乐/配音/音效参考

        Args:
            asset_type: 素材类型（character/scene/prop/effect/audio）
            asset_id: 素材ID（如C01, S01, P01, FX01, BGM01）
            description: 素材描述
            frame_type: 帧类型（start_frame/key_frame/end_frame）

        Returns:
            格式化的素材引用字符串，如：@图片1[C01] 角色正面全身
        """
        prefix = ASSET_REFERENCE_PREFIX.get(asset_type.lower(), "图片")
        type_code = ASSET_CODES.get(asset_type.lower(), "X")

        if description:
            return f"@{prefix}{asset_id}[{type_code}{asset_id}] {description}"
        return f"@{prefix}{asset_id}[{type_code}{asset_id}]"

    def generate_multi_modal_references(
        self,
        character_refs: List[tuple] = None,
        scene_refs: List[tuple] = None,
        prop_refs: List[tuple] = None,
        video_refs: List[tuple] = None,
        audio_refs: List[tuple] = None,
    ) -> str:
        """生成多模态参考列表

        Args:
            character_refs: [(asset_id, description), ...]
            scene_refs: [(asset_id, description), ...]
            prop_refs: [(asset_id, description), ...]
            video_refs: [(asset_id, description), ...]  # 镜头运动参考
            audio_refs: [(asset_id, description), ...]  # 音频参考

        Returns:
            格式化的多模态参考字符串
        """
        refs = []

        if character_refs:
            for asset_id, desc in character_refs:
                refs.append(f"@图片{asset_id}[C{asset_id}] {desc}")

        if scene_refs:
            for asset_id, desc in scene_refs:
                refs.append(f"@图片{asset_id}[S{asset_id}] {desc}")

        if prop_refs:
            for asset_id, desc in prop_refs:
                refs.append(f"@图片{asset_id}[P{asset_id}] {desc}")

        if video_refs:
            for asset_id, desc in video_refs:
                refs.append(f"@视频{asset_id}[VID{asset_id}] {desc}")

        if audio_refs:
            for asset_id, desc in audio_refs:
                refs.append(f"@音频{asset_id}[AUD{asset_id}] {desc}")

        return "\n".join(refs) if refs else ""

    # =============================================================================
    # P3: 多集串联尾帧衔接
    # =============================================================================

    def generate_end_frame(
        self,
        characters: List[CharacterSpec],
        scene: Optional[SceneSpec],
        final_action: str,
        mood: str = "",
        camera_state: str = "",
        motion_state: str = ""
    ) -> EndFrameDescription:
        """生成尾帧描述（增强版：包含镜头/运动状态用于衔接）

        Args:
            characters: 角色列表
            scene: 场景规格
            final_action: 最后的动作状态
            mood: 氛围情绪
            camera_state: 镜头状态（用于下一集衔接）
            motion_state: 运动状态（用于下一集衔接）

        Returns:
            EndFrameDescription实例
        """
        # 角色状态
        if characters:
            char_states = [c.to_subject_description() for c in characters]
            char_state = "，".join(char_states)
        else:
            char_state = "未知角色"

        # 背景环境
        if scene:
            bg = scene.to_environment_description()
        else:
            bg = "未知场景"

        # 光线色调
        lighting = scene.lighting.get("default", "自然光") if scene and scene.lighting else "自然光"

        return EndFrameDescription(
            character_state=char_state + "，" + final_action,
            background=bg,
            lighting=lighting,
            composition="中景构图" if not mood else f"{mood}构图",
            mood=mood or "平静",
            camera_state=camera_state or "固定镜头",
            motion_state=motion_state or "静止"
        )

    def format_end_frame(self, end_frame: EndFrameDescription) -> str:
        """格式化尾帧描述

        Args:
            end_frame: 尾帧描述对象

        Returns:
            格式化的尾帧描述字符串
        """
        return f"""主体状态：{end_frame.character_state}
背景环境：{end_frame.background}
光线色调：{end_frame.lighting}
构图方式：{end_frame.composition}
氛围情绪：{end_frame.mood}
镜头状态：{end_frame.camera_state}
运动状态：{end_frame.motion_state}"""

    def generate_continuity_prompt(
        self,
        previous_episode_end: EndFrameDescription,
        episode_number: int,
        connection_type: str = "承接",
        transition_direction: str = "顺接"
    ) -> ContinuityPrompt:
        """生成多集串联提示词

        基于 Seedance2-Storyboard-Generator 的尾帧衔接设计：
        E1尾帧 → E2开头 自动衔接

        Args:
            previous_episode_end: 上一集尾帧描述
            episode_number: 当前集号
            connection_type: 衔接类型（承接/淡入/跳切）
            transition_direction: 过渡方向（顺接/倒叙）

        Returns:
            ContinuityPrompt实例
        """
        # 衔接描述模板
        connection_templates = {
            "承接": "承接上一镜头，镜头从{start_state}缓缓{transition}至{end_state}",
            "淡入": "画面渐隐过渡，天色从{lighting}转至下一场景",
            "跳切": "画面跳转，下一幕：同一角色在{background}中继续{action}"
        }

        template = connection_templates.get(connection_type, connection_templates["承接"])
        start_state = previous_episode_end.camera_state
        transition = "推进" if transition_direction == "顺接" else "拉远"

        current_start = template.format(
            start_state=start_state,
            transition=transition,
            end_state="新场景建立",
            lighting=previous_episode_end.lighting,
            background=previous_episode_end.background,
            action=previous_episode_end.character_state
        )

        return ContinuityPrompt(
            previous_episode_end=previous_episode_end,
            current_episode_start=current_start,
            transition_direction=transition_direction,
            connection_type=connection_type
        )

    def format_continuity_prompt(self, continuity: ContinuityPrompt, episode_number: int) -> str:
        """格式化多集串联提示词

        Args:
            continuity: ContinuityPrompt实例
            episode_number: 当前集号

        Returns:
            格式化的串联提示词字符串
        """
        end = continuity.previous_episode_end

        return f"""【第{episode_number}集承接第{episode_number-1}集尾帧】

【上一集尾帧】
{self.format_end_frame(end)}

【衔接方式】{continuity.connection_type}
【当前集开头】
承接@图片1[E{episode_number-1}尾帧]延长5秒
{continuity.current_episode_start}

【镜头过渡】{continuity.transition_direction}"""

    # =============================================================================
    # P4: Camera Language 关键词库
    # =============================================================================

    def lookup_camera_keywords(self, effect: str) -> List[str]:
        """查找运镜效果对应的关键词

        Args:
            effect: 效果名称（如"推近"、"环绕"）

        Returns:
            关键词列表
        """
        effect_lower = effect.lower()
        for key, data in CAMERA_LANGUAGE.items():
            if effect_lower in key or any(effect_lower in kw for kw in data["keywords"]):
                return data["keywords"]
        return [effect]  # 未找到时返回原词

    def generate_camera_prompt(
        self,
        shot_type: str,
        camera_effect: str = "",
        focal_length: str = ""
    ) -> str:
        """生成运镜描述（增强版：包含关键词库）

        Args:
            shot_type: 镜头类型
            camera_effect: 运镜效果（如"推近"、"环绕"）
            focal_length: 焦段

        Returns:
            运镜描述字符串
        """
        parts = []

        shot_cn = self.SHOT_TYPES.get(shot_type, shot_type)
        parts.append(f"景别：{shot_cn}")

        if camera_effect:
            # 使用关键词库
            keywords = self.lookup_camera_keywords(camera_effect)
            parts.append(f"镜头：{', '.join(keywords)}")

        if focal_length:
            parts.append(f"焦段：{focal_length}")
        elif shot_type in self.LENS_FOCAL_LENGTHS:
            parts.append(f"焦段：{self.LENS_FOCAL_LENGTHS[shot_type]}")

        return "，".join(parts)

    # =============================================================================
    # 原有功能保留
    # =============================================================================

    def _generate_subject_motion(
        self,
        characters: List[CharacterSpec],
        action_description: str,
        emotion: str = "default",
        motion_track: Optional[str] = None
    ) -> str:
        """生成绝对主体与物理动势描述"""
        parts = []

        char_descs = [c.to_subject_description(emotion if emotion else "default") for c in characters]
        if len(char_descs) == 1:
            parts.append(f"人物：{char_descs[0]}")
        else:
            parts.append(f"人物：{'，'.join(char_descs)}")

        if action_description:
            parts.append(f"动作：{action_description}")

        if motion_track:
            parts.append(f"运动轨迹：{motion_track}")

        return "\n".join(parts)

    def _generate_environment(
        self,
        scene: Optional[SceneSpec],
        environment_description: str,
        time_of_day: str = "清晨"
    ) -> str:
        """生成环境场与情绪光影描述"""
        parts = []

        if scene:
            env_desc = scene.to_environment_description(time_of_day.lower())
            parts.append(f"场景：{env_desc}")
        elif environment_description:
            parts.append(f"场景：{environment_description}")

        if scene and scene.atmosphere:
            parts.append(f"氛围：{scene.atmosphere}")

        return "\n".join(parts)

    def _generate_camera(
        self,
        shot_type: str,
        camera_movement: str = "",
        focal_length: str = ""
    ) -> str:
        """生成光学与摄影机调度描述"""
        parts = []

        shot_cn = self.SHOT_TYPES.get(shot_type, shot_type)
        parts.append(f"景别：{shot_cn}")

        if camera_movement:
            parts.append(f"镜头运动：{camera_movement}")

        if focal_length:
            parts.append(f"焦段：{focal_length}")
        elif shot_type in self.LENS_FOCAL_LENGTHS:
            parts.append(f"焦段：{self.LENS_FOCAL_LENGTHS[shot_type]}")

        return "\n".join(parts)

    def generate_prompt(
        self,
        scene_description: str,
        characters: Optional[List[CharacterSpec]] = None,
        scene: Optional[SceneSpec] = None,
        shot_type: str = "medium",
        emotion: str = "default",
        camera_movement: str = "",
        duration: int = 15,
        style: str = "",
        sound_effects: str = "",
        dialogue: str = "",
        tech_params: str = "16:9, 24fps",
        end_frame: Optional[EndFrameDescription] = None,
        asset_references: Optional[List[str]] = None,
        use_enhanced_timeline: bool = True,
    ) -> Dict[str, Any]:
        """生成完整的Seedance 2.0提示词（增强版）

        Args:
            scene_description: 场景描述（动作、情节）
            characters: 角色规格列表
            scene: 场景规格
            shot_type: 镜头类型
            emotion: 情绪状态
            camera_movement: 相机运动
            duration: 视频时长（秒）
            style: 风格（可选，覆盖默认）
            sound_effects: 音效描述
            dialogue: 对白描述
            tech_params: 技术参数（如"16:9, 24fps"）
            end_frame: 尾帧描述（用于shot间衔接）
            asset_references: 素材引用列表
            use_enhanced_timeline: 是否使用增强时间轴（默认True）

        Returns:
            包含五维结构的字典
        """
        characters = characters or []
        style = style or self.default_style

        # 时间轴（增强版：每5秒一段，或传统每3秒一段）
        segment_duration = 5 if use_enhanced_timeline else 3
        time_segments = duration // segment_duration

        if use_enhanced_timeline:
            timeline = self.generate_timeline_segments(
                scene_description=scene_description,
                duration=duration,
                segment_duration=segment_duration,
                camera_movement=camera_movement,
                sound_effects=sound_effects,
                dialogue=dialogue,
            )
        else:
            # 传统时间轴（保持兼容性）
            timeline = []
            for i in range(time_segments):
                start = i * segment_duration
                end = (i + 1) * segment_duration
                timeline.append(TimelineSegment(
                    time_range=f"{start}-{end}秒",
                    description=f"镜头{i+1}：情节推进",
                    sound_effects=sound_effects,
                    dialogue=dialogue if i == time_segments - 1 else ""
                ))

        result = {
            "tech_params": tech_params,
            "style": style,
            "duration": duration,
            "absolute_subject_motion": self._generate_subject_motion(
                characters,
                scene_description,
                emotion=emotion
            ),
            "environment_light_mood": self._generate_environment(
                scene,
                scene_description
            ),
            "optical_camera": self._generate_camera(shot_type, camera_movement),
            "timeline_evolution": self._format_timeline(timeline),
            "sound_effects": sound_effects,
            "aesthetic_rendering": f"质感：{style}，{self.RENDER_PARAMS}"
        }

        # 尾帧描述（用于shot间衔接）
        if end_frame:
            result["end_frame"] = self.format_end_frame(end_frame)

        # 素材引用
        if asset_references:
            result["asset_references"] = "\n".join(asset_references)

        return result

    def generate_frame_prompts(
        self,
        frame_sequence: List[Dict[str, str]],
        characters: Optional[List[CharacterSpec]] = None,
        scene: Optional[SceneSpec] = None,
        style: str = ""
    ) -> List[FramePrompt]:
        """生成帧级提示词序列"""
        characters = characters or []
        style = style or self.default_style
        frame_prompts = []

        for frame in frame_sequence:
            frame_type = frame.get("frame_type", "key_frame")
            time_range = frame.get("time", "0-5s")
            description = frame.get("description", "")

            prompt_parts = []

            if characters:
                char_desc = "，".join([c.to_subject_description() for c in characters])
                prompt_parts.append(f"人物：{char_desc}")

            if scene:
                prompt_parts.append(f"场景：{scene.to_environment_description()}")

            if description:
                prompt_parts.append(f"动作：{description}")

            prompt_parts.append(f"风格：{style}，{self.RENDER_PARAMS}")

            frame_prompts.append(FramePrompt(
                frame_type=frame_type,
                time_range=time_range,
                prompt_text="，".join(prompt_parts)
            ))

        return frame_prompts

    def generate_from_template(
        self,
        template_name: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """从预定义模板生成提示词"""
        templates = {
            "对峙沉默": {
                "tech_params": "16:9, 24fps, 15秒",
                "style": "高度写实风格",
                "absolute_subject_motion": "二人相隔数步无言对视，脊背挺直，表情凝重",
                "environment_light_mood": "太虚宗演武场，清晨薄雾，金色侧逆光，明暗对比强烈",
                "optical_camera": "景别：过肩双人中景 → 面容特写，焦段：85mm人像镜头",
                "timeline_evolution": "0-5秒：双人对视中景\n5-10秒：缓慢推近面部\n10-15秒：定格特写",
                "sound_effects": "风声、衣物摩擦声，呼吸声",
                "aesthetic_rendering": "8K超清，电影级画质，精细渲染"
            },
            "誓言宣告": {
                "tech_params": "16:9, 24fps, 15秒",
                "style": "高度写实风格",
                "absolute_subject_motion": "主角挺胸抬头，目光坚定，手握信物，缓缓开口",
                "environment_light_mood": "测灵台前，晨光笼罩，薄雾升腾，庄严神圣",
                "optical_camera": "景别：中景 → 特写，焦段：50mm标准镜头",
                "timeline_evolution": "0-5秒：全身中景\n5-10秒：手部特写\n10-15秒：面部特写",
                "sound_effects": "风声、低沉配乐、誓言回响",
                "aesthetic_rendering": "8K超清，电影级画质，精细渲染"
            },
            "退婚羞辱": {
                "tech_params": "16:9, 24fps, 15秒",
                "style": "高度写实风格",
                "absolute_subject_motion": "素白长裙女子缓步向前，玉手轻抬展示玉佩，松手碎裂，转身离去",
                "environment_light_mood": "太虚宗演武场清晨，冷白色轮廓光，高傲决绝氛围",
                "optical_camera": "景别：跟随全身 → 手部特写 → 碎裂慢动作，焦段：50mm → 90mm",
                "timeline_evolution": "0-5秒：跟随拍摄\n5-10秒：玉佩特写\n10-15秒：转身离去",
                "sound_effects": "玉佩碎裂声、周围惊呼声、渐行渐远的脚步声",
                "aesthetic_rendering": "8K超清，电影级画质，精细渲染"
            }
        }

        if template_name not in templates:
            logger.warning(f"Unknown template: {template_name}, using default")
            return templates["对峙沉默"]

        template = templates[template_name]

        result = {}
        for key, value in template.items():
            result[key] = value.format(**kwargs)

        return result

    def to_seedance_prompt(self, prompt_dict: Dict[str, Any]) -> str:
        """将提示词字典转换为Seedance 2.0格式"""
        sections = []

        # 技术参数前缀
        if "tech_params" in prompt_dict:
            sections.append(f"【技术参数】\n{prompt_dict['tech_params']}")

        if "style" in prompt_dict:
            sections.append(f"【风格】\n{prompt_dict['style']}")

        if "duration" in prompt_dict:
            sections.append(f"【时长】\n{prompt_dict['duration']}秒")

        if "absolute_subject_motion" in prompt_dict:
            sections.append(f"【绝对主体与物理动势】\n{prompt_dict['absolute_subject_motion']}")

        if "environment_light_mood" in prompt_dict:
            sections.append(f"【环境场与情绪光影】\n{prompt_dict['environment_light_mood']}")

        if "optical_camera" in prompt_dict:
            sections.append(f"【光学与摄影机调度】\n{prompt_dict['optical_camera']}")

        if "timeline_evolution" in prompt_dict:
            sections.append(f"【时间轴与状态演变】\n{prompt_dict['timeline_evolution']}")

        if "sound_effects" in prompt_dict:
            sections.append(f"【声音设计】\n{prompt_dict['sound_effects']}")

        if "aesthetic_rendering" in prompt_dict:
            sections.append(f"【美学介质与底层渲染参数】\n{prompt_dict['aesthetic_rendering']}")

        if "end_frame" in prompt_dict:
            sections.append(f"【尾帧描述】（下一shot衔接）\n{prompt_dict['end_frame']}")

        if "asset_references" in prompt_dict:
            sections.append(f"【素材引用】\n{prompt_dict['asset_references']}")

        sections.append(f"【负面提示词】\n{self.NEGATIVE_PROMPT}")

        return "\n\n".join(sections)


# =============================================================================
# Factory Functions
# =============================================================================


def create_character_spec(
    name: str,
    age_appearance: str = "",
    face: str = "",
    hair: str = "",
    clothing: str = "",
    build: str = "",
    expression_range: Optional[Dict[str, str]] = None,
    accessories: str = ""
) -> CharacterSpec:
    """创建角色规格"""
    return CharacterSpec(
        name=name,
        age_appearance=age_appearance,
        face=face,
        hair=hair,
        clothing=clothing,
        build=build,
        expression_range=expression_range or {},
        accessories=accessories
    )


def create_scene_spec(
    name: str,
    location_type: str = "",
    architecture: str = "",
    exterior: str = "",
    color_palette: str = "",
    atmosphere: str = "",
    lighting: Optional[Dict[str, str]] = None
) -> SceneSpec:
    """创建场景规格

    Args:
        name: 场景名称
        location_type: 场所类型
        architecture: 建筑风格
        exterior: 室外特征
        color_palette: 色彩基调
        atmosphere: 氛围
        lighting: 光照字典

    Returns:
        SceneSpec实例
    """
    return SceneSpec(
        name=name,
        location_type=location_type,
        architecture=architecture,
        exterior=exterior,
        color_palette=color_palette,
        atmosphere=atmosphere,
        lighting=lighting or {}
    )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Data classes
    "FramePrompt",
    "TimelineSegment",
    "EndFrameDescription",
    "ContinuityPrompt",
    "CharacterSpec",
    "SceneSpec",
    # Main adapter
    "Seedance2PromptAdapter",
    # Factory functions
    "create_character_spec",
    "create_scene_spec",
    # Camera Language
    "CAMERA_LANGUAGE",
]