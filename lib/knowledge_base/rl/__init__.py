"""
RL Self-Evolution Module for Young-Writer

基于 OpenYoung 的 RL 实现，为 young-writer 项目提供强化学习自我进化机制。

Features:
- COLLECTION_ONLY 模式 - 仅收集经验，无训练
- GRPO 引擎 - 组内相对排名 advantage
- GiGPO 引擎 - 两层优势估计（episode + step）

Usage:
    from knowledge_base.rl import RLEngine, RLConfig

    config = RLConfig(mode="COLLECTION_ONLY")
    engine = RLEngine(config)

    # Collect experience
    engine.collect_experience(task_id, content, reward)

    # Train step (only in GRPO/GiGPO mode)
    engine.train_step()
"""

from .config import RLConfig, RLMode
from .engine import RLEngine
from .experience import Experience, ExperienceBatch, StepData
from .grpo_engine import GRPOEngine
from .rewards import (
    NovelRewardFunction,
    RewardWeights,
    compute_novel_reward,
)
from .store import ExperienceStore

__all__ = [
    "RLConfig",
    "RLMode",
    "RLEngine",
    "Experience",
    "ExperienceBatch",
    "StepData",
    "GRPOEngine",
    "ExperienceStore",
    "NovelRewardFunction",
    "RewardWeights",
    "compute_novel_reward",
]
