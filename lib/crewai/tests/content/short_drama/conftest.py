"""Pytest fixtures for short_drama tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.production_bible.bible_types import (
    CharacterProfile,
    ProductionBible,
    TimelineEvent,
    WorldRules,
)
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.short_drama_types import (
    EpisodeOutline,
    ShortDramaBible,
    ShortDramaEpisode,
    ShortDramaScene,
    Shot,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# ProductionBible fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bible() -> ProductionBible:
    """Construct a minimal ProductionBible for testing."""
    characters = {
        "韩林": CharacterProfile(
            name="韩林",
            role="protagonist",
            personality="坚韧不拔，心思缜密",
            appearance="少年模样，眉清目秀",
            core_desire="突破修为，探寻真相",
            fear="失去至亲",
            backstory="出身寒门，偶得机缘踏上修仙路",
            character_arc="从懵懂少年成长为一代宗师",
            first_appearance=1,
            cultivation_realm="炼气期",
            faction="青云宗",
            speech_pattern="沉稳有力，简洁直接",
            relationships={"长老": "师徒", "对手": "竞争"},
        ),
        "长老": CharacterProfile(
            name="长老",
            role="supporting",
            personality="慈祥和蔼，经验丰富",
            appearance="白发苍苍，仙风道骨",
            core_desire="传承道统",
            fear="宗门衰落",
            backstory="青云宗元老，教导过多代弟子",
            character_arc="见证后辈成长",
            first_appearance=1,
            cultivation_realm="金丹期",
            faction="青云宗",
            speech_pattern="循循善诱",
            relationships={"韩林": "师徒"},
        ),
    }

    world_rules = WorldRules(
        power_system_name="修仙灵力体系",
        cultivation_levels=["炼气", "筑基", "金丹", "元婴", "化神"],
        level_abilities={"炼气": ["引气入体"], "筑基": ["凝气化液"]},
        world_constraints=["不可逆天而行", "因果报应"],
        geography={"青云山": "宗门所在，云雾缭绕"},  # type: ignore[arg-type]
        factions={"青云宗": "正道领袖"},  # type: ignore[arg-type]
    )

    timeline = [
        TimelineEvent(
            id="event_1",
            chapter_range=(1, 3),
            volume_num=1,
            description="韩林入宗测试",
            involved_characters=["韩林", "长老"],
            consequences=["韩林入门"],
        ),
    ]

    return ProductionBible(
        characters=characters,
        world_rules=world_rules,
        timeline=timeline,
    )


@pytest.fixture
def short_drama_bible(mock_bible: ProductionBible) -> ShortDramaBible:
    """Build a ShortDramaBible from mock_bible."""
    builder = ShortDramaBibleBuilder(style="xianxia")
    return builder.build(
        bible=mock_bible,
        episode_num=1,
        series_title="仙侠史诗",
        episode_context="上集韩林在测灵仪式上震惊四座，本集将继续他在青云宗的修行之路。",
        characters_in_episode=["韩林", "长老"],
    )


# ---------------------------------------------------------------------------
# EpisodeOutline fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_episode_outline() -> EpisodeOutline:
    """Return a hardcoded EpisodeOutline for testing."""
    return EpisodeOutline(
        episode_num=1,
        title="第1集：入门",
        episode_summary="韩林通过测灵仪式，正式成为青云宗弟子，开始了他的修仙之路。",
        scene_plan=[
            {
                "scene_number": 1,
                "location": "青云山演武场",
                "time_of_day": "清晨",
                "description": "韩林来到青云宗参加入门测试",
                "key_actions": ["韩林入场", "测灵仪式", "震惊全场"],
                "characters": ["韩林", "长老"],
                "emotion": "紧张/兴奋",
                "duration_estimate": 45,
            },
            {
                "scene_number": 2,
                "location": "青云宗大殿",
                "time_of_day": "上午",
                "description": "韩林正式入门，领取宗门物资",
                "key_actions": ["拜师", "领取物资", "结识师兄"],
                "characters": ["韩林", "长老"],
                "emotion": "喜悦/期待",
                "duration_estimate": 30,
            },
        ],
    )


# ---------------------------------------------------------------------------
# Shot fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_shot() -> Shot:
    """Return a single sample Shot."""
    return Shot(
        shot_number=1,
        scene_number=1,
        duration_seconds=5.0,
        shot_type="establishing",
        action="韩林站在测灵石前，神情紧张，周围站满了围观的弟子",
        characters=["韩林"],
        video_prompt="establishing shot, 韩林站在测灵石前, 清晨光线, 仙侠风格",
        voiceover_segment="今日，是决定我命运的一天",
        emotion="紧张",
    )


@pytest.fixture
def sample_shots() -> list[Shot]:
    """Return a list of sample Shot objects."""
    return [
        Shot(
            shot_number=1,
            scene_number=1,
            duration_seconds=5.0,
            shot_type="establishing",
            action="韩林站在测灵石前，神情紧张",
            characters=["韩林"],
            video_prompt="establishing, 测灵石, 仙侠风格",
            voiceover_segment="今日是决定我命运的一天",
            emotion="紧张",
        ),
        Shot(
            shot_number=2,
            scene_number=1,
            duration_seconds=4.0,
            shot_type="medium",
            action="测灵石突然发出耀眼光芒，众人惊呼",
            characters=["韩林"],
            video_prompt="medium shot, 测灵石发光, 众人惊呼",
            voiceover_segment="",
            emotion="震惊",
        ),
        Shot(
            shot_number=3,
            scene_number=1,
            duration_seconds=6.0,
            shot_type="close_up",
            action="长老走到韩林面前，面露惊讶之色",
            characters=["长老", "韩林"],
            video_prompt="close up, 长老表情, 仙侠风格",
            voiceover_segment="此子天赋异禀，将来必成大器",
            emotion="惊讶",
        ),
    ]


# ---------------------------------------------------------------------------
# ShortDramaScene / ShortDramaEpisode fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_short_drama_scene(sample_shots: list[Shot]) -> ShortDramaScene:
    """Return a ShortDramaScene with sample shots."""
    scene = ShortDramaScene(
        scene_number=1,
        location="青云山演武场",
        time_of_day="清晨",
        description="韩林参加入门测试",
    )
    for shot in sample_shots:
        scene.add_shot(shot)
    return scene


@pytest.fixture
def sample_short_drama_episode(sample_short_drama_scene: ShortDramaScene) -> ShortDramaEpisode:
    """Return a ShortDramaEpisode with one scene."""
    episode = ShortDramaEpisode(
        episode_num=1,
        title="第1集：入门",
        summary="韩林通过测灵仪式，正式成为青云宗弟子",
        voiceover_intro="修仙之路，始于足下",
        voiceover_outro="他的修仙之路，正式开始",
        episode_context="上集韩林在测灵仪式上震惊四座",
    )
    episode.add_scene(sample_short_drama_scene)
    return episode


# ---------------------------------------------------------------------------
# Mock LLM fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    """Return a mock LLM that returns preset responses."""
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.model = "mock-llm"
    return mock


# ---------------------------------------------------------------------------
# Novel project fixture (tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture
def test_novel_project(tmp_path: Path) -> Path:
    """Create a mock novel project directory with basic structure."""
    project_dir = tmp_path / "测试小说_novel"
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(parents=True)

    # Create world.json (ProductionBible JSON)
    bible_data = {
        "characters": {
            "主角": {
                "name": "主角",
                "role": "protagonist",
                "personality": "勇敢",
                "appearance": "普通",
                "core_desire": "成为强者",
                "fear": "死亡",
                "backstory": "平凡少年",
                "character_arc": "成长",
                "first_appearance": 1,
            }
        },
        "world_rules": None,
        "timeline": [],
        "foreshadowing_registry": {},
        "canonical_relationships": {},
        "volume_boundaries": {},
    }
    import json

    with open(project_dir / "bible.json", "w", encoding="utf-8") as f:
        json.dump(bible_data, f, ensure_ascii=False)

    # Create pipeline_state.json
    state_data = {
        "world_name": "测试世界",
        "plot_ready": True,
        "volumes_count": 1,
    }
    with open(project_dir / "pipeline_state.json", "w", encoding="utf-8") as f:
        json.dump(state_data, f, ensure_ascii=False)

    # Create sample chapter
    chapter_text = """第1章 入门

清晨，阳光洒在青云山的演武场上。
韩林站在测灵石前，深吸一口气。
测灵石突然发出耀眼光芒，众人惊呼。
长老走到韩林面前，面露惊讶之色。

第2章 修行

韩林正式成为青云宗弟子。
他开始学习宗门功法，努力修行。
"""
    with open(chapters_dir / "chapter_001.md", "w", encoding="utf-8") as f:
        f.write(chapter_text)

    return project_dir


# ---------------------------------------------------------------------------
# Mock crewai agent / task for integration tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_crewai_agent():
    """Mock a crewai Agent for testing without real LLM calls."""
    from unittest.mock import MagicMock

    agent = MagicMock()
    agent.role = "测试角色"
    agent.goal = "测试目标"
    return agent
