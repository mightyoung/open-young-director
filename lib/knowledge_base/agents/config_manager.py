"""Configuration Manager for novel generation projects."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, ClassVar


logger = logging.getLogger(__name__)


@dataclass
class NovelProject:
    """Novel project configuration."""
    id: str
    title: str
    author: str
    genre: str = ""
    outline: str = ""
    world_setting: str = ""
    character_intro: str = ""
    current_chapter: int = 0
    total_chapters: int = 60
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    volumes: list[dict] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = datetime.now().isoformat()


@dataclass
class VolumeConfig:
    """Volume configuration."""
    volume_name: str = ""
    start_chapter: int = 1
    end_chapter: int = 60


@dataclass
class FanqieConfig:
    """Fanqie publishing configuration."""
    book_id: str = ""
    volume_id: str = ""
    author_name: str = ""
    cookies_path: str = "./cookies/fanqie_cookies.json"
    upload_delay_seconds: int = 10
    retry_times: int = 3
    enabled: bool = False


def _default_provider_settings() -> dict[str, dict[str, Any]]:
    """Return default provider profiles for the generation workspace."""
    return {
        "kimi": {
            "provider": "kimi",
            "label": "Kimi",
            "enabled": True,
            "api_key": "",
            "base_url": "https://api.kimi.com/coding/v1",
            "api_host": "",
            "model_name": "kimi-k2.5",
            "temperature": 0.7,
            "max_tokens": 8192,
            "use_cli": True,
            "system_prompt": "",
        },
        "doubao": {
            "provider": "doubao",
            "label": "Doubao",
            "enabled": True,
            "api_key": "",
            "base_url": "",
            "api_host": "https://ark.cn-beijing.volces.com/api/v3",
            "model_name": "doubao-seed-2-0-pro-260215",
            "temperature": 0.7,
            "max_tokens": 8192,
            "use_cli": False,
            "system_prompt": "",
        },
        "minimax": {
            "provider": "minimax",
            "label": "MiniMax",
            "enabled": True,
            "api_key": "",
            "base_url": "https://api.minimaxi.com/anthropic",
            "api_host": "",
            "model_name": "MiniMax-M2.7-highspeed",
            "temperature": 1.0,
            "max_tokens": 8192,
            "use_cli": False,
            "system_prompt": "",
        },
    }


@dataclass
class LLMProviderConfig:
    """Persisted profile for an LLM provider."""

    provider: str
    label: str
    enabled: bool = True
    api_key: str = ""
    base_url: str = ""
    api_host: str = ""
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 8192
    use_cli: bool = False
    system_prompt: str = ""


@dataclass
class GenerationConfig:
    """Generation configuration."""
    model_name: str = "kimi-k2.5"
    active_provider: str = "kimi"
    temperature: float = 0.7
    max_tokens: int = 8192
    chapter_word_count: int = 3000
    chapters_per_volume: int = 60
    volume_enabled: bool = False
    volumes: list[VolumeConfig] = field(default_factory=list)
    output_dir: str = "./novels"
    scripts_dir: str = "./generated_scripts"  # Separate directory for video_prompts, podcasts, etc.
    film_drama_dir: str = "./film_drama_scripts"  # Separate directory for FILM_DRAMA mode output
    providers: dict[str, LLMProviderConfig] = field(default_factory=lambda: {
        name: LLMProviderConfig(**values)
        for name, values in _default_provider_settings().items()
    })

    VOLUME_TEMPLATES: ClassVar[dict[str, dict[str, Any]]] = {
        "第一卷：废物崛起": {"chapters": 60, "theme": "废物逆袭"},  # noqa: RUF001
        "第二卷：筑基之路": {"chapters": 60, "theme": "修仙成长"},  # noqa: RUF001
        "第三卷：宗门恩怨": {"chapters": 60, "theme": "宗门斗争"},  # noqa: RUF001
        "第四卷：天下大势": {"chapters": 60, "theme": "天下纷争"},  # noqa: RUF001
    }

    def plan_volumes(self, total_chapters: int, chapters_per_volume: int | None = None) -> list[VolumeConfig]:
        """Plan volume breakdown for a novel."""
        volumes = []
        volume_names = list(self.VOLUME_TEMPLATES.keys())
        step = chapters_per_volume or self.chapters_per_volume
        current = 1
        i = 0
        while current <= total_chapters:
            name = volume_names[i] if i < len(volume_names) else f"第{i + 1}卷"
            if current > total_chapters:
                break
            end = current + step - 1
            volumes.append(VolumeConfig(
                volume_name=name,
                start_chapter=current,
                end_chapter=end
            ))
            current = end + 1
            i += 1
        return volumes


class ConfigManager:
    """Manages project configuration and state."""

    _instance = None

    def __new__(cls, config_dir: str | None = None):
        if config_dir is None and cls._instance is not None:
            return cls._instance
        instance = super().__new__(cls)
        if config_dir is None:
            cls._instance = instance
        return instance

    def __init__(self, config_dir: str | None = None):
        if hasattr(self, '_initialized'):
            return

        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.root_dir = self.config_dir.parent

        self.fanqie = FanqieConfig()
        self.generation = GenerationConfig()
        self.current_project: NovelProject | None = None
        self._initialized = True

        self._load_configs()

    def _load_configs(self):
        """Load configuration files."""
        fanqie_file = self.config_dir / "fanqie.json"
        if fanqie_file.exists():
            try:
                data = json.loads(fanqie_file.read_text(encoding="utf-8"))
                self.fanqie = FanqieConfig(**data)
            except Exception:
                logger.warning("Failed to load fanqie config from %s", fanqie_file, exc_info=True)

        gen_file = self.config_dir / "generation.json"
        if gen_file.exists():
            try:
                data = json.loads(gen_file.read_text(encoding="utf-8"))
                volumes = [VolumeConfig(**v) for v in data.get("volumes", [])]
                data["volumes"] = volumes
                data["providers"] = self._normalize_provider_configs(data)
                self.generation = GenerationConfig(**data)
            except Exception:
                logger.warning("Failed to load generation config from %s", gen_file, exc_info=True)
        self._sync_generation_provider_defaults()

        current_file = self.config_dir / "current_project.txt"
        if current_file.exists():
            project_id = current_file.read_text().strip()
            self.load_project(project_id)

    def _load_env_vars(self):
        """Load environment variables."""

    def _normalize_provider_configs(self, data: dict[str, Any]) -> dict[str, LLMProviderConfig]:
        """Merge persisted provider configs with defaults."""
        defaults = _default_provider_settings()
        raw_providers = data.get("providers", {}) if isinstance(data, dict) else {}
        normalized: dict[str, LLMProviderConfig] = {}
        for provider_name, default_values in defaults.items():
            provider_values = dict(default_values)
            incoming = raw_providers.get(provider_name, {})
            incoming_dict = incoming if isinstance(incoming, dict) else {}
            if incoming_dict:
                provider_values.update(incoming_dict)
            if provider_name == "kimi" and data.get("model_name") and not incoming_dict.get("model_name"):
                provider_values["model_name"] = data["model_name"]
            if provider_name == "kimi" and data.get("temperature") is not None and "temperature" not in incoming_dict:
                provider_values["temperature"] = data["temperature"]
            if provider_name == "kimi" and data.get("max_tokens") is not None and "max_tokens" not in incoming_dict:
                provider_values["max_tokens"] = data["max_tokens"]
            normalized[provider_name] = LLMProviderConfig(**provider_values)
        return normalized

    def _sync_generation_provider_defaults(self) -> None:
        """Keep legacy top-level generation settings aligned with the active provider."""
        providers = getattr(self.generation, "providers", {}) or {}
        if not providers:
            self.generation.providers = {
                name: LLMProviderConfig(**values)
                for name, values in _default_provider_settings().items()
            }
            providers = self.generation.providers

        active = self.generation.active_provider or "kimi"
        if active not in providers:
            active = "kimi"
            self.generation.active_provider = active

        provider = providers[active]
        self.generation.model_name = provider.model_name or self.generation.model_name
        self.generation.temperature = provider.temperature
        self.generation.max_tokens = provider.max_tokens

    def create_project(
        self,
        title: str,
        author: str,
        genre: str = "",
        outline: str = "",
        world_setting: str = "",
        character_intro: str = "",
        total_chapters: int = 60,
        llm_client: Any | None = None,
    ) -> NovelProject:
        """Create a new novel project."""
        title = title.strip() or "未命名作品"
        author = author.strip() or "AI Author"
        genre = genre.strip() or "玄幻"
        outline = outline.strip()
        world_setting = world_setting.strip()
        character_intro = character_intro.strip()

        if not outline or not world_setting or not character_intro:
            generated = self._generate_project_seed(
                title=title,
                author=author,
                genre=genre,
                total_chapters=total_chapters,
                llm_client=llm_client,
            )
            outline = outline or generated.get("outline", "")
            world_setting = world_setting or generated.get("world_setting", "")
            character_intro = character_intro or generated.get("character_intro", "")

        if not outline:
            outline = self._fallback_outline(title=title, genre=genre)
        if not world_setting:
            world_setting = self._fallback_world_setting(title=title, genre=genre)
        if not character_intro:
            character_intro = self._fallback_character_intro(
                title=title,
                genre=genre,
                author=author,
                total_chapters=total_chapters,
            )

        project_id = hashlib.sha256(
            f"{title}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        project = NovelProject(
            id=project_id,
            title=title,
            author=author,
            genre=genre,
            outline=outline,
            world_setting=world_setting,
            character_intro=character_intro,
            total_chapters=total_chapters,
            current_chapter=0,
        )

        self._save_project(project)
        self.set_current_project(project)
        return project

    def _generate_project_seed(
        self,
        title: str,
        author: str,
        genre: str,
        total_chapters: int,
        llm_client: Any | None = None,
    ) -> dict[str, str]:
        """Generate outline/world/characters for a new project."""
        client = llm_client
        if client is None:
            try:
                client = self.build_generation_llm_client()
            except Exception:
                client = None

        if client is None or not hasattr(client, "generate"):
            return {}

        prompt = f"""你是资深中文网文策划。请根据以下信息直接输出严格 JSON，不要输出额外解释。

