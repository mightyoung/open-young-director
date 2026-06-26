"""Tests for structured story input assets and assembly."""

from types import SimpleNamespace

from young_writer.services.input_assembler import InputAssembler
from young_writer.services.story_input import (
    ChapterPlan,
    CharacterEntry,
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


def test_seed_goal_lock_handles_discovery_clause_after_identity_prefix():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="近未来海洋悬疑科幻",
        outline=(
            "海洋声学工程师林澈回到岚港，发现深海监听阵列记录到来自失踪父亲的旧式摩斯信号。"
            "林澈必须阻止岚港潮汐异常和集体失忆。"
        ),
        world_setting="岚港外海有深海监听阵列和零号监听站。",
        character_intro="林澈：主角，海洋声学工程师。许望舒：救援队队长。",
        total_chapters=3,
    )

    bundle = build_story_input_bundle(project)
    first_plan = bundle.chapter_plans[0]

    assert first_plan.goal_lock.startswith("林澈发现深海监听")
    assert "摩斯信号" in first_plan.goal_lock
    assert "海洋声学工程师林澈回到岚港" not in first_plan.goal_lock
    assert not first_plan.goal_lock.endswith("的")
    assert first_plan.key_events == [first_plan.goal_lock]
    assert first_plan.must_include == [first_plan.goal_lock]


def test_seed_goal_lock_preserves_long_reactor_noun_in_50_chapter_plan():
    project = SimpleNamespace(
        title="深海回声五十章",
        author="作者",
        genre="近未来海洋科幻悬疑",
        outline=(
            "近未来，深海城市群依靠一座名为潮汐心脏的古老反应堆维持生态屏障。"
            "年轻声学工程师林澈在一次海底地震后听见只属于自己的鲸歌信号。"
        ),
        world_setting="海下穹顶城和深渊矿区构成主要舞台。",
        character_intro="林澈：主角，声学工程师。顾南舟：潜航员。",
        total_chapters=50,
    )

    bundle = build_story_input_bundle(project)
    first_goals = [plan.goal_lock for plan in bundle.chapter_plans[:8]]
    reactor_goals = [goal for goal in first_goals if "潮汐心脏" in goal]

    assert reactor_goals
    assert all("反应堆" in goal for goal in reactor_goals)
    assert all(not goal.endswith("古老反应") for goal in reactor_goals)


def test_long_run_repeats_action_units_instead_of_background_premise():
    project = SimpleNamespace(
        title="深海回声五十章",
        author="作者",
        genre="近未来海洋科幻悬疑",
        outline=(
            "近未来，深海城市群依靠一座名为潮汐心脏的古老反应堆维持生态屏障。"
            "年轻声学工程师林澈在一次海底地震后听见只属于自己的鲸歌信号，信号指向三十年前失踪的母亲。"
            "她与被流放的潜航员顾南舟组成小队，逐层进入海沟遗迹，揭开潮汐心脏其实在封印外海意识体的真相。"
            "全书要从调查异常、城市政治、深海远征、母亲真相、外海意识苏醒五个阶段推进，最终林澈必须做出选择。"
        ),
        world_setting="海下穹顶城和深渊矿区构成主要舞台。",
        character_intro="林澈：主角，声学工程师。顾南舟：潜航员。",
        total_chapters=50,
    )

    bundle = build_story_input_bundle(project)
    chapter_seven = bundle.chapter_plans[6]

    assert "潮汐心脏的古老反应堆维持生态屏障" not in chapter_seven.goal_lock
    assert bundle.chapter_plans[1].goal_lock == "林澈追查母亲失踪线索"
    assert chapter_seven.goal_lock == "林澈调查母亲失踪线索"
    assert bundle.chapter_plans[11].goal_lock == "林澈复听并比对母亲最后信号确认来源"
    assert (
        bundle.chapter_plans[12].goal_lock
        == "林澈与小队比对潮汐心脏与外海意识体封印记录"
    )
    assert (
        bundle.chapter_plans[16].goal_lock
        == "林澈比对母亲警告与星痕中枢档案确认关系"
    )
    assert bundle.chapter_plans[19].goal_lock == "林澈组织深海远征进入遗迹"
    assert "五个阶段推进" not in bundle.chapter_plans[19].goal_lock
    assert bundle.chapter_plans[25].goal_lock == "林澈制定执行第三种选择的方案"
    assert "揭开必须" not in bundle.chapter_plans[25].goal_lock
    assert bundle.chapter_plans[28].goal_lock == "林澈接入主数据库追踪外海意识苏醒风险"


