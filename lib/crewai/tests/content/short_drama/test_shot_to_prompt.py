"""Tests for ShotToPromptConverter."""

import pytest

from crewai.content.short_drama.short_drama_types import Shot
from crewai.content.short_drama.video.shot_to_prompt import ShotToPromptConverter


class TestShotToPromptConverter:
    """Test ShotToPromptConverter."""

    def test_init_default_style(self):
        """Converter initialises with a Seedance2PromptAdapter."""
        converter = ShotToPromptConverter()
        assert converter.adapter is not None

    def test_init_custom_style(self):
        """Converter accepts custom default style argument."""
        converter = ShotToPromptConverter(default_style="电影风格")
        assert converter.adapter is not None

    def test_convert_shot_returns_string(
        self, sample_shot: Shot, short_drama_bible
    ):
        """convert_shot returns a non-empty string prompt."""
        converter = ShotToPromptConverter()
        result = converter.convert_shot(
            shot=sample_shot,
            bible=short_drama_bible,
            location="青云山演武场",
            time_of_day="清晨",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_convert_shot_to_dict_returns_dict(
        self, sample_shot: Shot, short_drama_bible
    ):
        """convert_shot_to_dict returns a dict with expected keys."""
        converter = ShotToPromptConverter()
        result = converter.convert_shot_to_dict(
            shot=sample_shot,
            bible=short_drama_bible,
            location="青云山演武场",
            time_of_day="清晨",
        )

        assert isinstance(result, dict)
        assert len(result) > 0

    def test_convert_shots_batch(
        self, sample_shots: list[Shot], short_drama_bible
    ):
        """convert_shots_batch returns list of dicts."""
        converter = ShotToPromptConverter()
        results = converter.convert_shots_batch(
            shots=sample_shots,
            bible=short_drama_bible,
            scene_locations={1: "青云山演武场"},
            scene_times={1: "清晨"},
        )

        assert isinstance(results, list)
        assert len(results) == 3
        assert all(isinstance(r, dict) for r in results)

    def test_build_character_specs_includes_profile(
        self, sample_shot: Shot, short_drama_bible
    ):
        """Character specs are built from bible profile when available."""
        converter = ShotToPromptConverter()
        specs = converter._build_character_specs(sample_shot, short_drama_bible)

        assert isinstance(specs, list)
        assert len(specs) > 0

    def test_build_scene_spec_returns_value(self, short_drama_bible):
        """_build_scene_spec returns a SceneSpec or None without crashing."""
        converter = ShotToPromptConverter()
        # Empty location returns None
        spec = converter._build_scene_spec(
            location="",
            time_of_day="清晨",
            bible=short_drama_bible,
        )
        assert spec is None
