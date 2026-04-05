"""Tests for NovelConfig."""

import pytest

from crewai.content.novel.config.novel_config import NovelConfig


class TestNovelConfigDefaults:
    """Tests for NovelConfig defaults and post_init behavior."""

    def test_init_default(self):
        """Test initialization with defaults."""
        config = NovelConfig(topic="Test Novel")
        assert config.topic == "Test Novel"
        assert config.style == "urban"
        assert config.genre == "urban"  # Defaults to style

    def test_init_xianxia_style(self):
        """Test initialization with xianxia style."""
        config = NovelConfig(topic="Test", style="xianxia")
        # xianxia style applies specific chapter word count config
        assert config.words_per_chapter_target == 6000
        assert config.words_per_chapter_min == 4000
        assert config.words_per_chapter_max == 10000

    def test_init_urban_style(self):
        """Test initialization with urban style."""
        config = NovelConfig(topic="Test", style="urban")
        assert config.words_per_chapter_target == 4000
        assert config.words_per_chapter_min == 2500
        assert config.words_per_chapter_max == 6000

    def test_explicit_chapter_words_override_style_config(self):
        """Test that explicit chapter word counts override style defaults."""
        config = NovelConfig(
            topic="Test",
            style="xianxia",
            words_per_chapter_target=8000,  # Override
        )
        assert config.words_per_chapter_target == 8000
        # Min and max should still use style config since they use default values
        assert config.words_per_chapter_min == 4000  # from xianxia style


class TestNovelConfigChapters:
    """Tests for chapter auto-calculation."""

    def test_auto_calculate_chapters(self):
        """Test automatic chapter calculation from target_words."""
        config = NovelConfig(topic="Test", target_words=120000)
        # 120000 / 4000 (urban default) = 30 chapters
        assert config.num_chapters == 30

    def test_auto_calculate_chapters_rounds_to_5(self):
        """Test chapter count rounds to nearest 5."""
        config = NovelConfig(topic="Test", target_words=115000)  # ~28.75 chapters
        # Should round to 30
        assert config.num_chapters == 30

    def test_explicit_chapters_not_overridden(self):
        """Test that explicit num_chapters is not overridden."""
        config = NovelConfig(topic="Test", num_chapters=50, target_words=1000000)
        assert config.num_chapters == 50

    def test_zero_target_words_uses_default(self):
        """Test that zero target_words uses fallback."""
        config = NovelConfig(topic="Test", target_words=0)
        assert config.num_chapters == 10  # Fallback


class TestNovelConfigVolumes:
    """Tests for volume auto-calculation."""

    def test_auto_calculate_volumes_small_novel(self):
        """Test volume calculation for small novels (30 chapters or less)."""
        config = NovelConfig(topic="Test", num_chapters=20)
        # 20 // 10 + 1 = 3, clamped to 3
        assert config.num_volumes == 3

    def test_auto_calculate_volumes_medium_novel(self):
        """Test volume calculation for medium novels (30-60 chapters)."""
        config = NovelConfig(topic="Test", num_chapters=50)
        assert config.num_volumes == 4

    def test_auto_calculate_volumes_large_novel(self):
        """Test volume calculation for large novels (60-120 chapters)."""
        config = NovelConfig(topic="Test", num_chapters=100)
        assert config.num_volumes == 6

    def test_auto_calculate_volumes_very_large_novel(self):
        """Test volume calculation for very large novels (120-200 chapters)."""
        config = NovelConfig(topic="Test", num_chapters=180)
        assert config.num_volumes == 8

    def test_auto_calculate_volumes_massive_novel(self):
        """Test volume calculation for massive novels (200+ chapters)."""
        config = NovelConfig(topic="Test", num_chapters=300)
        assert config.num_volumes == 10

    def test_explicit_volumes_not_overridden(self):
        """Test that explicit num_volumes is not overridden."""
        config = NovelConfig(topic="Test", num_chapters=50, num_volumes=10)
        assert config.num_volumes == 10

    def test_chapters_per_volume_auto_calc(self):
        """Test chapters_per_volume auto-calculation."""
        config = NovelConfig(topic="Test", num_chapters=30, num_volumes=3)
        assert config.chapters_per_volume == 10  # 30 / 3


class TestNovelConfigVolumeDistribution:
    """Tests for volume distribution calculation."""

    def test_equal_distribution(self):
        """Test equal distribution when chapters divide evenly."""
        config = NovelConfig(topic="Test", num_chapters=30, num_volumes=3)
        dist = config.get_volume_distribution()
        assert dist == [10, 10, 10]

    def test_unequal_distribution_remainder(self):
        """Test distribution with remainder goes to first volumes."""
        config = NovelConfig(topic="Test", num_chapters=31, num_volumes=3)
        dist = config.get_volume_distribution()
        # 31 // 3 = 10, remainder = 1
        # First volume gets +1
        assert dist == [11, 10, 10]

    def test_unequal_distribution_large_remainder(self):
        """Test distribution with larger remainder."""
        config = NovelConfig(topic="Test", num_chapters=35, num_volumes=3)
        dist = config.get_volume_distribution()
        # 35 // 3 = 11, remainder = 2
        # First 2 volumes get +1 each
        assert dist == [12, 12, 11]


class TestNovelConfigSerialization:
    """Tests for config serialization."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = NovelConfig(topic="Test", style="xianxia")
        result = config.to_dict()

        assert isinstance(result, dict)
        assert result["topic"] == "Test"
        assert result["style"] == "xianxia"
        assert result["genre"] == "xianxia"
        assert "num_chapters" in result
        assert "num_volumes" in result

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "topic": "Test Novel",
            "style": "xianxia",
            "target_words": 200000,
            "num_chapters": 0,  # Will auto-calculate
            "num_volumes": 0,  # Will auto-calculate
        }
        config = NovelConfig.from_dict(data)

        assert config.topic == "Test Novel"
        assert config.style == "xianxia"
        assert config.target_words == 200000

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        config = NovelConfig(topic="Test", style="doushi", target_words=150000)
        # Store calculated values
        original_chapters = config.num_chapters
        original_volumes = config.num_volumes

        # Serialize and deserialize
        data = config.to_dict()
        restored = NovelConfig.from_dict(data)

        assert restored.topic == config.topic
        assert restored.style == config.style
        assert restored.target_words == config.target_words


class TestNovelConfigEdgeCases:
    """Tests for edge cases."""

    def test_negative_target_words(self):
        """Test negative target_words uses fallback."""
        config = NovelConfig(topic="Test", target_words=-100)
        assert config.num_chapters == 10  # Fallback

    def test_very_small_target_words(self):
        """Test very small target_words."""
        config = NovelConfig(topic="Test", target_words=1000)
        # 1000 / 4000 = 0.25, rounds to 0, then max(1, 0) = 1
        assert config.num_chapters == 1

    def test_chapters_less_than_volumes(self):
        """Test when chapters < volumes."""
        config = NovelConfig(topic="Test", num_chapters=2, num_volumes=5)
        # With 2 chapters and 5 volumes, some volumes get 0
        dist = config.get_volume_distribution()
        # But num_chapters / num_volumes = 0
        assert config.chapters_per_volume == 0  # Floor division


