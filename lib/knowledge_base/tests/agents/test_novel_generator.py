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


def test_goal_terms_extracts_compact_action_anchors():
    generator = _make_generator()

    terms = generator._goal_terms("林渊追查失踪舰队回声真相")

    assert "林渊" in terms
    assert "追查" in terms
    assert any(term in terms for term in ("失踪舰队回声真相", "回声真相"))


def test_goal_terms_extracts_terminal_rescue_anchors():
    generator = _make_generator()

    terms = generator._goal_terms("林渊救回母亲")

    assert "林渊" in terms
    assert "救回" in terms
    assert "母亲" in terms


def test_goal_lock_false_inheritance_downgrades_when_key_events_are_covered(monkeypatch):
    generator = _make_generator()
    chapter = _make_chapter(
        1,
        "第1章",
        """
        林渊守在监测站前，盯着回声舰队的加密波形。
        白昼环的旧坐标在终端上一行行跳出，他继续顺着残缺记录往下查。
        """,
    )
    chapter.metadata.update(
        {
            "key_events": ["林渊追查失踪舰队回声真相"],
            "outline_summary": "林渊追查失踪舰队回声真相",
        }
    )

    monkeypatch.setattr(
        generator,
        "_check_goal_lock_alignment",
        lambda chapter, context: (
            [
                {
                    "category": "goal_lock_false_inheritance",
                    "message": "目标锁假继承",
                }
            ],
            {
                "goal_lock": "林渊追查失踪舰队回声真相",
                "summary_alignment": True,
                "body_matches": [{"fragment": "林渊守在监测站前", "negated": False}],
            },
        ),
    )
    monkeypatch.setattr(
        generator,
        "_check_structure_drift",
        lambda content, previous_summary, context: ([], {}),
    )
    monkeypatch.setattr(generator, "_event_is_covered", lambda event, content, context=None: True)

    report = generator._check_consistency(
        chapter,
        "",
        {
            "known_char_names": ["林渊"],
            "chapter_intent_contract": {"goal_lock": "林渊追查失踪舰队回声真相"},
        },
    )

    assert report["invalid"] is False
    assert "goal_lock_false_inheritance" not in report["hard_gate_issue_types"]
    assert any("目标锁假继承" in item for item in report["warning_issues"])


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
        assert "中文长篇小说写作助手" in prompt
        assert "宗门名称" not in prompt

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
                "characters": [{"name": "沈夜", "identity": "主角"}],
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

    def test_generate_content_skips_orchestrator_when_character_sources_missing(self):
        generator = _make_generator()
        generator.llm_client.generate.return_value = "沈夜回到边境空间城，开始调查异质核心来源。" * 80

        calls = {"count": 0}

        class _FakeOrchestrator:
            def orchestrate_chapter(self, **_kwargs):
                calls["count"] += 1
                return {"content": "不应调用", "plot_outline": {"beats": []}, "cast": []}

        generator.orchestrator = _FakeOrchestrator()

        result = generator._generate_content(
            chapter_number=1,
            title="第1章",
            outline="沈夜带着异质核心归来，在边境空间城落脚并查清核心来源",
            previous_summary="",
            context={"chapter_number": 1, "genre": "科幻修真"},
            retry_attempt=0,
        )

        assert calls["count"] == 0
        assert result["generation_trace"]["path"] == "direct_llm"
        assert result["generation_trace"]["orchestrator"]["failure_reasons"] == [
            "orchestrator_preflight_no_characters"
        ]
        assert generator._orchestrator_consecutive_failures == 0

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
                "characters": [{"name": "沈夜", "identity": "主角"}],
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

    def test_consistency_report_prefers_previous_tail_over_template_summary_consequence(
        self,
    ):
        report = _run_consistency_check(
            previous_summary=(
                "承接上一章局势，继续开场阶段推进。"
                "在近未来的极地轨道电梯网络崩塌后，沈雁重返被封锁的冰穹城。"
            ),
            previous_content="""
            远程通信器响起紧急呼叫，岑暮警告冰穹城外围冰架出现大面积共振裂缝。
            祁湛的雷达同时显示不明潜航器正高速逼近港口。
            沈雁必须在“立刻下探”与“紧急撤离”之间做出选择。
            """,
            current_content="""
            沈雁穿过极地轨道电梯的残骸区，踏入被封锁的北海冰穹城外围。
            她像是重新开始了一段调查，前一刻的紧急呼叫与逼近威胁仿佛都没有发生。
            """,
            context_overrides={
                "chapter_intent_contract": {
                    "goal_lock": "沈雁重返被封锁的北海冰穹城"
                },
            },
        )

        _assert_transition_issue(report, "上一章后果未被承接")
        assert any(
            detail["category"] == "上一章后果未被承接"
            and "立刻下探" in detail["previous_evidence"]
            for detail in report["smoothness_details"]
        )
        assert all(
            detail.get("previous_evidence") != "崩塌"
            for detail in report["smoothness_details"]
        )

    def test_consistency_report_falls_back_to_summary_when_previous_tail_missing(self):
        report = _run_consistency_check(
            previous_summary="上一章结尾，爆炸将叶尘炸成重伤，柳如烟也在废墟中昏迷不醒。",
            previous_content="",
            current_content="""
            清晨的集市热闹非凡。
            韩林慢悠悠地挑着糕点，还盘算着今晚去哪里听戏。
            """,
        )

        _assert_transition_issue(report, "上一章后果未被承接")
        assert any(
            detail["category"] == "上一章后果未被承接"
            and detail["previous_evidence"] == "重伤"
            for detail in report["smoothness_details"]
        )

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
            issue == "scene_or_timeline_disconnect" for issue in report["issue_types"]
        )

    def test_consistency_report_allows_explicit_path_bridge_into_new_room(self):
        report = _run_consistency_check(
            previous_summary="上一章结尾，季衡刚踏进那扇门，准备去监控室确认求救信号。",
            previous_content="""
            季衡压住呼吸，在走廊尽头推开那扇门。
            他知道门后就是监控区，必须尽快确认那段异常信号的真假。
            """,
            current_content="""
            季衡从上一章踏进那扇门后，穿过昏暗的走廊进入声呐监控室。
            苏未已经坐在控制台前，等他把第一轮波形比对结果调出来。
            """,
        )

        assert report["invalid"] is False
        assert not any("地点跳切无承接" in issue for issue in report["blocking_issues"])

    def test_extract_location_anchor_prefers_destination_over_control_console(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "季衡从上一章踏进那扇门后，穿过昏暗的走廊进入声呐监控室。苏未已经坐在控制台前。"
        )

        assert anchor == "声呐监控室"

    def test_extract_location_anchor_keeps_full_scifi_place_name(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "深潜器进入禁航海沟后，季衡发现所谓的求救信号并非来自失踪考察舰。"
        )

        assert anchor == "禁航海沟"

    def test_extract_location_anchor_rejects_window_countdown_fragment(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "深潜器在潮汐窗口关闭前三十秒冲出禁航区边界，船身猛地一沉。"
        )

        assert anchor == "禁航区边界"

    def test_extract_location_anchor_detects_station_scene(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "季衡在声呐监测站值班时，突然收到来自潮汐空间边界的微弱求救信号。"
        )

        assert anchor == "声呐监测站"

    def test_extract_location_anchor_prefers_earliest_scene_over_later_goal_place(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "声呐译码师季衡在潮汐监测站加班时，突然接收到异常信号。上司要求他在72小时内完成鉴定，并准备进入禁航海沟。"
        )

        assert anchor == "潮汐监测站"

    def test_extract_location_anchor_prefers_nested_room_over_outer_region(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "季衡在潮汐空间边界的声呐室中，突然收到持续脉冲信号。"
        )

        assert anchor == "声呐室"

    def test_extract_location_anchor_prefers_nested_center_over_outer_city(self):
        generator = _make_generator()

        anchor = generator._extract_location_anchor(
            "苏未在深海城的控制中心调取图谱。"
        )

        assert anchor == "控制中心"

    def test_consistency_report_flags_reset_from_trench_back_to_station(self):
        report = _run_consistency_check(
            previous_summary="上一章末尾，季衡和苏未已经进入禁航海沟，准备打捞中继浮标。",
            previous_content="""
            深潜器进入禁航海沟后，季衡发现所谓的求救信号并非来自失踪考察舰，
            而是一个由季岚预先设置的中继浮标。
            """,
            current_content="""
            季衡在声呐监测站值班时，突然收到来自潮汐空间边界的微弱求救信号。
            经比对，信号编码与失踪多年的深海考察舰完全一致。
            """,
        )

        assert report["invalid"] is True
        assert "scene_or_timeline_disconnect" in report["issue_types"]
        assert any(
            detail["previous_evidence"] == "禁航海沟"
            and detail["current_evidence"] == "声呐监测站"
            for detail in report["smoothness_details"]
        )

    def test_consistency_report_ignores_markdown_prelude_when_checking_opening(self):
        report = _run_consistency_check(
            previous_summary="上一章末尾，季衡和苏未已经进入禁航海沟，准备打捞中继浮标。",
            previous_content="""
            深潜器进入禁航海沟后，季衡发现所谓的求救信号并非来自失踪考察舰，
            而是一个由季岚预先设置的中继浮标。
            """,
            current_content="""
            # 第3章

            **本章概要**: 季衡必须确认信号真假、进入禁航海沟

            **关键事件**: 季衡确认信号真假、进入禁航海沟

            ---

            ◆开场
            季衡在声呐监测站值班时，突然收到来自潮汐空间边界的微弱求救信号。
            经比对，信号编码与失踪多年的深海考察舰完全一致。
            """,
        )

        assert report["invalid"] is True
        assert "scene_or_timeline_disconnect" in report["issue_types"]

    def test_future_goal_phrase_does_not_count_as_transition_bridge(self):
        generator = _make_generator()

        assert (
            generator._has_bridge_signal(
                "声呐译码师季衡在潮汐监测站加班时，闻彻要求他在72小时内完成鉴定，并准备进入禁航海沟。"
            )
            is False
        )

    def test_generate_chapter_falls_back_to_context_previous_summary_on_resume(
        self, monkeypatch
    ):
        generator = _make_generator()
        context = {
            "previous_summary": "上一章末尾，季衡和苏未已经进入禁航海沟，准备打捞中继浮标。",
            "previous_chapters": [
                {
                    "content": dedent(
                        """
                        深潜器进入禁航海沟后，季衡发现所谓的求救信号并非来自失踪考察舰，
                        而是一个由季岚预先设置的中继浮标。
                        """
                    ).strip()
                }
            ],
        }

        monkeypatch.setattr(
            generator,
            "_get_chapter_outline",
            lambda chapter_number: {
                "title": f"第{chapter_number}章",
                "summary": "承接上一章局势，继续承压阶段推进。",
                "key_events": ["季衡确认信号真假", "进入禁航海沟"],
                "magic_line": "",
                "goal_lock": "季衡确认信号真假、进入禁航海沟",
                "continuity_in": "",
                "continuity_out": "",
            },
        )
        monkeypatch.setattr(
            generator,
            "_generate_candidate",
            lambda **kwargs: {
                "content": dedent(
                    """
                    ◆开场
                    季衡在声呐监测站值班时，突然收到来自潮汐空间边界的微弱求救信号。
                    经比对，信号编码与失踪多年的深海考察舰完全一致。
                    """
                ).strip(),
                "orchestrator_result": None,
                "generation_trace": None,
            },
        )
        monkeypatch.setattr(
            generator,
            "_create_chapter",
            lambda **kwargs: MODULE.GeneratedChapter(
                number=kwargs["chapter_number"],
                title=kwargs["title"],
                content=kwargs["content"],
                word_count=len(kwargs["content"]),
                metadata={
                    "key_events": ["季衡确认信号真假", "进入禁航海沟"],
                    "outline_summary": kwargs["outline_summary"],
                },
            ),
        )
        monkeypatch.setattr(
            generator, "_rewrite_invalid_chapter", lambda **kwargs: kwargs["chapter"]
        )

        chapter = generator.generate_chapter(
            chapter_number=3,
            context=context,
            previous_summary="",
        )

        assert chapter.consistency_report["invalid"] is True
        assert "scene_or_timeline_disconnect" in chapter.consistency_report["issue_types"]

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

    def test_consistency_report_accepts_compound_event_split_across_actions(self):
        generator = NovelGeneratorAgent(
            config_manager=DummyConfigManager(), llm_client=MagicMock()
        )
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content=dedent(
                """
                林渊盯着回声空域回传的波形，先把异常频段与旧星门底噪逐项比对，确认这批数据到底是真是假。
                他转向顾岚，低声请她帮忙复核那组偏移参数，再配合自己锁定隐藏在噪声里的第二层坐标。
                """
            ).strip(),
            word_count=94,
            metadata={
                "key_events": ["途中他必须验证信号真假、争取顾岚协助"],
                "outline_summary": "途中他必须验证信号真假、争取顾岚协助",
            },
            plot_summary={
                "l2_brief_summary": "林渊继续验证信号真假，并争取顾岚协助破解噪声。"
            },
        )

        report = generator._check_consistency(
            chapter,
            previous_summary="上一章林渊刚跃入旧星门外围，准备继续追查母亲线索。",
            context={
                "character_names": ["林渊", "顾岚"],
                "chapter_intent_contract": {
                    "goal_lock": "途中他必须验证信号真假、争取顾岚协助"
                },
            },
        )

        assert report["invalid"] is False
        assert "missing_key_events" not in report["issue_types"]
        assert "goal_lock_false_inheritance" not in report["issue_types"]
        assert report["anti_drift_details"]["body_alignment"] is True
        assert set(report["anti_drift_details"]["covered_subgoals"]) == {
            "验证信号真假",
            "争取顾岚协助",
        }

    def test_goal_lock_alignment_reports_all_compound_subgoals_from_full_content(self):
        generator = _make_generator()
        chapter = MODULE.GeneratedChapter(
            number=3,
            title="第三章",
            content=dedent(
                """
                林渊抵达白昼环监测站主控室，面对星图投影中标记的异常信号源。他调出回声空域的旧星门与远征舰队残骸的扫描数据，发现信号与已知航标波形存在细微偏差，必须优先验证真伪才能决定是否启航。

                林渊试图独立解析信号编码，但发现其中嵌入了顾岚团队特有的加密片段。他主动联络顾岚，说明情况并请求顾岚协助解码。
                """
            ).strip(),
            word_count=138,
            metadata={"key_events": [], "outline_summary": ""},
            plot_summary={
                "l2_brief_summary": "林渊继续验证信号真假，并争取顾岚协助破解噪声。"
            },
        )

        issues, details = generator._check_goal_lock_alignment(
            chapter,
            {"chapter_intent_contract": {"goal_lock": "途中他必须验证信号真假、争取顾岚协助"}},
        )

        assert issues == []
        assert details["body_alignment"] is True
        assert set(details["covered_subgoals"]) == {"验证信号真假", "争取顾岚协助"}
        assert details["missing_subgoals"] == []

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

    def test_build_chapter_repair_plan_adds_plan_first_fields(self):
        generator = _make_generator()

        repair_plan = generator._build_chapter_repair_plan(
            report={
                "issue_types": [
                    "scene_or_timeline_disconnect",
                    "goal_lock_false_inheritance",
                ],
                "blocking_issues": ["上一章后果未被承接。"],
                "continuity_issues": ["上一章后果未被承接。"],
                "missing_events": ["林渊救回母亲"],
                "anti_drift_details": {
                    "goal_lock": "林渊救回母亲",
                    "matched_fragments": ["林渊冲向舱门"],
                },
            },
            outline_summary="林渊救回母亲并撤离白昼环。",
            context={"chapter_plan": {"continuity_out": "暴露撤离路线"}},
        )

        assert repair_plan["rewrite_mode"] == "plan_first_full_rewrite"
        assert repair_plan["goal_lock"] == "林渊救回母亲"
        assert repair_plan["goal_subgoals"] == ["林渊救回母亲"]
        assert repair_plan["must_include_events"] == ["林渊救回母亲"]
        assert repair_plan["opening_bridge"] == ["上一章后果未被承接。"]
        assert repair_plan["continuity_anchor_contract"] == {}
        assert repair_plan["failure_evidence"]["blocking_issues"] == [
            "上一章后果未被承接。"
        ]
        assert [item["phase"] for item in repair_plan["ordered_beats"]] == [
            "opening",
            "development",
            "conflict",
            "resolution",
        ]

    def test_format_rewrite_guidance_includes_plan_first_sections(self):
        generator = _make_generator()

        guidance = generator._format_rewrite_guidance(
            {
                "failure_evidence": {"blocking_issues": ["上一章后果未被承接。"]},
                "opening_bridge": ["先回应暴露后果。"],
                "must_include_events": ["林渊救回母亲"],
                "fixes": ["重建章节行动链。"],
                "success_criteria": ["正文真实推进目标锁。"],
                "goal_lock": "林渊验证信号真假、争取顾岚协助",
                "goal_subgoals": ["验证信号真假", "争取顾岚协助"],
                "ordered_beats": [
                    {"phase": "opening", "required_action": "承接暴露后果"},
                    {
                        "phase": "resolution",
                        "required_action": "交代撤离压力",
                        "continuity_out": "暴露撤离路线",
                    },
                ],
            }
        )

        assert "【失败证据】1. 上一章后果未被承接。" in guidance
        assert "【开篇补桥】1. 先回应暴露后果。" in guidance
        assert "【必须覆盖事件】1. 林渊救回母亲" in guidance
        assert "【目标锁】林渊验证信号真假、争取顾岚协助" in guidance
        assert "【目标锁分项】1. 验证信号真假 2. 争取顾岚协助" in guidance
        assert "【重写节拍】1. opening: 承接暴露后果" in guidance
        assert "2. resolution: 交代撤离压力（暴露撤离路线）" in guidance

    def test_rewrite_plan_adds_explicit_scene_anchor_contract(self):
        generator = _make_generator()

        repair_plan = generator._build_chapter_repair_plan(
            report={
                "issue_types": ["scene_or_timeline_disconnect"],
                "blocking_issues": [
                    "顺畅性问题[地点跳切无承接] 上一章线索「禁航海沟」 与当前开篇「深海城邦」之间缺少地点转换或行动路径交代。"
                ],
                "continuity_issues": [
                    "顺畅性问题[地点跳切无承接] 上一章线索「禁航海沟」 与当前开篇「深海城邦」之间缺少地点转换或行动路径交代。"
                ],
                "smoothness_details": [
                    {
                        "category": "地点跳切无承接",
                        "previous_evidence": "禁航海沟",
                        "current_evidence": "深海城邦",
                    }
                ],
                "anti_drift_details": {
                    "goal_lock": "季衡确认信号真假、进入禁航海沟",
                    "matched_fragments": ["季衡拖着浮标回到舱内"],
                },
            },
            outline_summary="季衡在海沟内确认图谱真假并应对追兵。",
            context={},
        )

        assert repair_plan["continuity_anchor_contract"] == {
            "previous_anchor": "禁航海沟",
            "current_anchor": "深海城邦",
            "instruction": "开篇先接住「禁航海沟」；如需切到「深海城邦」，必须写出路径、抵达动作或切换原因，不得直接在「深海城邦」重开。",
        }
        assert any(
            item["action"] == "lock_scene_anchor"
            for item in repair_plan["operations"]
        )

        rewrite_outline = generator._compose_rewrite_outline(
            outline="承接上一章局势，继续推进。",
            repair_plan=repair_plan,
        )
        assert "场景锚点硬约束" in rewrite_outline
        assert "开篇先接住「禁航海沟」" in rewrite_outline

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
    expected_anti_drift_details = case.get("expected_anti_drift_details", {})
    if expected_anti_drift_details:
        anti_drift_details = report.get("anti_drift_details", {})
        for key, expected_value in expected_anti_drift_details.items():
            actual_value = anti_drift_details.get(key)
            if key in {"covered_subgoals", "missing_subgoals"}:
                assert sorted(actual_value or []) == sorted(expected_value)
            else:
                assert actual_value == expected_value


