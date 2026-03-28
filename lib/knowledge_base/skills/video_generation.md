---
name: video_generation
version: 1.0.0
description: 将场景数据生成为视频分镜脚本，支持多镜头切换
consumer_type: video
inputs:
  - scene_id
  - beats
  - emotional_arc
outputs:
  script: VideoScript
  scenes: List[Scene]
---

# Skill: video_generation

将场景数据转换为视频分镜脚本。

## Overview

video_generation 技能负责将结构化的场景数据转换为专业的视频分镜脚本。生成符合行业标准的分镜描述，包含镜头类型、画面内容、台词、音效等元素。

## When to Use

- 用户请求生成视频脚本
- 需要将小说场景转换为视频分镜
- 触发短语：`生成视频`、`写分镜`、`视频脚本`

---

## Metadata

| Field | Value |
|-------|-------|
| name | video_generation |
| version | 1.0.0 |
| consumer_type | video |

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| scene_id | str | Yes | 场景唯一标识符 |
| beats | list | Yes | 情节发展 beats 列表 |
| emotional_arc | dict | Yes | 情感弧线数据 |
| characters | list | No | 角色列表 |
| scene_descriptions | list | No | 场景视觉描述 |

---

## Outputs

```python
{
    "script": VideoScript {
        "title": str,
        "duration": int,         # 总时长（秒）
        "scenes": List[Scene] {
            "scene_id": str,
            "shot_type": str,     # wide, medium, close-up, etc.
            "camera_movement": str,
            "description": str,
            "dialogue": str,
            "sound_effect": str,
            "music_cue": str
        }
    },
    "scenes": List[Scene]  # 详细场景列表
}
```

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| video_format | "film" | 视频格式（film, tv, web） |
| aspect_ratio | "16:9" | 画面比例 |
| frame_rate | 24 | 帧率 |

---

## Integration

### 与 Orchestra 集成

video_generation 技能由 `VideoConsumer` 处理：

```python
from consumers.video_consumer import VideoConsumer

consumer = VideoConsumer(llm_client=llm_client)
script = await consumer.generate(raw_data)
```

---

## Workflow Steps

1. **分析 beats** - 解析情节发展脉络
2. **确定镜头类型** - 根据内容选择合适镜头
3. **生成分镜描述** - 创建详细画面描述
4. **添加音效音乐** - 生成音效和音乐提示词
5. **组装脚本** - 合并为完整视频脚本

---

## Usage Example

```python
# 基本使用
script = await video_consumer.generate(scene_data)

# 访问场景
for scene in script["scenes"]:
    print(f"Scene: {scene['scene_id']}")
    print(f"Shot: {scene['shot_type']}")
    print(f"Description: {scene['description']}")
```

---

## Tips

1. **镜头语言**：合理运用推、拉、摇、移等镜头运动
2. **情感匹配**：确保画面节奏与情感弧线匹配
3. **音效提示**：为关键动作添加音效提示
4. **音乐线索**：使用音乐cue增强情感表达
