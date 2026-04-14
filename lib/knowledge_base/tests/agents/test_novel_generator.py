"""Tests for NovelGeneratorAgent writing option prompt integration."""

import importlib.util
from pathlib import Path
import sys
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


class TestNovelGeneratorWritingOptions:
    """Test writing option prompt expansion in the main generation path."""

    def test_generation_prompt_includes_writing_options(self):
        generator = NovelGeneratorAgent(config_manager=DummyConfigManager(), llm_client=MagicMock())

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
        generator = NovelGeneratorAgent(config_manager=DummyConfigManager(), llm_client=MagicMock())

        prompt = generator._build_generation_prompt(
            chapter_number=12,
            title="新卷开篇",
            outline="主角进入新卷主线。",
            previous_summary="上一卷在大战后收束。",
            genre="玄幻",
            volume_guidance="- 必须回收的伏笔/问题: 下一卷必须尽快回收师门裂痕\n- 需要强化的人物关系: 强化主角的主动性",
        )

        assert "本卷修订指令" in prompt
        assert "必须回收的伏笔/问题" in prompt
        assert "下一卷必须尽快回收师门裂痕" in prompt
