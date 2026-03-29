"""Content quality evaluation for novel generation.

Provides RuleBasedEvaluator, LLMasJudgeEvaluator, and pass@k metrics.
"""
from .metrics import (
    QualityLevel,
    ContentReward,
    ContentMetrics,
    PassAtK,
    pass_at_k,
    calculate_pass_at_k,
    estimate_pass_at_k,
    compute_reward_from_metrics,
    aggregate_rewards,
)
from .evaluator import (
    EvaluatorType,
    EvaluationConfig,
    EvaluationResult,
    ContentEvaluator,
    RuleBasedEvaluator,
    LLMasJudgeEvaluator,
    create_evaluator,
)

__all__ = [
    # Metrics
    "QualityLevel",
    "ContentReward",
    "ContentMetrics",
    "PassAtK",
    "pass_at_k",
    "calculate_pass_at_k",
    "estimate_pass_at_k",
    "compute_reward_from_metrics",
    "aggregate_rewards",
    # Evaluator
    "EvaluatorType",
    "EvaluationConfig",
    "EvaluationResult",
    "ContentEvaluator",
    "RuleBasedEvaluator",
    "LLMasJudgeEvaluator",
    "create_evaluator",
]