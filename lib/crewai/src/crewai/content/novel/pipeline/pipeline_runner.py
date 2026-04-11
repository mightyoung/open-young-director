"""PipelineRunner — lightweight state-machine orchestrator for novel generation.

Executes all pipeline stages in sequence, supporting:
  - Fresh runs (no existing state)
  - Resuming from a named stage (``resume_from``)
  - Explicit state-file paths (``state_path``)
  - Automatic output-directory scaffolding

No crewAI dependency; pure Python + stdlib + httpx (via DeepSeekClient).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import ClassVar

from crewai.content.novel.pipeline_state import PipelineState
from crewai.llm.deepseek_client import DeepSeekClient
from crewai.content.novel.pipeline.stage_runner import StageRunner

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy stage imports — kept here to avoid circular imports and to make the
# module importable even when individual stage files are still being authored.
# ---------------------------------------------------------------------------

def _import_stages() -> dict[str, type[StageRunner]]:
    """Return a mapping of stage-name → StageRunner subclass.

    Imports are deferred so that the module can be imported (e.g. for testing
    PipelineRunner in isolation) without triggering heavy upstream imports.
    """
    from crewai.content.novel.pipeline.evaluate_stage import EvaluateStage
    from crewai.content.novel.pipeline.review_stage import ReviewStage

    # WorldStage, OutlineStage, VolumeStage, SummaryStage, WritingStage are
    # expected to live alongside this file.  Imported lazily so that partially-
    # implemented stages do not break the runner.
    try:
        from crewai.content.novel.pipeline.world_stage import WorldStage  # type: ignore[import]
    except ImportError:
        WorldStage = None  # type: ignore[assignment,misc]

    try:
        from crewai.content.novel.pipeline.outline_stage import OutlineStage  # type: ignore[import]
    except ImportError:
        OutlineStage = None  # type: ignore[assignment,misc]

    try:
        from crewai.content.novel.pipeline.volume_stage import VolumeStage  # type: ignore[import]
    except ImportError:
        VolumeStage = None  # type: ignore[assignment,misc]

    try:
        from crewai.content.novel.pipeline.summary_stage import SummaryStage  # type: ignore[import]
    except ImportError:
        SummaryStage = None  # type: ignore[assignment,misc]

    try:
        from crewai.content.novel.pipeline.writing_stage import WritingStage  # type: ignore[import]
    except ImportError:
        WritingStage = None  # type: ignore[assignment,misc]

    mapping: dict[str, type[StageRunner] | None] = {
        "world": WorldStage,
        "outline": OutlineStage,
        "evaluate": EvaluateStage,
        "volume": VolumeStage,
        "summary": SummaryStage,
        "writing": WritingStage,
        "review": ReviewStage,
    }
    return mapping  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PipelineRunner
# ---------------------------------------------------------------------------

@dataclass
class PipelineRunner:
    """Lightweight state-machine pipeline runner.

    Attributes:
        config: Novel configuration dictionary.  Keys understood:
            - ``topic``, ``style``, ``genre``: narrative parameters
            - ``words_per_chapter_target``: target chapter length (default 5000)
            - ``state_path``: override for the state-file location
        llm: Shared :class:`~crewai.llm.deepseek_client.DeepSeekClient`.
        output_dir: Root output directory (default ``"output"``).
    """

    #: Ordered stage names.  ClassVar so dataclass does not treat it as a field.
    STAGES: ClassVar[tuple[str, ...]] = (
        "world",
        "outline",
        "evaluate",
        "volume",
        "summary",
        "writing",
        "review",
    )

    config: dict
    llm: DeepSeekClient
    output_dir: str = "output"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        resume_from: str | None = None,
        state_path: str | None = None,
    ) -> PipelineState:
        """Run the full pipeline (or resume from a stage).

        Args:
            resume_from: Name of the stage to start from.  If ``None`` the
                pipeline starts at the beginning (``"world"``).  Must be one
                of ``PipelineRunner.STAGES``.
            state_path: Path to the JSON state file.  When ``None`` the path
                defaults to ``{output_dir}/state/pipeline_state.json``.

        Returns:
            Final :class:`~crewai.content.novel.pipeline_state.PipelineState`.

        Raises:
            ValueError: If ``resume_from`` is not a recognised stage name, or
                if a stage's ``validate_input`` check fails.
        """
        self._ensure_output_dirs()

        resolved_state_path = state_path or self._default_state_path()

        # 1. Load or create state
        state = self._load_or_create_state(resolved_state_path)

        # Stamp config snapshot and canonical state_path into state.
        state.config = dict(self.config)
        state.config["state_path"] = resolved_state_path
        state.config.setdefault("output_dir", self.output_dir)

        # 2. Determine start stage
        start_idx = self._resolve_start_index(resume_from)

        stage_map = _import_stages()

        # 3. Execute stages sequentially
        for stage_name in self.STAGES[start_idx:]:
            logger.info("=== Starting stage: %s ===", stage_name)

            stage_cls = stage_map.get(stage_name)
            if stage_cls is None:
                logger.warning(
                    "Stage %r is not yet implemented — skipping.", stage_name
                )
                continue

            stage = self._create_stage(stage_name, stage_cls)

            if not stage.validate_input(state):
                raise ValueError(
                    f"Stage {stage_name!r} prerequisites not met. "
                    f"Current pipeline state: {state!r}"
                )

            try:
                state = stage.run(state)
            except Exception as exc:
                logger.exception("Stage %r raised an exception: %s", stage_name, exc)
                # Persist partial state before re-raising so the user can inspect it.
                state.current_stage = f"{stage_name}:failed"
                state.save(resolved_state_path)
                raise

            state.current_stage = stage_name
            state.save(resolved_state_path)
            logger.info("=== Stage %s complete ===", stage_name)

        return state

    # ------------------------------------------------------------------
    # Directory scaffolding
    # ------------------------------------------------------------------

    def _ensure_output_dirs(self) -> None:
        """Create ``{output_dir}/chapters/`` and ``{output_dir}/state/`` if absent."""
        for subdir in ("chapters", "state"):
            path = os.path.join(self.output_dir, subdir)
            os.makedirs(path, exist_ok=True)
            logger.debug("Ensured output directory exists: %s", path)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _default_state_path(self) -> str:
        """Return the default path for the pipeline-state JSON file."""
        return os.path.join(self.output_dir, "state", "pipeline_state.json")

    def _load_or_create_state(self, state_path: str) -> PipelineState:
        """Load an existing state from *state_path*, or create a fresh one.

        Args:
            state_path: Absolute or relative path to the JSON state file.

        Returns:
            A :class:`~crewai.content.novel.pipeline_state.PipelineState`
            instance — either loaded from disk or freshly initialised.
        """
        if os.path.exists(state_path):
            try:
                state = PipelineState.load(state_path)
                logger.info("Loaded existing pipeline state from %s", state_path)
                return state
            except Exception as exc:
                logger.warning(
                    "Failed to load state from %s (%s); starting fresh.", state_path, exc
                )

        logger.info("Creating fresh pipeline state (no existing state at %s)", state_path)
        return PipelineState()

    # ------------------------------------------------------------------
    # Stage creation
    # ------------------------------------------------------------------

    def _resolve_start_index(self, resume_from: str | None) -> int:
        """Translate a stage name (or ``None``) into a STAGES index.

        Args:
            resume_from: Stage name to resume from, or ``None`` to start fresh.

        Returns:
            Index into ``self.STAGES``.

        Raises:
            ValueError: If ``resume_from`` is not in ``self.STAGES``.
        """
        if resume_from is None:
            return 0

        stages_list = list(self.STAGES)
        if resume_from not in stages_list:
            raise ValueError(
                f"Unknown resume_from stage: {resume_from!r}. "
                f"Valid stages: {stages_list}"
            )

        idx = stages_list.index(resume_from)
        logger.info("Resuming from stage: %s (index %d)", resume_from, idx)
        return idx

    def _create_stage(self, name: str, cls: type[StageRunner]) -> StageRunner:
        """Instantiate a stage runner.

        Args:
            name: Stage name (used as the ``name`` field on the stage).
            cls: Concrete :class:`StageRunner` subclass to instantiate.

        Returns:
            Instantiated stage runner with the shared LLM client.
        """
        return cls(name=name, llm=self.llm)
