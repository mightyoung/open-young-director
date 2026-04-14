"""Tests for Streamlit helper functions."""

import json
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
    update_status(
        first,
        status="paused",
        current_stage="volume.review",
        chapters_total=120,
        chapters_completed=60,
        queued_volume_guidance="- 必须回收的伏笔/问题: 回收第一卷伏笔\n- 明确避免的方向: 不要新增支线角色",
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
    update_status(
        run_dir,
        status="paused",
        pause_reason="volume_review",
        pending_state_path=str(run_dir / "pending.json"),
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


def test_pause_reason_label_maps_known_values():
    assert streamlit_app._pause_reason_label("outline_review") == "大纲审批"
    assert streamlit_app._pause_reason_label("volume_review") == "分卷审批"
    assert streamlit_app._pause_reason_label("risk_review") == "风险复核"


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
    assert "第 1 章《开局》" in summary


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


def test_render_run_monitor_uses_unkeyed_text_areas(monkeypatch):
    calls = []

    class _FakeStreamlit:
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
            calls.append({"label": label, "value": value, "height": height, "kwargs": kwargs})
            return None

    monkeypatch.setattr(streamlit_app, "_resolve_active_run_dir", lambda: Path("/tmp/demo-run"))
    monkeypatch.setattr(
        streamlit_app,
        "_run_monitor_payload",
        lambda _run_dir: {"status": {}, "stdout": "out", "stderr": "err", "run_dir": "/tmp/demo-run", "is_active": True},
    )
    monkeypatch.setattr(streamlit_app, "_render_run_status_summary", lambda *_args, **_kwargs: None)

    streamlit_app._render_run_monitor(_FakeStreamlit())

    assert [item["label"] for item in calls] == ["stdout.log", "stderr.log"]
    assert all("key" not in item["kwargs"] for item in calls)
