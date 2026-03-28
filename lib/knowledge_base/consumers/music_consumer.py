# -*- encoding: utf-8 -*-
"""Music Consumer - generates background music with optional vocals from raw scene data.

This consumer transforms FILM_DRAMA scene data into music generation requests,
supporting both instrumental background music and singing vocals with lyrics.

Inspired by:
- deer-flow skill format (structured prompts, separation of concerns)
- game-audio-engineer adaptive music (tension/intensity curves)
- MiniMax Music 2.5 structured generation (16 styles × 11 moods × 10 scenes)
- Video prompt five-dimensional coordinate system (五维控制坐标系)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import BaseConsumer
from media.minimax_executor import get_media_executor

logger = logging.getLogger(__name__)


@dataclass
class MusicCue:
    """A music cue for a scene segment."""

    segment: str  # Description of when this music plays
    style: str  # Music style
    mood: str  # Emotional mood
    tempo: str  # Tempo description
    instruments: List[str]  # Suggested instruments
    intensity: float = 0.5  # 0.0 to 1.0, intensity level
    lyrics: str = ""  # Lyrics for this segment (if singing)
    tension: float = 0.5  # 0.0-1.0, music tension level


@dataclass
class TensionCurve:
    """Music tension curve across segments.

    Similar to game-audio-engineer's intensity parameter (0-1).
    Drives adaptive music transitions and emotional arc.
    """

    timestamps: List[float] = field(default_factory=list)  # Seconds
    values: List[float] = field(default_factory=list)  # 0.0-1.0

    def get_value_at(self, timestamp: float) -> float:
        """Get tension value at a given timestamp using linear interpolation."""
        if not self.timestamps:
            return 0.5
        if timestamp <= self.timestamps[0]:
            return self.values[0]
        if timestamp >= self.timestamps[-1]:
            return self.values[-1]

        for i in range(len(self.timestamps) - 1):
            if self.timestamps[i] <= timestamp <= self.timestamps[i + 1]:
                t = (timestamp - self.timestamps[i]) / (self.timestamps[i + 1] - self.timestamps[i])
                return self.values[i] + t * (self.values[i + 1] - self.values[i])
        return 0.5


class MusicConsumer(BaseConsumer):
    """Music consumer - generates background music prompts.

    Transforms FILM_DRAMA scene data into music generation prompts
    for AI music generation tools (e.g., Suno, Udio).

    Output format:
        dict: {
            "style": str,
            "mood": str,
            "tempo": str,
            "instruments": list of str,
            "prompt_for_generation": str,
            "cues": list of MusicCue dicts,
            "reference_tracks": list of str (optional),
            "media_urls": list of str (optional, if generate_media=True),
            "media_result": dict (optional, if generate_media=True)
        }
    """

    # Class-level attribute for lazy initialization
    _media_executor = None

    # Instrument presets by genre
    INSTRUMENT_PRESETS = {
        "xianxia": ["古筝", "笛子", "琵琶", "古琴", "编钟", "鼓"],
        "wuxia": ["二胡", "琵琶", "萧", "鼓", "锣", "梆子"],
        "fantasy": ["管弦乐", "竖琴", "圆号", "小提琴", "合成器"],
        "modern": ["钢琴", "吉他", "贝斯", "架子鼓", "电子合成器"],
        "epic": ["交响乐", "合唱团", "铜管乐", "定音鼓", "大提琴"],
    }

    # Mood to tempo mapping
    MOOD_TEMPO_MAP = {
        "紧张": "快节奏",
        "激烈": "快节奏",
        "悬疑": "中快节奏",
        "战斗": "快节奏",
        "悲伤": "慢节奏",
        "沉静": "慢节奏",
        "舒缓": "慢节奏",
        "欢快": "中快节奏",
        "浪漫": "中节奏",
        "高潮": "快节奏",
        "平缓": "中节奏",
    }

    # Tension curve presets by emotional arc shape (use tuples to prevent mutation)
    TENSION_CURVE_PRESETS = {
        "build": (0.0, 0.3, 0.5, 0.7, 1.0),  # Steady build to climax
        "drop": (1.0, 0.7, 0.5, 0.3, 0.0),  # Climax to calm
        "wave": (0.2, 0.6, 0.3, 0.8, 0.4),  # Multiple peaks
        "sustain": (0.5, 0.5, 0.5, 0.5, 0.5),  # Constant tension
        "rise_fall": (0.2, 0.4, 0.7, 0.4, 0.2),  # Rise then fall
    }

    @property
    def consumer_type(self) -> str:
        """Return consumer type."""
        return "music"

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
        """Query raw scene data for music generation.

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
        """Generate music prompt from raw scene data.

        Args:
            raw_data: Raw scene data containing:
                - beats: Plot beats for segment identification
                - emotional_arc: Scene emotional arc
                - character_states: Character emotional states
                - scene_descriptions: Scene visuals
                - background: Story background
                - chapter_info: Chapter metadata
            **kwargs: Additional generation parameters:
                - genre: Music genre (default: "xianxia")
                - format: "background" or "featured" (default: "background")
                - include_cues: Whether to include segment cues (default: True)
                - generate_media: Whether to generate actual music (default: True)
                - with_lyrics: Whether to generate singing music (default: False)
                - lyrics_style: "narrative" or "poetic" (default: "poetic")
                - use_llm_prompt: Use LLM for prompt generation (default: True if llm_client available)

        Returns:
            dict with keys: style, mood, tempo, instruments,
            prompt_for_generation, cues, reference_tracks, tension_curve,
            lyrics (if with_lyrics=True), media_urls, media_result
        """
        if self.llm_client is None:
            raise ValueError("llm_client not configured")

        # Extract components
        beats = raw_data.get("beats", [])
        emotional_arc = raw_data.get("emotional_arc", {})
        character_states = raw_data.get("character_states", {})
        scene_descriptions = raw_data.get("scene_descriptions", [])
        chapter_info = raw_data.get("chapter_info", {})
        background = raw_data.get("background", "")

        genre = kwargs.get("genre", "xianxia")
        include_cues = kwargs.get("include_cues", True)
        generate_media = kwargs.get("generate_media", True)
        with_lyrics = kwargs.get("with_lyrics", False)
        lyrics_style = kwargs.get("lyrics_style", "poetic")
        use_llm_prompt = kwargs.get("use_llm_prompt", True)

        # Determine overall mood and tempo from emotional arc
        mood = self._determine_mood(emotional_arc, character_states)
        tempo = self._determine_tempo(emotional_arc, mood)

        # Get instruments for genre
        instruments = self.INSTRUMENT_PRESETS.get(
            genre, self.INSTRUMENT_PRESETS["xianxia"]
        )

        # Build tension curve
        tension_curve = self._build_tension_curve(emotional_arc, beats)

        # Generate segment cues if requested
        cues = []
        if include_cues and beats:
            cues = self._generate_cues(beats, emotional_arc, genre, tension_curve)

        # Generate lyrics if requested
        lyrics = ""
        if with_lyrics:
            lyrics = await self._generate_lyrics(
                beats=beats,
                emotional_arc=emotional_arc,
                chapter_info=chapter_info,
                genre=genre,
                style=lyrics_style,
            )

        # Build main prompt - LLM-based or rule-based
        if use_llm_prompt and self.llm_client:
            # Use LLM for intelligent prompt generation (五维音乐坐标系 format)
            # Use asyncio.to_thread to avoid blocking event loop since LLM call is sync
            prompt_for_generation = await asyncio.to_thread(
                self._build_music_prompt_with_llm,
                beats=beats,
                emotional_arc=emotional_arc,
                scene_descriptions=scene_descriptions,
                chapter_info=chapter_info,
                genre=genre,
                with_lyrics=with_lyrics,
            )
            # Fallback to rule-based if LLM fails
            if not prompt_for_generation:
                prompt_for_generation = self._build_music_prompt(
                    genre=genre,
                    mood=mood,
                    tempo=tempo,
                    instruments=instruments,
                    emotional_arc=emotional_arc,
                    scene_descriptions=scene_descriptions,
                    chapter_info=chapter_info,
                    tension_curve=tension_curve,
                    with_lyrics=with_lyrics,
                    **kwargs,
                )
        else:
            # Use direct rule-based prompt
            prompt_for_generation = self._build_music_prompt(
                genre=genre,
                mood=mood,
                tempo=tempo,
                instruments=instruments,
                emotional_arc=emotional_arc,
                scene_descriptions=scene_descriptions,
                chapter_info=chapter_info,
                tension_curve=tension_curve,
                with_lyrics=with_lyrics,
                **kwargs,
            )

        # Build result
        result = {
            "style": self._format_style(genre, emotional_arc),
            "mood": mood,
            "tempo": tempo,
            "instruments": instruments,
            "prompt_for_generation": prompt_for_generation,
            "cues": [c.__dict__ for c in cues],
            "reference_tracks": self._get_reference_tracks(genre, mood),
            "tension_curve": {
                "timestamps": tension_curve.timestamps,
                "values": tension_curve.values,
            },
        }

        if lyrics:
            result["lyrics"] = lyrics

        # Generate actual music if requested
        media_result = None
        media_urls = []
        if generate_media:
            try:
                media_result = await self._generate_music(
                    prompt=prompt_for_generation,
                    genre=genre,
                    lyrics=lyrics if with_lyrics else "",
                )
                if media_result and media_result.get("success"):
                    music_url = media_result.get("music_url")
                    if music_url:
                        media_urls.append(music_url)
                    result["media_result"] = media_result
                    result["media_urls"] = media_urls
            except Exception as e:
                logger.warning(f"Music generation failed: {e}")
                result["media_result"] = {"success": False, "error": str(e)}
                result["media_urls"] = []

        return result

    async def _generate_music(
        self, prompt: str, genre: str, lyrics: str = ""
    ) -> Dict[str, Any]:
        """Generate actual music using MiniMax API.

        Args:
            prompt: Music prompt for generation
            genre: Music genre
            lyrics: Lyrics for singing music (optional)

        Returns:
            dict with music generation result
        """
        return await self.media_executor.generate_music(
            prompt=prompt,
            lyrics=lyrics,
            model="music-2.5",
            wait_for_completion=True,
        )

    def _determine_mood(
        self, emotional_arc: Dict, character_states: Dict[str, List]
    ) -> str:
        """Determine overall mood from emotional data.

        Args:
            emotional_arc: Emotional arc data
            character_states: Character emotional states

        Returns:
            Mood description string
        """
        # Start with emotional arc peak
        peak = emotional_arc.get("peak_state", "")

        if peak:
            if any(t in peak for t in ["紧张", "危机", "战斗"]):
                return "紧张激烈"
            elif any(t in peak for t in ["悲伤", "痛苦", "失落"]):
                return "悲伤沉痛"
            elif any(t in peak for t in ["高潮", "兴奋", "喜悦"]):
                return "激昂澎湃"
            elif any(t in peak for t in ["平静", "舒缓"]):
                return "舒缓悠扬"

        # Fall back to character states
        if character_states:
            latest_states = [states[-1] for states in character_states.values() if states]
            emotional_states = [s.get("emotional_state", "") for s in latest_states]

            # Count emotional frequencies
            tense_count = sum(1 for e in emotional_states if "紧张" in e or "愤怒" in e)
            sad_count = sum(1 for e in emotional_states if "悲伤" in e or "失落" in e)

            if tense_count > sad_count:
                return "紧张悬疑"
            elif sad_count > 0:
                return "悲伤舒缓"

        return "史诗大气"

    def _determine_tempo(self, emotional_arc: Dict, mood: str) -> str:
        """Determine tempo from emotional data and mood.

        Args:
            emotional_arc: Emotional arc data
            mood: Determined mood

        Returns:
            Tempo description string
        """
        # Check mood mapping first
        for key, tempo in self.MOOD_TEMPO_MAP.items():
            if key in mood:
                return tempo

        # Check emotional arc
        peak = emotional_arc.get("peak_state", "")
        if peak:
            if any(t in peak for t in ["紧张", "激烈", "战斗"]):
                return "快节奏"
            elif any(t in peak for t in ["悲伤", "沉静"]):
                return "慢节奏"

        return "中节奏"

    def _format_style(self, genre: str, emotional_arc: Dict) -> str:
        """Format style description.

        Args:
            genre: Music genre
            emotional_arc: Emotional arc data

        Returns:
            Style description string
        """
        style_prefix = {
            "xianxia": "古风玄幻",
            "wuxia": "武侠豪迈",
            "fantasy": "奇幻史诗",
            "modern": "现代都市",
            "epic": "史诗大片",
        }

        prefix = style_prefix.get(genre, "古风")

        # Add emotional nuance
        peak = emotional_arc.get("peak_state", "")
        if peak:
            if "紧张" in peak or "战斗" in peak:
                return f"{prefix}战斗"
            elif "悲伤" in peak:
                return f"{prefix}抒情"

        return f"{prefix}配乐"

    def _build_music_prompt(
        self,
        genre: str,
        mood: str,
        tempo: str,
        instruments: List[str],
        emotional_arc: Dict,
        scene_descriptions: List[str],
        chapter_info: Dict,
        tension_curve: Optional[TensionCurve] = None,
        with_lyrics: bool = False,
        **kwargs,
    ) -> str:
        """Build the main music generation prompt.

        Uses direct structured format (五维音乐坐标系) for MiniMax Music 2.5.
        No indirect LLM→LLM chain - outputs directly usable prompt.

        Args:
            genre: Music genre
            mood: Emotional mood
            tempo: Tempo description
            instruments: List of instruments
            emotional_arc: Emotional arc data
            scene_descriptions: Scene visuals
            chapter_info: Chapter metadata
            tension_curve: Music tension curve (optional)
            with_lyrics: Whether lyrics will be added (optional)
            **kwargs: Additional parameters

        Returns:
            Music prompt string for AI generation (direct format)
        """
        instrument_str = "、".join(instruments[:4])  # Use top 4 instruments
        chapter_title = chapter_info.get("title", "太古魔帝传") if chapter_info else "太古魔帝传"

        # Format emotional journey
        arc_text = ""
        if emotional_arc:
            arc_text = f"""
情感曲线:
- 开场: {emotional_arc.get('start_state', '平静')}
- 发展: {emotional_arc.get('development_state', '紧张')}
- 高潮: {emotional_arc.get('peak_state', '激烈')}
- 结尾: {emotional_arc.get('end_state', '舒缓')}
"""

        # Format scene context
        scene_text = ""
        if scene_descriptions:
            scene_text = f"""
场景描述:
{chr(10).join(f"- {d[:50]}" for d in scene_descriptions[:2])}
"""

        # Format tension curve (五维音乐坐标系 时序化动态控制)
        tension_text = ""
        if tension_curve and tension_curve.values:
            tension_segments = []
            for i, (ts, val) in enumerate(zip(tension_curve.timestamps, tension_curve.values)):
                if i < len(tension_curve.timestamps) - 1:
                    next_ts = tension_curve.timestamps[i + 1]
                    tension_segments.append(f"{int(ts)}-{int(next_ts)}秒: 强度{val:.1f}")
                else:
                    tension_segments.append(f"{int(ts)}秒+: 强度{val:.1f}")
            tension_text = f"""
张力曲线 (时序化动态五维精准控制):
{chr(10).join(tension_segments)}
(0.0=平静铺垫, 0.5=渐进展开, 1.0=极致高潮)
"""

        # MiniMax Music 2.5 style tags
        style_tags = {
            "xianxia": "Chinese xianxia fantasy, 古风玄幻, ancient Chinese instruments, 仙侠",
            "wuxia": "Chinese wuxia, 武侠, martial arts soundtrack, 江湖豪情",
            "fantasy": "Epic fantasy orchestral, cinematic, 奇幻史诗, grand scale",
            "modern": "Modern cinematic soundtrack, contemporary, 现代都市, emotional",
            "epic": "Epic orchestral, 史诗大片, soundtrack, grand cinematic",
        }
        style_tag = style_tags.get(genre, style_tags["xianxia"])

        # Mood to English mapping
        mood_tags = {
            "紧张激烈": "tense, dramatic, action-packed, intense",
            "悲伤沉痛": "sad, melancholic, emotional, grief",
            "舒缓悠扬": "peaceful, serene, flowing, meditative",
            "激昂澎湃": "uplifting, powerful, epic, heroic",
            "史诗大气": "epic, grand, majestic, cinematic",
            "紧张悬疑": "suspenseful, mysterious, tense, thriller",
            "浪漫温馨": "romantic, warm, tender, love",
            "战斗狂热": "battle, intense, aggressive, warrior",
        }
        mood_tag = mood_tags.get(mood, "cinematic, emotional")

        # Build direct prompt for MiniMax Music 2.5 (五维音乐坐标系格式)
        prompt = f"""{style_tag}, {mood_tag}, {tempo}
乐器配置: {instrument_str}
时长: 2-3分钟

{arc_text}
{tension_text}
{scene_text}

【五维音乐坐标系 - 全局固定基准】
绝对音色锚定: {instrument_str}，全程保持统一音色质感，禁止中途换音色
情绪光影锚定: {mood}，全局情绪基调统一，张力曲线严格遵循时序控制
【时序化动态五维精准控制 全流程连贯无断点】
0-30秒: 开场铺垫，强度{tension_curve.values[0] if tension_curve and tension_curve.values else 0.3}，引入主旋律
30-60秒: 渐入发展，强度{tension_curve.values[1] if tension_curve and len(tension_curve.values) > 1 else 0.5}，叠加乐器层次
60-90秒: 推向高潮，强度{tension_curve.values[2] if tension_curve and len(tension_curve.values) > 2 else 0.7}，全奏+高潮点
90-120秒: 高潮延续，强度{tension_curve.values[3] if tension_curve and len(tension_curve.values) > 3 else 0.9}，情绪最高点
120-150秒: 缓步收尾，强度{tension_curve.values[4] if tension_curve and len(tension_curve.values) > 4 else 0.5}，旋律回归
150-180秒: 完美收束，强度{tension_curve.values[5] if tension_curve and len(tension_curve.values) > 5 else 0.3}，自然淡出"""

        return prompt

    def _generate_cues(
        self, beats: List[Dict], emotional_arc: Dict, genre: str, tension_curve: TensionCurve
    ) -> List[MusicCue]:
        """Generate music cues for each segment/beats.

        Args:
            beats: Plot beats
            emotional_arc: Emotional arc data
            genre: Music genre
            tension_curve: Music tension curve

        Returns:
            List of MusicCue objects
        """
        cues = []

        # Map BeatType enum values to mood/tempo/intensity
        # Note: BeatType values are English ("opening", "development", etc.)
        beat_type_moods = {
            "opening": ("舒缓", "中节奏", 0.3),
            "development": ("渐进", "中节奏", 0.5),
            "conflict": ("紧张", "快节奏", 0.8),
            "climax": ("激烈", "快节奏", 1.0),
            "resolution": ("舒缓", "慢节奏", 0.4),
            "transition": ("平缓", "中节奏", 0.4),
            "dialogue": ("平缓", "中节奏", 0.5),
            "action": ("激烈", "快节奏", 0.9),
        }

        # Calculate cumulative timestamps for beats
        cumulative_time = 0.0
        beat_durations = [30, 30, 30, 30, 30, 30]  # Default 30s per beat

        for i, beat in enumerate(beats[:6]):  # Limit to 6 cues
            beat_type = beat.get("beat_type", "dialogue")
            mood, tempo, intensity = beat_type_moods.get(
                beat_type, beat_type_moods["dialogue"]
            )

            # Get tension value from curve at this timestamp
            tension = tension_curve.get_value_at(cumulative_time)

            # Get segment description
            description = beat.get("description", "")[:30]

            # Get instruments based on genre and intensity
            instruments = self.INSTRUMENT_PRESETS.get(
                genre, self.INSTRUMENT_PRESETS["xianxia"]
            )
            if intensity > 0.7:
                instruments = instruments[:4]  # Full ensemble
            else:
                instruments = instruments[:2]  # Subdued

            cues.append(MusicCue(
                segment=f"场景{i+1}: {description}...",
                style=self._format_style(genre, {}),
                mood=mood,
                tempo=tempo,
                instruments=instruments,
                intensity=intensity,
                tension=tension,
            ))

            # Update cumulative time
            cumulative_time += beat_durations[i]

        return cues

    def _build_tension_curve(
        self, emotional_arc: Dict, beats: List[Dict]
    ) -> TensionCurve:
        """Build a tension curve based on emotional arc and beats.

        Inspired by game-audio-engineer's intensity parameter (0-1).
        Drives adaptive music transitions.

        Args:
            emotional_arc: Emotional arc data with start/peak/end states
            beats: Plot beats for segment timing

        Returns:
            TensionCurve object
        """
        curve = TensionCurve()
        num_segments = min(len(beats), 6) if beats else 5

        if num_segments == 0:
            curve.timestamps = [0.0]
            curve.values = [0.5]
            return curve

        # Determine curve shape from emotional arc
        start_state = emotional_arc.get("start_state", "平静")
        peak_state = emotional_arc.get("peak_state", "高潮")
        end_state = emotional_arc.get("end_state", "舒缓")

        # Determine curve type based on emotional arc
        curve_type = "sustain"
        if "紧张" in peak_state or "高潮" in peak_state or "激烈" in peak_state:
            if "舒缓" in end_state or "平静" in end_state:
                curve_type = "rise_fall"
            elif "紧张" in start_state:
                curve_type = "sustain"
            else:
                curve_type = "build"
        elif "悲伤" in peak_state or "沉静" in peak_state:
            curve_type = "sustain"
        elif "战斗" in peak_state:
            curve_type = "build"

        # Get preset values
        preset_values = self.TENSION_CURVE_PRESETS.get(curve_type, [0.5] * 5)

        # Adjust values based on peak intensity
        if "紧张" in peak_state or "激烈" in peak_state:
            preset_values = [min(1.0, v + 0.2) for v in preset_values]
        elif "悲伤" in peak_state or "舒缓" in peak_state:
            preset_values = [max(0.2, v - 0.2) for v in preset_values]

        # Resample to match number of segments
        if num_segments <= 0 or len(preset_values) == 0:
            # Defensive: return flat curve if no valid data
            curve.timestamps = [0.0]
            curve.values = [0.5]
            return curve
        step = len(preset_values) / num_segments
        curve.values = [preset_values[min(int(i * step), len(preset_values) - 1)] for i in range(num_segments)]

        # Generate timestamps (assuming 30s per segment)
        curve.timestamps = [i * 30.0 for i in range(num_segments)]

        return curve

    def _get_reference_tracks(self, genre: str, mood: str) -> List[str]:
        """Get reference track suggestions.

        Args:
            genre: Music genre
            mood: Emotional mood

        Returns:
            List of reference track names
        """
        # In production, these would be actual track names
        references = {
            ("xianxia", "紧张激烈"): [
                "《大话西游》配乐",
                "《仙剑奇侠传》战斗音乐",
            ],
            ("xianxia", "舒缓悠扬"): [
                "《古剑奇谭》背景音乐",
                "《三生三世十里桃花》配乐",
            ],
            ("wuxia", "紧张激烈"): [
                "《卧虎藏龙》配乐",
                "《功夫熊猫》战斗音乐",
            ],
            ("epic", "紧张激烈"): [
                "《权力的游戏》配乐",
                "《指环王》战斗音乐",
            ],
        }

        key = (genre, mood)
        if key in references:
            return references[key]

        # Generic references
        generic_refs = {
            "xianxia": ["《原神》OST", "《黑神话悟空》配乐"],
            "wuxia": ["《卧虎藏龙》OST"],
            "fantasy": ["《巫师3》OST"],
            "modern": ["《你的名字》OST"],
            "epic": ["《环太平洋》配乐"],
        }

        return generic_refs.get(genre, ["《原神》OST"])

    def _build_music_prompt_with_llm(
        self,
        beats: List[Dict],
        emotional_arc: Dict,
        scene_descriptions: List[str],
        chapter_info: Dict,
        genre: str,
        with_lyrics: bool = False,
    ) -> str:
        """Build enhanced music prompt using LLM (similar to video prompt optimization).

        Uses the LLM to generate a structured 五维音乐坐标系 format prompt
        directly, without the indirect LLM→LLM chain.

        Args:
            beats: Plot beats for segment context
            emotional_arc: Emotional arc data
            scene_descriptions: Scene visuals
            chapter_info: Chapter metadata
            genre: Music genre
            with_lyrics: Whether lyrics will be added

        Returns:
            Enhanced music prompt in 五维音乐坐标系 format
        """
        if self.llm_client is None:
            return ""

        chapter_title = chapter_info.get("title", "未知章节") if chapter_info else "未知章节"

        # Format beats
        beats_text = ""
        for i, beat in enumerate(beats[:6]):
            description = beat.get("description", "")
            beat_type = beat.get("beat_type", "")
            beats_text += f"{i+1}. [{beat_type}] {description[:50]}\n"

        system_prompt = """你是一个专业的AI音乐提示词工程师，擅长为MiniMax Music 2.5音乐生成模型创建精确、专业的提示词。

【重要】你正在为MiniMax Music 2.5生成音乐提示词。Music 2.5是MiniMax推出的AI音乐生成模型，支持高质量的歌曲和纯音乐生成。

请严格按照以下【五维音乐坐标系】格式生成音乐提示词。

【输出格式 - 必须严格遵循】

【全局固定音乐基准】
绝对音色锚定：[详细描述主要乐器音色特点，如古筝的清亮悠扬、二胡的深沉婉转，全程保持统一]
情绪光影锚定：[全局情绪基调描述，如紧张悬疑、史诗悲壮，全程情绪统一]
【时序化动态五维精准控制 全流程连贯无断点】
0-30秒：[开场处理，如轻柔引入、渐强铺垫]
30-60秒：[发展阶段，如旋律展开、层次叠加]
60-90秒：[推向高潮，如情绪爆发、节奏加速]
90-120秒：[高潮延续，如最强点、情绪顶点]
120-150秒：[缓步收尾，如旋律回归、强度下降]
150-180秒：[完美收束，如自然淡出、余韵悠长]
【歌词结构 - 仅当with_lyrics=true时】
前奏：[2-4小节器乐前奏描述]
主歌1：[歌词主题和情绪，4-8句]
副歌：[Hook记忆点，旋律记忆点，4句]
主歌2：[剧情推进，4-8句]
副歌：[重复+变化]
桥段：[情绪转折，4句]
结尾：[副歌尾声，淡出]

【MiniMax Music 2.5专属参数】
风格标签：Chinese xianxia fantasy / epic orchestral / modern cinematic
情绪标签：tense, dramatic, melancholic, epic, romantic
乐器配置：古筝、笛子、琵琶 / 钢琴、吉他、贝斯
节奏：快节奏(120BPM+)、中节奏(80-120BPM)、慢节奏(<80BPM)

【关键要求】
1. 输出只包含提示词本身，不要任何解释性文字
2. 提示词应为英文，简洁专业，便于AI音乐模型理解
3. 时序控制必须具体，每个时间段都有明确描述
4. 歌词结构要包含记忆点Hook，便于传唱
5. 如果with_lyrics=false，跳过歌词结构部分"""

        user_prompt = f"""为以下场景生成MiniMax Music 2.5音乐提示词：

章节标题：{chapter_title}
音乐类型：{genre}
情节概述：
{beats_text}

情感曲线：
开场：{emotional_arc.get('start_state', '平静')}
发展：{emotional_arc.get('development_state', '紧张')}
高潮：{emotional_arc.get('peak_state', '激烈')}
结尾：{emotional_arc.get('end_state', '舒缓')}

场景描述：
{chr(10).join(f"- {d[:50]}" for d in scene_descriptions[:3])}

是否带歌词：{"是" if with_lyrics else "否"}

请生成完整的五维音乐坐标系提示词，确保音乐连贯、情感饱满。输出只包含提示词本身。"""

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            result = self.llm_client.generate(messages)
            return result.strip()
        except Exception as e:
            logger.warning(f"LLM music prompt generation failed: {e}")
            return ""

    async def _generate_lyrics(
        self,
        beats: List[Dict],
        emotional_arc: Dict,
        chapter_info: Dict,
        genre: str,
        style: str = "poetic",
    ) -> str:
        """Generate lyrics for singing music using MiniMax lyrics generation API.

        Uses the MiniMax media executor's lyrics generation which leverages
        MiniMax's text model API for structured lyrics with MiniMax Music 2.5
        paragraph-level control support.

        Args:
            beats: Plot beats for lyrical content
            emotional_arc: Emotional arc for mood
            chapter_info: Chapter metadata
            genre: Music genre
            style: "narrative" or "poetic" (default: "poetic")

        Returns:
            Generated lyrics string with structure tags
        """
        # Format beats for lyrics topic
        beats_text = ""
        for i, beat in enumerate(beats[:4]):  # Use top 4 beats
            description = beat.get("description", "")
            beat_type = beat.get("beat_type", "")
            beats_text += f"{i+1}. [{beat_type}] {description[:30]}...\n"

        # Emotional context
        start = emotional_arc.get("start_state", "平静")
        peak = emotional_arc.get("peak_state", "高潮")
        end = emotional_arc.get("end_state", "舒缓")

        chapter_title = chapter_info.get("title", "未知章节") if chapter_info else "未知章节"

        # Build topic from beats and emotional arc
        topic = f"《{chapter_title}》"
        if beats_text:
            topic += f"\n情节：{beats_text.strip()}"
        topic += f"\n情感曲线：开场({start}) → 高潮({peak}) → 结尾({end})"

        # Determine structure based on emotional arc
        structure = "verse_chorus"
        if "战斗" in peak or "高潮" in peak:
            structure = "with_bridge"  # More dramatic structure for climactic scenes
        elif "悲伤" in peak or "沉静" in peak:
            structure = "verse_only"  # Simpler structure for emotional scenes

        try:
            result = await self.media_executor.generate_lyrics(
                topic=topic,
                genre=genre,
                mood=self._determine_mood(emotional_arc, {}),
                style=style,
                structure=structure,
            )
            if result.get("success") and result.get("lyrics"):
                return result["lyrics"]
            else:
                logger.warning(f"Lyrics generation failed: {result.get('error')}")
                return ""
        except Exception as e:
            logger.warning(f"Lyrics generation failed: {e}")
            return ""
