---
name: podcast_generation
version: 1.0.0
description: 将场景数据生成为播客音频脚本，支持多人对话
consumer_type: podcast
inputs:
  - scene_id
  - beats
  - speakers
outputs:
  script: str
  duration_estimate: int
---

# Skill: podcast_generation

将场景数据转换为播客音频脚本。

## Overview

podcast_generation 技能负责将场景数据转换为播客音频脚本。支持多人对话场景，自动分配角色台词，生成符合播客语体的脚本。

## When to Use

- 用户请求生成播客脚本
- 需要将小说场景转换为音频内容
- 触发短语：`生成播客`、`写音频脚本`、`播客内容`

---

## Metadata

| Field | Value |
|-------|-------|
| name | podcast_generation |
| version | 1.0.0 |
| consumer_type | podcast |

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| scene_id | str | Yes | 场景唯一标识符 |
| beats | list | Yes | 情节发展 beats 列表 |
| speakers | list | Yes | 说话人列表 |
| emotional_arc | dict | No | 情感弧线数据 |

---

## Outputs

```python
{
    "script": str,             # 播客脚本正文
    "duration_estimate": int,  # 预估时长（秒）
    "segments": List[Segment] {
        "speaker": str,
        "content": str,
        "duration": int
    }
}
```

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| podcast_style | "conversation" | 播客风格（conversation, monologue, interview） |
| speakers_count | 2 | 说话人数量 |
| avg_speaking_rate | 150 | 平均语速（字/分钟） |

---

## Integration

### 与 Orchestra 集成

podcast_generation 技能由 `PodcastConsumer` 处理：

```python
from consumers.podcast_consumer import PodcastConsumer

consumer = PodcastConsumer(llm_client=llm_client)
script = await consumer.generate(raw_data)
```

---

## Workflow Steps

1. **分析 beats** - 解析情节发展脉络
2. **分配角色** - 为每个 beats 分配说话人
3. **生成对话** - 创建自然的对话内容
4. **添加过渡** - 生成段落过渡语
5. **估算时长** - 根据字数估算音频时长

---

## Usage Example

```python
# 基本使用
podcast = await podcast_consumer.generate(scene_data)

# 访问脚本
print(f"Duration: {podcast['duration_estimate']}s")
for segment in podcast.get("segments", []):
    print(f"[{segment['speaker']}] {segment['content']}")
```

---

## Tips

1. **对话自然**：确保对话符合角色性格
2. **节奏把控**：合理控制每段的时长
3. **过渡自然**：段落之间添加自然的过渡语
4. **情感表达**：通过语速、停顿指示增强表达
