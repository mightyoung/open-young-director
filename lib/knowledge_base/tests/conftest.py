"""Pytest fixtures for knowledge_base tests."""

import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory that is cleaned up after the test."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_novels_dir(temp_project_dir):
    """Create a temporary novels directory for chapter storage."""
    novels_dir = temp_project_dir / "novels"
    novels_dir.mkdir(parents=True, exist_ok=True)
    return novels_dir


@pytest.fixture
def temp_config_dir(temp_project_dir):
    """Create a temporary config directory."""
    config_dir = temp_project_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_kimi_response():
    """Mock KIMI API response."""
    return {
        "content": '{"title": "测试章节", "summary": "测试概要", "key_events": ["事件1", "事件2"]}',
        "model": "moonshot-v1-8k",
        "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        "raw_response": {
            "choices": [
                {
                    "message": {
                        "content": '{"title": "测试章节", "summary": "测试概要"}'
                    }
                }
            ],
            "model": "moonshot-v1-8k",
            "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        },
    }


@pytest.fixture
def mock_kimi_client():
    """Mock KIMI client."""
    mock = MagicMock()
    mock.chat.return_value = MagicMock(
        content='{"title": "测试章节", "summary": "测试概要"}',
        model="moonshot-v1-8k",
        usage={"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        raw_response={},
    )
    return mock


@pytest.fixture
def sample_chapter_metadata():
    """Sample chapter metadata for testing."""
    return {
        "number": 1,
        "title": "废物少年",
        "word_count": 3000,
        "file_path": "/path/to/ch001.md",
        "created_at": datetime.now(),
        "generation_time": datetime.now(),
        "summary": "少年被发现是废物，被退婚",
        "key_events": ["退婚", "发现废物体质"],
        "character_appearances": ["林轩", "萧薰儿"],
    }


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "id": "test_project_001",
        "title": "太古魔帝传",
        "author": "测试作者",
        "genre": "玄幻修仙",
        "outline": "讲述一个废物少年逆袭成帝的故事",
        "world_setting": "修真世界",
        "character_intro": "主角林轩，本是废物体质",
        "current_chapter": 5,
        "total_chapters": 240,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def mock_config_manager(temp_config_dir, monkeypatch):
    """Mock ConfigManager that uses temp directory."""
    from agents.config_manager import ConfigManager
    monkeypatch.setattr(ConfigManager, "_load_env_vars", lambda self: None)
    manager = ConfigManager(config_dir=str(temp_config_dir))
    return manager
