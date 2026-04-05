"""Tests for CheckpointManager."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crewai.content.novel.orchestrator.checkpoint_manager import CheckpointManager


class TestCheckpointManager:
    """Tests for CheckpointManager."""

    def test_init_with_config(self):
        """Test initialization with config dict."""
        config = {"topic": "Test Novel", "style": "xianxia"}
        manager = CheckpointManager(config)
        assert manager.config == config
        assert manager.output_dir.startswith("novels/")

    def test_init_with_output_dir(self):
        """Test initialization with explicit output_dir."""
        config = {"topic": "Test Novel"}
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(config, output_dir=tmpdir)
            assert manager.output_dir == tmpdir

    def test_set_output_dir(self):
        """Test setting output directory."""
        config = {"topic": "Test"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            manager.set_output_dir(tmpdir)
            assert manager.output_dir == tmpdir

    def test_atomic_write_creates_file(self):
        """Test atomic_write creates file correctly."""
        config = {"topic": "Test"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            manager.atomic_write(test_file, "Hello, World!")
            assert test_file.read_text() == "Hello, World!"

    def test_atomic_write_overwrites(self):
        """Test atomic_write overwrites existing file."""
        config = {"topic": "Test"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Old content")
            manager.atomic_write(test_file, "New content")
            assert test_file.read_text() == "New content"

    def test_atomic_write_json(self):
        """Test atomic_write_json creates valid JSON."""
        config = {"topic": "Test"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            data = {"key": "value", "number": 42}
            manager.atomic_write_json(test_file, data)
            loaded = json.loads(test_file.read_text())
            assert loaded == data

    def test_save_chapter_checkpoint(self):
        """Test saving chapter checkpoint."""
        config = {"topic": "Test Novel", "style": "xianxia"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            manager.set_output_dir(tmpdir)

            mock_chapter = MagicMock()
            mock_chapter.chapter_num = 5
            mock_chapter.title = "测试章节"
            mock_chapter.content = "这是章节内容。"
            mock_chapter.word_count = 100

            manager.save_chapter_checkpoint(mock_chapter)

            # Verify chapters directory exists
            chapters_dir = Path(tmpdir) / "chapters"
            assert chapters_dir.exists()

            # Verify chapter file was created
            chapter_files = list(chapters_dir.glob("*.md"))
            assert len(chapter_files) == 1
            assert "005" in chapter_files[0].name

            # Verify result.json was created
            result_file = Path(tmpdir) / "result.json"
            assert result_file.exists()

    def test_save_outline_checkpoint(self):
        """Test saving outline checkpoint."""
        config = {"topic": "Test Novel"}
        manager = CheckpointManager(config)
        with tempfile.TemporaryDirectory() as tmpdir:
            manager.set_output_dir(tmpdir)

            world_data = {
                "name": "Test World",
                "description": "A test world",
                "factions": "Faction A, Faction B",
                "locations": "Location 1, Location 2",
                "power_system": "Magic system",
            }
            plot_data = {
                "main_strand": {"description": "Main plot"},
                "volumes": [{"title": "Volume 1"}],
                "high_points": ["Point 1", "Point 2"],
            }

            manager.save_outline_checkpoint(world_data, plot_data, "outline")

            # Verify outline directory exists
            outline_dir = Path(tmpdir) / "outline"
            assert outline_dir.exists()

            # Verify files were created
            assert (outline_dir / "world.md").exists()
            assert (outline_dir / "outline.md").exists()
            assert (outline_dir / "metadata.json").exists()

            # Verify metadata.json content
            metadata = json.loads((outline_dir / "metadata.json").read_text())
            assert metadata["topic"] == "Test Novel"
            assert metadata["stage"] == "outline"
