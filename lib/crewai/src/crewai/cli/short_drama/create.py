"""crewai short_drama create — create a new short drama project.

Entry point: `crewai short_drama create "仙侠史诗" --from-novel "仙侠史诗_novel"`
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import click

from crewai.cli.short_drama._llm import ensure_output_dir
from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder


def _copy_novel_files(novel_path: Path, sd_path: Path) -> None:
    """Copy relevant files from the novel project to the short drama project."""
    # Copy chapters
    chapters_src = novel_path / "chapters"
    if chapters_src.exists():
        chapters_dst = sd_path / "chapters"
        shutil.copytree(chapters_src, chapters_dst)

    # Copy bible
    bible_src = novel_path / "bible.json"
    if bible_src.exists():
        shutil.copy2(bible_src, sd_path / "bible.json")

    # Copy pipeline_state
    state_src = novel_path / "pipeline_state.json"
    if state_src.exists():
        shutil.copy2(state_src, sd_path / "pipeline_state.json")


@click.command(name="create")
@click.argument("project_name")
@click.option(
    "--from-novel",
    type=str,
    default=None,
    help="Existing novel project to adapt from (e.g. '仙侠史诗_novel')",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output directory for the short drama project",
)
@click.option(
    "--style",
    "-s",
    type=str,
    default="xianxia",
    help="Story style (xianxia, doushi, modern, etc.)",
)
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Initial episode number for bible generation",
)
def create_short_drama_project(
    project_name: str,
    from_novel: str | None,
    output: str | None,
    style: str,
    episode: int,
):
    """Create a new short drama project.

    Optionally adapts from an existing novel project (recommended).

    Example:
        crewai short_drama create "仙侠史诗" --from-novel "仙侠史诗_novel"
    """
    # Determine output path
    project_name_safe = project_name.replace(" ", "_")
    if output:
        sd_path = Path(output)
    else:
        sd_path = Path.cwd() / f"{project_name_safe}_short_drama"

    if sd_path.exists():
        click.confirm(
            f"Directory {sd_path} already exists. Overwrite?",
            abort=True,
        )
        shutil.rmtree(sd_path)

    sd_path.mkdir(parents=True, exist_ok=True)
    click.echo(f"Creating short drama project: {sd_path}")

    # Copy from novel if specified
    if from_novel:
        novel_path = Path(from_novel) if Path(from_novel).is_absolute() else Path.cwd() / from_novel
        if not novel_path.exists():
            click.secho(f"Error: Novel project not found: {novel_path}", fg="red")
            raise click.Abort()

        click.echo(f"Adapting from novel project: {novel_path}")
        _copy_novel_files(novel_path, sd_path)

        # Generate short drama bible
        click.echo("Generating ShortDramaBible...")
        try:
            adapter = NovelToShortDramaAdapter(novel_path)
            adapter.load_pipeline_state()
            production_bible = adapter.get_production_bible()

            if production_bible:
                builder = ShortDramaBibleBuilder(style=style)
                sd_bible = builder.build(
                    bible=production_bible,
                    episode_num=episode,
                    series_title=project_name,
                    episode_context="",
                )
                bible_file = sd_path / "short_drama_bible.json"
                with open(bible_file, "w", encoding="utf-8") as f:
                    json.dump(sd_bible.to_dict(), f, ensure_ascii=False, indent=2)
                click.echo(f"  ShortDramaBible saved to: {bible_file}")
            else:
                click.secho(
                    "  Warning: Could not load ProductionBible, skipping bible generation",
                    fg="yellow",
                )
        except Exception as e:
            click.secho(f"  Warning: Bible generation failed: {e}", fg="yellow")

    # Write metadata
    metadata = {
        "project_name": project_name,
        "style": style,
        "created_from_novel": from_novel,
    }
    with open(sd_path / "project.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    click.echo(f"\n✅ Short drama project created: {sd_path}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Generate episode outline:")
    click.echo(f"     crewai short_drama outline generate \"{project_name}\" --episode 1")
    click.echo(f"  2. Decompose into shots:")
    click.echo(f"     crewai short_drama shots decompose \"{project_name}\" --episode 1")
    click.echo(f"  3. Assemble video:")
    click.echo(f"     crewai short_drama assemble concat \"{project_name}\" --episode 1")
