"""Shared inspection helpers for generated content directories."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_MEMORY_PATH = Path(".claude/PROJECT_MEMORY.md")


def _repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "CLAUDE.md").exists():
            return candidate
    return current


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_content_type(result: dict[str, Any]) -> str:
    """Infer content type from the structured result payload."""
    if {"target_words", "chapters_count", "style"}.issubset(result):
        return "Novel"
    if {"platforms", "title_style", "body_length"}.issubset(result):
        return "Blog"
    if {"duration", "acts", "scenes_count"}.issubset(result):
        return "Script"
    if {"hosts", "failed_sections", "total_duration_minutes"}.issubset(result) or {
        "hosts",
        "duration",
    }.issubset(result):
        return "Podcast"
    return result.get("content_type", "Unknown")


def collect_artifacts(output_dir: Path) -> dict[str, bool]:
    """Collect common artifacts for a generated content directory."""
    candidates = {
        "result.json": output_dir / "result.json",
        "summary.md": output_dir / "summary.md",
        "pipeline_state.json": output_dir / "pipeline_state.json",
        "world.json": output_dir / "world.json",
        "content.txt": output_dir / "content.txt",
        "script.txt": output_dir / "script.txt",
        "shownotes.json": output_dir / "shownotes.json",
        "beat_sheet.json": output_dir / "beat_sheet.json",
    }
    return {name: path.exists() for name, path in candidates.items()}


def expected_artifacts(content_type: str) -> list[str]:
    """List expected artifacts for a given content type."""
    if content_type == "Novel":
        return ["result.json", "summary.md", "pipeline_state.json", "world.json", "chapters/"]
    if content_type == "Blog":
        return ["result.json", "summary.md", "content.txt", "hooks.json"]
    if content_type == "Podcast":
        return ["result.json", "summary.md", "script.txt", "shownotes.json"]
    if content_type == "Script":
        return ["result.json", "summary.md", "beat_sheet.json", "scenes/"]
    return ["result.json", "summary.md"]


def summarize_report(result: dict[str, Any]) -> dict[str, Any]:
    quality_report = result.get("quality_report", {})
    return {
        "status": result.get("status") or quality_report.get("output_status", "unknown"),
        "is_usable": result.get("is_usable", quality_report.get("is_usable", True)),
        "requires_manual_review": result.get(
            "requires_manual_review",
            quality_report.get("requires_manual_review", False),
        ),
        "warnings": list(result.get("warnings", [])),
        "errors": list(result.get("errors", [])),
        "next_actions": list(result.get("next_actions", [])),
    }


def extract_task_dashboard(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize task dashboard data from a result payload."""
    dashboard = result.get("task_dashboard") or {}
    summary = dashboard.get("summary") or {}
    tasks = dashboard.get("tasks") or []
    active_tasks = dashboard.get("active_tasks") or []
    return {
        "summary": summary,
        "tasks": tasks,
        "active_tasks": active_tasks,
    }


def project_memory_info(base_dir: Path | None = None) -> dict[str, Any]:
    root = _repo_root(base_dir)
    path = (root / PROJECT_MEMORY_PATH).resolve()
    return {
        "path": str(path),
        "exists": path.exists(),
    }
