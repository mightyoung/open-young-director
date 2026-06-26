"""Tests unified prompt-facing memory context arbitration."""

from young_writer.services.context_memory import (
    PACKET_SCHEMA_VERSION,
    build_memory_context_packet,
    render_memory_context_packet_summary,
)


def test_memory_context_suppresses_longform_fact_covered_by_narrative_state():
    packet = build_memory_context_packet(
        chapter_number=4,
        narrative_state_packet={
            "recent_key_events": ["进入废弃港"],
            "unresolved_goals": ["找到信号源"],
        },
        narrative_state_summary="近期关键事件: 进入废弃港",
        longform_memory=[
            {
                "chapter_number": 3,
                "memory_type": "plot_anchor",
                "summary": "进入废弃港",
                "content_excerpt": "进入废弃港",
                "artifact_path": "chapters/ch003.md",
                "artifact_checksum": "abc123",
            },
            {
                "chapter_number": 2,
                "memory_type": "plot_anchor",
                "summary": "发现暗门",
                "content_excerpt": "发现暗门",
                "artifact_path": "chapters/ch002.md",
                "artifact_checksum": "def456",
            },
        ],
    )

    assert packet["schema_version"] == PACKET_SCHEMA_VERSION
    assert [item["summary"] for item in packet["longform_evidence"]] == ["发现暗门"]
    assert [item["summary"] for item in packet["suppressed_longform_duplicates"]] == [
        "进入废弃港"
    ]

    rendered = render_memory_context_packet_summary(packet)
    assert "持久叙事状态:" in rendered
    assert "长程记忆证据:" in rendered
    assert "发现暗门" in rendered
    assert rendered.count("进入废弃港") == 1
    assert "长程记忆重复证据已合并: 第3章 plot_anchor" in rendered


def test_memory_context_keeps_longform_when_no_current_layer_covers_it():
    packet = build_memory_context_packet(
        chapter_number=5,
        chapter_graph_summary="开篇补桥: 从控制室转入外城。",
        narrative_state_summary="当前位置: 外城门口",
        longform_memory=[
            {
                "chapter_number": 1,
                "memory_type": "chapter_summary",
                "summary": "主角曾把钥匙交给阿宁",
            }
        ],
    )

    rendered = render_memory_context_packet_summary(packet)

    assert packet["suppressed_longform_duplicates"] == []
    assert "主角曾把钥匙交给阿宁" in rendered
