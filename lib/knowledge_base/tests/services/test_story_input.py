"""Tests for structured story input assets and assembly."""

from types import SimpleNamespace

from young_writer.services.input_assembler import InputAssembler
from young_writer.services.story_input import (
    ChapterPlan,
    GenerationPacket,
    InputValidationReport,
    ProjectBible,
    RuntimeOverrides,
    StyleProfile,
    WorldBible,
    build_story_input_bundle,
    load_story_input_bundle,
    validate_generation_packet,
    write_story_input_bundle,
)


def test_story_input_bundle_round_trips(temp_project_dir):
    project_dir = temp_project_dir / "runtime" / "projects" / "深渊归航_demo123"
    project_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        title="深渊归航",
        author="作者",
        genre="科幻修真",
        outline="沈夜带着异质核心归来，调查母舰失踪真相。",
        world_setting="空间城与深渊航道构成主要舞台。",
        character_intro="沈夜：主角。顾砚青：工程师。",
        total_chapters=3,
    )

    bundle = build_story_input_bundle(project, writing_options={"style": "dramatic"})
    write_story_input_bundle(project_dir, bundle)
    reloaded = load_story_input_bundle(project_dir)

    assert reloaded is not None
    assert reloaded.project_bible.title == "深渊归航"
    assert reloaded.chapter_plans[0].summary
    assert reloaded.style_profile.style == "dramatic"


def test_validate_generation_packet_blocks_unknown_character_ids():
    packet = GenerationPacket(
        chapter_number=1,
        total_chapters=3,
        project_bible=ProjectBible(
            title="测试项目",
            author="作者",
            genre="科幻",
            premise="前提",
            synopsis="大纲",
        ),
        world_bible=WorldBible(summary="空间城"),
        characters=[],
        chapter_plan=ChapterPlan(
            chapter_number=1,
            title="第1章",
            summary="沈夜调查空间城异动",
            key_events=["调查空间城异动"],
            character_ids=["character:shenye"],
            continuity_in="承接上一章",
            continuity_out="留下线索",
            goal_lock="守住空间城",
        ),
        style_profile=StyleProfile(),
        runtime_overrides=RuntimeOverrides(),
        validation=InputValidationReport(),
    )

    report = validate_generation_packet(packet)

    assert report.invalid is True
    assert "未知角色" in report.blocking_issues[0]


def test_validate_generation_packet_blocks_missing_goal_lock():
    packet = GenerationPacket(
        chapter_number=1,
        total_chapters=3,
        project_bible=ProjectBible(
            title="测试项目",
            author="作者",
            genre="科幻",
            premise="前提",
            synopsis="大纲",
        ),
        world_bible=WorldBible(summary="空间城"),
        characters=[],
        chapter_plan=ChapterPlan(
            chapter_number=1,
            title="第1章",
            summary="沈夜调查空间城异动",
            key_events=["调查空间城异动"],
            continuity_in="承接上一章",
            continuity_out="留下线索",
            goal_lock="",
        ),
        style_profile=StyleProfile(),
        runtime_overrides=RuntimeOverrides(
            volume_guidance_payload={"goal_lock": "守住空间城"}
        ),
        validation=InputValidationReport(),
    )

    report = validate_generation_packet(packet)

    assert report.invalid is True
    assert any("chapter_plan.goal_lock" in issue for issue in report.blocking_issues)


def test_input_assembler_enriches_context_with_generation_packet(temp_project_dir):
    project_dir = temp_project_dir / "runtime" / "projects" / "深渊归航_demo123"
    project_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        id="demo123",
        title="深渊归航",
        author="作者",
        genre="科幻修真",
        outline="沈夜带着异质核心归来，调查母舰失踪真相。",
        world_setting="空间城与深渊航道构成主要舞台。",
        character_intro="沈夜：主角。顾砚青：工程师。",
        total_chapters=3,
        metadata={},
    )
    config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
    )

    assembler = InputAssembler(config)
    context = assembler.enrich_context(
        chapter_number=2,
        base_context={"previous_summary": "上一章沈夜返回空间城。"},
        writing_options={"style": "dramatic", "perspective": "third_limited"},
    )

    assert context["generation_packet"]["chapter_number"] == 2
    assert context["project_outline"]
    assert context["character_names"][0] == "沈夜"
    assert context["story_input_validation"]["blocking_issues"] == []
    assert context["canonical_input_policy"]["story_input_json"] == "canonical"
    assert context["goal_lock_resolution"]["effective_source"] == "chapter_plan.goal_lock"


def test_input_assembler_marks_runtime_goal_lock_conflict_as_plan_first(temp_project_dir):
    project_dir = temp_project_dir / "runtime" / "projects" / "深渊归航_demo123"
    project_dir.mkdir(parents=True, exist_ok=True)
    project = SimpleNamespace(
        id="demo123",
        title="深渊归航",
        author="作者",
        genre="科幻修真",
        outline="守住空间城，再调查母舰失踪真相。",
        world_setting="空间城与深渊航道构成主要舞台。",
        character_intro="沈夜：主角。顾砚青：工程师。",
        total_chapters=3,
        metadata={},
    )
    config = SimpleNamespace(
        current_project=project,
        generation=SimpleNamespace(output_dir=str(project_dir), chapters_per_volume=60),
    )

    assembler = InputAssembler(config)
    context = assembler.enrich_context(
        chapter_number=1,
        base_context={
            "volume_guidance_payload": {
                "goal_lock": "追查异质核心",
                "goal_lock_mode": "additive_only",
            }
        },
    )

    resolution = context["goal_lock_resolution"]
    assert resolution["effective_source"] == "chapter_plan.goal_lock"
    assert resolution["conflict"] is True
    assert "watch_items" in context["story_input_validation"]
