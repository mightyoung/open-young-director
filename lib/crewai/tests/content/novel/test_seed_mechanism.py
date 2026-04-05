"""Tests for seed_mechanism."""

import pytest

from crewai.content.novel.seed_mechanism import (
    SeedConfig,
    ReplayPlan,
    DirtyTracker,
    set_llm_seed,
)


class TestSeedConfig:
    """Tests for SeedConfig."""

    def test_init_default(self):
        """Test initialization with defaults."""
        config = SeedConfig()
        assert config.seed == ""
        assert config.topic == ""
        assert config.genre == ""
        assert config.style == ""
        assert config.variant is None
        assert config.version == 1

    def test_init_with_values(self):
        """Test initialization with values."""
        config = SeedConfig(
            seed="abc123",
            topic="Test Topic",
            genre="xianxia",
            style="修仙",
            variant="horror",
            version=2,
        )
        assert config.seed == "abc123"
        assert config.topic == "Test Topic"
        assert config.genre == "xianxia"
        assert config.style == "修仙"
        assert config.variant == "horror"
        assert config.version == 2

    def test_generate_seed(self):
        """Test seed generation from parameters."""
        config = SeedConfig(
            topic="Test Topic",
            genre="xianxia",
            style="修仙",
        )
        seed = config.generate_seed()

        assert len(seed) == 32
        assert seed.isalnum()  # hex string

    def test_generate_seed_deterministic(self):
        """Test that seed generation is deterministic."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Test", genre="xianxia", style="修仙")

        assert config1.generate_seed() == config2.generate_seed()

    def test_generate_seed_different_params(self):
        """Test that different params produce different seeds."""
        config1 = SeedConfig(topic="Topic1", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Topic2", genre="xianxia", style="修仙")

        assert config1.generate_seed() != config2.generate_seed()

    def test_generate_seed_with_variant(self):
        """Test seed generation with variant."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙", variant=None)
        config2 = SeedConfig(topic="Test", genre="xianxia", style="修仙", variant="horror")

        seed1 = config1.generate_seed()
        seed2 = config2.generate_seed()

        assert seed1 != seed2

    def test_matches_identical(self):
        """Test matches with identical configs."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Test", genre="xianxia", style="修仙")

        assert config1.matches(config2) is True

    def test_matches_different_topic(self):
        """Test matches fails with different topic."""
        config1 = SeedConfig(topic="Topic1", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Topic2", genre="xianxia", style="修仙")

        assert config1.matches(config2) is False

    def test_matches_different_genre(self):
        """Test matches fails with different genre."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Test", genre="urban", style="修仙")

        assert config1.matches(config2) is False

    def test_matches_different_style(self):
        """Test matches fails with different style."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙")
        config2 = SeedConfig(topic="Test", genre="xianxia", style="都市")

        assert config1.matches(config2) is False

    def test_matches_ignores_variant(self):
        """Test matches ignores variant difference."""
        config1 = SeedConfig(topic="Test", genre="xianxia", style="修仙", variant=None)
        config2 = SeedConfig(topic="Test", genre="xianxia", style="修仙", variant="horror")

        assert config1.matches(config2) is True

    def test_matches_ignores_seed(self):
        """Test matches ignores seed difference."""
        config1 = SeedConfig(seed="seed1", topic="Test", genre="xianxia", style="修仙")
        config2 = SeedConfig(seed="seed2", topic="Test", genre="xianxia", style="修仙")

        assert config1.matches(config2) is True

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = SeedConfig(
            seed="abc123",
            topic="Test",
            genre="xianxia",
            style="修仙",
            variant="horror",
            version=2,
        )
        result = config.to_dict()

        assert isinstance(result, dict)
        assert result["seed"] == "abc123"
        assert result["topic"] == "Test"
        assert result["genre"] == "xianxia"
        assert result["style"] == "修仙"
        assert result["variant"] == "horror"
        assert result["version"] == 2

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "seed": "abc123",
            "topic": "Test",
            "genre": "xianxia",
            "style": "修仙",
            "variant": "horror",
            "version": 2,
        }
        config = SeedConfig.from_dict(data)

        assert config.seed == "abc123"
        assert config.topic == "Test"
        assert config.variant == "horror"

    def test_from_legacy(self):
        """Test creation from legacy format."""
        config = SeedConfig.from_legacy(
            seed="legacy_seed",
            topic="Legacy Topic",
            genre="xianxia",
            style="修仙",
        )

        assert config.seed == "legacy_seed"
        assert config.topic == "Legacy Topic"
        assert config.genre == "xianxia"
        assert config.style == "修仙"
        assert config.variant is None


class TestReplayPlan:
    """Tests for ReplayPlan."""

    def test_init_default(self):
        """Test initialization with defaults."""
        plan = ReplayPlan()
        assert plan.regenerate_all is False
        assert plan.replay_all is False
        assert plan.regenerate_from is None
        assert plan.preserve == []
        assert plan.dirty_chapters is None

    def test_should_regenerate_world_regenerate_all(self):
        """Test should_regenerate_world when regenerate_all is True."""
        plan = ReplayPlan(regenerate_all=True)
        assert plan.should_regenerate_world() is True

    def test_should_regenerate_world_from_world(self):
        """Test should_regenerate_world when regenerate_from is world."""
        plan = ReplayPlan(regenerate_from="world")
        assert plan.should_regenerate_world() is True

    def test_should_regenerate_world_false(self):
        """Test should_regenerate_world returns False otherwise."""
        plan = ReplayPlan(regenerate_from="chapters")
        assert plan.should_regenerate_world() is False

    def test_should_regenerate_outline_regenerate_all(self):
        """Test should_regenerate_outline when regenerate_all is True."""
        plan = ReplayPlan(regenerate_all=True)
        assert plan.should_regenerate_outline() is True

    def test_should_regenerate_outline_from_world(self):
        """Test should_regenerate_outline when regenerate_from is world."""
        plan = ReplayPlan(regenerate_from="world")
        assert plan.should_regenerate_outline() is True

    def test_should_regenerate_outline_from_outline(self):
        """Test should_regenerate_outline when regenerate_from is outline."""
        plan = ReplayPlan(regenerate_from="outline")
        assert plan.should_regenerate_outline() is True

    def test_should_regenerate_outline_false(self):
        """Test should_regenerate_outline returns False from chapters."""
        plan = ReplayPlan(regenerate_from="chapters")
        assert plan.should_regenerate_outline() is False

    def test_should_regenerate_chapters_regenerate_all(self):
        """Test should_regenerate_chapters when regenerate_all is True."""
        plan = ReplayPlan(regenerate_all=True)
        assert plan.should_regenerate_chapters() is True

    def test_should_regenerate_chapters_from_world(self):
        """Test should_regenerate_chapters when regenerate_from is world."""
        plan = ReplayPlan(regenerate_from="world")
        assert plan.should_regenerate_chapters() is True

    def test_should_regenerate_chapters_with_dirty(self):
        """Test should_regenerate_chapters with dirty chapters."""
        plan = ReplayPlan(dirty_chapters=[1, 3])
        assert plan.should_regenerate_chapters() is True

    def test_should_regenerate_chapters_false(self):
        """Test should_regenerate_chapters returns False when nothing dirty and not from earlier stage."""
        plan = ReplayPlan(regenerate_from=None, dirty_chapters=[])
        assert plan.should_regenerate_chapters() is False

    def test_get_chapters_to_regenerate_regenerate_all(self):
        """Test get_chapters_to_regenerate returns None when regenerate_all."""
        plan = ReplayPlan(regenerate_all=True, dirty_chapters=[1, 2, 3])
        assert plan.get_chapters_to_regenerate() is None

    def test_get_chapters_to_regenerate_no_dirty(self):
        """Test get_chapters_to_regenerate returns None when no dirty."""
        plan = ReplayPlan(dirty_chapters=None)
        assert plan.get_chapters_to_regenerate() is None

    def test_get_chapters_to_regenerate_with_dirty(self):
        """Test get_chapters_to_regenerate returns dirty list."""
        plan = ReplayPlan(dirty_chapters=[1, 3])
        assert plan.get_chapters_to_regenerate() == [1, 3]

    def test_to_dict(self):
        """Test conversion to dictionary."""
        plan = ReplayPlan(
            regenerate_all=True,
            replay_all=False,
            regenerate_from="world",
            preserve=["outline"],
            dirty_chapters=[1, 2],
        )
        result = plan.to_dict()

        assert isinstance(result, dict)
        assert result["regenerate_all"] is True
        assert result["regenerate_from"] == "world"
        assert result["dirty_chapters"] == [1, 2]

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "regenerate_all": True,
            "replay_all": False,
            "regenerate_from": "world",
            "preserve": ["outline"],
            "dirty_chapters": [1, 2],
        }
        plan = ReplayPlan.from_dict(data)

        assert plan.regenerate_all is True
        assert plan.regenerate_from == "world"
        assert plan.dirty_chapters == [1, 2]


class TestDirtyTracker:
    """Tests for DirtyTracker."""

    def test_init(self):
        """Test initialization."""
        tracker = DirtyTracker()
        assert tracker._dirty_fields == {}
        assert tracker._original_values == {}

    def test_mark_dirty_new_field(self):
        """Test marking a new field as dirty."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")

        assert tracker.is_dirty("world_data") is True
        assert tracker._original_values["world_data"] is None

    def test_mark_dirty_existing_field(self):
        """Test marking an already dirty field."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")
        tracker.mark_dirty("world_data")

        assert tracker.is_dirty("world_data") is True

    def test_mark_clean(self):
        """Test marking a field as clean."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")
        tracker.mark_clean("world_data")

        assert tracker.is_dirty("world_data") is False

    def test_is_dirty_unknown_field(self):
        """Test is_dirty returns False for unknown fields."""
        tracker = DirtyTracker()
        assert tracker.is_dirty("unknown") is False

    def test_get_dirty_fields(self):
        """Test getting all dirty fields."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")
        tracker.mark_dirty("plot_data")
        tracker.mark_clean("world_data")

        dirty = tracker.get_dirty_fields()
        assert dirty == ["plot_data"]

    def test_get_dirty_fields_empty(self):
        """Test get_dirty_fields when none are dirty."""
        tracker = DirtyTracker()
        assert tracker.get_dirty_fields() == []

    def test_clear(self):
        """Test clearing all dirty tracking."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")
        tracker.mark_dirty("plot_data")
        tracker.clear()

        assert tracker.get_dirty_fields() == []
        assert tracker._original_values == {}

    def test_to_dict(self):
        """Test conversion to dictionary."""
        tracker = DirtyTracker()
        tracker.mark_dirty("world_data")

        result = tracker.to_dict()

        assert isinstance(result, dict)
        assert "dirty_fields" in result
        assert "original_values" in result
        assert result["dirty_fields"]["world_data"] is True

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "dirty_fields": {"world_data": True, "plot_data": False},
            "original_values": {"world_data": None},
        }
        tracker = DirtyTracker.from_dict(data)

        assert tracker.is_dirty("world_data") is True
        assert tracker.is_dirty("plot_data") is False
        assert tracker._original_values["world_data"] is None


