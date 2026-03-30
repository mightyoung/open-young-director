"""Tests for NovelConfig typed configuration."""
import pytest
from crewai.content.novel.config import NovelConfig, ScriptConfig, BlogConfig, PodcastConfig


class TestNovelConfig:
    """Tests for NovelConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = NovelConfig(topic="Test Novel")

        assert config.topic == "Test Novel"
        assert config.style == "urban"
        assert config.num_chapters == 0  # Auto-calculated
        assert config.target_words == 100000

    def test_auto_calculate_chapters(self):
        """Test that num_chapters is auto-calculated when 0."""
        config = NovelConfig(topic="Test", target_words=50000)
        # 50000 / 10000 = 5 chapters
        assert config.num_chapters == 5

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


class TestScriptConfig:
    """Tests for ScriptConfig."""

    def test_default_values(self):
        """Test default script configuration."""
        config = ScriptConfig(topic="Test Script")

        assert config.topic == "Test Script"
        assert config.script_format == "film"
        assert config.target_duration == 120
        assert config.num_acts == 3


class TestBlogConfig:
    """Tests for BlogConfig."""

    def test_default_values(self):
        """Test default blog configuration."""
        config = BlogConfig(topic="Test Blog")

        assert config.topic == "Test Blog"
        assert config.target_platforms == ["medium"]
        assert config.title_style == "seo"


class TestPodcastConfig:
    """Tests for PodcastConfig."""

    def test_default_values(self):
        """Test default podcast configuration."""
        config = PodcastConfig(topic="Test Podcast")

        assert config.topic == "Test Podcast"
        assert config.duration_minutes == 30
        assert config.hosts == 2
        assert config.include_interview is False
        assert config.include_ads is False
