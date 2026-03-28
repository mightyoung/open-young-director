"""RL Configuration Module

强化学习配置模块，定义 RL 自我进化机制的各项配置参数。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RLMode(str, Enum):
    """RL 模式枚举

    - COLLECTION_ONLY: 仅收集经验，不进行训练
    - GRPO: 组内相对排名优化 (Group Relative Policy Optimization)
    - GIGPO: 双层 GRPO (Episode + Step 两层优势估计)
    """

    COLLECTION_ONLY = "COLLECTION_ONLY"
    GRPO = "GRPO"
    GIGPO = "GIGPO"


@dataclass
class RLConfig:
    """RL 配置文件

    Attributes:
        enabled: 是否启用 RL 机制
        mode: RL 模式 (COLLECTION_ONLY, GRPO, GIGPO)
        group_size: 组内样本数量，用于 GRPO 优势计算
        learning_rate: 学习率
        clip_epsilon: PPO 裁剪系数
        max_experiences: 最大经验存储数量
        train_interval: 训练间隔（多少次收集后进行一次训练）
        reward_weights: 奖励权重配置
        checkpoint_dir: 检查点保存目录
        experiment_name: 实验名称
    """

    enabled: bool = True
    mode: RLMode = RLMode.COLLECTION_ONLY
    group_size: int = 4
    learning_rate: float = 1e-5
    clip_epsilon: float = 0.2
    max_experiences: int = 10000
    train_interval: int = 8
    checkpoint_dir: str = ".young/rl_checkpoints"
    experiment_name: str = "young_writer_rl"

    # GiGPO specific settings
    episode_gae_lambda: float = 0.95
    step_gae_lambda: float = 0.9
    value_coef: float = 0.5
    entropy_coef: float = 0.01

    # Logging
    log_level: str = "INFO"
    verbose: bool = False


@dataclass
class RewardWeights:
    """小说生成奖励权重配置

    用于平衡不同维度的奖励信号。
    """

    # 任务完成度权重
    task_completion: float = 0.25

    # 评估分数权重
    evaluation: float = 0.20

    # 效率权重
    efficiency: float = 0.05

    # 连贯性权重
    coherence: float = 0.15

    # 人物一致性权重
    character_consistency: float = 0.15

    # 对话质量权重
    dialogue_quality: float = 0.10

    # 情节发展权重
    plot_progression: float = 0.05

    # 情感共鸣权重
    emotional_resonance: float = 0.05

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_completion": self.task_completion,
            "evaluation": self.evaluation,
            "efficiency": self.efficiency,
            "coherence": self.coherence,
            "character_consistency": self.character_consistency,
            "dialogue_quality": self.dialogue_quality,
            "plot_progression": self.plot_progression,
            "emotional_resonance": self.emotional_resonance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RewardWeights":
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class ModelConfig:
    """模型配置

    用于 GRPO 更新的策略模型配置。
    由于 young-writer 主要使用 LLM API，此配置主要用于记录和兼容性。
    """

    model_name: str = "default"
    model_type: str = "api"  # api, local, checkpoint
    checkpoint_path: Optional[str] = None
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 4096

    # 策略更新相关
    use_lora: bool = True
    lora_rank: int = 8
    lora_alpha: float = 16.0


def default_rl_config() -> RLConfig:
    """创建默认 RL 配置"""
    return RLConfig(
        enabled=True,
        mode=RLMode.COLLECTION_ONLY,
        group_size=4,
        learning_rate=1e-5,
        clip_epsilon=0.2,
        max_experiences=10000,
        train_interval=8,
    )


def grpo_config() -> RLConfig:
    """创建 GRPO 模式配置"""
    return RLConfig(
        enabled=True,
        mode=RLMode.GRPO,
        group_size=4,
        learning_rate=1e-5,
        clip_epsilon=0.2,
        max_experiences=10000,
        train_interval=4,
    )


def gigpo_config() -> RLConfig:
    """创建 GiGPO 模式配置"""
    return RLConfig(
        enabled=True,
        mode=RLMode.GIGPO,
        group_size=4,
        learning_rate=5e-6,
        clip_epsilon=0.15,
        max_experiences=10000,
        train_interval=4,
        episode_gae_lambda=0.95,
        step_gae_lambda=0.9,
        value_coef=0.5,
        entropy_coef=0.01,
    )
