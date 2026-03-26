"""Content generation CLI commands - novel, script, blog, podcast."""
import click
import os
import json
from pathlib import Path


def _ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_json_output(result, output_dir: Path, filename: str) -> None:
    """Save result as JSON file."""
    output_file = output_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)


def _create_llm_from_env():
    """Create an LLM instance from environment variables.

    Checks Gemini, DeepSeek, Doubao, Kimi, MiniMax in priority order
    and returns the first configured one.
    """
    # Check Gemini first (reliable, widely compatible)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        from crewai.llm import LLM
        # Try gemini-2.5-flash, fall back to gemini-1.5-pro
        return LLM(model="gemini/gemini-2.5-flash", api_key=gemini_key)

    # Check DeepSeek (widely compatible, reliable)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        from crewai.llm import LLM
        return LLM(model="deepseek/deepseek-chat", api_key=deepseek_key)

    # Check Doubao/Volcengine (OpenAI-compatible endpoint)
    doubao_key = os.environ.get("DOUBAO_API_KEY", "").strip()
    doubao_url = os.environ.get("DOUBAO_API_HOST", "").strip()
    doubao_model = os.environ.get("DOUBAO_MODEL", "").strip()

    if doubao_key and doubao_url:
        from crewai.llm import LLM
        return LLM(
            model=doubao_model or "doubao-seed-2-0-pro-260215",
            api_key=doubao_key,
            base_url=doubao_url,
        )

    # Check Kimi/Moonshot AI (OpenAI-compatible endpoint)
    kimi_key = os.environ.get("KIMI_API_KEY", "").strip()
    kimi_model = os.environ.get("KIMI_MODEL_NAME", "").strip()

    if kimi_key:
        from crewai.llm import LLM
        model = kimi_model or "moonshot-v1-8k"
        return LLM(
            model=model,
            api_key=kimi_key,
            base_url="https://api.moonshot.cn/v1",
        )

    # Check MiniMax (common in China, OpenAI-compatible endpoint)
    minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    minimax_url = os.environ.get("MINIMAX_BASE_URL", "").strip()
    minimax_model = os.environ.get("MINIMAX_MODEL", "").strip()

    if minimax_key and minimax_url:
        from crewai.llm import LLM
        # Use the model string as-is for OpenAI-compatible endpoint
        model = minimax_model or "MiniMax-M2.7-highspeed"
        return LLM(
            model=model,
            api_key=minimax_key,
            base_url=minimax_url,
        )

    # Last resort: let crewai auto-detect (will use OPENAI_API_KEY from env)
    return None


