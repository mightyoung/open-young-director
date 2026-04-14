"""Tests for file-backed run telemetry storage."""

from services.run_storage import (
    create_run,
    ensure_run_initialized,
    format_eta,
    latest_run_dir,
    read_log_tail,
    read_status,
    run_dir_for,
    update_status,
)


def test_create_run_initializes_status_and_logs(temp_project_dir):
    project_dir = temp_project_dir / "project"
    run_dir = create_run(project_dir=project_dir, run_id="run-001", project_id="project-123", command=["--generate", "2"])

    assert run_dir == run_dir_for(project_dir, "run-001")
    status = read_status(run_dir)
    assert status["run_id"] == "run-001"
    assert status["project_id"] == "project-123"
    assert status["status"] == "queued"
    assert (run_dir / "stdout.log").exists()
    assert (run_dir / "stderr.log").exists()


def test_update_status_merges_existing_payload(temp_project_dir):
    project_dir = temp_project_dir / "project"
    run_dir = create_run(project_dir=project_dir, run_id="run-001", project_id="project-123")

    update_status(run_dir, status="running", chapters_total=4, chapters_completed=1, current_stage="chapter.generate")

    status = read_status(run_dir)
    assert status["status"] == "running"
    assert status["chapters_total"] == 4
    assert status["chapters_completed"] == 1
    assert status["current_stage"] == "chapter.generate"


def test_read_log_tail_and_latest_run_dir(temp_project_dir):
    project_dir = temp_project_dir / "project"
    create_run(project_dir=project_dir, run_id="run-001", project_id="project-123")
    second_run = create_run(project_dir=project_dir, run_id="run-002", project_id="project-123")

    (second_run / "stdout.log").write_text("line-1\nline-2\nline-3", encoding="utf-8")

    assert read_log_tail(second_run, "stdout", max_chars=8) == "2\nline-3"
    assert latest_run_dir(project_dir) == second_run


def test_format_eta_is_human_readable():
    assert format_eta(None) == "计算中"
    assert format_eta(9) == "9s"
    assert format_eta(75) == "1m 15s"
    assert format_eta(3700) == "1h 01m"


def test_ensure_run_initialized_backfills_missing_status(temp_project_dir):
    run_dir = temp_project_dir / "project" / "runs" / "cli-run"

    ensure_run_initialized(
        run_dir,
        run_id="cli-run",
        project_id="project-123",
        command=["--generate", "2"],
    )

    status = read_status(run_dir)
    assert status["run_id"] == "cli-run"
    assert status["project_id"] == "project-123"
    assert status["command"] == ["--generate", "2"]
    assert status["status"] == "queued"
    assert (run_dir / "stdout.log").exists()
    assert (run_dir / "stderr.log").exists()
