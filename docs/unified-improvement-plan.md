# crewAI 内容生成系统 - 统一改进方案

> 合并自: implementation-plan-v2.md + TASK_PLAN.md + 研究发现
> 状态: 整合完成
> 日期: 2026-03-26

---

## 一、现状评估：已实现 vs 未实现

### 已实现（可直接使用）

| 组件 | 文件 | 状态 |
|------|------|------|
| ReviewPipeline 3阶段 | `review/review_pipeline.py` | ✅ critique→revise→polish |
| EntityMemory | `memory/entity_memory.py` | ✅ 存在但**未集成** |
| ContinuityTracker | `memory/continuity_tracker.py` | ✅ 存在但**未集成** |
| NovelOrchestratorCrew | `adapters/novel_orchestrator_crew.py` | ✅ 适配器已就绪 |
| KnowledgeBaseAdapter | `adapters/knowledge_base_adapter.py` | ✅ 包含 outline evolution |
| OutlineEngine | `outline/outline_engine.py` | ✅ 3步顺序pipeline |
| NovelCrew | `novel/crews/novel_crew.py` | ✅ 4 sub-crews编排 |

### 未实现 / 关键缺口

| 缺口 | 严重程度 | 说明 |
|------|----------|------|
| **EntityMemory 未集成到 WritingCrew** | 🔴 P0 | 角色状态追踪存在但未注入写作流程 |
| **ContinuityTracker 未集成** | 🔴 P0 | 时间线冲突检测存在但未使用 |
| **章节草稿未持久化** | 🔴 P0 | 每阶段产物（artifact）无中间存储 |
| **Per-chapter PostPass 缺失** | 🟡 P1 | 章节写完立即 critique 的流程未闭环 |
| **Global PostPass 缺失** | 🟡 P1 | 全书完成后无全局一致性检查 |
| **_is_location_consistent stub** | 🟡 P1 | ContinuityTracker 位置一致性始终返回 True |
| **多章节并行风险** | 🟡 P1 | current_summary 只存 title，无 actual content |

---

## 二、外部研究关键发现

### 2.1 waoowaoo 分阶段 Pipeline（高借鉴价值）

```
Phase1 (并行) → Phase2-Cinematography (并行) → Phase2-Acting (并行) → Phase3 (细节)
   10-40%              40-55%                    55-70%                 70-100%
```

- **mapWithConcurrency()**: 控制同一阶段内并发数
- **artifact 中间持久化**: 每个 phase 完成后保存，用于断点续传和重试
- **runStepWithRetry()**: 单阶段原子重试，失败只重做当前阶段
- **mergePanelsWithRules()**: 最终合并时应用跨阶段规则

### 2.2 影视工业最佳实践（高借鉴价值）

| 阶段 | 影视术语 | 对应实现 |
|------|----------|----------|
| 拍摄中 | **Rushes/Dailies**（日片素材） | 每章节写完后立即 critique，保存中间产物 |
| 单片审查 | **A-Copy**（导演剪辑版） | Per-chapter PostPass：章节写完→立即 ReviewCrew |
| 剪辑中 | **Assembly Cut**（初剪版） | 全书章节按顺序组织 |
| 全局检查 | **PostPass**（后期通过） | 全书完成后 Global Consistency Check |
| 最终交付 | **Fine Cut + VFX + Final** | 最终润色 + 导出 |

### 2.3 多章节并行一致性方案

**问题根因**: `previous_summary = f"第{chapter_num}章: {chapter_output.title}"` 只存标题，无实际内容

**四层解决方案**（来自 AI_NovelGenerator + Stanford Generative Agents）:

1. **Story Bible（故事圣经）**:  Canonical state of all characters, locations, world rules
2. **Vector Semantic Retrieval（向量检索）**: Stanford Memory Stream pattern — when writing Chapter N, retrieve relevant facts from Chapters 1..N-1
3. **Consistency Checker（一致性检查）**: Post-generation scan for contradictions
4. **Lock-Step Parallel（分阶段并行）**: Group chapters by weave_points — 同组可并行，组间顺序写入

---

## 三、三大核心改进（优先级排序）

### 改进 1（P0）: EntityMemory + ContinuityTracker 集成到 WritingCrew

**现状**: `EntityMemory` 和 `ContinuityTracker` 已实现，但 `WritingCrew.write_chapter()` 从未调用它们

**目标**: 每次写完章节后，更新记忆并在下一章写入前检查一致性

**需要修改的文件**:

```
lib/crewai/src/crewai/content/memory/entity_memory.py
lib/crewai/src/crewai/content/memory/continuity_tracker.py
lib/crewai/src/crewai/content/novel/crews/writing_crew.py
lib/crewai/src/crewai/content/novel/crews/novel_crew.py
```

**具体改动**:

