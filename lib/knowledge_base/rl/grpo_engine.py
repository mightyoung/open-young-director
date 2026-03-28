"""GRPO Engine

组内相对排名优化 (Group Relative Policy Optimization) 实现。

GRPO 是一种简化的 RL 算法，核心思想：
1. 对于同一个任务，生成 group_size 个响应
2. 计算组内每个响应的相对排名 advantage
3. 使用 PPO-style 裁剪更新策略

参考: DeepSeek-R1 的 GRPO 方法
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .config import RLConfig, RLMode
from .experience import Experience, ExperienceBatch, StepData, TrainingStats
from .store import ExperienceStore


class GRPOEngine:
    """GRPO 引擎

    实现组内相对排名优化的核心逻辑。
    """

    def __init__(
        self,
        config: RLConfig,
        store: Optional[ExperienceStore] = None,
    ):
        """初始化 GRPO 引擎

        Args:
            config: RL 配置
            store: 经验存储
        """
        self.config = config
        self.store = store or ExperienceStore()
        self._train_step = 0

    def compute_advantages(self, batch: ExperienceBatch) -> List[float]:
        """计算组内相对排名 advantage

        使用相对排名而非绝对奖励来计算 advantage，减少异常值影响。

        Formula:
            advantage_i = (rank_i - 1) / (group_size - 1) * 2 - 1
            其中 rank_i 是组内排名（0 到 group_size-1）

        Args:
            batch: 经验批次

        Returns:
            各经验的 advantage 列表
        """
        if batch.size == 0:
            return []

        if batch.size == 1:
            return [0.0]

        # 按奖励排序 (从高到低)
        sorted_exps = sorted(batch.experiences, key=lambda e: e.reward, reverse=True)

        # 计算相对排名 advantage
        # 公式: advantage = 1 - 2 * (rank / (size - 1))
        # 最好 (rank=0) -> 1, 最差 (rank=size-1) -> -1
        advantages = []
        for i, exp in enumerate(sorted_exps):
            if batch.size > 1:
                rank_advantage = 1 - 2 * (i / (batch.size - 1))
            else:
                rank_advantage = 0.0
            advantages.append(rank_advantage)
            exp.advantage = rank_advantage
            exp.rank = i

        return advantages

    def normalize_advantages(self, advantages: List[float]) -> List[float]:
        """标准化 advantage

        使用均值和标准差进行标准化。

        Args:
            advantages: advantage 列表

        Returns:
            标准化后的 advantage 列表
        """
        if not advantages:
            return []

        adv_array = np.array(advantages)
        mean = np.mean(adv_array)
        std = np.std(adv_array)

        if std < 1e-8:
            return [0.0] * len(advantages)

        normalized = (adv_array - mean) / std
        return normalized.tolist()

    def compute_grpo_loss(
        self,
        old_log_probs: List[float],
        new_log_probs: List[float],
        advantages: List[float],
        clip_epsilon: float = 0.2,
    ) -> Tuple[float, float]:
        """计算 GRPO 损失

        使用 PPO-style 裁剪来限制策略更新幅度。

        L = -min(r * advantage, clip(r, 1-eps, 1+eps) * advantage)

        其中 r = exp(new_log_prob - old_log_prob)

        Args:
            old_log_probs: 旧策略的对数概率
            new_log_probs: 新策略的对数概率
            advantages: 优势
            clip_epsilon: 裁剪系数

        Returns:
            (损失, 裁剪比例)
        """
        if len(old_log_probs) != len(new_log_probs) or len(old_log_probs) != len(advantages):
            raise ValueError("Length mismatch between log probs and advantages")

        if not old_log_probs:
            return 0.0, 0.0

        # 计算概率比
        ratios = [np.exp(new - old) for new, old in zip(new_log_probs, old_log_probs)]

        # 计算裁剪比例
        clipped_ratios = [np.clip(r, 1 - clip_epsilon, 1 + clip_epsilon) for r in ratios]

        # 计算原始和裁剪目标的最小值
        surr1 = [r * adv for r, adv in zip(ratios, advantages)]
        surr2 = [clip_r * adv for clip_r, adv in zip(clipped_ratios, advantages)]

        # GRPO 损失
        losses = [-min(s1, s2) for s1, s2 in zip(surr1, surr2)]
        loss = np.mean(losses)

        # 计算裁剪比例（用于监控）
        clipped = [
            1 for r, clip_r in zip(ratios, clipped_ratios)
            if np.abs(r - clip_r) > 1e-6
        ]
        clip_fraction = len(clipped) / len(ratios) if ratios else 0.0

        return float(loss), float(clip_fraction)

    def train_step(
        self,
        experiences: List[Experience],
        old_log_probs: Optional[List[float]] = None,
    ) -> TrainingStats:
        """执行一次 GRPO 训练步骤

        Args:
            experiences: 经验列表
            old_log_probs: 旧策略对数概率（用于计算策略损失）

        Returns:
            训练统计
        """
        self._train_step += 1

        # 创建批次
        batch = ExperienceBatch(experiences=experiences)
        batch.group_id = str(uuid.uuid4())

        # 计算 advantage
        advantages = self.compute_advantages(batch)
        normalized_advantages = self.normalize_advantages(advantages)

        # 更新经验的 advantage
        for exp, norm_adv in zip(experiences, normalized_advantages):
            exp.advantage = norm_adv

        # 计算策略损失
        policy_loss = 0.0
        clip_fraction = 0.0

        if old_log_probs and len(old_log_probs) == len(experiences):
            # 模拟新策略的对数概率（实际需要调用模型）
            # 这里使用简单的扰动来模拟
            new_log_probs = [
                lp + np.random.normal(0, 0.1)
                for lp in old_log_probs
            ]
            policy_loss, clip_fraction = self.compute_grpo_loss(
                old_log_probs,
                new_log_probs,
                normalized_advantages,
                self.config.clip_epsilon,
            )

        # 创建训练统计
        rewards = [e.reward for e in experiences]
        stats = TrainingStats(
            step=self._train_step,
            timestamp=datetime.now(),
            policy_loss=policy_loss,
            total_loss=policy_loss,
            mean_advantage=np.mean(normalized_advantages) if normalized_advantages else 0.0,
            max_advantage=max(normalized_advantages) if normalized_advantages else 0.0,
            min_advantage=min(normalized_advantages) if normalized_advantages else 0.0,
            mean_reward=np.mean(rewards) if rewards else 0.0,
            max_reward=max(rewards) if rewards else 0.0,
            min_reward=min(rewards) if rewards else 0.0,
            learning_rate=self.config.learning_rate,
            clip_fraction=clip_fraction,
        )

        # 保存统计
        self.store.save_training_stats(stats.to_dict())

        return stats


class GiGPOEngine(GRPOEngine):
    """GiGPO 引擎

    两层 GRPO：Episode 层 + Step 层

    Episode 层:
    - 使用 GAE 计算每个 episode 的 advantage
    - 组内相对排名

    Step 层:
    - 对每个 episode 内的 step 使用 GAE
    - 更细粒度的优势估计
    """

    def __init__(
        self,
        config: RLConfig,
        store: Optional[ExperienceStore] = None,
    ):
        """初始化 GiGPO 引擎

        Args:
            config: RL 配置
            store: 经验存储
        """
        super().__init__(config, store)
        self.episode_gae_lambda = config.episode_gae_lambda
        self.step_gae_lambda = config.step_gae_lambda
        self.value_coef = config.value_coef
        self.entropy_coef = config.entropy_coef

    def compute_gae(
        self,
        rewards: List[float],
        values: List[float],
        next_values: List[float],
        dones: List[bool],
        gamma: float = 0.99,
        lambda_: float = 0.95,
    ) -> Tuple[List[float], List[float]]:
        """计算 GAE (Generalized Advantage Estimation)

        Args:
            rewards: 奖励列表
            values: 价值列表
            next_values: 下一状态价值列表
            dones: 是否结束列表
            gamma: 折扣因子
            lambda_: GAE 参数

        Returns:
            (advantages, value_targets)
        """
        advantages = [0.0] * len(rewards)
        value_targets = [0.0] * len(rewards)

        # 反向计算
        gae = 0.0
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = next_values[t] if t < len(next_values) else 0.0
            else:
                next_value = values[t + 1]

            delta = rewards[t] + gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + gamma * lambda_ * (1 - dones[t]) * gae
            advantages[t] = gae
            value_targets[t] = gae + values[t]

        return advantages, value_targets

    def compute_intrinsic_reward(
        self,
        experience: Experience,
        all_experiences: List[Experience],
    ) -> float:
        """计算内在奖励（ novelty bonus）

        基于与组内其他经验的差异来计算 novelty 奖励。

        Args:
            experience: 当前经验
            all_experiences: 所有经验

        Returns:
            内在奖励
        """
        if len(all_experiences) <= 1:
            return 0.0

        # 简单的文本相似度（使用长度差异）
        target_len = np.mean([len(e.content) for e in all_experiences])
        len_diff = abs(len(experience.content) - target_len)
        novelty = np.exp(-len_diff / 1000)

        return novelty * 0.1  # 小的 novelty 奖励

    def gigpo_train_step(
        self,
        experiences: List[Experience],
        old_log_probs: Optional[List[float]] = None,
    ) -> TrainingStats:
        """执行一次 GiGPO 训练步骤

        结合 Episode 层和 Step 层的优势估计。

        Args:
            experiences: 经验列表
            old_log_probs: 旧策略对数概率

        Returns:
            训练统计
        """
        self._train_step += 1

        # Episode 层: 计算组内相对排名 advantage
        batch = ExperienceBatch(experiences=experiences)
        batch.group_id = str(uuid.uuid4())
        episode_advantages = self.compute_advantages(batch)
        episode_advantages = self.normalize_advantages(episode_advantages)

        # Step 层: 对每个 episode 内的 step 计算 GAE
        all_step_advantages = []
        all_step_rewards = []
        policy_losses = []

        for i, exp in enumerate(experiences):
            # 计算内在奖励
            intrinsic_reward = self.compute_intrinsic_reward(exp, experiences)
            exp.reward += intrinsic_reward

            if exp.steps:
                # 从步骤数据提取信息
                step_rewards = [s.reward for s in exp.steps]
                step_values = [s.value for s in exp.steps]

                # 计算 step 层 GAE
                next_values = step_values[1:] + [0.0]
                dones = [False] * len(step_rewards)  # 假设非终止

                step_advantages, _ = self.compute_gae(
                    step_rewards,
                    step_values,
                    next_values,
                    dones,
                    lambda_=self.step_gae_lambda,
                )

                all_step_advantages.extend(step_advantages)
                all_step_rewards.extend(step_rewards)

                # 更新步骤的 advantage
                for step, adv in zip(exp.steps, step_advantages):
                    step.advantage = adv
            else:
                # 如果没有步骤数据，使用 episode advantage
                all_step_advantages.append(episode_advantages[i])
                all_step_rewards.append(exp.reward)

            # 更新 episode 的 advantage
            exp.advantage = episode_advantages[i]

        # 计算策略损失
        policy_loss = 0.0
        clip_fraction = 0.0

        if old_log_probs and len(old_log_probs) == len(experiences):
            new_log_probs = [
                lp + np.random.normal(0, 0.1)
                for lp in old_log_probs
            ]
            policy_loss, clip_fraction = self.compute_grpo_loss(
                old_log_probs,
                new_log_probs,
                episode_advantages,
                self.config.clip_epsilon,
            )

        # 计算价值损失（简化版）
        value_loss = 0.0
        if all_step_values := [s.value for e in experiences for s in e.steps]:
            value_targets = [
                adv + val for adv, val in zip(all_step_advantages, all_step_values)
            ]
            value_loss = np.mean([
                (vt - val) ** 2
                for vt, val in zip(value_targets, all_step_values)
            ]) * self.value_coef

        # 创建训练统计
        rewards = [e.reward for e in experiences]
        stats = TrainingStats(
            step=self._train_step,
            timestamp=datetime.now(),
            policy_loss=policy_loss,
            value_loss=value_loss,
            total_loss=policy_loss + value_loss,
            mean_advantage=np.mean(episode_advantages) if episode_advantages else 0.0,
            max_advantage=max(episode_advantages) if episode_advantages else 0.0,
            min_advantage=min(episode_advantages) if episode_advantages else 0.0,
            mean_reward=np.mean(rewards) if rewards else 0.0,
            max_reward=max(rewards) if rewards else 0.0,
            min_reward=min(rewards) if rewards else 0.0,
            learning_rate=self.config.learning_rate,
            clip_fraction=clip_fraction,
        )

        self.store.save_training_stats(stats.to_dict())

        return stats


def create_grpo_engine(config: RLConfig, store: Optional[ExperienceStore] = None) -> GRPOEngine:
    """创建 GRPO 引擎工厂函数

    Args:
        config: RL 配置
        store: 经验存储

    Returns:
        GRPO 或 GiGPO 引擎实例
    """
    if config.mode == RLMode.GIGPO:
        return GiGPOEngine(config, store)
    else:
        return GRPOEngine(config, store)
