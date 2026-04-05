"""Script content generation runner."""
import click

from crewai.cli.content.serializers import (
    build_review_markdown,
    ensure_output_dir,
    save_json_output,
    save_markdown_output,
    save_script_content,
)


class ScriptGenerationError(Exception):
    """Script generation error with context."""

    def __init__(self, message: str, stage: str):
        self.message = message
        self.stage = stage
        super().__init__(f"[{stage}] {message}")

    @property
    def cause(self) -> BaseException | None:
        """Return the chained exception cause (from `raise ... from e`)."""
        return self.__cause__


def run_script(
    topic: str,
    format: str,
    target_runtime: int,
    num_acts: int,
    output: str,
) -> None:
    """Run script generation.

    Args:
        topic: Script topic
        format: Script format (film/tv/web series)
        target_runtime: Target runtime in minutes
        num_acts: Number of acts
        output: Output directory
    """
    from crewai.content.script import ScriptCrew
    from crewai.content.script.crews.script_crew import ScriptConfig

    # Validate inputs early (P1-17: strict contract testing)
    VALID_FORMATS = {"film", "tv", "web series"}
    if format not in VALID_FORMATS:
        raise ScriptGenerationError(
            f"不支持的脚本格式: '{format}'。支持的格式: {', '.join(sorted(VALID_FORMATS))}",
            stage="config",
        )
    if num_acts <= 0:
        raise ScriptGenerationError(
            f"幕数必须大于0，当前值: {num_acts}。请使用 --acts 参数指定正整数。",
            stage="config",
        )
    if target_runtime <= 0:
        raise ScriptGenerationError(
            f"目标时长必须大于0分钟，当前值: {target_runtime}。请使用 --duration 参数指定正整数。",
            stage="config",
        )

    try:
        script_config = ScriptConfig(
            topic=topic,
            format=format,
            target_runtime=target_runtime,
            num_acts=num_acts,
        )
    except (TypeError, ValueError, AttributeError) as e:
        raise ScriptGenerationError(f"配置创建失败: {e}", stage="config") from e

    try:
        crew = ScriptCrew(config=script_config)
        result = crew.kickoff()
    except (RuntimeError, TimeoutError, IOError) as e:
        raise ScriptGenerationError(f"ScriptCrew执行失败: {e}", stage="generation") from e

    # Save results - result.content is ScriptOutput
    content = result.content
    try:
        output_dir = ensure_output_dir(output)
    except OSError as e:
        raise ScriptGenerationError(f"输出目录创建失败: {output} - {e}", stage="output_dir") from e

    try:
        save_script_content(content, output_dir)
    except (IOError, OSError) as e:
        raise ScriptGenerationError(f"内容保存失败: {e}", stage="save_content") from e

    quality_report = result.metadata.get("quality_report", {})
    warnings = list(content.warnings or [])
    errors = list(quality_report.get("errors", []))
    status = quality_report.get("output_status", "warning" if warnings else "success")
    is_usable = bool(quality_report.get("is_usable", True))
    requires_manual_review = bool(quality_report.get("requires_manual_review", bool(warnings)))
    next_actions = _build_script_next_actions(
        warnings=warnings,
        requires_manual_review=requires_manual_review,
        scenes_count=len(content.scenes),
    )

    try:
        save_json_output(
            {
                "topic": topic,
                "format": format,
                "duration": target_runtime,
                "acts": num_acts,
                "scenes_count": len(content.scenes),
                "title": content.title,
                "warnings": warnings,
                "status": status,
                "is_usable": is_usable,
                "requires_manual_review": requires_manual_review,
                "next_actions": next_actions,
                "metadata": result.metadata,
            },
            output_dir,
            "result.json",
        )
    except (IOError, OSError, ValueError) as e:
        raise ScriptGenerationError(f"结果JSON保存失败: {e}", stage="save_result") from e

    summary = build_review_markdown(
        content_type="Script",
        topic=topic,
        title=content.title,
        status=status,
        is_usable=is_usable,
        requires_manual_review=requires_manual_review,
        warnings=warnings,
        errors=errors,
        next_actions=next_actions,
        extra_sections={
            "输出概览": [
                f"幕数: {num_acts}",
                f"场景数: {len(content.scenes)}",
                f"对白场景数: {len(content.dialogues)}",
            ]
        },
    )
    save_markdown_output(summary, output_dir, "summary.md")

    status_icon = "✅" if is_usable and not requires_manual_review else "⚠️"
    click.echo(f"{status_icon} Script结果状态: {status} | 可直接使用: {'是' if is_usable else '否'} | 需人工审核: {'是' if requires_manual_review else '否'}")
    if warnings:
        click.echo(f"   警告: {warnings[0]}")
    if next_actions:
        click.echo(f"   下一步: {next_actions[0]}")


def _build_script_next_actions(
    *,
    warnings: list[str],
    requires_manual_review: bool,
    scenes_count: int,
) -> list[str]:
    """Build user-facing next actions for script output."""
    actions: list[str] = []
    if scenes_count == 0:
        actions.append("补充场景内容后再进入对白或分镜阶段。")
    if warnings:
        actions.append("检查 summary.md 中的警告，重点核对结构和对白完整性。")
    if requires_manual_review:
        actions.append("进行人工剧本审读后再交给导演或分镜环节。")
    if not actions:
        actions.append("可直接进入剧本审读、分镜或试读环节。")
    return actions
