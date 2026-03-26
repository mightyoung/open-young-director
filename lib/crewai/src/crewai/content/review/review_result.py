from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Issue:
    """审查问题"""
    type: str  # consistency, pacing, ooc, high_point, continuity
    description: str
    location: str = ""  # 章节/段落位置
    severity: str = "medium"  # high, medium, low
    suggestion: str = ""

    def __post_init__(self):
        valid_types = {"consistency", "pacing", "ooc", "high_point", "continuity", "interiority", "pov"}
        if self.type not in valid_types:
            raise ValueError(f"Invalid issue type: {self.type}. Must be one of {valid_types}")

        valid_severities = {"high", "medium", "low"}
        if self.severity not in valid_severities:
            raise ValueError(f"Invalid severity: {self.severity}. Must be one of {valid_severities}")


@dataclass
class ReviewResult:
    """审查结果"""
    issues: List[Issue] = field(default_factory=list)
    score: float = 0.0
    summary: str = ""

    def add_issue(self, issue: Issue) -> None:
        """添加一个问题"""
        self.issues.append(issue)

    def has_critical_issues(self) -> bool:
        """是否存在严重问题"""
        return any(issue.severity == "high" for issue in self.issues)

    def get_issues_by_type(self, issue_type: str) -> List[Issue]:
        """获取指定类型的问题"""
        return [issue for issue in self.issues if issue.type == issue_type]

    def get_issues_by_severity(self, severity: str) -> List[Issue]:
        """获取指定严重级别的问题"""
        return [issue for issue in self.issues if issue.severity == severity]

    def __str__(self) -> str:
        if not self.issues:
            return "No issues found."
        lines = [f"Review Score: {self.score}/10"]
        lines.append(f"Summary: {self.summary}")
        lines.append(f"\nFound {len(self.issues)} issues:")
        for i, issue in enumerate(self.issues, 1):
            lines.append(f"\n{i}. [{issue.type.upper()}] {issue.description}")
            if issue.location:
                lines.append(f"   Location: {issue.location}")
            lines.append(f"   Severity: {issue.severity}")
            if issue.suggestion:
                lines.append(f"   Suggestion: {issue.suggestion}")
        return "\n".join(lines)
