from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class BaseCrewOutput:
    """Crew执行输出"""
    content: Any
    tasks_completed: List[str]
    execution_time: float
    metadata: Dict[str, Any]


class BaseContentCrew(ABC):
    """内容生成Crew基类 (Facade模式)

    所有内容类型Crews必须继承此类并实现抽象方法。

    设计说明:
    - 内部使用 Dict[str, Agent/Task] 管理，方便命名访问
    - _create_workflow() 创建Crew时，需转换为 list[Agent/Task]
    - kickoff() 返回 BaseCrewOutput 封装Crew的原始输出

    与Crew类的类型适配由子类在 _create_workflow() 中完成转换。
    """

    def __init__(
        self,
        config: Any,
        agents: Optional[Dict[str, Any]] = None,
        tasks: Optional[Dict[str, Any]] = None,
        verbose: bool = True
    ):
        self.config = config
        self._agents = agents or {}
        self._tasks = tasks or {}
        self.verbose = verbose
        self._crew: Optional[Any] = None

    @abstractmethod
    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents - 子类必须实现"""
        pass

    @abstractmethod
    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks - 子类必须实现"""
        pass

    @abstractmethod
    def _create_workflow(self) -> Any:
        """创建Crew工作流 - 子类必须实现"""
        pass

    def kickoff(self) -> BaseCrewOutput:
        """执行Crew并返回内容输出"""
        import time
        start = time.time()

        crew = self._create_workflow()
        result = crew.kickoff()

        execution_time = time.time() - start

        return BaseCrewOutput(
            content=self._parse_output(result),
            tasks_completed=[t.description for t in crew.tasks] if hasattr(crew, 'tasks') else [],
            execution_time=execution_time,
            metadata={"config": self.config.__dict__ if hasattr(self.config, '__dict__') else {}}
        )

    def _parse_output(self, result: Any) -> Any:
        """解析Crew输出"""
        return result

    @property
    def agents(self) -> Dict[str, Any]:
        """获取Agents字典"""
        if not self._agents:
            self._agents = self._create_agents()
        return self._agents

    @property
    def tasks(self) -> Dict[str, Any]:
        """获取Tasks字典"""
        if not self._tasks:
            self._tasks = self._create_tasks()
        return self._tasks


__all__ = [
    "BaseCrewOutput",
    "BaseContentCrew",
]
