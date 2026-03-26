"""Embedded ComfyUI integration for CrewAI.

This module provides embedded ComfyUI workflow execution,
allowing image, audio, and video generation directly within
CrewAI agents without requiring a separate ComfyUI server.

Usage:
    from crewai.comfy import ComfyWorkflowExecutor, WorkflowBuilder

    # Execute a workflow
    executor = ComfyWorkflowExecutor()
    result = executor.execute(workflow)

    # Build a text-to-image workflow
    builder = WorkflowBuilder()
    workflow = builder.image.build_text_to_image("a beautiful landscape")

For novel content generation:
    from crewai.comfy import NovelMultimodalFlow

    flow = NovelMultimodalFlow()
    result = flow.kickoff({
        "chapter_outline": "场景描述",
        "characters": {...},
        "context": {...}
    })

For specialized agents:
    from crewai.comfy.agents import VisualDirectorAgent, SoundDesignerAgent

    visual_director = VisualDirectorAgent()
    result = visual_director.generate_scene_illustration(scene_description="...")

For preset workflows:
    from crewai.comfy import ScenePreset, get_preset

    preset = get_preset("battle")
    workflow = preset.build_workflow(scene_description="韩林vs叶尘")

For caching:
    from crewai.comfy.cache import get_cache, CachedComfyWorkflowExecutor

    executor = CachedComfyWorkflowExecutor()
"""

from crewai.comfy.executor import ComfyWorkflowExecutor
from crewai.comfy.workflow_builder import (
    ImageWorkflowBuilder,
    AudioWorkflowBuilder,
    VideoWorkflowBuilder,
    WorkflowBuilder,
)
from crewai.comfy.novel_multimodal_flow import (
    NovelMultimodalFlow,
    NovelMultimodalState,
    ChapterContent,
    SceneContent,
    MultimodalAsset,
    generate_novel_multimedia,
)

# Agents - import separately to avoid circular imports
from crewai.comfy.agents import (
    VisualDirectorAgent,
    SoundDesignerAgent,
    VideoProducerAgent,
)

# Crew
from crewai.comfy.crew import (
    MultimodalCrew,
    MultimodalCrewConfig,
    create_novel_multimodal_crew,
)

# Presets
from crewai.comfy.presets import (
    ScenePreset,
    get_preset,
    list_presets,
    build_preset_workflow,
    PresetWorkflowBuilder,
    SCENE_PRESETS,
)

# MiniMax Media Generation
from crewai.comfy.minimax import (
    MiniMaxMediaClient,
    MiniMaxVideoStatus,
    MiniMaxModel,
    MiniMaxDirectTextToVideoNode,
    MiniMaxDirectImageToVideoNode,
    MiniMaxDirectHailuoNode,
    MiniMaxDirectSubjectToVideoNode,
    MiniMaxDirectImageNode,
    MiniMaxDirectSpeechNode,
    MiniMaxDirectMusicNode,
    MiniMaxDirectVoiceCloneNode,
    MiniMaxDirectListVoicesNode,
    MiniMaxDirectVoiceDesignNode,
)

# Cache
from crewai.comfy.cache import (
    GenerationCache,
    CacheConfig,
    CacheEntry,
    get_cache,
    reset_cache,
    CachedComfyWorkflowExecutor,
)

__all__ = [
    # Executors
    "ComfyWorkflowExecutor",
    # Workflow Builders
    "ImageWorkflowBuilder",
    "AudioWorkflowBuilder",
    "VideoWorkflowBuilder",
    "WorkflowBuilder",
    # Flow
    "NovelMultimodalFlow",
    "NovelMultimodalState",
    "ChapterContent",
    "SceneContent",
    "MultimodalAsset",
    "generate_novel_multimedia",
    # Agents
    "VisualDirectorAgent",
    "SoundDesignerAgent",
    "VideoProducerAgent",
    # Crew
    "MultimodalCrew",
    "MultimodalCrewConfig",
    "create_novel_multimodal_crew",
    # Presets
    "ScenePreset",
    "get_preset",
    "list_presets",
    "build_preset_workflow",
    "PresetWorkflowBuilder",
    "SCENE_PRESETS",
    # MiniMax
    "MiniMaxMediaClient",
    "MiniMaxVideoStatus",
    "MiniMaxModel",
    "MiniMaxDirectTextToVideoNode",
    "MiniMaxDirectImageToVideoNode",
    "MiniMaxDirectHailuoNode",
    "MiniMaxDirectSubjectToVideoNode",
    "MiniMaxDirectImageNode",
    "MiniMaxDirectSpeechNode",
    "MiniMaxDirectMusicNode",
    "MiniMaxDirectVoiceCloneNode",
    "MiniMaxDirectListVoicesNode",
    "MiniMaxDirectVoiceDesignNode",
    # Cache
    "GenerationCache",
    "CacheConfig",
    "CacheEntry",
    "get_cache",
    "reset_cache",
    "CachedComfyWorkflowExecutor",
]
