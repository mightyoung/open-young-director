"""Content generation agents package.

Migrated from knowledge_base.agents for native crewai integration.

Subpackages:
- film_drama: FILM_DRAMA mode multi-agent novel generation
- protocols: Agent collaboration protocols (handoff, workflow, context)
- evaluation: Content quality evaluation and pass@k metrics
- consistency: Character/scene consistency for video generation

Top-level modules:
- reality_checker: Quality validation agent
- novel_orchestrator: Chapter orchestration
- novel_generator: Chapter content generation
- feedback_loop: Iterative content improvement
- outline_loader: Chapter outline parsing
- novel_workflow_orchestrator: Workflow orchestration
- config_manager: Configuration management
- chapter_manager: Chapter management
- knowledge_extractor: Knowledge extraction from chapters
- derivative_generator: Video prompts, podcasts, character descriptions
"""

# Re-export subpackages
from . import film_drama
from . import protocols
from . import evaluation
from . import consistency

# Re-export from subpackages for convenience
from .film_drama import (
    DirectorAgent,
    CharacterAgent,
    BeatType,
    Scene,
    DirectorScript,
    AgentPersona,
    MessageType,
    AgentRole,
    SceneStatus,
    InMemoryMessageQueue,
    MiddlewareChain,
    get_persona,
    render_system_prompt,
)
from .protocols import (
    AgentHandoff,
    HandoffResult,
    QualityGateError,
    WorkflowOrchestrator,
    PipelineConfig,
    PipelineResult,
    ContextManager,
    ExecutionContext,
    ContextPropagation,
    handoff_to_agent,
)
from .evaluation import (
    QualityLevel,
    ContentReward,
    ContentMetrics,
    PassAtK,
    pass_at_k,
    calculate_pass_at_k,
    estimate_pass_at_k,
    compute_reward_from_metrics,
    aggregate_rewards,
    EvaluatorType,
    EvaluationConfig,
    EvaluationResult,
    ContentEvaluator,
    RuleBasedEvaluator,
    LLMasJudgeEvaluator,
    create_evaluator,
)
from .consistency import (
    CharacterProfile,
    SceneProfile,
    Shot,
    Storyboard,
    SHOT_TYPES,
    CAMERA_MOVEMENTS,
    ConsistencyManager,
    DEFAULT_CHARACTER_TEMPLATES,
)

# Top-level modules
from .reality_checker import RealityChecker, RealityCheckerConfig, ValidationResult, get_reality_checker
from .novel_orchestrator import NovelOrchestrator, OrchestratorConfig
from .novel_generator import NovelGeneratorAgent, GeneratedChapter, get_novel_generator
from .feedback_loop import FeedbackLoop
from .outline_loader import OutlineLoader, OutlineEnforcer
from .novel_workflow_orchestrator import NovelWorkflowOrchestrator
from .config_manager import ConfigManager, get_config_manager
from .chapter_manager import ChapterManager
from .knowledge_extractor import KnowledgeExtractor, KnowledgeQuerier, ExtractedKnowledge
from .knowledge_extractor import extract_all_chapters, query_novel_knowledge
from .derivative_generator import DerivativeContentGenerator, VideoPrompt, PodcastScript, CharacterDescription
from .derivative_generator import get_derivative_generator

__all__ = [
    # Subpackages
    "film_drama",
    "protocols",
    "evaluation",
    "consistency",
    # Film drama
    "DirectorAgent",
    "CharacterAgent",
    "BeatType",
    "Scene",
    "DirectorScript",
    "AgentPersona",
    "MessageType",
    "AgentRole",
    "SceneStatus",
    "InMemoryMessageQueue",
    "MiddlewareChain",
    "get_persona",
    "render_system_prompt",
    # Protocols
    "AgentHandoff",
    "HandoffResult",
    "QualityGateError",
    "WorkflowOrchestrator",
    "PipelineConfig",
    "PipelineResult",
    "ContextManager",
    "ExecutionContext",
    "ContextPropagation",
    "handoff_to_agent",
    # Evaluation
    "QualityLevel",
    "ContentReward",
    "ContentMetrics",
    "PassAtK",
    "pass_at_k",
    "calculate_pass_at_k",
    "estimate_pass_at_k",
    "compute_reward_from_metrics",
    "aggregate_rewards",
    "EvaluatorType",
    "EvaluationConfig",
    "EvaluationResult",
    "ContentEvaluator",
    "RuleBasedEvaluator",
    "LLMasJudgeEvaluator",
    "create_evaluator",
    # Consistency
    "CharacterProfile",
    "SceneProfile",
    "Shot",
    "Storyboard",
    "SHOT_TYPES",
    "CAMERA_MOVEMENTS",
    "ConsistencyManager",
    "DEFAULT_CHARACTER_TEMPLATES",
    # Reality checker
    "RealityChecker",
    "RealityCheckerConfig",
    "ValidationResult",
    "get_reality_checker",
    # Novel orchestrator
    "NovelOrchestrator",
    "OrchestratorConfig",
    # Novel generator
    "NovelGeneratorAgent",
    "GeneratedChapter",
    "get_novel_generator",
    # Feedback loop
    "FeedbackLoop",
    # Outline loader
    "OutlineLoader",
    "OutlineEnforcer",
    # Workflow orchestrator
    "NovelWorkflowOrchestrator",
    # Config manager
    "ConfigManager",
    "get_config_manager",
    # Chapter manager
    "ChapterManager",
    # Knowledge extractor
    "KnowledgeExtractor",
    "KnowledgeQuerier",
    "ExtractedKnowledge",
    "extract_all_chapters",
    "query_novel_knowledge",
    # Derivative generator
    "DerivativeContentGenerator",
    "VideoPrompt",
    "PodcastScript",
    "CharacterDescription",
    "get_derivative_generator",
]
