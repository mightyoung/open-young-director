"""Data Converters - Transform between crewai and knowledge_base data formats."""

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from knowledge_base.agents.data_structures import (
        CharacterBible,
        WorldContext,
        PlotOutline,
    )


def convert_world_data_to_world_context(world_data: Dict[str, Any]) -> "WorldContext":
    """Convert crewai world_data to knowledge_base WorldContext.

    Args:
        world_data: World output from WorldCrew, containing:
            - name, description, main_conflict
            - factions, key_locations
            - power_system

    Returns:
        WorldContext for knowledge_base components
    """
    # Extract realm system from power_system
    realm_system = {}
    power_system = world_data.get("power_system", {})
    if isinstance(power_system, dict):
        levels = power_system.get("levels", [])
        for i, level in enumerate(levels):
            realm_system[level] = str(i)

    # Extract sect hierarchy from factions
    sect_hierarchy = {}
    factions = world_data.get("factions", [])
    for i, faction in enumerate(factions):
        if isinstance(faction, dict):
            sect_hierarchy[faction.get("name", f"faction_{i}")] = i

    # Extract key rules from power_system special_abilities
    key_rules = []
    if isinstance(power_system, dict):
        special_abilities = power_system.get("special_abilities", [])
        key_rules.extend(special_abilities)

    # Extract cultivation arts
    cultivation_arts = {}
    if isinstance(power_system, dict):
        if "name" in power_system:
            cultivation_arts[power_system["name"]] = "Primary cultivation method"

    # Extract sect divisions
    sect_divisions = {}
    for faction in factions:
        if isinstance(faction, dict):
            name = faction.get("name", "")
            desc = faction.get("description", "")
            if name:
                sect_divisions[name] = desc

    # Extract spirit_root_system from power_system
    spirit_root_system = {}
    if isinstance(power_system, dict):
        spirit_root = power_system.get("spirit_root", {})
        if isinstance(spirit_root, dict):
            for root_type, description in spirit_root.items():
                spirit_root_system[root_type] = description

    from knowledge_base.agents.data_structures import WorldContext
    return WorldContext(
        realm_system=realm_system,
        sect_hierarchy=sect_hierarchy,
        key_rules=key_rules,
        cultivation_arts=cultivation_arts,
        spirit_root_system=spirit_root_system,
        sect_divisions=sect_divisions,
        world_background={
            "world_name": world_data.get("name", ""),
            "main_region": world_data.get("description", ""),
            "main_conflict": world_data.get("main_conflict", ""),
        },
    )


def convert_chapter_outline(
    chapter_outline: Dict[str, Any],
    chapter_num: int,
) -> "PlotOutline":
    """Convert crewai chapter_outline to knowledge_base PlotOutline.

    Args:
        chapter_outline: Chapter outline dict from PlotAgent, containing:
            - chapter_num, title, hook
            - main_events, climax
            - ending_hook, tension_level
            - weave_connections, character_developments

    Returns:
        PlotOutline for knowledge_base NovelOrchestrator
    """
    # 使用PlotOutline.from_chapter_outline进行完整转换
    from knowledge_base.agents.data_structures import PlotOutline
    return PlotOutline.from_chapter_outline(chapter_outline, chapter_num)


def convert_chapter_memory_to_summary(
    character_states: Dict[str, Dict[str, Any]],
    relationship_states: Dict[str, str],
    key_events: List[str],
) -> str:
    """Convert knowledge_base ChapterMemory to crewai previous_chapters_summary.

    Args:
        character_states: Character states dict from ChapterMemory
        relationship_states: Relationship states dict
        key_events: List of key events that happened

    Returns:
        String summary for crewai WritingContext.previous_chapters_summary
    """
    summary_parts = []

    # Add character states
    if character_states:
        summary_parts.append("【角色状态】")
        for char, state in character_states.items():
            realm = state.get("realm", "unknown")
            status = state.get("status", "")
            summary_parts.append(f"  {char}: {realm}" + (f" - {status}" if status else ""))

    # Add relationships
    if relationship_states:
        summary_parts.append("\n【关系变化】")
        for pair, relation in relationship_states.items():
            if "_" in pair:
                chars = pair.split("_", 1)
                summary_parts.append(f"  {chars[0]}与{chars[1]}: {relation}")

    # Add key events
    if key_events:
        summary_parts.append("\n【关键事件】")
        for event in key_events[-5:]:  # Last 5 events
            summary_parts.append(f"  - {event}")

    return "\n".join(summary_parts) if summary_parts else ""


def convert_character_profiles_to_bibles(
    character_profiles: Dict[str, str],
    world_data: Optional[Dict[str, Any]] = None,
) -> List["CharacterBible"]:
    """Convert crewai character_profiles to knowledge_base CharacterBible list.

    Args:
        character_profiles: Dict mapping character names to profile descriptions
        world_data: Optional world data for additional context

    Returns:
        List of CharacterBible for knowledge_base SubAgentPool
    """
    bibles = []

    # Extract complete character info from world_data
    world_chars = {}
    if world_data and isinstance(world_data, dict):
        world_chars = world_data.get("characters", {})

    from knowledge_base.agents.data_structures import CharacterBible
    for name, profile in character_profiles.items():
        # Get additional info from world_data if available
        char_info = world_chars.get(name, {}) if isinstance(world_chars, dict) else {}

        bible = CharacterBible(
            name=name,
            identity=char_info.get("identity", profile),
            realm=char_info.get("cultivation_realm", _infer_realm_from_profile(profile)),
            personality=char_info.get("personality", ""),
            speaking_style=char_info.get("speaking_style", ""),
            speaking_examples=char_info.get("speaking_examples", []),
            backstory=char_info.get("backstory", ""),
            objective_this_chapter="",
            key_moments_this_chapter=[],
            relationships=char_info.get("relationships", {}),
            forbidden_actions=char_info.get("forbidden_actions", []),
        )
        bibles.append(bible)

    return bibles


def _infer_realm_from_profile(profile: str) -> str:
    """Infer cultivation realm from character profile text.

    This is a heuristic since crewai doesn't have explicit realm in profiles.
    """
    profile_lower = profile.lower()

    # Check for common realm indicators
    if any(word in profile_lower for word in ["凡人", " mortal", "mortal"]):
        return "凡人"
    elif any(word in profile_lower for word in ["炼气", "qi refining", "foundation"]):
        return "炼气期"
    elif any(word in profile_lower for word in ["筑基", "building foundation", "foundation"]):
        return "筑基期"
    elif any(word in profile_lower for word in ["金丹", "golden core"]):
        return "金丹期"
    elif any(word in profile_lower for word in ["元婴", "nascent soul"]):
        return "元婴期"
    elif any(word in profile_lower for word in ["化神", "deity", "transcendence"]):
        return "化神期"
    else:
        return "境界未知"


def convert_novel_output(
    draft: str,
    chapter_num: int,
    title: str,
    key_events: Optional[List[str]] = None,
    character_appearances: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert knowledge_base draft to crewai ChapterOutput format.

    Args:
        draft: Generated chapter draft text
        chapter_num: Chapter number
        title: Chapter title
        key_events: Optional list of key events
        character_appearances: Optional list of appearing characters

    Returns:
        Dict compatible with crewai ChapterOutput
    """
    # Estimate word count (rough calculation for Chinese)
    word_count = len(draft) // 2

    return {
        "chapter_num": chapter_num,
        "title": title,
        "content": draft,
        "word_count": word_count,
        "key_events": key_events or [],
        "character_appearances": character_appearances or [],
    }
