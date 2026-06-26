"""Schema-bound project asset helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


ASSET_SCHEMA_VERSION = "project_assets.v1"


class ProjectAssetValidationError(ValueError):
    """Raised when imported project assets do not satisfy the local schema."""


@dataclass
class OutlineAsset:
    """Structured story outline asset."""

    premise: str
    major_arcs: list[str] = field(default_factory=list)
    ending_hint: str = ""
    themes: list[str] = field(default_factory=list)


@dataclass
class WorldAsset:
    """Structured world-building asset."""

    summary: str
    rules: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    factions: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)


@dataclass
class CharacterAsset:
    """Structured character asset."""

    name: str
    role: str = ""
    motivation: str = ""
    arc: str = ""
    voice: str = ""
    relationships: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class ProjectAssetBundle:
    """Bundle of schema-bound project seed assets."""

    outline: OutlineAsset
    world_setting: WorldAsset
    characters: list[CharacterAsset]
    schema_version: str = ASSET_SCHEMA_VERSION
    source_path: str = ""

    def to_project_fields(self) -> dict[str, str]:
        return {
            "outline": render_outline_asset(self.outline),
            "world_setting": render_world_asset(self.world_setting),
            "character_intro": render_character_assets(self.characters),
        }

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        return {
            "schema_version": self.schema_version,
            "source_path": self.source_path,
            "outline": payload["outline"],
            "world_setting": payload["world_setting"],
            "characters": payload["characters"],
        }


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return [cleaned] if cleaned else []
    if not isinstance(value, list):
        raise ProjectAssetValidationError("list fields must be strings or arrays")
    return [cleaned for item in value if (cleaned := _clean_text(item))]


def _coerce_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectAssetValidationError(f"{field_name} must be an object")
    return value


def _parse_outline_asset(value: Any) -> OutlineAsset:
    if isinstance(value, str):
        premise = _clean_text(value)
        if not premise:
            raise ProjectAssetValidationError("outline.premise is required")
        return OutlineAsset(premise=premise)

    data = _coerce_mapping(value, "outline")
    premise = _clean_text(
        data.get("premise")
        or data.get("summary")
        or data.get("description")
        or data.get("text")
    )
    if not premise:
        raise ProjectAssetValidationError("outline.premise is required")
    return OutlineAsset(
        premise=premise,
        major_arcs=_clean_list(data.get("major_arcs") or data.get("arcs")),
        ending_hint=_clean_text(data.get("ending_hint") or data.get("ending")),
        themes=_clean_list(data.get("themes")),
    )


def _parse_world_asset(value: Any) -> WorldAsset:
    if isinstance(value, str):
        summary = _clean_text(value)
        if not summary:
            raise ProjectAssetValidationError("world_setting.summary is required")
        return WorldAsset(summary=summary)

    data = _coerce_mapping(value, "world_setting")
    summary = _clean_text(
        data.get("summary")
        or data.get("premise")
        or data.get("description")
        or data.get("text")
    )
    if not summary:
        raise ProjectAssetValidationError("world_setting.summary is required")
    return WorldAsset(
        summary=summary,
        rules=_clean_list(data.get("rules")),
        locations=_clean_list(data.get("locations")),
        factions=_clean_list(data.get("factions")),
        hard_constraints=_clean_list(data.get("hard_constraints")),
    )


def parse_character_asset(value: Any) -> CharacterAsset:
    if isinstance(value, str):
        name, _, rest = value.partition(":")
        if not rest:
            name, _, rest = value.partition("\uff1a")
        name = _clean_text(name)
        if not name:
            raise ProjectAssetValidationError("characters[].name is required")
        return CharacterAsset(name=name, role=_clean_text(rest))

    data = _coerce_mapping(value, "characters[]")
    name = _clean_text(data.get("name"))
    if not name:
        raise ProjectAssetValidationError("characters[].name is required")
    return CharacterAsset(
        name=name,
        role=_clean_text(data.get("role")),
        motivation=_clean_text(data.get("motivation")),
        arc=_clean_text(data.get("arc")),
        voice=_clean_text(data.get("voice")),
        relationships=_clean_list(data.get("relationships")),
        tags=_clean_list(data.get("tags")),
    )


def _normalize_characters(value: Any) -> list[Any]:
    if value is None:
        raise ProjectAssetValidationError("characters is required")
    if isinstance(value, dict):
        protagonist = value.get("protagonist")
        supporting = value.get("supporting_characters") or value.get("supporting") or []
        if isinstance(supporting, dict):
            supporting = list(supporting.values())
        if not isinstance(supporting, list):
            supporting = [supporting]
        return [item for item in [protagonist, *supporting] if item]
    if isinstance(value, list):
        return value
    return [value]


def parse_project_asset_bundle(
    payload: dict[str, Any], *, source_path: str = ""
) -> ProjectAssetBundle:
    data = _coerce_mapping(payload, "project assets")
    characters = [
        parse_character_asset(item)
        for item in _normalize_characters(data.get("characters", data.get("character_intro")))
    ]
    if not characters:
        raise ProjectAssetValidationError("characters is required")

    return ProjectAssetBundle(
        outline=_parse_outline_asset(data.get("outline")),
        world_setting=_parse_world_asset(
            data.get("world_setting", data.get("world_building"))
        ),
        characters=characters,
        schema_version=_clean_text(data.get("schema_version")) or ASSET_SCHEMA_VERSION,
        source_path=source_path,
    )


def load_project_asset_bundle(path: str | Path) -> ProjectAssetBundle:
    asset_path = Path(path)
    try:
        payload = json.loads(asset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProjectAssetValidationError(f"invalid project asset JSON: {exc}") from exc
    return parse_project_asset_bundle(payload, source_path=str(asset_path))


def load_project_assets_from_files(
    *,
    asset_file: str | None = None,
    outline_file: str | None = None,
    world_file: str | None = None,
    characters_file: str | None = None,
) -> ProjectAssetBundle | None:
    if asset_file:
        return load_project_asset_bundle(asset_file)
    if not any([outline_file, world_file, characters_file]):
        return None

    payload: dict[str, Any] = {}
    if outline_file:
        payload["outline"] = json.loads(Path(outline_file).read_text(encoding="utf-8"))
    if world_file:
        payload["world_setting"] = json.loads(
            Path(world_file).read_text(encoding="utf-8")
        )
    if characters_file:
        payload["characters"] = json.loads(
            Path(characters_file).read_text(encoding="utf-8")
        )
    return parse_project_asset_bundle(payload)


def render_outline_asset(asset: OutlineAsset) -> str:
    lines = [asset.premise]
    if asset.major_arcs:
        lines.append("主要篇章: " + "\uff1b".join(asset.major_arcs))
    if asset.ending_hint:
        lines.append("结局方向: " + asset.ending_hint)
    if asset.themes:
        lines.append("主题: " + "\uff1b".join(asset.themes))
    return "\n".join(lines)


def render_world_asset(asset: WorldAsset) -> str:
    lines = [asset.summary]
    if asset.rules:
        lines.append("核心规则: " + "\uff1b".join(asset.rules))
    if asset.locations:
        lines.append("关键地点: " + "\uff1b".join(asset.locations))
    if asset.factions:
        lines.append("势力: " + "\uff1b".join(asset.factions))
    if asset.hard_constraints:
        lines.append("硬约束: " + "\uff1b".join(asset.hard_constraints))
    return "\n".join(lines)


def render_character_assets(characters: list[CharacterAsset]) -> str:
    lines: list[str] = []
    for character in characters:
        details = [
            character.role,
            character.motivation,
            character.arc,
            character.voice,
            "关系: " + "\uff1b".join(character.relationships)
            if character.relationships
            else "",
        ]
        body = "\uff0c".join(item for item in details if item)
        lines.append(f"{character.name}: {body}" if body else character.name)
    return "\n".join(lines)
