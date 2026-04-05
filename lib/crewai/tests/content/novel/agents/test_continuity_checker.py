"""Tests for ContinuityChecker."""
import pytest
from unittest.mock import MagicMock, patch

from crewai.content.novel.agents.continuity_checker import ContinuityChecker
from crewai.content.novel.novel_types import ReviewCheckResult


class TestContinuityCheckerParse:
    """Tests for ContinuityChecker._parse_response method."""

    def test_parse_valid_json(self):
        """Test parsing a valid JSON response."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = '{"score": 9.0, "issues": [], "suggestions": []}'

        result = checker._parse_response(mock_response)

        assert result.check_type == "continuity"
        assert result.score == 9.0
        assert result.passed is True

    def test_parse_with_issues(self):
        """Test parsing a response with issues."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = (
            '{"score": 5.5, '
            '"issues": ["地点突变：前章在城市，下章突然在乡村"], '
            '"suggestions": ["增加过渡描写"]}'
        )

        result = checker._parse_response(mock_response)

        assert result.score == 5.5
        assert len(result.issues) == 1
        assert "地点突变" in result.issues[0]
        assert result.passed is False  # Score < 7.0

    def test_parse_with_markdown_json(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = '```json\n{"score": 8.0, "issues": [], "suggestions": []}\n```'

        result = checker._parse_response(mock_response)

        assert result.score == 8.0
        assert result.passed is True

    def test_parse_invalid_json_returns_fail_result(self):
        """Test that invalid JSON returns a failing result."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = "这是无效的响应内容"

        result = checker._parse_response(mock_response)

        assert result.score == 5.0
        assert result.passed is False
        assert len(result.issues) > 0

    def test_score_7_is_passing_threshold(self):
        """Test that score >= 7.0 is passing."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = '{"score": 7.0, "issues": [], "suggestions": []}'

        result = checker._parse_response(mock_response)
        assert result.passed is True

    def test_score_below_7_fails(self):
        """Test that score < 7.0 fails."""
        checker = ContinuityChecker(llm=None)

        mock_response = MagicMock()
        mock_response.raw = '{"score": 6.9, "issues": ["问题"], "suggestions": []}'

        result = checker._parse_response(mock_response)
        assert result.passed is False


class TestContinuityCheckerBuildPrompt:
    """Tests for ContinuityChecker._build_check_prompt method."""

    def test_prompt_includes_chapter_numbers(self):
        """Test that prompt includes correct chapter numbers."""
        checker = ContinuityChecker(llm=None)

        prompt = checker._build_check_prompt(
            chapter_content="本章内容",
            previous_chapter_ending="前章结尾",
            context={"chapter_number": 5, "style": "xianxia"},
        )

        assert "第5章" in prompt
        assert "第4章" in prompt  # chapter - 1
        assert "xianxia" in prompt

    def test_prompt_includes_previous_ending(self):
        """Test that prompt includes previous chapter ending."""
        checker = ContinuityChecker(llm=None)

        prompt = checker._build_check_prompt(
            chapter_content="新章节内容",
            previous_chapter_ending="主角在城门口等待天明",
            context={"chapter_number": 3, "style": "urban"},
        )

        assert "城门口等待天明" in prompt
        assert "新章节内容" in prompt

    def test_prompt_handles_missing_context(self):
        """Test that prompt handles None or empty context."""
        checker = ContinuityChecker(llm=None)

        prompt = checker._build_check_prompt(
            chapter_content="内容",
            previous_chapter_ending="前章",
            context=None,
        )

        assert "?" in prompt  # chapter number defaults to "?"

    def test_prompt_includes_four_dimensions(self):
        """Test that prompt covers the four continuity dimensions."""
        checker = ContinuityChecker(llm=None)

        prompt = checker._build_check_prompt(
            chapter_content="内容",
            previous_chapter_ending="前章结尾",
            context={"chapter_number": 2, "style": "通用"},
        )

        assert "地点连贯性" in prompt
        assert "角色状态连贯性" in prompt
        assert "时间线连贯性" in prompt
        assert "悬念连贯性" in prompt


class TestContinuityCheckerIntegration:
    """Integration tests for ContinuityChecker with mocked agent."""

    def test_check_calls_agent_kickoff_with_prompt(self):
        """Test that check() calls the agent with the correct prompt.

        Note: This test requires a real LLM/API key, so we test the prompt
        building logic directly instead.
        """
        checker = ContinuityChecker(llm=None)
        prompt = checker._build_check_prompt(
            chapter_content="本章在皇宫继续",
            previous_chapter_ending="前章结尾在城门口",
            context={"chapter_number": 2, "style": "xianxia"},
        )
        assert "第2章" in prompt
        assert "第1章" in prompt
        assert "皇宫" in prompt
        assert "城门口" in prompt
        assert "xianxia" in prompt


class TestReviewPipelineContinuity:
    """Tests for ReviewPipeline continuity integration."""

    def test_review_pipeline_runs_continuity_when_ending_provided(self):
        """Test that ReviewPipeline runs continuity check when previous_chapter_ending is set."""
        from crewai.content.review.review_pipeline import ReviewPipeline
        from crewai.content.review.review_context import ReviewContext

        pipeline = ReviewPipeline()

        mock_checker = MagicMock()
        mock_result = ReviewCheckResult(check_type="continuity", passed=True)
        mock_result.score = 9.0
        mock_checker.check.return_value = mock_result

        pipeline._continuity_checker = mock_checker

        context = ReviewContext(
            title="测试小说",
            previous_chapter_ending="主角在城门口等待",
            chapter_number=2,
        )

        # Mock critique and polish
        with patch.object(pipeline.critique_agent, "critique") as mock_critique, \
             patch.object(pipeline.revision_agent, "revise") as mock_revise, \
             patch.object(pipeline.polish_agent, "polish") as mock_polish:

            mock_critique.return_value = MagicMock(summary="", score=10.0)
            mock_revise.return_value = "修改后草稿"
            mock_polish.return_value = "润色后草稿"

            result = pipeline.run("草稿内容", context)

        mock_checker.check.assert_called_once()
        call_kwargs = mock_checker.check.call_args.kwargs
        assert call_kwargs["chapter_content"] == "草稿内容"
        assert "城门口" in call_kwargs["previous_chapter_ending"]
        assert result["continuity"] is not None
        assert result["continuity"].score == 9.0

    def test_review_pipeline_skips_continuity_when_ending_empty(self):
        """Test that ReviewPipeline skips continuity when previous_chapter_ending is empty."""
        from crewai.content.review.review_pipeline import ReviewPipeline
        from crewai.content.review.review_context import ReviewContext

        pipeline = ReviewPipeline()

        mock_checker = MagicMock()
        pipeline._continuity_checker = mock_checker

        context = ReviewContext(
            title="测试小说",
            previous_chapter_ending="",
            chapter_number=2,
        )

        with patch.object(pipeline.critique_agent, "critique") as mock_critique, \
             patch.object(pipeline.revision_agent, "revise") as mock_revise, \
             patch.object(pipeline.polish_agent, "polish") as mock_polish:

            mock_critique.return_value = MagicMock(summary="", score=10.0)
            mock_revise.return_value = "修改后草稿"
            mock_polish.return_value = "润色后草稿"

            result = pipeline.run("草稿内容", context)

        mock_checker.check.assert_not_called()
        assert result["continuity"] is None

    def test_skip_continuity_flag_bypasses_check(self):
        """Test that skip_continuity=True bypasses the continuity check."""
        from crewai.content.review.review_pipeline import ReviewPipeline
        from crewai.content.review.review_context import ReviewContext

        pipeline = ReviewPipeline(skip_continuity=True)

        mock_checker = MagicMock()
        pipeline._continuity_checker = mock_checker

        context = ReviewContext(
            title="测试小说",
            previous_chapter_ending="主角在城门口",
            chapter_number=2,
        )

        with patch.object(pipeline.critique_agent, "critique") as mock_critique, \
             patch.object(pipeline.revision_agent, "revise") as mock_revise, \
             patch.object(pipeline.polish_agent, "polish") as mock_polish:

            mock_critique.return_value = MagicMock(summary="", score=10.0)
            mock_revise.return_value = "修改后草稿"
            mock_polish.return_value = "润色后草稿"

            result = pipeline.run("草稿内容", context)

        mock_checker.check.assert_not_called()
        assert result["continuity"] is None


class TestReviewContextPreviousChapterEnding:
    """Tests for ReviewContext previous_chapter_ending field."""

    def test_review_context_has_previous_chapter_ending(self):
        """Test that ReviewContext accepts previous_chapter_ending."""
        from crewai.content.review.review_context import ReviewContext

        context = ReviewContext(
            title="测试",
            previous_chapter_ending="主角在城门口等待天明",
        )

        assert context.previous_chapter_ending == "主角在城门口等待天明"

    def test_review_context_to_dict_includes_ending(self):
        """Test that to_dict() includes previous_chapter_ending."""
        from crewai.content.review.review_context import ReviewContext

        context = ReviewContext(
            title="测试",
            previous_chapter_ending="前章结尾场景",
        )

        d = context.to_dict()
        assert "previous_chapter_ending" in d
        assert d["previous_chapter_ending"] == "前章结尾场景"

    def test_review_context_from_dict_restores_ending(self):
        """Test that from_dict() restores previous_chapter_ending."""
        from crewai.content.review.review_context import ReviewContext

        data = {
            "title": "测试",
            "previous_chapter_ending": "前章结尾在城门口",
        }
        context = ReviewContext.from_dict(data)
        assert context.previous_chapter_ending == "前章结尾在城门口"

    def test_review_context_get_context_string_includes_ending(self):
        """Test that get_context_string() includes previous_chapter_ending."""
        from crewai.content.review.review_context import ReviewContext

        context = ReviewContext(
            title="测试",
            previous_chapter_ending="前章结尾场景内容",
        )

        context_str = context.get_context_string()
        assert "前章结尾场景" in context_str
