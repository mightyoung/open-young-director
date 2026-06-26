# 小说生成叙事驱动器执行方案

## 背景结论

当前主线已从旧 `film_drama` 体系收缩为小说生成优先架构。`NovelOrchestrator` 默认 `mode="STANDARD"`，`use_directorial_guidance=False`，`enable_npc_simulation=False`，并且 `orchestrate_scenes()` 明确返回空列表。也就是说，旧 `film_drama` 的媒体化、导演调度、角色子代理和 scene 级派生生成已不在主链路。

但旧 `film_drama` 曾承担过一类有效职责：在章节生成前提供 scene / beat / cast / tension / emotional arc / cliffhanger 等叙事驱动变量。当前系统已有 `story_input`、`goal_lock`、`chapter_graph_packet`、`story_graph` 和一致性检查，但这些更偏章节目标和状态约束，尚未完整替代旧驱动器的 scene/beat 级小说写作控制能力。

本方案目标不是恢复旧 `film_drama` 包，而是在现有小说主线内增加一个轻量、确定性、无 CrewAI 依赖的 `NarrativeDriver`。

## 目标

1. 补回小说生成过程中的叙事驱动变量。
2. 保持 `young_writer` 小说主线为唯一入口，不恢复旧 `film_drama` 媒体/短剧/导演子代理体系。
3. 不引入 CrewAI 或 agent 子框架依赖。
4. 与现有 `story_input`、导入资产、`goal_lock`、`chapter_graph_packet`、一致性检查兼容。
5. 输出可测试、可持久化、可在 prompt 中审计的 `chapter_driver_packet`。

## 非目标

1. 不恢复 `young_writer/agents/film_drama/*`。
2. 不恢复 `film_drama_scripts`、视频、播客、分镜、短剧派生资产。
3. 不恢复多角色子代理通信、导演 agent 或消息队列。
4. 不改变当前大纲、世界观、角色资产导入 schema 的主入口。
5. 不处理已有 CrewAI 删除大 diff 中的无关文件。

## 设计原则

1. Additive first：驱动器只追加结构化约束，不覆盖 `goal_lock`、`chapter_plan`、`chapter_graph_packet`。
2. Deterministic first：优先从结构化输入推导，避免新增 LLM 调用。
3. Prompt visible：关键变量必须进入生成上下文和 prompt 摘要，便于排查生成漂移。
4. Persistable：每章驱动包可随运行报告保存，后续质量闸门可引用。
5. Deletable boundary：模块名使用 `narrative_driver`，不再使用 `film_drama`，避免概念回潮。

## 拟新增数据结构

新增 `chapter_driver_packet.v1`：

```json
{
  "schema_version": "chapter_driver_packet.v1",
  "chapter_number": 1,
  "scene_beats": [
    {
      "index": 1,
      "purpose": "承接上一章后果",
      "location": "目标地点",
      "cast": ["主角"],
      "action": "必须发生的行动",
      "turn": "情绪或局势变化",
      "success_evidence": "正文中可验证的证据"
    }
  ],
  "cast": [
    {
      "name": "角色名",
      "role": "本章功能",
      "objective": "本章目标",
      "pressure": "本章压力",
      "relationship_signal": "关系变化"
    }
  ],
  "emotional_arc": ["开篇状态", "中段转折", "结尾余波"],
  "tension_points": ["本章必须被感知到的压力点"],
  "cliffhanger": "结尾钩子或余波",
  "driver_notes": ["写作执行提示"]
}
```

字段来源优先级：

1. `generation_packet.chapter_plan`：`summary`、`key_events`、`goal_lock`、`continuity_in/out`、`emotional_turn`、`magic_line`、`location_ids`、`character_names`。
2. `chapter_graph_packet`：`required_bridge`、`chapter_goal`、`success_evidence`、`target_destinations`、上一章场景锚点。
3. 导入资产：大纲、世界观、角色资产中的结构化字段。
4. `runtime_overrides`：`previous_summary`、`longform_memory`、人工追加 guidance。

