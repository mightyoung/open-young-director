---
name: skill_index
version: 1.1.0
description: 小说生成主线技能索引
---

# Skill Index

当前仅保留小说生成主体流程相关技能。

## 可用技能

| 技能 | 版本 | 描述 |
|------|------|------|
| [novel_generation](./novel_generation.md) | 1.0.0 | 将规划输入生成为小说正文 |
| [quality_check](./quality_check.md) | 1.0.0 | 对小说正文进行质量评估和门禁检查 |

## 主线关系

```text
NovelOrchestrator
├── novel_generation
└── quality_check
```
