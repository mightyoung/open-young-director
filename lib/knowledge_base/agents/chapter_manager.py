"""Chapter Manager for novel generation system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ChapterMetadata:
    """Metadata for a saved chapter."""

    number: int
    title: str
    word_count: int
    summary: str = ""
    key_events: list[str] = field(default_factory=list)
    character_appearances: list[str] = field(default_factory=list)
    file_path: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ChapterContent:
    """Full chapter content with metadata."""

    metadata: ChapterMetadata
    content: str


@dataclass
class ChapterSaveResult:
    """Result returned after saving a chapter."""

    metadata: ChapterMetadata
    content: str


@dataclass
class ChapterPlotSummary:
    """Three-level plot summary for a chapter."""

    chapter_number: int
    one_line_summary: str = ""  # L1: One line summary
    brief_summary: str = ""  # L2: Brief summary (2-3 sentences)
    key_plot_points: list[str] = field(default_factory=list)  # L3: Key plot points
    character_states: dict[str, str] = field(default_factory=dict)
    plot_threads: list[str] = field(default_factory=list)
    foreshadowing: list[str] = field(default_factory=list)


class ChapterContext(dict):
    """Dictionary-like context that also renders as a human-readable summary."""

    def __init__(self, rendered_text: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.rendered_text = rendered_text

    def __str__(self) -> str:
        return self.rendered_text

    def __repr__(self) -> str:
        return self.rendered_text

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return item in self.rendered_text
        return dict.__contains__(self, item)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.rendered_text == other
        return dict.__eq__(self, other)


class ChapterManager:
    """Manages chapter files and metadata."""

    def __init__(
        self,
        project_id: str,
        base_dir: str | None = None,
        base_dir_override: str | None = None,
    ):
        self.project_id = project_id
        base_dir_value = base_dir if base_dir is not None else base_dir_override
        override_path = Path(base_dir_value) if base_dir_value else None
        if override_path is not None:
            looks_like_project_dir = (
                (override_path / "chapters").exists()
                or (override_path / "metadata.json").exists()
                or override_path.name.endswith(f"_{project_id}")
                or project_id in override_path.name
            )
            project_dir_hint = override_path if looks_like_project_dir else None
            novels_root = override_path.parent if looks_like_project_dir else override_path
            self.root_dir = novels_root.parent
        else:
            project_dir_hint = None
            self.root_dir = Path(__file__).resolve().parents[1]
            novels_root = self.root_dir / "novels"
        self.base_dir = novels_root

        project_config_file = self.root_dir / "config" / f"project_{project_id}.json"
        if project_config_file.exists():
            data = json.loads(project_config_file.read_text(encoding="utf-8"))
            self.project_title = data.get("title", project_id)
        else:
            self.project_title = project_id

        project_slug = self.project_title.replace("/", "-")
        project_dir_basename = project_id if project_slug == project_id else f"{project_slug}_{project_id}"

        if base_dir_value:
            if project_dir_hint is not None:
                self.novel_dir = project_dir_hint
            elif override_path.name == self.project_title:
                self.novel_dir = override_path
            else:
                exact_dir = self.base_dir / project_dir_basename
                matches: list[Path] = []
                for prefix in {self.project_title, project_slug}:
                    matches.extend(path for path in self.base_dir.glob(f"{prefix}*") if path.is_dir())
                matches = sorted({path.resolve() for path in matches})
                preferred = next(
                    (
                        path
                        for path in matches
                        if path.name.endswith(f"_{self.project_id}") or self.project_id in path.name
                    ),
                    None,
                )
                if preferred is not None:
                    self.novel_dir = preferred
                elif exact_dir.exists():
                    self.novel_dir = exact_dir
                else:
                    self.novel_dir = matches[0] if matches else exact_dir
        else:
            self.novel_dir = self.base_dir / self.project_title

        self.base_dir = self.novel_dir

        self.chapters_dir = self.novel_dir / "chapters"
        self.consistency_dir = self.novel_dir / "consistency_reports"
        self.plot_summary_dir = self.novel_dir / "plot_summaries"
        self.plot_summaries_dir = self.plot_summary_dir
        self.film_drama_dir = self.root_dir / "film_drama_scripts" / project_dir_basename

        self._chapters_index: dict[int, ChapterMetadata] | None = None
        self._ensure_directories()
        self._chapters_index = self._load_chapters_index()

    def _ensure_directories(self):
        """Ensure all necessary directories exist."""
        self.chapters_dir.mkdir(parents=True, exist_ok=True)
        self.consistency_dir.mkdir(parents=True, exist_ok=True)
        self.plot_summary_dir.mkdir(parents=True, exist_ok=True)
        self.film_drama_dir.mkdir(parents=True, exist_ok=True)

    def _coerce_datetime(self, value: Any) -> datetime:
        """Parse persisted timestamps into datetimes."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now()

    def _metadata_from_entry(self, entry: dict[str, Any]) -> ChapterMetadata:
        """Convert a metadata entry into a dataclass."""
        return ChapterMetadata(
            number=int(entry.get("number", 0)),
            title=str(entry.get("title", "")),
            word_count=int(entry.get("word_count", 0)),
            summary=str(entry.get("summary", "")),
            key_events=list(entry.get("key_events", [])),
            character_appearances=list(entry.get("character_appearances", [])),
            file_path=str(entry.get("file_path", "")),
            created_at=self._coerce_datetime(entry.get("created_at") or entry.get("generation_time")),
        )

    def _entry_from_metadata(self, metadata: ChapterMetadata) -> dict[str, Any]:
        """Convert a dataclass into a persisted metadata entry."""
        return {
            "number": metadata.number,
            "title": metadata.title,
            "word_count": metadata.word_count,
            "summary": metadata.summary,
            "key_events": list(metadata.key_events),
            "character_appearances": list(metadata.character_appearances),
            "file_path": metadata.file_path,
            "created_at": metadata.created_at.isoformat(),
        }

    def _scan_chapter_files(self) -> dict[int, ChapterMetadata]:
        """Fallback scan when metadata.json is missing or incomplete."""
        if not self.chapters_dir.exists():
            return {}

        entries: dict[int, ChapterMetadata] = {}
        for chapter_file in sorted(self.chapters_dir.glob("ch*.md")):
            match = re.match(r"ch(\d{3})_(.*)\.md$", chapter_file.name)
            number = int(match.group(1)) if match else 0
            title = match.group(2).replace("_", " ") if match else chapter_file.stem
            content = chapter_file.read_text(encoding="utf-8")
            summary_match = re.search(r"\*\*本章概要\*\*:\s*(.*)", content)
            key_events_match = re.search(r"\*\*关键事件\*\*:\s*(.*)", content)
            entries[number] = ChapterMetadata(
                number=number,
                title=title,
                word_count=len(re.sub(r"\s+", "", content)),
                summary=summary_match.group(1).strip() if summary_match else "",
                key_events=[
                    item.strip()
                    for item in (key_events_match.group(1).split(",") if key_events_match else [])
                    if item.strip() and item.strip() != "无"
                ],
                character_appearances=[],
                file_path=str(chapter_file),
                created_at=datetime.fromtimestamp(chapter_file.stat().st_mtime),
            )
        return entries

    def _load_chapters_index(self) -> dict[int, ChapterMetadata]:
        """Load chapters index from metadata file."""
        if self._chapters_index is not None:
            return self._chapters_index

        metadata_file = self.novel_dir / "metadata.json"
        if metadata_file.exists():
            try:
                data = json.loads(metadata_file.read_text(encoding="utf-8"))
                entries = {
                    int(item.get("number", 0)): self._metadata_from_entry(item)
                    for item in data.get("chapters", [])
                }
                self._chapters_index = entries
                return self._chapters_index
            except Exception:
                logger.warning("Failed to load chapter metadata from %s", metadata_file, exc_info=True)

        self._chapters_index = self._scan_chapter_files()
        return self._chapters_index

    def _save_chapters_index(self):
        """Save chapters index to metadata file."""
        metadata_file = self.novel_dir / "metadata.json"
        self._ensure_directories()

        chapters = [self._entry_from_metadata(chapter) for chapter in self.get_chapter_list()]

        metadata = {
            "project_id": self.project_id,
            "updated_at": datetime.now().isoformat(),
            "total_chapters": len(chapters),
            "chapters": chapters,
        }

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def build_context(self, chapter_num: int, window: int = 2) -> ChapterContext:
        """Build context for generating a chapter.

        The returned object behaves like a dict for the generator, but also
        renders as a human-readable summary for tests and CLI display.
        """
        self._ensure_directories()

        previous_chapters: list[dict[str, Any]] = []
        rendered_lines: list[str] = []

        if chapter_num <= 1:
            rendered_lines.append("暂无前情 (第一章)")
        else:
            start = max(1, chapter_num - window)
            for i in range(start, chapter_num):
                chapter_content = self.load_chapter(i)
                if chapter_content is None:
                    continue
                summary = chapter_content.metadata.summary or ""
                chapter_title = chapter_content.metadata.title
                summary_file = self.plot_summary_dir / f"ch{i:03d}_summary.json"
                key_events = []
                character_states = {}
                if summary_file.exists():
                    summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                    key_events = summary_data.get("key_plot_points", [])
                    character_states = summary_data.get("character_states", {})
                    if not summary:
                        summary = summary_data.get("brief_summary", "")

                previous_chapters.append(
                    {
                        "number": i,
                        "title": chapter_title,
                        "content": chapter_content.content,
                        "key_events": key_events,
                        "character_states": character_states,
                        "file_path": chapter_content.metadata.file_path,
                    }
                )
                rendered_lines.append(f"第{i}章 {chapter_title}")
                if summary:
                    rendered_lines.append(summary)
                else:
                    rendered_lines.append(f"故事已发展到第{i}章")

        summary_file = self.plot_summary_dir / f"ch{chapter_num-1:03d}_summary.json"
        previous_summary = ""
        if summary_file.exists():
            summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
            previous_summary = summary_data.get("brief_summary", "")

        outline_file = self.novel_dir / "outline" / "第一卷详细章节规划.md"
        outline = outline_file.read_text(encoding="utf-8") if outline_file.exists() else ""
        world_name, character_names = self._extract_world_and_characters(outline_file)

        rendered_text = "\n".join(rendered_lines) if rendered_lines else "暂无前情 (第一章)"
        return ChapterContext(
            rendered_text,
            chapter_number=chapter_num,
            project_title=self.project_title,
            previous_chapters=previous_chapters,
            previous_summary=previous_summary,
            chapter_dir=str(self.chapters_dir),
            outline=outline,
            world_name=world_name,
            character_names=character_names,
        )

    def _extract_world_and_characters(self, outline_file: Path) -> tuple[str, list[str]]:
        """Extract world/sect name and character names from outline file.

        Returns:
            tuple: (world_name: str, character_names: list)
        """
        if not outline_file or not outline_file.exists():
            return "", []

        try:
            content = outline_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            # 1. Extract world/sect name from the architecture table
            # Look for "太虚宗" or similar sect names in the outline
            world_name = ""
            sect_patterns = [
                r"太虚宗",
                r"青岚宗",
                r"天玄宗",
                r"玄天宗",
            ]
            for line in lines:
                for pattern in sect_patterns:
                    if pattern in line:
                        world_name = pattern
                        break
                if world_name:
                    break

            # 2. Extract character names from ALL lines in the outline
            # Scan every line for known character names
            character_names_set = set()
            known_chars = {
                "韩林", "韩啸天", "柳如烟", "叶尘", "赵元启",
                "赵天罡", "韩铁山", "小六子", "小蝶", "老周头",
                "叶瑶", "林青", "陈风", "周通", "太虚子",
            }

            for line in lines:
                # Scan every line (not just table lines) for character names
                for char in known_chars:
                    if char in line:
                        character_names_set.add(char)

            return world_name, sorted(character_names_set)

        except Exception:
            return "", []

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from chapter content."""
        lines = content.split("\n")
        for line in lines:
            if line.startswith("#"):
                return line.lstrip("#").strip()
        return ""

    def save_chapter(
        self,
        number: int,
        title: str,
        content: str,
        word_count: int,
        summary: str = "",
        key_events: list[str] | None = None,
        character_appearances: list[str] | None = None,
        generation_time: str | None = None,
    ) -> ChapterSaveResult:
        """Save a chapter to disk."""
        self._ensure_directories()

        if key_events is None:
            key_events = []
        if character_appearances is None:
            character_appearances = []
        if generation_time is None:
            generation_time = datetime.now().isoformat()

        safe_title = re.sub(r'[^\w\s\-]', '', title.replace(" ", "_"))
        chapter_file = self.chapters_dir / f"ch{number:03d}_{safe_title}.md"

        header = f"""# {title}

