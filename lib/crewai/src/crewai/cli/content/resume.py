"""Resume generated content from an output directory."""
from __future__ import annotations

from pathlib import Path

import click

from crewai.cli.content.inspection import detect_content_type, load_json
from crewai.cli.content.novel_runner import run_novel_creation


@click.command(name="resume-content")
@click.argument("output_dir", type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option(
    "--resume-from",
    type=click.Choice(["evaluation", "volume", "summary", "writing"], case_sensitive=False),
    default="writing",
    show_default=True,
    help="Novel resume stage.",
)
def resume_content(output_dir: Path, resume_from: str) -> None:
    """Resume content generation from an output directory."""
    result_path = output_dir / "result.json"
    if not result_path.exists():
        click.echo(f"❌ 未找到 result.json: {result_path}", err=True)
        raise click.Abort()

    result = load_json(result_path)
    content_type = detect_content_type(result)

    if content_type != "Novel":
        click.echo(
            f"❌ 当前仅支持从 Novel 输出目录恢复，检测到: {content_type}。",
            err=True,
        )
        click.echo("   可先使用 `crewai status <output_dir>` 查看状态。", err=True)
        raise click.Abort()

    state_path = output_dir / "pipeline_state.json"
    if not state_path.exists():
        click.echo(f"❌ 未找到可恢复的 pipeline_state.json: {state_path}", err=True)
        raise click.Abort()

    topic = result.get("topic") or output_dir.stem
    words = int(result.get("target_words", 100000))
    style = result.get("style", "urban")
    chapters = int(result.get("chapters_count", 0))

    click.echo(f"📂 从输出目录恢复小说: {output_dir}")
    click.echo(f"   主题: {topic}")
    click.echo(f"   恢复阶段: {resume_from}")
    click.echo(f"   状态文件: {state_path}")

    run_novel_creation(
        topic=topic,
        words=words,
        style=style,
        output=str(output_dir),
        chapters=chapters,
        resume_from=resume_from,
        pipeline_state_path=str(state_path),
    )
