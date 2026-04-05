from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar


T = TypeVar("T")


@dataclass
class BaseCrewOutput(Generic[T]):
    """Crew执行输出"""
    content: T
    tasks_completed: list[str]
    execution_time: float
    metadata: dict[str, Any]


class BaseContentCrew(ABC, Generic[T]):
    """内容生成Crew基类 (Facade模式)

    所有内容类型Crews必须继承此类并实现抽象方法。

    类型参数:
        T: kickoff() 返回的 content 类型

    设计说明:
    - 内部使用 Dict[str, Agent/Task] 管理，方便命名访问
    - _create_workflow() 创建Crew时，需转换为 list[Agent/Task]
    - kickoff() 返回 BaseCrewOutput[T] 封装Crew的原始输出

    与Crew类的类型适配由子类在 _create_workflow() 中完成转换。

    子类可以通过重写以下方法扩展状态管理能力:
    - get_state(): 获取当前状态
    - set_state(state): 设置状态
    - save_state(path): 保存状态到文件
    - load_state(path): 从文件加载状态
    - evaluate_output_quality(output): 评估输出质量，返回质量报告

    P1: 新增 _evaluate_output() 钩子，子类实现以支持 partial/approval 语义
    """

    def __init__(
        self,
        config: Any,
        agents: dict[str, Any] | None = None,
        tasks: dict[str, Any] | None = None,
        verbose: bool = True
    ):
        self.config = config
        self._agents = agents or {}
        self._tasks = tasks or {}
        self.verbose = verbose
        self._crew: Any | None = None

    def _load_market_persona(self, agent_role_id: str) -> dict[str, Any]:
        """从市集档案中加载特定角色的 Agent 灵魂 (Persona)"""
        market_id = self.config.get(f"use_market_{agent_role_id}")
        if not market_id:
            return {}

        try:
            from crewai.content.novel.orchestrator.market_loader import MarketLoader
            loader = MarketLoader()
            profile = loader.load_profile(market_id)
            if profile:
                import logging
                logging.getLogger(__name__).info(f"Marketplace Sync: Loaded '{market_id}' persona for {agent_role_id}.")
                return profile
        except Exception:
            pass
        return {}

    @abstractmethod
    def _create_agents(self) -> dict[str, Any]:
        """创建Agents - 子类必须实现"""

    @abstractmethod
    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks - 子类必须实现"""

    @abstractmethod
    def _create_workflow(self) -> Any:
        """创建Crew工作流 - 子类必须实现"""

    def kickoff(self, *, fail_on_quality_issue: bool = False) -> BaseCrewOutput[T]:
        """执行Crew并返回内容输出

        流程:
        1. 创建并执行 Crew 工作流
        2. 解析原始输出
        3. 调用 _evaluate_output() 评估质量
        4. 将质量报告纳入 metadata 返回
        5. 根据质量报告设置 output_status

        Args:
            fail_on_quality_issue: 如果为 True，当 is_usable=False 或有 errors 时抛出异常
                                   用于需要严格质量把控的场景

        Raises:
            QualityThresholdException: 当 fail_on_quality_issue=True 且质量不达标时
        """
        import time
        start = time.time()

        crew = self._create_workflow()
        result = crew.kickoff()

        execution_time = time.time() - start

        parsed_content = self._parse_output(result)
        quality_report = self._evaluate_output(parsed_content)

        # P1: 质量报告驱动执行策略 - fail-closed 行为
        output_status = "success"
        if not quality_report.is_usable:
            output_status = "failed"
        elif quality_report.errors:
            output_status = "failed"
        elif quality_report.requires_manual_review:
            output_status = "partial"
        elif quality_report.warnings:
            output_status = "warning"

        # P1: fail_on_quality_issue 模式 - 质量不达标时抛出异常
        if fail_on_quality_issue and output_status == "failed":
            raise QualityThresholdException(
                f"Quality threshold not met: is_usable={quality_report.is_usable}, "
                f"errors={quality_report.errors}, output_status={output_status}"
            )

        return BaseCrewOutput(
            content=parsed_content,
            tasks_completed=[t.description for t in crew.tasks] if hasattr(crew, 'tasks') else [],
            execution_time=execution_time,
            metadata={
                "config": self.config.__dict__ if hasattr(self.config, '__dict__') else {},
                "quality_report": {
                    "is_usable": quality_report.is_usable,
                    "requires_manual_review": quality_report.requires_manual_review,
                    "output_status": output_status,
                    "warnings": quality_report.warnings,
                    "errors": quality_report.errors,
                },
            }
        )

    def _parse_output(self, result: Any) -> T:
        """解析Crew输出"""
        return result  # type: ignore

    @property
    def agents(self) -> dict[str, Any]:
        """获取Agents字典"""
        if not self._agents:
            self._agents = self._create_agents()
        return self._agents

    @property
    def tasks(self) -> dict[str, Any]:
        """获取Tasks字典"""
        if not self._tasks:
            self._tasks = self._create_tasks()
        return self._tasks

    def _evaluate_output(self, output: Any) -> QualityReport:
        """评估输出质量 - 子类可重写

        P1: 用于支持 partial/approval 语义。子类返回 QualityReport，
        包含 is_usable 和 requires_manual_review 等字段。

        默认实现返回成功状态。
        """
        return QualityReport(is_usable=True, requires_manual_review=False)

    def get_state(self) -> dict[str, Any]:
        """获取当前状态 - 子类可重写"""
        return {"config": self.config.__dict__ if hasattr(self.config, '__dict__') else {}}

    def set_state(self, state: dict[str, Any]) -> None:
        """设置状态 - 子类可重写"""

    def save_state(self, path: str) -> None:
        """保存状态到文件 - 子类可重写"""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.get_state(), f, ensure_ascii=False, indent=2, default=str)

    def load_state(self, path: str) -> None:
        """从文件加载状态 - 子类可重写"""
        import json
        with open(path, "r", encoding="utf-8") as f:
            self.set_state(json.load(f))


@dataclass
class QualityReport:
    """内容质量报告

    P1: 用于 BaseContentCrew._evaluate_output() 的标准返回类型。
    调用方在处理输出前应检查 is_usable 和 requires_manual_review。
    """
    is_usable: bool = True      # 内容是否可直接使用
    requires_manual_review: bool = False  # 是否需要人工审核
    warnings: list[str] = field(default_factory=list)  # 警告信息
    errors: list[str] = field(default_factory=list)  # 错误信息


class QualityThresholdException(Exception):
    """质量阈值异常 - 当 fail_on_quality_issue=True 且质量不达标时抛出

    P1: 用于 BaseContentCrew.kickoff() 的 fail-closed 行为。
    当 is_usable=False 或 errors 不为空时表示质量未达阈值。
    """
    def __init__(self, message: str, quality_report: QualityReport | None = None):
        super().__init__(message)
        self.quality_report = quality_report


__all__ = [
    "BaseContentCrew",
    "BaseCrewOutput",
    "QualityReport",
    "QualityThresholdException",
]
