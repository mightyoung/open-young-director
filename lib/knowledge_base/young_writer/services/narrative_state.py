"""Persistent narrative state derived from accepted longform chapters."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

SNAPSHOT_SCHEMA_VERSION = "narrative_state.snapshot.v1"
DELTA_SCHEMA_VERSION = "narrative_state.delta.v1"
PACKET_SCHEMA_VERSION = "narrative_state_packet.v1"


def narrative_state_dir(project_dir: str | Path) -> Path:
    return Path(project_dir) / "narrative_state"


def narrative_state_snapshot_dir(project_dir: str | Path) -> Path:
    return narrative_state_dir(project_dir) / "snapshots"


class NarrativeStateStore:
    """Project-local JSON store for compact current-story state."""

    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir)
        self.root_dir = narrative_state_dir(self.project_dir)
        self.snapshot_root = narrative_state_snapshot_dir(self.project_dir)
        self.current_path = self.root_dir / "current.json"
        self.events_path = self.root_dir / "events.jsonl"
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

    def load_current(self) -> dict[str, Any] | None:
        if not self.current_path.exists():
            return None
        return self._read_json(self.current_path)

    def load_snapshot(self, chapter_number: int) -> dict[str, Any] | None:
        path = self.snapshot_root / f"ch{int(chapter_number):03d}.json"
        if not path.exists():
            return None
        return self._read_json(path)

    def save_snapshot(self, snapshot: dict[str, Any]) -> Path:
        chapter_number = int(snapshot.get("chapter_number", 0) or 0)
        self.prune_snapshots_after(chapter_number)
        path = self.snapshot_root / f"ch{chapter_number:03d}.json"
        payload = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True)
        _atomic_write_text(path, payload)
        _atomic_write_text(self.current_path, payload)
        self.append_event(
            {
                "event": "narrative_state_saved",
                "chapter_number": chapter_number,
                "snapshot_path": str(path),
                "saved_at": datetime.now().isoformat(),
            }
        )
        return path

    def append_event(self, event: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def load_base_for_chapter(self, chapter_number: int) -> dict[str, Any] | None:
        """Load the canonical predecessor state for saving one chapter."""

        if int(chapter_number) > 1:
            return self.load_snapshot(int(chapter_number) - 1)
        return None

    def prune_snapshots_after(self, chapter_number: int) -> list[str]:
        """Remove downstream snapshots invalidated by an earlier chapter resave."""

        removed: list[str] = []
        for path in sorted(self.snapshot_root.glob("ch*.json")):
            try:
                suffix = path.stem.removeprefix("ch")
                snapshot_chapter = int(suffix)
            except ValueError:
                continue
            if snapshot_chapter <= int(chapter_number):
                continue
            path.unlink(missing_ok=True)
            removed.append(str(path))
        if removed:
            self.append_event(
                {
                    "event": "narrative_state_downstream_snapshots_pruned",
                    "chapter_number": int(chapter_number),
                    "removed_snapshot_paths": removed,
                    "saved_at": datetime.now().isoformat(),
                }
            )
        return removed

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning("Ignoring corrupt narrative state sidecar %s: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("Unable to read narrative state sidecar %s: %s", path, exc)
            return None
        if not isinstance(payload, dict):
            logger.warning("Ignoring non-object narrative state sidecar %s", path)
            return None
        return payload


def build_state_delta(
    *,
    project_id: str,
    chapter_number: int,
    story_graph_snapshot: dict[str, Any] | None = None,
    rebaseline_delta: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    run_id: str | None = None,
    chapter_path: str = "",
    summary: str = "",
    key_events: list[str] | None = None,
    character_appearances: list[str] | None = None,
    goal_lock: str = "",
    unresolved_goals: list[str] | None = None,
) -> dict[str, Any]:
    """Build a compact state delta from accepted chapter artifacts."""

    snapshot = dict(story_graph_snapshot or {})
    state = dict(snapshot.get("state", {}) or {})
    packet = dict((context or {}).get("chapter_graph_packet", {}) or {})
    rebaseline = dict(rebaseline_delta or {})
    evidence_ref = _evidence_ref(chapter_path, chapter_number)
    physical_location = _first_text(
        state.get("physical_location"),
        state.get("scene_anchor"),
        packet.get("previous_physical_location"),
    )
    chapter_summary = _first_text(summary, state.get("chapter_summary"))
    resolved_goal_lock = _first_text(goal_lock, packet.get("goal_lock"))

    return {
        "schema_version": DELTA_SCHEMA_VERSION,
        "project_id": project_id,
        "run_id": run_id,
        "chapter_number": int(chapter_number),
        "created_at": datetime.now().isoformat(),
        "timeline": {
            "physical_location": physical_location,
            "scene_anchor": _first_text(state.get("scene_anchor"), physical_location),
            "opening_excerpt": _first_text(state.get("opening_excerpt")),
            "chapter_summary": chapter_summary,
        },
        "goal_progress": {
            "goal_lock": resolved_goal_lock,
            "completed_goal_subgoals": _clean_list(
                rebaseline.get("completed_goal_subgoals")
                or packet.get("completed_goal_subgoals")
            ),
            "reached_destinations": _clean_list(
                rebaseline.get("destination_reached")
                or packet.get("reached_destinations")
            ),
            "unresolved_goals": _clean_list(unresolved_goals),
        },
        "story_threads": {
            "key_events": _clean_list(key_events),
            "must_include_events": _clean_list(packet.get("must_include_events")),
            "target_destinations": _clean_list(packet.get("target_destinations")),
        },
        "characters": [
            {
                "name": name,
                "last_seen_chapter": int(chapter_number),
                "evidence_refs": [evidence_ref] if evidence_ref else [],
            }
            for name in _clean_list(character_appearances)
        ],
        "world_facts": {
            "challenged_world_facts": _normalize_fact_list(
                rebaseline.get("challenged_world_facts")
                or packet.get("challenged_world_facts")
            ),
            "prohibited_inheritance": _clean_list(packet.get("prohibited_inheritance")),
        },
        "evidence_refs": [evidence_ref] if evidence_ref else [],
    }


def apply_state_delta(
    previous: dict[str, Any] | None,
    delta: dict[str, Any],
) -> dict[str, Any]:
    """Merge one accepted chapter delta into persistent narrative state."""

    chapter_number = int(delta.get("chapter_number", 0) or 0)
    previous = dict(previous or {})
    timeline = dict(previous.get("timeline", {}) or {})
    timeline.update(_without_empty(dict(delta.get("timeline", {}) or {})))

    goal_progress = dict(previous.get("goal_progress", {}) or {})
    delta_goal = dict(delta.get("goal_progress", {}) or {})
    completed = _unique(
        _clean_list(goal_progress.get("completed_goal_subgoals"))
        + _clean_list(delta_goal.get("completed_goal_subgoals"))
    )
    reached = _unique(
        _clean_list(goal_progress.get("reached_destinations"))
        + _clean_list(delta_goal.get("reached_destinations"))
    )
    unresolved = _unique(
        _clean_list(delta_goal.get("unresolved_goals"))
        or _clean_list(goal_progress.get("unresolved_goals"))
    )
    goal_progress.update(
        {
            "goal_lock": _first_text(
                delta_goal.get("goal_lock"), goal_progress.get("goal_lock")
            ),
            "completed_goal_subgoals": completed,
            "reached_destinations": reached,
            "unresolved_goals": [
                item for item in unresolved if item not in set(completed)
            ],
        }
    )

    story_threads = dict(previous.get("story_threads", {}) or {})
    delta_threads = dict(delta.get("story_threads", {}) or {})
    for key in ("key_events", "must_include_events", "target_destinations"):
        story_threads[key] = _unique(
            _clean_list(story_threads.get(key)) + _clean_list(delta_threads.get(key))
        )[-20:]

    characters = dict(previous.get("characters", {}) or {})
    for character in delta.get("characters", []) or []:
        if not isinstance(character, dict):
            continue
        name = _first_text(character.get("name"))
        if not name:
            continue
        existing = dict(characters.get(name, {}) or {})
        existing.update(
            {
                "name": name,
                "last_seen_chapter": int(
                    character.get("last_seen_chapter", chapter_number) or chapter_number
                ),
                "evidence_refs": _limited_refs(
                    list(existing.get("evidence_refs", []) or [])
                    + list(character.get("evidence_refs", []) or [])
                ),
            }
        )
        characters[name] = existing

    world_facts = dict(previous.get("world_facts", {}) or {})
    delta_facts = dict(delta.get("world_facts", {}) or {})
    for key in ("challenged_world_facts", "prohibited_inheritance"):
        world_facts[key] = _unique(
            _clean_list(world_facts.get(key)) + _clean_list(delta_facts.get(key))
        )[-20:]

    evidence_refs = _limited_refs(
        list(previous.get("evidence_refs", []) or [])
        + list(delta.get("evidence_refs", []) or [])
    )
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "project_id": _first_text(delta.get("project_id"), previous.get("project_id")),
        "run_id": _first_text(delta.get("run_id"), previous.get("run_id")),
        "chapter_number": chapter_number,
        "updated_at": datetime.now().isoformat(),
        "timeline": timeline,
        "goal_progress": goal_progress,
        "story_threads": story_threads,
        "characters": characters,
        "world_facts": world_facts,
        "evidence_refs": evidence_refs,
        "metadata": {
            "source_delta_schema_version": delta.get("schema_version"),
            "derived_from": "story_graph+plot_summary+chapter_metadata",
        },
    }


def record_narrative_state_after_save(
    *,
    project_dir: str | Path,
    project_id: str,
    chapter_number: int,
    story_graph_result: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    run_id: str | None = None,
    chapter_path: str = "",
    summary: str = "",
    key_events: list[str] | None = None,
    character_appearances: list[str] | None = None,
    goal_lock: str = "",
    unresolved_goals: list[str] | None = None,
) -> dict[str, Any]:
    """Persist the current narrative state after a chapter is accepted."""

    result = dict(story_graph_result or {})
    store = NarrativeStateStore(project_dir)
    delta = build_state_delta(
        project_id=project_id,
        run_id=run_id,
        chapter_number=chapter_number,
        story_graph_snapshot=result.get("snapshot"),
        rebaseline_delta=result.get("rebaseline_delta"),
        context=context,
        chapter_path=chapter_path,
        summary=summary,
        key_events=key_events,
        character_appearances=character_appearances,
        goal_lock=goal_lock,
        unresolved_goals=unresolved_goals,
    )
    snapshot = apply_state_delta(store.load_base_for_chapter(chapter_number), delta)
    snapshot_path = store.save_snapshot(snapshot)
    return {
        "snapshot": snapshot,
        "delta": delta,
        "snapshot_path": str(snapshot_path),
        "current_path": str(store.current_path),
    }


def build_narrative_state_packet(
    project_dir: str | Path,
    *,
    chapter_number: int,
) -> dict[str, Any]:
    """Return compact prompt-facing state for the next chapter."""

    store = NarrativeStateStore(project_dir)
    source = None
    if chapter_number > 1:
        source = store.load_snapshot(chapter_number - 1)
    if source is None:
        current = store.load_current()
        if current and int(current.get("chapter_number", 0) or 0) < int(chapter_number):
            source = current
    if not source:
        return {}

    characters = list((source.get("characters") or {}).values())
    characters.sort(
        key=lambda item: int(item.get("last_seen_chapter", 0) or 0),
        reverse=True,
    )
    goal_progress = dict(source.get("goal_progress", {}) or {})
    world_facts = dict(source.get("world_facts", {}) or {})
    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "target_chapter_number": int(chapter_number),
        "source_chapter_number": int(source.get("chapter_number", 0) or 0),
        "timeline": dict(source.get("timeline", {}) or {}),
        "active_characters": characters[:8],
        "goal_lock": goal_progress.get("goal_lock", ""),
        "completed_goal_subgoals": _clean_list(
            goal_progress.get("completed_goal_subgoals")
        )[-8:],
        "unresolved_goals": _clean_list(goal_progress.get("unresolved_goals"))[:8],
        "reached_destinations": _clean_list(
            goal_progress.get("reached_destinations")
        )[-8:],
        "recent_key_events": _clean_list(
            (source.get("story_threads") or {}).get("key_events")
        )[-8:],
        "world_fact_warnings": _unique(
            _clean_list(world_facts.get("challenged_world_facts"))
            + _clean_list(world_facts.get("prohibited_inheritance"))
        )[:8],
        "evidence_refs": _limited_refs(list(source.get("evidence_refs", []) or []), 8),
    }


def render_narrative_state_packet_summary(packet: dict[str, Any]) -> str:
    if not packet:
        return ""
    timeline = dict(packet.get("timeline", {}) or {})
    lines: list[str] = []
    source_chapter = packet.get("source_chapter_number")
    if source_chapter:
        lines.append(f"状态来源: 截至第{source_chapter}章")
    if timeline.get("physical_location"):
        lines.append(f"当前位置: {timeline['physical_location']}")
    if timeline.get("chapter_summary"):
        lines.append(f"最近进展: {timeline['chapter_summary']}")
    characters = [
        str(item.get("name"))
        for item in packet.get("active_characters", [])[:6]
        if isinstance(item, dict) and item.get("name")
    ]
    if characters:
        lines.append("近期角色: " + "、".join(characters))
    if packet.get("goal_lock"):
        lines.append(f"持续目标: {packet['goal_lock']}")
    if packet.get("unresolved_goals"):
        lines.append("未解决事项: " + "; ".join(packet["unresolved_goals"][:4]))
    if packet.get("world_fact_warnings"):
        lines.append("世界事实提醒: " + "; ".join(packet["world_fact_warnings"][:4]))
    return "\n".join(lines)


def _evidence_ref(chapter_path: str, chapter_number: int) -> dict[str, Any]:
    if not chapter_path:
        return {}
    path = Path(chapter_path)
    checksum = ""
    if path.exists():
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return {
        "source_path": str(path),
        "chapter_number": int(chapter_number),
        "checksum": checksum,
    }


def _atomic_write_text(path: Path, payload: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    temp_path.replace(path)


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, dict):
        values = [json.dumps(value, ensure_ascii=False, sort_keys=True)]
    else:
        try:
            values = list(value)
        except TypeError:
            values = [value]
    return [str(item).strip() for item in values if str(item or "").strip()]


def _normalize_fact_list(value: Any) -> list[str]:
    facts: list[str] = []
    for item in value or []:
        if isinstance(item, dict):
            label = _first_text(
                item.get("label"),
                item.get("fact"),
                item.get("summary"),
                item.get("description"),
            )
        else:
            label = _first_text(item)
        if label:
            facts.append(label)
    return _unique(facts)


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _without_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item not in ("", [], {}, None)}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _limited_refs(refs: list[Any], limit: int = 20) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        item = {
            "source_path": str(ref.get("source_path", "") or ""),
            "chapter_number": int(ref.get("chapter_number", 0) or 0),
            "checksum": str(ref.get("checksum", "") or ""),
        }
        key = (item["source_path"], item["chapter_number"], item["checksum"])
        if not item["source_path"] or key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned[-limit:]
