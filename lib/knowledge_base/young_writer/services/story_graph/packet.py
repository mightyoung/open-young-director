"""Compact per-chapter graph packet used during generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from young_writer.services.story_input import load_story_input_bundle

from .build import build_story_graph_snapshot
from .store import StoryGraphStore


def build_chapter_graph_packet(
    project_dir: str | Path,
    *,
    chapter_number: int,
) -> dict[str, Any]:
    project_path = Path(project_dir)
    bundle = load_story_input_bundle(project_path)
    plan = None
    if bundle is not None:
        plan = next(
            (
                item
                for item in bundle.chapter_plans
                if int(item.chapter_number) == int(chapter_number)
            ),
            None,
        )

    store = StoryGraphStore(project_path)
    previous_snapshot = None
    if chapter_number > 1:
        previous_snapshot = store.load_snapshot(chapter_number - 1)
        if previous_snapshot is None:
            previous_snapshot = build_story_graph_snapshot(
                project_path,
                chapter_number=chapter_number - 1,
                persist=False,
            )

    deltas = store.load_rebaseline_deltas(before_chapter=chapter_number)
    completed_goal_subgoals: list[str] = []
    challenged_world_facts: list[dict[str, Any]] = []
    reached_destinations: list[str] = []
    for delta in deltas:
        completed_goal_subgoals.extend(delta.get("completed_goal_subgoals", []) or [])
        challenged_world_facts.extend(delta.get("challenged_world_facts", []) or [])
        reached_destinations.extend(delta.get("destination_reached", []) or [])

    goal_lock = str(getattr(plan, "goal_lock", "") or "").strip()
    target_destinations = [
        str(item).split(":", 1)[-1] for item in getattr(plan, "location_ids", []) or []
    ]
    goal_subgoals = [
        item
        for item in (goal_lock.replace("，", "、").replace(",", "、").split("、") if goal_lock else [])
        if item.strip()
    ] or ([goal_lock] if goal_lock else [])
    singleton_macro_goal = len(goal_subgoals) == 1 and goal_subgoals[0] == goal_lock
    if singleton_macro_goal:
        completed_goal_subgoals = []
    remaining_goal_subgoals = [
        item for item in goal_subgoals if item not in completed_goal_subgoals
    ]

    previous_state = dict(previous_snapshot.get("state", {}) or {}) if previous_snapshot else {}
    previous_anchor = str(previous_state.get("scene_anchor", "") or previous_state.get("physical_location", "") or "")
    current_plan_anchor = target_destinations[0] if target_destinations else ""
    opening_bridge = ""
    if previous_anchor and current_plan_anchor and previous_anchor != current_plan_anchor:
        opening_bridge = (
            f"开篇先接住「{previous_anchor}」；如需切到「{current_plan_anchor}」，"
            "必须写出路径、抵达动作或切换原因。"
        )
    chapter_goal = ""
    must_include_events = list(getattr(plan, "key_events", []) or [])
    if must_include_events:
        chapter_goal = str(must_include_events[0]).strip()
    if not chapter_goal and remaining_goal_subgoals:
        chapter_goal = str(remaining_goal_subgoals[0]).strip()
    if not chapter_goal:
        chapter_goal = goal_lock

    success_evidence: list[str] = []
    if chapter_goal:
        success_evidence.append(f"正文出现与「{chapter_goal}」直接相关的关键行动或结果。")
    if opening_bridge:
        success_evidence.append("开篇明确交代上一章场景如何过渡到本章场景。")
    for event in must_include_events[:2]:
        success_evidence.append(f"覆盖关键事件：{event}")
    for destination in target_destinations[:1]:
        success_evidence.append(f"若前往目标地点，正文需写出抵达或接近「{destination}」的动作。")

    packet = {
        "schema_version": "chapter_graph_packet.v1",
        "chapter_number": int(chapter_number),
        "goal_lock": goal_lock,
        "goal_subgoals": goal_subgoals,
        "remaining_goal_subgoals": remaining_goal_subgoals,
        "chapter_goal": chapter_goal,
        "required_bridge": opening_bridge or str(getattr(plan, "continuity_in", "") or ""),
        "success_evidence": success_evidence,
        "must_include_events": must_include_events,
        "target_destinations": target_destinations,
        "completed_goal_subgoals": sorted({str(item) for item in completed_goal_subgoals if str(item).strip()}),
        "challenged_world_facts": challenged_world_facts,
        "reached_destinations": sorted({str(item) for item in reached_destinations if str(item).strip()}),
        "previous_scene_anchor": previous_anchor,
        "previous_physical_location": str(previous_state.get("physical_location", "") or ""),
        "previous_opening_excerpt": str(previous_state.get("opening_excerpt", "") or ""),
        "opening_bridge_required": opening_bridge,
        "continuity_in": str(getattr(plan, "continuity_in", "") or ""),
        "continuity_out": str(getattr(plan, "continuity_out", "") or ""),
        "rebaseline_deltas": deltas,
        "prohibited_inheritance": [
            "不要继续把 remote signal source 当作当前物理场景位置。"
        ],
    }
    return packet


def render_chapter_graph_packet_summary(packet: dict[str, Any]) -> str:
    if not packet:
        return ""
    lines: list[str] = []
    if packet.get("previous_scene_anchor"):
        lines.append(f"上一场景锚点: {packet['previous_scene_anchor']}")
    if packet.get("opening_bridge_required"):
        lines.append(f"开篇补桥: {packet['opening_bridge_required']}")
    if packet.get("goal_lock"):
        lines.append(f"当前目标锁: {packet['goal_lock']}")
    if packet.get("chapter_goal"):
        lines.append(f"本章目标: {packet['chapter_goal']}")
    if packet.get("required_bridge"):
        lines.append(f"必补桥段: {packet['required_bridge']}")
    if packet.get("completed_goal_subgoals"):
        lines.append(
            "已完成分项: " + "、".join(str(item) for item in packet["completed_goal_subgoals"][:4])
        )
    if packet.get("target_destinations"):
        lines.append(
            "目标地点: " + "、".join(str(item) for item in packet["target_destinations"][:3])
        )
    if packet.get("success_evidence"):
        lines.append(
            "验收证据: " + "；".join(str(item) for item in packet["success_evidence"][:3])
        )
    return "\n".join(lines)
