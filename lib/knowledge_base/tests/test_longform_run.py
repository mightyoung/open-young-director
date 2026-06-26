"""Tests for longform pause/resume state helpers."""

from datetime import datetime
from pathlib import Path

from agents.novel_generator import GeneratedChapter
from run_novel_generation import _pause_for_invalid_chapter
from services.longform_run import (
    CHECKPOINT_CHAPTER,
    CHECKPOINT_OUTLINE,
    LONGFORM_REGISTRY_FIELDS,
    STAGE_CHAPTER_REVIEW,
    STAGE_OUTLINE_REVIEW,
    STRUCTURED_VOLUME_GUIDANCE_FIELDS,
    approval_entry_detail_parts,
    approval_entry_summary,
    approval_history_summary,
    approval_payload_from_input,
    approval_preview_text,
    build_volume_risk_report,
    clear_pause,
    format_longform_registry,
    format_volume_guidance,
    initial_longform_state,
    load_longform_state,
    merge_longform_registry,
    normalize_longform_registry,
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
    assert state["cross_volume_registry"] == {
        "unresolved_goals": [],
        "open_promises": [],
        "dangling_settings": [],
    }
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
            "continuity_issues": [
                "本章开头未自然承接上章人物或局势状态，存在明显割裂。"
            ],
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


def test_pause_for_invalid_chapter_preserves_anti_drift_review_details(
    temp_project_dir,
):
    project_dir = temp_project_dir / "project"
    run_dir = create_run(
        project_dir=project_dir,
        run_id="run-002",
        project_id="project-123",
        command=["--generate-full"],
    )
    state = initial_longform_state(
        project=_Project(),
        run_id="run-002",
        run_dir=run_dir,
        chapters_per_volume=60,
        approval_mode="outline+volume",
        auto_approve=False,
    )
    chapter = GeneratedChapter(
        number=5,
        title="第五章",
        content="测试内容",
        word_count=4,
        metadata={"rewrite_history": [{"attempt": 1, "mode": "rewrite"}]},
        consistency_report={
            "summary": "结构漂移风险导致章节暂停",
            "blocking_issues": [
                "结构漂移风险[主线目标锁被新设定冲散]: budget=1，goal_terms=守住宗门祖地"
            ],
            "issue_types": ["structure_drift_risk"],
            "missing_events": [],
            "continuity_issues": [],
            "world_fact_issues": [],
            "warning_issues": [
                "生成前意图检查已重写章节大纲，本章虽继续生成，但建议观察是否出现计划层掉锚复发。"
            ],
            "semantic_review": {
                "enabled": True,
                "warning_only": True,
                "issue_count": 1,
                "issues": [
                    {
                        "category": "chapter_intent_rewrite_applied",
                        "severity": "warning",
                        "message": "生成前意图检查已重写章节大纲，本章虽继续生成，但建议观察是否出现计划层掉锚复发。",
                    }
                ],
            },
            "anti_drift_details": {
                "goal_lock": "守住宗门祖地",
                "budget": 1,
                "intro_count": 2,
            },
            "chapter_intent_contract": {
                "goal_lock": "守住宗门祖地",
                "planned_action": "韩林必须先稳住祖地防线。",
            },
            "rewrite_attempted": True,
            "rewrite_succeeded": False,
            "rewrite_plan": {
                "issue_types": ["structure_drift_risk"],
                "must_keep": ["保留本章既有关键事件，不要靠删除冲突来伪造顺畅。"],
                "fixes": ["先推进主线目标锁：守住宗门祖地。"],
                "success_criteria": ["任何新增设定都必须在近邻段落中桥接回主线目标。"],
            },
            "rewrite_guidance": "先推进主线目标锁：守住宗门祖地。",
            "smoothness_details": [
                {
                    "category": "structure_drift_risk",
                    "message": "结构漂移风险[主线目标锁被新设定冲散]",
                }
            ],
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
    pending = approval_payload_from_input(status["pending_state_path"])

    assert result == 0
    assert (
        pending["review_payload"]["anti_drift_details"]["goal_lock"] == "守住宗门祖地"
    )
    assert pending["review_payload"]["warning_issues"][0].startswith(
        "生成前意图检查已重写章节大纲"
    )
    assert pending["review_payload"]["semantic_review"]["issue_count"] == 1
    assert (
        pending["review_payload"]["chapter_intent_contract"]["planned_action"]
        == "韩林必须先稳住祖地防线。"
    )
    assert pending["review_payload"]["rewrite_plan"]["issue_types"] == [
        "structure_drift_risk"
    ]
    assert (
        pending["review_payload"]["rewrite_guidance"]
        == "先推进主线目标锁：守住宗门祖地。"
    )
    assert (
        pending["review_payload"]["smoothness_details"][0]["category"]
        == "structure_drift_risk"
    )


def test_approval_payload_from_file_and_inline_json(temp_project_dir):
    payload_path = temp_project_dir / "payload.json"
    payload_path.write_text('{"outline": "revised"}', encoding="utf-8")

    from_file = approval_payload_from_input(str(payload_path))
    inline = approval_payload_from_input('{"world_setting": "new"}')
    fallback = approval_payload_from_input("plain note")

    assert from_file["outline"] == "revised"
    assert inline["world_setting"] == "new"
    assert fallback["notes"] == "plain note"


def test_approval_history_formatter_helpers_cover_primary_checkpoints():
    assert approval_preview_text("  demo  ") == "demo"
    assert approval_preview_text("") == ""

    chapter_details = approval_entry_detail_parts(
        {
            "checkpoint_type": CHECKPOINT_CHAPTER,
            "payload": {
                "notes": "先把祖地防线的实际行动补出来，然后再处理追兵。",
                "chapter_rewrite_plan": {
                    "operations": [{"action": "rebuild_goal_lock_chain"}]
                },
            },
        }
    )
    outline_details = approval_entry_detail_parts(
        {
            "checkpoint_type": CHECKPOINT_OUTLINE,
            "payload": {
                "outline": "新大纲",
                "world_setting": "新世界观",
                "character_intro": "新人设",
            },
        }
    )

    summary = approval_entry_summary(
        {
            "checkpoint_type": CHECKPOINT_CHAPTER,
            "action": "revise",
            "payload": {
                "chapter_rewrite_guidance": "先接住上一章后果，再重组目标锁推进链。",
                "chapter_rewrite_plan": {
                    "operations": [{"action": "restore_carryover"}]
                },
            },
            "submitted_at": "2026-04-21T10:15:00",
        }
    )
    history = approval_history_summary(
        {
            "approval_history": [
                {
                    "checkpoint_type": CHECKPOINT_OUTLINE,
                    "action": "approve",
                    "payload": {},
                    "submitted_at": "2026-04-21T09:00:00",
                },
                {
                    "checkpoint_type": CHECKPOINT_CHAPTER,
                    "action": "revise",
                    "payload": {
                        "notes": "补上祖地防线推进。",
                        "chapter_rewrite_plan": {
                            "operations": [{"action": "rebuild_goal_lock_chain"}]
                        },
                    },
                    "submitted_at": "2026-04-21T10:15:00",
                },
            ]
        },
        limit=2,
    )

    assert chapter_details[0] == "patch=1"
    assert chapter_details[1].startswith("notes=先把祖地防线的实际行动补出来")
    assert outline_details == ["fields=outline,world,characters"]
    assert summary.startswith("- 2026-04-21 10:15 章节复核 -> 修订")
    assert "guidance=先接住上一章后果，再重组目标锁推进链。" in summary
    assert "大纲审批 -> 批准" in history
    assert "章节复核 -> 修订" in history


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
            "anti_drift_start_ratio": "0.4",
            "anti_drift_min_chapter": "20",
            "goal_lock_false_inheritance_mode": "warn",
            "anti_drift_notes": "优先回收伏笔，延后新体系扩写",
            "extra_notes": "尽快把主角推入主动局面",
        }
    )

    formatted = format_volume_guidance(payload)

    assert payload["must_recover"] == "回收第一卷宗门裂痕"
    assert payload["goal_lock"] == "守住宗门祖地"
    assert payload["new_setting_budget"] == "1"
    assert payload["anti_drift_start_ratio"] == "0.4"
    assert payload["goal_lock_false_inheritance_mode"] == "warn"
    assert "必须回收的伏笔/问题: 回收第一卷宗门裂痕" in formatted
    assert "明确避免的方向: 不要新增支线角色" in formatted
    assert "当前主线目标锁: 守住宗门祖地" in formatted
    assert "新设定预算: 1" in formatted
    assert "anti_drift_start_ratio" not in formatted
    assert "goal_lock_false_inheritance_mode" not in formatted


def test_structured_volume_guidance_fields_keep_core_fields_and_allow_additions():
    core_fields = {
        "must_recover",
        "relationship_focus",
        "must_avoid",
        "tone_target",
        "extra_notes",
    }
    assert core_fields.issubset(set(STRUCTURED_VOLUME_GUIDANCE_FIELDS))


def test_longform_registry_helpers_normalize_and_format():
    payload = normalize_longform_registry(
        {
            "unresolved_goals": ["守住宗门祖地", "追回失落阵眼"],
            "open_promises": "回收师门裂痕\n揭示魔帝线",
            "dangling_settings": ["远古秘境现世", ""],
        }
    )

    formatted = format_longform_registry(payload)

    assert payload["unresolved_goals"] == ["守住宗门祖地", "追回失落阵眼"]
    assert payload["open_promises"] == ["回收师门裂痕", "揭示魔帝线"]
    assert payload["dangling_settings"] == ["远古秘境现世"]
    assert "跨卷未完成目标: 守住宗门祖地；追回失落阵眼" in formatted
    assert "尚未回收承诺/伏笔: 回收师门裂痕；揭示魔帝线" in formatted


def test_longform_registry_fields_keep_core_fields():
    assert set(LONGFORM_REGISTRY_FIELDS) == {
        "unresolved_goals",
        "open_promises",
        "dangling_settings",
    }


def test_merge_longform_registry_updates_only_provided_buckets():
    merged = merge_longform_registry(
        {
            "unresolved_goals": ["守住宗门祖地"],
            "open_promises": ["回收第一卷宗门裂痕"],
            "dangling_settings": ["远古秘境现世"],
        },
        {"open_promises": ["揭示魔帝线"]},
    )

    assert merged == {
        "unresolved_goals": ["守住宗门祖地"],
        "open_promises": ["揭示魔帝线"],
        "dangling_settings": ["远古秘境现世"],
    }


def test_normalize_volume_guidance_payload_returns_strings_for_all_declared_fields():
    normalized = normalize_volume_guidance_payload(
        {"must_recover": 123, "extra_notes": None}
    )
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
            {"number": 1, "title": "开局", "word_count": 3200, "summary": "主角初入宗门", "key_events": ["入门", "拜师"], "file_path": "chapters/ch001.md"},
            {"number": 2, "title": "冲突", "word_count": 3400, "summary": "", "key_events": ["对决"], "file_path": "chapters/ch002.md"},
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
    chapter_dir = project_dir / "chapters"
    chapter_dir.mkdir()
    (chapter_dir / "ch001.md").write_text(
        "# 第一章\n\n韩林踏入宗门，暗暗记住祖地的裂痕。" * 20,
        encoding="utf-8",
    )
    (chapter_dir / "ch002.md").write_text(
        "# 第二章\n\n对手逼近演武场，韩林决定正面迎战。" * 20,
        encoding="utf-8",
    )

    payload = review_payload_for_volume(
        {
            "current_volume": 1,
            "current_volume_start_chapter": 1,
            "current_volume_end_chapter": 60,
            "chapters_completed": 60,
            "volume_plan": [
                {
                    "volume_index": 1,
                    "start_chapter": 1,
                    "end_chapter": 60,
                    "chapter_count": 60,
                }
            ],
            "project_dir": str(project_dir),
            "cross_volume_registry": {
                "unresolved_goals": ["守住宗门祖地"],
                "open_promises": ["回收第一卷宗门裂痕"],
                "dangling_settings": ["远古秘境现世"],
            },
        }
    )

    assert payload["generated_chapter_count"] == 2
    assert payload["total_word_count"] == 6600
    assert payload["opening_summary"] == "主角初入宗门"
    assert payload["closing_summary"] == "主角与对手正面冲突，埋下新的伏笔。"
    assert len(payload["chapter_highlights"]) == 2
    assert (
        payload["chapter_highlights"][1]["summary"]
        == "主角与对手正面冲突，埋下新的伏笔。"
    )
    assert payload["cross_volume_registry"]["unresolved_goals"] == ["守住宗门祖地"]
    assert "跨卷未完成目标: 守住宗门祖地" in payload["cross_volume_registry_summary"]
    assert len(payload["chapter_evidence_excerpts"]) == 2
    assert payload["chapter_evidence_excerpts"][0]["opening_excerpt"].startswith(
        "韩林踏入宗门"
    )
    assert len(payload["chapter_evidence_excerpts"][0]["opening_excerpt"]) <= 240
