"""
Base Grader - 所有 Grader 的抽象基类

基于 openyoung 的 Grader 架构设计
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GraderType(Enum):
    """Grader 类型"""

    CODE_BASED = "code"  # 确定性检查 (lint/测试/状态)
    MODEL_BASED = "model"  # LLM评判 (rubric打分)
    HUMAN = "human"  # 人工判定


class GradingMode(Enum):
    """评分模式"""

    WEIGHTED = "weighted"  # 加权组合
    BINARY = "binary"  # 所有grader必须通过
    HYBRID = "hybrid"  # 部分grader必需，部分可选


@dataclass
class GradeResult:
    """Grader 输出 - 统一格式"""

    grader_name: str
    grader_type: GraderType

    # 判定结果
    passed: bool
    score: float  # 0.0 - 1.0
    details: str

    # 原始输出 (调试用)
    raw_output: Optional[str] = None

    # 指标
    latency_ms: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "grader_name": self.grader_name,
            "grader_type": self.grader_type.value,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
            "raw_output": self.raw_output,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class BaseGrader(ABC):
    """
    Grader 抽象基类

    所有 Grader 必须实现 grade() 方法
    """

    def __init__(
        self,
        name: str,
        grader_type: GraderType,
        weight: float = 1.0,
        required: bool = True,
        timeout_sec: int = 60,
    ):
        self.name = name
        self.grader_type = grader_type
        self.weight = weight
        self.required = required
        self.timeout_sec = timeout_sec

    @abstractmethod
    async def grade(
        self,
        content: str,
        context: dict[str, Any],
    ) -> GradeResult:
        """
        执行评判

        Args:
            content: 要评估的内容
            context: 额外上下文 (rubric, criteria, expected_output, etc.)

        Returns:
            GradeResult: 评判结果
        """
        raise NotImplementedError

    async def _run_with_timing(self, coro) -> tuple[Any, float]:
        """执行协程并计时"""
        start = time.perf_counter()
        result = await coro
        elapsed = (time.perf_counter() - start) * 1000
        return result, elapsed
