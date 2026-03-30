"""PipelineState - 跨阶段持久化状态

用于在多阶段流水线中保存和恢复中间结果：
- world_data: 世界观数据
- plot_data: 情节规划数据
- volume_outlines: 分卷大纲列表
- chapter_summaries: 章节概要列表
- chapters: 章节内容列表

支持：
- save() / load() - 磁盘持久化
- stop_at 语义 - 在指定阶段暂停
- resume_from 语义 - 从指定阶段恢复
- seed 语义 - 基于 topic+genre+style 的确定性重放
- replay_plan 语义 - 基于 ReplayPlan 的增量重放

使用示例:
    state = PipelineState()
    state.seed_config = SeedConfig(topic="修仙", genre="xianxia", style="epic")
    state.seed_config.generate_seed()
    state.world_data = world_data
    state.plot_data = plot_data
    state.save("novel_pipeline.json")

    # 恢复（使用 ReplayPlan 进行增量重放）
    state = PipelineState.load("novel_pipeline.json")
    replay_plan = state.get_replay_plan(new_seed_config)
    if replay_plan.regenerate_all:
        state = PipelineState()  # 完全重置
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from pathlib import Path

from crewai.content.novel.seed_mechanism import (
    SeedConfig,
    ReplayPlan,
    DirtyTracker,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """跨阶段流水线状态

    Attributes:
        world_data: 世界观数据（WorldAgent 输出）
        plot_data: 情节规划数据（PlotAgent 输出）
        volume_outlines: 分卷大纲列表
        chapter_summaries: 章节概要列表
        chapters: 章节输出列表
        current_stage: 当前阶段名称
        metadata: 额外元数据（配置、评分等）
    """

    world_data: dict = field(default_factory=dict)
    plot_data: dict = field(default_factory=dict)
    volume_outlines: list = field(default_factory=list)
    chapter_summaries: list = field(default_factory=list)
    chapters: list = field(default_factory=list)
    current_stage: str = "init"
    metadata: dict = field(default_factory=dict)

    # 评估结果
    outline_evaluation: dict = field(default_factory=dict)
    evaluation_passed: bool = False

    # 配置快照
    config: dict = field(default_factory=dict)

    # Production Bible 序列化（用于 resume 场景）
    bible_serialized: dict | None = field(default=None)

    # 审批工作流相关
    # 阶段状态: pending / approve / revise / reject / reinstruct / skip
    stage_statuses: dict = field(default_factory=dict)
    # 审批历史记录
    approval_history: list = field(default_factory=list)
    # 待处理的反馈
    pending_feedback: dict | None = field(default=None)
    # 审批模式是否开启
    approval_mode: bool = False

    # Seed 配置（基于 seed_mechanism.py 的改进设计）
    seed_config: SeedConfig | None = field(default=None)
    # 兼容性别名：保留旧的 seed 字段用于向后兼容
    seed: str = ""

    # 增量检查点相关
    # 保存检查点时的核心内容 hash（用于判断大纲是否变化）
    core_content_hash: str = ""
    # 脏章节标记：需要重新生成的章节号集合
    dirty_chapters: set = field(default_factory=set)
    # 脏数据追踪器
    _dirty_tracker: DirtyTracker = field(default_factory=DirtyTracker, repr=False)

    def save(self, path: str) -> None:
        """保存到磁盘

        Args:
            path: 保存路径（.json 文件）
        """
        # 确保目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # 自定义序列化，避免 asdict() 的 deepcopy 问题
        # (asdict 会递归复制所有对象，可能触发 RLock 等不可 pickle 对象的复制)
        data = self._serialize()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def _serialize(self) -> dict[str, Any]:
        """自定义序列化方法，避免 deepcopy 带来的 RLock pickle 问题

        Returns:
            dict: 可序列化的字典
        """
        import copy

        # 手动构建字典，避免 deepcopy
        result = {
            "world_data": self._safe_copy(self.world_data),
            "plot_data": self._safe_copy(self.plot_data),
            "volume_outlines": self._safe_copy(self.volume_outlines),
            "chapter_summaries": self._safe_copy(self.chapter_summaries),
            "chapters": self._safe_copy(self.chapters),
            "current_stage": self.current_stage,
            "metadata": self._safe_copy(self.metadata),
            "outline_evaluation": self._safe_copy(self.outline_evaluation),
            "evaluation_passed": self.evaluation_passed,
            "config": self._safe_copy(self.config),
            "bible_serialized": self._safe_copy(self.bible_serialized),
            "stage_statuses": self._safe_copy(self.stage_statuses),
            "approval_history": self._safe_copy(self.approval_history),
            "pending_feedback": self._safe_copy(self.pending_feedback),
            "approval_mode": self.approval_mode,
            # seed_config 单独处理
            "seed_config": self.seed_config.to_dict() if self.seed_config else None,
            "seed": self.seed,
            "core_content_hash": self.core_content_hash,
            "dirty_chapters": sorted(self.dirty_chapters) if self.dirty_chapters else [],
        }
        return result

    def _safe_copy(self, obj: Any) -> Any:
        """安全复制对象，使用 JSON 作为中介来避免不可 pickle 对象

        Args:
            obj: 要复制的对象

        Returns:
            复制后的对象
        """
        try:
            # 尝试使用 JSON 作为中介进行深拷贝
            # 这会剥离掉所有不可序列化的对象（如 RLock）
            return json.loads(json.dumps(obj, default=str, ensure_ascii=False))
        except (TypeError, ValueError):
            # 如果 JSON 序列化失败，尝试 asdict
            try:
                return copy.deepcopy(obj)
            except Exception:
                # 最后手段：返回原始对象（可能会有引用问题，但至少不会崩溃）
                return obj

    @classmethod
    def load(cls, path: str) -> "PipelineState":
        """从磁盘加载

        Args:
            path: 保存路径（.json 文件）

        Returns:
            PipelineState: 加载的状态
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Pipeline state file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 检查是否是旧格式（只有 seed，没有 seed_config）
        if "seed" in data and "seed_config" not in data:
            logger.info("Migrating legacy PipelineState format")
            return cls.migrate_legacy_state(data)

        # 确保 seed_config dict 被正确转换为 SeedConfig 对象
        if "seed_config" in data and data["seed_config"] is not None:
            if isinstance(data["seed_config"], dict):
                data["seed_config"] = SeedConfig.from_dict(data["seed_config"])

        return cls(**data)

    def get_stage(self) -> str:
        """获取当前阶段名称"""
        return self.current_stage

    def set_stage(self, stage: str) -> None:
        """设置当前阶段名称

        Args:
            stage: 阶段名称 (outline, evaluation, volume, summary, writing, complete)
        """
        self.current_stage = stage

    def has_stage(self, stage: str) -> bool:
        """检查是否已完成指定阶段

        Args:
            stage: 阶段名称

        Returns:
            bool: 是否已完成该阶段
        """
        stage_order = ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]
        try:
            current_idx = stage_order.index(self.current_stage)
            target_idx = stage_order.index(stage)
            return current_idx >= target_idx
        except ValueError:
            return False

    def is_resumable(self) -> bool:
        """检查是否可以从当前状态恢复"""
        # 至少要完成了大纲生成才能恢复
        return self.current_stage in ("outline", "evaluation", "volume", "summary")

    def get_outline_data(self) -> dict:
        """获取大纲数据（world + plot）"""
        return {
            "world": self.world_data,
            "plot": self.plot_data,
        }

    def set_outline_data(self, outline_data: dict) -> None:
        """设置大纲数据"""
        self.world_data = outline_data.get("world", {})
        self.plot_data = outline_data.get("plot", {})
        self.current_stage = "outline"

    def set_evaluation_result(self, result: dict, passed: bool) -> None:
        """设置评估结果

        Args:
            result: 评估结果字典
            passed: 是否通过
        """
        self.outline_evaluation = result
        self.evaluation_passed = passed
        self.current_stage = "evaluation"

    def set_volume_outlines(self, volume_outlines: list) -> None:
        """设置分卷大纲"""
        self.volume_outlines = volume_outlines
        self.current_stage = "volume"

    def set_chapter_summaries(self, chapter_summaries: list) -> None:
        """设置章节概要"""
        self.chapter_summaries = chapter_summaries
        self.current_stage = "summary"

    def add_chapter(self, chapter: Any) -> None:
        """添加章节内容

        Args:
            chapter: 章节内容（ChapterOutput 或 dict）
        """
        if hasattr(chapter, "__dict__"):
            # dataclass - 转换
            self.chapters.append(asdict(chapter))
        else:
            self.chapters.append(chapter)
        self.current_stage = "writing"

    def set_bible(self, bible: Any) -> None:
        """保存 ProductionBible（序列化后存入 bible_serialized）

        Args:
            bible: ProductionBible 实例
        """
        # Bible 对象无法直接 JSON 序列化，需要通过 asdict 转换
        # ProductionBible 是 dataclass，所以 asdict 可以工作
        try:
            self.bible_serialized = asdict(bible)
        except Exception as e:
            # 如果序列化失败，尝试其他方式
            try:
                import json
                # 尝试用 JSON 序列化后反序列化（清理不可序列化对象）
                self.bible_serialized = json.loads(json.dumps(bible, default=str, ensure_ascii=False))
            except Exception as e2:
                logger.warning(f"Failed to serialize ProductionBible (asdict: {e}, json: {e2})")
                self.bible_serialized = None

    def rebuild_bible(self) -> Any | None:
        """从 world_data + plot_data 重建 ProductionBible

        用于 resume 场景：PipelineState.load() 后调用此方法恢复 bible。
        要求 world_data 和 plot_data 已从状态中恢复。

        Returns:
            ProductionBible 实例，或 None（如果 world_data/plot_data 为空）
        """
        if not self.world_data and not self.plot_data:
            return None

        # 检查是否有序列化的 bible，如果有则从序列化重建
        if self.bible_serialized:
            try:
                from crewai.content.novel.production_bible.bible_types import ProductionBible
                # bible_serialized 是 asdict 后的 dict，直接用 dataclass.fromdict
                # 但 ProductionBible.from_dict 可能不存在，用 fromdict 替代
                bible = ProductionBible(**self.bible_serialized)
                # 重建后清除序列化数据（避免重复存储）
                self.bible_serialized = None
                return bible
            except Exception:
                pass

        # Fallback：通过 ProductionBibleBuilder 从头重建
        if not self.world_data or not self.plot_data:
            return None
        try:
            from crewai.content.novel.production_bible import ProductionBibleBuilder
            builder = ProductionBibleBuilder()
            return builder.build(self.world_data, self.plot_data)
        except Exception:
            return None

    def finalize(self) -> None:
        """标记流水线完成"""
        self.current_stage = "complete"

    def to_summary(self) -> dict:
        """获取流水线摘要"""
        return {
            "current_stage": self.current_stage,
            "world_name": self.world_data.get("name", ""),
            "plot_title": self.plot_data.get("series_overview", "")[:50],
            "volumes_count": len(self.volume_outlines),
            "chapters_summary_count": len(self.chapter_summaries),
            "chapters_written": len(self.chapters),
            "evaluation_passed": self.evaluation_passed,
            "config": self.config,
            "approval_mode": self.approval_mode,
            "stage_statuses": self.stage_statuses,
            "seed": self.seed,
            "seed_config": self.seed_config.to_dict() if self.seed_config else None,
        }

    @property
    def outline_data(self) -> dict:
        """获取大纲数据（world + plot）- 兼容性属性"""
        return self.get_outline_data()

    @property
    def dirty_tracker(self) -> DirtyTracker:
        """获取脏数据追踪器"""
        return self._dirty_tracker

    def mark_dirty(self, field: str) -> None:
        """标记字段为脏（需要重新生成）

        Args:
            field: 字段名 (world, outline, chapter_0, chapter_1, etc.)
        """
        self._dirty_tracker.mark_dirty(field)
        if field.startswith("chapter_"):
            try:
                chapter_num = int(field.split("_")[1])
                self.mark_chapters_dirty([chapter_num])
            except (IndexError, ValueError):
                pass
        elif field == "outline":
            self.mark_all_chapters_dirty()
        elif field == "world":
            self.mark_all_chapters_dirty()

    # ==================== 审批工作流方法 ====================

    def set_stage_status(self, stage: str, status: str) -> None:
        """设置阶段审批状态

        Args:
            stage: 阶段名 (outline, volume, summary)
            status: 状态 (pending, approve, revise, reject, reinstruct, skip)
        """
        self.stage_statuses[stage] = status

    def get_stage_status(self, stage: str) -> str:
        """获取阶段审批状态

        Args:
            stage: 阶段名

        Returns:
            状态字符串
        """
        return self.stage_statuses.get(stage, "pending")

    def is_stage_approved(self, stage: str) -> bool:
        """检查阶段是否已批准

        Args:
            stage: 阶段名

        Returns:
            是否已批准
        """
        return self.stage_statuses.get(stage) == "approve"

    def needs_user_feedback(self, stage: str) -> bool:
        """检查阶段是否需要用户反馈

        Args:
            stage: 阶段名

        Returns:
            是否需要用户反馈
        """
        if not self.approval_mode:
            return False
        return self.stage_statuses.get(stage) in ("pending", "revise", "reject")

    def add_approval_record(self, record: dict) -> None:
        """添加审批记录

        Args:
            record: 审批记录字典
        """
        self.approval_history.append(record)

    def set_pending_feedback(self, feedback: dict) -> None:
        """设置待处理的反馈

        Args:
            feedback: HumanFeedback 字典
        """
        self.pending_feedback = feedback

    def get_pending_feedback(self) -> dict | None:
        """获取待处理的反馈

        Returns:
            反馈字典或 None
        """
        return self.pending_feedback

    def clear_pending_feedback(self) -> None:
        """清除待处理的反馈"""
        self.pending_feedback = None

    def enable_approval_mode(self) -> None:
        """启用审批模式"""
        self.approval_mode = True
        # 初始化各阶段的待审批状态
        for stage in ["outline", "volume", "summary"]:
            if stage not in self.stage_statuses:
                self.stage_statuses[stage] = "pending"

    @staticmethod
    def generate_seed(topic: str, genre: str, style: str, variant: str | None = None) -> str:
        """基于 topic + genre + style 生成唯一 seed

        Args:
            topic: 小说主题
            genre: 小说类型
            style: 写作风格
            variant: 可选的变体标识，用于生成同一主题的不同变体

        Returns:
            str: 32字符的十六进制 seed
        """
        # 组合关键要素
        combined = f"{topic}|{genre}|{style}|{variant or 'default'}"
        # 使用 SHA256 生成确定性的 32字符 hash
        hash_digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return hash_digest[:32]

    @classmethod
    def create_seed_config(
        cls,
        topic: str = "",
        genre: str = "",
        style: str = "",
        variant: str | None = None,
        seed: str | None = None,
    ) -> SeedConfig:
        """创建 SeedConfig

        Args:
            topic: 小说主题
            genre: 小说类型
            style: 写作风格
            variant: 可选的变体标识
            seed: 可选的已有 seed

        Returns:
            SeedConfig: 种子配置
        """
        config = SeedConfig(
            topic=topic,
            genre=genre,
            style=style,
            variant=variant,
        )
        if seed:
            config.seed = seed
        else:
            config.generate_seed()
        return config

    def seed_valid(self, expected_seed: str | None = None) -> bool:
        """验证 seed 是否匹配

        当 expected_seed 为 None 时，只检查状态中是否已有 seed。
        当 expected_seed 提供时，检查是否与状态中的 seed 匹配。

        Args:
            expected_seed: 期望的 seed 值（通常来自配置）

        Returns:
            bool: seed 匹配返回 True，不匹配或无 seed 返回 False
        """
        # 优先使用 seed_config
        if self.seed_config:
            return self.seed_config.seed == expected_seed if expected_seed else True

        # 兼容旧格式
        if not self.seed:
            return False

        # 如果没有提供 expected_seed，只要状态中有 seed 就认为有效
        if expected_seed is None:
            return True

        # 比较 seed
        return self.seed == expected_seed

    def get_replay_plan(self, new_seed_config: SeedConfig | None = None) -> ReplayPlan:
        """计算重放计划

        基于当前状态的 seed_config 和新提供的 seed_config，
        确定哪些阶段需要重新生成。

        Args:
            new_seed_config: 新的种子配置

        Returns:
            ReplayPlan: 包含需要重新生成的阶段信息
        """
        # 情况1: 没有 seed_config，需要完全重新生成
        if not self.seed_config:
            logger.info("No seed_config found, will regenerate all")
            return ReplayPlan(regenerate_all=True)

        # 情况2: 没有新配置，只检查脏数据
        if not new_seed_config:
            if self.dirty_chapters:
                return ReplayPlan(
                    regenerate_from="chapters",
                    preserve=["outline", "world"],
                    dirty_chapters=list(self.dirty_chapters),
                )
            return ReplayPlan(replay_all=False)

        # 情况3: 核心参数变化（topic/genre/style）
        if not self.seed_config.matches(new_seed_config):
            logger.info(
                f"Core parameters changed: "
                f"({self.seed_config.topic},{self.seed_config.genre},{self.seed_config.style}) -> "
                f"({new_seed_config.topic},{new_seed_config.genre},{new_seed_config.style})"
            )
            return ReplayPlan(
                regenerate_from="world",
                preserve=["chapters"],
            )

        # 情况4: 核心内容（world/outline）变化
        if self.has_core_content_changed():
            logger.info("Core content (world/outline) changed")
            return ReplayPlan(
                regenerate_from="outline",
                preserve=["chapters"],
            )

        # 情况5: 只有脏章节
        if self.dirty_chapters:
            return ReplayPlan(
                regenerate_from="chapters",
                dirty_chapters=list(self.dirty_chapters),
            )

        # 情况6: variant 变化（只影响章节，不影响 world/outline）
        if self.seed_config.variant != new_seed_config.variant:
            logger.info(f"Variant changed: {self.seed_config.variant} -> {new_seed_config.variant}")
            return ReplayPlan(
                regenerate_from="chapters",
                preserve=["world", "outline"],
                dirty_chapters=list(range(len(self.chapters))) if self.chapters else None,
            )

        # 情况7: 不需要重新生成
        logger.info("No regeneration needed, using cached state")
        return ReplayPlan(replay_all=False)

    def preserve_approval_history(self) -> dict:
        """保留审批历史用于恢复

        Returns:
            dict: 包含 stage_statuses 和 approval_history 的字典
        """
        return {
            "stage_statuses": dict(self.stage_statuses),
            "approval_history": list(self.approval_history),
        }

    def restore_approval_history(self, preserved: dict) -> None:
        """恢复审批历史

        Args:
            preserved: preserve_approval_history() 返回的字典
        """
        if "stage_statuses" in preserved:
            self.stage_statuses = preserved["stage_statuses"]
        if "approval_history" in preserved:
            self.approval_history = preserved["approval_history"]

    @classmethod
    def migrate_legacy_state(cls, state_data: dict) -> "PipelineState":
        """迁移旧格式的 PipelineState

        旧格式只有 seed 字符串，没有 seed_config。

        Args:
            state_data: 旧格式的状态字典

        Returns:
            PipelineState: 迁移后的新状态
        """
        legacy_seed = state_data.get("seed", "")

        # 尝试从 metadata 反推
        metadata = state_data.get("metadata", {}) or state_data.get("config", {}) or {}
        seed_config = SeedConfig(
            seed=legacy_seed,
            topic=metadata.get("topic", ""),
            genre=metadata.get("genre", ""),
            style=metadata.get("style", ""),
        )

        # 创建新状态
        state = cls(**state_data)
        state.seed_config = seed_config

        logger.info("Migrated legacy PipelineState format to new format with SeedConfig")
        return state

    def verify(self) -> tuple[bool, str]:
        """验证检查点完整性

        Returns:
            (is_valid, error_message)
        """
        STAGE_ORDER = ["init", "outline", "evaluation", "volume", "summary", "writing", "complete"]

        if not self.seed:
            return False, "Missing seed"

        if self.current_stage not in STAGE_ORDER:
            return False, f"Invalid stage: {self.current_stage}"

        # 验证核心内容存在
        if self.current_stage in ["outline", "evaluation", "volume", "summary", "writing", "complete"]:
            if not self.world_data:
                return False, "Missing world_data"

        return True, ""

    def get_core_content_hash(self) -> str:
        """获取核心主干内容的 hash

        用于判断世界观、大纲等核心内容是否发生变化。

        Returns:
            str: 核心内容的 hash 值
        """
        # 核心内容：world_data + plot_data
        core = {
            "world": self.world_data,
            "plot": self.plot_data,
        }
        core_str = json.dumps(core, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(core_str.encode("utf-8")).hexdigest()[:16]

    def compute_core_content_hash(self) -> str:
        """计算当前核心内容的 hash

        与 get_core_content_hash 相同，但语义上表示"计算"而非"获取"。

        Returns:
            str: 核心内容的 hash 值
        """
        return self.get_core_content_hash()

    def mark_chapters_dirty(self, chapter_nums: list[int]) -> None:
        """标记章节为脏（需要重新生成）

        Args:
            chapter_nums: 需要重新生成的章节号列表
        """
        self.dirty_chapters.update(chapter_nums)

    def mark_all_chapters_dirty(self) -> None:
        """标记所有章节为脏（需要重新生成）"""
        # 所有已存在的章节都需要重新生成
        self.dirty_chapters.update(range(len(self.chapters)))

    def clear_dirty_chapters(self) -> None:
        """清除脏章节标记"""
        self.dirty_chapters.clear()

    def is_chapter_dirty(self, chapter_num: int) -> bool:
        """检查章节是否需要重新生成

        Args:
            chapter_num: 章节号（从 0 开始）

        Returns:
            bool: 是否需要重新生成
        """
        return chapter_num in self.dirty_chapters

    def get_dirty_chapters(self) -> list[int]:
        """获取所有需要重新生成的章节号

        Returns:
            list[int]: 脏章节号列表（已排序）
        """
        return sorted(self.dirty_chapters)

    def update_core_content_hash(self) -> str:
        """更新并保存当前核心内容 hash

        在保存检查点时调用，记录当前大纲的 hash。

        Returns:
            str: 更新后的 hash 值
        """
        self.core_content_hash = self.get_core_content_hash()
        return self.core_content_hash

    def has_core_content_changed(self) -> bool:
        """检查核心内容是否发生变化

        比较当前核心内容 hash 与保存检查点时的 hash。

        Returns:
            bool: 是否发生变化
        """
        if not self.core_content_hash:
            # 没有保存过 hash，视为变化
            return True
        return self.get_core_content_hash() != self.core_content_hash

    def __repr__(self) -> str:
        return f"PipelineState(stage={self.current_stage}, volumes={len(self.volume_outlines)}, chapters={len(self.chapters)})"