def _run_novel_interactive(crew, output: str, stop_at: str | None):
    """Interactive stage-by-stage novel creation with human confirmation.

    Args:
        crew: NovelCrew instance
        output: Output directory
        stop_at: Optional stage to stop at (limits interactive sequence)
    """
    import json

    stages = ["outline", "evaluation", "volume", "summary"]
    stop_idx = stages.index(stop_at) if stop_at else len(stages)

    output_dir = _ensure_output_dir(output)
    state_file = Path(output_dir) / "pipeline_state.json"

    for i, stage in enumerate(stages[:stop_idx + 1]):
        click.echo(f"\n{'='*50}")
        click.echo(f"📍 阶段 {i+1}/{stop_idx + 1}: {stage.upper()}")
        click.echo(f"{'='*50}")

        # Pass pipeline_state_path to load existing state for skip-logic
        result = crew.kickoff(
            stop_at=stage,
            pipeline_state_path=str(state_file) if state_file.exists() else None,
        )

        # Save state after each stage
        crew.save_pipeline_state(str(state_file))

        # Display stage result
        pipeline_state = result.metadata.get("pipeline_state", {})
        click.echo(f"\n📊 阶段完成: {stage}")
        click.echo(f"   文件: {state_file}")

        if stage == "outline":
            click.echo(f"   世界: {pipeline_state.get('world_name', 'N/A')}")
            click.echo(f"   情节: {'已就绪' if pipeline_state.get('plot_ready') else '未就绪'}")
        elif stage == "evaluation":
            click.echo(f"   通过: {pipeline_state.get('evaluation_passed', False)}")
            click.echo(f"   评分: {pipeline_state.get('evaluation_score', 'N/A')}")
            issues = pipeline_state.get("evaluation_issues", [])
            if issues:
                click.echo(f"   问题: {', '.join(str(x) for x in issues[:3])}")
        elif stage == "volume":
            click.echo(f"   卷数: {pipeline_state.get('volumes_count', 0)}")
        elif stage == "summary":
            click.echo(f"   概要数: {pipeline_state.get('summaries_count', 0)}")

        # Ask before continuing
        if i < stop_idx:
            click.echo()
            confirmed = click.confirm(f"✅ 阶段 {stage} 完成。是否继续到下一阶段？", default=True)
            if not confirmed:
                click.echo(f"⏸️ 已暂停。可使用 --resume-from {stages[i+1]} 继续。")
                return

    # All stages complete, run writing
    click.echo(f"\n{'='*50}")
    click.echo(f"📖 开始撰写章节...")
    click.echo(f"{'='*50}")
    # Resume from saved state — kickoff will skip already-completed phases
    result = crew.kickoff(pipeline_state_path=str(state_file))

    # Final save
    if hasattr(result, "content") and result.content:
        novel = result.content
        if hasattr(novel, "chapters") and novel.chapters:
            chapters_dir = output_dir / "chapters"
            chapters_dir.mkdir(exist_ok=True)
            for chapter in novel.chapters:
                chapter_file = chapters_dir / f"chapter_{chapter.chapter_num}.txt"
                with open(chapter_file, "w", encoding="utf-8") as f:
                    f.write(chapter.content)
        _save_json_output(
            {
                "topic": crew.config.get("topic", ""),
                "chapters_count": len(novel.chapters),
                "word_count": novel.total_word_count,
            },
            output_dir,
            "result.json",
        )
    click.echo(f"✅ 小说已生成: {output_dir}")


