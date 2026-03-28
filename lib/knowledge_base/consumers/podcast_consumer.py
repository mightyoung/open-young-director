# -*- encoding: utf-8 -*-
"""Podcast Consumer - generates audio scripts from raw scene data."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base import BaseConsumer
from media.minimax_executor import get_media_executor

logger = logging.getLogger(__name__)


@dataclass
class Speaker:
    """Podcast speaker definition."""

    name: str
    voice: str  # e.g., "male_young", "female_mature", "narrator"
    role: str = "guest"  # "host", "guest", "narrator"


class PodcastConsumer(BaseConsumer):
    """Podcast consumer - generates audio scripts from raw scene data.

    Transforms FILM_DRAMA scene data into podcast scripts with:
    - Title and introduction
    - Dialogue script with speakers
    - Duration estimate
    - Speaker definitions

    Output format:
        dict: {
            "title": str,
            "script": str,
            "duration_estimate": int (seconds),
            "speakers": list of Speaker dicts,
            "intro": str (optional),
            "outro": str (optional),
            "media_urls": list of str (optional, if generate_media=True),
            "media_result": dict (optional, if generate_media=True)
        }
    """

    # Class-level attribute for lazy initialization
    _media_executor = None

    # Default speakers for different content types
    DEFAULT_SPEAKERS = {
        "novel": [
            Speaker(name="韩林", voice="male_young", role="protagonist"),
            Speaker(name="旁白", voice="narrator", role="narrator"),
        ],
        "story": [
            Speaker(name="主播小A", voice="female_young", role="host"),
            Speaker(name="主播小B", voice="male_mature", role="host"),
            Speaker(name="旁白", voice="narrator", role="narrator"),
        ],
    }

    @property
    def consumer_type(self) -> str:
        """Return consumer type."""
        return "podcast"

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
        """Query raw scene data for podcast generation.

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
        """Generate podcast script from raw scene data.

        Args:
            raw_data: Raw scene data containing:
                - beats: Plot beats with character interactions
                - character_states: Character states for dialogue context
                - scene_descriptions: Scene visuals
                - emotional_arc: Scene emotional arc
            **kwargs: Additional generation parameters:
                - content_type: "novel" or "story" (default: "novel")
                - format: "conversation" or "narrated" (default: "narrated")
                - duration_target: Target duration in seconds (default: 300)
                - generate_media: Whether to generate actual speech (default: True)

        Returns:
            dict with keys: title, script, duration_estimate, speakers,
            media_urls, media_result (if generate_media=True)
        """
        if self.llm_client is None:
            raise ValueError("llm_client not configured")

        # Extract components
        beats = raw_data.get("beats", [])
        character_states = raw_data.get("character_states", {})
        scene_descriptions = raw_data.get("scene_descriptions", [])
        emotional_arc = raw_data.get("emotional_arc", {})
        chapter_info = raw_data.get("chapter_info", {})
        background = raw_data.get("background", "")

        content_type = kwargs.get("content_type", "novel")
        duration_target = kwargs.get("duration_target", 300)  # 5 minutes default
        generate_media = kwargs.get("generate_media", True)

        # Determine speakers based on content type
        speakers = self._get_speakers(content_type, character_states)

        # Build generation prompt
        prompt = self._build_podcast_prompt(
            beats=beats,
            character_states=character_states,
            scene_descriptions=scene_descriptions,
            emotional_arc=emotional_arc,
            chapter_info=chapter_info,
            background=background,
            speakers=speakers,
            duration_target=duration_target,
            **kwargs,
        )

        # Generate podcast script
        messages = [{"role": "user", "content": prompt}]
        script_text = self.llm_client.generate(messages)

        # Estimate duration based on script length
        duration_estimate = self._estimate_duration(script_text, duration_target)

        # Build result
        result = {
            "title": self._generate_title(chapter_info, beats, content_type),
            "script": script_text,
            "duration_estimate": duration_estimate,
            "speakers": [s.__dict__ for s in speakers],
        }

        # Add optional intro/outro if requested
        if kwargs.get("include_intro", True):
            result["intro"] = self._generate_intro(result["title"], speakers[0])

        if kwargs.get("include_outro", True):
            result["outro"] = self._generate_outro()

        # Generate actual speech audio if requested
        media_result = None
        media_urls = []
        if generate_media:
            try:
                media_result = await self._generate_speech(result, speakers)
                if media_result and media_result.get("success"):
                    audio_url = media_result.get("audio_url")
                    if audio_url:
                        media_urls.append(audio_url)
                    result["media_result"] = media_result
                    result["media_urls"] = media_urls
            except Exception as e:
                logger.warning(f"Speech generation failed: {e}")
                result["media_result"] = {"success": False, "error": str(e)}
                result["media_urls"] = []

        return result

    async def _generate_speech(self, script_data: Dict[str, Any], speakers: List[Speaker]) -> Dict[str, Any]:
        """Generate actual speech audio using MiniMax API.

        Args:
            script_data: Generated script data containing title, script, intro, outro
            speakers: List of speakers

        Returns:
            dict with speech generation result
        """
        # Combine script text for TTS
        full_script = ""
        if script_data.get("intro"):
            full_script += script_data["intro"] + "\n\n"
        full_script += script_data.get("script", "")
        if script_data.get("outro"):
            full_script += "\n\n" + script_data["outro"]

        # Use first speaker's voice
        voice_id = "female-shaonv"
        if speakers:
            voice_id = speakers[0].voice if speakers[0].voice else voice_id

        return await self.media_executor.generate_speech(
            text=full_script[:1000],  # Limit text length
            voice_id=voice_id,
            model="speech-02-hd",
            speed=1.0,
            emotion="neutral",
        )

    def _get_speakers(
        self, content_type: str, character_states: Dict[str, List]
    ) -> List[Speaker]:
        """Determine speakers for the podcast.

        Args:
            content_type: Type of content ("novel" or "story")
            character_states: Character states for voice matching

        Returns:
            List of Speaker objects
        """
        # Start with defaults for content type
        speakers = [
            Speaker(name=s.name, voice=s.voice, role=s.role)
            for s in self.DEFAULT_SPEAKERS.get(content_type, self.DEFAULT_SPEAKERS["story"])
        ]

        # If we have character states, add characters as guests
        if character_states:
            char_names = list(character_states.keys())[:4]  # Max 4 additional speakers
            for name in char_names:
                if not any(s.name == name for s in speakers):
                    # Assign a voice based on name characteristics
                    voice = self._assign_voice_for_character(name)
                    speakers.append(Speaker(name=name, voice=voice, role="character"))

        return speakers

    def _assign_voice_for_character(self, name: str) -> str:
        """Assign a voice profile based on character name.

        Args:
            name: Character name

        Returns:
            Voice profile string
        """
        # Simple heuristic based on common Chinese naming patterns
        # In production, this could use more sophisticated matching
        if name in ["韩林", "叶尘", "萧炎", "林动"]:
            return "male_young"
        elif name in ["柳如烟", "薰儿", "彩鳞"]:
            return "female_young"
        elif "长老" in name or "掌门" in name:
            return "male_mature"
        elif "仙子" in name or "女王" in name:
            return "female_mature"
        return "neutral"

    def _build_podcast_prompt(
        self,
        beats: List[Dict],
        character_states: Dict[str, List],
        scene_descriptions: List[str],
        emotional_arc: Dict,
        chapter_info: Dict,
        background: str,
        speakers: List[Speaker],
        duration_target: int,
        **kwargs,
    ) -> str:
        """Build the podcast generation prompt.

        Args:
            beats: Plot beats
            character_states: Character states
            scene_descriptions: Scene visuals
            emotional_arc: Emotional arc
            chapter_info: Chapter metadata
            background: Story background
            speakers: List of speakers
            duration_target: Target duration in seconds
            **kwargs: Additional parameters

        Returns:
            Formatted prompt string
        """
        format_type = kwargs.get("format", "narrated")

        # Format speakers
        speakers_text = "\n".join(
            f"- {s.name} ({s.role}): 音色={s.voice}" for s in speakers
        )

        # Format beats for dialogue
        beats_text = self._format_beats_for_dialogue(beats)

        # Format emotional arc
        arc_text = ""
        if emotional_arc:
            arc_text = f"""
情感节奏:
- 开场: {emotional_arc.get('start_state', '平静')}
- 发展: {emotional_arc.get('peak_state', '紧张')}
- 结尾: {emotional_arc.get('end_state', '舒缓')}
"""

        chapter_context = ""
        if chapter_info:
            chapter_context = f"""
章节信息:
- 章节号: {chapter_info.get('chapter_number', '未知')}
- 章节标题: {chapter_info.get('title', '未知')}
"""

        prompt = f"""<identity>
你是一个资深播客编剧，擅长将故事内容转化为适合音频聆听的脚本。
你的脚本对话自然流畅，旁白引人入胜。
</identity>

<context>
{chapter_context}

故事背景:
{background}

情感节奏:
{arc_text}
</context>

<speakers>
主播/角色配置:
{speakers_text}
</speakers>

<source_material>
情节发展:
{beats_text}

场景描述:
{chr(10).join(f"- {d}" for d in scene_descriptions[:3])}
</source_material>

<requirements>
播客格式: {format_type}
目标时长: 约{duration_target}秒（约{duration_target // 60}分钟）

脚本格式要求:
1. 使用「」标注对话，如：韩林：「这件事，我必须亲自去。」
2. 旁白/介绍使用【】标注，如：【场景转至太虚宗】
3. 主持人过渡使用【主持人】标注
4. 每个说话者的发言控制在50字以内，便于朗读
5. 控制节奏，避免过长的独白

重要规则:
1. 直接输出脚本正文，不要输出任何说明
2. 确保对话符合角色性格
3. 保持情节连贯性
4. 适当加入场景转换提示
5. 不要使用占位符
</requirements>

请根据以上素材，创作播客脚本:
"""
        return prompt

    def _format_beats_for_dialogue(self, beats: List[Dict]) -> str:
        """Format beats for dialogue extraction.

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
            lines.append(f"   出场角色: {char_str}")

        return "\n".join(lines)

    def _generate_title(
        self, chapter_info: Dict, beats: List[Dict], content_type: str
    ) -> str:
        """Generate podcast title.

        Args:
            chapter_info: Chapter metadata
            beats: Plot beats
            content_type: Content type

        Returns:
            Generated title string
        """
        chapter_title = chapter_info.get("title", "")
        if chapter_title:
            return f"【音频】{chapter_title}"

        # Generate from beats
        if beats:
            first_beat = beats[0].get("description", "")[:20]
            return f"【音频】{first_beat}..."

        return "【音频】精彩内容分享"

    def _generate_intro(self, title: str, host: Speaker) -> str:
        """Generate podcast intro.

        Args:
            title: Podcast title
            host: Main host speaker

        Returns:
            Intro text
        """
        return f"""【{host.name}】
大家好，欢迎收听今天的节目。
今天我们要分享的是：{title}
让我们一起进入故事的世界。
"""

    def _generate_outro(self) -> str:
        """Generate podcast outro.

        Returns:
            Outro text
        """
        return """【主持人】
感谢大家的收听。
如果你喜欢本期内容，请点赞、关注、转发。
我们下期再见！
"""

    def _estimate_duration(
        self, script_text: str, target: int
    ) -> int:
        """Estimate actual duration from script.

        Args:
            script_text: Generated script
            target: Target duration

        Returns:
            Estimated duration in seconds
        """
        # Rough estimate: ~5 characters per second for Chinese
        char_count = len(script_text)
        estimated = char_count // 5

        # Clamp to reasonable range (50% to 150% of target)
        return max(int(target * 0.5), min(int(target * 1.5), estimated))
