"""内容生成系统异常定义"""


class ContentGenerationError(Exception):
    """内容生成基础异常"""
    pass


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
    "ContentGenerationError",
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
