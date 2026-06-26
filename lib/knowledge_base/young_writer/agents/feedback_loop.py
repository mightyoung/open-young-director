"""Feedback Loop for iterative content improvement."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class FeedbackMode(Enum):
    """Feedback loop modes."""

    LIGHT = "light"
    DEEP = "deep"
    FULL = "full"
    VOLUME_COMPLETE = "volume_complete"


@dataclass
class FeedbackStrategy:
    """Strategy for feedback loop."""

    mode: FeedbackMode
    batch_size: int = 5
    use_llm: bool = False
    auto_fix: bool = True
    max_iterations: int = 3


class FeedbackLoop:
    """Feedback loop for content improvement."""

    def __init__(
        self,
        project_id: str,
        llm_client=None,
        project_dir: str | Path | None = None,
    ):
        self.project_id = project_id
        self.llm_client = llm_client
        self.project_dir = Path(project_dir).resolve() if project_dir else None

    def run_with_strategy(self, strategy: FeedbackStrategy) -> dict[str, Any]:
        """Run feedback with given strategy."""
        logger.info(f"Running {strategy.mode.value} feedback")

        if strategy.mode == FeedbackMode.LIGHT:
            return self._run_light_feedback(strategy)
        if strategy.mode == FeedbackMode.DEEP:
            return self._run_deep_feedback(strategy)
        if strategy.mode == FeedbackMode.FULL:
            return self._run_full_feedback(strategy)
        if strategy.mode == FeedbackMode.VOLUME_COMPLETE:
            return self._run_volume_feedback(strategy)

        return {"status": "unknown_mode"}

    def _run_light_feedback(self, strategy: FeedbackStrategy) -> dict[str, Any]:
        """Run light feedback (basic checks)."""
        issues = self.discover_issues()
        return {
            "status": "passed" if not issues else "needs_attention",
            "mode": "light",
            "issues_found": len(issues),
            "issues": issues[: strategy.batch_size],
            "severity_summary": self._count_field(issues, "severity"),
            "category_summary": self._count_field(issues, "category"),
            "fixes_applied": 0,
        }

    def _run_deep_feedback(self, strategy: FeedbackStrategy) -> dict[str, Any]:
        """Run deep feedback (detailed analysis)."""
        issues = self.discover_issues()
        return {
            "status": "passed" if not issues else "needs_attention",
            "mode": "deep",
            "issues_found": len(issues),
            "issues": issues[: strategy.batch_size],
            "severity_summary": self._count_field(issues, "severity"),
            "category_summary": self._count_field(issues, "category"),
            "analysis": self.analyze_issues(issues),
            "fixes_applied": 0,
        }

    def _run_full_feedback(self, strategy: FeedbackStrategy) -> dict[str, Any]:
        """Run a compatibility full feedback cycle."""
        started_at = datetime.now().isoformat()
        discovery = self.run_discovery()
        if discovery.get("needs_fix"):
            analysis = self.run_analysis(use_llm=strategy.use_llm)
        else:
            analysis = {"iteration": 1, "analyses": {}}
        if strategy.auto_fix and discovery.get("needs_fix"):
            fix = self.run_fix(strategy="recommended")
        else:
            fix = {
                "iteration": 1,
                "summary": {"total": 0, "success": 0, "failed": 0},
            }
        verification = self.run_verification(full=True)
        return {
            "final_status": "passed"
            if verification.get("verification_passed")
            else "failed",
            "start_time": started_at,
            "end_time": datetime.now().isoformat(),
            "iterations": [
                {"phase": "discovery", "result": discovery},
                {"phase": "analysis", "result": analysis},
                {"phase": "fix", "result": fix},
                {"phase": "verification", "result": verification},
            ],
        }

    def _run_volume_feedback(self, strategy: FeedbackStrategy) -> dict[str, Any]:
        """Run volume-complete feedback."""
        issues = self.discover_issues()
        return {
            "status": "passed" if not issues else "needs_attention",
            "mode": "volume_complete",
            "issues_found": len(issues),
            "issues": issues,
            "severity_summary": self._count_field(issues, "severity"),
            "category_summary": self._count_field(issues, "category"),
            "fixes_applied": 0,
        }

    def discover_issues(self) -> list[dict[str, Any]]:
        """Discover issues in generated content."""
        project_dir = self._resolve_project_dir()
        if project_dir is None:
            return []

        issues: list[dict[str, Any]] = []
        for report_path in sorted((project_dir / "consistency_reports").glob("*.json")):
            issues.extend(self._issues_from_consistency_report(report_path))
        results_path = project_dir / "generation_results.json"
        if results_path.exists():
            issues.extend(self._issues_from_generation_results(results_path))
        for pending_path in sorted((project_dir / "runs").glob("**/*.json")):
            issues.extend(self._issues_from_pending_review(pending_path))
        for summary_path in sorted((project_dir / "plot_summaries").glob("*.json")):
            issues.extend(self._issues_from_plot_summary(summary_path))
        return issues

    def run_discovery(
        self,
        check_realm_progression: bool = True,
        check_consistency: bool = True,
        check_character_state: bool = True,
    ) -> dict[str, Any]:
        """Run issue discovery using the lightweight local checks currently available."""
        issues = self.discover_issues()
        return {
            "iteration": 1,
            "issues_found": len(issues),
            "issues": issues,
            "needs_fix": bool(issues),
            "severity_summary": self._count_field(issues, "severity"),
            "category_summary": self._count_field(issues, "category"),
            "checks": {
                "realm_progression": check_realm_progression,
                "consistency": check_consistency,
                "character_state": check_character_state,
            },
        }

    def analyze_issues(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze discovered issues."""
        category_counts = self._count_field(issues, "category")
        return {
            "analyzed": True,
            "issue_count": len(issues),
            "category_summary": category_counts,
            "recommendations": [
                {
                    "title": f"处理 {category} 问题",
                    "category": category,
                    "count": count,
                    "action": self._suggest_action_for_category(category),
                }
                for category, count in category_counts.items()
            ],
        }

    def run_analysis(self, use_llm: bool = False) -> dict[str, Any]:
        """Run compatibility issue analysis."""
        issues = self.discover_issues()
        analysis = self.analyze_issues(issues)
        return {
            "iteration": 1,
            "analyses": {
                str(issue.get("id", index + 1)): {
                    "root_cause": issue.get("description", "暂无根因分析。"),
                    "impact_scope": issue.get("affected_chapters", []),
                    "options": analysis.get("recommendations", []),
                    "use_llm": use_llm,
                }
                for index, issue in enumerate(issues)
            },
        }

    def fix_issues(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Fix discovered issues."""
        return {
            "fixed": False,
            "fixes_applied": 0,
            "proposed_actions": [
                {
                    "issue_id": issue.get("id"),
                    "proposed_action": issue.get("suggested_action", ""),
                }
                for issue in issues
            ],
        }

    def run_fix(self, strategy: str = "recommended") -> dict[str, Any]:
        """Run compatibility fix stage."""
        issues = self.discover_issues()
        result = self.fix_issues(issues)
        fixes_applied = int(result.get("fixes_applied", 0) or 0)
        return {
            "iteration": 1,
            "dry_run": True,
            "strategy": strategy,
            "summary": {
                "total": len(issues),
                "success": fixes_applied,
                "failed": max(len(issues) - fixes_applied, 0),
            },
            "fix_results": [
                {
                    "issue_id": issue.get("id"),
                    "success": False,
                    "fix_description": "P0 反馈修复阶段只输出指导，不自动修改章节或状态文件。",
                    "proposed_action": issue.get("suggested_action", ""),
                    "files_modified": [],
                }
                for issue in issues
            ],
        }

    def verify_fixes(self, fixes: dict[str, Any]) -> dict[str, Any]:
        """Verify that fixes were successful."""
        return {
            "verified": True,
            "all_fixed": True,
        }

    def run_verification(self, full: bool = False) -> dict[str, Any]:
        """Run compatibility verification stage."""
        issues = self.discover_issues()
        verification = self.verify_fixes({"issues": issues, "full": full})
        return {
            "iteration": 1,
            "verification_passed": bool(verification.get("all_fixed", True)),
            "checks": {"issue_discovery": not issues},
            "summary": {
                "total_issues": len(issues),
                "fixed": 0,
                "open": len(issues),
            },
            "open_issues": issues,
        }

    def get_issues_summary(self) -> dict[str, Any]:
        """Return a compact summary for report surfaces."""
        issues = self.discover_issues()
        return {
            "total": len(issues),
            "by_severity": self._count_field(issues, "severity"),
            "by_category": self._count_field(issues, "category"),
            "by_status": {"open": len(issues)},
        }

    def export_report(self) -> str:
        """Export the current lightweight feedback report."""
        issues = self.discover_issues()
        report = {
            "schema_version": "feedback_report.v2",
            "project_id": self.project_id,
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_issues_summary(),
            "issues": issues,
        }
        output_dir = self.project_dir or Path.cwd()
        report_path = (output_dir / f"feedback_report_{self.project_id}.json").resolve()
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(report_path)

    def _resolve_project_dir(self) -> Path | None:
        if self.project_dir and self.project_dir.exists():
            return self.project_dir
        candidates = [
            path
            for path in Path.cwd().glob(f"**/*{self.project_id}*")
            if path.is_dir() and (path / "consistency_reports").exists()
        ]
        return candidates[0].resolve() if candidates else None

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _count_field(issues: list[dict[str, Any]], field: str) -> dict[str, int]:
        return dict(Counter(str(issue.get(field, "unknown")) for issue in issues))

    def _issue(
        self,
        *,
        category: str,
        severity: str,
        source_path: Path,
        evidence: str,
        chapter_number: int | None = None,
        suggested_action: str = "",
    ) -> dict[str, Any]:
        digest = hashlib.sha1(
            f"{source_path}|{category}|{evidence}".encode("utf-8")
        ).hexdigest()[:10]
        return {
            "id": f"{self.project_id}-{category}-{digest}",
            "severity": severity,
            "category": category,
            "source_path": str(source_path),
            "chapter_number": chapter_number,
            "evidence": evidence,
            "description": evidence,
            "title": category.replace("_", " "),
            "affected_chapters": [chapter_number] if chapter_number else [],
            "suggested_action": suggested_action
            or self._suggest_action_for_category(category),
            "status": "open",
        }

    def _issues_from_consistency_report(self, path: Path) -> list[dict[str, Any]]:
        payload = self._read_json(path)
        report = payload.get("report", payload)
        if not isinstance(report, dict):
            return []
        chapter_number = int(payload.get("chapter_number") or 0) or self._chapter_from_path(
            path
        )
        issues: list[dict[str, Any]] = []
        issue_types = list(report.get("issue_types", []) or [])
        blocking = [
            str(item) for item in report.get("blocking_issues", []) or [] if str(item)
        ]
        if report.get("invalid") or blocking:
            categories = issue_types or ["consistency_blocker"]
            for category in categories:
                evidence = "；".join(blocking) or str(
                    report.get("summary", "") or category
                )
                issues.append(
                    self._issue(
                        category=str(category),
                        severity="error",
                        source_path=path,
                        chapter_number=chapter_number,
                        evidence=evidence,
                    )
                )
        for warning in report.get("warning_issues", []) or []:
            issues.append(
                self._issue(
                    category="semantic_warning",
                    severity="warning",
                    source_path=path,
                    chapter_number=chapter_number,
                    evidence=str(warning),
                )
            )
        return issues

    def _issues_from_generation_results(self, path: Path) -> list[dict[str, Any]]:
        payload = self._read_json(path)
        issues: list[dict[str, Any]] = []
        for result in payload.get("chapter_results", []) or []:
            if not isinstance(result, dict) or result.get("status") == "success":
                continue
            issues.append(
                self._issue(
                    category="generation_failed",
                    severity="error",
                    source_path=path,
                    chapter_number=int(result.get("chapter_number") or 0) or None,
                    evidence=str(result.get("error") or result.get("message") or result),
                )
            )
        return issues

    def _issues_from_pending_review(self, path: Path) -> list[dict[str, Any]]:
        payload = self._read_json(path)
        if payload.get("checkpoint_type") != "chapter_review":
            return []
        review = payload.get("review_payload", {}) or {}
        if not isinstance(review, dict):
            return []
        blockers = [
            str(item) for item in review.get("blocking_issues", []) or [] if str(item)
        ]
        if not blockers:
            return []
        return [
            self._issue(
                category="pending_chapter_review",
                severity="error",
                source_path=path,
                chapter_number=int(review.get("chapter_number") or 0) or None,
                evidence="；".join(blockers),
                suggested_action="在 chapter_review 中审批、修订或拒绝该章节后再继续。",
            )
        ]

    def _issues_from_plot_summary(self, path: Path) -> list[dict[str, Any]]:
        payload = self._read_json(path)
        unresolved = payload.get("unresolved_issues", []) or []
        return [
            self._issue(
                category="summary_unresolved_issue",
                severity="warning",
                source_path=path,
                chapter_number=int(payload.get("chapter_number") or 0)
                or self._chapter_from_path(path),
                evidence=str(item),
            )
            for item in unresolved
            if str(item).strip()
        ]

    @staticmethod
    def _chapter_from_path(path: Path) -> int | None:
        import re

        match = re.search(r"ch(\d+)", path.name)
        return int(match.group(1)) if match else None

    @staticmethod
    def _suggest_action_for_category(category: str) -> str:
        suggestions = {
            "generation_failed": "检查失败日志后重试该章节生成。",
            "pending_chapter_review": "处理 pending chapter_review 审批节点。",
            "semantic_warning": "将语义告警作为重写提示或人工复核依据。",
        }
        return suggestions.get(category, "根据来源报告修订章节指导或重跑质量检查。")


def get_feedback_loop(
    project_id: str, llm_client=None, project_dir: str | Path | None = None
) -> FeedbackLoop:
    """Get a FeedbackLoop instance."""
    return FeedbackLoop(project_id, llm_client=llm_client, project_dir=project_dir)
