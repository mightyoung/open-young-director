"""内容生成系统异常定义"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContentGenerationError(Exception):
    """内容生成基础异常"""
    pass


class ExecutionStatus(Enum):
    """执行状态枚举"""
    SUCCESS = "success"       # 完全成功
    PARTIAL = "partial"       # 部分成功，有失败但可恢复
    FAILED = "failed"        # 完全失败


@dataclass
class StageFailure:
    """阶段失败信息"""
    stage: str                          # 阶段名称
    reason: str                         # 失败原因
    details: dict[str, Any] = field(default_factory=dict)  # 详细错误信息
    recoverable: bool = False           # 是否可恢复


@dataclass
class ExecutionResult:
    """执行结果（结构化失败语义）"""
    status: ExecutionStatus = ExecutionStatus.SUCCESS
    failures: list[StageFailure] = field(default_factory=list)
    completed_stages: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict[str, Any]:
        """转换为 metadata dict 用于存储"""
        return {
            "status": self.status.value,
            "failures": [
                {
                    "stage": f.stage,
                    "reason": f.reason,
                    "details": f.details,
                    "recoverable": f.recoverable,
                }
                for f in self.failures
            ],
            "completed_stages": self.completed_stages,
        }

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    @property
    def is_partial(self) -> bool:
        return self.status == ExecutionStatus.PARTIAL

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    def add_failure(self, stage: str, reason: str, details: dict | None = None, recoverable: bool = False):
        """添加一个阶段失败"""
        self.failures.append(StageFailure(
            stage=stage,
            reason=reason,
            details=details or {},
            recoverable=recoverable,
        ))
        # 自动更新状态
        if not recoverable:
            self.status = ExecutionStatus.FAILED
        elif self.status == ExecutionStatus.SUCCESS:
            self.status = ExecutionStatus.PARTIAL

    def add_completed_stage(self, stage: str):
        """添加一个完成的阶段"""
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)


class InvalidContentTypeError(ContentGenerationError):
    """无效的内容类型"""
    pass


class InvalidStyleError(ContentGenerationError):
    """无效的风格配置"""
    pass


class InvalidPlatformError(ContentGenerationError):
    """无效的平台配置"""
    pass


class CritiqueFailedError(ContentGenerationError):
    """审查失败"""
    pass


class RevisionFailedError(ContentGenerationError):
    """修改失败"""
    pass


class PolishingFailedError(ContentGenerationError):
    """润色失败"""
    pass


class ExportFailedError(ContentGenerationError):
    """导出失败"""
    pass


class ValidationError(ContentGenerationError):
    """验证失败"""
    pass


class ConsistencyError(ContentGenerationError):
    """一致性错误"""
    pass


class PacingError(ContentGenerationError):
    """节奏错误"""
    pass


class OutOfCharacterError(ContentGenerationError):
    """角色偏离错误"""
    pass


class HighPointError(ContentGenerationError):
    """高潮点错误"""
    pass


class ContinuityError(ContentGenerationError):
    """连续性错误"""
    pass


class DiantingError(ContentGenerationError):
    """垫听机制错误"""
    pass


class ChapterEndingError(ContentGenerationError):
    """章节结尾错误"""
    pass


class ShuangganPatternError(ContentGenerationError):
    """爽感模式错误"""
    pass


class RepetitivePatternError(ContentGenerationError):
    """重复模式错误"""
    pass


class EntityMemoryError(ContentGenerationError):
    """实体记忆错误"""
    pass


class OutlineEngineError(ContentGenerationError):
    """大纲引擎错误"""
    pass


__all__ = [
    # Base
    "ContentGenerationError",
    # Status types
    "ExecutionStatus",
    "StageFailure",
    "ExecutionResult",
    # Content errors
    "InvalidContentTypeError",
    "InvalidStyleError",
    "InvalidPlatformError",
    "CritiqueFailedError",
    "RevisionFailedError",
    "PolishingFailedError",
    "ExportFailedError",
    "ValidationError",
    "ConsistencyError",
    "PacingError",
    "OutOfCharacterError",
    "HighPointError",
    "ContinuityError",
    "DiantingError",
    "ChapterEndingError",
    "ShuangganPatternError",
    "RepetitivePatternError",
    "EntityMemoryError",
    "OutlineEngineError",
]