## 实施阶段

### 阶段 1：驱动器核心模块

新增文件：

- `lib/knowledge_base/young_writer/services/narrative_driver.py`
- `lib/knowledge_base/tests/services/test_narrative_driver.py`

核心函数：

- `build_chapter_driver_packet(packet, chapter_graph_packet=None) -> dict`
- `render_chapter_driver_packet_summary(packet) -> str`
- `validate_chapter_driver_packet(packet) -> list[str]`

验收标准：

- 给定包含 `goal_lock/key_events/emotional_turn/characters/location_ids` 的 `GenerationPacket`，能生成稳定 `scene_beats/cast/emotional_arc/tension_points/cliffhanger`。
- 缺少可选字段时降级为空数组或空字符串，不中断生成。
- 输出 schema_version 固定为 `chapter_driver_packet.v1`。

### 阶段 2：接入输入组装

修改文件：

- `lib/knowledge_base/young_writer/services/input_assembler.py`

接入点：

- 在 `InputAssembler.enrich_context()` 中生成并写入：
  - `context["chapter_driver_packet"]`
  - `context["chapter_driver_summary"]`

前置条件：

- 若 `chapter_graph_packet` 尚未存在，驱动器只使用 `GenerationPacket`。
- 若后续在运行入口中先构建了 `chapter_graph_packet`，允许再次补全或覆盖同名驱动包。

验收标准：

- 通过 `InputAssembler.enrich_context()` 返回的上下文稳定包含 `chapter_driver_packet`。
- 旧调用方不需要改签名。

### 阶段 3：接入主运行链路

修改文件：

- `lib/knowledge_base/run_novel_generation.py`
- 可能涉及 `lib/knowledge_base/young_writer/services/longform_run.py`

接入点：

- 在已有 `chapter_graph_packet` 构建后，用它补全 `chapter_driver_packet`。
- 将驱动包写入章节报告，例如 `consistency_reports` 或章节运行 payload。
- 在重写、质量闸门、失败分析时允许读取 `chapter_driver_packet`。

验收标准：

- 每章运行报告中能看到 `chapter_driver_packet`。
- 出现 `missing_key_events`、`goal_lock_false_inheritance`、`scene_or_timeline_disconnect` 时，报告能同时展示驱动变量和图谱约束。

### 阶段 4：接入生成 prompt

修改文件：

- `lib/knowledge_base/young_writer/agents/novel_generator.py`

接入点：

- `_build_chapter_intent_contract()` 增加：
  - `scene_beats`
  - `cast_objectives`
  - `emotional_arc`
  - `tension_points`
  - `cliffhanger`
- prompt 渲染中增加一个短块，例如“叙事驱动变量”。

约束：

- `goal_lock` 仍是最高优先级。
- `chapter_guidance` 仍是 additive only。
- 驱动变量是执行路径，不是替代大纲。

验收标准：

- 单元测试能断言 prompt 或 intent contract 中包含 `chapter_driver_packet` 的关键字段。
- 缺少驱动包时原行为不变。

### 阶段 5：质量闸门联动

修改文件：

- `lib/knowledge_base/young_writer/agents/novel_generator.py`
- `lib/knowledge_base/run_novel_generation.py`

联动方式：

- 对 `scene_beats.success_evidence` 做轻量文本命中或摘要对齐检查。
- 对 `cast.objective` 做角色目标是否出现的弱检查。
- 对 `cliffhanger` 做结尾段落是否存在余波/钩子的弱检查。

验收标准：

- 不把该检查作为默认硬闸门，先作为 `anti_drift_details` / report evidence。
- 只在已有硬问题类型触发时提升为修复提示。

### 阶段 6：文档和迁移清理

修改文件：

- `lib/knowledge_base/docs/story_input_schema_zh.md`
- `lib/knowledge_base/docs/longform_run_contract.md`
- `lib/knowledge_base/docs/directory_architecture.md`
- `lib/knowledge_base/docs/user_manual.md`

