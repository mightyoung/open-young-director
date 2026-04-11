"""Content generation CLI commands - novel, script, blog, podcast."""
from pathlib import Path

import click

from crewai.cli.content.blog_runner import run_blog
from crewai.cli.content.novel_runner import run_novel_creation
from crewai.cli.content.podcast_runner import run_podcast
from crewai.cli.content.script_runner import run_script


@click.command()
@click.argument("topic")
@click.option("--words", default=100000, help="目标字数")
@click.option("--chapters", default=0, help="章节数量 (0=自动根据字数计算)")
@click.option("--style", default="urban", help="小说风格 (urban/xianxia/doushi/modern)")
@click.option("--output", default="./novel_output", help="输出目录")
@click.option("--stop-at", default=None, help="在指定阶段暂停 (outline/evaluation/volume/summary)")
@click.option("--resume-from", default=None, help="从指定阶段恢复 (evaluation/volume/summary/writing)")
@click.option("--pipeline-state-path", default=None, help="流水线状态文件路径（用于恢复）")
@click.option("--interactive", is_flag=True, help="交互模式：每阶段完成后等待确认再继续")
@click.option("--review-each-chapter", is_flag=True, help="逐章审核：每章写完后等待确认再继续")
@click.option("--seed-variant", default=None, help="Seed变体：用于生成同一主题的不同变体")
@click.option("--engine", default="v1", type=click.Choice(["v1", "v2"]), help="执行引擎 (v1=CrewAI, v2=纯Python流水线)")
def create_novel(
    topic: str,
    words: int,
    chapters: int,
    style: str,
    output: str,
    stop_at: str | None,
    resume_from: str | None,
    pipeline_state_path: str | None,
    interactive: bool,
    review_each_chapter: bool,
    seed_variant: str | None,
    engine: str,
):
    """创建小说项目 (Create a new novel project).

    Examples:
        # 完整生成 100万字，100章节
        crewai create novel "都市修仙" --words 1000000 --chapters 100 --style xianxia

        # 完整生成 200万字，自动计算章节数 (每章约1万字)
        crewai create novel "都市修仙" --words 2000000

        # 在大纲阶段暂停（查看大纲）
        crewai create novel "都市修仙" --stop-at outline

        # 在评估阶段暂停（查看评估结果）
        crewai create novel "都市修仙" --stop-at evaluation

        # 在分卷大纲后暂停
        crewai create novel "都市修仙" --stop-at volume

        # 在章节概要后暂停
        crewai create novel "都市修仙" --stop-at summary

        # 交互模式：每个阶段暂停等待确认
        crewai create novel "都市修仙" --interactive

        # 从流水线状态恢复继续
        crewai create novel "都市修仙" --resume-from volume

        # 逐章审核模式
        crewai create novel "都市修仙" --review-each-chapter

        # 逐章审核后恢复继续
        crewai create novel "都市修仙" --review-each-chapter
        # (暂停后) crewai create novel "都市修仙" --resume-from writing --pipeline-state-path "./novels/xxx/.pending_chapter.json"
    """
    try:
        run_novel_creation(
            topic=topic,
            words=words,
            style=style,
            output=output,
            chapters=chapters,
            stop_at=stop_at,
            resume_from=resume_from,
            pipeline_state_path=pipeline_state_path or (
                str(Path(output) / "pipeline_state.json")
                if (stop_at or resume_from or interactive or review_each_chapter) else None
            ),
            interactive=interactive,
            review_each_chapter=review_each_chapter,
            seed_variant=seed_variant,
            engine=engine,
        )
    except ValueError as e:
        click.echo(f"❌ 参数错误: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ 小说生成失败: {e}", err=True)
        raise


