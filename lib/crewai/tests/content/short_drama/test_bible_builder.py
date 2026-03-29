"""Tests for ShortDramaBibleBuilder."""

import pytest

from crewai.content.novel.production_bible.bible_types import ProductionBible
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.short_drama_types import ShortDramaBible


class TestShortDramaBibleBuilder:
    """Test ShortDramaBibleBuilder.build() and helper methods."""

    def test_build_returns_short_drama_bible(self, mock_bible: ProductionBible):
        """Builder returns a ShortDramaBible with correct episode_num."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
            episode_context="承接剧情",
        )

        assert isinstance(result, ShortDramaBible)
        assert result.episode_num == 1
        assert result.series_title == "仙侠史诗"
        assert result.episode_context == "承接剧情"

    def test_build_extracts_relevant_characters(
        self, mock_bible: ProductionBible
    ):
        """Builder extracts only characters_in_episode when provided."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
            characters_in_episode=["韩林"],
        )

        assert "韩林" in result.relevant_characters
        assert "长老" not in result.relevant_characters

    def test_build_includes_protagonist_when_no_filter(
        self, mock_bible: ProductionBible
    ):
        """Protagonist is always included even without explicit filter."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=99,  # far outside chapter range
            series_title="仙侠史诗",
        )

        # Protagonist should still be included
        assert "韩林" in result.relevant_characters

    def test_world_rules_summary_formatted(self, mock_bible: ProductionBible):
        """World rules are summarised into a readable string."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
        )

        assert "修仙灵力体系" in result.world_rules_summary
        assert "炼气" in result.world_rules_summary

    def test_visual_style_from_bible(self, mock_bible: ProductionBible):
        """Visual style is determined from bible or style argument."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
        )

        # Should default to "古风仙侠" for xianxia style
        assert result.visual_style in ("古风仙侠", "古风", "写实风格")

    def test_tone_from_bible(self, mock_bible: ProductionBible):
        """Tone is determined from bible or style argument."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
        )

        assert result.tone in ("古风", "写实")


class TestShortDramaBibleBuilderVisualStyleMap:
    """Test style → visual-style mapping."""

    @pytest.mark.parametrize(
        "style,expected_contains",
        [
            ("xianxia", "古风"),
            ("doushi", "现代"),
            ("modern", "现代"),
        ],
    )
    def test_style_mapping(self, mock_bible: ProductionBible, style, expected_contains):
        """Various style strings map to expected tone/visual keywords."""
        builder = ShortDramaBibleBuilder(style=style)
        result = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="测试",
        )

        assert expected_contains in result.tone or expected_contains in result.visual_style