def test_consistency_report_adds_graph_diff_details_from_chapter_graph_packet():
    report = _run_consistency_check(
        previous_summary="上一章林渊刚在白昼环控制室确认母亲信号来自二十七年前。",
        previous_content="""
        林渊站在白昼环控制室，意识到信号源并不等于当前所在地点。
        他决定下一章转去废弃港继续追查。
        """,
        current_content="""
        三天后，林渊已经到了废弃港，却把大量篇幅耗在无关闲谈上。
        他没有真正确认信号真假，也没有推进进入禁航海沟的行动。
        """,
        chapter_number=6,
        context_overrides={
            "chapter_graph_packet": {
                "goal_lock": "确认信号真假、进入禁航海沟",
                "goal_subgoals": ["确认信号真假", "进入禁航海沟"],
                "must_include_events": ["救回母亲"],
                "previous_scene_anchor": "白昼环控制室",
                "opening_bridge_required": "开篇先接住白昼环控制室；如需切到废弃港，必须写出路径或抵达动作。",
                "rebaseline_deltas": [],
            },
            "chapter_driver_validation": ["scene_beats must be a list"],
        },
        plot_summary={"l2_brief_summary": "林渊在废弃港继续追查母亲信号。"},
    )

    assert report["chapter_graph_packet"]["goal_lock"] == "确认信号真假、进入禁航海沟"
    assert report["chapter_driver_validation"] == ["scene_beats must be a list"]
    assert report["graph_diff_details"]["schema_version"] == "graph_diff_details.v1"
    assert report["graph_diff_details"]["recommended_action"] == "accept"
    assert any(
        item["type"] == "MUST_INCLUDE" and item["label"] == "救回母亲"
        for item in report["graph_diff_details"]["planned_edges"]
    )


