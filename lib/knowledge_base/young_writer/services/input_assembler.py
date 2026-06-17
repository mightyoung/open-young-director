"""Assemble structured chapter-generation input packets."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from young_writer.services.story_input import (
    CANONICAL_INPUT_POLICY,
    ChapterPlan,
    GenerationPacket,
    RuntimeOverrides,
    StyleProfile,
    StoryInputBundle,
    build_story_input_bundle,
    chapter_plan_to_outline_info,
    load_story_input_bundle,
    packet_to_dict,
    resolve_goal_lock_resolution,
    validate_generation_packet,
    write_story_input_bundle,
)


class InputAssembler:
    """Build a canonical generation packet while preserving legacy context fields."""

    def __init__(self, config_manager: Any):
        self.config_manager = config_manager

    def _project_dir(self) -> Path:
        output_dir = getattr(getattr(self.config_manager, "generation", None), "output_dir", "")
        return Path(output_dir).resolve()

    def _load_or_build_bundle(
        self,
        *,
        writing_options: dict[str, str] | None = None,
    ) -> StoryInputBundle:
        project_dir = self._project_dir()
        bundle = load_story_input_bundle(project_dir)
        if bundle is not None:
            return bundle
        project = getattr(self.config_manager, "current_project", None)
        if project is None:
            raise RuntimeError("current_project unavailable for input assembly")
        bundle = build_story_input_bundle(
            project,
            writing_options=writing_options,
            chapters_per_volume=getattr(self.config_manager.generation, "chapters_per_volume", 60),
        )
        write_story_input_bundle(project_dir, bundle)
        return bundle

    def _select_chapter_plan(
        self, bundle: StoryInputBundle, chapter_number: int
    ) -> ChapterPlan:
        for plan in bundle.chapter_plans:
            if int(plan.chapter_number) == int(chapter_number):
                return plan
        fallback = bundle.chapter_plans[-1] if bundle.chapter_plans else None
        if fallback is None:
            raise RuntimeError(f"chapter plan missing for chapter {chapter_number}")
        return ChapterPlan(
            **{
                **asdict(fallback),
                "chapter_number": chapter_number,
                "title": f"第{chapter_number}章",
                "source": "fallback",
            }
        )

    def assemble(
        self,
        *,
        chapter_number: int,
        base_context: dict[str, Any] | None,
        writing_options: dict[str, str] | None = None,
        chapter_guidance_target: int | None = None,
    ) -> GenerationPacket:
        bundle = self._load_or_build_bundle(writing_options=writing_options)
        project = getattr(self.config_manager, "current_project", None)
        if project is None:
            raise RuntimeError("current_project unavailable for input assembly")
        style_profile = StyleProfile(
            **{
                **asdict(bundle.style_profile),
                **{k: v for k, v in (writing_options or {}).items() if v and hasattr(StyleProfile, k)},
            }
        )
        runtime = RuntimeOverrides(
            volume_guidance=str((base_context or {}).get("volume_guidance", "") or "").strip(),
            volume_guidance_payload=dict((base_context or {}).get("volume_guidance_payload", {}) or {}),
            chapter_guidance=str((base_context or {}).get("chapter_guidance", "") or "").strip(),
            chapter_guidance_target=chapter_guidance_target,
            previous_summary=str((base_context or {}).get("previous_summary", "") or "").strip(),
            previous_chapters=list((base_context or {}).get("previous_chapters", []) or []),
            longform_memory=list((base_context or {}).get("longform_memory", []) or []),
        )
        packet = GenerationPacket(
            chapter_number=chapter_number,
            total_chapters=max(int(getattr(project, "total_chapters", 0) or 0), 1),
            project_bible=bundle.project_bible,
            world_bible=bundle.world_bible,
            characters=bundle.characters,
            chapter_plan=self._select_chapter_plan(bundle, chapter_number),
            style_profile=style_profile,
            runtime_overrides=runtime,
        )
        packet.validation = validate_generation_packet(packet)
        return packet

    def _legacy_orchestrator_characters(
        self, packet: GenerationPacket
    ) -> list[dict[str, Any]]:
        """Expose structured characters in the legacy shape used by FILM_DRAMA."""
        objective = str(packet.chapter_plan.goal_lock or "").strip()
        characters: list[dict[str, Any]] = []
        for character in packet.characters:
            name = str(character.name or "").strip()
            if not name:
                continue
            characters.append(
                {
                    "name": name,
                    "identity": character.role or character.motivation or "关键角色",
                    "cultivation_realm": "",
                    "personality": character.voice or character.motivation or "目标明确",
                    "speaking_style": character.voice or "简洁清晰",
                    "backstory": character.arc or "",
                    "objective_this_chapter": objective,
                    "relationships": {
                        item: item for item in (character.relationships or [])
                    },
                }
            )
        return characters

    def _resolve_primary_location(self, packet: GenerationPacket) -> str:
        locations = list(packet.world_bible.locations or [])
        location_map = {
            f"location:{str(location or '').strip().lower()}": str(location or "").strip()
            for location in locations
            if str(location or "").strip()
        }
        for location_id in packet.chapter_plan.location_ids:
            resolved = location_map.get(str(location_id or "").strip().lower())
            if resolved:
                return resolved
        return locations[0] if locations else ""

    def enrich_context(
        self,
        *,
        chapter_number: int,
        base_context: dict[str, Any] | None,
        writing_options: dict[str, str] | None = None,
        chapter_guidance_target: int | None = None,
    ) -> dict[str, Any]:
        packet = self.assemble(
            chapter_number=chapter_number,
            base_context=base_context,
            writing_options=writing_options,
            chapter_guidance_target=chapter_guidance_target,
        )
        outline_info = chapter_plan_to_outline_info(packet.chapter_plan)
        project_outline = packet.project_bible.synopsis or packet.project_bible.premise
        character_names = [character.name for character in packet.characters if character.name]
        goal_lock_resolution = resolve_goal_lock_resolution(packet)
        context = dict(base_context) if isinstance(base_context, dict) else {}
        existing_characters = context.get("characters")
        legacy_characters = (
            existing_characters
            if isinstance(existing_characters, (dict, list)) and existing_characters
            else self._legacy_orchestrator_characters(packet)
        )
        context.update(
            {
                "chapter_number": chapter_number,
                "total_chapters": packet.total_chapters,
                "project_outline": project_outline,
                "world_setting": packet.world_bible.summary,
                "character_intro": "\n".join(
                    f"{character.name}：{character.motivation or character.role or '关键角色'}"
                    for character in packet.characters
                ),
                "genre": packet.project_bible.genre,
                "outline": outline_info["summary"],
                "chapter_plan": asdict(packet.chapter_plan),
                "outline_info": outline_info,
                "goal_lock": goal_lock_resolution["effective_goal_lock"],
                "goal_lock_resolution": goal_lock_resolution,
                "world_name": self._resolve_primary_location(packet),
                "location": self._resolve_primary_location(packet),
                "time_of_day": str(context.get("time_of_day", "") or "").strip(),
                "characters": legacy_characters,
                "character_names": character_names[:8],
                "generation_packet": packet_to_dict(packet),
                "story_input_validation": asdict(packet.validation),
                "writing_options": asdict(packet.style_profile),
                "canonical_input_policy": dict(CANONICAL_INPUT_POLICY),
            }
        )
        return context
