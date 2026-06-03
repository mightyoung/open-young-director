"""Derived longform memory indexing for generated chapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import sqlite3
from typing import Any, Protocol
from uuid import uuid4


logger = logging.getLogger(__name__)


@dataclass
class LongformMemoryRecord:
    """One derived memory entry with artifact provenance."""

    project_id: str
    chapter_number: int
    memory_type: str
    content: str
    artifact_path: str
    artifact_checksum: str
    source_stage: str
    run_id: str | None = None
    title: str = ""
    summary: str = ""
    tags: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_payload(self, *, score: float = 1.0, max_excerpt_chars: int = 500) -> dict[str, Any]:
        content_excerpt = self.content[:max_excerpt_chars]
        return {
            "memory_type": self.memory_type,
            "chapter_number": self.chapter_number,
            "summary": self.summary,
            "content_excerpt": content_excerpt,
            "artifact_path": self.artifact_path,
            "artifact_checksum": self.artifact_checksum,
            "score": score,
        }


class LongformMemoryStoreProtocol(Protocol):
    """Protocol used by ChapterManager and tests."""

    def write_memories(self, records: list[LongformMemoryRecord]) -> int:
        """Persist records and return count written."""

    def retrieve(
        self,
        *,
        project_id: str,
        chapter_number: int,
        query: str = "",
        top_k: int = 6,
        max_excerpt_chars: int = 500,
        total_budget: int = 2500,
    ) -> list[dict[str, Any]]:
        """Retrieve provenance-bearing memory payloads."""


class EmbeddingProvider(Protocol):
    """Embedding provider interface for semantic retrieval."""

    def embed(self, text: str) -> list[float]:
        """Return a fixed-width embedding vector."""


class DeterministicEmbeddingProvider:
    """Deterministic test fallback embedding provider."""

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _cosine_score(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=False))))


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


class InMemoryLongformMemoryStore:
    """Deterministic test/local memory store."""

    def __init__(self, embedding_provider: EmbeddingProvider | None = None) -> None:
        self.records: list[LongformMemoryRecord] = []
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()

    def write_memories(self, records: list[LongformMemoryRecord]) -> int:
        self.records.extend(records)
        return len(records)

    def retrieve(
        self,
        *,
        project_id: str,
        chapter_number: int,
        query: str = "",
        top_k: int = 6,
        max_excerpt_chars: int = 500,
        total_budget: int = 2500,
    ) -> list[dict[str, Any]]:
        query_embedding = self.embedding_provider.embed(query) if query else []
        scored = []
        for record in self.records:
            if record.project_id != project_id or record.chapter_number >= chapter_number:
                continue
            score = 1.0
            if query_embedding:
                record_embedding = self.embedding_provider.embed(
                    " ".join([record.title, record.summary, record.content])
                )
                score = _cosine_score(query_embedding, record_embedding)
            scored.append((score, record))
        scored.sort(key=lambda item: (item[0], item[1].chapter_number), reverse=True)
        payloads: list[dict[str, Any]] = []
        used = 0
        for score, record in scored[:top_k]:
            remaining = max(total_budget - used, 0)
            if remaining <= 0:
                break
            excerpt_limit = min(max_excerpt_chars, remaining)
            payload = record.to_payload(score=score, max_excerpt_chars=excerpt_limit)
            used += len(payload["content_excerpt"])
            payloads.append(payload)
        return payloads


class PgLongformMemoryStore:
    """PostgreSQL-backed derived memory index."""

    def __init__(
        self,
        database_url: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        from young_writer.scene_db.schema import get_database_url

        self.database_url = database_url or get_database_url()
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()

    def _connection(self):
        from young_writer.scene_db.schema import get_connection

        return get_connection(self.database_url)

    def write_memories(self, records: list[LongformMemoryRecord]) -> int:
        if not records:
            return 0
        conn = self._connection()
        cursor = conn.cursor()
        for record in records:
            embedding = self.embedding_provider.embed(
                " ".join([record.title, record.summary, record.content])
            )
            cursor.execute(
                """
                INSERT INTO longform_memory (
                    id, project_id, run_id, chapter_number, memory_type, title,
                    content, summary, tags, metadata, artifact_path,
                    artifact_checksum, source_stage, embedding, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s)
                """,
                (
                    record.id,
                    record.project_id,
                    record.run_id,
                    record.chapter_number,
                    record.memory_type,
                    record.title,
                    record.content,
                    record.summary,
                    json.dumps(record.tags, ensure_ascii=False),
                    json.dumps(record.metadata, ensure_ascii=False),
                    record.artifact_path,
                    record.artifact_checksum,
                    record.source_stage,
                    _vector_literal(embedding),
                    record.created_at,
                ),
            )
        conn.commit()
        cursor.close()
        conn.close()
        return len(records)

    def retrieve(
        self,
        *,
        project_id: str,
        chapter_number: int,
        query: str = "",
        top_k: int = 6,
        max_excerpt_chars: int = 500,
        total_budget: int = 2500,
    ) -> list[dict[str, Any]]:
        conn = self._connection()
        cursor = conn.cursor()
        if query:
            query_vector = _vector_literal(self.embedding_provider.embed(query))
            cursor.execute(
                """
                SELECT memory_type, chapter_number, summary, content, artifact_path,
                       artifact_checksum, 1 - (embedding <=> %s::vector) AS score
                FROM longform_memory
                WHERE project_id = %s AND chapter_number < %s AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_vector, project_id, chapter_number, query_vector, top_k),
            )
        else:
            cursor.execute(
                """
                SELECT memory_type, chapter_number, summary, content, artifact_path,
                       artifact_checksum, 1.0 AS score
                FROM longform_memory
                WHERE project_id = %s AND chapter_number < %s
                ORDER BY chapter_number DESC, created_at DESC
                LIMIT %s
                """,
                (project_id, chapter_number, top_k),
            )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        payloads: list[dict[str, Any]] = []
        used = 0
        for row in rows:
            content = row[3] or ""
            remaining = max(total_budget - used, 0)
            if remaining <= 0:
                break
            excerpt = content[: min(max_excerpt_chars, remaining)]
            used += len(excerpt)
            payloads.append(
                {
                    "memory_type": row[0],
                    "chapter_number": row[1],
                    "summary": row[2] or "",
                    "content_excerpt": excerpt,
                    "artifact_path": row[4],
                    "artifact_checksum": row[5],
                    "score": float(row[6] or 0.0),
                }
            )
        return payloads


