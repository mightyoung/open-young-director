---
name: skill_index
version: 1.0.0
description: 技能索引 - 提供所有技能的快速查找入口
---

# Skill Index

内容生成系统技能索引。

## Overview

本文档列出所有可用的技能定义，提供快速查找入口。

---

## 可用技能

### 内容生成技能

| 技能 | 版本 | 描述 | 消费者类型 |
|------|------|------|------------|
| [novel_generation](./novel_generation.md) | 1.0.0 | 将场景数据生成为小说正文 | novel |
| [video_generation](./video_generation.md) | 1.0.0 | 将场景数据生成为视频分镜脚本 | video |
| [podcast_generation](./podcast_generation.md) | 1.0.0 | 将场景数据生成为播客音频脚本 | podcast |
| [music_generation](./music_generation.md) | 1.0.0 | 根据情感曲线生成背景音乐提示词 | music |

### 质量保证技能

| 技能 | 版本 | 描述 |
|------|------|------|
| [quality_check](./quality_check.md) | 1.0.0 | 对生成内容进行质量评估和门禁检查 |

---

## 技能关系图

```
Orchestra (编排器)
├── NovelOrchestrator
│   └── NovelConsumer → novel_generation
│       └── RealityChecker → quality_check
│
├── VideoConsumer → video_generation
│
├── PodcastConsumer → podcast_generation
│
└── MusicConsumer → music_generation
```

---

## 按输入类型查找

### scene_id + beats + characters

- [novel_generation](./novel_generation.md) - 小说正文生成
- [video_generation](./video_generation.md) - 视频脚本生成
- [podcast_generation](./podcast_generation.md) - 播客脚本生成

### emotional_arc

- [music_generation](./music_generation.md) - 背景音乐生成
- [novel_generation](./novel_generation.md) - 情感弧线指导写作
- [video_generation](./video_generation.md) - 情感匹配镜头

### 质量验证

- [quality_check](./quality_check.md) - 通用质量检查

---

## 按输出类型查找

### 文本内容

- [novel_generation](./novel_generation.md) - `content: str`
- [podcast_generation](./podcast_generation.md) - `script: str`

### 结构化数据

- [video_generation](./video_generation.md) - `script: VideoScript, scenes: List[Scene]`
- [music_generation](./music_generation.md) - `prompt: str, cues: List[MusicCue]`
- [quality_check](./quality_check.md) - `decision: GateDecision, issues: List[str]`

---

## 快速开始

### 生成小说

```python
from consumers.novel_consumer import NovelConsumer
from agents.novel_orchestrator import NovelOrchestrator

consumer = NovelConsumer(llm_client=llm_client)
orchestrator = NovelOrchestrator(config=config, llm_client=llm_client)

scene_data = await consumer.query(scene_id)
content = await consumer.generate(scene_data)

# 质量验证
validation = orchestrator.validate_chapter(content, context)
```

### 生成视频脚本

```python
from consumers.video_consumer import VideoConsumer

consumer = VideoConsumer(llm_client=llm_client)
script = await consumer.generate(raw_data)
```

### 生成播客

```python
from consumers.podcast_consumer import PodcastConsumer

consumer = PodcastConsumer(llm_client=llm_client)
podcast = await consumer.generate(raw_data)
```

### 生成音乐

```python
from consumers.music_consumer import MusicConsumer

consumer = MusicConsumer(llm_client=llm_client)
music = await consumer.generate({
    "genre": "xianxia",
    "emotional_arc": emotional_arc
})
```

---

## 技能版本历史

| 技能 | 版本 | 更新日期 | 变更 |
|------|------|----------|------|
| novel_generation | 1.0.0 | 2026-03-24 | 初始版本 |
| video_generation | 1.0.0 | 2026-03-24 | 初始版本 |
| podcast_generation | 1.0.0 | 2026-03-24 | 初始版本 |
| music_generation | 1.0.0 | 2026-03-24 | 初始版本 |
| quality_check | 1.0.0 | 2026-03-24 | 初始版本 |
