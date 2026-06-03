"""Project workspace path helpers for young-writer runtime data."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


RUNTIME_DIR_ENV_VARS = ("YOUNG_WRITER_DATA_DIR", "YOUNG_WRITER_RUNTIME_DIR")


def safe_project_slug(title: str, fallback: str = "untitled") -> str:
    """Return a filesystem-safe project title segment without changing CJK names."""
    cleaned = str(title or "").replace("/", "-").replace("\\", "-").strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned or fallback


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved paths for one novel project."""

    project_id: str
    title: str
    project_dir: Path
    scripts_dir: Path
    film_drama_dir: Path
    legacy_novel_dir: Path
    legacy_scripts_dir: Path
    legacy_film_drama_dir: Path
    layout: str

    @property
    def chapters_dir(self) -> Path:
        return self.project_dir / "chapters"

    @property
    def consistency_reports_dir(self) -> Path:
        return self.project_dir / "consistency_reports"

    @property
    def plot_summaries_dir(self) -> Path:
        return self.project_dir / "plot_summaries"

    @property
    def runs_dir(self) -> Path:
        return self.project_dir / "runs"

    @property
    def uses_unified_runtime_root(self) -> bool:
        return self.layout == "runtime"

    def ensure_runtime_dirs(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.film_drama_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class WorkspacePaths:
    """Resolved repository-local runtime and legacy workspace roots."""

    root_dir: Path
    runtime_dir: Path
    projects_dir: Path
    legacy_novels_dir: Path
    legacy_generated_scripts_dir: Path
    legacy_film_drama_scripts_dir: Path
    config_dir: Path

    @classmethod
    def from_root(
        cls, root_dir: str | Path, *, config_dir: str | Path | None = None
    ) -> WorkspacePaths:
        root_path = Path(root_dir).expanduser().resolve()
        runtime_override = next(
            (
                value
                for name in RUNTIME_DIR_ENV_VARS
                if (value := os.environ.get(name))
            ),
            None,
        )
        runtime_dir = (
            Path(runtime_override).expanduser().resolve()
            if runtime_override
            else root_path / "runtime"
        )
        config_path = (
            Path(config_dir).expanduser().resolve()
            if config_dir is not None
            else root_path / "config"
        )
        return cls(
            root_dir=root_path,
            runtime_dir=runtime_dir,
            projects_dir=runtime_dir / "projects",
            legacy_novels_dir=root_path / "novels",
            legacy_generated_scripts_dir=root_path / "generated_scripts",
            legacy_film_drama_scripts_dir=root_path / "film_drama_scripts",
            config_dir=config_path,
        )

    @classmethod
    def from_config_dir(cls, config_dir: str | Path) -> WorkspacePaths:
        config_path = Path(config_dir).expanduser().resolve()
        return cls.from_root(config_path.parent, config_dir=config_path)

    def project_basename(self, title: str, project_id: str) -> str:
        project_slug = safe_project_slug(title, fallback=project_id)
        if project_slug == project_id:
            return project_id
        return f"{project_slug}_{project_id}"

    def _existing_or_default(self, candidates: tuple[Path, ...]) -> Path:
        existing = next((path for path in candidates if path.exists()), None)
        return existing if existing is not None else candidates[0]

    def project_paths(
        self,
        *,
        title: str,
        project_id: str,
        prefer_existing_legacy: bool = True,
    ) -> ProjectPaths:
        basename = self.project_basename(title, project_id)
        legacy_novel_dir = self.legacy_novels_dir / basename
        legacy_slug = safe_project_slug(title, fallback=project_id)
        legacy_title_dir = self.legacy_novels_dir / legacy_slug
        legacy_dir_names = (basename, legacy_slug, project_id)
        legacy_scripts_dir = self._existing_or_default(
            tuple(self.legacy_generated_scripts_dir / name for name in legacy_dir_names)
        )
        legacy_film_drama_dir = self._existing_or_default(
            tuple(self.legacy_film_drama_scripts_dir / name for name in legacy_dir_names)
        )

        if prefer_existing_legacy:
            existing_legacy = next(
                (
                    path
                    for path in (legacy_novel_dir, legacy_title_dir)
                    if path.exists()
                ),
                None,
            )
            if existing_legacy is not None:
                return ProjectPaths(
                    project_id=project_id,
                    title=title,
                    project_dir=existing_legacy,
                    scripts_dir=legacy_scripts_dir,
                    film_drama_dir=legacy_film_drama_dir,
                    legacy_novel_dir=legacy_novel_dir,
                    legacy_scripts_dir=legacy_scripts_dir,
                    legacy_film_drama_dir=legacy_film_drama_dir,
                    layout="legacy",
                )

        project_dir = self.projects_dir / basename
        return ProjectPaths(
            project_id=project_id,
            title=title,
            project_dir=project_dir,
            scripts_dir=project_dir / "derivatives",
            film_drama_dir=project_dir / "film_drama",
            legacy_novel_dir=legacy_novel_dir,
            legacy_scripts_dir=legacy_scripts_dir,
            legacy_film_drama_dir=legacy_film_drama_dir,
            layout="runtime",
        )
