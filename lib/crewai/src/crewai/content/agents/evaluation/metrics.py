"""pass@k metrics and multi-dimensional reward functions for novel content generation.

基于 openyoung 的 pass@k 指标体系，设计适合小说内容生成的评估指标。

Formula Reference:
    pass@k = 1 - (1-s)^k  # s = 成功率 (success rate)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import math
import numpy as np


class QualityLevel(Enum):
    """内容质量等级 (Content quality levels)."""
    EXCELLENT = "excellent"      # 优秀：达到专业发表标准
    GOOD = "good"               # 良好：达到发布标准
    ACCEPTABLE = "acceptable"   # 可接受：需要少量修改
    POOR = "poor"               # 较差：需要大量修改
    FAIL = "fail"               # 不合格：无法使用


@dataclass
class ContentReward:
    """多维度奖励结构 (Multi-dimensional reward structure).

    参考 openyoung 的 ContentReward 设计，扩展适用于小说内容生成。
    """
    # 任务完成奖励 (Task completion reward)
    # - 1.0: 完全符合任务要求
    # - 0.0-1.0: 部分完成
    task_completion: float = 0.0

    # 评估分数奖励 (Evaluation score reward)
    # - 基于规则评估的综合分数
    evaluation: float = 0.0

    # 效率奖励 (Efficiency reward)
    # - 基于生成效率（字数/时间/成本）
    efficiency: float = 0.0

    # 连贯性奖励 (Coherence reward)
    # - 叙事连贯性评分
    coherence: float = 0.0

    # 人物一致性奖励 (Character consistency reward)
    # - 人物言行一致性评分
    character_consistency: float = 0.0

    # 对话质量奖励 (Dialogue quality reward)
    dialogue_quality: float = 0.0

    # 情节发展奖励 (Plot progression reward)
    plot_progression: float = 0.0

    # 情感共鸣奖励 (Emotional resonance reward)
    emotional_resonance: float = 0.0

    @property
    def total(self) -> float:
        """计算总奖励 (Calculate total reward)."""
        return (
            self.task_completion * 0.25 +
            self.evaluation * 0.20 +
            self.efficiency * 0.05 +
            self.coherence * 0.15 +
            self.character_consistency * 0.15 +
            self.dialogue_quality * 0.10 +
            self.plot_progression * 0.05 +
            self.emotional_resonance * 0.05
        )

    def to_dict(self) -> Dict[str, float]:
        """转换为字典 (Convert to dictionary)."""
        return {
            "task_completion": self.task_completion,
            "evaluation": self.evaluation,
            "efficiency": self.efficiency,
            "coherence": self.coherence,
            "character_consistency": self.character_consistency,
            "dialogue_quality": self.dialogue_quality,
            "plot_progression": self.plot_progression,
            "emotional_resonance": self.emotional_resonance,
            "total": self.total,
        }


@dataclass
class ContentMetrics:
    """内容评估指标 (Content evaluation metrics)."""
    # 质量等级 (Quality level)
    quality_level: QualityLevel = QualityLevel.FAIL

    # 各维度分数 (Dimension scores) - 0.0 to 1.0
    coherence_score: float = 0.0
    character_consistency_score: float = 0.0
    dialogue_quality_score: float = 0.0
    plot_coherence_score: float = 0.0
    emotional_depth_score: float = 0.0
    language_quality_score: float = 0.0

    # 综合分数 (Overall score) - 0.0 to 1.0
    overall_score: float = 0.0

    # 通过阈值 (Pass threshold) - 达到此分数视为通过
    pass_threshold: float = 0.7

    @property
    def is_passed(self) -> bool:
        """是否通过质量标准 (Whether passed quality standards)."""
        return self.overall_score >= self.pass_threshold

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (Convert to dictionary)."""
        return {
            "quality_level": self.quality_level.value,
            "coherence_score": self.coherence_score,
            "character_consistency_score": self.character_consistency_score,
            "dialogue_quality_score": self.dialogue_quality_score,
            "plot_coherence_score": self.plot_coherence_score,
            "emotional_depth_score": self.emotional_depth_score,
            "language_quality_score": self.language_quality_score,
            "overall_score": self.overall_score,
            "pass_threshold": self.pass_threshold,
            "is_passed": self.is_passed,
        }


