# young-writer 部署与使用手册

本手册覆盖当前 `knowledge_base` 工作台的本地部署、运行入口、长篇生成流程和常见排查方式。

## 1. 适用范围

当前交付形态是单机、本地、单用户工作台：

- UI 入口：[streamlit_app.py](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/streamlit_app.py)
- CLI 入口：[run_novel_generation.py](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/run_novel_generation.py)
- 长篇运行合同：[longform_run_contract.md](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/docs/longform_run_contract.md)

不包含：

- 远程 API 服务
- 多用户部署
- 队列/Worker 集群
- Docker/K8s 发布方案

## 2. 目录与数据布局

所有数据都落在 `lib/knowledge_base/` 下：

- 配置：`lib/knowledge_base/config/`
- 项目目录：`lib/knowledge_base/novels/<title>_<project_id>/`
- 章节输出：`.../chapters/`
- 一致性报告：`.../consistency_reports/`
- 情节摘要：`.../plot_summaries/`
- 运行目录：`.../runs/<run_id>/`

运行目录中的关键文件：

- `status.json`：运行状态快照
- `stdout.log` / `stderr.log`：追加式日志
- `longform_state.v1.json`：长篇模式唯一可恢复状态
- `.novel_pipeline_*_pending.json`：审批暂停时生成的派生 review 文件

## 3. 环境准备

推荐直接使用仓库根目录的 `uv` 环境：

```bash
cd /Users/muyi/Downloads/dev/young-writer
uv sync
```

如果只在 `knowledge_base` 子目录工作：

```bash
cd /Users/muyi/Downloads/dev/young-writer/lib/knowledge_base
uv sync
```

建议准备：

- Python 3.13
- `uv`
- 可用的 Kimi API Key，或本地 `kimi-cli`

如果使用 API 模式，需要环境变量：

```bash
export KIMI_API_KEY=your_key
```

可选变量：

```bash
export KIMI_BASE_URL=https://api.moonshot.cn/v1
export KIMI_MODEL_NAME=moonshot-v1-8k
```

## 4. 本地部署

### 4.1 启动 Streamlit 控制台

```bash
cd /Users/muyi/Downloads/dev/young-writer/lib/knowledge_base
uv run streamlit run streamlit_app.py
```

适合：

- 创建/加载项目
- 修改写作参数
- 发起普通章节生成
- 发起整本长篇生成
- 在 outline/volume 节点做人工审批
- 查看日志、ETA 和章节内容

### 4.2 直接运行 CLI

```bash
cd /Users/muyi/Downloads/dev/young-writer/lib/knowledge_base
uv run python run_novel_generation.py --help
```

CLI 适合：

- 自动化脚本
- 调试生成流程
- 手动恢复长篇暂停任务
- 验证参数与运行合同

## 5. 首次使用

### 5.1 创建项目

在 Streamlit 左侧栏填写：

- 标题
- 作者
- 题材
- 计划章节数
- 大纲
- 世界观
- 人物设定

配置会写入：

- `lib/knowledge_base/config/project_<project_id>.json`

项目目录会创建为：

- `lib/knowledge_base/novels/<title>_<project_id>/`

其中 `outline`、`world_setting`、`character_intro` 允许留空，系统会尝试自动补全。

### 5.2 设置写作参数

当前 UI 和 CLI 都支持以下参数透传：

- `style`
- `style_preset`
- `perspective`
- `narrative_mode`
- `pace`
- `dialogue_density`
- `prose_style`
- `world_building_density`
- `emotion_intensity`
- `combat_style`
- `hook_strength`

可在 CLI 查询可选值：

```bash
uv run python run_novel_generation.py --show-writing-options
```

## 6. 普通章节生成

### 6.1 在 UI 中启动

“生成控制台”支持：

- 生成章节数
- 起始章节
- `Dry-run`
- 禁用自动反馈

点击“开始生成”后，系统会：

1. 创建 `runs/<run_id>/`
2. 初始化 `status.json`
3. 启动子进程执行 CLI
4. 持续更新运行状态和日志

### 6.2 在 CLI 中启动

```bash
uv run python run_novel_generation.py --load <project_id> --generate 1
```

常见变体：

```bash
uv run python run_novel_generation.py --load <project_id> --generate 5 --start 12
uv run python run_novel_generation.py --load <project_id> --generate 5 --dry-run
uv run python run_novel_generation.py --load <project_id> --generate 3 --no-auto-feedback
```

## 7. 整本长篇生成

### 7.1 目标流程

当前长篇模式支持：

