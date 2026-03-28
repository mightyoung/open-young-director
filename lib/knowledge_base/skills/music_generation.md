---
name: music_generation
version: 1.0.0
description: 根据情感曲线生成背景音乐提示词
consumer_type: music
inputs:
  - genre
  - emotional_arc
  - scene_descriptions
outputs:
  prompt: str
  cues: List[MusicCue]
---

# Skill: music_generation

根据情感曲线生成背景音乐生成提示词。

## Overview

music_generation 技能负责根据场景的情感弧线和描述，生成适合的背景音乐提示词。生成的提示词可用于音乐生成模型（如 Suno、Udio）。

## When to Use

- 用户请求生成背景音乐
- 需要为场景匹配背景音乐
- 触发短语：`生成音乐`、`背景音乐`、`配乐`

---

## Metadata

| Field | Value |
|-------|-------|
| name | music_generation |
| version | 1.0.0 |
| consumer_type | music |

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| genre | str | Yes | 音乐风格（xianxia, fantasy, epic, etc.） |
| emotional_arc | dict | Yes | 情感弧线数据 |
| scene_descriptions | list | No | 场景视觉描述列表 |

---

## Outputs

```python
{
    "prompt": str,             # 音乐生成提示词
    "cues": List[MusicCue] {
        "timestamp": float,     # 时间点（秒）
        "type": str,           # intro, verse, chorus, bridge, outro
        "mood": str,          # 情绪描述
        "intensity": float,   # 强度 0-1
        "description": str    # 详细描述
    }
}
```

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| music_format | "instrumental" | 音乐格式（instrumental, with_lyrics） |
| tempo_range | (60, 120) | 节奏范围（BPM） |
| key_signature | "undefined" | 调性 |

---

## Integration

### 与 Orchestra 集成

music_generation 技能由 `MusicConsumer` 处理：

```python
from consumers.music_consumer import MusicConsumer

consumer = MusicConsumer(llm_client=llm_client)
music = await consumer.generate(raw_data)
```

---

## Workflow Steps

1. **分析情感弧线** - 提取情感变化曲线
2. **匹配音乐类型** - 根据场景类型选择音乐风格
3. **生成分段提示** - 为不同情感阶段生成对应提示
4. **创建时间线** - 生成带时间戳的 music cues
5. **组装提示词** - 合并为完整的音乐生成提示词

---

## Usage Example

```python
# 基本使用
music = await music_consumer.generate({
    "genre": "xianxia",
    "emotional_arc": emotional_arc,
    "scene_descriptions": scenes
})

# 访问提示词
print(music["prompt"])

# 访问分段
for cue in music["cues"]:
    print(f"[{cue['timestamp']}s] {cue['type']}: {cue['mood']}")
```

---

## Tips

1. **风格匹配**：确保音乐风格与场景类型匹配
2. **情感连续**：music cues 之间保持情感连续性
3. **强度渐变**：通过 intensity 实现平滑的强度变化
4. **提示词优化**：生成的提示词应简洁且具有描述性
