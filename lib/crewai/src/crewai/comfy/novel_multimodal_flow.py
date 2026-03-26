"""NovelMultimodalFlow - Event-driven multimodal novel content generation.

This flow coordinates:
1. Text generation via NovelOrchestrator (FILM_DRAMA)
2. Image generation via ComfyUI (embedded)
3. Audio generation for audiobook

Usage:
    # Auto-initialize with LLM client
    flow = NovelMultimodalFlow(auto_init_orchestrator=True)
    result = flow.kickoff({
        "chapter_outline": "韩林在测灵大典上被羞辱",
        "characters": {...},
        "context": {...}
    })

    # Manual orchestrator
    from agents.novel_orchestrator import NovelOrchestrator
    orchestrator = NovelOrchestrator(llm_client=llm)
    flow = NovelMultimodalFlow(orchestrator=orchestrator)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from crewai.flow import Flow, listen, start
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================================
# State Models
# ============================================================================


class MultimodalAsset(BaseModel):
    """A generated multimodal asset."""

    asset_id: str = Field(default_factory=lambda: str(uuid4()))
    asset_type: str  # "image", "audio", "video"
    prompt: str
    content: Optional[str] = None  # Path to file or content
    metadata: dict[str, Any] = {}
    scene_id: Optional[str] = None


class SceneContent(BaseModel):
    """Content for a single scene."""

    scene_id: str
    beat_type: str  # "opening", "conflict", "climax", "resolution"
    characters: list[str]
    location: str
    text_content: str
    image_assets: list[MultimodalAsset] = []
    audio_assets: list[MultimodalAsset] = []


class ChapterContent(BaseModel):
    """Complete chapter content with multimodal assets."""

    chapter_number: int
    title: str
    outline: str
    scenes: list[SceneContent] = []
    images: list[MultimodalAsset] = []
    audio: Optional[MultimodalAsset] = None
    final_content: str = ""


class NovelMultimodalState(BaseModel):
    """State for NovelMultimodalFlow."""

    chapter_number: int = 1
    chapter_outline: str = ""
    context: dict[str, Any] = {}
    characters: dict[str, Any] = {}

    # Generated content
    scenes: list[SceneContent] = []
    images: list[MultimodalAsset] = []
    audio: Optional[MultimodalAsset] = None
    final_content: str = ""

    # Status
    text_generation_complete: bool = False
    image_generation_complete: bool = False
    audio_generation_complete: bool = False

    # Orchestrator reference
    orchestrator: Any = None


# ============================================================================
# Flow Implementation
# ============================================================================


class NovelMultimodalFlow(Flow[NovelMultimodalState]):
    """Flow for multimodal novel content generation.

    This flow:
    1. Generates text content using NovelOrchestrator (FILM_DRAMA)
    2. Generates illustrations for key scenes via ComfyUI
    3. Generates audiobook audio via ComfyUI

    Usage:
        # Auto-initialize orchestrator with LLM
        flow = NovelMultimodalFlow(auto_init_orchestrator=True)
        result = flow.kickoff({
            "chapter_outline": "测灵大典场景",
            "characters": {"韩林": {...}, "柳如烟": {...}},
            "context": {"location": "太虚宗", ...}
        })

        # Manual orchestrator injection
        flow = NovelMultimodalFlow(orchestrator=my_orchestrator)
    """

    def __init__(
        self,
        config: Optional[dict[str, Any]] = None,
        orchestrator: Any = None,
        auto_init_orchestrator: bool = False,
    ):
        """Initialize the flow.

        Args:
            config: Optional configuration dict with keys:
                - comfy_path: Path to ComfyUI installation
                - models_dir: Path to models directory
                - generate_images: Whether to generate images (default: True)
                - generate_audio: Whether to generate audio (default: True)
                - auto_init_orchestrator: Auto-create orchestrator if True
            orchestrator: Pre-configured NovelOrchestrator instance
            auto_init_orchestrator: If True, auto-create orchestrator with LLM
        """
        self._media_executor = None
        self._orchestrator = orchestrator
        self.config = config or {}
        self.comfy_path = self.config.get("comfy_path")
        self.models_dir = self.config.get("models_dir")
        self.generate_images = self.config.get("generate_images", True)
        self.generate_audio = self.config.get("generate_audio", True)
        self._auto_init_orchestrator = auto_init_orchestrator or self.config.get("auto_init_orchestrator", False)
        super().__init__()

    # =========================================================================
    # Media Executor (Lazy initialization)
    # =========================================================================

    @property
    def media_executor(self) -> Any:
        """Get or create the MiniMaxMediaExecutor instance."""
        if self._media_executor is None:
            from knowledge_base.media import get_media_executor
            self._media_executor = get_media_executor()
            logger.info("MiniMaxMediaExecutor initialized")
        return self._media_executor

    # =========================================================================
    # Orchestrator (Lazy initialization)
    # =========================================================================

    def _create_orchestrator(self) -> Optional[Any]:
        """Create a NovelOrchestrator with LLM client.

        Returns:
            NovelOrchestrator instance or None if creation fails
        """
        try:
            # Add knowledge_base to path
            kb_path = self._find_knowledge_base_path()
            if kb_path and kb_path not in sys.path:
                sys.path.insert(0, kb_path)
                logger.info(f"Added knowledge_base path: {kb_path}")

            from agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig

            # Try to get LLM client
            llm_client = self._get_llm_client()

            config = OrchestratorConfig(
                max_subagent_concurrent=5,
                max_concurrent_scenes=3,
                enable_verification=True,
                max_retry=2,
                mode="FILM_DRAMA",
            )

            orchestrator = NovelOrchestrator(
                llm_client=llm_client,
                config=config,
            )
            orchestrator.setup({})
            logger.info("NovelOrchestrator (FILM_DRAMA) initialized")
            return orchestrator

        except Exception as e:
            logger.error(f"Failed to create NovelOrchestrator: {e}")
            return None

    def _run_orchestrator_sync(self, orchestrator: Any, chapter_number: int, chapter_outline: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run orchestrator synchronously, handling async event loop issues.

        The NovelOrchestrator uses asyncio.get_event_loop() which fails when called
        from a thread without an event loop. This method handles that properly.
        """
        try:
            # Try running with new event loop
            import threading

            def run_in_thread():
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return orchestrator.orchestrate_chapter(
                        chapter_number=chapter_number,
                        chapter_outline=chapter_outline,
                        context=context,
                    )
                finally:
                    loop.close()

            # Run in dedicated thread to avoid event loop conflicts
            result = threading.Thread(target=lambda: setattr(threading.current_thread(), '_result', run_in_thread())).start()
            # Actually execute
            thread_result = None
            exception_holder = [None]

            def target():
                nonlocal thread_result
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        thread_result = orchestrator.orchestrate_chapter(
                            chapter_number=chapter_number,
                            chapter_outline=chapter_outline,
                            context=context,
                        )
                    finally:
                        loop.close()
                except Exception as e:
                    exception_holder[0] = e

            t = threading.Thread(target=target)
            t.start()
            t.join(timeout=120)  # 2 minute timeout

            if exception_holder[0]:
                raise exception_holder[0]

            if thread_result is None:
                raise TimeoutError("Orchestrator timed out")

            return thread_result

        except Exception as e:
            logger.error(f"Orchestrator sync execution failed: {e}")
            raise

    def _find_knowledge_base_path(self) -> Optional[str]:
        """Find the knowledge_base directory path."""
        # Try common locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent.parent / "knowledge_base",
            Path(__file__).parent.parent.parent.parent / "knowledge_base",
            Path.cwd() / "knowledge_base",
            Path.cwd().parent / "knowledge_base",
        ]

        for path in possible_paths:
            if path.exists() and (path / "agents").exists():
                return str(path.parent)

        # Try parent chain
        current = Path(__file__).parent
        for _ in range(6):
            kb_path = current / "knowledge_base"
            if kb_path.exists() and (kb_path / "agents").exists():
                return str(kb_path.parent)
            current = current.parent

        return None

    def _get_llm_client(self) -> Any:
        """Get LLM client for orchestrator.

        Priority: MiniMax > Kimi > OpenAI
        """
        kb_path = self._find_knowledge_base_path()
        if kb_path and kb_path not in sys.path:
            sys.path.insert(0, kb_path)

        # Try MiniMax first
        try:
            from llm.minimax_client import get_minimax_client
            client = get_minimax_client()
            if client.api_key:
                logger.info("Using MiniMax LLM client")
                return client
        except Exception as e:
            logger.warning(f"Could not get MiniMax client: {e}")

        # Try Kimi second
        try:
            from llm.kimi_client import get_kimi_client
            client = get_kimi_client()
            if client.api_key or client._cli_available:
                logger.info("Using Kimi LLM client")
                return client
        except Exception as e:
            logger.warning(f"Could not get Kimi client: {e}")

        # Fallback to OpenAI
        try:
            from openai import OpenAI
            return OpenAI()
        except Exception:
            pass

        return None

    # =========================================================================
    # Flow Steps
    # =========================================================================

    @start()
    def initialize_chapter(self, crewai_trigger_payload: dict = None) -> dict[str, Any]:
        """Initialize chapter generation.

        Args:
            crewai_trigger_payload: Dict with:
                - chapter_outline: Scene outline description
                - characters: Character profiles dict
                - context: Additional context
                - chapter_number: Chapter number (optional)

        Returns:
            Initialized state dict
        """
        logger.info("Initializing chapter generation")

        # Handle both direct kickoff inputs and trigger payload
        inputs = crewai_trigger_payload or {}

        self.state.chapter_outline = inputs.get("chapter_outline", "")
        self.state.characters = inputs.get("characters", {})
        self.state.context = inputs.get("context", {})
        self.state.chapter_number = inputs.get("chapter_number", 1)

        # Initialize orchestrator if available
        orchestrator = inputs.get("orchestrator")
        if orchestrator:
            self.state.orchestrator = orchestrator

        return inputs

    @listen(initialize_chapter)
    def generate_text_content(self, inputs: dict[str, Any]) -> ChapterContent:
        """Generate text content using NovelOrchestrator.

        Args:
            inputs: Initialized state from initialize_chapter

        Returns:
            ChapterContent with text
        """
        logger.info("Generating text content")

        orchestrator = self.state.orchestrator

        # Auto-initialize orchestrator if configured
        if orchestrator is None and self._auto_init_orchestrator:
            orchestrator = self._create_orchestrator()
            if orchestrator:
                self.state.orchestrator = orchestrator

        if orchestrator:
            try:
                # Use _run_orchestrator_sync to handle async event loop issues
                result = self._run_orchestrator_sync(
                    orchestrator,
                    self.state.chapter_number,
                    self.state.chapter_outline,
                    {
                        **self.state.context,
                        "characters": self.state.characters,
                    },
                )
                self.state.final_content = result.get("content", "")
                logger.info(f"FILM_DRAMA content generated: {len(self.state.final_content)} chars")
            except Exception as e:
                logger.error(f"FILM_DRAMA generation failed: {e}")
                self.state.final_content = f"第{self.state.chapter_number}章\n\n{self.state.chapter_outline}"
        else:
            # Fallback: just use the outline as content
            logger.info("No orchestrator available, using outline as content")
            self.state.final_content = f"第{self.state.chapter_number}章\n\n{self.state.chapter_outline}"

        self.state.text_generation_complete = True
        logger.info("Text generation complete")

        return self._build_chapter_content()

    @listen(generate_text_content)
    def generate_illustrations(self, chapter_content: ChapterContent) -> ChapterContent:
        """Generate illustrations for scenes via ComfyUI.

        Args:
            chapter_content: Chapter with text content

        Returns:
            Updated ChapterContent with images
        """
        if not self.generate_images:
            logger.info("Image generation disabled, skipping")
            return chapter_content

        logger.info("Generating illustrations")

        # Extract key scenes that need images
        key_scenes = self._extract_key_scenes(chapter_content)

        for scene in key_scenes:
            image_asset = self._generate_scene_image(scene)
            if image_asset:
                chapter_content.images.append(image_asset)
                scene.image_assets.append(image_asset)

        self.state.images = chapter_content.images
        self.state.image_generation_complete = True
        logger.info(f"Generated {len(chapter_content.images)} images")

        return chapter_content

    @listen(generate_illustrations)
    def generate_audiobook(self, chapter_content: ChapterContent) -> ChapterContent:
        """Generate audiobook audio via ComfyUI.

        Args:
            chapter_content: Chapter with text and images

        Returns:
            Updated ChapterContent with audio
        """
        if not self.generate_audio:
            logger.info("Audio generation disabled, skipping")
            return chapter_content

        logger.info("Generating audiobook audio")

        audio_asset = self._generate_audio_from_text(chapter_content.final_content)
        if audio_asset:
            chapter_content.audio = audio_asset
            self.state.audio = audio_asset

        self.state.audio_generation_complete = True
        logger.info("Audio generation complete")

        return chapter_content

    @listen(generate_audiobook)
    def finalize_chapter(self, chapter_content: ChapterContent) -> dict[str, Any]:
        """Finalize chapter with all assets.

        Args:
            chapter_content: Complete chapter content

        Returns:
            Final result dict
        """
        logger.info("Finalizing chapter")

        return {
            "chapter_number": chapter_content.chapter_number,
            "title": chapter_content.title,
            "content": chapter_content.final_content,
            "scenes": [s.model_dump() for s in chapter_content.scenes],
            "images": [img.model_dump() for img in chapter_content.images],
            "audio": chapter_content.audio.model_dump() if chapter_content.audio else None,
            "status": "complete",
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _build_chapter_content(self) -> ChapterContent:
        """Build ChapterContent from state."""
        return ChapterContent(
            chapter_number=self.state.chapter_number,
            title=f"第{self.state.chapter_number}章",
            outline=self.state.chapter_outline,
            scenes=self.state.scenes,
            images=self.state.images,
            audio=self.state.audio,
            final_content=self.state.final_content,
        )

    def _extract_key_scenes(self, chapter_content: ChapterContent) -> list[SceneContent]:
        """Extract key scenes that need illustrations.

        Returns scenes with beat_type "opening", "conflict", or "climax".
        """
        key_types = {"opening", "conflict", "climax"}
        return [s for s in chapter_content.scenes if s.beat_type in key_types]

    def _generate_scene_image(self, scene: SceneContent) -> Optional[MultimodalAsset]:
        """Generate an image for a scene.

        Args:
            scene: SceneContent to generate image for

        Returns:
            MultimodalAsset or None if generation fails
        """
        # Build prompt from scene content
        prompt = self._build_scene_prompt(scene)

        try:
            import asyncio
            result = asyncio.run(
                self.media_executor.generate_image(
                    prompt=prompt,
                    aspect_ratio="16:9",
                )
            )

            image_url = result.get("image_url")

            return MultimodalAsset(
                asset_type="image",
                prompt=prompt,
                content=image_url,
                metadata={"scene_id": scene.scene_id, "model": "image-01"},
                scene_id=scene.scene_id,
            )
        except Exception as e:
            logger.error(f"Image generation failed for scene {scene.scene_id}: {e}")
            return None

    def _build_scene_prompt(self, scene: SceneContent) -> str:
        """Build image generation prompt from scene.

        Args:
            scene: Scene to build prompt for

        Returns:
            Prompt string for image generation
        """
        char_names = ", ".join(scene.characters) if scene.characters else ""
        location = scene.location

        # Build descriptive prompt
        prompt = f"Chinese fantasy novel scene"
        if char_names:
            prompt += f", featuring {char_names}"
        if location:
            prompt += f", in {location}"
        if scene.text_content:
            # Use first 200 chars of text as context
            context = scene.text_content[:200]
            prompt += f", {context}"

        return prompt

    def _generate_audio_from_text(self, text: str) -> Optional[MultimodalAsset]:
        """Generate audio from text content.

        Args:
            text: Text to convert to audio

        Returns:
            MultimodalAsset or None if generation fails
        """
        try:
            import asyncio
            result = asyncio.run(
                self.media_executor.generate_speech(
                    text=text[:5000] if len(text) > 5000 else text,  # Limit text length
                    voice_id="female-shaonv",
                    speed=1.0,
                )
            )

            audio_url = result.get("audio_url")

            return MultimodalAsset(
                asset_type="audio",
                prompt=text[:100] + "..." if len(text) > 100 else text,
                content=audio_url,
                metadata={"model": "speech-02-hd"},
            )
        except Exception as e:
            logger.error(f"Audio generation failed: {e}")
            return None

    def _extract_image_from_outputs(self, outputs: dict) -> Optional[str]:
        """Extract image path from workflow outputs.

        Args:
            outputs: Workflow output dict

        Returns:
            Image path or None
        """
        # Look for SaveImage node output
        for node_id, output in outputs.items():
            if isinstance(output, dict):
                if "images" in output:
                    images = output["images"]
                    if images and isinstance(images, list):
                        # Return first image path
                        return images[0].get("filename") if isinstance(images[0], dict) else str(images[0])
        return None

    def _extract_audio_from_outputs(self, outputs: dict) -> Optional[str]:
        """Extract audio path from workflow outputs.

        Args:
            outputs: Workflow output dict

        Returns:
            Audio path or None
        """
        # Look for SaveAudio node output
        for node_id, output in outputs.items():
            if isinstance(output, dict):
                if "audio" in output:
                    audio = output["audio"]
                    if audio and isinstance(audio, list):
                        return audio[0].get("filename") if isinstance(audio[0], dict) else str(audio[0])
        return None


# ============================================================================
# Simple Interface
# ============================================================================


def generate_novel_multimedia(
    chapter_outline: str,
    characters: dict[str, Any],
    context: dict[str, Any],
    orchestrator: Any = None,
    **kwargs,
) -> dict[str, Any]:
    """Simple interface for generating multimodal novel content.

    Args:
        chapter_outline: Scene outline
        characters: Character profiles
        context: Generation context
        orchestrator: Optional NovelOrchestrator instance
        **kwargs: Additional config (comfy_path, models_dir, etc.)

    Returns:
        Dict with content, images, and audio
    """
    flow = NovelMultimodalFlow(config=kwargs)

    result = flow.kickoff({
        "chapter_outline": chapter_outline,
        "characters": characters,
        "context": context,
        "orchestrator": orchestrator,
    })

    return result
