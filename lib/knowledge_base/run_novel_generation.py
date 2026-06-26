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
import re
import subprocess
import sys
from typing import Any
import uuid

from dotenv import load_dotenv


KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT_DIR = KNOWLEDGE_BASE_DIR.parents[1]
load_dotenv(REPO_ROOT_DIR / ".env", override=False)
load_dotenv(KNOWLEDGE_BASE_DIR / ".env", override=True)

from young_writer.agents.chapter_manager import (  # noqa: E402
    ChapterPlotSummary,
    get_chapter_manager,
)
from young_writer.agents.config_manager import get_config_manager  # noqa: E402
from young_writer.agents.feedback_loop import (  # noqa: E402
    FeedbackMode,
    FeedbackStrategy,
    get_feedback_loop,
)
from young_writer.agents.longform_memory import (  # noqa: E402
    create_longform_memory_store,
    record_memory_after_save,
)
from young_writer.agents.novel_generator import get_novel_generator  # noqa: E402
from young_writer.agents.novel_orchestrator import (  # noqa: E402
    NovelOrchestrator,
    OrchestratorConfig,
)
from young_writer.services.chapter_artifacts import (  # noqa: E402
    discover_saved_chapter_numbers,
    summarize_saved_chapters,
)
from young_writer.services.cli_commands import append_writing_option_flags  # noqa: E402
from young_writer.services.experience_pool import (  # noqa: E402
    EXPERIENCE_KIND_GENERATION,
    PROMOTED_STATUSES,
    GlobalExperiencePool,
    build_case_from_review_payload,
    build_experience_capsule,
    format_experience_capsule,
)
from young_writer.services.input_assembler import InputAssembler  # noqa: E402
from young_writer.services.longform_run import (  # noqa: E402
    CHECKPOINT_CHAPTER,
    CHECKPOINT_OUTLINE,
    CHECKPOINT_RISK,
    CHECKPOINT_VOLUME,
    STAGE_CHAPTER_REVIEW,
    STAGE_FINALIZE_EXPORT,
    STAGE_OUTLINE_GENERATE,
    STAGE_OUTLINE_REVIEW,
    STAGE_RISK_PAUSE,
    STAGE_VOLUME_PLAN,
    STAGE_VOLUME_REVIEW,
    STAGE_VOLUME_WRITE,
    apply_outline_revision,
    approval_payload_from_input,
    build_volume_risk_report,
    clear_pause,
    compile_chapter_rewrite_guidance,
    format_longform_registry,
    format_volume_guidance,
    initial_longform_state,
    load_json_file,
    load_longform_state,
    merge_longform_registry,
    next_volume,
    normalize_longform_registry,
    normalize_volume_guidance_payload,
    record_pause,
    review_payload_for_chapter,
    review_payload_for_outline,
    review_payload_for_risk,
    review_payload_for_volume,
    save_longform_state,
    save_risk_report,
    should_pause_for_stage,
)
from young_writer.services.narrative_state import (  # noqa: E402
    record_narrative_state_after_save,
)
from young_writer.services.paths import WorkspacePaths  # noqa: E402
from young_writer.services.project_assets import (  # noqa: E402
    ProjectAssetValidationError,
    load_project_assets_from_files,
)
from young_writer.services.run_storage import (  # noqa: E402
    create_run,
    ensure_run_dir,
    ensure_run_initialized,
    read_status,
    update_status,
)
from young_writer.services.story_graph.build import (  # noqa: E402
    record_story_graph_after_save,
)
from young_writer.services.story_input import load_story_input_bundle  # noqa: E402
from young_writer.writing_options import (  # noqa: E402
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


def _contiguous_completed_chapter(chapter_numbers: set[int]) -> int:
    expected = 1
    while expected in chapter_numbers:
        expected += 1
    return expected - 1


def _build_generation_worklist(
    *,
    explicit_start: int | None,
    continue_from: int | None,
    count: int,
    saved_chapters: set[int],
) -> list[int]:
    if count <= 0:
        return []
    if continue_from is not None:
        start = continue_from
        return [start + i for i in range(count)]
    if explicit_start is not None:
        start = explicit_start
        return [start + i for i in range(count)]

    contiguous_completed = _contiguous_completed_chapter(saved_chapters)
    high_watermark = max(saved_chapters) if saved_chapters else 0
    gap_repairs = [
        chapter for chapter in range(contiguous_completed + 1, high_watermark + 1)
        if chapter not in saved_chapters
    ]
    append_after_high_watermark = list(
        range(high_watermark + 1, high_watermark + 1 + count)
    )
    return (gap_repairs + append_after_high_watermark)[:count]


def cmd_diagnose_config(args) -> int:
    """Print non-secret integration diagnostics."""
    diagnostics = get_config_manager().diagnose_integrations()
    if getattr(args, "diagnose_json", False):
        print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    else:
        for name, status in diagnostics.items():
            reachable = status.get("reachable")
            suffix = "" if reachable is None else f", reachable={reachable}"
            print(
                f"{name}: configured={status.get('configured')}, "
                f"source={status.get('source')}{suffix}"
            )
    return 0


class GenerationError(Exception):
    """章节生成失败的异常."""


def _format_quality_gate_failure(report: dict[str, Any]) -> str:
    """Format deterministic quality gate evidence for CLI failures."""
    summary = str(report.get("summary", "") or "章节未通过质量闸门").strip()
    issue_types = [
        str(item).strip()
        for item in report.get("issue_types", [])
        if str(item).strip()
    ]
    hard_gate_issue_types = [
        str(item).strip()
        for item in report.get("hard_gate_issue_types", [])
        if str(item).strip()
    ]
    blocking_issues = [
        str(item).strip()
        for item in report.get("blocking_issues", [])
        if str(item).strip()
    ]
    rewrite_history = [
        item for item in report.get("rewrite_history", []) if isinstance(item, dict)
    ]
    graph_diff = dict(report.get("graph_diff_details", {}) or {})
    lines = [summary]
    if issue_types:
        lines.append(f"issue_types: {', '.join(issue_types)}")
    if hard_gate_issue_types:
        lines.append(f"hard_gate_issue_types: {', '.join(hard_gate_issue_types)}")
    if blocking_issues:
        lines.append("blocking_issues:")
        lines.extend(f"- {item}" for item in blocking_issues[:5])
    if rewrite_history:
        lines.append("rewrite_history:")
        for item in rewrite_history[-2:]:
            attempt = item.get("attempt", "?")
            mode = item.get("mode", "")
            invalid = bool(item.get("invalid"))
            item_issues = ", ".join(str(value) for value in item.get("issue_types", []))
            lines.append(
                f"- attempt={attempt}, mode={mode}, invalid={invalid}, issue_types={item_issues}"
            )
    recommended_action = str(graph_diff.get("recommended_action", "") or "").strip()
    if recommended_action:
        lines.append(f"graph_recommended_action: {recommended_action}")
    return "\n".join(lines)


# 反馈循环自动触发阈值
FEEDBACK_LIGHT_INTERVAL = 5  # 每5章
FEEDBACK_DEEP_INTERVAL = 20  # 每20章
FEEDBACK_VOLUME_SIZE = 20  # 一卷20章

STAGE_INIT = "init"
STAGE_CONTEXT_BUILD = "context.build"
STAGE_CHAPTER_GENERATE = "chapter.generate"
STAGE_CHAPTER_SAVE = "chapter.save"
STAGE_FEEDBACK_AUTO = "feedback.auto"
STAGE_FINALIZE = "finalize"


def _run_auto_feedback(
    project_id: str,
    generated_chapters: list,
    total_current: int,
    llm_client=None,
    project_dir: str | Path | None = None,
) -> None:
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

    feedback = get_feedback_loop(
        project_id, llm_client=llm_client, project_dir=project_dir
    )

    # 1. 检查 LIGHT 触发 (每5章)
    should_light = (total_current % FEEDBACK_LIGHT_INTERVAL == 0) or (
        end_ch % FEEDBACK_LIGHT_INTERVAL == 0
    )
    if should_light:
        print(f"\n📊 [AUTO] 触发 LIGHT 反馈 (每{FEEDBACK_LIGHT_INTERVAL}章)")
        strategy = FeedbackStrategy(
            mode=FeedbackMode.LIGHT,
            batch_size=FEEDBACK_LIGHT_INTERVAL,
            use_llm=False,
            auto_fix=True,
        )
        result = feedback.run_with_strategy(strategy)
        status = result.get("status", "unknown")
        print(f"   结果: {status}")

    # 2. 检查 DEEP 触发 (每20章)
    should_deep = (total_current % FEEDBACK_DEEP_INTERVAL == 0) or (
        end_ch % FEEDBACK_DEEP_INTERVAL == 0
    )
    if should_deep:
        print(f"\n📊 [AUTO] 触发 DEEP 反馈 (每{FEEDBACK_DEEP_INTERVAL}章)")
        strategy = FeedbackStrategy(
            mode=FeedbackMode.DEEP,
            batch_size=FEEDBACK_DEEP_INTERVAL,
            use_llm=True,
            auto_fix=True,
        )
        result = feedback.run_with_strategy(strategy)
        status = result.get("status", "unknown")
        print(f"   结果: {status}")

    # 3. 检查 VOLUME_COMPLETE 触发 (每20章=一卷)
    should_volume = (total_current % FEEDBACK_VOLUME_SIZE == 0) or (
        end_ch % FEEDBACK_VOLUME_SIZE == 0
    )
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
        status = result.get("status", "unknown")
        print(f"   结果: {status}")


def _project_dir(config_mgr) -> Path:
    """Return the canonical project output directory."""
    return Path(config_mgr.generation.output_dir).resolve()


def _build_llm_clients(config_mgr) -> tuple[Any | None, Any | None]:
    """Build the configured text client and optional Doubao client."""
    try:
        clients = config_mgr.build_provider_clients()
        return clients.get("text"), clients.get("doubao")
    except Exception as exc:
        logging.getLogger(__name__).warning("Failed to build provider clients: %s", exc)
        return None, None


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


def _initialize_telemetry_run(
    run_dir: Path | None,
    *,
    run_id: str,
    project_id: str,
    command: list[str],
) -> Path | None:
    """Ensure CLI-driven telemetry runs start from a complete status payload."""
    if run_dir is None:
        return None
    return ensure_run_initialized(
        run_dir,
        run_id=run_id,
        project_id=project_id,
        command=command,
    )


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


def _latest_run_failure_message(run_dir: Path | None, fallback: str) -> str:
    """Prefer the concrete child failure persisted in status.json."""
    if run_dir is None:
        return fallback
    try:
        status = read_status(run_dir)
    except Exception:
        return fallback
    for key in ("error_message", "current_step"):
        value = str(status.get(key) or "").strip()
        if value and value != fallback:
            return value
    return fallback


def _sync_status_longform_fields(run_dir: Path | None, state: dict[str, Any]) -> None:
    """Mirror lightweight longform fields into status.json for faster UI reads."""
    if run_dir is None:
        return
    attempts_used = dict(state.get("chapter_auto_repair_attempts_used", {}) or {})
    escalations_used = dict(
        state.get("chapter_auto_repair_escalations_used", {}) or {}
    )
    update_status(
        run_dir,
        longform_state_path=state.get("longform_state_path"),
        pending_state_path=state.get("pending_state_path"),
        risk_report_path=state.get("risk_report_path"),
        queued_volume_guidance=str(state.get("next_volume_guidance", "") or "").strip()
        or None,
        queued_volume_guidance_payload=state.get("next_volume_guidance_payload", {})
        or None,
        chapter_review_mode=state.get("chapter_review_mode"),
        chapter_auto_repair_attempts=state.get("chapter_auto_repair_attempts"),
        chapter_auto_repair_attempts_used=attempts_used,
        chapter_auto_repair_escalations_used=escalations_used,
        auto_repair_status=state.get("auto_repair_status"),
        last_auto_repair_action=state.get("last_auto_repair_action"),
        last_auto_repair_reason=state.get("last_auto_repair_reason"),
        last_auto_repair_chapter=state.get("last_auto_repair_chapter"),
        repair_exhausted_reason=state.get("repair_exhausted_reason"),
        graph_recommended_action=state.get("graph_recommended_action"),
        repair_decision=state.get("repair_decision"),
        repair_decision_reason=state.get("repair_decision_reason"),
        next_chapter_experience_capsule=state.get("next_chapter_experience_capsule"),
        global_experience_trace=state.get("global_experience_trace"),
        global_experience_promotion=state.get("global_experience_promotion"),
        chapters_completed_high_watermark=state.get(
            "chapters_completed_high_watermark"
        ),
    )


def _chapter_auto_repair_count(state: dict[str, Any], chapter_number: int) -> int:
    attempts = dict(state.get("chapter_auto_repair_attempts_used", {}) or {})
    return int(attempts.get(str(int(chapter_number)), 0) or 0)


def _set_chapter_auto_repair_count(
    state: dict[str, Any], chapter_number: int, count: int
) -> None:
    attempts = dict(state.get("chapter_auto_repair_attempts_used", {}) or {})
    attempts[str(int(chapter_number))] = max(int(count), 0)
    state["chapter_auto_repair_attempts_used"] = attempts


def _chapter_auto_repair_escalation_count(
    state: dict[str, Any], chapter_number: int
) -> int:
    escalations = dict(state.get("chapter_auto_repair_escalations_used", {}) or {})
    return int(escalations.get(str(int(chapter_number)), 0) or 0)


def _set_chapter_auto_repair_escalation_count(
    state: dict[str, Any], chapter_number: int, count: int
) -> None:
    escalations = dict(state.get("chapter_auto_repair_escalations_used", {}) or {})
    escalations[str(int(chapter_number))] = max(int(count), 0)
    state["chapter_auto_repair_escalations_used"] = escalations


def _resolve_chapter_auto_repair_attempts(
    explicit_value: Any,
    fallback_value: Any,
) -> int:
    raw_value = fallback_value if explicit_value is None else explicit_value
    return max(int(raw_value or 0), 0)


def _classify_chapter_repair_decision(report: dict[str, Any]) -> tuple[str, str]:
    """Return the controller repair decision for an invalid chapter report."""
    graph_diff = dict(report.get("graph_diff_details", {}) or {})
    recommended_action = str(graph_diff.get("recommended_action", "") or "").strip()
    issue_types = {
        str(item).strip()
        for item in report.get("issue_types", [])
        if str(item).strip()
    }
    conflicting_edges = [
        item
        for item in graph_diff.get("conflicting_edges", [])
        if isinstance(item, dict)
    ]
    rewrite_plan = (
        dict(report.get("rewrite_plan", {}) or {})
        if isinstance(report.get("rewrite_plan"), dict)
        else {}
    )
    operations = [
        item for item in rewrite_plan.get("operations", []) if isinstance(item, dict)
    ]
    operation_actions = {
        str(item.get("action", "") or "").strip() for item in operations if item
    }
    has_world_fact_conflict = "world_fact_violation" in issue_types
    world_fact_only = bool(issue_types) and issue_types <= {"world_fact_violation"}
    world_fact_edges_only = bool(conflicting_edges) and all(
        str(item.get("type", "") or "").strip() == "WORLD_FACT"
        for item in conflicting_edges
    )
    has_reconcile_plan = "reconcile_canon_fact" in operation_actions

    if recommended_action == "rebaseline":
        return "rebaseline", "graph_requested_rebaseline"
    if recommended_action == "rewrite":
        return "rewrite", "graph_requested_rewrite"
    if (
        recommended_action == "chapter_review"
        and has_world_fact_conflict
        and world_fact_only
        and world_fact_edges_only
        and has_reconcile_plan
    ):
        return "rewrite", "rewriteable_world_fact_conflict"
    if recommended_action == "chapter_review":
        return "chapter_review", "graph_requested_human_review"
    if has_world_fact_conflict and has_reconcile_plan and world_fact_edges_only:
        return "rewrite", "rewriteable_world_fact_conflict"
    return "chapter_review", "controller_default_human_review"


def _reconcile_pause_boundary_state(
    *,
    run_dir: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Refresh progress and bounded auto-repair bookkeeping before pausing."""
    project_dir = Path(
        state.get("project_dir")
        or run_dir.parent.parent
    ).resolve()
    saved_chapters = discover_saved_chapter_numbers(project_dir)
    disk_contiguous = _contiguous_completed_chapter(saved_chapters)
    disk_watermark = max(saved_chapters) if saved_chapters else 0
    if saved_chapters:
        state["chapters_completed"] = max(
            int(state.get("chapters_completed", 0) or 0),
            disk_contiguous,
        )
    state["chapters_completed_high_watermark"] = max(
        int(state.get("chapters_completed_high_watermark", 0) or 0),
        disk_watermark,
    )

    pending_validation = (
        state.get("pending_revision_validation")
        if isinstance(state.get("pending_revision_validation"), dict)
        else None
    )
    target_chapter = int(state.get("last_auto_repair_chapter", 0) or 0)
    if (
        target_chapter > 0
        and pending_validation
        and int(pending_validation.get("chapter_number") or 0) == target_chapter
    ):
        current_attempt = _chapter_auto_repair_count(state, target_chapter)
        inferred_attempt = int(pending_validation.get("auto_repair_attempt") or 0)
        if current_attempt <= 0 and inferred_attempt > 0:
            _set_chapter_auto_repair_count(state, target_chapter, inferred_attempt)
    return state


def _build_quality_gate_failure_notes(report: dict[str, Any]) -> str:
    """Format raw quality gate findings for regeneration prompts."""
    findings: list[str] = []
    for item in report.get("blocking_issues", []) or []:
        text = str(item).strip()
        if text and text not in findings:
            findings.append(text)
    for item in report.get("smoothness_details", []) or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("message", "") or "").strip()
        if text and text not in findings:
            findings.append(text)

    if not findings:
        summary = str(report.get("summary", "") or "").strip()
        if summary:
            findings.append(summary)

    if not findings:
        return ""

    lines = ["【失败证据】"]
    lines.extend(f"{index + 1}. {item}" for index, item in enumerate(findings[:5]))
    return "\n".join(lines)


def _compile_auto_repair_guidance_with_capsule(
    report: dict[str, Any],
    *,
    recommended_action: str,
    extra_notes: str = "",
) -> tuple[str, dict[str, Any]]:
    rewrite_plan = (
        dict(report.get("rewrite_plan", {}) or {})
        if isinstance(report.get("rewrite_plan", {}), dict)
        else {}
    )
    note_lines: list[str] = []
    failure_notes = _build_quality_gate_failure_notes(report)
    if recommended_action == "rebaseline":
        note_lines.append(
            "优先接受已发生剧情的推进结果，并重写本章使开篇承接、章节目标和后续计划基线一致。"
        )
    report_aware_notes = _build_report_aware_rewrite_notes(report)
    if report_aware_notes:
        note_lines.append(report_aware_notes)
    experience_capsule = _load_global_experience_capsule(report)
    experience_notes = format_experience_capsule(experience_capsule)
    if experience_notes:
        note_lines.append(experience_notes)
    if str(extra_notes or "").strip():
        note_lines.append(str(extra_notes).strip())
    guidance = compile_chapter_rewrite_guidance(
        rewrite_plan,
        extra_notes="\n".join(note_lines).strip(),
    )
    if failure_notes:
        guidance = "\n".join(part for part in (failure_notes, guidance) if part).strip()
    return guidance, experience_capsule


def _compile_auto_repair_guidance(
    report: dict[str, Any],
    *,
    recommended_action: str,
    extra_notes: str = "",
) -> str:
    guidance, _capsule = _compile_auto_repair_guidance_with_capsule(
        report,
        recommended_action=recommended_action,
        extra_notes=extra_notes,
    )
    return guidance


def _experience_query_terms(review_payload: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ("blocking_issues", "success_criteria"):
        value = review_payload.get(key)
        if isinstance(value, list):
            terms.extend(str(item).strip() for item in value if str(item).strip())
    rewrite_plan = review_payload.get("rewrite_plan")
    if isinstance(rewrite_plan, dict):
        for key in ("fixes", "success_criteria"):
            value = rewrite_plan.get(key)
            if isinstance(value, list):
                terms.extend(str(item).strip() for item in value if str(item).strip())
    anti_drift = review_payload.get("anti_drift_details")
    if isinstance(anti_drift, dict):
        for key in ("goal_lock", "previous_tail_signal"):
            value = str(anti_drift.get(key) or "").strip()
            if value:
                terms.append(value)
    return terms[:12]


def _load_global_experience_capsule(review_payload: dict[str, Any]) -> dict[str, Any]:
    issue_types = [
        str(item).strip()
        for item in review_payload.get("issue_types", [])
        if str(item).strip()
    ]
    query_terms = _experience_query_terms(review_payload)
    try:
        pool = GlobalExperiencePool()
        candidate_matches = pool.retrieve(
            stage="chapter.review",
            issue_types=issue_types,
            query_terms=query_terms,
            top_k=20,
            include_unverified=True,
            experience_kinds=[EXPERIENCE_KIND_GENERATION],
        )
        verified_matches = pool.retrieve(
            stage="chapter.review",
            issue_types=issue_types,
            query_terms=query_terms,
            top_k=4,
            experience_kinds=[EXPERIENCE_KIND_GENERATION],
        )
        capsule = build_experience_capsule(
            verified_matches
        )
        loaded_ids = capsule.get("loaded_ids", [])
        filtered_unverified = [
            case.id
            for _, case in candidate_matches
            if case.status not in PROMOTED_STATUSES
        ]
        trace = {
            "schema_version": "young_writer.global_experience_trace.v1",
            "experience_dir": str(pool.root_dir),
            "issue_types": issue_types,
            "query_terms": query_terms,
            "candidate_count": len(candidate_matches),
            "candidate_ids": [case.id for _, case in candidate_matches[:12]],
            "filtered_unverified_count": len(filtered_unverified),
            "filtered_unverified_ids": filtered_unverified[:12],
            "loaded_count": len(loaded_ids) if isinstance(loaded_ids, list) else 0,
            "loaded_ids": list(loaded_ids) if isinstance(loaded_ids, list) else [],
            "reason": (
                "loaded"
                if loaded_ids
                else (
                    "only_unverified_generation_guidance"
                    if filtered_unverified
                    else "no_matching_generation_guidance"
                )
            ),
        }
        capsule["trace"] = trace
        if capsule.get("loaded_ids"):
            pool.record_usage(
                experience_ids=list(capsule["loaded_ids"]),
                project_id=str(review_payload.get("source_project_id") or ""),
                run_id=str(review_payload.get("run_id") or ""),
                stage="chapter.review",
                chapter_number=int(review_payload.get("chapter_number") or 0),
                outcome="loaded",
            )
        return capsule
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Global experience retrieval skipped: %s", exc
        )
        return {
            "schema_version": "young_writer.global_experience.v1",
            "source": "young_writer_global_experience_pool",
            "items": [],
            "loaded_ids": [],
            "error": str(exc),
            "trace": {
                "schema_version": "young_writer.global_experience_trace.v1",
                "reason": "error",
                "error": str(exc),
            },
        }


def _capture_global_experience_case(
    review_payload: dict[str, Any],
    *,
    project_id: str,
    run_id: str,
) -> dict[str, Any]:
    try:
        pool = GlobalExperiencePool()
        saved = pool.append_case(
            build_case_from_review_payload(
                review_payload,
                project_id=project_id,
                run_id=run_id,
                status="captured",
            )
        )
        return {
            "schema_version": "young_writer.global_experience_capture.v1",
            "case_id": saved.id,
            "status": saved.status,
            "experience_kind": saved.experience_kind,
            "pool_path": str(pool.cases_path),
        }
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Global experience capture skipped: %s", exc
        )
        return {
            "schema_version": "young_writer.global_experience_capture.v1",
            "status": "skipped",
            "error": str(exc),
        }


def _promote_captured_experience_after_revision(
    *,
    pending_validation: dict[str, Any] | None,
    chapter_number: int,
    project_id: str,
    run_id: str,
) -> dict[str, Any]:
    if not isinstance(pending_validation, dict):
        return {"status": "skipped", "reason": "missing_pending_revision_validation"}

    target_chapter = int(pending_validation.get("chapter_number") or 0)
    if target_chapter != int(chapter_number):
        return {
            "status": "skipped",
            "reason": "chapter_mismatch",
            "target_chapter": target_chapter,
            "saved_chapter": int(chapter_number),
        }

    case_id = str(pending_validation.get("captured_experience_id") or "").strip()
    if not case_id:
        return {"status": "skipped", "reason": "missing_captured_experience_id"}
    if pending_validation.get("promotion_candidate") is not True:
        return {"status": "skipped", "reason": "not_a_promotion_candidate"}

    issue_types = [
        str(item).strip()
        for item in pending_validation.get("issue_types", [])
        if str(item).strip()
    ]
    captured_issue_types = [
        str(item).strip()
        for item in pending_validation.get("captured_issue_types", [])
        if str(item).strip()
    ]
    if issue_types and captured_issue_types and not set(issue_types).intersection(
        captured_issue_types
    ):
        return {
            "status": "skipped",
            "reason": "issue_type_mismatch",
            "issue_types": issue_types,
            "captured_issue_types": captured_issue_types,
        }

    try:
        pool = GlobalExperiencePool()
        candidate = pool.get_case(case_id)
        if candidate is None:
            return {
                "status": "skipped",
                "reason": "case_not_found",
                "case_id": case_id,
            }
        if candidate.status != "captured":
            return {
                "status": "skipped",
                "reason": "case_not_captured",
                "case_id": case_id,
                "case_status": candidate.status,
            }
        if candidate.experience_kind != EXPERIENCE_KIND_GENERATION:
            return {
                "status": "skipped",
                "reason": "case_not_generation_guidance",
                "case_id": case_id,
                "experience_kind": candidate.experience_kind,
            }
        promoted = pool.promote_case(
            case_id,
            status="verified",
            evidence_append={
                "event": "chapter_saved_after_revision",
                "project_id": project_id,
                "run_id": run_id,
                "chapter_number": int(chapter_number),
                "issue_types": issue_types,
                "success_criteria": [
                    str(item).strip()
                    for item in pending_validation.get("success_criteria", [])
                    if str(item).strip()
                ],
            },
        )
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Global experience promotion skipped: %s", exc
        )
        return {"status": "skipped", "reason": "error", "error": str(exc)}

    if promoted is None:
        return {"status": "skipped", "reason": "case_not_found", "case_id": case_id}
    return {
        "status": promoted.status,
        "case_id": promoted.id,
        "experience_kind": promoted.experience_kind,
        "chapter_number": int(chapter_number),
    }


def _record_successful_experience_promotion(
    *,
    run_dir: Path,
    longform_state: dict[str, Any],
    promotion_trace: dict[str, Any],
) -> None:
    longform_state["pending_revision_validation"] = None
    longform_state["next_chapter_guidance"] = ""
    longform_state["next_chapter_guidance_chapter"] = None
    longform_state["next_chapter_experience_capsule"] = {}
    longform_state["global_experience_trace"] = None
    longform_state["auto_repair_status"] = None
    longform_state["repair_exhausted_reason"] = None
    longform_state["global_experience_promotion"] = promotion_trace
    save_longform_state(run_dir, longform_state)
    _sync_status_longform_fields(run_dir, longform_state)


def _is_continuity_escalation_candidate(
    report: dict[str, Any], repair_decision: str
) -> bool:
    if repair_decision != "rewrite":
        return False
    issue_types = {
        str(item).strip()
        for item in report.get("issue_types", [])
        if str(item).strip()
    }
    allowed_issue_types = {
        "scene_or_timeline_disconnect",
        "goal_lock_false_inheritance",
    }
    if not issue_types or "scene_or_timeline_disconnect" not in issue_types:
        return False
    if not issue_types <= allowed_issue_types:
        return False
    smoothness_details = [
        item for item in report.get("smoothness_details", []) if isinstance(item, dict)
    ]
    if not smoothness_details:
        return False
    allowed_categories = {
        "上一章后果未被承接",
        "地点跳切无承接",
        "时间跳跃无锚点",
        "表面流畅但因果断裂",
    }
    categories = {
        str(item.get("category", "") or "").strip() for item in smoothness_details
    }
    return bool(categories) and categories <= allowed_categories


def _build_continuity_escalation_notes(report: dict[str, Any]) -> str:
    smoothness_details = [
        item for item in report.get("smoothness_details", []) if isinstance(item, dict)
    ]
    note_lines = [
        "这是连续性定向升级修复：只重写开头承接和首个关键行动，不要把上一章后果降成背景说明。"
    ]
    for item in smoothness_details[:2]:
        category = str(item.get("category", "") or "").strip()
        previous_evidence = str(item.get("previous_evidence", "") or "").strip()
        current_evidence = str(item.get("current_evidence", "") or "").strip()
        if category == "上一章后果未被承接" and previous_evidence:
            note_lines.append(
                f"开头第一段必须先回应上一章未完成后果「{previous_evidence}」，再解释它为何把人物带到当前场景「{current_evidence or '当前场景'}」。"
            )
        elif category == "地点跳切无承接" and previous_evidence and current_evidence:
            note_lines.append(
                f"先接住上一章地点「{previous_evidence}」，再明确写出到「{current_evidence}」的路径、抵达动作或切换原因。"
            )
        elif category == "时间跳跃无锚点" and current_evidence:
            note_lines.append(
                f"若保留时间跳跃「{current_evidence}」，必须在开头两句内交代缺失时段发生了什么、角色状态为何变成现在这样。"
            )
        elif category == "表面流畅但因果断裂":
            note_lines.append(
                "开头两段必须把上一章危险、选择或代价改写成当前行动的直接原因，不能只保留表面顺接。"
            )
    return "\n".join(note_lines).strip()


def _build_goal_lock_progression_notes(report: dict[str, Any]) -> str:
    issue_types = {
        str(item).strip()
        for item in report.get("issue_types", [])
        if str(item).strip()
    }
    if not issue_types.intersection({"missing_key_events", "goal_lock_false_inheritance"}):
        return ""

    packet = (
        dict(report.get("chapter_graph_packet", {}) or {})
        if isinstance(report.get("chapter_graph_packet", {}), dict)
        else {}
    )
    graph_diff = (
        dict(report.get("graph_diff_details", {}) or {})
        if isinstance(report.get("graph_diff_details", {}), dict)
        else {}
    )
    goal_lock = str(packet.get("chapter_goal", "") or packet.get("goal_lock", "") or "").strip()
    target_destination = ""
    for item in packet.get("target_destinations", []) or []:
        candidate = str(item).strip()
        if candidate:
            target_destination = candidate
            break
    must_include_event = ""
    for item in packet.get("must_include_events", []) or []:
        candidate = str(item).strip()
        if candidate:
            must_include_event = candidate
            break

    static_arrival_excerpt = ""
    for item in graph_diff.get("evidence_refs", []) or []:
        if not isinstance(item, dict):
            continue
        excerpt = str(item.get("excerpt", "") or "").strip()
        if not excerpt:
            continue
        if any(marker in excerpt for marker in ("抵达", "站在", "边缘", "外围", "凝视", "透过舷窗")):
            static_arrival_excerpt = excerpt[:120]
            break

    note_lines: list[str] = []
    if must_include_event:
        note_lines.append(
            f"关键事件「{must_include_event}」必须在正文里以动作加结果真实发生，不能只停留在摘要、宣言句或回想里。"
        )
    if goal_lock:
        note_lines.append(
            f"正文前半段必须围绕目标锁「{goal_lock}」推进一个可见动作链：接近阻碍、做出选择、执行动作、得到结果。"
        )
    if target_destination:
        note_lines.append(
            f"如果角色已经到达或接近「{target_destination}」，不要把正文主体停留在观察环境；必须继续写出进入、突破、核验或搜查等下一步行动。"
        )
    if static_arrival_excerpt:
        note_lines.append(
            f"当前失败样式是静态抵达开篇「{static_arrival_excerpt}」；重写时不要再次以抵达、站位、凝视或回想结束首段，首段后必须立刻进入主线动作。"
        )
    return "\n".join(note_lines).strip()


def _build_report_aware_rewrite_notes(report: dict[str, Any]) -> str:
    note_blocks: list[str] = []
    continuity_notes = _build_continuity_escalation_notes(report)
    if continuity_notes:
        note_blocks.append(continuity_notes)
    goal_lock_notes = _build_goal_lock_progression_notes(report)
    if goal_lock_notes:
        note_blocks.append(goal_lock_notes)
    return "\n".join(block for block in note_blocks if block).strip()


def _queue_chapter_auto_repair(
    *,
    run_dir: Path,
    state: dict[str, Any],
    project_id: str,
    command: list[str],
    run_started_at: datetime,
    chapter_number: int,
    title: str,
    report: dict[str, Any],
) -> bool:
    mode = str(state.get("chapter_review_mode", "manual") or "manual").strip()
    if mode != "auto":
        return False
    repair_decision, repair_decision_reason = _classify_chapter_repair_decision(report)
    graph_diff = dict(report.get("graph_diff_details", {}) or {})
    recommended_action = str(graph_diff.get("recommended_action", "") or "").strip()
    if repair_decision not in {"rewrite", "rebaseline"}:
        return False
    max_attempts = max(int(state.get("chapter_auto_repair_attempts", 0) or 0), 0)
    used_attempts = _chapter_auto_repair_count(state, chapter_number)
    continuity_escalation_allowed = (
        _is_continuity_escalation_candidate(report, repair_decision)
        and _chapter_auto_repair_escalation_count(state, chapter_number) <= 0
    )
    escalation_notes = ""
    if used_attempts >= max_attempts and continuity_escalation_allowed:
        escalation_notes = _build_continuity_escalation_notes(report)
        _set_chapter_auto_repair_escalation_count(state, chapter_number, 1)
    elif used_attempts >= max_attempts:
        state["auto_repair_status"] = "auto_repair_exhausted"
        state["repair_exhausted_reason"] = (
            f"第 {chapter_number} 章自动修复已达上限 {max_attempts} 次"
        )
        state["graph_recommended_action"] = recommended_action or None
        state["repair_decision"] = repair_decision
        state["repair_decision_reason"] = repair_decision_reason
        state["last_auto_repair_action"] = repair_decision
        state["last_auto_repair_reason"] = "attempt_limit_reached"
        state["last_auto_repair_chapter"] = int(chapter_number)
        _reconcile_pause_boundary_state(run_dir=run_dir, state=state)
        save_longform_state(run_dir, state)
        _sync_status_longform_fields(run_dir, state)
        return False

    guidance, experience_capsule = _compile_auto_repair_guidance_with_capsule(
        report,
        recommended_action=repair_decision,
        extra_notes=escalation_notes,
    )
    next_attempt = used_attempts + 1
    _set_chapter_auto_repair_count(state, chapter_number, next_attempt)
    state["next_chapter_guidance"] = guidance
    state["next_chapter_guidance_chapter"] = int(chapter_number)
    state["next_chapter_experience_capsule"] = experience_capsule
    state["global_experience_trace"] = (
        experience_capsule.get("trace") if isinstance(experience_capsule, dict) else None
    )
    rewrite_plan = (
        dict(report.get("rewrite_plan", {}) or {})
        if isinstance(report.get("rewrite_plan", {}), dict)
        else {}
    )
    state["pending_revision_validation"] = {
        "chapter_number": int(chapter_number),
        "issue_types": [
            str(item).strip()
            for item in report.get("issue_types", [])
            if str(item).strip()
        ],
        "success_criteria": [
            str(item).strip()
            for item in rewrite_plan.get("success_criteria", [])
            if str(item).strip()
        ],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
        "auto_repair_action": repair_decision,
        "auto_repair_attempt": next_attempt,
        "auto_repair_variant": "continuity_escalation"
        if escalation_notes
        else "standard",
    }
    state["status"] = "running"
    state["current_checkpoint"] = None
    state["pending_state_path"] = None
    state["current_stage"] = STAGE_VOLUME_PLAN
    state["auto_repair_status"] = "auto_repair_pending"
    state["graph_recommended_action"] = recommended_action or None
    state["repair_decision"] = repair_decision
    state["repair_decision_reason"] = repair_decision_reason
    state["last_auto_repair_action"] = repair_decision
    state["last_auto_repair_reason"] = (
        "quality_gate_invalid_continuity_escalation"
        if escalation_notes
        else "quality_gate_invalid"
    )
    state["last_auto_repair_chapter"] = int(chapter_number)
    state["repair_exhausted_reason"] = None
    save_longform_state(run_dir, state)
    _sync_status_longform_fields(run_dir, state)
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="running",
        current_stage=STAGE_CHAPTER_REVIEW,
        current_step=(
            f"第 {chapter_number} 章进入自动修复 "
            f"({next_attempt}/{max_attempts}): {repair_decision}"
        ),
        chapters_total=state.get("total_chapters", 0),
        chapters_completed=state.get("chapters_completed", 0),
        run_started_at=run_started_at,
        failed_stage=None,
        error_message=None,
    )
    update_status(
        run_dir,
        chapter_quality_report=report,
        graph_recommended_action=recommended_action or None,
        repair_decision=repair_decision,
        repair_decision_reason=repair_decision_reason,
        pending_state_path=None,
        pause_reason=None,
        review_disposition="auto_repair_pending",
    )
    return True


def _chapter_plan_goal_lock(project_dir: Path, chapter_number: int) -> str:
    bundle = load_story_input_bundle(project_dir)
    if bundle is None:
        return ""
    for plan in bundle.chapter_plans:
        if int(getattr(plan, "chapter_number", 0) or 0) == int(chapter_number):
            return str(getattr(plan, "goal_lock", "") or "").strip()
    return ""


def _extract_guidance_goal_lock(guidance: str) -> str:
    text = str(guidance or "")
    if not text:
        return ""
    match = re.search(r"【目标锁】([^\n\r]+)", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"goal_lock=([^，。\n\r]+)", text)
    return match.group(1).strip() if match else ""


def _clear_stale_revision_guidance(
    *, project_dir: Path, state: dict[str, Any]
) -> None:
    pending_validation = (
        state.get("pending_revision_validation")
        if isinstance(state.get("pending_revision_validation"), dict)
        else None
    )
    if not pending_validation:
        return
    chapter_number = int(pending_validation.get("chapter_number") or 0)
    if chapter_number <= 0:
        return
    current_goal_lock = _chapter_plan_goal_lock(project_dir, chapter_number)
    pending_goal_lock = str(pending_validation.get("goal_lock") or "").strip()
    if not pending_goal_lock:
        pending_goal_lock = _extract_guidance_goal_lock(
            str(state.get("next_chapter_guidance") or "")
        )
    if not current_goal_lock or not pending_goal_lock or current_goal_lock == pending_goal_lock:
        return

    state["pending_revision_validation"] = None
    state["next_chapter_guidance"] = ""
    state["next_chapter_guidance_chapter"] = None
    state["next_chapter_experience_capsule"] = {}
    state["global_experience_trace"] = None
    state["auto_repair_status"] = None
    state["repair_exhausted_reason"] = None
    state["last_auto_repair_action"] = None
    state["last_auto_repair_reason"] = "stale_goal_lock_cleared"
    attempts = dict(state.get("chapter_auto_repair_attempts_used", {}) or {})
    attempts.pop(str(chapter_number), None)
    state["chapter_auto_repair_attempts_used"] = attempts
    escalations = dict(state.get("chapter_auto_repair_escalations_used", {}) or {})
    escalations.pop(str(chapter_number), None)
    state["chapter_auto_repair_escalations_used"] = escalations


def _reconcile_longform_progress(
    config_mgr: Any,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Reconcile longform progress against the saved chapter artifacts on disk."""
    project_dir = _project_dir(config_mgr)
    _clear_stale_revision_guidance(project_dir=project_dir, state=state)
    saved_chapters = discover_saved_chapter_numbers(project_dir)
    disk_contiguous = _contiguous_completed_chapter(saved_chapters)
    disk_watermark = max(saved_chapters) if saved_chapters else 0
    project_watermark = int(getattr(config_mgr.current_project, "current_chapter", 0) or 0)
    if saved_chapters:
        state["chapters_completed"] = disk_contiguous
    else:
        state["chapters_completed"] = max(
            int(state.get("chapters_completed", 0) or 0),
            project_watermark,
        )
    state["chapters_completed_high_watermark"] = max(
        int(state.get("chapters_completed_high_watermark", 0) or 0),
        disk_watermark,
        project_watermark,
    )
    return state


def _pause_for_invalid_chapter(
    *,
    run_dir: Path,
    state: dict[str, Any],
    project_id: str,
    command: list[str],
    run_started_at: datetime,
    chapter,
) -> int:
    """Pause a longform run when a chapter remains invalid after one rewrite."""
    report = dict(chapter.consistency_report or {})
    if _queue_chapter_auto_repair(
        run_dir=run_dir,
        state=state,
        project_id=project_id,
        command=command,
        run_started_at=run_started_at,
        chapter_number=chapter.number,
        title=chapter.title,
        report=report,
    ):
        return 0
    repair_decision, repair_decision_reason = _classify_chapter_repair_decision(report)
    recommended_action = str(
        dict(report.get("graph_diff_details", {}) or {}).get("recommended_action", "")
        or ""
    ).strip()
    state["graph_recommended_action"] = recommended_action or None
    state["repair_decision"] = repair_decision
    state["repair_decision_reason"] = repair_decision_reason
    existing_auto_repair_status = str(state.get("auto_repair_status", "") or "").strip()
    if existing_auto_repair_status == "auto_repair_exhausted":
        state["auto_repair_status"] = "auto_repair_exhausted"
        state["repair_exhausted_reason"] = (
            report.get("summary") or f"第 {chapter.number} 章自动修复耗尽"
        )
    else:
        state["auto_repair_status"] = (
            "plan_rebaseline_required"
            if repair_decision == "rebaseline"
            else "human_review_required"
        )
    if state["auto_repair_status"] == "human_review_required":
        state["last_auto_repair_action"] = None
        state["last_auto_repair_reason"] = None
        state["last_auto_repair_chapter"] = None
    else:
        state["last_auto_repair_chapter"] = int(chapter.number)
    report["auto_repair_status"] = state["auto_repair_status"]
    report["repair_decision"] = repair_decision
    report["repair_decision_reason"] = repair_decision_reason
    _reconcile_pause_boundary_state(run_dir=run_dir, state=state)
    chapter_review_payload = review_payload_for_chapter(
        chapter_number=chapter.number,
        title=chapter.title,
        report=report,
        rewrite_history=chapter.metadata.get("rewrite_history", []),
    )
    chapter_review_payload["source_project_id"] = project_id
    chapter_review_payload["run_id"] = str(run_dir.name)
    global_experience_capture = _capture_global_experience_case(
        chapter_review_payload,
        project_id=project_id,
        run_id=str(run_dir.name),
    )
    chapter_review_payload["global_experience_capture"] = global_experience_capture
    paused_state = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload=chapter_review_payload,
    )
    rewrite_plan = (
        dict(report.get("rewrite_plan", {}) or {})
        if isinstance(report.get("rewrite_plan", {}), dict)
        else {}
    )
    captured_case_id = str(global_experience_capture.get("case_id") or "").strip()
    paused_state["pending_revision_validation"] = {
        "chapter_number": int(chapter.number),
        "issue_types": [
            str(item).strip()
            for item in report.get("issue_types", [])
            if str(item).strip()
        ],
        "success_criteria": [
            str(item).strip()
            for item in rewrite_plan.get("success_criteria", [])
            if str(item).strip()
        ],
        "created_from_checkpoint": CHECKPOINT_CHAPTER,
        "captured_experience_id": captured_case_id or None,
        "captured_issue_types": [
            str(item).strip()
            for item in report.get("issue_types", [])
            if str(item).strip()
        ],
        "promotion_candidate": bool(captured_case_id),
    }
    paused_state = save_longform_state(run_dir, paused_state)
    _sync_status_longform_fields(run_dir, paused_state)
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="paused",
        current_stage=STAGE_CHAPTER_REVIEW,
        current_step=f"第 {chapter.number} 章未通过质量闸门，等待决策",
        chapters_total=paused_state.get("total_chapters", 0),
        chapters_completed=paused_state.get("chapters_completed", 0),
        run_started_at=run_started_at,
        failed_stage=STAGE_CHAPTER_GENERATE,
        error_message=report.get("summary") or "章节未通过质量闸门",
        return_code=1,
    )
    update_status(
        run_dir,
        pending_state_path=paused_state.get("pending_state_path"),
        longform_state_path=paused_state.get("longform_state_path"),
        pause_reason=CHECKPOINT_CHAPTER,
        risk_report_path=None,
        chapter_quality_report=report,
        graph_recommended_action=recommended_action or None,
        repair_decision=repair_decision,
        repair_decision_reason=repair_decision_reason,
        review_disposition=state["auto_repair_status"],
    )
    _sync_status_longform_fields(run_dir, paused_state)
    return 0


