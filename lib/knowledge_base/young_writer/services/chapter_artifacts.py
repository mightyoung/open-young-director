"""Helpers for trusting saved chapter artifacts on disk."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


_CHAPTER_FILE_PATTERN = re.compile(r"ch(\d+)_")
_CHAPTER_HEADING_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_CHAPTER_WORD_COUNT_PATTERN = re.compile(r"字数:\s*(\d+)")
_CHAPTER_GENERATED_AT_PATTERN = re.compile(r"生成时间:\s*([^\n|]+)")
_CHAPTER_SUMMARY_PATTERN = re.compile(r"\*\*本章概要\*\*:\s*(.+)")


def is_complete_chapter_artifact(chapter_file: Path) -> bool:
    """Return True when a saved chapter file looks complete enough to trust."""
    try:
        text = chapter_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(_CHAPTER_HEADING_PATTERN.search(text)) and "生成时间:" in text and "*(本章完)*" in text


def discover_saved_chapter_numbers(project_dir: Path) -> set[int]:
    """Discover trusted saved chapter numbers from actual chapter artifacts on disk."""
    chapters_dir = project_dir / "chapters"
    if not chapters_dir.exists():
        return set()

    chapter_numbers: set[int] = set()
    for chapter_file in chapters_dir.glob("ch*.md"):
        match = _CHAPTER_FILE_PATTERN.match(chapter_file.name)
        if match and is_complete_chapter_artifact(chapter_file):
            chapter_numbers.add(int(match.group(1)))
    return chapter_numbers


def load_saved_chapter_metadata(project_dir: Path) -> list[dict[str, Any]]:
    """Load trusted saved chapter metadata from metadata.json filtered by complete files."""
    metadata_file = project_dir / "metadata.json"
    saved_numbers = discover_saved_chapter_numbers(project_dir)
    if not saved_numbers:
        return []
    if not metadata_file.exists():
        return _chapter_metadata_from_artifacts(project_dir, saved_numbers)
    try:
        payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    except Exception:
        return _chapter_metadata_from_artifacts(project_dir, saved_numbers)

    chapters: list[dict[str, Any]] = []
    for item in payload.get("chapters", []):
        try:
            chapter_number = int(item.get("number", 0) or 0)
        except Exception:
            continue
        if chapter_number not in saved_numbers:
            continue
        chapters.append(
            {
                "number": chapter_number,
                "title": str(item.get("title", "") or ""),
                "word_count": int(item.get("word_count", 0) or 0),
                "summary": str(item.get("summary", "") or ""),
                "file_path": str(item.get("file_path", "") or ""),
                "created_at": str(
                    item.get("created_at") or item.get("generation_time") or ""
                ),
            }
        )
    chapters.sort(key=lambda item: int(item.get("number", 0) or 0))
    return chapters


def _chapter_metadata_from_artifacts(
    project_dir: Path,
    saved_numbers: set[int],
) -> list[dict[str, Any]]:
    chapters_dir = project_dir / "chapters"
    chapters: list[dict[str, Any]] = []
    for chapter_number in sorted(saved_numbers):
        matches = sorted(chapters_dir.glob(f"ch{chapter_number:03d}_*.md"))
        if not matches:
            continue
        chapter_file = matches[0]
        try:
            text = chapter_file.read_text(encoding="utf-8")
        except OSError:
            continue
        heading_match = _CHAPTER_HEADING_PATTERN.search(text)
        word_count_match = _CHAPTER_WORD_COUNT_PATTERN.search(text)
        generated_at_match = _CHAPTER_GENERATED_AT_PATTERN.search(text)
        summary_match = _CHAPTER_SUMMARY_PATTERN.search(text)
        chapters.append(
            {
                "number": chapter_number,
                "title": (
                    heading_match.group(1).strip()
                    if heading_match
                    else chapter_file.stem
                ),
                "word_count": int(word_count_match.group(1)) if word_count_match else 0,
                "summary": summary_match.group(1).strip() if summary_match else "",
                "file_path": str(chapter_file),
                "created_at": (
                    generated_at_match.group(1).strip()
                    if generated_at_match
                    else ""
                ),
            }
        )
    return chapters


def summarize_saved_chapters(project_dir: Path) -> dict[str, Any]:
    """Return a project-level summary derived from trusted chapter artifacts."""
    chapter_entries = load_saved_chapter_metadata(project_dir)
    chapter_numbers = [int(item["number"]) for item in chapter_entries]
    total_words = sum(int(item.get("word_count", 0) or 0) for item in chapter_entries)
    return {
        "successful": len(chapter_entries),
        "checkpoints": chapter_numbers,
        "total_words_generated": total_words,
        "saved_chapters": chapter_entries,
    }
