#!/usr/bin/env python3
"""小说生成主入口 - 使用 KIMI 自动生成小说（自动反馈循环）.

Usage:
    python run_novel_generation.py --new "小说标题" --genre "玄幻" --outline "大纲"
    python run_novel_generation.py --generate 5  # 生成5章（自动触发反馈）
    python run_novel_generation.py --generate 5 --no-auto-feedback  # 禁用自动反馈
    python run_novel_generation.py --status       # 查看状态
    python run_novel_generation.py --list         # 列出章节
    python run_novel_generation.py --export       # 导出为文本

    # 反馈循环命令 (发现问题→分析→修复→验证)
    python run_novel_generation.py --load 7414da9519da
    python run_novel_generation.py --feedback-discover  # 发现问题
    python run_novel_generation.py --feedback-analyze    # 分析问题
    python run_novel_generation.py --feedback-fix       # 修复错误
    python run_novel_generation.py --feedback-verify    # 验证结果
    python run_novel_generation.py --feedback-cycle     # 反馈循环
    python run_novel_generation.py --feedback-cycle --feedback-mode deep  # 深度反馈(完成20章后)
    python run_novel_generation.py --feedback-cycle --feedback-mode volume_complete  # 卷完成反馈
    python run_novel_generation.py --feedback-report   # 导出报告
"""

import argparse
from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any
import uuid


# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env")

from agents.chapter_manager import ChapterPlotSummary, get_chapter_manager  # noqa: E402
from agents.config_manager import get_config_manager  # noqa: E402
from agents.derivative_generator import get_derivative_generator  # noqa: E402
from agents.feedback_loop import FeedbackMode, FeedbackStrategy, get_feedback_loop  # noqa: E402
from agents.novel_generator import get_novel_generator  # noqa: E402
from agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig  # noqa: E402
from services.longform_run import (  # noqa: E402
    CHECKPOINT_OUTLINE,
    CHECKPOINT_VOLUME,
    STAGE_FINALIZE_EXPORT,
    STAGE_OUTLINE_GENERATE,
    STAGE_OUTLINE_REVIEW,
    STAGE_VOLUME_PLAN,
    STAGE_VOLUME_REVIEW,
    STAGE_VOLUME_WRITE,
    approval_payload_from_input,
    apply_outline_revision,
    clear_pause,
    initial_longform_state,
    load_json_file,
    load_longform_state,
    next_volume,
    record_pause,
    review_payload_for_outline,
    review_payload_for_volume,
    save_longform_state,
    should_pause_for_stage,
)
from services.run_storage import create_run, ensure_run_dir, read_status, update_status  # noqa: E402
from writing_options import (  # noqa: E402
    DEFAULT_WRITING_OPTIONS,
    WRITING_OPTION_GROUPS,
    normalize_writing_options,
)


BASE_STYLE_CHOICES = ["literary", "concise", "dramatic"]
STYLE_PRESET_CHOICES = [
    "fanren_flow",
    "face_slapping",
    "cthulhu_mystery",
    "cinematic_youth",
    "epic_rebel",
    "new_wuxia",
    "sword_philosophy",
]


