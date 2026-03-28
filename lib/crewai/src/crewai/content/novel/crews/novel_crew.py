"""NovelCrew - 主编排"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict


logger = logging.getLogger(__name__)

from crewai.content.adapters.knowledge_base_adapter import (
    NovelOrchestratorAdapterConfig,
)
from crewai.content.adapters.novel_orchestrator_crew import NovelOrchestratorCrew
from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.memory.continuity_tracker import ContinuityTracker
from crewai.content.memory.entity_memory import EntityMemory
from crewai.content.memory.memory_types import Entity, Event
from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator
from crewai.content.novel.agents.plot_agent import PlotAgent
from crewai.content.novel.crews.chapter_summary_crew import ChapterSummaryCrew
from crewai.content.novel.crews.outline_crew import OutlineCrew
from crewai.content.novel.crews.review_crew import ReviewCrew
from crewai.content.novel.crews.volume_outline_crew import VolumeOutlineCrew
from crewai.content.novel.crews.world_crew import WorldCrew
from crewai.content.novel.crews.writing_crew import WritingCrew
from crewai.content.novel.novel_types import ChapterOutput, NovelOutput, WritingContext
from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.human_feedback import (
    HumanFeedback,
    FeedbackParser,
    ApprovalDecision,
    ApprovalWorkflow,
    create_approval_feedback,
)
from crewai.content.novel.feedback_applier import FeedbackApplier
from crewai.content.review.global_postpass import GlobalPostPass
from crewai.content.review.per_chapter_postpass import PerChapterPostPass, PostPassResult
from crewai.content.review.review_context import ReviewContext
from crewai.content.exceptions import ValidationError


if TYPE_CHECKING:
    pass


class PendingChapterApproval(Exception):
    """章节待审批异常

    当 review_each_chapter=True 时，章节完成后会抛出此异常，
    表示需要用户审批后才能继续下一章。

    Attributes:
        chapter_num: 章节号
        chapter_output: 章节输出
        pipeline_state_path: 流水线状态保存路径
    """

    def __init__(
        self,
        message: str,
        chapter_num: int,
        chapter_output: ChapterOutput,
        pipeline_state_path: str,
    ):
        super().__init__(message)
        self.chapter_num = chapter_num
        self.chapter_output = chapter_output
        self.pipeline_state_path = pipeline_state_path


class NovelCrew(BaseContentCrew):
    """小说内容生成主编排Crew

    协调其他Crews完成完整的小说创作流程：
    1. OutlineCrew - 生成大纲（世界观 + 情节规划）
    2. OutlineEvaluator - 评估大纲质量（Evaluator-Optimizer Gate）
    3. VolumeOutlineCrew - 生成分卷大纲
    4. ChapterSummaryCrew - 生成章节概要
    5. WritingCrew - 撰写章节初稿
    6. ReviewCrew - 审查和修改

    使用示例:
        crew = NovelCrew(config={
            "topic": "修仙逆袭",
            "style": "xianxia",
            "num_chapters": 30,
            "target_words": 500000,
        })
        result = crew.kickoff()
        novel = result.content  # NovelOutput
    """

    def __init__(self, config: Any, agents: dict[str, Any] | None = None, tasks: dict[str, Any] | None = None, verbose: bool = True):
        super().__init__(config, agents, tasks, verbose)
        self._world_crew: WorldCrew | None = None
        self._outline_crew: OutlineCrew | None = None
        self._volume_outline_crew: VolumeOutlineCrew | None = None
        self._chapter_summary_crew: ChapterSummaryCrew | None = None
        self._writing_crew: WritingCrew | None = None
        self._review_crew: ReviewCrew | None = None
        self._plot_agent: PlotAgent | None = None
        self._outline_evaluator: OutlineEvaluator | None = None
        self._orchestrator_crew: NovelOrchestratorCrew | None = None
        # Chapter artifact storage: chapter_n -> {phase: content}
        self._chapter_artifacts: dict[int, dict[str, Any]] = {}
        # Memory integration for entity tracking and continuity
        self._entity_memory: EntityMemory | None = None
        self._continuity_tracker: ContinuityTracker | None = None
        # Pipeline state for cross-stage persistence
        self._pipeline_state: PipelineState | None = None
        # Production Bible for parallel generation consistency
        self._production_bible: Any = None
        # Per-Chapter PostPass for consistency verification
        self._per_chapter_postpass: PerChapterPostPass | None = None

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents - 委托给子Crews"""
        return {}

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks - 委托给子Crews"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流 - 委托给子Crews"""
        return None

    @property
    def world_crew(self) -> WorldCrew:
        """获取世界观构建Crew"""
        if self._world_crew is None:
            self._world_crew = WorldCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._world_crew

    @property
    def outline_crew(self) -> OutlineCrew:
        """获取大纲生成Crew"""
        if self._outline_crew is None:
            self._outline_crew = OutlineCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._outline_crew

    @property
    def volume_outline_crew(self) -> VolumeOutlineCrew:
        """获取分卷大纲生成Crew"""
        if self._volume_outline_crew is None:
            self._volume_outline_crew = VolumeOutlineCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._volume_outline_crew

    @property
    def chapter_summary_crew(self) -> ChapterSummaryCrew:
        """获取章节概要生成Crew"""
        if self._chapter_summary_crew is None:
            self._chapter_summary_crew = ChapterSummaryCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._chapter_summary_crew

    @property
    def writing_crew(self) -> WritingCrew:
        """获取写作Crew"""
        if self._writing_crew is None:
            self._writing_crew = WritingCrew(
                config=self.config,
                entity_memory=self.entity_memory,
                continuity_tracker=self.continuity_tracker,
                verbose=self.verbose,
            )
        return self._writing_crew

    @property
    def review_crew(self) -> ReviewCrew:
        """获取审查Crew"""
        if self._review_crew is None:
            self._review_crew = ReviewCrew(
                config=self.config,
                verbose=self.verbose,
            )
        return self._review_crew

    @property
    def orchestrator_crew(self) -> NovelOrchestratorCrew:
        """获取基于知识库编排器的写作Crew（可选）"""
        if self._orchestrator_crew is None:
            adapter_config = NovelOrchestratorAdapterConfig(
                max_subagent_concurrent=self.config.get("max_subagent_concurrent", 5),
                max_concurrent_scenes=self.config.get("max_concurrent_scenes", 3),
                enable_verification=self.config.get("enable_verification", True),
                enable_evolution=self.config.get("enable_evolution", True),
            )
            self._orchestrator_crew = NovelOrchestratorCrew(
                config=self.config,
                verbose=self.verbose,
                adapter_config=adapter_config,
            )
        return self._orchestrator_crew

    @property
    def plot_agent(self) -> PlotAgent:
        """获取情节规划Agent"""
        if self._plot_agent is None:
            self._plot_agent = PlotAgent(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._plot_agent

    @property
    def outline_evaluator(self) -> OutlineEvaluator:
        """获取大纲评估器"""
        if self._outline_evaluator is None:
            self._outline_evaluator = OutlineEvaluator(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._outline_evaluator

    @property
    def pipeline_state(self) -> PipelineState:
        """获取流水线状态"""
        if self._pipeline_state is None:
            self._pipeline_state = PipelineState(
                config=dict(self.config) if hasattr(self.config, "keys") else {},
            )
        return self._pipeline_state

    def load_pipeline_state(self, path: str) -> PipelineState:
        """从磁盘加载流水线状态

        Args:
            path: 状态文件路径

        Returns:
            PipelineState: 加载的状态
        """
        self._pipeline_state = PipelineState.load(path)
        return self._pipeline_state

    def save_pipeline_state(self, path: str) -> None:
        """保存流水线状态到磁盘

        Args:
            path: 状态文件路径
        """
        self.pipeline_state.save(path)

    @property
    def entity_memory(self) -> EntityMemory:
        """获取实体记忆系统"""
        if self._entity_memory is None:
            self._entity_memory = EntityMemory()
        return self._entity_memory

    @property
    def continuity_tracker(self) -> ContinuityTracker:
        """获取连续性追踪器"""
        if self._continuity_tracker is None:
            self._continuity_tracker = ContinuityTracker()
        return self._continuity_tracker

    @property
    def per_chapter_postpass(self) -> PerChapterPostPass:
        """获取每章 PostPass"""
        if self._per_chapter_postpass is None:
            self._per_chapter_postpass = PerChapterPostPass()
        return self._per_chapter_postpass

    def save_artifact(self, chapter_num: int, phase: str, content: Any) -> None:
        """Save chapter artifact for a specific phase.

        Args:
            chapter_num: Chapter number
            phase: One of 'outline', 'draft', 'critique', 'revised', 'polished'
            content: The artifact content
        """
        if chapter_num not in self._chapter_artifacts:
            self._chapter_artifacts[chapter_num] = {}
        self._chapter_artifacts[chapter_num][phase] = content

    def get_artifact(self, chapter_num: int, phase: str) -> Any | None:
        """Retrieve saved artifact for a chapter and phase."""
        return self._chapter_artifacts.get(chapter_num, {}).get(phase)

    def has_artifact(self, chapter_num: int, phase: str) -> bool:
        """Check if artifact exists for chapter and phase."""
        return chapter_num in self._chapter_artifacts and phase in self._chapter_artifacts[chapter_num]

    def _get_novel_output_dir(self) -> str:
        """Get the output directory for the novel: novels/{novel_name}_{timestamp}/

        Uses timestamp to isolate different runs of the same novel topic.
        Cached after first call to ensure consistent directory throughout a run.
        """
        # Cache the output directory to ensure consistency within a single run
        if not hasattr(self, '_cached_output_dir'):
            topic = self.config.get("topic", "未命名小说")
            # Sanitize topic for filesystem
            safe_topic = "".join(c if c.isalnum() or c in "_- " else "_" for c in topic)
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._cached_output_dir = f"novels/{safe_topic}_{timestamp}"
        return self._cached_output_dir

    def _save_chapter_checkpoint(self, chapter_output: ChapterOutput) -> None:
        """Save chapter content to disk immediately as checkpoint.

        Uses atomic write (temp file + rename) to ensure version always works.
        Directory: novels/{novel_name}/chapters/
        Filename: {chapter_num:03d}.{title}.md

        Args:
            chapter_output: The completed chapter output
        """
        import json
        import os
        import tempfile
        from pathlib import Path
        from datetime import datetime

        output_dir = self._get_novel_output_dir()
        topic = self.config.get("topic", "未命名小说")

        # Create chapters directory
        chapters_dir = Path(output_dir) / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)

        # Build filename: 001.第一章标题.md
        chapter_num = chapter_output.chapter_num
        # Ensure chapter_num is integer for formatting
        try:
            chapter_num_int = int(chapter_num)
        except (ValueError, TypeError):
            chapter_num_int = 1
        title = getattr(chapter_output, "title", f"第{chapter_num}章")
        # Sanitize title for filename
        safe_title = "".join(c if c.isalnum() or c in "_- " else "_" for c in title)[:50]
        chapter_filename = f"{chapter_num_int:03d}.{safe_title}.md"
        chapter_file = chapters_dir / chapter_filename

        # Build markdown content with frontmatter
        content = chapter_output.content if hasattr(chapter_output, "content") else str(chapter_output)
        word_count = chapter_output.word_count or len(content) // 2

        markdown_content = f"""---
title: "{title}"
chapter: {chapter_num}
novel: "{topic}"
generated_at: "{datetime.now().isoformat()}"
word_count: {word_count}
---

# {title}

{content}
"""

        # Atomic write: write to temp file, then rename
        temp_fd, temp_path = tempfile.mkstemp(suffix=".md", dir=str(chapters_dir))
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            # Atomic rename (on POSIX this is atomic if within same filesystem)
            os.replace(temp_path, chapter_file)
            logger.info(f"Checkpoint saved: {chapter_file} ({word_count} words)")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint for chapter {chapter_num}: {e}")
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        # Update result.json with current progress (also atomic)
        result_file = Path(output_dir) / "result.json"
        result_temp_fd, result_temp_path = tempfile.mkstemp(suffix=".json", dir=str(chapters_dir))
        try:
            # Read existing result or create new
            if result_file.exists():
                with open(result_file, "r", encoding="utf-8") as f:
                    result_data = json.load(f)
            else:
                result_data = {
                    "topic": topic,
                    "target_words": self.config.get("target_words", 0),
                    "style": self.config.get("style", ""),
                    "title": topic,
                    "chapters_count": 0,
                    "word_count": 0,
                }

            # Update with current chapter (take max to avoid double-counting on retries)
            result_data["chapters_count"] = max(result_data.get("chapters_count", 0), chapter_num)
            result_data["word_count"] = (result_data.get("word_count", 0) or 0) + word_count
            result_data["last_updated"] = datetime.now().isoformat()
            result_data["last_chapter"] = chapter_num

            # Write atomically
            with os.fdopen(result_temp_fd, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            os.replace(result_temp_path, result_file)
        except Exception as e:
            logger.warning(f"Failed to update result.json: {e}")
            if os.path.exists(result_temp_path):
                os.unlink(result_temp_path)

    def _save_outline_checkpoint(self, world_data: dict, plot_data: dict, stage: str) -> None:
        """Save outline/evaluation artifacts to disk atomically.

        Saves: world.md, outline.md, evaluation.json to novels/{novel_name}/outline/

        Args:
            world_data: World-building data
            plot_data: Plot planning data
            stage: Current pipeline stage name
        """
        import json
        import os
        import tempfile
        from pathlib import Path
        from datetime import datetime

        output_dir = self._get_novel_output_dir()
        topic = self.config.get("topic", "未命名小说")

        # Create outline directory
        outline_dir = Path(output_dir) / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)

        # Save world.md
        world_content = f"""# 世界观: {world_data.get('name', topic)}

## 简介
{world_data.get('description', '待补充')}

## 势力
{world_data.get('factions', '待补充')}

## 地点
{world_data.get('locations', '待补充')}

## 力量体系
{world_data.get('power_system', '待补充')}

---
生成时间: {datetime.now().isoformat()}
阶段: {stage}
"""
        self._atomic_write(outline_dir / "world.md", world_content)

        # Save outline.md
        outline_content = f"""# 情节大纲: {topic}

## 主线
{plot_data.get('main_strand', {}).get('description', '待补充')}

## 卷结构
{json.dumps(plot_data.get('volumes', []), ensure_ascii=False, indent=2)}

## 高潮点
{json.dumps(plot_data.get('high_points', []), ensure_ascii=False, indent=2)}

---
生成时间: {datetime.now().isoformat()}
阶段: {stage}
"""
        self._atomic_write(outline_dir / "outline.md", outline_content)

        # Save metadata.json
        metadata = {
            "topic": topic,
            "stage": stage,
            "generated_at": datetime.now().isoformat(),
            "world_name": world_data.get('name', '未知'),
            "chapter_count": len(plot_data.get('volumes', [])) * 10,
        }
        self._atomic_write_json(outline_dir / "metadata.json", metadata)

        logger.info(f"Outline checkpoint saved: {outline_dir}")

    def _atomic_write(self, path: Path, content: str) -> None:
        """Atomically write content to file (temp file + rename)."""
        import os
        import tempfile
        try:
            temp_fd, temp_path = tempfile.mkstemp(dir=str(path.parent))
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, path)
        except Exception as e:
            logger.warning(f"Failed to write {path}: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Atomically write JSON to file (temp file + rename)."""
        import json
        import os
        import tempfile
        try:
            temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=str(path.parent))
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception as e:
            logger.warning(f"Failed to write JSON {path}: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def kickoff(
        self,
        stop_at: str | None = None,
        pipeline_state_path: str | None = None,
        review_each_chapter: bool = False,
        approval_mode: bool = False,
        seed: str | None = None,
    ) -> BaseCrewOutput:
        """执行完整的小说创作流程

        Args:
            stop_at: 可选，在指定阶段暂停并返回。
                      支持的值：None (完整流程), "outline", "evaluation", "volume", "summary"
            pipeline_state_path: 可选，从指定路径加载流水线状态，实现断点续跑。
            review_each_chapter: 可选，是否在每章写完后暂停等待确认（逐章审核模式）。
            approval_mode: 可选，是否开启审批模式。开启后，每个阶段（outline, volume, summary）
                          完成后会暂停等待用户审批。
            seed: 可选，用于确定性重放的 seed。如果提供，会验证与已保存状态的 seed 匹配。
                  不匹配时，不加载已有状态，从头开始生成核心内容（世界观、大纲等）。
                  如果未提供但配置中有 seed，会自动使用配置的 seed。

        Returns:
            BaseCrewOutput: 包含NovelOutput的crew输出，或PipelineState
        """
        import time
        start = time.time()

        # 自动生成 seed（如果配置中提供了 topic, genre, style）
        if seed is None:
            seed = self.config.get("seed")
        if seed is None:
            topic = self.config.get("topic", "")
            genre = self.config.get("genre", "")
            style = self.config.get("style", "")
            if topic:
                seed = PipelineState.generate_seed(topic, genre, style)

        # 设置 seed 到 pipeline_state（用于保存时记录）
        if seed:
            self.pipeline_state.seed = seed
            # 将 seed 传递给 LLM，使其真正影响 LLM 输出
            # 将 32 字符 hex seed 转换为 int（取模 2^32 以适应 API 要求）
            llm = self.config.get("llm")
            if llm and hasattr(llm, 'seed'):
                llm_seed = int(seed, 16) % (2**32)
                llm.seed = llm_seed
                logger.info(f"LLM seed set to {llm_seed} (from hex: {seed})")

        # 如果提供了状态路径，加载已有状态以支持断点续跑
        if pipeline_state_path:
            loaded_state = PipelineState.load(pipeline_state_path)
            # Seed 验证：seed 不匹配时不加载已有状态，从头开始生成
            if seed and not loaded_state.seed_valid(seed):
                logger.warning(
                    f"Seed mismatch: expected '{seed}', got '{loaded_state.seed}'. "
                    f"Will regenerate core content (world, outline, etc.)"
                )
                # 重置状态，只保留 seed
                self._pipeline_state = PipelineState(config=dict(self.config) if hasattr(self.config, "keys") else {})
                self._pipeline_state.seed = seed
            else:
                self._pipeline_state = loaded_state

        # 获取当前流水线阶段
        current_stage = self.pipeline_state.current_stage

        # 阶段顺序定义
        stage_order = ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]

        # 确定目标阶段索引
        target_stage = stop_at if stop_at else "complete"
        try:
            target_idx = stage_order.index(target_stage)
        except ValueError:
            target_idx = len(stage_order) - 1

        # 确定从哪里开始（基于已完成的阶段）
        try:
            current_idx = stage_order.index(current_stage)
        except ValueError:
            current_idx = 0

        # 审批模式初始化
        self._approval_mode = approval_mode
        if approval_mode:
            self.pipeline_state.enable_approval_mode()
            self._approval_workflow = ApprovalWorkflow(self.pipeline_state, llm=self.config.get("llm"))
            logger.info("Approval mode enabled")

            # 检查是否有待处理的反馈
            pending = self.pipeline_state.get_pending_feedback()
            if pending:
                logger.info(f"Found pending feedback for stage '{pending.get('stage')}'")

        # PHASE 1: 生成大纲（包含世界观构建）
        # 条件：当前阶段在outline之前 且 目标阶段在outline或之后
        outline_idx = stage_order.index("outline")
        if current_idx < outline_idx and target_idx >= outline_idx:
            outline_data = self.outline_crew.generate_outline()
            world_data = outline_data.get("world", {})
            plot_data = outline_data.get("plot", {})

            # 保存大纲数据到流水线状态
            self.pipeline_state.set_outline_data(outline_data)
            self.pipeline_state.set_stage("outline")

            # 审批模式：暂停等待用户审批
            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("outline", "pending")
                return self._pack_approval_output(
                    stage="outline",
                    content={
                        "world_data": world_data,
                        "plot_data": plot_data,
                        "evaluation": None,  # evaluation 还未运行
                    },
                    execution_time=time.time() - start,
                )
        else:
            # 从状态恢复
            outline_data = self.pipeline_state.outline_data or {}
            world_data = outline_data.get("world", {})
            plot_data = outline_data.get("plot", {})

            # 审批模式：检查是否有针对 outline 的反馈需要处理
            if approval_mode:
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("stage") == "outline":
                    # 处理用户反馈
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.APPROVE:
                        self.pipeline_state.set_stage_status("outline", "approve")
                        logger.info("Outline approved by user")
                    elif feedback.decision == ApprovalDecision.REVISE:
                        # 需要基于反馈重新生成 outline
                        logger.info("User requested outline revision")
                        feedback_applier = FeedbackApplier(llm=self.config.get("llm"))
                        # 重新生成大纲
                        outline_data = self.outline_crew.generate_outline_with_feedback(
                            original_outline=outline_data,
                            feedback=feedback.structured,
                            feedback_applier=feedback_applier,
                        )
                        world_data = outline_data.get("world", {})
                        plot_data = outline_data.get("plot", {})
                        self.pipeline_state.set_outline_data(outline_data)
                        self.pipeline_state.clear_pending_feedback()
                        # 重新进入 outline 完成后的流程
                        if stop_at == "outline":
                            return self._pack_state_output(
                                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data), "regenerated": True},
                                execution_time=time.time() - start,
                            )
                    elif feedback.decision == ApprovalDecision.REJECT:
                        # 拒绝，完全重新生成（忽略原大纲）
                        logger.info("User rejected outline, regenerating from scratch...")
                        outline_data = self.outline_crew.generate_outline()
                        world_data = outline_data.get("world", {})
                        plot_data = outline_data.get("plot", {})
                        self.pipeline_state.set_outline_data(outline_data)
                        self.pipeline_state.clear_pending_feedback()
                        if stop_at == "outline":
                            return self._pack_state_output(
                                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data), "regenerated": True},
                                execution_time=time.time() - start,
                            )

        if stop_at == "outline":
            return self._pack_state_output(
                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data)},
                execution_time=time.time() - start,
            )

        # PHASE 2: 大纲评估（Evaluator-Optimizer Gate）
        # 条件：当前阶段在evaluation之前 且 (目标在evaluation之后 或 目标是evaluation本身)
        evaluation_idx = stage_order.index("evaluation")
        eval_result = None
        if current_idx < evaluation_idx and (target_idx > evaluation_idx or stop_at == "evaluation"):
            eval_result, revised_plot = self.outline_evaluator.evaluate_and_revise(
                world_data, plot_data,
                max_retries=2,
            )

            # 如果评估不通过，打印警告但继续（因为evaluate_and_revise已尝试修正）
            if not eval_result.passed:
                logger.warning(f"Outline evaluation issues: {eval_result.issues}")
                logger.warning(f"Suggestions: {eval_result.suggestions}")

            # 保存评估结果
            self.pipeline_state.set_evaluation_result(
                {
                    "score": eval_result.score,
                    "issues": eval_result.issues,
                    "suggestions": eval_result.suggestions,
                },
                passed=eval_result.passed,
            )

            # 如果plot_data被修正过，更新它
            if revised_plot and "error" not in revised_plot:
                plot_data = revised_plot

            self.pipeline_state.set_stage("evaluation")

            # 保存大纲检查点（原子写入）
            self._save_outline_checkpoint(world_data, plot_data, "evaluation")

        # Build ProductionBible after evaluation (before parallel volume generation)
        # This bible is the single source of truth for all parallel generation
        bible = None
        if self._production_bible is None:
            try:
                # 优先尝试从已保存的 pipeline_state 中重建 bible（resume 场景）
                if self.pipeline_state.bible_serialized or (self.pipeline_state.world_data and self.pipeline_state.plot_data):
                    bible = self.pipeline_state.rebuild_bible()
                    if bible:
                        logger.info("ProductionBible rebuilt from pipeline state")
                # 如果重建失败或无序列化数据，则从头构建
                if bible is None:
                    from crewai.content.novel.production_bible import (
                        ProductionBibleBuilder,
                    )
                    builder = ProductionBibleBuilder()
                    bible = builder.build(world_data, plot_data)
                self._production_bible = bible
                # 保存 bible 到 pipeline_state（供后续 save 时序列化）
                self.pipeline_state.set_bible(bible)
            except Exception as e:
                logger.warning(f"Failed to build ProductionBible: {e}")
                bible = None
        else:
            bible = self._production_bible

        if stop_at == "evaluation":
            eval_result = eval_result or self.pipeline_state.outline_evaluation or type('EvalResult', (), {'passed': False, 'score': 0.0, 'issues': [], 'suggestions': []})()
            return self._pack_state_output(
                pipeline_summary={
                    "stage": "evaluation",
                    "evaluation_passed": eval_result.passed,
                    "evaluation_score": eval_result.score,
                    "evaluation_issues": eval_result.issues,
                    "bible_built": bible is not None,
                },
                execution_time=time.time() - start,
            )
        # 从状态恢复
        eval_data = self.pipeline_state.outline_evaluation
        if eval_data:
            eval_result = type('EvalResult', (), {
                'passed': eval_data.get('passed', False),
                'score': eval_data.get('score', 0.0),
                'issues': eval_data.get('issues', []),
                'suggestions': eval_data.get('suggestions', []),
            })()

        # PHASE 3: 分卷大纲生成
        # 条件：当前阶段在volume之前 且 (目标在volume之后 或 目标是volume本身)
        volume_idx = stage_order.index("volume")
        volume_outlines = None
        if current_idx < volume_idx and (target_idx > volume_idx or stop_at == "volume"):
            # 使用并行生成（多卷并发）
            num_volumes = self.config.get("num_volumes", 3)
            max_conc = self.config.get("max_concurrent_volumes", 3)
            if num_volumes >= 2:
                volume_outlines = self.volume_outline_crew.generate_parallel(
                    plot_data, world_data, max_concurrency=max_conc,
                    bible=bible, verify=True
                )
            else:
                volume_outlines = self.volume_outline_crew.generate(plot_data, world_data)
            self.pipeline_state.set_volume_outlines(volume_outlines)
            self.pipeline_state.set_stage("volume")

            # 审批模式：暂停等待用户审批
            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("volume", "pending")
                return self._pack_approval_output(
                    stage="volume",
                    content={
                        "volume_outlines": volume_outlines,
                    },
                    execution_time=time.time() - start,
                )
        else:
            # 从状态恢复
            volume_outlines = self.pipeline_state.volume_outlines

            # 审批模式：检查是否有针对 volume 的反馈需要处理
            if approval_mode:
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("stage") == "volume":
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.APPROVE:
                        self.pipeline_state.set_stage_status("volume", "approve")
                        logger.info("Volume approved by user")
                    elif feedback.decision in (ApprovalDecision.REVISE, ApprovalDecision.REJECT):
                        # 需要基于反馈重新生成分卷大纲
                        logger.info(f"User requested volume {feedback.decision.value}, regenerating...")
                        feedback_applier = FeedbackApplier(llm=self.config.get("llm"))
                        num_volumes = self.config.get("num_volumes", 3)
                        max_conc = self.config.get("max_concurrent_volumes", 3)
                        if num_volumes >= 2:
                            volume_outlines = self.volume_outline_crew.generate_parallel_with_feedback(
                                plot_data, world_data,
                                original_volumes=volume_outlines,
                                feedback=feedback.structured,
                                feedback_applier=feedback_applier,
                                max_concurrency=max_conc,
                                bible=bible, verify=True
                            )
                        else:
                            volume_outlines = self.volume_outline_crew.generate_with_feedback(
                                plot_data, world_data,
                                original_volumes=volume_outlines,
                                feedback=feedback.structured,
                                feedback_applier=feedback_applier,
                            )
                        self.pipeline_state.set_volume_outlines(volume_outlines)
                        self.pipeline_state.clear_pending_feedback()

        if stop_at == "volume":
            return self._pack_state_output(
                pipeline_summary={
                    "stage": "volume",
                    "volumes_count": len(volume_outlines) if volume_outlines else 0,
                },
                execution_time=time.time() - start,
            )

        # PHASE 4: 章节概要生成
        # 条件：当前阶段在summary之前 且 (目标在summary之后 或 目标是summary本身)
        summary_idx = stage_order.index("summary")
        chapter_summaries = None
        if current_idx < summary_idx and (target_idx > summary_idx or stop_at == "summary"):
            # 使用并行生成（多卷并发）
            num_volumes = len(volume_outlines) if volume_outlines else 1
            max_conc = self.config.get("max_concurrent_volumes", 3)
            if num_volumes >= 2:
                chapter_summaries = self.chapter_summary_crew.generate_parallel(
                    volume_outlines, world_data, bible=bible, max_concurrency=max_conc
                )
            else:
                chapter_summaries = self.chapter_summary_crew.generate(volume_outlines, world_data, bible=bible)
            self.pipeline_state.set_chapter_summaries(chapter_summaries)
            self.pipeline_state.set_stage("summary")

            # 审批模式：暂停等待用户审批
            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("summary", "pending")
                return self._pack_approval_output(
                    stage="summary",
                    content={
                        "chapter_summaries": chapter_summaries,
                    },
                    execution_time=time.time() - start,
                )
        else:
            # 从状态恢复
            chapter_summaries = self.pipeline_state.chapter_summaries

            # 审批模式：检查是否有针对 summary 的反馈需要处理
            if approval_mode:
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("stage") == "summary":
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.APPROVE:
                        self.pipeline_state.set_stage_status("summary", "approve")
                        logger.info("Summary approved by user")
                    elif feedback.decision in (ApprovalDecision.REVISE, ApprovalDecision.REJECT):
                        logger.info(f"User requested summary {feedback.decision.value}, regenerating...")
                        feedback_applier = FeedbackApplier(llm=self.config.get("llm"))
                        chapter_num = feedback.chapter_num  # 可以指定修改特定章节
                        if num_volumes >= 2:
                            chapter_summaries = self.chapter_summary_crew.generate_parallel_with_feedback(
                                volume_outlines, world_data,
                                original_summaries=chapter_summaries,
                                feedback=feedback.structured,
                                feedback_applier=feedback_applier,
                                max_concurrency=self.config.get("max_concurrent_volumes", 3),
                                bible=bible,
                                target_chapter=chapter_num,
                            )
                        else:
                            chapter_summaries = self.chapter_summary_crew.generate_with_feedback(
                                volume_outlines, world_data,
                                original_summaries=chapter_summaries,
                                feedback=feedback.structured,
                                feedback_applier=feedback_applier,
                                bible=bible,
                                target_chapter=chapter_num,
                            )
                        self.pipeline_state.set_chapter_summaries(chapter_summaries)
                        self.pipeline_state.clear_pending_feedback()

        if stop_at == "summary":
            return self._pack_state_output(
                pipeline_summary={
                    "stage": "summary",
                    "summaries_count": len(chapter_summaries) if chapter_summaries else 0,
                },
                execution_time=time.time() - start,
            )

        # PHASE 5: 撰写章节（使用章节概要）
        try:
            chapters = self._write_all_chapters_from_summaries(world_data, chapter_summaries, review_each_chapter=review_each_chapter)
        except PendingChapterApproval as e:
            # 保存状态并返回待审批结果
            self.pipeline_state.set_stage("writing")
            return self._pack_approval_output(
                stage="chapter",
                content={
                    "chapter_num": e.chapter_num,
                    "chapter_output": e.chapter_output,
                    "pipeline_state_path": e.pipeline_state_path,
                },
                execution_time=time.time() - start,
            )

        # Run Global PostPass
        postpass = GlobalPostPass(continuity_tracker=self._continuity_tracker)
        global_report = postpass.run(chapters, world_data)

        # Log issues if any
        if not global_report.passed:
            logger.warning(f"Global PostPass found {len(global_report.character_death_issues)} character death issues")
            logger.warning(f"Global PostPass found {len(global_report.transition_issues)} transition issues")

        # 组装输出
        novel_output = NovelOutput(
            title=self.config.get("topic", "未命名小说"),
            genre=self.config.get("genre", ""),
            style=self.config.get("style", ""),
            world_output=world_data,
            chapters=chapters,
            total_word_count=sum(c.word_count for c in chapters),
        )

        self.pipeline_state.finalize()

        execution_time = time.time() - start

        # Build artifact summary for metadata
        artifact_summary = {
            chapter_num: list(artifacts.keys())
            for chapter_num, artifacts in self._chapter_artifacts.items()
        }

        return BaseCrewOutput(
            content=novel_output,
            tasks_completed=[
                "构建世界观",
                "生成章节大纲",
                "大纲评估",
                "生成分卷大纲",
                "生成章节概要",
                "撰写章节初稿",
                "审查和修改",
            ],
            execution_time=execution_time,
            metadata={
                "config": self.config.__dict__ if hasattr(self.config, "__dict__") else {},
                "chapter_count": len(chapters),
                "total_words": novel_output.total_word_count,
                "artifacts": artifact_summary,
                "global_postpass": global_report.to_dict(),
                "pipeline_state": self.pipeline_state.to_summary(),
            },
        )

    def _pack_state_output(self, pipeline_summary: dict, execution_time: float) -> BaseCrewOutput:
        """打包流水线状态为输出（用于 stop_at 模式）"""
        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"完成阶段: {pipeline_summary.get('stage', 'unknown')}"],
            execution_time=execution_time,
            metadata={
                "pipeline_state": pipeline_summary,
                "stopped": True,
            },
        )

    def _pack_approval_output(
        self,
        stage: str,
        content: dict,
        execution_time: float,
    ) -> BaseCrewOutput:
        """打包审批状态为输出（用于 approval_mode 暂停点）

        Args:
            stage: 当前阶段名
            content: 该阶段的生成内容
            execution_time: 执行时间

        Returns:
            BaseCrewOutput: 包含待审批内容的输出
        """
        # 保存当前状态以便恢复
        state_path = f".novel_pipeline_{stage}_pending.json"
        self.pipeline_state.save(state_path)
        logger.info(f"Pipeline state saved to {state_path} for approval")

        return BaseCrewOutput(
            content=None,
            tasks_completed=[f"等待审批: {stage}"],
            execution_time=execution_time,
            metadata={
                "approval_required": True,
                "stage": stage,
                "stage_status": "pending_approval",
                "pipeline_state_path": state_path,
                "content_summary": self._summarize_stage_content(stage, content),
                "feedback_options": {
                    "approve": "通过当前内容，继续下一阶段",
                    "revise": "需要修改，请提供修改意见",
                    "reject": "拒绝，重新生成",
                    "reinstruct": "重新指令，大幅修改",
                    "skip": "跳过此阶段",
                },
            },
        )

    def _summarize_stage_content(self, stage: str, content: dict) -> dict:
        """生成阶段内容的摘要（用于显示给用户）

        Args:
            stage: 阶段名
            content: 阶段内容

        Returns:
            摘要字典
        """
        if stage == "outline":
            return {
                "world_name": content.get("world_data", {}).get("name", ""),
                "world_summary": str(content.get("world_data", {}))[:200] + "...",
                "plot_summary": str(content.get("plot_data", {}))[:200] + "...",
            }
        elif stage == "volume":
            volumes = content.get("volume_outlines", [])
            return {
                "volumes_count": len(volumes),
                "volume_titles": [v.get("title", "") for v in volumes[:3]],
            }
        elif stage == "summary":
            summaries = content.get("chapter_summaries", [])
            return {
                "chapters_count": len(summaries),
                "chapter_titles": [s.get("title", "") for s in summaries[:5]],
            }
        elif stage == "chapter":
            chapter_output = content.get("chapter_output")
            return {
                "chapter_num": content.get("chapter_num"),
                "chapter_title": getattr(chapter_output, "title", "") if chapter_output else "",
                "word_count": getattr(chapter_output, "word_count", 0) if chapter_output else 0,
                "key_events": getattr(chapter_output, "key_events", []) if chapter_output else [],
            }
        return {}

    def submit_feedback(
        self,
        feedback: HumanFeedback | dict,
        pipeline_state_path: str | None = None,
    ) -> BaseCrewOutput:
        """提交用户反馈并继续生成

        Args:
            feedback: 用户反馈（HumanFeedback 对象或字典）
            pipeline_state_path: 可选，流水线状态路径

        Returns:
            BaseCrewOutput: 继续执行的结果
        """
        # 解析反馈
        if isinstance(feedback, dict):
            feedback = HumanFeedback.from_dict(feedback)

        # 解析自然语言
        if feedback.natural_language and not feedback.structured:
            parser = FeedbackParser(llm=self.config.get("llm"))
            feedback.structured = parser.parse(feedback)

        # 加载流水线状态
        if pipeline_state_path:
            self.load_pipeline_state(pipeline_state_path)
        elif self.pipeline_state.pending_feedback:
            # 使用内存中的状态
            pass
        else:
            raise ValueError("No pipeline state found. Please provide pipeline_state_path.")

        # 设置待处理反馈
        self.pipeline_state.set_pending_feedback(feedback.to_dict())

        # 记录审批历史
        self.pipeline_state.add_approval_record({
            "stage": feedback.stage,
            "decision": feedback.decision.value,
            "natural_language": feedback.natural_language,
            "structured": feedback.structured,
        })

        # 继续执行
        return self.kickoff(
            stop_at=None,
            approval_mode=True,  # 保持审批模式
        )

    def approve(
        self,
        stage: str,
        pipeline_state_path: str | None = None,
    ) -> BaseCrewOutput:
        """快速通过当前阶段（无修改意见）

        Args:
            stage: 阶段名 (outline, volume, summary)
            pipeline_state_path: 可选，流水线状态路径

        Returns:
            BaseCrewOutput: 继续执行的结果
        """
        feedback = create_approval_feedback(
            stage=stage,
            decision="approve",
            natural_language="",
        )
        return self.submit_feedback(feedback, pipeline_state_path)

    def revise(
        self,
        stage: str,
        feedback_text: str,
        pipeline_state_path: str | None = None,
    ) -> BaseCrewOutput:
        """请求修改（带自然语言反馈）

        Args:
            stage: 阶段名
            feedback_text: 自然语言修改意见
            pipeline_state_path: 可选，流水线状态路径

        Returns:
            BaseCrewOutput: 继续执行的结果
        """
        feedback = create_approval_feedback(
            stage=stage,
            decision="revise",
            natural_language=feedback_text,
        )
        return self.submit_feedback(feedback, pipeline_state_path)

    def approve_chapter(
        self,
        chapter_num: int,
        pipeline_state_path: str | None = None,
    ) -> BaseCrewOutput:
        """快速通过章节（无修改意见）

        Args:
            chapter_num: 章节号
            pipeline_state_path: 可选，流水线状态路径

        Returns:
            BaseCrewOutput: 继续执行的结果
        """
        feedback = HumanFeedback(
            stage=f"chapter_{chapter_num}",
            decision=ApprovalDecision.APPROVE,
            natural_language="",
            chapter_num=chapter_num,
        )
        return self.submit_feedback(feedback, pipeline_state_path)

    def revise_chapter(
        self,
        chapter_num: int,
        feedback_text: str,
        pipeline_state_path: str | None = None,
    ) -> BaseCrewOutput:
        """请求修改章节（带自然语言反馈）

        Args:
            chapter_num: 章节号
            feedback_text: 自然语言修改意见
            pipeline_state_path: 可选，流水线状态路径

        Returns:
            BaseCrewOutput: 继续执行的结果
        """
        feedback = HumanFeedback(
            stage=f"chapter_{chapter_num}",
            decision=ApprovalDecision.REVISE,
            natural_language=feedback_text,
            chapter_num=chapter_num,
        )
        return self.submit_feedback(feedback, pipeline_state_path)

    def _write_all_chapters(
        self,
        world_data: dict,
        plot_data: dict,
    ) -> list[ChapterOutput]:
        """撰写所有章节

        Args:
            world_data: 世界观数据
            plot_data: 情节规划数据

        Returns:
            List[ChapterOutput]: 章节输出列表
        """
        num_chapters = self.config.get("num_chapters", 10)
        target_words_per_chapter = self.config.get("target_words", 10000) // num_chapters

        chapters = []
        previous_summary = ""

        # Build BibleSection per volume for bible-constrained writing (P1-4)
        bible_section_builder = None
        bible_volume_map: dict[int, Any] = {}  # volume_num -> BibleSection cache
        if self._production_bible is not None:
            try:
                from crewai.content.novel.production_bible.section_builder import (
                    BibleSectionBuilder,
                )
                bible_section_builder = BibleSectionBuilder()
                # For sequential writing, we use volume 1 as default since there's no volume structure
                bible_volume_map[1] = bible_section_builder.build_section(self._production_bible, 1)
                logger.info("BibleSection pre-built for sequential writing (volume 1)")
            except Exception as e:
                logger.warning(f"Failed to build BibleSections for writing: {e}")
                bible_section_builder = None

        # 获取主线信息
        main_strand = plot_data.get("main_strand", {})
        high_points = plot_data.get("high_points", [])

        for i in range(num_chapters):
            chapter_num = i + 1

            # 构建章节大纲（使用PlotAgent进行智能规划）
            chapter_outline = self._build_chapter_outline(
                chapter_num=chapter_num,
                total_chapters=num_chapters,
                world_data=world_data,
                plot_data=plot_data,
                previous_summary=previous_summary,
                target_words=target_words_per_chapter,
            )

            # Save outline artifact
            self.save_artifact(chapter_num, 'outline', chapter_outline)

            # 构建写作上下文
            context = self._build_writing_context(
                chapter_num,
                world_data,
                previous_summary,
                chapter_outline,
                target_words_per_chapter,
            )

            # 根据配置选择写作引擎
            use_orchestrator = self.config.get("use_orchestrator", True)

            # 获取本章对应的 BibleSection（P1-4: bible 约束写作）
            bible_section = bible_volume_map.get(1) if bible_section_builder else None

            # 用于存储 orchestrator 返回的记忆（用于跨章节连续性）
            chapter_memory = None

            if use_orchestrator:
                try:
                    # 使用知识库的 NovelOrchestrator 进行多智能体写作
                    draft, chapter_memory = self.orchestrator_crew.write_chapter(context, chapter_outline, bible_section)
                except TimeoutError as e:
                    # LLM 超时，重试3次
                    for attempt in range(3):
                        try:
                            draft, chapter_memory = self.orchestrator_crew.write_chapter(context, chapter_outline, bible_section)
                            break
                        except TimeoutError:
                            if attempt == 2:
                                logger.error(f"LLM timeout after 3 retries: {e}, falling back to WritingCrew")
                                draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                                chapter_memory = None
                except ValidationError as e:
                    # 格式/验证错误，阻止并报告
                    logger.error(f"Orchestrator validation error (not falling back): {e}")
                    raise
                except Exception as e:
                    # 其他异常，fallback
                    logger.warning(f"Orchestrator failed: {e}, falling back to WritingCrew")
                    draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                    chapter_memory = None
            else:
                # 使用标准的单 Agent 写作
                draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)

            # 如果从 orchestrator 获取了记忆，更新 context 的 previous_chapters_summary
            # 这样下一章就能利用本章的角色状态和关键事件
            if chapter_memory:
                context.previous_chapters_summary = self._update_context_from_memory(
                    context.previous_chapters_summary, chapter_memory
                )

            # Save draft artifact
            self.save_artifact(chapter_num, 'draft', draft)

            # 审查和修改
            review_context = self._build_review_context(context, chapter_outline)
            critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
                draft, review_context
            )

            # Save review artifacts
            self.save_artifact(chapter_num, 'critique', critique_result)
            self.save_artifact(chapter_num, 'revised', revised_draft)
            self.save_artifact(chapter_num, 'polished', polished_draft)

            # 计算字数（使用润色后的草稿）
            word_count = len(polished_draft) // 2  # 粗略估计中文字数

            # 如果字数低于目标的50%，尝试扩展章节
            min_word_count = target_words_per_chapter * 0.5
            expansion_attempts = 0
            max_expansion_attempts = 2
            while word_count < min_word_count and expansion_attempts < max_expansion_attempts:
                expansion_attempts += 1
                logger.info(f"Chapter {chapter_num} word count ({word_count}) below target ({min_word_count:.0f}), expanding (attempt {expansion_attempts})...")

                # 请求LLM扩展章节
                expansion_prompt = f"""请扩展以下章节，增加细节描写和情节发展，使字数达到约{target_words_per_chapter}字。

现有章节:
{polished_draft[:500]}...

请续写并扩展这个章节，增加:
1. 更详细的环境/场景描写
2. 更多的对话和互动
3. 更深入的内心描写
4. 更多的情节细节

直接输出扩展后的完整章节内容。"""

                try:
                    from crewai.agent import Agent
                    expand_agent = Agent(
                        role="小说写作专家",
                        goal="扩展章节内容",
                        backstory="你是一个擅长扩展情节的小说作家",
                        verbose=False,
                    )
                    expanded = expand_agent.kickoff(messages=expansion_prompt)
                    if hasattr(expanded, 'raw'):
                        expanded = expanded.raw
                    expanded = str(expanded).strip()

                    # 用扩展内容替换原内容（取较长的）
                    if len(expanded) > len(polished_draft):
                        polished_draft = expanded
                        word_count = len(polished_draft) // 2
                except Exception as e:
                    logger.warning(f"Expansion attempt {expansion_attempts} failed: {e}")
                    break

            # 创建章节输出
            chapter_output = ChapterOutput(
                chapter_num=chapter_num,
                title=chapter_outline.get("title", f"第{chapter_num}章"),
                content=polished_draft,
                word_count=word_count,
                key_events=chapter_outline.get("main_events", []),
                character_appearances=self._extract_character_names(polished_draft, world_data),
                setting=world_data.get("name", ""),
            )

            chapters.append(chapter_output)

            # Save checkpoint immediately to disk (enables recovery on crash)
            self._save_chapter_checkpoint(chapter_output)

            # Update entity memory with characters from this chapter
            character_names = chapter_output.character_appearances or []
            for char_name in character_names:
                entity = self.entity_memory.get_entity(char_name)
                if entity is None:
                    entity = Entity(
                        id=char_name,
                        name=char_name,
                        type="character",
                        description=f"角色{char_name}",
                    )
                    self.entity_memory.add_entity(entity)
                # Update location property if we can infer it from the content
                self.entity_memory.update_entity_property(char_name, "last_appearance_chapter", str(chapter_num))

            # Record chapter in continuity tracker
            event = Event(
                id=f"chapter_{chapter_num}",
                timestamp=f"第{chapter_num}章",
                description=chapter_output.content[:200] if chapter_output.content else "",
                involved_entities=character_names,
                chapter=chapter_num,
            )
            self.continuity_tracker.add_event(event)

            # Check continuity before next chapter
            continuity_issues = self.continuity_tracker.check_continuity(event)
            if continuity_issues:
                logger.warning(f"Chapter {chapter_num} continuity issues: {continuity_issues}")

            # Store actual content for better context
            previous_summary = f"第{chapter_num}章《{chapter_output.title}》: {chapter_output.content[:500] if chapter_output.content else ''}..."

        return chapters

    def _write_all_chapters_from_summaries(
        self,
        world_data: dict,
        chapter_summaries: list[dict],
        review_each_chapter: bool = False,
    ) -> list[ChapterOutput]:
        """撰写所有章节（使用预先生成的章节概要）

        Args:
            world_data: 世界观数据
            chapter_summaries: 章节概要列表（来自 ChapterSummaryAgent）
            review_each_chapter: 是否在每章写完后暂停等待确认（用于交互审核模式）

        Returns:
            List[ChapterOutput]: 章节输出列表
        """
        chapters = []
        previous_summary = ""

        # 计算每章目标字数
        num_chapters = len(chapter_summaries) if chapter_summaries else self.config.get("num_chapters", 10)
        target_words_per_chapter = self.config.get("target_words", 10000) // num_chapters

        # Build BibleSection per volume for bible-constrained writing (P1-4)
        bible_section_builder = None
        bible_volume_map: dict[int, Any] = {}  # volume_num -> BibleSection cache
        if self._production_bible is not None:
            try:
                from crewai.content.novel.production_bible.section_builder import (
                    BibleSectionBuilder,
                )
                bible_section_builder = BibleSectionBuilder()
                # Pre-build BibleSection for each volume that appears in chapter_summaries
                # Build a chapter_num -> volume_num lookup from pipeline_state.volume_outlines
                volume_outlines = getattr(self.pipeline_state, 'volume_outlines', []) or []
                chapter_to_volume: dict[int, int] = {}
                for vol in volume_outlines:
                    vol_num = vol.get("volume_num", 1)
                    for ch in vol.get("chapters_summary", []) or vol.get("chapters", []):
                        ch_num = ch.get("chapter_num", 0)
                        if ch_num > 0:
                            chapter_to_volume[ch_num] = vol_num
                # Pre-build BibleSections for each unique volume
                used_volumes = set()
                for cs in chapter_summaries:
                    vol_num = cs.get("volume_num") or chapter_to_volume.get(cs.get("chapter_num", 0), 1)
                    used_volumes.add(vol_num)
                for vol_num in used_volumes:
                    bible_volume_map[vol_num] = bible_section_builder.build_section(self._production_bible, vol_num)
                logger.info(f"BibleSections pre-built for {len(bible_volume_map)} volumes")
            except Exception as e:
                logger.warning(f"Failed to build BibleSections for writing: {e}")
                bible_section_builder = None

        for i, chapter_summary in enumerate(chapter_summaries):
            chapter_num = chapter_summary.get("chapter_num", i + 1)

            # 从概要构建章节大纲
            chapter_outline = self._build_outline_from_summary(chapter_summary)

            # 构建写作上下文
            context = self._build_writing_context(
                chapter_num,
                world_data,
                previous_summary,
                chapter_outline,
                chapter_summary.get("word_target", target_words_per_chapter),
            )

            # 获取本章对应的 BibleSection（P1-4: bible 约束写作）
            bible_section = None
            if bible_section_builder is not None:
                vol_num = chapter_summary.get("volume_num") or chapter_to_volume.get(chapter_num, 1)
                bible_section = bible_volume_map.get(vol_num)

            # 根据配置选择写作引擎
            # 混合模式(hybrid): orchestrator 支持 bible 约束，通过 bible_constraint 参数传递
            use_orchestrator = self.config.get("use_orchestrator", True)

            # 用于存储 orchestrator 返回的记忆（用于跨章节连续性）
            chapter_memory = None

            if use_orchestrator:
                try:
                    # Hybrid mode: pass bible_section to orchestrator for FILM_DRAMA + Bible constraints
                    draft, chapter_memory = self.orchestrator_crew.write_chapter(context, chapter_outline, bible_section)
                except Exception as e:
                    logger.warning(f"Orchestrator failed: {e}, falling back to WritingCrew")
                    draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
            else:
                draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)

            # 如果从 orchestrator 获取了记忆，更新 context 的 previous_chapters_summary
            # 这样下一章就能利用本章的角色状态和关键事件
            if chapter_memory:
                context.previous_chapters_summary = self._update_context_from_memory(
                    context.previous_chapters_summary, chapter_memory
                )

            # Save draft artifact
            self.save_artifact(chapter_num, 'draft', draft)

            # 审查和修改
            review_context = self._build_review_context(context, chapter_outline)
            critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
                draft, review_context
            )

            # Save review artifacts
            self.save_artifact(chapter_num, 'critique', critique_result)
            self.save_artifact(chapter_num, 'revised', revised_draft)
            self.save_artifact(chapter_num, 'polished', polished_draft)

            # 计算字数
            word_count = len(polished_draft) // 2

            # 如果字数低于目标的50%，尝试扩展章节
            min_word_count = target_words_per_chapter * 0.5
            expansion_attempts = 0
            max_expansion_attempts = 2
            while word_count < min_word_count and expansion_attempts < max_expansion_attempts:
                expansion_attempts += 1
                logger.info(f"Chapter {chapter_num} word count ({word_count}) below target ({min_word_count:.0f}), expanding (attempt {expansion_attempts})...")

                # 请求LLM扩展章节
                expansion_prompt = f"""请扩展以下章节，增加细节描写和情节发展，使字数达到约{target_words_per_chapter}字。

现有章节:
{polished_draft[:500]}...

请续写并扩展这个章节，增加:
1. 更详细的环境/场景描写
2. 更多的对话和互动
3. 更深入的内心描写
4. 更多的情节细节

直接输出扩展后的完整章节内容。"""

                try:
                    from crewai.agent import Agent
                    expand_agent = Agent(
                        role="小说写作专家",
                        goal="扩展章节内容",
                        backstory="你是一个擅长扩展情节的小说作家",
                        verbose=False,
                    )
                    expanded = expand_agent.kickoff(messages=expansion_prompt)
                    if hasattr(expanded, 'raw'):
                        expanded = expanded.raw
                    expanded = str(expanded).strip()

                    # 用扩展内容替换原内容（取较长的）
                    if len(expanded) > len(polished_draft):
                        polished_draft = expanded
                        word_count = len(polished_draft) // 2
                except Exception as e:
                    logger.warning(f"Expansion attempt {expansion_attempts} failed: {e}")
                    break

            # Per-Chapter PostPass
            postpass_result = self.per_chapter_postpass.process(
                chapter_num=chapter_num,
                chapter_content=polished_draft,
                chapter_outline=chapter_outline,
            )

            if postpass_result.has_high_severity_issues:
                logger.warning(f"Chapter {chapter_num} has high severity consistency issues:")
                for issue in postpass_result.issues:
                    if issue.severity == "high":
                        logger.warning(f"  [{issue.issue_type}] {issue.description}")

            # 保存 PostPass 结果
            if postpass_result.snapshot:
                self.save_artifact(chapter_num, 'postpass_snapshot', postpass_result.snapshot.to_dict())

            # 创建章节输出
            chapter_output = ChapterOutput(
                chapter_num=chapter_num,
                title=chapter_outline.get("title", f"第{chapter_num}章"),
                content=polished_draft,
                word_count=word_count,
                key_events=chapter_summary.get("key_events", []),
                character_appearances=self._extract_character_names(polished_draft, world_data),
                setting=world_data.get("name", ""),
            )

            chapters.append(chapter_output)

            # Save checkpoint immediately to disk (enables recovery on crash)
            self._save_chapter_checkpoint(chapter_output)

            # Update entity memory
            character_names = chapter_output.character_appearances or []
            for char_name in character_names:
                entity = self.entity_memory.get_entity(char_name)
                if entity is None:
                    entity = Entity(
                        id=char_name,
                        name=char_name,
                        type="character",
                        description=f"角色{char_name}",
                    )
                    self.entity_memory.add_entity(entity)
                self.entity_memory.update_entity_property(char_name, "last_appearance_chapter", str(chapter_num))

            # Record chapter in continuity tracker
            event = Event(
                id=f"chapter_{chapter_num}",
                timestamp=f"第{chapter_num}章",
                description=chapter_output.content[:200] if chapter_output.content else "",
                involved_entities=character_names,
                chapter=chapter_num,
            )
            self.continuity_tracker.add_event(event)

            # Store content for context
            previous_summary = f"第{chapter_num}章《{chapter_output.title}》: {chapter_output.content[:500] if chapter_output.content else ''}..."

            # Per-chapter review pause point
            if review_each_chapter:
                logger.info(f"[REVIEW-GATE] Chapter {chapter_num} completed — awaiting confirmation before proceeding")
                logger.info(f"  Title: {chapter_output.title}")
                logger.info(f"  Words: {chapter_output.word_count}")
                logger.info(f"  Key events: {', '.join(str(e) for e in chapter_output.key_events[:3]) if chapter_output.key_events else 'none'}")

                # 检查是否有针对本章的待处理反馈
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("chapter_num") == chapter_num:
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.REVISE:
                        logger.info(f"Chapter {chapter_num}: user requested revision")
                        # 基于反馈修改章节内容
                        feedback_applier = FeedbackApplier(llm=self.config.get("llm"))
                        revised_content = feedback_applier.revise_chapter_content(
                            original_content=polished_draft,
                            chapter_outline=chapter_outline,
                            feedback=feedback.structured or {"summary": feedback.natural_language},
                            world_data=world_data,
                        )
                        # 重新审查修改后的内容
                        critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
                            revised_content, review_context
                        )
                        chapter_output.content = polished_draft
                        chapter_output.word_count = len(polished_draft) // 2
                        self.pipeline_state.clear_pending_feedback()
                    elif feedback.decision == ApprovalDecision.REJECT:
                        logger.info(f"Chapter {chapter_num}: user rejected, regenerating...")
                        # 重新生成本章
                        draft = self._regenerate_chapter(context, chapter_outline, bible_section)
                        polished_draft = draft
                        # 重新审查
                        critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
                            draft, review_context
                        )
                        chapter_output.content = polished_draft
                        chapter_output.word_count = len(polished_draft) // 2
                        self.pipeline_state.clear_pending_feedback()
                    elif feedback.decision == ApprovalDecision.APPROVE:
                        logger.info(f"Chapter {chapter_num}: approved")
                        self.pipeline_state.clear_pending_feedback()
                else:
                    # 没有反馈，保存状态并暂停
                    self.pipeline_state.set_stage_status(f"chapter_{chapter_num}", "pending")
                    # 保存当前章节状态供恢复
                    self._save_chapter_checkpoint(chapter_output)
                    raise PendingChapterApproval(
                        f"Chapter {chapter_num} pending approval",
                        chapter_num=chapter_num,
                        chapter_output=chapter_output,
                        pipeline_state_path=self.pipeline_state.save(".pending_chapter.json"),
                    )

        return chapters

    def _regenerate_chapter(
        self,
        context: WritingContext,
        chapter_outline: dict,
        bible_section: Any = None,
    ) -> str:
        """重新生成单个章节

        Args:
            context: 写作上下文
            chapter_outline: 章节大纲
            bible_section: BibleSection

        Returns:
            重新生成的章节内容
        """
        use_orchestrator = self.config.get("use_orchestrator", True)

        if use_orchestrator:
            try:
                draft, _ = self.orchestrator_crew.write_chapter(context, chapter_outline, bible_section)
                return draft
            except Exception as e:
                logger.warning(f"Orchestrator failed: {e}, falling back to WritingCrew")
                return self.writing_crew.write_chapter(context, chapter_outline, bible_section)
        else:
            return self.writing_crew.write_chapter(context, chapter_outline, bible_section)

    def _build_outline_from_summary(self, chapter_summary: dict) -> dict:
        """从章节概要构建章节大纲

        Args:
            chapter_summary: 章节概要

        Returns:
            dict: 标准化的章节大纲格式
        """
        # 从概要提取关键信息构建章节大纲
        key_events = chapter_summary.get("key_events", [])
        character_arcs = chapter_summary.get("character_arcs", {})

        # 构建 main_events 列表
        main_events = key_events if key_events else [chapter_summary.get("summary_paragraph", "")[:100]]

        return {
            "chapter_num": chapter_summary.get("chapter_num", 0),
            "title": chapter_summary.get("title", f"第{chapter_summary.get('chapter_num', '?')}章"),
            "hook": chapter_summary.get("summary_paragraph", "")[:200] if chapter_summary.get("summary_paragraph") else "",
            "main_events": main_events,
            "climax": "",
            "ending_hook": chapter_summary.get("foreshadowing", [{}])[0].get("payoff_chapter", "") if chapter_summary.get("foreshadowing") else "",
            "tension_level": chapter_summary.get("tension_arc", {}).get("climax", 5),
            "character_developments": [f"{char}: {arc}" for char, arc in character_arcs.items()] if character_arcs else [],
            "weave_connections": [],
            "_from_summary": True,
        }

    def _build_chapter_outline(
        self,
        chapter_num: int,
        total_chapters: int,
        world_data: dict,
        plot_data: dict,
        previous_summary: str,
        target_words: int,
    ) -> dict:
        """构建章节大纲 - 使用PlotAgent进行智能规划

        该方法考虑了：
        - 事件之间的逻辑依赖关系
        - "起承转合"的张力曲线分布
        - 高潮点在章节中后部的合理安排
        - 多线索叙事（Strand Weave）的事件交织

        Args:
            chapter_num: 章节编号
            total_chapters: 总章节数
            world_data: 世界观数据
            plot_data: 完整情节规划数据（包含多线索）
            previous_summary: 前章概要
            target_words: 目标字数

        Returns:
            dict: 章节大纲
        """
        # 优先使用PlotAgent进行智能章节规划
        try:
            chapter_plan = self.plot_agent.plan_chapter(
                chapter_num=chapter_num,
                world_data=world_data,
                plot_data=plot_data,
                previous_summary=previous_summary,
                target_words=target_words,
            )
            return self._convert_chapter_plan(chapter_plan, chapter_num, total_chapters)
        except Exception as e:
            # Fallback: 使用增强的启发式方法
            return self._build_chapter_outline_fallback(
                chapter_num, total_chapters, plot_data, target_words, str(e)
            )

    def _convert_chapter_plan(self, chapter_plan: dict, chapter_num: int, total_chapters: int) -> dict:
        """将PlotAgent返回的章节规划转换为标准格式

        Args:
            chapter_plan: PlotAgent返回的章节规划
            chapter_num: 章节编号
            total_chapters: 总章节数

        Returns:
            dict: 标准化的章节大纲
        """
        return {
            "chapter_num": chapter_num,
            "title": chapter_plan.get("title", f"第{chapter_num}章"),
            "hook": chapter_plan.get("hook", ""),
            "main_events": chapter_plan.get("main_events", []),
            "climax": chapter_plan.get("climax", ""),
            "ending_hook": chapter_plan.get("ending_hook", ""),
            "character_developments": chapter_plan.get("character_developments", []),
            "weave_connections": chapter_plan.get("weave_connections", []),
        }

    def _build_chapter_outline_fallback(
        self,
        chapter_num: int,
        total_chapters: int,
        plot_data: dict,
        target_words: int,
        error_msg: str,
    ) -> dict:
        """Fallback方法：当PlotAgent不可用时使用增强的启发式逻辑

        该方法改进了原有的简单平均分配：
        1. 分析主线事件的逻辑顺序和依赖关系
        2. 根据章节位置分配不同的张力级别（起承转合）
        3. 高潮点优先安排在中后部（60%-85%位置）
        4. 考虑多线索叙事的事件交织
        """
        main_strand = plot_data.get("main_strand", {})
        sub_strands = plot_data.get("sub_strands", [])
        high_points = plot_data.get("high_points", [])
        weave_points = plot_data.get("weave_points", [])

        main_events = main_strand.get("main_events", [])

        # 计算章节位置特征
        chapter_position = chapter_num / total_chapters  # 0.0 - 1.0

        # 1. 张力曲线分配（起承转合）
        # 前期(0-30%): 铺垫建立
        # 中前期(30-50%): 发展升温
        # 中后期(50-70%): 转折深化
        # 后期(70-90%): 高潮爆发
        # 收尾(90-100%): 收束余韵
        if chapter_position < 0.3:
            tension_level = "establishing"  # 铺垫
            event_count = max(2, len(main_events) // total_chapters)
        elif chapter_position < 0.5:
            tension_level = "developing"  # 发展
            event_count = max(3, len(main_events) // total_chapters + 1)
        elif chapter_position < 0.7:
            tension_level = "turning"  # 转折
            event_count = max(3, len(main_events) // total_chapters + 1)
        elif chapter_position < 0.9:
            tension_level = "climax"  # 高潮
            event_count = max(4, len(main_events) // total_chapters + 2)
        else:
            tension_level = "resolution"  # 收束
            event_count = max(2, len(main_events) // total_chapters)

        # 2. 高潮点分布：将high_points合理分布到章节
        # 优先在中后部安排高潮
        climax_chapters = self._distribute_climax_points(high_points, total_chapters)
        is_high_point = chapter_num in climax_chapters

        # 3. 事件分配：考虑逻辑依赖和交织点
        chapter_events = self._allocate_events_for_chapter(
            chapter_num, total_chapters, main_events, sub_strands, weave_points, event_count
        )

        # 4. 生成开篇钩子
        hook = self._generate_chapter_hook(chapter_num, tension_level, chapter_events, is_high_point)

        # 5. 生成结尾悬念
        ending_hook = self._generate_ending_hook(chapter_num, total_chapters, plot_data)

        return {
            "chapter_num": chapter_num,
            "title": f"第{chapter_num}章",
            "hook": hook,
            "main_events": chapter_events,
            "climax": "高潮点" if is_high_point else tension_level,
            "ending_hook": ending_hook,
            "tension_level": tension_level,
            "weave_point": self._is_weave_point(chapter_num, weave_points),
            "_fallback": True,
            "_error": error_msg,
        }

    def _distribute_climax_points(self, high_points: list, total_chapters: int) -> list:
        """将高潮点合理分布到章节中

        高潮点应该集中安排在故事的40%-85%位置，避免过早或过晚
        """
        climax_chapters = []

        # 提取已有的高潮章节
        for hp in high_points:
            if isinstance(hp, dict) and hp.get("chapter"):
                climax_chapters.append(hp["chapter"])

        # 如果高潮点数量不足，补充分配
        if len(climax_chapters) < max(1, total_chapters // 10):
            # 需要补充高潮点：优先安排在中后部
            climax_positions = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85]
            needed = max(1, total_chapters // 10) - len(climax_chapters)

            for i, pos in enumerate(climax_positions[:needed]):
                chapter = int(total_chapters * pos)
                if chapter not in climax_chapters and 1 <= chapter <= total_chapters:
                    climax_chapters.append(chapter)

        return sorted(set(climax_chapters))

    def _allocate_events_for_chapter(
        self,
        chapter_num: int,
        total_chapters: int,
        main_events: list,
        sub_strands: list,
        weave_points: list,
        event_count: int,
    ) -> list:
        """为章节分配事件，考虑逻辑依赖和交织点

        Args:
            chapter_num: 章节编号
            total_chapters: 总章节数
            main_events: 主线事件列表
            sub_strands: 副线列表
            weave_points: 交织点列表
            event_count: 需要的事件数量

        Returns:
            list: 分配给该章节的事件
        """
        if not main_events:
            return [f"第{chapter_num}章主要事件"]

        total_events = len(main_events)
        events_per_chapter = max(1, total_events // total_chapters)

        # 计算基础分配范围
        start_idx = (chapter_num - 1) * events_per_chapter
        end_idx = start_idx + events_per_chapter

        chapter_events = []

        # 添加主线事件
        if start_idx < total_events:
            chapter_events.extend(main_events[start_idx:min(end_idx, total_events)])

        # 检查是否是交织点，如果是则添加副线事件
        if self._is_weave_point(chapter_num, weave_points) and sub_strands:
            # 在交织点添加副线相关事件
            for strand in sub_strands[:2]:  # 最多添加2条副线
                strand_events = strand.get("main_events", [])
                if strand_events:
                    # 从副线事件中选取与本章相关的内容
                    strand_idx = (chapter_num - 1) % max(1, len(strand_events))
                    if strand_idx < len(strand_events):
                        chapter_events.append(f"[副线] {strand_events[strand_idx]}")

        # 确保事件数量适中
        if len(chapter_events) < event_count and end_idx < total_events:
            # 补充下一个事件作为悬念铺垫
            chapter_events.append(main_events[min(end_idx, total_events - 1)])

        return chapter_events[:event_count + 1] if chapter_events else [f"第{chapter_num}章主要事件"]

    def _is_weave_point(self, chapter_num: int, weave_points: list) -> bool:
        """检查章节是否是交织点"""
        for wp in weave_points:
            if isinstance(wp, dict) and wp.get("chapter") == chapter_num:
                return True
            if isinstance(wp, int) and wp == chapter_num:
                return True
        return False

    def _generate_chapter_hook(
        self,
        chapter_num: int,
        tension_level: str,
        events: list,
        is_high_point: bool,
    ) -> str:
        """生成章节开篇钩子"""
        if is_high_point:
            return f"第{chapter_num}章迎来全书重大转折，所有线索在此交汇"
        if tension_level == "establishing":
            return f"第{chapter_num}章继续展开故事，世界观和人物关系逐步清晰"
        if tension_level == "developing":
            return f"第{chapter_num}章冲突升级，主角面临新的挑战"
        if tension_level == "turning":
            return f"第{chapter_num}章局势突变，故事迎来重大转折"
        if tension_level == "climax":
            return f"第{chapter_num}章高潮来临，所有矛盾即将爆发"
        return f"第{chapter_num}章收束前情，为后续故事埋下伏笔"

    def _generate_ending_hook(self, chapter_num: int, total_chapters: int, plot_data: dict) -> str:
        """生成章节结尾悬念"""
        if chapter_num >= total_chapters:
            return "全书完"

        chapter_position = chapter_num / total_chapters

        # 检查下一章是否是交织点
        weave_points = plot_data.get("weave_points", [])
        next_is_weave = self._is_weave_point(chapter_num + 1, weave_points)

        # 检查是否有伏笔
        foreshadowing = plot_data.get("foreshadowing_strands", [])

        if next_is_weave:
            return "下一章多条线索将交汇，故事即将进入关键阶段"
        if chapter_position > 0.7:
            return "高潮过后，更大的危机正在酝酿"
        if chapter_position > 0.5:
            return "冲突升级，下一章将迎来更大的挑战"
        return f"第{chapter_num + 1}章将继续展开故事"

    def _extract_character_profiles(self, world_data: dict) -> dict:
        """从世界数据中提取角色信息

        从world_data的factions中提取领袖信息，构建角色简介字典。

        Args:
            world_data: 世界观数据字典

        Returns:
            dict: 角色名到角色简介的映射字典
        """
        character_profiles = {}

        # 从势力(Factions)中提取领袖信息
        factions = world_data.get("factions", [])
        for faction in factions:
            if not isinstance(faction, dict):
                continue

            leader_name = faction.get("leader", "").strip()
            if not leader_name:
                continue

            # 构建角色简介
            faction_name = faction.get("name", "")
            faction_desc = faction.get("description", "")
            goals = faction.get("goals", [])
            allies = faction.get("allies", [])
            enemies = faction.get("enemies", [])

            # 构建角色描述
            profile_parts = []
            if faction_name:
                profile_parts.append(f"所属势力: {faction_name}")
            if faction_desc:
                profile_parts.append(f"背景: {faction_desc}")
            if goals and isinstance(goals, list):
                goals_str = ", ".join(g for g in goals if g)
                if goals_str:
                    profile_parts.append(f"目标: {goals_str}")
            if allies and isinstance(allies, list) and any(a for a in allies if a):
                allies_str = ", ".join(a for a in allies if a)
                profile_parts.append(f"盟友: {allies_str}")
            if enemies and isinstance(enemies, list) and any(e for e in enemies if e):
                enemies_str = ", ".join(e for e in enemies if e)
                profile_parts.append(f"敌对: {enemies_str}")

            profile_str = "; ".join(profile_parts) if profile_parts else f"来自{faction_name}的成员"

            character_profiles[leader_name] = profile_str

        # 从key_locations中提取关键人物（如果地点有重要人物）
        key_locations = world_data.get("key_locations", [])
        for location in key_locations:
            if not isinstance(location, dict):
                continue

            # 某些地点可能记录了重要人物
            significant_chars = location.get("significant_characters", [])
            if isinstance(significant_chars, list):
                for char_name in significant_chars:
                    if char_name and char_name not in character_profiles:
                        location_name = location.get("name", "")
                        character_profiles[char_name] = f"重要人物，出现在{location_name}"

        return character_profiles

    def _build_writing_context(
        self,
        chapter_num: int,
        world_data: dict,
        previous_summary: str,
        chapter_outline: dict,
        target_words: int,
    ) -> WritingContext:
        """构建写作上下文"""
        # 从世界数据中提取角色信息
        character_profiles = self._extract_character_profiles(world_data)

        return WritingContext(
            title=self.config.get("topic", "未命名小说"),
            genre=self.config.get("genre", ""),
            style=self.config.get("style", ""),
            world_description=world_data.get("description", ""),
            character_profiles=character_profiles,
            previous_chapters_summary=previous_summary,
            chapter_outline=str(chapter_outline),
            target_word_count=target_words,
            current_chapter_num=chapter_num,
            tension_arc="",  # 后续可以从情节数据中提取
        )

    def _build_review_context(
        self,
        writing_context: WritingContext,
        chapter_outline: dict,
    ) -> ReviewContext:
        """构建审查上下文

        Args:
            writing_context: 写作上下文
            chapter_outline: 章节大纲，包含本章的标题、主要事件、张力级别等信息

        Returns:
            ReviewContext: 审查上下文
        """
        # 从 chapter_outline 提取关键信息
        chapter_title = chapter_outline.get("title", f"第{writing_context.current_chapter_num}章")
        main_events = chapter_outline.get("main_events", [])
        tension_level = chapter_outline.get("tension_level", "")
        climax = chapter_outline.get("climax", "")
        weave_connections = chapter_outline.get("weave_connections", [])

        # 构建写作目标（本章主要事件）
        writing_goals = f"本章标题：{chapter_title}"
        if main_events:
            writing_goals += "\n本章主要事件：\n" + "\n".join(f"- {event}" for event in main_events)
        if climax and climax != tension_level:
            writing_goals += f"\n高潮点：{climax}"

        # 构建节奏笔记
        pacing_notes = f"张力级别：{tension_level}" if tension_level else ""
        if weave_connections:
            pacing_notes += "\n交织点连接：" + ", ".join(str(w) for w in weave_connections)

        return ReviewContext(
            title=writing_context.title,
            genre=writing_context.genre,
            style_guide=writing_context.style,
            previous_chapters_summary=writing_context.previous_chapters_summary,
            chapter_number=writing_context.current_chapter_num,
            word_count_target=writing_context.target_word_count,
            writing_goals=writing_goals,
            pacing_notes=pacing_notes,
        )

    def _extract_character_names(self, content: str, world_data: dict) -> list[str]:
        """提取内容中出现的主要角色名

        从 world_data 获取已知角色列表，然后在正文中检测这些名字是否出现。

        Args:
            content: 正文内容
            world_data: 世界观数据，包含 factions 等

        Returns:
            List[str]: 在正文中出现的角色名列表
        """
        import re

        found_names = set()

        # 1. 从 world_data 的 factions 中提取已知角色名
        known_names = []
        factions = world_data.get("factions", [])
        for faction in factions:
            if not isinstance(faction, dict):
                continue
            # 从 leader 字段提取
            leader = faction.get("leader", "").strip()
            if leader:
                known_names.append(leader)
            # 从 members 或 characters 中提取
            members = faction.get("members", [])
            if isinstance(members, list):
                for m in members:
                    if isinstance(m, str) and m.strip():
                        known_names.append(m.strip())
                    elif isinstance(m, dict) and m.get("name"):
                        known_names.append(m["name"])

        # 2. 从 world_data 的 characters 中提取（如果存在）
        characters = world_data.get("characters", [])
        if isinstance(characters, list):
            for char in characters:
                if isinstance(char, str) and char.strip():
                    known_names.append(char.strip())
                elif isinstance(char, dict) and char.get("name"):
                    known_names.append(char["name"])

        # 3. 在正文中检测已知角色名
        for name in known_names:
            if name and len(name) >= 2:
                # 使用单词边界检测，确保是完整名字
                pattern = re.compile(re.escape(name))
                if pattern.search(content):
                    found_names.add(name)

        # 4. 补充：使用正则匹配中文名字（2-4个汉字）作为兜底
        # 避免匹配到已发现的名字
        chinese_name_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}')
        for match in chinese_name_pattern.finditer(content):
            name = match.group()
            # 排除常见的非人名组合
            if name not in found_names and not self._is_likely_place_or_common_word(name):
                found_names.add(name)

        return list(found_names)

    def _is_likely_place_or_common_word(self, name: str) -> bool:
        """判断是否是可能的地点或常用词（非人名）"""
        # 常见非人名组合
        common_non_names = {
            "时候", "地方", "这里", "那里", "什么", "怎么",
            "为何", "如何", "因为", "所以", "但是", "然而",
            "于是", "之后", "之前", "左右", "上下", "高低",
            "大小", "长短", "好坏", "多少", "远近", "快慢",
        }
        return name in common_non_names

    def _update_context_from_memory(
        self,
        current_summary: str,
        chapter_memory: Dict[str, Any],
    ) -> str:
        """从章节记忆更新写作上下文的高潮点摘要.

        将 knowledge_base 的 ChapterMemory 转换为 crewai 的 previous_chapters_summary 格式，
        包含角色状态、关系变化和关键事件。

        Args:
            current_summary: 当前的高潮点摘要
            chapter_memory: 来自 KnowledgeBaseAdapter 的章节记忆字典

        Returns:
            更新后的高潮点摘要字符串
        """
        from crewai.content.adapters.data_converters import (
            convert_chapter_memory_to_summary,
        )

        character_states = chapter_memory.get("character_states", {})
        relationship_states = chapter_memory.get("relationship_states", {})
        key_events = chapter_memory.get("key_events", [])

        # 如果没有有效记忆内容，直接返回当前摘要
        if not character_states and not relationship_states and not key_events:
            return current_summary

        # 转换记忆为摘要格式
        memory_summary = convert_chapter_memory_to_summary(
            character_states=character_states,
            relationship_states=relationship_states,
            key_events=key_events,
        )

        # 追加到现有摘要
        if current_summary:
            return f"{current_summary}\n\n{memory_summary}"
        return memory_summary
