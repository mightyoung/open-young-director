"""Deterministic narrative driver packets for chapter generation."""

# ruff: noqa: RUF001

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


SCHEMA_VERSION = "chapter_driver_packet.v1"


def build_chapter_driver_packet(
    packet: Any,
    chapter_graph_packet: dict[str, Any] | None = None,
    effective_goal_lock: str = "",
) -> dict[str, Any]:
    """Build scene/beat level driver variables from structured chapter input."""
    packet_data = _to_mapping(packet)
    plan = _to_mapping(packet_data.get("chapter_plan"))
    world = _to_mapping(packet_data.get("world_bible"))
    characters = _to_list(packet_data.get("characters"))
    runtime = _to_mapping(packet_data.get("runtime_overrides"))
    graph = dict(chapter_graph_packet or {})

    chapter_number = _as_int(
        packet_data.get("chapter_number") or plan.get("chapter_number"),
        default=0,
    )
    key_events = _clean_list(plan.get("key_events"))
    must_include = _clean_list(plan.get("must_include"))
    success_evidence = _clean_list(graph.get("success_evidence"))
    target_destinations = _clean_list(graph.get("target_destinations"))
    locations = _resolve_locations(plan, world, target_destinations)
    cast_names = _resolve_cast_names(plan, characters)
    goal_lock = _clean_text(
        plan.get("goal_lock") or graph.get("goal_lock") or effective_goal_lock
    )
    chapter_goal = _clean_text(graph.get("chapter_goal")) or _first_non_empty(
        key_events,
        goal_lock,
        _clean_text(plan.get("summary")),
    )
    required_bridge = _clean_text(
        graph.get("required_bridge")
        or graph.get("opening_bridge_required")
        or plan.get("continuity_in")
    )

    scene_sources = _scene_sources(
        required_bridge=required_bridge,
        key_events=key_events,
        must_include=must_include,
        continuity_out=_clean_text(plan.get("continuity_out")),
        chapter_goal=chapter_goal,
    )
    scene_beats = [
        _build_scene_beat(
            index=index,
            source=source,
            location=_pick(locations, index - 1),
            cast=cast_names,
            success_evidence=_pick(success_evidence, index - 1),
            fallback_goal=chapter_goal,
        )
        for index, source in enumerate(scene_sources, start=1)
    ]

    emotional_arc = _build_emotional_arc(plan, runtime)
    tension_points = _build_tension_points(
        goal_lock=goal_lock,
        required_bridge=required_bridge,
        key_events=key_events,
        world=world,
        graph=graph,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "chapter_number": chapter_number,
        "scene_beats": scene_beats,
        "cast": _build_cast(characters, cast_names, chapter_goal, goal_lock, plan),
        "emotional_arc": emotional_arc,
        "tension_points": tension_points,
        "cliffhanger": _build_cliffhanger(plan, key_events, graph),
        "driver_notes": _build_driver_notes(
            goal_lock=goal_lock,
            chapter_goal=chapter_goal,
            required_bridge=required_bridge,
            magic_line=_clean_text(plan.get("magic_line")),
            previous_summary=_clean_text(runtime.get("previous_summary")),
        ),
    }


def finalize_chapter_driver_context(context: dict[str, Any]) -> dict[str, Any]:
    """Recompute driver fields from the final prompt-facing context."""
    packet = context.get("generation_packet")
    if not isinstance(packet, dict):
        return context
    graph = context.get("chapter_graph_packet")
    driver = build_chapter_driver_packet(
        packet,
        chapter_graph_packet=graph if isinstance(graph, dict) else None,
        effective_goal_lock=_resolve_effective_goal_lock(context),
    )
    context["chapter_driver_packet"] = driver
    context["chapter_driver_summary"] = render_chapter_driver_packet_summary(driver)
    context["chapter_driver_validation"] = validate_chapter_driver_packet(driver)
    return context


def render_chapter_driver_packet_summary(packet: dict[str, Any]) -> str:
    """Render a compact prompt-facing summary of the driver packet."""
    if not packet:
        return ""
    lines: list[str] = []
    scene_beats = _to_list(packet.get("scene_beats"))
    if scene_beats:
        rendered_beats: list[str] = []
        for beat in scene_beats[:4]:
            data = _to_mapping(beat)
            action = _clean_text(data.get("action"))
            turn = _clean_text(data.get("turn"))
            evidence = _clean_text(data.get("success_evidence"))
            parts = [action]
            if turn:
                parts.append(f"转折: {turn}")
            if evidence:
                parts.append(f"验收: {evidence}")
            rendered_beats.append(
                f"{data.get('index', len(rendered_beats) + 1)}. "
                + "；".join(parts)
            )
        lines.append("场景节拍: " + " / ".join(rendered_beats))

    cast = _to_list(packet.get("cast"))
    if cast:
        cast_parts = []
        for item in cast[:6]:
            data = _to_mapping(item)
            name = _clean_text(data.get("name"))
            objective = _clean_text(data.get("objective"))
            pressure = _clean_text(data.get("pressure"))
            if name:
                cast_parts.append(
                    f"{name}({objective or '跟随本章目标'}"
                    + (f"，压力: {pressure}" if pressure else "")
                    + ")"
                )
        if cast_parts:
            lines.append("角色驱动: " + "；".join(cast_parts))

    emotional_arc = _clean_list(packet.get("emotional_arc"))
    if emotional_arc:
        lines.append("情绪弧: " + " -> ".join(emotional_arc[:4]))
    tension_points = _clean_list(packet.get("tension_points"))
    if tension_points:
        lines.append("压力点: " + "；".join(tension_points[:4]))
    cliffhanger = _clean_text(packet.get("cliffhanger"))
    if cliffhanger:
        lines.append(f"结尾钩子: {cliffhanger}")
    notes = _clean_list(packet.get("driver_notes"))
    if notes:
        lines.append("执行提示: " + "；".join(notes[:4]))
    return "\n".join(lines)


