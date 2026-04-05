"""Project memory commands for persistent repository-level context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import click


PROJECT_MEMORY_RELATIVE_PATH = Path(".claude/PROJECT_MEMORY.md")


@dataclass(frozen=True)
class ProjectMemoryInfo:
    path: Path
    exists: bool


def _project_memory_path(base_dir: Path | None = None) -> Path:
    root = _repo_root(base_dir or Path.cwd())
    return (root / PROJECT_MEMORY_RELATIVE_PATH).resolve()


def _repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() or (candidate / "CLAUDE.md").exists():
            return candidate
    return current


def _template_content() -> str:
    return """# Project Memory

This file stores repository-level preferences and durable working agreements.

## Current Facts

- This repo is a crewAI-based content generation system for novels, blogs, podcasts, scripts, and short drama.
- Novel is the most stateful pipeline and uses `status`, `tasks`, and `resume-content` for control flow.
- Output directories should be the source of truth for `result.json`, `summary.md`, and stage state files.
- Prefer explicit, user-visible control planes over hidden log-only state.

## Working Agreements

- Keep CLI contract and help text aligned with real behavior.
- Favor file-backed, inspectable state for long-running workflows.
- Treat partial outputs as first-class results with clear next actions.

## Notes

- Add durable project-specific facts here when they should survive across sessions.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _memory_info() -> ProjectMemoryInfo:
    path = _project_memory_path()
    return ProjectMemoryInfo(path=path, exists=path.exists())


@click.group(name="project-memory")
def project_memory() -> None:
    """Inspect and update repository-level project memory."""


@project_memory.command(name="init")
@click.option("--force", is_flag=True, help="Overwrite the current project memory file.")
def init_project_memory(force: bool) -> None:
    """Initialize the project memory file if it does not exist."""
    info = _memory_info()
    if info.exists and not force:
        click.echo(f"ℹ️ 已存在: {info.path}")
        raise click.Abort()

    _write(info.path, _template_content())
    click.echo(f"✅ 已初始化项目记忆: {info.path}")


@project_memory.command(name="show")
def show_project_memory() -> None:
    """Display the current project memory file."""
    info = _memory_info()
    if not info.exists:
        click.echo(f"❌ 未找到项目记忆文件: {info.path}", err=True)
        click.echo("   先运行 `crewai project-memory init` 创建文件。", err=True)
        raise click.Abort()

    click.echo(f"📚 项目记忆: {info.path}")
    click.echo(_read(info.path))


@project_memory.command(name="add")
@click.argument("entry")
@click.option("--section", default="Notes", show_default=True, help="Section name to append under.")
def add_project_memory(entry: str, section: str) -> None:
    """Append a durable note to the project memory file."""
    info = _memory_info()
    if not info.exists:
        _write(info.path, _template_content())

    content = _read(info.path)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = f"## {section}"
    note = f"- {entry} ({timestamp})"

    if header not in content:
        content = content.rstrip() + f"\n\n{header}\n\n{note}\n"
    else:
        lines = content.splitlines()
        updated: list[str] = []
        inserted = False
        in_target_section = False
        for line in lines:
            updated.append(line)
            if line.strip() == header:
                in_target_section = True
                continue
            if in_target_section and line.startswith("## ") and line.strip() != header:
                if not inserted:
                    updated.insert(len(updated) - 1, note)
                    inserted = True
                in_target_section = False
        if in_target_section and not inserted:
            updated.append(note)
        content = "\n".join(updated).rstrip() + "\n"

    _write(info.path, content)
    click.echo(f"✅ 已写入项目记忆: {entry}")
