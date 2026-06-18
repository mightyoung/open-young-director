# Young-writer 中文输入 Schema

## 目标

`story_input` 是 young-writer 长篇生成的结构化输入源。所有用户提供的叙事内容必须使用中文输入；程序内部枚举值可以继续使用英文代码。

权威输入目录：

```text
story_input/
  project_bible.json
  world_bible.json
  characters.json
  chapter_plans.json
  style_profile.json
```

兼容 Markdown 大纲只用于导出和兼容，不作为生成主源。

## project_bible.json

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `title` | string | 中文必填，作品名 |
| `author` | string | 中文推荐，作者名 |
| `genre` | string | 中文必填，例如“科幻悬疑”“玄幻”“仙侠” |
| `premise` | string | 中文必填，一句话核心前提 |
| `synopsis` | string | 中文必填，整体故事大纲 |
| `reader_promise` | string | 中文可选，读者期待 |
| `themes` | string[] | 中文可选，主题关键词 |
| `forbidden_directions` | string[] | 中文可选，禁止方向 |

## world_bible.json

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `summary` | string | 中文必填，世界观摘要 |
| `locations` | string[] | 中文可选，地点或场景 |
| `factions` | string[] | 中文可选，组织/势力 |
| `rules` | string[] | 中文可选，世界规则 |
| `hard_constraints` | string[] | 中文可选，不可违反约束 |
| `known_facts` | string[] | 中文可选，既定事实 |

## characters.json

每个角色对象：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `id` | string | 程序内部 ID，可用英文或拼音，例如 `character:linyuan` |
| `name` | string | 中文必填，角色名 |
| `role` | string | 中文推荐，角色功能或身份 |
| `voice` | string | 中文推荐，语言风格 |
| `motivation` | string | 中文推荐，动机 |
| `arc` | string | 中文推荐，角色弧线 |
| `relationships` | string[] | 中文可选，关系 |
| `tags` | string[] | 可选，内部标签可用英文代码 |

## chapter_plans.json

每个章节计划对象：

| 字段 | 类型 | 要求 |
| --- | --- | --- |
| `chapter_number` | integer | 必填，章节号 |
| `title` | string | 中文必填，章节标题 |
| `summary` | string | 中文必填，章节摘要 |
| `key_events` | string[] | 中文必填，关键事件，建议包含明确动作词 |
| `realm` | string | 中文可选，题材/阶段/境界 |
| `purpose` | string | 中文可选，本章功能 |
| `must_include` | string[] | 中文可选，必须写入 |
| `must_not_include` | string[] | 中文可选，禁止写入 |
| `character_ids` | string[] | 内部 ID，必须能在 `characters.json` 中找到 |
| `character_names` | string[] | 中文推荐，必须与结构化角色表一致 |
| `location_ids` | string[] | 内部地点 ID，可由中文地点名派生 |
| `continuity_in` | string | 中文推荐，承接上一章 |
| `continuity_out` | string | 中文推荐，本章收束/尾钩 |
| `goal_lock` | string | 中文必填，本章不可漂移目标 |
| `pacing` | string | 中文可选，例如“开场”“推进”“转折” |
| `emotional_turn` | string | 中文可选，情绪转折 |
| `volume_number` | integer | 必填，卷号 |
| `volume_label` | string | 中文可选，例如“第1卷” |
| `magic_line` | string | 中文可选，暗线/钩子 |
| `source` | string | 内部来源标记，可用英文代码 |

## style_profile.json

风格字段是程序内部选项，可以使用英文代码；如果由用户填写自然语言说明，建议使用中文。

常见字段：

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

## 校验策略

`validate_generation_packet` 会阻断非中文叙事输入。当前阻断范围包括：

- `project_bible.title / genre / premise / synopsis`
- `world_bible.summary / locations / factions / rules / hard_constraints / known_facts`
- `characters[].name`
- `chapter_plan.title / summary / key_events / realm / purpose / must_include / must_not_include / character_names / continuity_in / continuity_out / goal_lock / pacing / emotional_turn / volume_label / magic_line`

空字段仍按原有必填规则处理；非必填空字段不会因为未包含中文而失败。
