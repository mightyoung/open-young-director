"""NovelToShortDramaAdapter - 从小说项目适配到短剧

负责从已有的小说项目中读取：
- ProductionBible
- 章节文本

并转换为短剧生成所需的格式。
"""

import json
import logging
from pathlib import Path
from typing import Optional

from crewai.content.novel.production_bible.bible_types import ProductionBible
from crewai.content.novel.pipeline_state import PipelineState
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.short_drama_types import (
    ShortDramaBible,
    EpisodeOutline,
)

logger = logging.getLogger(__name__)


class NovelToShortDramaAdapter:
    """从小说项目适配到短剧

    读取已有的小说项目数据，转换为短剧生成所需的格式。
    支持两种输入模式：
    1. PipelineState（推荐）：直接获取序列化的 ProductionBible
    2. 手动指定路径：从文件读取
    """

    def __init__(self, project_root: str | Path):
        """初始化适配器

        Args:
            project_root: 小说项目根目录
        """
        self.project_root = Path(project_root)
        self._bible: Optional[ProductionBible] = None
        self._pipeline_state: Optional[PipelineState] = None

    def load_pipeline_state(self, state_file: str = "pipeline_state.json") -> PipelineState:
        """加载流水线状态

        Args:
            state_file: 状态文件名

        Returns:
            PipelineState: 加载的状态
        """
        state_path = self.project_root / state_file
        if not state_path.exists():
            raise FileNotFoundError(f"Pipeline state not found: {state_path}")

        self._pipeline_state = PipelineState.load(str(state_path))
        return self._pipeline_state

    def get_production_bible(self) -> Optional[ProductionBible]:
        """获取 ProductionBible

        优先从 PipelineState 获取，如果不可用则尝试从文件加载。

        Returns:
            ProductionBible 或 None
        """
        if self._bible:
            return self._bible

        # 尝试从 pipeline_state 重建
        if self._pipeline_state:
            bible = self._pipeline_state.rebuild_bible()
            if bible:
                self._bible = bible
                return bible

        # 尝试从 bible.json 加载
        bible_path = self.project_root / "bible.json"
        if bible_path.exists():
            with open(bible_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            try:
                self._bible = ProductionBible(**data)
                return self._bible
            except Exception as e:
                logger.warning(f"Failed to load bible from {bible_path}: {e}")

        return None

    def get_chapter_text(self, chapter_num: int, chapter_file: str = None) -> str:
        """获取章节文本

        Args:
            chapter_num: 章节号
            chapter_file: 可选，章节文件名（默认按 convention 查找）

        Returns:
            str: 章节文本
        """
        if chapter_file:
            chapter_path = self.project_root / chapter_file
        else:
            # 按 convention 查找：chapters/chapter_001.md
            chapter_path = self.project_root / "chapters" / f"chapter_{chapter_num:03d}.md"

        if not chapter_path.exists():
            # 尝试其他格式
            for pattern in [
                f"chapter_{chapter_num}.md",
                f"ch_{chapter_num}.md",
                f"{chapter_num}.md",
            ]:
                alt_path = self.project_root / "chapters" / pattern
                if alt_path.exists():
                    chapter_path = alt_path
                    break

        if not chapter_path.exists():
            raise FileNotFoundError(f"Chapter {chapter_num} not found")

        with open(chapter_path, "r", encoding="utf-8") as f:
            return f.read()

    def get_chapters_text(self, chapter_nums: list[int]) -> list[tuple[int, str]]:
        """获取多个章节文本

        Args:
            chapter_nums: 章节号列表

        Returns:
            list[tuple[int, str]]: [(章节号, 文本), ...]
        """
        result = []
        for num in chapter_nums:
            try:
                text = self.get_chapter_text(num)
                result.append((num, text))
            except FileNotFoundError as e:
                logger.warning(f"Skipping chapter {num}: {e}")
        return result

    def build_short_drama_bible(
        self,
        episode_num: int,
        series_title: str,
        episode_context: str = "",
        characters_in_episode: list[str] = None,
        style: str = "xianxia",
    ) -> ShortDramaBible:
        """构建 ShortDramaBible

        Args:
            episode_num: 目标集号
            series_title: 系列标题
            episode_context: 本集剧情承接
            characters_in_episode: 本集出场角色
            style: 小说风格

        Returns:
            ShortDramaBible
        """
        bible = self.get_production_bible()
        if not bible:
            raise ValueError("ProductionBible not available")

        builder = ShortDramaBibleBuilder(style=style)
        return builder.build(
            bible=bible,
            episode_num=episode_num,
            series_title=series_title,
            episode_context=episode_context,
            characters_in_episode=characters_in_episode,
        )

    def extract_episode_context(
        self,
        prev_chapter_num: int,
        current_chapter_num: int,
    ) -> str:
        """提取剧情承接

        从上一章结尾提取本集开始前的剧情承接。

        Args:
            prev_chapter_num: 上一章编号
            current_chapter_num: 当前章编号

        Returns:
            str: 剧情承接描述
        """
        try:
            prev_text = self.get_chapter_text(prev_chapter_num)
            # 取最后 500 字作为剧情承接
            context = prev_text[-500:].strip()
            return context
        except Exception as e:
            logger.warning(f"Failed to extract context: {e}")
            return ""

    def get_episode_outline_from_chapter(
        self,
        chapter_num: int,
    ) -> EpisodeOutline:
        """从章节文本生成集大纲

        当前使用启发式分割（按段落+短对话检测），精度有限。

        Args:
            chapter_num: 章节号

        Returns:
            EpisodeOutline
        """
        text = self.get_chapter_text(chapter_num)

        # TODO: 使用 LLM 分析情节结构替代启发式分割
        scenes = []
        current_scene = None
        scene_count = 0

        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 简单启发式：如果段落较短且包含对话，可能是新场景
            if len(para) < 200 and ("【" in para or "场景" in para):
                scene_count += 1
                if current_scene:
                    scenes.append(current_scene)
                current_scene = {
                    "scene_number": scene_count,
                    "location": "待定",
                    "time_of_day": "待定",
                    "description": para[:100],
                    "key_actions": [],
                    "characters": [],
                    "emotion": "待定",
                }
            elif current_scene:
                current_scene["description"] += f"\n{para[:200]}"

        if current_scene:
            scenes.append(current_scene)

        return EpisodeOutline(
            episode_num=chapter_num,
            title=f"第{chapter_num}章",
            episode_summary=text[:200],
            scene_plan=scenes,
        )


__all__ = ["NovelToShortDramaAdapter"]
