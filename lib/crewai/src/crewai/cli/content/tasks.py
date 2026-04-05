"""Inspect task dashboards stored in generated novel outputs."""
from __future__ import annotations

import json
from pathlib import Path

import click

from crewai.cli.content.inspection import detect_content_type, extract_task_dashboard, load_json


@click.command(name="tasks")
@click.argument("output_dir", type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option("--json-output", is_flag=True, help="Print machine-readable JSON output.")
def content_tasks(output_dir: Path, json_output: bool) -> None:
    """Inspect the task dashboard for a generated content directory."""
    result_path = output_dir / "result.json"
    if not result_path.exists():
        click.echo(f"❌ 未找到 result.json: {result_path}", err=True)
        raise click.Abort()

    result = load_json(result_path)
    content_type = detect_content_type(result)
    task_dashboard = extract_task_dashboard(result)

    payload = {
        "content_type": content_type,
        "output_dir": str(output_dir),
        "task_dashboard": task_dashboard,
    }

    if json_output:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    summary = task_dashboard["summary"]
    if not summary and not task_dashboard["tasks"]:
        click.echo(f"ℹ️ {content_type} 输出未包含任务大盘。")
        click.echo("   这类产物目前没有保存执行任务态。")
        return

    click.echo(f"📋 {content_type} 任务大盘")
    click.echo(f"   目录: {output_dir}")
    click.echo(
        "   统计: "
        f"pending={summary.get('pending', 0)} "
        f"running={summary.get('running', 0)} "
        f"completed={summary.get('completed', 0)} "
        f"failed={summary.get('failed', 0)} "
        f"retrying={summary.get('retrying', 0)}"
    )

    active_tasks = task_dashboard["active_tasks"]
    if active_tasks:
        click.echo("   活跃任务:")
        for task in active_tasks[:5]:
            click.echo(
                f"     - [{task.get('status', 'unknown')}] {task.get('id', '?')} "
                f"{task.get('description', '')}"
            )
    else:
        click.echo("   活跃任务: 无")