@click.command()
@click.argument("topic")
@click.option("--duration", default=30, help="播客时长 (分钟)")
@click.option("--hosts", default=2, help="主持人数量")
@click.option("--style", default="conversational", help="播客风格")
@click.option("--output", default="./podcast_output", help="输出目录")
@click.option("--include-interview", is_flag=True, help="包含访谈环节")
@click.option("--include-ads", is_flag=True, help="包含广告口播")
def create_podcast(
    topic: str,
    duration: int,
    hosts: int,
    style: str,
    output: str,
    include_interview: bool,
    include_ads: bool,
):
    """创建播客项目 (Create a new podcast project).

    Example:
        crewai create podcast "AI技术趋势" --duration 30 --hosts 2
    """
    import click

    click.echo(f"🎙️ 开始生成播客: {topic}")
    click.echo(f"   时长: {duration} 分钟")
    click.echo(f"   主持人: {hosts}")
    click.echo(f"   风格: {style}")

    try:
        run_podcast(
            topic=topic,
            duration=duration,
            hosts=hosts,
            style=style,
            include_interview=include_interview,
            include_ads=include_ads,
            output=output,
        )
        click.echo(f"✅ 播客已生成: {output}")

    except Exception as e:
        error_msg = f"❌ 生成失败: {e!s}"
        if hasattr(e, 'stage') and hasattr(e, 'cause') and e.cause:
            error_msg += f"\n   阶段: {e.stage}"
            error_msg += f"\n   原因: {e.cause}"
        click.echo(error_msg, err=True)
        raise


@click.command()
@click.argument("topic")
@click.option("--platforms", default="medium,wordpress", help="目标平台 (逗号分隔)")
@click.option("--keywords", default="", help="SEO关键词 (逗号分隔)")
@click.option("--output", default="./blog_output", help="输出目录")
@click.option("--title-style", default="seo", help="标题风格 (seo/sensational/curiosity/list/guide/question/number)")
def create_blog(
    topic: str,
    platforms: str,
    keywords: str,
    output: str,
    title_style: str,
):
    """创建博客项目 (Create a new blog project).

    Example:
        crewai create blog "Python异步编程" --platforms medium,zhihu --keywords python,async
    """
    import click

    platform_list = [p.strip() for p in platforms.split(",")]
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []

    click.echo(f"📝 开始生成博客: {topic}")
    click.echo(f"   平台: {', '.join(platform_list)}")
    click.echo(f"   关键词: {', '.join(keyword_list) if keyword_list else '无'}")

    try:
        run_blog(
            topic=topic,
            platforms=platform_list,
            keywords=keyword_list,
            title_style=title_style,
            output=output,
        )
        click.echo(f"✅ 博客已生成: {output}")

    except Exception as e:
        error_msg = f"❌ 生成失败: {e!s}"
        if hasattr(e, 'stage') and hasattr(e, 'cause') and e.cause:
            error_msg += f"\n   阶段: {e.stage}"
            error_msg += f"\n   原因: {e.cause}"
        click.echo(error_msg, err=True)
        raise


@click.command()
@click.argument("topic")
@click.option("--format", default="film", help="脚本格式 (film/tv/web series)")
@click.option("--duration", default=120, help="目标时长 (分钟)")
@click.option("--output", default="./script_output", help="输出目录")
@click.option("--acts", default=3, help="幕数")
def create_script(
    topic: str,
    format: str,
    duration: int,
    output: str,
    acts: int,
):
    """创建剧本项目 (Create a new script project).

    Example:
        crewai create script "科幻故事" --format film --duration 120
    """
    import click

    click.echo(f"🎬 开始生成剧本: {topic}")
    click.echo(f"   格式: {format}")
    click.echo(f"   时长: {duration} 分钟")
    click.echo(f"   幕数: {acts}")

    try:
        run_script(
            topic=topic,
            format=format,
            target_runtime=duration,
            num_acts=acts,
            output=output,
        )
        click.echo(f"✅ 剧本已生成: {output}")

    except Exception as e:
        error_msg = f"❌ 生成失败: {e!s}"
        if hasattr(e, 'stage') and hasattr(e, 'cause') and e.cause:
            error_msg += f"\n   阶段: {e.stage}"
            error_msg += f"\n   原因: {e.cause}"
        click.echo(error_msg, err=True)
        raise
