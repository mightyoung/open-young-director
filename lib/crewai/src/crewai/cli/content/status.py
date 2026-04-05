"""Inspect generated content output directories."""
from __future__ import annotations

import json
from pathlib import Path

import click

from crewai.cli.content.inspection import (
    collect_artifacts,
    detect_content_type,
    expected_artifacts,
    load_json,
    project_memory_info,
    summarize_report,
    extract_task_dashboard,
)


@click.command(name="status")
@click.argument("output_dir", type=click.Path(path_type=Path, exists=True, file_okay=False))
@click.option("--json-output", is_flag=True, help="Print machine-readable JSON output.")
def content_status(output_dir: Path, json_output: bool) -> None:
    """Inspect a generated content output directory."""
    result_path = output_dir / "result.json"
    if not result_path.exists():
        click.echo(f"❌ 未找到 result.json: {result_path}", err=True)
        raise click.Abort()

    result = load_json(result_path)
    content_type = detect_content_type(result)
    report = summarize_report(result)
    artifacts = collect_artifacts(output_dir)
    expected = expected_artifacts(content_type)
    missing = [name for name in expected if not (output_dir / name).exists()]
    task_dashboard = extract_task_dashboard(result)
    project_memory = project_memory_info()

    payload = {
        "content_type": content_type,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "missing_artifacts": missing,
        "report": report,
        "task_dashboard": task_dashboard,
        "project_memory": project_memory,
    }

    if json_output:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        return

    status_icon = "✅" if report["is_usable"] and not report["requires_manual_review"] else "⚠️"
    click.echo(f"{status_icon} {content_type} 输出状态")
    click.echo(f"   目录: {output_dir}")
    click.echo(f"   状态: {report['status']}")
    click.echo(f"   可直接使用: {'是' if report['is_usable'] else '否'}")
    click.echo(f"   需人工审核: {'是' if report['requires_manual_review'] else '否'}")
    if report["warnings"]:
        click.echo(f"   警告: {report['warnings'][0]}")
    if report["errors"]:
        click.echo(f"   错误: {report['errors'][0]}")
    if report["next_actions"]:
        click.echo(f"   下一步: {report['next_actions'][0]}")
    if task_dashboard["summary"]:
        summary = task_dashboard["summary"]
        click.echo(
            "   任务: "
            f"pending={summary.get('pending', 0)} "
            f"running={summary.get('running', 0)} "
            f"completed={summary.get('completed', 0)} "
            f"failed={summary.get('failed', 0)} "
            f"retrying={summary.get('retrying', 0)}"
        )
    click.echo(
        f"   项目记忆: {'已存在' if project_memory['exists'] else '未创建'}"
    )
    click.echo("   产物:")
    for name, exists in artifacts.items():
        marker = "✓" if exists else "✗"
        click.echo(f"     {marker} {name}")
    if missing:
        click.echo(f"   缺失: {', '.join(missing)}")
