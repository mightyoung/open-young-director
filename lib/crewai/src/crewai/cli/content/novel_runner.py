"""Novel content generation runner - handles execution, approval, resume, serialization."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import click

from crewai.cli.content.serializers import (
    build_review_markdown,
    ensure_output_dir,
    save_json_output,
    save_markdown_output,
)


def _resolve_approval_state_path(relative_path: str) -> Path:
    """Resolve a relative approval state path to absolute."""
    state_file = Path(relative_path)
    if not state_file.is_absolute():
        state_file = Path.cwd() / state_file
    return state_file.resolve()


def display_approval_message(
    topic: str,
    pending_chapter: str,
    pending_title: str,
    state_path: str,
) -> None:
    """Display the chapter approval pending message.

    Args:
        topic: Novel topic
        pending_chapter: Chapter number pending approval
        pending_title: Title of pending chapter
        state_path: Path to the pending state file
    """
    click.echo(f"⏸️ 章节 {pending_chapter} ({pending_title}) 已完成，等待审批...")

    state_file_abs = _resolve_approval_state_path(state_path)
    click.echo(f"💾 审批状态已保存: {state_file_abs}")
    click.echo("   请审阅章节内容后，使用以下命令继续:")
    click.echo(f'   crewai create novel "{topic}" --resume-from writing --pipeline-state-path "{state_file_abs}"')


def save_novel_result(
    result: Any,
    crew: Any,
    topic: str,
    words: int,
    style: str,
    output: str,
    exec_status: str,
) -> None:
    """Save novel result to output directory.

    Args:
        result: Crew kickoff result with content metadata
        topic: Novel topic
        words: Target word count
        style: Novel style
        output: Output directory
        exec_status: Execution status (success/partial/failed)
    """
    output_dir = ensure_output_dir(output)

    if hasattr(result, "content") and result.content:
        novel = result.content
        # 保存小说大纲
        if hasattr(novel, "world_output") and novel.world_output:
            world_data = novel.world_output.__dict__ if hasattr(novel.world_output, "__dict__") else novel.world_output
            save_json_output(world_data, output_dir, "world.json")

        # 保存章节内容
        if hasattr(novel, "chapters") and novel.chapters:
            chapters_dir = output_dir / "chapters"
            chapters_dir.mkdir(exist_ok=True)
            for chapter in novel.chapters:
                chapter_file = chapters_dir / f"chapter_{chapter.chapter_num}.txt"
                content = chapter.content if hasattr(chapter, "content") else str(chapter)
                with open(chapter_file, "w", encoding="utf-8") as f:
                    f.write(content)

        # P1: 提取质量报告 (统一输出契约)
        quality_report = result.metadata.get("quality_report", {}) if hasattr(result, "metadata") else {}
        warnings = list(quality_report.get("warnings", []))
        errors = list(quality_report.get("errors", []))
        is_usable = bool(quality_report.get("is_usable", exec_status == "success"))
        requires_manual_review = bool(quality_report.get("requires_manual_review", bool(warnings or errors)))
        status = exec_status if exec_status else ("success" if is_usable else "failed")
        task_dashboard = None
        if hasattr(crew, "task_registry") and crew.task_registry is not None:
            try:
                snapshot = crew.task_registry.snapshot()
                if isinstance(snapshot, dict):
                    task_dashboard = snapshot
            except Exception:
                task_dashboard = None

        # 构建下一步指引
        next_actions = _build_novel_next_actions(
            novel=novel,
            warnings=warnings,
            errors=errors,
            is_usable=is_usable,
            requires_manual_review=requires_manual_review,
        )
        context_compaction = result.metadata.get("context_compaction", {}) if hasattr(result, "metadata") else {}
        compaction_lines: list[str] = []
        if context_compaction:
            for chapter_num, report in context_compaction.items():
                if not isinstance(report, dict):
                    continue
                compaction_lines.append(
                    f"第{chapter_num}章: saved {report.get('estimated_tokens_saved', 0)} tokens, "
                    f"trimmed {report.get('trimmed_character_count', 0)} characters / "
                    f"{report.get('trimmed_foreshadowing_count', 0)} foreshadowing entries"
                )

        # 保存完整结果 (P1: 统一输出契约)
        save_json_output(
            {
                "topic": topic,
                "target_words": words,
                "style": style,
                "title": novel.title if hasattr(novel, "title") else topic,
                "chapters_count": len(novel.chapters) if hasattr(novel, "chapters") else 0,
                "word_count": novel.total_word_count if hasattr(novel, "total_word_count") else 0,
                "status": status,
                "is_usable": is_usable,
                "requires_manual_review": requires_manual_review,
                "warnings": warnings,
                "errors": errors,
                "next_actions": next_actions,
                "context_compaction": context_compaction,
                "task_dashboard": task_dashboard,
            },
            output_dir,
            "result.json",
        )

        # P1: 创建统一审阅摘要
        summary = build_review_markdown(
            content_type="Novel",
            topic=topic,
            title=novel.title if hasattr(novel, "title") else topic,
            status=status,
            is_usable=is_usable,
            requires_manual_review=requires_manual_review,
            warnings=warnings,
            errors=errors,
            next_actions=next_actions,
            extra_sections={
                "输出概览": [
                    f"目标字数: {words}",
                    f"章节数: {len(novel.chapters) if hasattr(novel, 'chapters') else 0}",
                    f"总字数: {novel.total_word_count if hasattr(novel, 'total_word_count') else 0}",
                    f"风格: {style}",
                ]
                if not compaction_lines
                else [
                    f"目标字数: {words}",
                    f"章节数: {len(novel.chapters) if hasattr(novel, 'chapters') else 0}",
                    f"总字数: {novel.total_word_count if hasattr(novel, 'total_word_count') else 0}",
                    f"风格: {style}",
                ],
                "上下文压缩": compaction_lines,
            },
        )
        if task_dashboard:
            summary = task_dashboard.get("summary", {})
            summary_md = [
                "## 任务大盘",
                "",
                f"- pending: {summary.get('pending', 0)}",
                f"- running: {summary.get('running', 0)}",
                f"- completed: {summary.get('completed', 0)}",
                f"- failed: {summary.get('failed', 0)}",
                f"- retrying: {summary.get('retrying', 0)}",
                "",
            ]
            summary = summary + "\n".join(summary_md)
        save_markdown_output(summary, output_dir, "summary.md")

        # P1: 显示状态图标 (与其他内容类型一致)
        status_icon = "✅" if is_usable and not requires_manual_review else "⚠️"
        click.echo(f"{status_icon} Novel结果状态: {status} | 可直接使用: {'是' if is_usable else '否'} | 需人工审核: {'是' if requires_manual_review else '否'}")
        if warnings:
            click.echo(f"   警告: {warnings[0]}")
        if next_actions:
            click.echo(f"   下一步: {next_actions[0]}")
    else:
        # 没有内容但也没有异常，可能是部分完成
        if exec_status in ("partial", "failed"):
            click.echo(f"⚠️  生成{exec_status}（已保存中间状态）: {output_dir}")
        else:
            click.echo(f"⚠️  未生成内容: {output_dir}")


def _build_novel_next_actions(
    novel: Any,
    warnings: list[str],
    errors: list[str],
    is_usable: bool,
    requires_manual_review: bool,
) -> list[str]:
    """Build user-facing next actions for novel output."""
    actions: list[str] = []
    if errors:
        actions.append("修复错误后再重新生成。")
    if not is_usable:
        actions.append("检查章节内容完整性，补充缺失章节。")
    if warnings:
        actions.append("检查 summary.md 中的警告项，必要时重新生成相关章节。")
    if requires_manual_review:
        actions.append("人工审阅章节内容，确认无误后再发布。")
    if not actions:
        actions.append("可直接进入发布或后续编辑流程。")
    return actions


def determine_resume_stop_at(resume_from: str) -> str | None:
    """Determine the stop_at value based on resume_from stage.

    Args:
        resume_from: Stage to resume from (evaluation/volume/summary/writing)

    Returns:
        stop_at value for kickoff, or None to run to completion
    """
    if resume_from == "evaluation":
        return "volume"
    if resume_from == "volume":
        return "volume"
    if resume_from == "summary":
        return "summary"
    if resume_from == "writing":
        return None  # No stop, runs to completion
    return None


def compute_default_pipeline_state_path(output: str, has_flags: bool) -> str | None:
    """Compute the default pipeline state path based on CLI flags.

    Args:
        output: Output directory
        has_flags: Whether any stateful flags are set

    Returns:
        Path to pipeline state or None
    """
    if not has_flags:
        return None
    return str(Path(output) / "pipeline_state.json")


def load_env_from_project_root() -> None:
    """Load .env from project root so API keys are available to litellm."""
    try:
        from dotenv import load_dotenv
        project_root = os.environ.get("CREWAI_PROJECT_ROOT", str(Path.cwd()))
        env_path = Path(project_root) / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass  # python-dotenv not installed


def save_pipeline_stage_result(
    result: Any,
    crew: Any,
    output: str,
    pipeline_state_path: str | None,
) -> None:
    """Save result when pipeline stops at a stage (not writing).

    Args:
        result: Crew kickoff result
        crew: NovelCrew instance
        output: Output directory
        pipeline_state_path: Optional explicit state path
    """
    ensure_output_dir(output)

    stage = result.metadata.get("pipeline_state", {}).get("stage", "unknown")
    click.echo(f"⏸️ 流水线已停止在阶段: {stage}")

    # 优先使用用户提供的 pipeline_state_path，否则使用默认路径
    state_file = Path(pipeline_state_path) if pipeline_state_path else Path(output) / "pipeline_state.json"
    crew.save_pipeline_state(str(state_file))
    click.echo(f"💾 流水线状态已保存: {state_file}")

    pipeline_summary = result.metadata.get("pipeline_state", {})
    save_json_output(pipeline_summary, Path(output), "pipeline_stage.json")
    click.echo(f"✅ 阶段结果已保存: {output}")


# ==================== LLM 工厂 ====================


def create_llm_from_env():
    """Create an LLM instance from environment variables.

    Checks MiniMax, DeepSeek, Gemini, Doubao, Kimi in priority order
    and returns the first configured one.
    """
    import os
    # Check MiniMax first (fast, good for China)
    minimax_key = os.environ.get("MINIMAX_API_KEY", "").strip()
    minimax_url = os.environ.get("MINIMAX_BASE_URL", "").strip()
    minimax_model = os.environ.get("MINIMAX_MODEL", "").strip()

    if minimax_key and minimax_url:
        from crewai.llm import LLM
        model = minimax_model or "MiniMax-M2.7-highspeed"
        return LLM(
            model=model,
            api_key=minimax_key,
            base_url=minimax_url,
        )

    # Check DeepSeek (widely compatible, reliable)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if deepseek_key:
        from crewai.llm import LLM
        return LLM(model="deepseek/deepseek-chat", api_key=deepseek_key)

    # Check Gemini (reliable, widely compatible)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        from crewai.llm import LLM
        return LLM(model="gemini/gemini-2.5-flash", api_key=gemini_key)

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

    # Last resort: let crewai auto-detect (will use OPENAI_API_KEY from env)
    return None


# ==================== Novel 核心执行逻辑 ====================


def _run_novel_interactive(crew: Any, output: str, stop_at: str | None):
    """Interactive stage-by-stage novel creation with human confirmation.

    Args:
        crew: NovelCrew instance
        output: Output directory
        stop_at: Optional stage to stop at (limits interactive sequence)
    """

    stages = ["outline", "evaluation", "volume", "summary"]
    stop_idx = stages.index(stop_at) if stop_at else len(stages)

    output_dir = ensure_output_dir(output)
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
    click.echo("📖 开始撰写章节...")
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
            save_json_output(
                {
                    "topic": crew.config.get("topic", ""),
                    "chapters_count": len(novel.chapters),
                    "word_count": novel.total_word_count,
                },
                output_dir,
                "result.json",
            )
    click.echo(f"✅ 小说已生成: {output_dir}")


def run_novel_creation(
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
    seed_variant: str | None = None,
) -> None:
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
        seed_variant: 可选的 seed 变体，用于生成同一主题的不同变体
    """
    from crewai.content.novel import NovelCrew

    # Validate inputs early with clear error messages (P1-17: strict contract testing)
    VALID_STYLES = {"urban", "xianxia", "doushi", "modern", "fantasy", "scifi", "romance", "wuxia"}
    if words <= 0:
        raise ValueError(
            f"目标字数必须大于0，当前值: {words}。"
            "请使用 --words 参数指定正整数，例如: crewai create novel '我的小说' --words 100000"
        )
    if style and style.lower() not in VALID_STYLES:
        raise ValueError(
            f"不支持的小说风格: '{style}'。"
            f"支持的风格: {', '.join(sorted(VALID_STYLES))}"
        )
    VALID_STOP_AT = {"outline", "evaluation", "volume", "summary"}
    if stop_at and stop_at not in VALID_STOP_AT:
        raise ValueError(
            f"无效的 --stop-at 值: '{stop_at}'。"
            f"支持的值: {', '.join(sorted(VALID_STOP_AT))}"
        )
    VALID_RESUME_FROM = {"evaluation", "volume", "summary", "writing"}
    if resume_from and resume_from not in VALID_RESUME_FROM:
        raise ValueError(
            f"无效的 --resume-from 值: '{resume_from}'。"
            f"支持的值: {', '.join(sorted(VALID_RESUME_FROM))}"
        )

    load_env_from_project_root()

    click.echo(f"🚀 开始生成小说: {topic}")
    click.echo(f"   目标字数: {words}")
    click.echo(f"   小说风格: {style}")
    if stop_at:
        click.echo(f"   停止阶段: {stop_at}")
    if resume_from:
        click.echo(f"   恢复阶段: {resume_from}")

    try:
        # Create LLM instance from environment or defaults
        llm = create_llm_from_env()

        # Use typed config instead of raw dict
        from crewai.content.novel.config import NovelConfig
        config = NovelConfig(
            topic=topic,
            style=style,
            target_words=words,
            num_chapters=chapters if chapters > 0 else 0,  # 0 = auto
            genre=style,
            llm=llm,
            output_dir=output,
            review_each_chapter=review_each_chapter,
            seed_variant=seed_variant,
        )
        crew = NovelCrew(config=config.to_dict())

        # Compute seed with variant for deterministic variant generation
        from crewai.content.novel.pipeline_state import PipelineState
        seed = PipelineState.generate_seed(topic, style, style, seed_variant)
        config.seed = seed  # Set computed seed on config
        if seed_variant:
            click.echo(f"   Seed变体: {seed_variant}")

        # Interactive mode: stage-by-stage with human confirmation
        if interactive:
            _run_novel_interactive(crew, output, stop_at)
            return

        # Handle resume mode
        if resume_from and pipeline_state_path:
            click.echo(f"📂 从状态文件恢复: {pipeline_state_path}")
            crew.load_pipeline_state(pipeline_state_path)

            # Use kickoff with state-caching to skip already-done phases
            resume_stop_at = determine_resume_stop_at(resume_from)
            state_path = pipeline_state_path if Path(pipeline_state_path).exists() else None
            result = crew.kickoff(stop_at=resume_stop_at, pipeline_state_path=state_path, review_each_chapter=review_each_chapter, seed=seed)

            # If stopped at a stage (not completed writing), return
            if result.metadata.get("stopped"):
                click.echo(f"⏸️ 已停止在阶段: {result.metadata.get('pipeline_state', {}).get('stage', 'unknown')}")
                crew.save_pipeline_state(pipeline_state_path)
                return

            # 检查是否需要审批（review_each_chapter模式下的章节待审批）
            if result.metadata.get("approval_required"):
                pending_chapter = result.metadata.get("pending_chapter", "?")
                pending_title = result.metadata.get("content_summary", {}).get("chapter_title", "未知")
                state_path = result.metadata.get("pipeline_state_path", ".pending_chapter.json")
                display_approval_message(topic, pending_chapter, pending_title, state_path)
                return

            # Writing completed — fall through to result saving below
        else:
            # Normal (non-resume) mode
            state_path = pipeline_state_path if pipeline_state_path and Path(pipeline_state_path).exists() else None
            result = crew.kickoff(stop_at=stop_at, pipeline_state_path=state_path, review_each_chapter=review_each_chapter, seed=seed)

            # 检查是否需要审批（review_each_chapter模式）
            if result.metadata.get("approval_required"):
                pending_chapter = result.metadata.get("pending_chapter", "?")
                pending_title = result.metadata.get("content_summary", {}).get("chapter_title", "未知")
                state_path = result.metadata.get("pipeline_state_path", ".pending_chapter.json")
                display_approval_message(topic, pending_chapter, pending_title, state_path)
                return

            # 检查是否停止在某个阶段（没有完整内容）
            if result.metadata.get("stopped"):
                save_pipeline_stage_result(result, crew, output, pipeline_state_path)
                return

        # 保存完整小说结果（resume或正常完成都会走到这里）
        exec_status = result.metadata.get("status", "success")
        save_novel_result(result, crew, topic, words, style, output, exec_status)

    except (ValueError, RuntimeError, TimeoutError, IOError) as e:
        click.echo(f"❌ 生成失败: {e!s}", err=True)
        raise
