"""BibleSectionBuilder - builds BibleSection for a specific volume.

Each parallel volume generation task receives only the bible section
relevant to its volume, preventing context overflow and ensuring focus.
"""

from crewai.content.novel.production_bible.bible_types import (
    BibleSection,
    CharacterProfile,
    ProductionBible,
    WorldRules,
)


class BibleSectionBuilder:
    """Builds a BibleSection for a specific volume.

    Each parallel volume generation task receives only the bible section
    relevant to its volume, preventing context overflow.
    """

    def build_section(self, bible: ProductionBible, volume_num: int) -> BibleSection:
        """Build bible section for a specific volume.

        Args:
            bible: Full production bible
            volume_num: Target volume number

        Returns:
            BibleSection: Relevant subset of the bible for this volume
        """
        # Characters appearing in this volume (by timeline)
        relevant_chars = self._get_relevant_characters(bible, volume_num)

        # World rules summary
        world_rules_summary = self._summarize_world_rules(bible.world_rules)

        # Timeline up to this volume
        timeline = [e for e in bible.timeline if e.volume_num < volume_num]

        # Open foreshadowing (setup before this volume, payoff in this volume)
        open_fs = [
            f
            for f in bible.foreshadowing_registry.values()
            if f.setup_volume < volume_num <= f.payoff_volume and f.is_active
        ]

        # Relationship states at volume start
        rel_states = self._get_relationship_states(bible, volume_num)

        # Canonical facts for this volume
        canonical_facts = self._extract_canonical_facts(bible, volume_num)

        return BibleSection(
            volume_num=volume_num,
            relevant_characters=relevant_chars,
            world_rules_summary=world_rules_summary,
            timeline_up_to_this_point=timeline,
            open_foreshadowing=open_fs,
            relationship_states_at_start=rel_states,
            canonical_facts_this_volume=canonical_facts,
        )

    def _get_relevant_characters(self, bible: ProductionBible, volume_num: int) -> dict[str, CharacterProfile]:
        """Get characters who appear in this volume."""
        relevant: dict[str, CharacterProfile] = {}
        for event in bible.timeline:
            if event.volume_num == volume_num:
                for char_name in event.involved_characters:
                    char = bible.get_character(char_name)
                    if char and char_name not in relevant:
                        relevant[char_name] = char
        # Also include protagonist always
        for char_name, char in bible.characters.items():
            if char.role == "protagonist" and char_name not in relevant:
                relevant[char_name] = char
        return relevant

    def _summarize_world_rules(self, world_rules: WorldRules | None) -> str:
        """Create abbreviated world rules summary."""
        if not world_rules:
            return "无特殊世界规则"
        levels = ", ".join(world_rules.cultivation_levels) if world_rules.cultivation_levels else "未知"
        return (
            f"灵力体系：{world_rules.power_system_name}，"
            f"等级：{levels}。"
            f"约束：{'；'.join(world_rules.world_constraints) if world_rules.world_constraints else '无'}。"
        )

    def _get_relationship_states(self, bible: ProductionBible, volume_num: int) -> dict[str, dict[str, str]]:
        """Get relationship states at volume start."""
        states = {}
        events_before = [e for e in bible.timeline if e.volume_num < volume_num]
        for event in events_before:
            for char in event.involved_characters:
                if char not in states:
                    states[char] = {}
        return states

    def _extract_canonical_facts(self, bible: ProductionBible, volume_num: int) -> list[str]:
        """Extract hard facts that must not be contradicted."""
        facts = []
        # Volume boundary facts
        boundary = bible.get_volume_boundary(volume_num)
        if boundary.get("opening_state"):
            facts.append(f"开篇状态：{boundary['opening_state']}")
        if boundary.get("closing_hook"):
            facts.append(f"本卷结尾悬念：{boundary['closing_hook']}")
        # World rule constraints
        if bible.world_rules:
            for constraint in bible.world_rules.world_constraints:
                facts.append(f"世界规则：{constraint}")
        return facts
