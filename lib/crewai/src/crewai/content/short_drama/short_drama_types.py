"""Short Drama 类型定义

定义短剧生成所需的核心数据类型：
- Shot: 视频生成的最小单元
- ShortDramaEpisode: 单集剧本（包含场景列表）
- ShortDramaBible: ProductionBible 的短剧适配版
- ShortDramaPipelineState: 流水线状态管理
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

# 复用已有的 PipelineState 和 CharacterProfile
from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.production_bible.bible_types import CharacterProfile


# ============================================================================
# Shot - 视频生成的最小单元
# ============================================================================


@dataclass
class Shot:
    """Shot — 视频生成的最小单元

    每个 Shot 代表一个 3-8 秒的视频片段，包含：
    - 镜头基本信息（编号、时长、类型）
    - 角色和动作描述
    - 视频生成提示词（Seedance2 五维格式）
    - 配音词
    """
    shot_number: int  # 镜头序号
    scene_number: int  # 所属场景序号
    duration_seconds: float  # 时长（3-8秒）
    shot_type: str  # establishing, wide, medium, close_up, etc.
    action: str  # 镜头动作描述
    characters: list[str]  # 出场角色列表
    video_prompt: str  # Seedance2 五维 Prompt
    voiceover_segment: str  # 对应配音词
    emotion: str  # 情绪基调

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Shot":
        """从字典创建"""
        return cls(**data)


# ============================================================================
# ShortDramaScene - 单个场景（由多个 Shot 组成）
# ============================================================================


@dataclass
class ShortDramaScene:
    """ShortDramaScene — 单个场景

    场景是情节发展的基本单元，由多个连续的 Shot 组成。
    """
    scene_number: int  # 场景序号
    location: str  # 地点
    time_of_day: str  # 时间段
    description: str  # 场景描述
    shots: list[Shot] = field(default_factory=list)  # 镜头列表
    voiceover: str = ""  # 场景级配音（可选）

    def add_shot(self, shot: Shot) -> None:
        """添加镜头"""
        self.shots.append(shot)

    def get_duration(self) -> float:
        """获取场景总时长"""
        return sum(s.duration_seconds for s in self.shots)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "scene_number": self.scene_number,
            "location": self.location,
            "time_of_day": self.time_of_day,
            "description": self.description,
            "shots": [s.to_dict() for s in self.shots],
            "voiceover": self.voiceover,
        }


# ============================================================================
# ShortDramaEpisode - 单集剧本
# ============================================================================


@dataclass
class ShortDramaEpisode:
    """ShortDramaEpisode — 单集剧本

    包含一集完整的内容：
    - 集号和标题
    - 场景列表
    - 集级配音
    - 尾帧信息（用于多集串联）
    """
    episode_num: int  # 集号
    title: str  # 集标题
    summary: str  # 剧情概要
    scenes: list[ShortDramaScene] = field(default_factory=list)  # 场景列表
    voiceover_intro: str = ""  # 开场配音
    voiceover_outro: str = ""  # 结尾配音
    episode_context: str = ""  # 本集剧情承接（上集结尾）
    end_frame: dict = field(default_factory=dict)  # 尾帧信息（用于下一集串联）

    def add_scene(self, scene: ShortDramaScene) -> None:
        """添加场景"""
        self.scenes.append(scene)

    def get_duration(self) -> float:
        """获取本集总时长（秒）"""
        return sum(s.get_duration() for s in self.scenes)

    def get_all_shots(self) -> list[Shot]:
        """获取所有镜头"""
        shots = []
        for scene in self.scenes:
            shots.extend(scene.shots)
        return shots

    def get_characters(self) -> set[str]:
        """获取本集所有出场角色"""
        chars = set()
        for scene in self.scenes:
            for shot in scene.shots:
                chars.update(shot.characters)
        return chars

    def get_end_frame(self) -> dict:
        """获取尾帧信息（用于下一集串联）"""
        if self.end_frame:
            return self.end_frame

        # 如果没有预设尾帧，从最后一个镜头生成
        all_shots = self.get_all_shots()
        if not all_shots:
            return {}

        last_shot = all_shots[-1]
        last_scene = self.scenes[-1] if self.scenes else None

        return {
            "character_state": f"{', '.join(last_shot.characters)} {last_shot.action}" if last_shot.characters else last_shot.action,
            "background": last_scene.location if last_scene else "未知",
            "lighting": "自然光",
            "composition": "中景构图",
            "mood": last_shot.emotion or "平静",
            "camera_state": "固定镜头",
            "motion_state": "静止",
        }

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "episode_num": self.episode_num,
            "title": self.title,
            "summary": self.summary,
            "scenes": [s.to_dict() for s in self.scenes],
            "voiceover_intro": self.voiceover_intro,
            "voiceover_outro": self.voiceover_outro,
            "episode_context": self.episode_context,
            "end_frame": self.end_frame,
        }


# ============================================================================
# ShortDramaBible - ProductionBible 的短剧适配版
# ============================================================================


@dataclass
class ShortDramaBible:
    """ShortDramaBible — 短剧版 ProductionBible

    专门为短剧生成设计的圣经，包含：
    - 本集出场角色
    - 简化版世界观规则
    - 本集剧情承接
    - 统一视觉风格
    """
    episode_num: int  # 集号
    series_title: str  # 系列标题
    relevant_characters: dict[str, CharacterProfile]  # 本集出场角色
    world_rules_summary: str  # 简化版世界观规则
    episode_context: str  # 本集剧情承接
    visual_style: str  # 统一视觉风格
    tone: str  # 整体基调（古风/现代/科幻）

    def get_character(self, name: str) -> Optional[CharacterProfile]:
        """获取角色信息"""
        return self.relevant_characters.get(name)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "episode_num": self.episode_num,
            "series_title": self.series_title,
            "relevant_characters": {
                name: asdict(profile) for name, profile in self.relevant_characters.items()
            },
            "world_rules_summary": self.world_rules_summary,
            "episode_context": self.episode_context,
            "visual_style": self.visual_style,
            "tone": self.tone,
        }


# ============================================================================
# ShortDramaPipelineState - 流水线状态
# ============================================================================


@dataclass
class ShortDramaPipelineState(PipelineState):
    """ShortDramaPipelineState — 短剧流水线状态

    继承自 PipelineState，添加短剧特有的状态字段：
    - short_drama_bible: 短剧圣经
    - episodes: 剧集列表
    - shots_per_episode: 每集的镜头列表
    - audio_files: 音频文件路径
    - video_segments: 视频片段路径
    """
    short_drama_bible: Optional[ShortDramaBible] = None
    current_episode: int = 0
    episodes: list[ShortDramaEpisode] = field(default_factory=list)
    shots_per_episode: list[list[Shot]] = field(default_factory=list)
    audio_files: list[str] = field(default_factory=list)
    video_segments: list[str] = field(default_factory=list)

    def add_episode(self, episode: ShortDramaEpisode) -> None:
        """添加剧集"""
        self.episodes.append(episode)
        self.current_episode = len(self.episodes)

    def add_shots(self, episode_idx: int, shots: list[Shot]) -> None:
        """添加镜头到指定剧集"""
        while len(self.shots_per_episode) <= episode_idx:
            self.shots_per_episode.append([])
        self.shots_per_episode[episode_idx].extend(shots)

    def get_current_episode(self) -> Optional[ShortDramaEpisode]:
        """获取当前剧集"""
        if 0 <= self.current_episode - 1 < len(self.episodes):
            return self.episodes[self.current_episode - 1]
        return None

    def to_summary(self) -> dict:
        """获取摘要"""
        base = super().to_summary()
        base.update({
            "short_drama_episodes": len(self.episodes),
            "total_shots": sum(len(shots) for shots in self.shots_per_episode),
            "audio_files": len(self.audio_files),
            "video_segments": len(self.video_segments),
        })
        return base


# ============================================================================
# EpisodeOutline - 集大纲（生成阶段的中间产物）
# ============================================================================


@dataclass
class EpisodeOutline:
    """EpisodeOutline — 集大纲

    用于 EpisodeOutlineCrew 生成的集大纲，包含场景规划和尾帧。
    """
    episode_num: int  # 集号
    title: str  # 集标题
    episode_summary: str  # 集概要
    scene_plan: list[dict] = field(default_factory=list)  # 场景规划列表
    end_frame: dict = field(default_factory=dict)  # 尾帧信息（用于下一集串联）

    # 每个场景的信息
    # {
    #     "scene_number": 1,
    #     "location": "演武场",
    #     "time_of_day": "清晨",
    #     "description": "主角首次登场",
    #     "key_actions": ["主角入场", "测灵仪式", "震惊全场"],
    #     "characters": ["韩林", "长老", "对手"],
    #     "emotion": "紧张/兴奋",
    #     "duration_estimate": 30,  # 秒
    #     "is_opening": true,
    #     "is_ending": false
    # }

    # 尾帧信息
    # {
    #     "character_state": "主角回眸一笑，眼神中带着坚定",
    #     "background": "太虚宗演武场",
    #     "lighting": "夕阳余晖",
    #     "mood": "释然/坚定"
    # }

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "episode_num": self.episode_num,
            "title": self.title,
            "episode_summary": self.episode_summary,
            "scene_plan": self.scene_plan,
            "end_frame": self.end_frame,
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "Shot",
    "ShortDramaScene",
    "ShortDramaEpisode",
    "ShortDramaBible",
    "ShortDramaPipelineState",
    "EpisodeOutline",
]