def _load_chapter_consistency_report(
    project_dir: Path, chapter_number: int
) -> dict[str, Any] | None:
    path = (
        project_dir / "consistency_reports" / f"ch{chapter_number:03d}_consistency.json"
    )
    if not path.exists():
        return None
    payload = load_json_file(path)
    if not payload:
        return None
    report = payload.get("report", payload)
    return report if isinstance(report, dict) else None


def _pause_for_revision_validation_failure(
    *,
    run_dir: Path,
    state: dict[str, Any],
    project_id: str,
    command: list[str],
    run_started_at: datetime,
    chapter_number: int,
    issue_types: list[str],
    reason: str,
    command_return: bool = False,
) -> int:
    review_payload = {
        "chapter_number": chapter_number,
        "title": f"第{chapter_number}章",
        "summary": reason,
        "issue_types": issue_types,
        "blocking_issues": [reason],
        "missing_events": [],
        "continuity_issues": [],
        "world_fact_issues": [],
        "pause_disposition": "auto_repair_exhausted",
    }
    state["auto_repair_status"] = "auto_repair_exhausted"
    state["repair_exhausted_reason"] = reason
    state["last_auto_repair_chapter"] = int(chapter_number)
    paused_state = record_pause(
        run_dir=run_dir,
        longform_state=state,
        checkpoint_type=CHECKPOINT_CHAPTER,
        current_stage=STAGE_CHAPTER_REVIEW,
        review_payload=review_payload,
    )
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="paused",
        current_stage=STAGE_CHAPTER_REVIEW,
        current_step=f"第 {chapter_number} 章修订验证未通过，等待决策",
        chapters_total=paused_state.get("total_chapters", 0),
        chapters_completed=paused_state.get("chapters_completed", 0),
        run_started_at=run_started_at,
        failed_stage=STAGE_CHAPTER_GENERATE,
        error_message=reason,
        return_code=1,
    )
    update_status(
        run_dir,
        pending_state_path=paused_state.get("pending_state_path"),
        longform_state_path=paused_state.get("longform_state_path"),
        pause_reason=CHECKPOINT_CHAPTER,
        risk_report_path=None,
        review_disposition="auto_repair_exhausted",
    )
    _sync_status_longform_fields(run_dir, paused_state)
    return 1 if command_return else 0


