"""Pytest configuration for pipeline memory system tests."""

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module_directly(module_name, filepath):
    """Load a module directly from file to avoid __init__.py circular imports."""
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if not spec or not spec.loader:
        raise ImportError(f"Cannot create spec for {filepath}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", autouse=True)
def _preload_modules():
    """Pre-load modules directly to avoid circular import issues."""
    # __file__ = .../lib/crewai/tests/content/novel/pipeline/conftest.py
    # Go up 4 levels to reach lib/crewai, then src
    conftest_dir = Path(__file__).parent
    tests_dir = conftest_dir.parent.parent.parent
    crewai_lib = tests_dir.parent
    src_path = crewai_lib / "src" / "crewai"
    base_path = src_path

    # Load modules in dependency order
    # ForeshadowingBoard has no special dependencies beyond standard lib
    _load_module_directly(
        "crewai.content.novel.pipeline.foreshadowing_board",
        base_path / "content" / "novel" / "pipeline" / "foreshadowing_board.py",
    )

    # DeepSeekClient for ChapterConnector
    _load_module_directly(
        "crewai.llm.deepseek_client",
        base_path / "llm" / "deepseek_client.py",
    )

    # ChapterConnector depends on DeepSeekClient
    _load_module_directly(
        "crewai.content.novel.pipeline.chapter_connector",
        base_path / "content" / "novel" / "pipeline" / "chapter_connector.py",
    )

    # ContextBuilder depends on PipelineState - load PipelineState minimally
    # For now, we'll mock PipelineState in tests
    yield
