"""Tests for longform pause/resume state helpers."""

from pathlib import Path

from services.longform_run import (
    CHECKPOINT_OUTLINE,
    STAGE_OUTLINE_REVIEW,
    approval_payload_from_input,
    clear_pause,
    initial_longform_state,
    load_longform_state,
    record_pause,
)


class _Project:
    def __init__(self):
        self.id = "project-123"
        self.title = "demo"
        self.total_chapters = 120
        self.current_chapter = 0
        self.outline = "outline"
        self.world_setting = "world"
        self.character_intro = "characters"


def test_initial_longform_state_creates_volume_plan(temp_project_dir):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)

    state = initial_longform_state(
        project=_Project(),
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    assert state["run_id"] == "run-001"
    assert state["total_volumes"] == 2
    assert state["current_volume"] == 1
    assert state["current_volume_start_chapter"] == 1
    assert state["current_volume_end_chapter"] == 60
    assert Path(state["longform_state_path"]).exists()


def test_record_pause_writes_pending_state_and_clear_pause_resets_it(temp_project_dir):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    state = initial_longform_state(
        project=_Project(),
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_OUTLINE,
        current_stage=STAGE_OUTLINE_REVIEW,
        review_payload={"outline": "outline"},
    )

    assert paused["status"] == "paused"
    assert paused["current_checkpoint"] == CHECKPOINT_OUTLINE
    assert paused["pending_state_path"]
    assert Path(paused["pending_state_path"]).exists()

    resumed = clear_pause(run_dir, paused)
    assert resumed["status"] == "running"
    assert resumed["pending_state_path"] is None

    reloaded = load_longform_state(run_dir)
    assert reloaded["status"] == "running"


def test_approval_payload_from_file_and_inline_json(temp_project_dir):
    payload_path = temp_project_dir / "payload.json"
    payload_path.write_text('{"outline": "revised"}', encoding="utf-8")

    from_file = approval_payload_from_input(str(payload_path))
    inline = approval_payload_from_input('{"world_setting": "new"}')
    fallback = approval_payload_from_input("plain note")

    assert from_file["outline"] == "revised"
    assert inline["world_setting"] == "new"
    assert fallback["note"] == "plain note"
