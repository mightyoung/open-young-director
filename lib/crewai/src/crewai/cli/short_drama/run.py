"""crewai short_drama run — one-command full pipeline execution.

Usage:
    crewai short_drama run "仙侠史诗" --episode 1 --from-novel "仙侠史诗_novel"
    crewai short_drama run "仙侠史诗" --episode 1-3 --provider minimax --max-parallel 5
    crewai short_drama run "仙侠史诗" --episode 1 --skip-tts --skip-video
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import click

from crewai.cli.short_drama._llm import create_llm_from_env
from crewai.content.short_drama.pipeline_orchestrator import (
    ShortDramaPipelineOrchestrator,
)


def _parse_episode_range(episodes_str: str) -> list[int]:
    """Parse episode string like '1', '1-3', '1,3,5' into list of ints.

    Args:
        episodes_str: Episode specification string.

    Returns:
        List of episode numbers.

    Raises:
        click.BadParameter: If the format is invalid.
    """
    episodes = []
    parts = episodes_str.replace(" ", ",").split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            match = re.match(r"(\d+)-(\d+)", part)
            if not match:
                raise click.BadParameter(
                    f"Invalid range format: {part!r}. Use '1-3'."
                )
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                raise click.BadParameter(
                    f"Invalid range: start {start} > end {end}"
                )
            episodes.extend(range(start, end + 1))
        else:
            try:
                episodes.append(int(part))
            except ValueError:
                raise click.BadParameter(
                    f"Invalid episode number: {part!r}"
                )

    return sorted(set(episodes))  # deduplicate and sort


@click.command(name="run")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=str,
    default="1",
    help=(
        "Episode number(s) to generate. "
        "Supports: '1' (single), '1-3' (range), '1,3,5' (list), '1-3,7,9-10' (mixed). "
        "Defaults to '1'."
    ),
)
@click.option(
    "--chapter",
    type=int,
    default=None,
    help="Source chapter number (defaults to episode number).",
)
@click.option(
    "--from-novel",
    type=str,
    default=None,
    help="Path to novel project to adapt from.",
)
@click.option(
    "--provider",
    type=str,
    default="minimax",
    help="Video provider: minimax (default), runway, kling.",
)
@click.option(
    "--tts-provider",
    type=str,
    default="minimax",
    help="TTS provider: minimax (default), elevenlabs.",
)
@click.option(
    "--max-parallel",
    type=int,
    default=3,
    help="Maximum parallel video/TTS generation tasks (default: 3).",
)
@click.option(
    "--aspect-ratio",
    type=str,
    default="16:9",
    help="Video aspect ratio: 16:9 (default), 9:16, 1:1.",
)
@click.option(
    "--style",
    "-s",
    type=str,
    default="xianxia",
    help="Story style: xianxia (default), doushi, modern, etc.",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output directory for the project.",
)
@click.option(
    "--skip-video",
    is_flag=True,
    help="Skip video generation (useful for testing outline/shots).",
)
@click.option(
    "--skip-tts",
    is_flag=True,
    help="Skip TTS generation.",
)
@click.option(
    "--skip-assemble",
    is_flag=True,
    help="Skip final video assembly.",
)
@click.option(
    "--no-resume",
    is_flag=True,
    help="Do not resume from checkpoints; start fresh.",
)
def run(
    project_name: str,
    episode: str,
    chapter: int | None,
    from_novel: str | None,
    provider: str,
    tts_provider: str,
    max_parallel: int,
    aspect_ratio: str,
    style: str,
    output: str | None,
    skip_video: bool,
    skip_tts: bool,
    skip_assemble: bool,
    no_resume: bool,
):
    """Run the full short drama pipeline with one command.

    PROJECT_NAME is the short drama project name. The pipeline will:

        1. Load/build the ShortDramaBible
        2. Generate the episode outline
        3. Decompose the outline into shots
        4. Generate video for each shot (parallel, via --provider)
        5. Generate TTS voiceover for each shot (parallel, via --tts-provider)
        6. Assemble all segments into a final video

    Examples:

        # Generate episode 1 from novel
        crewai short_drama run "仙侠史诗" --episode 1 --from-novel "仙侠史诗_novel"

        # Generate episodes 1 through 3
        crewai short_drama run "仙侠史诗" --episode 1-3 --from-novel "仙侠史诗_novel"

        # Generate with custom settings
        crewai short_drama run "仙侠史诗" --episode 2 \\
            --provider minimax --max-parallel 5 --aspect-ratio 9:16

        # Skip expensive stages for debugging
        crewai short_drama run "仙侠史诗" --episode 1 --skip-video --skip-tts
    """
    # Parse episode range
    try:
        episode_list = _parse_episode_range(episode)
    except click.BadParameter:
        raise

    if len(episode_list) > 1:
        click.echo(
            f"📋 Batch mode: generating episodes {episode_list}"
        )
    else:
        click.echo(f"🎬 Generating episode {episode_list[0]}")

    # Validate provider
    valid_providers = {"minimax", "runway", "kling"}
    if provider.lower() not in valid_providers:
        click.secho(
            f"Error: Unknown video provider: {provider!r}. "
            f"Supported: {', '.join(valid_providers)}",
            fg="red",
        )
        raise click.Abort()

    # Validate TTS provider
    valid_tts = {"minimax", "elevenlabs"}
    if tts_provider.lower() not in valid_tts:
        click.secho(
            f"Error: Unknown TTS provider: {tts_provider!r}. "
            f"Supported: {', '.join(valid_tts)}",
            fg="red",
        )
        raise click.Abort()

    # Validate aspect ratio
    valid_ratios = {"16:9", "9:16", "1:1", "4:3", "3:4"}
    if aspect_ratio not in valid_ratios:
        click.secho(
            f"Error: Unknown aspect ratio: {aspect_ratio!r}. "
            f"Supported: {', '.join(valid_ratios)}",
            fg="red",
        )
        raise click.Abort()

    # Resolve project directory
    project_name_safe = project_name.replace(" ", "_")
    if output:
        project_dir = Path(output)
    else:
        project_dir = Path.cwd() / f"{project_name_safe}_short_drama"

    project_dir.mkdir(parents=True, exist_ok=True)

    # Check for LLM
    llm = create_llm_from_env()
    if not llm:
        click.secho(
            "Error: No LLM configured. Set MINIMAX_API_KEY or DEEPSEEK_API_KEY.",
            fg="red",
        )
        raise click.Abort()

    # Show configuration
    click.echo("\n⚙️  Configuration:")
    click.echo(f"  Project:     {project_name} ({project_dir})")
    click.echo(f"  Episodes:    {episode_list}")
    click.echo(f"  Video:       {provider}")
    click.echo(f"  TTS:         {tts_provider}")
    click.echo(f"  Parallel:    {max_parallel}")
    click.echo(f"  Aspect:      {aspect_ratio}")
    click.echo(f"  Style:       {style}")
    if from_novel:
        click.echo(f"  From Novel:  {from_novel}")
    click.echo(
        f"  Skip:       video={skip_video}, tts={skip_tts}, assemble={skip_assemble}"
    )
    click.echo(f"  Resume:      {not no_resume}")
    click.echo("")

    # Create orchestrator
    orchestrator = ShortDramaPipelineOrchestrator(
        project_name=project_name,
        project_dir=str(project_dir),
        llm=llm,
        video_provider_name=provider,
        tts_provider_name=tts_provider,
        style=style,
        aspect_ratio=aspect_ratio,
        max_parallel=max_parallel,
    )

    # Run for each episode
    results = []
    for ep_num in episode_list:
        click.echo(f"\n{'='*60}")
        click.echo(f"🎬 Episode {ep_num} — Pipeline Start")
        click.echo(f"{'='*60}")

        result = asyncio.run(
            orchestrator.run_full_pipeline(
                episode=ep_num,
                chapter=chapter,
                from_novel=from_novel,
                max_parallel=max_parallel,
                skip_video=skip_video,
                skip_tts=skip_tts,
                skip_assemble=skip_assemble,
                resume=not no_resume,
            )
        )
        results.append(result)

        # Summary
        if result.success:
            click.echo(f"\n✅ Episode {ep_num} — Pipeline Complete!")
            if result.final_video_path:
                click.echo(f"   📹 Final video: {result.final_video_path}")
            else:
                click.echo(f"   📹 Videos: {len(result.video_segments)} segments")
                click.echo(f"   🔊 Audio: {len(result.audio_segments)} segments")
        else:
            click.secho(f"\n❌ Episode {ep_num} — Pipeline Failed!", fg="red")
            for err in result.errors:
                click.secho(f"   Error: {err}", fg="yellow")

    # Overall summary
    click.echo(f"\n{'='*60}")
    success_count = sum(1 for r in results if r.success)
    click.echo(f"📊 Batch Summary: {success_count}/{len(results)} episodes succeeded")
    if success_count > 0:
        click.echo(f"📁 Project: {project_dir}")
    click.echo(f"{'='*60}")

    if success_count < len(results):
        raise click.Abort(code=1)
