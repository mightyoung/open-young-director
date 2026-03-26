# 改进方案：多阶段评估门控内容生成流水线

> 基于网络最佳实践研究（AI/Agentic + 影视工业） + 现状分析，2026-03-26

---

## 一、现状与设计差距分析

### 你设计的流水线

```
大纲 → 评估 → 分卷大纲 → 章节概要 → 逐章生成
```

### 当前 `NovelCrew.kickoff()` 实际执行流程

```
OutlineCrew.generate_outline() → _write_all_chapters() 循环（无断点）
```

**缺失的关键环节**：

| 设计阶段 | 当前状态 | 差距 |
|---------|---------|------|
| **评估** | 无 | OutlineCrew 直接输出 world + plot，无任何评估节点 |
| **分卷大纲** | 无 | 只有整体 plot_data（main_strand/sub_strands），无卷层抽象 |
| **章节概要** | 无 | 章节大纲在 `_build_chapter_outline()` 运行时动态生成，无独立阶段 |
| **评估门控** | 无 | 所有章节连续写入，无暂停/人工确认机制 |
| **流水线持久化** | 内存 | 每次运行从头开始，无中间结果缓存 |

---

## 二、网络最佳实践研究

### 2.1 LangGraph 的"提示链模式"（Prompt Chaining）

> 核心引用来源：CSDN/LangGraph 官方文档

LangGraph 将复杂任务分解为线性步骤，在步骤之间引入**程序化检查点（Gate）**：

- **Gate（门控）** 作为质量审查节点，校验上一步输出是否满足特定条件
- 满足条件 → 流程继续向前
- 不满足 → 转向特定分支（重试 / 修正 / 终止）

```
[节点A] → [Gate: 检查条件] → [节点B] → [Gate] → [节点C]
                  ↓不满足                    ↓不满足
              [修正节点A']                [修正节点B']
```

### 2.2 Evaluator-Optimizer（评估者-优化者）模式

> 核心引用来源：CSDN/LangGraph 文档 — "五种核心工作流模式"

这是实现**评估阶段**的核心模式：

- **Optimizer（优化者）节点**：生成输出（大纲 / 草稿）
- **Evaluator（评估者）节点**：检验输出质量
- **如果评估不通过** → 带回反馈意见 → 重新生成（loop）

```
[OutlineAgent] → [OutlineEvaluator] → [分卷大纲生成] → [分卷大纲评估] → ...
        ↑ 不通过                               ↑ 不通过
        └──────── 反馈修正循环 ────────────────┘
```

### 2.3 Human-in-the-Loop（人工介入）

LangGraph 支持在关键节点**中断和恢复执行**，允许人工在某些阶段进行决策、验证和修正：

```
[大纲生成] → [人工审核/确认] → [分卷大纲] → [人工审核/确认] → [章节概要] → ...
```

### 2.4 现有系统参考

| 系统 | 关键特征 |
|------|---------|
| **Sudowrite** | 分阶段生成：Outline → Draft → Revision，每阶段有独立的人机交互 |
| **NovelistAI** | 多-pass 生成：先结构化大纲，再按章节生成内容 |
| **CrewAI / LangGraph** | Agent 协调模式，支持 hierarchical / sequential / parallel 流程 |

---

## 三、改进方案

### 3.1 目标流水线架构

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: 大纲生成（WorldAgent + PlotAgent）                  │
│  输出: world_data + plot_data                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: 大纲评估（OutlineEvaluator）                        │
│  检查: 世界观一致性 / 情节完整性 / Strand Weave 比例           │
│  输出: 评估报告 {passed: bool, issues: [], suggestions: []}  │
│  [Gate] 通过 → 进入分卷大纲；不通过 → 修正循环                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: 分卷大纲生成（VolumeOutlineAgent）                  │
│  将整体 plot_data 拆分为 num_volumes 个卷大纲                  │
│  输出: volume_outlines: [VolumeOutline, ...]                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: 章节概要生成（ChapterSummaryAgent）                  │
│  每个卷内生成 chapters_per_volume 个章节概要                    │
│  输出: chapter_summaries: [ChapterSummary, ...]               │
│  [Gate] 每 N 章暂停，等待人工确认（或自动通过）                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: 逐章生成                                          │
│  for each chapter_summary:                                   │
│    WritingCrew.write_chapter() → PostPass → 章节输出         │
│  [可选: 每章完成后人工审核]                                   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 新增组件清单

