"""crewai short_drama outline — generate episode outlines."""

from __future__ import annotations

from pathlib import Path

import click

from crewai.cli.short_drama._llm import (
    create_llm_from_env,
    ensure_output_dir,
    save_json_output,
)
from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.crews.episode_outline_crew import EpisodeOutlineCrew


@click.group(name="outline")
def outline():
    """Generate episode outlines from novel chapters."""
    pass


def _load_bible_and_adapter(
    project_name: str,
    from_novel: str | None,
    episode: int,
    style: str,
):
    """Load (or build) ShortDramaBible and NovelToShortDramaAdapter."""
    # Resolve novel path
    if from_novel:
        novel_path = (
            Path(from_novel)
            if Path(from_novel).is_absolute()
            else Path.cwd() / from_novel
        )
    else:
        project_name_safe = project_name.replace(" ", "_")
        novel_path = Path.cwd() / f"{project_name_safe}_novel"

    if not novel_path.exists():
        raise FileNotFoundError(f"Novel project not found: {novel_path}")

    adapter = NovelToShortDramaAdapter(novel_path)
    adapter.load_pipeline_state()
    production_bible = adapter.get_production_bible()

    if not production_bible:
        raise ValueError("Could not load ProductionBible")

    builder = ShortDramaBibleBuilder(style=style)
    sd_bible = builder.build(
        bible=production_bible,
        episode_num=episode,
        series_title=project_name,
        episode_context="",
    )

    return adapter, sd_bible


@outline.command(name="generate")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number to generate outline for",
)
@click.option(
    "--chapter",
    type=int,
    default=None,
    help="Source chapter number (defaults to episode number)",
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
    "--from-novel",
    type=str,
    default=None,
    help="Novel project to adapt from",
)
@click.option(
    "--context",
    type=str,
    default="",
    help="Episode context / continuation from previous episode",
)
def outline_generate(
    project_name: str,
    episode: int,
    chapter: int | None,
    style: str,
    output: str | None,
    from_novel: str | None,
    context: str,
):
    """Generate an episode outline for PROJECT_NAME.

    Reads the specified chapter from the novel project and uses an LLM
    to generate a structured episode outline (scene plan, key actions, etc.).
    """

    llm = create_llm_from_env()
    if not llm:
        click.secho(
            "Error: No LLM configured. Set MINIMAX_API_KEY or DEEPSEEK_API_KEY.",
            fg="red",
        )
        raise click.Abort()

    chapter_num = chapter if chapter is not None else episode

    try:
        adapter, sd_bible = _load_bible_and_adapter(
            project_name, from_novel, episode, style
        )
    except (FileNotFoundError, ValueError) as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

    output_dir_name = output or f"{project_name.replace(' ', '_')}_short_drama"
    output_dir = ensure_output_dir(output_dir_name)

    click.echo(f"Generating outline for episode {episode} from chapter {chapter_num}...")

    try:
        chapter_text = adapter.get_chapter_text(chapter_num)
    except FileNotFoundError:
        click.secho(
            f"Error: Chapter {chapter_num} not found in novel project",
            fg="red",
        )
        raise click.Abort()

    crew = EpisodeOutlineCrew(config={"llm": llm}, verbose=False)

    try:
        episode_outline = crew.generate_outline(
            chapter_text=chapter_text,
            bible=sd_bible,
            episode_num=episode,
            series_title=project_name,
            episode_context=context or sd_bible.episode_context,
        )
    except Exception as e:
        click.secho(f"Error generating outline: {e}", fg="red")
        raise click.Abort()

    # Save outline
    outline_file = output_dir / f"episode_{episode:03d}_outline.json"
    save_json_output(episode_outline.to_dict(), output_dir, f"episode_{episode:03d}_outline.json")

    click.echo(f"Outline generated successfully!")
    click.echo(f"  Episode: {episode}")
    click.echo(f"  Title: {episode_outline.title}")
    click.echo(f"  Scenes: {len(episode_outline.scene_plan)}")
    click.echo(f"  Saved to: {outline_file}")


@outline.command(name="batch")
@click.argument("project_name")
@click.option(
    "--episodes",
    "-n",
    type=int,
    default=3,
    help="Number of episode outlines to generate",
)
@click.option(
    "--start-episode",
    type=int,
    default=1,
    help="Starting episode number",
)
@click.option(
    "--style",
    "-s",
    type=str,
    default="xianxia",
    help="Story style",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output directory",
)
@click.option(
    "--from-novel",
    type=str,
    default=None,
    help="Novel project to adapt from",
)
def outline_batch(
    project_name: str,
    episodes: int,
    start_episode: int,
    style: str,
    output: str | None,
    from_novel: str | None,
):
    """Batch generate multiple episode outlines."""

    llm = create_llm_from_env()
    if not llm:
        click.secho(
            "Error: No LLM configured. Set MINIMAX_API_KEY or DEEPSEEK_API_KEY.",
            fg="red",
        )
        raise click.Abort()

    output_dir_name = output or f"{project_name.replace(' ', '_')}_short_drama"
    output_dir = ensure_output_dir(output_dir_name)

    click.echo(f"Batch generating {episodes} episode outlines...")

    try:
        adapter, sd_bible = _load_bible_and_adapter(
            project_name, from_novel, start_episode, style
        )
    except (FileNotFoundError, ValueError) as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

    crew = EpisodeOutlineCrew(config={"llm": llm}, verbose=False)

    for i in range(episodes):
        ep_num = start_episode + i
        ch_num = ep_num  # default: chapter number = episode number

        try:
            chapter_text = adapter.get_chapter_text(ch_num)
        except FileNotFoundError:
            click.secho(f"  [Episode {ep_num}] Chapter {ch_num} not found, skipping", fg="yellow")
            continue

        try:
            episode_outline = crew.generate_outline(
                chapter_text=chapter_text,
                bible=sd_bible,
                episode_num=ep_num,
                series_title=project_name,
            )
            save_json_output(
                episode_outline.to_dict(),
                output_dir,
                f"episode_{ep_num:03d}_outline.json",
            )
            click.echo(f"  [Episode {ep_num}] Done: {episode_outline.title}")
        except Exception as e:
            click.secho(f"  [Episode {ep_num}] Error: {e}", fg="yellow")

    click.echo(f"Batch complete. Results saved to: {output_dir}")
