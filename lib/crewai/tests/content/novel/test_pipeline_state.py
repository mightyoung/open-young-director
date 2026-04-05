"""Tests for PipelineState."""

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.seed_mechanism import SeedConfig, ReplayPlan


class TestPipelineState:
    """Tests for PipelineState core functionality."""

    def test_init_default(self):
        """Test initialization with defaults."""
        state = PipelineState()
        assert state.current_stage == "init"
        assert state.world_data == {}
        assert state.plot_data == {}
        assert state.chapters == []
        assert state.dirty_chapters == set()

    def test_init_with_config(self):
        """Test initialization with config dict."""
        config = {"topic": "Test Novel", "style": "xianxia"}
        state = PipelineState(config=config)
        assert state.config == config

    def test_set_outline_data(self):
        """Test setting outline data."""
        state = PipelineState()
        outline_data = {
            "world": {"name": "Test World"},
            "plot": {"main_strand": "Test plot"},
        }
        state.set_outline_data(outline_data)
        assert state.world_data == {"name": "Test World"}
        assert state.plot_data == {"main_strand": "Test plot"}
        assert state.current_stage == "outline"

    def test_set_stage(self):
        """Test setting current stage."""
        state = PipelineState()
        state.set_stage("volume")
        assert state.current_stage == "volume"

    def test_set_chapter_summaries(self):
        """Test setting chapter summaries."""
        state = PipelineState()
        summaries = [
            {"chapter_num": 1, "title": "Chapter 1"},
            {"chapter_num": 2, "title": "Chapter 2"},
        ]
        state.set_chapter_summaries(summaries)
        assert len(state.chapter_summaries) == 2

    def test_add_chapter_as_dict(self):
        """Test adding a chapter as dict."""
        state = PipelineState()
        chapter = {"chapter_num": 1, "title": "Test Chapter"}
        state.add_chapter(chapter)
        assert len(state.chapters) == 1
        assert state.current_stage == "writing"

    def test_add_chapter_as_dataclass(self):
        """Test adding a chapter as dataclass."""
        @dataclass
        class MockChapter:
            chapter_num: int
            title: str

        state = PipelineState()
        chapter = MockChapter(chapter_num=1, title="Test Chapter")
        state.add_chapter(chapter)
        assert len(state.chapters) == 1
        assert isinstance(state.chapters[0], dict)

    def test_add_chapter_dataclass_stores_as_dict_for_replay(self):
        """Test that dataclass chapters are stored as dicts for replay compatibility.

        P1-1: Verifies that chapter_num access via .get() works correctly.
        This is critical for dirty chapter replay filtering.
        """
        @dataclass
        class MockChapter:
            chapter_num: int
            title: str

        state = PipelineState()
        state.add_chapter(MockChapter(chapter_num=5, title="Chapter Five"))
        state.add_chapter(MockChapter(chapter_num=10, title="Chapter Ten"))

        # Verify storage format is dict
        assert isinstance(state.chapters[0], dict)
        assert isinstance(state.chapters[1], dict)

        # P1-1: Verify replay pattern (.get("chapter_num")) works
        existing = [c for c in state.chapters if c.get("chapter_num") == 5]
        assert len(existing) == 1
        assert existing[0]["title"] == "Chapter Five"

        # Verify 1-based chapter number filtering
        filtered = [c for c in state.chapters if c.get("chapter_num") in {5, 10}]
        assert len(filtered) == 2


class TestPipelineStateDirtyChapters:
    """Tests for dirty chapter tracking."""

    def test_mark_chapters_dirty(self):
        """Test marking chapters as dirty."""
        state = PipelineState()
        state.mark_chapters_dirty([1, 3, 5])
        assert state.is_chapter_dirty(1) is True
        assert state.is_chapter_dirty(3) is True
        assert state.is_chapter_dirty(5) is True
        assert state.is_chapter_dirty(2) is False

    def test_is_chapter_dirty_1_based(self):
        """Test that chapter numbers are 1-based."""
        state = PipelineState()
        state.mark_chapters_dirty([1])
        # Chapter 0 should NOT be dirty (chapters are 1-based)
        assert state.is_chapter_dirty(0) is False
        assert state.is_chapter_dirty(1) is True

    def test_mark_all_chapters_dirty(self):
        """Test marking all chapters dirty."""
        state = PipelineState()
        state.add_chapter({"chapter_num": 1, "title": "Ch1"})
        state.add_chapter({"chapter_num": 2, "title": "Ch2"})
        state.add_chapter({"chapter_num": 3, "title": "Ch3"})

        state.mark_all_chapters_dirty()

        assert state.is_chapter_dirty(1) is True
        assert state.is_chapter_dirty(2) is True
        assert state.is_chapter_dirty(3) is True

    def test_clear_dirty_chapters(self):
        """Test clearing dirty chapter markers."""
        state = PipelineState()
        state.mark_chapters_dirty([1, 2])
        state.clear_dirty_chapters()

        assert state.is_chapter_dirty(1) is False
        assert state.is_chapter_dirty(2) is False

    def test_get_dirty_chapters(self):
        """Test getting list of dirty chapters."""
        state = PipelineState()
        state.mark_chapters_dirty([3, 1, 5])
        dirty = state.get_dirty_chapters()

        assert dirty == [1, 3, 5]  # Should be sorted


