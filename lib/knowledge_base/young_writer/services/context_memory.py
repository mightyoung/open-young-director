"""Prompt-facing memory context arbitration for longform generation."""

from __future__ import annotations

import re
from typing import Any


PACKET_SCHEMA_VERSION = "memory_context_packet.v1"


def build_memory_context_packet(
    *,
    chapter_number: int,
    chapter_graph_packet: dict[str, Any] | None = None,
    chapter_graph_summary: str = "",
    narrative_state_packet: dict[str, Any] | None = None,
    narrative_state_summary: str = "",
    longform_memory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build one ordered memory packet for prompt rendering.

    Story graph and narrative state own the current/control facts. Longform
    memory remains available as provenance, but repeated facts are suppressed
    before prompt rendering.
    """

    graph_packet = dict(chapter_graph_packet or {})
    state_packet = dict(narrative_state_packet or {})
    memory_items = [dict(item) for item in (longform_memory or []) if isinstance(item, dict)]
    covered_facts = _covered_fact_keys(graph_packet, chapter_graph_summary)
    covered_facts.update(_covered_fact_keys(state_packet, narrative_state_summary))

    evidence_items: list[dict[str, Any]] = []
    suppressed_duplicates: list[dict[str, Any]] = []
    seen_evidence: set[str] = set()

    for item in memory_items:
        text = _memory_text(item)
        key = _fact_key(text)
        if not key:
            continue
        duplicate = _is_covered(key, covered_facts)
        rendered_item = {
            "chapter_number": item.get("chapter_number"),
            "memory_type": item.get("memory_type", ""),
            "summary": item.get("summary", ""),
            "content_excerpt": item.get("content_excerpt", ""),
            "artifact_path": item.get("artifact_path", ""),
            "artifact_checksum": item.get("artifact_checksum", ""),
            "score": item.get("score"),
            "text": text,
        }
        if duplicate:
            suppressed_duplicates.append(rendered_item)
            continue
        evidence_key = _fact_key(
            f"{rendered_item['chapter_number']} {rendered_item['memory_type']} {text}"
        )
        if evidence_key in seen_evidence:
            continue
        seen_evidence.add(evidence_key)
        evidence_items.append(rendered_item)

    return {
        "schema_version": PACKET_SCHEMA_VERSION,
        "chapter_number": int(chapter_number),
        "chapter_graph_summary": chapter_graph_summary,
        "narrative_state_summary": narrative_state_summary,
        "longform_evidence": evidence_items,
        "suppressed_longform_duplicates": suppressed_duplicates,
    }


def render_memory_context_packet_summary(packet: dict[str, Any]) -> str:
    """Render the unified memory packet in prompt priority order."""

    if not packet:
        return ""
    lines: list[str] = []
    graph_summary = str(packet.get("chapter_graph_summary", "") or "").strip()
    if graph_summary:
        lines.append("剧情状态图摘要:")
        lines.extend(graph_summary.splitlines())
    state_summary = str(packet.get("narrative_state_summary", "") or "").strip()
    if state_summary:
        lines.append("持久叙事状态:")
        lines.extend(state_summary.splitlines())
    evidence = packet.get("longform_evidence") or []
    if evidence:
        lines.append("长程记忆证据:")
        for item in evidence:
            if not isinstance(item, dict):
                continue
            text = _memory_text(item)
            if not text:
                continue
            lines.append(
                f"- 第{item.get('chapter_number')}章 "
                f"{item.get('memory_type')}: {text}"
            )
    suppressed = packet.get("suppressed_longform_duplicates") or []
    if suppressed:
        refs = _duplicate_refs(suppressed)
        if refs:
            lines.append("长程记忆重复证据已合并: " + "、".join(refs))
    return "\n".join(lines)


def _covered_fact_keys(packet: dict[str, Any], rendered_summary: str = "") -> set[str]:
    keys: set[str] = set()
    for value in _walk_values(packet):
        key = _fact_key(value)
        if key:
            keys.add(key)
    for line in rendered_summary.splitlines():
        key = _fact_key(line)
        if key:
            keys.add(key)
    return keys


def _walk_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_walk_values(item))
        return result
    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            result.extend(_walk_values(item))
        return result
    if isinstance(value, (int, float, bool)):
        return []
    return [str(value)]


def _memory_text(item: dict[str, Any]) -> str:
    return str(item.get("summary") or item.get("text") or item.get("content_excerpt") or "").strip()


def _fact_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\s\u3000]+", "", text)
    punctuation = (
        r"[\uFF0C,\u3002\uFF1B;\uFF1A:\u3001.!\uFF01\uFF1F?"
        r"\u300A\u300B\u300C\u300D\u300E\u300F\u3010\u3011"
        r"\[\]()\uFF08\uFF09\-—_\"']"
    )
    return re.sub(punctuation, "", text)


def _is_covered(memory_key: str, covered_facts: set[str]) -> bool:
    if not memory_key:
        return False
    for fact in covered_facts:
        if not fact:
            continue
        if memory_key == fact or memory_key in fact or fact in memory_key:
            return True
    return False


def _duplicate_refs(items: list[Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        chapter = item.get("chapter_number")
        memory_type = str(item.get("memory_type", "") or "").strip()
        ref = f"第{chapter}章 {memory_type}".strip()
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs[:8]
