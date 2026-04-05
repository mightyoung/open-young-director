"""Tests for the context compactor."""
from __future__ import annotations

from crewai.content.novel.production_bible.bible_types import (
    BibleSection,
    CharacterProfile,
    ForeshadowingEntry,
)
from crewai.content.novel.services.context_compactor import ContextCompactor


def test_compact_bible_section_with_report_trims_inactive_context() -> None:
    """Inactive characters and foreshadowing should be trimmed with a report."""
    bible_section = BibleSection(
        volume_num=1,
        relevant_characters={
            "主角": CharacterProfile(
                name="主角",
                role="protagonist",
                personality="坚韧",
                appearance="黑发",
                core_desire="变强",
                fear="失败",
                backstory="出身平凡",
                character_arc="成长",
                first_appearance=1,
            ),
            "路人甲": CharacterProfile(
                name="路人甲",
                role="supporting",
                personality="沉默",
                appearance="普通",
                core_desire="生存",
                fear="被注意",
                backstory="只是普通修士",
                character_arc="",
                first_appearance=2,
            ),
        },
        world_rules_summary="灵力体系稳定，城中禁飞。",
        timeline_up_to_this_point=[],
        open_foreshadowing=[
            ForeshadowingEntry(
                id="fs-1",
                setup_chapter=1,
                setup_description="神秘令牌出现",
                payoff_chapter=3,
                payoff_description="揭示身份",
            ),
            ForeshadowingEntry(
                id="fs-2",
                setup_chapter=5,
                setup_description="远处伏笔",
                payoff_chapter=8,
                payoff_description="后续揭晓",
            ),
        ],
        relationship_states_at_start={},
        canonical_facts_this_volume=["主角不能违背宗门规矩"],
    )

    chapter_outline = {
        "chapter_num": 1,
        "title": "主角初遇令牌",
        "main_events": ["主角发现神秘令牌", "路人甲短暂出现"],
    }

    compactor = ContextCompactor({"context_budget_tokens": 1200})
    compacted, report = compactor.compact_bible_section_with_report(bible_section, chapter_outline)

    assert compacted is not None
    assert report.active_keywords
    assert report.original_character_count == 2
    assert report.compacted_character_count == 2
    assert report.original_foreshadowing_count == 2
    assert report.compacted_foreshadowing_count == 1
    assert report.trimmed_foreshadowing_count == 1
    assert report.estimated_tokens_saved >= 0
    assert compacted.relevant_characters["路人甲"].backstory == "[已压缩]"
    assert compacted.open_foreshadowing[0].id == "fs-1"
