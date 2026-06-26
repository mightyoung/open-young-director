"""File-backed local store for story graph artifacts."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any


def story_graph_dir(project_dir: str | Path) -> Path:
    return Path(project_dir) / "story_graph"


def snapshot_dir(project_dir: str | Path) -> Path:
    return story_graph_dir(project_dir) / "snapshots"


def rebaseline_dir(project_dir: str | Path) -> Path:
    return story_graph_dir(project_dir) / "rebaseline"


class StoryGraphStore:
    """Project-local JSONL/snapshot store with optional SQLite index."""

    def __init__(self, project_dir: str | Path) -> None:
        self.project_dir = Path(project_dir)
        self.root_dir = story_graph_dir(self.project_dir)
        self.events_path = self.root_dir / "graph_events.jsonl"
        self.snapshot_root = snapshot_dir(self.project_dir)
        self.rebaseline_root = rebaseline_dir(self.project_dir)
        self.sqlite_path = self.root_dir / "story_graph.sqlite"
        self._ensure_dirs()
        self._ensure_sqlite()

    def _ensure_dirs(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        self.rebaseline_root.mkdir(parents=True, exist_ok=True)

    def _ensure_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    chapter_number INTEGER PRIMARY KEY,
                    saved_at TEXT NOT NULL,
                    snapshot_path TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rebaseline_deltas (
                    chapter_number INTEGER PRIMARY KEY,
                    saved_at TEXT NOT NULL,
                    delta_path TEXT NOT NULL
                )
                """
            )

    def append_events(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0
        with self.events_path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return len(events)

    def save_snapshot(self, snapshot: dict[str, Any], *, chapter_number: int) -> Path:
        path = self.snapshot_root / f"ch{int(chapter_number):03d}.json"
        path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots(chapter_number, saved_at, snapshot_path)
                VALUES (?, ?, ?)
                """,
                (int(chapter_number), datetime.now().isoformat(), str(path)),
            )
        return path

    def load_snapshot(self, chapter_number: int) -> dict[str, Any] | None:
        path = self.snapshot_root / f"ch{int(chapter_number):03d}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_rebaseline_delta(
        self, chapter_number: int, payload: dict[str, Any]
    ) -> Path:
        path = self.rebaseline_root / f"ch{int(chapter_number):03d}_delta.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rebaseline_deltas(chapter_number, saved_at, delta_path)
                VALUES (?, ?, ?)
                """,
                (int(chapter_number), datetime.now().isoformat(), str(path)),
            )
        return path

    def load_rebaseline_deltas(
        self, *, before_chapter: int | None = None
    ) -> list[dict[str, Any]]:
        rows: list[tuple[int, str]] = []
        with sqlite3.connect(self.sqlite_path) as conn:
            if before_chapter is None:
                rows = conn.execute(
                    """
                    SELECT chapter_number, delta_path
                    FROM rebaseline_deltas
                    ORDER BY chapter_number
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT chapter_number, delta_path
                    FROM rebaseline_deltas
                    WHERE chapter_number < ?
                    ORDER BY chapter_number
                    """,
                    (int(before_chapter),),
                ).fetchall()
        payloads: list[dict[str, Any]] = []
        for _, path_str in rows:
            path = Path(path_str)
            if path.exists():
                payloads.append(json.loads(path.read_text(encoding="utf-8")))
        return payloads
