"""Stage service abstract base class."""
from abc import ABC, abstractmethod
from typing import Any, Optional
from crewai.content.exceptions import ExecutionResult, ExecutionStatus, StageFailure


class BaseStageService(ABC):
    """所有阶段服务的抽象基类。

    设计原则:
    - 每个服务负责一个阶段 (outline/volume/summary/writing)
    - execute() 返回 (output, execution_result)
    - 失败信息通过 ExecutionResult 结构化返回
    """

    def __init__(self, pipeline_state: Any, config: dict, llm: Any = None):
        self.pipeline_state = pipeline_state
        self.config = config
        self.llm = llm
        self._failures: list[StageFailure] = []
        self._completed_stages: list[str] = []

    @abstractmethod
    def execute(self, context: dict) -> tuple[Any, ExecutionResult]:
        """执行阶段并返回 (输出, 执行结果)

        Args:
            context: 包含前置阶段数据的上下文

        Returns:
            tuple: (阶段输出, ExecutionResult)
        """
        pass

    def add_failure(
        self,
        stage: str,
        reason: str,
        details: dict = None,
        recoverable: bool = False
    ):
        """添加一个失败记录。"""
        self._failures.append(StageFailure(
            stage=stage,
            reason=reason,
            details=details or {},
            recoverable=recoverable,
        ))

    def add_completed_stage(self, stage: str):
        """记录一个完成的阶段。"""
        if stage not in self._completed_stages:
            self._completed_stages.append(stage)

    def build_execution_result(self) -> ExecutionResult:
        """根据当前失败记录构建执行结果。"""
        if not self._failures:
            status = ExecutionStatus.SUCCESS
        elif all(f.recoverable for f in self._failures):
            status = ExecutionStatus.PARTIAL
        else:
            status = ExecutionStatus.FAILED

        return ExecutionResult(
            status=status,
            failures=self._failures,
            completed_stages=self._completed_stages,
        )

    @property
    def topic(self) -> str:
        return self.config.get("topic", "")

    @property
    def style(self) -> str:
        return self.config.get("style", "urban")

    @property
    def genre(self) -> str:
        return self.config.get("genre", self.style)
