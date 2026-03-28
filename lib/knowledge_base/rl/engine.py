"""RL Engine

RL 自我进化引擎主入口。

整合经验收集、奖励计算、策略更新等模块。
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .config import RLConfig, RLMode
from .experience import Experience, ExperienceBatch, ExperienceType, StepData
from .grpo_engine import GRPOEngine, GiGPOEngine, create_grpo_engine
from .rewards import NovelRewardFunction, RewardResult, RewardWeights, compute_novel_reward
from .store import ExperienceStore, get_experience_store


logger = logging.getLogger(__name__)


@dataclass
class RLEngineConfig:
    """RL 引擎配置"""

    rl_config: RLConfig
    reward_weights: Optional[RewardWeights] = None
    db_path: str = ".young/rl_experiences.db"


class RLEngine:
    """RL 自我进化引擎

    主要接口类，负责：
    1. 经验收集 (collect_experience)
    2. 奖励计算 (compute_reward)
    3. 训练步骤 (train_step)
    4. 经验回放 (replay)
    """

    def __init__(
        self,
        config: Optional[RLConfig] = None,
        db_path: str = ".young/rl_experiences.db",
        reward_weights: Optional[RewardWeights] = None,
    ):
        """初始化 RL 引擎

        Args:
            config: RL 配置
            db_path: 数据库路径
            reward_weights: 奖励权重
        """
        self.config = config or RLConfig()
        self.reward_weights = reward_weights or RewardWeights()
        self.store = ExperienceStore(db_path)

        # 初始化奖励函数
        self.reward_function = NovelRewardFunction(weights=self.reward_weights)

        # 初始化 GRPO 引擎
        self.grpo_engine = create_grpo_engine(self.config, self.store)

        # 训练统计
        self._collection_count = 0
        self._total_train_steps = 0

        # 回调函数
        self._on_experience_collected: Optional[Callable[[Experience], None]] = None
        self._on_train_step: Optional[Callable[[Dict[str, Any]], None]] = None

        logger.info(f"RL Engine initialized in {self.config.mode.value} mode")

    @property
    def mode(self) -> RLMode:
        """获取当前模式"""
        return self.config.mode

    @property
    def is_training_enabled(self) -> bool:
        """是否启用训练"""
        return self.config.mode in (RLMode.GRPO, RLMode.GIGPO)

    def set_experience_callback(
        self, callback: Callable[[Experience], None]
    ) -> None:
        """设置经验收集回调

        Args:
            callback: 回调函数，每次收集经验后调用
        """
        self._on_experience_collected = callback

    def set_train_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """设置训练回调

        Args:
            callback: 回调函数，每次训练后调用
        """
        self._on_train_step = callback

    def compute_reward(
        self,
        content: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> RewardResult:
        """计算奖励

        Args:
            content: 生成的内容
            prompt: 提示/指令
            context: 上下文信息

        Returns:
            奖励计算结果
        """
        ctx = context or {}
        return self.reward_function.compute(content, prompt, ctx)

    def collect_experience(
        self,
        task_id: str,
        content: str,
        reward: Optional[float] = None,
        prompt: Optional[str] = None,
        task_type: str = "chapter_generation",
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Experience:
        """收集经验

        主要接口：将生成的内容和奖励保存为经验。

        Args:
            task_id: 任务 ID
            content: 生成的内容
            reward: 奖励值（如果为 None，则自动计算）
            prompt: 提示/指令
            task_type: 任务类型
            context: 上下文信息
            metadata: 额外元数据

        Returns:
            创建的经验对象
        """
        ctx = context or {}

        # 计算奖励（如果未提供）
        if reward is None:
            reward_result = self.reward_function.compute(content, prompt or "", ctx)
            reward = reward_result.total
        else:
            reward_result = None

        # 创建经验
        experience = Experience(
            id=str(uuid.uuid4()),
            task_id=task_id,
            task_type=task_type,
            prompt=prompt or "",
            content=content,
            reward=reward,
            total_reward=reward,
            rewards=reward_result.to_dict() if reward_result else {},
            created_at=datetime.now(),
            exp_type=ExperienceType.EPISODE,
            metadata=metadata or {},
            model_name=ctx.get("model_name", "default"),
            temperature=ctx.get("temperature", 0.7),
            generation_params=ctx.get("generation_params", {}),
        )

        # 保存到存储
        self.store.save_experience(experience)
        self._collection_count += 1

        # 触发回调
        if self._on_experience_collected:
            self._on_experience_collected(experience)

        logger.debug(f"Collected experience {experience.id} with reward {reward:.4f}")

        return experience

    def collect_step_experience(
        self,
        task_id: str,
        step_id: int,
        prompt: str,
        response: str,
        reward: float = 0.0,
        value: float = 0.0,
        task_type: str = "chapter_generation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Experience:
        """收集单步经验（用于 GiGPO）

        Args:
            task_id: 任务 ID
            step_id: 步骤 ID
            prompt: 步骤提示
            response: 步骤响应
            reward: 步骤奖励
            value: 价值估计
            task_type: 任务类型
            metadata: 额外元数据

        Returns:
            创建的经验对象
        """
        step_data = StepData(
            step_id=step_id,
            prompt=prompt,
            response=response,
            reward=reward,
            value=value,
            metadata=metadata or {},
        )

        # 创建包含步骤的经验
        experience = Experience(
            id=str(uuid.uuid4()),
            task_id=task_id,
            task_type=task_type,
            prompt=prompt,
            content=response,
            reward=reward,
            total_reward=reward,
            created_at=datetime.now(),
            exp_type=ExperienceType.STEP,
            steps=[step_data],
            metadata=metadata or {},
        )

        self.store.save_experience(experience)
        self._collection_count += 1

        return experience

    def collect_batch(
        self,
        task_id: str,
        contents: List[str],
        rewards: Optional[List[float]] = None,
        prompts: Optional[List[str]] = None,
        task_type: str = "chapter_generation",
        context: Optional[Dict[str, Any]] = None,
    ) -> ExperienceBatch:
        """批量收集经验

        Args:
            task_id: 任务 ID
            contents: 生成的内容列表
            rewards: 奖励列表
            prompts: 提示列表
            task_type: 任务类型
            context: 上下文信息

        Returns:
            经验批次
        """
        ctx = context or {}
        group_id = str(uuid.uuid4())

        # 计算奖励（如果未提供）
        if rewards is None:
            rewards = []
            for i, content in enumerate(contents):
                prompt = prompts[i] if prompts else ""
                reward = self.reward_function.compute_simple(content, prompt, ctx)
                rewards.append(reward)
        else:
            rewards = list(rewards)

        # 创建经验列表
        experiences = []
        for i, (content, reward) in enumerate(zip(contents, rewards)):
            prompt = prompts[i] if prompts else ""

            exp = Experience(
                id=str(uuid.uuid4()),
                task_id=task_id,
                task_type=task_type,
                prompt=prompt,
                content=content,
                reward=reward,
                total_reward=reward,
                created_at=datetime.now(),
                exp_type=ExperienceType.EPISODE,
                group_id=group_id,
                metadata=ctx,
            )
            experiences.append(exp)

        # 创建批次
        batch = ExperienceBatch(
            experiences=experiences,
            group_id=group_id,
            task_type=task_type,
        )

        # 保存批次
        self.store.save_batch(batch)
        self._collection_count += len(experiences)

        logger.info(f"Collected batch {group_id} with {len(experiences)} experiences")

        return batch

    def train_step(
        self,
        task_type: Optional[str] = None,
        group_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """执行一次训练步骤

        从收集的经验中采样，进行 GRPO 训练。

        Args:
            task_type: 任务类型过滤
            group_size: 组大小（覆盖配置）

        Returns:
            训练结果
        """
        if not self.is_training_enabled:
            return {"status": "disabled", "message": "Training is disabled in COLLECTION_ONLY mode"}

        gs = group_size or self.config.group_size

        # 获取最新的经验
        experiences = self.store.get_latest_experiences(
            task_type=task_type,
            limit=gs * 2,  # 获取更多以便过滤
        )

        if len(experiences) < gs:
            return {
                "status": "insufficient",
                "message": f"Need at least {gs} experiences, got {len(experiences)}",
                "experiences": len(experiences),
            }

        # 按 task_id 分组
        task_groups: Dict[str, List[Experience]] = {}
        for exp in experiences:
            if exp.task_id not in task_groups:
                task_groups[exp.task_id] = []
            task_groups[exp.task_id].append(exp)

        # 选择最大的组或随机选择
        if len(task_groups) > 0:
            selected_task = max(task_groups.keys(), key=lambda k: len(task_groups[k]))
            selected_exps = task_groups[selected_task][:gs]
        else:
            selected_exps = experiences[:gs]

        # 执行 GRPO 训练
        stats = self.grpo_engine.train_step(selected_exps)

        self._total_train_steps += 1

        result = {
            "status": "success",
            "train_step": self._total_train_steps,
            "stats": stats.to_dict(),
            "num_experiences": len(selected_exps),
        }

        # 触发回调
        if self._on_train_step:
            self._on_train_step(result)

        logger.info(
            f"Training step {self._total_train_steps}: "
            f"loss={stats.total_loss:.4f}, reward={stats.mean_reward:.4f}"
        )

        return result

    def auto_train(self) -> Dict[str, Any]:
        """自动训练

        根据收集的经验数量自动决定是否训练。

        Returns:
            训练结果
        """
        if not self.is_training_enabled:
            return {"status": "disabled"}

        # 检查是否达到训练间隔
        if self._collection_count >= self.config.train_interval:
            self._collection_count = 0
            return self.train_step()

        return {
            "status": "skipped",
            "message": f"Collection count {self._collection_count} < train_interval {self.config.train_interval}",
        }

    def replay(
        self,
        exp_id: str,
    ) -> Optional[Experience]:
        """回放单条经验

        Args:
            exp_id: 经验 ID

        Returns:
            经验对象
        """
        return self.store.get_experience(exp_id)

    def get_group_experiences(
        self,
        group_id: str,
    ) -> ExperienceBatch:
        """获取组内所有经验

        Args:
            group_id: 组 ID

        Returns:
            经验批次
        """
        return self.store.get_group_experiences(group_id)

    def get_recent_experiences(
        self,
        task_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Experience]:
        """获取最近的经验

        Args:
            task_type: 任务类型过滤
            limit: 返回数量

        Returns:
            经验列表
        """
        return self.store.get_latest_experiences(task_type=task_type, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息

        Returns:
            统计字典
        """
        store_stats = self.store.get_stats()
        return {
            "collection_count": self._collection_count,
            "total_train_steps": self._total_train_steps,
            "mode": self.config.mode.value,
            "enabled": self.config.enabled,
            "store_stats": store_stats,
        }

    def export_experiences(
        self,
        task_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """导出经验数据

        Args:
            task_type: 任务类型过滤
            limit: 导出数量

        Returns:
            经验字典列表
        """
        experiences = self.store.get_latest_experiences(
            task_type=task_type,
            limit=limit,
        )
        return [e.to_dict() for e in experiences]

    def clear_old_experiences(self, keep_count: int = 1000) -> int:
        """清理旧经验

        Args:
            keep_count: 保留数量

        Returns:
            删除数量
        """
        return self.store.delete_old_experiences(keep_count)


# 便捷函数
_default_engine: Optional[RLEngine] = None


def get_rl_engine(
    config: Optional[RLConfig] = None,
    db_path: str = ".young/rl_experiences.db",
) -> RLEngine:
    """获取 RL 引擎单例

    Args:
        config: RL 配置
        db_path: 数据库路径

    Returns:
        RLEngine 实例
    """
    global _default_engine
    if _default_engine is None:
        _default_engine = RLEngine(config=config, db_path=db_path)
    return _default_engine


def init_rl_engine(
    mode: str = "COLLECTION_ONLY",
    group_size: int = 4,
    learning_rate: float = 1e-5,
    **kwargs,
) -> RLEngine:
    """初始化 RL 引擎的便捷函数

    Args:
        mode: 模式 (COLLECTION_ONLY, GRPO, GIGPO)
        group_size: 组大小
        learning_rate: 学习率
        **kwargs: 其他配置参数

    Returns:
        RLEngine 实例
    """
    config = RLConfig(
        enabled=True,
        mode=RLMode(mode),
        group_size=group_size,
        learning_rate=learning_rate,
        **kwargs,
    )
    return RLEngine(config=config)
