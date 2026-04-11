"""Sentinel test for optional Google GenAI dependency."""

from __future__ import annotations

import pytest


def test_google_genai_dependency_available() -> None:
    pytest.importorskip("google.genai")
