"""Derive small rebaseline deltas from accepted chapters."""

from __future__ import annotations

import re
from typing import Any


def split_goal_subgoals(goal_lock: str) -> list[str]:
    parts = re.split(r"[、，,；;及并和/\n]+", str(goal_lock or ""))
    values = [part.strip() for part in parts if len(part.strip()) >= 2]
    return values or ([goal_lock] if goal_lock else [])


def derive_rebaseline_delta(
    *,
    chapter_number: int,
    snapshot: dict[str, Any],
    chapter_graph_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet = dict(chapter_graph_packet or {})
    state = dict(snapshot.get("state", {}) or {})
    goal_lock = str(packet.get("goal_lock", "") or state.get("goal_lock", "") or "").strip()
    goal_subgoals = list(packet.get("goal_subgoals", []) or state.get("goal_subgoals", []))
    target_destinations = list(packet.get("target_destinations", []) or state.get("target_destinations", []))
    track_subgoal_completion = len(goal_subgoals) > 1
    summary_text = "\n".join(
        [
            str(state.get("chapter_summary", "") or ""),
            " ".join(str(item) for item in state.get("plot_key_points", []) or []),
            str(state.get("opening_excerpt", "") or ""),
        ]
    )

    completed_subgoals = [
        subgoal
        for subgoal in goal_subgoals
        if subgoal and subgoal in summary_text
    ] if track_subgoal_completion else []
    physical_location = str(state.get("physical_location", "") or "")
    reached_destinations = [
        item for item in target_destinations if item and physical_location and item in physical_location
    ]

    challenged_world_facts: list[dict[str, str]] = []
    if "而非" in summary_text:
        challenged_world_facts.append(
            {
                "evidence": summary_text[:200],
                "kind": "contrastive_reveal",
            }
        )

    if not completed_subgoals and not reached_destinations and not challenged_world_facts:
        return {}

    return {
        "schema_version": "story_graph.rebaseline.v1",
        "chapter_number": int(chapter_number),
        "goal_lock": goal_lock,
        "completed_goal_subgoals": completed_subgoals,
        "destination_reached": reached_destinations,
        "challenged_world_facts": challenged_world_facts,
        "recommended_action": "rebaseline",
        "plan_stale": bool(completed_subgoals or reached_destinations),
    }