| 组件 | 类型 | 职责 |
|------|------|------|
| `OutlineEvaluator` | Agent | 评估大纲质量（世界观一致性、情节完整性、Strand Weave 比例） |
| `VolumeOutlineAgent` | Agent | 将整体 plot 拆分为卷大纲 |
| `VolumeOutlineCrew` | Crew | 管理分卷大纲生成流程 |
| `ChapterSummaryAgent` | Agent | 为每个章节生成概要（独立于正文生成） |
| `ChapterSummaryCrew` | Crew | 管理章节概要批量生成 |
| `EvaluationGate` | 机制 | 评估通过/失败路由逻辑，支持修正循环 |
| `PipelineState` | 状态 | 跨阶段持久化：world / plot / volume_outlines / chapter_summaries |

### 3.3 修正循环（Evaluator-Optimizer Loop）设计

```python
def _evaluate_with_retry(agent, output, context, max_retries=2):
    """评估输出，不通过则修正后重试"""
    for attempt in range(max_retries + 1):
        evaluation = agent.evaluate(output, context)
        if evaluation.passed:
            return evaluation, output
        # 修正反馈
        output = agent.revise(output, context, evaluation.feedback)
    return evaluation, output  # 最终结果（无论是否通过）
```

### 3.4 分阶段执行接口（CLI 支持）

```bash
# 分阶段执行（每阶段完成后暂停）
crewai create novel "修仙逆袭" --words 30000 --style xianxia --stage-by-stage

# 只生成到指定阶段
crewai create novel "修仙逆袭" --stop-at outline      # 停在评估前
crewai create novel "修仙逆袭" --stop-at evaluation  # 停在评估后
crewai create novel "修仙逆袭" --stop-at volume      # 停在分卷大纲后
crewai create novel "修仙逆袭" --stop-at summary      # 停在章节概要后

# 从指定阶段恢复
crewai create novel "修仙逆袭" --resume-from chapter --chapter 1
```

---

## 四、实现优先级

### P0（立即修复）

1. **添加 OutlineEvaluator Agent** — 在 OutlineCrew 后增加评估 gate
2. **实现 EvaluationGate 机制** — 支持不通过时的修正循环
3. **添加 PipelineState 持久化** — 保存 world/plot/volume_outlines/chapter_summaries

### P1（第一阶段）

4. **实现 VolumeOutlineAgent** — 将整体 plot 拆分为卷大纲
5. **实现 ChapterSummaryAgent** — 在章节生成前先生成章节概要
6. **修改 NovelCrew.kickoff()** — 将顺序执行改为分阶段可中断流程

### P2（第二阶段）

7. **CLI 支持 --stage-by-stage / --stop-at / --resume-from**
8. **人工确认接口** — 每个阶段完成后等待用户确认
9. **多卷并行生成** — VolumeOutlineAgent 支持并行

---

## 五、关键代码改动点

### 5.1 新增文件

```
src/crewai/content/novel/
├── crews/
│   └── volume_outline_crew.py      # P1
├── agents/
│   ├── outline_evaluator.py         # P0
│   ├── volume_outline_agent.py      # P1
│   └── chapter_summary_agent.py      # P1
├── pipeline_state.py                # P0: 跨阶段状态持久化
└── types/
    ├── volume_outline.py            # P1
    └── chapter_summary.py           # P1
```

### 5.2 修改 `novel_crew.py` 的 kickoff() 流程

**当前**（line 180-195）：
```python
def kickoff(self):
    outline_data = self.outline_crew.generate_outline()
    chapters = self._write_all_chapters(world_data, plot_data)
```

**改进后**：
```python
def kickoff(self, stop_at: str = None):
    # PHASE 1: 大纲生成
    outline_data = self.outline_crew.generate_outline()
    if stop_at == "outline":
        return self._pack_state(outline_data=outline_data)

    # PHASE 2: 大纲评估
    eval_result = self.outline_evaluator.evaluate(outline_data)
    if not eval_result.passed:
        outline_data = self.outline_evaluator.revise(outline_data, eval_result)
    if stop_at == "evaluation":
        return self._pack_state(outline_data=outline_data, evaluation=eval_result)

    # PHASE 3: 分卷大纲
    volume_outlines = self.volume_outline_crew.generate(outline_data["plot"])
    if stop_at == "volume":
        return self._pack_state(volume_outlines=volume_outlines)

    # PHASE 4: 章节概要
    chapter_summaries = self.chapter_summary_crew.generate(volume_outlines)
    if stop_at == "summary":
        return self._pack_state(chapter_summaries=chapter_summaries)

    # PHASE 5: 逐章生成
    chapters = self._write_all_chapters(outline_data, chapter_summaries)
    return self._pack_output(chapters)
```

### 5.3 PipelineState 持久化

```python
class PipelineState:
    """跨阶段持久化状态"""
    world_data: dict = None
    plot_data: dict = None
    volume_outlines: list = []
    chapter_summaries: list = []
    chapters: list = []

    def save(self, path: str):
        """保存到磁盘，支持从指定阶段恢复"""
        with open(path, "w") as f:
            json.dump(self.__dict__, f, default=str)

    @classmethod
    def load(cls, path: str) -> "PipelineState":
        """从磁盘加载"""
```

