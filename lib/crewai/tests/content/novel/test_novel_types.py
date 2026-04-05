"""Tests for novel_types."""

import tempfile
from pathlib import Path

import pytest

from crewai.content.novel.novel_types import ChapterOutput, NovelOutput, ReviewCheckResult


class TestChapterOutput:
    """Tests for ChapterOutput."""

    def test_init(self):
        """Test ChapterOutput initialization."""
        chapter = ChapterOutput(
            chapter_num=1,
            title="第一章：觉醒",
            content="这是章节内容。",
            word_count=1000,
        )
        assert chapter.chapter_num == 1
        assert chapter.title == "第一章：觉醒"
        assert chapter.content == "这是章节内容。"
        assert chapter.word_count == 1000

    def test_init_with_defaults(self):
        """Test ChapterOutput with default values."""
        chapter = ChapterOutput(
            chapter_num=1,
            title="Test",
            content="Content",
            word_count=100,
        )
        assert chapter.key_events == []
        assert chapter.character_appearances == []
        assert chapter.setting == ""
        assert chapter.notes == ""

    def test_init_with_optional_fields(self):
        """Test ChapterOutput with optional fields."""
        chapter = ChapterOutput(
            chapter_num=5,
            title="第五章：决战",
            content="Long content...",
            word_count=5000,
            key_events=["事件1", "事件2"],
            character_appearances=["角色A", "角色B"],
            setting="战场",
            notes="重要章节",
        )
        assert chapter.chapter_num == 5
        assert len(chapter.key_events) == 2
        assert len(chapter.character_appearances) == 2
        assert chapter.setting == "战场"


class TestNovelOutput:
    """Tests for NovelOutput."""

    def test_init(self):
        """Test NovelOutput initialization."""
        novel = NovelOutput(
            title="测试小说",
            genre="xianxia",
            style="修仙",
            world_output={},
            total_word_count=500000,
        )
        assert novel.title == "测试小说"
        assert novel.genre == "xianxia"
        assert novel.style == "修仙"
        assert novel.total_word_count == 500000

    def test_init_with_chapters(self):
        """Test NovelOutput with chapters."""
        chapters = [
            ChapterOutput(chapter_num=1, title="第一章", content="Content1", word_count=1000),
            ChapterOutput(chapter_num=2, title="第二章", content="Content2", word_count=1200),
        ]
        novel = NovelOutput(
            title="测试小说",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=chapters,
            total_word_count=2200,
        )
        assert len(novel.chapters) == 2
        assert novel.chapters[0].chapter_num == 1
        assert novel.chapters[1].chapter_num == 2

    def test_get_chapter(self):
        """Test get_chapter method."""
        chapters = [
            ChapterOutput(chapter_num=1, title="第一章", content="Content1", word_count=1000),
            ChapterOutput(chapter_num=2, title="第二章", content="Content2", word_count=1200),
            ChapterOutput(chapter_num=3, title="第三章", content="Content3", word_count=1400),
        ]
        novel = NovelOutput(
            title="测试小说",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=chapters,
            total_word_count=3600,
        )

        # Find existing chapter
        ch2 = novel.get_chapter(2)
        assert ch2 is not None
        assert ch2.title == "第二章"

        # Find non-existent chapter
        ch99 = novel.get_chapter(99)
        assert ch99 is None

    def test_get_all_text(self):
        """Test get_all_text method."""
        chapters = [
            ChapterOutput(chapter_num=1, title="第一章", content="Content of chapter 1.", word_count=100),
            ChapterOutput(chapter_num=2, title="第二章", content="Content of chapter 2.", word_count=100),
        ]
        novel = NovelOutput(
            title="测试小说",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=chapters,
            total_word_count=200,
        )

        text = novel.get_all_text()
        assert "第1章: 第一章" in text
        assert "Content of chapter 1." in text
        assert "第2章: 第二章" in text
        assert "Content of chapter 2." in text

    def test_save_to_file(self):
        """Test save_to_file method."""
        chapters = [
            ChapterOutput(chapter_num=1, title="第一章", content="Content 1", word_count=100),
            ChapterOutput(chapter_num=2, title="第二章", content="Content 2", word_count=100),
        ]
        novel = NovelOutput(
            title="测试小说",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=chapters,
            total_word_count=200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_files = novel.save_to_file(tmpdir)

            # Should save: world file + 2 chapter files
            assert len(saved_files) >= 3

            # Check chapter files exist
            chapter1_path = Path(tmpdir) / "测试小说" / "第01章-第一章.md"
            assert chapter1_path.exists()

            # Check content
            content = chapter1_path.read_text()
            assert "第一章" in content
            assert "Content 1" in content

    def test_save_to_file_with_special_chars(self):
        """Test save_to_file handles special characters in title."""
        novel = NovelOutput(
            title="测试/小说: 危险标题?",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=[],
            total_word_count=0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            saved_files = novel.save_to_file(tmpdir)
            # Should not raise - special chars should be sanitized
            assert len(saved_files) >= 1


class TestNovelOutputWordCount:
    """Tests for word count calculation."""

    def test_total_word_count_from_chapters(self):
        """Test total word count can be calculated from chapters."""
        chapters = [
            ChapterOutput(chapter_num=1, title="第一章", content="A" * 1000, word_count=1000),
            ChapterOutput(chapter_num=2, title="第二章", content="B" * 2000, word_count=2000),
            ChapterOutput(chapter_num=3, title="第三章", content="C" * 3000, word_count=3000),
        ]
        novel = NovelOutput(
            title="测试",
            genre="xianxia",
            style="修仙",
            world_output={},
            chapters=chapters,
            total_word_count=6000,
        )

        # Verify word counts
        assert chapters[0].word_count == 1000
        assert chapters[1].word_count == 2000
        assert chapters[2].word_count == 3000
        assert novel.total_word_count == 6000


class TestReviewCheckResult:
    """Tests for ReviewCheckResult."""

    def test_init_passed(self):
        """Test initialization with passed=True."""
        result = ReviewCheckResult(check_type="outline", passed=True)
        assert result.check_type == "outline"
        assert result.passed is True
        assert result.issues == []
        assert result.suggestions == []
        assert result.score == 0.0

    def test_init_failed(self):
        """Test initialization with passed=False."""
        result = ReviewCheckResult(
            check_type="outline",
            passed=False,
            issues=["世界观不一致", "情节不完整"],
            suggestions=["建议1", "建议2"],
            score=5.0,
        )
        assert result.passed is False
        assert len(result.issues) == 2
        assert len(result.suggestions) == 2
        assert result.score == 5.0

    def test_has_issues_true(self):
        """Test has_issues returns True when issues exist."""
        result = ReviewCheckResult(
            check_type="outline",
            passed=False,
            issues=["问题1"],
        )
        assert result.has_issues() is True

    def test_has_issues_false(self):
        """Test has_issues returns False when no issues."""
        result = ReviewCheckResult(check_type="outline", passed=True)
        assert result.has_issues() is False

    def test_default_score(self):
        """Test default score is 0.0."""
        result = ReviewCheckResult(check_type="outline", passed=True)
        assert result.score == 0.0

    def test_score_can_be_set(self):
        """Test score can be set to any value."""
        result = ReviewCheckResult(check_type="outline", passed=True, score=8.5)
        assert result.score == 8.5
