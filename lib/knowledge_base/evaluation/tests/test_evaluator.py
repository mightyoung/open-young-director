"""Tests for content evaluator."""

import pytest
import sys
sys.path.insert(0, '..')

from evaluation.evaluator import (
    RuleBasedEvaluator,
    EvaluationResult,
    EvaluationConfig,
    EvaluatorType,
    QualityLevel,
)


class TestRuleBasedEvaluator:
    """Tests for RuleBasedEvaluator."""

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        return RuleBasedEvaluator()

    @pytest.fixture
    def good_content(self):
        """Good quality novel content."""
        return """
【张三丰】站在武当山顶，望着远处的云海。

\"无忌这孩子，资质的确不凡。\"他喃喃自语道。

片刻后，【张无忌】从山下走来，行礼道：\"太师父，弟子有困惑。\"

张三丰转过身，微笑道：\"说来听听。\"

张无忌道：\"弟子近日修炼九阳神功，总觉得有些地方无法突破。\"

张三丰点了点头，道：\"我知你所惑。来，我教你一套太极拳法。\"

说罢，他施展太极拳，招式行云流水，浑然天成。

张无忌仔细观看，心中若有所悟。
"""

    @pytest.fixture
    def poor_content(self):
        """Poor quality content with issues."""
        return """
张无忌。
"""

    def test_evaluate_good_content(self, evaluator, good_content):
        """Test evaluating good content."""
        result = evaluator.evaluate(good_content)

        # Check metrics are calculated (pass depends on threshold)
        assert result.metrics is not None
        assert result.metrics.overall_score > 0.5  # Should be at least mediocre
        assert result.error is None
        assert result.details['dialogue_quality'] > 0.7  # Good dialogue

    def test_evaluate_poor_content(self, evaluator, poor_content):
        """Test evaluating poor content."""
        result = evaluator.evaluate(poor_content)

        assert result.metrics is not None
        assert result.error is None

    def test_coherence_evaluation(self, evaluator, good_content):
        """Test coherence evaluation."""
        result = evaluator.evaluate(good_content)

        assert 'coherence' in result.details
        assert 0.0 <= result.details['coherence'] <= 1.0

    def test_character_extraction(self, evaluator):
        """Test character name extraction."""
        content = "【张无忌】和【张三丰】在武当山上。"
        characters = evaluator._extract_characters(content)

        assert '张无忌' in characters
        assert '张三丰' in characters

    def test_dialogue_quality(self, evaluator):
        """Test dialogue quality evaluation."""
        # Has good dialogue
        content_with_dialogue = """
张无忌道：\"太师父，这是怎么回事？\"
张三丰微微一笑：\"无忌，你且看好。\"
"""
        result = evaluator.evaluate(content_with_dialogue)
        assert result.details['dialogue_quality'] > 0.5

        # No dialogue
        content_no_dialogue = "张无忌在武当山上修炼。他的功力大增。"
        result = evaluator.evaluate(content_no_dialogue)
        assert result.details['dialogue_quality'] < 0.8

    def test_emotion_detection(self, evaluator):
        """Test emotion detection."""
        emotional_content = "张无忌心中大喜，高兴得手舞足蹈，却又突然悲伤起来。"
        score = evaluator._evaluate_emotional_depth(emotional_content)

        assert score > 0.5


class TestEvaluationConfig:
    """Tests for EvaluationConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = EvaluationConfig()

        assert config.pass_threshold == 0.7
        assert config.evaluator_type == EvaluatorType.RULE_BASED
        assert len(config.weights) == 6

    def test_custom_weights(self):
        """Test custom weights."""
        config = EvaluationConfig(
            weights={
                "coherence": 0.30,
                "character_consistency": 0.30,
                "dialogue_quality": 0.10,
                "plot_coherence": 0.10,
                "emotional_depth": 0.10,
                "language_quality": 0.10,
            }
        )

        assert config.weights["coherence"] == 0.30


class TestEvaluationResult:
    """Tests for EvaluationResult."""

    def test_to_dict(self):
        """Test converting result to dict."""
        result = EvaluationResult(
            content="Test content",
            passed=True,
        )

        d = result.to_dict()
        assert 'content' in d
        assert 'passed' in d
