"""Tests for ConfigManager."""

import json
from pathlib import Path

import pytest

from young_writer.agents.config_manager import (
    ConfigManager,
    GenerationConfig,
    LLMProviderConfig,
    NovelProject,
)
from young_writer.agents.outline_loader import OutlineLoader
from young_writer.services.story_input import STORY_INPUT_DIRNAME

COMPLETE_CHAPTER_ARTIFACT = """# 第1章

> 第1章 | 字数: 1200 | 生成时间: 2026-06-03T00:00:00

**本章概要**: 沈夜返回空间城。

**关键事件**: 无

---

正文。

*(本章完)*
"""


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

        output_dir = manager.generation.output_dir
        assert output_dir is not None
        assert str(temp_config_dir.parent / "runtime" / "projects") in output_dir
        assert (temp_config_dir.parent / "runtime" / "projects").exists()
        assert "目录测试" in output_dir
        story_input_dir = Path(output_dir) / STORY_INPUT_DIRNAME
        assert story_input_dir.exists()
        assert (story_input_dir / "chapter_plans.json").exists()
        assert (story_input_dir / "project_bible.json").exists()

    def test_existing_legacy_project_directory_is_preserved(
        self, temp_config_dir, mock_env_vars
    ):
        """Test that loaded old projects keep the legacy novels directory."""
        manager = ConfigManager(config_dir=str(temp_config_dir))
        legacy_project_dir = temp_config_dir.parent / "novels" / "旧项目_legacy001"
        legacy_project_dir.mkdir(parents=True)

        project = NovelProject(
            id="legacy001",
            title="旧项目",
            author="作者",
            genre="类型",
            outline="大纲",
        )

        manager.set_current_project(project)

        assert manager.generation.output_dir == str(legacy_project_dir.resolve())
        assert manager.generation.scripts_dir == str(
            (
                temp_config_dir.parent / "generated_scripts" / "旧项目_legacy001"
            ).resolve()
        )

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

    def test_get_project_summary_recovers_progress_from_chapter_files(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))
        project = manager.create_project(
            title="进度恢复测试",
            author="作者",
            genre="科幻",
            outline="大纲",
            world_setting="世界",
            character_intro="沈夜：主角",
            total_chapters=12,
        )

        chapters_dir = Path(manager.generation.output_dir) / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        (chapters_dir / "ch001_第1章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT, encoding="utf-8"
        )
        (chapters_dir / "ch007_第7章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT.replace("# 第1章", "# 第7章").replace(
                "> 第1章 |", "> 第7章 |"
            ),
            encoding="utf-8",
        )
        manager.current_project.current_chapter = 0

        summary = manager.get_project_summary()

        assert summary["current_chapter"] == 7
        assert summary["progress_percent"] == pytest.approx(7 / 12 * 100)
        reloaded = json.loads(
            (temp_config_dir / f"project_{project.id}.json").read_text(encoding="utf-8")
        )
        assert reloaded["current_chapter"] == 7

    def test_get_project_summary_ignores_incomplete_chapter_files(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))
        project = manager.create_project(
            title="进度恢复测试",
            author="作者",
            genre="科幻",
            outline="大纲",
            total_chapters=12,
        )

        chapters_dir = Path(manager.generation.output_dir) / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        (chapters_dir / "ch001_第1章.md").write_text(
            COMPLETE_CHAPTER_ARTIFACT, encoding="utf-8"
        )
        (chapters_dir / "ch007_第7章.md").write_text("# 第7章\n", encoding="utf-8")
        manager.current_project.current_chapter = 0

        summary = manager.get_project_summary()

        assert summary["current_chapter"] == 1
        reloaded = json.loads(
            (temp_config_dir / f"project_{project.id}.json").read_text(encoding="utf-8")
        )
        assert reloaded["current_chapter"] == 1

    def test_create_project_materializes_seed_outline_files(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="深渊归航",
            author="作者",
            genre="科幻修真",
            outline="沈夜带着异质核心归来。调查母舰失踪真相。拯救濒临坠毁的空间城。",
            world_setting="世界以星舰航道和空间城为核心秩序。深渊航道是危险禁区。",
            character_intro="沈夜：领航员。顾砚青：工程师。闻岚：猎航队指挥官。",
            total_chapters=3,
        )

        outline_dir = Path(manager.generation.output_dir) / "outline"
        outline_file = outline_dir / "第1卷详细章节规划.md"
        assert outline_file.exists()

        loader = OutlineLoader(str(outline_dir))
        chapter_outline = loader.get_chapter_outline(1)

        assert chapter_outline is not None
        assert chapter_outline["title"] == "第1章"
        assert "沈夜带着异质核心归来" in chapter_outline["summary"]
        assert chapter_outline["realm"] == "科幻修真"
        project_file = temp_config_dir / f"project_{project.id}.json"
        assert project_file.exists()

    def test_outline_loader_prefers_structured_chapter_plan_json(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))
        manager.create_project(
            title="结构化计划测试",
            author="作者",
            genre="科幻修真",
            outline="沈夜调查深渊航道真相。",
            world_setting="空间城与深渊航道构成主要舞台。",
            character_intro="沈夜：主角。顾砚青：工程师。",
            total_chapters=3,
        )

        output_dir = Path(manager.generation.output_dir)
        chapter_plans_file = output_dir / STORY_INPUT_DIRNAME / "chapter_plans.json"
        chapter_plans = json.loads(chapter_plans_file.read_text(encoding="utf-8"))
        chapter_plans[0]["title"] = "第1章：结构化标题"
        chapter_plans[0]["summary"] = "结构化计划要求沈夜先回到空间城再追查异质核心。"
        chapter_plans_file.write_text(
            json.dumps(chapter_plans, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        loader = OutlineLoader(str(output_dir / "outline"))
        outline = loader.get_chapter_outline(1)

        assert outline is not None
        assert outline["title"] == "第1章：结构化标题"
        assert "沈夜先回到空间城" in outline["summary"]

    def test_seed_outline_materialization_ignores_non_plan_markdown(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))

        project = manager.create_project(
            title="旁路文档测试",
            author="作者",
            genre="科幻修真",
            outline="沈夜归来。",
            world_setting="空间城。",
            character_intro="沈夜：主角",
            total_chapters=4,
        )

        outline_dir = Path(manager.generation.output_dir) / "outline"
        for file in outline_dir.glob("第*卷详细章节规划.md"):
            file.unlink()
        (outline_dir / "README.md").write_text("notes", encoding="utf-8")

        manager.set_current_project(project)

        assert (outline_dir / "第1卷详细章节规划.md").exists()

    def test_seed_outline_materialization_regenerates_plan_markdown_from_canonical_json(
        self, temp_config_dir, mock_env_vars
    ):
        manager = ConfigManager(config_dir=str(temp_config_dir))
        project = manager.create_project(
            title="canonical export",
            author="作者",
            genre="科幻修真",
            outline="沈夜守住空间城，再调查母舰失踪真相。",
            world_setting="空间城与深渊航道构成主要舞台。",
            character_intro="沈夜：主角。顾砚青：工程师。",
            total_chapters=3,
        )

        outline_dir = Path(manager.generation.output_dir) / "outline"
        outline_file = outline_dir / "第1卷详细章节规划.md"
        outline_file.write_text("人为修改的 markdown 计划", encoding="utf-8")

        manager.set_current_project(project)

        refreshed = outline_file.read_text(encoding="utf-8")
        assert "人为修改" not in refreshed
        assert "| 001 | 第1章 |" in refreshed

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
        assert set(config.providers) == {"kimi", "doubao", "minimax", "deepseek"}
        assert isinstance(config.providers["kimi"], LLMProviderConfig)
        assert config.providers["deepseek"].model_name == "deepseek-v4-flash"

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


class TestConfigDiagnostics:
    """Test non-secret integration diagnostics."""

    def test_diagnostics_reports_missing_optional_integrations_without_secrets(
        self, temp_config_dir, mock_env_vars, monkeypatch
    ):
        for key in [
            "KIMI_API_KEY",
            "DEEPSEEK_API_KEY",
            "FIRECRAWL_API_KEY",
            "DATABASE_URL",
            "REDIS_URL",
            "REDIS_HOST",
            "FANQIE_BOOK_ID",
            "FANQIE_VOLUME_ID",
        ]:
            monkeypatch.delenv(key, raising=False)

        manager = ConfigManager(config_dir=str(temp_config_dir))
        manager.generation.providers["kimi"].use_cli = False
        manager.generation.providers["kimi"].api_key = ""
        diagnostics = manager.diagnose_integrations()
        serialized = json.dumps(diagnostics, ensure_ascii=False)

        assert diagnostics["kimi"] == {"configured": False, "source": "missing"}
        assert diagnostics["deepseek"] == {"configured": False, "source": "missing"}
        assert diagnostics["firecrawl"] == {"configured": False, "source": "missing"}
        assert diagnostics["postgres"] == {
            "configured": False,
            "source": "missing",
            "reachable": None,
        }
        assert diagnostics["redis"] == {
            "configured": False,
            "source": "missing",
            "reachable": None,
        }
        assert "fake-secret-value-123" not in serialized

    def test_diagnostics_reports_env_sources_without_secret_values(
        self, temp_config_dir, mock_env_vars, monkeypatch
    ):
        monkeypatch.setenv("KIMI_API_KEY", "kimi-secret-token")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-secret-token")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "firecrawl-secret-token")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@127.0.0.1:1/db")
        monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
        monkeypatch.setenv("REDIS_PORT", "1")

        manager = ConfigManager(config_dir=str(temp_config_dir))
        diagnostics = manager.diagnose_integrations()
        serialized = json.dumps(diagnostics, ensure_ascii=False)

        assert diagnostics["kimi"] == {"configured": True, "source": "env"}
        assert diagnostics["deepseek"] == {"configured": True, "source": "env"}
        assert diagnostics["firecrawl"] == {"configured": True, "source": "env"}
        assert diagnostics["postgres"]["configured"] is True
        assert diagnostics["postgres"]["source"] == "env"
        assert diagnostics["postgres"]["reachable"] in {True, False}
        assert diagnostics["redis"]["configured"] is True
        assert diagnostics["redis"]["reachable"] in {True, False}
        assert "kimi-secret-token" not in serialized
        assert "deepseek-secret-token" not in serialized
        assert "firecrawl-secret-token" not in serialized
        assert "secret@127.0.0.1" not in serialized

    def test_diagnostics_handles_malformed_redis_port(
        self, temp_config_dir, mock_env_vars, monkeypatch
    ):
        monkeypatch.setenv("REDIS_HOST", "127.0.0.1")
        monkeypatch.setenv("REDIS_PORT", "not-a-port")

        manager = ConfigManager(config_dir=str(temp_config_dir))
        diagnostics = manager.diagnose_integrations()

        assert diagnostics["redis"] == {
            "configured": True,
            "source": "env",
            "reachable": False,
        }