@dataclass
class PassAtK:
    """pass@k 评估结果 (pass@k evaluation result).

    pass@k 表示在 k 次生成尝试中至少有一次成功的概率。
    Formula: pass@k = 1 - (1-s)^k
    其中 s 是单次尝试的成功率。
    """
    # pass@1, pass@3, pass@5, pass@10 等
    k_values: List[int] = field(default_factory=lambda: [1, 3, 5, 10])

    # 各 k 值对应的 pass@k 分数
    scores: Dict[int, float] = field(default_factory=dict)

    # 样本数量 (Number of samples)
    total_samples: int = 0

    # 成功数量 (Number of successes)
    successful_samples: int = 0

    # 成功率 (Success rate)
    success_rate: float = 0.0

    @property
    def pass_at_1(self) -> float:
        """pass@1 分数 (pass@1 score)."""
        return self.scores.get(1, 0.0)

    @property
    def pass_at_3(self) -> float:
        """pass@3 分数 (pass@3 score)."""
        return self.scores.get(3, 0.0)

    @property
    def pass_at_5(self) -> float:
        """pass@5 分数 (pass@5 score)."""
        return self.scores.get(5, 0.0)

    @property
    def pass_at_10(self) -> float:
        """pass@10 分数 (pass@10 score)."""
        return self.scores.get(10, 0.0)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (Convert to dictionary)."""
        return {
            "k_values": self.k_values,
            "scores": self.scores,
            "total_samples": self.total_samples,
            "successful_samples": self.successful_samples,
            "success_rate": self.success_rate,
        }


def pass_at_k(success_rate: float, k: int) -> float:
    """计算 pass@k 值 (Calculate pass@k value).

    Formula: pass@k = 1 - (1-s)^k

    Args:
        success_rate: 单次尝试的成功率 (Single attempt success rate) - 0.0 to 1.0
        k: 尝试次数 (Number of attempts)

    Returns:
        pass@k 分数 (pass@k score) - 0.0 to 1.0

    Example:
        >>> pass_at_k(0.3, 5)
        0.83193
    """
    if not 0.0 <= success_rate <= 1.0:
        raise ValueError(f"success_rate must be between 0.0 and 1.0, got {success_rate}")
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")

    return 1.0 - math.pow(1.0 - success_rate, k)


def calculate_pass_at_k(
    results: List[bool],
    k_values: List[int] = None
) -> PassAtK:
    """从布尔结果列表计算 pass@k (Calculate pass@k from boolean results list).

    Args:
        results: 每个生成的结果列表，True 表示通过质量标准 (List of generation results, True means passed quality standards)
        k_values: 要计算的 k 值列表 (List of k values to calculate)

    Returns:
        PassAtK 对象 (PassAtK object)

    Example:
        >>> results = [True, False, True, False, False] * 4  # 20 samples, 40% success rate
        >>> pass_at_k = calculate_pass_at_k(results, k_values=[1, 3, 5, 10])
        >>> pass_at_k.pass_at_3
        0.784
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    total_samples = len(results)
    if total_samples == 0:
        return PassAtK(
            k_values=k_values,
            scores={k: 0.0 for k in k_values},
            total_samples=0,
            successful_samples=0,
            success_rate=0.0,
        )

    successful_samples = sum(1 for r in results if r)
    success_rate = successful_samples / total_samples

    scores = {}
    for k in k_values:
        scores[k] = pass_at_k(success_rate, k)

    return PassAtK(
        k_values=k_values,
        scores=scores,
        total_samples=total_samples,
        successful_samples=successful_samples,
        success_rate=success_rate,
    )


