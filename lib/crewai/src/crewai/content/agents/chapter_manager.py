"""Chapter Manager for novel generation system."""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChapterPlotSummary:
    """Three-level plot summary for a chapter."""
    chapter_number: int
    one_line_summary: str = ""  # L1: One line summary
    brief_summary: str = ""  # L2: Brief summary (2-3 sentences)
    key_plot_points: List[str] = field(default_factory=list)  # L3: Key plot points
    character_states: Dict[str, str] = field(default_factory=dict)
    plot_threads: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)


class ChapterManager:
    """Manages chapter files and metadata."""

    def __init__(self, project_id: str, base_dir_override: str = None):
        self.project_id = project_id
        # base_dir_override can be either:
        # 1. A parent directory (e.g., lib/knowledge_base/novels) - then we append project_title
        # 2. A full novel directory (e.g., lib/knowledge_base/novels/太古魔帝传) - use directly
        self.base_dir = Path(base_dir_override) if base_dir_override else Path("lib/knowledge_base/novels")

        # Use absolute path to config directory
        project_config_file = Path("lib/knowledge_base/config") / f"project_{project_id}.json"
        if project_config_file.exists():
            data = json.loads(project_config_file.read_text(encoding="utf-8"))
            self.project_title = data.get("title", project_id)
        else:
            self.project_title = project_id

        # If base_dir_override is provided and contains the project title, use it directly
        # Otherwise, construct novel_dir by appending project_title to base_dir
        if base_dir_override:
            override_path = Path(base_dir_override)
            # Check if override_path already ends with project_title to avoid double-nesting
            if override_path.name == self.project_title:
                self.novel_dir = override_path
            else:
                self.novel_dir = self.base_dir / self.project_title
        else:
            self.novel_dir = self.base_dir / self.project_title

        self.chapters_dir = self.novel_dir / "chapters"
        self.consistency_dir = self.novel_dir / "consistency_reports"
        self.plot_summary_dir = self.novel_dir / "plot_summaries"

        # FILM_DRAMA scripts stored separately in: lib/knowledge_base/film_drama_scripts/{project_title}/
        self.film_drama_dir = Path("lib/knowledge_base/film_drama_scripts") / self.project_title

        self._chapters_index: Optional[List[Dict]] = None

    def _ensure_directories(self):
        """Ensure all necessary directories exist."""
        self.chapters_dir.mkdir(parents=True, exist_ok=True)
        self.consistency_dir.mkdir(parents=True, exist_ok=True)
        self.plot_summary_dir.mkdir(parents=True, exist_ok=True)
        self.film_drama_dir.mkdir(parents=True, exist_ok=True)

    def _load_chapters_index(self) -> List[Dict]:
        """Load chapters index from metadata file."""
        if self._chapters_index is not None:
            return self._chapters_index

        metadata_file = self.novel_dir / "metadata.json"
        if metadata_file.exists():
            try:
                data = json.loads(metadata_file.read_text(encoding="utf-8"))
                self._chapters_index = data.get("chapters", [])
                return self._chapters_index
            except Exception:
                pass

        self._chapters_index = []
        return self._chapters_index

    def _save_chapters_index(self):
        """Save chapters index to metadata file."""
        metadata_file = self.novel_dir / "metadata.json"
        self._ensure_directories()

        metadata = {
            "project_id": self.project_id,
            "updated_at": datetime.now().isoformat(),
            "total_chapters": len(self._chapters_index) if self._chapters_index else 0,
            "chapters": self._chapters_index or [],
        }

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def build_context(self, chapter_num: int) -> Dict[str, Any]:
        """Build context for generating a chapter.

        Includes progressive disclosure levels:
        - Level 1: Brief summary from plot_summaries
        - Level 2: Key events and character states from plot_summaries
        - Level 3: Full chapter content for recent chapters
        """
        self._ensure_directories()
        chapters = self._load_chapters_index()

        context = {
            "chapter_number": chapter_num,
            "project_title": self.project_title,
            "previous_chapters": [],
            "previous_summary": "",
            "chapter_dir": str(self.chapters_dir),
        }

        if chapter_num > 1:
            # Load previous 2 chapters with progressive disclosure
            for i in range(max(1, chapter_num - 2), chapter_num):
                matching = list(self.chapters_dir.glob(f"ch{i:03d}_*.md"))
                if matching:
                    ch_file = matching[0]
                    content = ch_file.read_text(encoding="utf-8")

                    # Get plot summary for this chapter
                    summary_file = self.plot_summary_dir / f"ch{i:03d}_summary.json"
                    key_events = []
                    character_states = {}
                    if summary_file.exists():
                        summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                        key_events = summary_data.get("key_plot_points", [])
                        character_states = summary_data.get("character_states", {})

                    context["previous_chapters"].append({
                        "number": i,
                        "title": self._extract_title_from_content(content),
                        "content": content,  # Full content for progressive reading
                        "key_events": key_events,
                        "character_states": character_states,
                        "file_path": str(ch_file),
                    })

            # Get previous chapter's summary for brief overview
            summary_file = self.plot_summary_dir / f"ch{chapter_num-1:03d}_summary.json"
            if summary_file.exists():
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                context["previous_summary"] = summary_data.get("brief_summary", "")

        outline_file = self.novel_dir / "outline" / "第一卷详细章节规划.md"
        if outline_file.exists():
            context["outline"] = outline_file.read_text(encoding="utf-8")
        else:
            context["outline"] = ""

        # Extract world_name and character_names from outline for prompt constraints
        world_name, character_names = self._extract_world_and_characters(outline_file)
        context["world_name"] = world_name
        context["character_names"] = character_names

        return context

    def _extract_world_and_characters(self, outline_file: Path) -> tuple:
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

            return world_name, sorted(list(character_names_set))

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
        key_events: List[str] = None,
        character_appearances: List[str] = None,
        generation_time: str = None,
    ) -> Dict[str, Any]:
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

        full_content = header + content + "\n\n*（本章完）*\n"

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
        existing_idx = None
        for idx, ch in enumerate(chapters):
            if ch.get("number") == number:
                existing_idx = idx
                break

        if existing_idx is not None:
            chapters[existing_idx] = chapter_entry
        else:
            chapters.append(chapter_entry)

        chapters.sort(key=lambda x: x.get("number", 0))
        self._chapters_index = chapters
        self._save_chapters_index()

        return chapter_entry

    def save_plot_summary(self, plot_summary: ChapterPlotSummary):
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

    def save_consistency_report(
        self,
        chapter_number: int,
        report: Dict[str, Any],
        rewrite_history: List[Dict] = None,
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

    def save_film_drama_content(
        self,
        chapter_number: int,
        film_drama_data: Dict[str, Any],
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

    def verify_project_integrity(self, declared_latest: int) -> Dict[str, Any]:
        """Verify project integrity."""
        chapters = self._load_chapters_index()
        files_on_disk = len(list(self.chapters_dir.glob("ch*.md")))

        result = {
            "valid": True,
            "stats": {
                "total_chapters": len(chapters),
                "actual_latest": chapters[-1].get("number", 0) if chapters else 0,
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

    def validate_chapter_sequence(self) -> Dict[str, Any]:
        """Validate chapter sequence continuity."""
        chapters = self._load_chapters_index()
        existing_numbers = sorted([ch.get("number", 0) for ch in chapters])

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

        gaps = []
        for i in range(1, len(existing_numbers)):
            if existing_numbers[i] - existing_numbers[i-1] > 1:
                gaps.append({
                    "from_chapter": existing_numbers[i-1],
                    "to_chapter": existing_numbers[i],
                    "gap_size": existing_numbers[i] - existing_numbers[i-1] - 1,
                })

        result["gaps"] = gaps
        result["stats"]["gap_count"] = len(gaps)
        result["stats"]["missing_count"] = sum(g["gap_size"] for g in gaps)
        result["valid"] = len(gaps) == 0

        return result


def get_chapter_manager(project_id: str, base_dir_override: str = None) -> ChapterManager:
    """Get a ChapterManager instance."""
    return ChapterManager(project_id, base_dir_override=base_dir_override)
