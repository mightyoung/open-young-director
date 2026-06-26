"""Tests persistent narrative state snapshots and packets."""

from young_writer.services.narrative_state import (
    PACKET_SCHEMA_VERSION,
    apply_state_delta,
    build_narrative_state_packet,
    build_state_delta,
    record_narrative_state_after_save,
    render_narrative_state_packet_summary,
)


def test_build_state_delta_derives_story_graph_and_metadata(temp_project_dir):
    chapter_path = temp_project_dir / "chapters" / "ch001_第一章.md"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一章正文", encoding="utf-8")

    delta = build_state_delta(
        project_id="demo",
        run_id="run-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        story_graph_snapshot={
            "state": {
                "physical_location": "白昼环控制室",
                "scene_anchor": "白昼环控制室",
                "opening_excerpt": "林渊站在控制室。",
                "chapter_summary": "林渊确认异常信号真假。",
            }
        },
        rebaseline_delta={
            "completed_goal_subgoals": ["确认信号真假"],
            "destination_reached": ["白昼环控制室"],
        },
        context={
            "chapter_graph_packet": {
                "goal_lock": "确认信号真假、进入废弃港",
                "must_include_events": ["确认信号真假"],
                "target_destinations": ["废弃港"],
                "prohibited_inheritance": ["不要把远程信号源当作物理位置。"],
            }
        },
        key_events=["确认信号真假"],
        character_appearances=["林渊"],
        unresolved_goals=["进入废弃港"],
    )

    assert delta["timeline"]["physical_location"] == "白昼环控制室"
    assert delta["goal_progress"]["completed_goal_subgoals"] == ["确认信号真假"]
    assert delta["goal_progress"]["unresolved_goals"] == ["进入废弃港"]
    assert delta["characters"][0]["name"] == "林渊"
    assert delta["evidence_refs"][0]["checksum"]


def test_apply_state_delta_merges_and_excludes_completed_unresolved_goal(
    temp_project_dir,
):
    chapter_path = temp_project_dir / "ch002.md"
    chapter_path.write_text("第二章正文", encoding="utf-8")
    previous = {
        "project_id": "demo",
        "chapter_number": 1,
        "goal_progress": {
            "completed_goal_subgoals": ["确认信号真假"],
            "unresolved_goals": ["进入废弃港"],
        },
        "characters": {
            "林渊": {"name": "林渊", "last_seen_chapter": 1, "evidence_refs": []}
        },
    }
    delta = build_state_delta(
        project_id="demo",
        chapter_number=2,
        chapter_path=str(chapter_path),
        story_graph_snapshot={"state": {"physical_location": "废弃港"}},
        rebaseline_delta={"completed_goal_subgoals": ["进入废弃港"]},
        character_appearances=["顾砚青"],
        unresolved_goals=["进入废弃港", "破解回声坐标"],
    )

    snapshot = apply_state_delta(previous, delta)

    assert snapshot["chapter_number"] == 2
    assert snapshot["timeline"]["physical_location"] == "废弃港"
    assert snapshot["goal_progress"]["completed_goal_subgoals"] == [
        "确认信号真假",
        "进入废弃港",
    ]
    assert snapshot["goal_progress"]["unresolved_goals"] == ["破解回声坐标"]
    assert set(snapshot["characters"]) == {"林渊", "顾砚青"}


def test_record_narrative_state_after_save_persists_current_and_snapshot(
    temp_project_dir,
):
    chapter_path = temp_project_dir / "chapters" / "ch001_第一章.md"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一章正文", encoding="utf-8")

    result = record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        run_id="run-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        story_graph_result={
            "snapshot": {"state": {"physical_location": "白昼环控制室"}},
            "rebaseline_delta": {"destination_reached": ["白昼环控制室"]},
        },
        context={"chapter_graph_packet": {"goal_lock": "确认信号真假"}},
        summary="林渊确认异常信号真假。",
        key_events=["确认信号真假"],
        character_appearances=["林渊"],
    )

    snapshot_path = temp_project_dir / "narrative_state" / "snapshots" / "ch001.json"
    current_path = temp_project_dir / "narrative_state" / "current.json"
    assert result["snapshot_path"] == str(snapshot_path)
    assert snapshot_path.exists()
    assert current_path.exists()
    assert result["snapshot"]["timeline"]["physical_location"] == "白昼环控制室"


def test_build_narrative_state_packet_uses_previous_snapshot(temp_project_dir):
    chapter_path = temp_project_dir / "chapters" / "ch001_第一章.md"
    chapter_path.parent.mkdir(parents=True)
    chapter_path.write_text("第一章正文", encoding="utf-8")
    record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        chapter_number=1,
        chapter_path=str(chapter_path),
        story_graph_result={
            "snapshot": {
                "state": {
                    "physical_location": "白昼环控制室",
                    "chapter_summary": "林渊确认异常信号真假。",
                }
            },
            "rebaseline_delta": {"completed_goal_subgoals": ["确认信号真假"]},
        },
        context={"chapter_graph_packet": {"goal_lock": "进入废弃港"}},
        character_appearances=["林渊"],
        unresolved_goals=["进入废弃港"],
    )

    packet = build_narrative_state_packet(temp_project_dir, chapter_number=2)
    summary = render_narrative_state_packet_summary(packet)

    assert packet["schema_version"] == PACKET_SCHEMA_VERSION
    assert packet["source_chapter_number"] == 1
    assert packet["timeline"]["physical_location"] == "白昼环控制室"
    assert packet["active_characters"][0]["name"] == "林渊"
    assert "未解决事项: 进入废弃港" in summary


def test_resaving_earlier_chapter_does_not_merge_future_current_state(
    temp_project_dir,
):
    first_path = temp_project_dir / "chapters" / "ch001.md"
    second_path = temp_project_dir / "chapters" / "ch002.md"
    third_path = temp_project_dir / "chapters" / "ch003.md"
    first_path.parent.mkdir(parents=True)
    first_path.write_text("第一章", encoding="utf-8")
    second_path.write_text("第二章", encoding="utf-8")
    third_path.write_text("第三章", encoding="utf-8")
    record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        chapter_number=1,
        chapter_path=str(first_path),
        key_events=["event-1"],
        character_appearances=["char-1"],
    )
    record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        chapter_number=2,
        chapter_path=str(second_path),
        key_events=["event-2"],
        character_appearances=["char-2"],
    )
    record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        chapter_number=3,
        chapter_path=str(third_path),
        key_events=["event-3"],
        character_appearances=["char-3"],
    )

    record_narrative_state_after_save(
        project_dir=temp_project_dir,
        project_id="demo",
        chapter_number=2,
        chapter_path=str(second_path),
        key_events=["event-2b"],
        character_appearances=["char-2b"],
    )
    packet = build_narrative_state_packet(temp_project_dir, chapter_number=3)

    assert "event-2b" in packet["recent_key_events"]
    assert "event-3" not in packet["recent_key_events"]
    assert [item["name"] for item in packet["active_characters"]] == [
        "char-2b",
        "char-1",
    ]
    downstream_packet = build_narrative_state_packet(
        temp_project_dir, chapter_number=4
    )
    assert downstream_packet["source_chapter_number"] == 2
    assert "event-2b" in downstream_packet["recent_key_events"]
    assert "event-3" not in downstream_packet["recent_key_events"]
    assert not (temp_project_dir / "narrative_state" / "snapshots" / "ch003.json").exists()
