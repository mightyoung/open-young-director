"""Tests for novel orchestrator input compatibility."""

from young_writer.agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig


def test_orchestrator_extracts_characters_from_generation_packet():
    orchestrator = NovelOrchestrator(config=OrchestratorConfig(mode="STANDARD"))

    characters = orchestrator._extract_characters_from_context(
        {
            "generation_packet": {
                "characters": [
                    {
                        "name": "林渊",
                        "role": "空间语言学工程师",
                        "motivation": "追查失踪舰队真相",
                        "arc": "从旁观工程师变成公开真相的人",
                    }
                ]
            }
        }
    )

    assert characters["林渊"]["identity"] == "空间语言学工程师"
    assert characters["林渊"]["objective"] == "追查失踪舰队真相"


def test_orchestrator_extracts_minimal_characters_from_names():
    orchestrator = NovelOrchestrator(config=OrchestratorConfig(mode="STANDARD"))

    characters = orchestrator._extract_characters_from_context(
        {"character_names": ["林渊", "顾岚"]}
    )

    assert list(characters) == ["林渊", "顾岚"]
    assert characters["林渊"]["identity"] == "关键角色"


def test_orchestrator_resolves_location_and_time_from_generation_packet():
    orchestrator = NovelOrchestrator(config=OrchestratorConfig(mode="STANDARD"))
    context = {
        "generation_packet": {
            "world_bible": {"locations": ["白昼环监测站", "企业主控塔"]},
            "chapter_plan": {"location_ids": ["location:企业主控塔"]},
        },
        "generation_outline": "夜晚，林渊潜入企业主控塔夺取权限。",
    }

    assert orchestrator._resolve_location_from_context(context) == "企业主控塔"
    assert orchestrator._resolve_time_of_day_from_context(context) == "夜晚"


def test_orchestrator_returns_empty_cast_without_fantasy_fallbacks():
    orchestrator = NovelOrchestrator(config=OrchestratorConfig(mode="STANDARD"))

    characters = orchestrator._extract_characters_from_context({})

    assert characters == {}
