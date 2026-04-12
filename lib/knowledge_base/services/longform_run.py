"""Longform novel run state helpers for pause/resume workflows."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any


CREWAI_SRC = Path(__file__).resolve().parents[2] / "crewai" / "src"
if str(CREWAI_SRC) not in sys.path:
    sys.path.insert(0, str(CREWAI_SRC))

from crewai.content.novel.orchestrator.output_packer import generate_pending_state_path  # noqa: E402
from crewai.content.novel.pipeline.human_review_gate import HumanReviewGate  # noqa: E402


LONGFORM_STATE_NAME = "longform_state.v1.json"
RISK_REPORT_NAME = "risk_report.json"
CHECKPOINT_OUTLINE = "outline_review"
CHECKPOINT_VOLUME = "volume_review"
CHECKPOINT_RISK = "risk_review"
STAGE_OUTLINE_GENERATE = "outline.generate"
STAGE_OUTLINE_REVIEW = "outline.review"
STAGE_VOLUME_PLAN = "volume.plan"
STAGE_VOLUME_WRITE = "volume.write"
STAGE_VOLUME_REVIEW = "volume.review"
STAGE_RISK_PAUSE = "risk.pause"
STAGE_FINALIZE_EXPORT = "finalize.export"
DEFAULT_ALLOWED_ACTIONS = ["approve", "revise", "reject"]


def _now_iso() -> str:
    return datetime.now().isoformat()


def longform_state_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / LONGFORM_STATE_NAME


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_json_file(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_longform_state(run_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data["updated_at"] = _now_iso()
    _atomic_write_json(longform_state_path(run_dir), data)
    return data


def load_longform_state(run_dir_or_state: str | Path) -> dict[str, Any]:
    path = Path(run_dir_or_state)
    if path.is_dir():
        path = longform_state_path(path)
    return load_json_file(path)


def volume_plan(total_chapters: int, chapters_per_volume: int) -> list[dict[str, int]]:
    plan: list[dict[str, int]] = []
    current = 1
    volume_index = 1
    while current <= max(total_chapters, 0):
        end = min(current + chapters_per_volume - 1, total_chapters)
        plan.append(
            {
                "volume_index": volume_index,
                "start_chapter": current,
                "end_chapter": end,
                "chapter_count": max(end - current + 1, 0),
            }
        )
        current = end + 1
        volume_index += 1
    return plan


def initial_longform_state(
    *,
    project: Any,
    run_id: str,
    run_dir: str | Path,
    chapters_per_volume: int,
    approval_mode: str,
    auto_approve: bool,
) -> dict[str, Any]:
    plan = volume_plan(
        total_chapters=int(getattr(project, "total_chapters", 0)),
        chapters_per_volume=max(int(chapters_per_volume), 1),
    )
    current_volume = plan[0] if plan else None
    state = {
        "schema_version": 1,
        "run_id": run_id,
        "project_id": getattr(project, "id", ""),
        "project_title": getattr(project, "title", ""),
        "project_dir": str(Path(run_dir).resolve().parent),
        "run_dir": str(Path(run_dir).resolve()),
        "longform_state_path": str(longform_state_path(run_dir).resolve()),
        "status": "running",
        "approval_mode": approval_mode,
        "auto_approve": auto_approve,
        "chapters_per_volume": chapters_per_volume,
        "total_chapters": int(getattr(project, "total_chapters", 0)),
        "chapters_completed": int(getattr(project, "current_chapter", 0)),
        "approved_outline": auto_approve or approval_mode == "none",
        "outline_snapshot": {
            "outline": getattr(project, "outline", ""),
            "world_setting": getattr(project, "world_setting", ""),
            "character_intro": getattr(project, "character_intro", ""),
        },
        "current_stage": STAGE_OUTLINE_GENERATE,
        "current_checkpoint": None,
        "current_volume": current_volume["volume_index"] if current_volume else 0,
        "current_volume_start_chapter": current_volume["start_chapter"] if current_volume else 0,
        "current_volume_end_chapter": current_volume["end_chapter"] if current_volume else 0,
        "last_completed_volume": 0,
        "total_volumes": len(plan),
        "volume_plan": plan,
        "pending_state_path": None,
        "risk_report_path": None,
        "approval_history": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    return save_longform_state(run_dir, state)


def gate_for(approval_mode: str, auto_approve: bool) -> HumanReviewGate:
    enabled_stages: set[str] = set()
    if approval_mode == "outline+volume":
        enabled_stages = {"outline", "volume"}
    elif approval_mode == "outline":
        enabled_stages = {"outline"}
    elif approval_mode == "volume":
        enabled_stages = {"volume"}
    return HumanReviewGate(enabled_stages=frozenset(enabled_stages), auto_approve=auto_approve)


def should_pause_for_stage(approval_mode: str, auto_approve: bool, stage_name: str) -> bool:
    gate = gate_for(approval_mode, auto_approve)
    return not gate.check(stage_name, {"current_stage": stage_name})


def create_pending_review(
    *,
    run_dir: str | Path,
    checkpoint_type: str,
    current_stage: str,
    review_payload: dict[str, Any],
    longform_state: dict[str, Any],
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    state_path = Path(longform_state["longform_state_path"])
    pending_path = Path(
        generate_pending_state_path(
            stage=checkpoint_type.replace("_review", ""),
            topic=longform_state.get("project_title") or longform_state.get("project_id") or "unknown",
            output_dir=str(Path(run_dir).resolve()),
        )
    )
    payload = {
        "run_id": longform_state["run_id"],
        "checkpoint_type": checkpoint_type,
        "longform_state_path": str(state_path.resolve()),
        "current_stage": current_stage,
        "current_volume": longform_state.get("current_volume", 0),
        "chapters_completed": longform_state.get("chapters_completed", 0),
        "review_payload": review_payload,
        "allowed_actions": allowed_actions or list(DEFAULT_ALLOWED_ACTIONS),
        "created_at": _now_iso(),
    }
    _atomic_write_json(pending_path, payload)
    return payload | {"pending_state_path": str(pending_path.resolve())}


def record_pause(
    *,
    run_dir: str | Path,
    longform_state: dict[str, Any],
    checkpoint_type: str,
    current_stage: str,
    review_payload: dict[str, Any],
    allowed_actions: list[str] | None = None,
) -> dict[str, Any]:
    pending_payload = create_pending_review(
        run_dir=run_dir,
        checkpoint_type=checkpoint_type,
        current_stage=current_stage,
        review_payload=review_payload,
        longform_state=longform_state,
        allowed_actions=allowed_actions,
    )
    updated = dict(longform_state)
    updated.update(
        {
            "status": "paused",
            "current_stage": current_stage,
            "current_checkpoint": checkpoint_type,
            "pending_state_path": pending_payload["pending_state_path"],
        }
    )
    return save_longform_state(run_dir, updated)


def clear_pause(run_dir: str | Path, longform_state: dict[str, Any]) -> dict[str, Any]:
    updated = dict(longform_state)
    updated["status"] = "running"
    updated["current_checkpoint"] = None
    updated["pending_state_path"] = None
    return save_longform_state(run_dir, updated)


def review_payload_for_outline(project: Any) -> dict[str, Any]:
    return {
        "outline": getattr(project, "outline", ""),
        "world_setting": getattr(project, "world_setting", ""),
        "character_intro": getattr(project, "character_intro", ""),
    }


def review_payload_for_volume(longform_state: dict[str, Any]) -> dict[str, Any]:
    current_volume = longform_state.get("current_volume", 0)
    plan = next(
        (item for item in longform_state.get("volume_plan", []) if item["volume_index"] == current_volume),
        None,
    )
    return {
        "volume_index": current_volume,
        "volume_start_chapter": longform_state.get("current_volume_start_chapter", 0),
        "volume_end_chapter": longform_state.get("current_volume_end_chapter", 0),
        "chapters_completed": longform_state.get("chapters_completed", 0),
        "planned_chapter_count": plan.get("chapter_count", 0) if plan else 0,
    }


def next_volume(longform_state: dict[str, Any]) -> dict[str, Any]:
    current = int(longform_state.get("current_volume", 0))
    next_entry = next(
        (item for item in longform_state.get("volume_plan", []) if item["volume_index"] == current + 1),
        None,
    )
    updated = dict(longform_state)
    if next_entry is None:
        updated["current_volume"] = current
        updated["current_volume_start_chapter"] = 0
        updated["current_volume_end_chapter"] = 0
        return updated
    updated["current_volume"] = next_entry["volume_index"]
    updated["current_volume_start_chapter"] = next_entry["start_chapter"]
    updated["current_volume_end_chapter"] = next_entry["end_chapter"]
    return updated


def apply_outline_revision(project: Any, payload: dict[str, Any]) -> None:
    if not payload:
        return
    for field_name in ("outline", "world_setting", "character_intro"):
        value = payload.get(field_name)
        if isinstance(value, str):
            setattr(project, field_name, value.strip())


def approval_payload_from_input(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    candidate = Path(raw_value)
    if candidate.exists():
        return load_json_file(candidate)
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {"note": raw_value}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
