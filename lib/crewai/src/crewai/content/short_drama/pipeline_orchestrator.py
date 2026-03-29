"""Short Drama Pipeline Orchestrator.

Orchestrates the full short drama pipeline:
    bible → outline → shots → prompts → video → TTS → assemble

Supports:
- Parallel video generation (configurable concurrency)
- Parallel TTS generation
- Resume from checkpoint (断点续传)
- Progress tracking

Usage:
    orchestrator = ShortDramaPipelineOrchestrator(
        project_name="仙侠史诗",
        project_dir="./仙侠史诗_short_drama",
    )

    # Run full pipeline for episode 1
    result = await orchestrator.run_full_pipeline(episode=1)

    # Run from novel
    result = await orchestrator.run_full_pipeline(
        episode=1,
        from_novel="./仙侠史诗_novel",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.crews.episode_outline_crew import EpisodeOutlineCrew
from crewai.content.short_drama.crews.shot_crew import ShotCrew
from crewai.content.short_drama.short_drama_types import (
    EpisodeOutline,
    ShortDramaBible,
    ShortDramaEpisode,
    Shot,
)
from crewai.content.short_drama.video.base import VideoGenerationResult
from crewai.content.short_drama.video.ffmpeg_assembler import FFmpegAssembler
from crewai.content.short_drama.video.tts.base import TTSProviderProtocol, TTSResult

logger = logging.getLogger(__name__)


# ============================================================================
# Pipeline Result
# ============================================================================


@dataclass
class PipelineResult:
    """Result of a full or partial pipeline run.

    Attributes:
        success: Whether the pipeline completed successfully.
        episode: Episode number that was generated.
        bible: ShortDramaBible that was used.
        episode_outline: Generated EpisodeOutline.
        short_drama_episode: Decomposed ShortDramaEpisode with shots.
        video_segments: List of generated video file paths.
        audio_segments: List of generated audio file paths.
        final_video_path: Path to the assembled final video.
        errors: List of error messages encountered.
        checkpoints: Dict of checkpoint data for resume.
    """
    success: bool = False
    episode: int = 0
    bible: Optional[ShortDramaBible] = None
    episode_outline: Optional[EpisodeOutline] = None
    short_drama_episode: Optional[ShortDramaEpisode] = None
    video_segments: list[str] = field(default_factory=list)
    audio_segments: list[str] = field(default_factory=list)
    final_video_path: Optional[str] = None
    errors: list[str] = field(default_factory=list)
    checkpoints: dict[str, Any] = field(default_factory=dict)

    def add_error(self, error: str) -> None:
        """Record an error."""
        self.errors.append(error)
        logger.error(f"[Pipeline] Error: {error}")

    def to_dict(self) -> dict:
        """Serialize to dict for checkpointing."""
        return {
            "success": self.success,
            "episode": self.episode,
            "video_segments": self.video_segments,
            "audio_segments": self.audio_segments,
            "final_video_path": self.final_video_path,
            "errors": self.errors,
            "checkpoints": self.checkpoints,
        }


# ============================================================================
# Checkpoint Management
# ============================================================================


class PipelineCheckpoint:
    """Manages pipeline state checkpoints for resume capability."""

    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, episode: int, stage: str, data: dict) -> None:
        """Save a checkpoint for an episode at a specific stage."""
        ckpt_file = self.checkpoint_dir / f"episode_{episode:03d}_{stage}.json"
        with open(ckpt_file, "w", encoding="utf-8") as f:
            json.dump({"episode": episode, "stage": stage, "data": data}, f)
        logger.info(f"[Checkpoint] Saved: {ckpt_file.name}")

    def load(self, episode: int, stage: str) -> Optional[dict]:
        """Load a checkpoint if it exists."""
        ckpt_file = self.checkpoint_dir / f"episode_{episode:03d}_{stage}.json"
        if ckpt_file.exists():
            with open(ckpt_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def clear(self, episode: int) -> None:
        """Clear all checkpoints for an episode."""
        for f in self.checkpoint_dir.glob(f"episode_{episode:03d}_*.json"):
            f.unlink()


# ============================================================================
# Main Orchestrator
# ============================================================================


class ShortDramaPipelineOrchestrator:
    """Orchestrates the full short drama generation pipeline.

    Coordinates the following stages:
        1. Bible: Load/build ShortDramaBible
        2. Outline: Generate EpisodeOutline from novel chapter
        3. Shots: Decompose outline into individual Shot objects
        4. Video: Generate video for each shot (parallel)
        5. TTS: Generate voiceover for each shot (parallel)
        6. Assemble: Combine video + audio into final episode video

    Supports parallel execution, checkpointing, and graceful error handling.
    """

    def __init__(
        self,
        project_name: str,
        project_dir: str | Path,
        llm: Optional[Any] = None,  # crewai LLM instance
        video_provider: Optional[Any] = None,  # VideoProviderProtocol
        tts_provider: Optional[Any] = None,  # TTSProviderProtocol
        video_provider_name: str = "minimax",
        tts_provider_name: str = "minimax",
        style: str = "xianxia",
        aspect_ratio: str = "16:9",
        max_parallel: int = 3,
        output_dir: Optional[str] = None,
    ):
        """Initialize the pipeline orchestrator.

        Args:
            project_name: Name of the short drama project.
            project_dir: Path to the project directory.
            llm: CrewAI LLM instance (optional, will try to create from env).
            video_provider: VideoProviderProtocol instance (optional).
            tts_provider: TTSProviderProtocol instance (optional).
            video_provider_name: Name of video provider to use if not provided.
            tts_provider_name: Name of TTS provider if not provided.
            style: Story style (xianxia, doushi, modern, etc.).
            aspect_ratio: Default aspect ratio for video generation.
            max_parallel: Maximum parallel video/TTS generation tasks.
            output_dir: Override output directory.
        """
        self.project_name = project_name
        self.project_dir = Path(project_dir)
        self.style = style
        self.aspect_ratio = aspect_ratio
        self.max_parallel = max_parallel
        self.output_dir = Path(output_dir or self.project_dir / "output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # LLM
        self._llm = llm

        # Providers
        self._video_provider = video_provider
        self._tts_provider = tts_provider
        self.video_provider_name = video_provider_name
        self.tts_provider_name = tts_provider_name

        # Checkpoint
        self.checkpoint = PipelineCheckpoint(self.project_dir / ".checkpoints")

        # Assembler
        self.assembler = FFmpegAssembler()

    # -------------------------------------------------------------------------
    # LLM Access
    # -------------------------------------------------------------------------

    def _get_llm(self) -> Any:
        """Get or create LLM instance."""
        if self._llm is None:
            from crewai.cli.short_drama._llm import create_llm_from_env

            llm = create_llm_from_env()
            if llm is None:
                raise RuntimeError(
                    "No LLM configured. Set MINIMAX_API_KEY or DEEPSEEK_API_KEY."
                )
            self._llm = llm
        return self._llm

    # -------------------------------------------------------------------------
    # Provider Access
    # -------------------------------------------------------------------------

    def _get_video_provider(self) -> Any:
        """Get or create video provider."""
        if self._video_provider is None:
            from crewai.content.short_drama.video.factory import create_video_provider

            self._video_provider = create_video_provider(self.video_provider_name)
        return self._video_provider

    def _get_tts_provider(self) -> TTSProviderProtocol:
        """Get or create TTS provider."""
        if self._tts_provider is None:
            from crewai.content.short_drama.video.tts.factory import create_tts_provider

            self._tts_provider = create_tts_provider(self.tts_provider_name)
        return self._tts_provider

    # -------------------------------------------------------------------------
    # Pipeline Stages
    # -------------------------------------------------------------------------

    async def step_bible(
        self,
        episode: int,
        from_novel: Optional[str] = None,
        chapter: Optional[int] = None,
    ) -> ShortDramaBible:
        """Step 1: Load or build the ShortDramaBible.

        Args:
            episode: Episode number.
            from_novel: Path to novel project (optional).
            chapter: Source chapter number (defaults to episode).

        Returns:
            ShortDramaBible instance.
        """
        logger.info(f"[Pipeline:Step1] Building bible for episode {episode}")

        # Check for checkpoint
        ckpt = self.checkpoint.load(episode, "bible")
        if ckpt:
            logger.info(f"[Pipeline:Step1] Resuming from checkpoint")
            return self._bible_from_dict(ckpt["data"])

        # Try to load from project directory
        bible_file = self.project_dir / "short_drama_bible.json"
        if bible_file.exists():
            with open(bible_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            bible = self._bible_from_dict(data)
            logger.info(f"[Pipeline:Step1] Loaded existing bible: {bible_file}")
            self.checkpoint.save(episode, "bible", data)
            return bible

        # Build from novel
        if from_novel:
            novel_path = Path(from_novel)
        else:
            novel_path = self.project_dir.parent / f"{self.project_name}_novel"

        if not novel_path.exists():
            raise FileNotFoundError(f"Novel project not found: {novel_path}")

        adapter = NovelToShortDramaAdapter(novel_path)
        adapter.load_pipeline_state()
        production_bible = adapter.get_production_bible()

        if not production_bible:
            raise RuntimeError("Could not load ProductionBible from novel")

        chapter_num = chapter if chapter is not None else episode
        try:
            chapter_text = adapter.get_chapter_text(chapter_num)
        except FileNotFoundError:
            chapter_text = ""

        builder = ShortDramaBibleBuilder(style=self.style)
        bible = builder.build(
            bible=production_bible,
            episode_num=episode,
            series_title=self.project_name,
            episode_context=chapter_text[:500],
        )

        # Save bible
        bible_file = self.project_dir / "short_drama_bible.json"
        with open(bible_file, "w", encoding="utf-8") as f:
            json.dump(bible.to_dict(), f, ensure_ascii=False, indent=2)

        bible_data = bible.to_dict()
        self.checkpoint.save(episode, "bible", bible_data)
        logger.info(f"[Pipeline:Step1] Bible saved to {bible_file}")

        return bible

    def _bible_from_dict(self, data: dict) -> ShortDramaBible:
        """Reconstruct ShortDramaBible from dict."""
        from crewai.content.novel.production_bible.bible_types import (
            CharacterProfile,
        )

        characters = {}
        for name, char_data in data.get("relevant_characters", {}).items():
            characters[name] = CharacterProfile(**char_data)

        return ShortDramaBible(
            episode_num=data["episode_num"],
            series_title=data["series_title"],
            relevant_characters=characters,
            world_rules_summary=data.get("world_rules_summary", ""),
            episode_context=data.get("episode_context", ""),
            visual_style=data.get("visual_style", ""),
            tone=data.get("tone", ""),
        )

    async def step_outline(
        self,
        episode: int,
        bible: ShortDramaBible,
        from_novel: Optional[str] = None,
        chapter: Optional[int] = None,
    ) -> EpisodeOutline:
        """Step 2: Generate episode outline.

        Args:
            episode: Episode number.
            bible: ShortDramaBible.
            from_novel: Path to novel project.
            chapter: Source chapter number.

        Returns:
            EpisodeOutline instance.
        """
        logger.info(f"[Pipeline:Step2] Generating outline for episode {episode}")

        # Check checkpoint
        ckpt = self.checkpoint.load(episode, "outline")
        if ckpt:
            logger.info("[Pipeline:Step2] Resuming from checkpoint")
            return self._outline_from_dict(ckpt["data"])

        # Load chapter text
        if from_novel:
            novel_path = Path(from_novel)
        else:
            novel_path = self.project_dir.parent / f"{self.project_name}_novel"

        chapter_num = chapter if chapter is not None else episode

        try:
            adapter = NovelToShortDramaAdapter(novel_path)
            adapter.load_pipeline_state()
            chapter_text = adapter.get_chapter_text(chapter_num)
        except (FileNotFoundError, AttributeError):
            chapter_text = ""

        # Generate outline using crew
        crew = EpisodeOutlineCrew(config={"llm": self._get_llm()}, verbose=False)

        episode_outline = crew.generate_outline(
            chapter_text=chapter_text,
            bible=bible,
            episode_num=episode,
            series_title=self.project_name,
            episode_context=bible.episode_context,
        )

        # Save outline
        outline_file = self.project_dir / f"episode_{episode:03d}_outline.json"
        with open(outline_file, "w", encoding="utf-8") as f:
            json.dump(episode_outline.to_dict(), f, ensure_ascii=False, indent=2)

        outline_data = episode_outline.to_dict()
        self.checkpoint.save(episode, "outline", outline_data)
        logger.info(f"[Pipeline:Step2] Outline saved to {outline_file}")

        return episode_outline

    def _outline_from_dict(self, data: dict) -> EpisodeOutline:
        """Reconstruct EpisodeOutline from dict."""
        return EpisodeOutline(
            episode_num=data["episode_num"],
            title=data["title"],
            episode_summary=data["episode_summary"],
            scene_plan=data.get("scene_plan", []),
        )

    async def step_shots(
        self,
        episode: int,
        outline: EpisodeOutline,
        bible: ShortDramaBible,
    ) -> ShortDramaEpisode:
        """Step 3: Decompose outline into shots.

        Args:
            episode: Episode number.
            outline: EpisodeOutline.
            bible: ShortDramaBible.

        Returns:
            ShortDramaEpisode with decomposed shots.
        """
        logger.info(f"[Pipeline:Step3] Decomposing episode {episode} into shots")

        # Check checkpoint
        ckpt = self.checkpoint.load(episode, "shots")
        if ckpt:
            logger.info("[Pipeline:Step3] Resuming from checkpoint")
            return self._episode_from_dict(ckpt["data"])

        # Decompose using shot crew
        crew = ShotCrew(config={"llm": self._get_llm()}, verbose=False)
        short_drama_episode = crew.decompose_episode(outline, bible)

        # Save episode
        episode_file = self.project_dir / f"episode_{episode:03d}.json"
        with open(episode_file, "w", encoding="utf-8") as f:
            json.dump(short_drama_episode.to_dict(), f, ensure_ascii=False, indent=2)

        episode_data = short_drama_episode.to_dict()
        self.checkpoint.save(episode, "shots", episode_data)
        logger.info(f"[Pipeline:Step3] Episode saved to {episode_file}")

        return short_drama_episode

    def _episode_from_dict(self, data: dict) -> ShortDramaEpisode:
        """Reconstruct ShortDramaEpisode from dict."""
        from crewai.content.short_drama.short_drama_types import (
            ShortDramaScene,
            Shot,
        )

        scenes = []
        for scene_data in data.get("scenes", []):
            shots = [Shot(**s) for s in scene_data.get("shots", [])]
            scene = ShortDramaScene(
                scene_number=scene_data["scene_number"],
                location=scene_data["location"],
                time_of_day=scene_data["time_of_day"],
                description=scene_data["description"],
                shots=shots,
                voiceover=scene_data.get("voiceover", ""),
            )
            scenes.append(scene)

        return ShortDramaEpisode(
            episode_num=data["episode_num"],
            title=data["title"],
            summary=data["summary"],
            scenes=scenes,
            voiceover_intro=data.get("voiceover_intro", ""),
            voiceover_outro=data.get("voiceover_outro", ""),
            episode_context=data.get("episode_context", ""),
        )

    async def step_generate_videos(
        self,
        episode: int,
        episode_obj: ShortDramaEpisode,
        max_parallel: int = 3,
    ) -> list[str]:
        """Step 4: Generate videos for all shots (parallel).

        Args:
            episode: Episode number.
            episode_obj: ShortDramaEpisode with shots.
            max_parallel: Maximum parallel generation tasks.

        Returns:
            List of generated video file paths.
        """
        logger.info(
            f"[Pipeline:Step4] Generating videos for episode {episode} "
            f"(max_parallel={max_parallel})"
        )

        # Check checkpoint for already-generated videos
        ckpt = self.checkpoint.load(episode, "videos")
        if ckpt:
            existing = ckpt["data"].get("video_segments", [])
            completed_shots = ckpt["data"].get("completed_shots", [])
            logger.info(f"[Pipeline:Step4] Resuming: {len(existing)} videos done")
        else:
            existing = []
            completed_shots = []

        provider = self._get_video_provider()
        video_dir = self.output_dir / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)

        all_shots = episode_obj.get_all_shots()
        tasks = []

        for shot in all_shots:
            if shot.shot_number in completed_shots:
                # Already done, check file exists
                fname = f"episode_{episode:03d}_shot_{shot.shot_number:03d}.mp4"
                fpath = video_dir / fname
                if fpath.exists():
                    existing.append(str(fpath))
                else:
                    logger.warning(
                        f"[Pipeline:Step4] Shot {shot.shot_number} in checkpoint "
                        f"but file missing: {fpath}"
                    )
                continue

            # Generate this shot (pair with shot for correct indexing)
            tasks.append((shot, self._generate_single_video(
                provider, episode, shot, video_dir
            )))

        if not tasks:
            logger.info("[Pipeline:Step4] All videos already generated")
            return existing

        # Run in parallel batches
        semaphore = asyncio.Semaphore(max_parallel)

        async def bounded_generate(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_generate(t) for t in tasks],
            return_exceptions=True,
        )

        video_segments = list(existing)
        newly_completed = []

        for (shot, result) in tasks:
            if isinstance(result, Exception):
                logger.error(f"[Pipeline:Step4] Shot {shot.shot_number} generation failed: {result}")
                continue

            if result and result.is_success and result.video_path:
                video_segments.append(result.video_path)
                newly_completed.append(shot.shot_number)

        # Save checkpoint
        self.checkpoint.save(
            episode,
            "videos",
            {
                "video_segments": video_segments,
                "completed_shots": completed_shots + newly_completed,
            },
        )

        logger.info(f"[Pipeline:Step4] Generated {len(newly_completed)} new videos")
        return video_segments

    async def _generate_single_video(
        self,
        provider: Any,
        episode: int,
        shot: Shot,
        video_dir: Path,
    ) -> VideoGenerationResult:
        """Generate a single video for one shot."""
        fname = f"episode_{episode:03d}_shot_{shot.shot_number:03d}.mp4"
        output_path = video_dir / fname

        try:
            # Submit generation
            result = await provider.generate(
                prompt=shot.video_prompt,
                duration=int(shot.duration_seconds),
                aspect_ratio=self.aspect_ratio,
            )

            if result.status == "failed":
                logger.error(
                    f"[Pipeline:Step4] Shot {shot.shot_number} failed: {result.error}"
                )
                return result

            # Wait for completion
            completed = await provider.wait(result.task_id)

            if completed.is_success:
                # Download
                local_path = await provider.download(completed, str(output_path))
                return VideoGenerationResult(
                    task_id=result.task_id,
                    status="completed",
                    video_url=completed.video_url,
                    video_path=local_path,
                    duration_seconds=shot.duration_seconds,
                )
            else:
                return completed

        except Exception as e:
            logger.error(f"[Pipeline:Step4] Shot {shot.shot_number} error: {e}")
            return VideoGenerationResult(
                task_id="",
                status="failed",
                error=str(e),
            )

    async def step_generate_tts(
        self,
        episode: int,
        episode_obj: ShortDramaEpisode,
        max_parallel: int = 3,
    ) -> list[str]:
        """Step 5: Generate TTS voiceover for all shots (parallel).

        Args:
            episode: Episode number.
            episode_obj: ShortDramaEpisode with shots.
            max_parallel: Maximum parallel synthesis tasks.

        Returns:
            List of generated audio file paths.
        """
        logger.info(
            f"[Pipeline:Step5] Generating TTS for episode {episode} "
            f"(max_parallel={max_parallel})"
        )

        # Check checkpoint
        ckpt = self.checkpoint.load(episode, "tts")
        if ckpt:
            existing = ckpt["data"].get("audio_segments", [])
            completed_shots = ckpt["data"].get("completed_shots", [])
            logger.info(f"[Pipeline:Step5] Resuming: {len(existing)} audio done")
        else:
            existing = []
            completed_shots = []

        provider = self._get_tts_provider()
        audio_dir = self.output_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        all_shots = episode_obj.get_all_shots()
        tasks = []

        for shot in all_shots:
            if shot.shot_number in completed_shots:
                fname = f"episode_{episode:03d}_shot_{shot.shot_number:03d}.mp3"
                fpath = audio_dir / fname
                if fpath.exists():
                    existing.append(str(fpath))
                continue

            if shot.voiceover_segment:
                tasks.append(
                    self._synthesize_single_tts(
                        provider, episode, shot, audio_dir
                    )
                )

        if not tasks:
            logger.info("[Pipeline:Step5] No TTS needed or all done")
            return existing

        # Run in parallel
        semaphore = asyncio.Semaphore(max_parallel)

        async def bounded_synth(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[bounded_synth(t) for t in tasks],
            return_exceptions=True,
        )

        audio_segments = list(existing)
        newly_completed = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"[Pipeline:Step5] TTS synthesis failed: {result}")
                continue

            if result and result.is_success and result.audio_path:
                audio_segments.append(result.audio_path)
                newly_completed.append(int(result.task_id))  # task_id = shot_number (int)

        self.checkpoint.save(
            episode,
            "tts",
            {
                "audio_segments": audio_segments,
                "completed_shots": completed_shots + newly_completed,
            },
        )

        logger.info(f"[Pipeline:Step5] Generated {len(newly_completed)} audio segments")
        return audio_segments

    async def _synthesize_single_tts(
        self,
        provider: TTSProviderProtocol,
        episode: int,
        shot: Shot,
        audio_dir: Path,
    ) -> TTSResult:
        """Synthesize TTS for one shot."""
        fname = f"episode_{episode:03d}_shot_{shot.shot_number:03d}.mp3"
        output_path = audio_dir / fname

        try:
            result = await provider.synthesize(
                text=shot.voiceover_segment,
                voice_id="female-shaonv",
                speed=1.0,
            )

            if result.is_success:
                local_path = await provider.download(result, str(output_path))
                # Embed shot number in task_id for tracking
                result.task_id = str(shot.shot_number)
                result.audio_path = local_path
                return result
            else:
                result.task_id = str(shot.shot_number)
                return result

        except Exception as e:
            logger.error(f"[Pipeline:Step5] Shot {shot.shot_number} TTS error: {e}")
            return TTSResult(
                task_id=str(shot.shot_number),
                status="failed",
                error=str(e),
            )

    async def step_assemble(
        self,
        episode: int,
        episode_obj: ShortDramaEpisode,
        video_segments: list[str],
        audio_segments: list[str],
    ) -> str:
        """Step 6: Assemble final video from segments.

        Args:
            episode: Episode number.
            episode_obj: ShortDramaEpisode.
            video_segments: List of video file paths.
            audio_segments: List of audio file paths.

        Returns:
            Path to the assembled final video.
        """
        logger.info(f"[Pipeline:Step6] Assembling episode {episode}")

        # Build audio list for mixer
        audio_files = []
        for audio_path in audio_segments:
            audio_files.append({
                "file": audio_path,
                "volume": 1.0,
                "start": 0,
            })

        # Determine output path
        output_path = self.output_dir / f"episode_{episode:03d}_final.mp4"

        # Concatenate videos
        success = self.assembler.concat_videos(
            video_files=video_segments,
            output_file=str(output_path),
        )

        if not success:
            raise RuntimeError("Video concatenation failed")

        # Mix audio if we have it
        if audio_files:
            temp_output = self.output_dir / f"episode_{episode:03d}_with_audio.mp4"
            audio_success = self.assembler.mix_audio(
                video_file=str(output_path),
                audio_files=audio_files,
                output_file=str(temp_output),
            )
            if audio_success:
                output_path = temp_output

        logger.info(f"[Pipeline:Step6] Final video: {output_path}")
        self.checkpoint.save(episode, "final", {"final_video_path": str(output_path)})

        return str(output_path)

    # -------------------------------------------------------------------------
    # Full Pipeline
    # -------------------------------------------------------------------------

    async def run_full_pipeline(
        self,
        episode: int = 1,
        chapter: int | None = None,
        from_novel: str | None = None,
        max_parallel: int | None = None,
        skip_video: bool = False,
        skip_tts: bool = False,
        skip_assemble: bool = False,
        resume: bool = True,
    ) -> PipelineResult:
        """Run the full short drama pipeline for one episode.

        Pipeline stages:
            1. Bible → 2. Outline → 3. Shots → 4. Videos → 5. TTS → 6. Assemble

        Args:
            episode: Episode number to generate.
            chapter: Source chapter number (defaults to episode).
            from_novel: Path to novel project.
            max_parallel: Override max parallel tasks.
            skip_video: Skip video generation stage.
            skip_tts: Skip TTS generation stage.
            skip_assemble: Skip final assembly stage.
            resume: Whether to resume from checkpoints.

        Returns:
            PipelineResult with all generated artifacts.
        """
        max_parallel = max_parallel or self.max_parallel
        result = PipelineResult(episode=episode)

        logger.info(
            f"[Pipeline] Starting full pipeline: episode={episode}, "
            f"max_parallel={max_parallel}"
        )

        try:
            # Stage 1: Bible
            bible = await self.step_bible(episode, from_novel, chapter)
            result.bible = bible

            # Stage 2: Outline
            outline = await self.step_outline(episode, bible, from_novel, chapter)
            result.episode_outline = outline

            # Stage 3: Shots
            episode_obj = await self.step_shots(episode, outline, bible)
            result.short_drama_episode = episode_obj

            # Stage 4: Videos (optional)
            if skip_video:
                logger.info("[Pipeline] Skipping video generation")
            else:
                video_segments = await self.step_generate_videos(
                    episode, episode_obj, max_parallel
                )
                result.video_segments = video_segments

            # Stage 5: TTS (optional)
            if skip_tts:
                logger.info("[Pipeline] Skipping TTS generation")
            else:
                audio_segments = await self.step_generate_tts(
                    episode, episode_obj, max_parallel
                )
                result.audio_segments = audio_segments

            # Stage 6: Assemble (optional)
            if skip_assemble:
                logger.info("[Pipeline] Skipping assembly")
            else:
                final_path = await self.step_assemble(
                    episode,
                    episode_obj,
                    result.video_segments,
                    result.audio_segments,
                )
                result.final_video_path = final_path

            result.success = True
            logger.info(f"[Pipeline] ✅ Pipeline complete for episode {episode}")

        except Exception as e:
            logger.exception(f"[Pipeline] ❌ Pipeline failed: {e}")
            result.add_error(str(e))

        return result


__all__ = [
    "ShortDramaPipelineOrchestrator",
    "PipelineResult",
    "PipelineCheckpoint",
]
