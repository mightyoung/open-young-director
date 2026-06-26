# young-writer 部署与使用手册

本手册覆盖当前 `knowledge_base` 工作台的本地部署、运行入口、长篇生成流程和常见排查方式。

## 1. 适用范围

当前交付形态是单机、本地、单用户工作台：

- UI 入口：[`../streamlit_app.py`](../streamlit_app.py)
- CLI 入口：[`../run_novel_generation.py`](../run_novel_generation.py)
- 长篇运行合同：[`longform_run_contract.md`](./longform_run_contract.md)

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
cd /path/to/young-writer
uv sync
```

如果只在 `knowledge_base` 子目录工作：

```bash
cd /path/to/young-writer/lib/knowledge_base
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
cd /path/to/young-writer/lib/knowledge_base
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
cd /path/to/young-writer/lib/knowledge_base
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
- 章节级 `chapter_review` 质量闸门暂停
- 同一 `run_id` / `run_dir` 的恢复执行
- append-only 日志

当前 chapter review 链路会复用既有 consistency report / anti-drift 闭环；如果你正在推进或排查该能力，可结合以下文档一起看：

- [`smoothness_p0_review.md`](./smoothness_p0_review.md)
- [`longform_run_contract.md`](./longform_run_contract.md)

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

### 7.5 卷级 guidance 继承与章节复核

长篇模式下，卷级审批可以写入结构化 guidance payload；当前合同里的核心字段包括：

- `must_recover`
- `relationship_focus`
- `must_avoid`
- `tone_target`
- `goal_lock`
- `new_setting_budget`
- `anti_drift_notes`
- `extra_notes`

使用上要注意三条规则：

1. `next_volume_guidance_payload` 才是结构化上游真源，`status.json.queued_volume_guidance_payload` 只是镜像给 UI 读。
2. `goal_lock` 一旦存在，就应该作为章节 prompt 的稳定锚点；one-shot `chapter_guidance` 只能追加，不能覆盖卷级目标锁。
3. 章节摘要只有在质量闸门确认正文也围绕 `goal_lock` 推进后，才应该晋升为下游 `previous_summary`。

当章节未通过质量闸门时，运行会暂停到 `chapter.review`。Review payload 至少应暴露：

- `chapter_number` / `title`
- `summary`
- `issue_types`
- `blocking_issues`
- `anti_drift_details`
- `warning_issues`
- `semantic_review`
- `chapter_intent_contract`
- `rewrite_plan`
- `rewrite_attempted` / `rewrite_succeeded` / `rewrite_history`

如果出现“摘要看起来对，但正文没围绕目标推进”的假继承问题，优先在 `anti_drift_details` 中查 `goal_lock`、命中词、对齐 verdict 和相关证据窗口。

当前 Streamlit review UI 也会直接消费这些结构化字段：

- `warning_issues`：warning-only 语义告警，提醒本章虽然未必触发新的 blocking gate，但仍可能有语义掉锚风险
- `semantic_review.issues[]`：结构化语义复核条目，便于按 category 看风险来源
- `chapter_intent_contract`：生成前执行合同，帮助操作者判断“计划动作”和“目标锁”是否一致
- `rewrite_plan.must_keep / fixes / success_criteria`：结构化重写方案，优先参考这一层，而不是只看拼接后的 `rewrite_guidance`
- `rewrite_plan.schema_version / strategy / operations[]`：机器可消费的 patch 层，描述“在哪个阶段、针对哪个目标、执行什么修复动作”

当你在 `chapter_review` 中点击继续重试时，UI 现在不会自己重新拼装一套临时 guidance，而是复用 `services.longform_run.compile_chapter_rewrite_guidance`：优先从 `rewrite_plan.must_keep`、`operations[]` / `fixes`、`success_criteria` 编译出稳定的 `chapter_rewrite_guidance`，再把人工备注作为附加说明并把原始 `chapter_rewrite_plan` 一并提交给恢复链路。

当运行暂停到 `volume.review` 时，review payload 除卷摘要外，还应暴露：

- `cross_volume_registry`
- `cross_volume_registry_summary`

其中 `cross_volume_registry` 当前包含三类跨卷状态：

- `unresolved_goals`
- `open_promises`
- `dangling_settings`

UI 允许直接编辑这三类字段；每行一条。若某个 bucket 留空并继续提交，后端会将其视为显式清空，而不是“保持旧值不变”。

