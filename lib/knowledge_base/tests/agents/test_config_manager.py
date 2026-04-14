"""Tests for ConfigManager."""

import json

import pytest

from agents.config_manager import (
    ConfigManager,
    GenerationConfig,
    LLMProviderConfig,
    NovelProject,
)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Disable loading of .env file for all tests."""
    monkeypatch.setattr(ConfigManager, "_load_env_vars", lambda self: None)


class TestConfigManagerInit:
    """Test ConfigManager initialization."""

    def test_init_creates_config_dir(self, temp_config_dir, mock_env_vars):
        """Test that initialization creates config directory."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        assert manager.config_dir == temp_config_dir
        assert manager.config_dir.exists()

    def test_init_loads_fanqie_config(self, temp_config_dir, mock_env_vars):
        """Test that initialization loads fanqie config."""
        # Pre-create fanqie config file
        fanqie_data = {
            "book_id": "test_book_123",
            "volume_id": "test_vol_456",
            "author_name": "测试作者",
            "cookies_path": "./cookies/fanqie_cookies.json",
            "upload_delay_seconds": 10,
            "retry_times": 5,
            "enabled": True,
        }
        fanqie_file = temp_config_dir / "fanqie.json"
        fanqie_file.write_text(json.dumps(fanqie_data, ensure_ascii=False), encoding="utf-8")

        manager = ConfigManager(config_dir=str(temp_config_dir))

        assert manager.fanqie.book_id == "test_book_123"
        assert manager.fanqie.upload_delay_seconds == 10
        assert manager.fanqie.enabled is True

    def test_init_loads_generation_config(self, temp_config_dir, mock_env_vars):
        """Test that initialization loads generation config."""
        # Pre-create generation config file
        gen_data = {
            "model_name": "kimi-k2.5",
            "active_provider": "minimax",
            "temperature": 0.8,
            "max_tokens": 16384,
            "chapter_word_count": 5000,
            "volume_enabled": True,
            "volumes": [],
            "providers": {
                "minimax": {
                    "provider": "minimax",
                    "label": "MiniMax",
                    "model_name": "MiniMax-M2.5",
                    "temperature": 0.9,
                    "max_tokens": 12000,
                }
            },
        }
        gen_file = temp_config_dir / "generation.json"
        gen_file.write_text(json.dumps(gen_data, ensure_ascii=False), encoding="utf-8")

        manager = ConfigManager(config_dir=str(temp_config_dir))

        assert manager.generation.active_provider == "minimax"
        assert manager.generation.model_name == "MiniMax-M2.5"
        assert manager.generation.temperature == 0.9
        assert manager.generation.max_tokens == 12000


