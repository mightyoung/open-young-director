"""Tests for NovelGeneratorAgent writing option prompt integration."""

import importlib.util
from pathlib import Path
import sys
from textwrap import dedent
import types
from unittest.mock import MagicMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

AGENTS_DIR = ROOT_DIR / "agents"
PACKAGE = types.ModuleType("agents")
PACKAGE.__path__ = [str(AGENTS_DIR)]
sys.modules.setdefault("agents", PACKAGE)

SPEC = importlib.util.spec_from_file_location(
    "agents.novel_generator",
    AGENTS_DIR / "novel_generator.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

NovelGeneratorAgent = MODULE.NovelGeneratorAgent


class DummyConfigManager:
    """Minimal config manager for prompt tests."""

    def __init__(self):
        self.current_project = MagicMock(title="测试项目", genre="玄幻")
        self.generation = MagicMock(chapter_word_count=3000)


def _make_generator() -> NovelGeneratorAgent:
    return NovelGeneratorAgent(
        config_manager=DummyConfigManager(),
        llm_client=MagicMock(),
    )


def _make_chapter(number: int, title: str, content: str) -> MODULE.GeneratedChapter:
    return MODULE.GeneratedChapter(
        number=number,
        title=title,
        content=dedent(content).strip(),
        word_count=len(content),
        metadata={"key_events": [], "outline_summary": ""},
        consistency_report={"character_states": {"韩林": "韩林仍带着上一章的伤势"}},
    )


def _run_consistency_check(
    *,
    previous_summary: str,
    previous_content: str,
    current_content: str,
    chapter_number: int = 2,
    context_overrides: dict | None = None,
) -> dict:
    generator = _make_generator()
    chapter = _make_chapter(chapter_number, f"第{chapter_number}章", current_content)
    context = {
        "known_char_names": ["韩林", "柳如烟", "叶尘"],
        "previous_chapters": [{"content": dedent(previous_content).strip()}],
    }
    if context_overrides:
        context.update(context_overrides)
    return generator._check_consistency(chapter, previous_summary, context)


def _assert_transition_issue(report: dict, phrase: str) -> None:
    assert report["invalid"] is True
    assert "scene_or_timeline_disconnect" in report["issue_types"]
    assert any(phrase in issue for issue in report["blocking_issues"])


class TestNovelGeneratorWritingOptions:
    """Test writing option prompt expansion in the main generation path."""

    def test_generation_prompt_includes_writing_options(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=MagicMock(),
        )

        prompt = generator._build_generation_prompt(
            chapter_number=5,
            title="第五章",
            outline="韩林在演武场反击对手并埋下后续暗线。",
            previous_summary="上一章韩林受辱。",
            genre="玄幻",
            target_word_count=3200,
            writing_options={
                "style": "dramatic",
                "style_preset": "epic_rebel",
                "perspective": "third_limited",
                "narrative_mode": "multi_line_foreshadowing",
                "pace": "fast",
                "dialogue_density": "high",
                "prose_style": "concise_forceful",
                "world_building_density": "dense",
                "emotion_intensity": "high",
                "combat_style": "epic",
                "hook_strength": "strong",
            },
        )

        assert "风格参数" in prompt
        assert "风格预设: epic_rebel" in prompt
        assert "叙事写法: multi_line_foreshadowing" in prompt
        assert "对白密度: high" in prompt
        assert "战斗写法: epic" in prompt
        assert "逆天写法" in prompt

    def test_generation_prompt_includes_volume_guidance(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=MagicMock(),
        )

        prompt = generator._build_generation_prompt(
            chapter_number=12,
            title="新卷开篇",
            outline="主角进入新卷主线。",
            previous_summary="上一卷在大战后收束。",
            genre="玄幻",
            volume_guidance=(
                "- 必须回收的伏笔/问题: 下一卷必须尽快回收师门裂痕\n"
                "- 需要强化的人物关系: 强化主角的主动性"
            ),
        )

        assert "本卷修订指令" in prompt
        assert "必须回收的伏笔/问题" in prompt
        assert "下一卷必须尽快回收师门裂痕" in prompt

class TestNovelGeneratorSmoothnessConsistency:
    def test_consistency_report_flags_location_jump_without_bridge(self):
        report = _run_consistency_check(
            previous_summary="上一章结尾，韩林刚在青石巷甩开追兵，准备找地方藏身。",
            previous_content="""
            夜色沉沉，韩林扶着墙喘息，确认追兵没有追进青石巷深处。
            他还没来得及离开这条窄巷，耳边全是急促的脚步声。
            """,
            current_content="""
            晨雾笼罩皇城书院。
            韩林已经坐在演武场看台上，仿佛昨夜的追杀从未发生。
            """,
        )

        _assert_transition_issue(report, "地点跳切无承接")

    def test_consistency_report_flags_time_jump_without_anchor(self):
        report = _run_consistency_check(
            previous_summary="上一章深夜，韩林刚在客栈拿到密信，还没来得及拆开。",
            previous_content="""
            深夜的客栈里只剩一盏孤灯。
            韩林捏着刚拿到的密信，警惕地听着门外的动静。
            """,
            current_content="""
            三天后，韩林已经站在山门前。
            他收起皱巴巴的密信，像是中间什么都没有发生。
            """,
        )

        _assert_transition_issue(report, "时间跳跃无锚点")

    def test_consistency_report_flags_unresolved_previous_consequence(self):
        report = _run_consistency_check(
            previous_summary="上一章结尾，爆炸将叶尘炸成重伤，柳如烟也在废墟中昏迷不醒。",
            previous_content="""
            爆炸余波掀翻整条街，叶尘重伤倒地，柳如烟在烟尘里失去意识。
            韩林拖着两人躲进废墟，连呼吸都带着血腥气。
            """,
            current_content="""
            清晨的集市热闹非凡。
            韩林慢悠悠地挑着糕点，还盘算着今晚去哪里听戏。
            """,
        )

        _assert_transition_issue(report, "上一章后果未被承接")

    def test_consistency_report_flags_superficially_smooth_but_causally_broken_opening(
        self,
    ):
        report = _run_consistency_check(
            previous_summary="上一章结尾，韩林在爆炸后背着昏迷的柳如烟逃离废墟，追兵仍在搜捕他们。",
            previous_content="""
            爆炸震塌了半条长街，柳如烟昏迷在韩林背上，追兵的火把已经逼近巷口。
            韩林只能带着她仓皇逃命，根本没有停下来的余地。
            """,
            current_content="""
            午后的王府花园里风平浪静，韩林对着池水整理衣袖，准备从容赴宴。
            他像是从来没有经历过昨夜那场追杀，也不必解释柳如烟去了哪里。
            """,
        )

        _assert_transition_issue(report, "表面流畅但因果断裂")

    def test_consistency_report_allows_location_change_with_explicit_bridge(self):
        report = _run_consistency_check(
            previous_summary="上一章结尾，韩林刚在青石巷甩开追兵。",
            previous_content="""
            韩林藏在青石巷尽头，确认追兵已经被夜色甩开。
            他抬头看向皇城书院的方向，知道自己必须马上转移。
            """,
            current_content="""
            离开青石巷后，韩林连夜赶往皇城书院。
            等他抵达演武场时，天色刚亮，掌心的血迹也还没有完全干透。
            """,
        )

        assert report["invalid"] is False
        assert not any("地点跳切无承接" in issue for issue in report["blocking_issues"])

    def test_consistency_report_allows_suspenseful_opening_with_quick_backfill(
        self,
    ):
        report = _run_consistency_check(
            previous_summary="上一章结尾，韩林带着柳如烟从废墟中逃出，准备天亮前潜入北城药坊。",
            previous_content="""
            废墟里的火光还没熄灭，韩林背着昏迷的柳如烟冲进北城小巷。
            他只剩下一个念头：天亮前找到药坊，把人藏起来。
            """,
            current_content="""
            门外忽然传来急促的敲门声，震得窗纸簌簌发颤。
            韩林按住腰间伤口，先把昏迷的柳如烟藏到药柜后，才示意老药师开门。
            这里仍是北城药坊，天还没亮，昨夜废墟里的焦糊味仿佛还黏在他的衣袖上。
            """,
        )

        assert report["invalid"] is False
        assert not any(
            "scene_or_timeline_disconnect" == issue
            for issue in report["issue_types"]
        )

    def test_consistency_report_marks_missing_events_as_invalid(self):
        generator = NovelGeneratorAgent(config_manager=DummyConfigManager(), llm_client=MagicMock())
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content="韩林来到演武场，却只是短暂交谈，完全没有爆发关键冲突。",
            word_count=30,
            metadata={"key_events": ["当众击败叶尘"], "outline_summary": "韩林反击叶尘"},
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章韩林刚踏入演武场。",
            context={"previous_chapters": [{"character_states": {"韩林": "准备出手"}}]},
        )

        assert report["invalid"] is True
        assert "missing_key_events" in report["issue_types"]

    def test_consistency_report_marks_world_fact_violation_as_invalid(self):
        generator = NovelGeneratorAgent(config_manager=DummyConfigManager(), llm_client=MagicMock())
        chapter = MODULE.GeneratedChapter(
            number=8,
            title="第八章",
            content="柳如烟重新现身，对着众人高声说道自己早已看穿这一切。",
            word_count=32,
            metadata={"key_events": [], "outline_summary": ""},
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章柳如烟身亡，婚书也碎裂消散。",
            context={"previous_chapters": []},
        )

        assert report["invalid"] is True
        assert "world_fact_violation" in report["issue_types"]

    def test_consistency_report_flags_structure_drift_when_new_settings_exceed_budget(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林立誓守住宗门祖地。",
            previous_content="""
            韩林确认祖地屏障正在崩裂，他唯一的目标就是守住宗门祖地。
            """,
            current_content="""
            传说中的远古秘境忽然现世，引得满城修士震动。
            又一神秘体系在废墟深处显露轮廓，人人都在议论新的修行法则。
            韩林却只是站在原地听他们议论，没有再提守住宗门祖地这件事。
            """,
            chapter_number=40,
            context_overrides={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
            },
        )

        assert report["invalid"] is True
        assert "structure_drift_risk" in report["issue_types"]
        assert any("结构漂移风险[" in issue for issue in report["blocking_issues"])
        assert report["anti_drift_details"]["intro_count"] == 2

    def test_consistency_report_allows_bridged_new_setting_within_budget(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林决定守住宗门祖地。",
            previous_content="""
            宗门祖地的封印摇摇欲坠，韩林必须守住这里。
            """,
            current_content="""
            传说中的远古秘境忽然现世。
            韩林为了守住宗门祖地，必须先夺下秘境里的阵眼，因此立刻带人赶去。
            """,
            chapter_number=38,
            context_overrides={
                "chapter_number": 38,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
            },
        )

        assert report["invalid"] is False
        assert "structure_drift_risk" not in report["issue_types"]

    def test_consistency_report_skips_structure_drift_in_early_stage(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林要守住宗门祖地。",
            previous_content="韩林还在为守住宗门祖地做准备。",
            current_content="""
            传说中的远古秘境忽然现世。
            又一神秘体系在废墟深处显露轮廓。
            """,
            chapter_number=10,
            context_overrides={
                "chapter_number": 10,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
            },
        )

        assert report["invalid"] is False
        assert report["anti_drift_details"]["skipped_reason"] == "not_mid_late_stage"

    def test_consistency_report_skips_structure_drift_without_goal_lock(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林在祖地布阵。",
            previous_content="韩林在祖地布阵。",
            current_content="传说中的远古秘境忽然现世。",
            chapter_number=35,
            context_overrides={"chapter_number": 35, "total_chapters": 60},
        )

        assert report["invalid"] is False
        assert report["anti_drift_details"]["skipped_reason"] == "missing_goal_lock"

    def test_consistency_report_uses_fixed_threshold_when_total_chapters_missing(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林决定守住宗门祖地。",
            previous_content="韩林决定守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世。
            又一神秘体系在废墟深处显露轮廓。
            """,
            chapter_number=35,
            context_overrides={
                "chapter_number": 35,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
            },
        )

        assert report["anti_drift_details"]["stage_gate_mode"] == "fixed_threshold_degraded"

    def test_consistency_report_deduplicates_repeated_new_setting_intro_fragments(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林决定守住宗门祖地。",
            previous_content="韩林决定守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世，引得四方震动。
            传说中的远古秘境忽然现世，引得四方震动。
            韩林站在原地，没有再提守住宗门祖地。
            """,
            chapter_number=40,
            context_overrides={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "0",
                },
            },
        )

        assert report["anti_drift_details"]["intro_count"] == 1
        assert len(report["anti_drift_details"]["counted_intro_fragments"]) == 1

    def test_structure_drift_requires_goal_term_and_connector_to_count_as_bridge(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林立誓守住宗门祖地。",
            previous_content="韩林立誓守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世，引得满城修士震动。
            韩林想起守住宗门祖地，却不解释缘由，也不说明接下来要做什么。
            又一神秘体系在废墟深处显露轮廓，人人都在议论新的修行法则。
            """,
            chapter_number=40,
            context_overrides={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
            },
        )

        assert report["invalid"] is True
        assert "structure_drift_risk" in report["issue_types"]
        assert any("结构漂移风险[" in issue for issue in report["blocking_issues"])

    @pytest.mark.parametrize(
        "budget_value,expected_budget",
        [
            ("not-a-number", 1),
            ("-2", 0),
            (None, 1),
        ],
    )
    def test_structure_drift_budget_parsing_is_deterministic(self, budget_value, expected_budget):
        payload = {"goal_lock": "守住宗门祖地"}
        if budget_value is not None:
            payload["new_setting_budget"] = budget_value
        report = _run_consistency_check(
            previous_summary="上一章韩林立誓守住宗门祖地。",
            previous_content="韩林立誓守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世，引得满城修士震动。
            又一神秘体系在废墟深处显露轮廓，人人都在议论新的修行法则。
            韩林却只是站在原地听他们议论，没有再提守住宗门祖地这件事。
            """,
            chapter_number=40,
            context_overrides={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": payload,
            },
        )

        assert report["anti_drift_details"]["budget"] == expected_budget

    def test_structure_drift_records_missing_chapter_number_as_observable_skip_reason(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林决定守住宗门祖地。",
            previous_content="韩林决定守住宗门祖地。",
            current_content="传说中的远古秘境忽然现世。",
            chapter_number=40,
            context_overrides={
                "chapter_number": 0,
                "total_chapters": 60,
                "volume_guidance_payload": {"goal_lock": "守住宗门祖地"},
            },
        )

        assert report["invalid"] is False
        assert report["anti_drift_details"]["skipped_reason"] == "missing_chapter_number"
