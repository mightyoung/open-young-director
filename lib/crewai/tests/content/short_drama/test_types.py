"""Tests for Shot/Episode serialization and dataclass behaviour."""

import json

import pytest

from crewai.content.short_drama.short_drama_types import (
    EpisodeOutline,
    ShortDramaBible,
    ShortDramaEpisode,
    ShortDramaScene,
    Shot,
)


class TestShotSerialization:
    """Test Shot to_dict / from_dict round-trip."""

    def test_shot_to_dict(self, sample_shot: Shot):
        """Shot.to_dict() returns correct field values."""
        d = sample_shot.to_dict()
        assert d["shot_number"] == 1
        assert d["scene_number"] == 1
        assert d["duration_seconds"] == 5.0
        assert d["shot_type"] == "establishing"
        assert d["characters"] == ["韩林"]

    def test_shot_from_dict(self):
        """Shot.from_dict() reconstructs a Shot correctly."""
        data = {
            "shot_number": 3,
            "scene_number": 2,
            "duration_seconds": 7.0,
            "shot_type": "close_up",
            "action": "特写表情",
            "characters": ["主角"],
            "video_prompt": "close up, 表情",
            "voiceover_segment": "配音",
            "emotion": "悲伤",
        }
        shot = Shot.from_dict(data)
        assert shot.shot_number == 3
        assert shot.scene_number == 2
        assert shot.duration_seconds == 7.0

    def test_shot_roundtrip_json(self, sample_shot: Shot):
        """Shot survives JSON serialization round-trip."""
        json_str = json.dumps(sample_shot.to_dict(), ensure_ascii=False)
        restored = Shot.from_dict(json.loads(json_str))
        assert restored.shot_number == sample_shot.shot_number
        assert restored.characters == sample_shot.characters


class TestShortDramaScene:
    """Test ShortDramaScene dataclass."""

    def test_add_shot(self, sample_shots: list[Shot]):
        """add_shot appends shots to scene."""
        scene = ShortDramaScene(
            scene_number=1,
            location="测试地点",
            time_of_day="白天",
            description="测试场景",
        )
        for shot in sample_shots:
            scene.add_shot(shot)

        assert len(scene.shots) == 3

    def test_get_duration(self, sample_shots: list[Shot]):
        """get_duration sums shot durations correctly."""
        scene = ShortDramaScene(
            scene_number=1,
            location="测试地点",
            time_of_day="白天",
            description="测试场景",
            shots=sample_shots,
        )
        # 5.0 + 4.0 + 6.0 = 15.0
        assert scene.get_duration() == 15.0

    def test_to_dict(self, sample_short_drama_scene: ShortDramaScene):
        """to_dict serializes scene and nested shots."""
        d = sample_short_drama_scene.to_dict()
        assert d["scene_number"] == 1
        assert d["location"] == "青云山演武场"
        assert len(d["shots"]) == 3


class TestShortDramaEpisode:
    """Test ShortDramaEpisode dataclass."""

    def test_add_scene(self, sample_short_drama_scene: ShortDramaScene):
        """add_scene appends scenes to episode."""
        episode = ShortDramaEpisode(
            episode_num=1,
            title="测试",
            summary="测试摘要",
        )
        episode.add_scene(sample_short_drama_scene)
        assert len(episode.scenes) == 1

    def test_get_duration(self, sample_short_drama_episode: ShortDramaEpisode):
        """get_duration sums all scene durations."""
        # Scene has 3 shots totalling 15s
        assert sample_short_drama_episode.get_duration() == 15.0

    def test_get_all_shots(self, sample_short_drama_episode: ShortDramaEpisode):
        """get_all_shots returns flat list of all shots."""
        shots = sample_short_drama_episode.get_all_shots()
        assert len(shots) == 3

    def test_get_characters(self, sample_short_drama_episode: ShortDramaEpisode):
        """get_characters returns union of all characters."""
        chars = sample_short_drama_episode.get_characters()
        assert "韩林" in chars

    def test_to_dict(self, sample_short_drama_episode: ShortDramaEpisode):
        """to_dict serializes episode and nested scenes/shots."""
        d = sample_short_drama_episode.to_dict()
        assert d["episode_num"] == 1
        assert d["title"] == "第1集：入门"
        assert len(d["scenes"]) == 1
        assert len(d["scenes"][0]["shots"]) == 3


class TestEpisodeOutline:
    """Test EpisodeOutline dataclass."""

    def test_to_dict(self, sample_episode_outline: EpisodeOutline):
        """to_dict returns expected fields."""
        d = sample_episode_outline.to_dict()
        assert d["episode_num"] == 1
        assert d["title"] == "第1集：入门"
        assert len(d["scene_plan"]) == 2

    def test_from_dict(self):
        """EpisodeOutline can be reconstructed from dict."""
        data = {
            "episode_num": 5,
            "title": "第5集",
            "episode_summary": "精彩剧情",
            "scene_plan": [],
        }
        outline = EpisodeOutline(**data)
        assert outline.episode_num == 5
        assert outline.title == "第5集"
