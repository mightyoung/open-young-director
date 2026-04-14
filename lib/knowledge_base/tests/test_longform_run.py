"""Tests for longform pause/resume state helpers."""

from pathlib import Path

from services.longform_run import (
    CHECKPOINT_OUTLINE,
    STAGE_OUTLINE_REVIEW,
    approval_payload_from_input,
    build_volume_risk_report,
    clear_pause,
    format_volume_guidance,
    initial_longform_state,
    load_longform_state,
    normalize_volume_guidance_payload,
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
            "extra_notes": "尽快把主角推入主动局面",
        }
    )

    formatted = format_volume_guidance(payload)

    assert payload["must_recover"] == "回收第一卷宗门裂痕"
    assert "必须回收的伏笔/问题: 回收第一卷宗门裂痕" in formatted
    assert "明确避免的方向: 不要新增支线角色" in formatted


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