class TestSetLLMSeed:
    """Tests for set_llm_seed function."""

    def test_none_llm(self):
        """Test with None LLM."""
        result = set_llm_seed(None, "abc123")
        assert result is False

    def test_direct_attribute(self):
        """Test setting seed via direct attribute."""
        class MockLLM:
            def __init__(self):
                self.seed = None

        llm = MockLLM()
        result = set_llm_seed(llm, "0000000000000000000000000000000a")

        assert result is True
        assert llm.seed == 10  # 0xa = 10

    def test_set_seed_method(self):
        """Test setting seed via set_seed method."""
        class MockLLM:
            def __init__(self):
                self._seed = None

            def set_seed(self, seed):
                self._seed = seed

        llm = MockLLM()
        result = set_llm_seed(llm, "0000000000000000000000000000000a")

        assert result is True
        assert llm._seed == 10

    def test_config_dict(self):
        """Test setting seed via config dict."""
        class MockLLM:
            def __init__(self):
                self.config = {}

        llm = MockLLM()
        result = set_llm_seed(llm, "0000000000000000000000000000000a")

        assert result is True
        assert llm.config["seed"] == 10

    def test_kwargs(self):
        """Test setting seed via kwargs."""
        class MockLLM:
            def __init__(self):
                self.kwargs = {}

        llm = MockLLM()
        result = set_llm_seed(llm, "0000000000000000000000000000000a")

        assert result is True
        assert llm.kwargs["seed"] == 10

    def test_invalid_seed_format(self):
        """Test with invalid seed format."""
        class MockLLM:
            seed = None

        llm = MockLLM()
        result = set_llm_seed(llm, "invalid")

        assert result is False

    def test_seed_modulo_2_pow_32(self):
        """Test that seed is taken modulo 2^32."""
        class MockLLM:
            def __init__(self):
                self.seed = None

        llm = MockLLM()
        # 0x100000000 = 2^32, so seed % 2^32 = 0
        result = set_llm_seed(llm, "00000000000000000000000100000000")

        assert result is True
        assert llm.seed == 0  # 2^32 mod 2^32 = 0

    def test_no_seed_support(self):
        """Test when LLM has no seed support."""
        class MockLLM:
            pass

        llm = MockLLM()
        result = set_llm_seed(llm, "abc123")

        assert result is False
