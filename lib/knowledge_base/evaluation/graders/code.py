"""
Code-Based Grader - 确定性检查

支持: sensitive_word, profanity, format_check, length_check, pattern_match

适用于小说内容的确定性质量检查
"""

import re
from typing import Any

from .base import BaseGrader, GradeResult, GraderType


class CodeGrader(BaseGrader):
    """Deterministic Code-Based Grader for content validation"""

    # 默认敏感词列表（示例）
    DEFAULT_SENSITIVE_WORDS = [
        # 政治敏感词（示例，实际使用时从配置文件加载）
        "敏感词1",
        "敏感词2",
    ]

    # 默认违禁词列表
    DEFAULT_PROFANITY_WORDS = [
        # 脏话/粗俗词汇（示例）
    ]

    def __init__(
        self,
        name: str = "code_grader",
        check_type: str = "sensitive_word",
        sensitive_words: list[str] = None,
        profanity_words: list[str] = None,
        forbidden_patterns: list[str] = None,
        required_patterns: list[str] = None,
        min_length: int = 0,
        max_length: int = 1000000,
        weight: float = 1.0,
        required: bool = True,
        timeout_sec: int = 30,
    ):
        super().__init__(
            name=name,
            grader_type=GraderType.CODE_BASED,
            weight=weight,
            required=required,
            timeout_sec=timeout_sec,
        )
        self.check_type = check_type
        self.sensitive_words = sensitive_words or self.DEFAULT_SENSITIVE_WORDS
        self.profanity_words = profanity_words or self.DEFAULT_PROFANITY_WORDS
        self.forbidden_patterns = forbidden_patterns or []
        self.required_patterns = required_patterns or []
        self.min_length = min_length
        self.max_length = max_length

    async def grade(
        self,
        content: str,
        context: dict[str, Any],
    ) -> GradeResult:
        """执行确定性检查"""
        import time

        start = time.perf_counter()

        try:
            if self.check_type == "sensitive_word":
                passed, score, details = self._check_sensitive_words(content)
            elif self.check_type == "profanity":
                passed, score, details = self._check_profanity(content)
            elif self.check_type == "format_check":
                passed, score, details = self._check_format(content, context)
            elif self.check_type == "length_check":
                passed, score, details = self._check_length(content)
            elif self.check_type == "pattern_match":
                passed, score, details = self._check_patterns(content)
            elif self.check_type == "composite":
                passed, score, details = self._check_composite(content)
            else:
                passed, score, details = False, 0.0, f"Unknown check_type: {self.check_type}"

            elapsed_ms = (time.perf_counter() - start) * 1000

            return GradeResult(
                grader_name=self.name,
                grader_type=GraderType.CODE_BASED,
                passed=passed,
                score=score,
                details=details,
                latency_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return GradeResult(
                grader_name=self.name,
                grader_type=GraderType.CODE_BASED,
                passed=False,
                score=0.0,
                details=f"CodeGrader error: {e}",
                error=str(e),
                latency_ms=elapsed_ms,
            )

    def _check_sensitive_words(self, content: str) -> tuple[bool, float, str]:
        """检查敏感词"""
        if not self.sensitive_words:
            return True, 1.0, "No sensitive words configured"

        found = []
        for word in self.sensitive_words:
            if word in content:
                found.append(word)

        if found:
            return (
                False,
                0.0,
                f"Found {len(found)} sensitive word(s): {', '.join(found[:5])}",
            )

        return True, 1.0, "No sensitive words detected"

    def _check_profanity(self, content: str) -> tuple[bool, float, str]:
        """检查违禁词/脏话"""
        if not self.profanity_words:
            return True, 1.0, "No profanity words configured"

        found = []
        for word in self.profanity_words:
            # 使用正则进行更灵活的匹配
            pattern = re.escape(word)
            if re.search(pattern, content, re.IGNORECASE):
                found.append(word)

        if found:
            return (
                False,
                0.0,
                f"Found {len(found)} profanity word(s): {', '.join(found[:5])}",
            )

        return True, 1.0, "No profanity detected"

    def _check_format(self, content: str, context: dict[str, Any]) -> tuple[bool, float, str]:
        """检查格式"""
        issues = []

        # 检查是否有空白内容
        if not content or not content.strip():
            issues.append("Content is empty")

        # 检查是否有过多的连续空白字符
        if re.search(r"\s{5,}", content):
            issues.append("Excessive whitespace detected")

        # 检查段落数量（如果有上下文）
        expected_paragraphs = context.get("expected_paragraphs", 0)
        if expected_paragraphs > 0:
            actual_paragraphs = len([p for p in content.split("\n\n") if p.strip()])
            if actual_paragraphs < expected_paragraphs:
                issues.append(
                    f"Insufficient paragraphs: expected >= {expected_paragraphs}, got {actual_paragraphs}"
                )

        # 检查是否包含标题标记
        has_title_marker = context.get("require_title", False)
        if has_title_marker and not re.search(r"^#+\s+\S", content, re.MULTILINE):
            issues.append("Missing title marker")

        if issues:
            return False, 0.0, "Format issues: " + "; ".join(issues)

        return True, 1.0, "Format check passed"

    def _check_length(self, content: str) -> tuple[bool, float, str]:
        """检查内容长度"""
        length = len(content)

        if length < self.min_length:
            ratio = length / max(1, self.min_length)
            return (
                False,
                ratio,
                f"Content too short: {length} < {self.min_length}",
            )

        if length > self.max_length:
            ratio = max(0.0, 1.0 - (length - self.max_length) / self.max_length)
            return (
                False,
                ratio,
                f"Content too long: {length} > {self.max_length}",
            )

        # 长度在合理范围内，给一个基于目标长度的分数
        optimal_length = context.get("optimal_length", (self.min_length + self.max_length) / 2)
        if optimal_length:
            ratio = 1.0 - abs(length - optimal_length) / optimal_length * 0.1
            ratio = max(0.8, min(1.0, ratio))
            return True, ratio, f"Length OK: {length}"

        return True, 1.0, f"Length OK: {length}"

    def _check_patterns(self, content: str) -> tuple[bool, float, str]:
        """检查必需和禁止的模式"""
        issues = []

        # 检查禁止模式
        for pattern in self.forbidden_patterns:
            matches = re.findall(pattern, content)
            if matches:
                issues.append(f"Forbidden pattern '{pattern}' found {len(matches)} time(s)")

        # 检查必需模式
        missing_patterns = []
        for pattern in self.required_patterns:
            if not re.search(pattern, content):
                missing_patterns.append(pattern)

        if missing_patterns:
            issues.append(f"Missing required pattern(s): {', '.join(missing_patterns)}")

        if issues:
            return False, 0.0, "Pattern issues: " + "; ".join(issues)

        return True, 1.0, "All patterns satisfied"

    def _check_composite(self, content: str) -> tuple[bool, float, str]:
        """组合检查：敏感词 + 格式 + 长度"""
        all_issues = []
        total_score = 1.0

        # 敏感词检查
        passed, score, details = self._check_sensitive_words(content)
        if not passed:
            all_issues.append(f"sensitive_word: {details}")
            total_score *= score

        # 违禁词检查
        passed, score, details = self._check_profanity(content)
        if not passed:
            all_issues.append(f"profanity: {details}")
            total_score *= score

        # 格式检查
        passed, score, details = self._check_format(content, {})
        if not passed:
            all_issues.append(f"format: {details}")
            total_score *= score

        # 长度检查
        passed, score, details = self._check_length(content)
        if not passed:
            all_issues.append(f"length: {details}")
            total_score *= score

        # 模式检查
        passed, score, details = self._check_patterns(content)
        if not passed:
            all_issues.append(f"patterns: {details}")
            total_score *= score

        if all_issues:
            return False, total_score, "Composite check failed: " + "; ".join(all_issues)

        return True, total_score, "All composite checks passed"
