"""Tests for Streamlit helper functions."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import run_novel_generation
from services.longform_run import CHECKPOINT_CHAPTER, STAGE_CHAPTER_REVIEW, approval_history_summary, initial_longform_state, record_pause
from services.longform_run import CHECKPOINT_OUTLINE
from services.run_storage import read_status
from services.run_storage import update_status
import streamlit_app


def _configure_streamlit_longform_env(temp_project_dir, mock_config_manager, monkeypatch, *, current_chapter: int):
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="demo",
        total_chapters=120,
        current_chapter=current_chapter,
        outline="outline",
        world_setting="world",
        character_intro="characters",
    )
    mock_config_manager.current_project = project
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    return project_dir, project


def _create_longform_run_with_state(project_dir: Path, project: SimpleNamespace, *, current_chapter: int):
    run_dir = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    state["chapters_completed"] = current_chapter
    return run_dir, state


def _assert_approval_history_visible(run_dir: Path, status: dict, expected_latest: str, expected_entries: list[str]):
    preview = streamlit_app._recent_run_preview(run_dir.name)
    sections = dict(streamlit_app._longform_control_panel_sections(status))

    assert expected_latest in preview["latest_approval"]
    for entry in expected_entries:
        assert entry in preview["approval_history"]
        assert entry in sections["审批轨迹"]


class _PressedColumn:
    def __init__(self, pressed_key: str):
        self._pressed_key = pressed_key

    def button(self, _label, **kwargs):
        return kwargs.get("key") == self._pressed_key


class _DummyExpander:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _PendingReviewFakeStreamlit:
    def __init__(
        self,
        *,
        pressed_key: str,
        text_area_values: dict[str, str] | None = None,
        text_input_values: dict[str, str] | None = None,
        column_count: int = 3,
        use_expander: bool = False,
        launched: dict | None = None,
    ):
        self.session_state = {}
        self._pressed_key = pressed_key
        self._text_area_values = text_area_values or {}
        self._text_input_values = text_input_values or {}
        self._column_count = column_count
        self._use_expander = use_expander
        self._launched = launched if launched is not None else {}

    def markdown(self, *_args, **_kwargs):
        return None

    def caption(self, *_args, **_kwargs):
        return None

    def info(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    def code(self, *_args, **_kwargs):
        return None

    def text_area(self, label, **_kwargs):
        return self._text_area_values[label]

    def text_input(self, label, **_kwargs):
        return self._text_input_values[label]

    def columns(self, count):
        assert count == self._column_count
        return [_PressedColumn(self._pressed_key) for _ in range(count)]

    def expander(self, *_args, **_kwargs):
        if not self._use_expander:
            raise AssertionError("unexpected expander usage")
        return _DummyExpander()

    def rerun(self):
        self._launched["rerun"] = True


def _install_pending_review_resume_capture(monkeypatch, launched: dict):
    def _fake_resume(_run_dir, pending_state_path, action, payload):
        launched["call"] = {
            "pending_state_path": pending_state_path,
            "action": action,
            "payload": payload,
        }
        return {"message": "ok"}

    monkeypatch.setattr(streamlit_app, "resume_longform_action", _fake_resume)


class _StatusMetricColumn:
    def metric(self, *_args, **_kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _StatusSummaryFakeStreamlit:
    def __init__(self, *, allow_caption: bool = True):
        self.warnings = []
        self.infos = []
        self.markdowns = []
        self.codes = []
        self.captions = []
        self._allow_caption = allow_caption

    def columns(self, count):
        return [_StatusMetricColumn() for _ in range(count)]

    def progress(self, *_args, **_kwargs):
        return None

    def warning(self, message, **_kwargs):
        self.warnings.append(message)

    def info(self, message, **_kwargs):
        self.infos.append(message)

    def markdown(self, message, **_kwargs):
        self.markdowns.append(message)

    def code(self, body, **_kwargs):
        self.codes.append(body)

    def caption(self, message, **_kwargs):
        if self._allow_caption:
            self.captions.append(message)
        return None

    def error(self, *_args, **_kwargs):
        raise AssertionError("unexpected error state")

    def success(self, *_args, **_kwargs):
        raise AssertionError("unexpected success state")


class _RunMonitorFakeStreamlit:
    def __init__(self):
        self.text_area_calls = []

    def markdown(self, *_args, **_kwargs):
        return None

    def button(self, *_args, **_kwargs):
        return False

    def rerun(self):
        return None

    def fragment(self, **_kwargs):
        def _decorator(func):
            return func

        return _decorator

    def text_area(self, label, value, height, **kwargs):
        self.text_area_calls.append({"label": label, "value": value, "height": height, "kwargs": kwargs})
        return None


def test_run_monitor_payload_handles_missing_run():
    payload = streamlit_app._run_monitor_payload(None)

    assert payload["status"] == {}
    assert payload["stdout"] == ""
    assert payload["stderr"] == ""
    assert payload["is_active"] is False
    assert payload["queued_volume_guidance"] == ""


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
        queued_volume_guidance="- 必须回收的伏笔/问题: 回收第一卷伏笔",
    )
    (run_dir / "stdout.log").write_text("stdout content", encoding="utf-8")
    (run_dir / "stderr.log").write_text("stderr content", encoding="utf-8")

    payload = streamlit_app._run_monitor_payload(run_dir)

    assert payload["status"]["status"] == "running"
    assert payload["stdout"] == "stdout content"
    assert payload["stderr"] == "stderr content"
    assert payload["is_active"] is True
    assert payload["queued_volume_guidance"] == "- 必须回收的伏笔/问题: 回收第一卷伏笔"


def test_recent_run_rows_include_guidance_headline(temp_project_dir, mock_config_manager, monkeypatch):
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = MagicMock(id="project-123", title="demo")
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    first = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    second = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-002",
        project_id="project-123",
        command=["--generate-full"],
    )
    (first / "longform_state.v1.json").write_text(
        json.dumps(
            {
                "approval_history": [
                    {
                        "checkpoint_type": "volume_review",
                        "action": "approve",
                        "payload": {"must_recover": "回收第一卷伏笔"},
                        "submitted_at": "2026-04-21T11:20:00",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    update_status(
        first,
        status="paused",
        current_stage="volume.review",
        chapters_total=120,
        chapters_completed=60,
        queued_volume_guidance="- 必须回收的伏笔/问题: 回收第一卷伏笔\n- 明确避免的方向: 不要新增支线角色",
        longform_state_path=str(first / "longform_state.v1.json"),
    )
    update_status(
        second,
        status="running",
        current_stage="volume.write",
        chapters_total=120,
        chapters_completed=61,
    )

    rows = streamlit_app._recent_run_rows(limit=2)

    assert len(rows) == 2
    assert rows[0][1] == "run-002"
    assert rows[0][2] == "运行中"
    assert rows[0][3] == "分卷写作"
    assert rows[1][1] == "run-001"
    assert rows[1][2] == "已暂停"
    assert rows[1][3] == "分卷审批"
    assert rows[1][5] == "- 必须回收的伏笔/问题: 回收第一卷伏笔"
    assert rows[1][6] == "- 2026-04-21 11:20 分卷审批 -> 批准"


def test_recent_run_rows_marks_active_run(temp_project_dir, mock_config_manager, monkeypatch):
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = MagicMock(id="project-123", title="demo")
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)
    monkeypatch.setattr(streamlit_app, "_active_run_id_from_state", lambda: "run-001")

    first = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    second = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-002",
        project_id="project-123",
        command=["--generate-full"],
    )
    update_status(first, status="paused")
    update_status(second, status="running")

    rows = streamlit_app._recent_run_rows(limit=2)

    marked = [row for row in rows if row[0] == "当前"]
    assert len(marked) == 1
    assert marked[0][1] == "run-001"


def test_switch_active_run_action_returns_selected_run(temp_project_dir, mock_config_manager, monkeypatch):
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = MagicMock(id="project-123", title="demo")
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )

    result = streamlit_app.switch_active_run_action("run-001")

    assert result["run_id"] == "run-001"
    assert result["run_dir"].endswith("/run-001")
    assert "已切换到运行任务" in result["message"]


def test_recent_run_preview_reads_selected_run_logs(temp_project_dir, mock_config_manager, monkeypatch):
    project_dir = temp_project_dir / "novels" / "demo_project"
    project_dir.mkdir(parents=True, exist_ok=True)
    mock_config_manager.current_project = MagicMock(id="project-123", title="demo")
    mock_config_manager.generation.output_dir = str(project_dir)
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    run_dir = streamlit_app.create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    (run_dir / "longform_state.v1.json").write_text(
        json.dumps(
            {
                "approval_history": [
                    {
                        "checkpoint_type": "outline_review",
                        "action": "approve",
                        "payload": {},
                        "submitted_at": "2026-04-21T09:00:00",
                    },
                    {
                        "checkpoint_type": "chapter_review",
                        "action": "revise",
                        "payload": {
                            "notes": "先把祖地防线的实际行动补出来。",
                            "chapter_rewrite_plan": {"operations": [{"action": "rebuild_goal_lock_chain"}]},
                        },
                        "submitted_at": "2026-04-21T10:15:00",
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    update_status(
        run_dir,
        status="paused",
        pause_reason="volume_review",
        pending_state_path=str(run_dir / "pending.json"),
        longform_state_path=str(run_dir / "longform_state.v1.json"),
    )
    (run_dir / "stdout.log").write_text("stdout preview", encoding="utf-8")
    (run_dir / "stderr.log").write_text("stderr preview", encoding="utf-8")

    preview = streamlit_app._recent_run_preview("run-001")

    assert preview["run_dir"].endswith("/run-001")
    assert preview["stdout"] == "stdout preview"
    assert preview["stderr"] == "stderr preview"
    assert preview["status"] == "已暂停"
    assert preview["pause_reason"] == "分卷审批"
    assert preview["has_pending_review"] is True
    assert "章节复核 -> 修订" in preview["latest_approval"]
    assert "大纲审批 -> 批准" in preview["approval_history"]
    assert "章节复核 -> 修订" in preview["approval_history"]


def test_streamlit_helpers_read_approval_history_written_by_resume_flow(temp_project_dir, mock_config_manager, monkeypatch):
    project_dir, project = _configure_streamlit_longform_env(
        temp_project_dir,
        mock_config_manager,
        monkeypatch,
        current_chapter=3,
    )
    run_dir, state = _create_longform_run_with_state(project_dir, project, current_chapter=3)
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={
            "chapter_number": 4,
            "title": "第四章",
            "summary": "目标锁假继承，正文掉锚。",
            "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
            "rewrite_plan": {
                "schema_version": "rewrite_plan.v2",
                "strategy": "targeted_patch",
                "operations": [
                    {
                        "phase": "body",
                        "action": "rebuild_goal_lock_chain",
                        "target": "goal_lock_progression",
                        "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                    }
                ],
            },
        },
    )

    def _unexpected_continue(*_args, **_kwargs):
        raise AssertionError("reject 分支不应继续长篇生成")

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

    reject_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="reject",
        approval_payload=json.dumps(
            {
                "chapter_rewrite_plan": {
                    "schema_version": "rewrite_plan.v2",
                    "strategy": "targeted_patch",
                    "operations": [{"phase": "body", "action": "rebuild_goal_lock_chain"}],
                },
                "notes": "先不要继续，等人工确认祖地防线怎么接。",
            },
            ensure_ascii=False,
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(reject_args) == 0

    captured = {}

    def _capture_continue(_args, *, state, run_dir, run_started_at):
        captured["state"] = dict(state)
        return 91

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_continue)

    revise_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="revise",
        approval_payload=json.dumps(
            {
                "chapter_rewrite_plan": {
                    "schema_version": "rewrite_plan.v2",
                    "strategy": "targeted_patch",
                    "operations": [
                        {
                            "phase": "body",
                            "action": "rebuild_goal_lock_chain",
                            "target": "goal_lock_progression",
                            "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                        }
                    ],
                },
                "notes": "现在继续，先把祖地防线的实际行动补出来。",
            },
            ensure_ascii=False,
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(revise_args) == 91

    status = read_status(run_dir)
    assert captured["state"]["approval_history"][0]["action"] == "reject"
    assert captured["state"]["approval_history"][1]["action"] == "revise"
    _assert_approval_history_visible(
        run_dir,
        status,
        "章节复核 -> 修订",
        ["章节复核 -> 拒绝", "章节复核 -> 修订"],
    )


def test_streamlit_helpers_read_risk_review_approval_history_written_by_resume_flow(
    temp_project_dir,
    mock_config_manager,
    monkeypatch,
):
    project_dir, project = _configure_streamlit_longform_env(
        temp_project_dir,
        mock_config_manager,
        monkeypatch,
        current_chapter=60,
    )
    run_dir, state = _create_longform_run_with_state(project_dir, project, current_chapter=60)
    state["current_volume"] = 1
    state["risk_report_path"] = str(run_dir / "risk_report.json")
    run_novel_generation.save_longform_state(run_dir, state)

    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type="risk_review",
        current_stage="risk.pause",
        review_payload={
            "volume_index": 1,
            "summary": "第 1 卷风险较高，需要人工确认。",
            "risk_level": "high",
        },
    )

    def _unexpected_continue(*_args, **_kwargs):
        raise AssertionError("risk reject 分支不应继续长篇生成")

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

    reject_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="reject",
        approval_payload=json.dumps({"notes": "先不要继续，风险点还没处理完。"}, ensure_ascii=False),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(reject_args) == 0

    status = read_status(run_dir)
    assert streamlit_app._recent_run_preview("run-001")["status"] == "已暂停"
    _assert_approval_history_visible(run_dir, status, "风险复核 -> 拒绝", ["风险复核 -> 拒绝"])


def test_streamlit_helpers_read_volume_review_approval_history_written_by_resume_flow(
    temp_project_dir,
    mock_config_manager,
    monkeypatch,
):
    project_dir, project = _configure_streamlit_longform_env(
        temp_project_dir,
        mock_config_manager,
        monkeypatch,
        current_chapter=60,
    )
    run_dir, state = _create_longform_run_with_state(project_dir, project, current_chapter=60)
    state["current_volume"] = 1
    state["current_volume_start_chapter"] = 1
    state["current_volume_end_chapter"] = 60
    state["cross_volume_registry"] = {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["回收第一卷宗门裂痕"],
        "dangling_settings": [],
    }
    run_novel_generation.save_longform_state(run_dir, state)

    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type="volume_review",
        current_stage="volume.review",
        review_payload={"volume_index": 1, "summary": "第 1 卷已完成，等待下一卷指令。"},
    )

    captured = {}

    def _capture_continue(_args, *, state, run_dir, run_started_at):
        captured["state"] = dict(state)
        return 92

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_continue)

    approve_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload=json.dumps(
            {
                "must_recover": "回收第一卷宗门裂痕",
                "relationship_focus": "强化主角与师尊的决裂后果",
                "unresolved_goals": ["守住宗门祖地", "追回失落阵眼"],
                "open_promises": ["回收第一卷宗门裂痕"],
                "dangling_settings": [],
            },
            ensure_ascii=False,
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(approve_args) == 92

    status = read_status(run_dir)
    assert captured["state"]["approval_history"][0]["action"] == "approve"
    _assert_approval_history_visible(run_dir, status, "分卷审批 -> 批准", ["分卷审批 -> 批准"])


def test_streamlit_helpers_read_outline_review_approval_history_written_by_resume_flow(
    temp_project_dir,
    mock_config_manager,
    monkeypatch,
):
    project_dir, project = _configure_streamlit_longform_env(
        temp_project_dir,
        mock_config_manager,
        monkeypatch,
        current_chapter=0,
    )
    run_dir, state = _create_longform_run_with_state(project_dir, project, current_chapter=0)

    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_OUTLINE,
        current_stage="outline.review",
        review_payload={
            "outline": "outline",
            "world_setting": "world",
            "character_intro": "characters",
        },
    )

    def _unexpected_continue(*_args, **_kwargs):
        raise AssertionError("outline reject 分支不应继续长篇生成")

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

    reject_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="reject",
        approval_payload=json.dumps({"notes": "先不要继续，等大纲修完再说。"}, ensure_ascii=False),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(reject_args) == 0

    captured = {}

    def _capture_continue(_args, *, state, run_dir, run_started_at):
        captured["state"] = dict(state)
        return 93

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_continue)

    revise_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="revise",
        approval_payload=json.dumps(
            {
                "outline": "新大纲：先守祖地，再追回失落阵眼。",
                "world_setting": "新世界观：祖地与秘境共振。",
                "character_intro": "新人设：主角与师尊彻底决裂。",
            },
            ensure_ascii=False,
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    assert run_novel_generation.cmd_generate_full(revise_args) == 93

    status = read_status(run_dir)
    assert captured["state"]["approval_history"][0]["action"] == "reject"
    assert captured["state"]["approval_history"][1]["action"] == "revise"
    _assert_approval_history_visible(
        run_dir,
        status,
        "大纲审批 -> 修订",
        ["大纲审批 -> 拒绝", "大纲审批 -> 修订"],
    )


def test_pause_reason_label_maps_known_values():
    assert streamlit_app._pause_reason_label("outline_review") == "大纲审批"
    assert streamlit_app._pause_reason_label("volume_review") == "分卷审批"
    assert streamlit_app._pause_reason_label("risk_review") == "风险复核"
    assert streamlit_app._pause_reason_label("chapter_review") == "章节复核"


def test_run_status_and_stage_label_maps_known_values():
    assert streamlit_app._run_status_label("queued") == "排队中"
    assert streamlit_app._run_status_label("running") == "运行中"
    assert streamlit_app._run_status_label("paused") == "已暂停"
    assert streamlit_app._run_status_label("succeeded") == "已完成"
    assert streamlit_app._run_status_label("failed") == "失败"
    assert streamlit_app._run_stage_label("init") == "初始化"
    assert streamlit_app._run_stage_label("outline.generate") == "生成大纲"
    assert streamlit_app._run_stage_label("outline.review") == "大纲审批"
    assert streamlit_app._run_stage_label("volume.write") == "分卷写作"
    assert streamlit_app._run_stage_label("volume.review") == "分卷审批"
    assert streamlit_app._run_stage_label("risk.review") == "风险复核"
    assert streamlit_app._run_stage_label("chapter.review") == "章节复核"
    assert streamlit_app._run_stage_label("chapter.generate") == "章节生成"


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


def test_pending_review_payload_preserves_structured_chapter_review_fields(temp_project_dir):
    run_dir = streamlit_app.create_run(
        project_dir=temp_project_dir / "project",
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    pending_path = run_dir / "pending.json"
    pending_path.write_text(
        json.dumps(
            {
                "checkpoint_type": "chapter_review",
                "review_payload": {
                    "chapter_number": 40,
                    "title": "第四十章",
                    "summary": "目标锁假继承，正文掉锚。",
                    "issue_types": ["goal_lock_false_inheritance"],
                    "warning_issues": ["生成前意图检查已重写章节大纲，本章虽继续生成，但建议观察是否出现计划层掉锚复发。"],
                    "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
                    "anti_drift_details": {
                        "goal_lock": "守住宗门祖地",
                        "summary_alignment": True,
                        "body_alignment": False,
                        "goal_terms": ["宗门祖地", "守住"],
                        "matched_fragments": ["韩林只是想起守住宗门祖地，却只是站在祖地墙头观望众人慌乱。"],
                        "unaligned_fragments": ["他嘴上说不能退，却把整章篇幅都耗在无关紧要的闲谈里。"],
                    },
                    "chapter_intent_contract": {
                        "goal_lock": "守住宗门祖地",
                        "planned_action": "韩林必须调度伏兵守住祖地。",
                        "success_checks": ["正文至少一个关键行动、冲突选择或结果必须直接推进目标锁：守住宗门祖地"],
                    },
                    "semantic_review": {
                        "warning_only": True,
                        "issues": [
                            {
                                "category": "goal_lock_semantic_risk",
                                "message": "目标锁当前未触发硬阻断，但正文只有少量片段显式推进 `守住宗门祖地`，仍有语义层掉锚风险。",
                            }
                        ],
                    },
                    "rewrite_plan": {
                        "schema_version": "rewrite_plan.v2",
                        "strategy": "targeted_patch",
                        "issue_types": ["goal_lock_false_inheritance"],
                        "issue_categories": [],
                        "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
                        "fixes": ["重写时围绕目标锁重组正文推进链：守住宗门祖地"],
                        "success_criteria": ["摘要和正文都必须真实推进目标锁：守住宗门祖地"],
                        "operations": [
                            {
                                "phase": "body",
                                "action": "rebuild_goal_lock_chain",
                                "target": "goal_lock_progression",
                                "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                            }
                        ],
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    update_status(run_dir, status="paused", pending_state_path=str(pending_path), pause_reason="chapter_review")

    payload = streamlit_app._pending_review_payload(run_dir)

    assert payload["checkpoint_type"] == "chapter_review"
    assert payload["review_payload"]["issue_types"] == ["goal_lock_false_inheritance"]
    assert payload["review_payload"]["anti_drift_details"]["goal_lock"] == "守住宗门祖地"
    assert payload["review_payload"]["rewrite_plan"]["fixes"] == ["重写时围绕目标锁重组正文推进链：守住宗门祖地"]
    assert payload["review_payload"]["semantic_review"]["warning_only"] is True


def test_provider_status_lines_include_active_provider(mock_config_manager, monkeypatch):
    mock_config_manager.update_generation_config(
        active_provider="minimax",
        provider_updates={"minimax": {"model_name": "MiniMax-M2.5"}},
        persist=False,
    )
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    lines = streamlit_app._provider_status_lines()

    assert any("`minimax`" in line and "`active`" in line for line in lines)
    assert any("MiniMax-M2.5" in line for line in lines)


def test_risk_review_summary_formats_chapter_highlights():
    summary = streamlit_app._risk_review_summary(
        {
            "review_payload": {
                "risk_level": "high",
                "volume_start_chapter": 1,
                "volume_end_chapter": 20,
                "low_score_chapter_count": 2,
                "total_missing_events": 4,
                "summary": "第 1 卷存在明显失控风险，建议先人工复核后再继续。",
                "at_risk_chapters": [
                    {
                        "chapter_number": 3,
                        "overall_score": 4.8,
                        "missing_events_count": 3,
                        "recommendations": ["补回伏笔", "修正人物动机"],
                    }
                ],
            }
        }
    )

    assert "风险等级: high" in summary
    assert "卷范围: 1-20" in summary
    assert "第 3 章 · 分数 4.8" in summary


def test_volume_review_summary_formats_highlights():
    summary = streamlit_app._volume_review_summary(
        {
            "review_payload": {
                "volume_start_chapter": 1,
                "volume_end_chapter": 20,
                "generated_chapter_count": 2,
                "planned_chapter_count": 20,
                "total_word_count": 6800,
                "cross_volume_registry_summary": "- 跨卷未完成目标: 守住宗门祖地",
                "opening_summary": "主角进入主线冲突。",
                "closing_summary": "第一卷以反转收束。",
                "chapter_highlights": [
                    {
                        "chapter_number": 1,
                        "title": "开局",
                        "word_count": 3200,
                        "summary": "主角进入主线冲突。",
                        "key_events": ["入门", "拜师"],
                    }
                ],
            }
        }
    )

    assert "卷范围: 1-20" in summary
    assert "已生成章节: 2 / 20" in summary
    assert "总字数: 6800" in summary
    assert "跨卷未完成目标: 守住宗门祖地" in summary
    assert "第 1 章《开局》" in summary


def test_chapter_review_helpers_surface_structured_evidence():
    review_payload = {
        "issue_types": ["goal_lock_false_inheritance"],
        "warning_issues": ["生成前意图检查已重写章节大纲，本章虽继续生成，但建议观察是否出现计划层掉锚复发。"],
        "anti_drift_details": {
            "goal_lock": "守住宗门祖地",
            "summary_alignment": True,
            "body_alignment": False,
            "goal_terms": ["宗门祖地", "守住"],
            "matched_fragments": ["韩林只是想起守住宗门祖地，却只是站在祖地墙头观望众人慌乱。"],
            "unaligned_fragments": ["他嘴上说不能退，却把整章篇幅都耗在无关紧要的闲谈里。"],
        },
        "chapter_intent_contract": {
            "goal_lock": "守住宗门祖地",
            "planned_action": "韩林必须调度伏兵守住祖地。",
            "success_checks": ["正文至少一个关键行动、冲突选择或结果必须直接推进目标锁：守住宗门祖地"],
        },
        "semantic_review": {
            "warning_only": True,
            "issues": [
                {
                    "category": "goal_lock_semantic_risk",
                    "message": "目标锁当前未触发硬阻断，但正文只有少量片段显式推进 `守住宗门祖地`，仍有语义层掉锚风险。",
                }
            ],
        },
        "rewrite_plan": {
            "schema_version": "rewrite_plan.v2",
            "strategy": "targeted_patch",
            "issue_types": ["goal_lock_false_inheritance"],
            "issue_categories": [],
            "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
            "fixes": ["重写时围绕目标锁重组正文推进链：守住宗门祖地"],
            "success_criteria": ["摘要和正文都必须真实推进目标锁：守住宗门祖地"],
            "operations": [
                {
                    "phase": "body",
                    "action": "rebuild_goal_lock_chain",
                    "target": "goal_lock_progression",
                    "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                }
            ],
        },
    }

    structured = dict(streamlit_app._chapter_review_structured_sections(review_payload))
    evidence = dict(streamlit_app._chapter_review_evidence(review_payload))

    assert "goal_lock_false_inheritance" in structured["问题类型"]
    assert "生成前意图检查已重写章节大纲" in structured["语义告警"]
    assert "当前目标锁: 守住宗门祖地" in evidence["目标锁证据"]
    assert "未对齐片段" in evidence["目标锁证据"]
    assert "本章计划动作: 韩林必须调度伏兵守住祖地。" in evidence["生成前执行合同"]
    assert "goal_lock_semantic_risk" in evidence["语义复核"]
    assert "重写时围绕目标锁重组正文推进链：守住宗门祖地" in evidence["结构化重写方案"]
    assert "body / rebuild_goal_lock_chain / goal_lock_progression" in evidence["结构化重写方案"]


def test_chapter_review_resume_payload_compiles_rewrite_plan_and_notes():
    payload = streamlit_app._chapter_review_resume_payload(
        {
            "rewrite_plan": {
                "schema_version": "rewrite_plan.v2",
                "strategy": "targeted_patch",
                "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
                "success_criteria": ["摘要和正文都必须真实推进目标锁：守住宗门祖地"],
                "operations": [
                    {
                        "phase": "body",
                        "action": "rebuild_goal_lock_chain",
                        "target": "goal_lock_progression",
                        "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                        "rationale": "goal_lock_false_inheritance",
                    }
                ],
            }
        },
        "补上与上一章战场结尾的衔接。",
    )

    assert payload["chapter_rewrite_plan"]["strategy"] == "targeted_patch"
    assert "Patch 操作：" in payload["chapter_rewrite_guidance"]
    assert "[body / rebuild_goal_lock_chain / goal_lock_progression]" in payload["chapter_rewrite_guidance"]
    assert "人工补充：" in payload["chapter_rewrite_guidance"]
    assert payload["notes"] == "补上与上一章战场结尾的衔接。"


def test_volume_registry_defaults_formats_lists_as_multiline_text():
    defaults = streamlit_app._volume_registry_defaults(
        {
            "cross_volume_registry": {
                "unresolved_goals": ["守住宗门祖地", "追回失落阵眼"],
                "open_promises": ["回收第一卷宗门裂痕"],
                "dangling_settings": ["远古秘境现世"],
            }
        }
    )

    assert defaults["unresolved_goals"] == "守住宗门祖地\n追回失落阵眼"
    assert defaults["open_promises"] == "回收第一卷宗门裂痕"
    assert defaults["dangling_settings"] == "远古秘境现世"


def test_volume_guidance_draft_uses_highlights_and_cross_volume_registry():
    draft = streamlit_app._volume_guidance_draft(
        {
            "chapter_highlights": [
                {
                    "title": "卷末冲突",
                    "summary": "主角死守祖地后迎来反转危机，局势仍在升级。",
                    "key_events": ["主角与师尊决裂", "祖地防线濒临崩裂"],
                }
            ],
            "cross_volume_registry": {
                "unresolved_goals": ["守住宗门祖地"],
                "open_promises": ["回收第一卷宗门裂痕"],
                "dangling_settings": ["远古秘境现世"],
            },
        }
    )

    assert draft["must_recover"] == "回收第一卷宗门裂痕"
    assert "关键事件继续施压相关人物关系" in draft["relationship_focus"]
    assert "不要扩写尚未桥接的新设定" in draft["must_avoid"]
    assert "延续高压推进" in draft["tone_target"]
    assert "卷末冲突" in draft["extra_notes"]


def test_queued_guidance_summary_reads_longform_state(temp_project_dir):
    longform_state_path = temp_project_dir / "longform_state.v1.json"
    longform_state_path.write_text(
        json.dumps(
            {
                "next_volume_guidance": "- 必须回收的伏笔/问题: 回收第一卷伏笔\n- 明确避免的方向: 不要新增支线角色"
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = streamlit_app._queued_guidance_summary({"longform_state_path": str(longform_state_path)})

    assert "回收第一卷伏笔" in summary
    assert "不要新增支线角色" in summary


def test_queued_guidance_summary_prefers_status_snapshot():
    summary = streamlit_app._queued_guidance_summary(
        {
            "queued_volume_guidance": "- 必须回收的伏笔/问题: 直接读 status 快照",
            "longform_state_path": "/tmp/unused.json",
        }
    )

    assert summary == "- 必须回收的伏笔/问题: 直接读 status 快照"


def test_longform_control_panel_sections_reads_goal_lock_registry_and_pending_review(temp_project_dir):
    longform_state_path = temp_project_dir / "longform_state.v1.json"
    pending_path = temp_project_dir / "pending.json"
    longform_state_path.write_text(
        json.dumps(
            {
                "next_volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "must_recover": "回收第一卷宗门裂痕",
                    "new_setting_budget": "1",
                },
                "cross_volume_registry": {
                    "unresolved_goals": ["守住宗门祖地"],
                    "open_promises": ["揭示魔帝线"],
                    "dangling_settings": ["远古秘境现世"],
                },
                "approval_history": [
                    {
                        "checkpoint_type": "chapter_review",
                        "action": "revise",
                        "payload": {
                            "notes": "先把祖地防线的实际行动补出来。",
                            "chapter_rewrite_plan": {
                                "operations": [
                                    {"phase": "body", "action": "rebuild_goal_lock_chain"},
                                ]
                            },
                        },
                        "submitted_at": "2026-04-21T10:15:00",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pending_path.write_text(
        json.dumps(
            {
                "checkpoint_type": "chapter_review",
                "review_payload": {
                    "summary": "目标锁假继承，正文掉锚。",
                    "issue_types": ["goal_lock_false_inheritance"],
                    "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    sections = dict(
        streamlit_app._longform_control_panel_sections(
            {
                "longform_state_path": str(longform_state_path),
                "pending_state_path": str(pending_path),
            }
        )
    )
    expected_approval_history = approval_history_summary(
        {
            "approval_history": [
                {
                    "checkpoint_type": "chapter_review",
                    "action": "revise",
                    "payload": {
                        "notes": "先把祖地防线的实际行动补出来。",
                        "chapter_rewrite_plan": {
                            "operations": [
                                {"phase": "body", "action": "rebuild_goal_lock_chain"},
                            ]
                        },
                    },
                    "submitted_at": "2026-04-21T10:15:00",
                }
            ]
        }
    )

    assert "当前 goal_lock: 守住宗门祖地" in sections["卷级控制面板"]
    assert "必须回收: 回收第一卷宗门裂痕" in sections["卷级控制面板"]
    assert "跨卷未完成目标: 守住宗门祖地" in sections["跨卷状态"]
    assert "尚未回收承诺/伏笔: 揭示魔帝线" in sections["跨卷状态"]
    assert sections["审批轨迹"] == expected_approval_history
    assert "待处理节点: chapter_review" in sections["最近待审批"]
    assert "问题类型: goal_lock_false_inheritance" in sections["最近待审批"]


def test_render_run_status_summary_shows_chapter_review_control_panel(temp_project_dir):
    longform_state_path = temp_project_dir / "longform_state.v1.json"
    pending_path = temp_project_dir / "pending.json"
    longform_state_path.write_text(
        json.dumps(
            {
                "next_volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "must_recover": "回收第一卷宗门裂痕",
                },
                "cross_volume_registry": {
                    "unresolved_goals": ["守住宗门祖地"],
                    "open_promises": ["揭示魔帝线"],
                    "dangling_settings": [],
                },
                "approval_history": [
                    {
                        "checkpoint_type": "chapter_review",
                        "action": "revise",
                        "payload": {
                            "notes": "先把祖地防线的实际行动补出来。",
                            "chapter_rewrite_plan": {
                                "operations": [
                                    {"phase": "body", "action": "rebuild_goal_lock_chain"},
                                ]
                            },
                        },
                        "submitted_at": "2026-04-21T10:15:00",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pending_path.write_text(
        json.dumps(
            {
                "checkpoint_type": "chapter_review",
                "review_payload": {
                    "summary": "目标锁假继承，正文掉锚。",
                    "issue_types": ["goal_lock_false_inheritance"],
                    "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fake_st = _StatusSummaryFakeStreamlit()

    payload = {
        "status": {
            "status": "paused",
            "current_stage": "chapter.review",
            "current_step": "等待章节复核",
            "chapters_completed": 4,
            "chapters_total": 120,
            "pause_reason": "chapter_review",
            "queued_volume_guidance": "- 必须回收的伏笔/问题: 回收第一卷宗门裂痕",
            "longform_state_path": str(longform_state_path),
            "pending_state_path": str(pending_path),
        },
        "run_dir": str(temp_project_dir / "runs" / "run-001"),
    }

    streamlit_app._render_run_status_summary(fake_st, payload)

    assert any("任务已暂停: 章节复核" in item for item in fake_st.warnings)
    assert any("下一卷排队指令" in item for item in fake_st.infos)
    assert any("卷级控制面板" in item for item in fake_st.markdowns)
    assert any("跨卷状态" in item for item in fake_st.markdowns)
    assert any("审批轨迹" in item for item in fake_st.markdowns)
    assert any("最近待审批" in item for item in fake_st.markdowns)
    assert any("当前 goal_lock: 守住宗门祖地" in item for item in fake_st.codes)
    assert any("章节复核 -> 修订" in item for item in fake_st.codes)
    assert any("待处理节点: chapter_review" in item for item in fake_st.codes)
    assert any("运行目录:" in item for item in fake_st.captions)


def test_render_run_status_summary_shows_volume_review_control_panel(temp_project_dir):
    longform_state_path = temp_project_dir / "longform_state.v1.json"
    pending_path = temp_project_dir / "pending.json"
    longform_state_path.write_text(
        json.dumps(
            {
                "next_volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "must_recover": "回收第一卷宗门裂痕",
                    "new_setting_budget": "1",
                },
                "cross_volume_registry": {
                    "unresolved_goals": ["守住宗门祖地"],
                    "open_promises": ["揭示魔帝线"],
                    "dangling_settings": ["远古秘境现世"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pending_path.write_text(
        json.dumps(
            {
                "checkpoint_type": "volume_review",
                "review_payload": {
                    "summary": "第 1 卷已完成，等待下一卷指令。",
                    "cross_volume_registry_summary": "- 跨卷未完成目标: 守住宗门祖地",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fake_st = _StatusSummaryFakeStreamlit(allow_caption=False)

    payload = {
        "status": {
            "status": "paused",
            "current_stage": "volume.review",
            "current_step": "等待分卷审批",
            "chapters_completed": 60,
            "chapters_total": 120,
            "pause_reason": "volume_review",
            "queued_volume_guidance": "- 必须回收的伏笔/问题: 回收第一卷宗门裂痕",
            "longform_state_path": str(longform_state_path),
            "pending_state_path": str(pending_path),
        },
        "run_dir": str(temp_project_dir / "runs" / "run-001"),
    }

    streamlit_app._render_run_status_summary(fake_st, payload)

    assert any("任务已暂停: 分卷审批" in item for item in fake_st.warnings)
    assert any("下一卷排队指令" in item for item in fake_st.infos)
    assert any("卷级控制面板" in item for item in fake_st.markdowns)
    assert any("跨卷状态" in item for item in fake_st.markdowns)
    assert any("最近待审批" in item for item in fake_st.markdowns)
    assert any("必须回收: 回收第一卷宗门裂痕" in item for item in fake_st.codes)
    assert any("跨卷未完成目标: 守住宗门祖地" in item for item in fake_st.codes)
    assert any("待处理节点: volume_review" in item for item in fake_st.codes)


def test_save_provider_settings_action_persists_generation_config(mock_config_manager, monkeypatch):
    monkeypatch.setattr(streamlit_app, "get_config_manager", lambda: mock_config_manager)

    message = streamlit_app.save_provider_settings_action(
        "doubao",
        {
            "doubao": {
                "provider": "doubao",
                "label": "Doubao",
                "enabled": True,
                "api_key": "demo-key",
                "base_url": "",
                "api_host": "https://ark.example.com/api/v3",
                "model_name": "doubao-text-pro",
                "temperature": 0.6,
                "max_tokens": 4096,
                "use_cli": False,
                "system_prompt": "你是小说助手",
            }
        },
    )

    saved = (mock_config_manager.config_dir / "generation.json").read_text(encoding="utf-8")
    assert "doubao-text-pro" in saved
    assert "已保存 Provider 配置" in message


def test_resume_longform_action_writes_guidance_payload(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)

    launched = {}

    monkeypatch.setattr(streamlit_app, "RUN_SCRIPT", Path("/tmp/fake_run.py"))
    monkeypatch.setattr(streamlit_app, "read_status", lambda _run_dir: {"run_id": "run-001"})
    monkeypatch.setattr(
        streamlit_app,
        "_launch_cli_process",
        lambda _run_dir, cmd: launched.setdefault("cmd", cmd),
    )

    streamlit_app.resume_longform_action(
        run_dir,
        str(run_dir / "pending.json"),
        "approve",
        {
            "must_recover": "回收第一卷伏笔",
            "relationship_focus": "强化师徒冲突",
            "must_avoid": "不要新增支线角色",
            "tone_target": "压迫感更强",
            "extra_notes": "让主角更主动",
        },
    )

    payload_files = list(run_dir.glob("approval_payload_*.json"))
    assert payload_files
    payload = json.loads(payload_files[0].read_text(encoding="utf-8"))
    assert payload["must_recover"] == "回收第一卷伏笔"
    assert payload["relationship_focus"] == "强化师徒冲突"
    assert "--approval-payload" in launched["cmd"]


def test_resume_longform_action_writes_cross_volume_registry_payload(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)

    launched = {}

    monkeypatch.setattr(streamlit_app, "RUN_SCRIPT", Path("/tmp/fake_run.py"))
    monkeypatch.setattr(streamlit_app, "read_status", lambda _run_dir: {"run_id": "run-001"})
    monkeypatch.setattr(
        streamlit_app,
        "_launch_cli_process",
        lambda _run_dir, cmd: launched.setdefault("cmd", cmd),
    )

    streamlit_app.resume_longform_action(
        run_dir,
        str(run_dir / "pending.json"),
        "approve",
        {
            "must_recover": "回收第一卷伏笔",
            "unresolved_goals": ["守住宗门祖地", "追回失落阵眼"],
            "open_promises": [],
            "dangling_settings": ["远古秘境现世"],
        },
    )

    payload_files = list(run_dir.glob("approval_payload_*.json"))
    assert payload_files
    payload = json.loads(payload_files[0].read_text(encoding="utf-8"))
    assert payload["unresolved_goals"] == ["守住宗门祖地", "追回失落阵眼"]
    assert payload["open_promises"] == []
    assert payload["dangling_settings"] == ["远古秘境现世"]
    assert "--approval-payload" in launched["cmd"]


def test_render_pending_review_submits_risk_revise(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "risk_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "review_payload": {"summary": "存在风险"},
        },
    )
    monkeypatch.setattr(streamlit_app, "_risk_review_summary", lambda _payload: "存在风险")
    _install_pending_review_resume_capture(monkeypatch, launched)

    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_risk_revise",
            text_area_values={"风险复核备注": "请补强第 3 章因果链。"},
            column_count=3,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "revise"
    assert launched["call"]["payload"] == {"notes": "请补强第 3 章因果链。"}
    assert launched["rerun"] is True


def test_render_pending_review_submits_volume_approve_with_cross_volume_registry(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "volume_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "current_volume": 2,
            "review_payload": {
                "volume_index": 2,
                "cross_volume_registry": {
                    "unresolved_goals": ["守住宗门祖地"],
                    "open_promises": ["回收第一卷宗门裂痕"],
                    "dangling_settings": ["远古秘境现世"],
                },
            },
        },
    )
    monkeypatch.setattr(streamlit_app, "_volume_review_summary", lambda _payload: "第 2 卷摘要")
    _install_pending_review_resume_capture(monkeypatch, launched)

    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_volume_approve",
            text_area_values={
                "必须回收的伏笔/问题": "回收第一卷宗门裂痕",
                "需要强化的人物关系": "强化师徒冲突",
                "明确避免的方向": "不要新增支线角色",
                "补充说明": "让主角更主动",
                "跨卷未完成目标": "守住宗门祖地\n追回失落阵眼",
                "尚未回收承诺/伏笔": "",
                "已引入但未桥接设定": "远古秘境现世",
            },
            text_input_values={"目标基调": "压迫感更强"},
            column_count=2,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "approve"
    assert launched["call"]["payload"] == {
        "must_recover": "回收第一卷宗门裂痕",
        "relationship_focus": "强化师徒冲突",
        "must_avoid": "不要新增支线角色",
        "tone_target": "压迫感更强",
        "extra_notes": "让主角更主动",
        "unresolved_goals": ["守住宗门祖地", "追回失落阵眼"],
        "open_promises": [],
        "dangling_settings": ["远古秘境现世"],
    }
    assert launched["rerun"] is True


def test_render_pending_review_submits_chapter_revise(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    _install_pending_review_resume_capture(monkeypatch, launched)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "chapter_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "review_payload": {
                "chapter_number": 4,
                "title": "第四章",
                "summary": "章节与前文严重割裂",
                "blocking_issues": ["本章开头未自然承接上章人物或局势状态。"],
            },
        },
    )
    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_chapter_revise",
            text_area_values={"追加重写指令": "补上与上一章战场结尾的衔接。"},
            column_count=3,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "revise"
    assert launched["call"]["payload"] == {
        "chapter_rewrite_guidance": "补上与上一章战场结尾的衔接。"
    }
    assert launched["rerun"] is True


def test_render_pending_review_submits_chapter_revise_with_structured_rewrite_plan(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    _install_pending_review_resume_capture(monkeypatch, launched)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "chapter_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "review_payload": {
                "chapter_number": 4,
                "title": "第四章",
                "summary": "目标锁假继承，正文掉锚。",
                "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
                "rewrite_plan": {
                    "schema_version": "rewrite_plan.v2",
                    "strategy": "targeted_patch",
                    "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
                    "success_criteria": ["摘要和正文都必须真实推进目标锁：守住宗门祖地"],
                    "operations": [
                        {
                            "phase": "body",
                            "action": "rebuild_goal_lock_chain",
                            "target": "goal_lock_progression",
                            "instruction": "重写时围绕目标锁重组正文推进链：守住宗门祖地",
                            "rationale": "goal_lock_false_inheritance",
                        }
                    ],
                },
            },
        },
    )
    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_chapter_revise",
            text_area_values={"追加重写指令": "补上与上一章战场结尾的衔接。"},
            column_count=3,
            use_expander=True,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "revise"
    assert launched["call"]["payload"]["chapter_rewrite_plan"]["strategy"] == "targeted_patch"
    assert "Patch 操作：" in launched["call"]["payload"]["chapter_rewrite_guidance"]
    assert "人工补充：" in launched["call"]["payload"]["chapter_rewrite_guidance"]
    assert launched["call"]["payload"]["notes"] == "补上与上一章战场结尾的衔接。"
    assert launched["rerun"] is True


def test_render_pending_review_submits_chapter_approve(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    _install_pending_review_resume_capture(monkeypatch, launched)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "chapter_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "review_payload": {
                "chapter_number": 4,
                "title": "第四章",
                "summary": "章节与前文严重割裂",
                "blocking_issues": ["本章开头未自然承接上章人物或局势状态。"],
            },
        },
    )
    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_chapter_approve",
            text_area_values={"追加重写指令": "沿用当前规则继续重试。"},
            column_count=3,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "approve"
    assert launched["call"]["payload"] == {
        "chapter_rewrite_guidance": "沿用当前规则继续重试。"
    }
    assert launched["rerun"] is True


def test_render_pending_review_submits_chapter_reject(temp_project_dir, monkeypatch):
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True)
    launched = {}

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: run_dir)
    _install_pending_review_resume_capture(monkeypatch, launched)
    monkeypatch.setattr(
        streamlit_app,
        "_pending_review_payload",
        lambda _run_dir: {
            "checkpoint_type": "chapter_review",
            "pending_state_path": str(run_dir / "pending.json"),
            "review_payload": {
                "chapter_number": 4,
                "title": "第四章",
                "summary": "章节与前文严重割裂",
                "blocking_issues": ["本章开头未自然承接上章人物或局势状态。"],
            },
        },
    )
    streamlit_app._render_pending_review(
        _PendingReviewFakeStreamlit(
            pressed_key="yw_chapter_reject",
            text_area_values={"追加重写指令": "先保持暂停，待人工处理。"},
            column_count=3,
            launched=launched,
        )
    )

    assert launched["call"]["action"] == "reject"
    assert launched["call"]["payload"] == {
        "chapter_rewrite_guidance": "先保持暂停，待人工处理。"
    }
    assert launched["rerun"] is True


def test_render_run_monitor_uses_unkeyed_text_areas(monkeypatch):
    fake_st = _RunMonitorFakeStreamlit()

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: Path("/tmp/demo-run"))
    monkeypatch.setattr(
        streamlit_app,
        "_run_monitor_payload",
        lambda _run_dir: {"status": {}, "stdout": "out", "stderr": "err", "run_dir": "/tmp/demo-run", "is_active": True},
    )
    monkeypatch.setattr(streamlit_app, "_render_run_status_summary", lambda *_args, **_kwargs: None)

    streamlit_app._render_run_monitor(fake_st)

    assert [item["label"] for item in fake_st.text_area_calls] == ["stdout.log", "stderr.log"]
    assert all("key" not in item["kwargs"] for item in fake_st.text_area_calls)
