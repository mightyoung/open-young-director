---
name: novel_generation
version: 1.0.0
description: 将场景数据生成为小说正文，支持玄幻、修仙等题材
consumer_type: novel
inputs:
  - scene_id
  - chapter_info
  - characters
  - beats
outputs:
  content: str
  metrics: ContentMetrics
---

# Skill: novel_generation

将 FILM_DRAMA 场景数据转换为小说正文。

## Overview

novel_generation 技能负责将结构化的场景数据（beats、角色状态、场景描述、情感弧线）转换为连贯的中文小说文本。支持多种写作风格和叙事视角。

## When to Use

- 用户请求生成小说章节
- 需要将场景数据转换为小说正文
- 触发短语：`生成小说`、`写小说`、`创作小说`

---

## Metadata

| Field | Value |
|-------|-------|
| name | novel_generation |
| version | 1.0.0 |
| consumer_type | novel |
| agent | NovelOrchestrator |

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| scene_id | str | Yes | 场景唯一标识符 |
| chapter_info | dict | Yes | 章节信息（章节号、标题等） |
| characters | dict/list | Yes | 角色信息（支持 dict 或 list 格式） |
| beats | list | Yes | 情节发展 beats 列表 |

---

## Outputs

```python
{
    "content": str,          # 生成的小说正文
    "metrics": ContentMetrics {
        "word_count": int,
        "scene_count": int,
        "beat_count": int
    }
}
```

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| style | "literary" | 基础写作风格（literary, concise, dramatic） |
| style_preset / author_style | None | 基于知识库总结的风格预设：fanren_flow, face_slapping, cthulhu_mystery, cinematic_youth, epic_rebel, new_wuxia, sword_philosophy |
| perspective | "third_limited" | 叙事视角（third_limited, third_omniscient, first_person, dual_perspective, ensemble） |
| narrative_mode | "balanced" | 叙事写法（balanced, progressive_upgrade, low_high_cycle, multi_line_foreshadowing, character_driven, scene_driven） |
| pace | "medium" | 节奏（slow, medium, fast） |
| dialogue_density | "medium" | 对白密度（low, medium, high） |
| prose_style | "clean" | 行文质感（ornate, clean, concise_forceful, airy_lyrical） |
| world_building_density | "medium" | 设定铺陈密度（light, medium, dense） |
| emotion_intensity | "medium" | 情绪强度（subtle, medium, high） |
| combat_style | "tactical" | 战斗写法（brief, tactical, cinematic, epic） |
| hook_strength | "medium" | 开篇抓力（gentle, medium, strong） |
| word_count_target | 3000 | 目标字数 |

### Knowledge-base-derived presets

- `fanren_flow`：凡人流，强调底层成长、资源经营、逻辑自洽
- `face_slapping`：退婚流/打脸流，强调压制后的强反弹和爽点兑现
- `cthulhu_mystery`：克苏鲁悬疑流，强调未知、污染感、层层揭示
- `cinematic_youth`：电影化青春叙事，镜头感强，人物带少年气
- `epic_rebel`：逆天改命、大格局热血悲壮
- `new_wuxia`：江湖烟火与庙堂暗流并置，人物气口鲜明
- `sword_philosophy`：剑道修行与人道思辨并重

---

## Integration

### 与 Orchestra 集成

novel_generation 技能由 `NovelOrchestrator` 驱动：

```python
from agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig

config = OrchestratorConfig(mode="FILM_DRAMA")
orchestrator = NovelOrchestrator(config=config, llm_client=llm_client)

# 设置上下文
context = {
    "characters": [...],
    "location": "太虚宗",
    "time_of_day": "morning"
}
orchestrator.setup(context)

# 生成章节
result = orchestrator.orchestrate_chapter(
    chapter_number=1,
    chapter_outline="韩立参加宗门大比",
    context=context
)
```

### 质量门禁

使用 `RealityChecker` 进行质量验证：

```python
validation = orchestrator.validate_chapter(
    chapter_content=result["content"],
    context=context
)
# validation.status: PASS | NEEDS_WORK
```

---

## Workflow Steps

1. **提取角色信息** - 从 context 中提取角色数据
2. **规划场景** - DirectorAgent 规划场景结构
3. **执行场景** - 多 agent 并发生成场景
4. **组装输出** - 合并场景为完整章节
5. **质量验证** - RealityChecker 验证内容质量

---

## Usage Example

```python
# 基本使用
content = await novel_consumer.generate(scene_data)

# 带参数
content = await novel_consumer.generate(
    scene_data,
    style="literary",
    style_preset="fanren_flow",
    perspective="third_limited",
    narrative_mode="progressive_upgrade",
    pace="medium",
    dialogue_density="medium",
    prose_style="clean",
    world_building_density="medium",
    emotion_intensity="medium",
    combat_style="tactical",
    hook_strength="strong",
    word_count_target=5000
)
```

---

## Tips

1. **字数控制**：通过 `word_count_target` 精确控制目标字数
2. **风格选择**：`style` 控整体表达，`style_preset` 控知识库中的流派写法
3. **写法拆分**：`narrative_mode`、`pace`、`dialogue_density` 适合单独微调
4. **视角一致**：确保叙事视角在整个章节中保持一致
5. **质量验证**：生成后通过 `quality_gate` 验证内容质量
