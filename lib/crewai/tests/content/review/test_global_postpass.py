"""Tests for the global post-pass consistency checks."""

from crewai.content.memory.continuity_tracker import ContinuityTracker
from crewai.content.memory.memory_types import Event
from crewai.content.review.global_postpass import GlobalPostPass


def _make_chapter(chapter_num: int, content: str, characters: list[str]) -> dict:
    return {
        "chapter_num": chapter_num,
        "content": content,
        "character_appearances": characters,
    }


def test_location_timeline_flags_unsupported_jump() -> None:
    tracker = ContinuityTracker()
    tracker.update_entity_state("char1", {"location": "京城"})
    tracker.add_event(
        Event(
            id="e1",
            timestamp="第1章",
            description="张三在京城",
            involved_entities=["char1"],
            chapter=1,
        )
    )
    tracker.update_entity_state("char1", {"location": "边境"})
    tracker.add_event(
        Event(
            id="e2",
            timestamp="第2章",
            description="张三忽然出现在边境",
            involved_entities=["char1"],
            chapter=2,
        )
    )

    postpass = GlobalPostPass(continuity_tracker=tracker)
    report = postpass.run(
        chapters=[
            _make_chapter(1, "张三站在京城的城楼上，俯瞰着远处的街巷。", ["char1"]),
            _make_chapter(2, "张三下一刻便站在边境，四周一片风平浪静。", ["char1"]),
        ],
        world_data={},
    )

    assert len(report.location_timeline_issues) == 1
    assert report.location_timeline_issues[0]["chapter"] == 2
    assert "突然转移" in report.location_timeline_issues[0]["description"]


def test_location_timeline_allows_explicit_transfer() -> None:
    tracker = ContinuityTracker()
    tracker.update_entity_state("char1", {"location": "京城"})
    tracker.add_event(
        Event(
            id="e1",
            timestamp="第1章",
            description="张三在京城",
            involved_entities=["char1"],
            chapter=1,
        )
    )
    tracker.update_entity_state("char1", {"location": "边境"})
    tracker.add_event(
        Event(
            id="e2",
            timestamp="第2章",
            description="张三前往边境执行任务",
            involved_entities=["char1"],
            chapter=2,
        )
    )

    postpass = GlobalPostPass(continuity_tracker=tracker)
    report = postpass.run(
        chapters=[
            _make_chapter(1, "张三在京城准备出发。", ["char1"]),
            _make_chapter(2, "张三前往边境执行任务。", ["char1"]),
        ],
        world_data={},
    )

    assert report.location_timeline_issues == []
