"""Tests for NovelConfig typed configuration."""
import pytest
from crewai.content.novel.config import NovelConfig


class TestNovelConfig:
    """Tests for NovelConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NovelConfig(topic="Test Novel")

        assert config.topic == "Test Novel"
        assert config.style == "urban"
        # num_chapters is auto-calculated based on target_words and style
        assert config.num_chapters > 0  # Auto-calculated
        assert config.target_words == 100000
        # For urban style with 100000 words and 4000 words/chapter target:
        # 100000 / 4000 = 25 -> round(25/5)*5 = 25
        assert config.num_chapters == 25

    def test_auto_calculate_chapters(self):
        """Test that num_chapters is auto-calculated when 0."""
        config = NovelConfig(topic="Test", target_words=50000)
        # For urban style: 50000 / 4000 = 12.5 -> round(12.5/5)*5 = 10
        assert config.num_chapters == 10

    def test_genre_defaults_to_style(self):
        """Test that genre defaults to style when empty."""
        config = NovelConfig(topic="Test", style="xianxia")
        assert config.genre == "xianxia"

    def test_to_dict(self):
        """Test conversion to dict."""
        config = NovelConfig(
            topic="Test",
            style="urban",
            target_words=100000,
            num_chapters=10,
        )
        d = config.to_dict()

        assert d["topic"] == "Test"
        assert d["style"] == "urban"
        assert d["target_words"] == 100000
        assert d["num_chapters"] == 10

    def test_from_dict(self):
        """Test creation from dict."""
        d = {
            "topic": "Test",
            "style": "xianxia",
            "target_words": 200000,
            "num_chapters": 20,
        }
        config = NovelConfig.from_dict(d)

        assert config.topic == "Test"
        assert config.style == "xianxia"
        assert config.target_words == 200000
        assert config.num_chapters == 20

    def test_roundtrip(self):
        """Test that to_dict -> from_dict preserves data."""
        original = NovelConfig(
            topic="Test Novel",
            style="modern",
            target_words=150000,
            num_chapters=15,
            review_each_chapter=True,
        )

        d = original.to_dict()
        restored = NovelConfig.from_dict(d)

        assert restored.topic == original.topic
        assert restored.style == original.style
        assert restored.target_words == original.target_words
        assert restored.num_chapters == original.num_chapters
        assert restored.review_each_chapter == original.review_each_chapter
