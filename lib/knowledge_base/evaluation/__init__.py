"""Content evaluation framework for young-writer pass@k metrics.

This module provides:
- pass@k指标计算 (pass@k metric calculation)
- 多维度奖励函数 (multi-dimensional reward functions)
- 基于规则的内容质量评估器 (rule-based content quality evaluator)
- 可选的 LLM-as-Judge 评估器 (optional LLM-as-Judge evaluator)
- Grader 系统 (WEIGHTED/BINARY/HYBRID 评分模式)
"""

from evaluation.metrics import (
    ContentReward,
    ContentMetrics,
    PassAtK,
    pass_at_k,
    calculate_pass_at_k,
    estimate_pass_at_k,
)
from evaluation.evaluator import (
    ContentEvaluator,
    RuleBasedEvaluator,
    LLMasJudgeEvaluator,
    EvaluationResult,
    EvaluationConfig,
)
from evaluation.graders import (
    BaseGrader,
    GradeResult,
    GraderType,
    GradingMode,
    CodeGrader,
    ModelGrader,
)
from evaluation.grading import (
    GradingOrchestrator,
    GradingConfig,
    GradingReport,
    grade_content,
)

__all__ = [
    # metrics
    "ContentReward",
    "ContentMetrics",
    "PassAtK",
    "pass_at_k",
    "calculate_pass_at_k",
    "estimate_pass_at_k",
    # evaluator
    "ContentEvaluator",
    "RuleBasedEvaluator",
    "LLMasJudgeEvaluator",
    "EvaluationResult",
    "EvaluationConfig",
    # graders
    "BaseGrader",
    "GradeResult",
    "GraderType",
    "GradingMode",
    "CodeGrader",
    "ModelGrader",
    # grading
    "GradingOrchestrator",
    "GradingConfig",
    "GradingReport",
    "grade_content",
]
