"""Tests for ChapterManager."""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest

from agents.chapter_manager import (
    ChapterManager,
    ChapterMetadata,
    ChapterContent,
    ChapterPlotSummary,
)


class TestChapterManagerInit:
    """Test ChapterManager initialization."""

    def test_init_creates_directories(self, temp_novels_dir):
        """Test that initialization creates required directories."""
        project_id = "test_project_001"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        assert manager.project_id == project_id
        assert manager.base_dir == temp_novels_dir / project_id
        assert manager.chapters_dir.exists()
        assert manager.plot_summaries_dir.exists()

    def test_init_loads_existing_index(self, temp_novels_dir):
        """Test that initialization loads existing metadata index."""
        project_id = "test_project_002"

        # Pre-create metadata file
        base_dir = temp_novels_dir / project_id
        base_dir.mkdir(parents=True)
        chapters_dir = base_dir / "chapters"
        chapters_dir.mkdir()

        # Create chapter file
        chapter_file = chapters_dir / "ch001_废物少年.md"
        chapter_file.write_text("# 废物少年\n\n内容...", encoding="utf-8")

        # Create metadata
        metadata_file = base_dir / "metadata.json"
        metadata_data = {
            "project_id": project_id,
            "updated_at": datetime.now().isoformat(),
            "total_chapters": 1,
            "chapters": [
                {
                    "number": 1,
                    "title": "废物少年",
                    "word_count": 1000,
                    "file_path": str(chapter_file),
                    "created_at": datetime.now().isoformat(),
                    "generation_time": datetime.now().isoformat(),
                    "summary": "测试概要",
                    "key_events": [],
                    "character_appearances": [],
                }
            ],
        }
        metadata_file.write_text(json.dumps(metadata_data, ensure_ascii=False), encoding="utf-8")

        # Initialize manager
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        assert len(manager._chapters_index) == 1
        assert 1 in manager._chapters_index


class TestSaveChapter:
    """Test save_chapter functionality."""

    def test_save_chapter_basic(self, temp_novels_dir):
        """Test saving a basic chapter."""
        project_id = "test_project_003"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        result = manager.save_chapter(
            number=1,
            title="废物少年",
            content="这是一个测试章节的内容。",
            word_count=15,
            summary="少年被发现是废物",
            key_events=["退婚"],
            character_appearances=["林轩", "萧薰儿"],
        )

        # save_chapter returns ChapterSaveResult with metadata
        assert result.metadata.number == 1
        assert result.metadata.title == "废物少年"
        assert result.metadata.word_count == 15
        assert result.metadata.summary == "少年被发现是废物"
        assert result.metadata.key_events == ["退婚"]
        assert result.metadata.character_appearances == ["林轩", "萧薰儿"]
        assert result.metadata.file_path is not None

    def test_save_chapter_creates_file(self, temp_novels_dir):
        """Test that save_chapter creates the chapter file."""
        project_id = "test_project_004"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(
            number=1,
            title="废物少年",
            content="正文内容",
            word_count=4,
        )

        chapter_file = list(manager.chapters_dir.glob("ch001_*.md"))
        assert len(chapter_file) == 1
        content = chapter_file[0].read_text(encoding="utf-8")
        assert "# 废物少年" in content
        assert "正文内容" in content

    def test_save_chapter_updates_index(self, temp_novels_dir):
        """Test that save_chapter updates the metadata index."""
        project_id = "test_project_005"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容", word_count=2)
        manager.save_chapter(number=2, title="第二章", content="内容2", word_count=4)

        assert len(manager._chapters_index) == 2
        assert 1 in manager._chapters_index
        assert 2 in manager._chapters_index
        assert manager._chapters_index[1].title == "第一章"
        assert manager._chapters_index[2].title == "第二章"

    def test_save_chapter_persists_to_disk(self, temp_novels_dir):
        """Test that saved chapters persist to disk."""
        project_id = "test_project_006"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容", word_count=2)

        # Create new manager instance to reload from disk
        manager2 = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        assert 1 in manager2._chapters_index
        assert manager2._chapters_index[1].title == "第一章"


class TestLoadChapter:
    """Test load_chapter functionality."""

    def test_load_chapter_basic(self, temp_novels_dir):
        """Test loading a saved chapter."""
        project_id = "test_project_007"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(
            number=1,
            title="废物少年",
            content="这是正文内容",
            word_count=6,
            summary="测试概要",
        )

        chapter = manager.load_chapter(1)

        assert chapter is not None
        assert isinstance(chapter, ChapterContent)
        assert chapter.metadata.number == 1
        assert chapter.metadata.title == "废物少年"
        assert "这是正文内容" in chapter.content

    def test_load_chapter_not_found(self, temp_novels_dir):
        """Test loading a non-existent chapter returns None."""
        project_id = "test_project_008"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        chapter = manager.load_chapter(999)
        assert chapter is None

    def test_load_chapter_file_missing(self, temp_novels_dir):
        """Test loading when chapter file is deleted returns None."""
        project_id = "test_project_009"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容", word_count=2)

        # Delete the file manually
        chapter_file = list(manager.chapters_dir.glob("ch001_*.md"))[0]
        chapter_file.unlink()

        chapter = manager.load_chapter(1)
        assert chapter is None