def setup_logging(level: str = "INFO"):
    """设置日志."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class GenerationError(Exception):
    """章节生成失败的异常."""


# 反馈循环自动触发阈值
FEEDBACK_LIGHT_INTERVAL = 5   # 每5章
FEEDBACK_DEEP_INTERVAL = 20  # 每20章
FEEDBACK_VOLUME_SIZE = 20     # 一卷20章

STAGE_INIT = "init"
STAGE_CONTEXT_BUILD = "context.build"
STAGE_CHAPTER_GENERATE = "chapter.generate"
STAGE_CHAPTER_SAVE = "chapter.save"
STAGE_DERIVATIVES_SYNC = "derivatives.sync"
STAGE_FEEDBACK_AUTO = "feedback.auto"
STAGE_FINALIZE = "finalize"


def _run_auto_feedback(project_id: str, generated_chapters: list, total_current: int, llm_client=None) -> None:
    """根据生成结果自动运行反馈循环

    策略：
    - LIGHT: 每5章生成后触发
    - DEEP: 每20章生成后触发
    - VOLUME_COMPLETE: 完成一卷（20章）后触发

    Args:
        project_id: 项目ID
        generated_chapters: 本次生成的章节列表
        total_current: 当前项目总章节数
        llm_client: KIMI LLM 客户端
    """
    if not generated_chapters:
        return

    start_ch = generated_chapters[0].number
    end_ch = generated_chapters[-1].number
    count = len(generated_chapters)

    print("\n🔄 检查反馈循环触发条件...")
    print(f"   本次生成: 第{start_ch}-{end_ch}章 (共{count}章)")
    print(f"   当前项目总章节: {total_current}")

    feedback = get_feedback_loop(project_id, llm_client=llm_client)

    # 1. 检查 LIGHT 触发 (每5章)
    should_light = (total_current % FEEDBACK_LIGHT_INTERVAL == 0) or (end_ch % FEEDBACK_LIGHT_INTERVAL == 0)
    if should_light:
        print(f"\n📊 [AUTO] 触发 LIGHT 反馈 (每{FEEDBACK_LIGHT_INTERVAL}章)")
        strategy = FeedbackStrategy(
            mode=FeedbackMode.LIGHT,
            batch_size=FEEDBACK_LIGHT_INTERVAL,
            use_llm=False,
            auto_fix=True,
        )
        result = feedback.run_with_strategy(strategy)
        status = result.get('status', 'unknown')
        print(f"   结果: {status}")

    # 2. 检查 DEEP 触发 (每20章)
    should_deep = (total_current % FEEDBACK_DEEP_INTERVAL == 0) or (end_ch % FEEDBACK_DEEP_INTERVAL == 0)
    if should_deep:
        print(f"\n📊 [AUTO] 触发 DEEP 反馈 (每{FEEDBACK_DEEP_INTERVAL}章)")
        strategy = FeedbackStrategy(
            mode=FeedbackMode.DEEP,
            batch_size=FEEDBACK_DEEP_INTERVAL,
            use_llm=True,
            auto_fix=True,
        )
        result = feedback.run_with_strategy(strategy)
        status = result.get('status', 'unknown')
        print(f"   结果: {status}")

    # 3. 检查 VOLUME_COMPLETE 触发 (每20章=一卷)
    should_volume = (total_current % FEEDBACK_VOLUME_SIZE == 0) or (end_ch % FEEDBACK_VOLUME_SIZE == 0)
    if should_volume:
        volume_num = total_current // FEEDBACK_VOLUME_SIZE
        print(f"\n📊 [AUTO] 触发 VOLUME_COMPLETE 反馈 (第{volume_num}卷完成)")
        strategy = FeedbackStrategy(
            mode=FeedbackMode.VOLUME_COMPLETE,
            batch_size=FEEDBACK_VOLUME_SIZE,
            use_llm=True,
            auto_fix=True,
        )
        result = feedback.run_with_strategy(strategy)
        status = result.get('status', 'unknown')
        print(f"   结果: {status}")


def _project_dir(config_mgr) -> Path:
    """Return the canonical project output directory."""
    return Path(config_mgr.generation.output_dir).resolve()


def _build_results_file(project_dir: Path) -> Path:
    """Return the canonical generation results path."""
    return project_dir / "generation_results.json"


def _telemetry_run_dir(args, project_dir: Path) -> Path | None:
    """Return the enabled telemetry run directory, if requested."""
    if not getattr(args, "run_id", None) and not getattr(args, "run_dir", None):
        return None

    if getattr(args, "run_dir", None):
        run_dir = Path(args.run_dir).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    return ensure_run_dir(project_dir, args.run_id)


def _estimate_eta_seconds(
    run_started_at: datetime,
    chapters_total: int,
    chapters_completed: int,
    current_stage: str,
) -> int | None:
    """Estimate remaining time for the current generation run."""
    if chapters_total <= 0:
        return None
    remaining_chapters = max(chapters_total - chapters_completed, 0)
    if remaining_chapters == 0:
        return 0

    elapsed = max((datetime.now() - run_started_at).total_seconds(), 1.0)
    if chapters_completed > 0:
        per_chapter = elapsed / chapters_completed
    else:
        per_chapter = 180.0

    stage_overhead = {
        STAGE_INIT: 30,
        STAGE_CONTEXT_BUILD: 20,
        STAGE_CHAPTER_GENERATE: 45,
        STAGE_CHAPTER_SAVE: 10,
        STAGE_DERIVATIVES_SYNC: 60,
        STAGE_FEEDBACK_AUTO: 90,
        STAGE_FINALIZE: 15,
    }.get(current_stage, 15)
    return int((per_chapter * remaining_chapters) + stage_overhead)


def _update_run_progress(
    run_dir: Path | None,
    *,
    project_id: str,
    command: list[str],
    status: str,
    current_stage: str,
    current_step: str,
    chapters_total: int,
    chapters_completed: int,
    run_started_at: datetime,
    failed_stage: str | None = None,
    error_message: str | None = None,
    finished_at: str | None = None,
    return_code: int | None = None,
) -> None:
    """Persist the current telemetry snapshot when run storage is enabled."""
    if run_dir is None:
        return

    update_status(
        run_dir,
        project_id=project_id,
        command=command,
        status=status,
        started_at=run_started_at.isoformat(),
        finished_at=finished_at,
        current_stage=current_stage,
        current_step=current_step,
        chapters_total=chapters_total,
        chapters_completed=chapters_completed,
        eta_seconds=_estimate_eta_seconds(
            run_started_at=run_started_at,
            chapters_total=chapters_total,
            chapters_completed=chapters_completed,
            current_stage=current_stage,
        ),
        error_message=error_message,
        failed_stage=failed_stage,
        pid=os.getpid(),
        return_code=return_code,
    )


def cmd_new_project(args):
    """创建新项目."""
    config_mgr = get_config_manager()

    project = config_mgr.create_project(
        title=args.title,
        author=args.author or "AI Author",
        genre=args.genre,
        outline=args.outline,
        world_setting=args.world or "",
        character_intro=args.characters or "",
        total_chapters=args.chapters or 100,
    )

    writing_options = _collect_writing_options_from_args(args)
    config_mgr.update_project_metadata({"writing_options": writing_options})

    print("\n✅ 项目创建成功!")
    print(f"   项目ID: {project.id}")
    print(f"   标题: {project.title}")
    print(f"   题材: {project.genre}")
    print(f"   计划章节: {project.total_chapters}")
    print(f"\n目录: {_project_dir(config_mgr)}")



def _create_orchestrator(config_mgr, project_id: str) -> NovelOrchestrator:
    """创建小说编排器（仅支持FILM_DRAMA模式）.

    Args:
        config_mgr: 配置管理器
        project_id: 项目ID

    Returns:
        NovelOrchestrator 实例
    """
    logger = logging.getLogger(__name__)

    # 获取 KIMI LLM 客户端
    try:
        from llm.kimi_client import get_kimi_client
        llm_client = get_kimi_client()
        logger.info("KIMI client initialized for NovelOrchestrator")
    except Exception as e:
        logger.error(f"Failed to get KIMI client: {e}")
        raise RuntimeError("KIMI client not available for orchestrator")

    # 创建编排器配置
    config = OrchestratorConfig(
        max_subagent_concurrent=5,
        max_concurrent_scenes=3,
        enable_verification=True,
        max_retry=2,
        max_verification_retries=3,
    )

    # 创建编排器
    orchestrator = NovelOrchestrator(
        llm_client=llm_client,
        config=config,
    )

    logger.info("NovelOrchestrator created for FILM_DRAMA mode")
    return orchestrator


def cmd_generate(args):
    """生成章节."""
    config_mgr = get_config_manager()
    logger = logging.getLogger(__name__)

    # 获取 KIMI client 供生成器使用
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception as e:
        logger.warning(f"Failed to get KIMI client: {e}")
        kimi_client = None

    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 创建项目")
        return 1

    project = config_mgr.current_project
    project_id = project.id
    project_dir = _project_dir(config_mgr)
    project_dir.mkdir(parents=True, exist_ok=True)
    command = sys.argv[1:]
    run_started_at = datetime.now()
    run_dir = _telemetry_run_dir(args, project_dir)

    # 使用标题目录而非ID目录
    base_dir_override = str(project_dir)
    chapter_mgr = get_chapter_manager(project_id, base_dir_override=base_dir_override)

    # 创建 orchestrator (仅支持 FILM_DRAMA 模式)
    novel_orchestrator = _create_orchestrator(config_mgr, project_id)

    # 创建小说生成器（传入 orchestrator 以启用 FILM_DRAMA 模式）
    generator = get_novel_generator(
        config_manager=config_mgr,
        novel_orchestrator=novel_orchestrator,
        llm_client=kimi_client,
    )

    # 处理 --continue-from 断点续传
    continue_from = getattr(args, 'continue_from', None)
    start = args.start or config_mgr.current_project.current_chapter + 1
    count = args.count
    dry_run = getattr(args, 'dry_run', False)
    mode = "incremental" if continue_from is not None else "full"
    active_writing_options = _resolve_active_writing_options(config_mgr, args)

    # 读取已有的 generation_results.json 获取已成功的章节（用于断点续传）
    results_file = _build_results_file(project_dir)
    existing_results = None
    chapters_to_skip = set()
    checkpoints = []
    if results_file.exists():
        with open(results_file) as f:
            existing_results = json.load(f)
        chapters_to_skip = {
            r['chapter_number']
            for r in existing_results.get('chapter_results', [])
            if r.get('status') == 'success'
        }
        checkpoints = existing_results.get('checkpoints', [])

    if continue_from is not None:
        start = continue_from
        print(f"\n🔄 断点续传模式: 从第 {continue_from} 章继续")
        print(f"   已成功章节: {sorted(chapters_to_skip)}")
        print(f"   已有检查点: {checkpoints}")
    else:
        print(f"\n🚀 开始生成 {count} 章...")
        print(f"   起始章节: {start}")
        print(f"   项目: {config_mgr.current_project.title}")
    _print_writing_options(active_writing_options)

    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="running",
        current_stage=STAGE_INIT,
        current_step="初始化生成任务",
        chapters_total=count,
        chapters_completed=0,
        run_started_at=run_started_at,
        return_code=None,
    )

    if dry_run:
        print("\n🔍 Dry-run 模式: 仅预览，不实际生成")
        print("   将生成章节: ", end="")
        preview = []
        for i in range(count):
            ch_num = start + i
            if ch_num in chapters_to_skip:
                preview.append(f"第{ch_num}章(已存在)")
            else:
                preview.append(f"第{ch_num}章")
        print(", ".join(preview))
        print(f"\n✅ Dry-run 完成，共 {count} 章需处理")
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="succeeded",
            current_stage=STAGE_FINALIZE,
            current_step="Dry-run 完成",
            chapters_total=count,
            chapters_completed=0,
            run_started_at=run_started_at,
            finished_at=datetime.now().isoformat(),
            return_code=0,
        )
        return 0

    print("-" * 50)

    # 初始化追踪结果
    generation_run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    generation_results = {
        "project_id": project_id,
        "generation_run_id": generation_run_id,
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "mode": mode,
        "total_attempted": count,
        "successful": 0,
        "failed": 0,
        "total_words_generated": 0,
        "total_time_seconds": 0.0,
        "chapter_results": [],
        "failed_chapters": [],
        "checkpoints": list(checkpoints),
    }

    # 获取 KIMI client 用于后续组件
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception as e:
        logger.warning(f"Failed to get KIMI client: {e}")
        kimi_client = None

    generated = []
    failed_chapters = []
    previous_summary = ""
    last_failed_stage: str | None = None
    for i in range(count):
        chapter_num = start + i

        # 跳过已成功的章节（断点续传时）
        if chapter_num in chapters_to_skip:
            print(f"\n📝 第 {chapter_num} 章已存在，跳过")
            continue

        start_time = datetime.now()
        current_stage = STAGE_CONTEXT_BUILD

        try:
            print(f"\n📝 生成第 {chapter_num} 章...")
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=STAGE_CONTEXT_BUILD,
                current_step=f"第 {chapter_num} 章上下文构建",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
            )

            # 构建上下文
            context = chapter_mgr.build_context(chapter_num)

            # 生成章节
            current_stage = STAGE_CHAPTER_GENERATE
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=STAGE_CHAPTER_GENERATE,
                current_step=f"第 {chapter_num} 章正文生成",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
            )
            chapter = generator.generate_chapter(
                chapter_number=chapter_num,
                context=context,
                previous_summary=previous_summary,
                writing_options=active_writing_options,
            )

            # 计算内容校验和
            content_checksum = hashlib.sha256(
                chapter.content.encode('utf-8')
            ).hexdigest()[:16]

            # 获取实际摘要（优先使用生成后的情节摘要，而非生成前的大纲）
            actual_summary = ""
            if hasattr(chapter, 'plot_summary') and chapter.plot_summary:
                actual_summary = chapter.plot_summary.get('l2_brief_summary', '')
            if not actual_summary:
                actual_summary = chapter.metadata.get("outline_summary", "")

            # 保存
            current_stage = STAGE_CHAPTER_SAVE
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=STAGE_CHAPTER_SAVE,
                current_step=f"第 {chapter_num} 章保存输出",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
            )
            chapter_mgr.save_chapter(
                number=chapter.number,
                title=chapter.title,
                content=chapter.content,
                word_count=chapter.word_count,
                summary=actual_summary,
                key_events=chapter.metadata.get("key_events", []),
                character_appearances=chapter.metadata.get("character_appearances", []),
                generation_time=chapter.generation_time,
            )

            # 保存情节概述（三级结构）
            if hasattr(chapter, 'plot_summary') and chapter.plot_summary:
                plot_summary_data = chapter.plot_summary
                plot_summary = ChapterPlotSummary(
                    chapter_number=chapter.number,
                    one_line_summary=plot_summary_data.get('l1_one_line_summary', ''),
                    brief_summary=plot_summary_data.get('l2_brief_summary', ''),
                    key_plot_points=plot_summary_data.get('l3_key_plot_points', []),
                    character_states={},
                    plot_threads=[],
                    foreshadowing=[],
                )
                chapter_mgr.save_plot_summary(plot_summary)
                logger.info(f"  📋 Plot summary saved for chapter {chapter.number}")

            # 保存一致性检查报告和重写历史
            if hasattr(chapter, 'consistency_report') and chapter.consistency_report:
                chapter_mgr.save_consistency_report(
                    chapter_number=chapter.number,
                    report=chapter.consistency_report,
                    rewrite_history=chapter.metadata.get("rewrite_history", [])
                )

            # 保存 FILM_DRAMA 内容（场景、角色、情节结构等）
            if hasattr(chapter, 'orchestrator_result') and chapter.orchestrator_result:
                try:
                    film_drama_file = chapter_mgr.save_film_drama_content(
                        chapter_number=chapter.number,
                        film_drama_data=chapter.orchestrator_result,
                    )
                    logger.info(f"  🎬 Film drama content saved: {film_drama_file}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to save film drama content: {e}")

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ✅ {chapter.title} ({chapter.word_count} 字, {elapsed:.1f}秒)")

            generated.append(chapter)
            # 使用生成后的情节摘要作为下一章的上下文，而非生成前的大纲
            if hasattr(chapter, 'plot_summary') and chapter.plot_summary:
                previous_summary = chapter.plot_summary.get('l2_brief_summary', '') or chapter.metadata.get("outline_summary", "")
            else:
                previous_summary = chapter.metadata.get("outline_summary", "")

            # 记录成功
            generation_results['successful'] += 1
            generation_results['total_words_generated'] += chapter.word_count
            generation_results['total_time_seconds'] += elapsed
            generation_results['chapter_results'].append({
                "chapter_number": chapter_num,
                "status": "success",
                "title": chapter.title,
                "word_count": chapter.word_count,
                "time_seconds": elapsed,
                "timestamp": datetime.now().isoformat(),
                "checksum": content_checksum,
            })

            # 保存 checkpoint（每成功一章就保存）
            generation_results['checkpoints'].append(chapter_num)
            _save_checkpoint(results_file, generation_results)
            print(f"   💾 Checkpoint 已保存 (第 {chapter_num} 章)")
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=STAGE_CHAPTER_SAVE,
                current_step=f"第 {chapter_num} 章已完成",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
            )

        except GenerationError as e:
            logger.error(f"Chapter {chapter_num} generation failed: {e}")
            print(f"   ❌ 生成失败: {e}")
            failed_chapters.append(chapter_num)
            generation_results['failed'] += 1
            generation_results['failed_chapters'].append({
                'chapter_number': chapter_num,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
            })
            generation_results['chapter_results'].append({
                "chapter_number": chapter_num,
                "status": "failed",
                "error": str(e),
                "time_seconds": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat(),
            })
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=current_stage,
                current_step=f"第 {chapter_num} 章失败，继续后续章节",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
                failed_stage=current_stage,
                error_message=str(e),
            )
            last_failed_stage = current_stage
            continue  # 继续处理其他章节

        except Exception as e:
            # 其他异常也包装为 GenerationError 继续处理
            logger.error(f"Chapter {chapter_num} generation failed (unexpected): {e}")
            print(f"   ❌ 生成失败: {e}")
            failed_chapters.append(chapter_num)
            generation_results['failed'] += 1
            generation_results['failed_chapters'].append({
                'chapter_number': chapter_num,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
            })
            generation_results['chapter_results'].append({
                "chapter_number": chapter_num,
                "status": "failed",
                "error": str(e),
                "time_seconds": (datetime.now() - start_time).total_seconds(),
                "timestamp": datetime.now().isoformat(),
            })
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=current_stage,
                current_step=f"第 {chapter_num} 章失败，继续后续章节",
                chapters_total=count,
                chapters_completed=len(generated),
                run_started_at=run_started_at,
                failed_stage=current_stage,
                error_message=str(e),
            )
            last_failed_stage = current_stage
            continue  # 继续处理其他章节

    # 保存最终结果到 JSON 文件
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="running",
        current_stage=STAGE_FINALIZE,
        current_step="写入最终结果",
        chapters_total=count,
        chapters_completed=len(generated),
        run_started_at=run_started_at,
    )
    generation_results['completed_at'] = datetime.now().isoformat()
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(generation_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    _print_statistics(generation_results, failed_chapters, results_file, project.title)

    # 同步生成衍生内容（播客、视频Prompt、角色/场景描述）
    if generated:
        print("\n🔄 开始同步生成衍生内容...")
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="running",
            current_stage=STAGE_DERIVATIVES_SYNC,
            current_step="同步衍生内容",
            chapters_total=count,
            chapters_completed=len(generated),
            run_started_at=run_started_at,
        )
        try:
            scripts_dir = config_mgr.generation.scripts_dir
            derivative_gen = get_derivative_generator(project_id, kimi_client=kimi_client, base_dir_override=base_dir_override, scripts_dir_override=scripts_dir)
            # 使用已生成章节的范围
            chapter_range = f"{generated[0].number}-{generated[-1].number}"
            sync_results = derivative_gen.sync_derivatives(chapter_range)
            print("   ✅ 衍生内容同步完成:")
            print(f"      - 视频Prompt: {len(sync_results.get('video_prompts', []))} 个")
            print(f"      - 角色描述: {len(sync_results.get('character_descriptions', []))} 个")
            print(f"      - 场景描述: {len(sync_results.get('scene_descriptions', []))} 个")
            print(f"      - 播客脚本: {len(sync_results.get('podcasts', []))} 个")
            if sync_results.get('errors'):
                print(f"      - 错误: {len(sync_results['errors'])} 个")
        except Exception as e:
            logger.warning(f"Failed to sync derivatives: {e}")
            print(f"   ⚠️ 衍生内容同步失败: {e}")

    # 自动反馈循环（根据策略触发）
    no_auto_feedback = getattr(args, 'no_auto_feedback', False)
    if generated and not no_auto_feedback:
        # 获取当前项目总章节数
        current_total = config_mgr.current_project.current_chapter
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="running",
            current_stage=STAGE_FEEDBACK_AUTO,
            current_step="运行自动反馈",
            chapters_total=count,
            chapters_completed=len(generated),
            run_started_at=run_started_at,
        )
        _run_auto_feedback(project_id, generated, current_total, llm_client=kimi_client)

    if failed_chapters:
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="failed",
            current_stage=STAGE_FINALIZE,
            current_step=f"任务结束，但有 {len(failed_chapters)} 章失败",
            chapters_total=count,
            chapters_completed=len(generated),
            run_started_at=run_started_at,
            failed_stage=last_failed_stage,
            error_message=f"共有 {len(failed_chapters)} 章生成失败",
            finished_at=datetime.now().isoformat(),
            return_code=1,
        )
        return 1
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="succeeded",
        current_stage=STAGE_FINALIZE,
        current_step="生成完成",
        chapters_total=count,
        chapters_completed=len(generated),
        run_started_at=run_started_at,
        finished_at=datetime.now().isoformat(),
        return_code=0,
    )
    return 0


def _save_checkpoint(results_file: Path, results: dict) -> None:
    """保存 checkpoint 到文件."""
    checkpoint_file = results_file.parent / "generation_checkpoint.json"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _print_statistics(results: dict, failed_chapters: list, results_file: Path, project_title: str) -> None:
    """打印生成统计信息."""
    total_words = results.get('total_words_generated', 0)
    total_time = results.get('total_time_seconds', 0.0)
    speed = total_words / total_time if total_time > 0 else 0
    chapters_dir = results_file.parent / "chapters"
    checkpoint_file = results_file.parent / "generation_checkpoint.json"

    print(f"""
