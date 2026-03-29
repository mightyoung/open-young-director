"""Short Drama - AI短剧自动生成系统

本模块负责将小说内容自动转换为短剧视频：
1. 从小说章节提取集大纲
2. 将集大纲分解为具体镜头
3. 为每个镜头生成视频提示词
4. 调用视频API生成片段
5. 生成TTS配音
6. 使用 FFmpeg 合成最终视频
"""

from crewai.content.short_drama.short_drama_types import (
    Shot,
    ShortDramaScene,
    ShortDramaEpisode,
    ShortDramaBible,
    ShortDramaPipelineState,
    EpisodeOutline,
)
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.pipeline_orchestrator import (
    ShortDramaPipelineOrchestrator,
    PipelineResult,
    PipelineCheckpoint,
)

__all__ = [
    # Types
    "Shot",
    "ShortDramaScene",
    "ShortDramaEpisode",
    "ShortDramaBible",
    "ShortDramaPipelineState",
    "EpisodeOutline",
    # Builders
    "ShortDramaBibleBuilder",
    # Adapters
    "NovelToShortDramaAdapter",
    # Pipeline
    "ShortDramaPipelineOrchestrator",
    "PipelineResult",
    "PipelineCheckpoint",
]
