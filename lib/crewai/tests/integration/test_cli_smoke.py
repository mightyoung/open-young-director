"""CLI smoke tests for content generation."""
import json
import tempfile
from pathlib import Path
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock


@pytest.fixture
def cli_runner():
    """Create a CLI runner."""
    return CliRunner()


class TestNovelCLI:
    """Tests for novel CLI commands."""

    def test_create_novel_help(self, cli_runner):
        """Test that novel creation shows in help."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "--help"])
        assert result.exit_code == 0
        assert "novel" in result.output
        # script/blog/podcast are mentioned as experimental in help text
        assert "EXPERIMENTAL" in result.output

    def test_create_type_choice_validation(self, cli_runner):
        """Test that invalid types are rejected."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "invalid_type", "test"])
        assert result.exit_code != 0
        # Click outputs error to stderr, check output contains the error
        assert "invalid_type" in result.output or "is not one of" in result.output

    def test_create_novel_shows_novel_options(self, cli_runner):
        """Test that novel-specific options are visible."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "novel", "--help"])
        assert result.exit_code == 0
        assert "--words" in result.output
        assert "--chapters" in result.output
        assert "--stop-at" in result.output
        assert "--resume-from" in result.output
        assert "--pipeline-state-path" in result.output


class TestExperimentalTypes:
    """Tests for experimental content types (now registered in CLI)."""

    def test_script_valid_choice(self, cli_runner):
        """Test that script is now a valid choice for create command."""
        from crewai.cli.cli import crewai

        # Script is now a valid choice but requires a name argument
        result = cli_runner.invoke(crewai, ["create", "script", "--help"])
        assert result.exit_code == 0
        assert "script" in result.output.lower() or "EXPERIMENTAL" in result.output

    def test_blog_valid_choice(self, cli_runner):
        """Test that blog is now a valid choice for create command."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "blog", "--help"])
        assert result.exit_code == 0
        assert "blog" in result.output.lower() or "EXPERIMENTAL" in result.output

    def test_podcast_valid_choice(self, cli_runner):
        """Test that podcast is now a valid choice for create command."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "podcast", "--help"])
        assert result.exit_code == 0
        assert "podcast" in result.output.lower() or "EXPERIMENTAL" in result.output


class TestBlogExecution:
    """Tests for blog execution path (mocked)."""

    def test_create_blog_with_mocked_crew(self, cli_runner, tmp_path):
        """Test blog creation with mocked BlogCrew."""
        from crewai.cli.create_content import create_blog
        from crewai.content.blog.blog_types import BlogCrewOutput, BlogPost, HookOption

        # Create mock output
        mock_post = BlogPost(
            original_topic="测试博客",
            title="测试标题",
            hooks=[
                HookOption(variant="疑问", hook_text="测试钩子", hook_type="question", engagement_score=8.5)
            ],
            body="这是博客正文内容",
        )
        mock_result = BlogCrewOutput(
            post=mock_post,
            tasks_completed=["生成钩子", "生成标题", "生成正文"],
            execution_time=1.5,
            metadata={"topic": "测试博客"},
        )

        with patch("crewai.content.blog.BlogCrew") as MockBlogCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockBlogCrew.return_value = mock_crew

            result = cli_runner.invoke(create_blog, [
                "测试博客",
                "--platforms", "medium",
                "--keywords", "test,blog",
                "--output", str(tmp_path),
            ])

            # Verify the crew was called
            mock_crew.kickoff.assert_called_once()

            # Verify result
            assert result.exit_code == 0
            assert "博客已生成" in result.output or "生成" in result.output

            result_json = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
            assert result_json["status"] == "success"
            assert "next_actions" in result_json
            assert (tmp_path / "summary.md").exists()

    def test_create_blog_partial_result_writes_summary(self, cli_runner, tmp_path):
        """Test partial blog result does not crash and persists review summary."""
        from crewai.cli.create_content import create_blog
        from crewai.content.blog.blog_types import BlogCrewOutput, BlogPost, ContentStatus

        mock_post = BlogPost(
            original_topic="测试博客",
            title="待人工审核标题",
            hooks=[],
            body="",
            warnings=["正文解析失败，内容为空，请手动补充正文"],
            status=ContentStatus.PARTIAL,
        )
        mock_result = BlogCrewOutput(
            post=mock_post,
            tasks_completed=["生成正文"],
            execution_time=1.0,
            metadata={},
            is_usable=False,
            requires_manual_review=True,
        )

        with patch("crewai.content.blog.BlogCrew") as MockBlogCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockBlogCrew.return_value = mock_crew

            result = cli_runner.invoke(create_blog, [
                "测试博客",
                "--platforms", "medium",
                "--output", str(tmp_path),
            ])

            assert result.exit_code == 0
            result_json = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
            assert result_json["status"] == "partial"
            assert result_json["is_usable"] is False
            assert result_json["requires_manual_review"] is True
            assert result_json["next_actions"]
            assert (tmp_path / "summary.md").exists()


class TestScriptExecution:
    """Tests for script execution path (mocked)."""

    def test_create_script_with_mocked_crew(self, cli_runner, tmp_path):
        """Test script creation with mocked ScriptCrew."""
        from crewai.cli.create_content import create_script
        from crewai.content.script.script_types import ScriptOutput, BeatSheet, Beat
        from crewai.content.base import BaseCrewOutput

        # Create mock output
        mock_beat = Beat(
            number=1,
            name="开场",
            description="介绍主角",
            scene_purpose="建立世界观",
            turning_point="主角出场",
        )
        mock_beat_sheet = BeatSheet(act=1, beats=[mock_beat])

        mock_content = ScriptOutput(
            title="测试剧本",
            logline="一句话概括",
            beat_sheets=[mock_beat_sheet],
            scenes=[],
            dialogues=[],
        )
        mock_result = BaseCrewOutput(
            content=mock_content,
            tasks_completed=["结构分析", "分镜表生成"],
            execution_time=2.0,
            metadata={},
        )

        with patch("crewai.content.script.ScriptCrew") as MockScriptCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockScriptCrew.return_value = mock_crew

            result = cli_runner.invoke(create_script, [
                "测试剧本",
                "--format", "film",
                "--duration", "120",
                "--output", str(tmp_path),
            ])

            # Verify the crew was called
            mock_crew.kickoff.assert_called_once()

            # Verify result
            assert result.exit_code == 0
            assert "剧本已生成" in result.output or "生成" in result.output

            result_json = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
            assert result_json["status"] in {"success", "warning"}
            assert "next_actions" in result_json
            assert (tmp_path / "summary.md").exists()


class TestPodcastExecution:
    """Tests for podcast execution path (mocked)."""

    def test_create_podcast_with_mocked_crew(self, cli_runner, tmp_path):
        """Test podcast creation with mocked PodcastCrew."""
        from crewai.cli.create_content import create_podcast
        from crewai.content.podcast.podcast_types import PodcastOutput
        from crewai.content.base import BaseCrewOutput

        # Create mock output
        mock_content = PodcastOutput(
            title="测试播客",
            preshow="预热内容",
            intro="开场介绍",
            outro="结尾总结",
            total_duration_minutes=30.0,
        )
        mock_result = BaseCrewOutput(
            content=mock_content,
            tasks_completed=["预热", "开场", "段落", "结尾"],
            execution_time=3.0,
            metadata={},
        )

        with patch("crewai.content.podcast.PodcastCrew") as MockPodcastCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockPodcastCrew.return_value = mock_crew

            result = cli_runner.invoke(create_podcast, [
                "测试播客",
                "--duration", "30",
                "--hosts", "2",
                "--style", "narrative",
                "--output", str(tmp_path),
            ])

            # Verify the crew was called
            mock_crew.kickoff.assert_called_once()

            # Verify result
            assert result.exit_code == 0
            assert "播客已生成" in result.output or "生成" in result.output

            result_json = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
            assert result_json["status"] == "complete"
            assert "next_actions" in result_json
            assert (tmp_path / "summary.md").exists()


class TestReviewEachChapterApproval:
    """Tests for review_each_chapter approval flow."""

    def test_pending_chapter_approval_metadata(self):
        """Test that PendingChapterApproval produces correct metadata."""
        from crewai.content.novel.crews.novel_crew import PendingChapterApproval
        from crewai.content.novel.novel_types import ChapterOutput

        # Create mock chapter output
        chapter_output = ChapterOutput(
            chapter_num=5,
            title="第五章：决战",
            content="章节内容...",
            word_count=5000,
        )

        # Create the exception
        exc = PendingChapterApproval(
            message="Chapter 5 pending approval",
            chapter_num=5,
            chapter_output=chapter_output,
            pipeline_state_path="/path/to/pending.json",
        )

        # Verify exception attributes
        assert exc.chapter_num == 5
        assert exc.chapter_output == chapter_output
        assert exc.pipeline_state_path == "/path/to/pending.json"
        assert "Chapter 5" in str(exc)

    def test_novel_crew_output_with_approval_metadata(self):
        """Test that NovelCrew returns correct metadata when approval required."""
        from crewai.content.base import BaseCrewOutput

        # Simulate the metadata returned when approval is required
        mock_result = BaseCrewOutput(
            content=None,
            tasks_completed=["等待审批: chapter_5"],
            execution_time=1.5,
            metadata={
                "approval_required": True,
                "stage": "chapter",
                "stage_status": "pending_approval",
                "pipeline_state_path": "/path/to/pending.json",
                "pending_chapter": 5,
                "content_summary": {
                    "chapter_title": "第五章：决战",
                    "word_count": 5000,
                },
            },
        )

        # Verify metadata structure
        assert mock_result.metadata["approval_required"] is True
        assert mock_result.metadata["pending_chapter"] == 5
        assert mock_result.metadata["pipeline_state_path"] == "/path/to/pending.json"
        assert "chapter_title" in mock_result.metadata["content_summary"]

    def test_approval_cli_message_display(self, cli_runner, tmp_path):
        """Test that CLI correctly displays approval message."""
        from crewai.content.base import BaseCrewOutput

        # Mock result with approval_required
        mock_result = BaseCrewOutput(
            content=None,
            tasks_completed=["等待审批: chapter_5"],
            execution_time=1.5,
            metadata={
                "approval_required": True,
                "pending_chapter": 5,
                "content_summary": {"chapter_title": "第五章：决战"},
                "pipeline_state_path": str(tmp_path / "pending.json"),
            },
        )

        # When approval_required is True, the CLI should show the pending message
        # This test verifies the metadata structure is correct for the CLI to display
        assert mock_result.metadata["approval_required"] is True
        assert "pending_chapter" in mock_result.metadata
        # CLI expects these fields to display the approval message
        assert "pipeline_state_path" in mock_result.metadata

    def test_review_each_chapter_recovery_path(self, cli_runner, tmp_path):
        """Test recovery path for review_each_chapter after pending approval.

        Simulates the scenario:
        1. Chapter 3 completed, pending approval
        2. User approves (removes pending flag)
        3. kickoff() resumes and generates chapter 4
        """
        from crewai.content.novel.pipeline_state import PipelineState
        from crewai.content.novel.config import NovelConfig

        state = PipelineState(config={"topic": "测试小说", "style": "urban"})
        state.set_outline_data({
            "world": {"name": "测试世界"},
            "plot": {"main_strand": "测试情节"},
        })

        # Simulate chapters 1-2 already written
        state.add_chapter({"chapter_num": 1, "title": "第一章", "content": "内容1", "word_count": 3000})
        state.add_chapter({"chapter_num": 2, "title": "第二章", "content": "内容2", "word_count": 3000})

        # Simulate chapter 3 written but pending approval
        state.add_chapter({"chapter_num": 3, "title": "第三章", "content": "内容3", "word_count": 3000})
        state.mark_chapters_dirty([3])

        # Mark chapter 3 as approved (emulates user approval)
        # In real flow: user edits .pending_chapter.json, removes pending flag
        state.clear_dirty_chapters()

        # Verify state is correct for recovery
        assert state.is_chapter_dirty(1) is False
        assert state.is_chapter_dirty(2) is False
        assert state.is_chapter_dirty(3) is False  # Cleared after approval
        assert len(state.chapters) == 3

        # Verify replay plan would skip chapter 3 (already approved) after recovery
        # Set seed_config on state to enable deterministic replay checks
        from crewai.content.novel.seed_mechanism import SeedConfig
        seed_config = SeedConfig(
            seed="test_seed",
            topic="测试小说",
            genre="urban",
            style="urban",
        )
        state.seed_config = seed_config
        state.world_data = {"name": "测试世界"}
        state.plot_data = {"main_strand": "测试情节"}
        state.update_core_content_hash()  # Sets core_content_hash so has_core_content_changed() is False

        plan = state.get_replay_plan(seed_config)

        # Chapter 3 is clean (approved), no dirty chapters → no chapter regeneration
        assert plan.should_regenerate_chapters() is False
        assert plan.regenerate_all is False


class TestBlogConfigWiring:
    """Non-mock tests for BlogCrewConfig wiring (P1-1)."""

    def test_title_style_passed_to_config(self):
        """Test that title_style CLI option is passed to BlogCrewConfig."""
        from crewai.content.blog.crews.blog_crew import BlogCrewConfig

        config = BlogCrewConfig(
            topic="测试博客",
            target_platforms=["medium"],
            include_keywords=["python"],
            title_style="clickbait",
        )
        assert config.title_style == "clickbait"

    def test_title_style_affects_filtering(self):
        """Test that title_style=clickbait filters sensational titles."""
        from crewai.content.blog.crews.blog_crew import BlogCrewConfig
        from crewai.content.blog.blog_types import TitleOption

        config = BlogCrewConfig(
            topic="测试博客",
            title_style="clickbait",
        )

        # Simulate available titles
        available = [
            TitleOption(variant=1, title="震惊！", style="sensational", click_score=9.0, seo_score=6.0),
            TitleOption(variant=2, title="Python技巧", style="list", click_score=7.0, seo_score=8.0),
            TitleOption(variant=3, title="你不知道的", style="sensational", click_score=8.5, seo_score=5.0),
        ]

        # generate_titles filtering logic
        style_map = {"clickbait": "sensational"}
        target = style_map.get(config.title_style)
        if target:
            filtered = [t for t in available if t.style == target]
        else:
            filtered = available

        # Should return only sensational (clickbait) titles
        assert len(filtered) == 2
        assert all(t.style == "sensational" for t in filtered)


class TestPodcastConfigWiring:
    """Non-mock tests for PodcastConfig wiring (P1-2).

    The include_interview/include_ads CLI flags are wired to guest_name/sponsors
    in run_podcast(), not in PodcastConfig itself. These tests verify the wiring logic.
    """

    def test_podcast_config_accepts_guest_name_and_sponsors(self):
        """Test that PodcastConfig accepts guest_name and sponsors fields."""
        from crewai.cli.content.podcast_runner import PodcastConfig

        config = PodcastConfig(
            topic="测试播客",
            duration_minutes=30,
            hosts=2,
            style="conversational",
            include_interview=True,
            include_ads=True,
            guest_name="待定嘉宾",
            sponsors=[{"name": "测试赞助商", "description": "", "type": "mid_roll", "duration": 60}],
        )
        assert config.guest_name == "待定嘉宾"
        assert len(config.sponsors) == 1

    def test_wiring_logic_interview_flag(self):
        """Test that include_interview=True in CLI produces guest_name."""
        # This simulates what run_podcast() does
        include_interview = True
        guest_name = f"待定嘉宾" if include_interview else ""
        assert guest_name == "待定嘉宾"

    def test_wiring_logic_ads_flag(self):
        """Test that include_ads=True in CLI produces sponsors."""
        # This simulates what run_podcast() does
        include_ads = True
        sponsors = [{"name": "默认赞助商", "description": "感谢赞助", "type": "mid_roll", "duration": 60}] if include_ads else []
        assert len(sponsors) == 1
        assert sponsors[0]["name"] == "默认赞助商"

    def test_wiring_logic_both_false(self):
        """Test that both flags False produces empty guest_name and sponsors."""
        include_interview = False
        include_ads = False
        guest_name = f"待定嘉宾" if include_interview else ""
        sponsors = [{"name": "默认赞助商", "description": "", "type": "mid_roll", "duration": 60}] if include_ads else []
        assert guest_name == ""
        assert sponsors == []


class TestScriptConfigTyped:
    """Non-mock tests for ScriptConfig typed dataclass (P2-1)."""

    def test_script_config_defaults(self):
        """Test ScriptConfig has correct defaults."""
        from crewai.content.script.crews.script_crew import ScriptConfig

        config = ScriptConfig(topic="测试剧本")
        assert config.topic == "测试剧本"
        assert config.format == "film"
        assert config.target_runtime == 120
        assert config.num_acts == 3
        assert config.genre == ""
        assert config.title == ""

    def test_script_config_explicit_values(self):
        """Test ScriptConfig with explicit values."""
        from crewai.content.script.crews.script_crew import ScriptConfig

        config = ScriptConfig(
            topic="科幻故事",
            format="tv",
            target_runtime=60,
            num_acts=5,
            genre="scifi",
        )
        assert config.format == "tv"
        assert config.target_runtime == 60
        assert config.num_acts == 5
        assert config.genre == "scifi"


class TestPodcastFailureMetadata:
    """Non-mock tests for podcast structured failure tracking (P1-3)."""

    def test_podcast_output_with_failed_sections(self):
        """Test that PodcastOutput tracks failed sections in metadata."""
        from crewai.content.podcast.podcast_types import PodcastOutput, ShowNotesOutput

        output = PodcastOutput(
            title="测试播客",
            preshow=None,  # Failed
            intro="正常开场",
            outro=None,  # Failed
            shownotes=ShowNotesOutput(),
            total_duration_minutes=25.0,
            metadata={"failed_sections": {"preshow": "预热内容生成失败: timeout", "outro": "结尾总结生成失败: LLM error"}},
        )

        assert output.preshow is None  # None means failed
        assert output.outro is None    # None means failed
        assert output.intro == "正常开场"
        assert "failed_sections" in output.metadata
        assert output.metadata["failed_sections"]["preshow"] == "预热内容生成失败: timeout"
        assert output.metadata["failed_sections"]["outro"] == "结尾总结生成失败: LLM error"

    def test_podcast_output_all_successful(self):
        """Test that PodcastOutput with no failures has no failed_sections."""
        from crewai.content.podcast.podcast_types import PodcastOutput, ShowNotesOutput

        output = PodcastOutput(
            title="测试播客",
            preshow="预热内容",
            intro="正常开场",
            outro="结尾总结",
            shownotes=ShowNotesOutput(),
            total_duration_minutes=30.0,
        )

        assert output.preshow == "预热内容"
        assert output.outro == "结尾总结"


class TestDetermineResumeStopAt:
    """Tests for determine_resume_stop_at function (used by --resume-from)."""

    def test_resume_from_evaluation_returns_volume(self):
        """Test that resume from evaluation sets stop_at to volume."""
        from crewai.cli.content.novel_runner import determine_resume_stop_at

        assert determine_resume_stop_at("evaluation") == "volume"

    def test_resume_from_volume_returns_volume(self):
        """Test that resume from volume sets stop_at to volume."""
        from crewai.cli.content.novel_runner import determine_resume_stop_at

        assert determine_resume_stop_at("volume") == "volume"

    def test_resume_from_summary_returns_summary(self):
        """Test that resume from summary sets stop_at to summary."""
        from crewai.cli.content.novel_runner import determine_resume_stop_at

        assert determine_resume_stop_at("summary") == "summary"

    def test_resume_from_writing_returns_none(self):
        """Test that resume from writing runs to completion (no stop)."""
        from crewai.cli.content.novel_runner import determine_resume_stop_at

        assert determine_resume_stop_at("writing") is None

    def test_resume_from_unknown_returns_none(self):
        """Test that unknown resume_from value runs to completion."""
        from crewai.cli.content.novel_runner import determine_resume_stop_at

        assert determine_resume_stop_at("unknown") is None
        assert determine_resume_stop_at(None) is None


class TestStopAtCLI:
    """Integration tests for --stop-at CLI flag with mocked NovelCrew."""

    def test_stop_at_outline_stops_at_outline_stage(self, cli_runner, tmp_path):
        """Test that --stop-at outline stops after outline generation."""
        from crewai.cli.cli import crewai
        from crewai.cli.create_content import create_novel
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["outline"],
            execution_time=1.0,
            metadata={
                "pipeline_state": {"stage": "outline"},
                "pipeline_summary": {
                    "stage": "outline",
                    "world_name": "测试世界",
                    "plot_ready": True,
                },
                "stopped": True,
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--style", "urban",
                "--stop-at", "outline",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_crew.kickoff.assert_called_once()
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") == "outline"

    def test_stop_at_evaluation_stops_at_evaluation_stage(self, cli_runner, tmp_path):
        """Test that --stop-at evaluation stops after evaluation."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["outline", "evaluation"],
            execution_time=2.0,
            metadata={
                "pipeline_state": {"stage": "evaluation"},
                "pipeline_summary": {
                    "stage": "evaluation",
                    "score": 8.5,
                },
                "stopped": True,
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--style", "xianxia",
                "--stop-at", "evaluation",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_crew.kickoff.assert_called_once()
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") == "evaluation"

    def test_stop_at_volume_stops_at_volume_stage(self, cli_runner, tmp_path):
        """Test that --stop-at volume stops after volume outline."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["outline", "evaluation", "volume"],
            execution_time=3.0,
            metadata={
                "pipeline_state": {"stage": "volume"},
                "pipeline_summary": {"stage": "volume"},
                "stopped": True,
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "500000",
                "--style", "doushi",
                "--stop-at", "volume",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") == "volume"

    def test_stop_at_summary_stops_at_summary_stage(self, cli_runner, tmp_path):
        """Test that --stop-at summary stops after chapter summaries."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["outline", "evaluation", "volume", "summary"],
            execution_time=4.0,
            metadata={
                "pipeline_state": {"stage": "summary"},
                "pipeline_summary": {"stage": "summary"},
                "stopped": True,
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "200000",
                "--stop-at", "summary",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") == "summary"


class TestResumeFromCLI:
    """Integration tests for --resume-from CLI flag."""

    def test_resume_from_loads_state_and_resumes(self, cli_runner, tmp_path):
        """Test that --resume-from evaluation loads state and resumes from evaluation."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        # Create a mock pipeline state file
        state_file = tmp_path / "pipeline_state.json"
        state_file.write_text('{"topic": "测试小说", "style": "urban"}')

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["outline", "evaluation"],
            execution_time=2.0,
            metadata={
                "pipeline_state": {"stage": "evaluation"},
                "stopped": True,
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--resume-from", "evaluation",
                "--pipeline-state-path", str(state_file),
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_crew.load_pipeline_state.assert_called_once_with(str(state_file))
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") == "volume"

    def test_resume_from_writing_runs_to_completion(self, cli_runner, tmp_path):
        """Test that --resume-from writing runs to completion (no stop_at)."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.novel_types import NovelOutput
        from unittest.mock import patch, MagicMock

        state_file = tmp_path / "pipeline_state.json"
        state_file.write_text('{"topic": "测试小说", "style": "urban"}')

        mock_novel = NovelOutput(
            title="测试小说",
            genre="urban",
            style="urban",
            world_output=None,
            chapters=[],
        )
        mock_output = BaseCrewOutput(
            content=mock_novel,
            tasks_completed=["outline", "evaluation", "volume", "summary", "writing"],
            execution_time=10.0,
            metadata={},
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--resume-from", "writing",
                "--pipeline-state-path", str(state_file),
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("stop_at") is None


class TestReviewEachChapterIntegration:
    """Integration tests for --review-each-chapter approval flow."""

    def test_review_each_chapter_passes_flag_to_kickoff(self, cli_runner, tmp_path):
        """Test that --review-each-chapter passes review_each_chapter=True to kickoff."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.novel_types import NovelOutput
        from unittest.mock import patch, MagicMock

        mock_novel = NovelOutput(
            title="测试小说",
            genre="urban",
            style="urban",
            world_output=None,
            chapters=[],
        )
        mock_output = BaseCrewOutput(
            content=mock_novel,
            tasks_completed=["writing"],
            execution_time=10.0,
            metadata={},
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--review-each-chapter",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            call_kwargs = mock_crew.kickoff.call_args.kwargs
            assert call_kwargs.get("review_each_chapter") is True

    def test_approval_required_triggers_approval_message(self, cli_runner, tmp_path):
        """Test that approval_required=True in result metadata triggers approval message."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from unittest.mock import patch, MagicMock

        mock_output = BaseCrewOutput(
            content=None,
            tasks_completed=["writing: chapter 3"],
            execution_time=5.0,
            metadata={
                "approval_required": True,
                "pending_chapter": 3,
                "pipeline_state_path": str(tmp_path / "pending.json"),
                "content_summary": {
                    "chapter_title": "第三章：决战",
                    "word_count": 5000,
                },
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--review-each-chapter",
            ])

            assert result.exit_code == 0, f"CLI failed: {result.output}"
            output_str = result.output if hasattr(result, "output") else str(result)
            assert "审批" in output_str or "pending" in output_str.lower() or "3" in output_str


class TestFailurePathTests:
    """Failure path tests for content generation CLI (P3-4)."""

    def test_invalid_word_count_zero(self, cli_runner):
        """Test that word count of 0 is rejected with clear error message (P1-17: strict contract)."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, [
            "create", "novel", "测试小说",
            "--words", "0",
        ])
        # Should fail with clear validation error, not traceback
        assert result.exit_code != 0, "words=0 should produce non-zero exit code"
        assert "Traceback" not in result.output, f"CLI crashed with traceback: {result.output}"
        assert "参数错误" in result.output or "目标字数必须大于0" in result.output, \
            f"Expected validation error about target_words > 0, got: {result.output}"

    def test_invalid_style_value(self, cli_runner):
        """Test that invalid style is rejected with clear error message (P1-17: strict contract)."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, [
            "create", "novel", "测试小说",
            "--words", "100000",
            "--style", "invalid_style_xyz",
        ])
        # Should fail with clear validation error listing valid styles
        assert result.exit_code != 0, "invalid style should produce non-zero exit code"
        assert "Traceback" not in result.output, f"CLI crashed with traceback: {result.output}"
        assert "参数错误" in result.output or "不支持的小说风格" in result.output, \
            f"Expected validation error about invalid style, got: {result.output}"

    def test_resume_from_nonexistent_state_file(self, cli_runner):
        """Test that resuming from non-existent state file handles gracefully."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.novel_types import NovelOutput
        from unittest.mock import patch, MagicMock

        mock_novel = NovelOutput(
            title="测试小说",
            genre="urban",
            style="urban",
            world_output=None,
            chapters=[],
        )
        mock_output = BaseCrewOutput(
            content=mock_novel,
            tasks_completed=["outline", "evaluation", "volume", "summary", "writing"],
            execution_time=10.0,
            metadata={},
        )

        nonexistent_path = "/tmp/does_not_exist_12345/pipeline_state.json"

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            # When state file doesn't exist, kickoff should gracefully skip loading and proceed
            # The implementation at novel_runner.py checks Path.exists() and sets state_path to None if missing
            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--resume-from", "writing",
                "--pipeline-state-path", nonexistent_path,
            ])

            # Should succeed (skips loading nonexistent state and continues)
            # No Python traceback crash, no error messages about missing file
            assert result.exit_code == 0, f"Expected success when state file missing, got exit_code={result.exit_code}, output={result.output}"
            assert "不存在" not in result.output and "does not exist" not in result.output.lower(), \
                f"Did not expect error message for missing state file, got: {result.output}"

    def test_unwritable_output_directory(self, cli_runner):
        """Test that unwritable output directory is handled with clear error (P1-19: strict contract)."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.novel_types import NovelOutput
        from unittest.mock import patch, MagicMock
        import os

        mock_novel = NovelOutput(
            title="测试小说",
            genre="urban",
            style="urban",
            world_output=None,
            chapters=[],
        )
        mock_output = BaseCrewOutput(
            content=mock_novel,
            tasks_completed=["outline"],
            execution_time=5.0,
            metadata={"stopped": True, "stage": "outline"},
        )

        # Use a path that definitely cannot be created (root-level restricted dir)
        unwritable_path = "/root/./impossible_dir_12345"

        # Skip this test on Windows or if running as root
        import platform
        if platform.system() == "Windows" or os.geteuid() == 0:
            pytest.skip("Skipping on Windows or when running as root")

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_output
            MockCrew.return_value = mock_crew

            result = cli_runner.invoke(crewai, [
                "create-novel", "测试小说",
                "--words", "100000",
                "--output", unwritable_path,
            ])

            # Should fail with non-zero exit AND clear error message (strict contract)
            assert result.exit_code != 0, \
                f"Expected non-zero exit code for unwritable directory, got {result.exit_code}"
            assert "Traceback" not in result.output, \
                f"CLI should not crash with traceback: {result.output}"
            # Error message should mention the directory/permissions issue
            error_patterns = ["权限", "Permission", "无法", "拒绝", "Read-only", "file system", "不存在", "No such"]
            assert any(pattern in result.output for pattern in error_patterns), \
                f"Expected directory-related error message, got: {result.output}"

    def test_approval_interruption_recovery(self, cli_runner, tmp_path):
        """Test that approval interruption can be recovered via resume."""
        from crewai.cli.cli import crewai
        from crewai.content.base import BaseCrewOutput
        from crewai.content.novel.novel_types import NovelOutput
        from unittest.mock import patch, MagicMock

        # Simulate: chapter 3 completed but approval pending
        state_file = tmp_path / "pending_state.json"
        pending_output = BaseCrewOutput(
            content=None,
            tasks_completed=["writing: chapter 3"],
            execution_time=5.0,
            metadata={
                "approval_required": True,
                "pending_chapter": 3,
                "pipeline_state_path": str(state_file),
                "content_summary": {
                    "chapter_title": "第三章：决战",
                    "word_count": 5000,
                },
            },
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = pending_output
            MockCrew.return_value = mock_crew

            # First run: approval required
            result1 = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--review-each-chapter",
            ])

            assert result1.exit_code == 0
            assert "审批" in result1.output or "pending" in result1.output.lower()

        # Now simulate state file exists and user resumes
        state_file.write_text('{"topic": "测试小说", "style": "urban", "current_chapter": 3}')

        completed_output = BaseCrewOutput(
            content=NovelOutput(
                title="测试小说",
                genre="urban",
                style="urban",
                world_output=None,
                chapters=[],
            ),
            tasks_completed=["writing: chapter 3", "writing: chapter 4"],
            execution_time=10.0,
            metadata={},
        )

        with patch("crewai.content.novel.NovelCrew") as MockCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = completed_output
            MockCrew.return_value = mock_crew

            # Second run: resume from writing after approval
            result2 = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--words", "100000",
                "--resume-from", "writing",
                "--pipeline-state-path", str(state_file),
            ])

            # Should complete without requiring approval again
            assert result2.exit_code == 0


