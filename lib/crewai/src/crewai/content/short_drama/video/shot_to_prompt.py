"""ShotToPrompt - 将 Shot 转换为 Seedance2 五维 Prompt (Enhanced)

将 Shot 对象转换为 Seedance2 视频生成所需的五维 Prompt。
增强功能：
1. 精确时间轴控制（每5秒一段）
2. 多模态参考系统
3. 多集串联尾帧衔接
4. Camera Language 关键词库

五维控制坐标系：
1. 绝对主体与物理动势
2. 环境场与情绪光影
3. 光学与摄影机调度
4. 时间轴与状态演变
5. 美学介质与底层渲染参数
"""

from typing import Optional, List, Dict, Any

from crewai.content.video.seedance_adapter import (
    Seedance2PromptAdapter,
    CharacterSpec,
    SceneSpec,
    EndFrameDescription,
    create_character_spec,
    create_scene_spec,
    CAMERA_LANGUAGE,
)
from crewai.content.short_drama.short_drama_types import Shot, ShortDramaBible


class ShotToPromptConverter:
    """将 Shot 转换为 Seedance2 五维 Prompt (增强版)

    核心功能：
    1. 根据 Shot 的角色信息创建 CharacterSpec
    2. 根据场景信息创建 SceneSpec
    3. 调用 Seedance2PromptAdapter 生成五维 Prompt
    4. 支持多模态参考
    5. 支持多集尾帧衔接
    """

    def __init__(self, default_style: str = "高度写实风格", use_enhanced_timeline: bool = True):
        """初始化转换器

        Args:
            default_style: 默认画面风格
            use_enhanced_timeline: 是否使用增强时间轴（每5秒一段）
        """
        self.adapter = Seedance2PromptAdapter(default_style=default_style)
        self.use_enhanced_timeline = use_enhanced_timeline

    def convert_shot(
        self,
        shot: Shot,
        bible: ShortDramaBible,
        location: str = "",
        time_of_day: str = "白天",
        asset_references: List[str] = None,
    ) -> str:
        """将 Shot 转换为 Seedance2 Prompt 字符串

        Args:
            shot: Shot 对象
            bible: ShortDramaBible
            location: 场景地点
            time_of_day: 时间段
            asset_references: 素材引用列表（如 ["@图片1[C01]", "@图片2[S01]"]）

        Returns:
            str: 格式化的 Seedance2 Prompt
        """
        # 构建 CharacterSpec 列表
        characters = self._build_character_specs(shot, bible)

        # 构建 SceneSpec
        scene = self._build_scene_spec(location, time_of_day, bible)

        # 调用 adapter 生成 Prompt
        prompt_dict = self.adapter.generate_prompt(
            scene_description=shot.action,
            characters=characters,
            scene=scene,
            shot_type=shot.shot_type,
            emotion=shot.emotion,
            duration=int(shot.duration_seconds),
            use_enhanced_timeline=self.use_enhanced_timeline,
            asset_references=asset_references,
        )

        # 转换为字符串
        return self.adapter.to_seedance_prompt(prompt_dict)

    def convert_shot_to_dict(
        self,
        shot: Shot,
        bible: ShortDramaBible,
        location: str = "",
        time_of_day: str = "白天",
        asset_references: List[str] = None,
    ) -> Dict[str, Any]:
        """将 Shot 转换为 Prompt 字典

        Args:
            shot: Shot 对象
            bible: ShortDramaBible
            location: 场景地点
            time_of_day: 时间段
            asset_references: 素材引用列表

        Returns:
            dict: 五维 Prompt 字典
        """
        characters = self._build_character_specs(shot, bible)
        scene = self._build_scene_spec(location, time_of_day, bible)

        return self.adapter.generate_prompt(
            scene_description=shot.action,
            characters=characters,
            scene=scene,
            shot_type=shot.shot_type,
            emotion=shot.emotion,
            duration=int(shot.duration_seconds),
            use_enhanced_timeline=self.use_enhanced_timeline,
            asset_references=asset_references,
        )

    # =============================================================================
    # 新增：多集串联功能
    # =============================================================================

    def generate_shot_end_frame(
        self,
        shot: Shot,
        bible: ShortDramaBible,
        location: str = "",
        time_of_day: str = "白天",
    ) -> EndFrameDescription:
        """为 Shot 生成尾帧描述（用于多集衔接）

        Args:
            shot: Shot 对象
            bible: ShortDramaBible
            location: 场景地点
            time_of_day: 时间段

        Returns:
            EndFrameDescription: 尾帧描述
        """
        characters = self._build_character_specs(shot, bible)
        scene = self._build_scene_spec(location, time_of_day, bible)

        return self.adapter.generate_end_frame(
            characters=characters,
            scene=scene,
            final_action=shot.action[-50:] if len(shot.action) > 50 else shot.action,
            mood=shot.emotion,
            camera_state=self._get_camera_state(shot.shot_type),
            motion_state="静止"
        )

    def generate_continuity_prompt(
        self,
        previous_end_frame: EndFrameDescription,
        episode_number: int,
        connection_type: str = "承接",
    ) -> str:
        """生成多集串联提示词

        Args:
            previous_end_frame: 上一集尾帧描述
            episode_number: 当前集号
            connection_type: 衔接类型（承接/淡入/跳切）

        Returns:
            str: 格式化的串联提示词
        """
        continuity = self.adapter.generate_continuity_prompt(
            previous_episode_end=previous_end_frame,
            episode_number=episode_number,
            connection_type=connection_type,
        )
        return self.adapter.format_continuity_prompt(continuity, episode_number)

    def _get_camera_state(self, shot_type: str) -> str:
        """根据镜头类型推断相机状态"""
        camera_states = {
            "establishing": "航拍俯视",
            "wide": "固定全景",
            "full": "固定全身",
            "medium": "固定中景",
            "medium_close": "固定中近景",
            "close_up": "固定特写",
            "extreme_close_up": "固定大特写",
        }
        return camera_states.get(shot_type, "固定镜头")

    # =============================================================================
    # 新增：多模态参考功能
    # =============================================================================

    def generate_asset_reference_for_character(
        self,
        character_name: str,
        character_id: int = 1,
        frame_type: str = "key_frame",
    ) -> str:
        """为角色生成素材引用

        Args:
            character_name: 角色名称
            character_id: 角色ID（用于编号）
            frame_type: 帧类型

        Returns:
            str: 格式化的素材引用，如 @图片1[C01] 角色名正面全身
        """
        return self.adapter.generate_asset_reference(
            asset_type="character",
            asset_id=f"{character_id:02d}",
            description=f"{character_name}正面全身"
        )

    def generate_asset_reference_for_scene(
        self,
        scene_name: str,
        scene_id: int = 1,
        frame_type: str = "key_frame",
    ) -> str:
        """为场景生成素材引用

        Args:
            scene_name: 场景名称
            scene_id: 场景ID
            frame_type: 帧类型

        Returns:
            str: 格式化的素材引用
        """
        return self.adapter.generate_asset_reference(
            asset_type="scene",
            asset_id=f"{scene_id:02d}",
            description=f"{scene_name}背景"
        )

    def convert_shots_batch(
        self,
        shots: List[Shot],
        bible: ShortDramaBible,
        scene_locations: Dict[int, str] = None,
        scene_times: Dict[int, str] = None,
    ) -> List[Dict[str, Any]]:
        """批量转换 Shot 为 Prompt

        Args:
            shots: Shot 列表
            bible: ShortDramaBible
            scene_locations: {scene_number: location}
            scene_times: {scene_number: time_of_day}

        Returns:
            list[dict]: Prompt 字典列表
        """
        scene_locations = scene_locations or {}
        scene_times = scene_times or {}

        results = []
        for shot in shots:
            location = scene_locations.get(shot.scene_number, "")
            time_of_day = scene_times.get(shot.scene_number, "白天")

            prompt_dict = self.convert_shot_to_dict(
                shot=shot,
                bible=bible,
                location=location,
                time_of_day=time_of_day,
            )
            results.append(prompt_dict)

        return results

    def _build_character_specs(
        self,
        shot: Shot,
        bible: ShortDramaBible,
    ) -> List[CharacterSpec]:
        """根据 Shot 中的角色信息构建 CharacterSpec 列表

        Args:
            shot: Shot 对象
            bible: ShortDramaBible

        Returns:
            list[CharacterSpec]: 角色规格列表
        """
        specs = []

        for char_name in shot.characters:
            profile = bible.get_character(char_name)
            if not profile:
                # 如果找不到，使用默认描述
                specs.append(create_character_spec(name=char_name))
                continue

            # 提取角色信息
            # 支持两种格式：新版 CharacterProfile 和旧版
            name = char_name

            # 外观
            age_appearance = ""
            appearance = ""
            if hasattr(profile, 'appearance') and profile.appearance:
                appearance = profile.appearance
            if hasattr(profile, 'physical') and profile.physical:
                if hasattr(profile.physical, 'age_appearance') and profile.physical.age_appearance:
                    age_appearance = profile.physical.age_appearance

            # 服装
            clothing = ""
            if hasattr(profile, 'physical') and profile.physical:
                if hasattr(profile.physical, 'usual_attire') and profile.physical.usual_attire:
                    clothing = profile.physical.usual_attire

            # 发型
            hair = ""
            if hasattr(profile, 'physical') and profile.physical:
                if hasattr(profile.physical, 'hair') and profile.physical.hair:
                    hair = profile.physical.hair

            # 表情
            expression_range = {}
            if hasattr(profile, 'physical') and profile.physical:
                if hasattr(profile.physical, 'facial_expression') and profile.physical.facial_expression:
                    expression_range = {"default": profile.physical.facial_expression}

            # 说话风格
            speech_pattern = ""
            if hasattr(profile, 'speech_pattern') and profile.speech_pattern:
                speech_pattern = profile.speech_pattern
            elif hasattr(profile, 'behavioral') and profile.behavioral:
                if hasattr(profile.behavioral, 'speech_patterns') and profile.behavioral.speech_patterns:
                    speech_pattern = profile.behavioral.speech_patterns

            specs.append(create_character_spec(
                name=name,
                age_appearance=age_appearance or appearance,
                clothing=clothing,
                hair=hair,
                expression_range=expression_range,
            ))

        return specs

    def _build_scene_spec(
        self,
        location: str,
        time_of_day: str,
        bible: ShortDramaBible,
    ) -> Optional[SceneSpec]:
        """构建 SceneSpec

        Args:
            location: 场景地点
            time_of_day: 时间段
            bible: ShortDramaBible

        Returns:
            SceneSpec 或 None
        """
        if not location:
            return None

        # 简单实现：基于地点和时间创建 SceneSpec
        lighting_map = {
            "清晨": "柔和晨光，金色暖调",
            "上午": "明亮日光，自然光",
            "中午": "强烈顶光，高对比",
            "下午": "斜阳，暖色调",
            "傍晚": "夕阳余晖，橙红光",
            "夜晚": "月光，冷色调",
            "深夜": "昏暗，冷蓝月光",
        }

        return create_scene_spec(
            name=location,
            lighting={
                "morning": lighting_map.get("清晨", "柔和光线"),
                "afternoon": lighting_map.get("下午", "自然光"),
                "evening": lighting_map.get("傍晚", "暖色调"),
                "night": lighting_map.get("夜晚", "月光"),
            },
            atmosphere=bible.tone,
        )


__all__ = ["ShotToPromptConverter"]