def validate_chapter_driver_packet(packet: dict[str, Any]) -> list[str]:
    """Return validation issues for a driver packet without blocking generation."""
    issues: list[str] = []
    if not isinstance(packet, dict):
        return ["chapter_driver_packet must be a dict"]
    if packet.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version must be chapter_driver_packet.v1")
    if not isinstance(packet.get("scene_beats", []), list):
        issues.append("scene_beats must be a list")
    if not isinstance(packet.get("cast", []), list):
        issues.append("cast must be a list")
    if not isinstance(packet.get("emotional_arc", []), list):
        issues.append("emotional_arc must be a list")
    if not isinstance(packet.get("tension_points", []), list):
        issues.append("tension_points must be a list")
    if not isinstance(packet.get("driver_notes", []), list):
        issues.append("driver_notes must be a list")
    return issues


def _to_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key, None))
    }


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _resolve_effective_goal_lock(context: dict[str, Any]) -> str:
    resolution = context.get("goal_lock_resolution")
    if isinstance(resolution, dict):
        value = _clean_text(resolution.get("effective_goal_lock"))
        if value:
            return value
    value = _clean_text(context.get("goal_lock"))
    if value:
        return value
    packet = _to_mapping(context.get("generation_packet"))
    runtime = _to_mapping(packet.get("runtime_overrides"))
    payload = _to_mapping(runtime.get("volume_guidance_payload"))
    return _clean_text(payload.get("goal_lock"))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_list(value: Any) -> list[str]:
    return [item for item in (_clean_text(item) for item in _to_list(value)) if item]


def _as_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                text = _clean_text(item)
                if text:
                    return text
        else:
            text = _clean_text(value)
            if text:
                return text
    return ""


def _pick(values: list[str], index: int) -> str:
    if not values:
        return ""
    return values[min(index, len(values) - 1)]


def _resolve_locations(
    plan: dict[str, Any],
    world: dict[str, Any],
    target_destinations: list[str],
) -> list[str]:
    locations = _clean_list(world.get("locations"))
    location_ids = [
        item.split(":", 1)[-1] for item in _clean_list(plan.get("location_ids"))
    ]
    resolved: list[str] = []
    for raw in [*target_destinations, *location_ids]:
        clean = _clean_text(raw)
        if not clean:
            continue
        match = next((location for location in locations if clean in location), clean)
        if match not in resolved:
            resolved.append(match)
    for location in locations:
        if location not in resolved:
            resolved.append(location)
    return resolved


def _resolve_cast_names(plan: dict[str, Any], characters: list[Any]) -> list[str]:
    names = _clean_list(plan.get("character_names"))
    character_map = {
        _clean_text(_to_mapping(character).get("name")): _to_mapping(character)
        for character in characters
    }
    for character_id in _clean_list(plan.get("character_ids")):
        candidate = character_id.split(":", 1)[-1]
        if candidate in character_map and candidate not in names:
            names.append(candidate)
    for name in character_map:
        if name and name not in names:
            names.append(name)
    return names[:8]


def _scene_sources(
    *,
    required_bridge: str,
    key_events: list[str],
    must_include: list[str],
    continuity_out: str,
    chapter_goal: str,
) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    if required_bridge:
        sources.append(("承接", required_bridge))
    sources.extend(("行动", event) for event in key_events[:4])
    for item in must_include[:3]:
        if item not in [source for _, source in sources]:
            sources.append(("必含", item))
    if continuity_out:
        sources.append(("余波", continuity_out))
    if not sources and chapter_goal:
        sources.append(("行动", chapter_goal))
    return sources[:6]


def _build_scene_beat(
    *,
    index: int,
    source: tuple[str, str],
    location: str,
    cast: list[str],
    success_evidence: str,
    fallback_goal: str,
) -> dict[str, Any]:
    purpose, action = source
    evidence = (
        success_evidence
        or f"正文出现与「{action or fallback_goal}」直接相关的行动或结果。"
    )
    return {
        "index": index,
        "purpose": purpose,
        "location": location,
        "cast": cast[:5],
        "action": action or fallback_goal,
        "turn": _infer_turn(purpose, action),
        "success_evidence": evidence,
    }


