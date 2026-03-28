"""分卷大纲Crew (Volume Outline Crew)

管理分卷大纲的批量生成流程：
1. 接收整体 plot_data
2. 调用 VolumeOutlineAgent 生成各卷大纲（支持并行）
3. 返回分卷大纲列表

使用示例:
    crew = VolumeOutlineCrew(config=config)
    # 顺序生成
    volume_outlines = crew.generate(plot_data, world_data)
    # 并行生成（更快）
    volume_outlines = crew.generate_parallel(plot_data, world_data)
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from crewai.content.base import BaseContentCrew
from crewai.content.novel.agents.volume_outline_agent import VolumeOutlineAgent

if TYPE_CHECKING:
    from crewai.content.novel.production_bible.bible_types import ProductionBible

logger = logging.getLogger(__name__)


class VolumeOutlineCrew(BaseContentCrew):
    """分卷大纲Crew

    管理分卷大纲生成流程。支持顺序和并行两种生成模式。

    使用示例:
        crew = VolumeOutlineCrew(config=config)
        # 顺序生成（兼容旧代码）
        outlines = crew.generate(plot_data, world_data)
        # 并行生成（推荐，更快）
        outlines = crew.generate_parallel(plot_data, world_data)
    """

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents"""
        return {
            "volume_outline": VolumeOutlineAgent(llm=self.config.get("llm")),
        }

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        return None

    def generate(
        self,
        plot_data: dict,
        world_data: dict,
        num_volumes: int | None = None,
        bible: "ProductionBible | None" = None,
        verify: bool = True,
    ) -> list[dict]:
        """生成分卷大纲（顺序）

        Args:
            plot_data: 整体情节规划
            world_data: 世界观数据
            num_volumes: 可选，覆盖卷数
            bible: Production Bible（可选），用于验证
            verify: 是否运行 VolumeOutlineVerifier（默认True）

        Returns:
            list[dict]: 分卷大纲列表
        """
        results = self.agents["volume_outline"].generate(plot_data, world_data, num_volumes)
        if verify and bible:
            verifier = self._get_verifier()
            verification_result = verifier.verify(results, bible, world_data)
            if not verification_result.passed:
                logger.warning(f"Sequential volume outline verification found {len(verification_result.issues)} HARD issues")
                for issue in verification_result.issues:
                    logger.warning(f"  [{issue.severity}] {issue.category}: {issue.description}")
            for warning in verification_result.warnings:
                logger.info(f"  [WARNING] {warning.category}: {warning.description}")
        return results

    def generate_parallel(
        self,
        plot_data: dict,
        world_data: dict,
        num_volumes: int | None = None,
        max_concurrency: int = 3,
        bible: "ProductionBible | None" = None,
        verify: bool = True,
        max_retries: int = 2,
    ) -> list[dict]:
        """并行生成分卷大纲（推荐， optionally with bible context）

        使用多线程并发调用 LLM，同时生成多个卷的大纲。
        适用于卷数较多（≥3卷）的场景，可显著缩短总生成时间。

        Args:
            plot_data: 整体情节规划
            world_data: 世界观数据
            num_volumes: 可选，覆盖卷数
            max_concurrency: 最大并发数（默认3）
            bible: Production Bible（可选），用于约束卷大纲与 canon 一致
            verify: 是否在生成后运行 VolumeOutlineVerifier（默认True）
            max_retries: 验证失败时最大重试次数（默认2）

        Returns:
            list[dict]: 分卷大纲列表（按卷号排序）
        """
        volumes = plot_data.get("volumes", [])
        if num_volumes:
            volumes = volumes[:num_volumes]

        if len(volumes) <= 1:
            # 单卷或无卷，退化为顺序生成
            return self.generate(plot_data, world_data, num_volumes, bible=bible, verify=verify)

        agent = self.agents["volume_outline"]
        section_builder = self._get_section_builder() if bible else None
        verifier = self._get_verifier() if verify and bible else None

        def generate_single(volume_outline: dict) -> dict:
            volume_num = volume_outline.get("volume_num", 1)
            if bible and section_builder:
                bible_section = section_builder.build_section(bible, volume_num)
                return agent.generate_for_volume_with_bible(
                    volume_outline, plot_data, world_data, volume_num, bible_section
                )
            else:
                return agent.generate_for_volume(volume_outline, plot_data, world_data, volume_num)

        # Retry loop: generate → verify → retry on HARD issues
        results: list[dict] = []
        attempt = 0
        while attempt <= max_retries:
            results = []
            with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
                futures = {executor.submit(generate_single, vol): vol for vol in volumes}
                for future in futures:
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Volume generation failed: {e}")
                        # Fallback: use original volume outline
                        results.append(futures[future])

            # Sort by volume number
            results.sort(key=lambda v: v.get("volume_num", 0))

            # Verify unless bible not provided or verify is disabled
            if verifier and bible:
                verification_result = verifier.verify(results, bible, world_data)
                if not verification_result.passed:
                    hard_issues = [i for i in verification_result.issues if i.severity == "HARD"]
                    if hard_issues and attempt < max_retries:
                        attempt += 1
                        logger.warning(f"Volume outline verification FAILED ({len(hard_issues)} HARD issues). Retry {attempt}/{max_retries}")
                        for issue in hard_issues:
                            logger.warning(f"  [HARD] {issue.category}: {issue.description}")
                        continue  # retry
                    else:
                        # Last attempt or no HARD issues
                        logger.warning(f"Volume outline verification found {len(verification_result.issues)} HARD issues")
                        for issue in verification_result.issues:
                            logger.warning(f"  [{issue.severity}] {issue.category}: {issue.description}")
                for warning in verification_result.warnings:
                    logger.info(f"  [WARNING] {warning.category}: {warning.description}")

            # Verification passed or no verifier
            break

        return results

    def _get_section_builder(self) -> "BibleSectionBuilder":
        """Get or create BibleSectionBuilder (lazy import to avoid circular deps)."""
        from crewai.content.novel.production_bible.section_builder import BibleSectionBuilder
        return BibleSectionBuilder()

    def _get_verifier(self) -> "VolumeOutlineVerifier":
        """Get or create VolumeOutlineVerifier (lazy import to avoid circular deps)."""
        from crewai.content.novel.production_bible.outline_verifier import VolumeOutlineVerifier
        return VolumeOutlineVerifier(llm=self.config.get("llm"), verbose=self.verbose)

    def generate_with_feedback(
        self,
        plot_data: dict,
        world_data: dict,
        original_volumes: list,
        feedback: dict,
        feedback_applier: Any = None,
    ) -> list[dict]:
        """根据反馈生成调整后的分卷大纲（顺序模式）

        Args:
            plot_data: 整体情节规划
            world_data: 世界观数据
            original_volumes: 原始分卷大纲
            feedback: 结构化反馈
            feedback_applier: FeedbackApplier 实例

        Returns:
            调整后的分卷大纲
        """
        if feedback_applier is None:
            from crewai.content.novel.feedback_applier import FeedbackApplier
            feedback_applier = FeedbackApplier(llm=self.config.get("llm"))

        return feedback_applier.apply_volume_feedback(original_volumes, feedback)

    def generate_parallel_with_feedback(
        self,
        plot_data: dict,
        world_data: dict,
        original_volumes: list,
        feedback: dict,
        feedback_applier: Any = None,
        max_concurrency: int = 3,
        bible: "ProductionBible | None" = None,
        verify: bool = True,
    ) -> list[dict]:
        """根据反馈生成调整后的分卷大纲（并行模式）

        Args:
            plot_data: 整体情节规划
            world_data: 世界观数据
            original_volumes: 原始分卷大纲
            feedback: 结构化反馈
            feedback_applier: FeedbackApplier 实例
            max_concurrency: 最大并发数
            bible: Production Bible
            verify: 是否验证

        Returns:
            调整后的分卷大纲
        """
        if feedback_applier is None:
            from crewai.content.novel.feedback_applier import FeedbackApplier
            feedback_applier = FeedbackApplier(llm=self.config.get("llm"))

        adjusted = feedback_applier.apply_volume_feedback(original_volumes, feedback)
        if adjusted == original_volumes:
            # 没有变化，直接使用并行生成（重新验证）
            return self.generate_parallel(
                plot_data, world_data,
                max_concurrency=max_concurrency,
                bible=bible, verify=verify,
            )
        return adjusted
