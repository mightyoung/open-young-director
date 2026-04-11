"""ArtifactStore — per-chapter artifact persistence.

Saves and loads intermediate chapter artifacts (outline, draft, review) to disk
under ``{base_dir}/artifacts/chapter_{N}/{phase}.txt`` (draft) or
``{base_dir}/artifacts/chapter_{N}/{phase}.json`` (outline/review).

Design: frozen dataclass with no crewAI dependency, no mutation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Phases that are stored as plain text; all others stored as JSON.
_TEXT_PHASES: frozenset[str] = frozenset({"draft"})


@dataclass(frozen=True)
class ArtifactStore:
    """Immutable artifact store rooted at *base_dir*.

    Artifacts are organised as::

        {base_dir}/artifacts/chapter_{N}/{phase}.txt   (for "draft")
        {base_dir}/artifacts/chapter_{N}/{phase}.json  (for "outline", "review")
    """

    base_dir: Path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_artifact(self, chapter_num: int, phase: str, content: str) -> Path:
        """Persist *content* for *chapter_num* / *phase* and return the path.

        Args:
            chapter_num: Chapter number (1-based).
            phase: Artifact phase — ``"outline"``, ``"draft"``, or ``"review"``.
            content: Raw text or JSON string to persist.

        Returns:
            Absolute :class:`~pathlib.Path` of the written file.
        """
        artifact_path = self._artifact_path(chapter_num, phase)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            artifact_path.write_text(content, encoding="utf-8")
            logger.debug(
                "[artifact_store] Saved chapter %d/%s → %s", chapter_num, phase, artifact_path
            )
        except OSError as exc:
            logger.warning(
                "[artifact_store] Could not save chapter %d/%s to %s: %s",
                chapter_num,
                phase,
                artifact_path,
                exc,
            )

        return artifact_path

    def load_artifact(self, chapter_num: int, phase: str) -> str | None:
        """Load the artifact for *chapter_num* / *phase*, or ``None`` if absent.

        Args:
            chapter_num: Chapter number (1-based).
            phase: Artifact phase.

        Returns:
            File contents as a string, or ``None`` if the file does not exist.
        """
        artifact_path = self._artifact_path(chapter_num, phase)
        if not artifact_path.exists():
            return None
        try:
            return artifact_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "[artifact_store] Could not load chapter %d/%s from %s: %s",
                chapter_num,
                phase,
                artifact_path,
                exc,
            )
            return None

    def list_artifacts(self, chapter_num: int) -> list[str]:
        """Return the phase names that have been persisted for *chapter_num*.

        Args:
            chapter_num: Chapter number (1-based).

        Returns:
            Sorted list of phase name strings (e.g. ``["draft", "review"]``).
        """
        chapter_dir = self._chapter_dir(chapter_num)
        if not chapter_dir.exists():
            return []
        phases: list[str] = []
        for entry in chapter_dir.iterdir():
            if entry.is_file():
                phases.append(entry.stem)
        return sorted(phases)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _chapter_dir(self, chapter_num: int) -> Path:
        return self.base_dir / "artifacts" / f"chapter_{chapter_num}"

    def _artifact_path(self, chapter_num: int, phase: str) -> Path:
        ext = "txt" if phase in _TEXT_PHASES else "json"
        return self._chapter_dir(chapter_num) / f"{phase}.{ext}"


def artifact_store_from_config(config: dict) -> ArtifactStore:
    """Construct an :class:`ArtifactStore` from a pipeline *config* dict.

    Uses ``config["output_dir"]`` as ``base_dir``, falling back to ``"output"``.
    """
    base_dir = Path(config.get("output_dir", "output"))
    return ArtifactStore(base_dir=base_dir)
