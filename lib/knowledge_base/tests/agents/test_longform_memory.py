"""Tests for derived longform memory."""

from young_writer.agents.longform_memory import (
    InMemoryLongformMemoryStore,
    build_memory_records,
    create_longform_memory_store,
    record_memory_after_save,
)


def test_build_memory_records_include_provenance(temp_project_dir):
    chapter_path = temp_project_dir / "ch001.md"
    chapter_path.write_text("chapter text", encoding="utf-8")

    records = build_memory_records(
        project_id="project-1",
        run_id="run-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        chapter_content="chapter text",
        summary="summary",
        key_events=["event"],
        character_appearances=["Lin"],
        goal_lock="hold the gate",
        unresolved_goals=["find the relic"],
    )

    assert {record.memory_type for record in records} == {
        "chapter_summary",
        "plot_anchor",
        "character_appearance",
        "goal_lock",
        "unresolved_goal",
    }
    assert all(record.artifact_path == str(chapter_path) for record in records)
    assert all(record.artifact_checksum for record in records)
    assert all(record.source_stage == "chapter.save" for record in records)


def test_in_memory_retrieval_honors_top_k_and_budget(temp_project_dir):
    chapter_path = temp_project_dir / "ch001.md"
    chapter_path.write_text("chapter text", encoding="utf-8")
    store = InMemoryLongformMemoryStore()
    records = build_memory_records(
        project_id="project-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        chapter_content="x" * 1000,
        summary="s" * 1000,
        key_events=["event"],
        character_appearances=["Lin"],
    )
    store.write_memories(records)

    results = store.retrieve(
        project_id="project-1",
        chapter_number=2,
        top_k=2,
        max_excerpt_chars=30,
        total_budget=50,
    )

    assert len(results) == 2
    assert sum(len(item["content_excerpt"]) for item in results) <= 50
    assert all("artifact_path" in item for item in results)
    assert all("artifact_checksum" in item for item in results)


def test_in_memory_retrieval_uses_query_similarity(temp_project_dir):
    chapter_path = temp_project_dir / "ch001.md"
    chapter_path.write_text("chapter text", encoding="utf-8")
    store = InMemoryLongformMemoryStore()
    records = build_memory_records(
        project_id="project-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        chapter_content="river archive clue",
        summary="river archive clue",
        key_events=["mountain duel"],
        character_appearances=[],
    )
    store.write_memories(records)

    results = store.retrieve(project_id="project-1", chapter_number=2, query="river archive", top_k=1)

    assert results[0]["memory_type"] == "chapter_summary"
    assert results[0]["score"] > 0


def test_record_memory_after_save_skips_when_disabled(temp_project_dir):
    chapter_path = temp_project_dir / "ch001.md"
    chapter_path.write_text("chapter text", encoding="utf-8")

    assert (
        record_memory_after_save(
            None,
            project_id="project-1",
            run_id=None,
            chapter_number=1,
            chapter_path=str(chapter_path),
            chapter_content="chapter text",
            summary="summary",
            key_events=[],
            character_appearances=[],
        )
        == 0
    )


def test_create_memory_store_respects_disabled_toggle(monkeypatch):
    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:1/db")

    assert create_longform_memory_store() is None


def test_create_memory_store_auto_skips_missing_database(monkeypatch):
    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "auto")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert create_longform_memory_store() is None


def test_create_memory_store_auto_uses_project_local_sqlite(monkeypatch, temp_project_dir):
    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "auto")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    store = create_longform_memory_store(project_dir=temp_project_dir)

    assert store is not None
    assert (temp_project_dir / "longform_memory.sqlite").exists()


def test_sqlite_memory_store_persists_and_retrieves_earlier_records(
    monkeypatch, temp_project_dir
):
    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "auto")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    chapter_path = temp_project_dir / "ch001.md"
    chapter_path.write_text("chapter text", encoding="utf-8")
    store = create_longform_memory_store(project_dir=temp_project_dir)
    records = build_memory_records(
        project_id="project-1",
        chapter_number=1,
        chapter_path=str(chapter_path),
        chapter_content="river archive clue",
        summary="river archive clue",
        key_events=["mountain duel"],
        character_appearances=["Lin"],
    )

    assert store.write_memories(records) == len(records)
    results = store.retrieve(
        project_id="project-1",
        chapter_number=2,
        query="river archive",
        top_k=2,
    )
    future_results = store.retrieve(project_id="project-1", chapter_number=1)

    assert results
    assert all(item["chapter_number"] == 1 for item in results)
    assert future_results == []


def test_create_memory_store_auto_skips_unreachable_database(monkeypatch):
    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "auto")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:1/db")
    monkeypatch.setattr("scene_db.schema.check_connection", lambda _url: False)

    assert create_longform_memory_store() is None


def test_create_memory_store_auto_uses_reachable_database(monkeypatch):
    created = {}

    class FakePgStore:
        def __init__(self, database_url):
            created["database_url"] = database_url

    monkeypatch.setenv("LONGFORM_MEMORY_ENABLED", "auto")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:5432/db")
    monkeypatch.setattr("scene_db.schema.check_connection", lambda _url: True)
    monkeypatch.setattr("scene_db.schema.init_schema", lambda _url: True)
    monkeypatch.setattr("young_writer.agents.longform_memory.PgLongformMemoryStore", FakePgStore)

    store = create_longform_memory_store()

    assert isinstance(store, FakePgStore)
    assert created["database_url"] == "postgresql://user:secret@127.0.0.1:5432/db"