def test_chapter_driver_packet_is_rendered_in_intent_contract():
    generator = _make_generator()
    context = {
        "goal_lock": "确认信号真假、进入禁航海沟",
        "chapter_driver_packet": {
            "schema_version": "chapter_driver_packet.v1",
            "scene_beats": [
                {
                    "index": 1,
                    "action": "确认信号真假",
                    "turn": "信息差被压缩",
                    "success_evidence": "正文写出确认信号真假的行动",
                }
            ],
            "cast": [
                {
                    "name": "林渊",
                    "objective": "进入禁航海沟",
                    "pressure": "从怀疑转为孤注一掷",
                }
            ],
            "emotional_arc": ["承接警报", "从怀疑转为孤注一掷"],
            "tension_points": ["主线目标不可漂移: 确认信号真假、进入禁航海沟"],
            "cliffhanger": "母亲第二段回声出现",
            "driver_notes": ["开篇先回应上一章后果"],
        },
    }

    contract = generator._build_chapter_intent_contract(
        outline="林渊确认信号真假。",
        context=context,
    )
    rendered = generator._format_chapter_intent_contract(contract)

    assert contract["scene_beats"][0]["action"] == "确认信号真假"
    assert "叙事驱动场景节拍" in rendered
    assert "角色驱动目标" in rendered
    assert "母亲第二段回声出现" in rendered
