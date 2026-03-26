"""小说内容生成Crews"""

from crewai.content.novel.crews.world_crew import WorldCrew
from crewai.content.novel.crews.outline_crew import OutlineCrew
from crewai.content.novel.crews.volume_outline_crew import VolumeOutlineCrew
from crewai.content.novel.crews.chapter_summary_crew import ChapterSummaryCrew
from crewai.content.novel.crews.writing_crew import WritingCrew
from crewai.content.novel.crews.review_crew import ReviewCrew
from crewai.content.novel.crews.novel_crew import NovelCrew

__all__ = [
    "WorldCrew",
    "OutlineCrew",
    "VolumeOutlineCrew",
    "ChapterSummaryCrew",
    "WritingCrew",
    "ReviewCrew",
    "NovelCrew",
]
