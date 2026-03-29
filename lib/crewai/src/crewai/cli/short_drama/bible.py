"""crewai short_drama bible — generate / inspect the short drama bible."""

from __future__ import annotations

import click

from crewai.cli.short_drama._llm import create_llm_from_env, ensure_output_dir, save_json_output
from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.short_drama_types import ShortDramaBible


@click.group(name="bible")
def bible():
    """Manage the short drama bible (ProductionBible → ShortDramaBible)."""
    pass


@bible.command(name="generate")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number to generate bible for",
)
@click.option(
    "--style",
    "-s",
    type=str,
    default="xianxia",
    help="Story style (xianxia, doushi, modern, etc.)",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output directory (defaults to <project_name>_short_drama/)",
)
@click.option(
    "--context",
    "-c",
    type=str,
    default="",
    help="Episode context / continuation from previous episode",
)
@click.option(
    "--from-novel",
    type=str,
    default=None,
    help="Novel project to adapt from (overrides project_name as path)",
)
def bible_generate(
    project_name: str,
    episode: int,
    style: str,
    output: str | None,
    context: str,
    from_novel: str | None,
):
    """Generate a ShortDramaBible for the given project.

    PROJECT_NAME is the short drama project name. If --from-novel is provided,
    the bible is adapted from that novel project.
    """
    import os

    # Resolve project path
    if from_novel:
        novel_path = Path(from_novel) if Path(from_novel).is_absolute() else Path.cwd() / from_novel
    else:
        project_name_for_dir = project_name.replace(" ", "_")
        novel_path = Path.cwd() / f"{project_name_for_dir}_novel"

    if not novel_path.exists():
        click.secho(f"Error: Novel project not found: {novel_path}", fg="red")
        raise click.Abort()

    output_dir_name = output or f"{project_name.replace(' ', '_')}_short_drama"
    output_dir = ensure_output_dir(output_dir_name)

    click.echo(f"Loading novel project: {novel_path}")

    try:
        adapter = NovelToShortDramaAdapter(novel_path)
        adapter.load_pipeline_state()
        production_bible = adapter.get_production_bible()

        if not production_bible:
            click.secho("Error: Could not load ProductionBible from novel project", fg="red")
            raise click.Abort()

        # Build ShortDramaBible
        builder = ShortDramaBibleBuilder(style=style)
        short_drama_bible = builder.build(
            bible=production_bible,
            episode_num=episode,
            series_title=project_name,
            episode_context=context,
        )

        # Save to file
        save_json_output(short_drama_bible.to_dict(), output_dir, "short_drama_bible.json")

        click.echo(f"ShortDramaBible generated successfully!")
        click.echo(f"  Episode: {episode}")
        click.echo(f"  Series: {project_name}")
        click.echo(f"  Characters: {len(short_drama_bible.relevant_characters)}")
        click.echo(f"  Visual Style: {short_drama_bible.visual_style}")
        click.echo(f"  Tone: {short_drama_bible.tone}")
        click.echo(f"  Saved to: {output_dir / "short_drama_bible.json"}")

    except Exception as e:
        click.secho(f"Error generating bible: {e}", fg="red")
        raise click.Abort()


@bible.command(name="inspect")
@click.argument("bible_file", type=click.Path(exists=True))
def bible_inspect(bible_file: str):
    """Inspect a saved ShortDramaBible JSON file."""
    import json

    with open(bible_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    click.echo(f"=== ShortDramaBible: {bible_file} ===")
    click.echo(f"Episode: {data.get('episode_num')}")
    click.echo(f"Series: {data.get('series_title')}")
    click.echo(f"Visual Style: {data.get('visual_style')}")
    click.echo(f"Tone: {data.get('tone')}")
    click.echo(f"\nCharacters ({len(data.get('relevant_characters', {}))}):")
    for name in data.get("relevant_characters", {}):
        click.echo(f"  - {name}")
    click.echo(f"\nWorld Rules Summary:\n  {data.get('world_rules_summary', 'N/A')}")
    click.echo(f"\nEpisode Context:\n  {data.get('episode_context', 'N/A')}")
