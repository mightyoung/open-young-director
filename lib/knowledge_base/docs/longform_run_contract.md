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

## Run Directory

Each longform run writes under:

- `project_dir/runs/<run_id>/status.json`
- `project_dir/runs/<run_id>/stdout.log`
- `project_dir/runs/<run_id>/stderr.log`
- `project_dir/runs/<run_id>/longform_state.v1.json`
- `project_dir/runs/<run_id>/.novel_pipeline_*_pending.json`

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

## Longform Stages

The longform telemetry stages are:

- `outline.generate`
- `outline.review`
- `volume.plan`
- `volume.write`
- `volume.review`
- `risk.pause`
- `finalize.export`