class TestCreateProject:
    """Test create_project functionality."""

    def test_create_project_basic(self, temp_config_dir, mock_env_vars):
        """Test creating a basic project."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="太古魔帝传",
            author="测试作者",
            genre="玄幻修仙",
            outline="废物少年逆袭成帝的故事",
            world_setting="修真世界",
            character_intro="主角林轩",
            total_chapters=240,
        )

        assert project is not None
        assert isinstance(project, NovelProject)
        assert project.title == "太古魔帝传"
        assert project.author == "测试作者"
        assert project.genre == "玄幻修仙"
        assert project.total_chapters == 240
        assert project.id is not None
        assert len(project.id) > 0

    def test_create_project_saves_to_disk(self, temp_config_dir, mock_env_vars):
        """Test that create_project saves project to disk."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="测试小说",
            author="作者",
            genre="玄幻",
            outline="大纲",
        )

        # Check project file exists
        project_file = temp_config_dir / f"project_{project.id}.json"
        assert project_file.exists()

        data = json.loads(project_file.read_text(encoding="utf-8"))
        assert data["title"] == "测试小说"
        assert data["author"] == "作者"

    def test_create_project_sets_current(self, temp_config_dir, mock_env_vars):
        """Test that create_project sets it as current project."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="当前项目",
            author="作者",
            genre="类型",
            outline="大纲",
        )

        assert manager.current_project is not None
        assert manager.current_project.id == project.id

    def test_create_project_creates_directories(self, temp_config_dir, mock_env_vars):
        """Test that create_project creates novel directories."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        manager.create_project(
            title="目录测试",
            author="作者",
            genre="类型",
            outline="大纲",
        )

        # output_dir template is set (expanded when set_current_project is called)
        assert manager.generation.output_dir is not None

    def test_create_project_generates_id(self, temp_config_dir, mock_env_vars):
        """Test that project ID is generated correctly."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project1 = manager.create_project(
            title="小说1", author="作者", genre="类型", outline="大纲"
        )
        project2 = manager.create_project(
            title="小说2", author="作者", genre="类型", outline="大纲"
        )

        # IDs should be different
        assert project1.id != project2.id
        # IDs should be 12 characters (MD5 hash truncated)
        assert len(project1.id) == 12

    def test_create_project_auto_fills_missing_fields(self, temp_config_dir, mock_env_vars):
        """Test that empty project fields are auto-generated."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        fake_client = type(
            "FakeClient",
            (),
            {
                "generate": lambda self, messages, temperature=None, max_tokens=None: (
                    '{"outline":"自动大纲","world_setting":"自动世界观","character_intro":{"title":"自动角色","tagline":"一句话","synopsis":"简介","tags":["玄幻"],"protagonist":"主角","supporting_characters":["配角"]}}'
                )
            },
        )()

        project = manager.create_project(
            title="自动生成测试",
            author="测试作者",
            genre="玄幻修仙",
            outline="",
            world_setting="",
            character_intro="",
            total_chapters=120,
            llm_client=fake_client,
        )

        assert project.outline == "自动大纲"
        assert project.world_setting == "自动世界观"
        assert "自动角色" in project.character_intro

    def test_create_project_keeps_user_provided_fields(self, temp_config_dir, mock_env_vars):
        """Test that provided project fields are not overwritten."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        fake_client = type(
            "FakeClient",
            (),
            {
                "generate": lambda self, messages, temperature=None, max_tokens=None: (
                    '{"outline":"不应覆盖","world_setting":"不应覆盖","character_intro":{"title":"不应覆盖"}}'
                )
            },
        )()

        project = manager.create_project(
            title="保留测试",
            author="测试作者",
            genre="玄幻",
            outline="手写大纲",
            world_setting="手写世界观",
            character_intro="手写人物设定",
            total_chapters=80,
            llm_client=fake_client,
        )

        assert project.outline == "手写大纲"
        assert project.world_setting == "手写世界观"
        assert project.character_intro == "手写人物设定"


class TestLoadProject:
    """Test load_project functionality."""

    def test_load_project_basic(self, temp_config_dir, mock_env_vars):
        """Test loading an existing project."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        # First create a project
        original = manager.create_project(
            title="待加载小说",
            author="作者",
            genre="类型",
            outline="大纲",
            total_chapters=100,
        )
        original_id = original.id

        # Create new manager and load
        manager2 = ConfigManager(config_dir=str(temp_config_dir))
        loaded = manager2.load_project(original_id)

        assert loaded is not None
        assert loaded.title == "待加载小说"
        assert loaded.author == "作者"
        assert loaded.total_chapters == 100

    def test_load_project_not_found(self, temp_config_dir, mock_env_vars):
        """Test loading a non-existent project returns None."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        result = manager.load_project("non_existent_id_123")
        assert result is None

    def test_load_project_corrupted_file(self, temp_config_dir, mock_env_vars):
        """Test loading a corrupted project file returns None."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        # Create a corrupted project file
        project_file = temp_config_dir / "project_corrupted.json"
        project_file.write_text("{ invalid json }", encoding="utf-8")

        result = manager.load_project("corrupted")
        assert result is None