class TestGetChapterList:
    """Test get_chapter_list functionality."""

    def test_get_chapter_list_empty(self, temp_novels_dir):
        """Test getting chapter list when no chapters exist."""
        project_id = "test_project_010"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        chapter_list = manager.get_chapter_list()
        assert chapter_list == []

    def test_get_chapter_list_sorted(self, temp_novels_dir):
        """Test that chapter list is sorted by chapter number."""
        project_id = "test_project_011"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=3, title="第三章", content="内容3", word_count=3)
        manager.save_chapter(number=1, title="第一章", content="内容1", word_count=1)
        manager.save_chapter(number=2, title="第二章", content="内容2", word_count=2)

        chapter_list = manager.get_chapter_list()

        assert len(chapter_list) == 3
        assert chapter_list[0].number == 1
        assert chapter_list[1].number == 2
        assert chapter_list[2].number == 3

    def test_get_chapter_list_returns_metadata(self, temp_novels_dir):
        """Test that chapter list returns ChapterMetadata objects."""
        project_id = "test_project_012"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(
            number=1,
            title="第一章",
            content="内容",
            word_count=2,
            summary="概要",
        )

        chapter_list = manager.get_chapter_list()

        assert len(chapter_list) == 1
        assert isinstance(chapter_list[0], ChapterMetadata)
        assert chapter_list[0].summary == "概要"


class TestBuildContext:
    """Test build_context functionality."""

    def test_build_context_first_chapter(self, temp_novels_dir):
        """Test context for first chapter."""
        project_id = "test_project_013"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        context = manager.build_context(1)
        assert context == "暂无前情 (第一章)"

    def test_build_context_with_previous_summaries(self, temp_novels_dir):
        """Test context building with previous chapter summaries."""
        project_id = "test_project_014"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(
            number=1, title="第一章", content="内容1", word_count=2, summary="少年发现自己是废物"
        )
        manager.save_chapter(
            number=2, title="第二章", content="内容2", word_count=2, summary="被未婚妻退婚"
        )

        context = manager.build_context(3)

        assert "第1章 第一章" in context
        assert "少年发现自己是废物" in context
        assert "第2章 第二章" in context
        assert "被未婚妻退婚" in context

    def test_build_context_window_limit(self, temp_novels_dir):
        """Test that context respects the window limit."""
        project_id = "test_project_015"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        for i in range(1, 6):
            manager.save_chapter(
                number=i,
                title=f"第{i}章",
                content=f"内容{i}",
                word_count=2,
                summary=f"概要{i}",
            )

        # Window=2 should only include 2 previous chapters
        context = manager.build_context(6, window=2)

        # Should only have the last 2 chapters (4 and 5), not all previous
        assert "第5章" in context
        assert "概要5" in context

    def test_build_context_no_summaries(self, temp_novels_dir):
        """Test context when previous chapters have no summaries."""
        project_id = "test_project_016"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容1", word_count=2)

        context = manager.build_context(2)
        assert "故事已发展到第1章" in context


class TestExportToText:
    """Test export_to_text functionality."""

    def test_export_to_text_empty(self, temp_novels_dir):
        """Test exporting when no chapters exist."""
        project_id = "test_project_017"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        output_path = temp_novels_dir / "export.txt"
        count = manager.export_to_text(str(output_path))

        assert count == 0
        assert not output_path.exists()

    def test_export_to_text_basic(self, temp_novels_dir):
        """Test exporting chapters to text file."""
        project_id = "test_project_018"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(
            number=1,
            title="第一章",
            content="这是第一章的正文内容",
            word_count=10,
        )
        manager.save_chapter(
            number=2,
            title="第二章",
            content="这是第二章的正文内容",
            word_count=10,
        )

        output_path = temp_novels_dir / "export.txt"
        count = manager.export_to_text(str(output_path))

        # count is number of lines written, not chapters
        assert count > 0
        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "第1章" in content and "第一章" in content
        assert "第2章" in content and "第二章" in content
        assert "这是第一章的正文内容" in content
        assert "这是第二章的正文内容" in content

    def test_export_to_text_range(self, temp_novels_dir):
        """Test exporting a range of chapters."""
        project_id = "test_project_019"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        for i in range(1, 4):
            manager.save_chapter(
                number=i, title=f"第{i}章", content=f"内容{i}", word_count=2
            )

        output_path = temp_novels_dir / "export.txt"
        count = manager.export_to_text(str(output_path), start=1, end=2)

        # count is lines written
        assert count > 0
        content = output_path.read_text(encoding="utf-8")
        assert "第3章" not in content