📊 生成统计:
   成功: {results.get('successful', 0)} 章
   失败: {results.get('failed', 0)} 章
   总字数: {total_words:,} 字
   总耗时: {total_time:.1f} 秒
   平均速度: {speed:.0f} 字/秒
   检查点: {len(results.get('checkpoints', []))} 个
""")

    if failed_chapters:
        print(f"⚠️  生成完成但有 {len(failed_chapters)} 章失败:")
        for ch in failed_chapters:
            print(f"   - 第 {ch} 章失败")
        print(f"\n可使用 --continue-from {min(failed_chapters)} 重新运行")
        print(f"   存储位置: {chapters_dir}")
        print(f"   结果文件: {results_file}")
        print(f"   检查点文件: {checkpoint_file}")
    else:
        print(f"✅ 生成完成! 共 {results.get('successful', 0)} 章")
        print(f"   项目: {project_title}")
        print(f"   存储位置: {chapters_dir}")


def cmd_status(args):
    """查看状态."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    summary = config_mgr.get_project_summary()

    print("\n📊 项目状态")
    print("-" * 50)
    print(f"   标题: {summary.get('title')}")
    print(f"   作者: {summary.get('author')}")
    print(f"   题材: {summary.get('genre')}")
    print(f"   进度: {summary.get('current_chapter')}/{summary.get('total_chapters')} 章")
    print(f"   完成度: {summary.get('progress_percent')}%")
    writing_options = normalize_writing_options(summary.get("metadata", {}).get("writing_options", {}))
    print(f"   写作参数: {', '.join(f'{k}={v}' for k, v in writing_options.items() if v)}")

    if summary.get("fanqie_enabled"):
        print(f"   番茄发布: ✅ 已配置 (书号: {summary.get('fanqie_book_id')})")
    else:
        print("   番茄发布: ❌ 未配置")

    return 0


