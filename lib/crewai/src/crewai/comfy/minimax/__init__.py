# -*- encoding: utf-8 -*-
"""MiniMax Media Generation Module.

This module provides direct integration with MiniMax API for:
- Video Generation (T2V, I2V, S2V, Hailuo-02)
- Image Generation
- Audio/Speech Generation (TTS)
- Music Generation
- Voice Clone & Voice Design

Based on ComfyUI's minimax_direct_api.py implementation.

Usage:
    from crewai.comfy.minimax import MiniMaxMediaClient

    client = MiniMaxMediaClient()
    result = await client.generate_video(prompt="a beautiful landscape")
"""

from crewai.comfy.minimax.client import (
    MiniMaxMediaClient,
    MiniMaxVideoStatus,
    MiniMaxModel,
)
from crewai.comfy.minimax.nodes import (
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

__all__ = [
    # Client
    "MiniMaxMediaClient",
    "MiniMaxVideoStatus",
    "MiniMaxModel",
    # Nodes
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
]
