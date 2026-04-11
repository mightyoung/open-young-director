"""End-to-end integration tests for the novel generation pipeline.

Uses a MockDeepSeekClient that returns pre-canned JSON responses based on
keywords in the prompt, so no real network calls are made.

Test cases
----------
test_full_pipeline_smoke    — Run PipelineRunner.run() from world → review (3-chapter novel).
test_pipeline_resume        — Start fresh, persist state, then resume from "volume" stage.
test_pipeline_stage_validation — Verify validate_input raises when prerequisites are missing.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from crewai.content.novel.pipeline.pipeline_runner import PipelineRunner
from crewai.content.novel.pipeline_state import PipelineState


# ---------------------------------------------------------------------------
# Canned responses
# ---------------------------------------------------------------------------

_WORLD_RESPONSE = json.dumps({
    "name": "测试大陆",
    "description": "一个以修炼为核心的世界",
    "power_system_name": "修炼体系",
    "cultivation_levels": ["凡人", "练气", "筑基", "金丹", "元婴", "化神"],
    "level_abilities": {
        "凡人": ["普通体能"],
        "练气": ["操控灵气"],
        "筑基": ["御剑飞行"],
        "金丹": ["神通初现"],
        "元婴": ["元神出窍"],
        "化神": ["规则掌控"],
    },
    "world_constraints": ["修炼需要灵气", "每次大境界突破都有雷劫", "杀戮过重者会被天道排斥"],
    "geography": [{"name": "中州", "description": "大陆中心"}],
    "factions": [{"name": "正道联盟", "description": "各大正派"}],
    "history": ["万年前上古大战"],
    "social_rules": ["弱肉强食，强者为尊"],
})

_PLOT_RESPONSE = json.dumps({
    "title": "苍穹传说",
    "synopsis": "一部关于修炼的史诗故事",
    "main_characters": [
        {
            "name": "林凡",
            "role": "protagonist",
            "personality": "坚毅果断",
            "core_desire": "超越极限",
            "hidden_agenda": "",
        }
    ],
    "plot_arcs": [
        {"name": "起源", "description": "主角踏上旅程", "start_chapter": 1, "end_chapter": 1},
        {"name": "成长", "description": "历经磨难", "start_chapter": 2, "end_chapter": 2},
        {"name": "终局", "description": "最终决战", "start_chapter": 3, "end_chapter": 3},
    ],
    "turning_points": [
        {"chapter": 1, "description": "第一个重大转折", "impact": "改变主角命运"},
        {"chapter": 2, "description": "中期大反转", "impact": "揭示真相"},
        {"chapter": 3, "description": "高潮前夕", "impact": "推向决战"},
    ],
    "themes": ["成长", "牺牲", "友情"],
})

_EVALUATION_RESPONSE = json.dumps({
    "plot_coherence": 8,
    "character_development": 7,
    "pacing": 7,
    "originality": 7,
    "comments": {
        "plot_coherence": "情节连贯",
        "character_development": "人物立体",
        "pacing": "节奏稳健",
        "originality": "有新意",
    },
})

_VOLUME_RESPONSE = json.dumps([
    {
        "volume_num": 1,
        "title": "第一卷",
        "theme": "初探修炼之路",
        "start_chapter": 1,
        "end_chapter": 3,
        "key_events": ["事件1", "事件2"],
        "character_focus": ["林凡"],
        "tension_arc": {
            "opening": "平静",
            "rising": "激化",
            "climax": "决战",
            "resolution": "平衡",
        },
        "chapters_summary": ["第1章: 起点", "第2章: 历练", "第3章: 突破"],
    }
])

_SUMMARY_RESPONSE = json.dumps([
    {
        "chapter_num": 1,
        "volume_num": 1,
        "title": "少年出山",
        "main_events": ["主角离家踏上旅程", "遭遇第一个挑战"],
        "character_appearances": ["林凡"],
        "tension_level": 5,
        "pov_character": "林凡",
        "ending_hook": "神秘人物出现，预示着更大的危机",
    },
    {
        "chapter_num": 2,
        "volume_num": 1,
        "title": "磨难历程",
        "main_events": ["经历重重磨难", "实力大幅提升"],
        "character_appearances": ["林凡"],
        "tension_level": 7,
        "pov_character": "林凡",
        "ending_hook": "隐藏的秘密即将揭晓",
    },
    {
        "chapter_num": 3,
        "volume_num": 1,
        "title": "境界突破",
        "main_events": ["最终决战", "突破大境界"],
        "character_appearances": ["林凡"],
        "tension_level": 9,
        "pov_character": "林凡",
        "ending_hook": "新的征程即将开始",
    },
])

# 500+ Chinese fiction characters for writing stage responses
_CHAPTER_TEXT = (
    "林凡站在山巅，俯瞰着脚下的大地。晨曦的光芒穿透云层，照耀在他的身上，"
    "映出一道修长的影子。他深吸一口气，感受着天地间涌动的灵气，心中涌现出"
    "一股前所未有的平静。这一路走来，历经无数磨难，才有了今日的成就。"
    "师父曾说过，修炼之路从来不是一帆风顺的，只有经历过最深的黑暗，才能"
    "迎来最耀眼的光明。林凡将这句话铭记于心，每当面临绝境之时，便以此自勉。"
    "今日，他终于站在了这个让无数修炼者望而兴叹的地方。远处，群山连绵，"
    "云雾缭绕，一切都显得那么宁静而壮观。林凡知道，属于他的征途才刚刚开始。"
    "前方等待着他的，将是更加艰险的试炼，更加强大的对手，以及更加深邃的秘密。"
    "但他已经做好了准备，带着对修炼的热爱，带着对伙伴的承诺，继续前行。"
)


# ---------------------------------------------------------------------------
# MockDeepSeekClient
# ---------------------------------------------------------------------------


class MockDeepSeekClient:
    """Keyword-dispatched mock that replaces DeepSeekClient in tests."""

    def __init__(self) -> None:
        self.call_count = 0

    def chat(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        self.call_count += 1
        prompt_text = " ".join(m.get("content", "") for m in messages)
        return self._dispatch(prompt_text)

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def set_seed(self, seed: int) -> None:
        pass

    # ------------------------------------------------------------------
    # Internal dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, prompt: str) -> str:
        """Return a canned response based on keywords found in *prompt*."""
        if any(kw in prompt for kw in ("世界观", "world", "题材", "类型", "风格")):
            # world_stage.py prompts contain these markers
            if any(kw in prompt for kw in ("世界观", "world_constraints", "geography", "factions")):
                return _WORLD_RESPONSE

        # Evaluation prompt uses 评估 or contains criterion names from evaluate_stage
        if any(kw in prompt for kw in ("评估", "evaluate", "plot_coherence", "OUTLINE START")):
            return _EVALUATION_RESPONSE

        # Outline stage prompts contain 大纲 or synopsis/plot_arcs
        if any(kw in prompt for kw in ("大纲", "outline", "plot_arcs", "turning_points", "synopsis")):
            return _PLOT_RESPONSE

        # Volume stage prompts contain 分卷
        if any(kw in prompt for kw in ("分卷", "volume", "volume_num", "分卷大纲")):
            return _VOLUME_RESPONSE

        # Summary stage prompts contain 概要
        if any(kw in prompt for kw in ("概要", "summary", "chapter_num", "ending_hook")):
            return _SUMMARY_RESPONSE

        # Writing stage — contains 撰写, 写, 第N章 etc.
        if any(kw in prompt for kw in ("撰写", "write", "第", "章节", "写作")):
            return _CHAPTER_TEXT

        return "{}"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm() -> MockDeepSeekClient:
    return MockDeepSeekClient()


@pytest.fixture
def novel_config(tmp_path) -> dict:
    """Minimal 3-chapter novel config pointing I/O at tmp_path."""
    return {
        "topic": "修炼者传奇",
        "genre": "xianxia",
        "style": "epic",
        "num_chapters": 3,
        "total_chapters": 3,
        "chapters_per_volume": 3,
        "words_per_chapter_target": 500,
        "output_dir": str(tmp_path / "output"),
    }


def _make_runner(config: dict, llm: MockDeepSeekClient) -> PipelineRunner:
    return PipelineRunner(
        config=config,
        llm=llm,  # type: ignore[arg-type]  — duck-typed mock
        output_dir=config["output_dir"],
    )


# ---------------------------------------------------------------------------
# Test 1: Full pipeline smoke test
# ---------------------------------------------------------------------------


def test_full_pipeline_smoke(tmp_path, mock_llm, novel_config):
    """Run all pipeline stages from world → review with a mock LLM.

    Verifies that:
    - state.world_data is populated after the world stage
    - state.plot_data is populated after the outline stage
    - state.current_stage progresses through all stages
    - No exceptions are raised
    - The mock LLM was actually called (call_count > 0)
    """
    runner = _make_runner(novel_config, mock_llm)
    state = runner.run()

    # LLM must have been called
    assert mock_llm.call_count > 0, "MockDeepSeekClient was never called"

    # World stage must have populated world_data
    assert state.world_data, "state.world_data is empty after full pipeline run"
    assert state.world_data.get("name"), "world_data is missing 'name'"

    # Outline stage must have populated plot_data
    assert state.plot_data, "state.plot_data is empty after full pipeline run"
    assert state.plot_data.get("title"), "plot_data is missing 'title'"
    assert state.plot_data.get("main_characters"), "plot_data is missing 'main_characters'"
    assert isinstance(state.plot_data.get("plot_arcs"), list), "plot_data 'plot_arcs' is not a list"

    # current_stage should be one of the known stage names (last completed = "review")
    assert state.current_stage in PipelineRunner.STAGES, (
        f"current_stage={state.current_stage!r} is not a recognised stage"
    )

    # Volume outlines must be populated
    assert state.volume_outlines, "state.volume_outlines is empty"

    # Chapter summaries must be populated (3-chapter novel)
    assert len(state.chapter_summaries) >= 3, (
        f"Expected >= 3 chapter summaries, got {len(state.chapter_summaries)}"
    )

    # Chapters must be written
    assert len(state.chapters) >= 3, (
        f"Expected >= 3 chapters, got {len(state.chapters)}"
    )

    # State file must exist on disk
    state_path = os.path.join(novel_config["output_dir"], "state", "pipeline_state.json")
    assert os.path.isfile(state_path), f"Pipeline state file not found at {state_path}"


# ---------------------------------------------------------------------------
# Test 2: Resume from volume stage
# ---------------------------------------------------------------------------


def test_pipeline_resume(tmp_path, mock_llm, novel_config):
    """Run world+outline+evaluate first, save state, then resume from volume.

    Verifies that when resuming from 'volume', the world/outline/evaluate
    stages are skipped and their data is preserved from the saved state.
    """
    runner = _make_runner(novel_config, mock_llm)
    state_path = str(tmp_path / "output" / "state" / "pipeline_state.json")

    # --- Phase 1: run only up to and including evaluate ---
    # Manually build state through world + outline + evaluate only
    initial_state = PipelineState()
    initial_state.config = dict(novel_config)
    initial_state.config["state_path"] = state_path
    initial_state.config["output_dir"] = novel_config["output_dir"]
    os.makedirs(os.path.dirname(state_path), exist_ok=True)

    # Populate world_data and plot_data directly (simulating completed stages)
    import json as _json
    initial_state.world_data = _json.loads(_WORLD_RESPONSE)
    initial_state.plot_data = _json.loads(_PLOT_RESPONSE)
    initial_state.outline_evaluation = _json.loads(_EVALUATION_RESPONSE)
    initial_state.evaluation_passed = True
    initial_state.current_stage = "evaluate"
    initial_state.save(state_path)

    # Track call count before resume
    calls_before = mock_llm.call_count

    # --- Phase 2: resume from "volume" ---
    # This should skip world, outline, evaluate stages
    resumed_state = runner.run(resume_from="volume", state_path=state_path)

    calls_after = mock_llm.call_count

    # LLM must be called for volume, summary, writing (review is rule-based)
    assert calls_after > calls_before, (
        "Expected LLM calls during resumed stages (volume/summary/writing)"
    )

    # Previously computed data must be preserved from the saved state
    assert resumed_state.world_data.get("name") == "测试大陆", (
        "world_data was overwritten during resume"
    )
    assert resumed_state.plot_data.get("title") == "苍穹传说", (
        "plot_data was overwritten during resume"
    )

    # Volume outlines must now be populated by the resume run
    assert resumed_state.volume_outlines, "volume_outlines not populated after resume"

    # Chapters must have been written
    assert resumed_state.chapters, "No chapters written after resume from volume"


# ---------------------------------------------------------------------------
# Test 3: Stage validation — missing prerequisites raise ValueError
# ---------------------------------------------------------------------------


def test_pipeline_stage_validation(tmp_path, mock_llm):
    """Start the pipeline at 'outline' with no world_data — should raise ValueError.

    OutlineStage.validate_input checks that state.world_data is non-empty.
    PipelineRunner.run() should surface this as a ValueError before running
    any stage logic.
    """
    config = {
        "topic": "测试题材",
        "genre": "urban",
        "style": "realistic",
        "num_chapters": 3,
        "total_chapters": 3,
        "output_dir": str(tmp_path / "output"),
    }
    runner = _make_runner(config, mock_llm)
    state_path = str(tmp_path / "output" / "state" / "pipeline_state.json")

    # Create a state with world_data missing (empty), so outline validate_input fails
    empty_state = PipelineState()
    empty_state.config = dict(config)
    empty_state.config["state_path"] = state_path
    empty_state.config["output_dir"] = config["output_dir"]
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    empty_state.save(state_path)

    # Resuming from "outline" should fail because world_data is empty
    with pytest.raises(ValueError, match="outline"):
        runner.run(resume_from="outline", state_path=state_path)

    # LLM should not have been called (validation fails before any LLM usage)
    assert mock_llm.call_count == 0, (
        f"LLM was called {mock_llm.call_count} time(s) despite validation failure"
    )
