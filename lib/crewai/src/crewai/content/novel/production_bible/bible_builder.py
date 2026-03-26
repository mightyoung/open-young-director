"""ProductionBibleBuilder - builds ProductionBible from world_data and plot_data.

This builder is a PURE DATA TRANSFORMATION LAYER. It does NOT import from agents
or crews - only transforms dict data into typed ProductionBible objects.

Called ONCE after WorldCrew/PlotAgent generate world and plot, but BEFORE
any parallel volume/chapter generation.
"""

from crewai.content.novel.production_bible.bible_types import (
    CharacterProfile,
    ForeshadowingEntry,
    ProductionBible,
    TimelineEvent,
    WorldRules,
)


class ProductionBibleBuilder:
    """Builds ProductionBible from world_data and plot_data.

    This is called ONCE after WorldCrew/PlotAgent generate world and plot,
    but BEFORE any parallel volume/chapter generation.
    """

    def build(self, world_data: dict, plot_data: dict) -> ProductionBible:
        """Build complete production bible.

        Args:
            world_data: Output from WorldCrew
            plot_data: Output from PlotAgent

        Returns:
            ProductionBible: Complete canonical bible
        """
        # 1. Extract characters
        characters = self._extract_characters(world_data, plot_data)

        # 2. Extract world rules
        world_rules = self._extract_world_rules(world_data)

        # 3. Extract timeline
        timeline = self._extract_timeline(plot_data)

        # 4. Extract foreshadowing
        foreshadowing = self._extract_foreshadowing(plot_data)

        # 5. Extract relationships
        relationships = self._extract_relationships(world_data, plot_data)

        # 6. Extract volume boundaries
        volume_boundaries = self._extract_volume_boundaries(plot_data)

        return ProductionBible(
            characters=characters,
            world_rules=world_rules,
            timeline=timeline,
            foreshadowing_registry=foreshadowing,
            canonical_relationships=relationships,
            volume_boundaries=volume_boundaries,
        )

    def _extract_characters(self, world_data: dict, plot_data: dict) -> dict[str, CharacterProfile]:
        """Extract character profiles from world_data factions."""
        characters = {}
        factions = world_data.get("factions", [])
        for faction in factions:
            if not isinstance(faction, dict):
                continue
            leader = faction.get("leader", "").strip()
            if leader:
                characters[leader] = CharacterProfile(
                    name=leader,
                    role="supporting",
                    personality=faction.get("description", ""),
                    appearance="",
                    core_desire="",
                    fear="",
                    backstory=faction.get("history", ""),
                    character_arc="",
                    first_appearance=1,
                    faction=faction.get("name", ""),
                    relationships={},
                )
        # Add protagonist from plot_data
        main_strand = plot_data.get("main_strand", {})
        # 支持两种格式：{protagonist: {name, ...}} 或直接 {name, ...}
        protagonist = main_strand.get("protagonist", {})
        if not isinstance(protagonist, dict) or not protagonist.get("name"):
            # Fallback: main_strand itself可能就是 protagonist 结构
            if isinstance(main_strand, dict) and main_strand.get("name"):
                protagonist = main_strand
        if protagonist and isinstance(protagonist, dict):
            name = protagonist.get("name", "") or protagonist.get("protagonist", {}).get("name", "") if isinstance(protagonist.get("protagonist"), dict) else ""
            if not name:
                # 最后尝试：直接从 main_strand 的 name 字段
                name = main_strand.get("name", "")
            if name:
                characters[name] = CharacterProfile(
                    name=name,
                    role="protagonist",
                    personality=protagonist.get("personality", "") or main_strand.get("personality", ""),
                    appearance="",
                    core_desire=protagonist.get("goal", "") or main_strand.get("goal", "") or main_strand.get("core_desire", ""),
                    fear="",
                    backstory="",
                    character_arc=main_strand.get("character_arc", "") or protagonist.get("character_arc", ""),
                    first_appearance=1,
                )
        return characters

    def _extract_world_rules(self, world_data: dict) -> WorldRules:
        """Extract world rules from world_data."""
        power_system = world_data.get("power_system", {})
        return WorldRules(
            power_system_name=power_system.get("name", "未知"),
            cultivation_levels=power_system.get("levels", []),
            level_abilities=power_system.get("abilities", {}),
            world_constraints=[
                "灵力不可跨域使用",
                "筑基以下无法御剑飞行",
            ],
            geography=world_data.get("geography", {}),
            factions={
                f.get("name", ""): f.get("description", "")
                for f in world_data.get("factions", [])
                if isinstance(f, dict)
            },
        )

    def _extract_timeline(self, plot_data: dict) -> list[TimelineEvent]:
        """Extract timeline events from plot strands."""
        events = []
        volumes = plot_data.get("volumes", [])
        for vol in volumes:
            vol_num = vol.get("volume_num", 1)
            # 支持 chapters_summary (VolumeOutlineAgent输出) 和 chapters (旧格式兼容)
            chapters = vol.get("chapters_summary") or vol.get("chapters", [])
            for ch in chapters:
                ch_num = ch.get("chapter_num", 0)
                if ch_num > 0:
                    events.append(
                        TimelineEvent(
                            id=f"v{vol_num}_ch{ch_num}",
                            chapter_range=(ch_num, ch_num),
                            volume_num=vol_num,
                            description=ch.get("title", ""),
                            involved_characters=ch.get("characters", []),
                            consequences=[],
                        )
                    )
        return events

    def _extract_foreshadowing(self, plot_data: dict) -> dict[str, ForeshadowingEntry]:
        """Extract foreshadowing from plot data."""
        registry = {}
        foreshadowing_strands = plot_data.get("foreshadowing_strands", []) or []
        for i, strand in enumerate(foreshadowing_strands):
            if not isinstance(strand, dict):
                continue
            # 支持 foreshadowing_strands 可能是列表形式：[setup_desc, payoff_desc]
            if "setup" not in strand and "payoff" not in strand:
                if len(strand) >= 2:
                    setup_desc = list(strand.values())[0] if isinstance(strand, dict) else str(strand)
                    payoff_desc = list(strand.values())[1] if isinstance(strand, dict) else ""
                    strand = {"setup": {"description": str(setup_desc), "chapter": 1, "volume": 1}, "payoff": {"description": str(payoff_desc), "chapter": 10, "volume": 2}}
                else:
                    continue
            setup = strand.get("setup", {})
            payoff = strand.get("payoff", {})
            if not setup and not payoff:
                continue
            setup_id = f"fs_{i}"
            registry[setup_id] = ForeshadowingEntry(
                setup_id=setup_id,
                setup_chapter=setup.get("chapter", 0) if isinstance(setup, dict) else 0,
                setup_volume=setup.get("volume", 1) if isinstance(setup, dict) else 1,
                setup_description=setup.get("description", "") if isinstance(setup, dict) else str(setup),
                payoff_chapter=payoff.get("chapter", 0) if isinstance(payoff, dict) else 0,
                payoff_volume=payoff.get("volume", 1) if isinstance(payoff, dict) else 1,
                payoff_description=payoff.get("description", "") if isinstance(payoff, dict) else str(payoff),
                is_active=True,
            )
        return registry

    def _extract_relationships(self, world_data: dict, plot_data: dict) -> dict[str, list[str]]:
        """Extract character relationships."""
        relationships = {}
        factions = world_data.get("factions", [])
        for faction in factions:
            if not isinstance(faction, dict):
                continue
            members = faction.get("members", [])
            leader = faction.get("leader", "").strip()
            for member in members:
                if isinstance(member, str) and member.strip():
                    if leader:
                        if leader not in relationships:
                            relationships[leader] = []
                        relationships[leader].append(member)
        return relationships

    def _extract_volume_boundaries(self, plot_data: dict) -> dict[int, dict]:
        """Extract opening/closing states for each volume."""
        boundaries = {}
        volumes = plot_data.get("volumes", [])
        for vol in volumes:
            vol_num = vol.get("volume_num", 1)
            boundaries[vol_num] = {
                "opening_state": vol.get("opening_hook", ""),
                "closing_hook": vol.get("closing_hook", ""),
                "main_conflict": vol.get("main_conflict", ""),
                "resolution": vol.get("resolution", ""),
            }
        return boundaries