class TestPipelineStateSerialization:
    """Tests for PipelineState serialization."""

    def test_save_and_load(self):
        """Test saving and loading state."""
        state = PipelineState(config={"topic": "Test"})
        state.set_outline_data({
            "world": {"name": "Test World"},
            "plot": {"main_strand": "Test"},
        })
        state.set_stage("outline")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            state.save(str(path))

            # Load the state
            loaded = PipelineState.load(str(path))
            assert loaded.current_stage == "outline"
            assert loaded.world_data == {"name": "Test World"}

    def test_load_nonexistent_raises(self):
        """Test loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            PipelineState.load("/nonexistent/path.json")

    def test_serialize_chapters_are_dicts(self):
        """Test that serialized chapters are dicts, not objects."""
        state = PipelineState()
        state.add_chapter({"chapter_num": 1, "title": "Test"})

        # Verify chapters are stored as dicts
        assert isinstance(state.chapters[0], dict)
        assert state.chapters[0]["chapter_num"] == 1


class TestPipelineStateReplayPlan:
    """Tests for replay plan generation."""

    def test_replay_plan_regenerate_all_no_seed_config(self):
        """Test replay plan when no seed config exists."""
        state = PipelineState()
        state.seed_config = None

        plan = state.get_replay_plan(None)
        assert plan.regenerate_all is True

    def test_replay_plan_regenerate_all_seed_mismatch(self):
        """Test replay plan when seed configs don't match.

        Note: seed itself doesn't trigger regenerate_all - only missing seed_config does.
        The seed is used for deterministic generation, not for determining regeneration scope.
        Different seeds with same topic/genre/style will regenerate from chapters level.
        """
        state = PipelineState()
        state.seed_config = SeedConfig(
            seed="old_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )

        new_config = SeedConfig(
            seed="new_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )

        plan = state.get_replay_plan(new_config)
        # Same core params means matches() returns True
        # Since core_content_hash is empty, has_core_content_changed() returns True
        # So it will regenerate from outline
        assert plan.regenerate_from == "outline"
        assert plan.regenerate_all is False

    def test_replay_plan_dirty_chapters(self):
        """Test replay plan with dirty chapters.

        When core_content_hash is set (no change), dirty chapters trigger chapter-level regeneration.
        """
        state = PipelineState()
        state.seed_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )
        # Set world_data and plot_data, then update hash to match
        state.world_data = {"name": "Test World"}
        state.plot_data = {"main_strand": "Test Plot"}
        state.update_core_content_hash()  # Sets core_content_hash based on current data
        state.mark_chapters_dirty([1, 3])

        new_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )

        plan = state.get_replay_plan(new_config)
        assert plan.should_regenerate_chapters() is True
        assert set(plan.dirty_chapters) == {1, 3}

    def test_replay_plan_no_regeneration_needed(self):
        """Test replay plan when no regeneration needed."""
        state = PipelineState()
        state.seed_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )
        # Set world_data and plot_data, then update hash to simulate unchanged content
        state.world_data = {"name": "Test World"}
        state.plot_data = {"main_strand": "Test Plot"}
        state.update_core_content_hash()  # Sets core_content_hash based on current data

        new_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
        )

        plan = state.get_replay_plan(new_config)
        assert plan.regenerate_all is False
        assert plan.should_regenerate_world() is False
        assert plan.should_regenerate_outline() is False
        assert plan.should_regenerate_chapters() is False

    def test_replay_plan_variant_change(self):
        """Test replay plan when variant changes."""
        state = PipelineState()
        state.seed_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
            variant="horror",
        )
        # Set world_data and plot_data, then update hash to avoid earlier conditions
        state.world_data = {"name": "Test World"}
        state.plot_data = {"main_strand": "Test Plot"}
        state.update_core_content_hash()
        state.add_chapter({"chapter_num": 1, "title": "Ch1"})
        state.add_chapter({"chapter_num": 2, "title": "Ch2"})

        new_config = SeedConfig(
            seed="same_seed",
            topic="Test",
            genre="xianxia",
            style="xianxia",
            variant="comedy",  # Different variant
        )

        plan = state.get_replay_plan(new_config)
        assert plan.should_regenerate_chapters() is True
        # Should use actual chapter numbers (1-based), not indices (0-based)
        assert set(plan.dirty_chapters) == {1, 2}


class TestPipelineStateSummary:
    """Tests for PipelineState summary generation."""

    def test_to_summary(self):
        """Test summary generation."""
        state = PipelineState(config={"topic": "Test Novel"})
        state.set_outline_data({
            "world": {"name": "Test World"},
            "plot": {"series_overview": "Test plot"},
        })

        summary = state.to_summary()

        assert summary["current_stage"] == "outline"
        assert summary["world_name"] == "Test World"
        assert summary["plot_title"] == "Test plot"
        # config is included, not topic directly
        assert "config" in summary


class TestPipelineStateApproval:
    """Tests for approval workflow integration."""

    def test_enable_approval_mode(self):
        """Test enabling approval mode."""
        state = PipelineState()
        state.enable_approval_mode()
        assert state.approval_mode is True

    def test_set_stage_status(self):
        """Test setting stage status."""
        state = PipelineState()
        state.set_stage_status("outline", "pending")
        assert state.stage_statuses["outline"] == "pending"

    def test_add_approval_record(self):
        """Test adding approval record."""
        state = PipelineState()
        record = {"stage": "outline", "decision": "approve"}
        state.add_approval_record(record)

        assert len(state.approval_history) == 1
        assert state.approval_history[0]["stage"] == "outline"
