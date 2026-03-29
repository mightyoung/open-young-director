# -*- encoding: utf-8 -*-
"""Consistency manager for video generation.

This module provides the ConsistencyManager class that:
1. Manages character profiles across the novel
2. Manages scene/location profiles
3. Generates storyboards with proper shot planning
4. Enhances prompts with consistent character/scene descriptions

Usage:
    manager = ConsistencyManager(project_id)
    manager.load_or_create_profiles()
    manager.generate_storyboard(chapter=1, content="...")
    enhanced_prompt = manager.enhance_prompt(scene, characters)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import (
    CharacterProfile,
    SceneProfile,
    Shot,
    Storyboard,
    SHOT_TYPES,
    CAMERA_MOVEMENTS,
)


logger = logging.getLogger(__name__)


# Default character templates for xianxia genre
DEFAULT_CHARACTER_TEMPLATES = {
    "少年": {
        "age_appearance": "16-18岁少年",
        "face": "清瘦、剑眉星目、眼神坚毅",
        "hair": "黑色长发，用布带束起",
        "build": "偏瘦但精干，因常年修炼而肌肉紧实",
    },
    "少女": {
        "age_appearance": "15-17岁少女",
        "face": "清秀、眉目如画",
        "hair": "长发或双髻，常配丝带",
        "build": "纤细柔美",
    },
    "长老": {
        "age_appearance": "50-70岁长者",
        "face": "面容沧桑、皱纹深刻、神情威严",
        "hair": "白发或灰发，常束高髻",
        "build": "清瘦但骨架宽大，不怒自威",
    },
    "反派": {
        "age_appearance": "20-30岁",
        "face": "英俊但带邪气、眼神阴鸷",
        "hair": "黑发或紫发",
        "build": "高大健硕",
    },
}


class ConsistencyManager:
    """Manages character and scene consistency for video generation.

    This class maintains:
    - Character profiles: Unified appearance descriptions
    - Scene profiles: Unified environment descriptions
    - Storyboards: Planned shot sequences

    Attributes:
        project_id: Project identifier
        base_dir: Base directory for the novel
        characters_dir: Directory for character profiles
        scenes_dir: Directory for scene profiles
        storyboards_dir: Directory for storyboard files
    """

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        """Initialize ConsistencyManager.

        Args:
            project_id: Project identifier
            base_dir: Base directory. If None, uses default path.
        """
        self.project_id = project_id

        if base_dir is None:
            # Default to lib/knowledge_base/novels for this project
            self.base_dir = Path("lib/knowledge_base/novels") / project_id
        else:
            self.base_dir = Path(base_dir)

        # Subdirectories
        self.visual_ref_dir = self.base_dir / "visual_reference"
        self.characters_dir = self.visual_ref_dir / "characters"
        self.scenes_dir = self.visual_ref_dir / "scenes"
        self.storyboards_dir = self.visual_ref_dir / "storyboards"

        # In-memory caches
        self._character_profiles: Dict[str, CharacterProfile] = {}
        self._scene_profiles: Dict[str, SceneProfile] = {}
        self._storyboards: Dict[int, Storyboard] = {}  # chapter -> storyboard

        # LLM client for generation
        self._kimi_client = None

    @property
    def kimi_client(self):
        """Lazy-load Kimi client."""
        if self._kimi_client is None:
            try:
                from knowledge_base.llm.kimi_client import get_kimi_client
                self._kimi_client = get_kimi_client()
            except Exception as e:
                logger.warning(f"Failed to get Kimi client: {e}")
        return self._kimi_client

    # ============ Directory Management ============

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        self.characters_dir.mkdir(parents=True, exist_ok=True)
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        self.storyboards_dir.mkdir(parents=True, exist_ok=True)

    # ============ Character Profile Management ============

    def get_character_file(self, character_id: str) -> Path:
        """Get path for character profile file."""
        safe_id = re.sub(r'[^\w\s-]', '', character_id).strip()
        return self.characters_dir / f"{safe_id}.json"

    def save_character_profile(self, profile: CharacterProfile) -> Path:
        """Save character profile to file."""
        self._ensure_directories()
        import datetime
        profile.updated_at = datetime.datetime.now()

        file_path = self.get_character_file(profile.character_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved character profile: {file_path}")
        return file_path

    def load_character_profile(self, character_id: str) -> Optional[CharacterProfile]:
        """Load character profile from file."""
        file_path = self.get_character_file(character_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return CharacterProfile.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load character {character_id}: {e}")
            return None

    def get_all_character_ids(self) -> List[str]:
        """Get all saved character IDs."""
        if not self.characters_dir.exists():
            return []
        return [p.stem for p in self.characters_dir.glob("*.json")]

    def load_all_character_profiles(self) -> Dict[str, CharacterProfile]:
        """Load all character profiles into memory."""
        for char_id in self.get_all_character_ids():
            if char_id not in self._character_profiles:
                profile = self.load_character_profile(char_id)
                if profile:
                    self._character_profiles[char_id] = profile
        return self._character_profiles

    def get_character(self, character_id: str) -> Optional[CharacterProfile]:
        """Get character profile (from cache or file)."""
        if character_id in self._character_profiles:
            return self._character_profiles[character_id]
        return self.load_character_profile(character_id)

    def add_character(self, profile: CharacterProfile) -> None:
        """Add character to in-memory cache and save to file."""
        self._character_profiles[profile.character_id] = profile
        self.save_character_profile(profile)

    # ============ Scene Profile Management ============

    def get_scene_file(self, scene_id: str) -> Path:
        """Get path for scene profile file."""
        safe_id = re.sub(r'[^\w\s-]', '', scene_id).strip()
        return self.scenes_dir / f"{safe_id}.json"

    def save_scene_profile(self, profile: SceneProfile) -> Path:
        """Save scene profile to file."""
        self._ensure_directories()
        import datetime
        profile.updated_at = datetime.datetime.now()

        file_path = self.get_scene_file(profile.scene_id)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved scene profile: {file_path}")
        return file_path

    def load_scene_profile(self, scene_id: str) -> Optional[SceneProfile]:
        """Load scene profile from file."""
        file_path = self.get_scene_file(scene_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return SceneProfile.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load scene {scene_id}: {e}")
            return None

    def get_all_scene_ids(self) -> List[str]:
        """Get all saved scene IDs."""
        if not self.scenes_dir.exists():
            return []
        return [p.stem for p in self.scenes_dir.glob("*.json")]

    def load_all_scene_profiles(self) -> Dict[str, SceneProfile]:
        """Load all scene profiles into memory."""
        for scene_id in self.get_all_scene_ids():
            if scene_id not in self._scene_profiles:
                profile = self.load_scene_profile(scene_id)
                if profile:
                    self._scene_profiles[scene_id] = profile
        return self._scene_profiles

    def get_scene(self, scene_id: str) -> Optional[SceneProfile]:
        """Get scene profile (from cache or file)."""
        if scene_id in self._scene_profiles:
            return self._scene_profiles[scene_id]
        return self.load_scene_profile(scene_id)

    def add_scene(self, profile: SceneProfile) -> None:
        """Add scene to in-memory cache and save to file."""
        self._scene_profiles[profile.scene_id] = profile
        self.save_scene_profile(profile)

    # ============ Profile Generation ============

    def generate_character_profile(
        self,
        character_id: str,
        name: str,
        content: str,
        role_type: Optional[str] = None,
    ) -> CharacterProfile:
        """Generate a character profile from content.

        Args:
            character_id: Unique identifier for the character
            name: Character name
            content: Text describing the character
            role_type: Optional type hint (e.g., "少年", "长老", "反派")

        Returns:
            Generated CharacterProfile
        """
        import datetime

        # Extract appearance details from content
        profile_data = {
            "character_id": character_id,
            "name": name,
        }

        # Try LLM-based extraction first
        if self.kimi_client:
            try:
                prompt = f"""分析以下小说文本，提取角色外貌特征描述。

