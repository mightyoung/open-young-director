"""Novel stage services."""
from crewai.content.novel.services.base_stage_service import BaseStageService
from crewai.content.novel.services.outline_stage_service import OutlineStageService
from crewai.content.novel.services.volume_stage_service import VolumeStageService
from crewai.content.novel.services.summary_stage_service import SummaryStageService
from crewai.content.novel.services.writing_stage_service import WritingStageService
from crewai.content.novel.services.approval_coordinator import ApprovalCoordinator, ApprovalResult
from crewai.content.novel.services.replay_coordinator import ReplayCoordinator, ReplayPlan

__all__ = [
    "BaseStageService",
    "OutlineStageService",
    "VolumeStageService",
    "SummaryStageService",
    "WritingStageService",
    "ApprovalCoordinator",
    "ApprovalResult",
    "ReplayCoordinator",
    "ReplayPlan",
]