def test_chapter_plans_distribute_actionable_outline_units_across_long_run():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="近未来海洋悬疑科幻",
        outline=(
            "海洋声学工程师林澈回到岚港，发现深海监听阵列记录到来自失踪父亲的旧式摩斯信号。"
            "岚港居民每逢大潮都会集体遗忘一段共同经历，港口企业、海研所和废弃零号监听站都在掩盖一次深潜事故。"
            "林澈必须沿着潮汐异常、集体失忆和深海回声三条线追查真相，逐步确认父亲并非单纯遇难。"
            "故事以林澈阻止岚港潮汐异常和集体失忆为主线。"
        ),
        world_setting="岚港外海有深海监听阵列和零号监听站。",
        character_intro="林澈：主角，海洋声学工程师。许望舒：救援队队长。",
        total_chapters=30,
    )

    bundle = build_story_input_bundle(project)
    first_five_summaries = [plan.summary for plan in bundle.chapter_plans[:5]]
    first_five_locks = [plan.goal_lock for plan in bundle.chapter_plans[:5]]

    assert len(set(first_five_summaries)) > 1
    assert "旧式摩斯信号" in first_five_summaries[0]
    assert "岚港居民" in first_five_summaries[1]
    assert "确认父亲并非单纯遇难" in first_five_summaries[2]
    assert len(set(first_five_locks)) > 1
    assert "旧式摩斯信号" in first_five_locks[0]
    assert all(not goal.endswith("三十") for goal in first_five_locks)
    assert bundle.chapter_plans[4].goal_lock != first_five_locks[0]
    assert "林澈" in bundle.chapter_plans[4].goal_lock
    assert any(
        plan.goal_lock.endswith("岚港集体遗忘")
        for plan in bundle.chapter_plans[:8]
    )
    assert not any(
        "每逢大潮都会集体遗忘一段共同经历" in plan.goal_lock
        for plan in bundle.chapter_plans[:8]
    )


def test_chapter_plan_compresses_role_prefix_and_possessive_background():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="近未来海洋悬疑科幻",
        outline=(
            "调查记者许照晚追查岚港居民集体遗忘事件。"
            "林澈的父亲当年参与一项以声波保存记忆的秘密实验。"
        ),
        world_setting="岚港外海有深海监听阵列和零号监听站。",
        character_intro="林澈：主角，海洋声学工程师。许照晚：调查记者。",
        total_chapters=6,
    )

    bundle = build_story_input_bundle(project)
    goals = [plan.goal_lock for plan in bundle.chapter_plans]

    assert "许照晚追查岚港居民集体遗忘事件" in goals[0]
    assert "许照晚调查记者许照晚" not in "".join(goals)
    assert any(goal.startswith("林澈发现父亲参与声波记忆实验线索") for goal in goals)
    assert "林澈发现林澈的父亲" not in "".join(goals)


def test_chapter_plan_trims_dangling_suffix_after_goal_compaction():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="近未来海洋悬疑科幻",
        outline="岚港海域出现周期性低频回声，逐步抹除居民关于灾难的记忆。",
        world_setting="岚港外海有深海监听阵列和零号监听站。",
        character_intro="林澈：主角，海洋声学工程师。",
        total_chapters=1,
    )

    bundle = build_story_input_bundle(project)
    goal = bundle.chapter_plans[0].goal_lock

    assert goal == "林澈发现岚港低频回声抹除记忆源头"
    assert not goal.endswith("关于")


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
        writing_options={
            "style": "dramatic",
            "perspective": "third_limited",
            "humanization_level": "strict",
        },
    )

    assert context["generation_packet"]["chapter_number"] == 2
    assert context["project_outline"]
    assert context["character_names"][0] == "沈夜"
    assert context["characters"][0]["name"] == "沈夜"
    assert context["characters"][0]["objective_this_chapter"]
    assert context["writing_options"]["humanization_level"] == "strict"
    assert (
        context["generation_packet"]["style_profile"]["humanization_level"] == "strict"
    )
    assert context["story_input_validation"]["blocking_issues"] == []
    assert context["canonical_input_policy"]["story_input_json"] == "canonical"
    assert context["goal_lock_resolution"]["effective_source"] == "chapter_plan.goal_lock"
    assert context["chapter_driver_packet"]["schema_version"] == "chapter_driver_packet.v1"
    assert context["chapter_driver_packet"]["chapter_number"] == 2
    assert "场景节拍" in context["chapter_driver_summary"]
    assert context["chapter_driver_validation"] == []


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


