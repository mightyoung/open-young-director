"""
Grading Orchestrator - 统一评分调度器

支持三种评分模式:
- WEIGHTED: 加权组合所有 grader 结果
- BINARY: 所有 grader 必须通过
- HYBRID: 必需 grader 必须通过，可选 grader 加权计算

基于 openyoung 的 GradingOrchestrator 设计
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from .graders import (
    BaseGrader,
    CodeGrader,
    GradeResult,
    GraderType,
    GradingMode,
    ModelGrader,
)


@dataclass
class GradingConfig:
    """评分配置"""

    mode: GradingMode = GradingMode.WEIGHTED
    pass_threshold: float = 0.7  # 综合分数通过阈值
    weight_threshold: float = 0.7  # 加权模式下必需通过的权重比例


@dataclass
class GradingReport:
    """评分报告"""

    # 总体结果
    passed: bool
    overall_score: float

    # 各 grader 结果
    grader_results: list[GradeResult]

    # 综合评判详情
    details: str

    # 错误信息
    error: Optional[str] = None

    # 耗时
    total_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "grader_results": [r.to_dict() for r in self.grader_results],
            "details": self.details,
            "error": self.error,
            "total_latency_ms": self.total_latency_ms,
        }


class GradingOrchestrator:
    """统一评分调度器"""

    def __init__(self, config: Optional[GradingConfig] = None):
        self.config = config or GradingConfig()
        self.graders: list[BaseGrader] = []

    def add_grader(self, grader: BaseGrader) -> "GradingOrchestrator":
        """添加 grader"""
        self.graders.append(grader)
        return self

    def add_model_grader(
        self,
        name: str = "model_grader",
        rubric: Optional[str] = None,
        **kwargs,
    ) -> "GradingOrchestrator":
        """便捷方法：添加 ModelGrader"""
        grader = ModelGrader(name=name, rubric=rubric, **kwargs)
        return self.add_grader(grader)

    def add_code_grader(
        self,
        name: str = "code_grader",
        check_type: str = "sensitive_word",
        **kwargs,
    ) -> "GradingOrchestrator":
        """便捷方法：添加 CodeGrader"""
        grader = CodeGrader(name=name, check_type=check_type, **kwargs)
        return self.add_grader(grader)

    async def grade(
        self,
        content: str,
        context: Optional[dict[str, Any]] = None,
    ) -> GradingReport:
        """
        执行评分

        Args:
            content: 要评估的内容
            context: 上下文信息

        Returns:
            GradingReport: 评分报告
        """
        import time

        start = time.perf_counter()
        context = context or {}

        if not self.graders:
            return GradingReport(
                passed=False,
                overall_score=0.0,
                grader_results=[],
                details="No graders configured",
                error="No graders available",
                total_latency_ms=0.0,
            )

        try:
            # 并行执行所有 grader
            import asyncio

            tasks = [grader.grade(content, context) for grader in self.graders]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 收集有效结果
            grader_results: list[GradeResult] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # 处理异常结果
                    grader_results.append(
                        GradeResult(
                            grader_name=self.graders[i].name,
                            grader_type=self.graders[i].grader_type,
                            passed=False,
                            score=0.0,
                            details=f"Grader failed: {result}",
                            error=str(result),
                        )
                    )
                else:
                    grader_results.append(result)

            # 计算综合结果
            passed, overall_score, details = self._compute_result(grader_results)

            elapsed_ms = (time.perf_counter() - start) * 1000

            return GradingReport(
                passed=passed,
                overall_score=overall_score,
                grader_results=grader_results,
                details=details,
                total_latency_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return GradingReport(
                passed=False,
                overall_score=0.0,
                grader_results=[],
                details=f"GradingOrchestrator error: {e}",
                error=str(e),
                total_latency_ms=elapsed_ms,
            )

    def _compute_result(
        self, results: list[GradeResult]
    ) -> tuple[bool, float, str]:
        """根据评分模式计算综合结果"""
        if self.config.mode == GradingMode.BINARY:
            return self._compute_binary(results)
        elif self.config.mode == GradingMode.HYBRID:
            return self._compute_hybrid(results)
        else:  # WEIGHTED
            return self._compute_weighted(results)

    def _compute_binary(self, results: list[GradeResult]) -> tuple[bool, float, str]:
        """BINARY 模式: 所有 grader 必须通过"""
        all_passed = all(r.passed for r in results)
        min_score = min((r.score for r in results), default=0.0)

        details_parts = []
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            details_parts.append(f"{r.grader_name}: {status} ({r.score:.2f})")

        details = f"Binary mode - All must pass: {'; '.join(details_parts)}"

        return all_passed, min_score, details

    def _compute_hybrid(self, results: list[GradeResult]) -> tuple[bool, float, str]:
        """HYBRID 模式: 必需 grader 必须通过，可选 grader 加权计算"""
        required_results = []
        optional_results = []

        for i, result in enumerate(results):
            grader = self.graders[i] if i < len(self.graders) else None
            if grader and grader.required:
                required_results.append(result)
            else:
                optional_results.append(result)

        # 检查必需 grader 是否都通过
        required_passed = all(r.passed for r in required_results)

        # 计算可选 grader 的加权分数
        optional_score = 0.0
        optional_weight_sum = 0.0
        for r in optional_results:
            optional_score += r.score * r.weight if hasattr(r, "weight") else r.score
            optional_weight_sum += r.weight if hasattr(r, "weight") else 1.0

        if optional_weight_sum > 0:
            optional_score /= optional_weight_sum

        # 综合分数 = 必需通过判定 * 可选加权分数
        overall_score = optional_score if required_passed else 0.0

        details_parts = []
        if required_results:
            req_status = "ALL_PASSED" if required_passed else "FAILED"
            details_parts.append(f"Required: {req_status}")
        if optional_results:
            details_parts.append(f"Optional weighted: {optional_score:.2f}")

        details = f"Hybrid mode - {'; '.join(details_parts)}"

        return required_passed, overall_score, details

    def _compute_weighted(self, results: list[GradeResult]) -> tuple[bool, float, str]:
        """WEIGHTED 模式: 所有 grader 加权组合"""
        weighted_sum = 0.0
        weight_sum = 0.0

        for i, result in enumerate(results):
            grader = self.graders[i] if i < len(self.graders) else None
            weight = grader.weight if grader else 1.0

            weighted_sum += result.score * weight
            weight_sum += weight

        overall_score = weighted_sum / weight_sum if weight_sum > 0 else 0.0

        passed = overall_score >= self.config.pass_threshold

        details_parts = []
        for r in results:
            details_parts.append(f"{r.grader_name}: {r.score:.2f}")
        details_parts.append(f"Weighted total: {overall_score:.2f}")

        details = f"Weighted mode - {'; '.join(details_parts)}"

        return passed, overall_score, details


# 便捷函数


async def grade_content(
    content: str,
    graders: list[BaseGrader],
    mode: GradingMode = GradingMode.WEIGHTED,
    pass_threshold: float = 0.7,
) -> GradingReport:
    """
    便捷函数: 对内容进行评分

    Args:
        content: 要评估的内容
        graders: grader 列表
        mode: 评分模式
        pass_threshold: 通过阈值

    Returns:
        GradingReport: 评分报告
    """
    config = GradingConfig(mode=mode, pass_threshold=pass_threshold)
    orchestrator = GradingOrchestrator(config)

    for grader in graders:
        orchestrator.add_grader(grader)

    return await orchestrator.grade(content, {})