当前 `Longform Control Panel` 还会额外展示最近几次 `approval_history` 轨迹，按 checkpoint / action / payload 摘要回放最近审批动作，方便操作者快速确认：

- 最近一次是 `approve`、`revise` 还是 `reject`
- 修改发生在 `outline_review`、`chapter_review`、`risk_review` 还是 `volume_review`
- 最近一次 chapter revise 是否带了结构化 patch 操作
- volume approve 是否提交了新的跨卷 registry / must_recover 指令

这层审批摘要不再由 Streamlit 页面各自拼接，而是统一复用 `services.longform_run` 里的 formatter helper：

- `approval_entry_detail_parts`
- `approval_entry_summary`
- `approval_history_summary`

同一层服务还负责把 `chapter_review` 的结构化 patch 方案编译成最终重试 guidance：

- `compile_chapter_rewrite_guidance`

因此 `Longform Control Panel`、最近运行列表、所选 run 预览现在看到的是同一套服务层审计摘要，而 `chapter_review` 的继续重试也会复用同一个服务层 guidance 编译规则，而不是页面内各自生成文案。

“最近运行”列表和所选运行预览现在也会同步显示最近一次审批 headline，方便在多 run 并行排查时快速识别：

- 哪个 run 刚被人工 `approve` / `revise` / `reject`
- 最近一次审批属于哪个 checkpoint
- 当前暂停 run 的最近人工动作是否和待审批节点相互矛盾

所选 run 预览还会显示最近几次审批轨迹的多行摘要，适合直接回看：

- 审批动作发生的先后顺序
- 最近几次是否从 `reject` 转成 `revise` 再恢复
- chapter revise 是否连续提交了不同 patch / notes


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
- `chapter.review`
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
- 长篇待审批节点（包括 `outline_review`、`volume_review`、`chapter_review`、`risk_review`）

## 10. 验证与回归

推荐最小验证：

```bash
cd /path/to/young-writer
uv run pytest lib/knowledge_base/tests -q
```

如果只验证本轮长篇和 UI 链路：

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  lib/knowledge_base/tests/test_streamlit_app.py -q
```

如果你正在验证 `goal_lock` 继承 / chapter review / summary promotion，至少补跑：

```bash
uv run pytest \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_longform_run.py \
  lib/knowledge_base/tests/test_run_novel_generation.py -q
```

当前已经补入一组初始的 anti-drift golden-style fixture：

- `lib/knowledge_base/tests/agents/fixtures/anti_drift_golden_cases.json`
- `lib/knowledge_base/tests/agents/test_novel_generator.py::test_consistency_report_matches_anti_drift_golden_cases`
- `lib/knowledge_base/tests/fixtures/longform_resume_golden_cases.json`
- `lib/knowledge_base/tests/test_run_novel_generation.py::test_longform_resume_golden_cases`

这组回归当前已经锁定 5 类更接近真实文本的失败模式：

- `goal_lock_false_inheritance`
- `structure_drift_risk`
- `missing_key_events`
- `world_fact_violation`
- `scene_or_timeline_disconnect`

另外，长篇恢复链路现在也有首批 golden case，覆盖：

- `outline_review -> reject` 时保持暂停
- `outline_review -> revise` 时会更新项目大纲快照并继续
- `outline_review -> approve` 时会直接用当前项目快照进入下一阶段
- 连续两次 `chapter_review -> revise` 时，最新结构化 patch guidance 会替换旧 guidance
- `chapter_review -> reject` 后保持暂停，再次 `revise` 时会恢复并消费最新结构化 guidance
- `risk_review -> reject` 时会保持在 `risk.pause`
- `risk_review -> revise` 时会清空 `risk_report_path` 并重新进入 `volume.review` 审批门
- `volume_review -> approve` 后，`cross_volume_registry` 会真实注入下一卷 `volume_guidance`
- 第二卷 `volume_review -> approve` 时，registry 的局部 merge / clear 会保留最新未清理线程
- `approval_history` 会按 checkpoint / action / payload 顺序追加，不会在 reject / revise / approve 循环里丢失历史审批轨迹

如果后续调整 `goal_lock` 对齐策略、结构漂移预算或 rewrite 证据结构，优先同步更新这份 fixture，而不是只补新的 synthetic case。

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
- 长篇模式下当前是否正处于 `outline.review`、`chapter.review`、`volume.review` 或 `risk.pause`
- `status.json.chapter_quality_report` 是否已记录本章拦截原因

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