---

## 六、评估维度（OutlineEvaluator）

| 维度 | 检查项 | 通过条件 |
|------|--------|---------|
| 世界观一致性 | 势力/地点/力量体系无矛盾 | 无冲突警告 |
| 情节完整性 | 主线事件齐全，高潮点分布合理 | 主线事件 ≥ 5 |
| Strand Weave 比例 | Quest / Fire / Constellation | 60±10% / 25±10% / 15±10% |
| 卷结构合理性 | 每卷有独立弧线，首尾呼应 | 卷数 × 章数 ≈ target_words |
| 伏笔一致性 | Dianting 铺设/回收计划 | 铺设章节 N → 回收 N+5~20 |

---

## 七、影视工业最佳实践借鉴

### 7.1 Hollywood 剧本开发流程（层层审批，每层都是 Gate）

成熟的好莱坞剧本开发流程是**多阶段审批制度**，每个阶段都需要特定的人（开发主管、制片人、执行制片）审核后才能进入下一阶段：

```
① Logline（一句话故事）
    ↓ [Gate: 开发主管审核]
② Premise/Concept（主题概念）
    ↓ [Gate: 制片人 pitch]
③ Treatment（剧情大纲/剧情概述）
    ↓ [Gate: 制片人/执行制片审核]
④ Beat Sheet（节拍表，如 Save the Cat 15 beats）
    ↓ [Gate: 内部评审]
⑤ Outline（场景大纲）
    ↓ [Gate: 绿灯会议]
⑥ First Draft（第一稿）
    ↓ [Gate: 剧本监制 notes]
⑦ Rewrite（重写）
    ↓ [Gate: 制片公司 notes]
⑧ Polish（润色/定稿）
```

**关键借鉴**：

| 阶段 | 影视工业做法 | 对应改进 |
|------|------------|---------|
| **Treatment** | 3-5页叙事概述，包含主题、角色、情节点 | 新增独立的 `Treatment` 阶段（非大纲也非正文） |
| **Beat Sheet** | Save the Cat 15 beats，明确每页对应 | 新增独立的 `BeatSheet` 阶段（15-20 个 story beats） |
| **Gate 审核** | 每阶段都有"开发主管/制片人"审核，不通过打回 | 引入 `HumanReviewGate` — 每阶段可选人工审核 |
| **Notes 反馈** | 剧本总监/制片公司给 notes，编剧据此重写 | `EvaluatorAgent` 给出 `suggestions`，进入修正循环 |

### 7.2 Save the Cat Beat Sheet（15 Beats）— 可作为 BeatSheet 阶段标准

Blake Snyder 的 Save the Cat 是 Hollywood 工业级标准节拍表，在 Netflix、Amazon、主流制片公司广泛使用：

| Beat # | 名称 | 典型页码 | 内容 |
|--------|------|---------|------|
| 1 | Opening Image | Page 1 | 开场画面，定调 |
| 2 | Theme Stated | Page 5 | 主题呈现 |
| 3 | Set-Up | Pages 1-10 | 世界观和角色建立 |
| 4 | Catalyst | Page 12 | 催化事件 |
| 5 | Debate | Pages 12-25 | 辩论/内心挣扎 |
| 6 | Break Into Two | Page 25 | 进入第二幕 |
| 7 | B Story | Page 30 | 副线故事（通常是爱情线） |
| 8 | Fun and Games | Pages 30-55 | 探索世界、承诺卖点 |
| 9 | Midpoint | Page 55 | 伪结局/真激励（分水岭） |
| 10 | Bad Guys Close In | Pages 55-75 | 反派逼近 |
| 11 | All Is Lost | Page 75 | 最低点 |
| 12 | Dark Night of the Soul | Pages 75-85 | 灵魂黑夜 |
| 13 | Break Into Three | Page 85 | 进入第三幕 |
| 14 | Finale | Pages 85-110 | 最终对决 |
| 15 | Final Image | Page 110 | 终幕画面 |

**关键借鉴**：
- Beat Sheet 阶段**比 Outline 更细**，它精确定义了每个 story beat 的叙事功能
- 每个 beat 有关键事件（如 Catalyst、Midpoint、All Is Lost），这些是天然的质量检查点
- 在小说中，每个 beat 可以对应**章节内的节拍**，而不是整本书的事件

### 7.3 TV Writers Room 模式 — 分集开发流程

TV 剧本开发使用 **Writers Room** 模式（美剧标准流程）：

```
① 整体 pitch（全季概念）
    ↓
②  Breaking the Story（全季分集大纲）
    - 每集用 index card（卡片）表示
    - Track A / B / C Story 在各集的分叉
    ↓
③ Per-Episode Outline（单集详细大纲）
    ↓
④ Episode Draft（单集初稿）
    ↓
⑤ Room Notes（编剧室笔记）
    ↓
⑥ Rewrite + Polishing
```

