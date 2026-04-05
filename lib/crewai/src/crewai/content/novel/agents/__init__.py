"""小说内容生成Agents"""

from crewai.content.novel.agents.world_agent import WorldAgent
from crewai.content.novel.agents.plot_agent import PlotAgent
from crewai.content.novel.agents.draft_agent import DraftAgent
from crewai.content.novel.agents.interiority_checker import InteriorityChecker
from crewai.content.novel.agents.pov_checker import POVChecker
from crewai.content.novel.agents.continuity_checker import ContinuityChecker
from crewai.content.novel.agents.outline_evaluator import OutlineEvaluator
from crewai.content.novel.agents.volume_outline_agent import VolumeOutlineAgent
from crewai.content.novel.agents.chapter_summary_agent import ChapterSummaryAgent
from crewai.content.novel.agents.reference_agent import ReferenceAgent

__all__ = [
    "WorldAgent",
    "PlotAgent",
    "DraftAgent",
    "InteriorityChecker",
    "POVChecker",
    "ContinuityChecker",
    "OutlineEvaluator",
    "VolumeOutlineAgent",
    "ChapterSummaryAgent",
    "ReferenceAgent",
]
