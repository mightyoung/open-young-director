"""Blog content generation runner."""
import logging
import click

from crewai.cli.content.serializers import (
    build_review_markdown,
    ensure_output_dir,
    save_blog_content,
    save_json_output,
    save_markdown_output,
)

logger = logging.getLogger(__name__)


class BlogGenerationError(Exception):
    """Blog generation error with context."""

    def __init__(self, message: str, stage: str, cause: Exception = None):
        self.message = message
        self.stage = stage
        self.cause = cause
        super().__init__(f"[{stage}] {message}")


def run_blog(
    topic: str,
    platforms: list[str],
    keywords: list[str],
    title_style: str,
    output: str,
) -> None:
    """Run blog generation.

    Args:
        topic: Blog topic
        platforms: Target platforms
        keywords: SEO keywords
        title_style: Title style (seo/sensational/curiosity/list/guide/question/number)
        output: Output directory
    """
    from crewai.content.blog import BlogCrew, BlogCrewConfig

    # Validate inputs early (P1-17: strict contract testing)
    VALID_TITLE_STYLES = {"seo", "sensational", "curiosity", "list", "guide", "question", "number"}
    if title_style and title_style.lower() not in VALID_TITLE_STYLES:
        raise BlogGenerationError(
            f"不支持的标题风格: '{title_style}'。支持的风格: {', '.join(sorted(VALID_TITLE_STYLES))}",
            stage="config",
            cause=None,
        )

    try:
        blog_config = BlogCrewConfig(
            topic=topic,
            target_platforms=platforms,
            include_keywords=keywords,
            title_style=title_style,
        )
    except (TypeError, ValueError, AttributeError) as e:
        raise BlogGenerationError(f"配置创建失败: {e}", stage="config", cause=e)

    try:
        crew = BlogCrew(config=blog_config)
        result = crew.kickoff()
    except (RuntimeError, TimeoutError, IOError) as e:
        raise BlogGenerationError(f"BlogCrew执行失败: {e}", stage="generation", cause=e)

    # Save results - result.post is BlogPost
    post = result.post

    # P0: 检查 partial 结果契约 - 调用方必须处理非成功状态
    # P0 fix: 确保 post 不为 None 才访问其属性
    if post is None:
        raise BlogGenerationError(
            "BlogCrew返回的post为None，生成失败",
            stage="output",
            cause=None,
        )

    # P1: 检查 partial 结果契约 - 调用方必须处理非成功状态
    if hasattr(result, 'is_usable') and not result.is_usable:
        post_warnings = list(post.warnings) if hasattr(post, 'warnings') and post.warnings else []
        logger.warning(
            f"Blog生成结果为部分成功状态 (is_usable=False)。"
            f"内容需要人工审核: {post_warnings}"
        )
    try:
        output_dir = ensure_output_dir(output)
    except OSError as e:
        raise BlogGenerationError(f"输出目录创建失败: {output} - {e}", stage="output_dir", cause=e)

    warnings = list(post.warnings or []) if post.warnings else []
    status = post.status.value if post.status else "unknown"
    is_usable = bool(getattr(result, "is_usable", bool(post.body and len(post.body) > 0)))
    requires_manual_review = bool(getattr(result, "requires_manual_review", not is_usable))
    next_actions = _build_blog_next_actions(post.body, post.platform_contents, warnings, requires_manual_review)

    try:
        save_blog_content(post, output_dir)
    except (IOError, OSError) as e:
        raise BlogGenerationError(f"内容保存失败: {e}", stage="save_content", cause=e)

    try:
        save_json_output(
            {
                "topic": topic,
                "platforms": platforms,
                "keywords": keywords,
                "title_style": title_style,
                "title": post.title,
                "body_length": len(post.body) if post.body else 0,
                "warnings": warnings,
                "status": status,
                "is_usable": is_usable,
                "requires_manual_review": requires_manual_review,
                "next_actions": next_actions,
            },
            output_dir,
            "result.json",
        )
    except (IOError, OSError, ValueError) as e:
        raise BlogGenerationError(f"结果JSON保存失败: {e}", stage="save_result", cause=e)

    summary = build_review_markdown(
        content_type="Blog",
        topic=topic,
        title=post.title,
        status=status,
        is_usable=is_usable,
        requires_manual_review=requires_manual_review,
        warnings=warnings,
        next_actions=next_actions,
        extra_sections={
            "输出概览": [
                f"正文长度: {len(post.body) if post.body else 0} 字符",
                f"平台内容数: {len(post.platform_contents)}",
                f"标题风格: {title_style}",
            ]
        },
    )
    save_markdown_output(summary, output_dir, "summary.md")

    status_icon = "✅" if is_usable and not requires_manual_review else "⚠️"
    click.echo(f"{status_icon} Blog结果状态: {status} | 可直接使用: {'是' if is_usable else '否'} | 需人工审核: {'是' if requires_manual_review else '否'}")
    if warnings:
        click.echo(f"   警告: {warnings[0]}")
    if next_actions:
        click.echo(f"   下一步: {next_actions[0]}")


def _build_blog_next_actions(
    body: str,
    platform_contents: dict,
    warnings: list[str],
    requires_manual_review: bool,
) -> list[str]:
    """Build user-facing next actions for blog output."""
    actions: list[str] = []
    if not body:
        actions.append("补充或重写正文后再发布。")
    if not platform_contents:
        actions.append("检查平台适配结果，必要时手动补齐各平台版本。")
    if warnings:
        actions.append("优先处理 summary.md 中的警告项，再进行发布。")
    if requires_manual_review:
        actions.append("完成人工审阅后再导出最终版本。")
    if not actions:
        actions.append("可直接审阅标题与正文，确认后发布。")
    return actions
