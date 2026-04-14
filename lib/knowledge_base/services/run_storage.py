"""File-backed run telemetry helpers for long-running generation tasks."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import uuid


STATUS_FILE_NAME = "status.json"
STDOUT_LOG_NAME = "stdout.log"
STDERR_LOG_NAME = "stderr.log"


def _now_iso() -> str:
    return datetime.now().isoformat()


def run_dir_for(project_dir: str | Path, run_id: str) -> Path:
    """Return the canonical directory for a run."""
    return Path(project_dir).resolve() / "runs" / run_id


def ensure_run_dir(project_dir: str | Path, run_id: str) -> Path:
    """Create the run directory if needed."""
    run_dir = run_dir_for(project_dir, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def status_file_for(run_dir: str | Path) -> Path:
    """Return the status.json path for a run."""
    return Path(run_dir) / STATUS_FILE_NAME


def stdout_log_for(run_dir: str | Path) -> Path:
    """Return the stdout log path for a run."""
    return Path(run_dir) / STDOUT_LOG_NAME


def stderr_log_for(run_dir: str | Path) -> Path:
    """Return the stderr log path for a run."""
    return Path(run_dir) / STDERR_LOG_NAME


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def default_status(run_id: str, project_id: str, command: list[str] | None = None) -> dict[str, Any]:
    """Return the default v1 run status payload."""
    return {
        "run_id": run_id,
        "project_id": project_id,
        "command": command or [],
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "current_stage": "init",
        "current_step": "等待启动",
        "chapters_total": 0,
        "chapters_completed": 0,
        "eta_seconds": None,
        "error_message": None,
        "failed_stage": None,
        "pid": None,
        "return_code": None,
        "updated_at": _now_iso(),
    }


def read_status(run_dir: str | Path) -> dict[str, Any]:
    """Read status.json. Missing or invalid files return an empty payload."""
    status_path = status_file_for(run_dir)
    if not status_path.exists():
        return {}
    try:
        return json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_status(run_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist an explicit status payload."""
    data = dict(payload)
    data["updated_at"] = _now_iso()
    _atomic_write_json(status_file_for(run_dir), data)
    return data


def ensure_run_initialized(
    run_dir: str | Path,
    *,
    run_id: str,
    project_id: str,
    command: list[str] | None = None,
) -> Path:
    """Ensure a run directory has logs and a baseline status payload."""
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    stdout_log_for(run_path).touch(exist_ok=True)
    stderr_log_for(run_path).touch(exist_ok=True)

    current = read_status(run_path)
    baseline = default_status(run_id=run_id, project_id=project_id, command=command)
    baseline.update(current)
    if command is not None and not baseline.get("command"):
        baseline["command"] = command
    write_status(run_path, baseline)
    return run_path


def create_run(
    project_dir: str | Path,
    run_id: str,
    project_id: str,
    command: list[str] | None = None,
) -> Path:
    """Initialize a run directory with default artifacts."""
    run_dir = ensure_run_dir(project_dir, run_id)
    return ensure_run_initialized(
        run_dir,
        run_id=run_id,
        project_id=project_id,
        command=command,
    )


def update_status(run_dir: str | Path, **updates: Any) -> dict[str, Any]:
    """Merge updates into the current run status and persist atomically."""
    current = read_status(run_dir)
    current.update(updates)
    return write_status(run_dir, current)


def read_log_tail(run_dir: str | Path, stream: str = "stdout", max_chars: int = 12000) -> str:
    """Return the tail of a run log for UI display."""
    log_path = stdout_log_for(run_dir) if stream == "stdout" else stderr_log_for(run_dir)
    if not log_path.exists():
        return ""
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if max_chars <= 0 or len(content) <= max_chars:
        return content
    return content[-max_chars:]


def latest_run_dir(project_dir: str | Path) -> Path | None:
    """Return the most recently updated run directory, if present."""
    runs_root = Path(project_dir).resolve() / "runs"
    if not runs_root.exists():
        return None
    candidates = [
        path for path in runs_root.iterdir()
        if path.is_dir() and status_file_for(path).exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: status_file_for(path).stat().st_mtime)


def format_eta(seconds: int | float | None) -> str:
    """Format ETA seconds for human display."""
    if seconds is None:
        return "计算中"
    remaining = max(int(seconds), 0)
    hours, rem = divmod(remaining, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