def _run_novel_creation(
    topic: str,
    words: int,
    style: str,
    output: str,
    chapters: int,
    stop_at: str | None = None,
    resume_from: str | None = None,
    pipeline_state_path: str | None = None,
    interactive: bool = False,
    review_each_chapter: bool = False,
):
    """Core novel creation logic — usable both from CLI and programmatic calls.

    Args:
        topic: 小说主题
        words: 目标字数
        style: 小说风格
        output: 输出目录
        chapters: 章节数（0表示自动）
        stop_at: 在指定阶段暂停 (outline/evaluation/volume/summary)
        resume_from: 从指定阶段恢复 (outline/evaluation/volume/summary)
        pipeline_state_path: 流水线状态文件路径（用于 resume）
    """
    # Load .env from project root so API keys are available to litellm
    from pathlib import Path
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not installed

    from crewai.content.novel import NovelCrew

    click.echo(f"🚀 开始生成小说: {topic}")
    click.echo(f"   目标字数: {words}")
    click.echo(f"   小说风格: {style}")
    if stop_at:
        click.echo(f"   停止阶段: {stop_at}")
    if resume_from:
        click.echo(f"   恢复阶段: {resume_from}")

    try:
        # Create LLM instance from environment or defaults
        llm = _create_llm_from_env()

        config = {
            "topic": topic,
            "style": style,
            "target_words": words,
            "num_chapters": chapters if chapters > 0 else 10,
            "genre": style,
            "llm": llm,
        }
        crew = NovelCrew(config=config)

        # Interactive mode: stage-by-stage with human confirmation
        if interactive:
            _run_novel_interactive(crew, output, stop_at)
            return

        # Handle resume mode
        if resume_from and pipeline_state_path:
            click.echo(f"📂 从状态文件恢复: {pipeline_state_path}")
            crew.load_pipeline_state(pipeline_state_path)

            # Determine stop_at based on resume_from
            # kickoff() will skip already-completed phases using state-caching
            resume_stop_at: str | None = None
            if resume_from == "evaluation":
                # Generate volumes (evaluation is already done, stored in state)
                resume_stop_at = "volume"
            elif resume_from == "volume":
                # Generate volumes (or skip if already done)
                resume_stop_at = "volume"
            elif resume_from == "summary":
                # Generate chapter summaries (or skip if already done)
                resume_stop_at = "summary"
            elif resume_from == "writing":
                # Run writing to completion (skip all pre-writing phases)
                resume_stop_at = None  # No stop, runs to completion

            # Use kickoff with state-caching to skip already-done phases
            state_path = pipeline_state_path if Path(pipeline_state_path).exists() else None
            result = crew.kickoff(stop_at=resume_stop_at, pipeline_state_path=state_path, review_each_chapter=review_each_chapter)

            # If stopped at a stage (not completed writing), return
            if result.metadata.get("stopped"):
                click.echo(f"⏸️ 已停止在阶段: {result.metadata.get('pipeline_state', {}).get('stage', 'unknown')}")
                crew.save_pipeline_state(pipeline_state_path)
                return

            # Writing completed — fall through to result saving below
        else:
            # Normal (non-resume) mode
            state_path = pipeline_state_path if pipeline_state_path and Path(pipeline_state_path).exists() else None
            result = crew.kickoff(stop_at=stop_at, pipeline_state_path=state_path, review_each_chapter=review_each_chapter)

            # 检查是否停止在某个阶段（没有完整内容）
            if result.metadata.get("stopped"):
                click.echo(f"⏸️ 流水线已停止在阶段: {result.metadata.get('pipeline_state', {}).get('stage', 'unknown')}")

                # 保存流水线状态
                state_file = Path(output) / "pipeline_state.json"
                crew.save_pipeline_state(str(state_file))
                click.echo(f"💾 流水线状态已保存: {state_file}")

                # 保存阶段结果
                pipeline_summary = result.metadata.get("pipeline_state", {})
                _save_json_output(pipeline_summary, Path(output), "pipeline_stage.json")
                click.echo(f"✅ 阶段结果已保存: {output}")
                return

        # 保存完整小说结果（resume或正常完成都会走到这里）
        output_dir = _ensure_output_dir(output)
        if hasattr(result, "content") and result.content:
            novel = result.content
            # 保存小说大纲
            if hasattr(novel, "world_output") and novel.world_output:
                world_data = novel.world_output.__dict__ if hasattr(novel.world_output, "__dict__") else novel.world_output
                _save_json_output(world_data, output_dir, "world.json")

            # 保存章节内容
            if hasattr(novel, "chapters") and novel.chapters:
                chapters_dir = output_dir / "chapters"
                chapters_dir.mkdir(exist_ok=True)
                for chapter in novel.chapters:
                    chapter_file = chapters_dir / f"chapter_{chapter.chapter_num}.txt"
                    content = chapter.content if hasattr(chapter, "content") else str(chapter)
                    with open(chapter_file, "w", encoding="utf-8") as f:
                        f.write(content)

            # 保存完整结果
            _save_json_output(
                {
                    "topic": topic,
                    "target_words": words,
                    "style": style,
                    "title": novel.title if hasattr(novel, "title") else topic,
                    "chapters_count": len(novel.chapters) if hasattr(novel, "chapters") else 0,
                    "word_count": novel.total_word_count if hasattr(novel, "total_word_count") else 0,
                },
                output_dir,
                "result.json",
            )

        click.echo(f"✅ 小说已生成: {output_dir}")

    except Exception as e:
        click.echo(f"❌ 生成失败: {str(e)}", err=True)
        raise


