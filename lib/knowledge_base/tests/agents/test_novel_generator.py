"""Tests for NovelGeneratorAgent writing option prompt integration."""

import importlib.util
from pathlib import Path
import sys
from textwrap import dedent
import types
from unittest.mock import MagicMock


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
) -> dict:
    generator = _make_generator()
    chapter = _make_chapter(2, "第二章", current_content)
    context = {
        "known_char_names": ["韩林", "柳如烟", "叶尘"],
        "previous_chapters": [{"content": dedent(previous_content).strip()}],
    }
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
