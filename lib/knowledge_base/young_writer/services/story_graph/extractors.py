"""Deterministic extractors from existing longform artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from young_writer.services.story_input import StoryInputBundle

from .models import EvidenceRef, StoryEdge, StoryNode, dataclass_to_dict


SCENE_HEADER_RE = re.compile(r"^【场景】(?P<anchor>.+)$", re.MULTILINE)
REMOTE_SIGNAL_RE = re.compile(
    r"(?:来自|发自|源自)(?P<source>[^，。；;\n]{2,24}?)(?:的)?(?:加密)?(?:求救|异常|回波|潮汐)?信号"
)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _pointer(path: str, pointer: str, excerpt: str, chapter_number: int) -> EvidenceRef:
    file_path = Path(path)
    checksum = _checksum(file_path) if file_path.exists() else ""
    return EvidenceRef(
        source_path=str(path),
        pointer=pointer,
        excerpt=str(excerpt or "")[:400],
        chapter_number=chapter_number,
        checksum=checksum,
    )


def _goal_subgoals(goal_lock: str) -> list[str]:
    parts = re.split(r"[、，,；;及并和/\n]+", str(goal_lock or ""))
    return [part.strip() for part in parts if len(part.strip()) >= 2] or ([goal_lock] if goal_lock else [])


def extract_planned_graph(
    bundle: StoryInputBundle | None,
    *,
    chapter_number: int,
    project_dir: str | Path,
) -> dict[str, Any]:
    if bundle is None:
        return {"nodes": [], "edges": [], "state": {}, "metadata": {}}

    plan = next(
        (
            item
            for item in bundle.chapter_plans
            if int(item.chapter_number) == int(chapter_number)
        ),
        None,
    )
    if plan is None:
        return {"nodes": [], "edges": [], "state": {}, "metadata": {}}

    project_dir = Path(project_dir)
    plan_path = project_dir / "story_input" / "chapter_plans.json"
    project_path = project_dir / "story_input" / "project_bible.json"
    world_path = project_dir / "story_input" / "world_bible.json"
    evidence = _pointer(str(plan_path), f"/chapter_plans/{chapter_number - 1}", plan.summary, chapter_number)
    nodes: list[StoryNode] = [
        StoryNode(
            id=f"chapter:{chapter_number}",
            type="ChapterPlan",
            label=plan.title or f"第{chapter_number}章",
            attrs={"summary": plan.summary, "purpose": plan.purpose, "goal_lock": plan.goal_lock},
            status="planned",
            chapter_number=chapter_number,
            source_refs=[evidence],
        )
    ]
    edges: list[StoryEdge] = []

    for event_index, event in enumerate(plan.key_events or [], start=1):
        event_id = f"planned_event:{chapter_number}:{event_index}"
        nodes.append(
            StoryNode(
                id=event_id,
                type="Event",
                label=event,
                attrs={"kind": "key_event"},
                status="planned",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:must_include:{event_index}",
                source=f"chapter:{chapter_number}",
                target=event_id,
                type="MUST_INCLUDE",
                status="planned",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )

    goal_lock = str(plan.goal_lock or "").strip()
    if goal_lock:
        goal_id = f"goal_lock:{chapter_number}"
        nodes.append(
            StoryNode(
                id=goal_id,
                type="GoalLock",
                label=goal_lock,
                attrs={"source": "chapter_plan.goal_lock"},
                status="planned",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:goal_lock",
                source=f"chapter:{chapter_number}",
                target=goal_id,
                type="PLANS",
                status="planned",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )
        for subgoal_index, subgoal in enumerate(_goal_subgoals(goal_lock), start=1):
            subgoal_id = f"goal_subgoal:{chapter_number}:{subgoal_index}"
            nodes.append(
                StoryNode(
                    id=subgoal_id,
                    type="GoalSubgoal",
                    label=subgoal,
                    attrs={"goal_lock": goal_lock},
                    status="planned",
                    chapter_number=chapter_number,
                    source_refs=[evidence],
                )
            )
            edges.append(
                StoryEdge(
                    id=f"edge:{goal_id}:subgoal:{subgoal_index}",
                    source=goal_id,
                    target=subgoal_id,
                    type="DECOMPOSES_TO",
                    status="planned",
                    chapter_number=chapter_number,
                    evidence=[evidence],
                )
            )

    location_path = str(world_path if world_path.exists() else project_path)
    for location_index, location_id in enumerate(plan.location_ids or [], start=1):
        label = str(location_id).split(":", 1)[-1]
        location_node = f"planned_location:{chapter_number}:{location_index}"
        location_evidence = _pointer(location_path, "/locations", label, chapter_number)
        nodes.append(
            StoryNode(
                id=location_node,
                type="Location",
                label=label,
                attrs={"modality": "target_destination"},
                status="planned",
                chapter_number=chapter_number,
                source_refs=[location_evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:destination:{location_index}",
                source=f"chapter:{chapter_number}",
                target=location_node,
                type="TARGET_DESTINATION",
                status="planned",
                chapter_number=chapter_number,
                evidence=[location_evidence],
            )
        )

    for fact_index, fact in enumerate(bundle.world_bible.hard_constraints or [], start=1):
        fact_evidence = _pointer(str(world_path), f"/hard_constraints/{fact_index - 1}", fact, chapter_number)
        fact_id = f"world_fact:{fact_index}"
        nodes.append(
            StoryNode(
                id=fact_id,
                type="WorldFact",
                label=fact,
                attrs={"state": "valid"},
                status="canon",
                chapter_number=chapter_number,
                source_refs=[fact_evidence],
            )
        )

    return {
        "nodes": dataclass_to_dict(nodes),
        "edges": dataclass_to_dict(edges),
        "state": {
            "goal_lock": goal_lock,
            "goal_subgoals": _goal_subgoals(goal_lock),
            "must_include_events": list(plan.key_events or []),
            "target_destinations": [str(item).split(":", 1)[-1] for item in plan.location_ids or []],
            "continuity_in": str(plan.continuity_in or ""),
            "continuity_out": str(plan.continuity_out or ""),
        },
        "metadata": {"source": "story_input"},
    }


def _scene_anchor_from_text(text: str) -> str:
    match = SCENE_HEADER_RE.search(text or "")
    if not match:
        return ""
    return str(match.group("anchor") or "").strip().split("，", 1)[0].strip()


def extract_chapter_markdown_graph(
    chapter_path: str | Path,
    *,
    chapter_number: int,
) -> dict[str, Any]:
    path = Path(chapter_path)
    if not path.exists():
        return {"nodes": [], "edges": [], "state": {}, "metadata": {}}
    text = path.read_text(encoding="utf-8")
    evidence = _pointer(str(path), "", text[:300], chapter_number)
    body_lines = [line.strip() for line in text.splitlines() if line.strip()]
    opening_excerpt = next((line for line in body_lines if not line.startswith("#")), "")
    scene_anchor = _scene_anchor_from_text(text)
    nodes: list[StoryNode] = []
    edges: list[StoryEdge] = []
    state: dict[str, Any] = {
        "opening_excerpt": opening_excerpt[:300],
        "scene_anchor": scene_anchor,
        "physical_location": scene_anchor,
    }
    if scene_anchor:
        location_id = f"physical_location:{chapter_number}"
        nodes.append(
            StoryNode(
                id=location_id,
                type="Location",
                label=scene_anchor,
                attrs={"modality": "physical"},
                status="canon",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:physical_location",
                source=f"chapter:{chapter_number}",
                target=location_id,
                type="PHYSICAL_LOCATION",
                status="canon",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )

    for signal_index, match in enumerate(REMOTE_SIGNAL_RE.finditer(text), start=1):
        source = str(match.group("source") or "").strip()
        if len(source) < 2:
            continue
        node_id = f"remote_signal:{chapter_number}:{signal_index}"
        signal_excerpt = text[max(match.start() - 30, 0) : min(match.end() + 40, len(text))]
        signal_evidence = _pointer(str(path), f"text:{match.start()}-{match.end()}", signal_excerpt, chapter_number)
        nodes.append(
            StoryNode(
                id=node_id,
                type="SignalSource",
                label=source,
                attrs={"modality": "remote_signal_source"},
                status="canon",
                chapter_number=chapter_number,
                source_refs=[signal_evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:remote_signal:{signal_index}",
                source=f"chapter:{chapter_number}",
                target=node_id,
                type="REMOTE_SIGNAL_SOURCE",
                status="canon",
                chapter_number=chapter_number,
                evidence=[signal_evidence],
            )
        )
    state["remote_signal_sources"] = [item["label"] for item in dataclass_to_dict(nodes) if item["type"] == "SignalSource"]
    return {
        "nodes": dataclass_to_dict(nodes),
        "edges": dataclass_to_dict(edges),
        "state": state,
        "metadata": {"source": "chapter_markdown"},
    }


def extract_plot_summary_graph(
    summary_path: str | Path,
    *,
    chapter_number: int,
) -> dict[str, Any]:
    path = Path(summary_path)
    if not path.exists():
        return {"nodes": [], "edges": [], "state": {}, "metadata": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence = _pointer(str(path), "", payload.get("brief_summary", ""), chapter_number)
    nodes: list[StoryNode] = []
    edges: list[StoryEdge] = []
    key_points = [str(item).strip() for item in payload.get("key_plot_points", []) if str(item).strip()]
    for index, point in enumerate(key_points, start=1):
        point_id = f"plot_point:{chapter_number}:{index}"
        nodes.append(
            StoryNode(
                id=point_id,
                type="Event",
                label=point,
                attrs={"kind": "plot_summary"},
                status="canon",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:plot_point:{index}",
                source=f"chapter:{chapter_number}",
                target=point_id,
                type="EVIDENCED_BY",
                status="canon",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )
    return {
        "nodes": dataclass_to_dict(nodes),
        "edges": dataclass_to_dict(edges),
        "state": {"plot_key_points": key_points, "brief_summary": str(payload.get("brief_summary", "") or "")},
        "metadata": {"source": "plot_summary"},
    }


def extract_film_drama_graph(
    film_drama_path: str | Path,
    *,
    chapter_number: int,
) -> dict[str, Any]:
    path = Path(film_drama_path)
    if not path.exists():
        return {"nodes": [], "edges": [], "state": {}, "metadata": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence = _pointer(str(path), "", str(payload.get("final_plot", "") or "")[:300], chapter_number)
    nodes: list[StoryNode] = []
    edges: list[StoryEdge] = []

    scene_anchor = _scene_anchor_from_text(str(payload.get("final_plot", "") or ""))
    if scene_anchor:
        node_id = f"film_drama_scene:{chapter_number}"
        nodes.append(
            StoryNode(
                id=node_id,
                type="Scene",
                label=scene_anchor,
                attrs={"source": "film_drama.final_plot"},
                status="draft",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:scene_anchor",
                source=f"chapter:{chapter_number}",
                target=node_id,
                type="SCENE_ANCHOR",
                status="draft",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )

    beats = []
    if isinstance(payload.get("plot_outline"), dict):
        beats = payload["plot_outline"].get("beats", []) or []
    for index, beat in enumerate(beats, start=1):
        if not isinstance(beat, dict):
            continue
        beat_desc = str(beat.get("desc", "") or "").strip()
        if not beat_desc:
            continue
        beat_id = f"beat:{chapter_number}:{index}"
        nodes.append(
            StoryNode(
                id=beat_id,
                type="Beat",
                label=beat_desc[:80],
                attrs={"phase": str(beat.get("type", "") or "")},
                status="draft",
                chapter_number=chapter_number,
                source_refs=[evidence],
            )
        )
        edges.append(
            StoryEdge(
                id=f"edge:chapter:{chapter_number}:beat:{index}",
                source=f"chapter:{chapter_number}",
                target=beat_id,
                type="CONTAINS_BEAT",
                status="draft",
                chapter_number=chapter_number,
                evidence=[evidence],
            )
        )
    return {
        "nodes": dataclass_to_dict(nodes),
        "edges": dataclass_to_dict(edges),
        "state": {"film_drama_scene_anchor": scene_anchor, "beat_count": len(beats)},
        "metadata": {"source": "film_drama"},
    }
