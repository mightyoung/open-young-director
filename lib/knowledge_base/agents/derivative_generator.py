"""Derivative Content Generator for video prompts, character descriptions, etc."""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Try to import MiniMax media executor
_MINIMAX_EXECUTOR = None


def _get_media_executor():
    """Get or create MiniMaxMediaExecutor instance."""
    global _MINIMAX_EXECUTOR
    if _MINIMAX_EXECUTOR is not None:
        return _MINIMAX_EXECUTOR

    # Try to import from crewai.comfy.minimax
    try:
        from media.minimax_executor import get_media_executor
        _MINIMAX_EXECUTOR = get_media_executor()
        return _MINIMAX_EXECUTOR
    except ImportError:
        logger.warning("MiniMaxMediaExecutor not available, media generation disabled")
        return None


@dataclass
class VideoPrompt:
    """Video generation prompt."""
    scene_name: str
    prompt_text: str
    style_tags: List[str]
    characters: List[str]
    mood: str


@dataclass
class PodcastScript:
    """Podcast script."""
    title: str
    duration_minutes: int
    speakers: List[str]
    content: str


@dataclass
class CharacterDescription:
    """Character description."""
    name: str
    appearance: str
    personality: str
    background: str
    first_appearance: str
    key_relationships: List[str]


class DerivativeContentGenerator:
    """Generates and syncs derivative content from chapters."""

    def __init__(
        self,
        project_id: str,
        kimi_client=None,
        doubao_client=None,
        base_dir_override=None,
        scripts_dir_override=None,
    ):
        self.project_id = project_id
        self.kimi_client = kimi_client
        self.doubao_client = doubao_client
        self.base_dir_override = base_dir_override
        self.scripts_dir_override = scripts_dir_override
        self._characters_cache: Dict[str, CharacterDescription] = {}
        self._extracted_characters: List[str] = []
        # Lazy-load consistency manager
        self._consistency_manager = None

    @property
    def consistency_manager(self):
        """Lazy-load ConsistencyManager."""
        if self._consistency_manager is None:
            try:
                from knowledge_base.consistency import ConsistencyManager
                self._consistency_manager = ConsistencyManager(self.project_id)
                self._consistency_manager.load_or_create_profiles()
                logger.info("ConsistencyManager initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize ConsistencyManager: {e}")
        return self._consistency_manager

    def _get_base_dir(self) -> Path:
        """Get the project base directory for novel chapters."""
        if self.base_dir_override:
            return Path(self.base_dir_override)
        # Use lib/knowledge_base/novels as base directory
        return Path(f"lib/knowledge_base/novels/{self.project_id}")

    def _get_scripts_dir(self) -> Path:
        """Get the scripts directory for video_prompts, podcasts, etc.

        Scripts are stored separately from novel chapters.
        """
        if self.scripts_dir_override:
            return Path(self.scripts_dir_override)

        # Try to get from config manager
        try:
            from agents.config_manager import get_config_manager
            cfg = get_config_manager()
            if cfg.generation.scripts_dir:
                return Path(cfg.generation.scripts_dir)
        except Exception:
            pass

        # Fallback to: lib/knowledge_base/generated_scripts/{project_id}
        return Path(f"lib/knowledge_base/generated_scripts/{self.project_id}")

    def sync_derivatives(self, chapter_range: str = None) -> Dict[str, Any]:
        """Sync derivative content with chapters.

        Args:
            chapter_range: Chapter range like "1-3" or "1,3,5"

        Returns:
            Dict with sync results and generated content counts
        """
        base_dir = self._get_base_dir()

        # Parse chapter range
        if chapter_range:
            chapters_to_sync = self._parse_chapter_range(chapter_range)
        else:
            # Sync all chapters
            chapters_to_sync = list(range(1, 100))

        results = {
            "synced": True,
            "count": 0,
            "fixed_chapters": [],
            "video_prompts": [],
            "character_descriptions": [],
            "scene_descriptions": [],
            "podcasts": [],
            "errors": [],
        }

        video_dir = self._get_scripts_dir() / "video_prompts"
        podcast_dir = self._get_scripts_dir() / "podcasts"
        characters_dir = base_dir / "visual_reference" / "characters"

        # Reset characters cache for each sync
        self._characters_cache = {}
        self._extracted_characters = []

        for chapter_num in chapters_to_sync:
            # Find chapter file
            matching_files = list(base_dir.glob(f"chapters/ch{chapter_num:03d}_*.md"))
            if not matching_files:
                continue

            chapter_file = matching_files[0]

            try:
                content = chapter_file.read_text(encoding="utf-8")

                # Generate video prompts (rule-based or LLM-enhanced)
                video_prompts = self._generate_video_prompts(chapter_num, content)
                for vp in video_prompts:
                    vp_file = video_dir / f"ch{chapter_num:03d}_video_prompt_{vp['scene_index']}.json"
                    vp_file.parent.mkdir(parents=True, exist_ok=True)
                    vp_file.write_text(json.dumps(vp, ensure_ascii=False, indent=2), encoding="utf-8")
                    results["video_prompts"].append(str(vp_file))

                # Generate podcast script (rule-based or LLM-enhanced)
                podcast = self._generate_podcast_script(chapter_num, content)
                if podcast:
                    podcast_file = podcast_dir / f"ch{chapter_num:03d}_podcast.json"
                    podcast_file.parent.mkdir(parents=True, exist_ok=True)
                    podcast_file.write_text(json.dumps(podcast, ensure_ascii=False, indent=2), encoding="utf-8")
                    results["podcasts"].append(str(podcast_file))

                results["fixed_chapters"].append(chapter_num)
                results["count"] += 1

            except Exception as e:
                logger.error(f"Failed to sync chapter {chapter_num}: {e}")
                results["errors"].append(f"Chapter {chapter_num}: {str(e)}")

        # Generate character descriptions from all extracted characters
        unique_characters = list(dict.fromkeys(self._extracted_characters))
        for char_name in unique_characters:
            try:
                char_desc = self.generate_character_description(char_name)
                char_file = characters_dir / f"{char_name}.json"
                char_file.parent.mkdir(parents=True, exist_ok=True)
                char_file.write_text(json.dumps(asdict(char_desc), ensure_ascii=False, indent=2), encoding="utf-8")
                results["character_descriptions"].append(str(char_file))
            except Exception as e:
                logger.error(f"Failed to generate character {char_name}: {e}")

        return results

    def _generate_video_prompts(self, chapter_num: int, content: str) -> List[Dict]:
        """Generate video prompts from chapter content.

        Uses LLM when available for richer prompts, otherwise falls back to rule-based.
        """
        # Extract key scenes from content
        scenes = self._extract_scenes(content)
        # Extract characters for this chapter
        chapter_characters = self._extract_characters_from_content(content)
        self._extracted_characters.extend(chapter_characters)

        prompts = []
        for i, scene in enumerate(scenes[:3]):  # Max 3 prompts per chapter
            # Try LLM-based generation first
            if self.kimi_client:
                prompt_text = self._generate_video_prompt_with_llm(scene, chapter_characters)
            else:
                prompt_text = self._build_video_prompt(scene)

            prompts.append({
                "chapter": chapter_num,
                "scene_index": i + 1,
                "scene_description": scene[:200],
                "prompt_text": prompt_text,
                "style_tags": ["xianxia", "fantasy", "cinematic"],
                "mood": self._detect_mood(scene),
                "characters": chapter_characters[:3],  # Include up to 3 character names
            })

        return prompts

    def _generate_video_prompt_with_llm(
        self,
        scene: str,
        characters: List[str],
        shot_type: str = "medium",
        emotion: Optional[str] = None,
    ) -> str:
        """Generate enhanced video prompt using LLM with consistency injection.

        Generates prompts in the 五维控制坐标系 (Five-Dimensional Control Coordinate System) format:
        - Technical specs: RAW photo, ARRI Alexa 65, 2.39:1, 8K UHD, HDR
        - Global fixed dimensions: character anchoring, environment/lighting anchoring, aesthetic medium anchoring
        - Temporal dynamic dimensions: shot sequence with specific timing (0-3s, 3-5s, etc.)
        - Negative prompts for seedance2.0

        Optimized for MiniMax Hailuo / AI video generation.
        """
        if not self.kimi_client:
            return self._build_video_prompt(scene)

        # Get character consistency info
        char_str = "、".join(characters[:3]) if characters else "林渊"
        char_consistency_info = ""
        if self.consistency_manager:
            char_profiles = []
            for char_name in characters[:3]:
                profile = self.consistency_manager.get_character(char_name)
                if profile:
                    seg = profile.to_prompt_segment(emotion)
                    char_profiles.append(seg)
            if char_profiles:
                char_consistency_info = "\n\n角色一致性描述（必须遵循）：\n" + "\n".join(char_profiles)

        # Get scene consistency info
        scene_consistency_info = ""
        if self.consistency_manager:
            scene_matches = re.findall(r'([^\s，。！？]+祠?|[^\s，。！？]+庙|[^\s，。！？]+山|[^\s，。！？]+宗|[^\s，。！？]+洞府)', scene)
            for scene_name in scene_matches[:2]:
                profile = self.consistency_manager.get_scene(scene_name)
                if profile:
                    seg = profile.to_prompt_segment()
                    scene_consistency_info = "\n\n场景一致性描述（必须遵循）：\n" + seg
                    break

        prompt = f"""为以下仙侠小说场景生成一个英文视频生成提示词，使用五维控制坐标系格式。

场景描述：
{scene[:800]}
{char_consistency_info}
{scene_consistency_info}

请严格按照以下格式生成提示词，使用中文标签分隔各部分，英文正文在标签后：

【RAW photo, 15秒完整连贯影视级视频，shot on ARRI Alexa 65电影机，2.39:1宽银幕电影画幅，8K UHD超清分辨率，HDR高动态范围，自然电影胶片颗粒，超写实真人实拍质感，全程无画面跳变、无人物属性畸变、无光影逻辑混乱，严格遵循五维控制坐标系理论，全局维度锁死+动态维度精准时序控制
【全局固定五维基准】
绝对主体锚定：[主要人物外貌特征描述]，全程保持[人物基调]的人物基调；[次要人物外貌特征描述]，全程保持[人物基调]的人物基调，二人全程外貌、服装、人物属性无跳变
环境场与情绪光影锚定：固定场景为[场景描述]；全局光线为[光线描述]，全程保持[光影效果]，[情绪基调]，全程氛围统一
美学介质与渲染锚定：全程超写实电影级真人实拍质感，无卡通、CG，游戏感，无模糊、无水印、无畸变，全程画质、风格统一
【时序化动态五维精准控制 全流程连贯无切镜卡顿】
0-3秒：[镜头描述]
3-5秒：[镜头描述]
5-8秒：[镜头描述]
8-10秒：[镜头描述]
10-12秒：[镜头描述]
12-14秒：[镜头描述]
14-15秒：[镜头描述]
【seedance2.0专属负面提示词】
CGI, 3D render, Unreal Engine, cartoon, anime, illustration, hand-drawn, painting, deformed characters, disproportionate body, facial distortion, broken fingers, extra limbs, floating characters, cutout feeling, inconsistent light and shadow, lens jump, sudden scene change, choppy motion, unnatural movement, glowing magic effect, floating sparkles, neon light, over-saturated colors, over-bloom, flat lighting, fake mist, blurry picture, out of focus, text, watermark, logo, UI elements, ugly face, distorted perspective, duplicate characters, messy composition】

注意：
1. 所有[]中的内容都需要根据场景描述填充完整
2. 镜头描述需要包含：镜头类型、景别、运动方式、人物动作、光影效果
3. 时间点之间需要平滑过渡，避免跳变
4. 人物外貌、服装、表情必须全程保持一致
5. 只输出完整提示词，不要解释
"""
        messages = [{"role": "user", "content": prompt}]
        try:
            result = self.kimi_client.generate(messages)
            if result and len(result) > 100:
                result = result.strip()
                # Ensure the format is correct
                if "【RAW photo" not in result and "RAW photo" in result.upper():
                    # Try to fix if the LLM didn't follow format
                    logger.warning("LLM didn't follow format exactly, attempting to use result as-is")
                return result
        except Exception as e:
            logger.warning(f"LLM prompt generation failed: {e}")

        return self._build_video_prompt(scene)

    def _generate_podcast_script(self, chapter_num: int, content: str) -> Optional[Dict]:
        """Generate podcast script from chapter content.

        Uses LLM when available for richer content, otherwise falls back to rule-based.
        """
        # Extract summary and key events
        summary = self._extract_summary(content)
        key_events = self._extract_key_events(content)

        # Try LLM-based generation first
        if self.kimi_client:
            try:
                llm_content = self._generate_podcast_content_with_llm(chapter_num, content, summary, key_events)
                if llm_content:
                    return llm_content
            except Exception as e:
                logger.warning(f"LLM podcast generation failed: {e}")

        # Fallback to rule-based
        script = {
            "title": f"第{chapter_num}章播客解读",
            "chapter": chapter_num,
            "duration_minutes": 15,
            "speakers": ["旁白", "解读人"],
            "content": f"""【开场】
欢迎收听《太古魔帝传》第{chapter_num}章解读。

【内容概要】
{summary}

【关键情节】
{chr(10).join(f"- {event}" for event in key_events[:5])}

【深度解读】
- 本章核心冲突分析
- 人物命运转折
- 伏笔与悬念

【结语】
以上就是第{chapter_num}章的全部内容，感谢收听。
""",
        }

        return script

    def _generate_podcast_content_with_llm(self, chapter_num: int, content: str, summary: str, key_events: List[str]) -> Optional[Dict]:
        """Generate enhanced podcast content using LLM."""
        if not self.kimi_client:
            return None

        # Get first 2000 chars of body content
        parts = content.split('\n---\n')
        body = '\n'.join(parts[1:]) if len(parts) > 1 else content[:2000]
        if len(body) > 2000:
            body = body[:2000]

        events_str = "\n".join(f"- {e}" for e in key_events[:5]) if key_events else "（无）"

        prompt = f"""为《太古魔帝传》第{chapter_num}章生成播客解读脚本。

本章概要：
{summary}

关键事件：
{events_str}

本章内容（部分）：
{body}

请生成一个完整的播客脚本，包含：
1. 开场介绍
2. 内容概要（简洁）
3. 关键情节分析（2-3个重点）
4. 深度解读（人物、主题、伏笔）
5. 结语

直接输出脚本内容，不要说明。"""

        try:
            messages = [{"role": "user", "content": prompt}]
            result = self.kimi_client.generate(messages)
            if result and len(result) > 50:
                return {
                    "title": f"第{chapter_num}章播客解读",
                    "chapter": chapter_num,
                    "duration_minutes": 15,
                    "speakers": ["旁白", "解读人"],
                    "content": result,
                }
        except Exception as e:
            logger.warning(f"LLM podcast content generation failed: {e}")

        return None

    def _extract_scenes(self, content: str) -> List[str]:
        """Extract scenes from chapter content using generic narrative structure markers."""
        # Skip header (everything before first ---)
        parts = content.split('\n---\n')
        if len(parts) > 1:
            body = '\n'.join(parts[1:])
        else:
            body = content

        # Generic scene segmentation using narrative structure markers
        # Matches: chapter markers (第X章), scene transitions (突然, 就在此时, 与此同时),
        # location changes (in xianxia: 山崖, 庙, 宗, 殿, 洞府, etc.)
        scene_pattern = r'\n(?=第[一二三四五六七八九十百千\d]+章|突然|就在此时|与此同时|[^，,]*[山崖庙宗殿洞府城镇村庄]里?[^，,]*[，。,])'
        scenes = re.split(scene_pattern, body)

        # Also try splitting by double newlines (paragraph breaks) for shorter content
        if len(scenes) < 2 or all(len(s) < 200 for s in scenes):
            scenes = re.split(r'\n\n+', body)

        # Filter and clean
        result = []
        for scene in scenes:
            scene = scene.strip()
            # Skip if it's too short or looks like a header
            if len(scene) > 100 and not scene.startswith('#'):
                result.append(scene)

        return result if result else [body[:500]]

    def _extract_characters_from_content(self, content: str) -> List[str]:
        """Extract character names from chapter content.

        Returns list of unique character names found in this chapter.
        Requires at least 2 occurrences AND proper context (not substring of another name).
        """
        # Known character patterns from the novel (2+ char names to avoid substring issues)
        known_characters = [
            "韩林", "柳如烟", "叶尘", "叶天行", "韩啸天", "韩天啸",
            "赵元启", "小六子", "小蝶", "老周头", "逆仙", "太古魔帝",
            "林渊", "赵无极", "李长青",
        ]

        found_characters = []
        for char in known_characters:
            # Count occurrences - require at least 2 for valid character
            count = content.count(char)
            if count >= 2:
                # Verify it's not just a substring of a longer name
                # by checking if char is followed/preceded by another common surname
                safe_to_add = True
                for other in known_characters:
                    if other != char and other.startswith(char):
                        # e.g., "林" would be substring of "林渊" - skip
                        safe_to_add = False
                        break
                if safe_to_add:
                    found_characters.append(char)

        return list(dict.fromkeys(found_characters))  # Preserve order, remove dupes

    def _extract_summary(self, content: str) -> str:
        """Extract chapter summary from header."""
        match = re.search(r'\*\*本章概要\*\*:\s*(.+)', content)
        if match:
            return match.group(1).strip()
        return content[:300] + "..."

    def _extract_key_events(self, content: str) -> List[str]:
        """Extract key events from chapter."""
        match = re.search(r'\*\*关键事件\*\*:\s*(.+)', content)
        if match:
            events_str = match.group(1)
            # Split by comma or顿号
            events = re.split(r'[,，]', events_str)
            return [e.strip() for e in events if e.strip()]
        return []

    def _build_video_prompt(self, scene: str) -> str:
        """Build video generation prompt from scene using 五维控制坐标系 format.

        Extracts contextual information from the scene to fill in specific details.
        The format includes:
        - Technical specs: RAW photo, ARRI Alexa 65, 2.39:1, 8K UHD, HDR
        - Global fixed dimensions: character, environment, lighting, aesthetic
        - Temporal sequence: 0-3s, 3-5s, etc.
        - Negative prompts for seedance2.0
        """
        # Clean and truncate scene
        scene_clean = scene[:800].replace('\n', ' ').strip()

        # Extract characters mentioned
        characters_in_scene = re.findall(r'(韩林|柳如烟|叶尘|赵元启|小六子|小蝶|老周头)+', scene_clean)
        characters = list(dict.fromkeys(characters_in_scene)) if characters_in_scene else ["韩林"]

        # Determine scene location
        location = "太虚宗演武场"
        if "测灵台" in scene_clean:
            location = "太虚宗演武场测灵台"
        elif "山崖" in scene_clean or "崖" in scene_clean:
            location = "太虚宗后山山崖"
        elif "宗门" in scene_clean:
            location = "太虚宗宗门大殿"
        elif "洞府" in scene_clean:
            location = "洞府"

        # Extract mood/emotion
        mood = self._detect_mood(scene_clean)
        mood_desc = {
            "action": "激烈对抗，剑拔弩张",
            "romantic": "柔情蜜意，暗生情愫",
            "sad": "悲凉凄怆，催人泪下",
            "mysterious": "神秘诡异，危机四伏",
            "happy": "欢快愉悦，喜气洋洋",
            "dramatic": "戏剧张力，悬念丛生",
        }.get(mood, "戏剧张力，悬念丛生")

        # Build character anchor based on detected characters
        if "韩林" in characters and "柳如烟" in characters:
            char_anchor = "20岁男性韩林，洗得发白的青色长袍，黑色短发，身形挺拔，全程保持沉静坚毅、隐忍克制的人物基调；20岁女性柳如烟，一袭垂坠感素白长裙，青丝柔顺，肌肤细腻，全程保持清冷决绝、疏离傲慢的人物基调，二人全程外貌、服装、人物属性无跳变"
        elif "韩林" in characters:
            char_anchor = "20岁男性韩林，洗得发白的青色长袍，黑色短发，身形挺拔，全程保持沉静坚毅、隐忍克制的人物基调，全程外貌、服装、人物属性无跳变"
        elif "柳如烟" in characters:
            char_anchor = "20岁女性柳如烟，一袭垂坠感素白长裙，青丝柔顺，肌肤细腻，全程保持清冷决绝、疏离傲慢的人物基调，全程外貌、服装、人物属性无跳变"
        else:
            char_anchor = f"{characters[0]}，[具体外貌描述]，[服装描述]，全程保持[人物基调]的人物基调，全程外貌、服装、人物属性无跳变"

        # Build the temporal sequence based on scene content
        if "玉佩" in scene_clean or "退婚" in scene_clean:
            # Jade pendant breaking scene
            seq_0_3 = "航拍全景，35mm电影广角镜头，镜头匀速垂直稳定下降，聚焦演武场中央测灵台与全场围观人群，完整呈现晨光薄雾中的演武场全貌"
            seq_3_5 = "镜头顺滑过渡锁定演武场边缘的韩林，50mm标准镜头，中景景别，镜头缓慢匀速向前推进，韩林独自静立，脊背挺直，目光望向测灵台方向，无多余动作"
            seq_5_8 = "镜头顺滑过渡跟拍柳如烟，50mm标准镜头，中景跟拍，镜头随柳如烟步伐匀速同步向前推进，柳如烟从东侧高台缓步向前行走，裙摆随步伐自然垂坠摆动，神情冷漠决绝"
            seq_8_10 = "镜头顺滑过渡切换90mm微距镜头，特写聚焦玉佩与手部，120fps慢动作拍摄，镜头稳定无抖动，柳如烟抬手松开玉佩，玉佩垂直坠落撞击地面碎裂，碎片向四周自然飞溅，晨光在碎片表面折射形成细碎自然闪光"
            seq_10_12 = "镜头顺滑过渡切回50mm标准镜头，双人中景景别，镜头稳定横移至二人正中位置，侧逆光勾勒二人轮廓，韩林与柳如烟相隔数步站立，正面无言对视，无多余肢体动作"
            seq_12_14 = "镜头顺滑过渡切换为过肩镜头（从柳如烟肩头望向韩林），85mm人像镜头，面部特写，镜头缓慢匀速向前推近，韩林眉头微锁，目光平静无波澜，脊背始终挺直，凸显隐忍克制的情绪"
            seq_14_15 = "镜头顺滑过渡切换90mm微距镜头，手部特写，镜头固定，韩林手部五指缓慢收紧成拳，画面随动作完成自然淡出收尾"
        elif "测灵" in scene_clean or "灵根" in scene_clean:
            # Spirit testing scene
            seq_0_3 = "航拍全景，35mm电影广角镜头，镜头匀速垂直稳定下降，聚焦演武场中央测灵台，完整呈现晨光薄雾中的测灵台全貌与围观人群"
            seq_3_5 = "镜头顺滑过渡锁定测灵台前的韩林，50mm标准镜头，中景景别，镜头缓慢匀速向前推进，韩林独自静立，脊背挺直，目光望向测灵台"
            seq_5_8 = "镜头顺滑过渡跟拍韩林走向测灵台，50mm标准镜头，中景跟拍，镜头随韩林步伐匀速同步向前推进，韩林神情凝重，步伐沉稳"
            seq_8_10 = "镜头顺滑过渡切换测灵台特写，90mm微距镜头，120fps慢动作拍摄，测灵台上的灵石开始发光，光芒逐渐变强"
            seq_10_12 = "镜头顺滑过渡切回50mm标准镜头，双人中景景别，镜头稳定横移至韩林与测灵台正中位置，侧逆光勾勒韩林轮廓"
            seq_12_14 = "镜头顺滑过渡切换韩林面部特写，85mm人像镜头，镜头缓慢匀速向前推近，韩林眉头紧锁，目光中透露出坚定与不屈"
            seq_14_15 = "镜头顺滑过渡切换手部特写，90mm微距镜头，镜头固定，韩林手部五指缓慢收紧成拳，画面随动作完成自然淡出收尾"
        else:
            # Default sequence
            seq_0_3 = "航拍全景，35mm电影广角镜头，镜头匀速垂直稳定下降，聚焦场景核心区域，完整呈现晨光薄雾中的场景全貌"
            seq_3_5 = "镜头顺滑过渡锁定主要人物，50mm标准镜头，中景景别，镜头缓慢匀速向前推进，人物独自静立，脊背挺直，目光望向目标方向，无多余动作"
            seq_5_8 = "镜头顺滑过渡跟拍次要人物，50mm标准镜头，中景跟拍，镜头随人物步伐匀速同步向前推进，人物神情[根据场景填充]，步伐沉稳"
            seq_8_10 = "镜头顺滑过渡切换90mm微距镜头，特写聚焦关键物品或手部，120fps慢动作拍摄，镜头稳定无抖动，物品动作或表情变化"
            seq_10_12 = "镜头顺滑过渡切回50mm标准镜头，双人中景景别，镜头稳定横移至二人正中位置，侧逆光勾勒人物轮廓，人物关系描述"
            seq_12_14 = "镜头顺滑过渡切换为过肩镜头，85mm人像镜头，面部特写，镜头缓慢匀速向前推近，人物眉头微锁，目光平静无波澜，情绪描述"
            seq_14_15 = "镜头顺滑过渡切换90mm微距镜头，手部特写，镜头固定，人物手部动作（如收紧成拳），画面随动作完成自然淡出收尾"

        prompt = f"""【RAW photo, 15秒完整连贯影视级视频，shot on ARRI Alexa 65电影机，2.39:1宽银幕电影画幅，8K UHD超清分辨率，HDR高动态范围，自然电影胶片颗粒，超写实真人实拍质感，全程无画面跳变、无人物属性畸变、无光影逻辑混乱，严格遵循五维控制坐标系理论，全局维度锁死+动态维度精准时序控制
【全局固定五维基准】
绝对主体锚定：{char_anchor}
环境场与情绪光影锚定：固定场景为{location}；全局光线为低角度金色晨光穿透薄雾形成自然丁达尔体积光，全程保持冷白色轮廓光勾勒人物边缘，光影入射方向全程统一为画面左侧；全局情绪基调为{mood_desc}，全程氛围统一
美学介质与渲染锚定：全程超写实电影级真人实拍质感，无卡通、CG，游戏感，无模糊、无水印、无畸变，全程画质、风格统一
【时序化动态五维精准控制 全流程连贯无切镜卡顿】
0-3秒：{seq_0_3}
3-5秒：{seq_3_5}
5-8秒：{seq_5_8}
8-10秒：{seq_8_10}
10-12秒：{seq_10_12}
12-14秒：{seq_12_14}
14-15秒：{seq_14_15}
【seedance2.0专属负面提示词】
CGI, 3D render, Unreal Engine, cartoon, anime, illustration, hand-drawn, painting, deformed characters, disproportionate body, facial distortion, broken fingers, extra limbs, floating characters, cutout feeling, inconsistent light and shadow, lens jump, sudden scene change, choppy motion, unnatural movement, glowing magic effect, floating sparkles, neon light, over-saturated colors, over-bloom, flat lighting, fake mist, blurry picture, out of focus, text, watermark, logo, UI elements, ugly face, distorted perspective, duplicate characters, messy composition"""
        return prompt

    def _detect_mood(self, text: str) -> str:
        """Detect emotional mood of text using multi-character word matching."""
        # Use word boundaries and multi-character patterns to avoid false positives
        # e.g., "战" alone could match in "林渊战斗" but we want actual combat words

        action_patterns = [
            r'战斗|厮杀|搏斗|激战|开战|宣战|战争|战役',
            r'愤怒|怒气|恼怒|暴怒|愤恨',
            r'激烈|猛烈|紧张|惊险|生死|对决',
        ]
        romantic_patterns = [
            r'爱情|爱慕|恋爱|倾心|甜蜜|温柔|浪漫|柔情',
            r'相依|相守|陪伴|厮守|红线|情缘',
        ]
        sad_patterns = [
            r'悲伤|悲痛|痛苦|伤心|流泪|泪水|哭泣|泪流|失落|绝望|无助',
            r'死去|死亡|灭亡|陨落|牺牲|诀别|永别',
        ]
        mysterious_patterns = [
            r'神秘|诡异|悬疑|阴谋|陷阱|谜团',
            r'未知|危险|阴暗|黑暗|幽暗',
        ]
        happy_patterns = [
            r'喜悦|欢喜|高兴|开心|快乐|欢快|兴奋|欢呼|雀跃',
            r'欢笑|大笑|狂喜|喜极|庆功|欢庆',
        ]

        def count_matches(patterns):
            """Count total pattern matches in text."""
            total = 0
            for pattern in patterns:
                total += len(re.findall(pattern, text))
            return total

        scores = {
            "action": count_matches(action_patterns),
            "romantic": count_matches(romantic_patterns),
            "sad": count_matches(sad_patterns),
            "mysterious": count_matches(mysterious_patterns),
            "happy": count_matches(happy_patterns),
        }

        # Return mood with highest score, default to dramatic
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "dramatic"

    def _detect_location(self, text: str) -> str:
        """Detect scene location from text.

        Returns a location string for video prompt generation.
        """
        location_patterns = {
            "太虚宗演武场测灵台": [r"测灵台", r"演武场.*测灵"],
            "太虚宗演武场": [r"演武场", r"演武场"],
            "太虚宗后山山崖": [r"山崖", r"后山.*崖", r"崖边"],
            "太虚宗宗门大殿": [r"宗门大殿", r"大殿", r"宗门"],
            "洞府": [r"洞府", r"修炼室"],
            "山谷": [r"山谷", r"谷中"],
            "密林": [r"密林", r"丛林", r"树林"],
            "湖畔": [r"湖畔", r"湖边", r"湖心"],
            "城镇": [r"城镇", r"街道", r"集市"],
            "宫殿": [r"宫殿", r"王府", r"皇宫"],
        }

        for location, patterns in location_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return location

        # Default location
        return "太虚宗演武场"

    def _parse_chapter_range(self, chapter_range: str) -> List[int]:
        """Parse chapter range string into list of chapter numbers."""
        chapters = set()
        for part in chapter_range.split(","):
            part = part.strip()
            if "-" in part:
                match = re.match(r"(\d+)-(\d+)", part)
                if match:
                    start, end = int(match.group(1)), int(match.group(2))
                    chapters.update(range(start, end + 1))
            else:
                match = re.match(r"\d+", part)
                if match:
                    chapters.add(int(match.group(0)))

        return sorted(chapters)

    def generate_video_prompt(self, chapter_number: int) -> VideoPrompt:
        """Generate video prompt for a chapter.

        Uses Doubao LLM when available for enhanced 五维控制坐标系 prompts,
        otherwise falls back to rule-based _build_video_prompt.
        """
        base_dir = self._get_base_dir()
        chapter_file = list(base_dir.glob(f"chapters/ch{chapter_number:03d}_*.md"))

        if chapter_file:
            content = chapter_file[0].read_text(encoding="utf-8")
            scenes = self._extract_scenes(content)
            if scenes:
                scene = scenes[0]
                characters = self._extract_characters_from_content(content)
                mood = self._detect_mood(scene)

                # Try Doubao LLM if available
                if self.doubao_client:
                    try:
                        location = self._detect_location(scene)
                        enhanced_prompt = self.doubao_client.generate_video_prompt(
                            scene_description=scene,
                            characters=characters,
                            location=location,
                            mood=mood,
                        )
                        if enhanced_prompt:
                            return VideoPrompt(
                                scene_name=f"Chapter {chapter_number} Scene",
                                prompt_text=enhanced_prompt,
                                style_tags=["xianxia", "fantasy", "cinematic"],
                                characters=characters,
                                mood=mood,
                            )
                    except Exception as e:
                        logger.warning(f"Doubao video prompt generation failed: {e}")

                # Fallback to rule-based prompt
                return VideoPrompt(
                    scene_name=f"Chapter {chapter_number} Scene",
                    prompt_text=self._build_video_prompt(scene),
                    style_tags=["xianxia", "fantasy", "cinematic"],
                    characters=characters,
                    mood=mood,
                )

        return VideoPrompt(
            scene_name=f"Chapter {chapter_number} Scene",
            prompt_text="A dramatic xianxia scene",
            style_tags=["xianxia", "fantasy"],
            characters=[],
            mood="dramatic",
        )

    def generate_character_description(self, character_name: str) -> CharacterDescription:
        """Generate character description for a character.

        Uses LLM when available for richer descriptions, otherwise uses rule-based extraction.
        """
        # Check cache first
        if character_name in self._characters_cache:
            return self._characters_cache[character_name]

        base_dir = self._get_base_dir()

        # Try to find character mentions across all chapters
        character_content = ""
        for chapter_file in sorted(base_dir.glob("chapters/ch*.md")):
            content = chapter_file.read_text(encoding="utf-8")
            if character_name in content:
                # Extract paragraphs mentioning this character
                paragraphs = content.split('\n\n')
                relevant = [p for p in paragraphs if character_name in p]
                character_content += '\n'.join(relevant[:5]) + '\n'

        if len(character_content) > 100:
            # Try LLM-based generation
            if self.kimi_client:
                try:
                    char_desc = self._generate_character_with_llm(character_name, character_content)
                    if char_desc:
                        self._characters_cache[character_name] = char_desc
                        return char_desc
                except Exception as e:
                    logger.warning(f"LLM character description for {character_name} failed: {e}")

            # Fallback to rule-based extraction
            desc = self._extract_character_rule_based(character_name, character_content)
            self._characters_cache[character_name] = desc
            return desc

        # Default description if not enough content
        default = CharacterDescription(
            name=character_name,
            appearance="待描述",
            personality="待分析",
            background="待完善",
            first_appearance="未知",
            key_relationships=[],
        )
        self._characters_cache[character_name] = default
        return default

    def _generate_character_with_llm(self, character_name: str, content: str) -> Optional[CharacterDescription]:
        """Generate character description using LLM."""
        if not self.kimi_client:
            return None

        prompt = f"""分析以下小说内容，为角色"{character_name}"生成详细的人物描述。

内容片段：
{content[:3000]}

请生成以下信息：
1. 外貌特征（appearance）
2. 性格特点（personality）
3. 背景故事（background）
4. 首次出场场景（first_appearance）
5. 关键人物关系（key_relationships）

输出格式（JSON）：
{{
    "name": "{character_name}",
    "appearance": "外貌特征描述",
    "personality": "性格特点描述",
    "background": "背景故事描述",
    "first_appearance": "首次出场描述",
    "key_relationships": ["关系1", "关系2"]
}}

只输出JSON，不要其他内容。"""

        try:
            messages = [{"role": "user", "content": prompt}]
            result = self.kimi_client.generate(messages)
            if result:
                # Parse JSON from result
                import json
                # Try to extract JSON from the response
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    data = json.loads(json_match.group())
                    return CharacterDescription(
                        name=character_name,
                        appearance=data.get("appearance", "待描述"),
                        personality=data.get("personality", "待分析"),
                        background=data.get("background", "待完善"),
                        first_appearance=data.get("first_appearance", "未知"),
                        key_relationships=data.get("key_relationships", []),
                    )
        except Exception as e:
            logger.warning(f"LLM character generation parse failed: {e}")

        return None

    def _extract_character_rule_based(self, character_name: str, content: str) -> CharacterDescription:
        """Extract character description using rule-based analysis."""
        # Simple rule-based extraction
        # Look for common patterns

        # Extract first appearance context
        first_match = re.search(rf'[，。\n]({character_name}[^。\n]*)[。\n]', content)
        first_appearance = first_match.group(1)[:100] if first_match else "未知"

        # Look for personality indicators
        personality_indicators = {
            "冷静": "冷静沉稳",
            "傲慢": "傲慢自大",
            "善良": "善良温和",
            "狡猾": "狡猾精明",
            "勇敢": "勇敢坚韧",
            "懦弱": "懦弱胆怯",
        }

        personality = []
        for key, value in personality_indicators.items():
            if key in content:
                personality.append(value)

        personality_str = "、".join(personality) if personality else "复杂多面"

        # Look for relationships
        relationships = []
        known_chars = ["韩林", "柳如烟", "叶尘", "赵元启", "老周头", "小六子", "小蝶"]
        for other in known_chars:
            if other != character_name and other in content:
                idx = content.find(other)
                context = content[max(0, idx-20):idx+20]
                if '父亲' in context or '母亲' in context or '师父' in context:
                    relationships.append(f"{other}（亲属）")
                elif '未婚' in context or '婚约' in context:
                    relationships.append(f"{other}（婚约）")
                elif '对手' in context or '敌人' in context:
                    relationships.append(f"{other}（对手）")

        return CharacterDescription(
            name=character_name,
            appearance="待描述",
            personality=personality_str,
            background="待完善",
            first_appearance=first_appearance,
            key_relationships=relationships[:5],
        )

    def generate_podcast_script(self, chapter_range: str) -> PodcastScript:
        """Generate podcast script for chapter range."""
        return PodcastScript(
            title=f"Chapters {chapter_range} Discussion",
            duration_minutes=30,
            speakers=["Host", "Guest"],
            content="播客内容占位符",
        )

    def list_derivatives(self) -> Dict[str, Any]:
        """List available derivative content."""
        base_dir = self._get_base_dir()

        def count_files(pattern):
            return len(list(base_dir.glob(pattern)))

        return {
            "fixed_chapters": list(range(1, 7)),
            "video_prompt_count": count_files("video_prompts/*.json"),
            "character_count": count_files("visual_reference/characters/*.json"),
            "scene_count": count_files("visual_reference/scenes/*.json"),
            "podcast_count": count_files("podcasts/*.json"),
            "last_sync": None,
        }


def get_derivative_generator(
    project_id: str,
    kimi_client=None,
    doubao_client=None,
    base_dir_override=None,
    scripts_dir_override=None,
) -> DerivativeContentGenerator:
    """Get a DerivativeContentGenerator instance.

    Args:
        project_id: Project identifier
        kimi_client: Optional Kimi LLM client for character descriptions
        doubao_client: Optional Doubao LLM client for enhanced video prompts
        base_dir_override: Override base directory path
        scripts_dir_override: Override scripts directory path
    """
    return DerivativeContentGenerator(
        project_id,
        kimi_client=kimi_client,
        doubao_client=doubao_client,
        base_dir_override=base_dir_override,
        scripts_dir_override=scripts_dir_override,
    )