@click.command()
@click.argument("topic")
@click.option("--words", default=100000, help="目标字数")
@click.option("--style", default="urban", help="小说风格 (urban/xianxia/doushi/modern)")
@click.option("--output", default="./novel_output", help="输出目录")
@click.option("--stop-at", default=None, help="在指定阶段暂停 (outline/evaluation/volume/summary)")
@click.option("--resume-from", default=None, help="从指定阶段恢复 (evaluation/volume/summary/writing)")
@click.option("--interactive", is_flag=True, help="交互模式：每阶段完成后等待确认再继续")
@click.option("--review-each-chapter", is_flag=True, help="逐章审核：每章写完后等待确认再继续")
def create_novel(
    topic: str,
    words: int,
    style: str,
    output: str,
    stop_at: str | None,
    resume_from: str | None,
    interactive: bool,
    review_each_chapter: bool,
):
    """创建小说项目 (Create a new novel project).

    Examples:
        # 完整生成
        crewai create novel "都市修仙" --words 100000 --style xianxia

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
    """
    _run_novel_creation(
        topic=topic,
        words=words,
        style=style,
        output=output,
        chapters=0,
        stop_at=stop_at,
        resume_from=resume_from,
        pipeline_state_path=str(Path(output) / "pipeline_state.json") if (stop_at or resume_from or interactive) else None,
        interactive=interactive,
        review_each_chapter=review_each_chapter,
    )


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
    from crewai.content.podcast import PodcastCrew

    click.echo(f"🎙️ 开始生成播客: {topic}")
    click.echo(f"   时长: {duration} 分钟")
    click.echo(f"   主持人: {hosts}")
    click.echo(f"   风格: {style}")

    try:
        crew = PodcastCrew(
            topic=topic,
            duration_minutes=duration,
            hosts=hosts,
            style=style,
            include_interview=include_interview,
            include_ads=include_ads,
        )

        result = crew.kickoff()

        # 保存结果
        output_dir = _ensure_output_dir(output)

        # 保存脚本
        if hasattr(result, "script") and result.script:
            script_file = output_dir / "script.txt"
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(result.script)

        # 保存时间戳
        if hasattr(result, "timestamps") and result.timestamps:
            _save_json_output(result.timestamps, output_dir, "timestamps.json")

        # 保存 shownotes
        if hasattr(result, "shownotes") and result.shownotes:
            _save_json_output(result.shownotes, output_dir, "shownotes.json")

        # 保存完整结果
        _save_json_output(
            {
                "topic": topic,
                "duration": duration,
                "hosts": hosts,
                "style": style,
                "script_length": len(result.script) if hasattr(result, "script") else 0,
            },
            output_dir,
            "result.json",
        )

        click.echo(f"✅ 播客已生成: {output_dir}")

    except Exception as e:
        click.echo(f"❌ 生成失败: {str(e)}", err=True)
        raise