def cmd_new_project(args):
    """创建新项目."""
    config_mgr = get_config_manager()
    llm_client, _ = _build_llm_clients(config_mgr)
    has_asset_files = any(
        getattr(args, name, None)
        for name in ("asset_file", "outline_file", "world_file", "characters_file")
    )
    project_assets = None
    if has_asset_files:
        try:
            project_assets = load_project_assets_from_files(
                asset_file=getattr(args, "asset_file", None),
                outline_file=getattr(args, "outline_file", None),
                world_file=getattr(args, "world_file", None),
                characters_file=getattr(args, "characters_file", None),
            )
        except ProjectAssetValidationError as exc:
            print(f"❌ 项目资产导入失败: {exc}")
            return 1
        except (OSError, json.JSONDecodeError) as exc:
            print(f"❌ 项目资产文件读取失败: {exc}")
            return 1

    project = config_mgr.create_project(
        title=args.title,
        author=args.author or "AI Author",
        genre=args.genre,
        outline=args.outline,
        world_setting=args.world or "",
        character_intro=args.characters or "",
        total_chapters=args.chapters or 100,
        llm_client=llm_client,
        project_assets=project_assets,
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
    """创建小说编排器（小说主线模式）.

    Args:
        config_mgr: 配置管理器
        project_id: 项目ID

    Returns:
        NovelOrchestrator 实例
    """
    logger = logging.getLogger(__name__)

    llm_client, _ = _build_llm_clients(config_mgr)
    if llm_client is None:
        raise RuntimeError("Configured LLM client not available for orchestrator")
    logger.info(
        "LLM client initialized for NovelOrchestrator: provider=%s model=%s",
        getattr(llm_client, "provider_name", config_mgr.generation.active_provider),
        getattr(llm_client, "model_name", config_mgr.generation.model_name),
    )

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

    logger.info("NovelOrchestrator created for novel generation")
    return orchestrator


def cmd_generate(args):
    """生成章节."""
    config_mgr = get_config_manager()
    logger = logging.getLogger(__name__)

    if not config_mgr.current_project:
        print("❌ 未设置当前项目. 请先使用 --new 创建项目")
        return 1

    llm_client, doubao_client = _build_llm_clients(config_mgr)
    if llm_client is None:
        logger.warning(
            "No configured text LLM client available, generation will rely on fallbacks"
        )

    project = config_mgr.current_project
    project_id = project.id
    project_dir = _project_dir(config_mgr)
    project_dir.mkdir(parents=True, exist_ok=True)
    command = sys.argv[1:]
    generation_run_id = getattr(args, "run_id", None) or str(uuid.uuid4())
    run_started_at = datetime.now()
    run_dir = _initialize_telemetry_run(
        _telemetry_run_dir(args, project_dir),
        run_id=generation_run_id,
        project_id=project_id,
        command=command,
    )
    status_payload = read_status(run_dir) if run_dir else {}
    queued_volume_guidance_payload = normalize_volume_guidance_payload(
        status_payload.get("queued_volume_guidance_payload")
    )

    # 使用标题目录而非ID目录
    base_dir_override = str(project_dir)
    longform_memory_store = create_longform_memory_store(project_dir=project_dir)
    chapter_mgr = get_chapter_manager(project_id, base_dir_override=base_dir_override)
    chapter_mgr.longform_memory_store = longform_memory_store
    if run_dir:
        update_status(
            run_dir,
            longform_memory_enabled=longform_memory_store is not None,
            longform_memory_store=type(longform_memory_store).__name__
            if longform_memory_store is not None
            else None,
        )

    # 创建 orchestrator（小说主线模式）
    novel_orchestrator = _create_orchestrator(config_mgr, project_id)
    input_assembler = InputAssembler(config_mgr)

    # 创建小说生成器（传入 orchestrator 以启用主线编排）
    generator = get_novel_generator(
        config_manager=config_mgr,
        novel_orchestrator=novel_orchestrator,
        llm_client=llm_client,
        allow_fallback=not getattr(args, "require_llm", False),
    )

    # 断点续传只信任实际章节落盘；generation_results.json 仅作为审计/检查点展示
    results_file = _build_results_file(project_dir)
    existing_results = None
    chapters_to_skip = discover_saved_chapter_numbers(project_dir)
    checkpoints = []
    if results_file.exists():
        with open(results_file) as f:
            existing_results = json.load(f)
        checkpoints = existing_results.get("checkpoints", [])
    if chapters_to_skip:
        checkpoints = sorted(set(checkpoints).union(chapters_to_skip))

    # 处理 --continue-from 断点续传；启动前先用磁盘章节回写进度，避免陈旧 watermark 影响起点
    continue_from = getattr(args, "continue_from", None)
    reconciled_current_chapter = max(chapters_to_skip) if chapters_to_skip else 0
    if getattr(config_mgr, "current_project", None) is not None:
        config_mgr.current_project.current_chapter = reconciled_current_chapter
    if hasattr(config_mgr, "update_project_progress"):
        config_mgr.update_project_progress(reconciled_current_chapter)
    worklist = _build_generation_worklist(
        explicit_start=args.start,
        continue_from=continue_from,
        count=args.count,
        saved_chapters=chapters_to_skip,
    )
    start = worklist[0] if worklist else (args.start or reconciled_current_chapter + 1)
    count = args.count
    dry_run = getattr(args, "dry_run", False)
    mode = "incremental" if continue_from is not None else "full"
    active_writing_options = _resolve_active_writing_options(config_mgr, args)

    if continue_from is not None:
        start = continue_from
        print(f"\n🔄 断点续传模式: 从第 {continue_from} 章继续")
        print(f"   已成功章节: {sorted(chapters_to_skip)}")
        print(f"   已有检查点: {checkpoints}")
    else:
        print(f"\n🚀 开始生成 {count} 章...")
        print(f"   起始章节: {start}")
        if args.start is None and worklist:
            print(f"   计划章节: {worklist}")
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
        for ch_num in worklist:
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

    generated = []
    failed_chapters = []
    previous_summary = ""
    last_failed_stage: str | None = None
    skipped_existing = 0
    for chapter_num in worklist:

        # 跳过已成功的章节（断点续传时）
        if chapter_num in chapters_to_skip:
            print(f"\n📝 第 {chapter_num} 章已存在，跳过")
            skipped_existing += 1
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
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
            )

            # 构建上下文
            context = chapter_mgr.build_context(chapter_num)
            original_context = context
            if any(queued_volume_guidance_payload.values()):
                context["volume_guidance_payload"] = queued_volume_guidance_payload
            volume_guidance = str(getattr(args, "volume_guidance", "") or "").strip()
            if volume_guidance:
                context["volume_guidance"] = volume_guidance
            chapter_guidance = str(getattr(args, "chapter_guidance", "") or "").strip()
            chapter_guidance_target = getattr(args, "chapter_guidance_target", None)
            if (
                chapter_guidance
                and chapter_guidance_target is not None
                and int(chapter_guidance_target) == chapter_num
            ):
                context["chapter_guidance"] = chapter_guidance
            enriched_context = input_assembler.enrich_context(
                chapter_number=chapter_num,
                base_context=context,
                writing_options=active_writing_options,
                chapter_guidance_target=int(chapter_guidance_target)
                if chapter_guidance_target is not None
                else None,
            )
            if isinstance(original_context, dict):
                original_context.clear()
                original_context.update(enriched_context)
                context = original_context
            else:
                context = enriched_context
            validation = dict(context.get("story_input_validation", {}) or {})
            if validation.get("blocking_issues"):
                raise GenerationError(
                    "结构化输入校验失败: "
                    + "；".join(str(item) for item in validation["blocking_issues"])
                )

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
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
            )
            chapter = generator.generate_chapter(
                chapter_number=chapter_num,
                context=context,
                previous_summary=previous_summary,
                writing_options=active_writing_options,
            )
            if hasattr(chapter, "consistency_report") and chapter.consistency_report:
                chapter_mgr.save_consistency_report(
                    chapter_number=chapter.number,
                    report=chapter.consistency_report,
                    rewrite_history=chapter.metadata.get("rewrite_history", []),
                )
            if getattr(chapter, "consistency_report", {}).get("invalid"):
                status_payload = read_status(run_dir) if run_dir else {}
                longform_state_path = status_payload.get("longform_state_path")
                if run_dir and longform_state_path:
                    longform_state = load_longform_state(longform_state_path)
                    if longform_state:
                        print(f"   ⏸️ 第 {chapter_num} 章未通过质量闸门，已暂停等待决策")
                    _pause_for_invalid_chapter(
                        run_dir=run_dir,
                        state=longform_state,
                        project_id=project_id,
                        command=command,
                        run_started_at=run_started_at,
                        chapter=chapter,
                    )
                    return 1
                raise GenerationError(
                    _format_quality_gate_failure(chapter.consistency_report)
                )

            # 计算内容校验和
            content_checksum = hashlib.sha256(
                chapter.content.encode("utf-8")
            ).hexdigest()[:16]

            # 获取实际摘要（优先使用生成后的情节摘要，而非生成前的大纲）
            actual_summary = ""
            if hasattr(chapter, "plot_summary") and chapter.plot_summary:
                actual_summary = chapter.plot_summary.get("l2_brief_summary", "")
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
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
            )
            chapter_save_result = chapter_mgr.save_chapter(
                number=chapter.number,
                title=chapter.title,
                content=chapter.content,
                word_count=chapter.word_count,
                summary=actual_summary,
                key_events=chapter.metadata.get("key_events", []),
                character_appearances=chapter.metadata.get("character_appearances", []),
                generation_time=chapter.generation_time,
            )
            chapter_artifact_path = getattr(
                getattr(chapter_save_result, "metadata", None), "file_path", ""
            )
            if run_dir:
                status_payload = read_status(run_dir)
                state_path = status_payload.get("longform_state_path")
                longform_state = load_longform_state(state_path) if state_path else {}
                capsule = status_payload.get("next_chapter_experience_capsule")
                if not isinstance(capsule, dict):
                    capsule = (
                        longform_state.get("next_chapter_experience_capsule")
                        if isinstance(longform_state, dict)
                        else {}
                    )
                loaded_ids = (
                    capsule.get("loaded_ids", []) if isinstance(capsule, dict) else []
                )
                if isinstance(loaded_ids, list) and loaded_ids:
                    try:
                        GlobalExperiencePool().record_usage(
                            experience_ids=[str(item) for item in loaded_ids],
                            project_id=project_id,
                            run_id=generation_run_id,
                            stage="chapter.save",
                            chapter_number=chapter.number,
                            outcome="helped",
                        )
                    except Exception as exc:
                        logger.warning("Global experience usage write skipped: %s", exc)
                pending_validation = (
                    longform_state.get("pending_revision_validation")
                    if isinstance(longform_state, dict)
                    else None
                )
                promotion_trace = _promote_captured_experience_after_revision(
                    pending_validation=pending_validation,
                    chapter_number=chapter.number,
                    project_id=project_id,
                    run_id=generation_run_id,
                )
                if (
                    isinstance(longform_state, dict)
                    and isinstance(pending_validation, dict)
                    and int(pending_validation.get("chapter_number") or 0)
                    == int(chapter.number)
                    and not getattr(chapter, "consistency_report", {}).get("invalid")
                ):
                    _record_successful_experience_promotion(
                        run_dir=run_dir,
                        longform_state=longform_state,
                        promotion_trace=promotion_trace,
                    )
                    update_status(
                        run_dir,
                        pending_state_path=None,
                        pause_reason=None,
                        chapter_quality_report=None,
                        review_disposition="resolved",
                    )

            # 保存情节概述（三级结构）
            if hasattr(chapter, "plot_summary") and chapter.plot_summary:
                plot_summary_data = chapter.plot_summary
                plot_summary = ChapterPlotSummary(
                    chapter_number=chapter.number,
                    one_line_summary=plot_summary_data.get("l1_one_line_summary", ""),
                    brief_summary=plot_summary_data.get("l2_brief_summary", ""),
                    key_plot_points=plot_summary_data.get("l3_key_plot_points", []),
                    character_states={},
                    plot_threads=[],
                    foreshadowing=[],
                )
                chapter_mgr.save_plot_summary(plot_summary)
                logger.info(f"  📋 Plot summary saved for chapter {chapter.number}")

            if chapter_artifact_path:
                goal_lock = ""
                unresolved_goals = []
                if isinstance(chapter.metadata, dict):
                    goal_lock = str(chapter.metadata.get("goal_lock", "") or "")
                    raw_unresolved = chapter.metadata.get("unresolved_goals", [])
                    if isinstance(raw_unresolved, list):
                        unresolved_goals = [str(item) for item in raw_unresolved if item]
                if not goal_lock and isinstance(context.get("volume_guidance_payload"), dict):
                    goal_lock = str(context["volume_guidance_payload"].get("goal_lock", "") or "")
                try:
                    memory_rows_written = record_memory_after_save(
                        longform_memory_store,
                        project_id=project_id,
                        run_id=generation_run_id,
                        chapter_number=chapter.number,
                        chapter_path=chapter_artifact_path,
                        chapter_content=chapter.content,
                        summary=actual_summary,
                        key_events=chapter.metadata.get("key_events", []),
                        character_appearances=chapter.metadata.get("character_appearances", []),
                        goal_lock=goal_lock,
                        unresolved_goals=unresolved_goals,
                    )
                    if memory_rows_written:
                        logger.info(
                            "  🧠 Longform memory rows written: %s",
                            memory_rows_written,
                        )
                    if run_dir:
                        update_status(
                            run_dir,
                            longform_memory_rows_written=memory_rows_written,
                            longform_memory_error=None,
                        )
                except Exception as exc:
                    logger.warning("Longform memory write skipped: %s", exc)
                    if run_dir:
                        update_status(
                            run_dir,
                            longform_memory_error=str(exc),
                        )

            try:
                story_graph_result = record_story_graph_after_save(
                    project_dir=getattr(chapter_mgr, "novel_dir", project_dir),
                    project_id=project_id,
                    chapter_number=chapter.number,
                    context=context,
                )
                logger.info(
                    "  🕸️ Story graph snapshot saved: %s",
                story_graph_result.get("snapshot_path", ""),
            )
                try:
                    narrative_state_result = record_narrative_state_after_save(
                        project_dir=getattr(chapter_mgr, "novel_dir", project_dir),
                        project_id=project_id,
                        run_id=generation_run_id,
                        chapter_number=chapter.number,
                        story_graph_result=story_graph_result,
                        context=context,
                        chapter_path=chapter_artifact_path,
                        summary=actual_summary,
                        key_events=chapter.metadata.get("key_events", []),
                        character_appearances=chapter.metadata.get(
                            "character_appearances", []
                        ),
                        goal_lock=goal_lock,
                        unresolved_goals=unresolved_goals,
                    )
                    logger.info(
                        " 🧭 Narrative state snapshot saved: %s",
                        narrative_state_result.get("snapshot_path", ""),
                    )
                    if run_dir:
                        update_status(
                            run_dir,
                            narrative_state_path=narrative_state_result.get(
                                "current_path", ""
                            ),
                            narrative_state_snapshot_path=narrative_state_result.get(
                                "snapshot_path", ""
                            ),
                            narrative_state_error=None,
                        )
                except Exception as exc:
                    logger.warning("Narrative state save skipped: %s", exc)
                    if run_dir:
                        update_status(run_dir, narrative_state_error=str(exc))
            except Exception as exc:
                logger.warning("Story graph save skipped: %s", exc)

            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ✅ {chapter.title} ({chapter.word_count} 字, {elapsed:.1f}秒)")

            generated.append(chapter)
            if hasattr(config_mgr, "update_project_progress"):
                config_mgr.update_project_progress(chapter_num)
            elif getattr(config_mgr, "current_project", None) is not None:
                config_mgr.current_project.current_chapter = chapter_num
            # 使用生成后的情节摘要作为下一章的上下文，而非生成前的大纲
            if hasattr(chapter, "plot_summary") and chapter.plot_summary:
                previous_summary = chapter.plot_summary.get(
                    "l2_brief_summary", ""
                ) or chapter.metadata.get("outline_summary", "")
            else:
                previous_summary = chapter.metadata.get("outline_summary", "")

            # 记录成功
            generation_results["successful"] += 1
            generation_results["total_words_generated"] += chapter.word_count
            generation_results["total_time_seconds"] += elapsed
            generation_results["chapter_results"].append(
                {
                    "chapter_number": chapter_num,
                    "status": "success",
                    "title": chapter.title,
                    "word_count": chapter.word_count,
                    "time_seconds": elapsed,
                    "timestamp": datetime.now().isoformat(),
                    "checksum": content_checksum,
                }
            )

            # 保存 checkpoint（每成功一章就保存）
            generation_results["checkpoints"].append(chapter_num)
            _save_checkpoint(results_file, generation_results)
            _save_generation_results(results_file, generation_results)
            print(f"   💾 Checkpoint 已保存 (第 {chapter_num} 章)")
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="running",
                current_stage=STAGE_CHAPTER_SAVE,
                current_step=f"第 {chapter_num} 章已完成",
                chapters_total=count,
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
            )

        except GenerationError as e:
            logger.error(f"Chapter {chapter_num} generation failed: {e}")
            print(f"   ❌ 生成失败: {e}")
            error_message = str(e)
            _record_chapter_generation_failure(
                generation_results,
                failed_chapters,
                chapter_num=chapter_num,
                error_message=error_message,
                elapsed=(datetime.now() - start_time).total_seconds(),
            )
            last_failed_stage = current_stage
            if _stop_controlled_run_after_chapter_failure(
                run_dir,
                results_file=results_file,
                generation_results=generation_results,
                project_id=project_id,
                command=command,
                current_stage=current_stage,
                chapter_num=chapter_num,
                count=count,
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
                error_message=error_message,
            ):
                return 1
            continue  # 继续处理其他章节

        except Exception as e:
            # 其他异常也包装为 GenerationError 继续处理
            logger.error(f"Chapter {chapter_num} generation failed (unexpected): {e}")
            print(f"   ❌ 生成失败: {e}")
            error_message = str(e)
            _record_chapter_generation_failure(
                generation_results,
                failed_chapters,
                chapter_num=chapter_num,
                error_message=error_message,
                elapsed=(datetime.now() - start_time).total_seconds(),
            )
            last_failed_stage = current_stage
            if _stop_controlled_run_after_chapter_failure(
                run_dir,
                results_file=results_file,
                generation_results=generation_results,
                project_id=project_id,
                command=command,
                current_stage=current_stage,
                chapter_num=chapter_num,
                count=count,
                chapters_completed=skipped_existing + len(generated),
                run_started_at=run_started_at,
                error_message=error_message,
            ):
                return 1
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
        chapters_completed=skipped_existing + len(generated),
        run_started_at=run_started_at,
    )
    final_saved_chapters = discover_saved_chapter_numbers(project_dir)
    final_chapter_numbers = set(final_saved_chapters).union(
        chapter.number for chapter in generated
    )
    final_current_chapter = max(final_chapter_numbers) if final_chapter_numbers else 0
    if getattr(config_mgr, "current_project", None) is not None:
        config_mgr.current_project.current_chapter = final_current_chapter
    if hasattr(config_mgr, "update_project_progress"):
        config_mgr.update_project_progress(final_current_chapter)

    generation_results["completed_at"] = datetime.now().isoformat()
    final_results = _save_generation_results(results_file, generation_results)

    print("\n" + "=" * 50)
    _print_statistics(final_results, failed_chapters, results_file, project.title)

    no_auto_feedback = getattr(args, "no_auto_feedback", False)
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
            chapters_completed=skipped_existing + len(generated),
            run_started_at=run_started_at,
        )
        _run_auto_feedback(
            project_id,
            generated,
            current_total,
            llm_client=llm_client,
            project_dir=project_dir,
        )

    if failed_chapters:
        _update_run_progress(
            run_dir,
            project_id=project_id,
            command=command,
            status="failed",
            current_stage=STAGE_FINALIZE,
            current_step=f"任务结束，但有 {len(failed_chapters)} 章失败",
            chapters_total=count,
            chapters_completed=skipped_existing + len(generated),
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
        chapters_completed=skipped_existing + len(generated),
        run_started_at=run_started_at,
        finished_at=datetime.now().isoformat(),
        return_code=0,
    )
    return 0


