# 影视剧模式多智能体小说生成系统 - 分步实施方案

> **版本**: v1.0
> **日期**: 2026-03-22
> **依赖设计**: `docs/film_drama_mode_design.md`

---

## 概述

### 目标
将现有单Director模式升级为**影视剧模式**，实现：
- 专业编剧团队分工 (Director + NovelWriter + SubAgents)
- 角色专属视角演绎
- 并行子代理执行
- 严格的大纲遵循验证

### 预期收益
| 指标 | 当前 | 目标 |
|------|------|------|
| 大纲遵循率 | ~70% | ≥95% |
| 角色个性化 | 无 | 每个主要角色有专属视角 |
| 叙事视角 | 混乱 | 第三人称限知 |
| 生成质量 | 流水账风险 | 专业分工互补 |

---

## Phase 0: 基础设施准备 (预计 1 天)

### 0.1 创建基础类和数据结构

**目标**: 创建支持新架构的基础组件

**文件变更**:
```
agents/
├── __init__.py                    # 导出新类
├── novel_orchestrator.py          # [NEW] 总指挥类
├── director_agent.py               # [NEW] 导演Agent
├── novel_writer_agent.py          # [NEW] 小说家Agent
├── character_sub_agent.py         # [NEW] 角色Agent基类
├── sub_agent_pool.py              # [NEW] 子代理池
├── data_structures.py             # [NEW] 数据结构定义
└── prompts/
    ├── __init__.py
    ├── director_prompts.py        # [NEW] 导演Prompt模板
    ├── novel_writer_prompts.py    # [NEW] 小说家Prompt模板
    └── character_prompts.py       # [NEW] 角色Prompt模板
```

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P0.1 | 创建 `data_structures.py` - 定义所有数据结构 | - | `PlotOutline`, `CharacterBible`, `ChapterContext`, `AssembledPlot` |
| P0.2 | 创建 `sub_agent_pool.py` - 子代理生命周期管理 | P0.1 | `SubAgentPool` 类 |
| P0.3 | 创建 `character_sub_agent.py` - 角色Agent基类 | P0.1, P0.2 | `CharacterSubAgent` 基类 |
| P0.4 | 创建 `director_agent.py` - 导演Agent | P0.1 | `DirectorAgent` 类 |
| P0.5 | 创建 `novel_writer_agent.py` - 小说家Agent | P0.1 | `NovelWriterAgent` 类 |
| P0.6 | 创建 `novel_orchestrator.py` - 总指挥 | P0.2-P0.5 | `NovelOrchestrator` 主流程类 |
| P0.7 | 创建 Prompt 模板文件 | P0.4-P0.5 | 角色/Director/NovelWriter 的系统提示词 |
| P0.8 | 更新 `__init__.py` 导出 | P0.1-P0.6 | 统一导出接口 |

**验收标准**:
- [ ] 所有数据结构可以序列化/反序列化
- [ ] SubAgentPool 可以派生和释放 Agent
- [ ] 可以通过 `from agents import NovelOrchestrator` 导入

---

## Phase 1: 最小可行版本 MVP (预计 2 天)

### 1.1 核心流程实现

**目标**: 实现串行版本，验证架构正确性

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P1.1 | 实现 `DirectorAgent.create_plot_outline()` | P0.4 | 从大纲生成剧本主干 |
| P1.2 | 实现 `DirectorAgent.determine_cast()` | P1.1 | 确定本章出场角色 |
| P1.3 | 实现 `DirectorAgent.create_character_bible()` | P1.2 | 为角色生成手册 |
| P1.4 | 实现 `CharacterSubAgent.act()` | P0.3 | 角色演绎方法 |
| P1.5 | 实现 `DirectorAgent.orchestrate_characters()` 串行版 | P1.3, P1.4 | 角色编排 (先串行验证) |
| P1.6 | 实现 `DirectorAgent.assemble_scene()` | P1.5 | 整合场景输出 |
| P1.7 | 实现 `NovelWriterAgent.novelize()` | P0.5 | 将骨架转化为小说正文 |
| P1.8 | 实现 `NovelOrchestrator.generate_chapter()` 主流程 | P1.6, P1.7 | 串联 6 步生成流程 |

### 1.2 集成测试

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P1.9 | 编写 ch001 生成测试 | P1.8 | 测试脚本验证完整流程 |
| P1.10 | 人工评估生成质量 | P1.9 | 质量评估报告 |

