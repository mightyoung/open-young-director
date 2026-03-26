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

使用示例:
    state = PipelineState()
    state.world_data = world_data
    state.plot_data = plot_data
    state.save("novel_pipeline.json")

    # 恢复
    state = PipelineState.load("novel_pipeline.json")
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from pathlib import Path

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

    def save(self, path: str) -> None:
        """保存到磁盘

        Args:
            path: 保存路径（.json 文件）
        """
        # 确保目录存在
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2, default=str)

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
        }

    def __repr__(self) -> str:
        return f"PipelineState(stage={self.current_stage}, volumes={len(self.volume_outlines)}, chapters={len(self.chapters)})"