class TestProjectProgress:
    """Test project progress tracking."""

    def test_update_project_progress(self, temp_config_dir, mock_env_vars):
        """Test updating project progress."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="进度测试",
            author="作者",
            genre="类型",
            outline="大纲",
        )

        # Update progress
        manager.update_project_progress(chapter=50)

        assert manager.current_project.current_chapter == 50

        # Reload and verify persistence
        manager2 = ConfigManager(config_dir=str(temp_config_dir))
        manager2.load_project(project.id)
        assert manager2.current_project.current_chapter == 50

    def test_update_progress_no_project(self, temp_config_dir, mock_env_vars):
        """Test updating progress with no current project does not raise."""
        manager = ConfigManager(config_dir=str(temp_config_dir))
        manager.current_project = None

        # Should not raise
        manager.update_project_progress(chapter=10)


class TestVolumeConfig:
    """Test volume configuration."""

    def test_plan_volumes_basic(self):
        """Test basic volume planning."""
        config = GenerationConfig()
        volumes = config.plan_volumes(total_chapters=240)

        assert len(volumes) == 4
        assert volumes[0].volume_name == "第一卷：废物崛起"
        assert volumes[1].volume_name == "第二卷：筑基之路"
        assert volumes[0].start_chapter == 1
        assert volumes[0].end_chapter == 60
        assert volumes[1].start_chapter == 61
        assert volumes[1].end_chapter == 120

    def test_plan_volumes_small_project(self):
        """Test volume planning for small project."""
        config = GenerationConfig()
        volumes = config.plan_volumes(total_chapters=50)

        assert len(volumes) == 1
        assert volumes[0].volume_name == "第一卷：废物崛起"
        assert volumes[0].start_chapter == 1
        assert volumes[0].end_chapter == 60

    def test_plan_volumes_large_project(self):
        """Test volume planning for large project."""
        config = GenerationConfig(chapters_per_volume=50)
        volumes = config.plan_volumes(total_chapters=300)

        assert len(volumes) == 6


class TestFanqieConfig:
    """Test Fanqie publishing configuration."""

    def test_configure_fanqie(self, temp_config_dir, mock_env_vars):
        """Test configuring Fanqie publishing."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        manager.configure_fanqie(
            book_id="fanqie_book_123",
            volume_id="fanqie_vol_456",
            author_name="番茄作者",
            upload_delay=15,
        )

        assert manager.fanqie.book_id == "fanqie_book_123"
        assert manager.fanqie.volume_id == "fanqie_vol_456"
        assert manager.fanqie.author_name == "番茄作者"
        assert manager.fanqie.upload_delay_seconds == 15
        assert manager.fanqie.enabled is True

    def test_save_fanqie_config(self, temp_config_dir, mock_env_vars):
        """Test saving Fanqie config to disk."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        manager.configure_fanqie(book_id="save_test_book")
        manager.save_fanqie_config()

        fanqie_file = temp_config_dir / "fanqie.json"
        assert fanqie_file.exists()

        data = json.loads(fanqie_file.read_text(encoding="utf-8"))
        assert data["book_id"] == "save_test_book"


class TestGetProjectSummary:
    """Test project summary functionality."""

    def test_get_summary_no_project(self, temp_config_dir, mock_env_vars):
        """Test getting summary when no project exists."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        summary = manager.get_project_summary()

        assert summary["status"] == "no_project"

    def test_get_summary_with_project(self, temp_config_dir, mock_env_vars):
        """Test getting summary with active project."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        manager.create_project(
            title="摘要测试",
            author="作者",
            genre="类型",
            outline="大纲",
            total_chapters=100,
        )
        manager.update_project_progress(chapter=25)

        summary = manager.get_project_summary()

        assert summary["status"] == "ok"
        assert summary["title"] == "摘要测试"
        assert summary["current_chapter"] == 25
        assert summary["total_chapters"] == 100
        assert summary["progress_percent"] == 25.0


class TestSetCurrentProject:
    """Test set_current_project functionality."""

    def test_set_current_project(self, temp_config_dir, mock_env_vars):
        """Test setting current project."""
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = NovelProject(
            id="manual_project",
            title="手动设置项目",
            author="作者",
            genre="类型",
            outline="大纲",
        )

        manager.set_current_project(project)

        assert manager.current_project is not None
        assert manager.current_project.id == "manual_project"
        assert "manual_project" in manager.generation.output_dir


class TestGenerationConfig:
    """Test GenerationConfig functionality."""

    def test_generation_config_defaults(self):
        """Test GenerationConfig default values."""
        config = GenerationConfig()

        assert config.model_name == "kimi-k2.5"
        assert config.active_provider == "kimi"
        assert config.temperature == 0.7
        assert config.max_tokens == 8192
        assert config.chapter_word_count == 3000
        assert config.volume_enabled is False
        assert len(config.volumes) == 0
        assert set(config.providers) == {"kimi", "doubao", "minimax"}
        assert isinstance(config.providers["kimi"], LLMProviderConfig)

    def test_volume_templates_exist(self):
        """Test that volume templates are defined."""
        templates = GenerationConfig.VOLUME_TEMPLATES

        assert len(templates) >= 4
        assert "第一卷：废物崛起" in templates


class TestProviderConfig:
    """Test provider config persistence and client creation."""

    def test_save_generation_config_persists_provider_profiles(self, temp_config_dir, mock_env_vars):
        manager = ConfigManager(config_dir=str(temp_config_dir))

        manager.update_generation_config(
            active_provider="doubao",
            provider_updates={
                "doubao": {
                    "model_name": "doubao-text-pro",
                    "temperature": 0.5,
                    "max_tokens": 4096,
                }
            },
        )

        payload = json.loads((temp_config_dir / "generation.json").read_text(encoding="utf-8"))
        assert payload["active_provider"] == "doubao"
        assert payload["providers"]["doubao"]["model_name"] == "doubao-text-pro"
        assert payload["providers"]["doubao"]["temperature"] == 0.5

    def test_build_generation_llm_client_uses_active_provider(self, temp_config_dir, mock_env_vars):
        manager = ConfigManager(config_dir=str(temp_config_dir))
        manager.update_generation_config(
            active_provider="doubao",
            provider_updates={
                "doubao": {
                    "api_key": "test-key",
                    "model_name": "doubao-text-pro",
                    "api_host": "https://ark.example.com/api/v3",
                }
            },
            persist=False,
        )

        client = manager.build_generation_llm_client()

        assert client.provider_name == "doubao"
        assert client.model_name == "doubao-text-pro"
