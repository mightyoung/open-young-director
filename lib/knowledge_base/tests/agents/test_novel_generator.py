"""Tests for NovelGeneratorAgent writing option prompt integration."""

import importlib.util
import json
from pathlib import Path
import sys
from textwrap import dedent
import types
from unittest.mock import MagicMock

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

AGENTS_DIR = ROOT_DIR / "young_writer" / "agents"
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
classify_hard_gate_issue_types = MODULE.classify_hard_gate_issue_types


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
    metadata_overrides: dict | None = None,
    plot_summary: dict | None = None,
) -> dict:
    generator = _make_generator()
    chapter = _make_chapter(chapter_number, f"第{chapter_number}章", current_content)
    if metadata_overrides:
        chapter.metadata.update(metadata_overrides)
    if plot_summary:
        chapter.plot_summary = dict(plot_summary)
    context = {
        "known_char_names": ["韩林", "柳如烟", "叶尘"],
        "previous_chapters": [{"content": dedent(previous_content).strip()}],
    }
    if context_overrides:
        context.update(context_overrides)
    return generator._check_consistency(chapter, previous_summary, context)


def _load_anti_drift_golden_cases() -> list[dict]:
    fixture_path = FIXTURES_DIR / "anti_drift_golden_cases.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _assert_transition_issue(report: dict, phrase: str) -> None:
    assert report["invalid"] is True
    assert "scene_or_timeline_disconnect" in report["issue_types"]
    assert any(phrase in issue for issue in report["blocking_issues"])


