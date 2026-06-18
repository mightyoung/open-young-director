"""Tests for structured story input assets and assembly."""

from types import SimpleNamespace

from young_writer.services.input_assembler import InputAssembler
from young_writer.services.story_input import (
    CharacterEntry,
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
    assert reloaded.chapter_plans[0].goal_lock != reloaded.chapter_plans[0].summary
    assert all(
        "推进开场阶段冲突" not in event
        for event in reloaded.chapter_plans[0].key_events
    )


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
    assert context["characters"][0]["name"] == "沈夜"
    assert context["characters"][0]["objective_this_chapter"]
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


def test_input_assembler_does_not_mutate_base_context(temp_project_dir):
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
    base_context = {"previous_summary": "上一章沈夜返回空间城。", "time_of_day": "夜晚"}

    context = assembler.enrich_context(chapter_number=2, base_context=base_context)

    assert context is not base_context
    assert base_context == {
        "previous_summary": "上一章沈夜返回空间城。",
        "time_of_day": "夜晚",
    }
    assert context["chapter_number"] == 2
    assert context["time_of_day"] == "夜晚"


def test_story_input_bundle_compacts_seed_goal_lock_and_key_events():
    project = SimpleNamespace(
        title="回声航道",
        author="作者",
        genre="科幻悬疑",
        outline="林渊追查失踪舰队回声真相并在白昼环截获异常信号。",
        world_setting="白昼环。回声空域。星门。",
        character_intro="林渊：主角。顾岚：舰长。",
        total_chapters=1,
    )

    bundle = build_story_input_bundle(project)
    plan = bundle.chapter_plans[0]

    assert plan.goal_lock == "林渊追查失踪舰队回声真相"
    assert plan.key_events[0] == "林渊追查失踪舰队回声真相"
    assert plan.key_events == ["林渊追查失踪舰队回声真相"]
    assert all("推进开场阶段冲突" not in event for event in plan.key_events)


def test_story_input_bundle_derives_goal_lock_per_chapter():
    project = SimpleNamespace(
        title="回声航道",
        author="作者",
        genre="科幻悬疑",
        outline="林渊追查失踪舰队回声真相并在白昼环截获异常信号。林渊确认信号来自二十七年前的远征舰队。",
        world_setting="白昼环。回声空域。",
        character_intro="林渊：主角。",
        total_chapters=2,
    )

    bundle = build_story_input_bundle(project)

    assert bundle.chapter_plans[0].goal_lock == "林渊追查失踪舰队回声真相"
    assert bundle.chapter_plans[1].goal_lock == "林渊确认信号来自二十七年前的远征舰队"


def test_story_input_bundle_preserves_character_descriptions_and_scifi_locations():
    project = SimpleNamespace(
        title="回声航道",
        author="作者",
        genre="科幻悬疑",
        outline=(
            "林渊在白昼环监测站确认异常信号来自二十七年前。"
            "随后前往企业主控塔夺取开启星门的权限。"
        ),
        world_setting="白昼环监测站。企业主控塔。回声空域。星门。",
        character_intro=(
            "林渊：空间语言学工程师，习惯先验证后行动，执念是找回母亲。"
            "顾岚：舰长，语气冷静克制，必须掩护林渊离开白昼环。"
        ),
        total_chapters=2,
    )

    bundle = build_story_input_bundle(project)

    assert bundle.characters[0].role == "空间语言学工程师"
    assert bundle.characters[0].motivation == "执念是找回母亲"
    assert bundle.characters[1].voice == "语气冷静克制"
    assert "白昼环监测站" in bundle.world_bible.locations
    assert "企业主控塔" in bundle.world_bible.locations
    assert bundle.chapter_plans[0].location_ids == ["location:白昼环监测站"]
    assert bundle.chapter_plans[1].location_ids == ["location:企业主控塔", "location:星门"]


def test_story_input_bundle_compacts_terminal_rescue_goal_lock():
    project = SimpleNamespace(
        title="回声航道",
        author="作者",
        genre="科幻悬疑",
        outline="林渊进入回声空域救回母亲并公开星门真相。",
        world_setting="白昼环。回声空域。星门。",
        character_intro="林渊：主角。顾岚：舰长。",
        total_chapters=1,
    )

    bundle = build_story_input_bundle(project)
    plan = bundle.chapter_plans[0]

    assert plan.goal_lock == "林渊救回母亲"
    assert plan.key_events == ["林渊救回母亲"]


def test_validate_generation_packet_requires_chinese_narrative_fields():
    packet = GenerationPacket(
        chapter_number=1,
        total_chapters=3,
        project_bible=ProjectBible(
            title="Echo Route",
            author="author",
            genre="science fiction",
            premise="A captain investigates a missing fleet.",
            synopsis="The story follows a signal across the ring.",
        ),
        world_bible=WorldBible(
            summary="A ring station and echo space.",
            locations=["Ring Station"],
        ),
        characters=[
            CharacterEntry(
                id="character:linyuan",
                name="Lin Yuan",
            )
        ],
        chapter_plan=ChapterPlan(
            chapter_number=1,
            title="Chapter One",
            summary="Lin Yuan investigates the signal.",
            key_events=["Lin Yuan intercepts the abnormal signal"],
            character_ids=["character:linyuan"],
            character_names=["Lin Yuan"],
            continuity_in="Start from the port.",
            continuity_out="Leave a signal clue.",
            goal_lock="Investigate the missing fleet echo.",
        ),
        style_profile=StyleProfile(),
    )

    report = validate_generation_packet(packet)

    assert report.invalid is True
    assert any("必须使用中文输入" in issue for issue in report.blocking_issues)


def test_validate_generation_packet_accepts_chinese_narrative_fields():
    packet = GenerationPacket(
        chapter_number=1,
        total_chapters=3,
        project_bible=ProjectBible(
            title="回声航道",
            author="作者",
            genre="科幻悬疑",
            premise="林渊追查失踪舰队回声真相。",
            synopsis="林渊在白昼环截获异常信号，并确认线索来自旧远征舰队。",
        ),
        world_bible=WorldBible(
            summary="白昼环与回声空域构成主要舞台。",
            locations=["白昼环"],
        ),
        characters=[
            CharacterEntry(
                id="character:linyuan",
                name="林渊",
            )
        ],
        chapter_plan=ChapterPlan(
            chapter_number=1,
            title="第一章 回声信号",
            summary="林渊追查失踪舰队回声真相。",
            key_events=["林渊截获异常信号"],
            character_ids=["character:linyuan"],
            character_names=["林渊"],
            continuity_in="林渊抵达白昼环。",
            continuity_out="异常信号指向旧远征舰队。",
            goal_lock="林渊追查失踪舰队回声真相",
            purpose="开场阶段的主线推进",
        ),
        style_profile=StyleProfile(),
    )

    report = validate_generation_packet(packet)

    assert not any("必须使用中文输入" in issue for issue in report.blocking_issues)
