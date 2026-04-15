"""Tests for longform pause/resume state helpers."""

from datetime import datetime
from pathlib import Path

from agents.novel_generator import GeneratedChapter
from run_novel_generation import _pause_for_invalid_chapter
from services.longform_run import (
    CHECKPOINT_CHAPTER,
    CHECKPOINT_OUTLINE,
    STAGE_CHAPTER_REVIEW,
    STAGE_OUTLINE_REVIEW,
    STRUCTURED_VOLUME_GUIDANCE_FIELDS,
    approval_payload_from_input,
    build_volume_risk_report,
    clear_pause,
    format_volume_guidance,
    initial_longform_state,
    load_longform_state,
    normalize_volume_guidance_payload,
    record_pause,
)
from services.run_storage import create_run, read_status


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
    assert state["next_volume_guidance"] == ""
    assert Path(state["project_dir"]).resolve() == temp_project_dir.resolve()
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


def test_pause_for_invalid_chapter_writes_chapter_review_payload(temp_project_dir):
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-001",
        project_id="project-123",
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=_Project(),
        run_id="run-001",
        run_dir=run_dir,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    chapter = GeneratedChapter(
        number=4,
        title="第四章",
        content="测试内容",
        word_count=4,
        metadata={
            "rewrite_history": [{"attempt": 0, "mode": "initial"}],
        },
        consistency_report={
            "summary": "章节与前文严重割裂",
            "blocking_issues": ["本章开头未自然承接上章人物或局势状态，存在明显割裂。"],
            "issue_types": ["scene_or_timeline_disconnect"],
            "missing_events": [],
            "continuity_issues": ["本章开头未自然承接上章人物或局势状态，存在明显割裂。"],
            "world_fact_issues": [],
            "rewrite_attempted": True,
            "rewrite_succeeded": False,
        },
    )

    result = _pause_for_invalid_chapter(
        run_dir=run_dir,
        state=state,
        project_id="project-123",
        command=["--generate-full"],
        run_started_at=datetime.now(),
        chapter=chapter,
    )

    status = read_status(run_dir)
    assert result == 0
    assert status["pause_reason"] == CHECKPOINT_CHAPTER
    assert status["current_stage"] == STAGE_CHAPTER_REVIEW
    assert "章节与前文严重割裂" in status["error_message"]
    assert status["pending_state_path"]
    pending = approval_payload_from_input(status["pending_state_path"])
    assert pending["checkpoint_type"] == CHECKPOINT_CHAPTER
    assert pending["review_payload"]["chapter_number"] == 4
    assert pending["review_payload"]["issue_types"] == ["scene_or_timeline_disconnect"]


def test_approval_payload_from_file_and_inline_json(temp_project_dir):
    payload_path = temp_project_dir / "payload.json"
    payload_path.write_text('{"outline": "revised"}', encoding="utf-8")

    from_file = approval_payload_from_input(str(payload_path))
    inline = approval_payload_from_input('{"world_setting": "new"}')
    fallback = approval_payload_from_input("plain note")

    assert from_file["outline"] == "revised"
    assert inline["world_setting"] == "new"
    assert fallback["note"] == "plain note"


def test_build_volume_risk_report_flags_obvious_drift(temp_project_dir):
    consistency_dir = temp_project_dir / "project" / "consistency_reports"
    consistency_dir.mkdir(parents=True)
    (consistency_dir / "ch001_consistency.json").write_text(
        '{"report":{"overall_score":4.8,"missing_events":["伏笔A","伏笔B","伏笔C"],"recommendations":["补回伏笔"]}}',
        encoding="utf-8",
    )
    (consistency_dir / "ch002_consistency.json").write_text(
        '{"report":{"overall_score":6.0,"missing_events":["角色动机"],"recommendations":["补强角色动机"]}}',
        encoding="utf-8",
    )

    report = build_volume_risk_report(
        project_dir=temp_project_dir / "project",
        volume_index=1,
        start_chapter=1,
        end_chapter=2,
    )

    assert report["risk_detected"] is True
    assert report["risk_level"] == "high"
    assert len(report["at_risk_chapters"]) == 2
    assert report["total_missing_events"] == 4


