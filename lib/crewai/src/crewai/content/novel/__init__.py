"""小说内容生成系统

这个模块提供完整的小说创作工作流，包括：
- 世界观构建
- 情节规划（Strand Weave结构）
- 章节撰写
- 内容审查和修改

主要组件：
- Agents: WorldAgent, PlotAgent, DraftAgent, InteriorityChecker, POVChecker
- Crews: WorldCrew, OutlineCrew, WritingCrew, ReviewCrew, NovelCrew

使用示例：
    from crewai.content.novel import NovelCrew

    crew = NovelCrew(config={
        "topic": "修仙逆袭",
        "style": "xianxia",
        "num_chapters": 30,
        "target_words": 500000,
    })
    result = crew.kickoff()
    novel = result.content
"""

from crewai.content.novel.novel_types import (
    NovelOutput,
    ChapterOutput,
    CharacterProfile,
    PlotStrand,
    WritingContext,
    ReviewCheckResult,
)

from crewai.content.novel.agents import (
    WorldAgent,
    PlotAgent,
    DraftAgent,
    InteriorityChecker,
    POVChecker,
    OutlineEvaluator,
    VolumeOutlineAgent,
    ChapterSummaryAgent,
)

from crewai.content.novel.crews import (
    WorldCrew,
    OutlineCrew,
    VolumeOutlineCrew,
    ChapterSummaryCrew,
    WritingCrew,
    ReviewCrew,
    NovelCrew,
)

from crewai.content.novel.pipeline_state import PipelineState

__all__ = [
    # Types
    "NovelOutput",
    "ChapterOutput",
    "CharacterProfile",
    "PlotStrand",
    "WritingContext",
    "ReviewCheckResult",
    # Agents
    "WorldAgent",
    "PlotAgent",
    "DraftAgent",
    "InteriorityChecker",
    "POVChecker",
    "OutlineEvaluator",
    "VolumeOutlineAgent",
    "ChapterSummaryAgent",
    # Crews
    "WorldCrew",
    "OutlineCrew",
    "VolumeOutlineCrew",
    "ChapterSummaryCrew",
    "WritingCrew",
    "ReviewCrew",
    "NovelCrew",
    # Pipeline
    "PipelineState",
]
