"""Global error-experience pool for young-writer generation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any


try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback.
    fcntl = None


SCHEMA_VERSION = "young_writer.global_experience.v1"
DEFAULT_STATUS = "captured"
PROMOTED_STATUSES = {"verified", "promoted"}
GLOBAL_EXPERIENCE_ENV = "YOUNG_WRITER_EXPERIENCE_DIR"
EXPERIENCE_KIND_GENERATION = "generation_guidance"
EXPERIENCE_KIND_CODE_REPAIR = "code_repair"
DEFAULT_EXPERIENCE_KIND = EXPERIENCE_KIND_GENERATION


def default_experience_dir() -> Path:
    """Return the process-wide young-writer experience pool path."""

    override = os.environ.get(GLOBAL_EXPERIENCE_ENV)
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "runtime" / "global_experience"


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(values: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = [_clean_str(item) for item in values]
    result = [item for item in cleaned if item]
    return result[:limit] if limit is not None else result


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class ExperienceCase:
    """One globally reusable generation failure or repair experience."""

    id: str
    status: str
    stage: str
    issue_types: list[str]
    lesson: str
    experience_kind: str = DEFAULT_EXPERIENCE_KIND
    source_project_id: str = ""
    run_id: str = ""
    chapter_number: int = 0
    title: str = ""
    symptoms: list[str] = field(default_factory=list)
    root_cause: str = ""
    fix: str = ""
    success_criteria: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    helped_count: int = 0
    hurt_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": self.id,
            "status": self.status,
            "scope": "global",
            "experience_kind": self.experience_kind,
            "stage": self.stage,
            "issue_types": self.issue_types,
            "lesson": self.lesson,
            "source_project_id": self.source_project_id,
            "run_id": self.run_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            "symptoms": self.symptoms,
            "root_cause": self.root_cause,
            "fix": self.fix,
            "success_criteria": self.success_criteria,
            "tags": self.tags,
            "evidence": self.evidence,
            "usage_count": self.usage_count,
            "helped_count": self.helped_count,
            "hurt_count": self.hurt_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExperienceCase:
        return cls(
            id=_clean_str(payload.get("id")),
            status=_clean_str(payload.get("status")) or DEFAULT_STATUS,
            stage=_clean_str(payload.get("stage")),
            issue_types=_clean_list(payload.get("issue_types")),
            lesson=_clean_str(payload.get("lesson")),
            experience_kind=(
                _clean_str(payload.get("experience_kind")) or DEFAULT_EXPERIENCE_KIND
            ),
            source_project_id=_clean_str(payload.get("source_project_id")),
            run_id=_clean_str(payload.get("run_id")),
            chapter_number=int(payload.get("chapter_number") or 0),
            title=_clean_str(payload.get("title")),
            symptoms=_clean_list(payload.get("symptoms")),
            root_cause=_clean_str(payload.get("root_cause")),
            fix=_clean_str(payload.get("fix")),
            success_criteria=_clean_list(payload.get("success_criteria")),
            tags=_clean_list(payload.get("tags")),
            evidence=dict(payload.get("evidence") or {}),
            usage_count=int(payload.get("usage_count") or 0),
            helped_count=int(payload.get("helped_count") or 0),
            hurt_count=int(payload.get("hurt_count") or 0),
            created_at=_clean_str(payload.get("created_at")) or datetime.now().isoformat(),
            updated_at=_clean_str(payload.get("updated_at")) or datetime.now().isoformat(),
        )


class GlobalExperiencePool:
    """Append-friendly global store with deterministic lightweight retrieval."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        self.root_dir = Path(root_dir) if root_dir is not None else default_experience_dir()
        self.cases_path = self.root_dir / "cases.jsonl"
        self.usage_path = self.root_dir / "usage.jsonl"

    def load_cases(self) -> list[ExperienceCase]:
        if not self.cases_path.exists():
            return []
        cases: list[ExperienceCase] = []
        for line in self.cases_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            case = ExperienceCase.from_dict(payload)
            if case.id and case.lesson:
                cases.append(case)
        return cases

    def get_case(self, case_id: str) -> ExperienceCase | None:
        target_id = _clean_str(case_id)
        if not target_id:
            return None
        for case in self.load_cases():
            if case.id == target_id:
                return case
        return None

    def _cases_lock_path(self) -> Path:
        return self.root_dir / ".cases.lock"

    def _locked_append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._cases_lock_path()
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            with path.open("a+", encoding="utf-8") as handle:
                handle.seek(0)
                existing_ids = set()
                for line in handle.read().splitlines():
                    if not line.strip():
                        continue
                    try:
                        existing = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    existing_id = _clean_str(existing.get("id"))
                    if existing_id:
                        existing_ids.add(existing_id)
                payload_id = _clean_str(payload.get("id"))
                if not payload_id or payload_id not in existing_ids:
                    handle.write(
                        json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    )
                    handle.write("\n")
                    handle.flush()
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _rewrite_cases_unlocked(self, cases: list[ExperienceCase]) -> None:
        tmp_path = self.cases_path.with_name(f"{self.cases_path.name}.tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for case in cases:
                handle.write(
                    json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True)
                )
                handle.write("\n")
            handle.flush()
        tmp_path.replace(self.cases_path)

    def update_case(
        self,
        case_id: str,
        *,
        status: str | None = None,
        evidence_append: dict[str, Any] | None = None,
        usage_delta: int = 0,
        helped_delta: int = 0,
        hurt_delta: int = 0,
    ) -> ExperienceCase | None:
        target_id = _clean_str(case_id)
        if not target_id:
            return None

        updated_case: ExperienceCase | None = None
        now = datetime.now().isoformat()
        cases: list[ExperienceCase] = []
        self.root_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self._cases_lock_path()
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            for case in self.load_cases():
                payload = case.to_dict()
                if case.id == target_id:
                    if status is not None:
                        payload["status"] = _clean_str(status) or case.status
                    if evidence_append:
                        evidence = dict(payload.get("evidence") or {})
                        events = evidence.get("events")
                        if not isinstance(events, list):
                            events = []
                        event = dict(evidence_append)
                        event.setdefault("created_at", now)
                        events.append(event)
                        evidence["events"] = events[-50:]
                        payload["evidence"] = evidence
                    payload["usage_count"] = max(
                        0, int(payload.get("usage_count") or 0) + usage_delta
                    )
                    payload["helped_count"] = max(
                        0, int(payload.get("helped_count") or 0) + helped_delta
                    )
                    payload["hurt_count"] = max(
                        0, int(payload.get("hurt_count") or 0) + hurt_delta
                    )
                    payload["updated_at"] = now
                    updated_case = ExperienceCase.from_dict(payload)
                    cases.append(updated_case)
                else:
                    cases.append(case)

            if updated_case is None:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
                return None
            self._rewrite_cases_unlocked(cases)
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        return updated_case

    def update_case_status(
        self,
        case_id: str,
        status: str,
        *,
        evidence_append: dict[str, Any] | None = None,
    ) -> ExperienceCase | None:
        return self.update_case(
            case_id,
            status=status,
            evidence_append=evidence_append,
        )

    def promote_case(
        self,
        case_id: str,
        *,
        status: str = "verified",
        evidence_append: dict[str, Any] | None = None,
    ) -> ExperienceCase | None:
        promoted_status = _clean_str(status) or "verified"
        if promoted_status not in PROMOTED_STATUSES:
            raise ValueError(f"Unsupported promoted status: {promoted_status}")
        return self.update_case_status(
            case_id,
            promoted_status,
            evidence_append=evidence_append,
        )

    def reject_case(
        self,
        case_id: str,
        *,
        evidence_append: dict[str, Any] | None = None,
    ) -> ExperienceCase | None:
        return self.update_case_status(
            case_id,
            "rejected",
            evidence_append=evidence_append,
        )

    def append_case(self, case: ExperienceCase) -> ExperienceCase:
        payload = case.to_dict()
        if not payload["id"]:
            payload["id"] = "exp_" + _stable_hash(
                {
                    "stage": payload["stage"],
                    "experience_kind": payload["experience_kind"],
                    "issue_types": payload["issue_types"],
                    "lesson": payload["lesson"],
                    "source_project_id": payload["source_project_id"],
                    "run_id": payload["run_id"],
                    "chapter_number": payload["chapter_number"],
                }
            )
        case = ExperienceCase.from_dict(payload)
        self._locked_append_jsonl(self.cases_path, case.to_dict())
        return case

    def record_usage(
        self,
        *,
        experience_ids: list[str],
        project_id: str = "",
        run_id: str = "",
        stage: str = "",
        chapter_number: int = 0,
        outcome: str = "unknown",
    ) -> None:
        cleaned_ids: list[str] = []
        for item in experience_ids:
            cleaned = _clean_str(item)
            if cleaned and cleaned not in cleaned_ids:
                cleaned_ids.append(cleaned)
        if not cleaned_ids:
            return
        project_id = _clean_str(project_id)
        run_id = _clean_str(run_id)
        if not project_id or not run_id:
            return
        stage = _clean_str(stage)
        outcome = _clean_str(outcome) or "unknown"
        payload = {
            "schema_version": SCHEMA_VERSION,
            "experience_ids": cleaned_ids,
            "project_id": project_id,
            "run_id": run_id,
            "stage": stage,
            "chapter_number": chapter_number,
            "outcome": outcome,
            "created_at": datetime.now().isoformat(),
        }
        self.root_dir.mkdir(parents=True, exist_ok=True)
        with self.usage_path.open("a", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            handle.flush()
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        helped_delta = 1 if outcome == "helped" else 0
        hurt_delta = 1 if outcome == "hurt" else 0
        for experience_id in cleaned_ids:
            self.update_case(
                experience_id,
                usage_delta=1,
                helped_delta=helped_delta,
                hurt_delta=hurt_delta,
                evidence_append={
                    "event": "usage",
                    "outcome": outcome,
                    "stage": stage,
                    "project_id": project_id,
                    "run_id": run_id,
                    "chapter_number": chapter_number,
                },
            )

    def retrieve(
        self,
        *,
        stage: str,
        issue_types: list[str] | None = None,
        query_terms: list[str] | None = None,
        top_k: int = 5,
        include_unverified: bool = False,
        experience_kinds: list[str] | None = None,
    ) -> list[tuple[float, ExperienceCase]]:
        issue_set = {item for item in _clean_list(issue_types or [])}
        query_set = {item.lower() for item in _clean_list(query_terms or [])}
        kind_set = {item for item in _clean_list(experience_kinds or [])}
        scored: list[tuple[float, ExperienceCase]] = []
        for case in self.load_cases():
            if not include_unverified and case.status not in PROMOTED_STATUSES:
                continue
            if kind_set and case.experience_kind not in kind_set:
                continue
            score = 0.0
            if stage and case.stage == stage:
                score += 3.0
            overlap = issue_set.intersection(case.issue_types)
            score += 4.0 * len(overlap)
            text = " ".join(
                [case.lesson, case.root_cause, case.fix, " ".join(case.tags)]
            ).lower()
            score += sum(1.0 for term in query_set if term and term in text)
            score += min(case.helped_count, 3) * 0.25
            score -= min(case.hurt_count, 3) * 0.5
            if score > 0:
                scored.append((score, case))
        scored.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return scored[:top_k]


def build_case_from_review_payload(
    review_payload: dict[str, Any],
    *,
    project_id: str = "",
    run_id: str = "",
    status: str = DEFAULT_STATUS,
) -> ExperienceCase:
    issue_types = _clean_list(review_payload.get("issue_types"))
    rewrite_plan = dict(review_payload.get("rewrite_plan") or {})
    fixes = _clean_list(rewrite_plan.get("fixes"), limit=3)
    success_criteria = _clean_list(rewrite_plan.get("success_criteria"), limit=3)
    blocking = _clean_list(review_payload.get("blocking_issues"), limit=5)
    lesson_parts = []
    if issue_types:
        lesson_parts.append("issue_types=" + ", ".join(issue_types))
    if blocking:
        lesson_parts.append("症状：" + "；".join(blocking[:2]))
    if fixes:
        lesson_parts.append("修复：" + "；".join(fixes[:2]))
    lesson = " | ".join(lesson_parts) or _clean_str(review_payload.get("summary"))
    return ExperienceCase(
        id="",
        status=status,
        stage="chapter.review",
        issue_types=issue_types,
        lesson=lesson,
        experience_kind=EXPERIENCE_KIND_GENERATION,
        source_project_id=project_id,
        run_id=run_id,
        chapter_number=int(review_payload.get("chapter_number") or 0),
        title=_clean_str(review_payload.get("title")),
        symptoms=blocking,
        root_cause=_clean_str(review_payload.get("summary")),
        fix="；".join(fixes),
        success_criteria=success_criteria,
        tags=issue_types + _clean_list(review_payload.get("hard_gate_issue_types")),
        evidence={
            "pause_disposition": review_payload.get("pause_disposition"),
            "repair_decision": review_payload.get("repair_decision"),
            "rewrite_history": review_payload.get("rewrite_history", []),
        },
    )


def build_experience_capsule(
    retrieved: list[tuple[float, ExperienceCase]],
    *,
    max_items: int = 4,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for score, case in retrieved[:max_items]:
        items.append(
            {
                "id": case.id,
                "score": round(score, 3),
                "status": case.status,
                "stage": case.stage,
                "experience_kind": case.experience_kind,
                "issue_types": case.issue_types,
                "lesson": case.lesson,
                "fix": case.fix,
                "success_criteria": case.success_criteria,
                "provenance": {
                    "source_project_id": case.source_project_id,
                    "run_id": case.run_id,
                    "chapter_number": case.chapter_number,
                },
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "young_writer_global_experience_pool",
        "items": items,
        "loaded_ids": [item["id"] for item in items],
    }


def format_experience_capsule(capsule: dict[str, Any] | None) -> str:
    if not capsule:
        return ""
    items = capsule.get("items")
    if not isinstance(items, list) or not items:
        return ""
    lines = ["全局经验池召回："]
    for index, item in enumerate(items[:4], start=1):
        lesson = _clean_str(item.get("lesson"))
        fix = _clean_str(item.get("fix"))
        criteria = _clean_list(item.get("success_criteria"), limit=2)
        provenance = item.get("provenance") if isinstance(item, dict) else {}
        provenance = provenance if isinstance(provenance, dict) else {}
        source = _clean_str(provenance.get("source_project_id"))
        run_id = _clean_str(provenance.get("run_id"))
        chapter_number = int(provenance.get("chapter_number") or 0)
        line = f"{index}. {lesson}"
        source_bits = []
        if source:
            source_bits.append(f"source={source}")
        if run_id:
            source_bits.append(f"run={run_id}")
        if chapter_number:
            source_bits.append(f"ch={chapter_number}")
        if source_bits:
            line += f"（{'，'.join(source_bits)}）"
        if fix:
            line += f"；建议修复：{fix}"
        if criteria:
            line += f"；验收：{'；'.join(criteria)}"
        lines.append(line)
    return "\n".join(lines)
