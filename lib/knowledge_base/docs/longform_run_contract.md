# Longform Run Contract v1

## Scope

This contract defines the near one-shot longform workflow driven by:

- CLI: `lib/knowledge_base/run_novel_generation.py --generate-full`
- UI: `lib/knowledge_base/streamlit_app.py`
- Canonical state: `project_dir/runs/<run_id>/longform_state.v1.json`

## Source Of Truth

Only `project_dir/runs/<run_id>/longform_state.v1.json` is authoritative for resume.

- `status.json` is telemetry only.
- Pending review files are derived review envelopes only.
- Export files and `generation_results.json` are not authoritative resume sources.
- `next_volume_guidance_payload` inside `longform_state.v1.json` is the authoritative structured volume-guidance source for longform resume; `status.json.queued_volume_guidance_payload` is only a mirrored snapshot for UI reads.
- `goal_lock` must be resolved from structured volume guidance first; freeform `volume_guidance` and one-shot `chapter_guidance` are additive text layers, not replacements for the structured source.

## Run Directory

Each longform run writes under:

- `project_dir/runs/<run_id>/status.json`
- `project_dir/runs/<run_id>/stdout.log`
- `project_dir/runs/<run_id>/stderr.log`
- `project_dir/runs/<run_id>/longform_state.v1.json`
- `project_dir/runs/<run_id>/.novel_pipeline_*_pending.json`

`status.json` may additionally mirror lightweight longform fields for the UI, including:

- `longform_state_path`
- `pending_state_path`
- `queued_volume_guidance`
- `queued_volume_guidance_payload`
- `chapter_quality_report` (only when a chapter-level quality gate pauses the run)

Logs remain append-only across resume actions.

## Pause And Resume

Initial launch:

- CLI starts with `--generate-full`.
- If outline approval is enabled, the run pauses at `outline.review`.
- `status.json` must expose `pending_state_path` and `longform_state_path`.

Resume:

- UI or CLI reuses the same `run_id` and `run_dir`.
- Resume passes `--resume-state <pending.json> --submit-approval <approve|revise|reject>`.
- On outline revise, the approved payload may update `outline`, `world_setting`, and `character_intro`.
- Every resume submission appends one entry into `longform_state.v1.json.approval_history` with `checkpoint_type`, `action`, the raw normalized `payload`, and `submitted_at`; this history is append-only across reject/revise/approve loops.
- Operator-facing approval summaries must be derived from that canonical history instead of ad hoc UI-only strings. The shared formatter helpers now live in `services.longform_run` (`approval_entry_detail_parts`, `approval_entry_summary`, `approval_history_summary`) so preview/control-panel surfaces reuse the same audit rendering contract.

## Pending Review Schema

Minimum pending file fields:

- `run_id`
- `checkpoint_type`
- `longform_state_path`
- `current_stage`
- `current_volume`
- `chapters_completed`
- `review_payload`
- `allowed_actions`

For `checkpoint_type == "chapter_review"`, `review_payload` must remain additive/compatible and should expose at least:

- `chapter_number`
- `title`
- `summary`
- `issue_types`
- `blocking_issues`
- `anti_drift_details`
- `warning_issues`
- `semantic_review`
- `chapter_intent_contract`
- `rewrite_plan`
- `rewrite_attempted`
- `rewrite_succeeded`
- `rewrite_history`

When goal-lock inheritance is active, `anti_drift_details` should preserve the evidence needed for UI/operator review, such as `goal_lock`, `goal_terms`, summary/body alignment verdicts, and any matched or checked fragments/windows.

`rewrite_plan` should remain the structured source for operator-facing rewrite guidance. At minimum it should preserve:

- `issue_types`
- optional `issue_categories`
- `must_keep`
- `fixes`
- `success_criteria`

When available, `rewrite_plan` should also expose a machine-readable patch layer so UI or future automation can reason about "what to rewrite" without reparsing the prose bullets:

- `schema_version`
- `strategy`
- `operations[]`

Each `operations[]` item should remain additive and compact. Recommended fields:

- `phase`
- `action`
- `target`
- `instruction`
- `rationale`
- `success_signal`

For `chapter_review -> revise`, resume consumers should preserve `rewrite_plan` as the structured source and derive the final freeform retry text from the shared service helper instead of rebuilding it ad hoc in the UI. The canonical compiler now lives in `services.longform_run.compile_chapter_rewrite_guidance`, which combines `must_keep`, `operations[]` / `fixes`, `success_criteria`, and optional operator notes into the submitted `chapter_rewrite_guidance`.

For `checkpoint_type == "volume_review"`, `review_payload` should additionally expose:

- `cross_volume_registry`
- `cross_volume_registry_summary`

`cross_volume_registry` currently uses three additive buckets:

- `unresolved_goals`
- `open_promises`
- `dangling_settings`

Resume consumers must preserve explicit empty-list updates for those buckets so operators can clear resolved items instead of carrying stale registry state into the next volume.

## Guidance Inheritance And Chapter Gate

The longform chapter loop must preserve these invariants:

1. Volume approval writes structured guidance into `longform_state.v1.json.next_volume_guidance_payload`.
2. Chapter generation inherits that payload through `context["volume_guidance_payload"]`.
3. `goal_lock` stays a stable prompt anchor for each chapter whenever the structured payload provides it.
4. Chapter-specific guidance is additive only; it must not overwrite or shadow the structured `goal_lock` source.
5. If a chapter fails the consistency/anti-drift gate, the run pauses at `chapter.review` and review consumers read the derived pending payload instead of guessing from raw logs.
6. If a chapter summary appears aligned but the body still drifts away from the `goal_lock`, the chapter review payload must surface that failure explicitly and downstream summary promotion must be gated on the verified result rather than the raw generated summary.

## Longform Stages

The longform telemetry stages are:

- `outline.generate`
- `outline.review`
- `volume.plan`
- `volume.write`
- `chapter.review`
- `volume.review`
- `risk.pause`
- `finalize.export`