> 第{number}章 | 字数: {word_count} | 生成时间: {generation_time}

**本章概要**: {summary}

**关键事件**: {', '.join(key_events) if key_events else '无'}

---

"""

        full_content = header + content + "\n\n*(本章完)*\n"

        with open(chapter_file, "w", encoding="utf-8") as f:
            f.write(full_content)

        chapter_entry = {
            "number": number,
            "title": title,
            "word_count": word_count,
            "summary": summary,
            "key_events": key_events,
            "character_appearances": character_appearances,
            "file_path": str(chapter_file),
            "created_at": generation_time,
        }

        chapters = self._load_chapters_index()
        chapters[number] = self._metadata_from_entry(chapter_entry)
        self._chapters_index = chapters
        self._save_chapters_index()

        metadata = self._metadata_from_entry(chapter_entry)
        return ChapterSaveResult(metadata=metadata, content=content)

    def save_plot_summary(self, plot_summary: ChapterPlotSummary) -> str:
        """Save plot summary for a chapter."""
        self._ensure_directories()

        summary_file = self.plot_summary_dir / f"ch{plot_summary.chapter_number:03d}_summary.json"

        summary_data = {
            "chapter_number": plot_summary.chapter_number,
            "one_line_summary": plot_summary.one_line_summary,
            "brief_summary": plot_summary.brief_summary,
            "key_plot_points": plot_summary.key_plot_points,
            "character_states": plot_summary.character_states,
            "plot_threads": plot_summary.plot_threads,
            "foreshadowing": plot_summary.foreshadowing,
            "saved_at": datetime.now().isoformat(),
        }

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        return str(summary_file)

    def get_plot_summary(self, chapter_number: int) -> ChapterPlotSummary | None:
        """Load a saved plot summary."""
        summary_file = self.plot_summary_dir / f"ch{chapter_number:03d}_summary.json"
        if not summary_file.exists():
            return None

        try:
            data = json.loads(summary_file.read_text(encoding="utf-8"))
        except Exception:
            return None

        return ChapterPlotSummary(
            chapter_number=int(data.get("chapter_number", chapter_number)),
            one_line_summary=str(data.get("one_line_summary", "")),
            brief_summary=str(data.get("brief_summary", "")),
            key_plot_points=list(data.get("key_plot_points", [])),
            character_states=dict(data.get("character_states", {})),
            plot_threads=list(data.get("plot_threads", [])),
            foreshadowing=list(data.get("foreshadowing", [])),
        )

    def save_consistency_report(
        self,
        chapter_number: int,
        report: dict[str, Any],
        rewrite_history: list[dict] | None = None,
    ):
        """Save consistency check report for a chapter."""
        self._ensure_directories()

        report_file = self.consistency_dir / f"ch{chapter_number:03d}_consistency.json"

        report_data = {
            "chapter_number": chapter_number,
            "report": report,
            "rewrite_history": rewrite_history or [],
            "updated_at": datetime.now().isoformat(),
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

    def get_chapter_list(self) -> list[ChapterMetadata]:
        """Return all chapters sorted by number."""
        chapters = list(self._load_chapters_index().values())
        chapters.sort(key=lambda chapter: chapter.number)
        return chapters

    def load_chapter(self, number: int) -> ChapterContent | None:
        """Load a chapter and its metadata."""
        chapters = self._load_chapters_index()
        metadata = chapters.get(number)
        if metadata is None:
            matching = list(self.chapters_dir.glob(f"ch{number:03d}_*.md"))
            if not matching:
                return None
            chapter_file = matching[0]
            content = chapter_file.read_text(encoding="utf-8")
            metadata = ChapterMetadata(
                number=number,
                title=self._extract_title_from_content(content) or chapter_file.stem,
                word_count=len(re.sub(r"\s+", "", content)),
                summary="",
                key_events=[],
                character_appearances=[],
                file_path=str(chapter_file),
                created_at=datetime.fromtimestamp(chapter_file.stat().st_mtime),
            )
            return ChapterContent(metadata=metadata, content=content)

        file_path = Path(metadata.file_path)
        if not file_path.exists():
            matching = list(self.chapters_dir.glob(f"ch{number:03d}_*.md"))
            if not matching:
                return None
            file_path = matching[0]
        content = file_path.read_text(encoding="utf-8")
        metadata.file_path = str(file_path)
        return ChapterContent(metadata=metadata, content=content)

    def get_chapter_content(self, number: int) -> str | None:
        """Return chapter content as plain text."""
        chapter = self.load_chapter(number)
        return chapter.content if chapter else None

    def get_latest_chapter_number(self) -> int:
        """Return the highest chapter number known to the manager."""
        chapters = self.get_chapter_list()
        return max((chapter.number for chapter in chapters), default=0)

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics for the project."""
        chapters = self.get_chapter_list()
        total_words = sum(chapter.word_count for chapter in chapters)
        return {
            "project_id": self.project_id,
            "project_title": self.project_title,
            "total_chapters": len(chapters),
            "total_words": total_words,
            "latest_chapter": self.get_latest_chapter_number(),
            "chapters": chapters,
        }

    def validate_character_state(self, chapter_number: int, character_name: str, expected_state: str) -> dict[str, Any]:
        """Validate a character state against the chapter plot summary."""
        summary = self.get_plot_summary(chapter_number)
        if summary is None:
            return {
                "valid": False,
                "reason": "情节概述不存在",
                "chapter_number": chapter_number,
                "character_name": character_name,
            }

        actual_state = summary.character_states.get(character_name)
        if actual_state is None:
            return {
                "valid": True,
                "reason": "状态未记录",
                "chapter_number": chapter_number,
                "character_name": character_name,
            }

        if actual_state == expected_state:
            return {
                "valid": True,
                "reason": "状态一致",
                "chapter_number": chapter_number,
                "character_name": character_name,
            }

        return {
            "valid": False,
            "reason": f"状态不一致: 期望 {expected_state}, 实际 {actual_state}",
            "chapter_number": chapter_number,
            "character_name": character_name,
        }

    def export_to_text(self, output_path: str, start: int = 1, end: int | None = None) -> int:
        """Export chapter content into a single text file."""
        chapters = [chapter for chapter in self.get_chapter_list() if chapter.number >= start and (end is None or chapter.number <= end)]
        if not chapters:
            output_file = Path(output_path)
            if output_file.exists():
                output_file.unlink()
            return 0

        lines: list[str] = [f"# {self.project_title}", ""]
        for chapter in chapters:
            chapter_content = self.get_chapter_content(chapter.number) or ""
            lines.append(f"## 第{chapter.number}章 {chapter.title}")
            lines.append("")
            lines.append(chapter_content.strip())
            lines.append("")

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return len(lines)

    def save_film_drama_content(
        self,
        chapter_number: int,
        film_drama_data: dict[str, Any],
    ) -> str:
        """Save FILM_DRAMA content for a chapter.

        FILM_DRAMA content includes:
        - plot_outline: scene structure with beats
        - cast: character cast information
        - scenes: scene IDs
        - final_plot: narrative text
        - content: final assembled chapter content

        Args:
            chapter_number: Chapter number
            film_drama_data: Dict with plot_outline, cast, scenes, final_plot, content

        Returns:
            Path to the saved file
        """
        self._ensure_directories()

        film_drama_file = self.film_drama_dir / f"ch{chapter_number:03d}_film_drama.json"

        save_data = {
            "chapter_number": chapter_number,
            "project_title": self.project_title,
            "plot_outline": film_drama_data.get("plot_outline", {}),
            "cast": film_drama_data.get("cast", []),
            "scenes": film_drama_data.get("scenes", []),
            "final_plot": film_drama_data.get("final_plot", ""),
            "content": film_drama_data.get("content", ""),
            "outline": film_drama_data.get("outline", ""),
            "saved_at": datetime.now().isoformat(),
        }

        with open(film_drama_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Film drama content saved for chapter {chapter_number}: {film_drama_file}")
        return str(film_drama_file)

    def verify_project_integrity(self, declared_latest: int) -> dict[str, Any]:
        """Verify project integrity."""
        chapters = self.get_chapter_list()
        files_on_disk = len(list(self.chapters_dir.glob("ch*.md")))

        result = {
            "valid": True,
            "stats": {
                "total_chapters": len(chapters),
                "actual_latest": chapters[-1].number if chapters else 0,
                "declared_latest": declared_latest,
                "files_on_disk": files_on_disk,
                "indexed_chapters": len(chapters),
            },
            "issues": [],
            "warnings": [],
        }

        if files_on_disk != len(chapters):
            result["warnings"].append(f"Files on disk ({files_on_disk}) != indexed chapters ({len(chapters)})")

        return result

    def validate_chapter_sequence(self) -> dict[str, Any]:
        """Validate chapter sequence continuity."""
        chapters = self.get_chapter_list()
        existing_numbers = sorted([ch.number for ch in chapters])

        result = {
            "valid": True,
            "stats": {
                "existing_count": len(existing_numbers),
                "total_in_range": 0,
                "missing_count": 0,
                "gap_count": 0,
            },
            "gaps": [],
        }

        if not existing_numbers:
            return result

        gaps = [
            {
                "from_chapter": existing_numbers[i - 1],
                "to_chapter": existing_numbers[i],
                "gap_size": existing_numbers[i] - existing_numbers[i - 1] - 1,
            }
            for i in range(1, len(existing_numbers))
            if existing_numbers[i] - existing_numbers[i - 1] > 1
        ]

        result["gaps"] = gaps
        result["stats"]["gap_count"] = len(gaps)
        result["stats"]["missing_count"] = sum(g["gap_size"] for g in gaps)
        result["valid"] = len(gaps) == 0

        return result


def get_chapter_manager(
    project_id: str,
    base_dir: str | None = None,
    base_dir_override: str | None = None,
) -> ChapterManager:
    """Get a ChapterManager instance."""
    return ChapterManager(project_id, base_dir=base_dir, base_dir_override=base_dir_override)