def cmd_list_chapters(args):
    """列出章节."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 使用标题目录而非ID目录
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)
    chapters = chapter_mgr.get_chapter_list()

    if not chapters:
        print("📭 暂无章节")
        return 0

    stats = chapter_mgr.get_stats()
    print(f"\n📚 章节列表 (共 {stats['total_chapters']} 章, {stats['total_words']} 字)")
    print("-" * 70)

    for ch in chapters:
        print(f"   {ch.number:03d}. {ch.title:<20} | {ch.word_count:>5} 字 | {ch.created_at.strftime('%m-%d %H:%M')}")

    return 0


def cmd_export(args):
    """导出为文本."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 使用标题目录而非ID目录
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)

    # 导出到标题目录
    if output_dir:
        base_path = Path(output_dir).resolve()
    else:
        base_path = Path(f"./lib/knowledge_base/novels/{config_mgr.current_project.id}")
    output_path = args.output or str(base_path / f"{config_mgr.current_project.title}.txt")

    count = chapter_mgr.export_to_text(
        output_path=output_path,
        start=args.start or 1,
        end=args.end,
    )

    print(f"\n✅ 导出完成: {count} 章")
    print(f"   文件: {output_path}")

    return 0


def cmd_load_project(args):
    """加载项目."""
    config_mgr = get_config_manager()

    project = config_mgr.load_project(args.project_id)

    if project:
        print(f"\n✅ 项目加载成功: {project.title}")
        return 0
    print(f"❌ 项目加载失败: {args.project_id}")
    return 1


def cmd_publish(args):
    """发布章节到番茄小说网."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 或 --load")
        return 1

    # 获取配置的书号
    fanqie_config = config_mgr.fanqie
    if not fanqie_config.book_id:
        print("❌ 未配置番茄书号. 请在 .env 中设置 FANQIE_BOOK_ID")
        return 1

    # 创建番茄发布器
    publisher = FanqiePublisher(
        book_id=fanqie_config.book_id,
        volume_id=fanqie_config.volume_id,
        upload_delay=fanqie_config.upload_delay_seconds,
    )

    # 检查认证状态
    if not publisher._authenticated:
        print("❌ Cookie 未加载或已过期")
        print("   请检查 cookies/fanqie_cookies.json 文件")
        return 1

    print("\n📤 开始发布到番茄小说网...")
    print(f"   书号: {fanqie_config.book_id}")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    # 获取章节列表 - 使用标题目录
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)
    chapters = chapter_mgr.get_chapter_list()

    if not chapters:
        print("📭 暂无章节可发布")
        return 0

    # 确定要发布的章节范围
    if args.all:
        # 发布所有章节
        start_num = 1
        end_num = len(chapters)
        chapter_range = range(1, end_num + 1)
        print(f"   模式: 发布所有章节 (1-{end_num})")
    else:
        # 发布指定范围
        parts = args.range.split("-")
        if len(parts) == 2:
            start_num = int(parts[0])
            end_num = int(parts[1])
        else:
            start_num = int(parts[0])
            end_num = start_num

        chapter_range = range(start_num, end_num + 1)
        print(f"   模式: 发布章节 {start_num}-{end_num}")

    print()

    # 发布章节
    success_count = 0
    fail_count = 0

    for num in chapter_range:
        # 查找对应章节
        chapter_data = None
        for ch in chapters:
            if ch.number == num:
                # 加载章节内容
                chapter_content = chapter_mgr.get_chapter_content(num)
                if chapter_content:
                    chapter_data = {
                        "number": num,
                        "title": ch.title,
                        "content": chapter_content,
                    }
                break

        if not chapter_data:
            print(f"   ⚠️ 章节 {num} 不存在或内容为空")
            continue

        print(f"📤 发布第 {num} 章: {chapter_data['title']}...")

        result = publisher.upload_chapter(
            chapter_number=chapter_data["number"],
            title=chapter_data["title"],
            content=chapter_data["content"],
        )

        if result.success:
            print(f"   ✅ 成功 (ID: {result.chapter_id})")
            success_count += 1
        else:
            print(f"   ❌ 失败: {result.message}")
            fail_count += 1

        # 间隔延迟
        if num < end_num:
            import time
            time.sleep(fanqie_config.upload_delay_seconds)

    print()
    print("=" * 50)
    print(f"✅ 发布完成! 成功: {success_count}, 失败: {fail_count}")

    return 0 if fail_count == 0 else 1


def cmd_sync_derivatives(args):
    """同步衍生内容."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 或 --load")
        return 1

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception:
        kimi_client = None

    print("\n🔄 开始同步衍生内容...")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        results = derivative_gen.sync_derivatives(args.range)

        print("\n📊 同步结果:")
        print(f"   固定章节: {len(results['fixed_chapters'])} 章")
        print(f"   视频Prompt: {len(results['video_prompts'])} 个")
        print(f"   角色描述: {len(results['character_descriptions'])} 个")
        print(f"   场景描述: {len(results['scene_descriptions'])} 个")
        print(f"   播客脚本: {len(results['podcasts'])} 个")

        if results['errors']:
            print(f"\n   错误: {len(results['errors'])} 个")
            for err in results['errors'][:5]:
                print(f"      - {err}")

        print("\n✅ 同步完成!")
        return 0

    except Exception as e:
        print(f"❌ 同步失败: {e}")
        return 1


def cmd_list_derivatives(args):
    """列出衍生内容."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception:
        kimi_client = None

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)
    info = derivative_gen.list_derivatives()

    print("\n📚 衍生内容列表")
    print("-" * 50)
    print(f"   固定章节: {len(info['fixed_chapters'])} 章")
    print(f"   视频Prompt: {info['video_prompt_count']} 个")
    print(f"   角色描述: {info['character_count']} 个")
    print(f"   场景描述: {info['scene_count']} 个")
    print(f"   播客脚本: {info['podcast_count']} 个")
    print(f"   最后同步: {info['last_sync'] or '从未同步'}")

    return 0


def cmd_generate_podcast(args):
    """生成播客脚本."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception:
        kimi_client = None

    print("\n🎙️ 生成播客脚本...")
    print(f"   章节范围: {args.range}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        script = derivative_gen.generate_podcast_script(args.range)
        print("\n✅ 播客脚本生成成功!")
        print(f"   标题: {script.title}")
        print(f"   时长: {script.duration_minutes} 分钟")
        print(f"   主持人: {', '.join(script.speakers)}")
        return 0
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return 1


def cmd_generate_video_prompt(args):
    """生成视频提示词."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception:
        kimi_client = None

    print("\n🎬 生成视频提示词...")
    print(f"   章节: 第{args.chapter}章")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        prompt = derivative_gen.generate_video_prompt(args.chapter)
        print("\n✅ 视频提示词生成成功!")
        print(f"   场景: {prompt.scene_name}")
        print(f"   风格: {', '.join(prompt.style_tags)}")
        print(f"   人物: {', '.join(prompt.characters)}")
        print(f"   氛围: {prompt.mood}")
        print(f"\n   Prompt:\n   {prompt.prompt_text[:200]}...")
        return 0
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return 1


def cmd_verify(args):
    """验证项目完整性."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    print("\n🔍 验证项目完整性...")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    # 使用标题目录而非ID目录
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)

    # 执行完整性检查
    declared_latest = config_mgr.current_project.current_chapter
    result = chapter_mgr.verify_project_integrity(declared_latest)

    # 打印结果
    print("\n📊 完整性检查结果:")
    print(f"   状态: {'✅ 通过' if result['valid'] else '❌ 存在问题'}")

    stats = result.get('stats', {})
    print("\n📈 统计信息:")
    print(f"   章节总数: {stats.get('total_chapters', 0)}")
    print(f"   实际最新: 第{stats.get('actual_latest', 0)}章")
    print(f"   声明最新: 第{stats.get('declared_latest', 0)}章")
    print(f"   磁盘文件: {stats.get('files_on_disk', 0)}")
    print(f"   索引条目: {stats.get('indexed_chapters', 0)}")

    # 打印问题
    if result.get('issues'):
        print(f"\n❌ 问题列表 ({len(result['issues'])} 个):")
        for issue in result['issues']:
            print(f"   - [{issue['type']}] {issue['message']}")

    # 打印警告
    if result.get('warnings'):
        print(f"\n⚠️  警告列表 ({len(result['warnings'])} 个):")
        for warning in result['warnings']:
            print(f"   - {warning}")

    # 执行章节连续性检查
    seq_result = chapter_mgr.validate_chapter_sequence()
    print("\n📚 章节序列检查:")
    print(f"   状态: {'✅ 连续' if seq_result['valid'] else '❌ 不连续'}")
    seq_stats = seq_result.get('stats', {})
    print(f"   范围内章节: {seq_stats.get('existing_count', 0)}/{seq_stats.get('total_in_range', 0)}")
    print(f"   缺失章节: {seq_stats.get('missing_count', 0)}")
    print(f"   跳跃次数: {seq_stats.get('gap_count', 0)}")

    if seq_result.get('gaps'):
        print("\n   跳跃详情:")
        for gap in seq_result['gaps']:
            print(f"     - 第{gap['from_chapter']}章 → 第{gap['to_chapter']}章 (缺失 {gap['gap_size']} 章)")

    # 返回状态
    if result['valid'] and seq_result['valid']:
        print("\n✅ 项目验证通过!")
        return 0
    print("\n⚠️ 项目验证发现问题，请检查上述信息")
    return 1


