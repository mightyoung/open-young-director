"""Build story graph snapshots from existing project artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from young_writer.services.story_input import load_story_input_bundle

from .extractors import (
    extract_chapter_markdown_graph,
    extract_film_drama_graph,
    extract_planned_graph,
    extract_plot_summary_graph,
)
from .models import StoryGraphSnapshot, dataclass_to_dict
from .rebaseline import derive_rebaseline_delta
from .store import StoryGraphStore


def _chapter_file(project_dir: Path, chapter_number: int) -> Path | None:
    chapters_dir = project_dir / "chapters"
    matches = sorted(chapters_dir.glob(f"ch{int(chapter_number):03d}_*.md"))
    return matches[0] if matches else None


def _merge_graph_parts(parts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges_by_id: dict[str, dict[str, Any]] = {}
    state: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    for part in parts:
        for node in part.get("nodes", []):
            if isinstance(node, dict) and node.get("id"):
                nodes_by_id[str(node["id"])] = node
        for edge in part.get("edges", []):
            if isinstance(edge, dict) and edge.get("id"):
                edges_by_id[str(edge["id"])] = edge
        state.update(dict(part.get("state", {}) or {}))
        metadata.update(dict(part.get("metadata", {}) or {}))
    return list(nodes_by_id.values()), list(edges_by_id.values()), state, metadata


def build_story_graph_snapshot(
    project_dir: str | Path,
    *,
    chapter_number: int,
    project_id: str = "",
    persist: bool = False,
) -> dict[str, Any]:
    project_path = Path(project_dir)
    bundle = load_story_input_bundle(project_path)
    parts: list[dict[str, Any]] = [
        extract_planned_graph(bundle, chapter_number=chapter_number, project_dir=project_path)
    ]
    chapter_path = _chapter_file(project_path, chapter_number)
    if chapter_path is not None:
        parts.append(
            extract_chapter_markdown_graph(chapter_path, chapter_number=chapter_number)
        )
    summary_path = project_path / "plot_summaries" / f"ch{int(chapter_number):03d}_summary.json"
    parts.append(extract_plot_summary_graph(summary_path, chapter_number=chapter_number))
    film_drama_path = project_path / "film_drama" / f"ch{int(chapter_number):03d}_film_drama.json"
    parts.append(extract_film_drama_graph(film_drama_path, chapter_number=chapter_number))

    nodes, edges, state, metadata = _merge_graph_parts(parts)
    state.setdefault("chapter_summary", "")
    if summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        state["chapter_summary"] = str(payload.get("brief_summary", "") or "")

    snapshot = dataclass_to_dict(
        StoryGraphSnapshot(
            schema_version="story_graph.snapshot.v1",
            project_id=project_id or project_path.name,
            chapter_number=int(chapter_number),
            nodes=[],
            edges=[],
            state=state,
            metadata=metadata,
        )
    )
    snapshot["nodes"] = nodes
    snapshot["edges"] = edges
    if persist:
        StoryGraphStore(project_path).save_snapshot(snapshot, chapter_number=chapter_number)
    return snapshot


def record_story_graph_after_save(
    *,
    project_dir: str | Path,
    project_id: str,
    chapter_number: int,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    store = StoryGraphStore(project_dir)
    snapshot = build_story_graph_snapshot(
        project_dir,
        chapter_number=chapter_number,
        project_id=project_id,
        persist=True,
    )
    delta = derive_rebaseline_delta(
        chapter_number=chapter_number,
        snapshot=snapshot,
        chapter_graph_packet=(context or {}).get("chapter_graph_packet", {}),
    )
    delta_path = None
    if delta:
        delta_path = store.save_rebaseline_delta(chapter_number, delta)
    events: list[dict[str, Any]] = [
        {
            "event": "snapshot_saved",
            "chapter_number": int(chapter_number),
            "snapshot_path": str(store.snapshot_root / f"ch{int(chapter_number):03d}.json"),
        }
    ]
    if delta_path is not None:
        events.append(
            {
                "event": "rebaseline_delta_saved",
                "chapter_number": int(chapter_number),
                "delta_path": str(delta_path),
            }
        )
    store.append_events(events)
    return {
        "snapshot": snapshot,
        "snapshot_path": str(store.snapshot_root / f"ch{int(chapter_number):03d}.json"),
        "rebaseline_delta": delta,
        "rebaseline_delta_path": str(delta_path) if delta_path is not None else "",
    }
