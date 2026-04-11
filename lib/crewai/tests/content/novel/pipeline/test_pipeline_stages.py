"""Unit tests for the core novel pipeline stages.

Covers:
- StageRunner base class (NotImplementedError, _call_llm, _parse_json_response)
- PipelineRunner (STAGES list, resume_from, validate_input failure)
- ReviewStage (forbidden words, word count, no-loop guarantee)
- EvaluateStage (passing / failing evaluation via mocked LLM)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline.pipeline_runner import PipelineRunner
from crewai.content.novel.pipeline.review_stage import ReviewStage, FORBIDDEN_WORDS
from crewai.content.novel.pipeline.evaluate_stage import EvaluateStage, _PASS_THRESHOLD


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_llm() -> MagicMock:
    """Return a MagicMock that quacks like a DeepSeekClient."""
    llm = MagicMock()
    llm.chat = MagicMock(return_value="")
    return llm


def _make_state(**kwargs) -> PipelineState:
    """Return a minimal PipelineState suitable for test use."""
    defaults: dict = {
        "config": {
            "output_dir": "/tmp/test_output",
            "words_per_chapter_target": 1000,
        },
    }
    defaults.update(kwargs)
    return PipelineState(**defaults)


# ---------------------------------------------------------------------------
# TestStageRunner
# ---------------------------------------------------------------------------

class TestStageRunner:
    """Tests for StageRunner base class helpers."""

    # ------------------------------------------------------------------
    # Concrete minimal subclass used only within these tests
    # ------------------------------------------------------------------

    @dataclass
    class _ConcreteStage(StageRunner):
        """Minimal concrete stage that does nothing — only used for testing base."""
        name: str = "concrete"

        def run(self, state: PipelineState) -> PipelineState:  # type: ignore[override]
            return state

    def _make_stage(self) -> "_ConcreteStage":
        return self._ConcreteStage(name="concrete", llm=_make_llm())

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_base_run_not_implemented(self):
        """StageRunner.run() raises NotImplementedError on the raw base class."""
        llm = _make_llm()
        # Instantiate the abstract base directly (no @dataclass enforcement)
        stage = StageRunner.__new__(StageRunner)
        stage.name = "base"
        stage.llm = llm
        stage.timeout = 300

        with pytest.raises(NotImplementedError, match="must implement run"):
            stage.run(_make_state())

    def test_call_llm_sends_correct_messages(self):
        """_call_llm passes system + user messages to llm.chat with correct shape."""
        llm = _make_llm()
        llm.chat.return_value = "hello world"
        stage = self._make_stage()
        stage.llm = llm

        result = stage._call_llm(
            system_prompt="You are helpful.",
            user_prompt="Write a haiku.",
            max_tokens=512,
            temperature=0.5,
        )

        assert result == "hello world"
        llm.chat.assert_called_once()
        call_args = llm.chat.call_args

        # First positional arg must be the messages list
        messages = call_args[0][0]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1] == {"role": "user", "content": "Write a haiku."}

        # Keyword args forwarded
        assert call_args[1]["max_tokens"] == 512
        assert call_args[1]["temperature"] == 0.5

    def test_parse_json_response_clean(self):
        """_parse_json_response handles a plain JSON string."""
        stage = self._make_stage()
        raw = '{"key": "value", "score": 7}'
        result = stage._parse_json_response(raw)
        assert result == {"key": "value", "score": 7}

    def test_parse_json_response_code_fence(self):
        """_parse_json_response extracts JSON wrapped in ```json ... ``` fences."""
        stage = self._make_stage()
        raw = '```json\n{"key": "fenced", "score": 9}\n```'
        result = stage._parse_json_response(raw)
        assert result == {"key": "fenced", "score": 9}

    def test_parse_json_response_plain_code_fence(self):
        """_parse_json_response handles ``` (no language tag) fences."""
        stage = self._make_stage()
        raw = '```\n{"unlabelled": true}\n```'
        result = stage._parse_json_response(raw)
        assert result == {"unlabelled": True}

    def test_parse_json_response_invalid_raises(self):
        """_parse_json_response raises json.JSONDecodeError for unparseable text."""
        import json as _json
        stage = self._make_stage()
        with pytest.raises(_json.JSONDecodeError):
            stage._parse_json_response("not json at all")


# ---------------------------------------------------------------------------
# TestPipelineRunner
# ---------------------------------------------------------------------------

class TestPipelineRunner:
    """Tests for PipelineRunner orchestration logic."""

    def _make_runner(self, **config_overrides) -> PipelineRunner:
        config = {"topic": "Test", "style": "xianxia", **config_overrides}
        return PipelineRunner(config=config, llm=_make_llm(), output_dir="/tmp/test_output")

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_stages_list(self):
        """STAGES must contain exactly the 7 expected stage names in order."""
        expected = ("world", "outline", "evaluate", "volume", "summary", "writing", "review")
        assert PipelineRunner.STAGES == expected

    def test_resume_from_stage_skips_earlier_stages(self):
        """run() with resume_from='evaluate' must skip 'world' and 'outline'."""
        runner = self._make_runner()

        executed_stages: list[str] = []

        # We build a mock stage map where every stage is a no-op that records itself.
        def _make_mock_stage_cls(stage_name: str):
            mock_cls = MagicMock()
            instance = MagicMock()
            instance.validate_input.return_value = True
            instance.run.side_effect = lambda s: s  # identity: return state unchanged
            mock_cls.return_value = instance
            executed_stages_ref = executed_stages

            # Override run to also record the stage name
            def _run(state, _name=stage_name):
                executed_stages_ref.append(_name)
                return state

            instance.run.side_effect = _run
            return mock_cls

        stage_map = {name: _make_mock_stage_cls(name) for name in PipelineRunner.STAGES}

        with (
            patch(
                "crewai.content.novel.pipeline.pipeline_runner._import_stages",
                return_value=stage_map,
            ),
            patch.object(runner, "_ensure_output_dirs"),
            patch.object(runner, "_load_or_create_state", return_value=_make_state()),
            patch.object(PipelineState, "save"),
        ):
            runner.run(resume_from="evaluate")

        # Only stages from 'evaluate' onward should have been executed
        assert "world" not in executed_stages
        assert "outline" not in executed_stages
        assert "evaluate" in executed_stages
        assert "review" in executed_stages

    def test_validate_input_failure_raises_value_error(self):
        """Pipeline raises ValueError when a stage's validate_input returns False."""
        runner = self._make_runner()

        failing_stage_cls = MagicMock()
        failing_instance = MagicMock()
        failing_instance.validate_input.return_value = False
        failing_stage_cls.return_value = failing_instance

        # All stages succeed except the first one ('world')
        stage_map = {name: MagicMock() for name in PipelineRunner.STAGES}
        stage_map["world"] = failing_stage_cls

        with (
            patch(
                "crewai.content.novel.pipeline.pipeline_runner._import_stages",
                return_value=stage_map,
            ),
            patch.object(runner, "_ensure_output_dirs"),
            patch.object(runner, "_load_or_create_state", return_value=_make_state()),
        ):
            with pytest.raises(ValueError, match="prerequisites not met"):
                runner.run()

    def test_resolve_start_index_unknown_stage_raises(self):
        """_resolve_start_index raises ValueError for an unrecognised stage name."""
        runner = self._make_runner()
        with pytest.raises(ValueError, match="Unknown resume_from stage"):
            runner._resolve_start_index("nonexistent_stage")

    def test_resolve_start_index_none_returns_zero(self):
        """_resolve_start_index(None) starts from index 0."""
        runner = self._make_runner()
        assert runner._resolve_start_index(None) == 0

    def test_resolve_start_index_named_stage(self):
        """_resolve_start_index returns the correct index for a valid stage name."""
        runner = self._make_runner()
        # 'evaluate' is at index 2 in STAGES
        assert runner._resolve_start_index("evaluate") == 2


# ---------------------------------------------------------------------------
# TestReviewStage
# ---------------------------------------------------------------------------

class TestReviewStage:
    """Tests for ReviewStage rule-based chapter checks."""

    def _make_stage(self) -> ReviewStage:
        return ReviewStage(name="review", llm=_make_llm())

    def _make_chapter(self, content: str, chapter_num: int = 1) -> dict:
        return {"chapter_num": chapter_num, "content": content}

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_forbidden_words_detected(self):
        """review_issues contains entries for each forbidden word found."""
        # Use the first two real forbidden words from the constant
        word1, word2 = FORBIDDEN_WORDS[0], FORBIDDEN_WORDS[1]
        # Build content that is long enough to pass word-count / empty checks but
        # contains both forbidden words
        filler = "这是一段测试内容，用于填充字数要求。" * 60  # ~900 chars
        content = f"{filler} {word1} 出现了。 {word2} 也出现了。"

        stage = self._make_stage()
        issues = stage._check_forbidden_words(content)

        found_words = {issue["word"] for issue in issues}
        assert word1 in found_words
        assert word2 in found_words
        for issue in issues:
            assert issue["type"] == "forbidden_word"
            assert issue["count"] >= 1

    def test_forbidden_words_none_present(self):
        """_check_forbidden_words returns empty list when no forbidden words appear."""
        stage = self._make_stage()
        content = "这是一段干净的文本，没有任何禁词。" * 10
        issues = stage._check_forbidden_words(content)
        assert issues == []

    def test_word_count_check_too_short(self):
        """_check_word_count flags content that is shorter than 50% of target."""
        stage = self._make_stage()
        target = 1000
        short_content = "短" * 400  # 400 chars < 500 (50% of 1000)
        issues = stage._check_word_count(short_content, target)
        assert len(issues) == 1
        assert issues[0]["type"] == "word_count"
        assert "偏少" in issues[0]["message"]

    def test_word_count_check_too_long(self):
        """_check_word_count flags content that exceeds 150% of target."""
        stage = self._make_stage()
        target = 1000
        long_content = "长" * 1600  # 1600 chars > 1500 (150% of 1000)
        issues = stage._check_word_count(long_content, target)
        assert len(issues) == 1
        assert issues[0]["type"] == "word_count"
        assert "偏多" in issues[0]["message"]

    def test_word_count_check_acceptable(self):
        """_check_word_count returns no issues for content within 50%–150% range."""
        stage = self._make_stage()
        target = 1000
        acceptable_content = "字" * 800  # 800 chars is within [500, 1500]
        issues = stage._check_word_count(acceptable_content, target)
        assert issues == []

    def test_review_run_annotates_chapters(self):
        """ReviewStage.run() adds review_issues to every chapter dict."""
        stage = self._make_stage()
        good_content = "好的内容。" * 200  # ~1000 chars, no forbidden words
        state = _make_state(
            chapters=[{"chapter_num": 1, "content": good_content}],
        )

        result_state = stage.run(state)

        assert "review_issues" in result_state.chapters[0]

    def test_review_no_loops(self):
        """ReviewStage.run() is called exactly once — no internal retry loop."""
        stage = self._make_stage()
        content = "测试内容。" * 200
        state = _make_state(
            chapters=[
                {"chapter_num": 1, "content": content},
                {"chapter_num": 2, "content": content},
            ],
        )

        # Spy on the individual checker to count invocations
        call_count = {"n": 0}
        original_check = stage._check_forbidden_words

        def counting_check(c):
            call_count["n"] += 1
            return original_check(c)

        stage._check_forbidden_words = counting_check  # type: ignore[method-assign]
        stage.run(state)

        # Called exactly once per chapter (2 chapters → 2 calls)
        assert call_count["n"] == 2

    def test_review_validate_input_empty_chapters(self):
        """validate_input returns False when state.chapters is empty."""
        stage = self._make_stage()
        state = _make_state(chapters=[])
        assert stage.validate_input(state) is False

    def test_review_validate_input_with_chapters(self):
        """validate_input returns True when at least one chapter is present."""
        stage = self._make_stage()
        state = _make_state(chapters=[{"chapter_num": 1, "content": "content"}])
        assert stage.validate_input(state) is True


# ---------------------------------------------------------------------------
# TestEvaluateStage
# ---------------------------------------------------------------------------

class TestEvaluateStage:
    """Tests for EvaluateStage LLM-based outline evaluation."""

    def _make_stage(self, llm_response: str = "") -> EvaluateStage:
        llm = _make_llm()
        llm.chat.return_value = llm_response
        return EvaluateStage(name="evaluate", llm=llm)

    def _passing_response(self) -> str:
        """Build a JSON LLM response where all criteria score 8 (avg 8.0 > 6.5)."""
        payload = {
            "plot_coherence": 8,
            "character_development": 8,
            "pacing": 8,
            "originality": 8,
            "comments": {
                "plot_coherence": "Well structured.",
                "character_development": "Characters feel real.",
                "pacing": "Good rhythm.",
                "originality": "Fresh premise.",
            },
        }
        return json.dumps(payload)

    def _failing_response(self) -> str:
        """Build a JSON LLM response where all criteria score 5 (avg 5.0 < 6.5)."""
        payload = {
            "plot_coherence": 5,
            "character_development": 5,
            "pacing": 5,
            "originality": 5,
            "comments": {
                "plot_coherence": "Needs work.",
                "character_development": "Thin characters.",
                "pacing": "Uneven.",
                "originality": "Derivative.",
            },
        }
        return json.dumps(payload)

    def _make_state_with_plot(self) -> PipelineState:
        return _make_state(
            plot_data={
                "main_strand": "Hero rises from humble origins to save the realm.",
                "chapters": [{"title": "Awakening", "summary": "The hero discovers power."}],
            }
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_passing_evaluation(self):
        """EvaluateStage sets evaluation_passed=True when avg score > 6.5."""
        stage = self._make_stage(llm_response=self._passing_response())
        state = self._make_state_with_plot()

        result = stage.run(state)

        assert result.evaluation_passed is True
        assert result.outline_evaluation["passed"] is True
        assert result.outline_evaluation["average_score"] >= _PASS_THRESHOLD

    def test_failing_evaluation(self):
        """EvaluateStage sets evaluation_passed=False when avg score < 6.5."""
        stage = self._make_stage(llm_response=self._failing_response())
        state = self._make_state_with_plot()

        result = stage.run(state)

        assert result.evaluation_passed is False
        assert result.outline_evaluation["passed"] is False
        assert result.outline_evaluation["average_score"] < _PASS_THRESHOLD

    def test_evaluation_result_stored_on_state(self):
        """outline_evaluation dict always has average_score, passed, and pass_threshold."""
        stage = self._make_stage(llm_response=self._passing_response())
        state = self._make_state_with_plot()

        result = stage.run(state)

        ev = result.outline_evaluation
        assert "average_score" in ev
        assert "passed" in ev
        assert "pass_threshold" in ev
        assert ev["pass_threshold"] == _PASS_THRESHOLD

    def test_evaluate_validate_input_empty_plot_data(self):
        """validate_input returns False when state.plot_data is empty."""
        stage = self._make_stage()
        state = _make_state(plot_data={})
        assert stage.validate_input(state) is False

    def test_evaluate_validate_input_with_plot_data(self):
        """validate_input returns True when state.plot_data is non-empty."""
        stage = self._make_stage()
        state = _make_state(plot_data={"main_strand": "Something."})
        assert stage.validate_input(state) is True

    def test_evaluate_run_raises_when_plot_data_empty(self):
        """run() raises ValueError when plot_data is empty (guard clause)."""
        stage = self._make_stage()
        state = _make_state(plot_data={})
        with pytest.raises(ValueError, match="Input validation failed"):
            stage.run(state)

    def test_evaluate_single_pass_no_loop(self):
        """EvaluateStage calls _call_llm exactly once — no retry loop."""
        stage = self._make_stage(llm_response=self._failing_response())
        state = self._make_state_with_plot()

        with patch.object(stage, "_call_llm", wraps=stage._call_llm) as mock_call:
            stage.run(state)
            assert mock_call.call_count == 1

    def test_evaluate_handles_malformed_llm_response(self):
        """Malformed LLM JSON falls back gracefully; state is still updated."""
        stage = self._make_stage(llm_response="This is not JSON at all.")
        state = self._make_state_with_plot()

        result = stage.run(state)

        # Should not raise; raw_response key indicates graceful fallback
        assert "raw_response" in result.outline_evaluation
        # Scores default to 0 → average 0.0 < threshold → not passed
        assert result.evaluation_passed is False
