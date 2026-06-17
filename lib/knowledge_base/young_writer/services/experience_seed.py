"""Curated global experience seeds for young-writer."""

from __future__ import annotations

import argparse
from pathlib import Path

from young_writer.services.experience_pool import (
    DEFAULT_STATUS,
    EXPERIENCE_KIND_CODE_REPAIR,
    ExperienceCase,
    GlobalExperiencePool,
)


CODE_REPAIR_EXPERIENCE_CASES: tuple[ExperienceCase, ...] = (
    ExperienceCase(
        id="exp_code_goal_lock_singleton_not_auto_complete",
        status="verified",
        experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
        stage="control_plane.story_graph",
        issue_types=["goal_lock_false_inheritance"],
        lesson=(
            "单目标 goal_lock 不能因为目标文本出现在摘要里就被自动判定完成；"
            "状态包必须保留未完成的 remaining_goal_subgoals。"
        ),
        title="Goal-lock singleton false inheritance",
        symptoms=[
            "章节 review 反复报告 goal_lock_false_inheritance",
            "故事图 packet 把未完成目标反馈成已完成状态",
        ],
        root_cause=(
            "story graph packet/rebaseline loop treated singleton macro goals as "
            "completed from summary text matches, then fed contradictory guidance "
            "back into retries."
        ),
        fix=(
            "在 story_graph packet/rebaseline 边界禁止仅凭摘要文本完成 singleton "
            "macro goal，并保持 remaining_goal_subgoals 作为权威未完成状态。"
        ),
        success_criteria=[
            "packet 中未完成目标不会因摘要文本命中而消失",
            "回归测试覆盖 story_graph、longform_run、run_novel_generation",
        ],
        tags=[
            "control_plane",
            "story_graph",
            "goal_lock",
            "code_repair",
        ],
        evidence={
            "files": [
                "lib/knowledge_base/young_writer/services/story_graph/packet.py",
                "lib/knowledge_base/young_writer/services/story_graph/rebaseline.py",
            ],
            "tests": [
                "lib/knowledge_base/tests/services/test_story_graph.py",
                "lib/knowledge_base/tests/test_longform_run.py",
                "lib/knowledge_base/tests/test_run_novel_generation.py",
            ],
            "historical_result": "68 passed in targeted combined run",
        },
    ),
    ExperienceCase(
        id="exp_code_story_graph_rebaseline_no_contradictory_packet",
        status="verified",
        experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
        stage="control_plane.story_graph",
        issue_types=[
            "scene_or_timeline_disconnect",
            "goal_lock_false_inheritance",
        ],
        lesson=(
            "故事图重建只能传递已验证的章节连续性和目标状态；"
            "不要把审查失败后的矛盾状态重新基线化为下一轮权威上下文。"
        ),
        title="Story graph packet and rebaseline contradiction guard",
        symptoms=[
            "修复后仍出现 scene_or_timeline_disconnect",
            "重试提示继承上一轮失败 packet 的矛盾状态",
        ],
        root_cause=(
            "rebaseline delta and chapter graph packet had no hard separation "
            "between accepted state and failed-review guidance."
        ),
        fix=(
            "把已保存章节状态、审查失败信号和重写指导分层；只有通过保存/验收的"
            "状态可以进入权威 story graph baseline。"
        ),
        success_criteria=[
            "失败审查不会污染 accepted story graph baseline",
            "下一轮重写仍能读取失败信号但不把它当成事实",
        ],
        tags=[
            "control_plane",
            "rebaseline",
            "anti_drift",
            "code_repair",
        ],
        evidence={
            "files": [
                "lib/knowledge_base/young_writer/services/story_graph/packet.py",
                "lib/knowledge_base/young_writer/services/story_graph/rebaseline.py",
                "lib/knowledge_base/young_writer/services/longform_run.py",
            ]
        },
    ),
    ExperienceCase(
        id="exp_code_story_input_canonical_assembler",
        status="verified",
        experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
        stage="input_assembly.story_input",
        issue_types=["missing_key_events", "world_fact_violation"],
        lesson=(
            "章节生成输入必须通过 canonical story_input/InputAssembler 汇总；"
            "多入口拼接会让关键事件、世界事实和目标锁在不同路径丢失。"
        ),
        title="Canonical story input assembly",
        symptoms=[
            "章节正文缺失关键事件",
            "不同生成入口携带的世界事实和目标锁不一致",
        ],
        root_cause=(
            "chapter context was assembled in multiple places, so anti-drift "
            "constraints diverged across CLI, orchestrator, and retry paths."
        ),
        fix=(
            "收敛到 InputAssembler/canonical story_input 作为章节上下文边界，"
            "生成、重写和测试都复用同一结构。"
        ),
        success_criteria=[
            "所有章节生成路径读取同一 story_input 结构",
            "关键事件和世界事实在重写路径可见",
        ],
        tags=[
            "input_assembler",
            "story_input",
            "anti_drift",
            "code_repair",
        ],
        evidence={
            "files": [
                "lib/knowledge_base/young_writer/services/input_assembler.py",
                "lib/knowledge_base/young_writer/services/story_input.py",
                "lib/knowledge_base/tests/services/test_story_input.py",
            ]
        },
    ),
    ExperienceCase(
        id="exp_code_pause_resume_review_state_boundary",
        status="verified",
        experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
        stage="runtime.pause_resume",
        issue_types=["chapter_review_pause", "auto_repair_state"],
        lesson=(
            "章节 review 失败后的暂停、自动修复、人工改写和保存必须有清晰状态边界；"
            "不能把失败草稿当作已保存章节继续推进。"
        ),
        title="Pause, repair, resume state boundary",
        symptoms=[
            "生成在 chapter.review 暂停后恢复语义不清",
            "修复指导、人工指导和保存状态可能互相覆盖",
        ],
        root_cause=(
            "runtime state mixed draft, failed review payload, loaded experience, "
            "operator guidance, and saved chapter side effects."
        ),
        fix=(
            "把 review pause payload、auto repair capsule、operator override 和"
            "chapter save success 分别记录；只有保存成功才推进运行状态。"
        ),
        success_criteria=[
            "review 失败只捕获经验并暂停，不推进章节为已完成",
            "保存成功后才记录 loaded experience helped usage",
        ],
        tags=[
            "runtime",
            "pause_resume",
            "chapter_review",
            "code_repair",
        ],
        evidence={
            "files": [
                "lib/knowledge_base/run_novel_generation.py",
                "lib/knowledge_base/young_writer/services/longform_run.py",
                "lib/knowledge_base/tests/test_run_novel_generation.py",
            ]
        },
    ),
)


def seed_global_code_repair_experiences(
    root_dir: str | Path | None = None,
    *,
    status: str | None = None,
) -> list[ExperienceCase]:
    """Append curated code-repair experiences to the global pool."""

    pool = GlobalExperiencePool(root_dir)
    saved: list[ExperienceCase] = []
    for case in CODE_REPAIR_EXPERIENCE_CASES:
        payload = case.to_dict()
        if status:
            payload["status"] = status
        saved.append(pool.append_case(ExperienceCase.from_dict(payload)))
    return saved


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed curated young-writer code-repair experiences."
    )
    parser.add_argument(
        "--root-dir",
        default=None,
        help="Experience pool directory. Defaults to YOUNG_WRITER_EXPERIENCE_DIR or runtime/global_experience.",
    )
    parser.add_argument(
        "--status",
        default="verified",
        choices=[DEFAULT_STATUS, "diagnosed", "fixed", "verified", "promoted"],
        help="Status to write for seeded cases.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    saved = seed_global_code_repair_experiences(args.root_dir, status=args.status)
    for case in saved:
        print(f"{case.id}\t{case.status}\t{case.stage}\t{case.experience_kind}")


if __name__ == "__main__":
    main()
