# -*- encoding: utf-8 -*-
"""Video Consumer - generates video scripts and storyboards from raw scene data."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseConsumer
from media.minimax_executor import get_media_executor

logger = logging.getLogger(__name__)


@dataclass
class VideoScene:
    """A single scene in the video script."""

    description: str  # Visual description for the scene
    duration: int  # Duration in seconds
    visual: str  # Visual direction (camera angle, movement, etc.)
    narration: str = ""  # Voiceover narration for this scene
    dialogue: str = ""  # Character dialogue
    music_cue: str = ""  # Music suggestion for this scene


class VideoConsumer(BaseConsumer):
    """Video consumer - generates video scripts and storyboards.

    Transforms FILM_DRAMA scene data into video production content with:
    - Title
    - Scene breakdown with visual directions
    - Narration script
    - Music suggestions

    Output format:
        dict: {
            "title": str,
            "scenes": list of VideoScene dicts,
            "narration": str,
            "music_suggestions": list of str,
            "total_duration": int (seconds),
            "genre": str,
            "media_urls": list of str (optional, if generate_media=True),
            "media_result": dict (optional, if generate_media=True)
        }
    """

    # Class-level attribute for lazy initialization
    _media_executor = None

    # Genre-specific visual styles (used as base context)
    GENRE_STYLES = {
        "xianxia": {
            "camera": "dynamic, floating, aerial shots",
            "color": "ethereal, misty, with jade and gold accents",
            "visual": "floating islands, ancient temples, cultivation realms",
        },
        "wuxia": {
            "camera": "fluid, sweeping martial arts choreography",
            "color": "ink wash, muted earth tones",
            "visual": "mountain tops, forests, martial arts arenas",
        },
        "modern": {
            "camera": "close-ups, urban perspectives",
            "color": "contemporary, vibrant",
            "visual": "modern cities, universities, corporations",
        },
    }

    # =============================================================================
    # 镜头语言库
    # =============================================================================

    # 基础镜头类型术语（中英对照，供AI精确理解）
    SHOT_TYPES = {
        # 按景别
        "极远景": {"abbrev": "ELS", "description": "Extreme Long Shot - 建立场景全貌，通常用于片头或转场"},
        "远景": {"abbrev": "LS", "description": "Long Shot - 展示角色与环境关系"},
        "全景": {"abbrev": "WS", "description": "Wide Shot / Full Shot - 完整展示角色全身"},
        "中景": {"abbrev": "MS", "description": "Medium Shot - 膝盖以上，叙事主力镜头"},
        "中近景": {"abbrev": "MCS", "description": "Medium Close-Up - 腰部到肩部"},
        "特写": {"abbrev": "CU", "description": "Close-Up - 面部为主"},
        "大特写": {"abbrev": "ECU", "description": "Extreme Close-Up - 眼睛、嘴唇等细节"},
        # 按角度
        "仰视": {"abbrev": "LU", "description": "Low Angle - 仰拍，显得角色高大威严"},
        "俯视": {"abbrev": "HA", "description": "High Angle - 俯拍，显得角色渺小脆弱"},
        "鸟瞰": {"abbrev": "TOP", "description": "Bird's Eye - 正上方俯拍，展现平面布局"},
        "倾斜": {"abbrev": "Dutch", "description": "Dutch Angle / Canted Frame - 斜角，制造不安或动感"},
        # 按运动
        "推轨": {"abbrev": "Dolly", "description": "摄影机沿轨道推进或拉离"},
        "摇镜": {"abbrev": "Pan", "description": "水平旋转，展现广度"},
        "俯仰": {"abbrev": "Tilt", "description": "垂直旋转，由上往下或由下往上"},
        "跟随": {"abbrev": "Follow", "description": "跟随主体移动，保持构图"},
        "伸缩": {"abbrev": "Crane", "description": "摇臂升降，大范围空间运动"},
        "手持": {"abbrev": "Handheld", "description": "手持跟拍，纪实感强"},
        "稳定器": {"abbrev": "Steadicam", "description": "稳定器跟拍，流畅运动"},
        "希区柯克": {"abbrev": "Zoom", "description": "光学推焦（焦距变化），不改变物理位置"},
    }

    # 场景类型驱动的镜头语言（详细化）
    # 包含：景别、镜头焦距、运动方式、角度、对焦、速度、特效
    SCENE_TYPE_CAMERA_LANGUAGE = {
        "战斗激烈": {
            "shots": ["远景", "全景", "中景"],
            "lens": "广角镜头（14-35mm），近距离搏斗可用中焦（50mm）",
            "movement": "手持跟拍+快速推轨，摄影机紧贴动作",
            "angles": "低角度仰拍为主，45度侧拍补充",
            "focus": "追踪对焦+区域对焦，虚化前景增加层次",
            "speed": "正常速度30%，关键帧升格至200%",
            "特效": "速度线、冲击波、镜头光晕、动态模糊",
        },
        "战斗前兆": {
            "shots": ["全景", "中景", "特写"],
            "lens": "长焦（85-135mm）压缩空间感",
            "movement": "缓慢推近，蓄力感",
            "angles": "正面平视+轻微仰视，营造对峙张力",
            "focus": "浅景深，焦点在主体眼神",
            "speed": "正常或减慢50%",
            "特效": "微速摄影、气氛光效、轻微镜头光晕",
        },
        "招式释放": {
            "shots": ["中景", "特写", "大特写"],
            "lens": "中焦至长焦（50-135mm）",
            "movement": "定格后快速推近，或极慢拉远展现威力范围",
            "angles": "低角度仰视+侧拍结合",
            "focus": "从主体快速切换至效果落点",
            "speed": "极慢升格（400-800%）展现过程",
            "特效": "能量波、爆破、碎片、颜色调色（冷暖对比）",
        },
        "对话平静": {
            "shots": ["中景", "中近景", "特写"],
            "lens": "标准焦距（50-85mm），还原真实透视",
            "movement": "固定或轻微摇镜，无突兀运动",
            "angles": "视线高度平拍，正反打",
            "focus": "浅景深F1.4-2.8，焦点锁定当前说话者",
            "speed": "正常速度24fps",
            "特效": "无或极简，依赖演员表演",
        },
        "对话紧张": {
            "shots": ["中景", "中近景", "特写"],
            "lens": "中焦（50mm）为主",
            "movement": "轻微手持增加不稳定感",
            "angles": "略微俯/仰打破平衡，暗示权力关系变化",
            "focus": "浅景深，焦点在说话者间切换",
            "speed": "正常或稍快（制造紧迫感）",
            "特效": "浅景深暗角，增强压迫感",
        },
        "对话高潮": {
            "shots": ["特写", "大特写"],
            "lens": "长焦（85-135mm）",
            "movement": "极慢推近，每一帧都是表情",
            "angles": "极端仰/俯，情绪外化",
            "focus": "单眼对焦，眼神成为叙事核心",
            "speed": "减慢25-50%",
            "特效": "散景、柔焦、边缘暗角",
        },
        "情感思念": {
            "shots": ["特写", "大特写", "极远景"],
            "lens": "长焦（85mm以上）",
            "movement": "极慢推近或不运动，靠演员表演",
            "angles": "侧脸或四分之三脸，背光营造氛围",
            "focus": "浅景深，背景光斑散景",
            "speed": "减慢50%",
            "特效": "柔焦、散景、慢速烟尘粒子",
        },
        "情感悲伤": {
            "shots": ["中近景", "特写"],
            "lens": "中焦（50-85mm）",
            "movement": "固定镜头，靠演员走位",
            "angles": "轻微俯拍，强化压抑情绪",
            "focus": "中景深，保留环境暗示",
            "speed": "正常或稍慢",
            "特效": "蓝冷色调、散景暗角",
        },
        "情感燃向": {
            "shots": ["全景", "中景", "特写"],
            "lens": "广角（24-35mm）展现气势",
            "movement": "快速推近、环绕跟拍",
            "angles": "低角度仰视为主",
            "focus": "追踪对焦",
            "speed": "正常速度，关键瞬间升格100-200%",
            "特效": "速度线、光芒效果、慢动作烟尘",
        },
        "过场环境": {
            "shots": ["极远景", "远景"],
            "lens": "广角（14-35mm）",
            "movement": "缓慢横移或升降，建立世界感",
            "angles": "客观视角，平行或轻微俯拍",
            "focus": "深景深F8-11，环境与角色同样清晰",
            "speed": "正常或极慢",
            "特效": "无",
        },
        "过场转场": {
            "shots": ["远景", "全景"],
            "lens": "根据转场方向选择",
            "movement": "与下一个场景运动方向匹配，实现无缝衔接",
            "angles": "中性",
            "focus": "深景深",
            "speed": "正常",
            "特效": "渐变、叠化或硬切",
        },
        "追逐": {
            "shots": ["全景", "中景", "第一视角"],
            "lens": "广角（18-35mm）增强速度感",
            "movement": "跟拍+手持结合，贴近主体",
            "angles": "低角度仰视，地面反射增强速度",
            "focus": "追踪对焦，焦点跟随主体",
            "speed": "正常+局部加速（快进感）",
            "特效": "速度线、动态模糊、广角畸变",
        },
        "危险/惊悚": {
            "shots": ["中景", "特写", "大特写"],
            "lens": "长焦（85mm以上）压缩空间",
            "movement": "手持轻微晃动，呼吸感",
            "angles": "斜角构图，打破平衡",
            "focus": "浅景深，暗示未知",
            "speed": "正常，关键瞬间降速",
            "特效": "暗角、闪黑、红蓝调色",
        },
        "神秘/悬疑": {
            "shots": ["全景", "中景", "特写"],
            "lens": "长焦（85mm以上）压缩空间",
            "movement": "缓慢推近或摇镜，探索感",
            "angles": "仰拍制造高大感，俯拍表现脆弱",
            "focus": "逐焦，从环境过渡到主体",
            "speed": "减慢50%",
            "特效": "暗角、浅焦、烟雾、低对比色调",
        },
        "浪漫": {
            "shots": ["中近景", "特写"],
            "lens": "标准至长焦（50-85mm）",
            "movement": "极慢推近，凝视感",
            "angles": "侧光或背光，制造轮廓光",
            "focus": "极浅景深，全身虚化",
            "speed": "正常或减慢",
            "特效": "柔焦、散景光斑、暖色调",
        },
        "回忆": {
            "shots": ["中景", "特写"],
            "lens": "中焦（50-85mm）",
            "movement": "固定镜头",
            "angles": "平视，客观叙述感",
            "focus": "中景深，保留环境线索",
            "speed": "正常",
            "特效": "褪色色调、划痕效果、柔焦",
        },
    }

    # 备用基础版（用于未分类场景）
    SCENE_TYPE_CAMERA_LANGUAGE["过场"] = SCENE_TYPE_CAMERA_LANGUAGE["过场环境"]
    SCENE_TYPE_CAMERA_LANGUAGE["混合"] = SCENE_TYPE_CAMERA_LANGUAGE["战斗激烈"]
    SCENE_TYPE_CAMERA_LANGUAGE["战斗"] = SCENE_TYPE_CAMERA_LANGUAGE["战斗激烈"]
    SCENE_TYPE_CAMERA_LANGUAGE["对话"] = SCENE_TYPE_CAMERA_LANGUAGE["对话平静"]
    SCENE_TYPE_CAMERA_LANGUAGE["情感"] = SCENE_TYPE_CAMERA_LANGUAGE["情感燃向"]

    @property
    def consumer_type(self) -> str:
        """Return consumer type."""
        return "video"

    @property
    def media_executor(self):
        """Get or create the MiniMaxMediaExecutor instance.

        Returns:
            MiniMaxMediaExecutor singleton instance
        """
        if self._media_executor is None:
            self._media_executor = get_media_executor()
        return self._media_executor

    async def query(self, scene_id: str, **kwargs) -> Dict[str, Any]:
        """Query raw scene data for video generation.

        Args:
            scene_id: The scene identifier
            **kwargs: Additional query parameters

        Returns:
            Raw scene data dictionary
        """
        if self.scene_store is None:
            raise ValueError("scene_store not configured")

        scene_data = await self.scene_store.get_scene(scene_id)

        if not scene_data:
            raise ValueError(f"Scene not found: {scene_id}")

        return scene_data

    async def generate(self, raw_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Generate video script from raw scene data.

        Args:
            raw_data: Raw scene data containing:
                - beats: Plot beats with character interactions
                - character_states: Character states
                - scene_descriptions: Visual scene descriptions
                - narration_pieces: Narration fragments
                - emotional_arc: Emotional arc
            **kwargs: Additional generation parameters:
                - genre: Video genre (default: "xianxia")
                - format: "short" (1-3 min) or "long" (5-15 min)
                - aspect_ratio: "16:9", "9:16", or "1:1"
                - generate_media: Whether to generate actual video (default: True)

        Returns:
            dict with keys: title, scenes, narration, music_suggestions,
            total_duration, genre, media_urls, media_result (if generate_media=True)
        """
        if self.llm_client is None:
            raise ValueError("llm_client not configured")

        # Extract components
        beats = raw_data.get("beats", [])
        character_states = raw_data.get("character_states", {})
        scene_descriptions = raw_data.get("scene_descriptions", [])
        narration_pieces = raw_data.get("narration_pieces", [])
        emotional_arc = raw_data.get("emotional_arc", {})
        chapter_info = raw_data.get("chapter_info", {})
        background = raw_data.get("background", "")

        genre = kwargs.get("genre", "xianxia")
        video_format = kwargs.get("format", "short")
        aspect_ratio = kwargs.get("aspect_ratio", "16:9")
        generate_media = kwargs.get("generate_media", True)

        # Determine duration based on format
        if video_format == "short":
            duration_target = 90  # 1.5 minutes
        else:
            duration_target = 300  # 5 minutes

        # Build generation prompt
        prompt = self._build_video_prompt(
            beats=beats,
            character_states=character_states,
            scene_descriptions=scene_descriptions,
            narration_pieces=narration_pieces,
            emotional_arc=emotional_arc,
            chapter_info=chapter_info,
            background=background,
            genre=genre,
            duration_target=duration_target,
            aspect_ratio=aspect_ratio,
            **kwargs,
        )

        # Generate video script
        messages = [{"role": "user", "content": prompt}]
        script_text = self.llm_client.generate(messages)

        # Parse into structured scenes
        scenes = self._parse_scenes(script_text, duration_target, genre)

        # Generate main narration
        narration = self._generate_narration(narration_pieces, scenes)

        # Generate music suggestions based on genre and emotional arc
        music_suggestions = self._generate_music_suggestions(genre, emotional_arc)

        # Calculate total duration
        total_duration = sum(s.duration for s in scenes)

        # Build result
        result = {
            "title": self._generate_title(chapter_info, beats, genre),
            "scenes": [s.__dict__ for s in scenes],
            "narration": narration,
            "music_suggestions": music_suggestions,
            "total_duration": total_duration,
            "genre": genre,
            "aspect_ratio": aspect_ratio,
        }

        # Generate actual video if requested
        media_result = None
        media_urls = []
        if generate_media:
            try:
                media_result = await self._generate_video(result, genre)
                if media_result and media_result.get("success"):
                    video_url = media_result.get("video_url")
                    if video_url:
                        media_urls.append(video_url)
                    result["media_result"] = media_result
                    result["media_urls"] = media_urls
            except Exception as e:
                logger.warning(f"Video generation failed: {e}")
                result["media_result"] = {"success": False, "error": str(e)}
                result["media_urls"] = []

        return result

    async def _generate_video(self, script_data: Dict[str, Any], genre: str) -> Dict[str, Any]:
        """Generate actual video using MiniMax API.

        Args:
            script_data: Generated script data containing scenes and narration
            genre: Video genre

        Returns:
            dict with video generation result
        """
        # Build video prompt from script data
        title = script_data.get("title", "")
        scenes = script_data.get("scenes", [])
        narration = script_data.get("narration", "")

        # Create a combined prompt for video generation
        scene_descriptions = []
        for scene in scenes[:5]:  # Use first 5 scenes
            desc = scene.get("description", "")
            visual = scene.get("visual", "")
            if desc or visual:
                scene_descriptions.append(f"{desc} {visual}".strip())

        prompt = f"{title}. "
        if scene_descriptions:
            prompt += " ".join(scene_descriptions)
        else:
            prompt += narration[:500] if narration else "Chinese fantasy scene"

        return await self.media_executor.generate_video(
            prompt=prompt,
            model="MiniMax-Hailuo-02",
            duration=6,
            wait_for_completion=True,
        )

    def _build_video_prompt(
        self,
        beats: List[Dict],
        character_states: Dict[str, List],
        scene_descriptions: List[str],
        narration_pieces: List[str],
        emotional_arc: Dict,
        chapter_info: Dict,
        background: str,
        genre: str,
        duration_target: int,
        aspect_ratio: str,
        **kwargs,
    ) -> str:
        """Build the video script generation prompt.

        Args:
            beats: Plot beats
            character_states: Character states
            scene_descriptions: Scene visuals
            narration_pieces: Narration fragments
            emotional_arc: Emotional arc
            chapter_info: Chapter metadata
            background: Story background
            genre: Video genre
            duration_target: Target duration in seconds
            aspect_ratio: Aspect ratio
            **kwargs: Additional parameters

        Returns:
            Formatted prompt string
        """
        style = self.GENRE_STYLES.get(genre, self.GENRE_STYLES["xianxia"])

        # Format beats
        beats_text = self._format_beats(beats)

        # Format character states (includes appearance when available)
        chars_text = self._format_character_states(character_states)

        # Extract character appearance details for dedicated section
        # This gives the LLM clear physical description to maintain visual consistency
        char_appearance_text = self._format_character_appearances(character_states)

        # Build scene-type camera guidance based on dominant scene type
        camera_guidance_text = self._format_scene_type_camera_guidance(beats)

        # Format emotional arc
        arc_text = ""
        if emotional_arc:
            arc_text = f"""
情感曲线:
- 起始: {emotional_arc.get('start_state', '平静')}
- 高潮: {emotional_arc.get('peak_state', '紧张')}
- 结束: {emotional_arc.get('end_state', '舒缓')}
"""

        chapter_context = ""
        if chapter_info:
            chapter_context = f"""
章节信息:
- 章节号: {chapter_info.get('chapter_number', '未知')}
- 章节标题: {chapter_info.get('title', '未知')}
"""

        prompt = f"""<identity>
你是一个资深视频分镜师，擅长将故事内容转化为视觉化的视频脚本。
你熟悉各种视频平台的热门内容形式。
</identity>

<context>
{chapter_context}

风格类型: {genre}
目标时长: 约{duration_target}秒
画面比例: {aspect_ratio}

视觉风格:
- 镜头: {style['camera']}
- 色调: {style['color']}
- 场景: {style['visual']}
</context>

<source_material>
情节发展:
{beats_text}

镜头语言指导（根据场景类型）:
{camera_guidance_text}

角色外貌（视觉一致性参考）:
{char_appearance_text}

角色状态:
{chars_text}

场景描述:
{chr(10).join(f"- {d}" for d in scene_descriptions[:5])}

情感曲线:
{arc_text}
</source_material>

<requirements>
输出格式要求（严格遵循）:

【场景1】
时长: XX秒
画面描述: 具体描述这个场景要拍什么
视觉指导: 镜头角度、运动方式、特效等
旁白: （如有）此场景的旁白内容
对话: （如有）角色对话内容
音乐提示: （可选）此场景的背景音乐建议

【场景2】
...以此类推

重要规则:
1. 每个场景时长控制在10-30秒
2. 画面描述要具体，便于拍摄执行
3. 视觉指导要包含镜头运动和风格
4. 旁白控制在30字以内
5. 对话控制在50字以内
6. 直接输出分镜内容，不要说明
7. 不要使用占位符
</requirements>

请生成视频分镜脚本:
"""
        return prompt

    def _format_beats(self, beats: List[Dict]) -> str:
        """Format beats for video script.

        Args:
            beats: List of plot beats

        Returns:
            Formatted beats text
        """
        if not beats:
            return "（无具体情节）"

        lines = []
        for i, beat in enumerate(beats, 1):
            beat_type = beat.get("beat_type", "unknown")
            description = beat.get("description", "")
            characters = beat.get("expected_chars", [])

            char_str = "、".join(characters) if characters else "无"
            lines.append(f"{i}. [{beat_type}] {description}")
            lines.append(f"   出场: {char_str}")

        return "\n".join(lines)

    def _format_character_states(
        self, character_states: Dict[str, List]
    ) -> str:
        """Format character states for video context.

        Args:
            character_states: Dict of character_name -> states list.
                Each state may include: emotional_state, physical_state, appearance.

        Returns:
            Formatted character states text with appearance included.
        """
        if not character_states:
            return "（无角色状态信息）"

        lines = []
        for char_name, states in character_states.items():
            if states:
                latest_state = states[-1]  # Most recent state
                emotional = latest_state.get("emotional_state", "未知")
                physical = latest_state.get("physical_state", "未知")
                appearance = latest_state.get("appearance", "")
                if appearance:
                    lines.append(f"- {char_name}: 情绪{emotional}, 状态{physical}, 外貌:{appearance}")
                else:
                    lines.append(f"- {char_name}: 情绪{emotional}, 状态{physical}")

        return "\n".join(lines) if lines else "（无角色状态信息）"

    def _format_character_appearances(
        self, character_states: Dict[str, List]
    ) -> str:
        """Extract and format character appearance descriptions for visual consistency.

        This provides a dedicated section so the LLM has clear physical descriptions
        to maintain character consistency across scenes.

        Args:
            character_states: Dict of character_name -> states list.
                States may include an 'appearance' string built from:
                height, build, hair, eye_color, skin, expression, clothing.

        Returns:
            Formatted character appearance text.
        """
        if not character_states:
            return "（无角色外貌信息）"

        lines = []
        for char_name, states in character_states.items():
            if states:
                latest_state = states[-1]
                appearance = latest_state.get("appearance", "")
                if appearance:
                    lines.append(f"- {char_name}: {appearance}")

        return "\n".join(lines) if lines else "（无角色外貌信息）"

    def _format_scene_type_camera_guidance(self, beats: List[Dict]) -> str:
        """Format scene-type-driven camera language guidance.

        Analyzes the dominant scene type from beats and returns detailed camera
        language guidance that should be used as the primary reference for
        each scene's visual direction.

        Args:
            beats: List of plot beats with beat_type field.

        Returns:
            Formatted camera language guidance text with per-type details.
        """
        if not beats:
            return "（无场景类型信息）"

        # Count scene types to find dominant
        scene_types = [b.get("beat_type", "过场") for b in beats]
        type_counts: Dict[str, int] = {}
        for st in scene_types:
            type_counts[st] = type_counts.get(st, 0) + 1

        # Primary scene type (most frequent)
        primary_type = max(type_counts, key=type_counts.get)
        primary_count = type_counts[primary_type]

        # Collect all types used
        all_types = list(type_counts.keys())

        lines = []
        lines.append(f"【主要场景类型】{primary_type}（{primary_count}个场景）")
        lines.append(f"【镜头术语参考】")
        lines.append("  景别速查: 极远景(ELS) > 远景(LS) > 全景(WS) > 中景(MS) > 特写(CU) > 大特写(ECU)")
        lines.append("  角度速查: 仰拍(高大) | 俯拍(渺小) | 平拍(平等) | 斜角(不安)")

        # Only show guidance for types actually present
        for scene_type in all_types:
            if scene_type in self.SCENE_TYPE_CAMERA_LANGUAGE:
                cam = self.SCENE_TYPE_CAMERA_LANGUAGE[scene_type]
                shot_list = cam.get("shots", [])
                shots_str = "、".join(shot_list) if shot_list else "标准中景"
                lines.append(f"\n◆ {scene_type}（{type_counts[scene_type]}个场景）:")
                lines.append(f"  推荐景别: {shots_str}")
                lines.append(f"  镜头焦距: {cam['lens']}")
                lines.append(f"  运动方式: {cam['movement']}")
                lines.append(f"  拍摄角度: {cam['angles']}")
                lines.append(f"  对焦策略: {cam['focus']}")
                lines.append(f"  速度处理: {cam['speed']}")
                if cam.get("特效"):
                    lines.append(f"  视觉特效: {cam['特效']}")

        # Add switching guidance for mixed scenes
        if len(all_types) > 1:
            lines.append(f"\n◆ 多场景切换原则:")
            lines.append("  在不同场景类型间切换时，镜头语言需平滑过渡")
            lines.append("  战斗→对话：先以动作结尾，再切换至平稳镜头")
            lines.append("  对话→战斗：以对白最后一句的节奏感引入动作")
            lines.append("  情感→战斗：以表情特写蓄力，再爆发")

        return "\n".join(lines)

    def _parse_scenes(
        self, script_text: str, duration_target: int, genre: str
    ) -> List[VideoScene]:
        """Parse generated script into structured VideoScene objects.

        Args:
            script_text: Generated script text
            duration_target: Target total duration
            genre: Video genre

        Returns:
            List of VideoScene objects
        """
        scenes = []

        # Simple parsing - split by scene markers
        # In production, could use more sophisticated parsing
        current_scene = None
        current_key = None

        lines = script_text.split("\n")
        scene_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect scene header
            if "【场景" in line and "】" in line:
                if current_scene:
                    scenes.append(current_scene)

                scene_count += 1
                current_scene = VideoScene(
                    description="",
                    duration=15,  # Default duration
                    visual="",
                )
                current_key = None

            elif current_scene is not None:
                # Parse key-value pairs
                if "时长:" in line:
                    try:
                        duration = int(line.split("时长:")[1].split("秒")[0].strip())
                        current_scene.duration = duration
                    except (ValueError, IndexError):
                        pass
                elif "画面描述:" in line:
                    current_scene.description = line.split("画面描述:")[1].strip()
                elif "视觉指导:" in line:
                    current_scene.visual = line.split("视觉指导:")[1].strip()
                elif "旁白:" in line:
                    current_scene.narration = line.split("旁白:")[1].strip()
                elif "对话:" in line:
                    current_scene.dialogue = line.split("对话:")[1].strip()
                elif "音乐提示:" in line:
                    current_scene.music_cue = line.split("音乐提示:")[1].strip()

        # Add last scene
        if current_scene:
            scenes.append(current_scene)

        # If no scenes parsed, create a default one
        if not scenes:
            scenes.append(VideoScene(
                description=script_text[:200],
                duration=duration_target,
                visual="standard shot",
            ))

        return scenes

    def _generate_narration(
        self, narration_pieces: List[str], scenes: List[VideoScene]
    ) -> str:
        """Generate main narration script.

        Args:
            narration_pieces: Narration fragments from source
            scenes: Generated scenes

        Returns:
            Combined narration text
        """
        if narration_pieces:
            return " ".join(narration_pieces[:3])

        # Generate from scenes
        narrations = [s.narration for s in scenes if s.narration]
        return " ".join(narrations) if narrations else ""

    def _generate_music_suggestions(
        self, genre: str, emotional_arc: Dict
    ) -> List[str]:
        """Generate music suggestions based on genre and emotional arc.

        Args:
            genre: Video genre
            emotional_arc: Emotional arc data

        Returns:
            List of music style suggestions
        """
        suggestions = []

        # Genre-based suggestions
        genre_music = {
            "xianxia": ["古风玄幻", "仙侠飘逸", "气势磅礴"],
            "wuxia": ["武侠豪迈", "古风激昂", "江湖气息"],
            "modern": ["现代都市", "轻松活泼", "悬疑紧张"],
        }
        suggestions.extend(genre_music.get(genre, ["通用"]))

        # Emotional arc based suggestions
        if emotional_arc:
            peak = emotional_arc.get("peak_state", "")
            if "紧张" in peak or "激烈" in peak:
                suggestions.append("紧张激昂")
            elif "悲伤" in peak or "低沉" in peak:
                suggestions.append("悲伤舒缓")
            elif "欢快" in peak or "高潮" in peak:
                suggestions.append("高潮迭起")

        return list(set(suggestions))[:4]  # Dedupe and limit

    def _generate_title(
        self, chapter_info: Dict, beats: List[Dict], genre: str
    ) -> str:
        """Generate video title.

        Args:
            chapter_info: Chapter metadata
            beats: Plot beats
            genre: Video genre

        Returns:
            Generated title
        """
        chapter_title = chapter_info.get("title", "")
        if chapter_title:
            return f"【视频】{chapter_title}"

        if beats:
            first_beat = beats[0].get("description", "")[:15]
            return f"【视频】{first_beat}..."

        return "【视频】精彩片段"
