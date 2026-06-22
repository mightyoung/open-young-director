from young_writer.services.narrative_driver import (
    build_chapter_driver_packet,
    finalize_chapter_driver_context,
    render_chapter_driver_packet_summary,
    validate_chapter_driver_packet,
)
from young_writer.services.story_input import (
    ChapterPlan,
    CharacterEntry,
    GenerationPacket,
    ProjectBible,
    RuntimeOverrides,
    StyleProfile,
    WorldBible,
)


def _packet() -> GenerationPacket:
    return GenerationPacket(
        chapter_number=3,
        total_chapters=12,
        project_bible=ProjectBible(
            title="深渊归航",
            author="作者",
            genre="科幻修真",
            premise="林渊追查失踪舰队回声真相。",
            synopsis="林渊必须进入禁航海沟。",
        ),
        world_bible=WorldBible(
            summary="潮汐城邦依赖窗口航行。",
            locations=["白昼环控制室", "禁航海沟"],
            hard_constraints=["潮汐窗口每七十二小时开启一次"],
        ),
        characters=[
            CharacterEntry(
                id="character:lin-yuan",
                name="林渊",
                role="声呐译码师",
                motivation="找回母亲失踪真相",
                arc="必须承认信号来自过去",
                relationships=["顾砚青"],
            ),
            CharacterEntry(id="character:gu", name="顾砚青", role="工程师"),
        ],
        chapter_plan=ChapterPlan(
            chapter_number=3,
            title="回声坐标",
            summary="林渊确认回声坐标并准备进入禁航海沟。",
            key_events=["确认信号真假", "进入禁航海沟"],
            must_include=["潮汐窗口倒计时"],
            character_names=["林渊", "顾砚青"],
            location_ids=["location:禁航海沟"],
            continuity_in="承接上一章白昼环控制室的警报",
            continuity_out="海沟深处传来母亲的第二段回声",
            goal_lock="确认信号真假、进入禁航海沟",
            emotional_turn="从怀疑转为孤注一掷",
            magic_line="母亲回声可能来自二十七年前",
        ),
        style_profile=StyleProfile(style="dramatic"),
        runtime_overrides=RuntimeOverrides(previous_summary="上一章警报刚刚响起。"),
    )


def test_build_chapter_driver_packet_from_generation_packet():
    driver = build_chapter_driver_packet(_packet())

    assert driver["schema_version"] == "chapter_driver_packet.v1"
    assert driver["chapter_number"] == 3
    assert driver["scene_beats"][0]["purpose"] == "承接"
    assert driver["scene_beats"][1]["action"] == "确认信号真假"
    assert any(beat["location"] == "禁航海沟" for beat in driver["scene_beats"])
    assert driver["cast"][0]["name"] == "林渊"
    assert driver["cast"][0]["objective"] == "确认信号真假"
    assert "从怀疑转为孤注一掷" in driver["emotional_arc"]
    assert any("主线目标不可漂移" in item for item in driver["tension_points"])
    assert driver["cliffhanger"] == "海沟深处传来母亲的第二段回声"
    assert validate_chapter_driver_packet(driver) == []


def test_graph_packet_enriches_driver_evidence_and_bridge():
    driver = build_chapter_driver_packet(
        _packet(),
        chapter_graph_packet={
            "chapter_goal": "进入禁航海沟",
            "required_bridge": "开篇先接住白昼环控制室",
            "success_evidence": ["正文写出抵达禁航海沟的动作"],
            "target_destinations": ["禁航海沟"],
        },
    )

    assert driver["scene_beats"][0]["action"] == "开篇先接住白昼环控制室"
    assert driver["scene_beats"][0]["success_evidence"] == "正文写出抵达禁航海沟的动作"
    assert driver["cast"][0]["objective"] == "进入禁航海沟"
    summary = render_chapter_driver_packet_summary(driver)
    assert "场景节拍" in summary
    assert "角色驱动" in summary
    assert "结尾钩子" in summary


def test_driver_degrades_without_optional_fields():
    driver = build_chapter_driver_packet(
        {
            "chapter_number": 1,
            "chapter_plan": {"summary": "主角出发。"},
            "world_bible": {},
            "characters": [],
            "runtime_overrides": {},
        }
    )

    assert driver["schema_version"] == "chapter_driver_packet.v1"
    assert driver["scene_beats"][0]["action"] == "主角出发。"
    assert driver["cast"] == []
    assert validate_chapter_driver_packet(driver) == []


def test_finalize_chapter_driver_context_reconciles_graph_and_goal_lock():
    context = {
        "generation_packet": {
            "chapter_number": 4,
            "chapter_plan": {
                "chapter_number": 4,
                "summary": "主角出发。",
                "key_events": ["抵达废弃港"],
                "character_names": ["林渊"],
            },
            "world_bible": {"locations": ["废弃港"]},
            "characters": [{"name": "林渊", "role": "译码师"}],
            "runtime_overrides": {},
        },
        "chapter_graph_packet": {
            "chapter_goal": "抵达废弃港",
            "required_bridge": "开篇先接住白昼环控制室",
            "success_evidence": ["正文写出抵达废弃港的动作"],
        },
        "goal_lock_resolution": {"effective_goal_lock": "追查母亲信号"},
    }

    finalized = finalize_chapter_driver_context(context)

    assert finalized is context
    assert finalized["chapter_driver_packet"]["scene_beats"][0]["action"] == (
        "开篇先接住白昼环控制室"
    )
    assert finalized["chapter_driver_packet"]["cast"][0]["objective"] == "抵达废弃港"
    assert any(
        "追查母亲信号" in item
        for item in finalized["chapter_driver_packet"]["tension_points"]
    )
    assert finalized["chapter_driver_validation"] == []