def _record_chapter_generation_failure(
    generation_results: dict[str, Any],
    failed_chapters: list[int],
    *,
    chapter_num: int,
    error_message: str,
    elapsed: float,
) -> None:
    failed_chapters.append(chapter_num)
    generation_results["failed"] += 1
    timestamp = datetime.now().isoformat()
    generation_results["failed_chapters"].append(
        {
            "chapter_number": chapter_num,
            "error": error_message,
            "timestamp": timestamp,
        }
    )
    generation_results["chapter_results"].append(
        {
            "chapter_number": chapter_num,
            "status": "failed",
            "error": error_message,
            "time_seconds": elapsed,
            "timestamp": timestamp,
        }
    )


def _stop_controlled_run_after_chapter_failure(
    run_dir: Path | None,
    *,
    results_file: Path,
    generation_results: dict[str, Any],
    project_id: str,
    command: list[str],
    current_stage: str,
    chapter_num: int,
    count: int,
    chapters_completed: int,
    run_started_at: datetime,
    error_message: str,
) -> bool:
    if run_dir is None:
        return False

    _save_checkpoint(results_file, generation_results)
    _save_generation_results(results_file, generation_results)
    _update_run_progress(
        run_dir,
        project_id=project_id,
        command=command,
        status="failed",
        current_stage=current_stage,
        current_step=f"第 {chapter_num} 章失败，已停止本次受控生成",
        chapters_total=count,
        chapters_completed=chapters_completed,
        run_started_at=run_started_at,
        failed_stage=current_stage,
        error_message=error_message,
        finished_at=datetime.now().isoformat(),
        return_code=1,
    )
    return True


