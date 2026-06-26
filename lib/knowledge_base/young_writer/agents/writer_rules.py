"""Curated machine-readable subset of WRITER.md."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[4]
RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "writer_rules.json"
WRITER_PATH = ROOT_DIR / "WRITER.md"

HUMANIZATION_LEVELS = ("off", "light", "standard", "strict")


def load_writer_rules(
    rules_path: str | Path = RULES_PATH,
    writer_path: str | Path = WRITER_PATH,
) -> dict[str, Any]:
    """Load curated writer rules and verify source anchors still exist."""
    payload = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    source_text = Path(writer_path).read_text(encoding="utf-8")
    missing = [
        rule.get("anchor", "")
        for rule in payload.get("rules", [])
        if rule.get("anchor") and str(rule.get("anchor")) not in source_text
    ]
    if missing:
        raise ValueError(f"Writer rule anchors missing from WRITER.md: {missing}")
    _validate_rule_patterns(payload)
    return payload


def _validate_rule_patterns(payload: dict[str, Any]) -> None:
    """Fail fast when configured style-rule regexes are invalid."""
    invalid: list[str] = []
    for rule in payload.get("rules", []):
        rule_id = str(rule.get("id", "<missing-id>") or "<missing-id>")
        for pattern in rule.get("patterns", []):
            pattern_text = str(pattern or "").strip()
            if not pattern_text:
                continue
            try:
                re.compile(pattern_text)
            except re.error as exc:
                invalid.append(f"{rule_id}: {pattern_text!r} ({exc})")
    if invalid:
        raise ValueError(f"Invalid writer rule regex patterns: {invalid}")


def normalize_humanization_level(level: str | None) -> str:
    """Return supported humanization level."""
    normalized = str(level or "light").strip().lower()
    return normalized if normalized in HUMANIZATION_LEVELS else "light"


def compact_writer_rule_summary(
    payload: dict[str, Any] | None = None,
    humanization_level: str | None = "light",
) -> str:
    """Return compact prompt block for curated writer rules."""
    level = normalize_humanization_level(humanization_level)
    if level == "off":
        return ""

    payload = payload or load_writer_rules()
    limit = {"light": 6, "standard": 10, "strict": 14}.get(level, 6)
    eligible_rules = [
        rule
        for rule in payload.get("rules", [])
        if _rule_prompt_weight(rule, level) > 0
    ]
    eligible_rules.sort(key=lambda rule: _rule_prompt_weight(rule, level), reverse=True)

    lines: list[str] = []
    for rule in eligible_rules[:limit]:
        terms = "、".join(str(item) for item in rule.get("terms", [])[:4])
        guidance = str(rule.get("guidance", "") or rule.get("rewrite_hint", "")).strip()
        suffix = f" 触发词示例: {terms}" if terms else ""
        lines.append(f"- {rule.get('category')}: {guidance}{suffix}")
    return "\n".join(lines)


def check_writer_rules(
    content: str,
    payload: dict[str, Any] | None = None,
    humanization_level: str | None = "light",
) -> list[dict[str, Any]]:
    """Return warning-only writer-rule matches in generated content."""
    payload = payload or load_writer_rules()
    level = normalize_humanization_level(humanization_level)
    if level == "off":
        return []

    segments = _split_content_segments(content or "")
    warnings: list[dict[str, Any]] = []
    for rule in payload.get("rules", []):
        if _rule_enabled_for_level(rule, level):
            warning = _match_rule(rule, segments, payload, content or "")
            if warning:
                warnings.append(warning)
    warnings.sort(
        key=lambda item: (
            str(item.get("category", "")),
            -int(item.get("matches_count", 0) or 0),
        )
    )
    return warnings


def build_style_review(
    warnings: list[dict[str, Any]],
    humanization_level: str | None = "light",
) -> dict[str, Any]:
    """Build a compact style review without affecting hard gates."""
    level = normalize_humanization_level(humanization_level)
    issue_groups: list[dict[str, Any]] = []
    score_penalty = 0.0
    for warning in warnings:
        count = int(warning.get("matches_count", 0) or len(warning.get("matches", [])))
        density = float(warning.get("density_per_1000", 0.0) or 0.0)
        score_penalty += min(0.18, 0.035 * count + 0.015 * density)
        issue_groups.append(
            {
                "category": warning.get("category", "writer_rule"),
                "rule_id": warning.get("rule_id", ""),
                "severity": warning.get("severity", "warning"),
                "matches_count": count,
                "density_per_1000": round(density, 2),
                "samples": list(warning.get("matches", [])[:5]),
                "guidance": warning.get("guidance", ""),
                "rewrite_hint": warning.get("rewrite_hint", ""),
                "false_positive_note": warning.get("false_positive_note", ""),
            }
        )

    score = max(0.0, round(1.0 - score_penalty, 2))
    rewrite_targets = [
        {
            "category": item["category"],
            "samples": item["samples"][:3],
            "rewrite_hint": item["rewrite_hint"] or item["guidance"],
        }
        for item in issue_groups
        if item["samples"] and (level == "strict" or item["matches_count"] >= 2)
    ][:5]
    return {
        "warning_only": True,
        "humanization_level": level,
        "score": score,
        "issue_count": len(issue_groups),
        "issue_groups": issue_groups,
        "rewrite_targets": rewrite_targets,
    }


def _rule_enabled_for_level(rule: dict[str, Any], level: str) -> bool:
    minimum = normalize_humanization_level(str(rule.get("min_level", "light")))
    order = {name: index for index, name in enumerate(HUMANIZATION_LEVELS)}
    return order[level] >= order[minimum]


def _rule_prompt_weight(rule: dict[str, Any], level: str) -> int:
    if not _rule_enabled_for_level(rule, level):
        return 0
    raw_weight = rule.get("prompt_weight", 0)
    try:
        return int(raw_weight)
    except (TypeError, ValueError):
        return 0


def _match_rule(
    rule: dict[str, Any],
    segments: list[dict[str, str]],
    payload: dict[str, Any],
    content: str,
) -> dict[str, Any] | None:
    scope = str(rule.get("scope", "all") or "all")
    candidate_text = "\n".join(
        segment["text"]
        for segment in segments
        if scope == "all" or segment["scope"] in {scope, "all"}
    )
    if not candidate_text:
        return None

    matches: list[str] = []
    for term in rule.get("terms", []):
        term_text = str(term or "").strip()
        if term_text and term_text in candidate_text:
            matches.extend([term_text] * candidate_text.count(term_text))

    for pattern in rule.get("patterns", []):
        pattern_text = str(pattern or "").strip()
        if not pattern_text:
            continue
        for match in re.finditer(pattern_text, candidate_text, flags=re.MULTILINE):
            sample = " ".join(match.group(0).split())
            matches.append(sample[:80])

    if not matches:
        return None

    unique_samples = list(dict.fromkeys(matches))
    threshold = int(rule.get("density_threshold", 1) or 1)
    if len(matches) < threshold:
        return None

    char_count = max(len(content), 1)
    density = len(matches) / (char_count / 1000)
    return {
        "rule_id": rule.get("id", ""),
        "category": rule.get("category", "writer_rule"),
        "severity": rule.get("severity", "warning"),
        "blocking": bool(rule.get("blocking", False)),
        "matches": unique_samples[:8],
        "matches_count": len(matches),
        "density_per_1000": round(density, 2),
        "guidance": rule.get("guidance", ""),
        "rewrite_hint": rule.get("rewrite_hint", ""),
        "false_positive_note": rule.get("false_positive_note", ""),
        "source": payload.get("source", "WRITER.md"),
        "anchor": rule.get("anchor", ""),
    }


def _split_content_segments(content: str) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        quote_count = sum(line.count(mark) for mark in ("“", "”", "「", "」"))
        colon_dialogue = bool(re.match(r"^[\u4e00-\u9fa5]{1,8}[：:]", line))
        scope = "dialogue" if quote_count >= 2 or colon_dialogue else "narration"
        segments.append({"scope": scope, "text": line})
    if not segments and content:
        segments.append({"scope": "narration", "text": content})
    return segments
