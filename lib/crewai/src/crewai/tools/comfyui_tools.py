"""ComfyUI integration tools for CrewAI.

This module provides two modes of ComfyUI integration:
1. REST API mode: Connect to a running ComfyUI server
2. Embedded mode: Execute workflows directly using embedded ComfyUI

Usage (Embedded - Recommended):
    from crewai.tools.comfyui_tools import EmbeddedComfyUITool

    tool = EmbeddedComfyUITool()
    result = tool.generate_image("a beautiful landscape", negative="blurry")

Usage (REST API):
    from crewai.tools.comfyui_tools import ComfyUIImageTool

    image_tool = ComfyUIImageTool()
    result = await image_tool.generate("a beautiful landscape", negative="blurry")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ComfyUIError(Exception):
    """Base exception for ComfyUI operations."""
    pass


class ComfyUIConnectionError(ComfyUIError):
    """Raised when connection to ComfyUI fails."""
    pass


class ComfyUITimeoutError(ComfyUIError):
    """Raised when ComfyUI operation times out."""
    pass


class ComfyUIExecutionError(ComfyUIError):
    """Raised when ComfyUI workflow execution fails."""
    pass


class ComfyUIAdapter:
    """ComfyUI REST API adapter for async workflow execution.

    This class provides methods to:
    - Submit workflows to ComfyUI
    - Poll for execution completion
    - Retrieve output files

    Attributes:
        base_url: ComfyUI server URL (default: http://localhost:8188)
        timeout: Maximum time to wait for workflow completion (seconds)
        poll_interval: Interval between status polls (seconds)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8188",
        timeout: int = 300,
        poll_interval: int = 2,
    ) -> None:
        """Initialize ComfyUI adapter.

        Args:
            base_url: ComfyUI server URL
            timeout: Maximum wait time for workflow completion
            poll_interval: Seconds between status polls
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request to ComfyUI API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response as dict

        Raises:
            ComfyUIConnectionError: If request fails
        """
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            raise ComfyUIConnectionError(
                f"Failed to connect to ComfyUI at {self.base_url}. "
                "Is ComfyUI running?"
            ) from e
        except httpx.TimeoutException as e:
            raise ComfyUITimeoutError(
                f"Request to ComfyUI timed out after {self.timeout}s"
            ) from e
        except httpx.HTTPStatusError as e:
            raise ComfyUIError(f"HTTP {e.response.status_code}: {e.response.text}") from e

    async def submit_workflow(self, workflow: dict[str, Any]) -> str:
        """Submit a workflow for execution.

        Args:
            workflow: Workflow definition as dict with node_id -> {class_type, inputs}

        Returns:
            prompt_id for tracking the execution

        Example workflow structure:
            {
                "3": {"class_type": "KSampler", "inputs": {...}},
                "4": {"class_type": "CheckpointLoaderSimple", "inputs": {...}}
            }
        """
        response = await self._request(
            "POST",
            "/prompt",
            json={"prompt": workflow},
        )
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"No prompt_id in response: {response}")
        logger.info(f"Submitted workflow, prompt_id: {prompt_id}")
        return prompt_id

    async def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        """Get execution history for a prompt.

        Args:
            prompt_id: The prompt ID returned from submit_workflow

        Returns:
            History dict with status and outputs, or None if not found
        """
        try:
            return await self._request("GET", f"/history/{prompt_id}")
        except ComfyUIConnectionError:
            return None

    async def wait_for_completion(self, prompt_id: str) -> dict[str, Any]:
        """Wait for workflow execution to complete.

        Args:
            prompt_id: The prompt ID to wait for

        Returns:
            Completed execution info with outputs

        Raises:
            ComfyUITimeoutError: If execution doesn't complete within timeout
            ComfyUIExecutionError: If execution fails
        """
        elapsed = 0
        while elapsed < self.timeout:
            history = await self.get_history(prompt_id)

            if history and prompt_id in history:
                prompt_data = history[prompt_id]
                status = prompt_data.get("status", {})

                if status.get("error"):
                    raise ComfyUIExecutionError(
                        f"Workflow execution error: {status['error']}"
                    )

                if status.get("completed"):
                    logger.info(f"Workflow {prompt_id} completed")
                    return prompt_data

            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        raise ComfyUITimeoutError(
            f"Workflow {prompt_id} did not complete within {self.timeout}s"
        )

    async def get_output_file(
        self,
        filename: str,
        subfolder: str = "output",
        output_type: str = "output",
    ) -> bytes:
        """Retrieve an output file from ComfyUI.

        Args:
            filename: Name of the file to retrieve
            subfolder: Subfolder within the output directory
            output_type: Type of output (output, temp, etc.)

        Returns:
            Raw file bytes
        """
        params = {"filename": filename, "subfolder": subfolder, "type": output_type}
        url = f"{self.base_url}/view"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.content

    async def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status.

        Returns:
            Dict with queue_running and queue_pending lists
        """
        return await self._request("GET", "/queue")

    async def get_system_stats(self) -> dict[str, Any]:
        """Get ComfyUI system statistics.

        Returns:
            System info including GPU, memory, versions
        """
        return await self._request("GET", "/system_stats")


class ComfyUIImageAdapter(ComfyUIAdapter):
    """ComfyUI adapter specialized for image generation."""

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        batch_size: int = 1,
        steps: int = 20,
        cfg: float = 8.0,
        sampler_name: str = "euler",
        seed: int | None = None,
        model: str = "z_image_turbo_bf16.safetensors",
        clip: str = "qwen_3_4b.safetensors",
        vae: str = "ae.safetensors",
        filename_prefix: str = "novel",
    ) -> dict[str, str]:
        """Generate an image from text prompt.

        Args:
            prompt: Positive prompt describing the desired image
            negative_prompt: Negative prompt (things to avoid)
            width: Image width in pixels
            height: Image height in pixels
            batch_size: Number of images to generate
            steps: Number of sampling steps
            cfg: CFG scale for guidance
            sampler_name: Sampler to use (euler, dpmpp_2m, etc.)
            seed: Random seed (random if None)
            model: Model checkpoint filename
            clip: CLIP model filename
            vae: VAE model filename
            filename_prefix: Prefix for output filenames

        Returns:
            Dict mapping node_id to output info, including filenames
        """
        import random

        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        # Build simplified SD workflow
        workflow = {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": model},
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {"clip_name": clip},
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": vae},
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": batch_size,
                },
            },
            "5": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 0],
                    "text": prompt,
                },
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "clip": ["2", 0],
                    "text": negative_prompt if negative_prompt else "",
                },
            },
            "7": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["5", 0],
                    "negative": ["6", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler_name,
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "8": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["7", 0],
                    "vae": ["3", 0],
                },
            },
            "9": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["8", 0],
                    "filename_prefix": filename_prefix,
                },
            },
        }

        prompt_id = await self.submit_workflow(workflow)
        result = await self.wait_for_completion(prompt_id)

        # Extract output filenames
        outputs = result.get("outputs", {})
        save_image_output = outputs.get("9", {})
        images = save_image_output.get("images", [])

        return {
            "prompt_id": prompt_id,
            "images": images,
            "seed": seed,
        }


class ComfyUIAudioAdapter(ComfyUIAdapter):
    """ComfyUI adapter specialized for audio generation."""

    async def generate_audiobook(
        self,
        text: str,
        duration: int = 30,
        model: str = "ace_step_1.5.safetensors",
        filename_prefix: str = "audiobook",
    ) -> dict[str, str]:
        """Generate audio from text (text-to-speech).

        Args:
            text: Text to convert to speech
            duration: Maximum duration in seconds
            model: Audio model filename
            filename_prefix: Prefix for output filenames

        Returns:
            Dict with prompt_id and output filename
        """
        # Build audio generation workflow
        workflow = {
            "1": {
                "class_type": "EmptyLatentAudio",
                "inputs": {
                    "seconds": duration,
                },
            },
            "2": {
                "class_type": "TextEncodeAceStepAudio",
                "inputs": {
                    "text": text,
                },
            },
            "3": {
                "class_type": "AudioSampler",
                "inputs": {
                    "model": model,
                    "conditioning": ["2", 0],
                    "latent_audio": ["1", 0],
                },
            },
            "4": {
                "class_type": "AudioDecode",
                "inputs": {
                    "samples": ["3", 0],
                },
            },
            "5": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["4", 0],
                    "filename_prefix": filename_prefix,
                },
            },
        }

        prompt_id = await self.submit_workflow(workflow)
        result = await self.wait_for_completion(prompt_id)

        outputs = result.get("outputs", {})
        save_audio_output = outputs.get("5", {})
        audio_files = save_audio_output.get("audio", [])

        return {
            "prompt_id": prompt_id,
            "audio": audio_files[0] if audio_files else None,
        }


# ============================================================================
# CrewAI Tool Definitions
# ============================================================================

from typing import Annotated

from pydantic import BaseModel, Field

from crewai.tools.base_tool import Tool


class GenerateImageInput(BaseModel):
    """Input schema for ComfyUI image generation tool."""

    prompt: str = Field(
        description="Positive prompt describing the desired image in detail"
    )
    negative_prompt: str = Field(
        default="",
        description="Negative prompt describing what to avoid in the image",
    )
    width: int = Field(
        default=1024,
        description="Image width in pixels",
    )
    height: int = Field(
        default=1024,
        description="Image height in pixels",
    )
    steps: int = Field(
        default=20,
        description="Number of sampling steps (higher = more detail but slower)",
    )
    cfg: float = Field(
        default=8.0,
        description="CFG scale for prompt adherence",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed (random if not specified)",
    )


class ComfyUIImageToolInput(BaseModel):
    """Input schema for ComfyUI image tool."""

    prompt: str = Field(description="Positive prompt describing the desired image")
    negative_prompt: str = Field(default="", description="Negative prompt")
    width: int = Field(default=1024, description="Image width")
    height: int = Field(default=1024, description="Image height")
    steps: int = Field(default=20, description="Sampling steps")
    cfg: float = Field(default=8.0, description="CFG scale")


def _create_comfyui_image_tool() -> Tool:
    """Create CrewAI tool for ComfyUI image generation."""

    async def _generate_image(
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
    ) -> str:
        """Generate image using ComfyUI."""
        adapter = ComfyUIImageAdapter()
        result = await adapter.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
        )
        images = result.get("images", [])
        if images:
            return f"Generated {len(images)} image(s): {images[0]['filename']}"
        return "Image generation completed but no output found"

    return Tool(
        name="comfyui_image_generator",
        description="Generate images from text prompts using ComfyUI. "
        "Input is a detailed prompt describing the desired image. "
        "Returns the generated image filename(s).",
        args_schema=ComfyUIImageToolInput,
        func=_generate_image,
    )


# Singleton instance
comfyui_image_tool = _create_comfyui_image_tool()


# ============================================================================
# Embedded ComfyUI Tool (Direct Execution)
# ============================================================================


class EmbeddedComfyUITool:
    """Embedded ComfyUI tool for direct workflow execution.

    This tool uses ComfyUI's PromptExecutor directly without requiring
    a separate server. It provides the same functionality as the REST API
    adapter but runs entirely in-process.

    Usage:
        tool = EmbeddedComfyUITool()
        result = tool.generate_image(
            prompt="a beautiful landscape",
            negative="blurry, low quality"
        )
    """

    def __init__(
        self,
        comfy_path: str | None = None,
        models_dir: str | None = None,
    ):
        """Initialize the embedded tool.

        Args:
            comfy_path: Path to ComfyUI installation
            models_dir: Explicit models directory
        """
        self.comfy_path = comfy_path
        self.models_dir = models_dir
        self._executor = None

    @property
    def executor(self):
        """Lazy-load the executor."""
        if self._executor is None:
            from crewai.comfy import ComfyWorkflowExecutor

            self._executor = ComfyWorkflowExecutor(
                comfy_path=self.comfy_path,
                models_dir=self.models_dir,
            )
        return self._executor

    def generate_image(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
        model: str = "sd_xl_base_1.0.safetensors",
    ) -> dict[str, Any]:
        """Generate an image using embedded ComfyUI.

        Args:
            prompt: Positive prompt describing the desired image
            negative: Negative prompt
            width: Image width in pixels
            height: Image height in pixels
            steps: Number of sampling steps
            cfg: CFG scale
            seed: Random seed
            model: Model checkpoint filename

        Returns:
            Dict with outputs from the workflow
        """
        from crewai.comfy import WorkflowBuilder

        builder = WorkflowBuilder()
        workflow = builder.image.build_text_to_image(
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
            model=model,
        )

        result = self.executor.execute(workflow)
        return result

    def list_available_nodes(self) -> list[str]:
        """List all available ComfyUI node classes.

        Returns:
            List of node class names
        """
        return self.executor.list_available_nodes()


def _create_embedded_image_tool() -> Tool:
    """Create CrewAI tool for embedded ComfyUI image generation."""

    def _generate_image(
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
    ) -> str:
        """Generate image using embedded ComfyUI."""
        tool = EmbeddedComfyUITool()
        result = tool.generate_image(
            prompt=prompt,
            negative=negative,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
        )
        outputs = result.get("outputs", {})
        if outputs:
            # Get the SaveImage node output
            for node_id, output in outputs.items():
                if isinstance(output, dict) and "images" in output:
                    images = output["images"]
                    if images:
                        return f"Generated {len(images)} image(s)"
        return "Image generation completed"

    return Tool(
        name="embedded_comfyui_image_generator",
        description="Generate images from text prompts using embedded ComfyUI. "
        "This tool runs ComfyUI directly without requiring a separate server. "
        "Input is a detailed prompt describing the desired image.",
        args_schema=ComfyUIImageToolInput,
        func=_generate_image,
    )


# Singleton instance for embedded tool
embedded_comfyui_image_tool = _create_embedded_image_tool()


__all__ = [
    "ComfyUIAdapter",
    "ComfyUIImageAdapter",
    "ComfyUIAudioAdapter",
    "ComfyUIError",
    "ComfyUIConnectionError",
    "ComfyUITimeoutError",
    "ComfyUIExecutionError",
    "ComfyUIImageToolInput",
    "GenerateImageInput",
    "comfyui_image_tool",
    "EmbeddedComfyUITool",
    "embedded_comfyui_image_tool",
]
