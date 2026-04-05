"""Podcast content generation runner."""
from dataclasses import dataclass, field
import click

from crewai.cli.content.serializers import (
    build_review_markdown,
    ensure_output_dir,
    save_json_output,
    save_markdown_output,
    save_podcast_content,
)


class PodcastGenerationError(Exception):
    """Podcast generation error with context."""

    def __init__(self, message: str, stage: str, cause: Exception = None):
        self.message = message
        self.stage = stage
        self.cause = cause
        super().__init__(f"[{stage}] {message}")


@dataclass
class PodcastConfig:
    """Podcast configuration for CLI."""
    topic: str
    duration_minutes: int
    hosts: int
    style: str
    format_type: str = "narrative"  # Maps from style: conversational → narrative, etc.
    include_interview: bool = False
    include_ads: bool = False
    # Wired fields: guest_name activates interview section, sponsors activates ad_reads
    guest_name: str = ""
    sponsors: list = field(default_factory=list)


def run_podcast(
    topic: str,
    duration: int,
    hosts: int,
    style: str,
    include_interview: bool,
    include_ads: bool,
    output: str,
) -> None:
    """Run podcast generation.

    Args:
        topic: Podcast topic
        duration: Duration in minutes
        hosts: Number of hosts
        style: Podcast style
        include_interview: Whether to include interview segment
        include_ads: Whether to include ad reads
        output: Output directory
    """
    from crewai.content.podcast import PodcastCrew

    # Validate inputs early (P1-17: strict contract testing)
    if duration <= 0:
        raise PodcastGenerationError(
            f"播客时长必须大于0分钟，当前值: {duration}。请使用 --duration 参数指定正整数。",
            stage="config",
            cause=None,
        )
    if hosts <= 0:
        raise PodcastGenerationError(
            f"主持人数量必须大于0，当前值: {hosts}。请使用 --hosts 参数指定正整数。",
            stage="config",
            cause=None,
        )
    VALID_STYLES = {"conversational", "narrative", "interview", "educational"}
    if style and style.lower() not in VALID_STYLES:
        raise PodcastGenerationError(
            f"不支持的播客风格: '{style}'。支持的风格: {', '.join(sorted(VALID_STYLES))}",
            stage="config",
            cause=None,
        )

    # Wire CLI flags to PodcastCrew's actual business logic
    guest_name = f"待定嘉宾" if include_interview else ""
    sponsors = [{"name": "默认赞助商", "description": "感谢赞助", "type": "mid_roll", "duration": 60}] if include_ads else []

    # Map CLI style to format_type expected by PodcastCrew
    # CLI style options: conversational, narrative, interview, educational
    # PodcastCrew format_type: narrative, conversational, interview, educational
    format_type = style if style else "narrative"

    try:
        podcast_config = PodcastConfig(
            topic=topic,
            duration_minutes=duration,
            hosts=hosts,
            style=style,
            format_type=format_type,
            include_interview=include_interview,
            include_ads=include_ads,
            guest_name=guest_name,
            sponsors=sponsors,
        )
    except (TypeError, ValueError, AttributeError) as e:
        raise PodcastGenerationError(f"配置创建失败: {e}", stage="config", cause=e)

    try:
        crew = PodcastCrew(config=podcast_config)
        result = crew.kickoff()
    except (RuntimeError, TimeoutError, IOError) as e:
        raise PodcastGenerationError(f"PodcastCrew执行失败: {e}", stage="generation", cause=e)

    # Save results
    content = result.content
    try:
        output_dir = ensure_output_dir(output)
    except OSError as e:
        raise PodcastGenerationError(f"输出目录创建失败: {output} - {e}", stage="output_dir", cause=e)

    try:
        save_podcast_content(content, output_dir)
    except (IOError, OSError) as e:
        raise PodcastGenerationError(f"内容保存失败: {e}", stage="save_content", cause=e)

    quality_report = result.metadata.get("quality_report", {})
    failed_sections = result.metadata.get("failed_sections", {})
    warnings = list(quality_report.get("warnings", []))
    errors = list(quality_report.get("errors", []))
    status = result.metadata.get("output_status", content.status)
    is_usable = bool(quality_report.get("is_usable", content.status != "failed"))
    requires_manual_review = bool(quality_report.get("requires_manual_review", content.status == "partial"))
    next_actions = _build_podcast_next_actions(
        status=status,
        requires_manual_review=requires_manual_review,
        failed_sections=failed_sections,
        warnings=warnings,
    )

    try:
        save_json_output(
            {
                "topic": topic,
                "duration": duration,
                "hosts": hosts,
                "style": style,
                "title": content.title,
                "total_duration_minutes": content.total_duration_minutes,
                "status": content.status,
                "failed_sections": failed_sections,
                "is_usable": is_usable,
                "requires_manual_review": requires_manual_review,
                "next_actions": next_actions,
                "metadata": result.metadata,
            },
            output_dir,
            "result.json",
        )
    except (IOError, OSError, ValueError) as e:
        raise PodcastGenerationError(f"结果JSON保存失败: {e}", stage="save_result", cause=e)

    summary = build_review_markdown(
        content_type="Podcast",
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
                f"总时长: {content.total_duration_minutes} 分钟",
                f"段落数: {len(content.segments)}",
                f"失败区块数: {len(failed_sections)}",
            ]
        },
    )
    save_markdown_output(summary, output_dir, "summary.md")

    status_icon = "✅" if is_usable and not requires_manual_review else "⚠️"
    click.echo(f"{status_icon} Podcast结果状态: {status} | 可直接使用: {'是' if is_usable else '否'} | 需人工审核: {'是' if requires_manual_review else '否'}")
    if failed_sections:
        click.echo(f"   失败区块: {', '.join(sorted(failed_sections.keys()))}")
    if next_actions:
        click.echo(f"   下一步: {next_actions[0]}")


def _build_podcast_next_actions(
    *,
    status: str,
    requires_manual_review: bool,
    failed_sections: dict[str, str],
    warnings: list[str],
) -> list[str]:
    """Build user-facing next actions for podcast output."""
    actions: list[str] = []
    if failed_sections:
        actions.append(f"补生成或手工修订失败区块: {', '.join(sorted(failed_sections.keys()))}。")
    if warnings:
        actions.append("检查 summary.md 中的警告，再确认脚本可录制。")
    if requires_manual_review or status == "partial":
        actions.append("人工通读脚本并确认段落衔接、口播和访谈结构。")
    if status == "failed":
        actions.append("修复配置或模型问题后重新生成。")
    if not actions:
        actions.append("可直接进入录制或后续剪辑准备。")
    return actions