def _infer_turn(purpose: str, action: str) -> str:
    if purpose == "承接":
        return "把上一章后果转成本章行动压力"
    if purpose == "余波":
        return "把本章行动结果转入下一章钩子"
    if any(keyword in action for keyword in ("确认", "揭开", "发现", "公开")):
        return "信息差被压缩，角色判断发生变化"
    if any(keyword in action for keyword in ("进入", "潜入", "抵达", "前往")):
        return "空间位置变化带来新的风险"
    if any(keyword in action for keyword in ("守住", "击败", "对抗", "阻止")):
        return "外部压力升级为正面冲突"
    return "局势或人物关系发生可见变化"


def _build_cast(
    characters: list[Any],
    cast_names: list[str],
    chapter_goal: str,
    goal_lock: str,
    plan: dict[str, Any],
) -> list[dict[str, str]]:
    character_data = [_to_mapping(character) for character in characters]
    by_name = {_clean_text(item.get("name")): item for item in character_data}
    cast: list[dict[str, str]] = []
    for name in cast_names:
        item = by_name.get(name, {})
        objective = chapter_goal or goal_lock or _clean_text(item.get("motivation"))
        pressure = _clean_text(plan.get("emotional_turn")) or _clean_text(item.get("arc"))
        cast.append(
            {
                "name": name,
                "role": _clean_text(item.get("role") or item.get("identity"))
                or "关键角色",
                "objective": objective,
                "pressure": pressure,
                "relationship_signal": "、".join(
                    _clean_list(item.get("relationships"))[:3]
                ),
            }
        )
    return cast


def _build_emotional_arc(
    plan: dict[str, Any],
    runtime: dict[str, Any],
) -> list[str]:
    arc: list[str] = []
    previous_summary = _clean_text(runtime.get("previous_summary"))
    continuity_in = _clean_text(plan.get("continuity_in"))
    emotional_turn = _clean_text(plan.get("emotional_turn"))
    continuity_out = _clean_text(plan.get("continuity_out"))
    if previous_summary or continuity_in:
        arc.append(continuity_in or "承接上一章未完成后果")
    if emotional_turn:
        arc.append(emotional_turn)
    elif _clean_text(plan.get("purpose")):
        arc.append(_clean_text(plan.get("purpose")))
    if continuity_out:
        arc.append(continuity_out)
    elif _clean_text(plan.get("magic_line")):
        arc.append(_clean_text(plan.get("magic_line")))
    return arc[:4]


def _build_tension_points(
    *,
    goal_lock: str,
    required_bridge: str,
    key_events: list[str],
    world: dict[str, Any],
    graph: dict[str, Any],
) -> list[str]:
    points: list[str] = []
    if required_bridge:
        points.append(f"必须先补足承接: {required_bridge}")
    if goal_lock:
        points.append(f"主线目标不可漂移: {goal_lock}")
    points.extend(f"关键事件必须落地: {event}" for event in key_events[:2])
    points.extend(
        f"世界硬约束: {fact}"
        for fact in _clean_list(world.get("hard_constraints"))[:2]
    )
    for fact in _to_list(graph.get("challenged_world_facts"))[:2]:
        data = _to_mapping(fact)
        text = _clean_text(data.get("fact") or data.get("summary") or fact)
        if text:
            points.append(f"已挑战设定需处理: {text}")
    return points[:6]


def _build_cliffhanger(
    plan: dict[str, Any],
    key_events: list[str],
    graph: dict[str, Any],
) -> str:
    continuity_out = _clean_text(plan.get("continuity_out"))
    if continuity_out:
        return continuity_out
    if _clean_text(plan.get("magic_line")):
        return _clean_text(plan.get("magic_line"))
    destinations = _clean_list(graph.get("target_destinations"))
    if destinations:
        return f"以接近或抵达「{destinations[0]}」后的新风险收束。"
    if key_events:
        return f"让「{key_events[-1]}」产生下一章必须回应的余波。"
    return ""


def _build_driver_notes(
    *,
    goal_lock: str,
    chapter_goal: str,
    required_bridge: str,
    magic_line: str,
    previous_summary: str,
) -> list[str]:
    notes: list[str] = []
    if previous_summary or required_bridge:
        notes.append("开篇先回应上一章后果，再进入本章新行动。")
    if goal_lock:
        notes.append(f"每个主要场景都要回扣目标锁「{goal_lock}」。")
    if chapter_goal and chapter_goal != goal_lock:
        notes.append(f"本章至少写出一次可验证结果「{chapter_goal}」。")
    if magic_line:
        notes.append(f"暗线只能作为推进变量，不能冲散主线: {magic_line}")
    return notes[:5]
