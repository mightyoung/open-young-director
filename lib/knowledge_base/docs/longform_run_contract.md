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
- `rewrite_attempted`
- `rewrite_succeeded`
- `rewrite_history`

When goal-lock inheritance is active, `anti_drift_details` should preserve the evidence needed for UI/operator review, such as `goal_lock`, `goal_terms`, summary/body alignment verdicts, and any matched or checked fragments/windows.

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