def test_build_volume_risk_report_ignores_healthy_volume(temp_project_dir):
    consistency_dir = temp_project_dir / "project" / "consistency_reports"
    consistency_dir.mkdir(parents=True)
    (consistency_dir / "ch001_consistency.json").write_text(
        '{"report":{"overall_score":8.8,"missing_events":[],"recommendations":[]}}',
        encoding="utf-8",
    )
    (consistency_dir / "ch002_consistency.json").write_text(
        '{"report":{"overall_score":8.2,"missing_events":["轻微细节"],"recommendations":["可选补强"]}}',
        encoding="utf-8",
    )

    report = build_volume_risk_report(
        project_dir=temp_project_dir / "project",
        volume_index=1,
        start_chapter=1,
        end_chapter=2,
    )

    assert report["risk_detected"] is False
    assert report["risk_level"] == "low"


def test_volume_guidance_helpers_normalize_and_format():
    payload = normalize_volume_guidance_payload(
        {
            "must_recover": "回收第一卷宗门裂痕",
            "relationship_focus": "强化师徒对抗",
            "must_avoid": "不要新增支线角色",
            "tone_target": "压迫感更强",
            "goal_lock": "守住宗门祖地",
            "new_setting_budget": 1,
            "anti_drift_notes": "优先回收伏笔，延后新体系扩写",
            "extra_notes": "尽快把主角推入主动局面",
        }
    )

    formatted = format_volume_guidance(payload)

    assert payload["must_recover"] == "回收第一卷宗门裂痕"
    assert payload["goal_lock"] == "守住宗门祖地"
    assert payload["new_setting_budget"] == "1"
    assert "必须回收的伏笔/问题: 回收第一卷宗门裂痕" in formatted
    assert "明确避免的方向: 不要新增支线角色" in formatted
    assert "当前主线目标锁: 守住宗门祖地" in formatted
    assert "新设定预算: 1" in formatted


def test_structured_volume_guidance_fields_keep_core_fields_and_allow_additions():
    core_fields = {
        "must_recover",
        "relationship_focus",
        "must_avoid",
        "tone_target",
        "extra_notes",
    }
    assert core_fields.issubset(set(STRUCTURED_VOLUME_GUIDANCE_FIELDS))


def test_normalize_volume_guidance_payload_returns_strings_for_all_declared_fields():
    normalized = normalize_volume_guidance_payload({"must_recover": 123, "extra_notes": None})
    for key in STRUCTURED_VOLUME_GUIDANCE_FIELDS:
        assert isinstance(normalized.get(key), str)


def test_review_payload_for_volume_includes_chapter_highlights(temp_project_dir):
    from services.longform_run import review_payload_for_volume

    project_dir = temp_project_dir / "demo-project"
    plot_dir = project_dir / "plot_summaries"
    plot_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(
        """
        {
          "chapters": [
            {"number": 1, "title": "开局", "word_count": 3200, "summary": "主角初入宗门", "key_events": ["入门", "拜师"]},
            {"number": 2, "title": "冲突", "word_count": 3400, "summary": "", "key_events": ["对决"]},
            {"number": 61, "title": "第二卷开局", "word_count": 3000, "summary": "不应出现在第一卷", "key_events": []}
          ]
        }
        """,
        encoding="utf-8",
    )
    (plot_dir / "ch002_summary.json").write_text(
        '{"brief_summary":"主角与对手正面冲突，埋下新的伏笔。"}',
        encoding="utf-8",
    )

    payload = review_payload_for_volume(
        {
            "current_volume": 1,
            "current_volume_start_chapter": 1,
            "current_volume_end_chapter": 60,
            "chapters_completed": 60,
            "volume_plan": [{"volume_index": 1, "start_chapter": 1, "end_chapter": 60, "chapter_count": 60}],
            "project_dir": str(project_dir),
        }
    )

    assert payload["generated_chapter_count"] == 2
    assert payload["total_word_count"] == 6600
    assert payload["opening_summary"] == "主角初入宗门"
    assert payload["closing_summary"] == "主角与对手正面冲突，埋下新的伏笔。"
    assert len(payload["chapter_highlights"]) == 2
    assert payload["chapter_highlights"][1]["summary"] == "主角与对手正面冲突，埋下新的伏笔。"