角色名：{name}
文本：
{content[:1000]}

请提取以下信息（用英文输出）：
1. age_appearance: 年龄和外貌特征
2. face: 面部特征
3. hair: 发型描述
4. clothing: 服装描述（包括宗门/身份标志）
5. build: 体型描述
6. accessories: 配饰（如有）
7. expression_range: 常见表情（格式：default/angry/sad/determined等）
8. negative: 需要避免的描述

输出JSON格式，不要其他内容。"""
                messages = [{"role": "user", "content": prompt}]
                result = self.kimi_client.generate(messages)
                if result:
                    # Try to parse as JSON
                    import json
                    try:
                        extracted = json.loads(result)
                        profile_data.update(extracted)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse LLM result as JSON: {result[:100]}")
            except Exception as e:
                logger.warning(f"LLM character extraction failed: {e}")

        # Apply template defaults if role_type provided and fields missing
        if role_type and role_type in DEFAULT_CHARACTER_TEMPLATES:
            template = DEFAULT_CHARACTER_TEMPLATES[role_type]
            for key, value in template.items():
                if key not in profile_data or not profile_data.get(key):
                    profile_data[key] = value

        # Ensure required fields
        if not profile_data.get("age_appearance"):
            profile_data["age_appearance"] = "外貌未描述"
        if not profile_data.get("face"):
            profile_data["face"] = "面容清秀"
        if not profile_data.get("clothing"):
            profile_data["clothing"] = "古装/道袍"
        if not profile_data.get("negative"):
            profile_data["negative"] = "不要：女性化、肥胖、现代服装、高科技元素"

        # Create profile
        profile = CharacterProfile(
            character_id=profile_data["character_id"],
            name=profile_data["name"],
            age_appearance=profile_data.get("age_appearance", ""),
            face=profile_data.get("face", ""),
            hair=profile_data.get("hair", ""),
            clothing=profile_data.get("clothing", ""),
            build=profile_data.get("build", ""),
            accessories=profile_data.get("accessories", ""),
            expression_range=profile_data.get("expression_range", {}),
            negative=profile_data.get("negative", ""),
        )

        return profile

    def generate_scene_profile(
        self,
        scene_id: str,
        name: str,
        content: str,
        location_type: Optional[str] = None,
    ) -> SceneProfile:
        """Generate a scene profile from content.

        Args:
            scene_id: Unique identifier for the scene
            name: Scene name
            content: Text describing the scene
            location_type: Optional type hint (e.g., "仙门宗门", "山洞")

        Returns:
            Generated SceneProfile
        """
        import datetime

        profile_data = {
            "scene_id": scene_id,
            "name": name,
            "location_type": location_type or "未分类",
        }

        # Try LLM-based extraction
        if self.kimi_client:
            try:
                prompt = f"""分析以下小说文本，提取场景/环境特征描述。