def estimate_pass_at_k(
    n_samples: int,
    n_successes: int,
    k_values: List[int] = None,
    confidence: float = 0.95
) -> Tuple[PassAtK, Tuple[float, float]]:
    """使用有限样本估计 pass@k 及其置信区间 (Estimate pass@k with confidence interval from finite samples).

    使用贝叶斯估计（Beta 分布）来计算 pass@k 的置信区间。

    Args:
        n_samples: 总样本数 (Total number of samples)
        n_successes: 成功样本数 (Number of successful samples)
        k_values: 要计算的 k 值列表 (List of k values to calculate)
        confidence: 置信水平 (Confidence level) - 默认 95%

    Returns:
        (PassAtK 对象, (下界, 上界)) (Tuple of (PassAtK object, (lower_bound, upper_bound)))

    Example:
        >>> pass_at_k, (lower, upper) = estimate_pass_at_k(20, 8, k_values=[1, 3, 5])
        >>> print(f"pass@3: {pass_at_k.pass_at_3:.3f} ({lower:.3f}-{upper:.3f})")
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    # 成功率点估计 (Point estimate of success rate)
    success_rate = n_successes / n_samples if n_samples > 0 else 0.0

    # 使用 Beta 分布计算置信区间
    # Beta(α, β) 其中 α = n_successes + 1, β = n_failures + 1
    alpha = n_successes + 1
    beta = (n_samples - n_successes) + 1

    # 计算置信区间 (使用 beta.ppf)
    from scipy import stats
    lower = stats.beta.ppf((1 - confidence) / 2, alpha, beta)
    upper = stats.beta.ppf((1 + confidence) / 2, alpha, beta)

    # 计算各 k 值的 pass@k
    scores = {}
    for k in k_values:
        scores[k] = pass_at_k(success_rate, k)

    pass_at_k_result = PassAtK(
        k_values=k_values,
        scores=scores,
        total_samples=n_samples,
        successful_samples=n_successes,
        success_rate=success_rate,
    )

    # 计算置信区间边界
    lower_bound = pass_at_k(lower, max(k_values))
    upper_bound = pass_at_k(upper, max(k_values))

    return pass_at_k_result, (lower_bound, upper_bound)


def compute_reward_from_metrics(metrics: ContentMetrics) -> ContentReward:
    """从内容指标计算奖励 (Compute reward from content metrics).

    将 ContentMetrics 转换为 ContentReward，权重可配置。

    Args:
        metrics: 内容评估指标 (Content evaluation metrics)

    Returns:
        ContentReward 对象 (ContentReward object)
    """
    return ContentReward(
        task_completion=metrics.overall_score,
        evaluation=metrics.overall_score,
        coherence=metrics.coherence_score,
        character_consistency=metrics.character_consistency_score,
        dialogue_quality=metrics.dialogue_quality_score,
        plot_progression=metrics.plot_coherence_score,
        emotional_resonance=metrics.emotional_depth_score,
        efficiency=1.0,  # 效率暂不评估，默认满分
    )


def aggregate_rewards(rewards: List[ContentReward]) -> ContentReward:
    """聚合多个奖励为平均奖励 (Aggregate multiple rewards into average reward).

    Args:
        rewards: 奖励列表 (List of rewards)

    Returns:
        平均奖励 (Average reward)
    """
    if not rewards:
        return ContentReward()

    n = len(rewards)
    return ContentReward(
        task_completion=sum(r.task_completion for r in rewards) / n,
        evaluation=sum(r.evaluation for r in rewards) / n,
        efficiency=sum(r.efficiency for r in rewards) / n,
        coherence=sum(r.coherence for r in rewards) / n,
        character_consistency=sum(r.character_consistency for r in rewards) / n,
        dialogue_quality=sum(r.dialogue_quality for r in rewards) / n,
        plot_progression=sum(r.plot_progression for r in rewards) / n,
        emotional_resonance=sum(r.emotional_resonance for r in rewards) / n,
    )