**验收标准**:
- [ ] ch001 可以成功生成
- [ ] 角色演绎有差异 (韩林 vs 柳如烟)
- [ ] 输出是小说格式，非剧本格式

---

## Phase 2: 并行执行优化 (预计 1 天)

### 2.1 并行化改造

**目标**: 角色演绎并行执行，提升效率

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P2.1 | 实现 `ParallelExecutor` 工具类 | P1.5 | 并行执行器 |
| P2.2 | 改造 `orchestrate_characters()` 为异步并行 | P2.1 | asyncio 并发执行 |
| P2.3 | 添加 Semaphore 限流 | P2.2 | 避免同时调用过多 LLM |
| P2.4 | 性能对比测试 (串行 vs 并行) | P2.3 | 性能报告 |

**验收标准**:
- [ ] 3个角色并行执行耗时 < 串行耗时的 60%
- [ ] 无 race condition 或数据竞争
- [ ] 错误处理: 单个角色失败不影响整体

---

## Phase 3: 大纲验证循环 (预计 1 天)

### 3.1 验证与反馈

**目标**: 集成 OutlineEnforcer，实现自动rewrite循环

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P3.1 | 集成 `OutlineEnforcer.enforce()` 到流程 | P1.8 | 验证步骤 |
| P3.2 | 实现验证失败时的 rewrite 触发 | P3.1 | 循环逻辑 |
| P3.3 | 实现大纲问题 vs 生成问题的判定 | P3.2 | `evaluate_failure_type()` |
| P3.4 | 实现最大重写次数限制 | P3.3 | 防死循环 |
| P3.5 | 测试验证循环 (故意注入错误) | P3.4 | 测试报告 |

**验收标准**:
- [ ] 缺少关键事件的章节会被标记并rewrite
- [ ] 境界不一致会被检测并修正
- [ ] 最多重写 3 次后强制通过或放弃

---

## Phase 4: Prompt 优化 (预计 1 天)

### 4.1 角色差异化

**目标**: 精细化各角色Prompt，实现真正的个性化

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P4.1 | 编写韩林角色Prompt | P1.4 | 沉默倔强、内心傲骨 |
| P4.2 | 编写柳如烟角色Prompt | P1.4 | 傲慢嘲讽、退婚执行者 |
| P4.3 | 编写魔帝残魂Prompt | P1.4 | 威严神秘、导师指引 |
| P4.4 | 编写太虚宗主Prompt | P1.4 | 公正严肃、引路人 |
| P4.5 | 编写 Director 系统Prompt | P4.1-P4.4 | 导演调度能力 |
| P4.6 | 编写 NovelWriter 系统Prompt | P4.5 | 文学化能力 |
| P4.7 | 人工评估角色差异 | P4.6 | 对比测试报告 |

**验收标准**:
- [ ] 韩林视角: 内心独白为主，被动反应
- [ ] 柳如烟视角: 嘲讽轻蔑，主动施压
- [ ] 魔帝残魂视角: 俯视苍生，暗示性语言
- [ ] 三个视角的文字有明显差异

---

## Phase 5: 世界观一致性 (预计 1 天)

### 5.1 修仙体系强化

**目标**: 避免境界、功法等描述前后矛盾

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P5.1 | 创建 `WorldContext` 数据结构 | P0.1 | 世界观定义 |
| P5.2 | 实现 `WorldContextManager` | P5.1 | 境界等级表、功法列表 |
| P5.3 | 在角色演绎时注入 WorldContext | P5.2 | 角色知道自己的境界 |
| P5.4 | 实现 `RealmConsistencyChecker` | P5.3 | 境界递进验证 |
| P5.5 | 测试境界一致性 | P5.4 | 验证报告 |

**验收标准**:
- [ ] 同一角色境界在前后章节一致
- [ ] 跨章节的境界对比合理
- [ ] 不会出现"炼气期主角打败金丹期敌人"的bug

---

## Phase 6: 记忆与连续性 (预计 1 天)

### 6.1 跨章节记忆

**目标**: 前一章的关键状态影响后续章节

**具体任务**:

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P6.1 | 实现 `ChapterMemory` 存储结构 | P0.1 | 章节状态快照 |
| P6.2 | 实现角色状态继承 | P6.1 | 从前一章加载状态 |
| P6.3 | 实现关系演化 | P6.2 | 韩林和柳如烟的关系变化 |
| P6.4 | 实现悬念钩子记忆 | P6.3 | 记住上一章的悬念 |
| P6.5 | 测试跨章节连续性 | P6.4 | 连续生成 ch001-ch005 |