文档内容：

- 说明 `chapter_driver_packet` 是小说生成驱动变量。
- 明确它不是 `film_drama` 复活。
- 更新业务流程图：导入资产 / story_input -> InputAssembler -> chapter_graph_packet -> chapter_driver_packet -> NovelGenerator -> quality gate -> persistence。

验收标准：

- `rg "film_drama|crewai"` 不出现新的主线依赖。
- 文档中的业务流与代码入口一致。

## 测试计划

优先新增和运行：

```bash
uv run pytest \
  lib/knowledge_base/tests/services/test_narrative_driver.py \
  lib/knowledge_base/tests/services/test_project_assets.py \
  lib/knowledge_base/tests/agents/test_novel_generator.py \
  lib/knowledge_base/tests/test_run_novel_generation.py \
  -q
```

补充静态检查：

```bash
python -m py_compile \
  lib/knowledge_base/young_writer/services/narrative_driver.py \
  lib/knowledge_base/young_writer/services/input_assembler.py \
  lib/knowledge_base/young_writer/agents/novel_generator.py

git diff --check
```

依赖剥离验证：

```bash
rg -n "from crewai|import crewai|Crew|Agent|Task|Process|film_drama" \
  lib/knowledge_base/young_writer lib/knowledge_base/run_novel_generation.py
```

预期结果：

- 不新增 CrewAI import。
- 不新增 `young_writer/agents/film_drama`。
- `film_drama` 只允许出现在历史说明或迁移文档中，不允许出现在运行时代码路径。

## 执行顺序

1. 新增 `narrative_driver.py` 和纯函数测试。
2. 接入 `InputAssembler.enrich_context()`，确认上下文可见。
3. 接入 `run_novel_generation.py` 的 `chapter_graph_packet` 后置补全。
4. 接入 `NovelGeneratorAgent` 的 intent contract 和 prompt。
5. 增加报告/质量闸门 evidence。
6. 更新文档。
7. 运行目标测试和依赖扫描。

## 风险和控制

风险：驱动变量与 `goal_lock` 或 `chapter_graph_packet` 发生冲突。

控制：驱动器只派生执行路径，`goal_lock` 和 `chapter_graph_packet` 保持优先级更高。

风险：恢复旧 `film_drama` 命名导致后续维护误判。

控制：新模块命名为 `narrative_driver`，旧名只在迁移说明中出现。

风险：prompt 过长。

控制：保存完整 `chapter_driver_packet`，prompt 只渲染压缩 summary。

风险：当前工作区已有大规模 CrewAI 删除 diff，容易混入无关变更。

控制：执行时只改 `lib/knowledge_base/young_writer`、`lib/knowledge_base/run_novel_generation.py`、相关测试和 docs；不触碰 `lib/crewai` 删除清单。

## 完成定义

1. 主线生成上下文包含 `chapter_driver_packet`。
2. 章节 prompt 或 intent contract 可见 scene/beat/cast/tension/emotional/cliffhanger 驱动变量。
3. 章节报告持久化驱动包或其摘要。
4. 相关测试通过。
5. 扫描确认没有新增 CrewAI 依赖和旧 `film_drama` runtime 代码。

## 实施记录

2026-06-18 已按本方案落地第一版：

- 新增 `young_writer.services.narrative_driver`，生成 `chapter_driver_packet.v1`。
- `InputAssembler.enrich_context()` 会写入 `chapter_driver_packet`、`chapter_driver_summary` 和非阻断 validation。
- `NovelGeneratorAgent` 会在生成前通过最终上下文重新 reconcile 驱动包，再把驱动变量并入 `chapter_intent_contract` 和 prompt-facing 文本，并写入一致性报告。
- `longform_run` review payload 会转发 `chapter_driver_packet`、`chapter_driver_summary` 和 `chapter_driver_validation`。
- 文档已同步到 schema、longform contract、目录架构和用户手册。
