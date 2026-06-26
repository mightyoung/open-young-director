"""Tests for scene database configuration behavior."""

import pytest

from young_writer.scene_db.schema import check_connection, get_database_url


def test_get_database_url_requires_explicit_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        get_database_url()


def test_check_connection_returns_false_when_database_url_missing(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert check_connection() is False
