"""Tests for run_novel_generation longform resume flows."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.novel_generator import GeneratedChapter
import run_novel_generation
from services.longform_run import (
    CHECKPOINT_CHAPTER,
    CHECKPOINT_OUTLINE,
    STAGE_CHAPTER_REVIEW,
    STAGE_VOLUME_PLAN,
    format_longform_registry,
    initial_longform_state,
    record_pause,
)
from services.run_storage import create_run, read_status

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class _Project:
    def __init__(self):
        self.id = "project-123"
        self.title = "demo"
        self.total_chapters = 120
        self.current_chapter = 3
        self.outline = "outline"
        self.world_setting = "world"
        self.character_intro = "characters"


def _load_longform_resume_golden_cases() -> list[dict]:
    fixture_path = FIXTURES_DIR / "longform_resume_golden_cases.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _assert_approval_history_entries(history: list[dict], expected_entries: list[dict]) -> None:
    assert len(history) == len(expected_entries)
    for actual, expected in zip(history, expected_entries):
        assert actual["checkpoint_type"] == expected["checkpoint_type"]
        assert actual["action"] == expected["action"]
        assert actual["payload"] == expected["payload"]
        assert actual["submitted_at"]


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
    )

    result = run_novel_generation.cmd_generate_full(args)

    status = read_status(run_dir)
    assert result == 7
    assert captured["run_dir"] == run_dir
    assert captured["state"]["current_stage"] == STAGE_VOLUME_PLAN
    assert captured["state"]["pending_state_path"] is None
    assert captured["state"]["next_volume_guidance"] == ""
    assert captured["state"]["next_chapter_guidance"] == "开头先承接上一章战场局势，再重写人物出场。"
    assert captured["state"]["next_chapter_guidance_chapter"] == 4
    assert status["pending_state_path"] is None
    assert status["pause_reason"] is None


def test_cmd_generate_full_rejects_chapter_review_and_stays_paused(temp_project_dir, monkeypatch):
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

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

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


def test_cmd_generate_full_compiles_chapter_rewrite_plan_into_next_guidance(temp_project_dir, monkeypatch):
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
    assert "[body / rebuild_goal_lock_chain / goal_lock_progression]" in captured["state"]["next_chapter_guidance"]
    assert "人工补充：" in captured["state"]["next_chapter_guidance"]
    assert captured["state"]["next_chapter_guidance_chapter"] == 4


def test_run_volume_generation_subprocess_passes_one_shot_chapter_guidance(monkeypatch):
    captured = {}

    def _fake_run(cmd, cwd, check):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["check"] = check
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_novel_generation.subprocess, "run", _fake_run)

    rc = run_novel_generation._run_volume_generation_subprocess(
        argparse.Namespace(log_level="INFO"),
        project_id="project-123",
        run_id="run-001",
        run_dir=run_novel_generation.Path("/tmp/run-001"),
        start=4,
        count=10,
        writing_options={},
        volume_guidance="延续本卷整体压迫感",
        chapter_guidance="补上与上一章战场结尾的衔接。",
        chapter_guidance_target=4,
    )

    assert rc == 0
    assert "--volume-guidance" in captured["cmd"]
    assert "--chapter-guidance" in captured["cmd"]
    assert "--chapter-guidance-target" in captured["cmd"]
    assert "补上与上一章战场结尾的衔接。" in captured["cmd"]


def test_cmd_generate_only_applies_chapter_guidance_to_target_chapter(temp_project_dir, monkeypatch):
    project_dir = temp_project_dir / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    run_dir = temp_project_dir / "runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)

    project = SimpleNamespace(
        id="project-123",
        title="demo",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")),
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
            return

        def save_plot_summary(self, _plot_summary):
            return None

        def save_film_drama_content(self, **_kwargs):
            return None

    class _FakeGenerator:
        def generate_chapter(self, chapter_number, context, previous_summary="", writing_options=None):
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

    class _FakeDerivativeGenerator:
        def sync_derivatives(self, _chapter_range):
            return {
                "video_prompts": [],
                "character_descriptions": [],
                "scene_descriptions": [],
                "podcasts": [],
                "errors": [],
            }

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
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
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(run_novel_generation, "get_chapter_manager", lambda _project_id, base_dir_override=None: _FakeChapterManager())
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "get_derivative_generator", lambda *args, **kwargs: _FakeDerivativeGenerator())
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

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
    assert context_calls[1][0] == 2
    assert context_calls[1][1]["volume_guidance"] == "整卷统一指令"
    assert context_calls[1][1]["chapter_guidance"] == "仅重写第2章的补充指令"
    assert project.current_chapter == 2
    assert (Path(project_dir) / "generation_results.json").exists()


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
        title="demo",
        current_chapter=0,
        total_chapters=120,
        metadata={},
    )
    fake_config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), scripts_dir=str(temp_project_dir / "scripts")),
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
            return None

        def save_film_drama_content(self, **_kwargs):
            return None

    class _FakeGenerator:
        def generate_chapter(self, chapter_number, context, previous_summary="", writing_options=None):
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
                    "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
                },
            )

    monkeypatch.setattr(run_novel_generation, "get_config_manager", lambda: fake_config)
    monkeypatch.setattr(run_novel_generation, "_build_llm_clients", lambda _cfg: (None, None))
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
    monkeypatch.setattr(run_novel_generation, "_create_orchestrator", lambda _cfg, _project_id: object())
    monkeypatch.setattr(run_novel_generation, "get_chapter_manager", lambda _project_id, base_dir_override=None: _FakeChapterManager())
    monkeypatch.setattr(
        run_novel_generation,
        "get_novel_generator",
        lambda config_manager, novel_orchestrator, llm_client: _FakeGenerator(),
    )
    monkeypatch.setattr(
        run_novel_generation,
        "_initialize_telemetry_run",
        lambda _run_dir, run_id, project_id, command: run_dir,
    )
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "get_derivative_generator", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "_print_statistics", lambda *args, **kwargs: None)

    longform_state = {
        "run_id": "run-001",
        "current_volume": 1,
        "current_volume_start_chapter": 1,
        "current_volume_end_chapter": 60,
        "volume_plan": [{"volume_index": 1, "start_chapter": 1, "end_chapter": 60, "chapter_count": 60}],
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

    assert result == 0
    assert context_calls == [1]
    assert saved_chapters == []
    assert saved_plot_summaries == []
    assert project.current_chapter == 0
    assert status.get("pending_state_path")
    assert status.get("chapter_quality_report", {}).get("invalid") is True
    assert status.get("chapter_quality_report", {}).get("issue_types") == ["goal_lock_false_inheritance"]


def test_continue_longform_run_clears_one_shot_chapter_guidance_after_success(temp_project_dir, monkeypatch):
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
    monkeypatch.setattr(run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {})
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "build_volume_risk_report", lambda **kwargs: {"risk_detected": False})
    monkeypatch.setattr(run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True)
    monkeypatch.setattr(run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 11)

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

    monkeypatch.setattr(run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess)

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


def test_continue_longform_run_keeps_one_shot_chapter_guidance_after_failure(temp_project_dir, monkeypatch):
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
    monkeypatch.setattr(run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {})
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)

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

    monkeypatch.setattr(run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess)

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


def test_cmd_generate_full_volume_approval_updates_cross_volume_registry(temp_project_dir, monkeypatch):
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


def test_cmd_generate_full_volume_approval_merges_partial_cross_volume_registry_update(temp_project_dir, monkeypatch):
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


def test_cmd_generate_full_volume_approval_clears_explicit_cross_volume_registry_buckets(temp_project_dir, monkeypatch):
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
        captured["registry_summary"] = format_longform_registry(state.get("cross_volume_registry"))
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
            "blocking_issues": ["目标锁假继承[摘要命中但正文掉锚]: goal_lock=守住宗门祖地"],
        },
    )

    captured_after_chapter = {}

    def _capture_after_chapter(args, *, state, run_dir, run_started_at):
        captured_after_chapter["state"] = dict(state)
        return 21

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_after_chapter)

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

    monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_after_volume)

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
    monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(run_novel_generation, "build_volume_risk_report", lambda **kwargs: {"risk_detected": False})
    monkeypatch.setattr(run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True)
    monkeypatch.setattr(run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 23)
    monkeypatch.setattr(run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {})

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

    monkeypatch.setattr(run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess)

    continue_result = original_continue_longform_run(
        argparse.Namespace(log_level="INFO"),
        state=next_volume_state,
        run_dir=run_dir,
        run_started_at=run_novel_generation.datetime.now(),
    )

    assert continue_result == 23
    assert captured_subprocess["volume_guidance"].startswith("- 跨卷未完成目标: 守住宗门祖地")
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_first)

        first_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=first_pause["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(case["first_approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        first_result = run_novel_generation.cmd_generate_full(first_args)
        assert first_result == 31
        assert first_capture["state"]["next_chapter_guidance_chapter"] == case["chapter_number"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_second)

        second_args = argparse.Namespace(
            run_id="run-001",
            run_dir=str(run_dir),
            resume_state=second_pause["pending_state_path"],
            submit_approval="revise",
            approval_payload=json.dumps(case["second_approval_payload"], ensure_ascii=False),
            chapters_per_volume=60,
            approval_mode="outline+volume",
            auto_approve=False,
        )

        second_result = run_novel_generation.cmd_generate_full(second_args)
        assert second_result == 32
        assert second_capture["state"]["next_chapter_guidance_chapter"] == case["chapter_number"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_after_volume)

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
        registry_summary = format_longform_registry(captured_after_volume["state"]["cross_volume_registry"])
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
        monkeypatch.setattr(run_novel_generation, "_update_run_progress", lambda *args, **kwargs: None)
        monkeypatch.setattr(run_novel_generation, "build_volume_risk_report", lambda **kwargs: {"risk_detected": False})
        monkeypatch.setattr(run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True)
        monkeypatch.setattr(run_novel_generation, "_pause_for_volume_review", lambda **kwargs: 42)
        monkeypatch.setattr(run_novel_generation, "_resolve_active_writing_options", lambda _cfg, _args: {})

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

        monkeypatch.setattr(run_novel_generation, "_run_volume_generation_subprocess", _fake_run_subprocess)

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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

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
        assert reject_status["current_stage"] == case["expected_reject_status"]["current_stage"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_revise)

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
        assert revise_capture["state"]["next_chapter_guidance_chapter"] == case["chapter_number"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _capture_after_volume)

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
        assert captured_after_volume["state"]["cross_volume_registry"] == case["expected_registry_after_merge"]
        registry_summary = format_longform_registry(captured_after_volume["state"]["cross_volume_registry"])
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

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

        monkeypatch.setattr(run_novel_generation, "should_pause_for_stage", lambda *args, **kwargs: True)
        monkeypatch.setattr(run_novel_generation, "_pause_for_volume_review", _fake_pause_for_volume_review)

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
        assert persisted_state["current_stage"] == case["expected_intermediate_state"]["current_stage"]
        assert persisted_state["risk_report_path"] is case["expected_intermediate_state"]["risk_report_path"]
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
        assert captured_pause["state"]["current_stage"] == case["expected_pause_call"]["state_current_stage"]
        assert captured_pause["state"]["current_volume"] == case["expected_pause_call"]["current_volume"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _unexpected_continue)

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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

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
        assert captured["state"]["approved_outline"] is case["expected_state"]["approved_outline"]
        assert captured["state"]["current_stage"] == case["expected_state"]["current_stage"]
        assert captured["state"]["outline_snapshot"]["outline"] == case["expected_project_fields"]["outline"]
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

        monkeypatch.setattr(run_novel_generation, "_continue_longform_run", _fake_continue)

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
        assert captured["state"]["approved_outline"] is case["expected_state"]["approved_outline"]
        assert captured["state"]["current_stage"] == case["expected_state"]["current_stage"]
        assert captured["state"]["outline_snapshot"]["outline"] == case["expected_project_fields"]["outline"]
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
