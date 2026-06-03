"""Experience Data Models

定义 RL 经验数据的结构和类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ExperienceType(str, Enum):
    """经验类型"""

    EPISODE = "episode"  # 完整情节/章节经验
    STEP = "step"  # 单步经验
    TRAJECTORY = "trajectory"  # 完整轨迹


@dataclass
class StepData:
    """单步数据

    表示一个单独的生成步骤。
    """

    step_id: int
    prompt: str
    response: str
    reward: float = 0.0
    value: float = 0.0
    log_prob: float = 0.0
    advantage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "prompt": self.prompt,
            "response": self.response,
            "reward": self.reward,
            "value": self.value,
            "log_prob": self.log_prob,
            "advantage": self.advantage,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepData":
        """从字典创建"""
        return cls(
            step_id=data["step_id"],
            prompt=data["prompt"],
            response=data["response"],
            reward=data.get("reward", 0.0),
            value=data.get("value", 0.0),
            log_prob=data.get("log_prob", 0.0),
            advantage=data.get("advantage", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Experience:
    """单条经验数据

    表示一次完整的生成经验，包含输入、输出和奖励。
    """

    id: str
    task_id: str
    task_type: str  # e.g., "chapter_generation", "dialogue", "plot_point"
    prompt: str
    content: str
    reward: float = 0.0
    total_reward: float = 0.0

    # 多维度奖励
    rewards: Dict[str, float] = field(default_factory=dict)

    # 时间戳
    created_at: datetime = field(default_factory=datetime.now)

    # 经验类型
    exp_type: ExperienceType = ExperienceType.EPISODE

    # 步骤数据（用于 GiGPO）
    steps: List[StepData] = field(default_factory=list)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # GRPO 相关
    group_id: Optional[str] = None
    rank: Optional[int] = None  # 组内排名
    advantage: float = 0.0

    # 生成参数
    model_name: str = "default"
    temperature: float = 0.7
    generation_params: Dict[str, Any] = field(default_factory=dict)

    @property
    def num_steps(self) -> int:
        """步骤数量"""
        return len(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "task_type": self.task_type,
            "prompt": self.prompt,
            "content": self.content,
            "reward": self.reward,
            "total_reward": self.total_reward,
            "rewards": self.rewards,
            "created_at": self.created_at.isoformat(),
            "exp_type": self.exp_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "group_id": self.group_id,
            "rank": self.rank,
            "advantage": self.advantage,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "generation_params": self.generation_params,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Experience":
        """从字典创建"""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        exp_type = data.get("exp_type", ExperienceType.EPISODE)
        if isinstance(exp_type, str):
            exp_type = ExperienceType(exp_type)

        steps = [StepData.from_dict(s) for s in data.get("steps", [])]

        return cls(
            id=data["id"],
            task_id=data["task_id"],
            task_type=data["task_type"],
            prompt=data["prompt"],
            content=data["content"],
            reward=data.get("reward", 0.0),
            total_reward=data.get("total_reward", 0.0),
            rewards=data.get("rewards", {}),
            created_at=created_at,
            exp_type=exp_type,
            steps=steps,
            metadata=data.get("metadata", {}),
            group_id=data.get("group_id"),
            rank=data.get("rank"),
            advantage=data.get("advantage", 0.0),
            model_name=data.get("model_name", "default"),
            temperature=data.get("temperature", 0.7),
            generation_params=data.get("generation_params", {}),
        )


@dataclass
class ExperienceBatch:
    """经验批次

    用于批量处理多条经验。
    """

    experiences: List[Experience] = field(default_factory=list)
    group_id: Optional[str] = None
    task_type: Optional[str] = None

    @property
    def size(self) -> int:
        """批次大小"""
        return len(self.experiences)

    @property
    def rewards(self) -> List[float]:
        """所有奖励"""
        return [exp.reward for exp in self.experiences]

    def add(self, experience: Experience) -> None:
        """添加经验"""
        self.experiences.append(experience)

    def filter_by_task_type(self, task_type: str) -> "ExperienceBatch":
        """按任务类型过滤"""
        filtered = [e for e in self.experiences if e.task_type == task_type]
        return ExperienceBatch(experiences=filtered, task_type=task_type)

    def get_top_k(self, k: int) -> List[Experience]:
        """获取 top-k 奖励的经验"""
        sorted_exps = sorted(self.experiences, key=lambda e: e.reward, reverse=True)
        return sorted_exps[:k]

    def get_worst_k(self, k: int) -> List[Experience]:
        """获取 bottom-k 奖励的经验"""
        sorted_exps = sorted(self.experiences, key=lambda e: e.reward)
        return sorted_exps[:k]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "experiences": [e.to_dict() for e in self.experiences],
            "group_id": self.group_id,
            "task_type": self.task_type,
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperienceBatch":
        """从字典创建"""
        experiences = [Experience.from_dict(e) for e in data.get("experiences", [])]
        return cls(
            experiences=experiences,
            group_id=data.get("group_id"),
            task_type=data.get("task_type"),
        )


@dataclass
class TrainingStats:
    """训练统计

    记录训练过程中的各项指标。
    """

    step: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    # 损失
    policy_loss: float = 0.0
    value_loss: float = 0.0
    entropy_loss: float = 0.0
    total_loss: float = 0.0

    # 优势统计
    mean_advantage: float = 0.0
    max_advantage: float = 0.0
    min_advantage: float = 0.0

    # 奖励统计
    mean_reward: float = 0.0
    max_reward: float = 0.0
    min_reward: float = 0.0

    # 其他
    learning_rate: float = 0.0
    clip_fraction: float = 0.0
    explained_variance: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step": self.step,
            "timestamp": self.timestamp.isoformat(),
            "policy_loss": self.policy_loss,
            "value_loss": self.value_loss,
            "entropy_loss": self.entropy_loss,
            "total_loss": self.total_loss,
            "mean_advantage": self.mean_advantage,
            "max_advantage": self.max_advantage,
            "min_advantage": self.min_advantage,
            "mean_reward": self.mean_reward,
            "max_reward": self.max_reward,
            "min_reward": self.min_reward,
            "learning_rate": self.learning_rate,
            "clip_fraction": self.clip_fraction,
            "explained_variance": self.explained_variance,
        }
