"""ComfyUI crewAI Agent - 将 ComfyUI agentic-workflow 封装为 crewAI Agent.

Usage::

    from young_writer.lib.crewai.agents.comfyui_agent import create_comfyui_agent

    # Create the ComfyUI agent
    comfyui = create_comfyui_agent(
        host="127.0.0.1",
        port=8188,
        role="视觉资产生成专家",
    )

    # Use in a crew
    from crewai import Crew
    crew = Crew(agents=[novel_writer, comfyui], tasks=[...])

    result = crew.kickoff()
"""

from __future__ import annotations

from typing import Optional

try:
    from crewai import Agent
except ImportError:
    Agent = None  # type: ignore


def create_comfyui_agent(
    host: str = "127.0.0.1",
    port: int = 8188,
    role: str = "视觉资产生成专家",
    goal: str = "根据小说内容生成对应的插图、视频、语音和音乐",
    backstory: str = (
        "AI视觉内容生成专家，精通图像生成、视频合成、语音合成和音乐创作。"
        "能够将小说中的场景描述转化为高质量的视觉内容资产。"
    ),
    verbose: bool = True,
) -> Agent:
    """Create a ComfyUI crewAI Agent with the given configuration.

    Args:
        host: ComfyUI server host address.
        port: ComfyUI server port.
        role: The agent's role in the crew.
        goal: The agent's goal.
        backstory: The agent's backstory.
        verbose: Enable verbose output.

    Returns:
        A crewAI Agent configured with ComfyUI tools.
    """
    if Agent is None:
        raise ImportError(
            "crewAI is required for ComfyUI crewAI agent. Install with: pip install crewai"
        )

    # Import tools here to allow graceful degradation when crewAI is not installed
    try:
        from comfy_workflow_agent.tools import (
            GenerateImageTool,
            GenerateVideoTool,
            GenerateSpeechTool,
            GenerateMusicTool,
        )
    except ImportError:
        # Fallback for when comfy_workflow_agent is not in the Python path
        import sys
        from pathlib import Path

        comfy_agent_path = str(
            Path(__file__).parent.parent.parent.parent
            / "ComfyUI"
            / "comfy_workflow_agent"
        )
        sys.path.insert(0, comfy_agent_path)
        from tools import (
            GenerateImageTool,
            GenerateVideoTool,
            GenerateSpeechTool,
            GenerateMusicTool,
        )

    return Agent(
        role=role,
        goal=goal,
        backstory=backstory,
        verbose=verbose,
        allow_delegation=False,
        tools=[
            GenerateImageTool(host=host, port=port),
            GenerateVideoTool(host=host, port=port),
            GenerateSpeechTool(host=host, port=port),
            GenerateMusicTool(host=host, port=port),
        ],
    )
