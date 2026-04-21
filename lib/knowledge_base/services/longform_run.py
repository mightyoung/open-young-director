"""Longform novel run state helpers for pause/resume workflows."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any


def generate_pending_state_path(
    stage: str,
    topic: str = "unknown",
    output_dir: str | None = None,
) -> str:
    """Generate a pending-state path using the same filename contract as crewai."""
    topic_part = "".join(char if char.isalnum() else "_" for char in str(topic))
    filename = f".novel_pipeline_{topic_part}_{stage}_{int(time.time())}_pending.json"
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return str(output_path / filename)
    return filename


class HumanReviewGate:
    """Minimal local review gate matching the behavior needed by knowledge_base."""

    def __init__(
        self,
        enabled_stages: frozenset[str],
        auto_approve: bool = False,
        callback: Any = None,
    ) -> None:
        self.enabled_stages = enabled_stages
        self.auto_approve = auto_approve
        self.callback = callback

    def check(self, stage_name: str, state: Any) -> bool:
        if stage_name not in self.enabled_stages:
            return True
        if self.auto_approve:
            return True
        if self.callback:
            summary = state if isinstance(state, dict) else getattr(state, "__dict__", {})
            return bool(self.callback(stage_name, summary))
        return False


LONGFORM_STATE_NAME = "longform_state.v1.json"
RISK_REPORT_NAME = "risk_report.json"
CHECKPOINT_OUTLINE = "outline_review"
CHECKPOINT_VOLUME = "volume_review"
CHECKPOINT_RISK = "risk_review"
CHECKPOINT_CHAPTER = "chapter_review"
STAGE_OUTLINE_GENERATE = "outline.generate"
STAGE_OUTLINE_REVIEW = "outline.review"
STAGE_VOLUME_PLAN = "volume.plan"
STAGE_VOLUME_WRITE = "volume.write"
STAGE_VOLUME_REVIEW = "volume.review"
STAGE_RISK_PAUSE = "risk.pause"
STAGE_CHAPTER_REVIEW = "chapter.review"
STAGE_FINALIZE_EXPORT = "finalize.export"
DEFAULT_ALLOWED_ACTIONS = ["approve", "revise", "reject"]
DEFAULT_RISK_SCORE_THRESHOLD = 6.5
DEFAULT_RISK_MISSING_EVENTS_THRESHOLD = 2
STRUCTURED_VOLUME_GUIDANCE_FIELDS = (
    "must_recover",
    "relationship_focus",
    "must_avoid",
    "tone_target",
    "goal_lock",
    "new_setting_budget",
    "anti_drift_notes",
    "extra_notes",
)
LONGFORM_REGISTRY_FIELDS = (
    "unresolved_goals",
    "open_promises",
    "dangling_settings",
)


def _now_iso() -> str:
    return datetime.now().isoformat()


def normalize_volume_guidance_payload(payload: dict[str, Any] | None) -> dict[str, str]:
    data = payload if isinstance(payload, dict) else {}
    normalized: dict[str, str] = {}
    for key in STRUCTURED_VOLUME_GUIDANCE_FIELDS:
        value = data.get(key, "")
        normalized[key] = str(value).strip()
    return normalized


def format_volume_guidance(payload: dict[str, Any] | None) -> str:
    normalized = normalize_volume_guidance_payload(payload)
    labels = {
        "must_recover": "必须回收的伏笔/问题",
        "relationship_focus": "需要强化的人物关系",
        "must_avoid": "明确避免的方向",
        "tone_target": "目标基调",
        "goal_lock": "当前主线目标锁",
        "new_setting_budget": "新设定预算",
        "anti_drift_notes": "结构防漂移备注",
        "extra_notes": "补充说明",
    }
    lines = [
        f"- {labels[key]}: {value}"
        for key, value in normalized.items()
        if value
    ]
    return "\n".join(lines)


def normalize_longform_registry(payload: dict[str, Any] | None) -> dict[str, list[str]]:
    data = payload if isinstance(payload, dict) else {}
    normalized: dict[str, list[str]] = {}
    for key in LONGFORM_REGISTRY_FIELDS:
        raw_value = data.get(key, [])
        values = raw_value if isinstance(raw_value, list) else str(raw_value or "").splitlines()
        normalized[key] = [str(item).strip() for item in values if str(item).strip()]
    return normalized


def format_longform_registry(payload: dict[str, Any] | None) -> str:
    normalized = normalize_longform_registry(payload)
    labels = {
        "unresolved_goals": "跨卷未完成目标",
        "open_promises": "尚未回收承诺/伏笔",
        "dangling_settings": "已引入但未桥接设定",
    }
    lines: list[str] = []
    for key in LONGFORM_REGISTRY_FIELDS:
        values = normalized.get(key, [])
        if not values:
            continue
        lines.append(f"- {labels[key]}: {'；'.join(values[:5])}")
    return "\n".join(lines)


def approval_action_label(action: str) -> str:
    labels = {
        "approve": "批准",
        "revise": "修订",
        "reject": "拒绝",
    }
    return labels.get(action, action or "unknown")


def approval_checkpoint_label(checkpoint_type: str) -> str:
    labels = {
        CHECKPOINT_OUTLINE: "大纲审批",
        CHECKPOINT_VOLUME: "分卷审批",
        CHECKPOINT_RISK: "风险复核",
        CHECKPOINT_CHAPTER: "章节复核",
    }
    return labels.get(str(checkpoint_type or "").strip(), str(checkpoint_type or "").strip())


def approval_preview_text(value: Any, limit: int = 24) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:limit]


def approval_entry_detail_parts(entry: dict[str, Any]) -> list[str]:
    checkpoint_type = str(entry.get("checkpoint_type", "") or "").strip()
    payload = entry.get("payload", {}) or {}
    if not isinstance(payload, dict):
        payload = {}

    detail_parts: list[str] = []
    if checkpoint_type == CHECKPOINT_CHAPTER:
        rewrite_plan = payload.get("chapter_rewrite_plan", {}) or {}
        if isinstance(rewrite_plan, dict):
            operations = rewrite_plan.get("operations", []) or []
            if operations:
                detail_parts.append(f"patch={len(operations)}")
        notes = approval_preview_text(payload.get("notes"))
        guidance = approval_preview_text(payload.get("chapter_rewrite_guidance"))
        if notes:
            detail_parts.append(f"notes={notes}")
        elif guidance:
            detail_parts.append(f"guidance={guidance}")
    elif checkpoint_type == CHECKPOINT_VOLUME:
        must_recover = approval_preview_text(payload.get("must_recover"))
        if must_recover:
            detail_parts.append(f"must_recover={must_recover}")
        registry_count = 0
        for key in LONGFORM_REGISTRY_FIELDS:
            values = payload.get(key, []) or []
            if isinstance(values, list):
                registry_count += len([str(item).strip() for item in values if str(item).strip()])
        if registry_count:
            detail_parts.append(f"registry={registry_count}")
    elif checkpoint_type == CHECKPOINT_OUTLINE:
        outline_fields = [
            label
            for label, key in (
                ("outline", "outline"),
                ("world", "world_setting"),
                ("characters", "character_intro"),
            )
            if str(payload.get(key, "") or "").strip()
        ]
        if outline_fields:
            detail_parts.append(f"fields={','.join(outline_fields)}")
    elif checkpoint_type == CHECKPOINT_RISK:
        notes = approval_preview_text(payload.get("notes"))
        if notes:
            detail_parts.append(f"notes={notes}")
    return detail_parts


def approval_entry_summary(entry: dict[str, Any]) -> str:
    checkpoint_type = str(entry.get("checkpoint_type", "") or "").strip()
    action = str(entry.get("action", "") or "").strip()
    submitted_at = str(entry.get("submitted_at", "") or "").strip().replace("T", " ")[:16]
    checkpoint_label = approval_checkpoint_label(checkpoint_type) or checkpoint_type or "未知节点"
    header = f"- {submitted_at or 'unknown time'} {checkpoint_label} -> {approval_action_label(action)}"

    detail_parts = approval_entry_detail_parts(entry)
    if not detail_parts:
        return header
    return f"{header}\n  {', '.join(detail_parts)}"


def approval_history_summary(state: dict[str, Any], limit: int = 3) -> str:
    history = state.get("approval_history", []) or []
    if not isinstance(history, list):
        return ""
    recent_entries = [entry for entry in history if isinstance(entry, dict)][-limit:]
    if not recent_entries:
        return ""
    return "\n".join(approval_entry_summary(entry) for entry in recent_entries)


def merge_longform_registry(
    current: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, list[str]]:
    merged = normalize_longform_registry(current)
    update_data = updates if isinstance(updates, dict) else {}
    for key in LONGFORM_REGISTRY_FIELDS:
        if key not in update_data:
            continue
        raw_value = update_data.get(key, [])
        values = raw_value if isinstance(raw_value, list) else str(raw_value or "").splitlines()
        merged[key] = [str(item).strip() for item in values if str(item).strip()]
    return merged


def longform_state_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / LONGFORM_STATE_NAME


def risk_report_path(run_dir: str | Path) -> Path:
    return Path(run_dir) / RISK_REPORT_NAME


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


def save_risk_report(run_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    data["updated_at"] = _now_iso()
    _atomic_write_json(risk_report_path(run_dir), data)
    return data


def build_volume_risk_report(
    *,
    project_dir: str | Path,
    volume_index: int,
    start_chapter: int,
    end_chapter: int,
    score_threshold: float = DEFAULT_RISK_SCORE_THRESHOLD,
    missing_events_threshold: int = DEFAULT_RISK_MISSING_EVENTS_THRESHOLD,
) -> dict[str, Any]:
    consistency_dir = Path(project_dir) / "consistency_reports"
    chapters: list[dict[str, Any]] = []
    at_risk_chapters: list[dict[str, Any]] = []
    total_missing_events = 0

    for chapter_number in range(start_chapter, end_chapter + 1):
        report_file = consistency_dir / f"ch{chapter_number:03d}_consistency.json"
        payload = load_json_file(report_file)
        report = payload.get("report", payload if isinstance(payload, dict) else {})
        if not isinstance(report, dict) or not report:
            continue

        missing_events = [str(item) for item in report.get("missing_events", []) if str(item).strip()]
        recommendations = [str(item) for item in report.get("recommendations", []) if str(item).strip()]
        overall_score = float(report.get("overall_score", 0.0) or 0.0)
        chapter_summary = {
            "chapter_number": chapter_number,
            "overall_score": round(overall_score, 1),
            "missing_events": missing_events,
            "missing_events_count": len(missing_events),
            "recommendations": recommendations[:3],
            "character_state_count": len(report.get("character_states", {}) or {}),
        }
        chapters.append(chapter_summary)
        total_missing_events += len(missing_events)

        if overall_score < score_threshold or len(missing_events) >= missing_events_threshold:
            at_risk_chapters.append(chapter_summary)

    highest_risk = max((item["missing_events_count"] for item in at_risk_chapters), default=0)
    low_score_count = sum(1 for item in at_risk_chapters if item["overall_score"] < score_threshold)
    risk_detected = bool(
        at_risk_chapters
        and (
            len(at_risk_chapters) >= 2
            or any(item["overall_score"] < 5.0 for item in at_risk_chapters)
            or total_missing_events >= 4
        )
    )

    if not risk_detected:
        risk_level = "low"
        summary = "本卷未检测到需要人工复核的明显失控风险。"
    elif any(item["overall_score"] < 5.0 for item in at_risk_chapters) or highest_risk >= 3:
        risk_level = "high"
        summary = f"第 {volume_index} 卷存在明显失控风险，建议先人工复核后再继续。"
    else:
        risk_level = "medium"
        summary = f"第 {volume_index} 卷出现多处连贯性/关键事件缺口，建议人工确认。"

    return {
        "volume_index": volume_index,
        "volume_start_chapter": start_chapter,
        "volume_end_chapter": end_chapter,
        "evaluated_chapter_count": len(chapters),
        "risk_detected": risk_detected,
        "risk_level": risk_level,
        "summary": summary,
        "score_threshold": score_threshold,
        "low_score_chapter_count": low_score_count,
        "total_missing_events": total_missing_events,
        "at_risk_chapters": at_risk_chapters,
        "chapters": chapters,
        "generated_at": _now_iso(),
    }


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
        "project_dir": str(Path(run_dir).resolve().parents[1]),
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
        "next_volume_guidance": "",
        "next_volume_guidance_payload": {},
        "cross_volume_registry": normalize_longform_registry(None),
        "next_chapter_guidance": "",
        "next_chapter_guidance_chapter": None,
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
    payload = {
        "volume_index": current_volume,
        "volume_start_chapter": longform_state.get("current_volume_start_chapter", 0),
        "volume_end_chapter": longform_state.get("current_volume_end_chapter", 0),
        "chapters_completed": longform_state.get("chapters_completed", 0),
        "planned_chapter_count": plan.get("chapter_count", 0) if plan else 0,
        "cross_volume_registry": normalize_longform_registry(longform_state.get("cross_volume_registry")),
        "cross_volume_registry_summary": format_longform_registry(longform_state.get("cross_volume_registry")),
    }
    project_dir_raw = str(longform_state.get("project_dir", "")).strip()
    project_dir = Path(project_dir_raw).resolve() if project_dir_raw else None
    metadata = load_json_file(project_dir / "metadata.json") if project_dir else {}
    chapter_entries = [
        item
        for item in metadata.get("chapters", [])
        if payload["volume_start_chapter"] <= int(item.get("number", 0)) <= payload["volume_end_chapter"]
    ]
    chapter_entries.sort(key=lambda item: int(item.get("number", 0)))

    highlights: list[dict[str, Any]] = []
    total_word_count = 0
    for item in chapter_entries:
        chapter_number = int(item.get("number", 0))
        plot_summary = (
            load_json_file(project_dir / "plot_summaries" / f"ch{chapter_number:03d}_summary.json")
            if project_dir
            else {}
        )
        summary = str(item.get("summary", "")).strip()
        if not summary:
            summary = str(plot_summary.get("brief_summary") or plot_summary.get("one_line_summary") or "").strip()
        highlight = {
            "chapter_number": chapter_number,
            "title": str(item.get("title", "")),
            "word_count": int(item.get("word_count", 0)),
            "summary": summary,
            "key_events": list(item.get("key_events", []))[:4],
        }
        highlights.append(highlight)
        total_word_count += highlight["word_count"]

    if highlights:
        payload["generated_chapter_count"] = len(highlights)
        payload["total_word_count"] = total_word_count
        payload["chapter_highlights"] = highlights[:8]
        payload["opening_summary"] = highlights[0]["summary"]
        payload["closing_summary"] = highlights[-1]["summary"]
    else:
        payload["generated_chapter_count"] = 0
        payload["total_word_count"] = 0
        payload["chapter_highlights"] = []
        payload["opening_summary"] = ""
        payload["closing_summary"] = ""
    return payload


def review_payload_for_risk(risk_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "volume_index": risk_report.get("volume_index", 0),
        "volume_start_chapter": risk_report.get("volume_start_chapter", 0),
        "volume_end_chapter": risk_report.get("volume_end_chapter", 0),
        "risk_level": risk_report.get("risk_level", "low"),
        "summary": risk_report.get("summary", ""),
        "low_score_chapter_count": risk_report.get("low_score_chapter_count", 0),
        "total_missing_events": risk_report.get("total_missing_events", 0),
        "at_risk_chapters": list(risk_report.get("at_risk_chapters", [])),
    }


def review_payload_for_chapter(
    *,
    chapter_number: int,
    title: str,
    report: dict[str, Any],
    rewrite_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    blocking_issues = [str(item) for item in report.get("blocking_issues", []) if str(item).strip()]
    return {
        "chapter_number": chapter_number,
        "title": title,
        "summary": str(report.get("summary", "") or "").strip(),
        "issue_types": list(report.get("issue_types", [])),
        "blocking_issues": blocking_issues,
        "missing_events": list(report.get("missing_events", [])),
        "continuity_issues": list(report.get("continuity_issues", [])),
        "world_fact_issues": list(report.get("world_fact_issues", [])),
        "warning_issues": list(report.get("warning_issues", [])),
        "semantic_review": dict(report.get("semantic_review", {}) or {}),
        "smoothness_details": list(report.get("smoothness_details", [])),
        "anti_drift_details": dict(report.get("anti_drift_details", {}) or {}),
        "chapter_intent_contract": dict(report.get("chapter_intent_contract", {}) or {}),
        "rewrite_plan": dict(report.get("rewrite_plan", {}) or {}),
        "rewrite_guidance": str(report.get("rewrite_guidance", "") or "").strip(),
        "rewrite_attempted": bool(report.get("rewrite_attempted")),
        "rewrite_succeeded": bool(report.get("rewrite_succeeded")),
        "rewrite_history": list(rewrite_history or []),
    }


def compile_chapter_rewrite_guidance(
    rewrite_plan: dict[str, Any] | None,
    *,
    extra_notes: str = "",
) -> str:
    """Compile a stable chapter rewrite guidance string from structured patch data plus operator notes."""
    rewrite_plan = rewrite_plan or {}
    lines: list[str] = []

    must_keep = [str(item).strip() for item in rewrite_plan.get("must_keep", []) if str(item).strip()]
    operations = [item for item in rewrite_plan.get("operations", []) if isinstance(item, dict)]
    success_criteria = [
        str(item).strip() for item in rewrite_plan.get("success_criteria", []) if str(item).strip()
    ]
    fixes = [str(item).strip() for item in rewrite_plan.get("fixes", []) if str(item).strip()]

    if must_keep:
        lines.append("保留要求：")
        lines.extend(f"{index + 1}. {item}" for index, item in enumerate(must_keep[:2]))

    if operations:
        lines.append("Patch 操作：")
        for index, item in enumerate(operations[:4], start=1):
            phase = str(item.get("phase", "") or "").strip()
            action = str(item.get("action", "") or "").strip()
            target = str(item.get("target", "") or "").strip()
            instruction = str(item.get("instruction", "") or "").strip()
            rationale = str(item.get("rationale", "") or "").strip()
            header = " / ".join(part for part in (phase, action, target) if part)
            if header and rationale:
                lines.append(f"{index}. [{header}] {instruction}（原因：{rationale}）")
            elif header:
                lines.append(f"{index}. [{header}] {instruction}")
            elif instruction:
                lines.append(f"{index}. {instruction}")
    elif fixes:
        lines.append("本次修复：")
        lines.extend(f"{index + 1}. {item}" for index, item in enumerate(fixes[:4]))

    if success_criteria:
        lines.append("验收条件：")
        lines.extend(f"{index + 1}. {item}" for index, item in enumerate(success_criteria[:3]))

    notes = str(extra_notes or "").strip()
    if notes:
        lines.append("人工补充：")
        lines.append(notes)

    return "\n".join(lines).strip()


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
    raw_value = raw_value.strip()
    try:
        parsed = json.loads(raw_value)
    except Exception:
        try:
            candidate = Path(raw_value)
            if candidate.exists():
                return load_json_file(candidate)
        except OSError:
            pass
        return {"note": raw_value}
    return parsed if isinstance(parsed, dict) else {"value": parsed}
