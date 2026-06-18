# young-writer Directory Architecture

This document records the current boundary for the `lib/knowledge_base` product
line and the compatibility rules used while the repository still contains older
runtime data.

## Source Boundaries

- `lib/knowledge_base/` is the active young-writer product surface. Its CLI,
  Streamlit console, agents, services, tests, and local generation runtime belong
  to this product.
- `lib/crewai*` remains the upstream framework/workspace area. Product runtime
  data, local novel projects, and Streamlit run state should not be written there.
- `lib/knowledge_base/young_writer/` is the primary Python package. Core
  product modules now live there and should be imported as
  `young_writer.<module>`.
- `lib/knowledge_base/knowledge_base/` plus top-level compatibility packages
  such as `agents/`, `services/`, `llm/`, and `triggers/` are shims for older
  imports. They should remain thin aliases only and should not receive new
  product code.
- The compatibility layer is transitional: new code should target
  `young_writer.*`, while existing CLI wrappers and tests can continue to pass
  through compatibility aliases until they are retired.

## Runtime Layout

New projects created through `ConfigManager` default to a unified project root:

```text
lib/knowledge_base/runtime/projects/<title>_<project_id>/
  chapters/
  consistency_reports/
  plot_summaries/
  runs/
```

The runtime root can be redirected with `YOUNG_WRITER_DATA_DIR` or
`YOUNG_WRITER_RUNTIME_DIR`. `YOUNG_WRITER_DATA_DIR` wins when both are set.

## Legacy Compatibility

Older projects may already exist under:

```text
lib/knowledge_base/novels/<title>_<project_id>/
```

When an existing legacy novel directory is present, path resolution keeps using
that legacy layout. This keeps existing project configs, tests, CLI invocations,
and Streamlit run history readable without a destructive migration.

## Git Boundary

Generated project data is ignored for future writes:

- `lib/knowledge_base/runtime/`
- legacy `novels/`
- local config state such as `config/current_project.txt` and
  `config/project_*.json`
- local caches, cookies, logs, and crawled web novel resources

`fixtures/` and `samples/` subdirectories under legacy generated-output roots
are explicitly left visible so reviewed examples can still be versioned.

Tracked historical data is not automatically removed by `.gitignore`. Any future
cleanup should be a separate reviewed migration that distinguishes fixtures from
local project state.

## Entrypoint Boundary

- `run_novel_generation.py` remains the CLI entrypoint.
- `streamlit_app.py` remains the local UI entrypoint.
- Both entrypoints should import product code from `young_writer.*`; direct
  legacy-root imports are compatibility-only.
- UI command construction lives in `services/cli_commands.py` so it can be tested
  without launching Streamlit.
- Runtime path decisions live in `services/paths.py`; writers should use that
  service instead of hand-building legacy `novels/` paths.
