"""Tests for run_novel_generation longform resume flows."""

import argparse
from pathlib import Path
from types import SimpleNamespace

from agents.novel_generator import GeneratedChapter
import run_novel_generation
from services.longform_run import (
    CHECKPOINT_CHAPTER,
    STAGE_CHAPTER_REVIEW,
    STAGE_VOLUME_PLAN,
    initial_longform_state,
    record_pause,
)
from services.run_storage import create_run, read_status


class _Project:
    def __init__(self):
        self.id = "project-123"
        self.title = "demo"
        self.total_chapters = 120
        self.current_chapter = 3
        self.outline = "outline"
        self.world_setting = "world"
        self.character_intro = "characters"


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
    assert context_calls[1][1]["volume_guidance"] == "仅重写第2章的补充指令"
    assert project.current_chapter == 2
    assert (Path(project_dir) / "generation_results.json").exists()


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
    assert captured["chapter_guidance"] == "失败后也要保留的第4章重写指令"
    assert captured["chapter_guidance_target"] == 4
    assert state["next_chapter_guidance"] == "失败后也要保留的第4章重写指令"
    assert state["next_chapter_guidance_chapter"] == 4
