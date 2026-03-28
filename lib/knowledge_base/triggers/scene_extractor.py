"""Scene extraction utilities for video content evaluation.

This module provides the SceneExtractor class for extracting scenes from
novel chapters, with intensity/importance/visual_potential scoring
suitable for video generation triggering.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Chinese action/emotion keywords for scene classification
COMBAT_KEYWORDS = {
    "激战", "苦战", "血战", "厮杀", "搏杀", "对决", "碰撞",
    "轰鸣", "爆炸", "崩塌", "粉碎", "撕裂", "斩杀", "击碎",
    "轰鸣", "电闪雷鸣", "山崩地裂", "洪水滔天", "烈焰", "烽火",
    "剑光", "刀影", "拳风", "惨叫", "怒吼", "咆哮", "嘶吼",
    "鲜血", "尸骨", "血溅", "断臂", "陨落", "爆体",
    "飞剑", "法宝", "神通", "灵力", "真元", "天雷",
}

EMOTION_KEYWORDS = {
    "泪水", "泪流", "泪如雨下", "心碎", "心碎", "狂喜", "悲痛",
    "嚎啕", "哽咽", "痛哭", "抽泣", "眼眶湿润", "热泪盈眶",
    "狂笑", "狞笑", "冷笑", "苦笑", "微笑", "淡然一笑",
    "愤怒", "暴怒", "怒火", "怨气", "恨意", "杀意",
    "惊恐", "恐惧", "战栗", "胆寒", "毛骨悚然",
    "震撼", "惊骇", "目瞪口呆", "瞠目结舌",
}

VISUAL_KEYWORDS = {
    # Fire/flame
    "火焰", "烈焰", "火海", "火舌", "火龙", "火凤", "烈焰焚烧",
    # Lightning/thunder
    "雷电", "闪电", "雷鸣", "天雷", "紫雷", "雷光",
    # Water/wave
    "洪水", "惊涛", "骇浪", "巨浪", "海啸", "波涛",
    # Earth collapse
    "山崩", "地裂", "飞沙", "走石", "龙卷风", "崩塌",
    # Light/color
    "金光", "银光", "彩霞", "七彩", "紫气东来", "光芒大盛", "绿光", "青光",
    # Sky/cosmic - 仙侠核心视觉词
    "星空", "银河", "星河", "流星", "皓月", "烈日", "血色", "星空",
    # Dragon/legendary
    "金龙", "九龙", "龙影", "真龙", "神龙", "凤凰", "神兽",
    # Jade/bijou - 传承物品
    "玉佩", "玉简", "令牌", "秘籍", "古朴", "灵光", "灵液", "仙露",
    # Martial arts cultivation visuals
    "剑芒", "刀光", "拳影", "掌风", "剑气", "拳风", "腿影",
    # Energy effects - 仙侠核心
    "真气", "灵力", "魔力", "血色真气", "冲霄", "爆发", "觉醒", "星辰之力",
    # Action effects
    "粉碎", "撕裂", "斩杀", "击碎", "轰炸", "爆体", "湮灭",
    # Mystical/ethereal - 仙侠氛围
    "仙气", "灵气", "云雾", "仙雾", "缥缈", "虚幻", "幻境", "幻象",
    "紫气", "金光大盛", "霞光", "瑞气", "祥云",
    # Special effects
    "绿光", "金光绽放", "星河之力", "星辉", "月华", "日光",
}

DIALOGUE_KEYWORDS = {
    "说道", "问道", "回答", "喊道", "轻声道", "冷笑道",
    "怒道", "叹道", "低声道", "沉声道", "厉声道",
    "喝道", "声道", "言道", "开口道", "应道",
}


@dataclass
class ExtractedScene:
    """Represents an extracted scene from content.

    Attributes:
        scene_id: Unique identifier for the scene.
        chapter_number: Parent chapter number.
        content: The scene content text.
        content_excerpt: First 100 chars of content.
        scene_type: Type of scene (战斗/对话/情感/过场/混合).
        intensity: Combat/action intensity 0.0-1.0.
        importance: Narrative importance 0.0-1.0.
        visual_potential: Visual presentation potential 0.0-1.0.
        emotional_tags: List of emotional tags.
        estimated_duration_sec: Estimated scene duration in seconds.
        char_count: Character count of scene.
    """
    scene_id: str
    chapter_number: int
    content: str
    content_excerpt: str = ""
    scene_type: str = "过场"
    intensity: float = 0.0
    importance: float = 0.0
    visual_potential: float = 0.0
    emotional_tags: List[str] = field(default_factory=list)
    estimated_duration_sec: int = 0
    char_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    extracted_at: Optional[datetime] = None

    def __post_init__(self):
        if self.extracted_at is None:
            self.extracted_at = datetime.now()
        if self.char_count == 0:
            self.char_count = len(self.content)
        if not self.content_excerpt:
            self.content_excerpt = self.content[:100] if self.content else ""


class SceneExtractor:
    """Extracts and scores scenes from novel chapters for video evaluation.

    Uses keyword-based scoring for:
    - intensity: Combat/action density
    - importance: Narrative significance (character appearances, plot advancement)
    - visual_potential: Visual spectacle potential

    In production, this could be enhanced with LLM-based scoring.
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def extract(self, chapter_number: int, chapter_content: str) -> List[ExtractedScene]:
        """Extract scenes from chapter content with scoring.

        Strategy:
        1. Split content by paragraphs and narrative beats
        2. Classify each scene type
        3. Score intensity / importance / visual_potential via keywords
        4. Return sorted list (highest score first)

        Args:
            chapter_number: Chapter number.
            chapter_content: Full chapter text.

        Returns:
            List of ExtractedScene sorted by composite score.
        """
        scenes = []
        # Split by double newlines or scene markers
        segments = re.split(r'\n{2,}|——+|\*{3,}', chapter_content)

        scene_idx = 0
        for seg in segments:
            seg = seg.strip()
            if len(seg) < 30:  # Skip too-short segments (保留30字以上的片段)
                continue

            scene_idx += 1
            scene = self._build_scene(chapter_number, scene_idx, seg)
            scenes.append(scene)

        # Sort by composite score (intensity + importance + visual_potential) / 3
        scenes.sort(key=lambda s: (s.intensity + s.importance + s.visual_potential) / 3, reverse=True)

        self._logger.info(
            f"Extracted {len(scenes)} scenes from ch{chapter_number:03d}, "
            f"top score: {scenes[0].intensity:.2f}" if scenes else ""
        )
        return scenes

    def _build_scene(self, chapter: int, idx: int, content: str) -> ExtractedScene:
        """Build a scored ExtractedScene from raw content."""
        char_count = len(content)

        # Classify scene type
        scene_type = self._classify_scene_type(content)

        # Score dimensions
        intensity = self._score_intensity(content)
        visual_potential = self._score_visual_potential(content)
        emotional_tags = self._extract_emotional_tags(content)

        # Importance: dialogue-heavy scenes with named characters are important
        importance = self._score_importance(content)

        # Duration estimate: ~300 chars/sec for silent reading, ~150 for action
        est_duration = int(char_count / 150) if scene_type in ("战斗", "混合") else int(char_count / 250)
        est_duration = max(10, min(est_duration, 300))  # Clamp 10s-300s

        return ExtractedScene(
            scene_id=f"ch{chapter:03d}_scene_{idx:02d}",
            chapter_number=chapter,
            content=content,
            content_excerpt=content[:100],
            scene_type=scene_type,
            intensity=round(intensity, 3),
            importance=round(importance, 3),
            visual_potential=round(visual_potential, 3),
            emotional_tags=emotional_tags,
            estimated_duration_sec=est_duration,
            char_count=char_count,
        )

    def _classify_scene_type(self, content: str) -> str:
        """Classify scene type by keyword density."""
        combat_count = sum(1 for kw in COMBAT_KEYWORDS if kw in content)
        emotion_count = sum(1 for kw in EMOTION_KEYWORDS if kw in content)
        dialogue_count = sum(1 for kw in DIALOGUE_KEYWORDS if kw in content)

        # Count lines with quotes (dialogue detection)
        quote_lines = len(re.findall(r'[""\'\'"].{10,}', content))

        if combat_count >= 2:
            return "战斗"
        elif quote_lines >= 3 and dialogue_count >= 2:
            return "对话"
        elif emotion_count >= 2:
            return "情感"
        elif combat_count >= 1 and quote_lines >= 1:
            return "混合"
        else:
            return "过场"

    def _score_intensity(self, content: str) -> float:
        """Score combat/action intensity 0.0-1.0."""
        score = 0.0
        combat_hits = sum(1 for kw in COMBAT_KEYWORDS if kw in content)
        score += min(1.0, combat_hits * 0.15)

        # Rapid-fire action verbs
        rapid_actions = ["闪电", "瞬息", "刹那", "转眼", "眨眼", "须臾"]
        score += sum(0.1 for kw in rapid_actions if kw in content)

        # Exclamation marks indicate heightened action
        exclamations = content.count("！") + content.count("!")
        score += min(0.2, exclamations * 0.05)

        return min(1.0, score)

    def _score_visual_potential(self, content: str) -> float:
        """Score visual spectacle potential 0.0-1.0."""
        score = 0.0
        visual_hits = sum(1 for kw in VISUAL_KEYWORDS if kw in content)
        score += min(1.0, visual_hits * 0.12)

        # Environmental description density
        env_patterns = [r'天空[的之]?[中上里]?', r'大地[上之]?', r'云海?', r'星河?']
        env_count = sum(len(re.findall(p, content)) for p in env_patterns)
        score += min(0.3, env_count * 0.1)

        return min(1.0, score)

    def _score_importance(self, content: str) -> float:
        """Score narrative importance 0.0-1.0."""
        score = 0.3  # Base score

        # Named characters appearing - 通用仙侠角色名
        # Note: Using larger character combinations to avoid substring matching
        known_chars = {
            "林渊", "赵无极", "李长青", "林玄", "韩林", "柳如烟", "叶尘",
            "叶天行", "韩啸天", "韩天啸", "赵元启", "小六子", "小蝶",
            "老周头", "逆仙", "太古魔帝", "赵天罡",
            # 通用仙侠角色后缀
            "真人", "长老", "宗主", "掌门", "仙师",
        }
        char_hits = sum(1 for char in known_chars if char in content)
        score += min(0.4, char_hits * 0.08)

        # Plot advancement keywords - 关键剧情转折
        plot_keywords = [
            "传承", "觉醒", "顿悟", "突破", "飞升", "渡劫",
            "先祖", "先祖之", "血脉觉醒", "功法", "秘籍",
            "阴谋", "真相", "揭露", "复仇", "报仇",
            "异变", "突变", "突变", "降临", "显现",
            "试炼", "考验", "问心", "幻境", "火海",
            "血月教", "九天星辰", "九星玉佩",
        ]
        plot_hits = sum(1 for kw in plot_keywords if kw in content)
        score += min(0.3, plot_hits * 0.1)

        # Dialogue indicates character interaction = important
        quote_count = len(re.findall(r'[""\'\'"].{5,}', content))
        score += min(0.3, quote_count * 0.06)

        return min(1.0, score)

    def _extract_emotional_tags(self, content: str) -> List[str]:
        """Extract emotional tags from content."""
        tags = []
        tag_map = {
            "热血": ["热血", "沸腾", "激昂", "慷慨"],
            "燃": ["燃", "激战", "拼搏", "奋战"],
            "悲壮": ["悲壮", "惨烈", "牺牲", "陨落", "断臂"],
            "浪漫": ["浪漫", "柔情", "温馨", "甜蜜"],
            "惊悚": ["恐怖", "诡异", "阴森", "毛骨悚然"],
            "搞笑": ["滑稽", "幽默", "捧腹", "喷饭"],
        }
        for tag, keywords in tag_map.items():
            if any(kw in content for kw in keywords):
                tags.append(tag)
        return tags[:5]  # Max 5 tags
