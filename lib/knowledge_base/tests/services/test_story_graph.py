"""Tests for deterministic story graph extraction and packet building."""

from young_writer.services.story_graph.build import (
    build_story_graph_snapshot,
    record_story_graph_after_save,
)
from young_writer.services.story_graph.packet import build_chapter_graph_packet
from young_writer.services.story_graph.rebaseline import derive_rebaseline_delta
from young_writer.services.story_input import (
    ChapterPlan,
    ProjectBible,
    StoryInputBundle,
    StyleProfile,
    WorldBible,
    write_story_input_bundle,
)


def _write_story_input(project_dir):
    bundle = StoryInputBundle(
        project_bible=ProjectBible(
            title="深潮航迹",
            author="测试作者",
            genre="科幻",
            premise="追查失踪信号",
            synopsis="林渊沿着异常信号追查母亲去向。",
        ),
        world_bible=WorldBible(
            summary="白昼环与废弃港构成主要舞台。",
            locations=["白昼环控制室", "废弃港"],
            hard_constraints=["远程信号源不能直接等于当前物理位置"],
        ),
        characters=[],
        chapter_plans=[
            ChapterPlan(
                chapter_number=1,
                title="第一章",
                summary="林渊在白昼环控制室确认异常信号。",
                key_events=["确认信号真假"],
                location_ids=["location:白昼环控制室"],
                goal_lock="确认信号真假",
            ),
            ChapterPlan(
                chapter_number=2,
                title="第二章",
                summary="林渊前往废弃港继续追查。",
                key_events=["进入废弃港"],
                location_ids=["location:废弃港"],
                continuity_in="承接白昼环的异常信号",
                goal_lock="确认信号真假、进入废弃港",
            ),
        ],
        style_profile=StyleProfile(),
    )
    write_story_input_bundle(project_dir, bundle)


def test_build_story_graph_snapshot_extracts_scene_anchor_and_remote_signal_source(
    temp_project_dir,
):
    project_dir = temp_project_dir / "runtime" / "projects" / "深潮航迹_demo123"
    (project_dir / "chapters").mkdir(parents=True, exist_ok=True)
    (project_dir / "plot_summaries").mkdir(parents=True, exist_ok=True)
    _write_story_input(project_dir)
    (project_dir / "chapters" / "ch001_第一章.md").write_text(
        "# 第一章\n【场景】白昼环控制室\n林渊截获来自潮汐空间边界的求救信号，并决定继续核验。",
        encoding="utf-8",
    )

    snapshot = build_story_graph_snapshot(project_dir, chapter_number=1, persist=False)

    assert snapshot["state"]["scene_anchor"] == "白昼环控制室"
    assert snapshot["state"]["physical_location"] == "白昼环控制室"
    assert snapshot["state"]["remote_signal_sources"] == ["潮汐空间边界"]
    assert any(edge["type"] == "REMOTE_SIGNAL_SOURCE" for edge in snapshot["edges"])


def test_build_chapter_graph_packet_uses_previous_snapshot_for_opening_bridge(
    temp_project_dir,
):
    project_dir = temp_project_dir / "runtime" / "projects" / "深潮航迹_demo123"
    (project_dir / "chapters").mkdir(parents=True, exist_ok=True)
    (project_dir / "plot_summaries").mkdir(parents=True, exist_ok=True)
    _write_story_input(project_dir)
    (project_dir / "chapters" / "ch001_第一章.md").write_text(
        "# 第一章\n【场景】白昼环控制室\n林渊在白昼环控制室确认了异常信号真假。",
        encoding="utf-8",
    )

    record_story_graph_after_save(
        project_dir=project_dir,
        project_id="demo123",
        chapter_number=1,
        context={"chapter_graph_packet": {}},
    )
    packet = build_chapter_graph_packet(project_dir, chapter_number=2)

    assert packet["previous_scene_anchor"] == "白昼环控制室"
    assert "白昼环控制室" in packet["opening_bridge_required"]
    assert "废弃港" in packet["opening_bridge_required"]


def test_build_chapter_graph_packet_derives_chapter_goal_and_success_evidence(
    temp_project_dir,
):
    project_dir = temp_project_dir / "runtime" / "projects" / "深潮航迹_demo123"
    (project_dir / "chapters").mkdir(parents=True, exist_ok=True)
    (project_dir / "plot_summaries").mkdir(parents=True, exist_ok=True)
    _write_story_input(project_dir)
    (project_dir / "chapters" / "ch001_第一章.md").write_text(
        "# 第一章\n【场景】白昼环控制室\n林渊在白昼环控制室确认了异常信号真假。",
        encoding="utf-8",
    )

    record_story_graph_after_save(
        project_dir=project_dir,
        project_id="demo123",
        chapter_number=1,
        context={"chapter_graph_packet": {}},
    )
    packet = build_chapter_graph_packet(project_dir, chapter_number=2)

    assert packet["chapter_goal"] == "进入废弃港"
    assert packet["required_bridge"]
    assert "进入废弃港" in packet["remaining_goal_subgoals"]
    assert any("进入废弃港" in item for item in packet["success_evidence"])


def test_derive_rebaseline_delta_does_not_complete_singleton_macro_goal_lock():
    snapshot = {
        "state": {
            "chapter_summary": "沈雁重返被封锁的北海冰穹城，在外围观察轨道电梯残骸。",
            "plot_key_points": [],
            "opening_excerpt": "沈雁站在北海冰穹城封锁区边缘。",
            "physical_location": "冰穹城",
        }
    }
    packet = {
        "goal_lock": "沈雁调查员沈雁重返被封锁的北海冰穹城",
        "goal_subgoals": ["沈雁调查员沈雁重返被封锁的北海冰穹城"],
        "target_destinations": ["冰穹城"],
    }

    delta = derive_rebaseline_delta(
        chapter_number=12,
        snapshot=snapshot,
        chapter_graph_packet=packet,
    )

    assert delta["destination_reached"] == ["冰穹城"]
    assert delta["completed_goal_subgoals"] == []


def test_build_chapter_graph_packet_ignores_stale_singleton_completion(
    temp_project_dir,
):
    project_dir = temp_project_dir / "runtime" / "projects" / "盐雪回声_demo123"
    (project_dir / "chapters").mkdir(parents=True, exist_ok=True)
    (project_dir / "plot_summaries").mkdir(parents=True, exist_ok=True)
    _write_story_input(project_dir)
    (project_dir / "chapters" / "ch001_第一章.md").write_text(
        "# 第一章\n【场景】白昼环控制室\n林渊在白昼环控制室确认了异常信号真假。",
        encoding="utf-8",
    )

    delta_root = project_dir / "story_graph" / "rebaseline"
    delta_root.mkdir(parents=True, exist_ok=True)
    (delta_root / "ch001_delta.json").write_text(
        """
        {
          "schema_version": "story_graph.rebaseline.v1",
          "chapter_number": 1,
          "goal_lock": "确认信号真假",
          "completed_goal_subgoals": ["确认信号真假"],
          "destination_reached": ["白昼环控制室"],
          "challenged_world_facts": [],
          "recommended_action": "rebaseline",
          "plan_stale": true
        }
        """.strip(),
        encoding="utf-8",
    )

    packet = build_chapter_graph_packet(project_dir, chapter_number=1)

    assert packet["completed_goal_subgoals"] == []
    assert packet["remaining_goal_subgoals"] == ["确认信号真假"]
