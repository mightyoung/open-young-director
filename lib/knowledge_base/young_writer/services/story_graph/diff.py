"""Build structured graph diff evidence for quality reports."""

from __future__ import annotations

from typing import Any


def build_graph_diff_details(
    *,
    chapter_number: int,
    context: dict[str, Any] | None,
    missing_events: list[str],
    continuity_issues: list[Any],
    world_fact_issues: list[str],
    anti_drift_details: dict[str, Any],
    hard_gate_issue_types: list[str],
) -> dict[str, Any]:
    packet = dict((context or {}).get("chapter_graph_packet", {}) or {})
    planned_edges: list[dict[str, Any]] = []
    draft_edges: list[dict[str, Any]] = []
    missing_edges: list[dict[str, Any]] = []
    conflicting_edges: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, Any]] = []

    for event in packet.get("must_include_events", []) or []:
        planned_edges.append(
            {
                "type": "MUST_INCLUDE",
                "label": str(event),
            }
        )
    for subgoal in packet.get("goal_subgoals", []) or []:
        planned_edges.append(
            {
                "type": "GOAL_SUBGOAL",
                "label": str(subgoal),
            }
        )

    for event in anti_drift_details.get("covered_subgoals", []) or []:
        draft_edges.append({"type": "GOAL_PROGRESS", "label": str(event)})
    for fragment in anti_drift_details.get("matched_fragments", []) or []:
        evidence_refs.append(
            {
                "kind": "goal_alignment_fragment",
                "excerpt": str(fragment)[:300],
                "chapter_number": chapter_number,
            }
        )

    for event in missing_events:
        missing_edges.append({"type": "MUST_INCLUDE", "label": str(event)})
    for issue in continuity_issues:
        if isinstance(issue, dict):
            missing_edges.append(
                {
                    "type": "SCENE_BRIDGE",
                    "label": str(issue.get("message", "") or ""),
                }
            )
            evidence_refs.append(
                {
                    "kind": "continuity",
                    "excerpt": str(issue.get("message", "") or "")[:300],
                    "previous_evidence": str(issue.get("previous_evidence", "") or ""),
                    "current_evidence": str(issue.get("current_evidence", "") or ""),
                    "chapter_number": chapter_number,
                }
            )
    for issue in world_fact_issues:
        conflicting_edges.append({"type": "WORLD_FACT", "label": str(issue)})

    recommended_action = "accept"
    if hard_gate_issue_types:
        if set(hard_gate_issue_types) <= {"missing_key_events", "goal_lock_false_inheritance", "scene_or_timeline_disconnect"}:
            recommended_action = "rewrite"
        else:
            recommended_action = "chapter_review"
    elif packet.get("rebaseline_deltas"):
        recommended_action = "rebaseline"

    return {
        "schema_version": "graph_diff_details.v1",
        "planned_edges": planned_edges,
        "draft_edges": draft_edges,
        "missing_edges": missing_edges,
        "conflicting_edges": conflicting_edges,
        "evidence_refs": evidence_refs,
        "recommended_action": recommended_action,
    }
