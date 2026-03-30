"""CLI smoke tests for content generation."""
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
        # script/blog/podcast should NOT appear in help
        assert "script" not in result.output
        assert "blog" not in result.output
        assert "podcast" not in result.output

    def test_create_type_choice_validation(self, cli_runner):
        """Test that invalid types are rejected."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "invalid_type", "test"])
        assert result.exit_code != 0
        assert "Invalid value for \"TYPE\"" in result.output

    def test_create_novel_shows_novel_options(self, cli_runner):
        """Test that novel-specific options are visible."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "novel", "--help"])
        assert result.exit_code == 0
        assert "--words" in result.output
        assert "--chapters" in result.output
        assert "--stop-at" in result.output
        assert "--resume-from" in result.output


class TestExperimentalTypes:
    """Tests for experimental content types (hidden from CLI)."""

    def test_script_not_in_choice(self, cli_runner):
        """Test that script is not available as a choice."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "script", "--help"])
        # Should fail because script is not a valid choice
        assert result.exit_code != 0

    def test_blog_not_in_choice(self, cli_runner):
        """Test that blog is not available as a choice."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "blog", "--help"])
        assert result.exit_code != 0

    def test_podcast_not_in_choice(self, cli_runner):
        """Test that podcast is not available as a choice."""
        from crewai.cli.cli import crewai

        result = cli_runner.invoke(crewai, ["create", "podcast", "--help"])
        assert result.exit_code != 0
