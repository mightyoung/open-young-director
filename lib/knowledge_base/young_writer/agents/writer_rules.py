"""Curated machine-readable subset of WRITER.md."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "writer_rules.json"
WRITER_PATH = ROOT_DIR / "WRITER.md"


def load_writer_rules(
    rules_path: str | Path = RULES_PATH,
    writer_path: str | Path = WRITER_PATH,
) -> dict[str, Any]:
    """Load curated writer rules and validate source anchors still exist."""
    payload = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    source_text = Path(writer_path).read_text(encoding="utf-8")
    missing = [
        rule.get("anchor", "")
        for rule in payload.get("rules", [])
        if rule.get("anchor") and str(rule.get("anchor")) not in source_text
    ]
    if missing:
        raise ValueError(f"Writer rule anchors missing from WRITER.md: {missing}")
    return payload


def compact_writer_rule_summary(payload: dict[str, Any] | None = None) -> str:
    """Return a compact prompt block from curated writer rules."""
    payload = payload or load_writer_rules()
    lines = []
    for rule in payload.get("rules", []):
        terms = "、".join(str(item) for item in rule.get("terms", [])[:6])
        guidance = str(rule.get("guidance", "") or "").strip()
        lines.append(f"- {rule.get('category')}: {guidance} 触发词示例: {terms}")
    return "\n".join(lines)


def check_writer_rules(content: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return warning-only writer-rule matches for generated content."""
    payload = payload or load_writer_rules()
    warnings: list[dict[str, Any]] = []
    for rule in payload.get("rules", []):
        matches = [
            str(term)
            for term in rule.get("terms", [])
            if str(term) and str(term) in content
        ]
        if not matches:
            continue
        warnings.append(
            {
                "rule_id": rule.get("id", ""),
                "category": rule.get("category", "writer_rule"),
                "severity": rule.get("severity", "warning"),
                "blocking": bool(rule.get("blocking", False)),
                "matches": matches[:8],
                "guidance": rule.get("guidance", ""),
                "source": payload.get("source", "WRITER.md"),
                "anchor": rule.get("anchor", ""),
            }
        )
    return warnings