题目: {title}
作者: {author}
题材: {genre}
计划章节数: {total_chapters}

返回格式:
{{
  "outline": "一句话或一段话的故事大纲",
  "world_setting": "世界观设定，包含力量体系/核心规则/氛围",
  "character_intro": {{
    "title": "作品标题",
    "tagline": "一句能抓住读者的宣传语",
    "synopsis": "200字左右简介",
    "tags": ["标签1", "标签2"],
    "protagonist": "主角简介",
    "supporting_characters": ["重要配角1", "重要配角2"]
  }}
}}
"""
        try:
            raw = client.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=2000,
            )
        except Exception as exc:
            logger.warning("Auto-generation of project seed failed: %s", exc)
            return {}

        return self._parse_project_seed(raw)

    def _parse_project_seed(self, raw: str) -> dict[str, str]:
        """Parse a JSON response into normalized project seed fields."""
        if not raw:
            return {}

        text = raw.strip()
        if not text:
            return {}

        data: dict[str, Any] | None = None
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            match = re.search(r"\{.*\}", text, flags=re.S)
            if match:
                try:
                    loaded = json.loads(match.group(0))
                    if isinstance(loaded, dict):
                        data = loaded
                except Exception:
                    data = None

        if not data:
            return {}

        result: dict[str, str] = {}
        outline = data.get("outline")
        if isinstance(outline, str) and outline.strip():
            result["outline"] = outline.strip()

        world_setting = data.get("world_setting")
        if isinstance(world_setting, str) and world_setting.strip():
            result["world_setting"] = world_setting.strip()

        character_intro = data.get("character_intro")
        if isinstance(character_intro, dict):
            result["character_intro"] = json.dumps(character_intro, ensure_ascii=False, indent=2)
        elif isinstance(character_intro, str) and character_intro.strip():
            result["character_intro"] = character_intro.strip()

        return result

    def _fallback_outline(self, title: str, genre: str) -> str:
        """Build a deterministic fallback outline."""
        return f"{title}以{genre}为背景，讲述主角从边缘处境中一步步崛起、揭开真相并改写命运的故事。"

    def _fallback_world_setting(self, title: str, genre: str) -> str:
        """Build a deterministic fallback world setting."""
        return (
            f"《{title}》的世界观基于{genre}展开，"
            "以修行、势力、资源争夺与命运反转为核心规则，"
            "强调层级成长、阵营冲突和持续升级的压力感。"
        )

    def _fallback_character_intro(
        self,
        title: str,
        genre: str,
        author: str,
        total_chapters: int,
    ) -> str:
        """Build a deterministic fallback character profile JSON."""
        synopsis = f"一部以{genre}展开的长篇故事，主角将在{total_chapters}章的篇幅里完成逆袭与蜕变。"
        payload = {
            "title": title,
            "tagline": f"在{genre}的世界里，命运从不只给一次机会。",
            "synopsis": synopsis,
            "tags": [genre, "成长", "逆袭", "热血"],
            "protagonist": f"一位由弱转强的主角，带着{author}式叙事中的情绪张力向前推进。",
            "supporting_characters": ["亦正亦邪的前辈", "立场复杂的对手", "承担信息推进的伙伴"],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _save_project(self, project: NovelProject):
        """Save project to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        project.updated_at = datetime.now().isoformat()
        project_file = self.config_dir / f"project_{project.id}.json"
        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(asdict(project), f, ensure_ascii=False, indent=2)

    def load_project(self, project_id: str) -> NovelProject | None:
        """Load project from disk."""
        project_file = self.config_dir / f"project_{project_id}.json"
        if not project_file.exists():
            return None

        try:
            data = json.loads(project_file.read_text(encoding="utf-8"))
            self.current_project = NovelProject(**data)
            # Also set up output_dir and scripts_dir
            self.set_current_project(self.current_project)
            return self.current_project
        except Exception:
            logger.warning("Failed to load project config from %s", project_file, exc_info=True)
            return None

    def set_current_project(self, project: NovelProject):
        """Set current active project."""
        self.current_project = project
        self.config_dir.mkdir(parents=True, exist_ok=True)
        current_file = self.config_dir / "current_project.txt"
        current_file.write_text(project.id)

        project_slug = project.title.replace("/", "-")

        # Novel chapters stored in: lib/knowledge_base/novels/{project_title}/
        # or lib/knowledge_base/novels/{project_title}_{project_id}/ when the
        # title directory does not already exist.
        novel_root = self.root_dir / "novels"
        novel_dir = novel_root / f"{project_slug}_{project.id}"
        novel_dir.mkdir(parents=True, exist_ok=True)
        self.generation.output_dir = str(novel_dir)

        # Generated scripts (video_prompts, podcasts) stored alongside the novel directory pattern.
        scripts_root = self.root_dir / "generated_scripts"
        scripts_dir = scripts_root / f"{project_slug}_{project.id}"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        self.generation.scripts_dir = str(scripts_dir)

        # FILM_DRAMA mode output stored alongside the novel directory pattern.
        film_drama_root = self.root_dir / "film_drama_scripts"
        film_drama_dir = film_drama_root / f"{project_slug}_{project.id}"
        film_drama_dir.mkdir(parents=True, exist_ok=True)
        self.generation.film_drama_dir = str(film_drama_dir)

    def update_project_progress(self, chapter: int):
        """Update current chapter progress."""
        if not self.current_project:
            return

        self.current_project.current_chapter = chapter
        self._save_project(self.current_project)

    def update_project_metadata(self, updates: dict[str, Any]):
        """Merge metadata into current project and persist."""
        if not self.current_project:
            return
        self.current_project.metadata.update(updates)
        self._save_project(self.current_project)

    def get_project_summary(self) -> dict[str, Any]:
        """Get project summary for display."""
        if not self.current_project:
            return {"status": "no_project"}

        p = self.current_project
        progress = (p.current_chapter / p.total_chapters * 100) if p.total_chapters > 0 else 0

        return {
            "status": "ok",
            "title": p.title,
            "author": p.author,
            "genre": p.genre,
            "current_chapter": p.current_chapter,
            "total_chapters": p.total_chapters,
            "progress_percent": progress,
            "metadata": p.metadata,
        }

    def configure_fanqie(
        self,
        book_id: str = "",
        volume_id: str = "",
        author_name: str = "",
        upload_delay: int = 10,
    ):
        """Configure Fanqie publishing."""
        self.fanqie.book_id = book_id
        self.fanqie.volume_id = volume_id
        self.fanqie.author_name = author_name
        self.fanqie.upload_delay_seconds = upload_delay
        self.fanqie.enabled = True

    def save_fanqie_config(self):
        """Save Fanqie config to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        fanqie_file = self.config_dir / "fanqie.json"
        with open(fanqie_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.fanqie), f, ensure_ascii=False, indent=2)

    def save_generation_config(self):
        """Save generation config to disk."""
        self._sync_generation_provider_defaults()
        self.config_dir.mkdir(parents=True, exist_ok=True)
        gen_file = self.config_dir / "generation.json"
        with open(gen_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.generation), f, ensure_ascii=False, indent=2)

    def get_provider_config(self, provider_name: str | None = None) -> LLMProviderConfig:
        """Get one configured provider profile."""
        name = (provider_name or self.generation.active_provider or "kimi").strip().lower()
        self._sync_generation_provider_defaults()
        provider = self.generation.providers.get(name)
        if provider is None:
            provider = LLMProviderConfig(**_default_provider_settings().get(name, _default_provider_settings()["kimi"]))
            self.generation.providers[name] = provider
        return provider

    def get_provider_payload(self, provider_name: str | None = None) -> dict[str, Any]:
        """Return provider profile as plain dict."""
        return asdict(self.get_provider_config(provider_name))

    def update_generation_config(
        self,
        *,
        active_provider: str | None = None,
        provider_updates: dict[str, dict[str, Any]] | None = None,
        persist: bool = True,
    ) -> None:
        """Update and optionally persist generation/provider config."""
        self._sync_generation_provider_defaults()
        if active_provider:
            normalized_provider = active_provider.strip().lower()
            self.generation.active_provider = normalized_provider
            self.generation.providers.setdefault(
                normalized_provider,
                LLMProviderConfig(
                    **_default_provider_settings().get(normalized_provider, _default_provider_settings()["kimi"])
                ),
            )

        if provider_updates:
            for provider_name, updates in provider_updates.items():
                current = self.get_provider_config(provider_name)
                for key, value in updates.items():
                    if hasattr(current, key):
                        setattr(current, key, value)

        self._sync_generation_provider_defaults()
        if persist:
            self.save_generation_config()

    def build_generation_llm_client(self, provider_name: str | None = None) -> Any:
        """Build the active text-generation client."""
        from llm.provider_factory import build_llm_client

        provider = self.get_provider_config(provider_name)
        return build_llm_client(provider.provider, asdict(provider))

    def build_provider_clients(self) -> dict[str, Any]:
        """Build the active text client and optional secondary provider clients."""
        clients: dict[str, Any] = {"text": self.build_generation_llm_client()}
        try:
            from llm.doubao_client import DoubaoClient

            doubao = self.get_provider_config("doubao")
            clients["doubao"] = DoubaoClient(
                api_key=doubao.api_key or None,
                api_host=doubao.api_host or None,
                model=doubao.model_name or None,
                temperature=doubao.temperature,
                max_tokens=doubao.max_tokens,
            )
        except Exception:
            clients["doubao"] = None
        return clients


def get_config_manager(config_dir: str | None = None) -> ConfigManager:
    """Get the global ConfigManager instance."""
    return ConfigManager(config_dir=config_dir)