**验收标准**:
- [ ] ch003 提到的事件可以追溯到 ch001
- [ ] 角色状态 (如受伤、获得宝物) 可以延续
- [ ] 悬念"梦中魔帝"在后续章节有呼应

---

## Phase 7: 高级特性 (可选)

### 7.1 性能优化

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P7.1 | 实现 Agent 结果缓存 | P2.3 | 相似场景复用 |
| P7.2 | 实现 Token 预算控制 | P7.1 | 控制单章最大消耗 |
| P7.3 | 实现生成进度恢复 | P7.2 | 中断后继续 |

### 7.2 质量增强

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P7.4 | 实现多版本生成对比 | P6.5 | A/B 测试 |
| P7.5 | 实现用户反馈学习 | P7.4 | 根据评分调整 |
| P7.6 | 实现自动Prompt优化 | P7.5 | 基于历史反馈迭代 |

### 7.3 高级功能

| 任务ID | 任务 | 依赖 | 产出 |
|--------|------|------|------|
| P7.7 | 实现支线剧情生成 | P6.5 | 主角外的视角 |
| P7.8 | 实现闪回/时间跳跃 | P7.7 | 非线性叙事 |
| P7.9 | 实现多结局分支 | P7.8 | 读者选择 |

---

## 实施时间线

```
Week 1
├── Day 1: Phase 0 (基础设施)
├── Day 2: Phase 1 (MVP核心流程)
├── Day 3: Phase 1 (集成测试) + Phase 2 (并行优化)
├── Day 4: Phase 3 (大纲验证) + Phase 4 (Prompt优化)
└── Day 5: Phase 5 (世界观一致性) + Phase 6 (记忆)

Week 2
├── Day 6-7: Phase 6 续 + 调优
├── Day 8-9: Phase 7 (高级特性)
└── Day 10: 整体测试 + 文档

总工期: 约 10 个工作日 (2 周)
```

---

## 风险与缓解

| 风险 | 概率 | 影响 | 缓解方案 |
|------|------|------|----------|
| LLM 调用成本过高 | 高 | 中 | 严格限制重写次数，并行执行 |
| 角色Prompt效果差异不明显 | 中 | 高 | 精细化设计，人工评估 |
| 并行执行导致乱序 | 低 | 高 | Semaphore 限流，顺序收集 |
| 大纲验证过于严格 | 中 | 低 | 可调节阈值，允许放行 |
| 上下文过长超出限制 | 高 | 中 | 及时压缩和摘要 |

---

## 成功指标

| 阶段 | 指标 | 目标值 |
|------|------|--------|
| Phase 1 | ch001 生成成功率 | 100% |
| Phase 2 | 并行 vs 串行加速比 | ≥2x |
| Phase 3 | 大纲遵循率 | ≥90% |
| Phase 4 | 角色差异评分 (人工) | ≥4/5 |
| Phase 5 | 境界一致性 | 100% |
| Phase 6 | 跨章节状态连续性 | 100% |

---

## 附录

### A. 参考项目

1. **deer-flow** (`/Users/muyi/Downloads/dev/deer-flow/`)
   - Lead Agent 编排模式
   - SubagentLimitMiddleware
   - Prompt 模板化

2. **mightoung** (`/Users/muyi/Downloads/dev/python/mightyoung/`)
   - AgentFactory 动态Agent管理
   - AgentConfigManager 配置管理
   - Session 记忆持久化

### B. 现有组件 (保持兼容)

| 组件 | 位置 | 用途 |
|------|------|------|
| `OutlineLoader` | `agents/outline_loader.py` | 读取大纲 |
| `OutlineEnforcer` | `agents/outline_enforcer.py` | 验证内容 |
| `novel_generator.py` | 根目录 | 原有生成器 (Phase 7后可能废弃) |

### C. 文件变更清单

```
agents/
├── __init__.py                    # 更新: 导出新类
├── novel_orchestrator.py          # [NEW]
├── director_agent.py              # [NEW]
├── novel_writer_agent.py         # [NEW]
├── character_sub_agent.py        # [NEW]
├── sub_agent_pool.py             # [NEW]
├── data_structures.py             # [NEW]
├── prompts/                      # [NEW]
│   ├── __init__.py
│   ├── director_prompts.py
│   ├── novel_writer_prompts.py
│   └── character_prompts.py
├── outline_loader.py              # [保持]
├── outline_enforcer.py           # [保持]
└── feedback_accumulator.py      # [NEW, 原计划 Task #35]
```