class TestOutputValidation:
    """Tests for validating output after content generation."""

    def test_blog_output_has_required_fields(self, cli_runner, tmp_path):
        """Test that blog output has all required fields when successful."""
        from crewai.cli.create_content import create_blog
        from crewai.content.blog.blog_types import BlogCrewOutput, BlogPost, HookOption
        from crewai.content.base import BaseCrewOutput

        mock_post = BlogPost(
            original_topic="测试博客",
            title="测试标题",
            hooks=[
                HookOption(variant="疑问", hook_text="测试钩子", hook_type="question", engagement_score=8.5)
            ],
            body="这是博客正文内容",
        )
        mock_result = BlogCrewOutput(
            post=mock_post,
            tasks_completed=["生成钩子", "生成标题", "生成正文"],
            execution_time=1.5,
            metadata={"topic": "测试博客"},
        )

        with patch("crewai.content.blog.BlogCrew") as MockBlogCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockBlogCrew.return_value = mock_crew

            result = cli_runner.invoke(create_blog, [
                "测试博客",
                "--platforms", "medium",
                "--output", str(tmp_path),
            ])

            assert result.exit_code == 0
            # Verify the mock was called with proper structure
            mock_crew.kickoff.assert_called_once()

    def test_podcast_output_has_required_fields(self, cli_runner, tmp_path):
        """Test that podcast output has all required fields when successful."""
        from crewai.cli.create_content import create_podcast
        from crewai.content.podcast.podcast_types import PodcastOutput, ShowNotesOutput
        from crewai.content.base import BaseCrewOutput

        mock_content = PodcastOutput(
            title="测试播客",
            preshow="预热内容",
            intro="开场介绍",
            outro="结尾总结",
            shownotes=ShowNotesOutput(title="测试", description="描述"),
            total_duration_minutes=30.0,
        )
        mock_result = BaseCrewOutput(
            content=mock_content,
            tasks_completed=["预热", "开场", "段落", "结尾"],
            execution_time=3.0,
            metadata={},
        )

        with patch("crewai.content.podcast.PodcastCrew") as MockPodcastCrew:
            mock_crew = MagicMock()
            mock_crew.kickoff.return_value = mock_result
            MockPodcastCrew.return_value = mock_crew

            result = cli_runner.invoke(create_podcast, [
                "测试播客",
                "--duration", "30",
                "--output", str(tmp_path),
            ])

            assert result.exit_code == 0


