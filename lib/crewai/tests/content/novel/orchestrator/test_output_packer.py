"""Tests for OutputPacker."""

import pytest
from unittest.mock import MagicMock, patch

from crewai.content.base import BaseCrewOutput
from crewai.content.novel.orchestrator.output_packer import OutputPacker


class TestOutputPacker:
    """Tests for OutputPacker output packing utility."""

    def test_pack_state_output(self):
        """Test packing state output."""
        summary = {"stage": "outline", "world_name": "Test World"}
        result = OutputPacker.pack_state_output(summary, 10.5)

        assert isinstance(result, BaseCrewOutput)
        assert result.content is None
        assert result.execution_time == 10.5
        assert "pipeline_state" in result.metadata
        assert result.metadata["stopped"] is True

    def test_pack_approval_output_with_output_dir(self):
        """Test packing approval output with explicit output_dir."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_pipeline_state = MagicMock()
            content = {"world_data": {"name": "Test"}, "plot_data": {}}
            result = OutputPacker.pack_approval_output(
                mock_pipeline_state, "outline", content, 5.0, output_dir=tmpdir
            )

            assert isinstance(result, BaseCrewOutput)
            assert result.content is None
            assert result.execution_time == 5.0
            assert result.metadata["approval_required"] is True
            assert result.metadata["stage"] == "outline"
            assert result.metadata["stage_status"] == "pending_approval"
            assert "_pending.json" in result.metadata["pipeline_state_path"]
            assert "outline" in result.metadata["pipeline_state_path"]

            # P1: Contract test - state file path MUST be in project output directory
            state_path = result.metadata["pipeline_state_path"]
            assert state_path.startswith(tmpdir), \
                f"State file must be in output_dir ({tmpdir}), got: {state_path}"
            # Verify path contains expected components
            assert "outline" in state_path
            assert "_pending.json" in state_path

            # Verify pipeline_state.save was called with correct path
            mock_pipeline_state.save.assert_called_once()
            saved_path = mock_pipeline_state.save.call_args[0][0]
            assert saved_path.startswith(tmpdir), \
                f"save() must be called with path in output_dir ({tmpdir}), got: {saved_path}"

    def test_pack_approval_output_without_output_dir(self):
        """Test packing approval output without output_dir falls back to cwd."""
        import os
        mock_pipeline_state = MagicMock()
        content = {"world_data": {"name": "Test"}, "plot_data": {}}
        result = OutputPacker.pack_approval_output(
            mock_pipeline_state, "outline", content, 5.0
        )

        assert isinstance(result, BaseCrewOutput)
        # Without output_dir, file should be in current working directory
        state_path = result.metadata["pipeline_state_path"]
        assert state_path.endswith("_pending.json")
        assert os.path.basename(state_path).startswith(".novel_pipeline_")

        # Verify pipeline_state.save was called
        mock_pipeline_state.save.assert_called_once()

    def test_summarize_stage_content_outline(self):
        """Test summarizing outline stage content."""
        content = {
            "world_data": {"name": "Test World", "factions": []},
            "plot_data": {"main_strand": "Test plot"},
        }
        result = OutputPacker.summarize_stage_content("outline", content)

        assert result["world_name"] == "Test World"
        assert "world_summary" in result
        assert "plot_summary" in result

    def test_summarize_stage_content_volume(self):
        """Test summarizing volume stage content."""
        content = {
            "volume_outlines": [
                {"title": "Volume 1"},
                {"title": "Volume 2"},
                {"title": "Volume 3"},
                {"title": "Volume 4"},
            ]
        }
        result = OutputPacker.summarize_stage_content("volume", content)

        assert result["volumes_count"] == 4
        assert result["volume_titles"] == ["Volume 1", "Volume 2", "Volume 3"]

    def test_summarize_stage_content_summary(self):
        """Test summarizing summary stage content."""
        content = {
            "chapter_summaries": [
                {"title": "Chapter 1"},
                {"title": "Chapter 2"},
                {"title": "Chapter 3"},
                {"title": "Chapter 4"},
                {"title": "Chapter 5"},
                {"title": "Chapter 6"},
            ]
        }
        result = OutputPacker.summarize_stage_content("summary", content)

        assert result["chapters_count"] == 6
        assert len(result["chapter_titles"]) == 5  # Limited to 5

    def test_summarize_stage_content_chapter(self):
        """Test summarizing chapter stage content."""
        mock_chapter = MagicMock()
        mock_chapter.title = "Test Chapter"
        mock_chapter.word_count = 5000
        mock_chapter.key_events = ["event1", "event2"]

        content = {
            "chapter_num": 5,
            "chapter_output": mock_chapter,
        }
        result = OutputPacker.summarize_stage_content("chapter", content)

        assert result["chapter_num"] == 5
        assert result["chapter_title"] == "Test Chapter"
        assert result["word_count"] == 5000
        assert result["key_events"] == ["event1", "event2"]

    def test_summarize_stage_content_unknown(self):
        """Test summarizing unknown stage returns empty dict."""
        result = OutputPacker.summarize_stage_content("unknown", {})
        assert result == {}
