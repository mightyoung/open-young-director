"""Tests for NovelCrew state persistence helpers."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from crewai.content.novel.crews.novel_crew import NovelCrew


def _make_crew(config: dict[str, str], output_dir: str = "/tmp/novel-output") -> NovelCrew:
    crew = NovelCrew.__new__(NovelCrew)
    crew.config = config
    crew._pipeline_state = SimpleNamespace(save=MagicMock())
    crew._checkpoint_manager = SimpleNamespace(output_dir=output_dir)
    return crew


def test_save_pipeline_state_snapshot_uses_explicit_path() -> None:
    crew = _make_crew({"pipeline_state_path": "/tmp/custom-state.json"})

    path = NovelCrew._save_pipeline_state_snapshot(crew)

    assert path == "/tmp/custom-state.json"
    crew.pipeline_state.save.assert_called_once_with("/tmp/custom-state.json")


def test_save_pipeline_state_snapshot_defaults_to_output_dir() -> None:
    crew = _make_crew({}, output_dir="/tmp/novel-output")

    path = NovelCrew._save_pipeline_state_snapshot(crew)

    assert path == str(Path("/tmp/novel-output") / "pipeline_state.json")
    crew.pipeline_state.save.assert_called_once_with(
        str(Path("/tmp/novel-output") / "pipeline_state.json")
    )
