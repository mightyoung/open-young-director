"""Tests for run_novel_generation longform resume flows."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_novel_generation
from young_writer.agents.novel_generator import GeneratedChapter
from young_writer.services.longform_run import (
    CHECKPOINT_CHAPTER,
    CHECKPOINT_OUTLINE,
    STAGE_CHAPTER_REVIEW,
    STAGE_VOLUME_PLAN,
    format_longform_registry,
    initial_longform_state,
    record_pause,
)
from young_writer.services.run_storage import create_run, read_status


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

COMPLETE_CHAPTER_ARTIFACT = """# 第1章

> 第1章 | 字数: 1200 | 生成时间: 2026-06-03T00:00:00

**本章概要**: 沈夜返回空间城。

**关键事件**: 无

---

正文。

*(本章完)*
"""

COMPLETE_CUSTOM_TITLED_CHAPTER_ARTIFACT = """# 星火初燃

> 星火初燃 | 字数: 900 | 生成时间: 2026-06-03T00:00:00

**本章概要**: 线索第一次点亮。

**关键事件**: 无

---

正文。

*(本章完)*
"""


class _Project:
    def __init__(self):
        self.id = "project-123"
        self.title = "演示项目"
        self.total_chapters = 120
        self.current_chapter = 3
        self.outline = "outline"
        self.world_setting = "world"
        self.character_intro = "characters"


def _load_longform_resume_golden_cases() -> list[dict]:
    fixture_path = FIXTURES_DIR / "longform_resume_golden_cases.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _assert_approval_history_entries(
    history: list[dict], expected_entries: list[dict]
) -> None:
    assert len(history) == len(expected_entries)
    for actual, expected in zip(history, expected_entries):
        assert actual["checkpoint_type"] == expected["checkpoint_type"]
        assert actual["action"] == expected["action"]
        assert actual["payload"] == expected["payload"]
        assert actual["submitted_at"]


def test_continue_longform_run_preserves_child_subprocess_failure_message(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 50
    project.current_chapter = 29
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=10,
        approval_mode="none",
        auto_approve=True,
    )
    state.update(
        {
            "current_volume": 3,
            "current_volume_start_chapter": 21,
            "current_volume_end_chapter": 30,
            "chapters_completed": 29,
            "total_chapters": 50,
            "total_volumes": 5,
        }
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=10),
        load_project=lambda _project_id: project,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_reconcile_longform_progress", lambda _cfg, st: st
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **kwargs: {"risk_detected": False},
    )
    monkeypatch.setattr(
        run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: False
    )

    detailed_error = (
        "LLM generation failed and fallback disabled: "
        "DeepSeek API error (402): Insufficient Balance"
    )

    def _fake_run_subprocess(
        args,
        *,
        project_id,
        run_id,
        run_dir,
        start,
        count,
        writing_options,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
    ):
        run_novel_generation.update_status(
            run_dir,
            status="failed",
            current_stage=run_novel_generation.STAGE_CHAPTER_GENERATE,
            current_step="第 30 章失败，已停止本次受控生成",
            error_message=detailed_error,
            return_code=1,
        )
        return 1

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO", require_llm=True),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 1
    status = read_status(run_dir)
    assert status["status"] == "failed"
    assert status["error_message"] == detailed_error
    longform_state = run_novel_generation.load_longform_state(run_dir)
    assert longform_state["error_message"] == detailed_error


def test_checkpoint_payload_uses_saved_chapter_metadata(temp_project_dir):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT,
        encoding="utf-8",
    )
    (project_dir / "metadata.json").write_text(
        json.dumps(
            {
                "chapters": [
                    {
                        "number": 1,
                        "title": "第1章",
                        "word_count": 1200,
                        "summary": "沈夜返回空间城。",
                        "file_path": str(chapters_dir / "ch001_第1章.md"),
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    results_file = project_dir / "generation_results.json"
    payload = run_novel_generation._checkpoint_payload_from_disk(
        results_file,
        {
            "successful": 0,
            "failed": 1,
            "total_words_generated": 0,
            "failed_chapters": [{"chapter_number": 2, "error": "boom"}],
            "checkpoints": [],
        },
    )

    assert payload["successful"] == 1
    assert payload["total_words_generated"] == 1200
    assert payload["checkpoints"] == [1]
    assert payload["failed"] == 1
    assert payload["saved_chapters"][0]["number"] == 1


def test_checkpoint_payload_rebuilds_chapter_results_from_saved_artifacts(
    temp_project_dir,
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT,
        encoding="utf-8",
    )
    (chapters_dir / "ch002_第2章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT.replace("第1章", "第2章").replace("1200", "1300"),
        encoding="utf-8",
    )

    payload = run_novel_generation._checkpoint_payload_from_disk(
        project_dir / "generation_results.json",
        {
            "successful": 1,
            "failed": 0,
            "total_words_generated": 1300,
            "failed_chapters": [],
            "checkpoints": [2],
            "chapter_results": [
                {
                    "chapter_number": 2,
                    "status": "success",
                    "word_count": 1300,
                    "time_seconds": 42,
                }
            ],
        },
    )

    assert payload["successful"] == 2
    assert payload["total_words_generated"] == 2500
    assert payload["checkpoints"] == [1, 2]
    assert [item["chapter_number"] for item in payload["chapter_results"]] == [1, 2]
    assert payload["chapter_results"][0]["status"] == "success"
    assert payload["chapter_results"][0]["word_count"] == 1200
    assert payload["chapter_results"][1]["time_seconds"] == 42


def test_checkpoint_payload_falls_back_to_saved_chapter_artifacts_without_metadata(
    temp_project_dir,
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT,
        encoding="utf-8",
    )
    payload = run_novel_generation._checkpoint_payload_from_disk(
        project_dir / "generation_results.json",
        {
            "successful": 0,
            "failed": 0,
            "total_words_generated": 0,
            "failed_chapters": [],
            "checkpoints": [],
        },
    )

    assert payload["successful"] == 1
    assert payload["total_words_generated"] == 1200
    assert payload["checkpoints"] == [1]
    assert payload["saved_chapters"][0]["title"] == "第1章"
    assert payload["saved_chapters"][0]["summary"] == "沈夜返回空间城。"


def test_checkpoint_payload_trusts_complete_artifact_with_custom_heading(
    temp_project_dir,
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_星火初燃.md").write_text(
        COMPLETE_CUSTOM_TITLED_CHAPTER_ARTIFACT,
        encoding="utf-8",
    )

    payload = run_novel_generation._checkpoint_payload_from_disk(
        project_dir / "generation_results.json",
        {
            "successful": 0,
            "failed": 0,
            "total_words_generated": 0,
            "failed_chapters": [],
            "checkpoints": [],
        },
    )

    assert payload["successful"] == 1
    assert payload["saved_chapters"][0]["title"] == "星火初燃"
    assert payload["saved_chapters"][0]["summary"] == "线索第一次点亮。"


def test_checkpoint_payload_normalizes_total_attempted_from_saved_results(
    temp_project_dir,
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for chapter_number in range(1, 6):
        (chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{chapter_number}章"),
            encoding="utf-8",
        )

    payload = run_novel_generation._checkpoint_payload_from_disk(
        project_dir / "generation_results.json",
        {
            "total_attempted": 2,
            "successful": 2,
            "failed": 0,
            "total_words_generated": 0,
            "failed_chapters": [],
            "checkpoints": [4, 5],
            "chapter_results": [
                {"chapter_number": 4, "status": "success", "time_seconds": 42},
                {"chapter_number": 5, "status": "success", "time_seconds": 43},
            ],
        },
    )

    assert payload["successful"] == 5
    assert payload["total_attempted"] == 5
    assert len(payload["chapter_results"]) == 5


def test_cmd_generate_full_resumes_from_chapter_review(temp_project_dir, monkeypatch):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={
            "chapter_number": 4,
            "title": "第四章",
            "summary": "章节与前文严重割裂",
            "blocking_issues": ["本章开头未自然承接上章人物或局势状态，存在明显割裂。"],
        },
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        captured["run_dir"] = run_dir
        return 7

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="revise",
        approval_payload='{"chapter_rewrite_guidance":"开头先承接上一章战场局势，再重写人物出场。"}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
        chapter_review_mode="auto",
        chapter_auto_repair_attempts=2,
    )

    result = run_novel_generation.cmd_generate_full(args)

    status = read_status(run_dir)
    assert result == 7
    assert captured["run_dir"] == run_dir
    assert captured["state"]["current_stage"] == STAGE_VOLUME_PLAN
    assert captured["state"]["chapter_review_mode"] == "auto"
    assert captured["state"]["chapter_auto_repair_attempts"] == 2
    assert captured["state"]["pending_state_path"] is None
    assert captured["state"]["next_volume_guidance"] == ""
    assert (
        captured["state"]["next_chapter_guidance"]
        == "开头先承接上一章战场局势，再重写人物出场。"
    )
    assert captured["state"]["next_chapter_guidance_chapter"] == 4
    assert captured["state"]["pending_revision_validation"] == {
        "chapter_number": 4,
        "issue_types": [],
        "success_criteria": [],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
        "captured_experience_id": None,
        "captured_issue_types": [],
        "promotion_candidate": False,
    }
    assert status["pending_state_path"] is None
    assert status["pause_reason"] is None


def test_cmd_generate_full_resume_preserves_stored_auto_repair_settings(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
        chapter_review_mode="auto",
        chapter_auto_repair_attempts=2,
    )
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={"chapter_number": 4, "title": "第四章", "summary": "等待修订"},
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 6

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload=None,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
        chapter_review_mode=None,
        chapter_auto_repair_attempts=None,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 6
    assert captured["state"]["chapter_review_mode"] == "auto"
    assert captured["state"]["chapter_auto_repair_attempts"] == 2


def test_cmd_generate_full_resume_preserves_explicit_zero_auto_repair_attempts(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
        chapter_review_mode="auto",
        chapter_auto_repair_attempts=2,
    )
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={"chapter_number": 4, "title": "第四章", "summary": "等待修订"},
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 6

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload=None,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
        chapter_review_mode=None,
        chapter_auto_repair_attempts=0,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 6
    assert captured["state"]["chapter_auto_repair_attempts"] == 0


def test_cmd_generate_full_new_run_preserves_explicit_zero_auto_repair_attempts(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 5

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)
    monkeypatch.setattr(run_novel_generation, "_ensure_run_tracking", lambda **kwargs: Path(kwargs["run_dir"]))

    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=None,
        submit_approval=None,
        approval_payload=None,
        chapters_per_volume=60,
        approval_mode="none",
        auto_approve=True,
        chapter_review_mode="auto",
        chapter_auto_repair_attempts=0,
        project_id=project.id,
        load=project.id,
        project=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 5
    assert captured["state"]["chapter_auto_repair_attempts"] == 0


def test_cmd_generate_full_rejects_chapter_review_and_stays_paused(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={
            "chapter_number": 4,
            "title": "第四章",
            "summary": "章节与前文严重割裂",
            "blocking_issues": ["本章开头未自然承接上章人物或局势状态，存在明显割裂。"],
        },
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    def _unexpected_continue(*args, **kwargs):
        raise AssertionError("reject 分支不应继续长篇生成")

    monkeypatch.setattr(
        run_novel_generation, "_continue_longform_run", _unexpected_continue
    )

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="reject",
        approval_payload='{"chapter_rewrite_guidance":"先不要继续。"}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    result = run_novel_generation.cmd_generate_full(args)

    status = read_status(run_dir)
    assert result == 0
    assert status["status"] == "paused"
    assert status["current_stage"] == STAGE_CHAPTER_REVIEW
    assert status["pending_state_path"] == paused["pending_state_path"]


def test_cmd_generate_full_compiles_chapter_rewrite_plan_into_next_guidance(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={
            "chapter_number": 4,
            "title": "第四章",
            "summary": "目标锁假继承，正文掉锚。",
            "blocking_issues": [
                "目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"
            ],
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
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 8

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="revise",
        approval_payload=json.dumps(
            {
                "chapter_rewrite_plan": {
                    "schema_version": "rewrite_plan.v2",
                    "strategy": "targeted_patch",
                    "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
                    "success_criteria": [
                        "摘要和正文都必须真实推进目标锁：守住宗门祖地"
                    ],
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
                "notes": "补上与上一章战场结尾的衔接。",
            },
            ensure_ascii=False,
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 8
    assert "Patch 操作：" in captured["state"]["next_chapter_guidance"]
    assert (
        "[body / rebuild_goal_lock_chain / goal_lock_progression]"
        in captured["state"]["next_chapter_guidance"]
    )
    assert "人工补充：" in captured["state"]["next_chapter_guidance"]
    assert captured["state"]["next_chapter_guidance_chapter"] == 4
    assert captured["state"]["pending_revision_validation"]["issue_types"] == []
    assert captured["state"]["pending_revision_validation"]["success_criteria"] == [
        "摘要和正文都必须真实推进目标锁：守住宗门祖地"
    ]


def test_run_volume_generation_subprocess_passes_one_shot_chapter_guidance(monkeypatch):
    captured = {}

    def _fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_novel_generation.subprocess, "run", _fake_run)

    rc = run_novel_generation._run_volume_generation_subprocess(
        argparse.Namespace(log_level="INFO", require_llm=True),
        project_id="project-123",
        run_id="run-001",
        run_dir=run_novel_generation.Path("/tmp/run-001"),
        start=4,
        count=10,
        writing_options={"humanization_level": "strict"},
        volume_guidance="延续本卷整体压迫感",
        chapter_guidance="补上与上一章战场结尾的衔接。",
        chapter_guidance_target=4,
    )

    assert rc == 0
    assert "--volume-guidance" in captured["cmd"]
    assert "--chapter-guidance" in captured["cmd"]
    assert "--chapter-guidance-target" in captured["cmd"]
    assert "--require-llm" in captured["cmd"]
    assert "--humanization-level" in captured["cmd"]
    assert "strict" in captured["cmd"]
    assert "补上与上一章战场结尾的衔接。" in captured["cmd"]


def test_compile_auto_repair_guidance_adds_goal_lock_progression_notes():
    report = {
        "issue_types": [
            "scene_or_timeline_disconnect",
            "goal_lock_false_inheritance",
        ],
        "smoothness_details": [
            {
                "category": "上一章后果未被承接",
                "previous_evidence": "你父亲当年也是在这种‘恰好的时机’下探的",
                "current_evidence": "沈雁乘坐破冰船抵达北海冰穹城外围",
            }
        ],
        "rewrite_plan": {
            "success_criteria": [
                "开头必须接住上一章的后果，不能让危机凭空消失。",
                "摘要和正文都必须真实推进目标锁：沈雁调查员沈雁重返被封锁的北海冰穹城",
            ],
            "operations": [
                {
                    "phase": "opening",
                    "action": "restore_carryover",
                    "target": "carryover_consequence",
                    "instruction": "明确回应上一章遗留的危机、伤势、追击或未完成动作。",
                    "rationale": "上一章后果未被承接",
                },
                {
                    "phase": "body",
                    "action": "rebuild_goal_lock_chain",
                    "target": "goal_lock_progression",
                    "instruction": "重写时围绕目标锁重组正文推进链：沈雁调查员沈雁重返被封锁的北海冰穹城",
                    "rationale": "goal_lock_false_inheritance",
                },
            ],
        },
        "chapter_graph_packet": {
            "chapter_goal": "沈雁调查员沈雁重返被封锁的北海冰穹城",
            "goal_lock": "沈雁调查员沈雁重返被封锁的北海冰穹城",
            "target_destinations": ["冰穹城"],
            "must_include_events": ["沈雁调查员沈雁重返被封锁的北海冰穹城"],
        },
        "graph_diff_details": {
            "evidence_refs": [
                {
                    "kind": "continuity",
                    "excerpt": "沈雁乘坐破冰船抵达北海冰穹城外围，透过舷窗凝视废弃的极地轨道电梯残骸。",
                }
            ]
        },
    }

    guidance = run_novel_generation._compile_auto_repair_guidance(
        report,
        recommended_action="rewrite",
    )

    assert "必须先回应上一章未完成后果" in guidance
    assert "关键事件「沈雁调查员沈雁重返被封锁的北海冰穹城」必须在正文里以动作加结果真实发生" in guidance
    assert "如果角色已经到达或接近「冰穹城」" in guidance
    assert "不要再次以抵达、站位、凝视或回想结束首段" in guidance


def test_continue_longform_run_validates_revised_chapter_before_volume_progress(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 4
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 3
    state["next_chapter_guidance"] = "重写第4章"
    state["next_chapter_guidance_chapter"] = 4
    state["pending_revision_validation"] = {
        "chapter_number": 4,
        "issue_types": ["goal_lock_false_inheritance"],
        "success_criteria": ["正文必须推进目标锁"],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
    }
    run_novel_generation.save_longform_state(run_dir, state)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=4),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **_kwargs: {"risk_detected": False},
    )

    captured = {}

    def _fake_run_subprocess(*_args, **kwargs):
        captured["start"] = kwargs["start"]
        captured["count"] = kwargs["count"]
        project.current_chapter = 4
        report_dir = project_dir / "consistency_reports"
        report_dir.mkdir(parents=True)
        (report_dir / "ch004_consistency.json").write_text(
            '{"report":{"issue_types":[],"blocking_issues":[]}}',
            encoding="utf-8",
        )
        return 0

    def _fake_finalize(**kwargs):
        captured["final_state"] = kwargs["state"]
        return 77

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )
    monkeypatch.setattr(run_novel_generation, "_finalize_longform_run", _fake_finalize)

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 77
    assert captured["start"] == 4
    assert captured["count"] == 1
    assert captured["final_state"]["pending_revision_validation"] is None
    assert captured["final_state"]["next_chapter_guidance"] == ""
    assert captured["final_state"]["chapters_completed"] == 4


def test_finalize_longform_run_reconciles_high_watermark_from_disk(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 50
    project.current_chapter = 40
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for chapter_number in range(1, 51):
        (chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{chapter_number}章"),
            encoding="utf-8",
        )
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=10,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 40
    state["chapters_completed_high_watermark"] = 40

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=10),
        load_project=lambda _project_id: project,
    )

    class _FakeExperiencePool:
        root_dir = temp_project_dir / "global_experience"
        usage_path = root_dir / "usage.jsonl"

        def load_cases(self):
            return []

    monkeypatch.setattr(run_novel_generation, "cmd_export", lambda _args: None)
    monkeypatch.setattr(run_novel_generation, "GlobalExperiencePool", _FakeExperiencePool)

    result = run_novel_generation._finalize_longform_run(
        run_dir=run_dir,
        state=state,
        project_id=project.id,
        command=["--generate-full"],
        run_started_at=run_novel_generation.datetime.now(),
        config_mgr=fake_config,
    )

    persisted = run_novel_generation.load_longform_state(run_dir)
    status = read_status(run_dir)
    assert result == 0
    assert persisted["chapters_completed"] == 50
    assert persisted["chapters_completed_high_watermark"] == 50
    assert status["chapters_completed"] == 50
    audit_path = Path(status["memory_audit_path"])
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["schema_version"] == "young_writer.memory_audit.v1"
    assert audit["chapters"]["chapter_files_count"] == 50
    assert audit["memory_layers"]["plot_summaries"]["count"] == 0


def test_continue_longform_run_reconciles_stale_progress_before_revision_validation(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 4
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for chapter_number in (1, 2, 3):
        (chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{chapter_number}章"),
            encoding="utf-8",
        )
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 1
    state["pending_revision_validation"] = {
        "chapter_number": 4,
        "issue_types": ["goal_lock_false_inheritance"],
        "success_criteria": ["正文必须推进目标锁"],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
    }
    run_novel_generation.save_longform_state(run_dir, state)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=4),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **_kwargs: {"risk_detected": False},
    )

    captured = {}

    def _fake_run_subprocess(*_args, **kwargs):
        captured["start"] = kwargs["start"]
        captured["count"] = kwargs["count"]
        return 99

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 99
    assert captured["start"] == 4
    assert captured["count"] == 1


def test_continue_longform_run_uses_contiguous_saved_prefix_for_next_start(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 4
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for chapter_number in (1, 3):
        (chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{chapter_number}章"),
            encoding="utf-8",
        )
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 3
    run_novel_generation.save_longform_state(run_dir, state)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=4),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )

    captured = {}

    def _fake_run_subprocess(*_args, **kwargs):
        captured["start"] = kwargs["start"]
        captured["count"] = kwargs["count"]
        return 95

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 95
    assert captured["start"] == 2
    assert captured["count"] == 3


def test_continue_longform_run_keeps_revision_validation_when_report_missing(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 4
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 3
    state["pending_revision_validation"] = {
        "chapter_number": 4,
        "issue_types": ["scene_or_timeline_disconnect"],
        "success_criteria": [],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
    }
    run_novel_generation.save_longform_state(run_dir, state)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=4),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", lambda *a, **k: 0
    )

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    persisted = run_novel_generation.load_longform_state(run_dir)
    status = read_status(run_dir)
    assert result == 1
    assert persisted["status"] == "paused"
    assert persisted["current_stage"] == STAGE_CHAPTER_REVIEW
    assert persisted["pending_revision_validation"]["chapter_number"] == 4
    assert status["pause_reason"] == CHECKPOINT_CHAPTER


def test_continue_longform_run_advances_to_newer_pending_revision_validation(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.total_chapters = 4
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for chapter_number in (1, 2, 3):
        (chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{chapter_number}章"),
            encoding="utf-8",
        )
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["chapters_completed"] = 3
    state["chapter_review_mode"] = "auto"
    state["chapter_auto_repair_attempts"] = 2
    state["pending_revision_validation"] = {
        "chapter_number": 4,
        "issue_types": ["scene_or_timeline_disconnect"],
        "success_criteria": [],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
        "auto_repair_attempt": 1,
    }
    run_novel_generation.save_longform_state(run_dir, state)

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=4),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **_kwargs: {"risk_detected": False},
    )

    captured = {"calls": 0}

    def _fake_run_subprocess(*_args, **kwargs):
        captured["calls"] += 1
        captured[f"start_{captured['calls']}"] = kwargs["start"]
        reloaded = run_novel_generation.load_longform_state(run_dir)
        if captured["calls"] == 1:
            reloaded["pending_revision_validation"] = {
                "chapter_number": 4,
                "issue_types": ["scene_or_timeline_disconnect"],
                "success_criteria": [],
                "created_from_checkpoint": CHECKPOINT_CHAPTER,
                "auto_repair_attempt": 2,
            }
            run_novel_generation.save_longform_state(run_dir, reloaded)
            return 0
        project.current_chapter = 4
        report_dir = project_dir / "consistency_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        (chapters_dir / "ch004_第4章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("第1章", "第4章"),
            encoding="utf-8",
        )
        (report_dir / "ch004_consistency.json").write_text(
            '{"report":{"issue_types":[],"blocking_issues":[]}}',
            encoding="utf-8",
        )
        return 0

    def _fake_finalize(**kwargs):
        captured["final_state"] = kwargs["state"]
        return 79

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )
    monkeypatch.setattr(run_novel_generation, "_finalize_longform_run", _fake_finalize)

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 79
    assert captured["calls"] == 2
    assert captured["start_1"] == 4
    assert captured["start_2"] == 4
    assert captured["final_state"]["pending_revision_validation"] is None


def test_cmd_generate_only_applies_chapter_guidance_to_target_chapter(
    temp_project_dir, monkeypatch
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )

    context_calls = []

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            context = {"chapter_number": chapter_number}
            context_calls.append((chapter_number, context))
            return context

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            project.current_chapter = kwargs["number"]
            return SimpleNamespace(
                metadata=SimpleNamespace(
                    file_path=str(project_dir / f"chapter_{kwargs['number']}.md")
                )
            )

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content=f"内容{chapter_number}",
                word_count=1000,
                metadata={
                    "outline_summary": f"概要{chapter_number}",
                    "key_events": [],
                    "character_appearances": [],
                },
                plot_summary={
                    "l1_one_line_summary": f"一句话{chapter_number}",
                    "l2_brief_summary": f"概要{chapter_number}",
                    "l3_key_plot_points": [],
                },
                consistency_report={},
            )
    class _FakeMemoryStore:
        pass

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(
        run_novel_generation,
        "read_status",
        lambda _run_dir: {
            "queued_volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "1",
            }
        },
    )
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "create_longform_memory_store",
        lambda project_dir: _FakeMemoryStore(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "record_memory_after_save",
        lambda *args, **kwargs: 3,
    )
    monkeypatch.setattr(
        run_novel_generation, "_print_statistics", lambda *args, **kwargs: None
    )
    original_checkpoint_payload = run_novel_generation._checkpoint_payload_from_disk

    def _marked_checkpoint_payload(results_file, results):
        payload = original_checkpoint_payload(results_file, results)
        payload["checkpoint_payload_rebuilt"] = True
        return payload

    monkeypatch.setattr(
        run_novel_generation,
        "_checkpoint_payload_from_disk",
        _marked_checkpoint_payload,
    )

    args = argparse.Namespace(
        count=2,
        start=1,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="整卷统一指令",
        chapter_guidance="仅重写第2章的补充指令",
        chapter_guidance_target=2,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)

    assert result == 0
    assert len(context_calls) == 2
    assert context_calls[0][0] == 1
    assert context_calls[0][1]["chapter_number"] == 1
    assert context_calls[0][1]["total_chapters"] == 120
    assert context_calls[0][1]["volume_guidance_payload"]["goal_lock"] == "守住宗门祖地"
    assert context_calls[0][1]["volume_guidance"] == "整卷统一指令"
    assert context_calls[0][1]["generation_packet"]["chapter_number"] == 1
    assert context_calls[0][1]["story_input_validation"]["blocking_issues"] == []
    assert context_calls[1][0] == 2
    assert context_calls[1][1]["volume_guidance"] == "整卷统一指令"
    assert context_calls[1][1]["chapter_guidance"] == "仅重写第2章的补充指令"
    assert project.current_chapter == 2
    results_payload = json.loads(
        (Path(project_dir) / "generation_results.json").read_text(encoding="utf-8")
    )
    assert results_payload["checkpoint_payload_rebuilt"] is True
    status = read_status(run_dir)
    assert status["longform_memory_enabled"] is True
    assert status["longform_memory_store"] == "_FakeMemoryStore"
    assert status["longform_memory_rows_written"] == 3
    assert status["longform_memory_error"] is None


@pytest.mark.parametrize(
    "failure_factory",
    [
        lambda: run_novel_generation.GenerationError("deepseek transport failed"),
        lambda: RuntimeError("deepseek transport failed"),
    ],
)
def test_cmd_generate_stops_controlled_run_on_first_chapter_failure(
    temp_project_dir, monkeypatch, failure_factory
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_progress=lambda chapter: setattr(
            project, "current_chapter", chapter
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )
    context_calls = []

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            context_calls.append(chapter_number)
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            chapters_dir = project_dir / "chapters"
            chapters_dir.mkdir(parents=True, exist_ok=True)
            chapter_path = chapters_dir / f"ch{kwargs['number']:03d}_第{kwargs['number']}章.md"
            chapter_path.write_text(
                COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{kwargs['number']}章"),
                encoding="utf-8",
            )
            return SimpleNamespace(metadata=SimpleNamespace(file_path=str(chapter_path)))

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            if chapter_number == 2:
                raise failure_factory()
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content=f"内容{chapter_number}",
                word_count=1000,
                metadata={
                    "outline_summary": f"概要{chapter_number}",
                    "key_events": [],
                    "character_appearances": [],
                },
                plot_summary={
                    "l1_one_line_summary": f"一句话{chapter_number}",
                    "l2_brief_summary": f"概要{chapter_number}",
                    "l3_key_plot_points": [],
                },
                consistency_report={},
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(run_novel_generation, "read_status", lambda _run_dir: {})
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(
        run_novel_generation,
        "read_status",
        lambda _run_dir: {"longform_state_path": str(run_dir / "longform_state.v1.json")},
    )
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *a, **k: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda **_: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *a, **k: 0)

    args = argparse.Namespace(
        count=3,
        start=1,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        require_llm=True,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)
    results_payload = json.loads(
        (project_dir / "generation_results.json").read_text(encoding="utf-8")
    )
    status = read_status(run_dir)

    assert result == 1
    assert context_calls == [1, 2]
    assert project.current_chapter == 1
    assert results_payload["failed_chapters"][0]["chapter_number"] == 2
    assert [item["chapter_number"] for item in results_payload["chapter_results"]] == [
        1,
        2,
    ]
    assert status["status"] == "failed"
    assert status["return_code"] == 1


def test_cmd_generate_continue_from_uses_saved_chapter_files_as_source_of_truth(
    temp_project_dir, monkeypatch
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(COMPLETE_CHAPTER_ARTIFACT, encoding="utf-8")
    (project_dir / "generation_results.json").write_text(
        json.dumps(
            {
                "chapter_results": [
                    {"chapter_number": 1, "status": "success"},
                    {"chapter_number": 2, "status": "success"},
                ],
                "checkpoints": [1, 2],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=3,
        metadata={},
        outline="沈夜归来",
        world_setting="空间城",
        character_intro="沈夜：主角",
        genre="科幻修真",
    )
    generated_numbers = []
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
        update_project_progress=lambda chapter: setattr(project, "current_chapter", chapter),
    )

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            generated_numbers.append(kwargs["number"])
            return SimpleNamespace(
                metadata=SimpleNamespace(
                    file_path=str(project_dir / f"chapter_{kwargs['number']}.md")
                )
            )

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="沈夜返回空间城。" * 80,
                word_count=1200,
                metadata={"outline_summary": "沈夜返回空间城。", "key_events": []},
                plot_summary={"l2_brief_summary": "沈夜返回空间城。"},
                consistency_report={},
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda project_dir: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *args, **kwargs: 0)
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

    args = argparse.Namespace(
        count=2,
        start=None,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=1,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)

    assert result == 0
    assert generated_numbers == [2]
    assert project.current_chapter == 2


def test_cmd_generate_reconciles_start_from_saved_chapter_files(
    temp_project_dir, monkeypatch
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(COMPLETE_CHAPTER_ARTIFACT, encoding="utf-8")
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=5,
        total_chapters=8,
        metadata={},
        outline="沈夜归来",
        world_setting="空间城",
        character_intro="沈夜：主角",
        genre="科幻修真",
    )
    generated_numbers = []
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
        update_project_progress=lambda chapter: setattr(project, "current_chapter", chapter),
    )

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            generated_numbers.append(kwargs["number"])
            return SimpleNamespace(
                metadata=SimpleNamespace(
                    file_path=str(project_dir / f"chapter_{kwargs['number']}.md")
                )
            )

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="沈夜返回空间城。" * 80,
                word_count=1200,
                metadata={"outline_summary": "沈夜返回空间城。", "key_events": []},
                plot_summary={"l2_brief_summary": "沈夜返回空间城。"},
                consistency_report={},
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda project_dir: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *args, **kwargs: 0)
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

    args = argparse.Namespace(
        count=1,
        start=None,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)

    assert result == 0
    assert generated_numbers == [2]
    assert project.current_chapter == 2


def test_cmd_generate_repairs_sparse_saved_chapter_gap_before_appending_new_work(
    temp_project_dir, monkeypatch
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch001_第1章.md").write_text(COMPLETE_CHAPTER_ARTIFACT, encoding="utf-8")
    (chapters_dir / "ch003_第3章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT.replace("# 第1章", "# 第3章").replace(
            "> 第1章 |", "> 第3章 |"
        ),
        encoding="utf-8",
    )
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=8,
        metadata={},
        outline="沈夜归来",
        world_setting="空间城",
        character_intro="沈夜：主角",
        genre="科幻修真",
    )
    generated_numbers = []
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
        update_project_progress=lambda chapter: setattr(project, "current_chapter", chapter),
    )

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            generated_numbers.append(kwargs["number"])
            return SimpleNamespace(
                metadata=SimpleNamespace(
                    file_path=str(project_dir / f"chapter_{kwargs['number']}.md")
                )
            )

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="沈夜返回空间城。" * 80,
                word_count=1200,
                metadata={"outline_summary": "沈夜返回空间城。", "key_events": []},
                plot_summary={"l2_brief_summary": "沈夜返回空间城。"},
                consistency_report={},
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda project_dir: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *args, **kwargs: 0)
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

    args = argparse.Namespace(
        count=1,
        start=None,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)

    assert result == 0
    assert generated_numbers == [2]
    assert project.current_chapter == 3


def test_cmd_generate_resyncs_final_progress_after_mixed_skip_and_regenerate(
    temp_project_dir, monkeypatch
):
    project_dir = temp_project_dir / "project"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "ch003_第3章.md").write_text(
        COMPLETE_CHAPTER_ARTIFACT.replace("# 第1章", "# 第3章").replace(
            "> 第1章 |", "> 第3章 |"
        ),
        encoding="utf-8",
    )
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=8,
        metadata={},
        outline="沈夜归来",
        world_setting="空间城",
        character_intro="沈夜：主角",
        genre="科幻修真",
    )
    generated_numbers = []
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
        update_project_progress=lambda chapter: setattr(project, "current_chapter", chapter),
    )

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            generated_numbers.append(kwargs["number"])
            chapter_number = kwargs["number"]
            chapter_file = chapters_dir / f"ch{chapter_number:03d}_第{chapter_number}章.md"
            chapter_file.write_text(
                COMPLETE_CHAPTER_ARTIFACT.replace("# 第1章", f"# 第{chapter_number}章").replace(
                    "> 第1章 |", f"> 第{chapter_number}章 |"
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(metadata=SimpleNamespace(file_path=str(chapter_file)))

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="沈夜返回空间城。" * 80,
                word_count=1200,
                metadata={"outline_summary": "沈夜返回空间城。", "key_events": []},
                plot_summary={"l2_brief_summary": "沈夜返回空间城。"},
                consistency_report={},
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda project_dir: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *args, **kwargs: 0)
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

    args = argparse.Namespace(
        count=3,
        start=1,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)

    assert result == 0
    assert generated_numbers == [1, 2]
    assert project.current_chapter == 3


def test_cmd_generate_invalid_goal_lock_chapter_does_not_promote_raw_summary_or_continue(
    temp_project_dir,
    monkeypatch,
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )

    context_calls = []
    saved_chapters = []
    saved_plot_summaries = []

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            context = {"chapter_number": chapter_number}
            context_calls.append(chapter_number)
            return context

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            saved_chapters.append(kwargs)
            project.current_chapter = kwargs["number"]

        def save_plot_summary(self, plot_summary):
            saved_plot_summaries.append(plot_summary)
            return

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="韩林只是想起守住宗门祖地，却把篇幅耗在无关闲谈里。",
                word_count=1000,
                metadata={
                    "outline_summary": "韩林为了守住宗门祖地继续推进防线。",
                    "key_events": [],
                    "character_appearances": [],
                },
                plot_summary={
                    "l1_one_line_summary": "韩林守住祖地。",
                    "l2_brief_summary": "韩林为了守住宗门祖地继续推进防线。",
                    "l3_key_plot_points": [],
                },
                consistency_report={
                    "invalid": True,
                    "summary": "目标锁假继承，正文掉锚。",
                    "issue_types": ["goal_lock_false_inheritance"],
                    "blocking_issues": [
                        "目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"
                    ],
                },
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(
        run_novel_generation,
        "read_status",
        lambda _run_dir: {
            "queued_volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "1",
            },
            "longform_state_path": str(run_dir / "longform_state.v1.json"),
        },
    )
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation, "_print_statistics", lambda *args, **kwargs: None
    )

    longform_state = {
        "run_id": "run-001",
        "current_volume": 1,
        "current_volume_start_chapter": 1,
        "current_volume_end_chapter": 60,
        "volume_plan": [
            {
                "volume_index": 1,
                "start_chapter": 1,
                "end_chapter": 60,
                "chapter_count": 60,
            }
        ],
        "chapters_completed": 0,
        "total_chapters": 120,
        "project_dir": str(project_dir),
        "longform_state_path": str(run_dir / "longform_state.v1.json"),
        "pending_state_path": None,
    }
    run_novel_generation.save_longform_state(run_dir, longform_state)

    args = argparse.Namespace(
        count=2,
        start=1,
        run_id="run-001",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)
    status = read_status(run_dir)

    assert result == 1
    assert context_calls == [1]
    assert saved_chapters == []
    assert saved_plot_summaries == []
    assert project.current_chapter == 0
    assert status.get("pending_state_path")
    assert status.get("chapter_quality_report", {}).get("invalid") is True
    assert status.get("chapter_quality_report", {}).get("issue_types") == [
        "goal_lock_false_inheritance"
    ]


def test_cmd_generate_refreshes_results_on_checkpoint_before_quality_pause(
    temp_project_dir,
    monkeypatch,
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        id="project-123",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_progress=lambda chapter: setattr(
            project, "current_chapter", chapter
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            chapters_dir = project_dir / "chapters"
            chapters_dir.mkdir(parents=True, exist_ok=True)
            chapter_path = chapters_dir / f"ch{kwargs['number']:03d}_第{kwargs['number']}章.md"
            chapter_path.write_text(
                COMPLETE_CHAPTER_ARTIFACT.replace("第1章", f"第{kwargs['number']}章"),
                encoding="utf-8",
            )
            return SimpleNamespace(metadata=SimpleNamespace(file_path=str(chapter_path)))

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            invalid = chapter_number == 2
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content=f"内容{chapter_number}",
                word_count=1000,
                metadata={
                    "outline_summary": f"概要{chapter_number}",
                    "key_events": [],
                    "character_appearances": [],
                },
                plot_summary={
                    "l1_one_line_summary": f"一句话{chapter_number}",
                    "l2_brief_summary": f"概要{chapter_number}",
                    "l3_key_plot_points": [],
                },
                consistency_report={
                    "invalid": invalid,
                    "blocking_issues": ["第2章断裂"] if invalid else [],
                    "issue_types": ["scene_or_timeline_disconnect"] if invalid else [],
                    "graph_diff_details": {"recommended_action": "rewrite"} if invalid else {},
                },
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *a, **k: None)
    monkeypatch.setattr(run_novel_generation, "create_longform_memory_store", lambda **_: None)
    monkeypatch.setattr(run_novel_generation, "record_memory_after_save", lambda *a, **k: 0)
    monkeypatch.setattr(
        run_novel_generation,
        "read_status",
        lambda _run_dir: {"longform_state_path": str(run_dir / "longform_state.v1.json")},
    )
    monkeypatch.setattr(
        run_novel_generation,
        "record_story_graph_after_save",
        lambda **_: SimpleNamespace(snapshot_path=project_dir / "story_graph.json"),
    )
    run_novel_generation.save_longform_state(
        run_dir,
        {
            "run_id": "run-001",
            "status": "running",
            "current_volume": 1,
            "chapters_completed": 0,
            "total_chapters": 120,
            "project_dir": str(project_dir),
            "longform_state_path": str(run_dir / "longform_state.v1.json"),
            "chapter_review_mode": "manual",
        },
    )

    result = run_novel_generation.cmd_generate(
        argparse.Namespace(
            count=2,
            start=1,
            run_id="run-001",
            run_dir=str(run_dir),
            continue_from=None,
            dry_run=False,
            no_auto_feedback=True,
            volume_guidance="",
            chapter_guidance="",
            chapter_guidance_target=None,
            require_llm=False,
            log_level="INFO",
        )
    )

    results_payload = json.loads(
        (project_dir / "generation_results.json").read_text(encoding="utf-8")
    )
    checkpoint_payload = json.loads(
        (project_dir / "generation_checkpoint.json").read_text(encoding="utf-8")
    )
    status = read_status(run_dir)

    assert result == 1
    assert status["status"] == "paused"
    assert results_payload["checkpoints"] == [1]
    assert checkpoint_payload["checkpoints"] == [1]
    assert [item["chapter_number"] for item in results_payload["chapter_results"]] == [1]


def test_cmd_generate_plain_invalid_chapter_records_structured_quality_failure(
    temp_project_dir,
    monkeypatch,
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        id="project-plain",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )
    saved_chapters = []
    story_graph_calls = []

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            saved_chapters.append(kwargs)

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="韩林没有承接上一章危机。",
                word_count=1000,
                metadata={
                    "rewrite_history": [
                        {
                            "attempt": 0,
                            "mode": "initial",
                            "invalid": True,
                            "issue_types": ["scene_or_timeline_disconnect"],
                        },
                        {
                            "attempt": 1,
                            "mode": "targeted_full_rewrite",
                            "invalid": True,
                            "issue_types": ["scene_or_timeline_disconnect"],
                        },
                    ]
                },
                consistency_report={
                    "invalid": True,
                    "summary": "章节与前文严重割裂",
                    "issue_types": ["scene_or_timeline_disconnect"],
                    "hard_gate_issue_types": ["scene_or_timeline_disconnect"],
                    "blocking_issues": ["上一章后果未被承接。"],
                    "rewrite_attempted": True,
                    "rewrite_succeeded": False,
                    "rewrite_history": [
                        {
                            "attempt": 1,
                            "mode": "targeted_full_rewrite",
                            "invalid": True,
                            "issue_types": ["scene_or_timeline_disconnect"],
                        }
                    ],
                },
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, allow_fallback=True: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation, "_print_statistics", lambda *args, **kwargs: None
    )

    args = argparse.Namespace(
        count=1,
        start=1,
        run_id=None,
        run_dir=None,
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        require_llm=False,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)
    results = json.loads((project_dir / "generation_results.json").read_text())

    assert result == 1
    assert saved_chapters == []
    error = results["failed_chapters"][0]["error"]
    assert "issue_types: scene_or_timeline_disconnect" in error
    assert "hard_gate_issue_types: scene_or_timeline_disconnect" in error
    assert "blocking_issues:" in error
    assert "rewrite_history:" in error


def test_cmd_generate_memory_write_failure_is_non_fatal(
    temp_project_dir,
    monkeypatch,
):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-memory"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-memory",
        title="演示项目",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(
            output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")
        ),
        update_project_metadata=lambda payload: project.metadata.update(payload),
    )
    saved_chapters = []
    story_graph_calls = []
    narrative_state_calls = []

    class _FakeChapterManager:
        def build_context(self, chapter_number):
            return {"chapter_number": chapter_number}

        def save_consistency_report(self, **_kwargs):
            return None

        def save_chapter(self, **kwargs):
            saved_chapters.append(kwargs)
            project.current_chapter = kwargs["number"]
            return SimpleNamespace(
                metadata=SimpleNamespace(file_path=str(project_dir / "chapter_1.md"))
            )

        def save_plot_summary(self, _plot_summary):
            return None

    class _FakeGenerator:
        def generate_chapter(
            self, chapter_number, context, previous_summary="", writing_options=None
        ):
            return GeneratedChapter(
                number=chapter_number,
                title=f"第{chapter_number}章",
                content="韩林守住宗门祖地。",
                word_count=1000,
                metadata={
                    "outline_summary": "韩林守住宗门祖地。",
                    "key_events": [],
                    "character_appearances": [],
                },
                plot_summary={
                    "l1_one_line_summary": "韩林守住祖地。",
                    "l2_brief_summary": "韩林守住宗门祖地。",
                    "l3_key_plot_points": [],
                },
                consistency_report={},
            )

    class _FakeMemoryStore:
        pass

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None)
    )
    monkeypatch.setattr(
        run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object()
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_chapter_manager",
        lambda _project_id, base_dir_override=None: _FakeChapterManager(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client, **_kwargs: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "create_longform_memory_store",
        lambda project_dir: _FakeMemoryStore(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "record_memory_after_save",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("memory down")),
    )
    def _record_story_graph_after_save(**kwargs):
        story_graph_calls.append(kwargs)
        return {
            "snapshot_path": str(project_dir / "story_graph" / "snapshots" / "ch001.json")
        }

    monkeypatch.setattr(
        run_novel_generation,
        "record_story_graph_after_save",
        _record_story_graph_after_save,
    )

    def _record_narrative_state_after_save(**kwargs):
        narrative_state_calls.append(kwargs)
        return {
            "current_path": str(project_dir / "narrative_state" / "current.json"),
            "snapshot_path": str(
                project_dir / "narrative_state" / "snapshots" / "ch001.json"
            ),
        }

    monkeypatch.setattr(
        run_novel_generation,
        "record_narrative_state_after_save",
        _record_narrative_state_after_save,
    )
    monkeypatch.setattr(
        run_novel_generation, "_print_statistics", lambda *args, **kwargs: None
    )

    args = argparse.Namespace(
        count=1,
        start=1,
        run_id="run-memory",
        run_dir=str(run_dir),
        continue_from=None,
        dry_run=False,
        no_auto_feedback=True,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
        require_llm=False,
        log_level="INFO",
    )

    result = run_novel_generation.cmd_generate(args)
    status = read_status(run_dir)

    assert result == 0
    assert saved_chapters
    assert story_graph_calls[0]["chapter_number"] == 1
    assert narrative_state_calls[0]["chapter_number"] == 1
    assert (
        narrative_state_calls[0]["story_graph_result"]["snapshot_path"]
        == str(project_dir / "story_graph" / "snapshots" / "ch001.json")
    )
    assert status["longform_memory_enabled"] is True
    assert status["longform_memory_error"] == "memory down"
    assert status["narrative_state_snapshot_path"] == str(
        project_dir / "narrative_state" / "snapshots" / "ch001.json"
    )


def test_continue_longform_run_clears_one_shot_chapter_guidance_after_success(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.current_chapter = 4
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    state["current_volume"] = 1
    state["current_volume_start_chapter"] = 1
    state["current_volume_end_chapter"] = 60
    state["chapters_completed"] = 3
    state["next_chapter_guidance"] = "只对第4章生效的重写指令"
    state["next_chapter_guidance_chapter"] = 4
    state["cross_volume_registry"] = {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["回收第一卷宗门裂痕"],
        "dangling_settings": ["远古秘境现世"],
    }

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **kwargs: {"risk_detected": False},
    )
    monkeypatch.setattr(
        run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 11
    )

    captured = {}

    def _fake_run_subprocess(
        args,
        *,
        project_id,
        run_id,
        run_dir,
        start,
        count,
        writing_options,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
    ):
        captured["volume_guidance"] = volume_guidance
        captured["chapter_guidance"] = chapter_guidance
        captured["chapter_guidance_target"] = chapter_guidance_target
        captured["start"] = start
        captured["count"] = count
        return 0

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    args = argparse.Namespace(log_level="INFO")
    result = run_novel_generation._continue_longform_run(
        args,
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 11
    assert captured["volume_guidance"].startswith("- 跨卷未完成目标: 守住宗门祖地")
    assert captured["chapter_guidance"] == "只对第4章生效的重写指令"
    assert captured["chapter_guidance_target"] == 4
    assert state["next_chapter_guidance"] == ""
    assert state["next_chapter_guidance_chapter"] is None


def test_continue_longform_run_keeps_one_shot_chapter_guidance_after_failure(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    state["current_volume"] = 1
    state["current_volume_start_chapter"] = 1
    state["current_volume_end_chapter"] = 60
    state["chapters_completed"] = 3
    state["next_chapter_guidance"] = "失败后也要保留的第4章重写指令"
    state["next_chapter_guidance_chapter"] = 4
    state["cross_volume_registry"] = {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": [],
        "dangling_settings": [],
    }

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )

    captured = {}

    def _fake_run_subprocess(
        args,
        *,
        project_id,
        run_id,
        run_dir,
        start,
        count,
        writing_options,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
    ):
        captured["volume_guidance"] = volume_guidance
        captured["chapter_guidance"] = chapter_guidance
        captured["chapter_guidance_target"] = chapter_guidance_target
        return 9

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    args = argparse.Namespace(log_level="INFO")
    result = run_novel_generation._continue_longform_run(
        args,
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 9
    assert captured["volume_guidance"].startswith("- 跨卷未完成目标: 守住宗门祖地")
    assert captured["chapter_guidance"] == "失败后也要保留的第4章重写指令"
    assert captured["chapter_guidance_target"] == 4
    assert state["next_chapter_guidance"] == "失败后也要保留的第4章重写指令"
    assert state["next_chapter_guidance_chapter"] == 4


def test_continue_longform_run_preserves_child_process_chapter_pause(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project.current_chapter = 3
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
        approval_mode="none",
        auto_approve=True,
    )
    state["current_volume"] = 1
    state["current_volume_start_chapter"] = 1
    state["current_volume_end_chapter"] = 60
    state["chapters_completed"] = 3
    state["next_chapter_guidance"] = "第4章重写指令"
    state["next_chapter_guidance_chapter"] = 4

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )

    def _fake_run_subprocess(*_args, **_kwargs):
        paused = run_novel_generation.load_longform_state(run_dir)
        paused["status"] = "paused"
        paused["current_stage"] = STAGE_CHAPTER_REVIEW
        paused["current_checkpoint"] = CHECKPOINT_CHAPTER
        paused["pending_state_path"] = str(
            run_dir / ".novel_pipeline_demo_chapter_pending.json"
        )
        run_novel_generation.save_longform_state(run_dir, paused)
        return 0

    def _unexpected_finalize(**_kwargs):
        raise AssertionError(
            "chapter_review 暂停不应被父流程当作分卷成功后继续 finalize"
        )

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )
    monkeypatch.setattr(
        run_novel_generation, "_finalize_longform_run", _unexpected_finalize
    )

    result = run_novel_generation._continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    persisted = run_novel_generation.load_longform_state(run_dir)
    assert result == 0
    assert persisted["status"] == "paused"
    assert persisted["current_stage"] == STAGE_CHAPTER_REVIEW
    assert persisted["current_checkpoint"] == CHECKPOINT_CHAPTER
    assert persisted["chapters_completed"] == 3
    assert persisted["next_chapter_guidance"] == "第4章重写指令"


def test_cmd_generate_full_volume_approval_updates_cross_volume_registry(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type="volume_review",
        current_stage="volume.review",
        review_payload={"volume_index": 1},
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 5

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload='{"must_recover":"回收第一卷宗门裂痕","unresolved_goals":["守住宗门祖地"],"open_promises":["揭示魔帝线"],"dangling_settings":["远古秘境现世"]}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 5
    assert captured["state"]["cross_volume_registry"] == {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["揭示魔帝线"],
        "dangling_settings": ["远古秘境现世"],
    }


def test_cmd_generate_full_volume_approval_merges_partial_cross_volume_registry_update(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    state["cross_volume_registry"] = {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["回收第一卷宗门裂痕"],
        "dangling_settings": ["远古秘境现世"],
    }
    run_novel_generation.save_longform_state(run_dir, state)
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type="volume_review",
        current_stage="volume.review",
        review_payload={"volume_index": 1},
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        return 6

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload='{"open_promises":["揭示魔帝线"]}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 6
    assert captured["state"]["cross_volume_registry"] == {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["揭示魔帝线"],
        "dangling_settings": ["远古秘境现世"],
    }


def test_cmd_generate_full_volume_approval_clears_explicit_cross_volume_registry_buckets(
    temp_project_dir, monkeypatch
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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
    state["cross_volume_registry"] = {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["回收第一卷宗门裂痕"],
        "dangling_settings": ["远古秘境现世"],
    }
    run_novel_generation.save_longform_state(run_dir, state)
    paused = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type="volume_review",
        current_stage="volume.review",
        review_payload={"volume_index": 1},
    )

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    captured = {}

    def _fake_continue(args, *, state, run_dir, run_started_at):
        captured["state"] = state
        captured["registry_summary"] = format_longform_registry(
            state.get("cross_volume_registry")
        )
        return 8

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

    args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=paused["pending_state_path"],
        submit_approval="approve",
        approval_payload='{"open_promises":[],"dangling_settings":[]}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    result = run_novel_generation.cmd_generate_full(args)

    assert result == 8
    assert captured["state"]["cross_volume_registry"] == {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": [],
        "dangling_settings": [],
    }
    assert captured["registry_summary"] == "- 跨卷未完成目标: 守住宗门祖地"


def test_longform_smoke_preserves_chapter_review_guidance_then_injects_updated_cross_volume_registry(
    temp_project_dir,
    monkeypatch,
):
    original_continue_longform_run = run_novel_generation._continue_longform_run
    project = _Project()
    project.current_chapter = 4
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    chapter_pause = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload={
            "chapter_number": 4,
            "title": "第四章",
            "summary": "目标锁假继承，正文掉锚。",
            "issue_types": ["goal_lock_false_inheritance"],
            "blocking_issues": [
                "目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"
            ],
        },
    )

    captured_after_chapter = {}

    def _capture_after_chapter(args, *, state, run_dir, run_started_at):
        captured_after_chapter["state"] = dict(state)
        return 21

    monkeypatch.setattr(
        run_novel_generation, "_continue_longform_run", _capture_after_chapter
    )

    chapter_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=chapter_pause["pending_state_path"],
        submit_approval="revise",
        approval_payload='{"chapter_rewrite_guidance":"重写正文推进链，确保关键行动持续服务守住宗门祖地。"}',
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    chapter_result = run_novel_generation.cmd_generate_full(chapter_args)

    assert chapter_result == 21
    assert captured_after_chapter["state"]["next_chapter_guidance"] == (
        "重写正文推进链，确保关键行动持续服务守住宗门祖地。"
    )
    assert captured_after_chapter["state"]["next_chapter_guidance_chapter"] == 4

    post_chapter_state = run_novel_generation.load_longform_state(run_dir)
    post_chapter_state["current_volume"] = 1
    post_chapter_state["current_volume_start_chapter"] = 1
    post_chapter_state["current_volume_end_chapter"] = 60
    post_chapter_state["chapters_completed"] = 60
    run_novel_generation.save_longform_state(run_dir, post_chapter_state)

    volume_pause = record_pause(
        run_dir=run_dir,
        longform_state=post_chapter_state,
        checkpoint_type="volume_review",
        current_stage="volume.review",
        review_payload={"volume_index": 1},
    )

    captured_after_volume = {}

    def _capture_after_volume(args, *, state, run_dir, run_started_at):
        captured_after_volume["state"] = dict(state)
        return 22

    monkeypatch.setattr(
        run_novel_generation, "_continue_longform_run", _capture_after_volume
    )

    volume_args = argparse.Namespace(
        run_id="run-001",
        run_dir=str(run_dir),
        resume_state=volume_pause["pending_state_path"],
        submit_approval="approve",
        approval_payload=(
            '{"must_recover":"回收第一卷宗门裂痕",'
            '"unresolved_goals":["守住宗门祖地"],'
            '"open_promises":["揭示魔帝线"],'
            '"dangling_settings":["远古秘境现世"]}'
        ),
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )

    volume_result = run_novel_generation.cmd_generate_full(volume_args)

    assert volume_result == 22
    assert captured_after_volume["state"]["cross_volume_registry"] == {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["揭示魔帝线"],
        "dangling_settings": ["远古秘境现世"],
    }

    next_volume_state = captured_after_volume["state"]
    next_volume_state["current_volume"] = 2
    next_volume_state["current_volume_start_chapter"] = 61
    next_volume_state["current_volume_end_chapter"] = 120
    next_volume_state["chapters_completed"] = 60
    next_volume_state["next_chapter_guidance"] = ""
    next_volume_state["next_chapter_guidance_chapter"] = None

    captured_subprocess = {}
    monkeypatch.setattr(
        run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        run_novel_generation,
        "build_volume_risk_report",
        lambda **kwargs: {"risk_detected": False},
    )
    monkeypatch.setattr(
        run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True
    )
    monkeypatch.setattr(
        run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 23
    )
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {}
    )

    def _fake_run_subprocess(
        args,
        *,
        project_id,
        run_id,
        run_dir,
        start,
        count,
        writing_options,
        volume_guidance="",
        chapter_guidance="",
        chapter_guidance_target=None,
    ):
        captured_subprocess["volume_guidance"] = volume_guidance
        captured_subprocess["chapter_guidance"] = chapter_guidance
        captured_subprocess["chapter_guidance_target"] = chapter_guidance_target
        return 0

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess
    )

    continue_result = original_continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=next_volume_state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert continue_result == 23
    assert captured_subprocess["volume_guidance"].startswith(
        "- 跨卷未完成目标: 守住宗门祖地"
    )
    assert "尚未回收承诺/伏笔: 揭示魔帝线" in captured_subprocess["volume_guidance"]
    assert "已引入但未桥接设定: 远古秘境现世" in captured_subprocess["volume_guidance"]
    assert captured_subprocess["chapter_guidance"] == ""
    assert captured_subprocess["chapter_guidance_target"] is None


@pytest.mark.parametrize(
    "case",
    _load_longform_resume_golden_cases(),
    ids=lambda case: case["name"],
)
def test_longform_resume_golden_cases(temp_project_dir, monkeypatch, case):
    original_continue_longform_run = run_novel_generation._continue_longform_run
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
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

    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
        load_project=lambda project_id: project,
        _save_project=lambda project_obj: None,
    )
    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)

    if case["type"] == "chapter_double_revise":
        first_pause = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_CHAPTER,
            current_stage=STAGE_CHAPTER_REVIEW,
            review_payload=case["first_review_payload"],
        )

        first_capture = {}

        def _capture_first(args, *, state, run_dir, run_started_at):
            first_capture["state"] = dict(state)
            return 31

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _capture_first
        )

        first_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=first_pause["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(
                case["first_approval_payload"], ensure_ascii=False
            ),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        first_result = run_novel_generation.cmd_generate_full(first_args)
        assert first_result == 31
        assert (
            first_capture["state"]["next_chapter_guidance_chapter"]
            == case["chapter_number"]
        )
        for snippet in case["expected_first_guidance_contains"]:
            assert snippet in first_capture["state"]["next_chapter_guidance"]
        _assert_approval_history_entries(
            first_capture["state"]["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "revise",
                    "payload": case["first_approval_payload"],
                }
            ],
        )

        updated_state = run_novel_generation.load_longform_state(run_dir)
        second_pause = record_pause(
            run_dir=run_dir,
            longform_state=updated_state,
            checkpoint_type=CHECKPOINT_CHAPTER,
            current_stage=STAGE_CHAPTER_REVIEW,
            review_payload=case["second_review_payload"],
        )

        second_capture = {}

        def _capture_second(args, *, state, run_dir, run_started_at):
            second_capture["state"] = dict(state)
            return 32

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _capture_second
        )

        second_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=second_pause["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(
                case["second_approval_payload"], ensure_ascii=False
            ),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        second_result = run_novel_generation.cmd_generate_full(second_args)
        assert second_result == 32
        assert (
            second_capture["state"]["next_chapter_guidance_chapter"]
            == case["chapter_number"]
        )
        for snippet in case["expected_second_guidance_contains"]:
            assert snippet in second_capture["state"]["next_chapter_guidance"]
        for snippet in case.get("expected_second_guidance_excludes", []):
            assert snippet not in second_capture["state"]["next_chapter_guidance"]
        _assert_approval_history_entries(
            second_capture["state"]["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "revise",
                    "payload": case["first_approval_payload"],
                },
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "revise",
                    "payload": case["second_approval_payload"],
                },
            ],
        )
        return

    if case["type"] == "volume_registry_handoff":
        state["current_volume"] = case["current_volume"]
        state["current_volume_start_chapter"] = case["current_volume_start_chapter"]
        state["current_volume_end_chapter"] = case["current_volume_end_chapter"]
        state["chapters_completed"] = case["chapters_completed"]
        state["cross_volume_registry"] = dict(case["existing_registry"])
        run_novel_generation.save_longform_state(run_dir, state)

        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type="volume_review",
            current_stage="volume.review",
            review_payload=case["volume_review_payload"],
        )

        captured_after_volume = {}

        def _capture_after_volume(args, *, state, run_dir, run_started_at):
            captured_after_volume["state"] = dict(state)
            return 41

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _capture_after_volume
        )

        volume_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="approve",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        volume_result = run_novel_generation.cmd_generate_full(volume_args)
        assert volume_result == 41
        _assert_approval_history_entries(
            captured_after_volume["state"]["approval_history"],
            [
                {
                    "checkpoint_type": "volume_review",
                    "action": "approve",
                    "payload": case["approval_payload"],
                }
            ],
        )
        registry_summary = format_longform_registry(
            captured_after_volume["state"]["cross_volume_registry"]
        )
        for snippet in case["expected_registry_summary_contains"]:
            assert snippet in registry_summary

        next_volume_state = dict(captured_after_volume["state"])
        next_volume_state["current_volume"] = case["current_volume"] + 1
        next_volume_state["current_volume_start_chapter"] = 61
        next_volume_state["current_volume_end_chapter"] = 120
        next_volume_state["chapters_completed"] = case["chapters_completed"]
        next_volume_state["next_chapter_guidance"] = ""
        next_volume_state["next_chapter_guidance_chapter"] = None

        captured_subprocess = {}
        monkeypatch.setattr(
            run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None
        )
        monkeypatch.setattr(
            run_novel_generation,
            "build_volume_risk_report",
            lambda **kwargs: {"risk_detected": False},
        )
        monkeypatch.setattr(
            run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True
        )
        monkeypatch.setattr(
            run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 42
        )
        monkeypatch.setattr(
            run_novel_generation,
            "_resolve_active_writing_options",
            lambda _cfg, _args: {},
        )

        def _fake_run_subprocess(
            args,
            *,
            project_id,
            run_id,
            run_dir,
            start,
            count,
            writing_options,
            volume_guidance="",
            chapter_guidance="",
            chapter_guidance_target=None,
        ):
            captured_subprocess["volume_guidance"] = volume_guidance
            captured_subprocess["chapter_guidance"] = chapter_guidance
            captured_subprocess["chapter_guidance_target"] = chapter_guidance_target
            return 0

        monkeypatch.setattr(
            run_novel_generation,
            "_run_volume_generation_subprocess",
            _fake_run_subprocess,
        )

        continue_result = original_continue_longform_run(
            argparse.Namespace(log_level="INFO"),
            state=next_volume_state,
            run_dir=run_dir,
            run_started_at=run_novel_generation.datetime.now(),
        )

        assert continue_result == 42
        for snippet in case["expected_registry_summary_contains"]:
            assert snippet in captured_subprocess["volume_guidance"]
        for snippet in case["expected_volume_guidance_contains"]:
            assert snippet in captured_subprocess["volume_guidance"]
        assert captured_subprocess["chapter_guidance"] == ""
        assert captured_subprocess["chapter_guidance_target"] is None
        return

    if case["type"] == "chapter_reject_then_revise":
        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_CHAPTER,
            current_stage=STAGE_CHAPTER_REVIEW,
            review_payload=case["review_payload"],
        )

        def _unexpected_continue(*args, **kwargs):
            raise AssertionError("reject 分支不应继续长篇生成")

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _unexpected_continue
        )

        reject_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="reject",
            approval_payload=json.dumps(case["reject_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        reject_result = run_novel_generation.cmd_generate_full(reject_args)
        reject_status = read_status(run_dir)
        assert reject_result == 0
        assert reject_status["status"] == case["expected_reject_status"]["status"]
        assert (
            reject_status["current_stage"]
            == case["expected_reject_status"]["current_stage"]
        )
        assert reject_status["pending_state_path"] == paused["pending_state_path"]
        rejected_state = run_novel_generation.load_longform_state(run_dir)
        _assert_approval_history_entries(
            rejected_state["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "reject",
                    "payload": case["reject_payload"],
                }
            ],
        )

        revise_capture = {}

        def _capture_revise(args, *, state, run_dir, run_started_at):
            revise_capture["state"] = dict(state)
            return 51

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _capture_revise
        )

        revise_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(case["revise_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        revise_result = run_novel_generation.cmd_generate_full(revise_args)
        assert revise_result == 51
        assert (
            revise_capture["state"]["next_chapter_guidance_chapter"]
            == case["chapter_number"]
        )
        for snippet in case["expected_revise_guidance_contains"]:
            assert snippet in revise_capture["state"]["next_chapter_guidance"]
        _assert_approval_history_entries(
            revise_capture["state"]["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "reject",
                    "payload": case["reject_payload"],
                },
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "revise",
                    "payload": case["revise_payload"],
                },
            ],
        )
        return

    if case["type"] == "volume_registry_second_volume_merge_clear":
        state["current_volume"] = case["current_volume"]
        state["current_volume_start_chapter"] = case["current_volume_start_chapter"]
        state["current_volume_end_chapter"] = case["current_volume_end_chapter"]
        state["chapters_completed"] = case["chapters_completed"]
        state["total_volumes"] = case["total_volumes"]
        state["volume_plan"] = list(case["volume_plan"])
        state["cross_volume_registry"] = dict(case["existing_registry"])
        run_novel_generation.save_longform_state(run_dir, state)

        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type="volume_review",
            current_stage="volume.review",
            review_payload=case["volume_review_payload"],
        )

        captured_after_volume = {}

        def _capture_after_volume(args, *, state, run_dir, run_started_at):
            captured_after_volume["state"] = dict(state)
            return 61

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _capture_after_volume
        )

        volume_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="approve",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        volume_result = run_novel_generation.cmd_generate_full(volume_args)
        assert volume_result == 61
        _assert_approval_history_entries(
            captured_after_volume["state"]["approval_history"],
            [
                {
                    "checkpoint_type": "volume_review",
                    "action": "approve",
                    "payload": case["approval_payload"],
                }
            ],
        )
        assert (
            captured_after_volume["state"]["cross_volume_registry"]
            == case["expected_registry_after_merge"]
        )
        registry_summary = format_longform_registry(
            captured_after_volume["state"]["cross_volume_registry"]
        )
        for snippet in case["expected_registry_summary_contains"]:
            assert snippet in registry_summary
        for snippet in case.get("expected_registry_summary_excludes", []):
            assert snippet not in registry_summary
        return

    if case["type"] == "risk_reject":
        state["current_volume"] = case["current_volume"]
        state["chapters_completed"] = case["chapters_completed"]
        state["risk_report_path"] = case["risk_report_path"]
        run_novel_generation.save_longform_state(run_dir, state)

        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type="risk_review",
            current_stage="risk.pause",
            review_payload=case["review_payload"],
        )

        def _unexpected_continue(*args, **kwargs):
            raise AssertionError("risk reject 分支不应继续长篇生成")

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _unexpected_continue
        )

        reject_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="reject",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        reject_result = run_novel_generation.cmd_generate_full(reject_args)
        status = read_status(run_dir)
        assert reject_result == 0
        assert status["status"] == case["expected_status"]["status"]
        assert status["current_stage"] == case["expected_status"]["current_stage"]
        assert status["pending_state_path"] == paused["pending_state_path"]
        persisted_state = run_novel_generation.load_longform_state(run_dir)
        assert persisted_state["risk_report_path"] == case["risk_report_path"]
        _assert_approval_history_entries(
            persisted_state["approval_history"],
            [
                {
                    "checkpoint_type": "risk_review",
                    "action": "reject",
                    "payload": case["approval_payload"],
                }
            ],
        )
        return

    if case["type"] == "risk_revise_to_volume_review":
        state["current_volume"] = case["current_volume"]
        state["chapters_completed"] = case["chapters_completed"]
        state["risk_report_path"] = case["risk_report_path"]
        run_novel_generation.save_longform_state(run_dir, state)

        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type="risk_review",
            current_stage="risk.pause",
            review_payload=case["review_payload"],
        )

        captured_pause = {}

        def _fake_pause_for_volume_review(**kwargs):
            captured_pause["state"] = dict(kwargs["state"])
            return 71

        monkeypatch.setattr(
            run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True
        )
        monkeypatch.setattr(
            run_novel_generation,
            "_pause_for_volume_review",
            _fake_pause_for_volume_review,
        )

        revise_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        revise_result = run_novel_generation.cmd_generate_full(revise_args)
        assert revise_result == 71
        persisted_state = run_novel_generation.load_longform_state(run_dir)
        assert (
            persisted_state["current_stage"]
            == case["expected_intermediate_state"]["current_stage"]
        )
        assert (
            persisted_state["risk_report_path"]
            is case["expected_intermediate_state"]["risk_report_path"]
        )
        _assert_approval_history_entries(
            persisted_state["approval_history"],
            [
                {
                    "checkpoint_type": "risk_review",
                    "action": "revise",
                    "payload": case["approval_payload"],
                }
            ],
        )
        assert (
            captured_pause["state"]["current_stage"]
            == case["expected_pause_call"]["state_current_stage"]
        )
        assert (
            captured_pause["state"]["current_volume"]
            == case["expected_pause_call"]["current_volume"]
        )
        return

    if case["type"] == "outline_reject":
        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_OUTLINE,
            current_stage="outline.review",
            review_payload=case["review_payload"],
        )

        def _unexpected_continue(*args, **kwargs):
            raise AssertionError("outline reject 分支不应继续长篇生成")

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _unexpected_continue
        )

        reject_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="reject",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        reject_result = run_novel_generation.cmd_generate_full(reject_args)
        status = read_status(run_dir)
        assert reject_result == 0
        assert status["status"] == case["expected_status"]["status"]
        assert status["current_stage"] == case["expected_status"]["current_stage"]
        assert status["pending_state_path"] == paused["pending_state_path"]
        assert project.outline == "outline"
        assert project.world_setting == "world"
        assert project.character_intro == "characters"
        persisted_state = run_novel_generation.load_longform_state(run_dir)
        _assert_approval_history_entries(
            persisted_state["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_OUTLINE,
                    "action": "reject",
                    "payload": case["approval_payload"],
                }
            ],
        )
        return

    if case["type"] == "outline_revise":
        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_OUTLINE,
            current_stage="outline.review",
            review_payload=case["review_payload"],
        )

        captured = {}

        def _fake_continue(args, *, state, run_dir, run_started_at):
            captured["state"] = dict(state)
            return 81

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _fake_continue
        )

        revise_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        revise_result = run_novel_generation.cmd_generate_full(revise_args)
        assert revise_result == 81
        for field_name, expected in case["expected_project_fields"].items():
            assert getattr(project, field_name) == expected
        assert (
            captured["state"]["approved_outline"]
            is case["expected_state"]["approved_outline"]
        )
        assert (
            captured["state"]["current_stage"]
            == case["expected_state"]["current_stage"]
        )
        assert (
            captured["state"]["outline_snapshot"]["outline"]
            == case["expected_project_fields"]["outline"]
        )
        _assert_approval_history_entries(
            captured["state"]["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_OUTLINE,
                    "action": "revise",
                    "payload": case["approval_payload"],
                }
            ],
        )
        return

    if case["type"] == "outline_approve":
        paused = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_OUTLINE,
            current_stage="outline.review",
            review_payload=case["review_payload"],
        )

        captured = {}

        def _fake_continue(args, *, state, run_dir, run_started_at):
            captured["state"] = dict(state)
            return 82

        monkeypatch.setattr(
            run_novel_generation, "_continue_longform_run", _fake_continue
        )

        approve_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=paused["pending_state_path"],
            submit_approval="approve",
            approval_payload=json.dumps(case["approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        approve_result = run_novel_generation.cmd_generate_full(approve_args)
        assert approve_result == 82
        for field_name, expected in case["expected_project_fields"].items():
            assert getattr(project, field_name) == expected
        assert (
            captured["state"]["approved_outline"]
            is case["expected_state"]["approved_outline"]
        )
        assert (
            captured["state"]["current_stage"]
            == case["expected_state"]["current_stage"]
        )
        assert (
            captured["state"]["outline_snapshot"]["outline"]
            == case["expected_project_fields"]["outline"]
        )
        _assert_approval_history_entries(
            captured["state"]["approval_history"],
            [
                {
                    "checkpoint_type": CHECKPOINT_OUTLINE,
                    "action": "approve",
                    "payload": case["approval_payload"],
                }
            ],
        )
        return

    raise AssertionError(f"Unhandled golden case type: {case['type']}")


def test_auto_repair_guidance_loads_global_experience(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    GlobalExperiencePool().append_case(
        ExperienceCase(
            id="exp_scene_bridge",
            status="verified",
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            lesson="开篇必须先回应上一章后果，再进入新地点。",
            fix="前 300 字承接 previous_tail_signal。",
            success_criteria=["开篇明确回应上一章后果"],
        )
    )

    guidance = run_novel_generation._compile_auto_repair_guidance(
        {
            "issue_types": ["scene_or_timeline_disconnect"],
            "blocking_issues": ["上一章后果未被承接。"],
            "rewrite_plan": {
                "fixes": ["补足开篇承接。"],
                "success_criteria": ["开篇承接上一章后果。"],
            },
        },
        recommended_action="rewrite",
    )

    assert "全局经验池召回" in guidance
    assert "开篇必须先回应上一章后果" in guidance


def test_auto_repair_guidance_returns_capsule_for_helped_attribution(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    GlobalExperiencePool().append_case(
        ExperienceCase(
            id="exp_goal_lock",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
        )
    )

    guidance, capsule = run_novel_generation._compile_auto_repair_guidance_with_capsule(
        {
            "issue_types": ["goal_lock_false_inheritance"],
            "blocking_issues": ["摘要命中但正文掉锚。"],
            "rewrite_plan": {"fixes": ["让目标锁进入正文动作链。"]},
        },
        recommended_action="rewrite",
    )

    assert "目标锁必须在正文动作链里推进" in guidance
    assert capsule["loaded_ids"] == ["exp_goal_lock"]


def test_auto_repair_guidance_includes_quality_gate_failure_evidence():
    guidance = run_novel_generation._compile_auto_repair_guidance(
        {
            "summary": "章节未通过质量闸门",
            "issue_types": ["scene_or_timeline_disconnect"],
            "blocking_issues": [
                "顺畅性问题[地点跳切无承接] 上一章线索「零号监听站」 与当前开篇「主控室」之间缺少地点转换或行动路径交代。"
            ],
            "rewrite_plan": {
                "fixes": ["补足地点变化的过渡动作、路径或抵达说明。"],
                "success_criteria": ["开场地点变化必须带过渡动作或抵达锚点。"],
            },
        },
        recommended_action="rewrite",
    )

    assert "【失败证据】" in guidance
    assert "顺畅性问题[地点跳切无承接]" in guidance
    assert "零号监听站" in guidance
    assert "主控室" in guidance
    assert guidance.index("【失败证据】") < guidance.index("补足地点变化")


def test_auto_repair_guidance_includes_smoothness_message_without_blocking_issue():
    guidance = run_novel_generation._compile_auto_repair_guidance(
        {
            "summary": "章节未通过质量闸门",
            "issue_types": ["scene_or_timeline_disconnect"],
            "smoothness_details": [
                {
                    "category": "地点跳切无承接",
                    "message": "上一章线索「码头」与当前开篇「档案室」之间缺少行动路径交代。",
                }
            ],
            "rewrite_plan": {"fixes": ["补桥。"]},
        },
        recommended_action="rewrite",
    )

    assert "【失败证据】" in guidance
    assert "码头" in guidance
    assert "档案室" in guidance


def test_global_experience_failure_is_non_fatal(monkeypatch):
    class _BrokenPool:
        def retrieve(self, **_kwargs):
            raise OSError("pool unavailable")

        def append_case(self, _case):
            raise OSError("pool unavailable")

    monkeypatch.setattr(run_novel_generation, "GlobalExperiencePool", _BrokenPool)

    capsule = run_novel_generation._load_global_experience_capsule(
        {"issue_types": ["scene_or_timeline_disconnect"]}
    )
    capture = run_novel_generation._capture_global_experience_case(
        {
            "chapter_number": 1,
            "issue_types": ["scene_or_timeline_disconnect"],
            "blocking_issues": ["上一章后果未被承接。"],
        },
        project_id="project-a",
        run_id="run-a",
    )

    assert capsule["loaded_ids"] == []
    assert capsule["error"] == "pool unavailable"
    assert capture["status"] == "skipped"
    assert capture["error"] == "pool unavailable"


def test_global_experience_capsule_reports_unverified_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    GlobalExperiencePool().append_case(
        ExperienceCase(
            id="exp_captured_scene_bridge",
            status="captured",
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            lesson="开篇必须承接上一章尾部线索。",
            fix="前 300 字回应 previous_tail_signal。",
        )
    )

    capsule = run_novel_generation._load_global_experience_capsule(
        {
            "issue_types": ["scene_or_timeline_disconnect"],
            "blocking_issues": ["上一章后果未被承接。"],
        }
    )

    assert capsule["loaded_ids"] == []
    assert capsule["trace"]["candidate_count"] == 1
    assert capsule["trace"]["filtered_unverified_count"] == 1
    assert capsule["trace"]["reason"] == "only_unverified_generation_guidance"


def test_promote_captured_experience_after_revision_marks_verified(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    pool = GlobalExperiencePool()
    pool.append_case(
        ExperienceCase(
            id="exp_revision_success",
            status="captured",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
        )
    )

    result = run_novel_generation._promote_captured_experience_after_revision(
        pending_validation={
            "chapter_number": 7,
            "issue_types": ["goal_lock_false_inheritance"],
            "captured_issue_types": ["goal_lock_false_inheritance"],
            "captured_experience_id": "exp_revision_success",
            "promotion_candidate": True,
            "success_criteria": ["正文必须推进目标锁"],
        },
        chapter_number=7,
        project_id="project-a",
        run_id="run-a",
    )

    assert result["status"] == "verified"
    promoted = pool.get_case("exp_revision_success")
    assert promoted is not None
    assert promoted.status == "verified"
    assert promoted.evidence["events"][0]["event"] == "chapter_saved_after_revision"


def test_promote_captured_experience_after_revision_rejects_mismatched_issue(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    pool = GlobalExperiencePool()
    pool.append_case(
        ExperienceCase(
            id="exp_revision_mismatch",
            status="captured",
            stage="chapter.review",
            issue_types=["missing_key_events"],
            lesson="关键事件必须写成场景行动。",
        )
    )

    result = run_novel_generation._promote_captured_experience_after_revision(
        pending_validation={
            "chapter_number": 7,
            "issue_types": ["goal_lock_false_inheritance"],
            "captured_issue_types": ["missing_key_events"],
            "captured_experience_id": "exp_revision_mismatch",
            "promotion_candidate": True,
        },
        chapter_number=7,
        project_id="project-a",
        run_id="run-a",
    )

    assert result["reason"] == "issue_type_mismatch"
    assert pool.get_case("exp_revision_mismatch").status == "captured"


def test_promote_captured_experience_requires_explicit_candidate_flag(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    pool = GlobalExperiencePool()
    pool.append_case(
        ExperienceCase(
            id="exp_revision_missing_flag",
            status="captured",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
        )
    )

    result = run_novel_generation._promote_captured_experience_after_revision(
        pending_validation={
            "chapter_number": 7,
            "issue_types": ["goal_lock_false_inheritance"],
            "captured_issue_types": ["goal_lock_false_inheritance"],
            "captured_experience_id": "exp_revision_missing_flag",
        },
        chapter_number=7,
        project_id="project-a",
        run_id="run-a",
    )

    assert result["reason"] == "not_a_promotion_candidate"
    assert pool.get_case("exp_revision_missing_flag").status == "captured"


def test_promote_captured_experience_rejects_non_captured_case(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        ExperienceCase,
        GlobalExperiencePool,
    )

    pool = GlobalExperiencePool()
    pool.append_case(
        ExperienceCase(
            id="exp_revision_rejected",
            status="rejected",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
        )
    )

    result = run_novel_generation._promote_captured_experience_after_revision(
        pending_validation={
            "chapter_number": 7,
            "issue_types": ["goal_lock_false_inheritance"],
            "captured_issue_types": ["goal_lock_false_inheritance"],
            "captured_experience_id": "exp_revision_rejected",
            "promotion_candidate": True,
        },
        chapter_number=7,
        project_id="project-a",
        run_id="run-a",
    )

    assert result["reason"] == "case_not_captured"
    assert result["case_status"] == "rejected"
    assert pool.get_case("exp_revision_rejected").status == "rejected"


def test_promote_captured_experience_rejects_non_generation_case(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUNG_WRITER_EXPERIENCE_DIR", str(tmp_path / "experience"))
    from young_writer.services.experience_pool import (
        EXPERIENCE_KIND_CODE_REPAIR,
        ExperienceCase,
        GlobalExperiencePool,
    )

    pool = GlobalExperiencePool()
    pool.append_case(
        ExperienceCase(
            id="exp_revision_code_repair",
            status="captured",
            stage="chapter.review",
            experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
            issue_types=["goal_lock_false_inheritance"],
            lesson="这条不是生成提示经验。",
        )
    )

    result = run_novel_generation._promote_captured_experience_after_revision(
        pending_validation={
            "chapter_number": 7,
            "issue_types": ["goal_lock_false_inheritance"],
            "captured_issue_types": ["goal_lock_false_inheritance"],
            "captured_experience_id": "exp_revision_code_repair",
            "promotion_candidate": True,
        },
        chapter_number=7,
        project_id="project-a",
        run_id="run-a",
    )

    assert result["reason"] == "case_not_generation_guidance"
    assert result["experience_kind"] == EXPERIENCE_KIND_CODE_REPAIR
    assert pool.get_case("exp_revision_code_repair").status == "captured"


def test_record_successful_experience_promotion_clears_consumed_state_and_status(
    temp_project_dir,
):
    project = _Project()
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id=project.id,
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=project,
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=4,
        approval_mode="none",
        auto_approve=True,
    )
    state["pending_revision_validation"] = {
        "chapter_number": 4,
        "captured_experience_id": "exp_revision_success",
        "promotion_candidate": True,
    }
    state["next_chapter_guidance"] = "重写第4章"
    state["next_chapter_guidance_chapter"] = 4
    state["next_chapter_experience_capsule"] = {"loaded_ids": ["exp_verified"]}
    state["global_experience_trace"] = {"reason": "loaded"}
    state["auto_repair_status"] = "auto_repair_pending"
    state["repair_exhausted_reason"] = "旧错误"
    run_novel_generation.save_longform_state(run_dir, state)
    run_novel_generation._sync_status_longform_fields(run_dir, state)

    promotion_trace = {
        "status": "verified",
        "case_id": "exp_revision_success",
        "chapter_number": 4,
    }
    run_novel_generation._record_successful_experience_promotion(
        run_dir=run_dir,
        longform_state=state,
        promotion_trace=promotion_trace,
    )

    reloaded = run_novel_generation.load_longform_state(run_dir)
    status = read_status(run_dir)
    assert reloaded["pending_revision_validation"] is None
    assert reloaded["next_chapter_guidance"] == ""
    assert reloaded["next_chapter_guidance_chapter"] is None
    assert reloaded["next_chapter_experience_capsule"] == {}
    assert reloaded["global_experience_trace"] is None
    assert reloaded["auto_repair_status"] is None
    assert reloaded["repair_exhausted_reason"] is None
    assert reloaded["global_experience_promotion"] == promotion_trace
    assert status["next_chapter_experience_capsule"] == {}
    assert status["global_experience_trace"] is None
    assert status["global_experience_promotion"] == promotion_trace


def test_continue_longform_pauses_when_pending_auto_repair_attempts_exhausted(
    tmp_path, monkeypatch
):
    project = SimpleNamespace(id="project-123", title="测试项目")
    fake_config = SimpleNamespace(current_project=project)
    state = {
        "chapter_auto_repair_attempts": 1,
        "chapter_auto_repair_attempts_used": {"13": 1},
        "pending_revision_validation": {
            "chapter_number": 13,
            "issue_types": ["missing_key_events"],
            "auto_repair_attempt": 1,
        },
    }
    captured = {}

    monkeypatch.setattr(
        run_novel_generation, "get_config_manager", lambda: fake_config
    )
    monkeypatch.setattr(
        run_novel_generation, "_resolve_active_writing_options", lambda *_: {}
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_reconcile_longform_progress",
        lambda _config, current_state: current_state,
    )

    def _fail_subprocess(*_args, **_kwargs):
        raise AssertionError("subprocess should not run after auto repair exhausted")

    def _fake_pause(**kwargs):
        captured.update(kwargs)
        return 42

    monkeypatch.setattr(
        run_novel_generation, "_run_volume_generation_subprocess", _fail_subprocess
    )
    monkeypatch.setattr(
        run_novel_generation, "_pause_for_revision_validation_failure", _fake_pause
    )

    result = run_novel_generation._continue_longform_run(
        SimpleNamespace(),
        state=state,
        run_dir=tmp_path,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert result == 42
    assert captured["chapter_number"] == 13
    assert captured["issue_types"] == ["missing_key_events"]
    assert "自动修复已达上限 1 次" in captured["reason"]
