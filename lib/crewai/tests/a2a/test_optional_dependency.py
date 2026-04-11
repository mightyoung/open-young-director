"""Sentinel test for optional A2A dependency."""

from __future__ import annotations

import pytest


def test_a2a_dependency_available() -> None:
    pytest.importorskip("a2a")