class TestPlotSummary:
    """Test plot summary functionality."""

    def test_save_and_get_plot_summary(self, temp_novels_dir):
        """Test saving and retrieving plot summary."""
        project_id = "test_project_020"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        summary = ChapterPlotSummary(
            chapter_number=1,
            one_line_summary="少年发现自己是废物",
            brief_summary="林轩在家族测试中被发现没有灵根，被所有人嘲笑。",
            key_plot_points=["测试日", "发现无灵根", "被退婚"],
            character_states={"林轩": "废物状态", "萧薰儿": "嫌弃"},
            plot_threads=["废物逆袭线", "退婚线"],
            foreshadowing=["神秘玉佩"],
        )

        filepath = manager.save_plot_summary(summary)
        assert Path(filepath).exists()

        loaded = manager.get_plot_summary(1)
        assert loaded is not None
        assert loaded.one_line_summary == "少年发现自己是废物"
        assert loaded.brief_summary == "林轩在家族测试中被发现没有灵根，被所有人嘲笑。"
        assert "测试日" in loaded.key_plot_points
        assert loaded.character_states["林轩"] == "废物状态"

    def test_get_plot_summary_not_found(self, temp_novels_dir):
        """Test getting non-existent plot summary."""
        project_id = "test_project_021"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        result = manager.get_plot_summary(999)
        assert result is None


class TestGetLatestChapterNumber:
    """Test get_latest_chapter_number functionality."""

    def test_get_latest_chapter_number_empty(self, temp_novels_dir):
        """Test when no chapters exist."""
        project_id = "test_project_022"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        assert manager.get_latest_chapter_number() == 0

    def test_get_latest_chapter_number(self, temp_novels_dir):
        """Test getting the latest chapter number."""
        project_id = "test_project_023"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容1", word_count=2)
        manager.save_chapter(number=3, title="第三章", content="内容3", word_count=2)
        manager.save_chapter(number=2, title="第二章", content="内容2", word_count=2)

        assert manager.get_latest_chapter_number() == 3


class TestGetStats:
    """Test get_stats functionality."""

    def test_get_stats_basic(self, temp_novels_dir):
        """Test getting statistics."""
        project_id = "test_project_024"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        manager.save_chapter(number=1, title="第一章", content="内容1", word_count=1000)
        manager.save_chapter(number=2, title="第二章", content="内容2", word_count=2000)

        stats = manager.get_stats()

        assert stats["project_id"] == project_id
        assert stats["total_chapters"] == 2
        assert stats["total_words"] == 3000
        assert stats["latest_chapter"] == 2
        assert len(stats["chapters"]) == 2


class TestValidateCharacterState:
    """Test validate_character_state functionality."""

    def test_validate_character_state_no_summary(self, temp_novels_dir):
        """Test validation when no plot summary exists."""
        project_id = "test_project_025"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        result = manager.validate_character_state(1, "林轩", "废物状态")

        assert result["valid"] is False
        assert "情节概述不存在" in result["reason"]

    def test_validate_character_state_not_recorded(self, temp_novels_dir):
        """Test validation when character is not recorded."""
        project_id = "test_project_026"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        summary = ChapterPlotSummary(
            chapter_number=1,
            one_line_summary="测试",
            character_states={"萧薰儿": "嫌弃"},
        )
        manager.save_plot_summary(summary)

        result = manager.validate_character_state(1, "林轩", "废物状态")

        assert result["valid"] is True
        assert "状态未记录" in result["reason"]

    def test_validate_character_state_match(self, temp_novels_dir):
        """Test validation when character state matches."""
        project_id = "test_project_027"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        summary = ChapterPlotSummary(
            chapter_number=1,
            one_line_summary="测试",
            character_states={"林轩": "废物状态"},
        )
        manager.save_plot_summary(summary)

        result = manager.validate_character_state(1, "林轩", "废物状态")

        assert result["valid"] is True

    def test_validate_character_state_mismatch(self, temp_novels_dir):
        """Test validation when character state does not match."""
        project_id = "test_project_028"
        manager = ChapterManager(project_id, base_dir=str(temp_novels_dir))

        summary = ChapterPlotSummary(
            chapter_number=1,
            one_line_summary="测试",
            character_states={"林轩": "筑基境界"},
        )
        manager.save_plot_summary(summary)

        result = manager.validate_character_state(1, "林轩", "废物状态")

        assert result["valid"] is False
        assert "状态不一致" in result["reason"]
