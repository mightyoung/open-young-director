# young-writer 部署指南

本指南面向维护者，说明如何在本地部署当前版本的 `knowledge_base` 工作台，并验证部署结果。

## 1. 部署目标

当前推荐部署模式只有一种：

- 单机本地部署
- Streamlit 作为操作界面
- CLI 子进程作为实际执行入口
- 文件系统作为运行状态和恢复状态存储

## 2. 部署前检查

在仓库根目录执行：

```bash
cd /Users/muyi/Downloads/dev/young-writer
uv sync
```

确认以下文件存在：

- [streamlit_app.py](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/streamlit_app.py)
- [run_novel_generation.py](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/run_novel_generation.py)
- [longform_run.py](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/services/longform_run.py)
- [longform_run_contract.md](/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/docs/longform_run_contract.md)

如果走 API 模式，准备：

```bash
export KIMI_API_KEY=your_key
```

## 3. 启动步骤

```bash
cd /Users/muyi/Downloads/dev/young-writer/lib/knowledge_base
uv run streamlit run streamlit_app.py
```

启动后验证页面具备以下能力：

- 创建/加载项目
- 写作参数保存
- 普通章节生成
- 整本长篇生成
- 暂停节点审批
- 运行日志查看

## 4. 运行合同检查

普通生成启动后，应看到：

- `novels/<title>_<project_id>/runs/<run_id>/status.json`
- `stdout.log`
- `stderr.log`

长篇生成启动后，还应看到：

- `longform_state.v1.json`
- 审批暂停时生成 `.novel_pipeline_*_pending.json`

恢复运行时必须保持：

- 相同 `run_id`
- 相同 `run_dir`
- append-only 日志

## 5. 部署后验证

推荐完整回归：

```bash
cd /Users/muyi/Downloads/dev/young-writer
uv run pytest lib/knowledge_base/tests -q
```

当前基线结果应为：

- `158 passed`

额外 smoke check：

```bash
uv run python lib/knowledge_base/run_novel_generation.py --help
uv run python -m py_compile \
  lib/knowledge_base/run_novel_generation.py \
  lib/knowledge_base/streamlit_app.py \
  lib/knowledge_base/services/longform_run.py \
  lib/knowledge_base/llm/kimi_client.py
```

## 6. 故障排查

如果 Streamlit 能启动但任务不运行：

- 检查 `runs/<run_id>/stderr.log`
- 检查 `status.json.error_message`
- 检查是否存在 `KIMI_API_KEY`

如果长篇运行无法恢复：

- 检查 `pending_state_path`
- 检查 `longform_state_path`
- 检查恢复命令是否复用相同 `run_id/run_dir`

如果回归失败：

- 先单独跑 `test_kimi_client.py`
- 再跑 `test_film_drama.py`
- 最后跑全量 `knowledge_base/tests`
