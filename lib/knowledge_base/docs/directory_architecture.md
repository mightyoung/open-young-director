# young-writer Directory Architecture

This document records the current boundary for the `lib/knowledge_base`
product line and its compatibility rules.

## Source Boundaries

- `lib/knowledge_base/` is the active young-writer product surface. Its CLI,
  Streamlit console, agents, services, tests, and local generation runtime
  belong to this product.
- Upstream framework workspace paths are not young-writer runtime/output
  targets. Product runtime data, local novel projects, and Streamlit run state
  belong under `lib/knowledge_base/`.
- `lib/knowledge_base/young_writer/` is the primary Python package. New product
  modules should be imported as `young_writer.<module>`.
- `lib/knowledge_base/knowledge_base/` plus top-level compatibility packages
  such as `agents/`, `services/`, `llm/`, and `triggers/` are shims for older
  imports. They should remain thin aliases and should not receive new product
  code.
- The compatibility layer is transitional: new code should target
  `young_writer.*`, while existing CLI wrappers and tests may continue through
  compatibility aliases until retired.

## Runtime Layout

New projects created through `ConfigManager` default to the unified project
root:

```text
lib/knowledge_base/runtime/projects/<title>_<project_id>/
  chapters/
  consistency_reports/
  plot_summaries/
  runs/
```

The runtime root can be redirected by `YOUNG_WRITER_DATA_DIR` or
`YOUNG_WRITER_RUNTIME_DIR`. `YOUNG_WRITER_DATA_DIR` wins when both are set.

## Legacy Compatibility

Older projects may already exist under:

```text
lib/knowledge_base/novels/<title>_<project_id>/
```

When an existing legacy novel directory is present, path resolution keeps using
that legacy layout. This keeps existing project configs, tests, CLI invocations,
and Streamlit run history readable without destructive migration.

## Git Boundary

Generated project data is ignored for future writes:

- `lib/knowledge_base/runtime/`
- legacy `novels/`
- local config state such as `config/current_project.txt` and
  `config/project_*.json`
- local caches, cookies, logs, and crawled web novel resources

`fixtures/` and `samples/` subdirectories under legacy generated-output roots
are explicitly left visible so reviewed examples can still be versioned.

Tracked historical data is not automatically removed by `.gitignore`. Future
cleanup should be a separate reviewed migration that distinguishes fixtures
from local project state.

## Entrypoint Boundary

- `run_novel_generation.py` remains the CLI entrypoint.
- `streamlit_app.py` remains the local UI entrypoint.
- Both entrypoints import product code through `young_writer.*`; direct
  legacy-root imports are compatibility-only.
- UI command construction lives in `services/cli_commands.py` so it can be
  tested without launching Streamlit.
- Runtime path decisions live in `services/paths.py`; writers should use that
  service instead of hand-building legacy `novels/` paths.

## Generation Control Plane

- `services/input_assembler.py` builds canonical `GenerationPacket`
  and legacy-compatible context fields.
- `services/narrative_driver.py` derives `chapter_driver_packet.v1`
  from structured chapter plans, characters, world facts, runtime
  overrides, and optional `chapter_graph_packet` evidence.
- `chapter_driver_packet.v1` is novel-generation driver only: it
  provides scene beats, cast objectives, emotional arc, tension points,
  and cliffhanger hints to `NovelGeneratorAgent`; it must not recreate
  old `film_drama` media, short-drama, director-agent, or sub-agent
  runtime paths.
- `chapter_graph_packet` remains continuity/goal-state packet.
  `chapter_driver_packet` stays subordinate to `goal_lock` and graph
  constraints.
