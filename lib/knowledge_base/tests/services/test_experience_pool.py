from young_writer.services.experience_pool import (
    EXPERIENCE_KIND_CODE_REPAIR,
    EXPERIENCE_KIND_GENERATION,
    ExperienceCase,
    GlobalExperiencePool,
    build_case_from_review_payload,
    build_experience_capsule,
    format_experience_capsule,
)
from young_writer.services.experience_seed import seed_global_code_repair_experiences


def test_global_experience_pool_retrieves_verified_issue_match(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_scene_bridge",
            status="verified",
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            lesson="开篇必须回应上一章尾部线索，避免地点跳切。",
            source_project_id="source-project",
            run_id="source-run",
            chapter_number=12,
            fix="前 300 字承接 previous_tail_signal。",
            success_criteria=["开篇明确回应上一章后果"],
        )
    )
    pool.append_case(
        ExperienceCase(
            id="exp_unverified",
            status="captured",
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            lesson="未验证经验不默认进入生成上下文。",
        )
    )

    retrieved = pool.retrieve(
        stage="chapter.review",
        issue_types=["scene_or_timeline_disconnect"],
        query_terms=["上一章"],
    )

    assert [case.id for _, case in retrieved] == ["exp_scene_bridge"]
    capsule = build_experience_capsule(retrieved)
    assert capsule["loaded_ids"] == ["exp_scene_bridge"]
    rendered = format_experience_capsule(capsule)
    assert "全局经验池召回" in rendered
    assert "开篇必须回应上一章尾部线索" in rendered
    assert "source=source-project" in rendered
    assert "run=source-run" in rendered
    assert "ch=12" in rendered


def test_retrieve_can_isolate_generation_guidance_from_code_repair(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_generation_goal_lock",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="生成时必须真实推进目标锁，不要用摘要伪造完成。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )
    pool.append_case(
        ExperienceCase(
            id="exp_code_goal_lock",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="代码修复：singleton macro goal 不得仅凭摘要文本完成。",
            experience_kind=EXPERIENCE_KIND_CODE_REPAIR,
        )
    )

    retrieved = pool.retrieve(
        stage="chapter.review",
        issue_types=["goal_lock_false_inheritance"],
        experience_kinds=[EXPERIENCE_KIND_GENERATION],
    )

    assert [case.id for _, case in retrieved] == ["exp_generation_goal_lock"]


