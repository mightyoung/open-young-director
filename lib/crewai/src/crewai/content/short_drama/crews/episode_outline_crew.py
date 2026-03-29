"""EpisodeOutlineCrew - 集大纲生成 Crew

使用 Agent 团队协作生成本集大纲：
- 主 Agent（EpisodeOutlineAgent）负责整体规划和情节编排
"""

from __future__ import annotations

__all__ = ["EpisodeOutlineCrew"]

from typing import Dict, Any, TYPE_CHECKING, List

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.short_drama.agents.episode_outline_agent import EpisodeOutlineAgent
from crewai.content.short_drama.short_drama_types import (
    ShortDramaBible,
    EpisodeOutline,
)

if TYPE_CHECKING:
    from crewai.llm import LLM


class EpisodeOutlineCrew(BaseContentCrew):
    """EpisodeOutlineCrew - 集大纲生成 Crew

    负责将章节内容或剧情摘要转换为短剧集大纲。

    使用示例:
        crew = EpisodeOutlineCrew(config=ContentConfig(...))
        result = crew.generate_outline(
            chapter_text="...",
            bible=short_drama_bible,
            episode_num=1,
        )
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建 Agents"""
        return {
            "episode_outliner": EpisodeOutlineAgent(
                llm=self.config.get("llm"),
                verbose=self.verbose,
            ),
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建 Tasks（由子类直接调用，不走通用 kickoff）"""
        return {}

    def generate_outline(
        self,
        chapter_text: str,
        bible: ShortDramaBible,
        episode_num: int,
        series_title: str = "",
        episode_context: str = "",
    ) -> EpisodeOutline:
        """生成本集大纲

        Args:
            chapter_text: 章节原文
            bible: ShortDramaBible
            episode_num: 集号
            series_title: 系列标题
            episode_context: 剧情承接（来自上一集结尾）

        Returns:
            EpisodeOutline: 集大纲
        """
        agent = self.agents.get("episode_outliner")
        if not agent:
            raise ValueError("EpisodeOutlineAgent not found in agents")

        # 直接调用 agent 生成
        result = agent.generate_outline(
            chapter_text=chapter_text,
            bible=bible,
            episode_num=episode_num,
            series_title=series_title,
            episode_context=episode_context,
        )

        # 转换为 EpisodeOutline 对象（包含尾帧）
        return EpisodeOutline(
            episode_num=result.get("episode_num", episode_num),
            title=result.get("title", f"第{episode_num}集"),
            episode_summary=result.get("episode_summary", ""),
            scene_plan=result.get("scene_plan", []),
            end_frame=result.get("end_frame", {}),
        )

    def generate_outline_batch(
        self,
        chapters_texts: List[tuple[int, str]],
        bible: ShortDramaBible,
        series_title: str = "",
    ) -> List[EpisodeOutline]:
        """批量生成本集大纲

        Args:
            chapters_texts: [(章节号, 章节文本), ...]
            bible: ShortDramaBible
            series_title: 系列标题

        Returns:
            list[EpisodeOutline]: 集大纲列表
        """
        outlines = []
        for chapter_num, chapter_text in chapters_texts:
            try:
                outline = self.generate_outline(
                    chapter_text=chapter_text,
                    bible=bible,
                    episode_num=chapter_num,
                    series_title=series_title,
                )
                outlines.append(outline)
            except Exception as e:
                import logging
                logging.warning(f"Failed to generate outline for chapter {chapter_num}: {e}")

        return outlines
