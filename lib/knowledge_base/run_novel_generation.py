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
import hashlib
import json
import logging
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from agents.config_manager import get_config_manager
from agents.novel_generator import get_novel_generator
from agents.chapter_manager import get_chapter_manager, ChapterPlotSummary
from agents.derivative_generator import get_derivative_generator
from agents.feedback_loop import get_feedback_loop, FeedbackMode, FeedbackStrategy
from agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig


def setup_logging(level: str = "INFO"):
    """设置日志."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class GenerationError(Exception):
    """章节生成失败的异常."""
    pass


# 反馈循环自动触发阈值
FEEDBACK_LIGHT_INTERVAL = 5   # 每5章
FEEDBACK_DEEP_INTERVAL = 20  # 每20章
FEEDBACK_VOLUME_SIZE = 20     # 一卷20章


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

    print(f"\n🔄 检查反馈循环触发条件...")
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

    print(f"\n✅ 项目创建成功!")
    print(f"   项目ID: {project.id}")
    print(f"   标题: {project.title}")
    print(f"   题材: {project.genre}")
    print(f"   计划章节: {project.total_chapters}")
    print(f"\n目录: ./lib/knowledge_base/novels/{project.title}/")



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

    # 使用标题目录而非ID目录
    from pathlib import Path
    # base_dir_override 直接使用 output_dir，因为 ChapterManager 会自动添加 project_title
    base_dir_override = str(Path(config_mgr.generation.output_dir).absolute())
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

    # 读取已有的 generation_results.json 获取已成功的章节（用于断点续传）
    results_file = Path(f"lib/knowledge_base/novels/{project_id}/generation_results.json")
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

    if dry_run:
        print(f"\n🔍 Dry-run 模式: 仅预览，不实际生成")
        print(f"   将生成章节: ", end="")
        preview = []
        for i in range(count):
            ch_num = start + i
            if ch_num in chapters_to_skip:
                preview.append(f"第{ch_num}章(已存在)")
            else:
                preview.append(f"第{ch_num}章")
        print(", ".join(preview))
        print(f"\n✅ Dry-run 完成，共 {count} 章需处理")
        return 0

    print("-" * 50)

    # 初始化追踪结果
    generation_run_id = str(uuid.uuid4())
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
    run_start_time = datetime.now()

    for i in range(count):
        chapter_num = start + i

        # 跳过已成功的章节（断点续传时）
        if chapter_num in chapters_to_skip:
            print(f"\n📝 第 {chapter_num} 章已存在，跳过")
            continue

        start_time = datetime.now()

        try:
            print(f"\n📝 生成第 {chapter_num} 章...")

            # 构建上下文
            context = chapter_mgr.build_context(chapter_num)

            # 生成章节
            chapter = generator.generate_chapter(
                chapter_number=chapter_num,
                context=context,
                previous_summary=previous_summary,
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
            metadata = chapter_mgr.save_chapter(
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
            _save_checkpoint(results_file, generation_results, project_id)
            print(f"   💾 Checkpoint 已保存 (第 {chapter_num} 章)")

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
            continue  # 继续处理其他章节

    # 保存最终结果到 JSON 文件
    generation_results['completed_at'] = datetime.now().isoformat()
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(generation_results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    _print_statistics(generation_results, failed_chapters, results_file, project.title)

    # 同步生成衍生内容（播客、视频Prompt、角色/场景描述）
    if generated:
        print("\n🔄 开始同步生成衍生内容...")
        try:
            scripts_dir = config_mgr.generation.scripts_dir
            derivative_gen = get_derivative_generator(project_id, kimi_client=kimi_client, base_dir_override=base_dir_override, scripts_dir_override=scripts_dir)
            # 使用已生成章节的范围
            chapter_range = f"{generated[0].number}-{generated[-1].number}"
            sync_results = derivative_gen.sync_derivatives(chapter_range)
            print(f"   ✅ 衍生内容同步完成:")
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
        _run_auto_feedback(project_id, generated, current_total, llm_client=kimi_client)

    if failed_chapters:
        return 1
    else:
        return 0


def _save_checkpoint(results_file: Path, results: dict, project_id: str) -> None:
    """保存 checkpoint 到文件."""
    checkpoint_file = Path(f"lib/knowledge_base/novels/{project_id}/generation_checkpoint.json")
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _print_statistics(results: dict, failed_chapters: list, results_file: Path, project_id: str) -> None:
    """打印生成统计信息."""
    total_words = results.get('total_words_generated', 0)
    total_time = results.get('total_time_seconds', 0.0)
    speed = total_words / total_time if total_time > 0 else 0

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
        print(f"   存储位置: ./lib/knowledge_base/novels/{project_id}/chapters/")
        print(f"   结果文件: {results_file}")
        print(f"   检查点文件: ./lib/knowledge_base/novels/{project_id}/generation_checkpoint.json")
    else:
        print(f"✅ 生成完成! 共 {results.get('successful', 0)} 章")
        print(f"   存储位置: ./lib/knowledge_base/novels/{project_id}/chapters/")


def cmd_status(args):
    """查看状态."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    summary = config_mgr.get_project_summary()

    print(f"\n📊 项目状态")
    print("-" * 50)
    print(f"   标题: {summary.get('title')}")
    print(f"   作者: {summary.get('author')}")
    print(f"   题材: {summary.get('genre')}")
    print(f"   进度: {summary.get('current_chapter')}/{summary.get('total_chapters')} 章")
    print(f"   完成度: {summary.get('progress_percent')}%")

    if summary.get("fanqie_enabled"):
        print(f"   番茄发布: ✅ 已配置 (书号: {summary.get('fanqie_book_id')})")
    else:
        print(f"   番茄发布: ❌ 未配置")

    return 0