def _checkpoint_payload_from_disk(results_file: Path, results: dict) -> dict:
    """Build a project-level checkpoint summary using trusted chapter artifacts."""
    payload = dict(results)
    disk_summary = summarize_saved_chapters(results_file.parent)
    saved_chapters = list(disk_summary.get("saved_chapters", []) or [])
    payload["successful"] = int(disk_summary.get("successful", 0) or 0)
    payload["checkpoints"] = list(disk_summary.get("checkpoints", []) or [])
    payload["total_words_generated"] = int(
        disk_summary.get("total_words_generated", 0) or 0
    )
    payload["saved_chapters"] = saved_chapters
    existing_results = {
        int(item.get("chapter_number", 0) or 0): dict(item)
        for item in payload.get("chapter_results", [])
        if isinstance(item, dict) and int(item.get("chapter_number", 0) or 0) > 0
    }
    chapter_results: list[dict[str, Any]] = []
    for chapter in saved_chapters:
        chapter_number = int(chapter.get("number", 0) or 0)
        if chapter_number <= 0:
            continue
        entry = existing_results.get(chapter_number, {})
        if entry.get("status") != "success":
            entry = {}
        entry.update(
            {
                "chapter_number": chapter_number,
                "status": "success",
                "title": chapter.get("title", ""),
                "word_count": int(chapter.get("word_count", 0) or 0),
                "file_path": chapter.get("file_path", ""),
            }
        )
        if chapter.get("created_at") and not entry.get("timestamp"):
            entry["timestamp"] = chapter.get("created_at")
        chapter_results.append(entry)
    saved_numbers = {item["chapter_number"] for item in chapter_results}
    for item in payload.get("chapter_results", []):
        if not isinstance(item, dict):
            continue
        chapter_number = int(item.get("chapter_number", 0) or 0)
        if chapter_number > 0 and chapter_number not in saved_numbers:
            chapter_results.append(dict(item))
    payload["chapter_results"] = sorted(
        chapter_results,
        key=lambda item: int(item.get("chapter_number", 0) or 0),
    )
    attempted_numbers = {
        int(item.get("chapter_number", 0) or 0)
        for item in payload["chapter_results"]
        if isinstance(item, dict) and int(item.get("chapter_number", 0) or 0) > 0
    }
    attempted_count = len(attempted_numbers)
    payload["total_attempted"] = max(
        int(payload.get("total_attempted", 0) or 0),
        attempted_count,
    )
    return payload


def _save_checkpoint(results_file: Path, results: dict) -> None:
    """保存 checkpoint 到文件."""
    checkpoint_file = results_file.parent / "generation_checkpoint.json"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    payload = _checkpoint_payload_from_disk(results_file, results)
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _save_generation_results(results_file: Path, results: dict) -> dict:
    """Persist the command result summary and return the normalized payload."""
    results_file.parent.mkdir(parents=True, exist_ok=True)
    payload = _checkpoint_payload_from_disk(results_file, results)
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def _chapter_numbers_from_files(project_dir: Path, pattern: str) -> list[int]:
    numbers: set[int] = set()
    for path in project_dir.glob(pattern):
        match = re.search(r"ch(\d+)", path.name)
        if match:
            numbers.add(int(match.group(1)))
    return sorted(numbers)


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _increment_counter(counter: dict[str, int], key: str) -> None:
    cleaned = str(key or "unknown").strip() or "unknown"
    counter[cleaned] = counter.get(cleaned, 0) + 1


def _write_memory_audit(
    *,
    run_dir: Path,
    project_dir: Path,
    project_id: str,
    run_id: str,
    state: dict[str, Any],
) -> Path:
    """Write a run-level memory and experience audit from durable artifacts."""
    try:
        status = read_status(run_dir)
    except Exception:
        status = {}

    usage_records: list[dict[str, Any]] = []
    matched_cases: list[dict[str, Any]] = []
    usage_by_outcome: dict[str, int] = {}
    usage_by_stage: dict[str, int] = {}
    experience_dir = ""
    try:
        pool = GlobalExperiencePool()
        experience_dir = str(pool.root_dir)
        for case in pool.load_cases():
            if case.source_project_id == project_id or case.run_id == run_id:
                matched_cases.append(
                    {
                        "id": case.id,
                        "status": case.status,
                        "experience_kind": case.experience_kind,
                        "stage": case.stage,
                        "chapter_number": case.chapter_number,
                        "issue_types": list(case.issue_types),
                        "usage_count": case.usage_count,
                        "helped_count": case.helped_count,
                        "hurt_count": case.hurt_count,
                    }
                )
        if pool.usage_path.exists():
            for line in pool.usage_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("project_id") != project_id and payload.get("run_id") != run_id:
                    continue
                _increment_counter(usage_by_outcome, str(payload.get("outcome") or ""))
                _increment_counter(usage_by_stage, str(payload.get("stage") or ""))
                usage_records.append(
                    {
                        "created_at": payload.get("created_at"),
                        "experience_ids": payload.get("experience_ids", []),
                        "stage": payload.get("stage"),
                        "chapter_number": payload.get("chapter_number"),
                        "outcome": payload.get("outcome"),
                    }
                )
    except Exception as exc:
        usage_records.append({"error": str(exc)})

    chapter_numbers = _chapter_numbers_from_files(project_dir, "chapters/ch*.md")
    consistency_numbers = _chapter_numbers_from_files(
        project_dir, "consistency_reports/ch*_consistency.json"
    )
    plot_summary_numbers = _chapter_numbers_from_files(
        project_dir, "plot_summaries/ch*_summary.json"
    )
    narrative_numbers = _chapter_numbers_from_files(
        project_dir, "narrative_state/snapshots/ch*.json"
    )
    story_graph_snapshot_numbers = _chapter_numbers_from_files(
        project_dir, "story_graph/snapshots/ch*.json"
    )

    audit = {
        "schema_version": "young_writer.memory_audit.v1",
        "generated_at": datetime.now().isoformat(),
        "project_id": project_id,
        "run_id": run_id,
        "chapters": {
            "total_chapters": int(state.get("total_chapters", 0) or 0),
            "chapters_completed": int(state.get("chapters_completed", 0) or 0),
            "chapters_completed_high_watermark": int(
                state.get("chapters_completed_high_watermark", 0) or 0
            ),
            "chapter_files_count": len(chapter_numbers),
            "chapter_files_first": chapter_numbers[:5],
            "chapter_files_last": chapter_numbers[-5:],
        },
        "experience_pool": {
            "experience_dir": experience_dir,
            "matched_cases_count": len(matched_cases),
            "matched_cases": matched_cases[-50:],
            "matched_usage_count": len(usage_records),
            "usage_by_outcome": usage_by_outcome,
            "usage_by_stage": usage_by_stage,
            "usage_records": usage_records[-100:],
        },
        "memory_layers": {
            "longform_memory": {
                "enabled": bool(status.get("longform_memory_enabled")),
                "store": status.get("longform_memory_store"),
                "last_rows_written": status.get("longform_memory_rows_written"),
                "error": status.get("longform_memory_error"),
            },
            "plot_summaries": {
                "count": len(plot_summary_numbers),
                "first": plot_summary_numbers[:5],
                "last": plot_summary_numbers[-5:],
            },
            "consistency_reports": {
                "count": len(consistency_numbers),
                "first": consistency_numbers[:5],
                "last": consistency_numbers[-5:],
            },
            "story_graph": {
                "snapshot_count": len(story_graph_snapshot_numbers),
                "event_count": _count_jsonl_lines(
                    project_dir / "story_graph" / "graph_events.jsonl"
                ),
                "first": story_graph_snapshot_numbers[:5],
                "last": story_graph_snapshot_numbers[-5:],
            },
            "narrative_state": {
                "snapshot_count": len(narrative_numbers),
                "event_count": _count_jsonl_lines(
                    project_dir / "narrative_state" / "events.jsonl"
                ),
                "current_path": status.get("narrative_state_path"),
                "latest_snapshot_path": status.get("narrative_state_snapshot_path"),
                "error": status.get("narrative_state_error"),
                "first": narrative_numbers[:5],
                "last": narrative_numbers[-5:],
            },
        },
    }
    audit_path = run_dir / "memory_audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return audit_path


