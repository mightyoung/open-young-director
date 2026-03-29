"""Configuration Manager for novel generation projects."""

import json
import hashlib
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


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
    metadata: Dict[str, Any] = field(default_factory=dict)
    volumes: List[Dict] = field(default_factory=list)

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


@dataclass
class GenerationConfig:
    """Generation configuration."""
    model_name: str = "kimi-k2.5"
    temperature: float = 0.7
    max_tokens: int = 8192
    chapter_word_count: int = 3000
    volume_enabled: bool = False
    volumes: List[VolumeConfig] = field(default_factory=list)
    output_dir: str = "./novels"
    scripts_dir: str = "./generated_scripts"  # Separate directory for video_prompts, podcasts, etc.
    film_drama_dir: str = "./film_drama_scripts"  # Separate directory for FILM_DRAMA mode output

    VOLUME_TEMPLATES = {
        "第一卷：废物崛起": {"chapters": 60, "theme": "废物逆袭"},
        "第二卷：筑基之路": {"chapters": 60, "theme": "修仙成长"},
        "第三卷：宗门恩怨": {"chapters": 60, "theme": "宗门斗争"},
        "第四卷：天下大势": {"chapters": 60, "theme": "天下纷争"},
    }

    def plan_volumes(self, total_chapters: int, chapters_per_volume: int = 60) -> List[VolumeConfig]:
        """Plan volume breakdown for a novel."""
        volumes = []
        volume_names = list(self.VOLUME_TEMPLATES.keys())
        current = 1
        for i, name in enumerate(volume_names):
            if current > total_chapters:
                break
            end = min(current + chapters_per_volume - 1, total_chapters)
            volumes.append(VolumeConfig(
                volume_name=name,
                start_chapter=current,
                end_chapter=end
            ))
            current = end + 1
        return volumes


class ConfigManager:
    """Manages project configuration and state."""

    _instance = None

    def __new__(cls, config_dir: str = None):
        if cls._instance is not None:
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance

    def __init__(self, config_dir: str = None):
        if hasattr(self, '_initialized'):
            return

        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.fanqie = FanqieConfig()
        self.generation = GenerationConfig()
        self.current_project: Optional[NovelProject] = None
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
                pass

        gen_file = self.config_dir / "generation.json"
        if gen_file.exists():
            try:
                data = json.loads(gen_file.read_text(encoding="utf-8"))
                volumes = [VolumeConfig(**v) for v in data.get("volumes", [])]
                data["volumes"] = volumes
                self.generation = GenerationConfig(**data)
            except Exception:
                pass

        current_file = self.config_dir / "current_project.txt"
        if current_file.exists():
            project_id = current_file.read_text().strip()
            self.load_project(project_id)

    def _load_env_vars(self):
        """Load environment variables."""
        pass

    def create_project(
        self,
        title: str,
        author: str,
        genre: str = "",
        outline: str = "",
        world_setting: str = "",
        character_intro: str = "",
        total_chapters: int = 60,
    ) -> NovelProject:
        """Create a new novel project."""
        project_id = hashlib.md5(f"{title}{datetime.now().isoformat}".encode()).hexdigest()[:12]

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

    def _save_project(self, project: NovelProject):
        """Save project to disk."""
        project.updated_at = datetime.now().isoformat()
        project_file = self.config_dir / f"project_{project.id}.json"
        with open(project_file, "w", encoding="utf-8") as f:
            json.dump(asdict(project), f, ensure_ascii=False, indent=2)

    def load_project(self, project_id: str) -> Optional[NovelProject]:
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
            return None

    def set_current_project(self, project: NovelProject):
        """Set current active project."""
        self.current_project = project
        current_file = self.config_dir / "current_project.txt"
        current_file.write_text(project.id)

        # Novel chapters stored in: lib/knowledge_base/novels/{project_title}/
        novel_dir = Path("lib/knowledge_base/novels") / project.title.replace("/", "-")
        novel_dir.mkdir(parents=True, exist_ok=True)
        self.generation.output_dir = str(novel_dir)

        # Generated scripts (video_prompts, podcasts) stored in: lib/knowledge_base/generated_scripts/{project_title}/
        scripts_dir = Path("lib/knowledge_base/generated_scripts") / project.title.replace("/", "-")
        scripts_dir.mkdir(parents=True, exist_ok=True)
        self.generation.scripts_dir = str(scripts_dir)

        # FILM_DRAMA mode output stored in: lib/knowledge_base/film_drama_scripts/{project_title}/
        film_drama_dir = Path("lib/knowledge_base/film_drama_scripts") / project.title.replace("/", "-")
        film_drama_dir.mkdir(parents=True, exist_ok=True)
        self.generation.film_drama_dir = str(film_drama_dir)

    def update_project_progress(self, chapter: int):
        """Update current chapter progress."""
        if not self.current_project:
            return

        self.current_project.current_chapter = chapter
        self._save_project(self.current_project)

    def get_project_summary(self) -> Dict[str, Any]:
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
        fanqie_file = self.config_dir / "fanqie.json"
        with open(fanqie_file, "w", encoding="utf-8") as f:
            json.dump(asdict(self.fanqie), f, ensure_ascii=False, indent=2)


def get_config_manager(config_dir: str = None) -> ConfigManager:
    """Get the global ConfigManager instance."""
    return ConfigManager(config_dir=config_dir)
