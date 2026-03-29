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
        previous_episode_end_frame: dict = None,
    ) -> List[Shot]:
        """将场景分解为镜头列表（增强版）

        Args:
            scene_plan: 场景规划（来自 EpisodeOutline）
            bible: ShortDramaBible
            episode_num: 集号
            scene_number: 场景序号
            previous_episode_end_frame: 上一集尾帧（用于多集串联）

        Returns:
            list[Shot]: 镜头列表
        """
        agent = self.agents.get("shot_decomposer")
        if not agent:
            raise ValueError("ShotAgent not found in agents")

        # 调用 agent 分解镜头（传入尾帧用于串联）
        shot_dicts = agent.decompose_scene(
            scene_plan=scene_plan,
            bible=bible,
            episode_num=episode_num,
            scene_number=scene_number,
            previous_episode_end_frame=previous_episode_end_frame,
        )

        # 初始化 Prompt 转换器（使用增强版）
        converter = ShotToPromptConverter(use_enhanced_timeline=True)

        # 转换为 Shot 对象并填充 video_prompt
        shots = []
        for shot_dict in shot_dicts:
            # 获取camera_movement（增强版新增字段）
            camera_movement = shot_dict.get("camera_movement", "")

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

            # 生成素材引用（用于角色一致性）
            asset_refs = []
            for i, char_name in enumerate(shot.characters[:3]):  # 最多3个角色
                char_ref = converter.generate_asset_reference_for_character(char_name, i + 1)
                asset_refs.append(char_ref)

            # 使用 ShotToPromptConverter 填充 video_prompt（增强版）
            if not shot.video_prompt:
                shot.video_prompt = converter.convert_shot(
                    shot=shot,
                    bible=bible,
                    location=scene_plan.get("location", ""),
                    time_of_day=scene_plan.get("time_of_day", "白天"),
                    asset_references=asset_refs,
                )

            shots.append(shot)

        return shots

    def decompose_episode(
        self,
        episode_outline: EpisodeOutline,
        bible: ShortDramaBible,
        previous_episode: ShortDramaEpisode | None = None,
    ) -> ShortDramaEpisode:
        """将整个集大纲分解为镜头（增强版：支持多集串联）

        Args:
            episode_outline: 集大纲
            bible: ShortDramaBible
            previous_episode: 上一集（用于多集剧情衔接）

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

        # 获取上一集尾帧（用于多集串联）
        previous_end_frame = None
        if previous_episode:
            previous_end_frame = self._extract_episode_end_frame(previous_episode)

        shot_counter = 1
        for scene_plan in episode_outline.scene_plan:
            scene_number = scene_plan.get("scene_number", len(episode.scenes) + 1)

            # 分解场景为镜头（传入上一集尾帧用于串联）
            shots = self.decompose_scene(
                scene_plan=scene_plan,
                bible=bible,
                episode_num=episode_outline.episode_num,
                scene_number=scene_number,
                previous_episode_end_frame=previous_end_frame if shot_counter == 1 else None,
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

    def _extract_episode_end_frame(self, previous_episode: ShortDramaEpisode) -> dict:
        """从上一集提取尾帧信息用于串联

        Args:
            previous_episode: 上一集 ShortDramaEpisode

        Returns:
            dict: 包含尾帧信息的字典
        """
        # 获取上一集最后一个场景的最后一个镜头
        all_shots = previous_episode.get_all_shots()
        if not all_shots:
            return None

        last_shot = all_shots[-1]

        # 构建尾帧信息
        end_frame = {
            "character_state": f"{', '.join(last_shot.characters)} {last_shot.action}" if last_shot.characters else last_shot.action,
            "background": previous_episode.scenes[-1].location if previous_episode.scenes else "未知",
            "lighting": "自然光",
            "composition": "中景构图",
            "mood": last_shot.emotion or "平静",
            "camera_state": "固定镜头",
            "motion_state": "静止",
        }

        return end_frame

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