def test_hard_gate_classifier_keeps_unknown_issue_categories_warning_only():
    assert classify_hard_gate_issue_types(
        ["scene_or_timeline_disconnect", "new_unreviewed_issue_type"]
    ) == ["scene_or_timeline_disconnect"]


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
        assert "WRITER.md 宪法摘录" in prompt
        assert "banned_wording" in prompt

    def test_writer_rule_warnings_are_advisory_not_invalid(self):
        report = _run_consistency_check(
            previous_summary="韩林仍在宗门祖地。",
            previous_content="韩林守在祖地墙头。",
            current_content="第二章\n韩林突然非常愤怒，竟然倒吸一口冷气。随后他仍守在宗门祖地。",
            context_overrides={
                "chapter_intent_contract": {"goal_lock": "守住宗门祖地"},
            },
            metadata_overrides={"key_events": []},
        )

        assert report["invalid"] is False
        assert report["writer_rule_warnings"]
        assert any(
            warning["category"] == "banned_wording"
            for warning in report["writer_rule_warnings"]
        )

    def test_writer_rule_blocking_flag_stays_warning_only(self, monkeypatch):
        monkeypatch.setattr(
            MODULE,
            "check_writer_rules",
            lambda _content: [
                {
                    "category": "banned_wording",
                    "blocking": True,
                    "matches": ["突然"],
                    "guidance": "避免 AI 腔垫话。",
                }
            ],
        )

        report = _run_consistency_check(
            previous_summary="韩林仍在宗门祖地。",
            previous_content="韩林守在祖地墙头。",
            current_content="韩林突然稳住宗门祖地防线。",
            context_overrides={
                "chapter_intent_contract": {"goal_lock": "守住宗门祖地"},
            },
            metadata_overrides={"key_events": []},
        )

        assert report["invalid"] is False
        assert report["hard_gate_issue_types"] == []
        assert "writer_rule_blocking" not in report["issue_types"]
        assert report["writer_rule_warnings"][0]["blocking"] is True

    def test_generate_chapter_uses_project_seed_when_outline_file_missing(self, monkeypatch):
        generator = _make_generator()
        generator.config_manager.current_project.outline = "沈夜带着异质核心归来，调查母舰失踪真相。"
        generator.config_manager.current_project.world_setting = "空间城与深渊航道构成主要舞台。"
        generator.config_manager.current_project.character_intro = (
            "沈夜：前采矿舰领航员。顾砚青：工程师。闻岚：猎航队指挥官。"
        )

        monkeypatch.setattr(generator, "_get_chapter_outline", lambda chapter_number: None)

        captured = {}

        def _fake_generate_candidate(**kwargs):
            captured["outline"] = kwargs["outline"]
            captured["context"] = dict(kwargs["context"])
            return {"content": "沈夜回到边境空间城。" * 50, "orchestrator_result": None}

        monkeypatch.setattr(generator, "_generate_candidate", _fake_generate_candidate)
        monkeypatch.setattr(
            generator,
            "_check_consistency",
            lambda chapter, previous_summary, context: {"invalid": False, "issue_types": []},
        )

        chapter = generator.generate_chapter(
            chapter_number=1,
            context={
                "project_outline": generator.config_manager.current_project.outline,
                "world_setting": generator.config_manager.current_project.world_setting,
                "character_intro": generator.config_manager.current_project.character_intro,
                "genre": "科幻修真",
            },
            previous_summary="",
        )

        assert "沈夜带着异质核心归来" in captured["outline"]
        assert "空间城与深渊航道" in captured["outline"]
        assert "顾砚青" in captured["outline"]
        assert chapter.metadata["outline_summary"] == captured["outline"]

    def test_generate_content_falls_back_when_orchestrator_character_plan_is_empty(self):
        generator = _make_generator()
        generator.llm_client.generate.return_value = "沈夜回到边境空间城，开始调查异质核心来源。" * 80

        class _FakeOrchestrator:
            def orchestrate_chapter(self, **_kwargs):
                return {
                    "content": "沈夜带着异质核心归来。" * 120,
                    "plot_outline": {"beats": [{"beat_id": "beat_001"}]},
                    "cast": [],
                }

        generator.orchestrator = _FakeOrchestrator()

        result = generator._generate_content(
            chapter_number=1,
            title="第1章",
            outline="沈夜带着异质核心归来，在边境空间城落脚并查清核心来源",
            previous_summary="",
            context={
                "chapter_number": 1,
                "character_intro": "沈夜：主角。顾砚青：调查官。",
                "genre": "科幻修真",
            },
            retry_attempt=0,
        )

        assert result["orchestrator_result"] is None
        assert result["generation_trace"]["path"] == "direct_llm"
        assert (
            "character_plan_empty"
            in result["generation_trace"]["orchestrator"]["failure_reasons"]
        )
        assert generator._orchestrator_consecutive_failures == 1

    def test_generate_content_disables_orchestrator_after_consecutive_failures(self):
        generator = _make_generator()
        generator.llm_client.generate.return_value = "沈夜回到边境空间城，开始调查异质核心来源。" * 80

        calls = {"count": 0}

        class _FakeOrchestrator:
            def orchestrate_chapter(self, **_kwargs):
                calls["count"] += 1
                return {
                    "content": "沈夜带着异质核心归来。" * 40,
                    "plot_outline": {"beats": [{"beat_id": "beat_001"}]},
                    "cast": [],
                }

        generator.orchestrator = _FakeOrchestrator()
        base_kwargs = {
            "title": "第1章",
            "outline": "沈夜带着异质核心归来，在边境空间城落脚并查清核心来源",
            "previous_summary": "",
            "context": {
                "chapter_number": 1,
                "character_intro": "沈夜：主角。顾砚青：调查官。",
                "genre": "科幻修真",
            },
            "retry_attempt": 0,
        }

        generator._generate_content(chapter_number=1, **base_kwargs)
        second = generator._generate_content(chapter_number=2, **base_kwargs)
        third = generator._generate_content(chapter_number=3, **base_kwargs)

        assert calls["count"] == 2
        assert generator._orchestrator_disabled_for_run is True
        assert second["generation_trace"]["orchestrator"]["disabled_for_run"] is True
        assert third["generation_trace"]["orchestrator"]["failure_reasons"] == [
            "orchestrator_backoff_active"
        ]
        assert third["generation_trace"]["path"] == "direct_llm"

    def test_low_llm_semantic_advisory_does_not_invalidate_chapter(self):
        generator = _make_generator()
        generator.llm_client.generate.return_value = json.dumps(
            {
                "overall_score": 0.2,
                "mainline_progress": 0.2,
                "character_motivation": 0.4,
                "causal_continuity": 0.3,
                "style_drift": 0.7,
                "warnings": ["主线推进偏弱"],
            }
        )
        chapter = _make_chapter(
            2,
            "第二章",
            "韩林守在宗门祖地，继续调度伏兵封住山门。" * 20,
        )

        report = generator._check_consistency(
            chapter,
            "韩林抵达宗门祖地。",
            {
                "known_char_names": ["韩林"],
                "previous_chapters": [{"content": "韩林抵达宗门祖地。"}],
                "semantic_advisory_enabled": True,
            },
        )

        assert report["invalid"] is False
        advisory = report["semantic_review"]["llm_advisory"]
        assert advisory["status"] == "completed"
        assert advisory["overall_score"] == 0.2
        assert any(
            item["category"] == "semantic_advisory_low_score"
            for item in report["semantic_review"]["issues"]
        )

    def test_semantic_advisory_provider_error_is_warning_only(self):
        generator = _make_generator()
        generator.llm_client.generate.side_effect = RuntimeError("judge unavailable")
        chapter = _make_chapter(
            2,
            "第二章",
            "韩林守在宗门祖地，继续调度伏兵封住山门。" * 20,
        )

        report = generator._check_consistency(
            chapter,
            "韩林抵达宗门祖地。",
            {
                "known_char_names": ["韩林"],
                "previous_chapters": [{"content": "韩林抵达宗门祖地。"}],
                "semantic_advisory_enabled": True,
            },
        )

        assert report["invalid"] is False
        advisory = report["semantic_review"]["llm_advisory"]
        assert advisory["status"] == "error"
        assert advisory["warning_only"] is True

    @pytest.mark.parametrize("raw_payload", ['[]', '{"overall_score": "low"}'])
    def test_malformed_semantic_advisory_payload_is_warning_only(self, raw_payload):
        generator = _make_generator()
        generator.llm_client.generate.return_value = raw_payload
        chapter = _make_chapter(
            2,
            "第二章",
            "韩林守在宗门祖地，继续调度伏兵封住山门。" * 20,
        )

        report = generator._check_consistency(
            chapter,
            "韩林抵达宗门祖地。",
            {
                "known_char_names": ["韩林"],
                "previous_chapters": [{"content": "韩林抵达宗门祖地。"}],
                "semantic_advisory_enabled": True,
            },
        )

        assert report["invalid"] is False
        advisory = report["semantic_review"]["llm_advisory"]
        assert advisory["status"] == "error"
        assert advisory["warning_only"] is True

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

    def test_generate_content_keeps_goal_lock_visible_alongside_chapter_guidance(self):
        llm_client = MagicMock()
        llm_client.generate.return_value = "第五章\n" + (
            "韩林为了守住宗门祖地，在夜色中调度伏兵。 " * 80
        )
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=llm_client,
        )
        context = {
            "volume_guidance": "本章要先写夜袭祖地时的伏兵调度。",
            "volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "1",
            },
            "chapter_guidance": "补上夜袭开始前与上一章的战场承接。",
        }
        context["chapter_intent_contract"] = generator._build_chapter_intent_contract(
            outline="韩林在祖地夜巡时察觉伏兵。",
            context=context,
            chapter_guidance=context["chapter_guidance"],
        )

        generator._generate_content(
            chapter_number=5,
            title="第五章",
            outline="韩林在祖地夜巡时察觉伏兵。",
            previous_summary="上一章韩林决定死守祖地。",
            context=context,
        )

        prompt = llm_client.generate.call_args.args[0][0]["content"]

        assert "本章要先写夜袭祖地时的伏兵调度。" in prompt
        assert "当前主线目标锁: 守住宗门祖地" in prompt
        assert "本章执行合同" in prompt
        assert "本章附加指令定位: 只补充执行方式，不覆盖主线目标锁。" in prompt
        assert (
            "正文至少一个关键行动、冲突选择或结果必须直接推进目标锁：守住宗门祖地"
            in prompt
        )

    def test_generate_content_falls_back_by_default_when_llm_fails(self):
        llm_client = MagicMock()
        llm_client.generate.side_effect = RuntimeError("network unavailable")
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=llm_client,
        )

        result = generator._generate_content(
            chapter_number=1,
            title="第一章",
            outline="韩林开始守住宗门祖地。",
            previous_summary="",
            context={},
        )

        assert "自动生成内容占位符" in result["content"]

    def test_generate_content_can_require_real_llm(self):
        llm_client = MagicMock()
        llm_client.generate.side_effect = RuntimeError("network unavailable")
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=llm_client,
            allow_fallback=False,
        )

        with pytest.raises(RuntimeError, match="fallback disabled"):
            generator._generate_content(
                chapter_number=1,
                title="第一章",
                outline="韩林开始守住宗门祖地。",
                previous_summary="",
                context={},
            )

    def test_generate_chapter_rewrites_outline_before_generation_when_intent_drifts(
        self,
    ):
        llm_client = MagicMock()
        llm_client.generate.return_value = "第五章\n" + (
            "韩林为了守住宗门祖地，立刻调度伏兵并重整祖地防线。 " * 80
        )
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(),
            llm_client=llm_client,
        )
        generator._get_chapter_outline = MagicMock(
            return_value={
                "title": "第五章",
                "summary": "传说中的远古秘境忽然现世，众人议论新的修行体系。",
                "key_events": [],
            },
        )

        generator.generate_chapter(
            chapter_number=5,
            previous_summary="上一章韩林决定死守祖地。",
            context={
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "0",
                },
                "chapter_guidance": "补上夜袭前与上一章祖地危机的承接。",
            },
        )

        prompt = llm_client.generate.call_args.args[0][0]["content"]
        assert "原始大纲：传说中的远古秘境忽然现世" in prompt
        assert (
            "执行重写：开场先承接上一章局势，再把关键行动、冲突选择和结果对准主线目标锁：守住宗门祖地"
            in prompt
        )
        assert "附加指令仅作为补充执行方式，不得覆盖主线" in prompt


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
            "scene_or_timeline_disconnect" == issue for issue in report["issue_types"]
        )

    def test_consistency_report_marks_missing_events_as_invalid(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content="韩林来到演武场，却只是短暂交谈，完全没有爆发关键冲突。",
            word_count=30,
            metadata={
                "key_events": ["当众击败叶尘"],
                "outline_summary": "韩林反击叶尘",
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章韩林刚踏入演武场。",
            context={"previous_chapters": [{"character_states": {"韩林": "准备出手"}}]},
        )

        assert report["invalid"] is True
        assert "missing_key_events" in report["issue_types"]

    def test_consistency_report_accepts_keyword_covered_key_event(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content=(
                "沈夜按住胸前那枚异质核心，从失控的逃生舱里回到边境空间城。"
                "他刚落地就意识到，自己必须赶在追兵封锁前藏起这枚核心。"
            ),
            word_count=58,
            metadata={
                "key_events": ["沈夜带着异质核心归来"],
                "outline_summary": "沈夜带着异质核心回到边境空间城",
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章沈夜从深渊航道脱身。",
            context={
                "character_names": ["沈夜"],
                "previous_chapters": [{"character_states": {"沈夜": "脱离险境"}}],
            },
        )

        assert report["invalid"] is False
        assert "missing_key_events" not in report["issue_types"]

    def test_consistency_report_requires_event_action_anchor(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content=(
                "沈夜在检修通道里与顾砚青碰面，两人迅速交换了空间城外围的监测结果。"
                "他们提到必须尽快应对接下来的风暴，却没有真正爆发冲突。"
            ),
            word_count=61,
            metadata={
                "key_events": ["沈夜击败顾砚青"],
                "outline_summary": "沈夜与顾砚青正面对决",
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章沈夜追到了顾砚青的藏身点。",
            context={
                "character_names": ["沈夜", "顾砚青"],
                "previous_chapters": [{"character_states": {"沈夜": "准备出手"}}],
            },
        )

        assert report["invalid"] is True
        assert "missing_key_events" in report["issue_types"]

    def test_consistency_report_accepts_short_event_action_synonym(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
        chapter = MODULE.GeneratedChapter(
            number=2,
            title="第二章",
            content="沈夜回到边境空间城后，立刻封存了那枚异质核心。",
            word_count=26,
            metadata={
                "key_events": ["沈夜归来"],
                "outline_summary": "沈夜返回边境空间城",
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章沈夜刚脱离深渊航道。",
            context={
                "character_names": ["沈夜"],
                "previous_chapters": [{"character_states": {"沈夜": "脱离险境"}}],
            },
        )

        assert report["invalid"] is False
        assert "missing_key_events" not in report["issue_types"]

    def test_consistency_report_marks_world_fact_violation_as_invalid(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
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

    def test_consistency_report_flags_structure_drift_when_new_settings_exceed_budget(
        self,
    ):
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
        assert "structure_drift_watch" in [
            item["category"] for item in report["semantic_review"]["issues"]
        ]
        assert any("语义复核告警:" in item for item in report["recommendations"])

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

        assert (
            report["anti_drift_details"]["stage_gate_mode"]
            == "fixed_threshold_degraded"
        )

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
    def test_structure_drift_budget_parsing_is_deterministic(
        self, budget_value, expected_budget
    ):
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

    def test_structure_drift_records_missing_chapter_number_as_observable_skip_reason(
        self,
    ):
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
        assert (
            report["anti_drift_details"]["skipped_reason"] == "missing_chapter_number"
        )

    def test_structure_drift_uses_body_instead_of_outline_summary_for_goal_lock_alignment(
        self,
    ):
        generator = _make_generator()
        chapter = MODULE.GeneratedChapter(
            number=40,
            title="第四十章",
            content=dedent(
                """
                传说中的远古秘境忽然现世，引得满城修士震动。
                又一神秘体系在废墟深处显露轮廓，人人都在议论新的修行法则。
                韩林却只是站在原地听他们议论，没有再提守住宗门祖地这件事。
                """
            ).strip(),
            word_count=120,
            metadata={
                "key_events": [],
                "outline_summary": "韩林为了守住宗门祖地继续推进主线。",
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章韩林立誓守住宗门祖地。",
            context={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                },
                "previous_chapters": [{"content": "韩林立誓守住宗门祖地。"}],
            },
        )

        assert report["invalid"] is True
        assert "structure_drift_risk" in report["issue_types"]

    def test_structure_drift_uses_configurable_stage_gate_ratio(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林立誓守住宗门祖地。",
            previous_content="韩林立誓守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世。
            又一神秘体系在废墟深处显露轮廓。
            韩林没有说明这些新设定如何帮助守住宗门祖地。
            """,
            chapter_number=20,
            context_overrides={
                "chapter_number": 20,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                    "anti_drift_start_ratio": "0.3",
                },
            },
        )

        assert report["invalid"] is True
        assert "structure_drift_risk" in report["issue_types"]
        assert report["anti_drift_details"]["anti_drift_start_ratio"] == 0.3

    def test_structure_drift_uses_configurable_min_chapter_when_total_missing(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林立誓守住宗门祖地。",
            previous_content="韩林立誓守住宗门祖地。",
            current_content="""
            传说中的远古秘境忽然现世。
            又一神秘体系在废墟深处显露轮廓。
            韩林没有说明这些新设定如何帮助守住宗门祖地。
            """,
            chapter_number=12,
            context_overrides={
                "chapter_number": 12,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "new_setting_budget": "1",
                    "anti_drift_min_chapter": "10",
                },
            },
        )

        assert report["invalid"] is True
        assert (
            report["anti_drift_details"]["stage_gate_mode"]
            == "fixed_threshold_degraded"
        )
        assert report["anti_drift_details"]["anti_drift_min_chapter"] == 10

    def test_goal_lock_false_inheritance_can_be_warning_only(self):
        report = _run_consistency_check(
            previous_summary="上一章韩林决定死守祖地并立刻调度伏兵。",
            previous_content="韩林决定死守祖地并立刻调度伏兵。",
            current_content="""
            韩林转身与众人讨论宴席安排。
            他把整章篇幅都耗在无关紧要的宴席安排里。
            """,
            chapter_number=40,
            plot_summary={"l2_brief_summary": "韩林为了守住宗门祖地继续推进防线。"},
            context_overrides={
                "chapter_number": 40,
                "total_chapters": 60,
                "volume_guidance_payload": {
                    "goal_lock": "守住宗门祖地",
                    "goal_lock_false_inheritance_mode": "warn",
                },
            },
        )

        assert report["invalid"] is False
        assert "goal_lock_false_inheritance" not in report["issue_types"]
        assert any("目标锁假继承" in item for item in report["warning_issues"])
        assert (
            report["anti_drift_details"]["goal_lock_false_inheritance_mode"] == "warn"
        )

    def test_consistency_report_builds_structured_rewrite_plan_for_goal_lock_false_inheritance(
        self,
    ):
        generator = _make_generator()
        context = {
            "chapter_number": 40,
            "total_chapters": 60,
            "volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "1",
            },
        }
        context["chapter_intent_contract"] = generator._build_chapter_intent_contract(
            outline="韩林必须调度伏兵守住祖地。",
            context=context,
            chapter_guidance="补上夜袭前的战场承接。",
        )
        context["chapter_intent_check"] = generator._check_chapter_intent(
            outline="韩林必须调度伏兵守住祖地。",
            context=context,
        )
        chapter = MODULE.GeneratedChapter(
            number=40,
            title="第四十章",
            content=dedent(
                """
                韩林只是想起守住宗门祖地，却只是站在祖地墙头观望众人慌乱。
                他嘴上说不能退，却把整章篇幅都耗在无关紧要的闲谈里。
                """
            ).strip(),
            word_count=80,
            metadata={"key_events": [], "outline_summary": ""},
            plot_summary={"l2_brief_summary": "韩林为了守住宗门祖地继续推进防线。"},
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章韩林决定死守祖地并立刻调度伏兵。",
            context=context,
        )

        assert report["invalid"] is True
        assert "goal_lock_false_inheritance" in report["issue_types"]
        assert report["chapter_intent_contract"]["goal_lock"] == "守住宗门祖地"
        assert "chapter_intent_rewrite_applied" not in [
            item["category"] for item in report["semantic_review"]["issues"]
        ]
        assert report["rewrite_plan"]["issue_types"] == ["goal_lock_false_inheritance"]
        assert report["rewrite_plan"]["schema_version"] == "rewrite_plan.v2"
        assert report["rewrite_plan"]["strategy"] == "targeted_patch"
        assert any(
            "重写时围绕目标锁重组正文推进链：守住宗门祖地" in item
            for item in report["rewrite_plan"]["fixes"]
        )
        assert any(
            item["action"] == "rebuild_goal_lock_chain"
            and item["target"] == "goal_lock_progression"
            and "守住宗门祖地" in item["instruction"]
            for item in report["rewrite_plan"]["operations"]
        )
        assert report["chapter_intent_check"]["passed"] is True
        assert "【本次修复】" in report["rewrite_guidance"]
        assert "【验收条件】" in report["rewrite_guidance"]

    def test_consistency_report_builds_structured_rewrite_plan_for_smoothness_failures(
        self,
    ):
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

        assert report["invalid"] is True
        assert report["rewrite_plan"]["issue_types"] == ["scene_or_timeline_disconnect"]
        assert report["rewrite_plan"]["issue_categories"] == ["时间跳跃无锚点"]
        assert (
            "交代时间跨度后的状态变化、缺失时段影响或切换原因。"
            in report["rewrite_plan"]["fixes"]
        )
        assert (
            "若发生时间跳跃，正文必须解释时间跨度带来的状态变化。"
            in report["rewrite_plan"]["success_criteria"]
        )
        assert any(
            item["action"] == "anchor_time_jump" and item["target"] == "time_transition"
            for item in report["rewrite_plan"]["operations"]
        )
        assert "【本次修复】" in report["rewrite_guidance"]
        assert "时间跨度带来的状态变化" in report["rewrite_guidance"]

    def test_chapter_intent_check_rewrites_unaligned_outline_before_generation(self):
        generator = _make_generator()
        context = {
            "volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "0",
            },
            "chapter_guidance": "补上祖地危机与上一章的承接。",
        }
        context["chapter_intent_contract"] = generator._build_chapter_intent_contract(
            outline="传说中的远古秘境忽然现世，众人议论新的修行体系。",
            context=context,
            chapter_guidance=context["chapter_guidance"],
        )

        result = generator._check_chapter_intent(
            outline="传说中的远古秘境忽然现世，众人议论新的修行体系。",
            context=context,
        )

        assert result["passed"] is False
        assert "goal_lock_missing_from_plan" in result["issues"]
        assert "unbridged_new_setting_in_plan" in result["issues"]
        assert "守住宗门祖地" in result["rewritten_outline"]
        assert "传说中的远古秘境忽然现世" in result["rewritten_outline"]

    def test_extract_goal_lock_prefers_packet_plan_over_runtime_payload(self):
        generator = _make_generator()
        context = {
            "goal_lock_resolution": {
                "effective_goal_lock": "守住空间城",
                "effective_source": "chapter_plan.goal_lock",
            },
            "volume_guidance_payload": {"goal_lock": "追查异质核心"},
            "generation_packet": {
                "chapter_plan": {"goal_lock": "守住空间城"},
                "runtime_overrides": {
                    "volume_guidance_payload": {"goal_lock": "追查异质核心"}
                },
            },
        }

        assert generator._extract_goal_lock(context) == "守住空间城"

    def test_consistency_report_adds_warning_only_semantic_review_when_precheck_rewrites_outline(
        self,
    ):
        generator = _make_generator()
        context = {
            "chapter_number": 12,
            "total_chapters": 60,
            "volume_guidance_payload": {
                "goal_lock": "守住宗门祖地",
                "new_setting_budget": "0",
            },
            "chapter_guidance": "补上祖地危机与上一章的承接。",
        }
        context["chapter_intent_contract"] = generator._build_chapter_intent_contract(
            outline="传说中的远古秘境忽然现世，众人议论新的修行体系。",
            context=context,
            chapter_guidance=context["chapter_guidance"],
        )
        context["chapter_intent_check"] = generator._check_chapter_intent(
            outline="传说中的远古秘境忽然现世，众人议论新的修行体系。",
            context=context,
        )
        chapter = MODULE.GeneratedChapter(
            number=12,
            title="第十二章",
            content=dedent(
                """
                韩林为了守住宗门祖地，连夜调度伏兵封住山门缺口。
                他当场改写守阵次序，让祖地防线重新稳定下来。
                """
            ).strip(),
            word_count=80,
            metadata={"key_events": [], "outline_summary": ""},
            plot_summary={"l2_brief_summary": "韩林为了守住宗门祖地重整防线。"},
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章韩林决定死守祖地并立刻调度伏兵。",
            context=context,
        )

        assert report["invalid"] is False
        assert "chapter_intent_rewrite_applied" in [
            item["category"] for item in report["semantic_review"]["issues"]
        ]
        assert any(
            "生成前意图检查已重写章节大纲" in item for item in report["warning_issues"]
        )


@pytest.mark.parametrize(
    "case",
    _load_anti_drift_golden_cases(),
    ids=lambda case: case["name"],
)
def test_consistency_report_matches_anti_drift_golden_cases(case):
    report = _run_consistency_check(
        previous_summary=case["previous_summary"],
        previous_content=case["previous_content"],
        current_content=case["current_content"],
        chapter_number=case["chapter_number"],
        context_overrides=case.get("context_overrides"),
        metadata_overrides=case.get("metadata_overrides"),
        plot_summary=case.get("plot_summary"),
    )

    assert report["invalid"] is case["expected_invalid"]
    assert report["issue_types"] == case["expected_issue_types"]
    expected_warning_categories = case.get("expected_warning_categories", [])
    if expected_warning_categories:
        warning_categories = [
            item.get("category")
            for item in report.get("semantic_review", {}).get("issues", [])
            if isinstance(item, dict)
        ]
        for category in expected_warning_categories:
            assert category in warning_categories
    expected_actions = case.get("expected_rewrite_actions", [])
    if expected_actions:
        rewrite_actions = [
            item.get("action")
            for item in report.get("rewrite_plan", {}).get("operations", [])
        ]
        for action in expected_actions:
            assert action in rewrite_actions