def cmd_generate_character(args):
    """生成角色描述."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception:
        kimi_client = None

    print("\n👤 生成角色描述...")
    print(f"   角色: {args.name}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        char = derivative_gen.generate_character_description(args.name)
        print("\n✅ 角色描述生成成功!")
        print(f"   姓名: {char.name}")
        print(f"   外貌: {char.appearance[:100]}...")
        print(f"   性格: {char.personality[:100]}...")
        print(f"   出场: 第{', '.join(str(n) for n in char.key_appearances)}章")
        return 0
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        return 1


def cmd_feedback_loop(args):
    """反馈循环命令.

    支持以下模式：
    1. --feedback-discover: 发现问题
    2. --feedback-analyze: 分析问题
    3. --feedback-fix: 修复错误
    4. --feedback-verify: 验证结果
    5. --feedback-cycle: 完整反馈循环
    6. --feedback-report: 导出报告
    """
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 或 --load")
        return 1

    project_id = config_mgr.current_project.id

    # 导入反馈循环模块
    from agents.feedback_loop import (
        FeedbackMode,
        FeedbackStrategy,
        get_feedback_loop,
    )

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        llm_client = get_kimi_client()
    except Exception:
        llm_client = None

    print("\n🔄 反馈循环")
    print(f"   项目: {config_mgr.current_project.title}")
    print(f"   项目ID: {project_id}")
    print("-" * 50)

    # 初始化反馈循环
    try:
        feedback = get_feedback_loop(project_id, llm_client=llm_client)
    except Exception as e:
        print(f"❌ 初始化反馈循环失败: {e}")
        return 1

    # 执行反馈循环的不同阶段
    if args.feedback_cycle:
        # 根据模式运行反馈循环
        mode_map = {
            "light": FeedbackMode.LIGHT,
            "deep": FeedbackMode.DEEP,
            "full": FeedbackMode.FULL,
            "volume_complete": FeedbackMode.VOLUME_COMPLETE,
        }
        mode = mode_map.get(args.feedback_mode, FeedbackMode.LIGHT)

        strategy = FeedbackStrategy(
            mode=mode,
            batch_size=5,
            use_llm=(mode in [FeedbackMode.DEEP, FeedbackMode.FULL]),
            auto_fix=True,
            max_iterations=args.feedback_max_iterations,
        )

        print(f"\n📊 运行反馈循环 (模式: {mode.value})...")
        print("   流程: 发现问题 → 分析问题 → 修复错误 → 验证结果")
        print("-" * 50)

        result = feedback.run_with_strategy(strategy)

        print("\n📊 反馈循环报告:")
        # 根据不同模式处理不同的结果结构
        if 'final_status' in result:
            # FULL模式 (run_full_cycle结构)
            print("   模式: full")
            print(f"   状态: {result['final_status']}")
            print(f"   迭代次数: {len(result.get('iterations', []))}")
            print(f"   开始时间: {result.get('start_time', 'N/A')}")
            print(f"   结束时间: {result.get('end_time', 'N/A')}")

            # 显示每次迭代的结果摘要
            for i, iteration in enumerate(result.get('iterations', [])):
                phase = iteration.get('phase', 'unknown')
                phase_result = iteration.get('result', {})
                if phase == 'discovery':
                    issues_count = phase_result.get('issues_found', 0)
                    needs_fix = phase_result.get('needs_fix', False)
                    print(f"\n   迭代 {i+1} - {phase.upper()}:")
                    print(f"      发现问题: {issues_count} 个")
                    print(f"      需要修复: {'是' if needs_fix else '否'}")
                elif phase == 'fix':
                    summary = phase_result.get('summary', {})
                    print(f"\n   迭代 {i+1} - {phase.upper()}:")
                    print(f"      总计: {summary.get('total', 0)}")
                    print(f"      成功: {summary.get('success', 0)}")
                    print(f"      失败: {summary.get('failed', 0)}")
                elif phase == 'verification':
                    print(f"\n   迭代 {i+1} - {phase.upper()}:")
                    print(f"      验证通过: {'是' if phase_result.get('verification_passed') else '否'}")
                    checks = phase_result.get('checks', {})
                    for check_name, check_result in checks.items():
                        print(f"      - {check_name}: {'✅' if check_result else '❌'}")
        elif 'mode' in result:
            # LIGHT/DEEP/MILESTONE 模式
            mode_str = result.get('mode', 'unknown')
            status_str = result.get('status', 'unknown')
            print(f"   模式: {mode_str}")
            print(f"   状态: {status_str}")

            if mode_str == 'light' and status_str == 'passed':
                print(f"   消息: {result.get('message', 'No critical issues found')}")
            else:
                # 显示子阶段结果
                for sub_key in ['discovery', 'analysis', 'fix']:
                    if sub_key in result:
                        sub_result = result[sub_key]
                        if sub_key == 'discovery':
                            print(f"\n   {sub_key.upper()}:")
                            print(f"      发现问题: {sub_result.get('issues_found', 0)} 个")
                            print(f"      需要修复: {'是' if sub_result.get('needs_fix') else '否'}")
                        elif sub_key == 'fix':
                            summary = sub_result.get('summary', {})
                            print(f"\n   {sub_key.upper()}:")
                            print(f"      总计: {summary.get('total', 0)}")
                            print(f"      成功: {summary.get('success', 0)}")
                            print(f"      失败: {summary.get('failed', 0)}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        # 根据模式确定返回状态
        if 'final_status' in result:
            return 0 if result['final_status'] == 'passed' else 1
        if 'status' in result:
            return 0 if result['status'] == 'passed' else 1
        return 0

    if args.feedback_discover:
        # 发现问题
        print("\n🔍 运行发现问题检查...")
        print("   检查项: 境界进度、角色状态、大纲一致性")
        print("-" * 50)

        result = feedback.run_discovery(
            check_realm_progression=True,
            check_consistency=True,
            check_character_state=True,
        )

        print("\n📊 发现问题报告:")
        print(f"   本次迭代: {result['iteration']}")
        print(f"   发现问题数: {result['issues_found']}")

        severity_summary = result.get('severity_summary', {})
        for sev, count in severity_summary.items():
            if count > 0:
                emoji = "🔴" if "P0" in sev else ("🟠" if "P1" in sev else ("🟡" if "P2" in sev else "⚪"))
                print(f"      {emoji} {sev}: {count} 个")

        print(f"\n   需要修复: {'是 ❌' if result['needs_fix'] else '否 ✅'}")

        if result['issues']:
            print("\n📋 问题列表:")
            for issue in result['issues'][:10]:  # 只显示前10个
                sev = issue.get('severity', '')
                sev_emoji = "🔴" if "P0" in sev else ("🟠" if "P1" in sev else "🟡")
                print(f"   {sev_emoji} [{issue.get('id')}] {issue.get('title')}")
                print(f"      描述: {issue.get('description', '')[:50]}...")
                print(f"      影响章节: {issue.get('affected_chapters', [])}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0

    if args.feedback_analyze:
        # 分析问题
        print("\n🔬 运行问题分析...")
        print("   分析方法: 5-Why根因分析 + LLM深入分析")
        print("-" * 50)

        result = feedback.run_analysis(use_llm=True)

        print("\n📊 问题分析报告:")
        print(f"   本次迭代: {result['iteration']}")
        print(f"   分析问题数: {len(result['analyses'])}")

        for issue_id, analysis in result['analyses'].items():
            print(f"\n   问题 {issue_id}:")
            print(f"      根本原因: {analysis.get('root_cause', '分析中...')[:100]}...")
            print(f"      影响范围: {', '.join(analysis.get('impact_scope', [])[:3])}")
            options = analysis.get('options', [])
            if options:
                print(f"      修复选项: {len(options)} 个")
                for opt in options[:2]:
                    print(f"         - {opt.get('title', '未命名')}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0

    if args.feedback_fix:
        # 修复错误
        print("\n🔧 运行错误修复...")
        print("   策略: 推荐方案")
        print("-" * 50)

        result = feedback.run_fix(strategy="recommended")

        print("\n📊 修复报告:")
        print(f"   本次迭代: {result['iteration']}")
        print(f"   干运行: {'是' if result.get('dry_run') else '否'}")

        summary = result.get('summary', {})
        print(f"\n   总计: {summary.get('total', 0)}")
        print(f"   成功: {summary.get('success', 0)} ✅")
        print(f"   失败: {summary.get('failed', 0)} ❌")

        for fix_result in result.get('fix_results', []):
            status_emoji = "✅" if fix_result['success'] else "❌"
            print(f"\n   {status_emoji} [{fix_result['issue_id']}]")
            print(f"      操作: {fix_result['fix_description'][:80]}...")
            if fix_result.get('files_modified'):
                print(f"      修改文件: {', '.join(fix_result['files_modified'][:3])}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0

    if args.feedback_verify:
        # 验证结果
        print("\n✅ 运行结果验证...")
        print("   验证项: 文件完整性、检查点验证")
        print("-" * 50)

        result = feedback.run_verification(full=True)

        print("\n📊 验证报告:")
        print(f"   本次迭代: {result['iteration']}")
        print(f"   验证通过: {'是 ✅' if result['verification_passed'] else '否 ❌'}")

        checks = result.get('checks', {})
        for check_name, check_result in checks.items():
            status_emoji = "✅" if check_result else "❌"
            print(f"   {status_emoji} {check_name}")

        summary = result.get('summary', {})
        print("\n   问题统计:")
        print(f"      总计: {summary.get('total_issues', 0)}")
        print(f"      已修复: {summary.get('fixed', 0)}")
        print(f"      待处理: {summary.get('open', 0)}")

        if result.get('open_issues'):
            print("\n   待处理问题:")
            for issue in result['open_issues'][:5]:
                print(f"      - [{issue.get('severity')}] {issue.get('title')}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0 if result['verification_passed'] else 1

    if args.feedback_report:
        # 导出报告
        print("\n📄 导出反馈报告...")
        report_path = feedback.export_report()
        print(f"✅ 报告已保存: {report_path}")

        # 同时显示摘要
        summary = feedback.get_issues_summary()
        print("\n📊 问题摘要:")
        print(f"   总计: {summary.get('total', 0)}")
        print(f"   按严重程度: {summary.get('by_severity', {})}")
        print(f"   按类别: {summary.get('by_category', {})}")
        print(f"   按状态: {summary.get('by_status', {})}")

        return 0

    print("❌ 未指定反馈循环操作")
    return 1


def _collect_writing_options_from_args(args) -> dict:
    """Collect writing options from argparse namespace."""
    return normalize_writing_options(
        {
            "style": getattr(args, "style", DEFAULT_WRITING_OPTIONS["style"]),
            "style_preset": getattr(args, "style_preset", ""),
            "perspective": getattr(args, "perspective", DEFAULT_WRITING_OPTIONS["perspective"]),
            "narrative_mode": getattr(args, "narrative_mode", DEFAULT_WRITING_OPTIONS["narrative_mode"]),
            "pace": getattr(args, "pace", DEFAULT_WRITING_OPTIONS["pace"]),
            "dialogue_density": getattr(args, "dialogue_density", DEFAULT_WRITING_OPTIONS["dialogue_density"]),
            "prose_style": getattr(args, "prose_style", DEFAULT_WRITING_OPTIONS["prose_style"]),
            "world_building_density": getattr(args, "world_building_density", DEFAULT_WRITING_OPTIONS["world_building_density"]),
            "emotion_intensity": getattr(args, "emotion_intensity", DEFAULT_WRITING_OPTIONS["emotion_intensity"]),
            "combat_style": getattr(args, "combat_style", DEFAULT_WRITING_OPTIONS["combat_style"]),
            "hook_strength": getattr(args, "hook_strength", DEFAULT_WRITING_OPTIONS["hook_strength"]),
        }
    )


def _resolve_active_writing_options(config_mgr, args) -> dict:
    """Merge project defaults with current CLI args."""
    project_defaults = {}
    if config_mgr.current_project:
        project_defaults = config_mgr.current_project.metadata.get("writing_options", {})
    cli_options = _collect_writing_options_from_args(args)
    merged = dict(normalize_writing_options(project_defaults))
    merged.update(cli_options)
    merged = normalize_writing_options(merged)
    if config_mgr.current_project:
        config_mgr.update_project_metadata({"writing_options": merged})
    return merged


def _print_writing_options(options: dict) -> None:
    """Print active writing options."""
    print("   写作参数:")
    for key, value in options.items():
        if value:
            print(f"      - {key}: {value}")


def _print_writing_option_catalog() -> None:
    """Print available writing option values."""
    print("\n🧭 写作参数可选值")
    print("-" * 50)
    for group, options in WRITING_OPTION_GROUPS.items():
        print(f"\n[{group}]")
        for key, desc in options.items():
            print(f"  - {key}: {desc}")


def _ensure_run_tracking(project_dir: Path, run_id: str, project_id: str, command: list[str], run_dir: Path | None) -> Path:
    """Create the run directory and baseline status if they do not exist yet."""
    resolved_run_dir = run_dir or ensure_run_dir(project_dir, run_id)
    if not read_status(resolved_run_dir):
        create_run(project_dir=project_dir, run_id=run_id, project_id=project_id, command=command)
    return resolved_run_dir


def _append_writing_options_to_command(cmd: list[str], options: dict[str, str]) -> None:
    cli_flag_map = {
        "style": "--style",
        "style_preset": "--style-preset",
        "perspective": "--perspective",
        "narrative_mode": "--narrative-mode",
        "pace": "--pace",
        "dialogue_density": "--dialogue-density",
        "prose_style": "--prose-style",
        "world_building_density": "--world-building-density",
        "emotion_intensity": "--emotion-intensity",
        "combat_style": "--combat-style",
        "hook_strength": "--hook-strength",
    }
    for key, value in options.items():
        if key in cli_flag_map and value:
            cmd.extend([cli_flag_map[key], value])


def _run_volume_generation_subprocess(
    args,
    *,
    project_id: str,
    run_id: str,
    run_dir: Path,
    start: int,
    count: int,
    writing_options: dict[str, str],
) -> int:
    """Reuse the existing incremental generator for one volume slice."""
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--load",
        project_id,
        "--generate",
        str(count),
        "--start",
        str(start),
        "--run-id",
        run_id,
        "--run-dir",
        str(run_dir),
        "--no-auto-feedback",
        "--log-level",
        getattr(args, "log_level", "INFO"),
    ]
    _append_writing_options_to_command(cmd, writing_options)
    result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent), check=False)  # noqa: S603
    return int(result.returncode)


def _finalize_longform_run(
    *,
    run_dir: Path,
    state: dict[str, Any],
    project_id: str,
    command: list[str],
    run_started_at: datetime,
    config_mgr,
) -> int:
    config_mgr.load_project(project_id)
    export_args = argparse.Namespace(
        output=None,
        start=1,
        end=None,
    )
    cmd_export(export_args)
    state["status"] = "succeeded"
    state["current_stage"] = STAGE_FINALIZE_EXPORT
    state["pending_state_path"] = None
    save_longform_state(run_dir, state)
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="succeeded",
        current_stage=STAGE_FINALIZE_EXPORT,
        current_step="长篇生成完成并导出",
        chapters_total=state.get("total_chapters", 0),
        chapters_completed=state.get("chapters_completed", 0),
        run_started_at=run_started_at,
        finished_at=datetime.now().isoformat(),
        return_code=0,
    )
    return 0


def _continue_longform_run(args, *, state: dict[str, Any], run_dir: Path, run_started_at: datetime) -> int:
    config_mgr = get_config_manager()
    project = config_mgr.current_project
    if not project:
        print("❌ 未设置当前项目. 请先使用 --load 或 --new")
        return 1

    project_id = project.id
    command = sys.argv[1:]
    writing_options = _resolve_active_writing_options(config_mgr, args)

    while True:
        current_volume = int(state.get("current_volume") or 0)
        start_chapter = int(state.get("current_volume_start_chapter") or 0)
        end_chapter = int(state.get("current_volume_end_chapter") or 0)

        if current_volume <= 0 or start_chapter <= 0 or end_chapter <= 0:
            return _finalize_longform_run(
                run_dir=run_dir,
                state=state,
                project_id=project_id,
                command=command,
                run_started_at=run_started_at,
                config_mgr=config_mgr,
            )

        next_start = max(int(state.get("chapters_completed", 0)) + 1, start_chapter)
        if next_start > end_chapter:
            state["last_completed_volume"] = current_volume
            if current_volume >= int(state.get("total_volumes", 0)):
                return _finalize_longform_run(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                    config_mgr=config_mgr,
                )
            state = next_volume(state)
            save_longform_state(run_dir, state)
            continue

        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="running",
            current_stage=STAGE_VOLUME_PLAN,
            current_step=f"准备第 {current_volume} 卷 ({start_chapter}-{end_chapter})",
            chapters_total=state.get("total_chapters", 0),
            chapters_completed=state.get("chapters_completed", 0),
            run_started_at=run_started_at,
        )

        state["current_stage"] = STAGE_VOLUME_WRITE
        save_longform_state(run_dir, state)
        return_code = _run_volume_generation_subprocess(
            args,
            project_id=project_id,
            run_id=state["run_id"],
            run_dir=run_dir,
            start=next_start,
            count=end_chapter - next_start + 1,
            writing_options=writing_options,
        )
        if return_code != 0:
            state["status"] = "failed"
            save_longform_state(run_dir, state)
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="failed",
                current_stage=STAGE_VOLUME_WRITE,
                current_step=f"第 {current_volume} 卷生成失败",
                chapters_total=state.get("total_chapters", 0),
                chapters_completed=state.get("chapters_completed", 0),
                run_started_at=run_started_at,
                failed_stage=STAGE_VOLUME_WRITE,
                error_message=f"第 {current_volume} 卷生成失败",
                finished_at=datetime.now().isoformat(),
                return_code=return_code,
            )
            return return_code

        refreshed_project = config_mgr.load_project(project_id) or project
        state["chapters_completed"] = max(int(getattr(refreshed_project, "current_chapter", 0)), end_chapter)
        state["current_stage"] = STAGE_VOLUME_REVIEW
        save_longform_state(run_dir, state)

        if should_pause_for_stage(state["approval_mode"], state["auto_approve"], "volume"):
            paused_state = record_pause(
                run_dir=run_dir,
                longform_state=state,
                checkpoint_type=CHECKPOINT_VOLUME,
                current_stage=STAGE_VOLUME_REVIEW,
                review_payload=review_payload_for_volume(state),
            )
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="paused",
                current_stage=STAGE_VOLUME_REVIEW,
                current_step=f"等待第 {current_volume} 卷审批",
                chapters_total=paused_state.get("total_chapters", 0),
                chapters_completed=paused_state.get("chapters_completed", 0),
                run_started_at=run_started_at,
                error_message=None,
                failed_stage=None,
            )
            update_status(
                run_dir,
                pending_state_path=paused_state.get("pending_state_path"),
                longform_state_path=paused_state.get("longform_state_path"),
                pause_reason=CHECKPOINT_VOLUME,
            )
            return 0

        state["last_completed_volume"] = current_volume
        if current_volume >= int(state.get("total_volumes", 0)):
            return _finalize_longform_run(
                run_dir=run_dir,
                state=state,
                project_id=project_id,
                command=command,
                run_started_at=run_started_at,
                config_mgr=config_mgr,
            )
        state = next_volume(state)
        save_longform_state(run_dir, state)


def cmd_generate_full(args):
    """Generate a full novel with outline/volume pause-resume checkpoints."""
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 或 --load")
        return 1

    project = config_mgr.current_project
    project_id = project.id
    project_dir = _project_dir(config_mgr)
    project_dir.mkdir(parents=True, exist_ok=True)
    run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    run_started_at = datetime.now()
    command = sys.argv[1:]
    run_dir = _ensure_run_tracking(
        project_dir=project_dir,
        run_id=run_id,
        project_id=project_id,
        command=command,
        run_dir=_telemetry_run_dir(args, project_dir),
    )

    if getattr(args, "resume_state", None):
        pending_state = load_json_file(args.resume_state)
        state = load_longform_state(pending_state.get("longform_state_path"))
        if not state:
            print("❌ 无法加载 longform_state.v1.json")
            return 1

        action = getattr(args, "submit_approval", None) or "approve"
        approval_payload = approval_payload_from_input(getattr(args, "approval_payload", None))
        approval_entry = {
            "checkpoint_type": pending_state.get("checkpoint_type"),
            "action": action,
            "payload": approval_payload,
            "submitted_at": datetime.now().isoformat(),
        }
        state.setdefault("approval_history", []).append(approval_entry)

        if pending_state.get("checkpoint_type") == CHECKPOINT_OUTLINE:
            if action == "reject":
                save_longform_state(run_dir, state)
                _update_run_progress(
                    run_dir,
                    project_id=project_id,
                    command=command,
                    status="paused",
                    current_stage=STAGE_OUTLINE_REVIEW,
                    current_step="大纲审批被拒绝，等待修订",
                    chapters_total=state.get("total_chapters", 0),
                    chapters_completed=state.get("chapters_completed", 0),
                    run_started_at=run_started_at,
                )
                return 0
            if action == "revise":
                apply_outline_revision(project, approval_payload)
                config_mgr._save_project(project)
            state["approved_outline"] = True
            state["outline_snapshot"] = review_payload_for_outline(project)
            state["current_stage"] = STAGE_VOLUME_PLAN
            state = clear_pause(run_dir, state)
            update_status(run_dir, pending_state_path=None, pause_reason=None)
            return _continue_longform_run(args, state=state, run_dir=run_dir, run_started_at=run_started_at)

        if pending_state.get("checkpoint_type") == CHECKPOINT_VOLUME:
            current_volume = int(state.get("current_volume", 0))
            if action == "reject":
                save_longform_state(run_dir, state)
                _update_run_progress(
                    run_dir,
                    project_id=project_id,
                    command=command,
                    status="paused",
                    current_stage=STAGE_VOLUME_REVIEW,
                    current_step=f"第 {current_volume} 卷审批被拒绝，等待处理",
                    chapters_total=state.get("total_chapters", 0),
                    chapters_completed=state.get("chapters_completed", 0),
                    run_started_at=run_started_at,
                )
                return 0
            state["last_completed_volume"] = current_volume
            state["current_stage"] = STAGE_VOLUME_PLAN
            state = clear_pause(run_dir, state)
            if current_volume >= int(state.get("total_volumes", 0)):
                return _finalize_longform_run(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                    config_mgr=config_mgr,
                )
            state = next_volume(state)
            save_longform_state(run_dir, state)
            update_status(run_dir, pending_state_path=None, pause_reason=None)
            return _continue_longform_run(args, state=state, run_dir=run_dir, run_started_at=run_started_at)

        print("❌ 不支持的审批检查点")
        return 1

    state = initial_longform_state(
        project=project,
        run_id=run_id,
        run_dir=run_dir,
        chapters_per_volume=max(int(getattr(args, "chapters_per_volume", config_mgr.generation.chapters_per_volume)), 1),
        approval_mode=getattr(args, "approval_mode", "outline+volume"),
        auto_approve=bool(getattr(args, "auto_approve", False)),
    )
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="running",
        current_stage=STAGE_OUTLINE_GENERATE,
        current_step="初始化整本小说生成",
        chapters_total=state.get("total_chapters", 0),
        chapters_completed=state.get("chapters_completed", 0),
        run_started_at=run_started_at,
        return_code=None,
    )
    update_status(run_dir, longform_state_path=state.get("longform_state_path"))

    if should_pause_for_stage(state["approval_mode"], state["auto_approve"], "outline"):
        paused_state = record_pause(
            run_dir=run_dir,
            longform_state=state,
            checkpoint_type=CHECKPOINT_OUTLINE,
            current_stage=STAGE_OUTLINE_REVIEW,
            review_payload=review_payload_for_outline(project),
        )
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="paused",
            current_stage=STAGE_OUTLINE_REVIEW,
            current_step="等待大纲审批",
            chapters_total=paused_state.get("total_chapters", 0),
            chapters_completed=paused_state.get("chapters_completed", 0),
            run_started_at=run_started_at,
        )
        update_status(
            run_dir,
            pending_state_path=paused_state.get("pending_state_path"),
            longform_state_path=paused_state.get("longform_state_path"),
            pause_reason=CHECKPOINT_OUTLINE,
        )
        return 0

    state["approved_outline"] = True
    state["outline_snapshot"] = review_payload_for_outline(project)
    save_longform_state(run_dir, state)
    return _continue_longform_run(args, state=state, run_dir=run_dir, run_started_at=run_started_at)


def main():
    """主入口."""
    parser = argparse.ArgumentParser(
        description="小说生成器 - 使用 KIMI 自动生成小说",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建新项目
  python run_novel_generation.py --new "太古魔帝传" --genre "玄幻修仙" \\
    --outline "少年韩林获得上古魔帝传承，逆天崛起..." \\
    --world "修真世界，境界分为炼气、筑基、金丹..." \\
    --characters "韩林: 主角，低调隐忍..." --chapters 100

  # 生成10章（自动触发反馈循环）
  python run_novel_generation.py --generate 10

  # 生成10章（禁用自动反馈）
  python run_novel_generation.py --generate 10 --no-auto-feedback

  # 从第5章开始生成5章
  python run_novel_generation.py --generate 5 --start 5

  # 指定风格参数
  python run_novel_generation.py --generate 3 --style-preset fanren_flow --pace fast --combat-style epic

  # 整本长篇生成（大纲 + 分卷检查点）
  python run_novel_generation.py --generate-full --chapters-per-volume 60
  python run_novel_generation.py --generate-full --resume-state /path/to/pending.json --submit-approval approve

  # 查看状态
  python run_novel_generation.py --status

  # 列出章节
  python run_novel_generation.py --list

  # 验证项目完整性
  python run_novel_generation.py --verify

  # 导出为文本
  python run_novel_generation.py --export

  # 加载已有项目
  python run_novel_generation.py --load abc123def456

  # 衍生内容生成
  python run_novel_generation.py --sync-derivatives 1-10  # 同步第1-10章的衍生内容
  python run_novel_generation.py --list-derivatives       # 列出所有衍生内容
  python run_novel_generation.py --podcast 1-4           # 生成第1-4章播客
  python run_novel_generation.py --video-prompt 5         # 生成第5章视频提示词
  python run_novel_generation.py --character 韩林          # 生成韩林的角色描述

  # 反馈循环 (发现问题→分析问题→修改错误)
  python run_novel_generation.py --load 7414da9519da     # 加载项目
  python run_novel_generation.py --feedback-discover      # 发现问题
  python run_novel_generation.py --feedback-analyze      # 分析问题
  python run_novel_generation.py --feedback-fix          # 修复错误
  python run_novel_generation.py --feedback-verify        # 验证结果
  python run_novel_generation.py --feedback-cycle         # 快速反馈循环（默认）
  python run_novel_generation.py --feedback-cycle --feedback-mode deep  # 完成20章后深度反馈
  python run_novel_generation.py --feedback-cycle --feedback-mode volume_complete  # 完成一卷后反馈
  python run_novel_generation.py --feedback-cycle --feedback-mode full --feedback-max-iterations 5  # 完整分析
  python run_novel_generation.py --feedback-report       # 导出报告
        """,
    )

    # 项目命令
    parser.add_argument("--new", metavar="TITLE", help="创建新项目")
    parser.add_argument("--genre", default="玄幻修仙", help="小说题材")
    parser.add_argument("--outline", default="", help="故事大纲")
    parser.add_argument("--world", default="", help="世界观设定")
    parser.add_argument("--characters", default="", help="人物设定")
    parser.add_argument("--author", default="AI Author", help="作者名")
    parser.add_argument("--chapters", type=int, default=100, help="计划章节数")
    parser.add_argument("--load", metavar="PROJECT_ID", help="加载已有项目")

    # 生成命令
    parser.add_argument("--generate", type=int, metavar="COUNT", help="生成章节数量")
    parser.add_argument("--generate-full", action="store_true", help="按整本长篇流程生成并在大纲/分卷节点暂停审批")
    parser.add_argument("--start", type=int, help="起始章节号")
    parser.add_argument("--run-id", help="运行任务ID（用于写入任务状态）")
    parser.add_argument("--run-dir", help="运行任务目录（用于写入 status.json 和日志）")
    parser.add_argument("--chapters-per-volume", type=int, default=60, help="长篇模式每卷章节数")
    parser.add_argument(
        "--approval-mode",
        choices=["outline+volume", "outline", "volume", "none"],
        default="outline+volume",
        help="长篇模式的人审节点",
    )
    parser.add_argument("--auto-approve", action="store_true", help="长篇模式自动跳过所有审批节点")
    parser.add_argument("--resume-state", help="恢复长篇运行时使用的 pending state 文件")
    parser.add_argument(
        "--submit-approval",
        choices=["approve", "revise", "reject"],
        help="提交对 pending state 的审批动作",
    )
    parser.add_argument("--approval-payload", help="审批补充 JSON，可传文件路径或 JSON 字符串")
    parser.add_argument("--continue-from", type=int,
                        help="从指定章节号继续生成（跳过已成功的章节）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览要生成的章节，不实际生成")
    parser.add_argument("--no-auto-feedback", action="store_true",
                        help="禁用自动反馈循环")
    parser.add_argument("--show-writing-options", action="store_true",
                        help="显示所有写作参数可选值并退出")
    parser.add_argument("--style", choices=BASE_STYLE_CHOICES,
                        default=DEFAULT_WRITING_OPTIONS["style"], help="基础写作风格")
    parser.add_argument("--style-preset", choices=[""] + STYLE_PRESET_CHOICES,
                        default="", help="知识库风格预设")
    parser.add_argument("--perspective", choices=sorted(WRITING_OPTION_GROUPS["perspective"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["perspective"], help="叙事视角")
    parser.add_argument("--narrative-mode", choices=sorted(WRITING_OPTION_GROUPS["narrative_mode"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["narrative_mode"], help="叙事写法")
    parser.add_argument("--pace", choices=sorted(WRITING_OPTION_GROUPS["pace"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["pace"], help="节奏")
    parser.add_argument("--dialogue-density", choices=sorted(WRITING_OPTION_GROUPS["dialogue_density"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["dialogue_density"], help="对白密度")
    parser.add_argument("--prose-style", choices=sorted(WRITING_OPTION_GROUPS["prose_style"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["prose_style"], help="行文质感")
    parser.add_argument("--world-building-density", choices=sorted(WRITING_OPTION_GROUPS["world_building_density"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["world_building_density"], help="设定密度")
    parser.add_argument("--emotion-intensity", choices=sorted(WRITING_OPTION_GROUPS["emotion_intensity"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["emotion_intensity"], help="情绪强度")
    parser.add_argument("--combat-style", choices=sorted(WRITING_OPTION_GROUPS["combat_style"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["combat_style"], help="战斗写法")
    parser.add_argument("--hook-strength", choices=sorted(WRITING_OPTION_GROUPS["hook_strength"].keys()),
                        default=DEFAULT_WRITING_OPTIONS["hook_strength"], help="开篇抓力")

    # 状态命令
    parser.add_argument("--status", action="store_true", help="查看项目状态")
    parser.add_argument("--list", action="store_true", help="列出所有章节")
    parser.add_argument("--verify", action="store_true", help="验证项目完整性")

    # 导出命令
    parser.add_argument("--export", action="store_true", help="导出为文本文件")
    parser.add_argument("--output", help="导出文件路径")
    parser.add_argument("--end", type=int, help="导出结束章节号")

    # 番茄发布命令
    parser.add_argument("--publish", metavar="RANGE", help="发布章节到番茄 (如: 1-5)")
    parser.add_argument("--publish-all", action="store_true", help="发布所有章节到番茄")
    parser.add_argument("--fanqie-book-id", help="番茄书号 (覆盖配置)")

    # 衍生内容命令
    parser.add_argument("--sync-derivatives", metavar="RANGE", help="同步衍生内容 (如: 1-10)")
    parser.add_argument("--list-derivatives", action="store_true", help="列出所有衍生内容")
    parser.add_argument("--podcast", metavar="RANGE", help="生成播客脚本 (如: 1-4)")
    parser.add_argument("--video-prompt", type=int, metavar="CHAPTER", help="生成视频提示词")
    parser.add_argument("--character", metavar="NAME", help="生成角色描述")

    # 反馈循环命令
    parser.add_argument("--feedback-discover", action="store_true",
                        help="发现问题：运行一致性检查，发现潜在问题")
    parser.add_argument("--feedback-analyze", action="store_true",
                        help="分析问题：对发现的问题进行根因分析")
    parser.add_argument("--feedback-fix", action="store_true",
                        help="修复错误：根据分析结果修复问题")
    parser.add_argument("--feedback-verify", action="store_true",
                        help="验证结果：验证修复是否有效")
    parser.add_argument("--feedback-cycle", action="store_true",
                        help="完整反馈循环：发现问题→分析→修复→验证")
    parser.add_argument("--feedback-report", action="store_true",
                        help="导出反馈报告：输出问题报告到文件")
    parser.add_argument("--feedback-mode", choices=["light", "deep", "full", "volume_complete"],
                        default="light",
                        help="反馈循环模式: light=每5章快速检查, deep=完成20章后, full=完整分析, volume_complete=完成一卷后")
    parser.add_argument("--feedback-max-iterations", type=int, default=3,
                        help="最大迭代次数 (默认: 3)")

    # 日志
    parser.add_argument("--log-level", default="INFO", help="日志级别")

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.log_level)

    if args.show_writing_options:
        _print_writing_option_catalog()
        return 0

    # 根据命令执行
    # 注意: --load 可以和其他生成命令组合使用，所以单独处理
    if args.new:
        args.title = args.new
        return cmd_new_project(args)

    if args.load:
        args.project_id = args.load
        ret = cmd_load_project(args)
        if ret != 0:
            sys.exit(ret)
        # 继续处理其他命令（允许 --load + --generate 组合）

    if args.generate:
        args.count = args.generate
        # 如果同时指定了 --start 和 --continue-from，优先使用 --continue-from
        return cmd_generate(args)

    if args.generate_full:
        return cmd_generate_full(args)

    if args.status:
        return cmd_status(args)

    if args.list:
        return cmd_list_chapters(args)

    if args.verify:
        return cmd_verify(args)

    if args.export:
        return cmd_export(args)

    if args.publish:
        args.range = args.publish
        args.all = False
        return cmd_publish(args)

    if args.publish_all:
        args.range = "1-9999"
        args.all = True
        return cmd_publish(args)

    if args.sync_derivatives:
        args.range = args.sync_derivatives
        return cmd_sync_derivatives(args)

    if args.list_derivatives:
        return cmd_list_derivatives(args)

    if args.podcast:
        args.range = args.podcast
        return cmd_generate_podcast(args)

    if args.video_prompt:
        args.chapter = args.video_prompt
        return cmd_generate_video_prompt(args)

    if args.character:
        args.name = args.character
        return cmd_generate_character(args)

    # 反馈循环命令
    if args.feedback_discover or args.feedback_analyze or args.feedback_fix or args.feedback_verify or args.feedback_cycle or args.feedback_report:
        return cmd_feedback_loop(args)

    # 默认显示状态
    return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
