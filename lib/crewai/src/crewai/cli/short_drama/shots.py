"""crewai short_drama shots — decompose episode outlines into shots."""

from __future__ import annotations

import json
from pathlib import Path

import click

from crewai.cli.short_drama._llm import (
    create_llm_from_env,
    ensure_output_dir,
    save_json_output,
)
from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder
from crewai.content.short_drama.crews.shot_crew import ShotCrew
from crewai.content.short_drama.short_drama_types import EpisodeOutline


@click.group(name="shots")
def shots():
    """Decompose episode outlines into individual shot lists."""
    pass


def _load_outline(outline_file: Path) -> EpisodeOutline:
    """Load an EpisodeOutline from a JSON file."""
    with open(outline_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return EpisodeOutline(**data)


def _load_bible_from_project(project_name: str, from_novel: str | None, episode: int, style: str):
    """Load (or build) ShortDramaBible for the given project."""
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
    )
    return sd_bible


@shots.command(name="decompose")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number",
)
@click.option(
    "--outline-file",
    "-f",
    type=click.Path(exists=True),
    default=None,
    help="Path to episode outline JSON (overrides default location)",
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
    help="Output directory (defaults to <project_name>_short_drama/)",
)
@click.option(
    "--from-novel",
    type=str,
    default=None,
    help="Novel project to adapt from",
)
def shots_decompose(
    project_name: str,
    episode: int,
    outline_file: str | None,
    style: str,
    output: str | None,
    from_novel: str | None,
):
    """Decompose an episode outline into individual shots.

    PROJECT_NAME is the short drama project name. The outline is loaded from
    the default location (<project>_short_drama/episode_<N>_outline.json)
    or from --outline-file if specified.
    """
    llm = create_llm_from_env()
    if not llm:
        click.secho(
            "Error: No LLM configured. Set MINIMAX_API_KEY or DEEPSEEK_API_KEY.",
            fg="red",
        )
        raise click.Abort()

    # Determine outline file
    if outline_file:
        outline_path = Path(outline_file)
    else:
        project_name_safe = project_name.replace(" ", "_")
        sd_dir = output or f"{project_name_safe}_short_drama"
        outline_path = Path(sd_dir) / f"episode_{episode:03d}_outline.json"

    if not outline_path.exists():
        click.secho(
            f"Error: Outline file not found: {outline_path}\n"
            f"  Run: crewai short_drama outline generate \"{project_name}\" --episode {episode}",
            fg="red",
        )
        raise click.Abort()

    click.echo(f"Loading outline from: {outline_path}")
    episode_outline = _load_outline(outline_path)

    try:
        sd_bible = _load_bible_from_project(project_name, from_novel, episode, style)
    except (FileNotFoundError, ValueError) as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

    output_dir = ensure_output_dir(output or f"{project_name.replace(' ', '_')}_short_drama")

    click.echo(f"Decomposing episode {episode} into shots...")

    crew = ShotCrew(config={"llm": llm}, verbose=False)

    try:
        short_drama_episode = crew.decompose_episode(episode_outline, sd_bible)
    except Exception as e:
        click.secho(f"Error decomposing episode: {e}", fg="red")
        raise click.Abort()

    # Save the full episode
    episode_file = output_dir / f"episode_{episode:03d}.json"
    save_json_output(
        short_drama_episode.to_dict(),
        output_dir,
        f"episode_{episode:03d}.json",
    )

    total_shots = len(short_drama_episode.get_all_shots())
    total_duration = short_drama_episode.get_duration()

    click.echo(f"Shot decomposition complete!")
    click.echo(f"  Episode: {episode}")
    click.echo(f"  Scenes: {len(short_drama_episode.scenes)}")
    click.echo(f"  Total Shots: {total_shots}")
    click.echo(f"  Total Duration: ~{total_duration:.0f}s ({total_duration/60:.1f} min)")
    click.echo(f"  Saved to: {episode_file}")

    # Print shot summary table
    click.echo("\nShot summary:")
    click.echo(f"  {'Shot':>4}  {'Scene':>5}  {'Type':>18}  {'Duration':>8}  {'Emotion':>8}")
    click.echo(f"  {'-'*4}  {'-'*5}  {'-'*18}  {'-'*8}  {'-'*8}")
    for shot in short_drama_episode.get_all_shots():
        click.echo(
            f"  {shot.shot_number:>4}  {shot.scene_number:>5}  "
            f"{shot.shot_type:>18}  {shot.duration_seconds:>7.1f}s  {shot.emotion:>8}"
        )


@shots.command(name="prompts")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output directory for prompts (defaults to <project_name>_short_drama/)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "markdown"]),
    default="markdown",
    help="Output format for prompts",
)
def shots_prompts(
    project_name: str,
    episode: int,
    output: str | None,
    format: str,
):
    """Export shot video prompts for an episode.

    Loads the decomposed episode JSON and prints all shot prompts
    in the specified format for use with video generation tools.
    """
    project_name_safe = project_name.replace(" ", "_")
    sd_dir = output or f"{project_name_safe}_short_drama"
    episode_file = Path(sd_dir) / f"episode_{episode:03d}.json"

    if not episode_file.exists():
        click.secho(
            f"Error: Episode file not found: {episode_file}\n"
            f"  Run: crewai short_drama shots decompose \"{project_name}\" --episode {episode}",
            fg="red",
        )
        raise click.Abort()

    with open(episode_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if format == "markdown":
        lines = [f"# {data['title']} - Shot Prompts\n"]
        for scene in data["scenes"]:
            lines.append(f"\n## Scene {scene['scene_number']}: {scene['location']} ({scene['time_of_day']})\n")
            for shot in scene["shots"]:
                lines.append(f"### Shot {shot['shot_number']} ({shot['duration_seconds']}s, {shot['shot_type']})\n")
                lines.append(f"**Action:** {shot['action']}\n")
                lines.append(f"**Characters:** {', '.join(shot['characters'])}\n")
                lines.append(f"**Emotion:** {shot['emotion']}\n")
                lines.append(f"**Voiceover:** {shot.get('voiceover_segment', '')}\n")
                lines.append(f"**Prompt:**\n```\n{shot.get('video_prompt', 'N/A')}\n```\n")
        click.echo("\n".join(lines))
    else:
        # JSON: extract just the prompts
        prompts = []
        for scene in data["scenes"]:
            for shot in scene["shots"]:
                prompts.append(
                    {
                        "shot_number": shot["shot_number"],
                        "scene_number": shot["scene_number"],
                        "duration": shot["duration_seconds"],
                        "shot_type": shot["shot_type"],
                        "action": shot["action"],
                        "characters": shot["characters"],
                        "prompt": shot.get("video_prompt", ""),
                    }
                )
        click.echo(json.dumps(prompts, ensure_ascii=False, indent=2))
