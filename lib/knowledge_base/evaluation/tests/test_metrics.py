"""Tests for pass@k metrics and reward functions."""

import pytest
import sys
sys.path.insert(0, '..')

from evaluation.metrics import (
    ContentReward,
    ContentMetrics,
    PassAtK,
    QualityLevel,
    pass_at_k,
    calculate_pass_at_k,
    estimate_pass_at_k,
    compute_reward_from_metrics,
    aggregate_rewards,
)


class TestPassAtK:
    """Tests for pass@k calculation."""

    def test_pass_at_k_basic(self):
        """Test basic pass@k calculation."""
        # 30% success rate
        assert abs(pass_at_k(0.3, 1) - 0.3) < 0.001
        assert abs(pass_at_k(0.3, 3) - 0.657) < 0.001
        assert abs(pass_at_k(0.3, 5) - 0.83193) < 0.001

    def test_pass_at_k_edge_cases(self):
        """Test edge cases."""
        # 0% success rate
        assert pass_at_k(0.0, 1) == 0.0
        assert pass_at_k(0.0, 10) == 0.0

        # 100% success rate
        assert pass_at_k(1.0, 1) == 1.0
        assert pass_at_k(1.0, 10) == 1.0

    def test_pass_at_k_invalid_input(self):
        """Test invalid input raises error."""
        with pytest.raises(ValueError):
            pass_at_k(-0.1, 5)
        with pytest.raises(ValueError):
            pass_at_k(1.1, 5)
        with pytest.raises(ValueError):
            pass_at_k(0.5, 0)

    def test_calculate_pass_at_k(self):
        """Test calculate_pass_at_k from boolean results."""
        # 10 samples, 3 successes (30% rate)
        results = [True, False, False, True, False, False, True, False, False, False]
        result = calculate_pass_at_k(results, k_values=[1, 3, 5])

        assert result.total_samples == 10
        assert result.successful_samples == 3
        assert abs(result.success_rate - 0.3) < 0.001
        assert abs(result.pass_at_1 - 0.3) < 0.001
        assert abs(result.pass_at_3 - 0.657) < 0.001

    def test_calculate_pass_at_k_empty(self):
        """Test empty results."""
        result = calculate_pass_at_k([])
        assert result.total_samples == 0
        assert result.success_rate == 0.0


class TestContentReward:
    """Tests for ContentReward dataclass."""

    def test_reward_total_calculation(self):
        """Test total reward is weighted sum."""
        reward = ContentReward(
            task_completion=1.0,
            evaluation=1.0,
            efficiency=1.0,
            coherence=1.0,
            character_consistency=1.0,
            dialogue_quality=1.0,
            plot_progression=1.0,
            emotional_resonance=1.0,
        )

        # All components at 1.0 should give total of 1.0
        assert abs(reward.total - 1.0) < 0.001

    def test_reward_to_dict(self):
        """Test reward to_dict conversion."""
        reward = ContentReward(task_completion=0.8, coherence=0.6)
        d = reward.to_dict()

        assert 'task_completion' in d
        assert 'coherence' in d
        assert 'total' in d
        assert d['task_completion'] == 0.8


class TestContentMetrics:
    """Tests for ContentMetrics dataclass."""

    def test_is_passed(self):
        """Test is_passed property."""
        metrics = ContentMetrics(overall_score=0.75, pass_threshold=0.7)
        assert metrics.is_passed is True

        metrics = ContentMetrics(overall_score=0.65, pass_threshold=0.7)
        assert metrics.is_passed is False

    def test_quality_level_determination(self):
        """Test quality level from score."""
        from evaluation.evaluator import RuleBasedEvaluator

        evaluator = RuleBasedEvaluator()

        # Test EXCELLENT threshold
        assert evaluator._determine_quality_level(0.95) == QualityLevel.EXCELLENT
        # Test GOOD threshold
        assert evaluator._determine_quality_level(0.85) == QualityLevel.GOOD
        # Test ACCEPTABLE threshold
        assert evaluator._determine_quality_level(0.75) == QualityLevel.ACCEPTABLE
        # Test POOR threshold
        assert evaluator._determine_quality_level(0.60) == QualityLevel.POOR
        # Test FAIL threshold
        assert evaluator._determine_quality_level(0.30) == QualityLevel.FAIL


class TestComputeReward:
    """Tests for reward computation from metrics."""

    def test_compute_reward_from_metrics(self):
        """Test converting metrics to reward."""
        metrics = ContentMetrics(
            overall_score=0.8,
            coherence_score=0.7,
            character_consistency_score=0.9,
            dialogue_quality_score=0.6,
            plot_coherence_score=0.8,
            emotional_depth_score=0.7,
            language_quality_score=0.8,
        )

        reward = compute_reward_from_metrics(metrics)

        assert reward.task_completion == 0.8
        assert reward.evaluation == 0.8
        assert reward.coherence == 0.7
        assert reward.character_consistency == 0.9

    def test_aggregate_rewards(self):
        """Test aggregating multiple rewards."""
        rewards = [
            ContentReward(task_completion=0.8, coherence=0.7),
            ContentReward(task_completion=0.6, coherence=0.9),
            ContentReward(task_completion=0.7, coherence=0.8),
        ]

        aggregated = aggregate_rewards(rewards)

        assert abs(aggregated.task_completion - 0.7) < 0.001
        assert abs(aggregated.coherence - 0.8) < 0.001

    def test_aggregate_rewards_empty(self):
        """Test aggregating empty list."""
        aggregated = aggregate_rewards([])
        assert aggregated.task_completion == 0.0
        assert aggregated.coherence == 0.0
