"""Tests for feedback loop CLI compatibility surface."""

from agents.feedback_loop import FeedbackMode, FeedbackStrategy, get_feedback_loop


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
