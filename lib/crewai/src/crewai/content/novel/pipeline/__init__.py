"""Novel generation pipeline — lightweight stage runner package.

Provides StageRunner (abstract base), EvaluateStage, WritingStage, ReviewStage,
PipelineRunner, ChapterConnector (inter-chapter continuity utility), and
ContextBuilder (token-budgeted context assembler for chapter writing).
No crewAI dependency; only stdlib + httpx via DeepSeekClient.
"""

from crewai.content.novel.pipeline.artifact_store import ArtifactStore, artifact_store_from_config
from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline.evaluate_stage import EvaluateStage
from crewai.content.novel.pipeline.review_stage import ReviewStage
from crewai.content.novel.pipeline.pipeline_runner import PipelineRunner
from crewai.content.novel.pipeline.chapter_connector import ChapterConnector
from crewai.content.novel.pipeline.context_builder import ContextBuilder
from crewai.content.novel.pipeline.backbone_validator import (
    BackboneMapping,
    BackboneValidator,
    ValidationResult,
)
from crewai.content.novel.pipeline.backbone_mapper import BackboneMapper
from crewai.content.novel.pipeline.human_review_gate import HumanReviewGate
from crewai.content.novel.pipeline.treatment_stage import TreatmentStage
from crewai.content.novel.pipeline.beat_sheet_stage import BeatSheetStage

try:
    from crewai.content.novel.pipeline.writing_stage import WritingStage  # type: ignore[import]
except ImportError:
    WritingStage = None  # type: ignore[assignment,misc]

__all__ = [
    "ArtifactStore",
    "artifact_store_from_config",
    "StageRunner",
    "EvaluateStage",
    "ReviewStage",
    "PipelineRunner",
    "WritingStage",
    "TreatmentStage",
    "BeatSheetStage",
    "ChapterConnector",
    "ContextBuilder",
    "BackboneMapping",
    "BackboneMapper",
    "BackboneValidator",
    "ValidationResult",
    "HumanReviewGate",
]