def cmd_list_chapters(args):
    """列出章节."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 使用标题目录而非ID目录
    from pathlib import Path
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).parent) if output_dir else None
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
    from pathlib import Path
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).parent) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)

    # 导出到标题目录
    if output_dir:
        base_path = Path(output_dir).parent
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
    else:
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

    print(f"\n📤 开始发布到番茄小说网...")
    print(f"   书号: {fanqie_config.book_id}")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    # 获取章节列表 - 使用标题目录
    from pathlib import Path
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).parent) if output_dir else None
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

    print(f"\n🔄 开始同步衍生内容...")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        results = derivative_gen.sync_derivatives(args.range)

        print(f"\n📊 同步结果:")
        print(f"   固定章节: {len(results['fixed_chapters'])} 章")
        print(f"   视频Prompt: {len(results['video_prompts'])} 个")
        print(f"   角色描述: {len(results['character_descriptions'])} 个")
        print(f"   场景描述: {len(results['scene_descriptions'])} 个")
        print(f"   播客脚本: {len(results['podcasts'])} 个")

        if results['errors']:
            print(f"\n   错误: {len(results['errors'])} 个")
            for err in results['errors'][:5]:
                print(f"      - {err}")

        print(f"\n✅ 同步完成!")
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

    print(f"\n📚 衍生内容列表")
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

    print(f"\n🎙️ 生成播客脚本...")
    print(f"   章节范围: {args.range}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        script = derivative_gen.generate_podcast_script(args.range)
        print(f"\n✅ 播客脚本生成成功!")
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

    print(f"\n🎬 生成视频提示词...")
    print(f"   章节: 第{args.chapter}章")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        prompt = derivative_gen.generate_video_prompt(args.chapter)
        print(f"\n✅ 视频提示词生成成功!")
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

    print(f"\n🔍 验证项目完整性...")
    print(f"   项目: {config_mgr.current_project.title}")
    print("-" * 50)

    # 使用标题目录而非ID目录
    from pathlib import Path
    output_dir = getattr(config_mgr.generation, 'output_dir', None)
    base_dir_override = str(Path(output_dir).parent) if output_dir else None
    chapter_mgr = get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)

    # 执行完整性检查
    declared_latest = config_mgr.current_project.current_chapter
    result = chapter_mgr.verify_project_integrity(declared_latest)

    # 打印结果
    print(f"\n📊 完整性检查结果:")
    print(f"   状态: {'✅ 通过' if result['valid'] else '❌ 存在问题'}")

    stats = result.get('stats', {})
    print(f"\n📈 统计信息:")
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
    print(f"\n📚 章节序列检查:")
    print(f"   状态: {'✅ 连续' if seq_result['valid'] else '❌ 不连续'}")
    seq_stats = seq_result.get('stats', {})
    print(f"   范围内章节: {seq_stats.get('existing_count', 0)}/{seq_stats.get('total_in_range', 0)}")
    print(f"   缺失章节: {seq_stats.get('missing_count', 0)}")
    print(f"   跳跃次数: {seq_stats.get('gap_count', 0)}")

    if seq_result.get('gaps'):
        print(f"\n   跳跃详情:")
        for gap in seq_result['gaps']:
            print(f"     - 第{gap['from_chapter']}章 → 第{gap['to_chapter']}章 (缺失 {gap['gap_size']} 章)")

    # 返回状态
    if result['valid'] and seq_result['valid']:
        print(f"\n✅ 项目验证通过!")
        return 0
    else:
        print(f"\n⚠️ 项目验证发现问题，请检查上述信息")
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

    print(f"\n👤 生成角色描述...")
    print(f"   角色: {args.name}")
    print("-" * 50)

    derivative_gen = get_derivative_generator(config_mgr.current_project.id, kimi_client=kimi_client, scripts_dir_override=config_mgr.generation.scripts_dir)

    try:
        char = derivative_gen.generate_character_description(args.name)
        print(f"\n✅ 角色描述生成成功!")
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
    from agents.feedback_loop import get_feedback_loop, FeedbackLoop, FeedbackMode, FeedbackStrategy

    # 获取 KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        llm_client = get_kimi_client()
    except Exception:
        llm_client = None

    print(f"\n🔄 反馈循环")
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
            print(f"   模式: full")
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
        elif 'status' in result:
            return 0 if result['status'] == 'passed' else 1
        return 0

    elif args.feedback_discover:
        # 发现问题
        print("\n🔍 运行发现问题检查...")
        print("   检查项: 境界进度、角色状态、大纲一致性")
        print("-" * 50)

        result = feedback.run_discovery(
            check_realm_progression=True,
            check_consistency=True,
            check_character_state=True,
        )

        print(f"\n📊 发现问题报告:")
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

    elif args.feedback_analyze:
        # 分析问题
        print("\n🔬 运行问题分析...")
        print("   分析方法: 5-Why根因分析 + LLM深入分析")
        print("-" * 50)

        result = feedback.run_analysis(use_llm=True)

        print(f"\n📊 问题分析报告:")
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

    elif args.feedback_fix:
        # 修复错误
        print("\n🔧 运行错误修复...")
        print("   策略: 推荐方案")
        print("-" * 50)

        result = feedback.run_fix(strategy="recommended")

        print(f"\n📊 修复报告:")
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

    elif args.feedback_verify:
        # 验证结果
        print("\n✅ 运行结果验证...")
        print("   验证项: 文件完整性、检查点验证")
        print("-" * 50)

        result = feedback.run_verification(full=True)

        print(f"\n📊 验证报告:")
        print(f"   本次迭代: {result['iteration']}")
        print(f"   验证通过: {'是 ✅' if result['verification_passed'] else '否 ❌'}")

        checks = result.get('checks', {})
        for check_name, check_result in checks.items():
            status_emoji = "✅" if check_result else "❌"
            print(f"   {status_emoji} {check_name}")

        summary = result.get('summary', {})
        print(f"\n   问题统计:")
        print(f"      总计: {summary.get('total_issues', 0)}")
        print(f"      已修复: {summary.get('fixed', 0)}")
        print(f"      待处理: {summary.get('open', 0)}")

        if result.get('open_issues'):
            print(f"\n   待处理问题:")
            for issue in result['open_issues'][:5]:
                print(f"      - [{issue.get('severity')}] {issue.get('title')}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0 if result['verification_passed'] else 1

    elif args.feedback_report:
        # 导出报告
        print("\n📄 导出反馈报告...")
        report_path = feedback.export_report()
        print(f"✅ 报告已保存: {report_path}")

        # 同时显示摘要
        summary = feedback.get_issues_summary()
        print(f"\n📊 问题摘要:")
        print(f"   总计: {summary.get('total', 0)}")
        print(f"   按严重程度: {summary.get('by_severity', {})}")
        print(f"   按类别: {summary.get('by_category', {})}")
        print(f"   按状态: {summary.get('by_status', {})}")

        return 0

    else:
        print("❌ 未指定反馈循环操作")
        return 1


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
    parser.add_argument("--start", type=int, help="起始章节号")
    parser.add_argument("--continue-from", type=int,
                        help="从指定章节号继续生成（跳过已成功的章节）")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅预览要生成的章节，不实际生成")
    parser.add_argument("--no-auto-feedback", action="store_true",
                        help="禁用自动反馈循环")

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

    # 根据命令执行
    # 注意: --load 可以和其他生成命令组合使用，所以单独处理
    exit_code = 0

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
        exit_code = cmd_generate(args)

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