def test_global_experience_pool_dedupes_case_ids(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    case = ExperienceCase(
        id="exp_duplicate",
        status="verified",
        stage="chapter.review",
        issue_types=["goal_lock_false_inheritance"],
        lesson="目标锁必须在正文动作链里推进。",
    )

    pool.append_case(case)
    pool.append_case(case)

    assert [item.id for item in pool.load_cases()] == ["exp_duplicate"]


def test_seed_global_code_repair_experiences_is_deduped_and_isolated(tmp_path):
    first = seed_global_code_repair_experiences(tmp_path)
    second = seed_global_code_repair_experiences(tmp_path)
    pool = GlobalExperiencePool(tmp_path)

    assert [case.id for case in first] == [case.id for case in second]
    loaded = pool.load_cases()
    assert len(loaded) == len(first)
    assert {case.experience_kind for case in loaded} == {EXPERIENCE_KIND_CODE_REPAIR}
    assert {
        "control_plane.story_graph",
        "input_assembly.story_input",
        "runtime.pause_resume",
    }.issubset({case.stage for case in loaded})


def test_build_case_from_review_payload_preserves_global_provenance():
    review_payload = {
        "chapter_number": 12,
        "title": "第十二章",
        "summary": "自动重写后仍未通过质量门。",
        "issue_types": ["scene_or_timeline_disconnect", "goal_lock_false_inheritance"],
        "blocking_issues": ["上一章后果未被承接。"],
        "rewrite_plan": {
            "fixes": ["开篇承接上一章尾部线索。"],
            "success_criteria": ["正文围绕目标锁推进。"],
        },
        "rewrite_history": [{"attempt": 1, "mode": "targeted_full_rewrite"}],
    }

    case = build_case_from_review_payload(
        review_payload,
        project_id="project-a",
        run_id="run-a",
        status="verified",
    )

    assert case.source_project_id == "project-a"
    assert case.run_id == "run-a"
    assert case.stage == "chapter.review"
    assert case.issue_types == [
        "scene_or_timeline_disconnect",
        "goal_lock_false_inheritance",
    ]
    assert "开篇承接上一章尾部线索" in case.fix


def test_promote_case_updates_status_and_preserves_retrieval_gate(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_captured_bridge",
            status="captured",
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            lesson="开篇必须承接上一章尾部线索。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )

    assert (
        pool.retrieve(
            stage="chapter.review",
            issue_types=["scene_or_timeline_disconnect"],
            query_terms=["上一章"],
            experience_kinds=[EXPERIENCE_KIND_GENERATION],
        )
        == []
    )

    promoted = pool.promote_case(
        "exp_captured_bridge",
        evidence_append={"event": "chapter_saved_after_revision"},
    )

    assert promoted is not None
    assert promoted.status == "verified"
    reloaded = pool.get_case("exp_captured_bridge")
    assert reloaded is not None
    assert reloaded.status == "verified"
    assert reloaded.evidence["events"][0]["event"] == "chapter_saved_after_revision"
    retrieved = pool.retrieve(
        stage="chapter.review",
        issue_types=["scene_or_timeline_disconnect"],
        query_terms=["上一章"],
        experience_kinds=[EXPERIENCE_KIND_GENERATION],
    )
    assert [case.id for _, case in retrieved] == ["exp_captured_bridge"]


def test_record_usage_updates_case_counters(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_usage",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )

    pool.record_usage(
        experience_ids=["exp_usage", "exp_usage"],
        project_id="project-a",
        run_id="run-a",
        stage="chapter.save",
        chapter_number=3,
        outcome="helped",
    )

    reloaded = pool.get_case("exp_usage")
    assert reloaded is not None
    assert reloaded.usage_count == 1
    assert reloaded.helped_count == 1
    assert reloaded.hurt_count == 0
    assert pool.usage_path.exists()


def test_record_usage_ignores_empty_project_or_run_context(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_usage",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )

    pool.record_usage(
        experience_ids=["exp_usage"],
        project_id="",
        run_id="",
        stage="chapter.review",
        chapter_number=4,
        outcome="loaded",
    )

    reloaded = pool.get_case("exp_usage")
    assert reloaded is not None
    assert reloaded.usage_count == 0
    assert not pool.usage_path.exists()


def test_record_usage_preserves_unrelated_cases_during_rewrite(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_usage_target",
            status="verified",
            stage="chapter.review",
            issue_types=["goal_lock_false_inheritance"],
            lesson="目标锁必须在正文动作链里推进。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )
    pool.append_case(
        ExperienceCase(
            id="exp_usage_unrelated",
            status="captured",
            stage="chapter.review",
            issue_types=["missing_key_events"],
            lesson="关键事件必须写成场景行动。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
        )
    )

    pool.record_usage(
        experience_ids=["exp_usage_target"],
        project_id="project-a",
        run_id="run-a",
        stage="chapter.save",
        chapter_number=3,
        outcome="helped",
    )

    assert pool.get_case("exp_usage_target").usage_count == 1
    unrelated = pool.get_case("exp_usage_unrelated")
    assert unrelated is not None
    assert unrelated.status == "captured"


def test_hurt_usage_lowers_retrieval_score(tmp_path):
    pool = GlobalExperiencePool(tmp_path)
    pool.append_case(
        ExperienceCase(
            id="exp_helped",
            status="verified",
            stage="chapter.review",
            issue_types=["missing_key_events"],
            lesson="关键事件必须写成场景行动。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
            helped_count=2,
        )
    )
    pool.append_case(
        ExperienceCase(
            id="exp_hurt",
            status="verified",
            stage="chapter.review",
            issue_types=["missing_key_events"],
            lesson="关键事件必须写成场景行动。",
            experience_kind=EXPERIENCE_KIND_GENERATION,
            hurt_count=2,
        )
    )

    retrieved = pool.retrieve(
        stage="chapter.review",
        issue_types=["missing_key_events"],
        query_terms=["关键事件"],
        experience_kinds=[EXPERIENCE_KIND_GENERATION],
    )

    assert [case.id for _, case in retrieved][:2] == ["exp_helped", "exp_hurt"]
