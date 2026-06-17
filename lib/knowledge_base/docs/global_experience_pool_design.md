# Young-writer Global Experience Pool Design

## Goal

Every novel generation run should learn from global young-writer experience,
not only from the local project directory. A run can:

1. retrieve verified global experience before chapter repair guidance is built;
2. capture structured failure evidence when a chapter review pause occurs;
3. record whether loaded experience later helped when a chapter is saved.

The pool is global to young-writer, while every case keeps provenance back to
the source project, run, chapter, and review payload.

## External Basis

- Reflexion: failed trials can be converted into verbal feedback reused as
  episodic memory without model weight updates. <https://arxiv.org/abs/2303.11366>
- Self-Refine: generation, feedback, and revision form a repeatable loop, which
  maps directly to chapter review rewrite. <https://arxiv.org/abs/2303.17651>
- Voyager: successful repairs should become reusable skills or procedures, not
  only raw traces. <https://arxiv.org/abs/2305.16291>
- Generative Agents: raw observations should be reflected into higher-level
  memories for later planning. <https://arxiv.org/abs/2304.03442>
- MemGPT: long-running agents need tiered memory instead of pushing all history
  into active context. <https://arxiv.org/abs/2310.08560>
- Google SRE postmortem culture: incident learning needs evidence, root cause,
  action items, and review instead of blame or vague summaries.
  <https://sre.google/sre-book/postmortem-culture/>

## First Implementation

The first implementation is deliberately small:

- `young_writer.services.experience_pool.GlobalExperiencePool` stores global
  JSONL files under `young_writer/runtime/global_experience/` by default.
- `YOUNG_WRITER_EXPERIENCE_DIR` can override the path for tests and isolated
  runs.
- `cases.jsonl` stores captured, verified, and promoted experiences.
- `usage.jsonl` records when experience was loaded and whether a later save
  marked it helpful.
- `experience_kind` separates generation guidance from engineering repair
  knowledge. Existing records without this field are treated as
  `generation_guidance`.
- retrieval is deterministic scoring over stage, issue type overlap, query
  terms, helped count, and hurt count.

Only `verified` and `promoted` cases enter rewrite guidance by default. New
chapter review failures are captured as `captured`, preserving evidence without
polluting future generation prompts.

Code-level fixes use the same global pool but a different loading channel:

- `generation_guidance` can be loaded into chapter review rewrite guidance.
- `code_repair` is for diagnosis, implementation, and tests. It must not be
  loaded into novel text generation prompts by default.
- curated historical repairs can be seeded with
  `python -m young_writer.services.experience_seed`; they are written as
  `verified` `code_repair` cases and deduped by stable ids.

## Lifecycle

```text
captured -> diagnosed -> fixed -> verified -> promoted -> rejected / stale
```

The patch implements `captured` writes, verified/promoted retrieval, usage
events, and curated code-repair seeds. Promotion remains a future explicit
review batch operation so one-off failures do not become global rules
automatically.

## Integration Points

- chapter review pause: `run_novel_generation._pause_for_invalid_chapter`
  builds review payload and appends a global captured case.
- automatic rewrite guidance: `_compile_auto_repair_guidance` loads a global
  experience capsule and adds it to the existing guidance compiler. This path
  filters to `generation_guidance` cases.
- manual chapter revise approval: `cmd_generate_full` loads the same capsule
  unless the operator provides explicit replacement guidance.
- chapter save success: `cmd_generate` records loaded experience as `helped`
  when chapter save succeeds and the capsule was attached to state.
- code repair seeding: `young_writer.services.experience_seed` writes curated
  `code_repair` cases for previous control-plane and input-assembly fixes.

## Non-goals

- no vector database or external service in v1;
- no automatic promotion from captured to verified;
- no storage of full chapter bodies in global experience cases;
- no weakening quality gates to force success.
