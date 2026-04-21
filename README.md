# Open Young Director / 青年导演

[English](#english) | [中文](#中文)

---

## English

### Overview

**Open Young Director** is a crewAI-based monorepo whose actively maintained novel-writing workflow currently lives in `lib/knowledge_base/`.

The current deliverable is a local, single-user writing workbench for long-form web fiction. It combines:

- a Streamlit control panel
- a CLI for project creation, chapter generation, and full-novel runs
- pause/resume checkpoints for outline, volume, and chapter review
- consistency, anti-drift, and review history tracking
- derivative-content generation hooks for podcast/video-style assets

This repository also contains the upstream-style `crewai` packages and tools, but if you want to run the novel system today, start from `lib/knowledge_base/`.

### Current Scope

What is working today:

- local project creation and loading
- chapter-by-chapter generation
- full-novel generation with approval checkpoints
- structured writing options shared by UI and CLI
- resumable runs backed by canonical run state
- chapter review payloads with anti-drift evidence and rewrite plans
- cross-volume registry tracking for unresolved goals, promises, and dangling settings

What this repository is not claiming today:

- hosted multi-user service
- production deployment target
- distributed worker cluster
- Docker/Kubernetes delivery lane

### Main Entry Points

- UI: [`lib/knowledge_base/streamlit_app.py`](./lib/knowledge_base/streamlit_app.py)
- CLI: [`lib/knowledge_base/run_novel_generation.py`](./lib/knowledge_base/run_novel_generation.py)
- Longform contract: [`lib/knowledge_base/docs/longform_run_contract.md`](./lib/knowledge_base/docs/longform_run_contract.md)
- Operator manual: [`lib/knowledge_base/docs/user_manual.md`](./lib/knowledge_base/docs/user_manual.md)

### Repository Layout

```text
lib/
├── crewai/                    # Core crewAI framework and CLI
├── crewai-tools/              # Tool integrations
└── knowledge_base/            # Active young-writer workspace
    ├── agents/                # Novel generation, orchestration, feedback loop
    ├── services/              # Run storage and longform workflow helpers
    ├── llm/                   # Provider clients and prompt plumbing
    ├── consistency/           # Consistency models and manager
    ├── consumers/             # Derivative-content consumers
    ├── media/                 # Media generation adapters/executors
    ├── streamlit_app.py       # Local control panel
    ├── run_novel_generation.py # Main CLI
    ├── writing_options.py     # Shared writing-option presets
    ├── docs/                  # Operator docs and workflow contracts
    └── tests/                 # Focused tests for the workbench
```

### Quick Start

```bash
uv sync
cp lib/knowledge_base/.env.example lib/knowledge_base/.env
```

Minimum environment you will usually need:

```bash
KIMI_API_KEY=your_key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL_NAME=moonshot-v1-8k
```

Launch the local UI:

```bash
cd lib/knowledge_base
uv run streamlit run streamlit_app.py
```

Create a project from the CLI:

```bash
cd lib/knowledge_base
uv run python run_novel_generation.py \
  --new "Taigu Demon Emperor" \
  --genre "xianxia" \
  --outline "A discarded disciple inherits an ancient demonic legacy and rises." \
  --world "A cultivation world with sects, realms, and forbidden inheritances." \
  --characters "Han Lin: patient, restrained, ambitious." \
  --chapters 120
```

Generate a few chapters:

```bash
uv run python run_novel_generation.py --load <project_id> --generate 3
```

Start a resumable longform run:

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --chapters-per-volume 60 \
  --approval-mode outline+volume
```

Resume a paused run:

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --run-id <run_id> \
  --run-dir <run_dir> \
  --resume-state <pending_state.json> \
  --submit-approval approve
```

Inspect supported writing knobs:

```bash
uv run python run_novel_generation.py --show-writing-options
```

### Longform Workflow Notes

Longform runs write canonical state into:

- `lib/knowledge_base/novels/<title>_<project_id>/runs/<run_id>/longform_state.v1.json`

Important behavior:

- `status.json` is telemetry, not the authoritative resume source
- pending review files are derived envelopes for operator review
- `approval_history` is append-only across reject/revise/approve loops
- `chapter_review` payloads can include anti-drift evidence, warning issues, semantic review, and structured rewrite plans
- `volume_review` payloads can include cross-volume registry state for unresolved goals, open promises, and dangling settings

### Tests

Focused workbench tests live under `lib/knowledge_base/tests/`.

Run the main regression set:

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  lib/knowledge_base/tests/test_streamlit_app.py -q
```

### Notes

- `lib/knowledge_base/.env` is local-only and should not be committed.
- Generated project data under `lib/knowledge_base/config/`, `novels/`, `generated_scripts/`, and run directories can contain local working state and should be reviewed before committing.

---

## 中文

### 概述

**Open Young Director（青年导演）** 是一个基于 crewAI 的单仓库项目，当前真正处于持续维护状态的小说创作系统位于 `lib/knowledge_base/`。

现在这套系统的定位是一个本地、单用户的长篇网文创作工作台，核心能力包括：

- Streamlit 可视化控制台
- 用于建项目、生成章节、整本长篇运行的 CLI
- 大纲、分卷、章节复核等可暂停/可恢复检查点
- 一致性、anti-drift、审批历史追踪
- 播客/视频提示词等衍生内容生成挂钩

仓库里仍然保留 `crewai` 主体框架和工具包，但如果你要使用当前的小说系统，应优先从 `lib/knowledge_base/` 开始。

### 当前范围

当前已经覆盖：

- 本地创建和加载项目
- 逐章生成
- 整本长篇生成与人工审批检查点
- UI 和 CLI 共用的结构化写作参数
- 基于规范化 run state 的恢复执行
- 带 anti-drift 证据和重写计划的章节复核
- 跨卷未完成目标、伏笔、设定线程的 registry 管理

当前不应误解为：

- 线上多用户服务
- 可直接发布的生产部署方案
- 分布式 worker 集群
- Docker / Kubernetes 交付形态

### 主要入口

- UI：[`lib/knowledge_base/streamlit_app.py`](./lib/knowledge_base/streamlit_app.py)
- CLI：[`lib/knowledge_base/run_novel_generation.py`](./lib/knowledge_base/run_novel_generation.py)
- 长篇运行合同：[`lib/knowledge_base/docs/longform_run_contract.md`](./lib/knowledge_base/docs/longform_run_contract.md)
- 操作手册：[`lib/knowledge_base/docs/user_manual.md`](./lib/knowledge_base/docs/user_manual.md)

### 仓库结构

```text
lib/
├── crewai/                    # crewAI 核心框架与 CLI
├── crewai-tools/              # 工具集成
└── knowledge_base/            # 当前 young-writer 工作台
    ├── agents/                # 小说生成、编排、反馈循环
    ├── services/              # run 存储与长篇流程辅助逻辑
    ├── llm/                   # 模型客户端与 prompt 适配
    ├── consistency/           # 一致性模型与管理器
    ├── consumers/             # 衍生内容消费链路
    ├── media/                 # 媒体生成适配器
    ├── streamlit_app.py       # 本地控制台
    ├── run_novel_generation.py # 主 CLI
    ├── writing_options.py     # 共用写作参数预设
    ├── docs/                  # 操作文档与运行合同
    └── tests/                 # 工作台相关测试
```

### 快速开始

```bash
uv sync
cp lib/knowledge_base/.env.example lib/knowledge_base/.env
```

通常至少需要配置：

```bash
KIMI_API_KEY=your_key
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL_NAME=moonshot-v1-8k
```

启动本地 UI：

```bash
cd lib/knowledge_base
uv run streamlit run streamlit_app.py
```

用 CLI 创建项目：

```bash
cd lib/knowledge_base
uv run python run_novel_generation.py \
  --new "太古魔帝传" \
  --genre "玄幻修仙" \
  --outline "少年韩林获得上古魔帝传承，逆天崛起。" \
  --world "修真世界，宗门林立，传承与禁地并存。" \
  --characters "韩林：隐忍、克制、目标明确。" \
  --chapters 120
```

生成几章正文：

```bash
uv run python run_novel_generation.py --load <project_id> --generate 3
```

启动可恢复的整本长篇流程：

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --chapters-per-volume 60 \
  --approval-mode outline+volume
```

恢复暂停中的 run：

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --run-id <run_id> \
  --run-dir <run_dir> \
  --resume-state <pending_state.json> \
  --submit-approval approve
```

查看支持的写作参数：

```bash
uv run python run_novel_generation.py --show-writing-options
```

### 长篇运行说明

长篇模式的规范化状态文件位于：

- `lib/knowledge_base/novels/<title>_<project_id>/runs/<run_id>/longform_state.v1.json`

几个关键点：

- `status.json` 只是遥测快照，不是恢复时的权威状态源
- pending review 文件只是给操作者查看/提交审批用的派生 envelope
- `approval_history` 会在 reject / revise / approve 循环里追加保留
- `chapter_review` 可暴露 anti-drift 证据、warning、语义复核结果和结构化重写计划
- `volume_review` 可暴露跨卷 registry，用于维护未完成目标、未回收伏笔和未桥接设定

### 测试

工作台相关测试主要位于 `lib/knowledge_base/tests/`。

建议回归命令：

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  lib/knowledge_base/tests/test_streamlit_app.py -q
```

### 备注

- `lib/knowledge_base/.env` 只用于本地开发，不应提交。
- `lib/knowledge_base/config/`、`novels/`、`generated_scripts/` 和各类 run 目录可能包含本地工作状态，提交前应单独检查。

---

## License / 许可证

MIT License. See [LICENSE](./LICENSE).