场景名：{name}
文本：
{content[:1000]}

请提取以下信息（用英文输出）：
1. architecture: 建筑风格描述
2. exterior: 外部环境描述
3. interior: 内部环境描述（如有）
4. color_palette: 主色调
5. atmosphere: 氛围描述
6. lighting: 光照条件（格式：morning/afternoon/evening/night等）
7. key_props: 主要道具（列表，最多5个）
8. negative: 需要避免的描述

输出JSON格式，不要其他内容。"""
                messages = [{"role": "user", "content": prompt}]
                result = self.kimi_client.generate(messages)
                if result:
                    import json
                    try:
                        extracted = json.loads(result)
                        profile_data.update(extracted)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse LLM result as JSON")
            except Exception as e:
                logger.warning(f"LLM scene extraction failed: {e}")

        # Ensure required fields
        if not profile_data.get("architecture"):
            profile_data["architecture"] = "古风建筑"
        if not profile_data.get("color_palette"):
            profile_data["color_palette"] = "古朴色调"
        if not profile_data.get("atmosphere"):
            profile_data["atmosphere"] = "神秘、庄重"
        if not profile_data.get("lighting"):
            profile_data["lighting"] = {"general": "自然光照"}
        if not profile_data.get("negative"):
            profile_data["negative"] = "不要：现代建筑、塑料、金属质感"

        profile = SceneProfile(
            scene_id=profile_data["scene_id"],
            name=profile_data["name"],
            location_type=profile_data.get("location_type", ""),
            architecture=profile_data.get("architecture", ""),
            exterior=profile_data.get("exterior", ""),
            interior=profile_data.get("interior", ""),
            color_palette=profile_data.get("color_palette", ""),
            atmosphere=profile_data.get("atmosphere", ""),
            lighting=profile_data.get("lighting", {}),
            key_props=profile_data.get("key_props", []),
            negative=profile_data.get("negative", ""),
        )

        return profile

    # ============ Storyboard Generation ============

    def get_storyboard_file(self, chapter: int) -> Path:
        """Get path for storyboard file."""
        return self.storyboards_dir / f"chapter_{chapter:03d}_storyboard.json"

    def save_storyboard(self, storyboard: Storyboard) -> Path:
        """Save storyboard to file."""
        self._ensure_directories()
        file_path = self.get_storyboard_file(storyboard.chapter)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(storyboard.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Saved storyboard: {file_path}")
        return file_path

    def load_storyboard(self, chapter: int) -> Optional[Storyboard]:
        """Load storyboard from file."""
        file_path = self.get_storyboard_file(chapter)
        if not file_path.exists():
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Storyboard.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load storyboard for chapter {chapter}: {e}")
            return None

    def generate_storyboard(
        self,
        chapter: int,
        content: str,
        characters: List[str],
        target_duration: int = 18,
        scenes: Optional[List[str]] = None,
    ) -> Storyboard:
        """Generate a storyboard for a chapter.

        Args:
            chapter: Chapter number
            content: Chapter text content
            characters: List of character IDs appearing in this chapter
            target_duration: Target total duration in seconds (default 18s)
            scenes: Optional list of scene IDs to prioritize

        Returns:
            Generated Storyboard with planned shots
        """
        # Determine number of shots based on duration
        # Rule: 1 shot per 3-5 seconds, adjust for content complexity
        num_shots = max(3, min(6, target_duration // 4))

        shots = []
        scene_ids = scenes or []
        char_ids = characters or []

        # Try LLM-based shot planning
        if self.kimi_client:
            try:
                shot_plan = self._generate_shots_with_llm(
                    chapter, content, char_ids, scene_ids, num_shots
                )
                if shot_plan:
                    shots = shot_plan
            except Exception as e:
                logger.warning(f"LLM storyboard generation failed: {e}")

        # Fallback to rule-based generation
        if not shots:
            shots = self._generate_shots_rule_based(
                chapter, content, char_ids, scene_ids, num_shots, target_duration
            )

        # Create storyboard
        storyboard = Storyboard(
            chapter=chapter,
            title=f"第{chapter}章分镜",
            description=f"共{len(shots)}个镜头，总时长约{target_duration}秒",
            shots=shots,
        )
        storyboard._recalculate_duration()

        # Cache and save
        self._storyboards[chapter] = storyboard
        self.save_storyboard(storyboard)

        return storyboard

    def _generate_shots_with_llm(
        self,
        chapter: int,
        content: str,
        characters: List[str],
        scenes: List[str],
        num_shots: int,
    ) -> Optional[List[Shot]]:
        """Generate shots using LLM."""
        if not self.kimi_client:
            return None

        char_str = ", ".join(characters) if characters else "林渊"
        scene_str = ", ".join(scenes) if scenes else "青云宗"

        prompt = f"""为小说章节生成视频分镜脚本。

