"""Tests for feedback loop CLI compatibility surface."""

import json

from young_writer.agents.feedback_loop import FeedbackMode, FeedbackStrategy, get_feedback_loop


def test_feedback_loop_exposes_cli_expected_methods(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    feedback = get_feedback_loop("project-123")

    cycle = feedback.run_with_strategy(
        FeedbackStrategy(mode=FeedbackMode.FULL, use_llm=True, max_iterations=2)
    )
    light = feedback.run_with_strategy(FeedbackStrategy(mode=FeedbackMode.LIGHT))
    discovery = feedback.run_discovery()
    analysis = feedback.run_analysis(use_llm=True)
    fix = feedback.run_fix(strategy="recommended")
    verification = feedback.run_verification(full=True)
    report_path = feedback.export_report()
    summary = feedback.get_issues_summary()

    assert cycle["final_status"] == "passed"
    assert light["status"] == "passed"
    assert discovery["issues_found"] == 0
    assert analysis["analyses"] == {}
    assert fix["summary"]["total"] == 0
    assert verification["verification_passed"] is True
    assert summary["total"] == 0
    assert (tmp_path / "feedback_report_project-123.json").exists()
    assert report_path.endswith("feedback_report_project-123.json")


def test_feedback_loop_discovers_structured_issues_from_artifacts(tmp_path):
    project_dir = tmp_path / "novels" / "测试项目_project-123"
    report_dir = project_dir / "consistency_reports"
    report_dir.mkdir(parents=True)
    (report_dir / "ch004_consistency.json").write_text(
        json.dumps(
            {
                "chapter_number": 4,
                "report": {
                    "invalid": True,
                    "issue_types": ["missing_key_events"],
                    "blocking_issues": ["缺少关键事件: 韩林守住祖地"],
                    "warning_issues": ["语义复核告警: 目标锁推进偏弱"],
                    "summary": "章节未通过质量闸门。",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "generation_results.json").write_text(
        json.dumps(
            {
                "chapter_results": [
                    {
                        "chapter_number": 5,
                        "status": "failed",
                        "error": "LLM timeout",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (project_dir / "runs" / "run-001").mkdir(parents=True)
    (project_dir / "runs" / "run-001" / "pending.json").write_text(
        json.dumps(
            {
                "checkpoint_type": "chapter_review",
                "review_payload": {
                    "chapter_number": 6,
                    "blocking_issues": ["目标锁假继承"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    feedback = get_feedback_loop("project-123", project_dir=project_dir)

    discovery = feedback.run_discovery()
    issues = discovery["issues"]

    assert discovery["issues_found"] == 4
    assert discovery["needs_fix"] is True
    assert all(issue["id"].startswith("project-123-") for issue in issues)
    assert {issue["category"] for issue in issues} >= {
        "missing_key_events",
        "semantic_warning",
        "generation_failed",
        "pending_chapter_review",
    }
    assert {issue["chapter_number"] for issue in issues} >= {4, 5, 6}
    assert all(issue["source_path"] for issue in issues)


def test_feedback_loop_modes_aggregate_real_issues(tmp_path):
    project_dir = tmp_path / "novels" / "测试项目_project-123"
    report_dir = project_dir / "consistency_reports"
    report_dir.mkdir(parents=True)
    (report_dir / "ch002_consistency.json").write_text(
        json.dumps(
            {
                "chapter_number": 2,
                "report": {
                    "invalid": True,
                    "issue_types": ["world_fact_violation"],
                    "blocking_issues": ["违反世界观: 无代价瞬移"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    feedback = get_feedback_loop("project-123", project_dir=project_dir)

    light = feedback.run_with_strategy(FeedbackStrategy(mode=FeedbackMode.LIGHT))
    deep = feedback.run_with_strategy(FeedbackStrategy(mode=FeedbackMode.DEEP))
    volume = feedback.run_with_strategy(
        FeedbackStrategy(mode=FeedbackMode.VOLUME_COMPLETE)
    )

    assert light["status"] == "needs_attention"
    assert light["issues_found"] == 1
    assert light["issues"][0]["severity"] == "error"
    assert deep["category_summary"]["world_fact_violation"] == 1
    assert volume["severity_summary"]["error"] == 1


def test_feedback_loop_fix_is_guidance_only_and_report_is_additive(tmp_path):
    project_dir = tmp_path / "novels" / "测试项目_project-123"
    report_dir = project_dir / "consistency_reports"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "ch003_consistency.json"
    original = {
        "chapter_number": 3,
        "report": {
            "invalid": True,
            "issue_types": ["scene_or_timeline_disconnect"],
            "blocking_issues": ["场景跳转缺少桥接"],
        },
    }
    report_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

    feedback = get_feedback_loop("project-123", project_dir=project_dir)
    fix = feedback.run_fix(strategy="recommended")
    exported_path = feedback.export_report()

    assert fix["dry_run"] is True
    assert fix["summary"]["success"] == 0
    assert fix["fix_results"][0]["proposed_action"]
    assert json.loads(report_path.read_text(encoding="utf-8")) == original
    exported = json.loads((tmp_path / exported_path).read_text(encoding="utf-8"))
    assert exported["schema_version"] == "feedback_report.v2"
    assert exported["summary"]["total"] == 1
    assert exported["issues"][0]["status"] == "open"
