# Open Young Director / young-writer

[English](#english) | [中文](#中文)

---

## English

### Overview

**Open Young Director** is a local, single-user workbench for long-form web
fiction. The maintained product code lives in `lib/knowledge_base/`, with
`lib/knowledge_base/young_writer/` as the primary Python package and
`knowledge_base` kept as a compatibility alias.

The workbench combines:

- a Streamlit control panel
- a CLI for project creation, chapter generation, and full-novel runs
- pause/resume checkpoints for outline, volume, and chapter review
- consistency, anti-drift, and review history tracking
- derivative-content hooks for podcast/video-style assets

### Main Entry Points

- UI: [`lib/knowledge_base/streamlit_app.py`](./lib/knowledge_base/streamlit_app.py)
- CLI: [`lib/knowledge_base/run_novel_generation.py`](./lib/knowledge_base/run_novel_generation.py)
- Longform contract: [`lib/knowledge_base/docs/longform_run_contract.md`](./lib/knowledge_base/docs/longform_run_contract.md)
- Operator manual: [`lib/knowledge_base/docs/user_manual.md`](./lib/knowledge_base/docs/user_manual.md)

### Repository Layout

```text
lib/
└── knowledge_base/
    ├── young_writer/           # Primary product package
    ├── knowledge_base/         # Compatibility alias package
    ├── agents/                 # Legacy import shim
    ├── services/               # Legacy import shim
    ├── streamlit_app.py        # Local control panel
    ├── run_novel_generation.py # Main CLI
    ├── writing_options.py      # Shared writing-option presets
    ├── docs/                   # Operator docs and workflow contracts
    └── tests/                  # Focused tests for the workbench
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

Run focused tests:

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  lib/knowledge_base/tests/test_streamlit_app.py -q
```

### Runtime Notes

- `lib/knowledge_base/.env` is local-only and should not be committed.
- Generated project data under `lib/knowledge_base/config/`, `novels/`,
  `generated_scripts/`, and run directories can contain local working state and
  should be reviewed before committing.
- `status.json` is telemetry, not the authoritative resume source.
- Longform resume state lives in `longform_state.v1.json`.

---

## 中文

### 概述

**Open Young Director / young-writer** 是一个本地、单用户的长篇网文创作工作台。
当前维护中的产品代码位于 `lib/knowledge_base/`，主 Python 包是
`lib/knowledge_base/young_writer/`，`knowledge_base` 仅作为兼容别名保留。

核心能力包括：

- Streamlit 可视化控制台
- 用于建项目、生成章节、整本长篇运行的 CLI
- 大纲、分卷、章节复核等可暂停/可恢复检查点
- 一致性、anti-drift、审批历史追踪
- 播客/视频提示词等衍生内容生成挂钩

### 主要入口

- UI：[`lib/knowledge_base/streamlit_app.py`](./lib/knowledge_base/streamlit_app.py)
- CLI：[`lib/knowledge_base/run_novel_generation.py`](./lib/knowledge_base/run_novel_generation.py)
- 长篇运行合同：[`lib/knowledge_base/docs/longform_run_contract.md`](./lib/knowledge_base/docs/longform_run_contract.md)
- 操作手册：[`lib/knowledge_base/docs/user_manual.md`](./lib/knowledge_base/docs/user_manual.md)

### 仓库结构

```text
lib/
└── knowledge_base/
    ├── young_writer/           # 主产品包
    ├── knowledge_base/         # 兼容别名包
    ├── agents/                 # 旧导入路径 shim
    ├── services/               # 旧导入路径 shim
    ├── streamlit_app.py        # 本地控制台
    ├── run_novel_generation.py # 主 CLI
    ├── writing_options.py      # 写作参数预设
    ├── docs/                   # 操作文档和流程合同
    └── tests/                  # 工作台测试
```

### 快速开始

```bash
uv sync
cp lib/knowledge_base/.env.example lib/knowledge_base/.env
```

通常需要配置：

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

运行重点回归测试：

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  lib/knowledge_base/tests/test_streamlit_app.py -q
```