```python
# 1. WritingCrew.write_chapter() 增加记忆更新
async def write_chapter(self, context, outline):
    draft = await self._draft_agent.write(context, outline)

    # 【新增】更新实体记忆
    entity_states = self._extract_entity_states(draft)
    for state in entity_states:
        self.entity_memory.update_character(state)

    # 【新增】检查与已建立事实的一致性
    conflicts = self.entity_memory.check_conflicts(draft)
    if conflicts:
        draft = await self._revision_agent.fix_conflicts(draft, conflicts)

    # 【新增】更新连续性追踪
    self.continuity_tracker.record_chapter(draft, context.chapter_num)

    return draft

# 2. ContinuityTracker._is_location_consistent() 实现stub → 实际逻辑
def _is_location_consistent(self, location: str, chapter: int) -> bool:
    # 查询该地点在之前章节的出现情况
    previous_locations = self.get_location_history(location)
    if not previous_locations:
        return True
    # 检查时间线是否冲突（如：第3章在京城，第5章突然在千里外）
    return self._check_timeline_consistency(location, chapter)
```

### 改进 2（P0）: Per-Chapter PostPass + Artifact 持久化

**现状**: NovelCrew 按顺序写完所有章节后，最后才跑 ReviewCrew

**目标**: 每章节写完立即触发 PostPass（Rushes/Dailies 模式），并保存中间 artifact

**借鉴 waoowaoo 的 PHASE_PROGRESS 映射**:

```python
# 每章节内部的阶段进度映射（类比 waoowaoo）
CHAPTER_PHASE_PROGRESS = {
    'draft': (0, 30),      # 草稿阶段 0-30%
    'critique': (30, 50),  # 批评阶段 30-50%
    'revision': (50, 70),  # 修订阶段 50-70%
    'polish': (70, 85),    # 润色阶段 70-85%
    'postpass': (85, 100), # 终检阶段 85-100%
}

# 每阶段完成后持久化 artifact
ARTIFACT_STRUCTURE = {
    'chapter_{n}_draft': '...',           # 草稿
    'chapter_{n}_critique_result': {...}, # 批评结果
    'chapter_{n}_revision': '...',        # 修订稿
    'chapter_{n}_polished': '...',         # 润色稿
    'chapter_{n}_postpass': '...',         # 终检通过稿
}
```

**需要修改的文件**:

```
lib/crewai/src/crewai/content/novel/crews/writing_crew.py
lib/crewai/src/crewai/content/novel/crews/review_crew.py
lib/crewai/src/crewai/content/review/review_pipeline.py
lib/crewai/src/crewai/content/adapters/knowledge_base_adapter.py  # 添加 artifact 保存
```

### 改进 3（P1）: Global PostPass + 多章节并行框架

**目标**: 所有章节写完后，执行全局 PostPass（后制通过模式），并建立分阶段并行的基础架构

**Global PostPass 检查项**:

```python
# 全局一致性 PostPass
class GlobalPostPass:
    def run(self, all_chapters: list[ChapterOutput]) -> PostPassReport:
        # 1. 角色状态全局扫描（有无死亡角色在后续章节出现）
        character_deaths = self._scan_deaths(all_chapters)
        # 2. 伏笔回收检查（埋了是否回收，回收是否在合理时机）
        hook_reuse = self._check_plant_reveal(all_chapters)
        # 3. 势力/地点时间线（地点变更是否有时序支持）
        location_timeline = self._check_location_timeline(all_chapters)
        # 4. 章节间 transition 质量
        transitions = self._check_transitions(all_chapters)
        return PostPassReport(
            character_issues=character_deaths,
            hook_issues=hook_reuse,
            location_issues=location_timeline,
            transition_issues=transitions,
            overall_score=self._compute_score(...)
        )
```

**分阶段并行框架**（为未来准备，当前保持顺序执行）:

```python
# Chapter Grouping by Weave Points
def group_chapters_by_weave_points(chapters: list[ChapterOutline]) -> list[list[int]]:
    """
    同组章节可并行写（共享 weave_point），
    组间必须顺序写（lock-step）以保证连戏。
    """
    groups = []
    current_group = []
    for ch in chapters:
        if ch.has_major_weave_point:
            if current_group:
                groups.append(current_group)
            current_group = [ch.number]
        else:
            current_group.append(ch.number)
    if current_group:
        groups.append(current_group)
    return groups

# 未来并行调用（当前为顺序，保持兼容性）
async def write_chapter_group(group: list[int], context, outlines):
    # mapWithConcurrency(group, max_concurrent=3)
    results = await asyncio.gather(*[
        write_chapter(ctx, outline) for ctx, outline in zip(context, outlines)
    ])
    return results
```

---

## 四、改进后的 Pipeline 流程图