- outline 审批暂停
- 每卷 volume 审批暂停
- 同一 `run_id` / `run_dir` 的恢复执行
- append-only 日志

当前**尚未**内建章节级 `chapter_review` 平滑性拦截；如果你正在推进该能力，先看当前状态评审：

- [smoothness_p0_review.md](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/docs/smoothness_p0_review.md)

### 7.2 在 UI 中启动

“生成控制台”中的“整本长篇生成”面板支持：

- `chapters_per_volume`
- `approval_mode`
- `auto_approve`

可选审批模式：

- `outline+volume`
- `outline`
- `volume`
- `none`

### 7.3 在 CLI 中启动

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --chapters-per-volume 60 \
  --approval-mode outline+volume
```

完全无人值守：

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --chapters-per-volume 60 \
  --approval-mode none \
  --auto-approve
```

### 7.4 长篇暂停与恢复

当运行暂停时：

- `status.json.status = "paused"`
- `status.json.pending_state_path` 会指向待审批文件
- `status.json.longform_state_path` 会指向 `longform_state.v1.json`

手动恢复示例：

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --run-id <run_id> \
  --run-dir <run_dir> \
  --resume-state <pending_state_path> \
  --submit-approval approve
```

如果是大纲修订后恢复：

```bash
uv run python run_novel_generation.py \
  --load <project_id> \
  --generate-full \
  --run-id <run_id> \
  --run-dir <run_dir> \
  --resume-state <pending_state_path> \
  --submit-approval revise \
  --approval-payload /abs/path/to/payload.json
```

`approval-payload` 可包含：

- `outline`
- `world_setting`
- `character_intro`
- 或 volume 审批备注

## 8. 运行状态说明

### 8.1 常见状态

- `queued`
- `running`
- `paused`
- `succeeded`
- `failed`

### 8.2 普通章节阶段

- `init`
- `context.build`
- `chapter.generate`
- `chapter.save`
- `derivatives.sync`
- `feedback.auto`
- `finalize`

### 8.3 长篇阶段

- `outline.generate`
- `outline.review`
- `volume.plan`
- `volume.write`
- `volume.review`
- `risk.pause`
- `finalize.export`

## 9. 输出与结果查看

生成完成后主要查看：

- 章节正文：`chapters/`
- 一致性报告：`consistency_reports/`
- 情节摘要：`plot_summaries/`
- 运行状态：`runs/<run_id>/status.json`
- 运行日志：`runs/<run_id>/stdout.log`、`stderr.log`
- 普通章节结果：`generation_results.json`
- 普通章节 checkpoint：`generation_checkpoint.json`
- 长篇可恢复状态：`runs/<run_id>/longform_state.v1.json`

UI 中可直接查看：

- 当前运行状态
- ETA
- stdout/stderr tail
- 章节列表
- 章节正文与报告
- 长篇待审批节点

## 10. 验证与回归

推荐最小验证：

```bash
cd /Users/muyi/Downloads/dev/young-writer
uv run pytest lib/knowledge_base/tests -q
```

如果只验证本轮长篇和 UI 链路：

```bash
uv run pytest \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_streamlit_app.py \
  lib/knowledge_base/tests/test_run_storage.py -q
```

验证 CLI 是否暴露了新参数：

```bash
uv run python lib/knowledge_base/run_novel_generation.py --help
```

## 11. 常见问题

### 11.1 页面提示没有当前项目

先创建项目，或在左侧栏加载 `project_id` 对应项目。

### 11.2 长篇运行暂停后无法继续

优先检查：

- `status.json.pending_state_path` 是否存在
- `status.json.longform_state_path` 是否存在
- 恢复时是否复用了同一个 `run_id` 和 `run_dir`

### 11.3 只生成了部分章节

检查：

- `status.json.failed_stage`
- `status.json.error_message`
- `stdout.log`
- `stderr.log`
- 长篇模式下当前是否正处于 `outline.review` 或 `volume.review`

### 11.4 测试失败

先跑：

```bash
uv run pytest lib/knowledge_base/tests/llm/test_kimi_client.py -q
uv run pytest lib/knowledge_base/tests/film_drama/test_film_drama.py -q
```

这两组是本轮修过的高风险区域。

## 12. 推荐工作流

1. `uv sync`
2. 启动 Streamlit
3. 创建或加载项目
4. 先用普通章节生成做 1 章 smoke test
5. 再切到整本长篇生成
6. 在 outline/volume 节点审批
7. 最后执行 `uv run pytest lib/knowledge_base/tests -q` 做回归
