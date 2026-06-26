"""Minimal data models for local story graph state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass
class EvidenceRef:
    source_path: str
    excerpt: str = ""
    pointer: str = ""
    chapter_number: int | None = None
    checksum: str = ""


@dataclass
class StoryNode:
    id: str
    type: str
    label: str
    attrs: dict[str, Any] = field(default_factory=dict)
    status: str = "canon"
    chapter_number: int | None = None
    source_refs: list[EvidenceRef] = field(default_factory=list)


@dataclass
class StoryEdge:
    id: str
    source: str
    target: str
    type: str
    attrs: dict[str, Any] = field(default_factory=dict)
    status: str = "canon"
    chapter_number: int | None = None
    evidence: list[EvidenceRef] = field(default_factory=list)


@dataclass
class StoryGraphSnapshot:
    schema_version: str
    project_id: str
    chapter_number: int
    nodes: list[StoryNode] = field(default_factory=list)
    edges: list[StoryEdge] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def dataclass_to_dict(value: Any) -> Any:
    """Convert nested dataclasses to plain dict/list payloads."""
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [dataclass_to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: dataclass_to_dict(item) for key, item in value.items()}
    return value
