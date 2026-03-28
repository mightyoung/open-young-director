# -*- encoding: utf-8 -*-
"""Seedance 2.0 Video Prompt Adapter

基于五维控制坐标系的视频提示词生成器，专为Seedance 2.0优化。

五维控制坐标系：
1. 绝对主体与物理动势：核心人物/物体的动作、运动轨迹
2. 环境场与情绪光影：场景氛围，光线色彩、情绪基调
3. 光学与摄影机调度：运镜方式、景别，焦段等专业镜头设置
4. 时间轴与状态演变：动作发生的时间段、形态变化过程
5. 美学介质与底层渲染参数：画面质感，渲染风格

核心设计原则："锁定已有参数，精准操控空白维度"
- 先分析素材已固定的维度（主体、环境、光影）
- 不对这些维度做重复描述
- 仅针对空白维度下达精准指令
- 让AI解放全部算力专注于画面优化

Usage:
    adapter = Seedance2PromptAdapter()

    # 基于场景描述生成提示词
    prompt = adapter.generate_prompt(
        scene_description="韩林立于演武场边缘，清晨薄雾中抬眸望向测灵台",
        characters=["韩林"],
        shot_type="establishing"
    )

    # 基于角色profile和环境生成提示词
    prompt = adapter.generate_from_profile(
        characters=[char_profile],
        scene=scene_profile,
        timeline=[
            {"time": "0-3s", "description": "航拍全景..."},
            {"time": "3-5s", "description": "聚焦韩林..."},
        ]
    )
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FramePrompt:
    """单帧提示词"""
    frame_type: str  # start_frame, key_frame, end_frame
    time_range: str  # 0-3s
    prompt_text: str


@dataclass
class TimelineSegment:
    """时间轴片段"""
    time_range: str  # 0-3s
    description: str
    camera: str = ""  # 镜头运动
    lens: str = ""  # 焦段
    mood: str = ""  # 情绪


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
        if time_of_day in self.lighting:
            parts.append(self.lighting[time_of_day])
        elif self.lighting:
            first_time = list(self.lighting.keys())[0]
            parts.append(self.lighting[first_time])
        return "，".join(parts)


class Seedance2PromptAdapter:
    """Seedance 2.0 视频提示词适配器

    基于五维控制坐标系生成精准的AI视频提示词，
    遵循"锁定已有参数，精准操控空白维度"原则。
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

    def __init__(self, default_style: str = "高度写实风格"):
        """初始化适配器

        Args:
            default_style: 默认画面风格
        """
        self.default_style = default_style

    def _format_timeline(self, segments: List[TimelineSegment]) -> str:
        """格式化时间轴"""
        lines = []
        for seg in segments:
            line = f"{seg.time_range}：{seg.description}"
            if seg.camera:
                line += f"，镜头：{seg.camera}"
            if seg.lens:
                line += f"，焦段：{seg.lens}"
            if seg.mood:
                line += f"，情绪：{seg.mood}"
            lines.append(line)
        return "\n".join(lines)

    def _generate_subject_motion(
        self,
        characters: List[CharacterSpec],
        action_description: str,
        motion_track: Optional[str] = None
    ) -> str:
        """生成绝对主体与物理动势描述"""
        parts = []

        # 角色描述
        char_descs = [c.to_subject_description() for c in characters]
        if len(char_descs) == 1:
            parts.append(f"人物：{char_descs[0]}")
        else:
            parts.append(f"人物：{'，'.join(char_descs)}")

        # 动作轨迹
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

        # 场景
        if scene:
            env_desc = scene.to_environment_description(time_of_day.lower())
            parts.append(f"场景：{env_desc}")
        elif environment_description:
            parts.append(f"场景：{environment_description}")

        # 氛围
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
        characters: List[CharacterSpec] = None,
        scene: SceneSpec = None,
        shot_type: str = "medium",
        emotion: str = "default",
        camera_movement: str = "",
        duration: int = 10,
        style: str = ""
    ) -> Dict[str, Any]:
        """生成完整的Seedance 2.0提示词

        Args:
            scene_description: 场景描述（动作、情节）
            characters: 角色规格列表
            scene: 场景规格
            shot_type: 镜头类型
            emotion: 情绪状态
            camera_movement: 相机运动
            duration: 视频时长（秒）
            style: 风格（可选，覆盖默认）

        Returns:
            包含五维结构的字典
        """
        characters = characters or []
        style = style or self.default_style

        # 计算时间轴
        time_segments = duration // 5
        timeline = []
        for i in range(time_segments):
            start = i * 5
            end = (i + 1) * 5
            timeline.append(TimelineSegment(
                time_range=f"{start}-{end}秒",
                description=f"镜头{i+1}：情节推进"
            ))

        return {
            "absolute_subject_motion": self._generate_subject_motion(
                characters,
                scene_description
            ),
            "environment_light_mood": self._generate_environment(
                scene,
                scene_description
            ),
            "optical_camera": self._generate_camera(shot_type, camera_movement),
            "timeline_evolution": self._format_timeline(timeline),
            "aesthetic_rendering": f"质感：{style}，{self.RENDER_PARAMS}"
        }

    def generate_frame_prompts(
        self,
        frame_sequence: List[Dict[str, str]],
        characters: List[CharacterSpec] = None,
        scene: SceneSpec = None,
        style: str = ""
    ) -> List[FramePrompt]:
        """生成帧级提示词序列

        Args:
            frame_sequence: 帧序列 [{"frame_type": "start_frame", "time": "0-3s", "description": "..."}, ...]
            characters: 角色规格列表
            scene: 场景规格
            style: 风格

        Returns:
            FramePrompt列表
        """
        characters = characters or []
        style = style or self.default_style
        frame_prompts = []

        for frame in frame_sequence:
            frame_type = frame.get("frame_type", "key_frame")
            time_range = frame.get("time", "0-5s")
            description = frame.get("description", "")

            # 构建提示词
            prompt_parts = []

            # 主体
            if characters:
                char_desc = "，".join([c.to_subject_description() for c in characters])
                prompt_parts.append(f"人物：{char_desc}")

            # 场景/环境
            if scene:
                prompt_parts.append(f"场景：{scene.to_environment_description()}")

            # 描述
            if description:
                prompt_parts.append(f"动作：{description}")

            # 风格
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
        **kwargs
    ) -> Dict[str, Any]:
        """从预定义模板生成提示词

        Args:
            template_name: 模板名称（如"对话对峙"、"誓言宣告"等）
            **kwargs: 模板参数

        Returns:
            提示词字典
        """
        templates = {
            "对峙沉默": {
                "absolute_subject_motion": "二人相隔数步无言对视，脊背挺直，表情凝重",
                "environment_light_mood": "太虚宗演武场，清晨薄雾，金色侧逆光，明暗对比强烈",
                "optical_camera": "景别：过肩双人中景 → 面容特写，焦段：85mm人像镜头",
                "timeline_evolution": "0-2秒：双人对视中景\n2-4秒：缓慢推近面部\n4-6秒：定格特写",
                "aesthetic_rendering": "高度写实风格，8K超清，电影级画质"
            },
            "誓言宣告": {
                "absolute_subject_motion": "主角挺胸抬头，目光坚定，手握信物，缓缓开口",
                "environment_light_mood": "测灵台前，晨光笼罩，薄雾升腾，庄严神圣",
                "optical_camera": "景别：中景 → 特写，焦段：50mm标准镜头",
                "timeline_evolution": "0-3秒：全身中景\n3-5秒：手部特写\n5-8秒：面部特写",
                "aesthetic_rendering": "高度写实风格，8K超清，电影级画质"
            },
            "退婚羞辱": {
                "absolute_subject_motion": "素白长裙女子缓步向前，玉手轻抬展示玉佩，松手碎裂，转身离去",
                "environment_light_mood": "太虚宗演武场清晨，冷白色轮廓光，高傲决绝氛围",
                "optical_camera": "景别：跟随全身 → 手部特写 → 碎裂慢动作，焦段：50mm → 90mm",
                "timeline_evolution": "0-3秒：跟随拍摄\n3-5秒：玉佩特写\n5-7秒：碎裂慢动作\n7-10秒：转身离去",
                "aesthetic_rendering": "高度写实风格，8K超清，电影级画质"
            }
        }

        if template_name not in templates:
            logger.warning(f"Unknown template: {template_name}, using default")
            return templates["对峙沉默"]

        template = templates[template_name]

        # 替换变量
        result = {}
        for key, value in template.items():
            result[key] = value.format(**kwargs)

        return result

    def to_seedance_prompt(self, prompt_dict: Dict[str, Any]) -> str:
        """将提示词字典转换为Seedance 2.0格式

        Args:
            prompt_dict: generate_prompt返回的字典

        Returns:
            格式化的提示词字符串
        """
        sections = []

        if "absolute_subject_motion" in prompt_dict:
            sections.append(f"【绝对主体与物理动势】\n{prompt_dict['absolute_subject_motion']}")

        if "environment_light_mood" in prompt_dict:
            sections.append(f"【环境场与情绪光影】\n{prompt_dict['environment_light_mood']}")

        if "optical_camera" in prompt_dict:
            sections.append(f"【光学与摄影机调度】\n{prompt_dict['optical_camera']}")

        if "timeline_evolution" in prompt_dict:
            sections.append(f"【时间轴与状态演变】\n{prompt_dict['timeline_evolution']}")

        if "aesthetic_rendering" in prompt_dict:
            sections.append(f"【美学介质与底层渲染参数】\n{prompt_dict['aesthetic_rendering']}")

        return "\n\n".join(sections)


def create_character_spec(
    character_id: str,
    name: str,
    age_appearance: str = "",
    face: str = "",
    hair: str = "",
    clothing: str = "",
    build: str = "",
    expression_range: Dict[str, str] = None,
    accessories: str = ""
) -> CharacterSpec:
    """从角色profile创建CharacterSpec"""
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
    scene_id: str,
    name: str,
    location_type: str = "",
    architecture: str = "",
    exterior: str = "",
    color_palette: str = "",
    atmosphere: str = "",
    lighting: Dict[str, str] = None
) -> SceneSpec:
    """从场景profile创建SceneSpec"""
    return SceneSpec(
        name=name,
        location_type=location_type,
        architecture=architecture,
        exterior=exterior,
        color_palette=color_palette,
        atmosphere=atmosphere,
        lighting=lighting or {}
    )
