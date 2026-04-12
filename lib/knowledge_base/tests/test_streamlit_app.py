"""Tests for Streamlit helper functions."""

from pathlib import Path
from unittest.mock import MagicMock

from services.run_storage import update_status
import streamlit_app


def test_run_monitor_payload_handles_missing_run():
    payload = streamlit_app._run_monitor_payload(None)

    assert payload["status"] == {}
    assert payload["stdout"] == ""
    assert payload["stderr"] == ""
    assert payload["is_active"] is False


def test_run_monitor_payload_reads_status_and_logs(temp_project_dir):
    project_dir = temp_project_dir / "project"
    run_dir = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate", "2"],
    )
    update_status(
        run_dir,
        status="running",
        current_stage="chapter.generate",
        current_step="第 1 章正文生成",
        chapters_total=2,
        chapters_completed=1,
        eta_seconds=42,
    )
    (run_dir / "stdout.log").write_text("stdout content", encoding="utf-8")
    (run_dir / "stderr.log").write_text("stderr content", encoding="utf-8")

    payload = streamlit_app._run_monitor_payload(run_dir)

    assert payload["status"]["status"] == "running"
    assert payload["stdout"] == "stdout content"
    assert payload["stderr"] == "stderr content"
    assert payload["is_active"] is True


def test_project_root_and_runs_root_follow_config_manager(mock_config_manager, monkeypatch):
    project = mock_config_manager.create_project(
        title="demo",
        author="tester",
        genre="玄幻",
        outline="",
    )
    project_dir = Path(mock_config_manager.root_dir) / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = project
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    assert streamlit_app._project_root() == project_dir
    assert streamlit_app._runs_root() == project_dir / "runs"


def test_run_full_novel_action_initializes_run_and_launches_cli(mock_config_manager, monkeypatch, temp_project_dir):
    project = mock_config_manager.create_project(
        title="demo",
        author="tester",
        genre="玄幻",
        outline="outline",
    )
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = project
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    launched = {}

    def fake_popen(cmd, cwd, stdout, stderr, text):
        launched["cmd"] = cmd
        launched["cwd"] = cwd
        return MagicMock()

    monkeypatch.setattr(streamlit_app.subprocess, "Popen", fake_popen)

    result = streamlit_app.run_full_novel_action(60, "outline+volume", False)
    run_dir = Path(result["run_dir"])

    assert run_dir.exists()
    assert (run_dir / "status.json").exists()
    assert "--generate-full" in launched["cmd"]
    assert "--run-id" in launched["cmd"]
    assert "--run-dir" in launched["cmd"]


def test_pending_review_payload_reads_pending_file(temp_project_dir):
    run_dir = streamlit_app.create_run(
        project_dir=temp_project_dir / "project",
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    pending_path = run_dir / "pending.json"
    pending_path.write_text(
        '{"checkpoint_type":"outline_review","review_payload":{"outline":"demo"}}',
        encoding="utf-8",
    )
    update_status(run_dir, status="paused", pending_state_path=str(pending_path), pause_reason="outline_review")

    payload = streamlit_app._pending_review_payload(run_dir)

    assert payload["checkpoint_type"] == "outline_review"
    assert payload["review_payload"]["outline"] == "demo"
    assert payload["pending_state_path"] == str(pending_path)
