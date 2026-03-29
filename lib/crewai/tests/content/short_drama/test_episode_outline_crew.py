"""Tests for EpisodeOutlineCrew."""

from unittest.mock import MagicMock

import pytest

from crewai.content.short_drama.crews.episode_outline_crew import EpisodeOutlineCrew
from crewai.content.short_drama.short_drama_types import (
    EpisodeOutline,
    ShortDramaBible,
)


class _MockEpisodeOutlineCrew(EpisodeOutlineCrew):
    """Non-abstract subclass for testing (bypasses ABC)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._agents: dict = {}

    def _create_agents(self):
        return {}

    def _create_tasks(self):
        return {}

    def _create_workflow(self):
        return MagicMock()


class TestEpisodeOutlineCrew:
    """Test EpisodeOutlineCrew.generate_outline()."""

    def test_generate_outline_returns_episode_outline(
        self,
        short_drama_bible: ShortDramaBible,
    ):
        """generate_outline returns an EpisodeOutline with correct episode_num."""
        crew = _MockEpisodeOutlineCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.generate_outline.return_value = {
            "episode_num": 1,
            "title": "测试集",
            "episode_summary": "测试摘要",
            "scene_plan": [{"scene_number": 1}],
        }
        crew._agents["episode_outliner"] = mock_agent

        result = crew.generate_outline(
            chapter_text="这是测试章节内容",
            bible=short_drama_bible,
            episode_num=1,
            series_title="测试剧",
            episode_context="测试承接",
        )

        assert isinstance(result, EpisodeOutline)
        assert result.episode_num == 1
        assert result.title == "测试集"

    def test_generate_outline_batch(
        self,
        short_drama_bible: ShortDramaBible,
    ):
        """generate_outline_batch returns list of EpisodeOutlines."""
        crew = _MockEpisodeOutlineCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.generate_outline.return_value = {
            "episode_num": 1,
            "title": "集1",
            "episode_summary": "摘要",
            "scene_plan": [],
        }
        crew._agents["episode_outliner"] = mock_agent

        results = crew.generate_outline_batch(
            chapters_texts=[(1, "第1章内容"), (2, "第2章内容")],
            bible=short_drama_bible,
            series_title="测试剧",
        )

        assert len(results) == 2
        assert all(isinstance(r, EpisodeOutline) for r in results)

    def test_generate_outline_parses_json_result(
        self,
        short_drama_bible: ShortDramaBible,
    ):
        """generate_outline correctly parses JSON returned by agent."""
        crew = _MockEpisodeOutlineCrew(config={}, verbose=False)

        mock_agent = MagicMock()
        mock_agent.generate_outline.return_value = {
            "episode_num": 5,
            "title": "自定义标题",
            "episode_summary": "详细摘要",
            "scene_plan": [
                {
                    "scene_number": 1,
                    "location": "测试地点",
                    "time_of_day": "白天",
                    "description": "场景描述",
                    "key_actions": ["动作1"],
                    "characters": ["角色1"],
                    "emotion": "中性",
                    "duration_estimate": 30,
                }
            ],
        }
        crew._agents["episode_outliner"] = mock_agent

        result = crew.generate_outline(
            chapter_text="测试内容",
            bible=short_drama_bible,
            episode_num=5,
        )

        assert result.episode_num == 5
        assert result.title == "自定义标题"
        assert len(result.scene_plan) == 1
        assert result.scene_plan[0]["location"] == "测试地点"
