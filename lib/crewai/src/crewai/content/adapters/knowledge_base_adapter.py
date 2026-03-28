"""KnowledgeBase Adapter - Wraps NovelOrchestrator for crewai integration.

This adapter allows crewai's content generation pipeline to use
knowledge_base's NovelOrchestrator without modifying knowledge_base itself.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM

from .llm_adapter import LLMClientAdapter
from .data_converters import (
    convert_world_data_to_world_context,
    convert_chapter_outline,
    convert_character_profiles_to_bibles,
    convert_chapter_memory_to_summary,
    convert_novel_output,
)

logger = logging.getLogger(__name__)


@dataclass
class NovelOrchestratorAdapterConfig:
    """Configuration for the KnowledgeBase adapter."""
    max_subagent_concurrent: int = 5
    max_concurrent_scenes: int = 3
    enable_verification: bool = True
    enable_evolution: bool = True  # Enable outline evolution (closed-loop feedback)
    max_retry: int = 2
    max_verification_retries: int = 3
    project_dir: str = "./novels"
    use_knowledge_base_storage: bool = False  # If True, use KB's ChapterManager
    mode: str = "FILM_DRAMA"  # Orchestration mode
    enable_npc_simulation: bool = False  # Enable NPC simulation
    enable_reality_checker: bool = False  # Enable reality checker
    reality_checker_config: Optional[Dict[str, Any]] = None  # Reality checker config


class KnowledgeBaseAdapter:
    """Adapter that wraps knowledge_base's NovelOrchestrator for crewai.

    This class provides a bridge between crewai's content generation pipeline
    and knowledge_base's NovelOrchestrator, allowing both systems to work together
    without modifying knowledge_base.

    Usage:
        adapter = KnowledgeBaseAdapter(
            llm=crewai_llm,
            config=NovelOrchestratorAdapterConfig()
        )
        draft, chapter_memory = adapter.generate_chapter(
            chapter=1,
            chapter_outline=chapter_outline,
            world_data=world_data,
            character_profiles=character_profiles,
        )
    """

    def __init__(
        self,
        llm: "LLM",
        config: Optional[NovelOrchestratorAdapterConfig] = None,
    ):
        """Initialize the adapter.

        Args:
            llm: crewai LLM instance
            config: Optional adapter configuration
        """
        self._llm = llm
        self._config = config or NovelOrchestratorAdapterConfig()

        # Create the LLM adapter for knowledge_base
        self._kb_llm = LLMClientAdapter(llm)

        # Lazy-loaded NovelOrchestrator instance
        self._orchestrator = None

        # Track chapter memory for cross-chapter continuity
        self._chapter_memory = None

    def _get_orchestrator(self):
        """Get or create the NovelOrchestrator instance (lazy loading)."""
        if self._orchestrator is None:
            from knowledge_base.agents.novel_orchestrator import (
                NovelOrchestrator,
                OrchestratorConfig,
            )

            kb_config = OrchestratorConfig(
                max_subagent_concurrent=self._config.max_subagent_concurrent,
                max_concurrent_scenes=self._config.max_concurrent_scenes,
                enable_verification=self._config.enable_verification,
                enable_evolution=self._config.enable_evolution,
                max_retry=self._config.max_retry,
                max_verification_retries=self._config.max_verification_retries,
                mode=self._config.mode,
                enable_npc_simulation=self._config.enable_npc_simulation,
                enable_reality_checker=self._config.enable_reality_checker,
                reality_checker_config=self._config.reality_checker_config,
            )

            self._orchestrator = NovelOrchestrator(
                llm_client=self._kb_llm,
                config=kb_config,
            )

        return self._orchestrator

    def generate_chapter(
        self,
        chapter: int,
        chapter_outline: Dict[str, Any],
        world_data: Dict[str, Any],
        character_profiles: Dict[str, str],
        previous_summary: Optional[str] = None,
        bible_section: Any = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Generate a chapter using knowledge_base's NovelOrchestrator.

        This uses orchestrate_chapter() which handles FILM_DRAMA mode properly.

        Args:
            chapter: Chapter number
            chapter_outline: Chapter outline dict from PlotAgent
            world_data: World data from WorldCrew
            character_profiles: Character profiles dict
            previous_summary: Optional previous chapters summary
            bible_section: Optional BibleSection for Production Bible constraints

        Returns:
            tuple: (generated_draft, memory_dict)
                - generated_draft: The chapter content as string
                - memory_dict: Dict representation of ChapterMemory for next chapter
        """
        orchestrator = self._get_orchestrator()

        # Convert data formats
        world_context = convert_world_data_to_world_context(world_data)
        kb_outline = convert_chapter_outline(chapter_outline, chapter)
        cast = convert_character_profiles_to_bibles(character_profiles, world_data)

        # Check if there's an evolved outline for this chapter from previous evolution
        # The evolved outline is stored in the previous chapter's memory under outline_versions[chapter]
        evolved_outline = self._get_evolved_outline_for_chapter(chapter)
        if evolved_outline is not None:
            logger.info(f"Using evolved outline for chapter {chapter} (version {evolved_outline.version})")
            kb_outline = evolved_outline

        # Build context for orchestrator
        context = {
            "characters": character_profiles,
            "location": world_data.get("name", "太虚宗"),
            "time_of_day": "morning",
            "previous_summary": previous_summary or "",
        }

        # Use orchestrate_chapter (synchronous, handles FILM_DRAMA properly)
        result = orchestrator.orchestrate_chapter(
            chapter_number=chapter,
            chapter_outline=str(kb_outline),
            context=context,
            bible_section=bible_section,
        )

        # Extract content from result
        draft = result.get("content", "")

        # Update chapter memory for next chapter
        memory_dict = self._update_memory(orchestrator, chapter)

        return draft, memory_dict

    async def _generate_async(
        self,
        orchestrator,
        chapter: int,
        kb_outline: Any,
        world_context: Any,
        available_characters: List[str],
    ) -> str:
        """Async wrapper for orchestrator.setup() and orchestrator.generate().

        Args:
            orchestrator: NovelOrchestrator instance
            chapter: Chapter number
            kb_outline: Converted chapter outline
            world_context: Converted world context
            available_characters: List of character names

        Returns:
            Generated chapter draft

        Raises:
            RuntimeError: If chapter generation fails after retries
        """
        try:
            # Setup chapter context
            context = await orchestrator.setup(
                chapter=chapter,
                outline=kb_outline,
                world_context=world_context,
                available_characters=available_characters,
            )

            # Set previous chapter memory if available
            if self._chapter_memory:
                from knowledge_base.agents.data_structures import ChapterMemory
                context.prev_chapter_state = ChapterMemory.from_dict(self._chapter_memory)

            # Generate chapter
            project_dir = Path(self._config.project_dir)
            draft = await orchestrator.generate(
                chapter_context=context,
                available_characters=available_characters,
                project_dir=project_dir,
            )

            return draft
        except Exception as e:
            logger.error(f"Failed to generate chapter {chapter}: {e}")
            raise RuntimeError(f"Chapter {chapter} generation failed: {e}") from e

    def _update_memory(self, orchestrator, chapter: int) -> Dict[str, Any]:
        """Update and return chapter memory for cross-chapter continuity.

        Args:
            orchestrator: NovelOrchestrator instance
            chapter: Current chapter number

        Returns:
            Dict representation of ChapterMemory
        """
        if orchestrator._chapter_memory:
            memory = orchestrator._chapter_memory
            self._chapter_memory = memory.to_dict()
            return self._chapter_memory

        return {
            "chapter": chapter,
            "character_states": {},
            "relationship_states": {},
            "key_events": [],
        }

    def _get_evolved_outline_for_chapter(self, chapter: int) -> Optional[Any]:
        """Get evolved outline for a chapter if it exists in memory.

        Storage scheme:
        - Original outline: outline_versions[chapter]
        - Evolved outline: outline_versions[chapter + 10000]

        Args:
            chapter: Chapter number to get evolved outline for

        Returns:
            Evolved PlotOutline if it exists, None otherwise
        """
        if self._chapter_memory is None:
            return None

        outline_versions = self._chapter_memory.get("outline_versions", {})
        if not outline_versions:
            return None

        # First check for evolved outline at chapter + 10000
        evolved_key = chapter + 10000
        evolved_outline = outline_versions.get(evolved_key)
        if evolved_outline is not None:
            if isinstance(evolved_outline, dict):
                from knowledge_base.agents.data_structures import PlotOutline
                return PlotOutline.from_dict(evolved_outline)
            return evolved_outline

        # Fallback: search for any outline with matching chapter attribute
        for key, outline_data in outline_versions.items():
            if isinstance(outline_data, dict):
                if outline_data.get("chapter") == chapter:
                    from knowledge_base.agents.data_structures import PlotOutline
                    return PlotOutline.from_dict(outline_data)
            elif hasattr(outline_data, "chapter") and outline_data.chapter == chapter:
                return outline_data

        return None

    def generate_chapter_with_memory(
        self,
        chapter: int,
        chapter_outline: Dict[str, Any],
        world_data: Dict[str, Any],
        character_profiles: Dict[str, str],
        bible_section: Any = None,
    ) -> Dict[str, Any]:
        """Generate chapter and return full result with memory.

        This is a convenience method that returns everything needed for
        crewai's chapter output.

        Args:
            chapter: Chapter number
            chapter_outline: Chapter outline dict
            world_data: World data dict
            character_profiles: Character profiles dict
            bible_section: Optional BibleSection with world rules and constraints

        Returns:
            Dict with keys:
                - draft: Chapter content
                - memory: ChapterMemory dict for next chapter
                - output: Dict compatible with crewai ChapterOutput
        """
        draft, memory = self.generate_chapter(
            chapter=chapter,
            chapter_outline=chapter_outline,
            world_data=world_data,
            character_profiles=character_profiles,
            bible_section=bible_section,
        )

        output = convert_novel_output(
            draft=draft,
            chapter_num=chapter,
            title=chapter_outline.get("title", f"第{chapter}章"),
            key_events=chapter_outline.get("main_events", []),
            character_appearances=list(character_profiles.keys()),
        )

        # Add outline version info
        outline_version = memory.get("current_outline_version", 1) if memory else 1
        output["outline_version"] = outline_version

        # Check if evolution was triggered (version > 1 means evolution occurred)
        has_evolution = memory.get("current_outline_version", 1) > 1 if memory else False
        output["evolution_triggered"] = has_evolution

        return {
            "draft": draft,
            "memory": memory,
            "output": output,
        }

    def reset(self) -> None:
        """Reset the adapter state, clearing cached orchestrator and memory."""
        self._orchestrator = None
        self._chapter_memory = None

        # Reset knowledge_base global state
        try:
            from knowledge_base.agents import reset_novel_orchestrator
            reset_novel_orchestrator()
        except Exception as e:
            logger.warning(f"Failed to reset knowledge_base orchestrator: {e}")

    # ─── Artifact Persistence (Phase B3) ───────────────────────────────────────

    def save_artifact(
        self,
        project_id: str,
        chapter_num: int,
        phase: str,
        content: Any,
    ) -> None:
        """Persist a chapter artifact to disk for crash recovery.

        Artifacts are stored under:
            {project_dir}/{project_id}/artifacts/chapter_{n}_{phase}.json

        Args:
            project_id: Unique project identifier (used in path)
            chapter_num: Chapter number
            phase: One of 'outline', 'draft', 'critique', 'revised', 'polished'
            content: The artifact content (must be JSON-serializable)
        """
        import json

        artifact_dir = Path(self._config.project_dir) / project_id / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = artifact_dir / f"chapter_{chapter_num}_{phase}.json"
        payload = {
            "project_id": project_id,
            "chapter": chapter_num,
            "phase": phase,
            "content": content,
        }
        try:
            artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.debug(f"Saved artifact: {artifact_path}")
        except Exception as e:
            logger.warning(f"Failed to save artifact {artifact_path}: {e}")

    def load_artifact(
        self,
        project_id: str,
        chapter_num: int,
        phase: str,
    ) -> Any | None:
        """Load a persisted chapter artifact from disk.

        Args:
            project_id: Unique project identifier
            chapter_num: Chapter number
            phase: Artifact phase

        Returns:
            The artifact content, or None if not found
        """
        import json

        artifact_path = (
            Path(self._config.project_dir) / project_id / "artifacts" / f"chapter_{chapter_num}_{phase}.json"
        )
        if not artifact_path.exists():
            return None

        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            logger.debug(f"Loaded artifact: {artifact_path}")
            return payload.get("content")
        except Exception as e:
            logger.warning(f"Failed to load artifact {artifact_path}: {e}")
            return None

    def has_artifact(self, project_id: str, chapter_num: int, phase: str) -> bool:
        """Check whether a persisted artifact exists on disk."""
        artifact_path = (
            Path(self._config.project_dir) / project_id / "artifacts" / f"chapter_{chapter_num}_{phase}.json"
        )
        return artifact_path.exists()

    def list_artifacts(self, project_id: str, chapter_num: int) -> list[str]:
        """List all artifact phases available for a chapter.

        Returns:
            List of phase names that have persisted artifacts
        """
        artifact_dir = Path(self._config.project_dir) / project_id / "artifacts"
        if not artifact_dir.exists():
            return []

        prefix = f"chapter_{chapter_num}_"
        phases = []
        for f in artifact_dir.iterdir():
            if f.is_file() and f.name.startswith(prefix):
                phases.append(f.name[len(prefix):-5])  # strip prefix and .json
        return phases