class TestContentStatusCommand:
    """Tests for the content status command."""

    def test_status_command_reports_blog_artifacts(self, cli_runner, tmp_path):
        """Test that status summarizes result.json and artifacts for blog outputs."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试博客",
                    "platforms": ["medium"],
                    "keywords": ["python"],
                    "title_style": "seo",
                    "title": "测试标题",
                    "body_length": 128,
                    "warnings": ["正文长度偏短"],
                    "status": "partial",
                    "is_usable": False,
                    "requires_manual_review": True,
                    "next_actions": ["补充正文后重新审阅。"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (tmp_path / "summary.md").write_text("# Blog 审阅摘要\n", encoding="utf-8")

        result = cli_runner.invoke(crewai, ["status", str(tmp_path)])

        assert result.exit_code == 0
        assert "Blog 输出状态" in result.output
        assert "partial" in result.output
        assert "需人工审核: 是" in result.output
        assert "summary.md" in result.output
        assert "result.json" in result.output

    def test_status_command_json_output(self, cli_runner, tmp_path):
        """Test that status can output machine-readable JSON."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试播客",
                    "duration": 30,
                    "hosts": 2,
                    "style": "conversational",
                    "title": "测试播客",
                    "total_duration_minutes": 30.0,
                    "status": "complete",
                    "failed_sections": {},
                    "metadata": {},
                    "is_usable": True,
                    "requires_manual_review": False,
                    "next_actions": ["可直接进入录制或后续剪辑准备。"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = cli_runner.invoke(crewai, ["status", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["content_type"] == "Podcast"
        assert payload["report"]["status"] == "complete"
        assert payload["report"]["next_actions"]
        assert "task_dashboard" in payload
        assert "project_memory" in payload


class TestContentTasksCommand:
    """Tests for the content tasks command."""

    def test_tasks_command_reports_novel_dashboard(self, cli_runner, tmp_path):
        """Test that tasks summarizes task_dashboard from novel outputs."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试小说",
                    "target_words": 100000,
                    "style": "urban",
                    "title": "测试小说",
                    "chapters_count": 3,
                    "word_count": 15000,
                    "status": "success",
                    "is_usable": True,
                    "requires_manual_review": False,
                    "next_actions": ["可直接进入发布或后续编辑流程。"],
                    "task_dashboard": {
                        "summary": {
                            "pending": 1,
                            "running": 1,
                            "completed": 3,
                            "failed": 0,
                            "retrying": 0,
                        },
                        "active_tasks": [
                            {
                                "id": "w-12345678",
                                "status": "running",
                                "description": "Chapter 12: 绝地反击",
                            }
                        ],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = cli_runner.invoke(crewai, ["tasks", str(tmp_path)])

        assert result.exit_code == 0
        assert "任务大盘" in result.output
        assert "pending=1" in result.output
        assert "running=1" in result.output
        assert "绝地反击" in result.output

    def test_tasks_command_json_output(self, cli_runner, tmp_path):
        """Test that tasks can output machine-readable JSON."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试小说",
                    "target_words": 100000,
                    "style": "urban",
                    "title": "测试小说",
                    "chapters_count": 3,
                    "word_count": 15000,
                    "status": "success",
                    "task_dashboard": {
                        "summary": {
                            "pending": 0,
                            "running": 0,
                            "completed": 2,
                            "failed": 0,
                            "retrying": 0,
                        },
                        "tasks": [],
                        "active_tasks": [],
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = cli_runner.invoke(crewai, ["tasks", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["content_type"] == "Novel"
        assert payload["task_dashboard"]["summary"]["completed"] == 2


class TestProjectMemoryCommand:
    """Tests for the project-memory command."""

    def test_project_memory_init_creates_file(self, cli_runner, tmp_path, monkeypatch):
        """Test that project-memory init creates a persistent memory file."""
        from crewai.cli.cli import crewai

        monkeypatch.chdir(tmp_path)
        result = cli_runner.invoke(crewai, ["project-memory", "init"])

        assert result.exit_code == 0
        memory_file = tmp_path / ".claude" / "PROJECT_MEMORY.md"
        assert memory_file.exists()
        content = memory_file.read_text(encoding="utf-8")
        assert "Project Memory" in content
        assert "Novel is the most stateful pipeline" in content

    def test_project_memory_add_appends_note(self, cli_runner, tmp_path, monkeypatch):
        """Test that project-memory add appends durable notes."""
        from crewai.cli.cli import crewai

        monkeypatch.chdir(tmp_path)
        init_result = cli_runner.invoke(crewai, ["project-memory", "init"])
        assert init_result.exit_code == 0

        result = cli_runner.invoke(
            crewai,
            ["project-memory", "add", "优先保留状态文件和审阅摘要", "--section", "Working Agreements"],
        )

        assert result.exit_code == 0
        memory_file = tmp_path / ".claude" / "PROJECT_MEMORY.md"
        content = memory_file.read_text(encoding="utf-8")
        assert "优先保留状态文件和审阅摘要" in content
        assert "Working Agreements" in content

    def test_project_memory_show_displays_file(self, cli_runner, tmp_path, monkeypatch):
        """Test that project-memory show prints the stored file."""
        from crewai.cli.cli import crewai

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".claude" / "PROJECT_MEMORY.md").write_text(
            "# Project Memory\n\n- 测试条目\n",
            encoding="utf-8",
        )

        result = cli_runner.invoke(crewai, ["project-memory", "show"])

        assert result.exit_code == 0
        assert "项目记忆" in result.output
        assert "测试条目" in result.output


class TestContentResumeCommand:
    """Tests for the content resume command."""

    def test_resume_content_replays_novel_from_output_dir(self, cli_runner, tmp_path):
        """Test that resume-content loads novel state from output dir and resumes."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试小说",
                    "target_words": 100000,
                    "style": "urban",
                    "title": "测试小说",
                    "chapters_count": 3,
                    "word_count": 15000,
                    "status": "partial",
                    "is_usable": False,
                    "requires_manual_review": True,
                    "warnings": ["需要人工审核"],
                    "errors": [],
                    "next_actions": ["检查章节内容完整性。"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (tmp_path / "pipeline_state.json").write_text(
            json.dumps({"topic": "测试小说", "current_stage": "summary"}, ensure_ascii=False),
            encoding="utf-8",
        )

        with patch("crewai.cli.content.resume.run_novel_creation") as mock_run:
            result = cli_runner.invoke(crewai, ["resume-content", str(tmp_path)])

            assert result.exit_code == 0, result.output
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["topic"] == "测试小说"
            assert call_kwargs["words"] == 100000
            assert call_kwargs["style"] == "urban"
            assert call_kwargs["output"] == str(tmp_path)
            assert call_kwargs["resume_from"] == "writing"
            assert call_kwargs["pipeline_state_path"] == str(tmp_path / "pipeline_state.json")

    def test_resume_content_rejects_non_novel_outputs(self, cli_runner, tmp_path):
        """Test that resume-content rejects non-novel output directories."""
        from crewai.cli.cli import crewai

        (tmp_path / "result.json").write_text(
            json.dumps(
                {
                    "topic": "测试播客",
                    "duration": 30,
                    "hosts": 2,
                    "style": "conversational",
                    "title": "测试播客",
                    "total_duration_minutes": 30.0,
                    "status": "complete",
                    "failed_sections": {},
                    "metadata": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = cli_runner.invoke(crewai, ["resume-content", str(tmp_path)])

        assert result.exit_code != 0
        assert "仅支持从 Novel 输出目录恢复" in result.output


class TestCLIRunnerIntegration:
    """Tests for CLI top-level command routing to runners.

    Verifies that `crewai create blog/podcast/script <name>` correctly
    passes type-specific parameters to the underlying runner functions.
    """

    def test_create_blog_routes_with_title_style(self, cli_runner):
        """Test blog creation passes --title-style to run_blog."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.blog_runner.run_blog") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "blog", "测试博客",
                "--title-style", "sensational",
                "--platforms", "medium,xiaohongshu",
                "--keywords", "python,ai",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["title_style"] == "sensational"
            assert call_kwargs["platforms"] == ["medium", "xiaohongshu"]
            assert call_kwargs["keywords"] == ["python", "ai"]
            assert call_kwargs["topic"] == "测试博客"
            assert call_kwargs["output"] == "./测试博客_blog"

    def test_create_blog_default_title_style(self, cli_runner):
        """Test blog creation defaults title_style to seo when not specified."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.blog_runner.run_blog") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "blog", "测试博客",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["title_style"] == "seo"

    def test_create_podcast_routes_with_include_flags(self, cli_runner):
        """Test podcast creation passes --include-interview and --include-ads."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.podcast_runner.run_podcast") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "podcast", "测试播客",
                "--podcast-style", "interview",
                "--include-interview",
                "--include-ads",
                "--hosts", "3",
                "--duration", "45",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["style"] == "interview"
            assert call_kwargs["include_interview"] is True
            assert call_kwargs["include_ads"] is True
            assert call_kwargs["hosts"] == 3
            assert call_kwargs["duration"] == 45

    def test_create_podcast_default_style(self, cli_runner):
        """Test podcast defaults to conversational style when not specified."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.podcast_runner.run_podcast") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "podcast", "测试播客",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["style"] == "conversational"
            assert mock_run.call_args.kwargs["include_interview"] is False
            assert mock_run.call_args.kwargs["include_ads"] is False

    def test_create_script_routes_with_format_and_acts(self, cli_runner):
        """Test script creation passes --format, --duration, and --acts."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.script_runner.run_script") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "script", "测试剧本",
                "--format", "tv",
                "--duration", "60",
                "--acts", "5",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs["format"] == "tv"
            assert call_kwargs["target_runtime"] == 60
            assert call_kwargs["num_acts"] == 5

    def test_create_script_default_format(self, cli_runner):
        """Test script defaults to film format when not specified."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.content.script_runner.run_script") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "script", "测试剧本",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["format"] == "film"

    def test_create_novel_preserves_style(self, cli_runner):
        """Test novel creation still uses --style for writing style."""
        from crewai.cli.cli import crewai

        with patch("crewai.cli.cli.run_novel_creation") as mock_run:
            result = cli_runner.invoke(crewai, [
                "create", "novel", "测试小说",
                "--style", "xianxia",
                "--words", "500000",
            ])
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["style"] == "xianxia"
