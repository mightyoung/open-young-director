"""NovelCrew - 主编排"""

import logging
import signal
from typing import TYPE_CHECKING, Any


logger = logging.getLogger(__name__)

from crewai.content.adapters.knowledge_base_adapter import (
    NovelOrchestratorAdapterConfig,
)
from crewai.content.adapters.novel_orchestrator_crew import NovelOrchestratorCrew
from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.exceptions import ValidationError
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
from crewai.content.novel.feedback_applier import FeedbackApplier
from crewai.content.novel.human_feedback import (
    ApprovalDecision,
    ApprovalWorkflow,
    FeedbackParser,
    HumanFeedback,
    create_approval_feedback,
)
from crewai.content.novel.novel_types import ChapterOutput, NovelOutput, WritingContext
from crewai.content.novel.orchestrator import (
    CheckpointManager,
    OutputPacker,
    StageSequence,
)
from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.novel.seed_mechanism import SeedConfig, set_llm_seed
from crewai.content.review.global_postpass import GlobalPostPass
from crewai.content.review.per_chapter_postpass import (
    PerChapterPostPass,
)
from crewai.content.review.review_context import ReviewContext


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


class NovelCrew(BaseContentCrew[NovelOutput]):
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
        # Chapters marked for regeneration (set during replay)
        self._chapters_to_regenerate: set[int] | None = None
        # Checkpoint manager for atomic file I/O
        self._checkpoint_manager: CheckpointManager | None = None

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents - 委托给子Crews"""
        return {}

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks - 委托给子Crews"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流 - 委托给子Crews"""
        return None

    def _evaluate_output(self, output: "NovelOutput") -> "QualityReport":
        """评估NovelOutput质量

        P2: 统一的 QualityReport 语义。
        - chapters为空 -> is_usable=False
        - total_word_count=0 -> is_usable=False
        - metadata中有warnings -> requires_manual_review=True
        """
        from crewai.content.base import QualityReport

        warnings = []
        errors = []

        # 检查章节数
        if not output.chapters:
            errors.append("no_chapters: 章节列表为空")
            return QualityReport(
                is_usable=False,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )

        # 检查总字数
        if output.total_word_count == 0:
            errors.append("zero_word_count: 总字数为0")
            return QualityReport(
                is_usable=False,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )

        # 检查章节质量问题
        failed_chapters = []
        for chapter in output.chapters:
            if not chapter.content or len(chapter.content.strip()) < 100:
                failed_chapters.append(chapter.chapter_num)

        if failed_chapters:
            warnings.append(f"partial_chapters: 以下章节内容过少或为空: {failed_chapters}")

        # 检查metadata中的warnings
        if output.metadata:
            meta_warnings = output.metadata.get("warnings", [])
            if meta_warnings:
                warnings.extend(meta_warnings)

        return QualityReport(
            is_usable=True,
            requires_manual_review=len(warnings) > 0 or len(errors) > 0,
            warnings=warnings,
            errors=errors,
        )

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

    def _load_writer_commandments(self) -> str:
        """多级加载宪法准则：优先级 输出目录 > 内存访谈 > 根目录默认"""
        from pathlib import Path
        
        # 1. 尝试从输出目录加载 (已存在的持久化宪法)
        output_dir = self.checkpoint_manager.output_dir
        task_md = Path(output_dir) / "WRITER.md"
        if task_md.exists():
            try:
                return f"\n【本案专属宪法 (已锁定)】：\n{task_md.read_text(encoding='utf-8')}\n"
            except: pass

        # 2. 尝试从内存加载 (当前访谈刚生成的指令)
        mem_rules = self.config.get("global_writer_rules")
        if mem_rules:
            return mem_rules

        # 3. 兜底加载根目录默认宪法
        path = Path("WRITER.md")
        if path.exists():
            try:
                return f"\n【项目默认准则 (全局)】：\n{path.read_text(encoding='utf-8')}\n"
            except: pass
            
        return ""

    @property
    def writing_crew(self) -> WritingCrew:
        """获取写作Crew"""
        if self._writing_crew is None:
            # 注入宪法准则
            self.config["global_writer_rules"] = self._load_writer_commandments()
            
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
    def gps_navigator(self) -> Any:
        """获取时空导航员"""
        if self._gps_navigator is None:
            from crewai.content.novel.agents.gps_navigator import GPSNavigator
            self._gps_navigator = GPSNavigator(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._gps_navigator

    @property
    def art_director(self) -> Any:
        """获取艺术总监"""
        if self._art_director is None:
            from crewai.content.novel.agents.art_director import ArtDirector
            self._art_director = ArtDirector(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._art_director

    @property
    def task_registry(self) -> Any:
        """获取任务注册表"""
        if self._task_registry is None:
            from crewai.content.novel.orchestrator.task_registry import TaskRegistry
            self._task_registry = TaskRegistry()
        return self._task_registry

    @property
    def narrative_healer(self) -> Any:
        """获取叙事自愈专家"""
        if self._narrative_healer is None:
            from crewai.content.novel.services.narrative_healer import NarrativeHealer
            self._narrative_healer = NarrativeHealer(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._narrative_healer

    @property
    def reader_swarm(self) -> Any:
        """获取读者陪审团"""
        if self._reader_swarm is None:
            from crewai.content.novel.agents.reader_swarm import ReaderSwarm
            self._reader_swarm = ReaderSwarm(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._reader_swarm

    @property
    def branch_evaluator(self) -> Any:
        """获取剧情分支评估器"""
        if self._branch_evaluator is None:
            from crewai.content.novel.services.branch_evaluator import BranchEvaluator
            self._branch_evaluator = BranchEvaluator(
                config=self.config,
                reader_swarm=self.reader_swarm
            )
        return self._branch_evaluator

    @property
    def destiny_rewriter(self) -> Any:
        """获取宏观命运重构师"""
        if self._destiny_rewriter is None:
            from crewai.content.novel.services.destiny_rewriter import DestinyRewriter
            self._destiny_rewriter = DestinyRewriter(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._destiny_rewriter

    @property
    def volume_auditor(self) -> Any:
        """获取全卷因果律监察长"""
        if self._volume_auditor is None:
            from crewai.content.novel.agents.volume_auditor import VolumeAuditor
            self._volume_auditor = VolumeAuditor(
                # 这里推荐使用支持 1M+ context 的模型
                llm=self.config.get("long_context_llm") or self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._volume_auditor

    @property
    def bible_evolver(self) -> Any:
        """获取Bible演进器"""
        if self._bible_evolver is None:
            from crewai.content.novel.agents.bible_evolver import BibleEvolver
            self._bible_evolver = BibleEvolver(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._bible_evolver

    @property
    def trope_crusher(self) -> Any:
        """获取套路粉碎机"""
        if self._trope_crusher is None:
            from crewai.content.novel.agents.trope_crusher import TropeCrusher
            self._trope_crusher = TropeCrusher(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            )
        return self._trope_crusher

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

    def _save_pipeline_state_snapshot(self) -> str:
        """Persist the current PipelineState using the configured or default path.

        Returns:
            The filesystem path the state was written to.
        """
        from pathlib import Path

        pipeline_state_path = self.config.get("pipeline_state_path")
        if not pipeline_state_path:
            pipeline_state_path = str(Path(self.checkpoint_manager.output_dir) / "pipeline_state.json")
        self.pipeline_state.save(pipeline_state_path)
        return pipeline_state_path

    def _init_pipeline_state(
        self,
        pipeline_state_path: str | None,
        seed: str | None,
        seed_config: "SeedConfig | None",
    ) -> str:
        """初始化流水线状态，支持从断点恢复和确定性重放。

        Args:
            pipeline_state_path: 状态文件路径（用于断点续跑）
            seed: 确定性重放种子
            seed_config: seed 配置对象

        Returns:
            当前阶段名称 (current_stage)
        """
        if pipeline_state_path:
            try:
                loaded_state = PipelineState.load(pipeline_state_path)
                replay_plan = loaded_state.get_replay_plan(seed_config)
                approval_preserve = loaded_state.preserve_approval_history() if not replay_plan.regenerate_all else {}

                if replay_plan.regenerate_all:
                    logger.warning(
                        "Regenerating all: seed_config mismatch or no seed_config found. "
                        "Will regenerate core content (world, outline, etc.)"
                    )
                    self._pipeline_state = PipelineState(config=dict(self.config) if hasattr(self.config, "keys") else {})
                    self._pipeline_state.seed = seed
                    if seed_config:
                        self._pipeline_state.seed_config = seed_config
                elif replay_plan.should_regenerate_world():
                    logger.info(f"Regenerating from world stage, preserving: {replay_plan.preserve}")
                    self._pipeline_state = loaded_state
                    self._pipeline_state.world_data = {}
                    self._pipeline_state.plot_data = {}
                    self._pipeline_state.current_stage = "init"
                elif replay_plan.should_regenerate_outline():
                    logger.info(f"Regenerating from outline stage, preserving: {replay_plan.preserve}")
                    self._pipeline_state = loaded_state
                    self._pipeline_state.plot_data = {}
                    self._pipeline_state.current_stage = "outline"
                elif replay_plan.should_regenerate_chapters() and replay_plan.dirty_chapters:
                    logger.info(f"Regenerating chapters: {replay_plan.dirty_chapters}")
                    self._pipeline_state = loaded_state
                    self._chapters_to_regenerate = set(replay_plan.dirty_chapters)
                    self.pipeline_state.dirty_chapters.update(replay_plan.dirty_chapters)
                else:
                    logger.info("Using cached state (no regeneration needed)")
                    self._pipeline_state = loaded_state

                if approval_preserve:
                    self._pipeline_state.restore_approval_history(approval_preserve)

            except FileNotFoundError:
                logger.info(f"Pipeline state file not found: {pipeline_state_path}, starting fresh")
                self._pipeline_state = PipelineState(config=dict(self.config) if hasattr(self.config, "keys") else {})
                self._pipeline_state.seed = seed
                if seed_config:
                    self._pipeline_state.seed_config = seed_config

        return self.pipeline_state.current_stage

    def _run_outline_stage(
        self,
        current_idx: int,
        target_idx: int,
        approval_mode: bool,
        stop_at: str | None,
        start: float,
    ) -> "BaseCrewOutput | None":
        """执行大纲阶段。

        Returns:
            BaseCrewOutput if should stop/return; None if should continue.
        """

        outline_idx = StageSequence.get_stage_index("outline")
        if current_idx < outline_idx and target_idx >= outline_idx:
            outline_data = self.outline_crew.generate_outline()
            world_data = outline_data.get("world", {})
            plot_data = outline_data.get("plot", {})

            self.pipeline_state.set_outline_data(outline_data)
            self.pipeline_state.set_stage("outline")

            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("outline", "pending")
                return OutputPacker.pack_approval_output(
                    pipeline_state=self.pipeline_state,
                    stage="outline",
                    content={
                        "world_data": world_data,
                        "plot_data": plot_data,
                        "evaluation": None,
                    },
                    execution_time=time.time() - start,
                    output_dir=self._get_novel_output_dir(),
                )
        else:
            outline_data = self.pipeline_state.outline_data or {}
            world_data = outline_data.get("world", {})
            plot_data = outline_data.get("plot", {})

            if approval_mode:
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("stage") == "outline":
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.APPROVE:
                        self.pipeline_state.set_stage_status("outline", "approve")
                        logger.info("Outline approved by user")
                    elif feedback.decision == ApprovalDecision.REVISE:
                        logger.info("User requested outline revision")
                        feedback_applier = FeedbackApplier(llm=self.config.get("llm"))
                        outline_data = self.outline_crew.generate_outline_with_feedback(
                            original_outline=outline_data,
                            feedback=feedback.structured,
                            feedback_applier=feedback_applier,
                        )
                        world_data = outline_data.get("world", {})
                        plot_data = outline_data.get("plot", {})
                        self.pipeline_state.set_outline_data(outline_data)
                        self.pipeline_state.clear_pending_feedback()
                        if stop_at == "outline":
                            return OutputPacker.pack_state_output(
                                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data), "regenerated": True},
                                execution_time=time.time() - start,
                            )
                    elif feedback.decision == ApprovalDecision.REJECT:
                        logger.info("User rejected outline, regenerating from scratch...")
                        outline_data = self.outline_crew.generate_outline()
                        world_data = outline_data.get("world", {})
                        plot_data = outline_data.get("plot", {})
                        self.pipeline_state.set_outline_data(outline_data)
                        self.pipeline_state.clear_pending_feedback()
                        if stop_at == "outline":
                            return OutputPacker.pack_state_output(
                                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data), "regenerated": True},
                                execution_time=time.time() - start,
                            )

        if stop_at == "outline":
            return OutputPacker.pack_state_output(
                pipeline_summary={"stage": "outline", "world_name": world_data.get("name", ""), "plot_ready": bool(plot_data)},
                execution_time=time.time() - start,
            )

        return None

    def _run_evaluation_and_bible_stage(
        self,
        current_idx: int,
        target_idx: int,
        world_data: dict,
        plot_data: dict,
        stop_at: str | None,
        start: float,
    ) -> "BaseCrewOutput | None":
        """执行大纲评估（Evaluator-Optimizer Gate）+ Production Bible构建。

        Returns:
            BaseCrewOutput if should stop/return; None if should continue.
        """
        evaluation_idx = StageSequence.get_stage_index("evaluation")
        eval_result = None
        if current_idx < evaluation_idx and (target_idx > evaluation_idx or stop_at == "evaluation"):
            eval_result, revised_plot = self.outline_evaluator.evaluate_and_revise(
                world_data, plot_data,
                max_retries=2,
            )

            if not eval_result.passed:
                logger.warning(f"Outline evaluation issues: {eval_result.issues}")
                logger.warning(f"Suggestions: {eval_result.suggestions}")

            self.pipeline_state.set_evaluation_result(
                {
                    "score": eval_result.score,
                    "issues": eval_result.issues,
                    "suggestions": eval_result.suggestions,
                },
                passed=eval_result.passed,
            )

            if revised_plot and "error" not in revised_plot:
                plot_data.update(revised_plot)

            self.pipeline_state.set_stage("evaluation")
            self._save_outline_checkpoint(world_data, plot_data, "evaluation")

        # Build ProductionBible after evaluation
        bible = None
        if self._production_bible is None:
            try:
                if self.pipeline_state.bible_serialized or (self.pipeline_state.world_data and self.pipeline_state.plot_data):
                    bible = self.pipeline_state.rebuild_bible()
                    if bible:
                        logger.info("ProductionBible rebuilt from pipeline state")
                if bible is None:
                    from crewai.content.novel.production_bible import (
                        ProductionBibleBuilder,
                    )
                    builder = ProductionBibleBuilder()
                    bible = builder.build(world_data, plot_data)
                self._production_bible = bible
                self.pipeline_state.set_bible(bible)
                self.checkpoint_manager.bind_bible(bible) # Bind for visuals

                # --- ART DIRECTION (Visual Asset Synthesis) ---
                try:
                    from crewai.content.novel.production_bible.bible_types import VisualAsset
                    logger.info("Synthesizing visual assets for the novel characters and covers...")
                    
                    # 为核心角色生成视觉卡
                    for name, char in bible.characters.items():
                        if char.role in ["protagonist", "antagonist"]:
                            art_data = self.art_director.generate_character_prompt(char)
                            bible.visual_assets.append(VisualAsset(
                                asset_type="character",
                                subject_id=name,
                                positive_prompt=art_data.get("positive_prompt", ""),
                                negative_prompt=art_data.get("negative_prompt", ""),
                                style_guide=bible.world_rules.power_system_name if bible.world_rules else ""
                            ))
                    
                    # 为分卷生成封面设计建议（如果已生成分卷）
                    volume_outlines = self.pipeline_state.volume_outlines
                    if volume_outlines:
                        for vol in volume_outlines:
                            art_data = self.art_director.generate_volume_cover_prompt(vol, bible.world_rules)
                            bible.visual_assets.append(VisualAsset(
                                asset_type="volume_cover",
                                subject_id=f"volume_{vol.get('volume_num')}",
                                positive_prompt=art_data.get("positive_prompt", ""),
                                negative_prompt=art_data.get("negative_prompt", ""),
                            ))
                    
                    logger.info(f"Art Library initialized with {len(bible.visual_assets)} visual assets.")
                    self.pipeline_state.set_bible(bible) # Save again with assets
                except Exception as e:
                    logger.warning(f"Art direction failed: {e}")
                # --- END ART DIRECTION ---
            except Exception as e:
                logger.warning(f"Failed to build ProductionBible: {e}")
                bible = None
        else:
            bible = self._production_bible

        if stop_at == "evaluation":
            eval_result = eval_result or self.pipeline_state.outline_evaluation or type('EvalResult', (), {'passed': False, 'score': 0.0, 'issues': [], 'suggestions': []})()
            return OutputPacker.pack_state_output(
                pipeline_summary={
                    "stage": "evaluation",
                    "evaluation_passed": eval_result.passed,
                    "evaluation_score": eval_result.score,
                    "evaluation_issues": eval_result.issues,
                    "bible_built": bible is not None,
                },
                execution_time=time.time() - start,
            )

        # Restore eval_result from state for downstream use
        if eval_result is None:
            eval_data = self.pipeline_state.outline_evaluation
            if eval_data:
                eval_result = type('EvalResult', (), {
                    'passed': eval_data.get('passed', False),
                    'score': eval_data.get('score', 0.0),
                    'issues': eval_data.get('issues', []),
                    'suggestions': eval_data.get('suggestions', []),
                })()

        return None

    def _run_volume_stage(
        self,
        current_idx: int,
        target_idx: int,
        world_data: dict,
        plot_data: dict,
        bible: Any,
        approval_mode: bool,
        stop_at: str | None,
        start: float,
    ) -> "BaseCrewOutput | None":
        """执行分卷大纲生成阶段。

        Returns:
            BaseCrewOutput if should stop/return; None if should continue.
        """
        volume_idx = StageSequence.get_stage_index("volume")
        if current_idx < volume_idx and (target_idx > volume_idx or stop_at == "volume"):
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

            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("volume", "pending")
                return OutputPacker.pack_approval_output(
                    pipeline_state=self.pipeline_state,
                    stage="volume",
                    content={"volume_outlines": volume_outlines},
                    execution_time=time.time() - start,
                    output_dir=self._get_novel_output_dir(),
                )
        else:
            volume_outlines = self.pipeline_state.volume_outlines

            if approval_mode:
                pending = self.pipeline_state.get_pending_feedback()
                if pending and pending.get("stage") == "volume":
                    feedback = HumanFeedback.from_dict(pending)
                    if feedback.decision == ApprovalDecision.APPROVE:
                        self.pipeline_state.set_stage_status("volume", "approve")
                        logger.info("Volume approved by user")
                    elif feedback.decision in (ApprovalDecision.REVISE, ApprovalDecision.REJECT):
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
            return OutputPacker.pack_state_output(
                pipeline_summary={
                    "stage": "volume",
                    "volumes_count": len(volume_outlines) if volume_outlines else 0,
                },
                execution_time=time.time() - start,
            )

        return None

    def _run_summary_stage(
        self,
        current_idx: int,
        target_idx: int,
        world_data: dict,
        plot_data: dict,
        volume_outlines: Any,
        bible: Any,
        approval_mode: bool,
        stop_at: str | None,
        start: float,
    ) -> "BaseCrewOutput | None":
        """执行章节概要生成阶段。

        Returns:
            BaseCrewOutput if should stop/return; None if should continue.
        """
        summary_idx = StageSequence.get_stage_index("summary")
        if current_idx < summary_idx and (target_idx > summary_idx or stop_at == "summary"):
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

            if approval_mode and self._approval_workflow:
                self.pipeline_state.set_stage_status("summary", "pending")
                return OutputPacker.pack_approval_output(
                    pipeline_state=self.pipeline_state,
                    stage="summary",
                    content={"chapter_summaries": chapter_summaries},
                    execution_time=time.time() - start,
                    output_dir=self._get_novel_output_dir(),
                )
        else:
            chapter_summaries = self.pipeline_state.chapter_summaries

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
                        chapter_num = feedback.chapter_num
                        num_volumes = len(volume_outlines) if volume_outlines else 1
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
            return OutputPacker.pack_state_output(
                pipeline_summary={
                    "stage": "summary",
                    "summaries_count": len(chapter_summaries) if chapter_summaries else 0,
                },
                execution_time=time.time() - start,
            )

        return None

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

    def _record_context_compaction(self, chapter_num: int) -> None:
        """Store the latest bible compaction report as a chapter artifact."""
        report = getattr(self.writing_crew, "last_compaction_report", None)
        if report is None:
            return

        try:
            report_dict = report.to_dict() if hasattr(report, "to_dict") else dict(report)
        except Exception:
            return

        self.save_artifact(chapter_num, "context_compaction", report_dict)

    def _get_novel_output_dir(self) -> str:
        """Get the output directory for the novel.

        Uses config's output_dir if provided, otherwise generates:
        novels/{novel_name}_{timestamp}/

        Cached after first call to ensure consistent directory throughout a run.
        """
        # Cache the output directory to ensure consistency within a single run
        if not hasattr(self, '_cached_output_dir'):
            # Use config's output_dir if available (set by CLI)
            config_output_dir = self.config.get("output_dir") if hasattr(self.config, "get") else None
            if config_output_dir:
                self._cached_output_dir = config_output_dir
            else:
                topic = self.config.get("topic", "未命名小说")
                # Sanitize topic for filesystem
                safe_topic = "".join(c if c.isalnum() or c in "_- " else "_" for c in topic)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self._cached_output_dir = f"novels/{safe_topic}_{timestamp}"
        return self._cached_output_dir

    @property
    def checkpoint_manager(self) -> CheckpointManager:
        """Get CheckpointManager instance (lazy init)."""
        if self._checkpoint_manager is None:
            output_dir = self._get_novel_output_dir()
            self._checkpoint_manager = CheckpointManager(self.config, output_dir)
        return self._checkpoint_manager

    def _save_chapter_checkpoint(self, chapter_output: ChapterOutput) -> None:
        """Save chapter content to disk immediately as checkpoint.

        Uses atomic write (temp file + rename) to ensure version always works.
        Directory: novels/{novel_name}/chapters/
        Filename: {chapter_num:03d}.{title}.md

        Args:
            chapter_output: The completed chapter output
        """
        self.checkpoint_manager.save_chapter_checkpoint(chapter_output)

    def _save_outline_checkpoint(self, world_data: dict, plot_data: dict, stage: str) -> None:
        """Save outline/evaluation artifacts to disk atomically.

        Saves: world.md, outline.md, evaluation.json to novels/{novel_name}/outline/

        Args:
            world_data: World-building data
            plot_data: Plot planning data
            stage: Current pipeline stage name
        """
        self.checkpoint_manager.save_outline_checkpoint(world_data, plot_data, stage)

    def kickoff(
        self,
        stop_at: str | None = None,
        pipeline_state_path: str | None = None,
        review_each_chapter: bool = False,
        approval_mode: bool = False,
        seed: str | None = None,
        variant: str | None = None,
    ) -> BaseCrewOutput:
        """执行完整流程（含强制 4 阶段访谈与宪法锁定）"""
        import time
        start = time.time()

        # --- MANDATORY DEEP INTERVIEW ---
        if not pipeline_state_path and not self.pipeline_state.world_data:
            from crewai.content.novel.services.interview_service import InterviewService
            service = InterviewService()
            logger.info("Initializing Story Engineering: Starting Deep Director's Interview...")
            
            # 1. 运行多阶段深度访谈
            interview_data = service.run_deep_interview()
            
            # 2. 合成本案专属宪法 (WRITER.md)
            commandments = service.synthesize_to_writer_md(interview_data)
            self.config["global_writer_rules"] = commandments
            
            # 3. 物理锁定宪法文件到小说专属目录
            out_dir = self.checkpoint_manager.output_dir
            from pathlib import Path
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            (Path(out_dir) / "WRITER.md").write_text(commandments, encoding="utf-8")
            logger.info(f"Framework Elements Locked. Constitution created at: {out_dir}/WRITER.md")

        # ... (rest of original kickoff logic)

        # 获取配置参数
        topic = self.config.get("topic", "")
        genre = self.config.get("genre", "")
        style = self.config.get("style", "")

        # 自动生成 seed_config（如果配置中提供了 topic, genre, style）
        seed_config = None
        if seed is None:
            seed = self.config.get("seed")
        if seed is None and topic:
            seed_config = SeedConfig(
                topic=topic,
                genre=genre,
                style=style,
                variant=variant,
            )
            seed = seed_config.generate_seed()
        elif seed:
            # 使用提供的 seed 创建 seed_config
            seed_config = SeedConfig(
                seed=seed,
                topic=topic,
                genre=genre,
                style=style,
                variant=variant,
            )

        # 设置 seed 到 pipeline_state（用于保存时记录）
        if seed:
            self.pipeline_state.seed = seed
            if seed_config:
                self.pipeline_state.seed_config = seed_config

            # 将 seed 传递给 LLM（使用 set_llm_seed 实现多方法 fallback）
            llm = self.config.get("llm")
            if llm:
                success = set_llm_seed(llm, seed)
                if success:
                    logger.info(f"LLM seed set successfully (from hex: {seed[:8]}...)")
                else:
                    logger.warning("Failed to set LLM seed, continuing without deterministic seed")

        # 初始化流水线状态（支持断点续跑和确定性重放）
        current_stage = self._init_pipeline_state(pipeline_state_path, seed, seed_config)

        # 阶段顺序定义
        stage_order = StageSequence.STAGES

        # 确定目标阶段索引
        target_stage = stop_at if stop_at else "complete"
        target_idx = StageSequence.get_stage_index(target_stage)
        if target_idx == 0 and target_stage != "init":
            target_idx = len(stage_order) - 1

        # 确定从哪里开始（基于已完成的阶段）
        current_idx = StageSequence.get_stage_index(current_stage)
        if current_idx == 0 and current_stage != "init":
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
        outline_idx = StageSequence.get_stage_index("outline")
        if current_idx < outline_idx and target_idx >= outline_idx:
            # --- MANDATORY CONSTITUTION SYNC ---
            self.outline_crew.config["global_writer_rules"] = self._load_writer_commandments()
            
            outline_data = self.outline_crew.generate_outline()
            world_data = outline_data.get("world", {})
            plot_data = outline_data.get("plot", {})

        # Restore from state after outline stage (variables may have been set from pipeline_state)
        outline_data = self.pipeline_state.outline_data or {}
        world_data = outline_data.get("world", {})
        plot_data = outline_data.get("plot", {})

        # PHASE 2: 大纲评估（Evaluator-Optimizer Gate）+ Production Bible
        if (result := self._run_evaluation_and_bible_stage(current_idx, target_idx, world_data, plot_data, stop_at, start)) is not None:
            return result

        # bible was built and stored in self._production_bible by _run_evaluation_and_bible_stage
        bible = self._production_bible

        # PHASE 3: 分卷大纲生成
        if (result := self._run_volume_stage(current_idx, target_idx, world_data, plot_data, bible, approval_mode, stop_at, start)) is not None:
            return result
        volume_outlines = self.pipeline_state.volume_outlines

        # --- ART DIRECTION (Volume Covers - Delayed until outlines exist) ---
        if bible is not None and volume_outlines:
            try:
                from crewai.content.novel.production_bible.bible_types import VisualAsset
                logger.info("Synthesizing exquisite volume cover prompts...")
                for vol in volume_outlines:
                    art_data = self.art_director.generate_volume_cover_prompt(vol, bible.world_rules)
                    bible.visual_assets.append(VisualAsset(
                        asset_type="volume_cover",
                        subject_id=f"Volume {vol.get('volume_num')}: {vol.get('title')}",
                        positive_prompt=art_data.get("positive_prompt", ""),
                        negative_prompt=art_data.get("negative_prompt", ""),
                    ))
                self.checkpoint_manager._export_art_manifest() # Force export
            except Exception as e:
                logger.warning(f"Volume art synthesis failed: {e}")

        # PHASE 4: 章节概要生成
        if (result := self._run_summary_stage(current_idx, target_idx, world_data, plot_data, volume_outlines, bible, approval_mode, stop_at, start)) is not None:
            return result
        chapter_summaries = self.pipeline_state.chapter_summaries

        # PHASE 5: 撰写章节（使用章节概要）
        try:
            chapters = self._write_all_chapters_from_summaries(world_data, chapter_summaries, review_each_chapter=review_each_chapter)
        except PendingChapterApproval as e:
            # P1: Delegate to ApprovalService for consistent approval output
            from crewai.content.novel.services.approval_service import ApprovalService

            self.pipeline_state.set_stage("writing")
            state_path = e.pipeline_state_path or ".pending_chapter.json"
            self.pipeline_state.save(state_path)

            service = ApprovalService.get_instance()
            return service.pack_chapter_approval_output(
                chapter_num=e.chapter_num,
                chapter_output=e.chapter_output,
                state_path=state_path,
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
        compaction_summary = {
            chapter_num: artifacts.get("context_compaction")
            for chapter_num, artifacts in self._chapter_artifacts.items()
            if "context_compaction" in artifacts
        }

        # P1: 调用 _evaluate_output() 评估输出质量 (与 BaseContentCrew.kickoff() 语义对齐)
        quality_report = self._evaluate_output(novel_output)
        output_status = "success"
        if not quality_report.is_usable:
            output_status = "failed"
        elif quality_report.errors:
            output_status = "failed"
        elif quality_report.requires_manual_review:
            output_status = "partial"
        elif quality_report.warnings:
            output_status = "warning"

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
                "context_compaction": compaction_summary,
                "global_postpass": global_report.to_dict(),
                "pipeline_state": self.pipeline_state.to_summary(),
                # P1: 质量报告 (与 BaseContentCrew.kickoff() 语义对齐)
                "quality_report": {
                    "is_usable": quality_report.is_usable,
                    "requires_manual_review": quality_report.requires_manual_review,
                    "output_status": output_status,
                    "warnings": quality_report.warnings,
                    "errors": quality_report.errors,
                },
            },
        )

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
        previous_chapter_ending = ""

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
        elif plot_data and plot_data.get("main_strand"):
            # FILM_DRAMA fallback: build minimal BibleSection from plot_data when ProductionBible unavailable
            try:
                from crewai.content.novel.production_bible.bible_types import (
                    BibleSection,
                    CharacterProfile,
                )
                main_strand = plot_data.get("main_strand", {})
                protagonist_data = main_strand.get("protagonist", {})
                if isinstance(protagonist_data, dict) and protagonist_data.get("name"):
                    protagonist_name = protagonist_data.get("name")
                else:
                    protagonist_name = main_strand.get("name", "林逸")

                # Build minimal characters from plot_data
                characters = {}
                characters[protagonist_name] = CharacterProfile(
                    name=protagonist_name,
                    role="protagonist",
                    personality=protagonist_data.get("personality", "") if isinstance(protagonist_data, dict) else "",
                    appearance="",
                    core_desire=protagonist_data.get("goal", "") if isinstance(protagonist_data, dict) else "",
                    fear="",
                    backstory=protagonist_data.get("background", "") if isinstance(protagonist_data, dict) else "",
                    character_arc="",
                    first_appearance=1,
                    faction="",
                    relationships={},
                )

                # Extract supporting characters from chapter_summaries if available
                chapter_summaries = self.pipeline_state.chapter_summaries if self.pipeline_state else []
                for ch in chapter_summaries[:5]:  # First 5 chapters
                    if "苏幼薇" in ch.get("summary", ""):
                        characters["苏幼薇"] = CharacterProfile(
                            name="苏幼薇", role="female_lead", personality="", appearance="",
                            core_desire="", fear="", backstory="", character_arc="",
                            first_appearance=5, faction="", relationships={},
                        )
                    if "沐风" in ch.get("summary", ""):
                        characters["沐风"] = CharacterProfile(
                            name="沐风", role="supporting", personality="", appearance="",
                            core_desire="", fear="", backstory="", character_arc="",
                            first_appearance=5, faction="", relationships={},
                        )
                    if "叶青" in ch.get("summary", ""):
                        characters["叶青"] = CharacterProfile(
                            name="叶青", role="supporting", personality="", appearance="",
                            core_desire="", fear="", backstory="", character_arc="",
                            first_appearance=5, faction="", relationships={},
                        )

                # Build minimal BibleSection
                bible_volume_map[1] = BibleSection(
                    volume_num=1,
                    relevant_characters=characters,
                    world_rules_summary="灵渊血脉：特殊血脉，可操控灵渊之力；境界：炼气境、筑基境、金丹境、元婴境、化神境",
                    timeline_up_to_this_point=[],
                    open_foreshadowing=[],
                    relationship_states_at_start={},
                    canonical_facts_this_volume=[
                        f"主角{protagonist_name}拥有灵渊血脉",
                        "星辰学院是主要修炼场所",
                        "暗影议会是敌对组织",
                    ],
                )
                logger.info("FILM_DRAMA: Built minimal BibleSection from plot_data")
            except Exception as e:
                logger.warning(f"Failed to build minimal BibleSection: {e}")

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
                previous_chapter_ending,
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
                                self._record_context_compaction(chapter_num)
                                chapter_memory = None
                except ValidationError as e:
                    # 格式/验证错误，阻止并报告
                    logger.error(f"Orchestrator validation error (not falling back): {e}")
                    raise
                except Exception as e:
                    # 其他异常，fallback
                    logger.warning(f"Orchestrator failed: {e}, falling back to WritingCrew")
                    draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                    self._record_context_compaction(chapter_num)
                    chapter_memory = None
            else:
                # 使用标准的单 Agent 写作
                draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                self._record_context_compaction(chapter_num)

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
                        logger.info(f"After expansion attempt {expansion_attempts}: word_count = {word_count}, min_required = {min_word_count:.0f}")
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

            # P1-2: 显式同步章节到 pipeline_state（让 replay 依赖的状态真实存在）
            self.pipeline_state.add_chapter(chapter_output)

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
            previous_summary = self._extract_chapter_ending_context(
                chapter_output.content if chapter_output.content else '',
                chapter_output.title
            )
            # Also store as previous_chapter_ending for dedicated continuity enforcement
            previous_chapter_ending = previous_summary

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
        previous_chapter_ending = ""

        # 计算每章目标字数
        num_chapters = len(chapter_summaries) if chapter_summaries else self.config.get("num_chapters", 10)
        target_words_per_chapter = self.config.get("target_words", 10000) // num_chapters

        # Build BibleSection per volume for bible-constrained writing (P1-4)
        bible_section_builder = None
        bible_volume_map: dict[int, Any] = {}  # volume_num -> BibleSection cache
        chapter_to_volume: dict[int, int] = {}  # Always initialize to avoid UnboundLocalError
        if self._production_bible is not None:
            try:
                from crewai.content.novel.production_bible.section_builder import (
                    BibleSectionBuilder,
                )
                bible_section_builder = BibleSectionBuilder()
                # Pre-build BibleSection for each volume that appears in chapter_summaries
                # Build a chapter_num -> volume_num lookup from pipeline_state.volume_outlines
                volume_outlines = getattr(self.pipeline_state, 'volume_outlines', []) or []
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
        elif self.pipeline_state.plot_data and self.pipeline_state.plot_data.get("main_strand"):
            # FILM_DRAMA fallback: build minimal BibleSections from plot_data when ProductionBible unavailable
            try:
                from crewai.content.novel.production_bible.bible_types import (
                    BibleSection,
                    CharacterProfile,
                )
                plot_data = self.pipeline_state.plot_data
                main_strand = plot_data.get("main_strand", {})
                protagonist_data = main_strand.get("protagonist", {})
                if isinstance(protagonist_data, dict) and protagonist_data.get("name"):
                    protagonist_name = protagonist_data.get("name")
                else:
                    protagonist_name = main_strand.get("name", "林逸")

                # Build minimal characters from plot_data
                characters = {}
                characters[protagonist_name] = CharacterProfile(
                    name=protagonist_name,
                    role="protagonist",
                    personality=protagonist_data.get("personality", "") if isinstance(protagonist_data, dict) else "",
                    appearance="",
                    core_desire=protagonist_data.get("goal", "") if isinstance(protagonist_data, dict) else "",
                    fear="",
                    backstory=protagonist_data.get("background", "") if isinstance(protagonist_data, dict) else "",
                    character_arc="",
                    first_appearance=1,
                    faction="",
                    relationships={},
                )

                # Build minimal BibleSection for all volumes
                bible_volume_map[1] = BibleSection(
                    volume_num=1,
                    relevant_characters=characters,
                    world_rules_summary="灵渊血脉：特殊血脉，可操控灵渊之力；境界：炼气境、筑基境、金丹境，元婴境、化神境",
                    timeline_up_to_this_point=[],
                    open_foreshadowing=[],
                    relationship_states_at_start={},
                    canonical_facts_this_volume=[
                        f"主角{protagonist_name}拥有灵渊血脉",
                        "星辰学院是主要修炼场所",
                        "暗影议会是敌对组织",
                    ],
                )
                logger.info("FILM_DRAMA: Built minimal BibleSection for parallel writing from plot_data")
            except Exception as e:
                logger.warning(f"Failed to build minimal BibleSection for parallel writing: {e}")

        for i, chapter_summary in enumerate(chapter_summaries):
            chapter_num = chapter_summary.get("chapter_num", i + 1)

            # 【新增】每 5 章自动进行内存折叠
            if chapter_num % 5 == 0 and chapter_num > 0:
                logger.info(f"Snipping history at chapter {chapter_num}")
                self.pipeline_state.snip_history(keep_last_n=3)

            # 如果有脏章节过滤，只重写脏章节；否则重写全部
            if self._chapters_to_regenerate is not None:
                    if chapter_num not in self._chapters_to_regenerate:
                        # 保留已有章节（从 pipeline_state.chapters 恢复，存储为dict）
                        existing = [c for c in self.pipeline_state.chapters if c.get("chapter_num") == chapter_num]
                        if existing:
                            # 重建 ChapterOutput dataclass 以保持类型一致（local chapters 期望 ChapterOutput）
                            preserved = ChapterOutput(
                                chapter_num=existing[0].get("chapter_num", chapter_num),
                                title=existing[0].get("title", f"第{chapter_num}章"),
                                content=existing[0].get("content", ""),
                                word_count=existing[0].get("word_count", 0),
                                key_events=existing[0].get("key_events", []),
                                character_appearances=existing[0].get("character_appearances", []),
                                setting=existing[0].get("setting", ""),
                                notes=existing[0].get("notes", ""),
                            )
                            chapters.append(preserved)
                            # 更新 previous_summary 以保持连续性
                            prev_content = existing[0].get("content", "") or ""
                            prev_summary = f"第{chapter_num}章结尾: {prev_content[-500:]}"
                            previous_summary = f"第{chapter_num}章结尾: {prev_summary}"
                            previous_chapter_ending = previous_summary
                            logger.info(f"Skipping clean chapter {chapter_num}, preserving from state")
                        else:
                            logger.warning(f"Chapter {chapter_num} marked clean but not in state, will generate")
                        continue

            # --- MACRO DESTINY REWRITER (Volume Boundary Optimization) ---
            vol_num = chapter_summary.get("volume_num") or chapter_to_volume.get(chapter_num, 1)
            is_volume_start = (chapter_num > 1 and chapter_to_volume.get(chapter_num) != chapter_to_volume.get(chapter_num - 1))
            
            
            if is_volume_start and self._production_bible is not None:
                try:
                    logger.info("Volume Boundary reached. Performing Total Audit and Memory Compaction...")
                    # 1. 执行全量深度审计 (对标 Claude Code Verify)
                    past_chapters = [c for c in chapters if c is not None]
                    full_volume_text = "\n\n".join(
                        [f"第{c.chapter_num}章 {c.title}\n{c.content}" for c in past_chapters]
                    )
                    audit_report = self.volume_auditor.audit_full_volume(full_volume_text, self._production_bible)
                    logger.info(
                        f"Volume Audit Complete. Health Score: {audit_report.get('total_health_score')}/100"
                    )
                    
                    # 2. 内存折叠 (对标 Claude Code Snip)
                    self.pipeline_state.snip_history(keep_last_n=5)
                    
                    # 3. 命运重构
                    future_volumes = [v for v in self.pipeline_state.volume_outlines if v.get("volume_num", 0) >= vol_num]
                    optimized = self.destiny_rewriter.optimize_future_path(self._production_bible, future_volumes)
                    if optimized.get("updated_volumes"):
                        for new_v in optimized["updated_volumes"]:
                            for i, old_v in enumerate(self.pipeline_state.volume_outlines):
                                if old_v.get("volume_num") == new_v.get("volume_num"):
                                    self.pipeline_state.volume_outlines[i] = new_v
                        logger.info(f"Future Destiny Updated: {optimized.get("optimization_logic")}")
                except Exception as e:
                    logger.warning(f"Macro processing failed: {e}")


            # 从概要构建章节大纲
            chapter_outline = self._build_outline_from_summary(chapter_summary)

            # --- PACING GOVERNOR (Narrative Heartbeat) ---
            pacing_instruction = ""
            if self._production_bible is not None:
                try:
                    adjustment = self.pacing_governor.calculate_adjustment(
                        target_tension=chapter_outline.get("tension_level", 5),
                        pacing_state=self._production_bible.pacing_state
                    )
                    # 动态微调大纲张力
                    chapter_outline["tension_level"] = adjustment.get("adjusted_tension", chapter_outline.get("tension_level", 5))
                    pacing_instruction = f"\n【节奏指挥官特别指令】：{adjustment.get('tone_instruction', '')}"
                    logger.info(f"Pacing adjustment applied: {adjustment.get('pacing_directive', 'balanced')}")
                except Exception as e:
                    logger.warning(f"Pacing governor failed: {e}")
            # --- END PACING ---

            # --- TROPE CRUSHER (Plot Subversion) ---
            if self._production_bible is not None:
                try:
                    logger.info(f"Crushing tropes for Chapter {chapter_num}...")
                    subversion = self.trope_crusher.subvert_outline(
                        chapter_outline=chapter_outline,
                        context=previous_summary
                    )
                    if subversion.get("updated_main_events"):
                        chapter_outline["main_events"] = subversion["updated_main_events"]
                        chapter_outline["signature_specs"] = subversion.get("updated_signature_specs", chapter_outline.get("signature_specs", []))
                        logger.info(f"Chapter {chapter_num} subverted: {subversion.get('subversion_logic', 'Logic Inversion applied')}")
                except Exception as e:
                    logger.warning(f"Trope crusher failed: {e}")
            # --- END TROPE CRUSHER ---

            # 构建写作上下文
            context = self._build_writing_context(
                chapter_num,
                world_data,
                previous_summary,
                previous_chapter_ending,
                chapter_outline,
                chapter_summary.get("word_target", target_words_per_chapter),
            )
            # 注入节奏指令
            if pacing_instruction:
                context.writing_goals = (context.writing_goals or "") + pacing_instruction

            # 获取本章对应的 BibleSection（P1-4: bible 约束写作）
            bible_section = None
            if bible_section_builder is not None or bible_volume_map:
                vol_num = chapter_summary.get("volume_num") or chapter_to_volume.get(chapter_num, 1)
                bible_section = bible_volume_map.get(vol_num) or bible_volume_map.get(1)

            # --- SELF-HEALING TASK WRITING LOOP (with A/B Testing support) ---
            chapter_task = self.task_registry.create_task(
                "writing", 
                f"Chapter {chapter_num}: {chapter_outline.get('title')}"
            )
            chapter_task.start()
            
            attempts = 0
            max_heals = 2
            polished_draft = ""
            current_fixup_directive = ""
            prev_score = None
            no_improvement_count = 0

            # 确定是否触发 A/B 测试 (仅限高潮章节且全局开启时)
            do_ab_test = (chapter_outline.get("tension_level", 0) >= 8 and self.config.get("ab_test_mode", False))

            while attempts <= max_heals:
                attempts += 1
                try:
                    # 1. 撰写草稿 (支持 A/B 分叉生成)
                    if current_fixup_directive:
                        context.writing_goals = (context.writing_goals or "") + f"\n【自愈修复指令】：{current_fixup_directive}"
                    
                    # 正常生成路径
                    draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                    self._record_context_compaction(chapter_num)
                    
                    # 如果需要 A/B 测试，再生成一个变体版本
                    if do_ab_test and attempts == 1:
                        logger.info(f"High-tension detected. Generating A/B branch for Chapter {chapter_num}...")
                        variant_context = context.model_copy()
                        variant_context.writing_goals = (variant_context.writing_goals or "") + "\n【分叉指令】：请尝试一个更激进/意外的剧情走向。"
                        draft_variant = self.writing_crew.write_chapter(variant_context, chapter_outline, bible_section)
                        self._record_context_compaction(chapter_num)
                        
                        # 评估两个分支
                        evaluations = self.branch_evaluator.run_evaluation([
                            {"id": "A (常规)", "content": draft},
                            {"id": "B (激进)", "content": draft_variant}
                        ], chapter_num)
                        
                        # --- INTERACTIVE CHOICE (Interview style) ---
                        from crewai.utilities.playback import ask_user
                        options = self.branch_evaluator.prepare_choice_ui(evaluations)
                        
                        logger.info("A/B Testing complete. Waiting for Director's decision...")
                        user_choice = ask_user(questions=[{
                            "header": f"第{chapter_num}章 剧情分叉选择",
                            "question": "请根据模拟读者的反馈选择最终执行版本：",
                            "type": "choice",
                            "options": options
                        }])
                        
                        chosen_label = user_choice["answers"]["0"]
                        chosen_idx = 0 if "版本 A" in chosen_label else 1
                        
                        logger.info(f"Director chose: {chosen_label}")
                        draft = draft if chosen_idx == 0 else draft_variant
                        # --- END INTERACTIVE CHOICE ---
                    
                    # 2. 审查和修改 (传入 suggest_only 参数以支持微操)
                    review_context = self._build_review_context(context, chapter_outline)
                    suggest_only = self.config.get("suggest_only", False)
                    critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
                        draft, review_context, suggest_only=suggest_only
                    )

                    # 2.5. 收敛性检测 (Quality Gate 质量分数无进展则强制退出)
                    if prev_score is not None and critique_result.score <= prev_score + 0.1:
                        no_improvement_count += 1
                        logger.warning(f"Quality score plateaued at {critique_result.score:.1f} (prev: {prev_score:.1f}), no_improvement_count={no_improvement_count}")
                        if no_improvement_count >= 2:
                            logger.warning(f"Quality score has plateaued for 2 consecutive attempts, forcing exit")
                            chapter_task.complete(result=f"Exited after {attempts} attempts due to score plateau")
                            break
                    else:
                        no_improvement_count = 0
                    prev_score = critique_result.score

                    # 3. 质量门禁校验
                    if not suggest_only and critique_result.has_high_severity_issues() and attempts <= max_heals:
                        logger.warning(f"Quality Gate Failed. Healing...")
                        chapter_task.fail(f"Quality issues found: {len(critique_result.issues)} issues")
                        current_fixup_directive = self.narrative_healer.diagnose_and_prescribe(
                            failed_content=polished_draft,
                            critique_issues=critique_result.issues
                        )
                        continue
                    
                    # 4. 成功通过
                    chapter_task.complete(result=f"Done in {attempts} attempts")
                    break
                    
                except Exception as e:
                    logger.error(f"Execution Error: {e}")
                    chapter_task.fail(str(e))
                    if attempts > max_heals: raise e

            # 计算字数
            word_count = len(polished_draft) // 2
            self.task_registry.print_status() # 实时打印任务大盘

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
                        logger.info(f"After expansion attempt {expansion_attempts}: word_count = {word_count}, min_required = {min_word_count:.0f}")
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

            # P1-2: 显式同步章节到 pipeline_state（让 replay 依赖的状态真实存在）
            self.pipeline_state.add_chapter(chapter_output)

            # Save checkpoint immediately to disk (enables recovery on crash)
            self._save_chapter_checkpoint(chapter_output)

            # 【新增】每章落盘后立即释放内存，防止内存累积
            chapter_output.content = "[SAVED to disk]"
            if hasattr(chapter_output, '_draft_phases'):
                chapter_output._draft_phases = {}  # 释放 5 个阶段的副本
            logger.info(f"Chapter {chapter_num} persisted and memory released")

            # 【新增】每章自动保存 PipelineState，防止 crash 导致状态丢失
            if hasattr(self.pipeline_state, 'save'):
                pipeline_state_path = self._save_pipeline_state_snapshot()
                logger.info(f"Chapter {chapter_num}: PipelineState saved to disk at {pipeline_state_path}")

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

            # 记录章节在连续性追踪器
            event = Event(
                id=f"chapter_{chapter_num}",
                timestamp=f"第{chapter_num}章",
                description=chapter_output.content[:200] if chapter_output.content else "",
                involved_entities=character_names,
                chapter=chapter_num,
            )
            self.continuity_tracker.add_event(event)

            # --- DYNAMIC BIBLE EVOLUTION (V2: Settings + Relationships) ---
            if self._production_bible is not None:
                try:
                    logger.info(f"Evolving Bible & Relationships from Chapter {chapter_num}...")
                    
                    # 1. 提取世界观/设定更新
                    updates = self.bible_evolver.extract_updates(
                        chapter_content=chapter_output.content,
                        chapter_num=chapter_num,
                        current_bible=self._production_bible
                    )
                    
                    # 2. 提取情感关系更新
                    rel_updates = self.relationship_evolver.extract_relationship_updates(
                        chapter_content=chapter_output.content,
                        current_bible=self._production_bible
                    )

                    # 3. 提取地理位置/移动更新
                    gps_updates = self.gps_navigator.track_movements(
                        chapter_content=chapter_output.content,
                        chapter_num=chapter_num,
                        current_gps=self._production_bible.character_gps
                    )
                    
                    if updates or rel_updates or gps_updates:
                        # Apply updates
                        if updates:
                            self._production_bible.apply_updates(updates)
                        if rel_updates:
                            self._apply_relationship_updates(rel_updates)
                        if gps_updates:
                            self._apply_gps_updates(gps_updates, chapter_num)
                            
                        logger.info(f"Bible evolved: {len(updates)} settings, {len(rel_updates)} relationships, {len(gps_updates)} movements.")
                        self.pipeline_state.set_bible(self._production_bible)

                        # Re-build BibleSection for the NEXT chapter's volume to ensure updates carry over
                        if bible_section_builder is not None:
                            next_chapter_num = chapter_num + 1
                            next_vol_num = chapter_to_volume.get(next_chapter_num)
                            if next_vol_num:
                                bible_volume_map[next_vol_num] = bible_section_builder.build_section(
                                    self._production_bible, next_vol_num
                                )
                                logger.info(f"BibleSection for volume {next_vol_num} refreshed with evolution.")
                except Exception as e:
                    logger.warning(f"Dynamic evolution failed for chapter {chapter_num}: {e}")
            # --- END BIBLE EVOLUTION ---

            # --- READER SWARM (Simulated Audience Feedback) ---
            try:
                logger.info(f"Gathering audience feedback for Chapter {chapter_num}...")
                feedback_report = self.reader_swarm.evaluate_chapter(
                    chapter_content=chapter_output.content,
                    chapter_num=chapter_num
                )
                if self._production_bible is not None:
                    self._production_bible.reader_sentiments.append(feedback_report)
                    logger.info(f"Chapter {chapter_num} Sentiment: {feedback_report.get('average_score')} | Highlight: {feedback_report.get('highlight_moment')}")
            except Exception as e:
                logger.warning(f"Reader swarm evaluation failed: {e}")
            # --- END AUDIENCE FEEDBACK ---

            # Store content for context
            previous_summary = self._extract_chapter_ending_context(
                chapter_output.content if chapter_output.content else '',
                chapter_output.title
            )
            # Also store as previous_chapter_ending for dedicated continuity enforcement
            previous_chapter_ending = previous_summary

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
                    # 保存状态文件到输出目录（使用_get_novel_output_dir()已缓存的路径）
                    output_dir = self._get_novel_output_dir()
                    pending_state_path = f"{output_dir}/.pending_chapter.json"
                    self.pipeline_state.save(pending_state_path)
                    raise PendingChapterApproval(
                        f"Chapter {chapter_num} pending approval",
                        chapter_num=chapter_num,
                        chapter_output=chapter_output,
                        pipeline_state_path=pending_state_path,
                    )

        # 清除脏章节标记（重写完成）
        if self._chapters_to_regenerate is not None:
            self.pipeline_state.clear_dirty_chapters()
            self._chapters_to_regenerate = None
            logger.info("Dirty chapters regeneration complete, cleared dirty markers")

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
                draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
                self._record_context_compaction(chapter_num)
                return draft
        else:
            draft = self.writing_crew.write_chapter(context, chapter_outline, bible_section)
            self._record_context_compaction(chapter_num)
            return draft

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
                bible=self._production_bible,
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
        previous_chapter_ending: str,
        chapter_outline: dict,
        target_words: int,
        bible_section: Any | None = None,
    ) -> WritingContext:
        """构建写作上下文（含角色人格 RAG 检索）"""
        # 从世界数据中提取角色信息
        character_profiles = self._extract_character_profiles(world_data)

        # --- CHARACTER RAG RETRIEVAL ---
        character_persona_context = ""
        if self.entity_memory is not None:
            try:
                # 检索本章活跃角色的人格快照
                character_persona_context = self.entity_memory.retrieve_character_context(
                    chapter_outline, self._production_bible
                )
            except Exception as e:
                logger.warning(f"Character RAG retrieval failed: {e}")

        return WritingContext(
            title=self.config.get("topic", "未命名小说"),
            genre=self.config.get("genre", ""),
            style=self.config.get("style", ""),
            world_description=world_data.get("description", ""),
            character_profiles=character_profiles,
            previous_chapters_summary=previous_summary,
            previous_chapter_ending=previous_chapter_ending,
            chapter_outline=str(chapter_outline),
            target_word_count=target_words,
            current_chapter_num=chapter_num,
            tension_arc="",
            bible_section=bible_section,
            character_persona_context=character_persona_context, # 注入 RAG 快照
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

    def _finalize_chapter(self, chapter_num, draft, context, chapter_outline, world_data, target_words_per_chapter) -> ChapterOutput:
        """完成章节的最后工序：Review, PostPass, Memory Update"""
        # 1. 审查和修改
        review_context = self._build_review_context(context, chapter_outline)
        critique_result, revised_draft, polished_draft = self.review_crew.critique_and_revise(
            draft, review_context
        )

        # 2. 存储 Artifacts
        self.save_artifact(chapter_num, 'draft', draft)
        self.save_artifact(chapter_num, 'critique', critique_result)
        self.save_artifact(chapter_num, 'revised', revised_draft)
        self.save_artifact(chapter_num, 'polished', polished_draft)

        # 3. 字数统计与扩展（略，保持原逻辑）
        word_count = len(polished_draft) // 2

        # 4. Per-Chapter PostPass
        postpass_result = self.per_chapter_postpass.process(
            chapter_num=chapter_num,
            chapter_content=polished_draft,
            chapter_outline=chapter_outline,
        )

        # 5. 创建输出对象
        chapter_output = ChapterOutput(
            chapter_num=chapter_num,
            title=chapter_outline.get("title", f"第{chapter_num}章"),
            content=polished_draft,
            word_count=word_count,
            key_events=chapter_outline.get("key_events", []),
            character_appearances=self._extract_character_names(polished_draft, world_data),
            setting=world_data.get("name", ""),
        )

        # 6. 同步状态
        self.pipeline_state.add_chapter(chapter_output)
        self._save_chapter_checkpoint(chapter_output)
        
        return chapter_output

    def _extract_character_names(self, content: str, world_data: dict) -> list[str]:
        """Extract character names from chapter content and world data.

        This is used to keep continuity tracking and relationship updates aligned
        with characters that actually appear in the generated chapter.
        """
        import re

        found_names = set()

        # 1. 从 world_data 的 factions 中提取已知角色名
        known_names: list[str] = []
        factions = world_data.get("factions", [])
        for faction in factions:
            if not isinstance(faction, dict):
                continue
            leader = faction.get("leader", "").strip()
            if leader:
                known_names.append(leader)
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
                pattern = re.compile(re.escape(name))
                if pattern.search(content):
                    found_names.add(name)

        # 4. 补充：使用正则匹配中文名字（2-4个汉字）作为兜底
        chinese_name_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}')
        for match in chinese_name_pattern.finditer(content):
            name = match.group()
            if name not in found_names and not self._is_likely_place_or_common_word(name):
                found_names.add(name)

        return list(found_names)

    
    def _apply_relationship_updates(self, rel_updates: dict) -> None:
        if not self._production_bible: return
        from crewai.content.novel.production_bible.bible_types import RelationshipState
        for char_name, targets in rel_updates.items():
            char = self._production_bible.get_character(char_name)
            if not char: continue
            for target_name, data in targets.items():
                if target_name not in char.relationships:
                    char.relationships[target_name] = RelationshipState(target_name=target_name, emotional_value=0, bond_type="认识")
                rel = char.relationships[target_name]
                rel.emotional_value = max(-100, min(100, rel.emotional_value + data.get("value_delta", 0)))
                if data.get("new_bond_type"): rel.bond_type = data["new_bond_type"]
                if data.get("interaction_summary"): rel.recent_interaction_summary = data["interaction_summary"]

    def _apply_gps_updates(self, gps_updates: dict, chapter_num: int) -> None:
        if not self._production_bible: return
        from crewai.content.novel.production_bible.bible_types import LocationState
        for char_name, update in gps_updates.items():
            new_loc = update.get("new_location")
            if new_loc:
                self._production_bible.character_gps[char_name] = LocationState(place_name=new_loc, arrival_chapter=chapter_num, status=update.get("action", "present"))
                if update.get("consistency_warning"):
                    import logging
                    logging.getLogger(__name__).warning(
                        f"GPS Warning for {char_name}: {update['consistency_warning']}"
                    )

    def _extract_character_names(self, content: str, world_data: dict) -> list[str]:
        """Extract character names found in chapter content.

        Uses both world data and a Chinese-name fallback to improve continuity
        tracking without requiring an LLM call.
        """
        import re

        found_names = set()
        known_names: list[str] = []
        factions = world_data.get("factions", [])
        if isinstance(factions, list):
            for faction in factions:
                if not isinstance(faction, dict):
                    continue
                leader = faction.get("leader", "").strip()
                if leader:
                    known_names.append(leader)
                members = faction.get("members", [])
                if isinstance(members, list):
                    for m in members:
                        if isinstance(m, str) and m.strip():
                            known_names.append(m.strip())
                        elif isinstance(m, dict) and m.get("name"):
                            known_names.append(m["name"])
        for name in known_names:
            if name and len(name) >= 2 and name in content:
                found_names.add(name)

        chinese_name_pattern = re.compile(r"[\u4e00-\u9fa5]{2,4}")
        for match in chinese_name_pattern.finditer(content):
            name = match.group()
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
        chapter_memory: dict[str, Any],
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

    def _extract_chapter_ending_context(self, content: str, chapter_title: str) -> str:
        """从章节内容中提取结尾场景描述，用于为下一章提供连贯的上下文。

        提取内容：具体场景/地点、人物及其状态、情绪氛围、悬念/伏笔

        Args:
            content: 章节正文内容
            chapter_title: 章节标题

        Returns:
            格式化结尾场景描述字符串
        """
        if not content:
            return ""

        # 取最后1500字作为结尾部分进行分析（扩大范围以捕获完整场景）
        ending_section = content[-1500:] if len(content) > 1500 else content

        # 简单分析：提取最后几段的关键信息
        # 注意：这里使用简单规则，未来可用LLM来做更精确的提取
        lines = ending_section.strip().split('\n')
        # 降低阈值到30字符，并取最后5段以更好地捕获结尾场景
        last_paragraphs = [l.strip() for l in lines if l.strip() and len(l.strip()) > 30][-5:]

        if not last_paragraphs:
            # fallback：简单截取最后300字
            return f"第{chapter_title}结尾: {content[-300:]}"

        # 组合最后几段作为场景延续的上下文
        scene_desc = "\n".join(last_paragraphs)
        return f"""【前章结尾场景】
{scene_desc}

以上是前章结尾的场景描述。请延续此场景继续写作，确保：
- 地点：必须与前章结尾保持一致，禁止切换到新地点
- 人物：必须延续前章结尾时在场的人物及其状态
- 情绪：必须自然延续前章结尾时的情绪氛围
- 时间：必须是前章结尾的延续，不能有时间跳跃
- 未解决情节：必须承接前章留下的悬念或伏笔"""