```
NovelCrew.kickoff()
│
├── WorldCrew (构建世界观)
│   └── WorldOutput → 存入 Story Bible
│
├── OutlineCrew (生成大纲)
│   ├── PlotStrands 定义
│   └── ChapterOutlines (含 weave_points)
│
└── Per-Chapter Loop (for each chapter):
    │
    ├── [Artifact: chapter_{n}_outline saved]
    │
    ├── WritingCrew.write_chapter()
    │   │
    │   ├── DraftAgent → draft
    │   │   └── [Artifact: chapter_{n}_draft saved]
    │   │   【EntityMemory】 检查角色状态冲突
    │   │
    │   ├── ReviewCrew (Per-Chapter PostPass)
    │   │   ├── CritiqueAgent → issues
    │   │   ├── 【ContinuityTracker】 记录本章实体状态
    │   │   ├── RevisionAgent → revised_draft
    │   │   └── PolishAgent → polished_draft
    │   │   └── [Artifact: chapter_{n}_postpass saved]
    │   │
    │   └── Output: ChapterOutput (content + review_results)
    │
    └── [Chapter写入完成，EntityMemory 更新]
        【previous_summary = actual_content，不是只存 title】
│
├── [All Chapters Done]
│
├── GlobalPostPass (全局 PostPass)
│   ├── 角色死亡一致性扫描
│   ├── 伏笔回收时机检查
│   ├── 地点时间线验证
│   └── Transition 质量评估
│   └── [Artifact: global_postpass_report saved]
│
└── Final Output: NovelOutput (full novel + reports)
```

---

## 五、实施路线图

### Phase A（1-2天）: EntityMemory 集成
**目标**: 将 EntityMemory 和 ContinuityTracker 接入 WritingCrew

| 任务 | 文件 | 行动 |
|------|------|------|
| A1 | `entity_memory.py` | `update_character()` 实际实现（非 stub） |
| A2 | `continuity_tracker.py` | `_is_location_consistent()` 实现（非 stub） |
| A3 | `writing_crew.py` | `write_chapter()` 调用 EntityMemory 更新 + 一致性检查 |
| A4 | `novel_crew.py` | `_write_all_chapters()` 传递 entity_memory 和 continuity_tracker |

### Phase B（1-2天）: Per-Chapter PostPass + Artifact
**目标**: 每章节写完立即 critique，保存中间产物

| 任务 | 文件 | 行动 |
|------|------|------|
| B1 | `writing_crew.py` | `write_chapter()` → draft → critique → revise → polish → return |
| B2 | `review_crew.py` | 适配为 Per-Chapter PostPass 模式（非全书） |
| B3 | `knowledge_base_adapter.py` | 增加 artifact 持久化（save/load chapter artifacts） |
| B4 | `novel_crew.py` | 每章节后触发 PostPass，不是全书完成后 |

### Phase C（2-3天）: Global PostPass + 准备并行框架
**目标**: 全局一致性检查 + 分阶段并行的基础代码

| 任务 | 文件 | 行动 |
|------|------|------|
| C1 | `review/review_pipeline.py` | 新增 `GlobalPostPass` 类 |
| C2 | `novel_crew.py` | 全书完成后调用 GlobalPostPass |
| C3 | `outline/outline_engine.py` | 添加 `group_chapters_by_weave_points()` |
| C4 | `writing_crew.py` | 添加 `write_chapter_group()` 预留并行接口 |

---

## 六、不需要做的事（基于研究确认）

以下在研究中被提出但经分析确认**暂不需要**：

| 提案 | 结论 | 原因 |
|------|------|------|
| 多章节同时并行写 | 暂缓 | 引入 race condition，当前顺序执行+per-chapter PostPass 已足够 |
| FLM_DRAMA 机制 | 不存在 | 代码库中无此实现，无需对接 |
| 全新 ReviewPipeline | 复用已有 | `review/review_pipeline.py` 已有 critique→revise→polish 3阶段 |
| 重写 OutlineEngine | 复用已有 | `outline/outline_engine.py` 3步顺序 pipeline 足够 |

---

## 七、关键文件修改清单

```
lib/crewai/src/crewai/content/
├── memory/
│   ├── entity_memory.py          # A1: update_character() 实现
│   └── continuity_tracker.py     # A2: _is_location_consistent() 实现
├── novel/crews/
│   ├── writing_crew.py          # A3, B1, C3: 集成 + Per-Chapter PostPass + 并行接口
│   ├── review_crew.py           # B2: 适配 Per-Chapter 模式
│   └── novel_crew.py            # A4, B4, C2: 调用链更新 + GlobalPostPass
├── review/
│   └── review_pipeline.py        # C1: 新增 GlobalPostPass 类
├── outline/
│   └── outline_engine.py         # C3: group_chapters_by_weave_points()
└── adapters/
    └── knowledge_base_adapter.py # B3: artifact 持久化
```

---

*整合版本: v1.0 | 来源: implementation-plan-v2.md + TASK_PLAN.md + waoowaoo研究 + 影视工业研究 + 多章节并行研究*
