"""Checkpoint management for novel pipeline.

Handles atomic file I/O for:
- Chapter checkpoints (markdown with frontmatter)
- Outline checkpoints (world.md, outline.md, metadata.json)
- Result.json updates
- Visual dashboard injection (Mermaid graphs, etc.)
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from crewai.content.novel.novel_types import ChapterOutput
    from crewai.content.novel.production_bible.bible_types import ProductionBible

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages atomic checkpoint saving with integrity guards and visual dashboarding."""

    def __init__(self, config: dict, output_dir: str | None = None):
        self.config = config
        self._output_dir = output_dir
        self._cached_output_dir: str | None = None
        self._current_stage: str = "init"
        self._file_hashes: dict[str, str] = {}
        self._current_bible_obj: Optional["ProductionBible"] = None

    def set_stage(self, stage: str) -> None:
        """Set current pipeline stage."""
        self._current_stage = stage

    def bind_bible(self, bible: "ProductionBible") -> None:
        """Bind bible object for visual exporting."""
        self._current_bible_obj = bible
        # 触发一次自动导出 ART.md
        self._export_art_manifest()

    def _export_art_manifest(self) -> None:
        """物理导出 ART.md 到小说目录"""
        if self._current_bible_obj:
            content = self._current_bible_obj.export_art_manifest()
            path = Path(self.output_dir) / "ART.md"
            self.atomic_write(path, content)
            logger.info(f"Art Manifest exported to: {path}")

    @property
    def output_dir(self) -> str:
        if self._cached_output_dir: return self._cached_output_dir
        if self._output_dir:
            self._cached_output_dir = self._output_dir
        else:
            topic = self.config.get("topic", "未命名小说")
            safe_topic = "".join(c if c.isalnum() or c in "_- " else "_" for c in topic)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._cached_output_dir = f"novels/{safe_topic}_{timestamp}"
        return self._cached_output_dir

    def set_output_dir(self, output_dir: str) -> None:
        """Override the checkpoint output directory."""
        self._output_dir = output_dir
        self._cached_output_dir = output_dir

    def save_chapter_checkpoint(self, chapter_output: "ChapterOutput") -> None:
        output_dir = self.output_dir
        topic = self.config.get("topic", "未命名小说")
        chapters_dir = Path(output_dir) / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)

        chapter_num = chapter_output.chapter_num
        title = getattr(chapter_output, "title", f"第{chapter_num}章")
        safe_title = "".join(c if c.isalnum() or c in "_- " else "_" for c in title)[:50]
        chapter_file = chapters_dir / f"{int(chapter_num):03d}.{safe_title}.md"

        content = chapter_output.content if hasattr(chapter_output, "content") else str(chapter_output)
        word_count = chapter_output.word_count or len(content) // 2

        markdown_content = f"""---
title: "{title}"
chapter: {chapter_num}
novel: "{topic}"
generated_at: "{datetime.now().isoformat()}"
word_count: {word_count}
---

# {title}

{content}
"""
        previous_stage = self._current_stage
        if previous_stage == "init":
            self._current_stage = "writing"
        try:
            self.atomic_write(chapter_file, markdown_content)
            self._update_result_json(chapter_num, word_count)
        finally:
            self._current_stage = previous_stage

    def save_outline_checkpoint(self, world_data: dict, plot_data: dict, stage: str) -> None:
        output_dir = self.output_dir
        topic = self.config.get("topic", "未命名小说")
        outline_dir = Path(output_dir) / "outline"
        outline_dir.mkdir(parents=True, exist_ok=True)

        # Build visuals from Bible
        visuals_section = ""
        if self._current_bible_obj:
            mermaid = self._current_bible_obj.export_mermaid_graph()
            sentiment = self._current_bible_obj.export_sentiment_trend()
            visuals_section = f"""
## 可视化驾驶舱 (Live Dashboard)
### 角色关系拓扑图
```mermaid
{mermaid}
```

### 最近读者反馈趋势
{sentiment}
"""

        world_content = f"""# 世界观: {world_data.get('name', topic)}
{visuals_section}

## 简介
{world_data.get('description', '待补充')}

## 势力
{world_data.get('factions', '待补充')}

## 地点
{world_data.get('locations', '待补充')}

## 力量体系
{world_data.get('power_system', '待补充')}

---
生成时间: {datetime.now().isoformat()}
阶段: {stage}
"""
        self.atomic_write(outline_dir / "world.md", world_content)

        outline_content = f"""# 大纲: {world_data.get('name', topic)}

## 主线
{plot_data.get('main_strand', '待补充')}

## 分卷
{plot_data.get('volumes', '待补充')}

## 高潮点
{plot_data.get('high_points', '待补充')}

---
生成时间: {datetime.now().isoformat()}
阶段: {stage}
"""
        self.atomic_write(outline_dir / "outline.md", outline_content)

        metadata = {
            "topic": topic, "stage": stage, "generated_at": datetime.now().isoformat(),
            "world_name": world_data.get('name', '未知'), "chapter_count": 0
        }
        self.atomic_write_json(outline_dir / "metadata.json", metadata)

    def _check_permission(self, path: Path) -> None:
        parent_name = path.parent.name
        if parent_name == "outline" and self._current_stage not in ["init", "outline", "evaluation"]:
            raise PermissionError(f"Attempted to modify outline during '{self._current_stage}' stage. Outline is now READ-ONLY.")
        if parent_name == "chapters" and self._current_stage in ["init", "outline", "evaluation"]:
            raise PermissionError(f"Attempted to write chapters during '{self._current_stage}' stage. Chapters directory is locked.")

    def atomic_write(self, path: Path, content: str) -> None:
        self._check_permission(path)
        temp_fd, temp_path = tempfile.mkstemp(dir=str(path.parent))
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path): os.unlink(temp_path)
            raise e

    def atomic_write_json(self, path: Path, data: dict) -> None:
        temp_fd, temp_path = tempfile.mkstemp(suffix=".json", dir=str(path.parent))
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path): os.unlink(temp_path)
            raise e

    def _update_result_json(self, chapter_num: int, word_count: int) -> None:
        result_file = Path(self.output_dir) / "result.json"
        try:
            if result_file.exists():
                with open(result_file, "r") as f: result_data = json.load(f)
            else:
                result_data = {"topic": self.config.get("topic"), "word_count": 0, "chapters_count": 0}
            
            result_data["chapters_count"] = max(result_data.get("chapters_count", 0), chapter_num)
            result_data["word_count"] = result_data.get("word_count", 0) + word_count
            result_data["last_updated"] = datetime.now().isoformat()
            
            self.atomic_write_json(result_file, result_data)
        except Exception as e:
            logger.warning(f"Failed to update result.json: {e}")
