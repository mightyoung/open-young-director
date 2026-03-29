"""crewai short_drama assemble — assemble shots into final video."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import click

from crewai.cli.short_drama._llm import ensure_output_dir
from crewai.content.short_drama.short_drama_types import ShortDramaEpisode, ShortDramaScene, Shot
from crewai.content.short_drama.video.ffmpeg_assembler import FFmpegAssembler


# ---------------------------------------------------------------------------
# Helper: load ShortDramaEpisode from project
# ---------------------------------------------------------------------------

def _load_episode(project_name: str, episode: int, output: str | None) -> ShortDramaEpisode:
    """Load a ShortDramaEpisode from the episode JSON file."""
    project_name_safe = project_name.replace(" ", "_")
    sd_dir = output or f"{project_name_safe}_short_drama"
    episode_file = Path(sd_dir) / f"episode_{episode:03d}.json"

    if not episode_file.exists():
        raise FileNotFoundError(f"Episode file not found: {episode_file}")

    with open(episode_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct ShortDramaEpisode from dict
    scenes = []
    for scene_data in data.get("scenes", []):
        shots = [Shot(**s) for s in scene_data.get("shots", [])]
        scene = ShortDramaScene(
            scene_number=scene_data["scene_number"],
            location=scene_data["location"],
            time_of_day=scene_data["time_of_day"],
            description=scene_data["description"],
            shots=shots,
            voiceover=scene_data.get("voiceover", ""),
        )
        scenes.append(scene)

    return ShortDramaEpisode(
        episode_num=data["episode_num"],
        title=data["title"],
        summary=data["summary"],
        scenes=scenes,
        voiceover_intro=data.get("voiceover_intro", ""),
        voiceover_outro=data.get("voiceover_outro", ""),
        episode_context=data.get("episode_context", ""),
    )


# ---------------------------------------------------------------------------
# Click group / commands
# ---------------------------------------------------------------------------

@click.group(name="assemble")
def assemble():
    """Assemble decomposed shots into final video files."""
    pass


@assemble.command(name="concat")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number to assemble",
)
@click.option(
    "--video-dir",
    type=str,
    default=None,
    help="Directory containing individual shot video files",
)
@click.option(
    "--output",
    "-o",
    type=str,
    default=None,
    help="Output file path (defaults to <project>_episode_<N>.mp4)",
)
@click.option(
    "--ffmpeg-path",
    type=str,
    default="ffmpeg",
    help="Path to ffmpeg executable",
)
@click.option(
    "--ffprobe-path",
    type=str,
    default="ffprobe",
    help="Path to ffprobe executable",
)
def assemble_concat(
    project_name: str,
    episode: int,
    video_dir: str | None,
    output: str | None,
    ffmpeg_path: str,
    ffprobe_path: str,
):
    """Concatenate pre-generated shot videos into a single episode video.

    VIDEO_DIR should contain files named:
      episode_<NNN>_shot_<MMM>.mp4

    where NNN is the episode number and MMM is the shot number.
    """
    assembler = FFmpegAssembler(ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)

    # Check FFmpeg availability
    if not assembler.check_ffmpeg():
        click.secho(
            "Error: ffmpeg not found or not executable.\n"
            f"  Checked: {ffmpeg_path}\n"
            "  Install: brew install ffmpeg  (macOS)  or  apt install ffmpeg  (Linux)",
            fg="red",
        )
        raise click.Abort()

    try:
        episode_obj = _load_episode(project_name, episode, video_dir)
    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

    # Determine video dir
    if video_dir:
        vd = Path(video_dir)
    else:
        project_name_safe = project_name.replace(" ", "_")
        vd = Path(f"{project_name_safe}_short_drama") / "shots"

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        project_name_safe = project_name.replace(" ", "_")
        sd_dir = f"{project_name_safe}_short_drama"
        output_path = Path(sd_dir) / f"episode_{episode:03d}_assembled.mp4"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Assembling episode {episode}...")
    click.echo(f"  Video dir: {vd}")
    click.echo(f"  Output: {output_path}")

    video_files = assembler.generate_concat_list(episode_obj, str(vd))

    if not video_files:
        click.secho(
            "Error: No video files found in "
            f"{vd}\n"
            "  Expected naming: episode_<NNN>_shot_<MMM>.mp4\n"
            "  Hint: Use --video-dir if your files are in a different location",
            fg="red",
        )
        raise click.Abort()

    click.echo(f"  Found {len(video_files)} video segments")

    # Show file list
    for f in video_files:
        click.echo(f"    + {Path(f).name}")

    success = assembler.concat_videos(
        video_files=video_files,
        output_file=str(output_path),
    )

    if success:
        duration = assembler.get_duration(str(output_path)) or 0
        click.echo(
            f"✅ Assembly complete! "
            f"{len(video_files)} segments → {output_path} "
            f"({duration:.1f}s)"
        )
    else:
        click.secho("❌ Assembly failed. Check ffmpeg output above.", fg="red")
        raise click.Abort()


@assemble.command(name="check")
@click.argument("project_name")
@click.option(
    "--episode",
    "-e",
    type=int,
    default=1,
    help="Episode number",
)
@click.option(
    "--video-dir",
    type=str,
    default=None,
    help="Directory containing shot video files",
)
def assemble_check(
    project_name: str,
    episode: int,
    video_dir: str | None,
):
    """Check which shot videos are present / missing.

    Useful for verifying all shots have been generated before assembly.
    """
    try:
        episode_obj = _load_episode(project_name, episode, video_dir)
    except FileNotFoundError as e:
        click.secho(f"Error: {e}", fg="red")
        raise click.Abort()

    if video_dir:
        vd = Path(video_dir)
    else:
        project_name_safe = project_name.replace(" ", "_")
        vd = Path(f"{project_name_safe}_short_drama") / "shots"

    click.echo(f"Checking episode {episode} in {vd}...")
    click.echo(f"  {'Shot':>4}  {'Scene':>5}  {'File':<45}  {'Status':<8}")
    click.echo(f"  {'-'*4}  {'-'*5}  {'-'*45}  {'-'*8}")

    all_present = True
    for shot in episode_obj.get_all_shots():
        fname = f"episode_{episode:03d}_shot_{shot.shot_number:03d}.mp4"
        fpath = vd / fname
        status = "✅ present" if fpath.exists() else "❌ MISSING"
        if not fpath.exists():
            all_present = False
        click.echo(
            f"  {shot.shot_number:>4}  {shot.scene_number:>5}  "
            f"{fname:<45}  {status:<8}"
        )

    total = len(episode_obj.get_all_shots())
    if all_present:
        click.echo(f"\n✅ All {total} shot videos are present. Ready to assemble!")
    else:
        missing = total - sum(1 for s in episode_obj.get_all_shots() if (vd / f"episode_{episode:03d}_shot_{s.shot_number:03d}.mp4").exists())
        click.secho(f"\n⚠️  {missing} of {total} shot videos are missing.", fg="yellow")
