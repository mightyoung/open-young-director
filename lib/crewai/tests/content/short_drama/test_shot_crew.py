"""Tests for ShotCrew."""

from unittest.mock import MagicMock, patch

import pytest

from crewai.content.short_drama.crews.shot_crew import ShotCrew
from crewai.content.short_drama.short_drama_types import (
    EpisodeOutline,
    ShortDramaBible,
    Shot,
)


class _MockShotCrew(ShotCrew):
    """Non-abstract subclass for testing (bypasses ABC)."""

    def _create_agents(self):
        return {}

    def _create_tasks(self):
        return {}

    def _create_workflow(self):
        return MagicMock()


class TestShotCrew:
    """Test ShotCrew.decompose_scene()."""

    def test_decompose_scene_returns_list_of_shots(
        self,
        sample_episode_outline: EpisodeOutline,
        short_drama_bible: ShortDramaBible,
    ):
        """decompose_scene returns a list of Shot objects."""
        crew = _MockShotCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.decompose_scene.return_value = [
            {
                "shot_number": 1,
                "scene_number": 1,
                "duration_seconds": 5.0,
                "shot_type": "medium",
                "action": "测试动作",
                "characters": ["韩林"],
                "voiceover_segment": "配音",
                "emotion": "紧张",
                "video_prompt": "medium, 测试",
            }
        ]
        crew._agents["shot_decomposer"] = mock_agent

        with patch.object(ShotCrew, "agents", crew._agents, create=True):
            scene_plan = sample_episode_outline.scene_plan[0]
            shots = crew.decompose_scene(
                scene_plan=scene_plan,
                bible=short_drama_bible,
                episode_num=1,
                scene_number=1,
            )

        assert isinstance(shots, list)
        assert len(shots) == 1
        assert isinstance(shots[0], Shot)
        assert shots[0].shot_number == 1

    def test_decompose_episode(
        self,
        sample_episode_outline: EpisodeOutline,
        short_drama_bible: ShortDramaBible,
    ):
        """decompose_episode returns ShortDramaEpisode with scenes and shots."""
        crew = _MockShotCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.decompose_scene.return_value = [
            {
                "shot_number": 1,
                "scene_number": 1,
                "duration_seconds": 5.0,
                "shot_type": "medium",
                "action": "动作",
                "characters": ["韩林"],
                "voiceover_segment": "配音",
                "emotion": "紧张",
                "video_prompt": "test prompt",
            }
        ]
        crew._agents["shot_decomposer"] = mock_agent

        with patch.object(ShotCrew, "agents", crew._agents, create=True):
            episode = crew.decompose_episode(
                episode_outline=sample_episode_outline,
                bible=short_drama_bible,
            )

        assert episode.episode_num == 1
        assert episode.title == "第1集：入门"
        assert len(episode.scenes) == 2  # Two scene plans

    def test_decompose_scene_uses_converter_when_prompt_missing(
        self,
        sample_episode_outline: EpisodeOutline,
        short_drama_bible: ShortDramaBible,
    ):
        """Shot.video_prompt is filled by ShotToPromptConverter when empty."""
        crew = _MockShotCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.decompose_scene.return_value = [
            {
                "shot_number": 1,
                "scene_number": 1,
                "duration_seconds": 5.0,
                "shot_type": "medium",
                "action": "测试动作",
                "characters": ["韩林"],
                "voiceover_segment": "配音",
                "emotion": "紧张",
                # no video_prompt
            }
        ]
        crew._agents["shot_decomposer"] = mock_agent

        with patch.object(ShotCrew, "agents", crew._agents, create=True):
            scene_plan = sample_episode_outline.scene_plan[0]
            shots = crew.decompose_scene(
                scene_plan=scene_plan,
                bible=short_drama_bible,
                episode_num=1,
                scene_number=1,
            )

        # Converter should have filled video_prompt
        assert shots[0].video_prompt != ""

    def test_decompose_episode_batch(
        self,
        short_drama_bible: ShortDramaBible,
    ):
        """decompose_episode_batch processes multiple outlines."""
        crew = _MockShotCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.decompose_scene.return_value = [
            {
                "shot_number": 1,
                "scene_number": 1,
                "duration_seconds": 5.0,
                "shot_type": "medium",
                "action": "动作",
                "characters": [],
                "voiceover_segment": "",
                "emotion": "中性",
                "video_prompt": "test",
            }
        ]
        crew._agents["shot_decomposer"] = mock_agent

        outlines = [
            EpisodeOutline(
                episode_num=1,
                title="集1",
                episode_summary="摘要1",
                scene_plan=[
                    {
                        "scene_number": 1,
                        "location": "地点",
                        "time_of_day": "白天",
                        "description": "描述",
                        "key_actions": [],
                        "characters": [],
                        "emotion": "中性",
                        "duration_estimate": 30,
                    }
                ],
            ),
            EpisodeOutline(
                episode_num=2,
                title="集2",
                episode_summary="摘要2",
                scene_plan=[
                    {
                        "scene_number": 1,
                        "location": "地点",
                        "time_of_day": "白天",
                        "description": "描述",
                        "key_actions": [],
                        "characters": [],
                        "emotion": "中性",
                        "duration_estimate": 30,
                    }
                ],
            ),
        ]

        with patch.object(ShotCrew, "agents", crew._agents, create=True):
            episodes = crew.decompose_episode_batch(outlines, short_drama_bible)

        assert len(episodes) == 2
        assert episodes[0].episode_num == 1
        assert episodes[1].episode_num == 2