def test_story_input_bundle_first_chapter_does_not_inherit_previous_chapter():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="克苏鲁悬疑",
        outline="林澈追查岚港潮汐异常。",
        world_setting="岚港。零号监听站。",
        character_intro="林澈：主角。",
        total_chapters=2,
    )

    bundle = build_story_input_bundle(project)

    assert "上一章" not in bundle.chapter_plans[0].continuity_in
    assert "上一章" in bundle.chapter_plans[1].continuity_in


def test_story_input_bundle_turns_non_action_premise_into_actionable_goal():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="克苏鲁悬疑",
        outline="近未来海滨城市岚港连续出现潮汐异常和集体失忆。",
        world_setting="故事发生在近未来岚港，海底有废弃的零号监听站。",
        character_intro="林澈：海洋声学工程师。许照晚：调查记者。",
        total_chapters=1,
    )

    bundle = build_story_input_bundle(project)
    plan = bundle.chapter_plans[0]

    assert plan.goal_lock == "林澈发现岚港潮汐异常和集体失忆"
    assert plan.key_events == ["林澈发现岚港潮汐异常和集体失忆"]
    assert not plan.goal_lock.endswith("和")


def test_story_input_bundle_advances_repeated_seed_goals():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="克苏鲁悬疑",
        outline="近未来海滨城市岚港连续出现潮汐异常和集体失忆。",
        world_setting="故事发生在近未来岚港，海底有废弃的零号监听站。",
        character_intro="林澈：海洋声学工程师。许照晚：调查记者。",
        total_chapters=3,
    )

    bundle = build_story_input_bundle(project)
    goals = [plan.goal_lock for plan in bundle.chapter_plans]

    assert goals == [
        "林澈发现岚港潮汐异常和集体失忆",
        "林澈调查岚港潮汐异常和集体失忆",
        "林澈确认岚港潮汐异常和集体失忆",
    ]
    assert [plan.key_events for plan in bundle.chapter_plans] == [[goal] for goal in goals]


def test_story_input_bundle_advances_repeated_morse_signal_goals():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="近未来海洋悬疑科幻",
        outline=(
            "海洋声学工程师林澈回到岚港，发现深海监听阵列记录到来自失踪父亲的旧式摩斯信号。"
        ),
        world_setting="岚港外海有深海监听阵列和零号监听站。",
        character_intro="林澈：主角，海洋声学工程师。许望舒：救援队队长。",
        total_chapters=3,
    )

    bundle = build_story_input_bundle(project)
    goals = [plan.goal_lock for plan in bundle.chapter_plans]

    assert goals == [
        "林澈发现深海监听阵列记录到来自失踪父亲的旧式摩斯信号",
        "林澈核查摩斯信号来源",
        "林澈确认摩斯信号与父亲有关",
    ]
    assert "林澈调查深海监听阵列记录到来自失踪父亲的旧式摩斯信号" not in goals


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


def test_seed_key_events_split_compound_goal_lock_into_actionable_events():
    project = SimpleNamespace(
        title="深海回声",
        author="作者",
        genre="现实奇幻悬疑",
        outline=(
            "沿海城市突发异常回声事件，青年声学工程师林澈在调查中发现海底旧站、"
            "失踪档案与城市记忆被篡改的关联。"
            "他必须在五十章内追查回声源头、保护身边人，并揭开十年前深海实验的真相。"
        ),
        world_setting="近未来沿海城市雾港，旧海底观测站与传感网络交织。",
        character_intro="林澈：青年声学工程师。许未央：调查记者。",
        total_chapters=50,
    )

    bundle = build_story_input_bundle(project)
    archive_plan = next(
        plan for plan in bundle.chapter_plans if "失踪档案" in plan.goal_lock
    )
    target_plan = next(
        plan for plan in bundle.chapter_plans if "保护身边人" in plan.goal_lock
    )

    assert "林澈调查失踪档案与城市记忆被篡改的关联" in archive_plan.key_events
    assert target_plan.key_events != [target_plan.goal_lock]
    assert "林澈追查回声源头" in target_plan.key_events
    assert "保护身边人" in target_plan.goal_lock
    assert all("保护身边人" not in event for event in target_plan.key_events)
    assert target_plan.must_include == target_plan.key_events