章节：第{chapter}章
角色：{char_str}
场景：{scene_str}
目标镜头数：{num_shots}

请为每个镜头指定：
1. time_range: 时间范围（如"0-3s"）
2. shot_type: 镜头类型（establishing/wide/medium/close_up/extreme_close_up等）
3. description: 具体画面描述（中文，50字以内）
4. camera: 镜头运动（static/dolly_in/pan_left/tracking等）
5. emotion: 主要情绪（如有角色）
6. transition: 过渡方式（cut/dissolve/fade）

内容摘要：
{content[:1500]}

输出JSON格式的镜头列表数组，不要其他内容。
格式：[{{"shot_number":1,"time_range":"0-3s","shot_type":"establishing","description":"...","camera":"drone_shot","transition":"cut"}},...]

只输出JSON数组。"""

        messages = [{"role": "user", "content": prompt}]
        result = self.kimi_client.generate(messages)
        if not result:
            return None

        try:
            import json
            shots_data = json.loads(result)
            shots = []
            for s in shots_data:
                shot = Shot(
                    shot_number=s.get("shot_number", 1),
                    time_range=s.get("time_range", "0-3s"),
                    shot_type=s.get("shot_type", "medium"),
                    description=s.get("description", ""),
                    camera=s.get("camera", "static"),
                    character_refs=characters[:1] if characters else [],
                    emotion=s.get("emotion"),
                    vfx=s.get("vfx", ""),
                    transition=s.get("transition", "cut"),
                )
                shots.append(shot)
            return shots
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse shot plan: {e}")
            return None

    def _generate_shots_rule_based(
        self,
        chapter: int,
        content: str,
        characters: List[str],
        scenes: List[str],
        num_shots: int,
        total_duration: int,
    ) -> List[Shot]:
        """Generate shots using rule-based approach."""
        shots = []

        # Calculate time per shot
        duration_per_shot = total_duration // num_shots

        # Standard shot sequence for narrative content
        shot_sequence = [
            ("establishing", "drone_shot", "建立场景全貌"),
            ("wide", "static", "展现主要人物和环境"),
            ("medium", "push_in", "聚焦角色动作"),
            ("close_up", "static", "特写表情/细节"),
            ("medium", "pan_right", "过渡到下一场景"),
            ("wide", "tracking", "展现高潮/结尾"),
        ]

        for i in range(num_shots):
            shot_type, camera, desc = shot_sequence[i % len(shot_sequence)]

            start_time = i * duration_per_shot
            end_time = start_time + duration_per_shot

            shot = Shot(
                shot_number=i + 1,
                time_range=f"{start_time}-{end_time}s",
                shot_type=shot_type,
                description=f"镜头{i+1}：{desc}",
                camera=camera,
                scene_ref=scenes[0] if scenes else None,
                character_refs=[characters[0]] if characters else [],
                emotion=None,
                duration_seconds=duration_per_shot,
                transition="cut" if i < num_shots - 1 else "fade",
            )
            shots.append(shot)

        return shots

    # ============ Prompt Enhancement ============

    def enhance_prompt(
        self,
        scene_description: str,
        characters: Optional[List[str]] = None,
        shot_type: str = "medium",
        emotion: Optional[str] = None,
        time_of_day: Optional[str] = None,
    ) -> str:
        """Enhance a prompt with character and scene consistency.

        Args:
            scene_description: Original scene description
            characters: List of character IDs to include
            shot_type: Type of shot (for scene framing)
            emotion: Target emotion
            time_of_day: Time of day (for lighting)

        Returns:
            Enhanced prompt string with character/scene consistency
        """
        parts = []

        # Scene description
        parts.append(scene_description)

        # Character profiles
        if characters:
            char_profiles = []
            for char_id in characters:
                profile = self.get_character(char_id)
                if profile:
                    char_profiles.append(profile.to_prompt_segment(emotion))
            if char_profiles:
                parts.append(f"Characters: {'; '.join(char_profiles)}")

        return ". ".join(parts)

    # ============ Load/Save All ============

    def load_or_create_profiles(self) -> None:
        """Load all profiles from files into memory."""
        self.load_all_character_profiles()
        self.load_all_scene_profiles()

    def save_all(self) -> None:
        """Save all in-memory profiles to files."""
        for profile in self._character_profiles.values():
            self.save_character_profile(profile)
        for profile in self._scene_profiles.values():
            self.save_scene_profile(profile)
        for storyboard in self._storyboards.values():
            self.save_storyboard(storyboard)
