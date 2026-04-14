"""Tests for NovelConsumer prompt option expansion."""

import importlib.util
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

CONSUMERS_DIR = Path(__file__).resolve().parents[2] / "consumers"
PACKAGE = types.ModuleType("consumers")
PACKAGE.__path__ = [str(CONSUMERS_DIR)]
sys.modules.setdefault("consumers", PACKAGE)

base_spec = importlib.util.spec_from_file_location("consumers.base", CONSUMERS_DIR / "base.py")
base_module = importlib.util.module_from_spec(base_spec)
sys.modules[base_spec.name] = base_module
assert base_spec.loader is not None
base_spec.loader.exec_module(base_module)

SPEC = importlib.util.spec_from_file_location(
    "consumers.novel_consumer",
    CONSUMERS_DIR / "novel_consumer.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

NovelConsumer = MODULE.NovelConsumer


class TestNovelConsumerPromptOptions:
    """Verify knowledge-base-derived prompt options are mapped correctly."""

    def test_build_prompt_includes_extended_options(self):
        consumer = NovelConsumer(llm_client=None)

        prompt = consumer._build_novel_prompt(
            beats=[{"beat_type": "conflict", "description": "韩林被当众羞辱", "expected_chars": ["韩林", "赵岩"]}],
            character_states={"韩林": [{"emotional_state": "愤怒", "physical_state": "受伤"}]},
            scene_descriptions=["演武场上众人围观，空气压抑。"],
            narration_pieces=["韩林强压怒火，握紧拳头。"],
            emotional_arc={"start_state": "压抑", "peak_state": "爆发", "end_state": "隐忍"},
            chapter_info={"chapter_number": 3, "title": "忍辱"},
            background="太虚宗外门竞争残酷，强者为尊。",
            style="dramatic",
            style_preset="epic_rebel",
            perspective="third_omniscient",
            narrative_mode="multi_line_foreshadowing",
            pace="fast",
            dialogue_density="high",
            prose_style="concise_forceful",
            world_building_density="dense",
            emotion_intensity="high",
            combat_style="epic",
            hook_strength="strong",
            word_count_target=4000,
        )

        assert "风格预设: epic_rebel" in prompt
        assert "叙事视角: third_omniscient" in prompt
        assert "叙事写法: multi_line_foreshadowing" in prompt
        assert "对白密度: high" in prompt
        assert "行文质感: concise_forceful" in prompt
        assert "设定密度: dense" in prompt
        assert "情绪强度: high" in prompt
        assert "战斗写法: epic" in prompt
        assert "开篇抓力: strong" in prompt
        assert "逆天写法" in prompt

    def test_author_style_alias_and_unknown_option_fallback(self):
        consumer = NovelConsumer(llm_client=None)

        prompt = consumer._build_novel_prompt(
            beats=[],
            character_states={},
            scene_descriptions=[],
            narration_pieces=[],
            emotional_arc={},
            chapter_info={},
            background="",
            author_style="fanren_flow",
            prose_style="minimalist_custom",
        )

        assert "风格预设: fanren_flow" in prompt
        assert "凡人流写法" in prompt
        assert "行文质感: minimalist_custom（自定义）" in prompt