def _print_statistics(
    results: dict, failed_chapters: list, results_file: Path, project_title: str
) -> None:
    """打印生成统计信息."""
    total_words = results.get("total_words_generated", 0)
    total_time = results.get("total_time_seconds", 0.0)
    speed = total_words / total_time if total_time > 0 else 0
    chapters_dir = results_file.parent / "chapters"
    checkpoint_file = results_file.parent / "generation_checkpoint.json"

    print(f"""
📊 生成统计:
   成功: {results.get("successful", 0)} 章
   失败: {results.get("failed", 0)} 章
   总字数: {total_words:,} 字
   总耗时: {total_time:.1f} 秒
   平均速度: {speed:.0f} 字/秒
   检查点: {len(results.get("checkpoints", []))} 个
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
    print(
        "   进度: 成功 "
        f"{summary.get('successful_chapter_count', 0)}/{summary.get('total_chapters')} 章"
    )
    print(
        "   连续完成: 第 "
        f"{summary.get('contiguous_completed_chapter', 0)} 章"
    )
    print(
        "   最高到达: 第 "
        f"{summary.get('high_watermark_chapter', summary.get('current_chapter', 0))} 章"
    )
    print(f"   完成度: {summary.get('progress_percent')}%")
    failed_chapters = summary.get("failed_chapters") or []
    if failed_chapters:
        print(f"   失败章节: {', '.join(str(item) for item in failed_chapters)}")
    writing_options = normalize_writing_options(
        summary.get("metadata", {}).get("writing_options", {})
    )
    print(
        f"   写作参数: {', '.join(f'{k}={v}' for k, v in writing_options.items() if v)}"
    )

    return 0


def cmd_list_chapters(args):
    """列出章节."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 使用标题目录而非ID目录
    output_dir = getattr(config_mgr.generation, "output_dir", None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(
        config_mgr.current_project.id, base_dir_override=base_dir_override
    )
    chapters = chapter_mgr.get_chapter_list()

    if not chapters:
        print("📭 暂无章节")
        return 0

    stats = chapter_mgr.get_stats()
    print(f"\n📚 章节列表 (共 {stats['total_chapters']} 章, {stats['total_words']} 字)")
    print("-" * 70)

    for ch in chapters:
        print(
            f"   {ch.number:03d}. {ch.title:<20} | {ch.word_count:>5} 字 | {ch.created_at.strftime('%m-%d %H:%M')}"
        )

    return 0


def cmd_export(args):
    """导出为文本."""
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ 未设置当前项目")
        return 1

    # 使用标题目录而非ID目录
    output_dir = getattr(config_mgr.generation, "output_dir", None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(
        config_mgr.current_project.id, base_dir_override=base_dir_override
    )

    # 导出到标题目录
    if output_dir:
        base_path = Path(output_dir).resolve()
    else:
        workspace_paths = WorkspacePaths.from_root(KNOWLEDGE_BASE_DIR)
        base_path = workspace_paths.project_paths(
            title=config_mgr.current_project.title,
            project_id=config_mgr.current_project.id,
        ).project_dir
    output_path = args.output or str(
        base_path / f"{config_mgr.current_project.title}.txt"
    )

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
    output_dir = getattr(config_mgr.generation, "output_dir", None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    chapter_mgr = get_chapter_manager(
        config_mgr.current_project.id, base_dir_override=base_dir_override
    )

    # 执行完整性检查
    declared_latest = config_mgr.current_project.current_chapter
    result = chapter_mgr.verify_project_integrity(declared_latest)

    # 打印结果
    print("\n📊 完整性检查结果:")
    print(f"   状态: {'✅ 通过' if result['valid'] else '❌ 存在问题'}")

    stats = result.get("stats", {})
    print("\n📈 统计信息:")
    print(f"   章节总数: {stats.get('total_chapters', 0)}")
    print(f"   实际最新: 第{stats.get('actual_latest', 0)}章")
    print(f"   声明最新: 第{stats.get('declared_latest', 0)}章")
    print(f"   磁盘文件: {stats.get('files_on_disk', 0)}")
    print(f"   索引条目: {stats.get('indexed_chapters', 0)}")

    # 打印问题
    if result.get("issues"):
        print(f"\n❌ 问题列表 ({len(result['issues'])} 个):")
        for issue in result["issues"]:
            print(f"   - [{issue['type']}] {issue['message']}")

    # 打印警告
    if result.get("warnings"):
        print(f"\n⚠️  警告列表 ({len(result['warnings'])} 个):")
        for warning in result["warnings"]:
            print(f"   - {warning}")

    # 执行章节连续性检查
    seq_result = chapter_mgr.validate_chapter_sequence()
    print("\n📚 章节序列检查:")
    print(f"   状态: {'✅ 连续' if seq_result['valid'] else '❌ 不连续'}")
    seq_stats = seq_result.get("stats", {})
    print(
        f"   范围内章节: {seq_stats.get('existing_count', 0)}/{seq_stats.get('total_in_range', 0)}"
    )
    print(f"   缺失章节: {seq_stats.get('missing_count', 0)}")
    print(f"   跳跃次数: {seq_stats.get('gap_count', 0)}")

    if seq_result.get("gaps"):
        print("\n   跳跃详情:")
        for gap in seq_result["gaps"]:
            print(
                f"     - 第{gap['from_chapter']}章 → 第{gap['to_chapter']}章 (缺失 {gap['gap_size']} 章)"
            )

    # 返回状态
    if result["valid"] and seq_result["valid"]:
        print("\n✅ 项目验证通过!")
        return 0
    print("\n⚠️ 项目验证发现问题，请检查上述信息")
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
    from young_writer.agents.feedback_loop import (
        FeedbackMode,
        FeedbackStrategy,
        get_feedback_loop,
    )

    llm_client, _ = _build_llm_clients(config_mgr)

    print("\n🔄 反馈循环")
    print(f"   项目: {config_mgr.current_project.title}")
    print(f"   项目ID: {project_id}")
    print("-" * 50)

    # 初始化反馈循环
    try:
        feedback = get_feedback_loop(
            project_id, llm_client=llm_client, project_dir=_project_dir(config_mgr)
        )
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
        if "final_status" in result:
            # FULL模式 (run_full_cycle结构)
            print("   模式: full")
            print(f"   状态: {result['final_status']}")
            print(f"   迭代次数: {len(result.get('iterations', []))}")
            print(f"   开始时间: {result.get('start_time', 'N/A')}")
            print(f"   结束时间: {result.get('end_time', 'N/A')}")

            # 显示每次迭代的结果摘要
            for i, iteration in enumerate(result.get("iterations", [])):
                phase = iteration.get("phase", "unknown")
                phase_result = iteration.get("result", {})
                if phase == "discovery":
                    issues_count = phase_result.get("issues_found", 0)
                    needs_fix = phase_result.get("needs_fix", False)
                    print(f"\n   迭代 {i + 1} - {phase.upper()}:")
                    print(f"      发现问题: {issues_count} 个")
                    print(f"      需要修复: {'是' if needs_fix else '否'}")
                elif phase == "fix":
                    summary = phase_result.get("summary", {})
                    print(f"\n   迭代 {i + 1} - {phase.upper()}:")
                    print(f"      总计: {summary.get('total', 0)}")
                    print(f"      成功: {summary.get('success', 0)}")
                    print(f"      失败: {summary.get('failed', 0)}")
                elif phase == "verification":
                    print(f"\n   迭代 {i + 1} - {phase.upper()}:")
                    print(
                        f"      验证通过: {'是' if phase_result.get('verification_passed') else '否'}"
                    )
                    checks = phase_result.get("checks", {})
                    for check_name, check_result in checks.items():
                        print(f"      - {check_name}: {'✅' if check_result else '❌'}")
        elif "mode" in result:
            # LIGHT/DEEP/MILESTONE 模式
            mode_str = result.get("mode", "unknown")
            status_str = result.get("status", "unknown")
            print(f"   模式: {mode_str}")
            print(f"   状态: {status_str}")

            if mode_str == "light" and status_str == "passed":
                print(f"   消息: {result.get('message', 'No critical issues found')}")
            else:
                # 显示子阶段结果
                for sub_key in ["discovery", "analysis", "fix"]:
                    if sub_key in result:
                        sub_result = result[sub_key]
                        if sub_key == "discovery":
                            print(f"\n   {sub_key.upper()}:")
                            print(
                                f"      发现问题: {sub_result.get('issues_found', 0)} 个"
                            )
                            print(
                                f"      需要修复: {'是' if sub_result.get('needs_fix') else '否'}"
                            )
                        elif sub_key == "fix":
                            summary = sub_result.get("summary", {})
                            print(f"\n   {sub_key.upper()}:")
                            print(f"      总计: {summary.get('total', 0)}")
                            print(f"      成功: {summary.get('success', 0)}")
                            print(f"      失败: {summary.get('failed', 0)}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        # 根据模式确定返回状态
        if "final_status" in result:
            return 0 if result["final_status"] == "passed" else 1
        if "status" in result:
            return 0 if result["status"] == "passed" else 1
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

        severity_summary = result.get("severity_summary", {})
        for sev, count in severity_summary.items():
            if count > 0:
                emoji = (
                    "🔴"
                    if "P0" in sev
                    else ("🟠" if "P1" in sev else ("🟡" if "P2" in sev else "⚪"))
                )
                print(f"      {emoji} {sev}: {count} 个")

        print(f"\n   需要修复: {'是 ❌' if result['needs_fix'] else '否 ✅'}")

        if result["issues"]:
            print("\n📋 问题列表:")
            for issue in result["issues"][:10]:  # 只显示前10个
                sev = issue.get("severity", "")
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

        for issue_id, analysis in result["analyses"].items():
            print(f"\n   问题 {issue_id}:")
            print(f"      根本原因: {analysis.get('root_cause', '分析中...')[:100]}...")
            print(f"      影响范围: {', '.join(analysis.get('impact_scope', [])[:3])}")
            options = analysis.get("options", [])
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

        summary = result.get("summary", {})
        print(f"\n   总计: {summary.get('total', 0)}")
        print(f"   成功: {summary.get('success', 0)} ✅")
        print(f"   失败: {summary.get('failed', 0)} ❌")

        for fix_result in result.get("fix_results", []):
            status_emoji = "✅" if fix_result["success"] else "❌"
            print(f"\n   {status_emoji} [{fix_result['issue_id']}]")
            print(f"      操作: {fix_result['fix_description'][:80]}...")
            if fix_result.get("files_modified"):
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

        checks = result.get("checks", {})
        for check_name, check_result in checks.items():
            status_emoji = "✅" if check_result else "❌"
            print(f"   {status_emoji} {check_name}")

        summary = result.get("summary", {})
        print("\n   问题统计:")
        print(f"      总计: {summary.get('total_issues', 0)}")
        print(f"      已修复: {summary.get('fixed', 0)}")
        print(f"      待处理: {summary.get('open', 0)}")

        if result.get("open_issues"):
            print("\n   待处理问题:")
            for issue in result["open_issues"][:5]:
                print(f"      - [{issue.get('severity')}] {issue.get('title')}")

        # 保存报告
        report_path = feedback.export_report()
        print(f"\n📄 报告已保存: {report_path}")

        return 0 if result["verification_passed"] else 1

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
            "perspective": getattr(
                args, "perspective", DEFAULT_WRITING_OPTIONS["perspective"]
            ),
            "narrative_mode": getattr(
                args, "narrative_mode", DEFAULT_WRITING_OPTIONS["narrative_mode"]
            ),
            "pace": getattr(args, "pace", DEFAULT_WRITING_OPTIONS["pace"]),
            "dialogue_density": getattr(
                args, "dialogue_density", DEFAULT_WRITING_OPTIONS["dialogue_density"]
            ),
            "prose_style": getattr(
                args, "prose_style", DEFAULT_WRITING_OPTIONS["prose_style"]
            ),
            "world_building_density": getattr(
                args,
                "world_building_density",
                DEFAULT_WRITING_OPTIONS["world_building_density"],
            ),
            "emotion_intensity": getattr(
                args, "emotion_intensity", DEFAULT_WRITING_OPTIONS["emotion_intensity"]
            ),
            "combat_style": getattr(
                args, "combat_style", DEFAULT_WRITING_OPTIONS["combat_style"]
            ),
        "hook_strength": getattr(
            args, "hook_strength", DEFAULT_WRITING_OPTIONS["hook_strength"]
        ),
        "humanization_level": getattr(
            args,
            "humanization_level",
            DEFAULT_WRITING_OPTIONS["humanization_level"],
        ),
    }
    )


def _resolve_active_writing_options(config_mgr, args) -> dict:
    """Merge project defaults with current CLI args."""
    project_defaults = {}
    if config_mgr.current_project:
        project_defaults = config_mgr.current_project.metadata.get(
            "writing_options", {}
        )
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


def _ensure_run_tracking(
    project_dir: Path,
    run_id: str,
    project_id: str,
    command: list[str],
    run_dir: Path | None,
) -> Path:
    """Create the run directory and baseline status if they do not exist yet."""
    resolved_run_dir = run_dir or ensure_run_dir(project_dir, run_id)
    if not read_status(resolved_run_dir):
        create_run(
            project_dir=project_dir,
            run_id=run_id,
            project_id=project_id,
            command=command,
        )
    return resolved_run_dir


def _append_writing_options_to_command(cmd: list[str], options: dict[str, str]) -> None:
    append_writing_option_flags(cmd, options)


def _run_volume_generation_subprocess(
    args,
    *,
    project_id: str,
    run_id: str,
    run_dir: Path,
    start: int,
    count: int,
    writing_options: dict[str, str],
    volume_guidance: str = "",
    chapter_guidance: str = "",
    chapter_guidance_target: int | None = None,
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
    if volume_guidance.strip():
        cmd.extend(["--volume-guidance", volume_guidance.strip()])
    if chapter_guidance.strip() and chapter_guidance_target:
        cmd.extend(
            [
                "--chapter-guidance",
                chapter_guidance.strip(),
                "--chapter-guidance-target",
                str(chapter_guidance_target),
            ]
        )
    if getattr(args, "require_llm", False):
        cmd.append("--require-llm")
    _append_writing_options_to_command(cmd, writing_options)
    result = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent), check=False)
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
    state = _reconcile_longform_progress(config_mgr, state)
    export_args = argparse.Namespace(
        output=None,
        start=1,
        end=None,
    )
    cmd_export(export_args)
    state["status"] = "succeeded"
    state["current_stage"] = STAGE_FINALIZE_EXPORT
    state["pending_state_path"] = None
    state["pending_revision_validation"] = None
    state["next_chapter_guidance"] = ""
    state["next_chapter_guidance_chapter"] = None
    state["next_chapter_experience_capsule"] = {}
    state["global_experience_trace"] = None
    state["auto_repair_status"] = None
    state["repair_exhausted_reason"] = None
    save_longform_state(run_dir, state)
    _sync_status_longform_fields(run_dir, state)
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
    update_status(
        run_dir,
        pending_state_path=None,
        pause_reason=None,
        chapter_quality_report=None,
        review_disposition=None,
        next_chapter_experience_capsule=None,
        global_experience_trace=None,
        repair_exhausted_reason=None,
        auto_repair_status=None,
        error_message=None,
        failed_stage=None,
    )
    try:
        audit_path = _write_memory_audit(
            run_dir=run_dir,
            project_dir=_project_dir(config_mgr),
            project_id=project_id,
            run_id=str(state.get("run_id") or run_dir.name),
            state=state,
        )
        update_status(run_dir, memory_audit_path=str(audit_path))
    except Exception as exc:
        logging.getLogger(__name__).warning("Memory audit export skipped: %s", exc)
    return 0


def _pause_for_volume_review(
    *,
    run_dir: Path,
    state: dict[str, Any],
    project_id: str,
    command: list[str],
    run_started_at: datetime,
) -> int:
    current_volume = int(state.get("current_volume", 0))
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
        risk_report_path=None,
    )
    _sync_status_longform_fields(run_dir, paused_state)
    return 0


def _continue_longform_run(
    args, *, state: dict[str, Any], run_dir: Path, run_started_at: datetime
) -> int:
    config_mgr = get_config_manager()
    project = config_mgr.current_project
    if not project:
        print("❌ 未设置当前项目. 请先使用 --load 或 --new")
        return 1

    project_id = project.id
    command = sys.argv[1:]
    writing_options = _resolve_active_writing_options(config_mgr, args)

    while True:
        state = _reconcile_longform_progress(config_mgr, state)
        volume_guidance = str(state.get("next_volume_guidance", "") or "").strip()
        registry_guidance = format_longform_registry(state.get("cross_volume_registry"))
        if registry_guidance:
            volume_guidance = "\n".join(
                part
                for part in [registry_guidance, volume_guidance]
                if str(part).strip()
            ).strip()
        chapter_guidance = str(state.get("next_chapter_guidance", "") or "").strip()
        chapter_guidance_target = state.get("next_chapter_guidance_chapter")
        pending_validation = (
            state.get("pending_revision_validation")
            if isinstance(state.get("pending_revision_validation"), dict)
            else None
        )
        if pending_validation:
            validation_target = int(pending_validation.get("chapter_number") or 0)
            max_attempts = max(
                int(state.get("chapter_auto_repair_attempts", 0) or 0), 0
            )
            used_attempts = _chapter_auto_repair_count(state, validation_target)
            if validation_target > 0 and used_attempts >= max_attempts:
                return _pause_for_revision_validation_failure(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                    chapter_number=validation_target,
                    issue_types=[
                        str(item).strip()
                        for item in pending_validation.get("issue_types", [])
                        if str(item).strip()
                    ],
                reason=(
                    f"第 {validation_target} 章自动修复已达上限 "
                    f"{max_attempts} 次，等待人工/代码修复后再继续"
                ),
                command_return=True,
            )

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
        subprocess_count = end_chapter - next_start + 1
        if pending_validation:
            validation_target = int(pending_validation.get("chapter_number") or 0)
            if validation_target != next_start:
                state["status"] = "paused"
                state["current_stage"] = STAGE_CHAPTER_REVIEW
                save_longform_state(run_dir, state)
                _sync_status_longform_fields(run_dir, state)
                _update_run_progress(
                    run_dir,
                    project_id=project_id,
                    command=command,
                    status="paused",
                    current_stage=STAGE_CHAPTER_REVIEW,
                    current_step="修订验证目标与下一章进度不一致",
                    chapters_total=state.get("total_chapters", 0),
                    chapters_completed=state.get("chapters_completed", 0),
                    run_started_at=run_started_at,
                    failed_stage=STAGE_VOLUME_WRITE,
                    error_message=(
                        f"pending_revision_validation targets chapter {validation_target}, "
                        f"but next resumable chapter is {next_start}"
                    ),
                )
                return 1
            subprocess_count = 1
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
            _sync_status_longform_fields(run_dir, state)
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
        _sync_status_longform_fields(run_dir, state)
        return_code = _run_volume_generation_subprocess(
            args,
            project_id=project_id,
            run_id=state["run_id"],
            run_dir=run_dir,
            start=next_start,
            count=subprocess_count,
            writing_options=writing_options,
            volume_guidance=volume_guidance,
            chapter_guidance=chapter_guidance,
            chapter_guidance_target=int(chapter_guidance_target)
            if chapter_guidance_target
            else None,
        )
        if return_code != 0:
            fallback_error = f"第 {current_volume} 卷生成失败"
            error_message = _latest_run_failure_message(run_dir, fallback_error)
            state["status"] = "failed"
            state["failed_stage"] = STAGE_VOLUME_WRITE
            state["error_message"] = error_message
            state["return_code"] = return_code
            save_longform_state(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="failed",
                current_stage=STAGE_VOLUME_WRITE,
                current_step=fallback_error,
                chapters_total=state.get("total_chapters", 0),
                chapters_completed=state.get("chapters_completed", 0),
                run_started_at=run_started_at,
                failed_stage=STAGE_VOLUME_WRITE,
                error_message=error_message,
                finished_at=datetime.now().isoformat(),
                return_code=return_code,
            )
            return return_code

        refreshed_state = load_longform_state(run_dir)
        if refreshed_state and (
            refreshed_state.get("status") == "paused"
            or refreshed_state.get("pending_state_path")
        ):
            state = refreshed_state
            _sync_status_longform_fields(run_dir, state)
            return 0
        refreshed_pending_validation = (
            refreshed_state.get("pending_revision_validation")
            if isinstance(refreshed_state, dict)
            and isinstance(refreshed_state.get("pending_revision_validation"), dict)
            else None
        )
        refreshed_attempt = int(
            (refreshed_pending_validation or {}).get("auto_repair_attempt") or 0
        )
        active_attempt = int((pending_validation or {}).get("auto_repair_attempt") or 0)
        refreshed_target = int(
            (refreshed_pending_validation or {}).get("chapter_number") or 0
        )
        active_target = int((pending_validation or {}).get("chapter_number") or 0)
        if refreshed_pending_validation and (
            not pending_validation
            or (
                refreshed_target == active_target
                and refreshed_attempt > active_attempt
            )
        ):
            state = refreshed_state
            _sync_status_longform_fields(run_dir, state)
            continue

        refreshed_project = config_mgr.load_project(project_id) or project
        if pending_validation:
            validation_target = int(pending_validation.get("chapter_number") or 0)
            original_issue_types = [
                str(item).strip()
                for item in pending_validation.get("issue_types", [])
                if str(item).strip()
            ]
            report = _load_chapter_consistency_report(
                _project_dir(config_mgr),
                validation_target,
            )
            if report is None:
                return _pause_for_revision_validation_failure(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                chapter_number=validation_target,
                issue_types=original_issue_types,
                reason="修订验证失败：缺少或无法读取新的 consistency report。",
                command_return=True,
            )
            current_issue_types = {
                str(item).strip()
                for item in report.get("issue_types", [])
                if str(item).strip()
            }
            remaining_issue_types = [
                item for item in original_issue_types if item in current_issue_types
            ]
            if remaining_issue_types:
                return _pause_for_revision_validation_failure(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                    chapter_number=validation_target,
                    issue_types=remaining_issue_types,
                reason=(
                    "修订验证失败：原阻断问题仍存在 "
                    + "、".join(remaining_issue_types)
                ),
                command_return=True,
            )
            state["chapters_completed"] = max(
                int(getattr(refreshed_project, "current_chapter", 0)),
                int(state.get("chapters_completed", 0)),
            )
            state["pending_revision_validation"] = None
            state["next_chapter_guidance"] = ""
            state["next_chapter_guidance_chapter"] = None
            state["next_chapter_experience_capsule"] = {}
            state["auto_repair_status"] = None
            state["repair_exhausted_reason"] = None
            state["repair_decision"] = None
            state["repair_decision_reason"] = None
            save_longform_state(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
            continue

        state["chapters_completed"] = max(
            int(getattr(refreshed_project, "current_chapter", 0)), end_chapter
        )
        state["next_volume_guidance"] = ""
        state["next_volume_guidance_payload"] = {}
        state["next_chapter_guidance"] = ""
        state["next_chapter_guidance_chapter"] = None
        state["next_chapter_experience_capsule"] = {}

        risk_report = build_volume_risk_report(
            project_dir=_project_dir(config_mgr),
            volume_index=current_volume,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
        )
        if risk_report.get("risk_detected"):
            risk_report = save_risk_report(run_dir, risk_report)
            state["risk_report_path"] = str((run_dir / "risk_report.json").resolve())
            state["current_stage"] = STAGE_RISK_PAUSE
            save_longform_state(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
            paused_state = record_pause(
                run_dir=run_dir,
                longform_state=state,
                checkpoint_type=CHECKPOINT_RISK,
                current_stage=STAGE_RISK_PAUSE,
                review_payload=review_payload_for_risk(risk_report),
            )
            _update_run_progress(
                run_dir,
                project_id=project_id,
                command=command,
                status="paused",
                current_stage=STAGE_RISK_PAUSE,
                current_step=f"第 {current_volume} 卷触发风险复核",
                chapters_total=paused_state.get("total_chapters", 0),
                chapters_completed=paused_state.get("chapters_completed", 0),
                run_started_at=run_started_at,
            )
            update_status(
                run_dir,
                pending_state_path=paused_state.get("pending_state_path"),
                longform_state_path=paused_state.get("longform_state_path"),
                risk_report_path=paused_state.get("risk_report_path"),
                pause_reason=CHECKPOINT_RISK,
            )
            _sync_status_longform_fields(run_dir, paused_state)
            return 0

        state["risk_report_path"] = None
        state["current_stage"] = STAGE_VOLUME_REVIEW
        save_longform_state(run_dir, state)
        _sync_status_longform_fields(run_dir, state)

        if should_pause_for_stage(
            state["approval_mode"], state["auto_approve"], "volume"
        ):
            return _pause_for_volume_review(
                run_dir=run_dir,
                state=state,
                project_id=project_id,
                command=command,
                run_started_at=run_started_at,
            )

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
        _sync_status_longform_fields(run_dir, state)


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
        if getattr(args, "chapter_review_mode", None) is not None:
            state["chapter_review_mode"] = str(
                getattr(args, "chapter_review_mode", None)
                or state.get("chapter_review_mode", "manual")
            )
        if getattr(args, "chapter_auto_repair_attempts", None) is not None:
            state["chapter_auto_repair_attempts"] = _resolve_chapter_auto_repair_attempts(
                getattr(args, "chapter_auto_repair_attempts", None),
                state.get("chapter_auto_repair_attempts", 1),
            )
        save_longform_state(run_dir, state)
        _sync_status_longform_fields(run_dir, state)

        action = getattr(args, "submit_approval", None) or "approve"
        approval_payload = approval_payload_from_input(
            getattr(args, "approval_payload", None)
        )
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
                _sync_status_longform_fields(run_dir, state)
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
            _sync_status_longform_fields(run_dir, state)
            update_status(
                run_dir,
                pending_state_path=None,
                pause_reason=None,
                risk_report_path=None,
            )
            return _continue_longform_run(
                args, state=state, run_dir=run_dir, run_started_at=run_started_at
            )

        if pending_state.get("checkpoint_type") == CHECKPOINT_VOLUME:
            current_volume = int(state.get("current_volume", 0))
            if action == "reject":
                save_longform_state(run_dir, state)
                _sync_status_longform_fields(run_dir, state)
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
            guidance_payload = normalize_volume_guidance_payload(approval_payload)
            registry_payload = normalize_longform_registry(approval_payload)
            freeform_guidance = str(
                approval_payload.get("next_volume_guidance")
                or approval_payload.get("notes")
                or ""
            ).strip()
            structured_guidance = format_volume_guidance(guidance_payload)
            state["next_volume_guidance_payload"] = guidance_payload
            state["next_volume_guidance"] = structured_guidance or freeform_guidance
            if any(key in approval_payload for key in registry_payload):
                state["cross_volume_registry"] = merge_longform_registry(
                    state.get("cross_volume_registry"),
                    approval_payload,
                )
            state["pending_revision_validation"] = None
            state["last_completed_volume"] = current_volume
            state["current_stage"] = STAGE_VOLUME_PLAN
            state = clear_pause(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
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
            _sync_status_longform_fields(run_dir, state)
            update_status(
                run_dir,
                pending_state_path=None,
                pause_reason=None,
                risk_report_path=None,
            )
            return _continue_longform_run(
                args, state=state, run_dir=run_dir, run_started_at=run_started_at
            )

        if pending_state.get("checkpoint_type") == CHECKPOINT_RISK:
            current_volume = int(state.get("current_volume", 0))
            if action == "reject":
                save_longform_state(run_dir, state)
                _sync_status_longform_fields(run_dir, state)
                _update_run_progress(
                    run_dir,
                    project_id=project_id,
                    command=command,
                    status="paused",
                    current_stage=STAGE_RISK_PAUSE,
                    current_step=f"第 {current_volume} 卷风险复核未通过，保持暂停",
                    chapters_total=state.get("total_chapters", 0),
                    chapters_completed=state.get("chapters_completed", 0),
                    run_started_at=run_started_at,
                )
                return 0

            state = clear_pause(run_dir, state)
            state["risk_report_path"] = None
            state["pending_revision_validation"] = None
            state["current_stage"] = STAGE_VOLUME_REVIEW
            save_longform_state(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
            update_status(
                run_dir,
                pending_state_path=None,
                pause_reason=None,
                risk_report_path=None,
            )

            if should_pause_for_stage(
                state["approval_mode"], state["auto_approve"], "volume"
            ):
                return _pause_for_volume_review(
                    run_dir=run_dir,
                    state=state,
                    project_id=project_id,
                    command=command,
                    run_started_at=run_started_at,
                )

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
            _sync_status_longform_fields(run_dir, state)
            update_status(
                run_dir,
                pending_state_path=None,
                pause_reason=None,
                risk_report_path=None,
            )
            return _continue_longform_run(
                args, state=state, run_dir=run_dir, run_started_at=run_started_at
            )

        if pending_state.get("checkpoint_type") == CHECKPOINT_CHAPTER:
            chapter_number = int(
                (pending_state.get("review_payload") or {}).get("chapter_number", 0)
            )
            if action == "reject":
                save_longform_state(run_dir, state)
                _sync_status_longform_fields(run_dir, state)
                _update_run_progress(
                    run_dir,
                    project_id=project_id,
                    command=command,
                    status="paused",
                    current_stage=STAGE_CHAPTER_REVIEW,
                    current_step=f"第 {chapter_number} 章质量复核未通过，保持暂停",
                    chapters_total=state.get("total_chapters", 0),
                    chapters_completed=state.get("chapters_completed", 0),
                    run_started_at=run_started_at,
                )
                return 0

            review_payload = dict((pending_state.get("review_payload") or {}))
            submitted_rewrite_plan = approval_payload.get("chapter_rewrite_plan")
            rewrite_plan = (
                submitted_rewrite_plan
                if isinstance(submitted_rewrite_plan, dict)
                else review_payload.get("rewrite_plan")
            )
            notes = str(approval_payload.get("notes") or "").strip()
            explicit_guidance = str(
                approval_payload.get("chapter_rewrite_guidance") or ""
            ).strip()
            experience_capsule = (
                {}
                if explicit_guidance
                else _load_global_experience_capsule(review_payload)
            )
            experience_notes = format_experience_capsule(experience_capsule)
            combined_notes = "\n".join(
                item for item in (experience_notes, notes) if item
            ).strip()
            guidance = explicit_guidance or compile_chapter_rewrite_guidance(
                rewrite_plan,
                extra_notes=combined_notes,
            )
            state["next_chapter_guidance"] = guidance
            state["next_chapter_guidance_chapter"] = chapter_number or None
            state["next_chapter_experience_capsule"] = experience_capsule
            state["global_experience_trace"] = (
                experience_capsule.get("trace")
                if isinstance(experience_capsule, dict)
                else None
            )
            global_experience_capture = review_payload.get("global_experience_capture")
            global_experience_capture = (
                global_experience_capture
                if isinstance(global_experience_capture, dict)
                else {}
            )
            captured_experience_id = str(
                global_experience_capture.get("case_id") or ""
            ).strip()
            pending_goal_lock = str(
                review_payload.get("goal_lock")
                or review_payload.get("chapter_goal")
                or ""
            ).strip()
            state["pending_revision_validation"] = {
                "chapter_number": chapter_number,
                "issue_types": [
                    str(item).strip()
                    for item in review_payload.get("issue_types", [])
                    if str(item).strip()
                ],
                "success_criteria": list(
                    (rewrite_plan or {}).get("success_criteria", [])
                    if isinstance(rewrite_plan, dict)
                    else []
                ),
                "created_from_checkpoint": CHECKPOINT_CHAPTER,
                "captured_experience_id": captured_experience_id or None,
                "captured_issue_types": [
                    str(item).strip()
                    for item in review_payload.get("issue_types", [])
                    if str(item).strip()
                ],
                "promotion_candidate": bool(captured_experience_id),
            }
            if pending_goal_lock:
                state["pending_revision_validation"]["goal_lock"] = pending_goal_lock
            state["auto_repair_status"] = None
            state["repair_exhausted_reason"] = None
            state["graph_recommended_action"] = str(
                review_payload.get("graph_recommended_action")
                or dict(review_payload.get("graph_diff_details", {}) or {}).get(
                    "recommended_action", ""
                )
                or ""
            ).strip() or None
            state = clear_pause(run_dir, state)
            state["current_stage"] = STAGE_VOLUME_PLAN
            save_longform_state(run_dir, state)
            _sync_status_longform_fields(run_dir, state)
            update_status(
                run_dir,
                pending_state_path=None,
                pause_reason=None,
                risk_report_path=None,
                chapter_quality_report=None,
            )
            return _continue_longform_run(
                args, state=state, run_dir=run_dir, run_started_at=run_started_at
            )

        print("❌ 不支持的审批检查点")
        return 1

    state = initial_longform_state(
        project=project,
        run_id=run_id,
        run_dir=run_dir,
        chapters_per_volume=max(
            int(
                getattr(
                    args,
                    "chapters_per_volume",
                    config_mgr.generation.chapters_per_volume,
                )
            ),
            1,
        ),
        approval_mode=getattr(args, "approval_mode", "outline+volume"),
        auto_approve=bool(getattr(args, "auto_approve", False)),
        chapter_review_mode=str(
            getattr(args, "chapter_review_mode", None) or "manual"
        ),
        chapter_auto_repair_attempts=_resolve_chapter_auto_repair_attempts(
            getattr(args, "chapter_auto_repair_attempts", None),
            1,
        ),
    )
    _sync_status_longform_fields(run_dir, state)
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
    _sync_status_longform_fields(run_dir, state)

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
        _sync_status_longform_fields(run_dir, paused_state)
        return 0

    state["approved_outline"] = True
    state["outline_snapshot"] = review_payload_for_outline(project)
    save_longform_state(run_dir, state)
    _sync_status_longform_fields(run_dir, state)
    return _continue_longform_run(
        args, state=state, run_dir=run_dir, run_started_at=run_started_at
    )


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

  # # 反馈循环 (发现问题→分析问题→修改错误)
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
    parser.add_argument(
        "--asset-file",
        help="导入包含 outline/world_setting/characters 的项目资产 JSON",
    )
    parser.add_argument("--outline-file", help="导入结构化大纲 JSON")
    parser.add_argument("--world-file", help="导入结构化世界观 JSON")
    parser.add_argument("--characters-file", help="导入结构化角色 JSON 数组")
    parser.add_argument("--author", default="AI Author", help="作者名")
    parser.add_argument("--chapters", type=int, default=100, help="计划章节数")
    parser.add_argument("--load", metavar="PROJECT_ID", help="加载已有项目")

    # 生成命令
    parser.add_argument("--generate", type=int, metavar="COUNT", help="生成章节数量")
    parser.add_argument(
        "--generate-full",
        action="store_true",
        help="按整本长篇流程生成并在大纲/分卷节点暂停审批",
    )
    parser.add_argument("--start", type=int, help="起始章节号")
    parser.add_argument("--run-id", help="运行任务ID（用于写入任务状态）")
    parser.add_argument("--run-dir", help="运行任务目录（用于写入 status.json 和日志）")
    parser.add_argument(
        "--chapters-per-volume", type=int, default=60, help="长篇模式每卷章节数"
    )
    parser.add_argument(
        "--approval-mode",
        choices=["outline+volume", "outline", "volume", "none"],
        default="outline+volume",
        help="长篇模式的人审节点",
    )
    parser.add_argument(
        "--auto-approve", action="store_true", help="长篇模式自动跳过所有审批节点"
    )
    parser.add_argument(
        "--chapter-review-mode",
        choices=["manual", "auto"],
        default=None,
        help="章节质量复核模式；auto 仅对 recommended_action 可证明的安全分支自动修复",
    )
    parser.add_argument(
        "--chapter-auto-repair-attempts",
        type=int,
        default=None,
        help="章节自动修复的最大附加尝试次数（仅在 --chapter-review-mode auto 下生效）",
    )
    parser.add_argument(
        "--resume-state", help="恢复长篇运行时使用的 pending state 文件"
    )
    parser.add_argument(
        "--submit-approval",
        choices=["approve", "revise", "reject"],
        help="提交对 pending state 的审批动作",
    )
    parser.add_argument(
        "--approval-payload", help="审批补充 JSON，可传文件路径或 JSON 字符串"
    )
    parser.add_argument(
        "--volume-guidance", default="", help="长篇模式传给当前分卷生成的额外修订指令"
    )
    parser.add_argument(
        "--chapter-guidance", default="", help="仅对指定章节生效的一次性重写指令"
    )
    parser.add_argument(
        "--chapter-guidance-target",
        type=int,
        default=None,
        help="一次性重写指令对应的章节号",
    )
    parser.add_argument(
        "--continue-from", type=int, help="从指定章节号继续生成（跳过已成功的章节）"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="仅预览要生成的章节，不实际生成"
    )
    parser.add_argument(
        "--no-auto-feedback", action="store_true", help="禁用自动反馈循环"
    )
    parser.add_argument(
        "--require-llm",
        action="store_true",
        help="要求真实 LLM 生成；LLM 调用失败或输出过短时不写入 fallback 占位章节",
    )
    parser.add_argument(
        "--show-writing-options",
        action="store_true",
        help="显示所有写作参数可选值并退出",
    )
    parser.add_argument(
        "--diagnose-config",
        action="store_true",
        help="检查 provider/database/Redis/crawler 配置状态（不输出密钥）",
    )
    parser.add_argument(
        "--diagnose-json",
        action="store_true",
        help="以 JSON 输出 --diagnose-config 结果",
    )
    parser.add_argument(
        "--style",
        choices=BASE_STYLE_CHOICES,
        default=DEFAULT_WRITING_OPTIONS["style"],
        help="基础写作风格",
    )
    parser.add_argument(
        "--style-preset",
        choices=[""] + STYLE_PRESET_CHOICES,
        default="",
        help="知识库风格预设",
    )
    parser.add_argument(
        "--perspective",
        choices=sorted(WRITING_OPTION_GROUPS["perspective"].keys()),
        default=DEFAULT_WRITING_OPTIONS["perspective"],
        help="叙事视角",
    )
    parser.add_argument(
        "--narrative-mode",
        choices=sorted(WRITING_OPTION_GROUPS["narrative_mode"].keys()),
        default=DEFAULT_WRITING_OPTIONS["narrative_mode"],
        help="叙事写法",
    )
    parser.add_argument(
        "--pace",
        choices=sorted(WRITING_OPTION_GROUPS["pace"].keys()),
        default=DEFAULT_WRITING_OPTIONS["pace"],
        help="节奏",
    )
    parser.add_argument(
        "--dialogue-density",
        choices=sorted(WRITING_OPTION_GROUPS["dialogue_density"].keys()),
        default=DEFAULT_WRITING_OPTIONS["dialogue_density"],
        help="对白密度",
    )
    parser.add_argument(
        "--prose-style",
        choices=sorted(WRITING_OPTION_GROUPS["prose_style"].keys()),
        default=DEFAULT_WRITING_OPTIONS["prose_style"],
        help="行文质感",
    )
    parser.add_argument(
        "--world-building-density",
        choices=sorted(WRITING_OPTION_GROUPS["world_building_density"].keys()),
        default=DEFAULT_WRITING_OPTIONS["world_building_density"],
        help="设定密度",
    )
    parser.add_argument(
        "--emotion-intensity",
        choices=sorted(WRITING_OPTION_GROUPS["emotion_intensity"].keys()),
        default=DEFAULT_WRITING_OPTIONS["emotion_intensity"],
        help="情绪强度",
    )
    parser.add_argument(
        "--combat-style",
        choices=sorted(WRITING_OPTION_GROUPS["combat_style"].keys()),
        default=DEFAULT_WRITING_OPTIONS["combat_style"],
        help="战斗写法",
    )
    parser.add_argument(
        "--hook-strength",
        choices=sorted(WRITING_OPTION_GROUPS["hook_strength"].keys()),
        default=DEFAULT_WRITING_OPTIONS["hook_strength"],
        help="开篇抓力",
    )
    parser.add_argument(
        "--humanization-level",
        choices=sorted(WRITING_OPTION_GROUPS["humanization_level"].keys()),
        default=DEFAULT_WRITING_OPTIONS["humanization_level"],
        help="去 AI 腔强度",
    )

    # 状态命令
    parser.add_argument("--status", action="store_true", help="查看项目状态")
    parser.add_argument("--list", action="store_true", help="列出所有章节")
    parser.add_argument("--verify", action="store_true", help="验证项目完整性")

    # 导出命令
    parser.add_argument("--export", action="store_true", help="导出为文本文件")
    parser.add_argument("--output", help="导出文件路径")
    parser.add_argument("--end", type=int, help="导出结束章节号")


    # 反馈循环命令
    parser.add_argument(
        "--feedback-discover",
        action="store_true",
        help="发现问题：运行一致性检查，发现潜在问题",
    )
    parser.add_argument(
        "--feedback-analyze",
        action="store_true",
        help="分析问题：对发现的问题进行根因分析",
    )
    parser.add_argument(
        "--feedback-fix", action="store_true", help="修复错误：根据分析结果修复问题"
    )
    parser.add_argument(
        "--feedback-verify", action="store_true", help="验证结果：验证修复是否有效"
    )
    parser.add_argument(
        "--feedback-cycle",
        action="store_true",
        help="完整反馈循环：发现问题→分析→修复→验证",
    )
    parser.add_argument(
        "--feedback-report",
        action="store_true",
        help="导出反馈报告：输出问题报告到文件",
    )
    parser.add_argument(
        "--feedback-mode",
        choices=["light", "deep", "full", "volume_complete"],
        default="light",
        help="反馈循环模式: light=每5章快速检查, deep=完成20章后, full=完整分析, volume_complete=完成一卷后",
    )
    parser.add_argument(
        "--feedback-max-iterations", type=int, default=3, help="最大迭代次数 (默认: 3)"
    )

    # 日志
    parser.add_argument("--log-level", default="INFO", help="日志级别")

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.log_level)

    if args.show_writing_options:
        _print_writing_option_catalog()
        return 0

    if args.diagnose_config:
        return cmd_diagnose_config(args)

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

    # 反馈循环命令
    if (
        args.feedback_discover
        or args.feedback_analyze
        or args.feedback_fix
        or args.feedback_verify
        or args.feedback_cycle
        or args.feedback_report
    ):
        return cmd_feedback_loop(args)

    # 默认显示状态
    return cmd_status(args)


if __name__ == "__main__":
    sys.exit(main())
