"""Tests for OutlineEvaluator."""

from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator
from crewai.content.novel.novel_types import ReviewCheckResult


def _complete_world_data() -> dict:
    return {
        "name": "青云界",
        "description": "一个宗门林立、灵脉交错的修真世界。",
        "world_constraints": ["灵气有限", "跨界传送代价高"],
        "geography": [
            {"name": "青云城", "description": "主城"},
            {"name": "天剑山", "description": "剑修圣地"},
        ],
        "factions": [
            {"name": "青云宗", "description": "守护主城的宗门"},
            {"name": "天魔教", "description": "暗中渗透的敌对势力"},
        ],
        "power_system": {
            "name": "灵阶体系",
            "levels": ["练气", "筑基", "金丹", "元婴"],
        },
    }


def _complete_plot_data() -> dict:
    return {
        "plot_arcs": [
            {
                "strand_type": "main",
                "description": "主角追查灵脉异常",
                "main_events": ["调查", "探查", "追踪", "对峙", "潜入", "决战"],
            },
            {
                "strand_type": "romance",
                "description": "主角与同伴感情线",
                "main_events": ["相识", "和解"],
            },
        ],
        "turning_points": ["入宗", "下山", "决战"],
        "themes": ["成长", "守护", "真相"],
        "main_characters": ["主角", "同伴", "反派"],
        "volumes": [
            {
                "title": "第一卷",
                "start_chapter": 1,
                "end_chapter": 20,
                "chapters_summary": ["开局", "入局"],
            },
            {
                "title": "第二卷",
                "start_chapter": 21,
                "end_chapter": 40,
                "chapters_summary": ["升级", "交锋"],
            },
        ],
        "foreshadowing_strands": [
            {
                "name": "黑幕伏笔",
                "strand_type": "constellation",
                "setup_chapter": 3,
                "payoff_chapter": 12,
            }
        ],
    }


def test_outline_evaluator_check_returns_review_result() -> None:
    evaluator = OutlineEvaluator(llm=None, verbose=False)

    result = evaluator.check(_complete_world_data(), _complete_plot_data(), context={})

    assert isinstance(result, ReviewCheckResult)
    assert result.check_type == "outline"
    assert result.passed is True
    assert result.score >= 7.0
    assert result.issues == []
    assert hasattr(result, "dimensions")


def test_outline_evaluator_fails_when_data_is_missing() -> None:
    evaluator = OutlineEvaluator(llm=None, verbose=False)

    result = evaluator.evaluate({}, {}, context=None)

    assert result.passed is False
    assert result.score < 7.0
    assert any("世界观" in issue for issue in result.issues)
    assert any("情节" in issue for issue in result.issues)
