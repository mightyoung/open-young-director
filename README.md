# Open Young Director - AI Novel Writing System / AI小说创作系统

[English](#english) | [中文](#中文)

---

## English

### Overview

**Open Young Director** is an AI-powered novel writing system built on [crewAI](https://github.com/crewAIInc/crewAI). It provides a complete pipeline for generating long-form fiction (200万+ words) with multi-agent orchestration, Production Bible consistency enforcement, and parallel chapter generation.

### Key Features

- **Multi-Agent Orchestration**: World-building, plot planning, and writing agents work in concert
- **Production Bible**: Hollywood-style canonical reference ensuring consistency across volumes/chapters
- **Parallel Generation**: Async chapter writing with configurable concurrency
- **PostPass Pipeline**: Critique → Revision → Polish workflow per chapter
- **Pipeline Persistence**: Save/resume from any stage (outline, volume, summary, writing)
- **Specialized Agents**: Interiority checker, POV checker, outline verifier

### Architecture

```
lib/crewai/src/crewai/content/novel/
├── agents/
│   ├── world_agent.py          # World-building agent
│   ├── plot_agent.py           # Plot planning agent
│   ├── draft_agent.py          # Chapter drafting (with Bible constraints)
│   ├── interiority_checker.py   # Inner monologue validator
│   └── pov_checker.py          # Point-of-view validator
├── crews/
│   ├── novel_crew.py           # Main orchestrator
│   ├── writing_crew.py         # Parallel chapter writer
│   ├── review_crew.py          # Critique/revision/polish
│   ├── volume_outline_crew.py  # Volume outline generator
│   └── chapter_summary_crew.py  # Chapter summary generator
├── production_bible/
│   ├── bible_types.py          # BibleSection, CharacterProfile
│   ├── bible_builder.py        # ProductionBible builder
│   └── section_builder.py      # Per-volume BibleSection builder
├── pipeline_state.py            # Cross-stage persistence
└── novel_types.py              # WritingContext, PlotData, etc.
```

### Pipeline Stages

1. **World** → Build world lore, magic systems, geography
2. **Outline** → Plot arc, series overview, character backgrounds
3. **Evaluation** → Verify outline quality (optional gate)
4. **Volume Outlines** → Per-volume structure
5. **Chapter Summaries** → Per-chapter beat outlines
6. **Writing** → Draft → Critique → Revision → Polish
7. **Complete** → Final output

### Quick Start

```bash
# Install dependencies
uv lock && uv sync

# Generate a novel (玄幻史诗, 200万字)
uv run crewai create novel --title "仙侠史诗" --genre xianxia --word-count 2000000

# Resume from a saved state
uv run crewai create novel --title "仙侠史诗" --resume-from pipeline_state.json
```

### Configuration

Environment variables (see `.env.example`):

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...

# Optional: Moonshot/Kimi for Chinese content
KIMI_API_KEY=...
KIMI_BASE_URL=https://api.moonshot.cn/v1
```

### CLI Commands

```bash
# Create new novel
uv run crewai create novel --title "Title" --genre genre --word-count N

# Resume from saved state
uv run crewai create novel --title "Title" --resume-from state.json

# Run tests
uv run pytest lib/crewai/tests/

# Type check
uvx mypy lib/crewai/src
```

---

## 中文

### 概述

**Open Young Director** 是基于 [crewAI](https://github.com/crewAIInc/crewAI) 构建的 AI 小说创作系统。提供完整流水线生成长篇小说（200万+字），支持多智能体编排、Production Bible 一致性约束、并行章节生成。

### 核心特性

- **多智能体编排**：世界构建、情节规划、写作智能体协同工作
- **Production Bible**：好莱坞式规范参考，确保卷/章节间一致性
- **并行生成**：基于 asyncio 的可配置并发章节写作
- **PostPass 流水线**：每章批判 → 修改 → 润色工作流
- **流水线持久化**：可在任意阶段保存/恢复（大纲、卷、概要、写作）
- **专项检查**：内心独白检查、视角检查、大纲验证

### 技术架构

```
lib/crewai/src/crewai/content/novel/
├── agents/
│   ├── world_agent.py          # 世界观构建智能体
│   ├── plot_agent.py           # 情节规划智能体
│   ├── draft_agent.py          # 章节起草（支持Bible约束）
│   ├── interiority_checker.py   # 内心独白检查器
│   └── pov_checker.py          # 视角检查器
├── crews/
│   ├── novel_crew.py           # 主编排器
│   ├── writing_crew.py         # 并行章节写作
│   ├── review_crew.py          # 批判/修改/润色
│   ├── volume_outline_crew.py  # 卷大纲生成
│   └── chapter_summary_crew.py # 章节概要生成
├── production_bible/
│   ├── bible_types.py          # BibleSection, CharacterProfile
│   ├── bible_builder.py        # ProductionBible 构建器
│   └── section_builder.py      # 分卷 BibleSection 构建器
├── pipeline_state.py            # 跨阶段持久化
└── novel_types.py              # WritingContext, PlotData 等
```

### 流水线阶段

1. **World** → 构建世界观、修炼体系、地理设定
2. **Outline** → 情节弧线、系列概述、角色背景
3. **Evaluation** → 大纲质量评估（可选关卡）
4. **Volume Outlines** → 分卷结构
5. **Chapter Summaries** → 章节节拍大纲
6. **Writing** → 起草 → 批判 → 修改 → 润色
7. **Complete** → 最终输出

### 快速开始

```bash
# 安装依赖
uv lock && uv sync

# 生成小说（仙侠史诗，200万字）
uv run crewai create novel --title "仙侠史诗" --genre xianxia --word-count 2000000

# 从保存状态恢复
uv run crewai create novel --title "仙侠史诗" --resume-from pipeline_state.json
```

### 配置

环境变量（参见 `.env.example`）：

```bash
# LLM 配置
OPENAI_API_KEY=sk-...

# 可选：使用 Moonshot/Kimi（适合中文内容）
KIMI_API_KEY=...
KIMI_BASE_URL=https://api.moonshot.cn/v1
```

### CLI 命令

```bash
# 创建新小说
uv run crewai create novel --title "标题" --genre 类型 --word-count 字数

# 从保存状态恢复
uv run crewai create novel --title "标题" --resume-from state.json

# 运行测试
uv run pytest lib/crewai/tests/

# 类型检查
uvx mypy lib/crewai/src
```

---

## License / 许可证

MIT License - See [LICENSE](./LICENSE)
