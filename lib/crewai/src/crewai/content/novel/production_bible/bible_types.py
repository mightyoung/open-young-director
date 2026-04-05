"""Canonical data types for the Production Bible system.

This module defines the core dataclasses that form the single source of truth
for all story facts during parallel volume generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CharacterProfile:
    """Canonical character information stored in the bible."""

    name: str
    role: str  # protagonist, antagonist, supporting
    personality: str
    appearance: str
    core_desire: str
    fear: str
    backstory: str
    character_arc: str  # how they change across the story
    first_appearance: int  # chapter number
    cultivation_realm: Optional[str] = None
    faction: Optional[str] = None
    speech_pattern: Optional[str] = None  # how they talk
    voice_samples: list[str] = field(default_factory=list)  # Example lines they would say
    linguistic_traits: list[str] = field(default_factory=list)  # Catchphrases, taboo words, etc.
    hidden_agenda: str = ""  # What they REALLY want but won't say
    subtext_style: str = "言不由衷"  # How they hide their agenda
    relationships: dict[str, RelationshipState] = field(default_factory=dict)  # name → RelationshipState


@dataclass
class RelationshipState:
    """Detailed state of a relationship between two characters."""
    target_name: str
    emotional_value: int  # -100 (mortal enemy) to 100 (soul mate)
    bond_type: str  # e.g., "mentor", "rival", "unrequited love", "ally"
    core_conflict: str = ""  # The underlying issue between them
    shared_secrets: list[str] = field(default_factory=list)
    recent_interaction_summary: str = ""


@dataclass
class WorldRules:
    """Canonical world physics and rules."""

    power_system_name: str  # e.g., "修仙灵力体系"
    cultivation_levels: list[str]  # ordered list, e.g., ["炼气", "筑基", "金丹"]
    level_abilities: dict[str, list[str]]  # level → abilities
    world_constraints: list[str]  # things that can't happen
    geography: dict[str, str] = field(default_factory=dict)  # location → characteristics
    sensory_anchors: dict[str, dict[str, str]] = field(default_factory=dict)  # location → {smell/sound/touch: description}
    factions: dict[str, str] = field(default_factory=dict)  # faction name → description

    def get_level_index(self, level_name: str) -> int:
        """Get the rank of a cultivation level (higher is stronger)."""
        if not level_name:
            return -1
        for i, level in enumerate(self.cultivation_levels):
            if level in level_name:
                return i
        return -1


@dataclass
class TimelineEvent:
    """Canonical event in story timeline."""

    id: str
    chapter: int
    volume: int
    description: str
    involved_entities: list[str]  # character names
    impact: str  # how this changes the world or characters


@dataclass
class ForeshadowingEntry:
    """A setup that should be paid off in a future chapter."""

    id: str
    setup_chapter: int
    setup_description: str
    payoff_chapter: int
    payoff_description: str
    is_active: bool = True
    was_successful: bool = False


@dataclass
class SeedDetail:
    """A minor detail mentioned in text that could be used for a future payoff."""
    description: str
    origin_chapter: int
    category: str  # item, npc_behavior, environment, lore
    is_used: bool = False


@dataclass
class PacingState:
    """Current rhythm and tension metrics of the novel."""
    recent_tension_levels: list[int] = field(default_factory=list)  # Last 5 chapters
    accumulated_fatigue: float = 0.0  # 0 to 1.0, high tension increases fatigue
    next_recommended_tone: str = "balanced"  # intense, breather, buildup

@dataclass
class LocationState:
    """Current coordinates and status of a character in the world."""
    place_name: str
    arrival_chapter: int
    stay_duration_est: int = 1  # in chapters
    status: str = "present"  # present, traveling, hidden

@dataclass
class VisualAsset:
    """Standardized prompts for AI image generation."""
    asset_type: str  # character, location, volume_cover, item
    subject_id: str
    positive_prompt: str
    negative_prompt: str
    style_guide: str = "cinematic, anime, high detail"

@dataclass
class SentimentPoint:
    """Feedback from a specific reader persona."""
    persona: str  # logic_nut, emotional_fan, action_junkie
    score: float  # -1.0 to 1.0
    comment: str
    predicted_churn_rate: float # probability of stopping reading

@dataclass
class ProductionBible:
    """Complete production bible - the single source of truth for all story facts."""

    characters: dict[str, CharacterProfile] = field(default_factory=dict)
    world_rules: Optional[WorldRules] = None
    timeline: list[TimelineEvent] = field(default_factory=list)
    foreshadowing_registry: dict[str, ForeshadowingEntry] = field(default_factory=dict)
    seeds_registry: list[SeedDetail] = field(default_factory=list)
    pacing_state: PacingState = field(default_factory=PacingState)
    character_gps: dict[str, LocationState] = field(default_factory=dict)
    visual_assets: list[VisualAsset] = field(default_factory=list)
    reader_sentiments: list[dict[str, Any]] = field(default_factory=list) # New field: Global feedback log
    current_global_chapter: int = 1
    volume_boundaries: dict[int, dict] = field(default_factory=dict)

    def get_character(self, name: str) -> Optional[CharacterProfile]:
        """Get a character profile by name."""
        return self.characters.get(name)

    def get_foreshadowing_for_chapter(self, chapter: int) -> list[ForeshadowingEntry]:
        """Get all active foreshadowing entries covering a chapter."""
        return [
            f for f in self.foreshadowing_registry.values()
            if f.setup_chapter <= chapter <= f.payoff_chapter and f.is_active
        ]

    def export_mermaid_graph(self) -> str:
        """Export character relationships as a Mermaid topology graph."""
        lines = ["graph TD"]
        for name, char in self.characters.items():
            for target, rel in char.relationships.items():
                color = "green" if rel.emotional_value > 30 else "red" if rel.emotional_value < -30 else "gray"
                edge = "-->" if rel.emotional_value >= 0 else "-.->"
                lines.append(f"    {name}{edge}|{rel.bond_type} {rel.emotional_value}|{target}")
        return "\n".join(lines)

    def export_sentiment_trend(self) -> str:
        """Export reader sentiment history as a text-based sparkline or table."""
        if not self.reader_sentiments: return "无反馈数据"
        lines = ["| 章节 | 平均得分 | 核心亮点 | 预测流失率 |", "|---|---|---|---|"]
        for s in self.reader_sentiments[-10:]: # 最近10章
            lines.append(f"| {s.get('chapter_num')} | {s.get('average_score')} | {s.get('highlight_moment')} | {s.get('predicted_churn_rate')} |")
        return "\n".join(lines)

    def export_art_manifest(self) -> str:
        """Export all visual asset prompts as a structured Markdown manifest."""
        if not self.visual_assets: return "# 艺术资产清单\n暂无生成的资产。"
        
        lines = ["# 🎨 小说视觉资产清单 (ART.md)", "\n本清单包含 AI 绘画专用提示词，可直接用于 Midjourney 或 Stable Diffusion。\n"]
        
        # 1. 卷封面
        lines.append("## 📘 分卷封面图 (Volume Covers)")
        for asset in self.visual_assets:
            if asset.asset_type == "volume_cover":
                lines.append(f"### {asset.subject_id}")
                lines.append(f"**提示词 (Positive):**\n`{asset.positive_prompt}`")
                lines.append(f"**反向提示词 (Negative):**\n`{asset.negative_prompt}`")
                lines.append("---\n")

        # 2. 角色卡
        lines.append("## 🎭 核心角色视觉卡 (Character Cards)")
        for asset in self.visual_assets:
            if asset.asset_type == "character":
                lines.append(f"### {asset.subject_id}")
                lines.append(f"**提示词 (Positive):**\n`{asset.positive_prompt}`")
                lines.append(f"**反向提示词 (Negative):**\n`{asset.negative_prompt}`")
                lines.append("---\n")
                
        return "\n".join(lines)

    def apply_updates(self, updates: dict) -> None:
        """Apply incremental updates to the bible."""
        # 1. New characters
        for char_data in updates.get("new_characters", []):
            name = char_data.get("name")
            if name and name not in self.characters:
                self.characters[name] = CharacterProfile(
                    name=name,
                    role=char_data.get("role", "supporting"),
                    personality=char_data.get("personality", ""),
                    appearance="",
                    core_desire="",
                    fear="",
                    backstory="",
                    character_arc="",
                    first_appearance=1
                )

        # 2. Character updates
        for name, state in updates.get("character_updates", {}).items():
            char = self.get_character(name)
            if char:
                if isinstance(state, str):
                    if any(kw in state for kw in ["境", "级"]):
                        char.cultivation_realm = state
                elif isinstance(state, dict):
                    for k, v in state.items():
                        if hasattr(char, k):
                            setattr(char, k, v)

        # 3. New locations
        for loc, desc in updates.get("new_locations", {}).items():
            if self.world_rules:
                self.world_rules.geography[loc] = desc

        # 4. World rules
        for rule in updates.get("world_rule_additions", []):
            if self.world_rules:
                self.world_rules.world_constraints.append(rule)

        # 5. Seed Details (New!)
        for seed_data in updates.get("new_seeds", []):
            self.seeds_registry.append(SeedDetail(
                description=seed_data.get("description", ""),
                origin_chapter=seed_data.get("chapter", 0),
                category=seed_data.get("category", "environment")
            ))


@dataclass
class BibleSection:
    """A subset of the bible relevant to a specific volume."""

    volume_num: int
    relevant_characters: dict[str, CharacterProfile]
    world_rules_summary: str
    timeline_up_to_this_point: list[TimelineEvent]
    open_foreshadowing: list[ForeshadowingEntry]
    available_seeds: list[SeedDetail] = field(default_factory=list) # New field
    relationship_states_at_start: dict[str, dict[str, str]] = field(default_factory=dict)
    canonical_facts_this_volume: list[str] = field(default_factory=list)