**关键借鉴**：
- **Breaking the Story** 阶段用卡片法把全季事件分解到各集 — 对应我们的"章节概要"阶段
- 编剧室集体讨论（room）对每个决定有记录 — 对应我们的 `EvaluationGate` + `suggestions`
- **Track Story**（A/B/C Story 分别对应主线/副线/伏笔线）— 对应我们的 Strand Weave（Quest/Fire/Constellation）

### 7.4 AI Writers Room 工具 — PITCH → VARIANTS → DIRECT → SHIP

一个 AI Writers Room 产品（writersroom.online）的工作流：

```
PITCH    → 提出创意想法（单句/段落）
   ↓
VARIANTS → 生成多个变体（safe / bold / wildcard）
   ↓
DIRECT   → 选择最佳方案，进入详细指导
   ↓
SHIP    → 输出最终内容
```

**关键借鉴**：
- **VARIANTS 阶段**生成多版本备选 — 对应我们可以在每个阶段生成多个候选方案，供选择
- **分阶段生成**而非一次性生成全部 — 每个阶段专注解决一个问题

---

## 八、改进方案 v2（含影视工业最佳实践）

### 8.1 目标流水线架构 v2

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE 0: Logline / Premise                                │
│  生成核心概念、一句话故事、主题                                │
│  [Gate] 人工审核：概念是否有足够的戏剧张力？                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 1: 大纲生成（WorldAgent + PlotAgent）                │
│  输出: world_data + plot_data                                │
│  [Gate] 评估: 世界观一致性 / 情节完整性 / Strand Weave 比例  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 2: Treatment 生成                                    │
│  将 plot_data 扩展为 3-5 页叙事概述（含角色弧线、高潮设计）   │
│  [Gate] 评估: 叙事逻辑 / 角色弧线完整性                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 3: Beat Sheet 生成                                  │
│  基于 Save the Cat 15 beats 格式，生成完整节拍表            │
│  [Gate] 评估: 节拍分布 / 高潮位置 / 转折点                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 4: 分卷大纲生成（VolumeOutlineAgent）                │
│  将 Beat Sheet 按卷结构分组，生成卷大纲                     │
│  [Gate] 评估: 卷弧线独立性 / 卷间呼应                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 5: 章节概要生成（ChapterSummaryAgent）              │
│  每个章节生成独立概要（含节拍点、主要事件、POV）              │
│  [Gate] 评估: 章节节拍对齐 / 伏笔铺垫                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGE 6: 逐章生成                                        │
│  for each chapter_summary:                                  │
│    WritingCrew → PostPass → 章节输出                       │
│  [Gate] 每 N 章后暂停，等待人工审核                         │
└─────────────────────────────────────────────────────────────┘
```

### 8.2 核心新增组件

| 组件 | 类型 | 职责 |
|------|------|------|
| `TreatmentAgent` | Agent | 生成独立 Treatment（3-5页叙事概述） |
| `BeatSheetAgent` | Agent | 基于 Save the Cat 15 beats 生成节拍表 |
| `HumanReviewGate` | 机制 | 每阶段可选人工审核，支持通过/打回/修正 |
| `MultiVariantGenerator` | 机制 | 在关键阶段生成多版本备选 |

### 8.3 与原方案 v1 的差异

| 对比项 | v1 方案 | v2 方案（+ 影视工业） |
|--------|---------|----------------------|
| Stage 0 | 无 | 新增 Logline/Premise 阶段 |
| Treatment | 无 | 新增独立 Treatment 阶段 |
| Beat Sheet | 无 | 新增 Save the Cat 15 beats 节拍表 |
| 人工 Gate | 仅可选 | 每阶段均可配置人工审核 |
| 多版本备选 | 无 | VARIANTS 机制（每阶段可选生成多版本） |
| 章节概要 | 有但不独立 | 有，且与 Beat Sheet 对齐 |

---

## 九、总结

核心改进：**将一次性的 `kickoff()` 改为分阶段可中断的流水线**，借鉴 Hollywood 多阶段审批制度（Logline → Treatment → Beat Sheet → Outline → Draft → Rewrite → Polish），在每个阶段之间通过 Evaluator-Optimizer 模式进行质量门控，评估不通过时触发修正循环。

新增 **Treatment** 和 **Beat Sheet** 两个独立阶段（来自影视工业标准流程），使大纲层与正文写作层之间有更丰富的中间产物层，既便于质量把控，也便于人工审核和修正。

这与 LangGraph 的提示链模式 + 评估者-优化者模式一致，也符合 Sudowrite、好莱坞 WGA 编剧室流程等商业/工业最佳实践。
