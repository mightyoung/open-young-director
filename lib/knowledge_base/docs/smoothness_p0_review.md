# Smoothness P0 当前状态评审（2026-04-14）

关联计划：`/Users/muyi/Downloads/dev/young-writer/.omx/plans/ralplan-young-writer-smoothness-p0-20260414.md`

## 1. 结论摘要

当前代码库**还没有进入该计划假设的实现起点**。计划里依赖的几个关键契约——章节平滑性阻断、`blocking_issues/issue_types`、章节级 `chapter_review` 暂停载荷、以及重写指导拼装——在现状中都还不存在，或者尚未暴露为可复用接口。

因此，这个 P0 更像是一次**契约补齐 + 规则落地**，而不是对既有 continuity gate 的小修小补。

## 2. 当前代码事实

### 2.1 `NovelGeneratorAgent` 目前只有“事件覆盖 + 角色状态抽取”检查

`lib/knowledge_base/agents/novel_generator.py:516-672` 的 `_check_consistency()` 当前只做了：

- 对话/动作正则抽取角色状态
- 用 `chapter.metadata["key_events"]` 检查正文是否覆盖关键事件
- 计算 `overall_score`
- 输出 `recommendations`

当前返回结构只有：

- `character_consistency`
- `character_states`
- `plot_consistency`
- `missing_events`
- `overall_score`
- `recommendations`

缺失项：

- `invalid`
- `blocking_issues`
- `issue_types`
- `_check_transition_continuity()`
- `ABRUPT_TRANSITION_MARKERS`
- `_build_rewrite_guidance()`

这意味着计划文档里的“沿用现有 blocking contract / continuity gate / rewrite guidance”在当前分支并不成立。

### 2.2 长篇暂停合同目前没有章节级 review payload

`lib/knowledge_base/services/longform_run.py:386-464` 目前只提供：

- `review_payload_for_outline()`
- `review_payload_for_volume()`
- `review_payload_for_risk()`

没有：

- `review_payload_for_chapter()`
- 章节无效后的 `chapter_review` 暂停载荷

如果 P0 要实现“重写一次后仍失败则进入现有 `chapter_review`”，那需要先补齐章节级暂停合同；它不是纯文案调整。

### 2.3 现有测试覆盖点与计划目标不匹配

当前测试现状：

- `lib/knowledge_base/tests/agents/test_novel_generator.py:1-87` 只覆盖写作参数 prompt 注入
- `lib/knowledge_base/tests/test_longform_run.py:1-204` 只覆盖 outline/volume pause-resume 与 volume review payload

没有覆盖：

- A→B 场景跳切
- 时间跳跃缺锚点
- 上章后果未承接
- suspenseful-but-valid opening
- `issue_types` 兼容性
- `chapter_review` 暂停/恢复

所以计划中列出的测试清单基本都属于新增覆盖，而不是补几条断言。

## 3. 代码质量评审

### 3.1 `_check_consistency()` 体积偏大，适合顺手拆 helper

当前方法把：

- 正则常量
- 角色状态抽取
- 关键事件检查
- 得分计算

都放在一个函数内，后续再塞入平滑性 P0 规则，会继续恶化可读性。建议至少拆出：

- `_extract_character_states(...)`
- `_collect_missing_key_events(...)`
- `_check_transition_continuity(...)`

这样才能让 P0 的 deterministic gate 保持“可解释、可测、可替换”。

### 3.2 新契约应采用“只增不破”的输出扩展

因为当前已有 `overall_score`、`missing_events`、`recommendations` 的消费链路，P0 更安全的做法是：

- 保留现有字段
- 增量新增 `invalid`
- 增量新增 `blocking_issues`
- 增量新增 `issue_types`

否则会把这次平滑性改动放大成一次高风险的报告协议重构。

### 3.3 计划文档里“现有流程”的表述需要按现状理解

按当前代码事实，以下说法应理解为“目标态”而不是“已存在能力”：

- “existing `_rewrite_invalid_chapter()`”
- “existing `chapter_review`”
- “existing `_build_rewrite_guidance(report)`”
- “existing `_check_transition_continuity()`”

实施时需要先确认这些能力是否在别处分散存在；若没有，就应在 PR 描述里明确说明本轮是在**补 contract**，避免 reviewer 误以为只是加几条 marker。

## 4. 文档层建议

为了让后续实现更稳，建议把 P0 文档口径统一成下面两点：

1. **当前长篇自动暂停只覆盖 outline / volume。**  
   章节级 smoothness failure pause 仍属新增合同。
2. **当前 consistency report 不是阻断式判定结构。**  
   本轮要把它扩成“评分 + 阻断原因”双轨输出。

## 5. 对后续实现者的建议顺序

建议按以下顺序落地，风险最低：

1. 先在 `novel_generator.py` 内补充 additive report contract
2. 再加入 deterministic transition checks
3. 再把“无效章节 → 重写一次 → 仍无效则暂停”接进 longform pause/resume
4. 最后补 Streamlit 展示和回归测试

如果顺序反过来，UI/恢复链路会先依赖一个尚未稳定的报告协议，回归成本会更高。

## 6. 本次文档更新的目的

这份文档不是功能设计替代品，而是给实现/评审者一个**当前代码现实基线**：

- 哪些能力已经存在
- 哪些只是计划中的目标态
- 哪些合同变更会牵动 longform pause/resume

后续实现 PR 可以直接引用本文件，减少“计划假设”和“代码现状”之间的认知偏差。