@click.command()
@click.argument("topic")
@click.option("--platforms", default="medium,wordpress", help="目标平台 (逗号分隔)")
@click.option("--keywords", default="", help="SEO关键词 (逗号分隔)")
@click.option("--output", default="./blog_output", help="输出目录")
@click.option("--title-style", default="seo", help="标题风格 (seo/clickbait/technical)")
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
    from crewai.content.blog import BlogCrew

    platform_list = [p.strip() for p in platforms.split(",")]
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else []

    click.echo(f"📝 开始生成博客: {topic}")
    click.echo(f"   平台: {', '.join(platform_list)}")
    click.echo(f"   关键词: {', '.join(keyword_list) if keyword_list else '无'}")

    try:
        crew = BlogCrew(
            topic=topic,
            target_platforms=platform_list,
            include_keywords=keyword_list,
            title_style=title_style,
        )

        result = crew.kickoff()

        # 保存结果
        output_dir = _ensure_output_dir(output)

        # 保存各平台内容
        if hasattr(result, "platform_contents") and result.platform_contents:
            for platform, content in result.platform_contents.items():
                platform_dir = output_dir / platform
                platform_dir.mkdir(exist_ok=True)

                if hasattr(content, "title"):
                    title_file = platform_dir / "title.txt"
                    with open(title_file, "w", encoding="utf-8") as f:
                        f.write(content.title)

                if hasattr(content, "body"):
                    body_file = platform_dir / "content.txt"
                    with open(body_file, "w", encoding="utf-8") as f:
                        f.write(content.body)

                if hasattr(content, "seo_data"):
                    seo_file = platform_dir / "seo.json"
                    with open(seo_file, "w", encoding="utf-8") as f:
                        json.dump(content.seo_data, f, ensure_ascii=False, indent=2, default=str)

        # 保存钩子选项
        if hasattr(result, "hook_options") and result.hook_options:
            _save_json_output(
                [
                    {"variant": h.variant, "hook_text": h.hook_text, "type": h.hook_type, "score": h.engagement_score}
                    for h in result.hook_options
                ],
                output_dir,
                "hooks.json",
            )

        # 保存完整结果
        _save_json_output(
            {
                "topic": topic,
                "platforms": platform_list,
                "keywords": keyword_list,
                "title_style": title_style,
            },
            output_dir,
            "result.json",
        )

        click.echo(f"✅ 博客已生成: {output_dir}")

    except Exception as e:
        click.echo(f"❌ 生成失败: {str(e)}", err=True)
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
    from crewai.content.script import ScriptCrew

    click.echo(f"🎬 开始生成剧本: {topic}")
    click.echo(f"   格式: {format}")
    click.echo(f"   时长: {duration} 分钟")
    click.echo(f"   幕数: {acts}")

    try:
        crew = ScriptCrew(
            topic=topic,
            script_format=format,
            target_duration=duration,
            num_acts=acts,
        )

        result = crew.kickoff()

        # 保存结果
        output_dir = _ensure_output_dir(output)

        # 保存beat sheet
        if hasattr(result, "beat_sheet") and result.beat_sheet:
            _save_json_output(
                [
                    {
                        "act": beat.act,
                        "beats": [
                            {
                                "number": b.number,
                                "name": b.name,
                                "description": b.description,
                                "scene_purpose": b.scene_purpose,
                                "turning_point": b.turning_point,
                            }
                            for b in beat.beats
                        ],
                    }
                    for beat in result.beat_sheet
                ],
                output_dir,
                "beat_sheet.json",
            )

        # 保存场景
        if hasattr(result, "scenes") and result.scenes:
            scenes_dir = output_dir / "scenes"
            scenes_dir.mkdir(exist_ok=True)
            for i, scene in enumerate(result.scenes):
                scene_file = scenes_dir / f"scene_{i+1}.txt"
                content = scene.content if hasattr(scene, "content") else str(scene)
                with open(scene_file, "w", encoding="utf-8") as f:
                    f.write(content)

        # 保存对白
        if hasattr(result, "dialogues") and result.dialogues:
            dialogues_dir = output_dir / "dialogues"
            dialogues_dir.mkdir(exist_ok=True)
            for i, dialogue in enumerate(result.dialogues):
                dialogue_file = dialogues_dir / f"dialogue_{i+1}.txt"
                content = dialogue.content if hasattr(dialogue, "content") else str(dialogue)
                with open(dialogue_file, "w", encoding="utf-8") as f:
                    f.write(content)

        # 保存完整结果
        _save_json_output(
            {
                "topic": topic,
                "format": format,
                "duration": duration,
                "acts": acts,
                "scenes_count": len(result.scenes) if hasattr(result, "scenes") else 0,
            },
            output_dir,
            "result.json",
        )

        click.echo(f"✅ 剧本已生成: {output_dir}")

    except Exception as e:
        click.echo(f"❌ 生成失败: {str(e)}", err=True)
        raise