class SQLiteLongformMemoryStore:
    """Project-local SQLite fallback for single-machine longform memory."""

    def __init__(
        self,
        database_path: str | Path,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS longform_memory (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    run_id TEXT,
                    chapter_number INTEGER NOT NULL,
                    memory_type TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    summary TEXT,
                    tags TEXT,
                    metadata TEXT,
                    artifact_path TEXT,
                    artifact_checksum TEXT,
                    source_stage TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_longform_memory_project_chapter
                ON longform_memory(project_id, chapter_number)
                """
            )

    def write_memories(self, records: list[LongformMemoryRecord]) -> int:
        if not records:
            return 0
        with self._connection() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO longform_memory (
                    id, project_id, run_id, chapter_number, memory_type, title,
                    content, summary, tags, metadata, artifact_path,
                    artifact_checksum, source_stage, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.id,
                        record.project_id,
                        record.run_id,
                        record.chapter_number,
                        record.memory_type,
                        record.title,
                        record.content,
                        record.summary,
                        json.dumps(record.tags, ensure_ascii=False),
                        json.dumps(record.metadata, ensure_ascii=False),
                        record.artifact_path,
                        record.artifact_checksum,
                        record.source_stage,
                        record.created_at,
                    )
                    for record in records
                ],
            )
        return len(records)

    def retrieve(
        self,
        *,
        project_id: str,
        chapter_number: int,
        query: str = "",
        top_k: int = 6,
        max_excerpt_chars: int = 500,
        total_budget: int = 2500,
    ) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT project_id, chapter_number, memory_type, title, content,
                       summary, artifact_path, artifact_checksum, run_id,
                       source_stage, created_at
                FROM longform_memory
                WHERE project_id = ? AND chapter_number < ?
                """,
                (project_id, chapter_number),
            ).fetchall()

        query_embedding = self.embedding_provider.embed(query) if query else []
        scored: list[tuple[float, LongformMemoryRecord]] = []
        for row in rows:
            record = LongformMemoryRecord(
                project_id=row[0],
                chapter_number=int(row[1]),
                memory_type=row[2],
                title=row[3] or "",
                content=row[4] or "",
                summary=row[5] or "",
                artifact_path=row[6] or "",
                artifact_checksum=row[7] or "",
                run_id=row[8],
                source_stage=row[9] or "",
                created_at=row[10],
            )
            score = 1.0
            if query_embedding:
                record_embedding = self.embedding_provider.embed(
                    " ".join([record.title, record.summary, record.content])
                )
                score = _cosine_score(query_embedding, record_embedding)
            scored.append((score, record))
        scored.sort(key=lambda item: (item[0], item[1].chapter_number), reverse=True)

        payloads: list[dict[str, Any]] = []
        used = 0
        for score, record in scored[:top_k]:
            remaining = max(total_budget - used, 0)
            if remaining <= 0:
                break
            excerpt_limit = min(max_excerpt_chars, remaining)
            payload = record.to_payload(score=score, max_excerpt_chars=excerpt_limit)
            used += len(payload["content_excerpt"])
            payloads.append(payload)
        return payloads


def checksum_file(path: str | Path) -> str:
    """Return sha256 checksum for an artifact."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_memory_records(
    *,
    project_id: str,
    chapter_number: int,
    chapter_path: str,
    chapter_content: str,
    summary: str,
    key_events: list[str] | None = None,
    character_appearances: list[str] | None = None,
    goal_lock: str = "",
    unresolved_goals: list[str] | None = None,
    run_id: str | None = None,
    source_stage: str = "chapter.save",
) -> list[LongformMemoryRecord]:
    """Build derived memory records from a successfully saved chapter."""
    checksum = checksum_file(chapter_path)
    key_events = key_events or []
    character_appearances = character_appearances or []
    unresolved_goals = unresolved_goals or []
    records = [
        LongformMemoryRecord(
            project_id=project_id,
            run_id=run_id,
            chapter_number=chapter_number,
            memory_type="chapter_summary",
            title=f"Chapter {chapter_number} summary",
            content=summary or chapter_content[:1000],
            summary=summary,
            artifact_path=chapter_path,
            artifact_checksum=checksum,
            source_stage=source_stage,
        )
    ]
    if key_events:
        records.append(
            LongformMemoryRecord(
                project_id=project_id,
                run_id=run_id,
                chapter_number=chapter_number,
                memory_type="plot_anchor",
                title=f"Chapter {chapter_number} key events",
                content="\n".join(key_events),
                summary="; ".join(key_events[:3]),
                artifact_path=chapter_path,
                artifact_checksum=checksum,
                source_stage=source_stage,
            )
        )
    if character_appearances:
        records.append(
            LongformMemoryRecord(
                project_id=project_id,
                run_id=run_id,
                chapter_number=chapter_number,
                memory_type="character_appearance",
                title=f"Chapter {chapter_number} characters",
                content=", ".join(character_appearances),
                summary=", ".join(character_appearances[:5]),
                artifact_path=chapter_path,
                artifact_checksum=checksum,
                source_stage=source_stage,
            )
        )
    if goal_lock:
        records.append(
            LongformMemoryRecord(
                project_id=project_id,
                run_id=run_id,
                chapter_number=chapter_number,
                memory_type="goal_lock",
                title=f"Chapter {chapter_number} goal lock",
                content=goal_lock,
                summary=goal_lock[:200],
                artifact_path=chapter_path,
                artifact_checksum=checksum,
                source_stage=source_stage,
            )
        )
    if unresolved_goals:
        records.append(
            LongformMemoryRecord(
                project_id=project_id,
                run_id=run_id,
                chapter_number=chapter_number,
                memory_type="unresolved_goal",
                title=f"Chapter {chapter_number} unresolved goals",
                content="\n".join(unresolved_goals),
                summary="; ".join(unresolved_goals[:3]),
                artifact_path=chapter_path,
                artifact_checksum=checksum,
                source_stage=source_stage,
            )
        )
    return records


def create_longform_memory_store(
    project_dir: str | Path | None = None,
) -> LongformMemoryStoreProtocol | None:
    """Create a memory store according to LONGFORM_MEMORY_ENABLED."""
    mode = os.getenv("LONGFORM_MEMORY_ENABLED", "auto").strip().lower() or "auto"
    if mode == "false":
        return None
    if mode not in {"auto", "true"}:
        logger.warning("Invalid LONGFORM_MEMORY_ENABLED=%s; disabling memory", mode)
        return None

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        if project_dir is not None:
            return SQLiteLongformMemoryStore(Path(project_dir) / "longform_memory.sqlite")
        if mode == "true":
            logger.warning(
                "LONGFORM_MEMORY_ENABLED=true but DATABASE_URL and project_dir are missing"
            )
        return None

    try:
        from young_writer.scene_db.schema import check_connection, init_schema

        if not check_connection(database_url):
            if mode == "true":
                logger.warning("Longform memory database is configured but unreachable")
            return None
        init_schema(database_url)
        return PgLongformMemoryStore(database_url)
    except Exception as exc:
        logger.warning("Longform memory disabled: %s", exc)
        return None


def record_memory_after_save(
    store: LongformMemoryStoreProtocol | None,
    *,
    project_id: str,
    run_id: str | None,
    chapter_number: int,
    chapter_path: str,
    chapter_content: str,
    summary: str,
    key_events: list[str] | None,
    character_appearances: list[str] | None,
    goal_lock: str = "",
    unresolved_goals: list[str] | None = None,
) -> int:
    """Best-effort write of derived memory after canonical chapter artifacts exist."""
    if store is None:
        return 0
    records = build_memory_records(
        project_id=project_id,
        run_id=run_id,
        chapter_number=chapter_number,
        chapter_path=chapter_path,
        chapter_content=chapter_content,
        summary=summary,
        key_events=key_events,
        character_appearances=character_appearances,
        goal_lock=goal_lock,
        unresolved_goals=unresolved_goals,
    )
    return store.write_memories(records)
