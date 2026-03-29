"""ShotCrew - 镜头分解 Crew

使用 Agent 团队协作将集大纲分解为镜头列表：
- 主 Agent（ShotAgent）负责镜头分解
- 生成 Seedance2 五维 Prompt
"""

from __future__ import annotations

__all__ = ["ShotCrew"]

from typing import Dict, Any, TYPE_CHECKING, List

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.short_drama.agents.shot_agent import ShotAgent
from crewai.content.short_drama.short_drama_types import (
    ShortDramaBible,
    ShortDramaScene,
    ShortDramaEpisode,
    Shot,
    EpisodeOutline,
)
from crewai.content.short_drama.video.shot_to_prompt import ShotToPromptConverter

if TYPE_CHECKING:
    from crewai.llm import LLM


class ShotCrew(BaseContentCrew):
    """ShotCrew - 镜头分解 Crew

    负责将集大纲中的每个场景分解为具体的镜头列表。

    使用示例:
        crew = ShotCrew(config=ContentConfig(...))
        shots = crew.decompose_scene(
            scene_plan=scene_plan,
            bible=short_drama_bible,
            episode_num=1,
            scene_number=1,
        )
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建 Agents"""
        return {
            "shot_decomposer": ShotAgent(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            ),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建 Tasks（由子类直接调用，不走通用 kickoff）"""
        return {}

    def decompose_scene(
        self,
        scene_plan: dict,
        bible: ShortDramaBible,
        episode_num: int,
        scene_number: int,
    ) -> List[Shot]:
        """将场景分解为镜头列表

        Args:
            scene_plan: 场景规划（来自 EpisodeOutline）
            bible: ShortDramaBible
            episode_num: 集号
            scene_number: 场景序号

        Returns:
            list[Shot]: 镜头列表
        """
        agent = self.agents.get("shot_decomposer")
        if not agent:
            raise ValueError("ShotAgent not found in agents")

        # 调用 agent 分解镜头
        shot_dicts = agent.decompose_scene(
            scene_plan=scene_plan,
            bible=bible,
            episode_num=episode_num,
            scene_number=scene_number,
        )

        # 初始化 Prompt 转换器
        converter = ShotToPromptConverter()

        # 转换为 Shot 对象并填充 video_prompt
        shots = []
        for shot_dict in shot_dicts:
            shot = Shot(
                shot_number=shot_dict.get("shot_number", len(shots) + 1),
                scene_number=shot_dict.get("scene_number", scene_number),
                duration_seconds=shot_dict.get("duration_seconds", 5.0),
                shot_type=shot_dict.get("shot_type", "medium"),
                action=shot_dict.get("action", ""),
                characters=shot_dict.get("characters", []),
                video_prompt=shot_dict.get("video_prompt", ""),
                voiceover_segment=shot_dict.get("voiceover_segment", ""),
                emotion=shot_dict.get("emotion", "中性"),
            )

            # 使用 ShotToPromptConverter 填充 video_prompt（若为空）
            if not shot.video_prompt:
                shot.video_prompt = converter.convert_shot(
                    shot=shot,
                    bible=bible,
                    location=scene_plan.get("location", ""),
                    time_of_day=scene_plan.get("time_of_day", "白天"),
                )

            shots.append(shot)

        return shots

    def decompose_episode(
        self,
        episode_outline: EpisodeOutline,
        bible: ShortDramaBible,
        previous_episode: ShortDramaEpisode | None = None,
    ) -> ShortDramaEpisode:
        """将整个集大纲分解为镜头

        Args:
            episode_outline: 集大纲
            bible: ShortDramaBible
            previous_episode: 上一集（用于获取剧情承接）

        Returns:
            ShortDramaEpisode: 包含完整镜头的剧集
        """
        # episode_context = 上一集的结尾剧情衔接
        episode_context = bible.episode_context
        if previous_episode:
            episode_context = getattr(previous_episode, "summary", "") or episode_context

        episode = ShortDramaEpisode(
            episode_num=episode_outline.episode_num,
            title=episode_outline.title,
            summary=episode_outline.episode_summary,
            episode_context=episode_context,
        )

        shot_counter = 1
        for scene_plan in episode_outline.scene_plan:
            scene_number = scene_plan.get("scene_number", len(episode.scenes) + 1)

            # 分解场景为镜头
            shots = self.decompose_scene(
                scene_plan=scene_plan,
                bible=bible,
                episode_num=episode_outline.episode_num,
                scene_number=scene_number,
            )

            # 更新镜头序号
            for shot in shots:
                shot.shot_number = shot_counter
                shot_counter += 1

            # 创建 ShortDramaScene
            scene = ShortDramaScene(
                scene_number=scene_number,
                location=scene_plan.get("location", "未知"),
                time_of_day=scene_plan.get("time_of_day", "白天"),
                description=scene_plan.get("description", ""),
                shots=shots,
            )

            episode.add_scene(scene)

        return episode

    def decompose_episode_batch(
        self,
        episode_outlines: List[EpisodeOutline],
        bible: ShortDramaBible,
    ) -> List[ShortDramaEpisode]:
        """批量分解剧集

        Args:
            episode_outlines: 集大纲列表
            bible: ShortDramaBible

        Returns:
            list[ShortDramaEpisode]: 剧集列表
        """
        episodes = []
        for i, outline in enumerate(episode_outlines):
            try:
                previous_episode = episodes[-1] if episodes else None
                episode = self.decompose_episode(outline, bible, previous_episode)
                episodes.append(episode)
            except Exception as e:
                import logging
                logging.warning(f"Failed to decompose episode {outline.episode_num}: {e}")

        return episodes
