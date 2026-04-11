"""Sentinel test for optional Qdrant dependency."""

from __future__ import annotations

import pytest


def test_qdrant_dependency_available() -> None:
    pytest.importorskip("qdrant_client")
