# crewAI 多Agent内容生成系统 - 详细实施方案

> 创建日期: 2026-03-20
> 基于: content-generation-system-plan.md v2.0
> 状态: 实施方案完成 (v1.1 - 整合最佳实践)

---

## 附录A: 行业最佳实践整合 (v1.1新增)

### A.1 核心参考框架

| 框架 | 关键特性 | 适用场景 |
|------|----------|----------|
| **crewAI Flows** | @start/@listen/@router装饰器, 事件驱动, 状态持久化 | 轻量级工作流编排 |
| **LangGraph StateGraph** | TypedDict状态, Checkpoint持久化, 条件边, 时间旅行调试 | 复杂状态管理, 长时运行任务 |
| **Azure Multi-Agent** | 多专家Agent协作, 阶段质量门控, 人工审核点 | 企业级内容生成 |

### A.2 Pipeline架构模式

```
模式1: 顺序Pipeline (适用于Blog/新闻)
  Task1 → Agent A → Output O1
  Task2 → Agent B (context: O1) → Output O2
  Task3 → Agent C (context: O1+O2) → Final

模式2: 分层/管理模式 (适用于Novel/Script)
  Manager Agent → 任务分发 → Worker Agents → 汇报
  └── 动态任务分配, 监督协调

模式3: Supervisor模式 (LangGraph风格)
  Central Supervisor → 路由到专业Agent (Research, Write, Review)
  └── 中央Agent控制通信流和任务路由
```

### A.3 状态管理模式

**LangGraph StateGraph Pattern (推荐用于统一架构):**
```python
from typing import TypedDict
from crewai.flow.flow import Flow, remember

class ContentState(TypedDict):
    topic: str
    content_type: str
    world_output: Optional[dict]      # Stage 1产出
    outline_output: Optional[dict]    # Stage 2产出
    draft_output: Optional[dict]      # Stage 3产出
    review_output: Optional[dict]      # Stage 4产出
    step_count: int
    metadata: dict

class UnifiedContentFlow(Flow[ContentState]):
    @start()
    def begin(self):
        self.state = ContentState(
            topic=self.topic,
            content_type=self.content_type,
            step_count=0
        )

    @listen("stage_complete")
    def continue_pipeline(self):
        self.state["step_count"] += 1
        # 路由到下一阶段
```

### A.4 Checkpoint/恢复机制 (LangGraph风格)

**4大核心职责:**
1. **持久化状态管理** - 保存完整图状态, 支持跨请求恢复
2. **容错** - 故障/重启后从最近checkpoint恢复
3. **时间旅行调试** - 回滚到历史状态
4. **人工审核** - 暂停等待人工输入, 然后恢复

**架构:**
```
应用层 → 图运行时 → Checkpoint系统 → 存储后端
                                    ↓
                          (SQLite/Redis/PostgreSQL)
```

### A.5 质量门控模式 (Stage Gates)

```python
class StageGate:
    """阶段质量门控"""
    def __init__(self, min_quality_score: float = 0.7):
        self.min_quality_score = min_quality_score

    def validate(self, output: Any) -> tuple[bool, str]:
        """验证阶段产出是否满足质量门槛"""
        score = self._calculate_quality_score(output)
        if score >= self.min_quality_score:
            return True, "PASS"
        return False, f"Quality score {score} below threshold {self.min_quality_score}"

    def _calculate_quality_score(self, output: Any) -> float:
        # 实现质量评分逻辑
        pass

# 使用示例
gate = StageGate(min_quality_score=0.7)
passed, msg = gate.validate(draft_output)
if not passed:
    raise QualityGateError(f"Stage gate failed: {msg}")
```

### A.6 统一内容Pipeline设计

| 内容类型 | Stage 1 (World) | Stage 2 (Outline) | Stage 3 (Generate) | Stage 4 (Review) |
|----------|-----------------|-------------------|-------------------|------------------|
| **Novel** | 世界观构建 | 情节大纲 | 分章写作 | 章节审核 |
| **Script** | 人物设定 | BeatSheet | 场景+对白 | 格式审查 |
| **Blog** | 主题研究 | 文章结构 | 正文写作 | SEO+平台适配 |
| **Podcast** | 嘉宾/话题研究 | 节目大纲 | 脚本+对白 | 音频优化 |

**核心洞察:** 所有内容类型共享相同的前两个阶段 (World→Outline), 差异在后面两个阶段。

---

## 一、项目结构

### 1.1 目录结构

```
lib/
├── crewai/                          # 核心框架
│   └── src/crewai/
│       ├── __init__.py
│       ├── agent.py
│       ├── crew.py
│       ├── task.py
│       └── content/                # 新增: 内容生成核心
│           ├── __init__.py
│           ├── types.py            # ContentType枚举
│           ├── base.py             # BaseCrew基类
│           ├── exceptions.py        # 内容生成异常
│           ├── config.py           # 配置模型
│           │
│           ├── agents/             # 基础Agent
│           │   ├── __init__.py
│           │   ├── outline_agent.py
│           │   ├── draft_agent.py
│           │   ├── critique_agent.py
│           │   ├── revision_agent.py
│           │   ├── polish_agent.py
│           │   └── export_agent.py
│           │
│           ├── memory/             # 实体记忆系统
│           │   ├── __init__.py
│           │   ├── entity_memory.py
│           │   └── continuity_tracker.py
│           │
│           ├── review/             # 审查流水线
│           │   ├── __init__.py
│           │   ├── review_pipeline.py
│           │   ├── review_context.py
│           │   ├── review_result.py
│           │   ├── checkers/       # 通用检查器
│           │   │   ├── __init__.py
│           │   │   ├── consistency_checker.py
│           │   │   ├── pacing_checker.py
│           │   │   ├── ooc_checker.py
│           │   │   ├── high_point_checker.py
│           │   │   ├── continuity_checker.py
│           │   │   └── reader_pull_checker.py
│           │   └── gates/          # 编辑关卡
│           │       ├── __init__.py
│           │       ├── critique_gate.py
│           │       ├── revision_gate.py
│           │       ├── polish_gate.py
│           │       ├── copy_edit_gate.py
│           │       └── proofread_gate.py
│           │
│           ├── outline/            # 大纲解析引擎
│           │   ├── __init__.py
│           │   ├── outline_engine.py
│           │   ├── chapter_outline.py
│           │   └── strand_weave.py
│           │
│           └── editing/            # 编辑Pipeline
│               ├── __init__.py
│               ├── edit_pipeline.py
│               ├── diagnosis.py
│               └── prescription.py
│
├── crewai-novel/                   # 新增: 小说生成插件
│   ├── __init__.py
│   └── src/crewai_novel/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── world_agent.py
│       │   ├── plot_agent.py
│       │   ├── dianting_checker.py
│       │   ├── chapter_ending_checker.py
│       │   ├── shuanggan_checker.py
│       │   ├── repetitive_pattern_checker.py
│       │   ├── interiority_checker.py
│       │   └── pov_checker.py
│       ├── crews/
│       │   ├── __init__.py
│       │   ├── world_crew.py
│       │   ├── outline_crew.py
│       │   ├── writing_crew.py
│       │   ├── review_crew.py
│       │   └── novel_crew.py
│       └── patterns/              # 爽感模式库
│           ├── __init__.py
│           └── shuanggan_patterns.py
│
├── crewai-script/                 # 新增: 剧本生成插件
│   ├── __init__.py
│   └── src/crewai_script/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── structure_agent.py
│       │   ├── beat_sheet_agent.py
│       │   ├── scene_agent.py
│       │   ├── dialogue_agent.py
│       │   ├── cinematography_agent.py
│       │   ├── visual_motif_tracker.py
│       │   ├── transition_agent.py
│       │   ├── coverage_planner.py
│       │   ├── location_vision_agent.py
│       │   └── visual_format_agent.py
│       └── crews/
│           ├── __init__.py
│           ├── show_bible_crew.py
│           ├── structure_crew.py
│           ├── beat_sheet_crew.py
│           ├── scene_crew.py
│           ├── dialogue_crew.py
│           ├── visual_crew.py
│           ├── export_crew.py
│           └── script_crew.py
│
├── crewai-blog/                   # 新增: 博客生成插件
│   ├── __init__.py
│   └── src/crewai_blog/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── hook_agent.py
│       │   ├── research_agent.py
│       │   ├── title_agent.py
│       │   ├── thumbnail_agent.py
│       │   ├── seo_agent.py
│       │   └── platform_adapter_agent.py
│       └── crews/
│           ├── __init__.py
│           ├── hook_crew.py
│           ├── research_crew.py
│           ├── writing_crew.py
│           ├── seo_crew.py
│           └── blog_crew.py
│
├── crewai-podcast/               # 新增: 播客生成插件
│   ├── __init__.py
│   └── src/crewai_podcast/
│       ├── __init__.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── preshow_agent.py
│       │   ├── cold_open_agent.py
│       │   ├── intro_agent.py
│       │   ├── segment_agent.py
│       │   ├── interview_agent.py
│       │   ├── ad_read_agent.py
│       │   ├── outro_agent.py
│       │   └── shownotes_agent.py
│       └── crews/
│           ├── __init__.py
│           ├── preshow_crew.py
│           ├── intro_crew.py
│           ├── segment_crew.py
│           ├── interview_crew.py
│           ├── ad_read_crew.py
│           ├── outro_crew.py
│           ├── shownotes_crew.py
│           └── podcast_crew.py
│
└── tests/
    └── content/                   # 新增: 内容生成测试
        ├── __init__.py
        ├── conftest.py
        ├── unit/
        │   ├── __init__.py
        │   ├── test_types.py
        │   ├── test_base_crew.py
        │   ├── test_outline_engine.py
        │   ├── test_entity_memory.py
        │   ├── test_review_pipeline.py
        │   └── test_edit_pipeline.py
        ├── integration/
        │   ├── __init__.py
        │   ├── test_novel_crew.py
        │   ├── test_script_crew.py
        │   ├── test_blog_crew.py
        │   └── test_podcast_crew.py
        └── fixtures/
            ├── outlines/
            ├── novels/
            ├── scripts/
            ├── blogs/
            └── podcasts/
```

### 1.2 核心文件依赖图

```
types.py (ContentType枚举)
    ↓
base.py (BaseCrew基类)
    ↓                    ↓
outline_engine.py    entity_memory.py
    ↓                    ↓
outline_agent.py    draft_agent.py
    ↓                    ↓
critique_agent.py ←─────────────────┐
    ↓                              │
revision_agent.py                   │
    ↓                              │
polish_agent.py                    │
    ↓                              │
export_agent.py                    │
                                   │
        ← ← ← ← ← ← ← ← ← ← ← ← ←
```

---

## 二、Phase 0: 架构基础 (v1.1增强)

### 2.0 UnifiedContentCrew 统一架构 (新增)

基于最佳实践研究，引入统一内容Crew架构，支持多内容类型复用同一Pipeline:

```python
# lib/crewai/src/crewai/content/unified.py
from typing import TypedDict, Optional, Any
from typing_extensions import TypedDict
from crewai.flow.flow import Flow, remember, listen
from crewai.content.base import BaseContentCrew

class UnifiedContentState(TypedDict, total=False):
    """统一内容状态 - LangGraph风格"""
    topic: str
    content_type: str
    language: str
    # Stage 1: World Building
    world_output: Optional[dict]
    world_quality_score: float
    # Stage 2: Outline Planning
    outline_output: Optional[dict]
    outline_quality_score: float
    # Stage 3: Content Generation
    draft_output: Optional[dict]
    draft_quality_score: float
    # Stage 4: Review
    review_output: Optional[dict]
    review_quality_score: float
    # Metadata
    step_count: int
    metadata: dict
    errors: list[str]

class UnifiedContentCrew(BaseContentCrew):
    """统一内容生成Crew - 支持多内容类型复用Pipeline

    设计原则:
    1. 4阶段Pipeline: World → Outline → Generate → Review
    2. 阶段质量门控 (Stage Gates)
    3. Checkpoint持久化 (LangGraph风格)
    4. 事件驱动编排 (Flow装饰器)
    """

    # 阶段质量门槛
    STAGE_THRESHOLDS = {
        "world": 0.6,
        "outline": 0.7,
        "draft": 0.75,
        "review": 0.8,
    }

    def __init__(
        self,
        content_type: str,
        config: Any,
        llm: Optional[Any] = None,
        enable_checkpoint: bool = True,
        enable_human_review: bool = False,
        **kwargs
    ):
        super().__init__(config=config, **kwargs)
        self.content_type = content_type
        self.llm = llm
        self.enable_checkpoint = enable_checkpoint
        self.enable_human_review = enable_human_review
        self._checkpoint_state: Optional[UnifiedContentState] = None
        self._stage_gates_passed: set = set()

    def _create_workflow(self) -> Flow:
        """使用Flow创建事件驱动工作流"""
        flow = UnifiedContentFlow(
            topic=self.config.topic if hasattr(self.config, 'topic') else "",
            content_type=self.content_type,
            llm=self.llm
        )
        return flow

    def kickoff(self) -> BaseCrewOutput:
        """执行统一内容生成Pipeline"""
        import time
        start = time.time()

        # 尝试从checkpoint恢复
        if self.enable_checkpoint and self._checkpoint_state:
            state = self._checkpoint_state
        else:
            state = UnifiedContentState(
                topic=self.config.topic if hasattr(self.config, 'topic') else "",
                content_type=self.content_type,
                step_count=0,
                metadata={}
            )

        # 执行Pipeline
        try:
            result_state = self._execute_pipeline(state)
        except Exception as e:
            # 记录错误但继续 (容错设计)
            state["errors"].append(str(e))
            result_state = state

        # 保存checkpoint
        if self.enable_checkpoint:
            self._save_checkpoint(result_state)

        execution_time = time.time() - start

        return BaseCrewOutput(
            content=result_state.get("draft_output"),
            tasks_completed=[f"Stage {i+1}" for i in range(result_state.get("step_count", 0))],
            execution_time=execution_time,
            metadata=result_state.get("metadata", {}),
        )

    def _execute_pipeline(self, state: UnifiedContentState) -> UnifiedContentState:
        """执行4阶段Pipeline"""
        # Stage 1: World Building
        state = self._stage_world(state)
        self._validate_gate("world", state)

        # Stage 2: Outline Planning
        state = self._stage_outline(state)
        self._validate_gate("outline", state)

        # Stage 3: Content Generation
        state = self._stage_generate(state)
        self._validate_gate("draft", state)

        # Stage 4: Review
        state = self._stage_review(state)
        self._validate_gate("review", state)

        return state

    def _validate_gate(self, stage: str, state: UnifiedContentState) -> None:
        """阶段质量门控验证"""
        threshold = self.STAGE_THRESHOLDS.get(stage, 0.7)
        score_key = f"{stage}_quality_score"

        if score_key in state:
            score = state[score_key]
            if score < threshold:
                raise QualityGateError(
                    f"Stage '{stage}' quality score {score} below threshold {threshold}"
                )
            self._stage_gates_passed.add(stage)

    def _save_checkpoint(self, state: UnifiedContentState) -> None:
        """保存Checkpoint到持久化存储"""
        self._checkpoint_state = state
        # TODO: 实现实际持久化 (Redis/SQLite)

    def _stage_world(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 1: 世界观/主题构建"""
        raise NotImplementedError("子类必须实现")

    def _stage_outline(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 2: 大纲规划"""
        raise NotImplementedError("子类必须实现")

    def _stage_generate(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 3: 内容生成"""
        raise NotImplementedError("子类必须实现")

    def _stage_review(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 4: 审核优化"""
        raise NotImplementedError("子类必须实现")


class UnifiedContentFlow(Flow[UnifiedContentState]):
    """统一内容Flow - 事件驱动编排 (LangGraph风格)"""

    def __init__(self, topic: str, content_type: str, llm=None):
        super().__init__()
        self.topic = topic
        self.content_type = content_type
        self.llm = llm

    @start()
    def begin(self):
        """入口点"""
        self.state = UnifiedContentState(
            topic=self.topic,
            content_type=self.content_type,
            step_count=0,
            metadata={},
            errors=[]
        )

    @listen("continue")
    def continue_pipeline(self):
        """继续下一阶段"""
        self.state["step_count"] += 1


class QualityGateError(Exception):
    """质量门控错误"""
    pass
```

### 2.0.1 统一架构 vs 分离架构对比

| 维度 | 分离架构 (当前) | 统一架构 (v1.1) |
|------|----------------|-----------------|
| 代码复用 | 低 - 每种内容类型独立 | 高 - World/Outline阶段复用 |
| Pipeline一致性 | 低 - 各类型流程不同 | 高 - 统一4阶段流程 |
| 状态管理 | 分散 | 集中 (TypedDict) |
| Checkpoint | 无 | LangGraph风格 |
| 质量门控 | 无 | Stage Gates |
| 人工审核 | 无 | 可选人工审核点 |

### 2.0.2 迁移路径

```
Phase 0.1: 定义UnifiedContentState类型
Phase 0.2: 实现QualityGateError和StageGate
Phase 0.3: 实现基础UnifiedContentCrew骨架
Phase 0.4: 将现有NovelCrew改为继承UnifiedContentCrew
Phase 0.5: 将ScriptCrew/BlogCrew/PodcastCrew逐步迁移
```

---

## 二、Phase 0: 架构基础

### 2.1 任务清单

| 任务ID | 文件 | 描述 | 类型 | 优先级 |
|--------|------|------|------|--------|
| P0-T1 | `types.py` | ContentType枚举定义 | 核心类型 | P0 |
| P0-T2 | `base.py` | BaseCrew抽象基类 | 核心类 | P0 |
| P0-T3 | `exceptions.py` | 异常定义 | 辅助 | P0 |
| P0-T4 | `config.py` | 配置模型 | 辅助 | P0 |
| P0-T5 | `edit_pipeline.py` | 编辑Pipeline基类 | 核心类 | P0 |
| P0-T6 | `gates/` | 编辑关卡基类 | 核心类 | P0 |

### 2.2 ContentType枚举 (types.py)

```python
# lib/crewai/src/crewai/content/types.py
from enum import Enum
from typing import Literal

ContentType = Literal["novel", "script", "blog", "podcast"]

class ContentTypeEnum(Enum):
    """内容类型枚举"""
    NOVEL = "novel"
    SCRIPT = "script"
    BLOG = "blog"
    PODCAST = "podcast"

class NovelStyle(Enum):
    """小说风格"""
    XIANXIA = "xianxia"           # 修仙
    URBAN = "urban"                # 都市
    FANTASY = "fantasy"            # 西幻
    ROMANCE = "romance"            # 言情
    MYSTERY = "mystery"            # 悬疑
    SCIFI = "scifi"               # 科幻
    HISTORICAL = "historical"      # 历史

class ScriptFormat(Enum):
    """剧本格式"""
    FINAL_DRAFT = "final_draft"
    CELTX = "celtx"
    FDX = "fdx"                   # Fountain
    PDF = "pdf"

class BlogPlatform(Enum):
    """博客平台"""
    SEO = "seo"                    # 通用SEO
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    MEDIUM = "medium"
    ZHIHU = "zhihu"

class PodcastFormat(Enum):
    """播客格式"""
    JSON = "json"
    SRT = "srt"                   # 带时间戳
    MARKDOWN = "markdown"

@dataclass
class ContentConfig:
    """内容生成配置"""
    content_type: ContentTypeEnum
    target_words: int = 10000
    language: str = "zh-CN"
    style: Optional[str] = None
    enable_feedback_loop: bool = False
    enable_dianting: bool = False
    enable_chapter_ending: bool = False
    # ... 其他配置
```

### 2.3 BaseCrew基类 (base.py)

```python
# lib/crewai/src/crewai/content/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from crewai import Agent, Crew, Task
from crewai.utilities.events import event_emitter

class BaseContentCrew(ABC):
    """内容生成Crew基类"""

    def __init__(
        self,
        content_type: ContentType,
        config: Optional[ContentConfig] = None,
        llm: Optional[Any] = None,
        memory: Optional[Any] = None,
    ):
        self.content_type = content_type
        self.config = config or ContentConfig(content_type=content_type)
        self.llm = llm
        self.memory = memory
        self._agents: Dict[str, Agent] = {}
        self._tasks: Dict[str, Task] = {}
        self._crew: Optional[Crew] = None

    @abstractmethod
    def _create_agents(self) -> Dict[str, Agent]:
        """创建所需的Agent"""
        pass

    @abstractmethod
    def _create_tasks(self) -> Dict[str, Task]:
        """创建所需的任务"""
        pass

    @abstractmethod
    def _create_workflow(self) -> Crew:
        """创建工作流程"""
        pass

    def kickoff(self) -> ContentOutput:
        """执行内容生成"""
        self._setup()
        crew = self._create_workflow()
        result = crew.kickoff()
        return self._process_output(result)

    def _setup(self) -> None:
        """初始化设置"""
        self._agents = self._create_agents()
        self._tasks = self._create_tasks()

    @abstractmethod
    def _process_output(self, result: Any) -> ContentOutput:
        """处理输出"""
        pass

    def get_memory(self) -> Optional[EntityMemory]:
        """获取实体记忆"""
        return self.memory

    def set_feedback_loop(self, enabled: bool) -> None:
        """设置反馈回路"""
        self.config.enable_feedback_loop = enabled
```

### 2.4 编辑关卡基类 (gates/)

```python
# lib/crewai/src/crewai/content/review/gates/copy_edit_gate.py
class CopyEditGate:
    """冻结点：内容锁定后不再修改"""

    def __init__(self):
        self._frozen = False

    def freeze(self) -> None:
        """冻结内容"""
        self._frozen = True

    def is_frozen(self) -> bool:
        return self._frozen

    def check(self, draft: str, context: ReviewContext) -> GateResult:
        """检查是否可以进入冻结状态"""
        if self._frozen:
            return GateResult(
                passed=True,
                message="内容已冻结"
            )

        # 检查是否满足冻结条件
        return GateResult(
            passed=False,
            message="尚未满足冻结条件",
            requirements=[
                "所有审查问题已解决",
                "内容结构稳定",
                "无需重大修改"
            ]
        )
```

### 2.5 测试要求

```python
# tests/content/unit/test_types.py
def test_content_type_enum():
    assert ContentTypeEnum.NOVEL.value == "novel"
    assert ContentTypeEnum.SCRIPT.value == "script"

def test_content_config_defaults():
    config = ContentConfig(content_type=ContentTypeEnum.NOVEL)
    assert config.target_words == 10000
    assert config.language == "zh-CN"
    assert config.enable_feedback_loop == False

# tests/content/unit/test_base_crew.py
def test_base_crew_abstract():
    with pytest.raises(TypeError):
        BaseContentCrew(content_type="novel")

def test_base_crew_kickoff():
    # 测试kickoff方法调用流程
    pass
```

---

## 三、Phase 1: 编辑Pipeline

### 3.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P1-T1 | `critique_agent.py` | CritiqueAgent实现 | P0 |
| P1-T2 | `revision_agent.py` | RevisionAgent实现 | P1-T1 |
| P1-T3 | `polish_agent.py` | PolishAgent实现 | P1-T2 |
| P1-T4 | `diagnosis.py` | 诊断数据结构 | P1-T1 |
| P1-T5 | `prescription.py` | 处方数据结构 | P1-T2 |
| P1-T6 | `edit_pipeline.py` | 编辑Pipeline编排 | P1-T3 |
| P1-T7 | `test_edit_pipeline.py` | 测试 | P1-T6 |

### 3.2 CritiqueAgent实现

```python
# lib/crewai/src/crewai/content/agents/critique_agent.py
from crewai import Agent
from pydantic import BaseModel
from typing import List, Optional

class Issue(BaseModel):
    """问题描述"""
    type: str  # developmental, content, line_editing, copy_editing
    severity: str  # high, medium, low
    description: str
    location: str  # Chapter X, Scene Y, Paragraph Z

class RootCause(BaseModel):
    """根因描述"""
    cause: str
    impact: str

class Diagnosis(BaseModel):
    """诊断报告"""
    issues: List[Issue]
    root_causes: List[RootCause]

class CritiqueAgent:
    """诊断问题Agent"""

    def __init__(self, llm=None):
        self.agent = Agent(
            role="内容诊断专家",
            goal="识别内容问题并找出根因",
            backstory="""你是一位资深编辑，擅长诊断内容问题。
            你不仅识别表面症状，更挖掘深层根因。""",
            llm=llm
        )

    async def diagnose(self, draft: str, context: ReviewContext) -> Diagnosis:
        """执行诊断"""
        prompt = f"""诊断以下内容的问题：

        内容类型: {context.content_type}
        目标读者: {context.target_audience}

        内容:
        {draft}

        请识别:
        1. 所有问题 (类型、严重程度、位置)
        2. 根因分析
        """
        result = await self.agent.execute(prompt)
        return self._parse_diagnosis(result)

    def _parse_diagnosis(self, raw_result: str) -> Diagnosis:
        """解析诊断结果"""
        # 实现解析逻辑
        pass
```

### 3.3 RevisionAgent实现

```python
# lib/crewai/src/crewai/content/agents/revision_agent.py
class Revision(BaseModel):
    """修改处方"""
    priority: int
    action: str  # 重写、扩展、压缩、删除等
    detail: str  # 具体修改建议
    rationale: str  # 修改理由

class Prescription(BaseModel):
    """处方报告"""
    revisions: List[Revision]

class RevisionAgent:
    """开处方Agent"""

    def __init__(self, llm=None):
        self.agent = Agent(
            role="内容修改专家",
            goal="根据诊断给出具体修改建议",
            backstory="""你是一位资深编辑，擅长给出具体可执行的修改建议。
            你的建议要具体、可操作、有优先级排序。"""
        )

    async def prescribe(self, diagnosis: Diagnosis) -> Prescription:
        """生成处方"""
        prompt = f"""基于以下诊断，生成修改处方：

        诊断:
        {diagnosis.json(indent=2)}

        请为每个问题生成:
        1. 优先级 (1-5, 1最高)
        2. 修改动作 (重写/扩展/压缩/删除)
        3. 详细建议
        4. 修改理由
        """
        result = await self.agent.execute(prompt)
        return self._parse_prescription(result)
```

### 3.4 PolishAgent实现

```python
# lib/crewai/src/crewai/content/agents/polish_agent.py
class PolishAgent:
    """行级润色Agent"""

    def __init__(self, llm=None):
        self.agent = Agent(
            role="文字润色专家",
            goal="执行行级润色，不改变内容方向",
            backstory="""你是一位语言大师，擅长句子润色。
            你关注句子节奏、词汇选择、表达清晰度。
            你不改变内容，只优化表达。"""
        )

    async def execute(self, draft: str, prescription: Prescription) -> str:
        """执行润色"""
        prompt = f"""基于以下处方，对内容进行润色：

        处方:
        {prescription.json(indent=2)}

        原稿:
        {draft}

        润色要求:
        - 不改变内容方向
        - 优化句子节奏
        - 改进词汇选择
        - 保持作者声音
        """
        result = await self.agent.execute(prompt)
        return result
```

---

## 四、Phase 2: 小说检查器

### 4.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P2-T1 | `dianting_checker.py` | 垫听检查器 | P0 |
| P2-T2 | `chapter_ending_checker.py` | 章末检查器 | P0 |
| P2-T3 | `shuanggan_checker.py` | 爽感类型检查器 | P2-T1 |
| P2-T4 | `repetitive_pattern_checker.py` | 套路重复检查器 | P2-T2 |
| P2-T5 | `interiority_checker.py` | 内心描写检查器 | P0 |
| P2-T6 | `pov_checker.py` | 视角规范检查器 | P0 |
| P2-T7 | `test_novel_checkers.py` | 测试 | P2-T6 |

### 4.2 DiantingChecker实现

```python
# lib/crewai-novel/src/crewai_novel/agents/dianting_checker.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

@dataclass
class PlantedHook:
    """伏笔记录"""
    chapter: int
    hook: str
    plant_text: str
    expected_reveal_range: tuple  # (min_chapter, max_chapter)
    planted_at: datetime = field(default_factory=datetime.now)

@dataclass
class RevealRecord:
    """回收记录"""
    chapter: int
    hook: PlantedHook
    reveal_text: str
    timing_optimal: bool
    gap: int  # 章节间隔

class DiantingChecker:
    """垫听机制：伏笔回收追踪"""

    def __init__(self):
        self._plants: Dict[int, PlantedHook] = {}  # chapter -> hook
        self._reveals: List[RevealRecord] = []
        self._suspense_balance: float = 1.0  # 悬念残留量

    def track_plant(self, chapter: int, hook: str, plant_text: str,
                    expected_reveal_chapter: int) -> None:
        """记录伏笔埋设"""
        min_reveal = chapter + 5
        max_reveal = chapter + 20
        plant = PlantedHook(
            chapter=chapter,
            hook=hook,
            plant_text=plant_text,
            expected_reveal_range=(min_reveal, max_reveal)
        )
        self._plants[chapter] = plant

    def check_reveal_timing(self, chapter: int, plant_chapter: int) -> str:
        """检查回收时机"""
        gap = chapter - plant_chapter
        if gap < 5:
            return "TOO_EARLY"  # 回收太早，悬念不足
        elif gap > 20:
            return "TOO_LATE"   # 回收太晚，读者已遗忘
        return "OPTIMAL"

    def record_reveal(self, chapter: int, hook: PlantedHook,
                      reveal_text: str) -> RevealRecord:
        """记录回收"""
        record = RevealRecord(
            chapter=chapter,
            hook=hook,
            reveal_text=reveal_text,
            timing_optimal=self.check_reveal_timing(chapter, hook.chapter) == "OPTIMAL",
            gap=chapter - hook.chapter
        )
        self._reveals.append(record)
        return record

    def get_suspense_balance(self) -> float:
        """返回悬念残留量"""
        open_plants = len(self._plants) - len(self._reveals)
        return min(open_plants / 10.0, 1.0)  # 每10章保持1个悬念

    def generate_report(self) -> Dict:
        """生成垫听报告"""
        return {
            "total_plants": len(self._plants),
            "total_reveals": len(self._reveals),
            "optimal_timing_count": sum(1 for r in self._reveals if r.timing_optimal),
            "suspense_balance": self.get_suspense_balance(),
            "unresolved_hooks": [
                {"chapter": h.chapter, "hook": h.hook}
                for h in self._plants.values()
                if h not in [r.hook for r in self._reveals]
            ]
        }
```

### 4.3 ChapterEndingChecker实现

```python
# lib/crewai-novel/src/crewai_novel/agents/chapter_ending_checker.py
from dataclasses import dataclass

@dataclass
class ChapterEndingReport:
    """章末质量报告"""
    quality_score: float  # 0-100
    conditions_met: dict
    has_battle_unresolved: bool
    has_info_half_revealed: bool
    has_crisis_imminent: bool
    has_secret_pending: bool
    suggestion: Optional[str]

class ChapterEndingChecker:
    """章末质量检查器"""

    BATTLE_KEYWORDS = ["战斗", "对决", "激战", "危机", "危险"]
    REVEAL_KEYWORDS = ["原来", "真相", "竟然", "秘密", "身份"]
    CRISIS_KEYWORDS = ["突然", "危机", "灾难", "威胁", "降临"]
    SECRET_KEYWORDS = ["秘密", "隐瞒", "真实", "身份", "揭穿"]

    def check_chapter_ending(self, chapter_text: str) -> ChapterEndingReport:
        """检查最后500字"""
        last_500 = chapter_text[-500:] if len(chapter_text) > 500 else chapter_text

        conditions = {
            "battle_unresolved": self._check_pattern(last_500, self.BATTLE_KEYWORDS),
            "info_half_revealed": self._check_pattern(last_500, self.REVEAL_KEYWORDS),
            "crisis_imminent": self._check_pattern(last_500, self.CRISIS_KEYWORDS),
            "secret_pending": self._check_pattern(last_500, self.SECRET_KEYWORDS),
        }

        passed = sum(conditions.values())
        quality_score = passed / len(conditions) * 100

        return ChapterEndingReport(
            quality_score=quality_score,
            conditions_met=conditions,
            has_battle_unresolved=conditions["battle_unresolved"],
            has_info_half_revealed=conditions["info_half_revealed"],
            has_crisis_imminent=conditions["crisis_imminent"],
            has_secret_pending=conditions["secret_pending"],
            suggestion=self._generate_hook_suggestion(conditions) if passed == 0 else None
        )

    def _check_pattern(self, text: str, keywords: list) -> bool:
        """检查是否包含关键词模式"""
        # 简化实现：实际需要更复杂的模式匹配
        return any(kw in text for kw in keywords)

    def _generate_hook_suggestion(self, conditions: dict) -> str:
        """生成钩子建议"""
        suggestions = []
        if not conditions["battle_unresolved"]:
            suggestions.append("在结尾添加未解决的战斗或对峙")
        if not conditions["info_half_revealed"]:
            suggestions.append("揭露一半信息，保留另一半")
        if not conditions["crisis_imminent"]:
            suggestions.append("引入即将降临的危机")
        if not conditions["secret_pending"]:
            suggestions.append("暗示一个即将揭晓的秘密")
        return "; ".join(suggestions)
```

---

## 五、Phase 3: OutlineEngine

### 5.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P3-T1 | `outline_engine.py` | 大纲解析引擎 | P0 |
| P3-T2 | `chapter_outline.py` | 章纲数据结构 | P3-T1 |
| P3-T3 | `strand_weave.py` | Strand Weave算法 | P3-T1 |
| P3-T4 | `outline_agent.py` | OutlineAgent | P3-T1 |
| P3-T5 | `feedback_mechanism.py` | 反馈回路机制 | P3-T4 |
| P3-T6 | `test_outline_engine.py` | 测试 | P3-T5 |

### 5.2 OutlineEngine实现

```python
# lib/crewai/src/crewai/content/outline/outline_engine.py
from dataclasses import dataclass
from typing import List, Optional, Dict
import asyncio

@dataclass
class Outline:
    """大纲结构"""
    title: str
    genre: str
    target_words: int
    chapters: List['ChapterOutline']
    world_settings: Optional['WorldSettings'] = None

@dataclass
class ChapterOutline:
    """章纲结构"""
    number: int
    title: str
    summary: str
    word_target: int
    strand_type: str  # quest, fire, constellation
    key_events: List[str]
    plant_hooks: List[str]  # 本章埋设的伏笔

@dataclass
class StrandReport:
    """Strand Weave分析报告"""
    quest_ratio: float
    fire_ratio: float
    constellation_ratio: float
    warnings: List[str]

class OutlineEngine:
    """大纲解析引擎"""

    def __init__(self, llm=None):
        self.llm = llm

    def parse(self, outline_text: str, content_type: str) -> Outline:
        """将自由格式大纲转为结构化Outline"""
        # LLM解析大纲文本
        parsed = asyncio.run(self._llm_parse(outline_text, content_type))
        return self._build_outline(parsed)

    async def _llm_parse(self, text: str, content_type: str) -> dict:
        """LLM解析大纲"""
        prompt = f"""解析以下{content_type}大纲，输出结构化JSON：

        {text}

        输出格式:
        {{
            "title": "标题",
            "genre": "类型",
            "target_words": 目标字数,
            "chapters": [
                {{
                    "number": 1,
                    "title": "章节标题",
                    "summary": "章节摘要",
                    "word_target": 目标字数,
                    "strand_type": "quest|fire|constellation",
                    "key_events": ["事件1", "事件2"],
                    "plant_hooks": ["伏笔1"]
                }}
            ]
        }}
        """
        result = await self.llm.acomplete(prompt)
        return json.loads(result)

    def generate_chapters(self, outline: Outline,
                        total_chapters: int) -> List[ChapterOutline]:
        """从大纲生成章纲列表"""
        # 确保Strand Weave比例
        quest_count = int(total_chapters * 0.60)  # 60%
        fire_count = int(total_chapters * 0.25)     # 25%
        constellation_count = total_chapters - quest_count - fire_count  # 15%

        chapters = []
        for i in range(total_chapters):
            if i < quest_count:
                strand = "quest"
            elif i < quest_count + fire_count:
                strand = "fire"
            else:
                strand = "constellation"

            chapters.append(ChapterOutline(
                number=i + 1,
                title=f"第{i+1}章",
                summary="",
                word_target=outline.target_words // total_chapters,
                strand_type=strand,
                key_events=[],
                plant_hooks=[]
            ))

        return chapters

    def validate_strand_balance(self,
                               chapters: List[ChapterOutline]) -> StrandReport:
        """验证Strand Weave比例"""
        total = len(chapters)
        if total == 0:
            return StrandReport(1.0, 0.0, 0.0, ["大纲为空"])

        quest_count = sum(1 for c in chapters if c.strand_type == "quest")
        fire_count = sum(1 for c in chapters if c.strand_type == "fire")
        constellation_count = sum(1 for c in chapters if c.strand_type == "constellation")

        quest_ratio = quest_count / total
        fire_ratio = fire_count / total
        constellation_ratio = constellation_count / total

        warnings = []
        if not (0.55 <= quest_ratio <= 0.65):
            warnings.append(f"Quest比例{quest_ratio:.0%}不在55-65%范围内")
        if not (0.20 <= fire_ratio <= 0.30):
            warnings.append(f"Fire比例{fire_ratio:.0%}不在20-30%范围内")
        if not (0.10 <= constellation_ratio <= 0.20):
            warnings.append(f"Constellation比例{constellation_ratio:.0%}不在10-20%范围内")

        return StrandReport(
            quest_ratio=quest_ratio,
            fire_ratio=fire_ratio,
            constellation_ratio=constellation_ratio,
            warnings=warnings
        )

    def should_update_outline(self, draft偏离程度: float,
                             threshold: float = 0.3) -> bool:
        """判断是否需要更新大纲（反馈回路）"""
        return draft偏离程度 > threshold
```

---

## 六、Phase 4: EntityMemory

### 6.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P4-T1 | `entity_memory.py` | 实体记忆系统 | P0 |
| P4-T2 | `continuity_tracker.py` | 连贯性追踪 | P4-T1 |
| P4-T3 | `test_entity_memory.py` | 测试 | P4-T2 |

### 6.2 EntityMemory实现

```python
# lib/crewai/src/crewai/content/memory/entity_memory.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

@dataclass
class CharacterState:
    """角色状态"""
    name: str
    role: str  # protagonist, antagonist, supporting
    status: str  # alive, dead, missing
    location: str
    relationships: Dict[str, str]  # name -> relationship
    emotional_state: str
    physical_state: str
    goals: List[str]
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class LocationState:
    """地点状态"""
    name: str
    description: str
    significance: str  # major, minor
    associated_characters: List[str]
    current_events: List[str]
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class ConsistencyResult:
    """一致性检查结果"""
    is_consistent: bool
    claim: str
    existing_facts: List[str]
    conflict: Optional[str] = None

class EntityMemory:
    """跨章节追踪角色/地点/势力状态"""

    def __init__(self, storage_path: Optional[str] = None):
        self._characters: Dict[str, CharacterState] = {}
        self._locations: Dict[str, LocationState] = {}
        self._factions: Dict[str, dict] = {}
        self._world_rules: List[str] = []
        self._storage_path = storage_path

    def track(self, chapter_output: 'ChapterOutput') -> None:
        """从章节输出提取实体更新记忆"""
        for character in chapter_output.characters:
            self._update_character(character)

        for location in chapter_output.locations:
            self._update_location(location)

        for event in chapter_output.world_events:
            self._update_world_rules(event)

    def _update_character(self, character: CharacterState) -> None:
        """更新角色状态"""
        existing = self._characters.get(character.name)
        if existing:
            # 合并状态
            self._characters[character.name] = self._merge_character_state(
                existing, character
            )
        else:
            self._characters[character.name] = character

    def _update_location(self, location: LocationState) -> None:
        """更新地点状态"""
        self._locations[location.name] = location

    def _update_world_rules(self, event: str) -> None:
        """更新世界规则"""
        # 从事件中提取并更新世界规则
        pass

    def _merge_character_state(self, old: CharacterState,
                              new: CharacterState) -> CharacterState:
        """合并角色状态"""
        return CharacterState(
            name=new.name,
            role=new.role or old.role,
            status=new.status or old.status,
            location=new.location or old.location,
            relationships={**old.relationships, **new.relationships},
            emotional_state=new.emotional_state or old.emotional_state,
            physical_state=new.physical_state or old.physical_state,
            goals=new.goals or old.goals,
            updated_at=datetime.now()
        )

    def get_context(self, chapter: int) -> Dict[str, Any]:
        """获取指定章节需要的上下文"""
        return {
            "characters": self._characters,
            "locations": self._locations,
            "factions": self._factions,
            "world_rules": self._world_rules,
            "active_plot_threads": self._get_active_plot_threads()
        }

    def _get_active_plot_threads(self) -> List[str]:
        """获取活跃的剧情线"""
        # 实现剧情线追踪
        pass

    def check_consistency(self, claim: str) -> ConsistencyResult:
        """检查新内容与已建立设定的一致性"""
        # 简化的实现
        relevant_facts = self._find_relevant_facts(claim)

        for fact in relevant_facts:
            if self._conflicts(fact, claim):
                return ConsistencyResult(
                    is_consistent=False,
                    claim=claim,
                    existing_facts=relevant_facts,
                    conflict=f"新声明与已有事实冲突: {fact}"
                )

        return ConsistencyResult(
            is_consistent=True,
            claim=claim,
            existing_facts=relevant_facts
        )

    def _find_relevant_facts(self, claim: str) -> List[str]:
        """查找相关事实"""
        # 实现语义搜索
        pass

    def _conflicts(self, fact: str, claim: str) -> bool:
        """判断是否冲突"""
        # 实现冲突检测
        pass

    def save(self) -> None:
        """保存到磁盘"""
        if not self._storage_path:
            return

        data = {
            "characters": {k: vars(v) for k, v in self._characters.items()},
            "locations": {k: vars(v) for k, v in self._locations.items()},
            "factions": self._factions,
            "world_rules": self._world_rules
        }

        with open(self._storage_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load(self) -> None:
        """从磁盘加载"""
        if not self._storage_path:
            return

        with open(self._storage_path, 'r') as f:
            data = json.load(f)

        self._characters = {
            k: CharacterState(**v) for k, v in data.get("characters", {}).items()
        }
        self._locations = {
            k: LocationState(**v) for k, v in data.get("locations", {}).items()
        }
        self._factions = data.get("factions", {})
        self._world_rules = data.get("world_rules", [])
```

---

## 七、Phase 5: NovelCrew

### 7.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P5-T1 | `world_crew.py` | WorldCrew | P3 |
| P5-T2 | `outline_crew.py` | OutlineCrew | P3 |
| P5-T3 | `writing_crew.py` | WritingCrew | P5-T1, P5-T2 |
| P5-T4 | `review_crew.py` | ReviewCrew | P2, P4 |
| P5-T5 | `novel_crew.py` | NovelCrew编排 | P5-T1~4 |
| P5-T6 | `test_novel_crew.py` | 集成测试 | P5-T5 |

### 7.2 NovelCrew实现 (v1.1增强 - 支持UnifiedContentCrew)

```python
# lib/crewai-novel/src/crewai_novel/crews/novel_crew.py
from crewai import Crew, Agent, Task
from crewai.utilities.events import event_emitter
from crewai.content.base import BaseContentCrew
from crewai.content.unified import UnifiedContentCrew, UnifiedContentState, QualityGateError
from crewai.content.types import ContentTypeEnum, ContentConfig
from crewai.content.memory.entity_memory import EntityMemory
from crewai.content.outline.outline_engine import OutlineEngine

class NovelCrew(UnifiedContentCrew):
    """小说生成Crew - 继承统一架构

    4阶段Pipeline:
    1. build_world()    - 世界观构建
    2. plan_outline()   - 情节大纲
    3. generate_chapters() - 分章生成
    4. review_all()     - 全局审核
    """

    def __init__(
        self,
        topic: str,
        target_words: int = 100000,
        style: str = "urban",
        enable_dianting: bool = True,
        enable_chapter_ending: bool = True,
        enable_shuanggan: bool = True,
        feedback_loop: bool = True,
        enable_checkpoint: bool = True,
        enable_human_review: bool = False,
        **kwargs
    ):
        config = ContentConfig(
            content_type=ContentTypeEnum.NOVEL,
            target_words=target_words,
            style=style,
            enable_dianting=enable_dianting,
            enable_chapter_ending=enable_chapter_ending,
            enable_shuanggan=enable_shuanggan,
            enable_feedback_loop=feedback_loop
        )
        super().__init__(
            content_type="novel",
            config=config,
            enable_checkpoint=enable_checkpoint,
            enable_human_review=enable_human_review,
            **kwargs
        )

        self.topic = topic
        self.target_words = target_words
        self.style = style
        self.enable_dianting = enable_dianting
        self.enable_chapter_ending = enable_chapter_ending
        self.enable_shuanggan = enable_shuanggan
        self.feedback_loop = feedback_loop

        # 核心组件
        self.outline_engine = OutlineEngine(llm=self.llm)
        self.entity_memory = EntityMemory()
        self.dianting_checker = None
        self.chapter_ending_checker = None

    def _create_agents(self) -> Dict[str, Agent]:
        from crewai_novel.agents import (
            WorldAgent, PlotAgent, DraftAgent,
            CritiqueAgent, RevisionAgent, PolishAgent,
            DiantingChecker, ChapterEndingChecker,
            ShuangganPatternChecker, RepetitivePatternChecker,
            InteriorityChecker, POVChecker
        )

        agents = {
            "world": WorldAgent(llm=self.llm),
            "plot": PlotAgent(llm=self.llm),
            "draft": DraftAgent(llm=self.llm),
            "critique": CritiqueAgent(llm=self.llm),
            "revision": RevisionAgent(llm=self.llm),
            "polish": PolishAgent(llm=self.llm),
        }

        if self.enable_dianting:
            self.dianting_checker = DiantingChecker()
            agents["dianting"] = self.dianting_checker

        if self.enable_chapter_ending:
            self.chapter_ending_checker = ChapterEndingChecker()
            agents["chapter_ending"] = self.chapter_ending_checker

        if self.enable_shuanggan:
            agents["shuanggan"] = ShuangganPatternChecker(llm=self.llm)

        agents["repetitive"] = RepetitivePatternChecker()
        agents["interiority"] = InteriorityChecker(llm=self.llm)
        agents["pov"] = POVChecker(llm=self.llm)

        return agents

    def _create_tasks(self) -> Dict[str, Task]:
        # 创建任务
        tasks = {
            "world_building": Task(
                description=f"为小说'{self.topic}'构建世界观",
                agent=self._agents["world"],
                expected_output="世界观设定文档"
            ),
            "plot_planning": Task(
                description="规划情节结构(Strand Weave)",
                agent=self._agents["plot"],
                expected_output="情节大纲"
            ),
        }
        return tasks

    def _create_workflow(self) -> Crew:
        # 构建工作流程
        crew = Crew(
            agents=list(self._agents.values()),
            tasks=list(self._tasks.values()),
            process=Process.sequential,
            memory=self.entity_memory
        )
        return crew

    def kickoff(self) -> NovelOutput:
        """执行小说生成 - 支持Checkpoint恢复

        Pipeline:
        1. build_world()     - 世界观构建
        2. plan_outline()   - 情节大纲
        3. generate_chapters() - 分章生成 (含反馈回路)
        4. review_all()     - 全局审核
        """
        import time
        start = time.time()

        # 初始化状态
        state = UnifiedContentState(
            topic=self.topic,
            content_type="novel",
            step_count=0,
            metadata={"target_words": self.target_words, "style": self.style}
        )

        # 从Checkpoint恢复 (如启用)
        if self.enable_checkpoint:
            checkpoint = self._load_checkpoint()
            if checkpoint:
                state = checkpoint

        try:
            # Stage 1: World Building
            if not state.get("world_output"):
                state = self._stage_world(state)

            # Stage 2: Outline Planning
            if not state.get("outline_output"):
                state = self._stage_outline(state)

            # Stage 3: Per-chapter writing loop
            if not state.get("draft_output"):
                state = self._stage_generate(state)

            # Stage 4: Review
            if not state.get("review_output"):
                state = self._stage_review(state)

        except QualityGateError as e:
            # 保存失败状态
            self._save_checkpoint(state)
            raise

        # 保存成功状态
        if self.enable_checkpoint:
            self._save_checkpoint(state)

        execution_time = time.time() - start

        return NovelOutput(
            title=state.get("outline_output", {}).get("title", self.topic),
            chapters=state.get("draft_output", {}).get("chapters", []),
            world_settings=state.get("world_output", {}),
            outline=state.get("outline_output", {}),
            dianting_report=state.get("metadata", {}).get("dianting_report"),
            execution_time=execution_time
        )

    def _write_chapter(self, chapter_outline, world_output) -> ChapterOutput:
        """单章写作流程"""
        # Draft → Review → Critique → Revision → Polish
        draft = self._agents["draft"].write(chapter_outline, world_output)

        # 并行审查
        review_results = self._run_review_crew(draft, chapter_outline)

        # 根据审查结果修改
        diagnosis = self._agents["critique"].diagnose(draft, review_results)
        prescription = self._agents["revision"].prescribe(diagnosis)
        final = self._agents["polish"].execute(draft, prescription)

        return ChapterOutput(
            number=chapter_outline.number,
            title=chapter_outline.title,
            content=final,
            review_results=review_results
        )

    def _run_review_crew(self, draft, context) -> ReviewResults:
        """运行审查Crew"""
        # 并行执行多个检查器
        tasks = []

        for checker_name, checker in self._agents.items():
            if hasattr(checker, 'check'):
                tasks.append(checker.check(draft, context))

        results = asyncio.gather(*tasks)
        return ReviewResults(results=dict(zip(self._agents.keys(), results)))

    # ==================== UnifiedContentCrew Stage Implementations ====================

    def _stage_world(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 1: 世界观构建"""
        world_crew = self._run_world_crew()
        world_output = world_crew.kickoff()

        # 评估世界观质量
        quality_score = self._evaluate_world_quality(world_output)

        state["world_output"] = world_output.__dict__ if hasattr(world_output, '__dict__') else {}
        state["world_quality_score"] = quality_score
        state["step_count"] = state.get("step_count", 0) + 1

        return state

    def _stage_outline(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 2: 大纲规划"""
        world_output = state.get("world_output", {})
        outline = self._run_outline_crew(world_output)

        # 评估大纲质量
        quality_score = self._evaluate_outline_quality(outline)

        state["outline_output"] = outline.__dict__ if hasattr(outline, '__dict__') else {}
        state["outline_quality_score"] = quality_score
        state["step_count"] = state.get("step_count", 0) + 1

        # 人工审核点 (可选)
        if self.enable_human_review:
            self._await_human_review("outline", outline)

        return state

    def _stage_generate(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 3: 章节生成 (含反馈回路)"""
        outline = state.get("outline_output", {})
        world_output = state.get("world_output", {})

        chapters = []
        total_chapters = outline.get("chapters", []) if isinstance(outline, dict) else []

        for chapter_outline in total_chapters:
            # 检查是否需要恢复
            chapter_num = chapter_outline.number if hasattr(chapter_outline, 'number') else 0
            if self._is_chapter_in_checkpoint(chapter_num):
                chapters.append(self._get_chapter_from_checkpoint(chapter_num))
                continue

            chapter = self._write_chapter(chapter_outline, world_output)
            chapters.append(chapter)

            # 检查反馈回路
            if self.feedback_loop and self._should_update_outline(chapter):
                outline = self._update_outline(outline, chapter)

            # 保存章节checkpoint
            if self.enable_checkpoint:
                self._save_chapter_checkpoint(chapter_num, chapter)

        draft_output = {
            "chapters": chapters,
            "total_words": sum(c.word_count for c in chapters if hasattr(c, 'word_count'))
        }
        quality_score = self._evaluate_draft_quality(draft_output)

        state["draft_output"] = draft_output
        state["draft_quality_score"] = quality_score
        state["step_count"] = state.get("step_count", 0) + 1

        return state

    def _stage_review(self, state: UnifiedContentState) -> UnifiedContentState:
        """Stage 4: 全局审核"""
        draft_output = state.get("draft_output", {})
        chapters = draft_output.get("chapters", [])

        # 并行审核所有章节
        review_tasks = []
        for chapter in chapters:
            if hasattr(self._agents["critique"], 'diagnose'):
                review_tasks.append(
                    self._agents["critique"].diagnose(chapter.content, {})
                )

        if review_tasks:
            import asyncio
            review_results = asyncio.gather(*review_tasks)
            # 汇总审核结果
            state["metadata"]["review_summary"] = self._summarize_reviews(review_results)

        state["review_output"] = {"status": "completed", "chapters_reviewed": len(chapters)}
        state["review_quality_score"] = 0.85  # TODO: 实际计算
        state["step_count"] = state.get("step_count", 0) + 1

        return state

    # ==================== Helper Methods ====================

    def _evaluate_world_quality(self, world_output) -> float:
        """评估世界观构建质量"""
        # TODO: 实现质量评估逻辑
        return 0.8

    def _evaluate_outline_quality(self, outline) -> float:
        """评估大纲质量"""
        # TODO: 实现质量评估逻辑
        return 0.75

    def _evaluate_draft_quality(self, draft_output: dict) -> float:
        """评估草稿质量"""
        # TODO: 实现质量评估逻辑
        chapters = draft_output.get("chapters", [])
        if not chapters:
            return 0.0
        # 基于字数完成度评估
        total_words = draft_output.get("total_words", 0)
        target_words = self.target_words
        completion_ratio = min(total_words / target_words, 1.0)
        return 0.5 + (completion_ratio * 0.5)

    def _is_chapter_in_checkpoint(self, chapter_num: int) -> bool:
        """检查章节是否已存在于checkpoint"""
        # TODO: 实现
        return False

    def _get_chapter_from_checkpoint(self, chapter_num: int):
        """从checkpoint获取章节"""
        # TODO: 实现
        pass

    def _save_chapter_checkpoint(self, chapter_num: int, chapter) -> None:
        """保存章节checkpoint"""
        # TODO: 实现
        pass

    def _load_checkpoint(self) -> UnifiedContentState:
        """加载checkpoint"""
        # TODO: 实现
        return None

    def _summarize_reviews(self, review_results) -> dict:
        """汇总审核结果"""
        # TODO: 实现
        return {"total_issues": 0, "resolved": 0}

    def _await_human_review(self, stage: str, content) -> None:
        """等待人工审核"""
        # TODO: 实现
        pass
```

---

## 八、Phase 6: PodcastCrew

### 8.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P6-T1 | `preshow_crew.py` | PreShowCrew | P0 |
| P6-T2 | `intro_crew.py` | IntroCrew | P6-T1 |
| P6-T3 | `segment_crew.py` | SegmentCrew | P6-T2 |
| P6-T4 | `interview_crew.py` | InterviewCrew | P6-T3 |
| P6-T5 | `ad_read_crew.py` | AdReadCrew | P6-T3 |
| P6-T6 | `outro_crew.py` | OutroCrew | P6-T4, P6-T5 |
| P6-T7 | `shownotes_crew.py` | ShowNotesCrew | P6-T6 |
| P6-T8 | `podcast_crew.py` | PodcastCrew编排 | P6-T1~7 |
| P6-T9 | `test_podcast_crew.py` | 集成测试 | P6-T8 |

### 8.2 PodcastCrew实现

```python
# lib/crewai-podcast/src/crewai_podcast/crews/podcast_crew.py
from crewai import Crew, Agent, Task
from crewai.content.base import BaseContentCrew
from crewai.content.types import ContentTypeEnum, ContentConfig

class PodcastCrew(BaseContentCrew):
    """播客生成Crew"""

    def __init__(
        self,
        topic: str,
        duration_minutes: int = 30,
        hosts: int = 2,
        style: str = "conversational",
        include_interview: bool = False,
        include_ads: bool = False,
        **kwargs
    ):
        config = ContentConfig(
            content_type=ContentTypeEnum.PODCAST,
            target_words=duration_minutes * 150,  # 约150字/分钟
            style=style
        )
        super().__init__(content_type="podcast", config=config, **kwargs)

        self.topic = topic
        self.duration_minutes = duration_minutes
        self.hosts = hosts
        self.style = style
        self.include_interview = include_interview
        self.include_ads = include_ads

    def _create_workflow(self) -> Crew:
        """播客工作流程"""
        # PreShow → Intro → Segment(s) → Interview (optional) →
        # AdRead(s) (optional) → Outro → ShowNotes
        crew = Crew(
            agents=list(self._agents.values()),
            tasks=self._create_podcast_tasks(),
            process=Process.sequential
        )
        return crew

    def kickoff(self) -> PodcastOutput:
        """执行播客生成"""
        result = super().kickoff()
        return PodcastOutput(
            topic=self.topic,
            duration=self.duration_minutes,
            script=result.content,
            timestamps=self._extract_timestamps(result),
            shownotes=self._generate_shownotes(result),
            transcript=result.content
        )
```

---

## 九、Phase 7-8: ScriptCrew

### 9.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P7-T1 | `beat_sheet_agent.py` | BeatSheetAgent | P0 |
| P7-T2 | `cinematography_agent.py` | CinematographyAgent | P7-T1 |
| P7-T3 | `visual_motif_tracker.py` | VisualMotifTracker | P7-T2 |
| P7-T4 | `scene_crew.py` | SceneCrew | P7-T2 |
| P7-T5 | `dialogue_crew.py` | DialogueCrew | P7-T4 |
| P7-T6 | `script_crew.py` | ScriptCrew编排 | P7-T1~5, P4 |
| P7-T7 | `test_script_crew.py` | 集成测试 | P7-T6 |

### 9.2 BeatSheetAgent实现

```python
# lib/crewai-script/src/crewai_script/agents/beat_sheet_agent.py
from dataclasses import dataclass
from typing import List

@dataclass
class Beat:
    """单个Beat"""
    number: int
    name: str
    description: str
    scene_purpose: str  # 谁想要什么？障碍是什么？
    turning_point: bool

@dataclass
class BeatSheet:
    """分镜表"""
    act: str  # Act I, Act IIa, etc.
    beats: List[Beat]
    total_runtime_estimate: int  # 分钟

class BeatSheetAgent:
    """分镜表Agent：结构→场景过渡"""

    def __init__(self, llm=None):
        self.agent = Agent(
            role="分镜规划师",
            goal="将结构分解为可执行的场景Beats",
            backstory="""你是一位资深编剧，擅长将故事结构
            分解为具体的场景转折点。"""
        )

    async def generate_beat_sheet(self, structure, target_runtime: int) -> List[BeatSheet]:
        """生成分镜表"""
        prompt = f"""基于以下结构，生成分镜表：

        结构:
        {structure.json(indent=2)}

        目标时长: {target_runtime}分钟

        分镜表格式:
        - 每个Act分解为多个Beat
        - 每个Beat有场景目的: 谁想要什么？障碍是什么？
        - 标记转折点(turning_point)
        """
        result = await self.agent.execute(prompt)
        return self._parse_beat_sheet(result)
```

---

## 十、Phase 9-10: BlogCrew

### 10.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P9-T1 | `hook_agent.py` | HookAgent (Phase 0) | P0 |
| P9-T2 | `title_agent.py` | TitleAgent | P9-T1 |
| P9-T3 | `thumbnail_agent.py` | ThumbnailConceptAgent | P9-T2 |
| P9-T4 | `seo_agent.py` | SEOAgent (多平台) | P9-T1 |
| P9-T5 | `platform_adapter_agent.py` | PlatformAdapterAgent | P9-T4 |
| P9-T6 | `blog_crew.py` | BlogCrew编排 | P9-T1~5 |
| P9-T7 | `test_blog_crew.py` | 集成测试 | P9-T6 |

### 10.2 HookAgent实现

```python
# lib/crewai-blog/src/crewai_blog/agents/hook_agent.py
from typing import List

@dataclass
class HookOption:
    """钩子选项"""
    variant: int
    hook_text: str
    hook_type: str  # question, statement, statistic, story, etc.
    engagement_score: float  # 预估参与度

class HookAgent:
    """钩子生成Agent (BlogCrew Phase 0)"""

    def __init__(self, llm=None):
        self.agent = Agent(
            role="钩子创作专家",
            goal="生成5-10个高吸引力钩子变体",
            backstory="""你是一位内容营销大师，擅长创作
            前30秒抓住读者注意力的钩子。"""
        )

    async def generate_hooks(self, topic: str, count: int = 5) -> List[HookOption]:
        """生成钩子变体"""
        prompt = f"""为以下主题生成{count}个钩子变体：

        主题: {topic}

        要求:
        1. 每个钩子必须能在前30秒抓住注意力
        2. 变体类型多样: 问题、数据、故事、声明、对比
        3. 每个钩子标注预估参与度(1-10)
        """
        result = await self.agent.execute(prompt)
        return self._parse_hook_options(result)
```

---

## 十一、Phase 11: CLI集成

### 11.1 任务清单

| 任务ID | 文件 | 描述 | 依赖 |
|--------|------|------|------|
| P11-T1 | `create_novel.py` | crewai create novel | P5 |
| P11-T2 | `create_script.py` | crewai create script | P8 |
| P11-T3 | `create_blog.py` | crewai create blog | P10 |
| P11-T4 | `create_podcast.py` | crewai create podcast | P6 |
| P11-T5 | `skills_integration.py` | 技能市场集成 | - |
| P11-T6 | `test_cli.py` | CLI测试 | P11-T1~5 |

### 11.2 CLI命令

```python
# lib/crewai/src/crewai/cli/commands/create_novel.py
import click
from crewai.novel import NovelCrew

@click.command()
@click.argument('topic')
@click.option('--words', default=100000, help='目标字数')
@click.option('--style', default='urban', help='小说风格')
@click.option('--output', default='./novel_output', help='输出目录')
def create_novel(topic, words, style, output):
    """创建小说项目"""
    crew = NovelCrew(
        topic=topic,
        target_words=words,
        style=style
    )

    click.echo(f"开始生成小说: {topic}")
    result = crew.kickoff()

    # 保存结果
    save_novel_output(result, output)
    click.echo(f"小说已生成: {output}")
```

---

## 十二、测试策略

### 12.1 测试分层

```
┌─────────────────────────────────────┐
│         集成测试 (Integration)         │
│   完整Crew流程，端到端验证            │
├─────────────────────────────────────┤
│           单元测试 (Unit)              │
│   Agent、Checker、Engine独立测试        │
├─────────────────────────────────────┤
│          模拟测试 (Mock)               │
│   LLM调用mock，隔离外部依赖            │
└─────────────────────────────────────┘
```

### 12.2 测试覆盖率要求

| 组件 | 覆盖率目标 |
|------|-----------|
| Core (base, types) | 90%+ |
| OutlineEngine | 85%+ |
| EntityMemory | 85%+ |
| ReviewPipeline | 80%+ |
| EditPipeline | 80%+ |
| NovelCrew | 75%+ |
| ScriptCrew | 75%+ |
| BlogCrew | 75%+ |
| PodcastCrew | 75%+ |

### 12.3 关键测试用例

```python
# tests/content/unit/test_dianting_checker.py
def test_plant_and_reveal_timing():
    checker = DiantingChecker()

    # 埋设伏笔
    checker.track_plant(
        chapter=1,
        hook="神秘剑客身份",
        plant_text="据说他是百年前消失的剑圣传人",
        expected_reveal_chapter=10
    )

    # 太早回收
    assert checker.check_reveal_timing(3, 1) == "TOO_EARLY"

    # 最佳时机
    assert checker.check_reveal_timing(10, 1) == "OPTIMAL"

    # 太晚回收
    assert checker.check_reveal_timing(25, 1) == "TOO_LATE"

# tests/content/unit/test_chapter_ending_checker.py
def test_chapter_ending_has_hook():
    checker = ChapterEndingChecker()

    text_with_battle = "战斗正酣，突然敌人使出了绝招..."

    result = checker.check_chapter_ending(text_with_battle)

    assert result.has_battle_unresolved == True
    assert result.quality_score >= 50

# tests/content/integration/test_novel_crew.py
def test_novel_crew_generates_10_chapters():
    crew = NovelCrew(
        topic="都市修仙",
        target_words=50000,
        style="xianxia"
    )

    result = crew.kickoff()

    assert len(result.chapters) >= 10
    assert result.dianting_report is not None
```

---

## 十三、里程碑验收

| 里程碑 | 验收标准 | 测试用例 |
|--------|----------|----------|
| **M1: 核心抽象** | ContentType + BaseCrew可实例化 | `test_base_crew_*` |
| **M2: 小说MVP** | 生成10章完整小说 | `test_novel_crew_generates_10_chapters` |
| **M3: 播客MVP** | 生成30分钟播客脚本 | `test_podcast_crew_*` |
| **M4: 剧本MVP** | 生成电影剧本含BeatSheet | `test_script_crew_*` |
| **M5: 博客MVP** | 生成SEO优化文章 | `test_blog_crew_*` |
| **M6: 技能集成** | `crewai create novel` 可执行 | `test_cli_create_*` |

---

## 十四、依赖关系总览

```
Phase 0 (P0) ──────────────────────────────────────────┐
    │                                                       │
    ├──► Phase 1 (P0) ───────────────────────────────────┤
    │         CritiqueAgent + RevisionAgent + PolishAgent   │
    │                                                       │
    ├──► Phase 2 (P0) ───────────────────────────────────┤
    │         DiantingChecker + ChapterEndingChecker       │
    │                                                       │
    ├──► Phase 3 (P0) ───────────────────────────────────┤
    │         OutlineEngine + 反馈回路                     │
    │                                                       │
    └──► Phase 4 (P0) ───────────────────────────────────┘
              EntityMemory
                                │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ◄── Phase 5 (P0)    ◄── Phase 6 (P0)    ◄── Phase 7 (P1)
    NovelCrew              PodcastCrew          BeatSheetAgent
          │                       │                   │
          │                       │                   ▼
          │                       │              Phase 8 (P1)
          │                       │              ScriptCrew
          │                       │
          │                       │
    ──► Phase 11 (P2) ◄──┘
          CLI集成
```

---

## 十五、v1.1改进总结 (基于行业最佳实践)

### 15.1 核心改进

| 改进项 | 原设计 | v1.1改进 | 参考来源 |
|--------|--------|----------|----------|
| **状态管理** | 分散在各个Crew | UnifiedContentState (TypedDict) | LangGraph StateGraph |
| **Checkpoint** | 无 | 支持持久化恢复 | LangGraph Checkpoint |
| **质量门控** | 无 | StageGate类 | Azure质量门控 |
| **Pipeline架构** | 分离设计 | 4阶段统一Pipeline | Azure Multi-Agent |
| **事件驱动** | 无 | Flow装饰器 (@start/@listen) | crewAI Flows |
| **人工审核** | 无 | 可选审核点 | Azure Human-in-loop |

### 15.2 统一Pipeline收益

```
复用性提升:
├── World阶段: Novel/Script/Blog/Podcast均可复用
├── Outline阶段: 所有内容类型可复用
├── Generate阶段: 类型特定实现
└── Review阶段: 可配置检查器组合

质量保证:
├── 每阶段质量评分
├── StageGate阈值检查
├── Checkpoint保存中间状态
└── 人工审核点 (可选)
```

### 15.3 迁移计划

```
Phase 0.1: 实现UnifiedContentState和QualityGateError
Phase 0.2: 实现UnifiedContentCrew基类
Phase 0.3: NovelCrew迁移到统一架构
Phase 0.4: ScriptCrew迁移
Phase 0.5: BlogCrew迁移
Phase 0.6: PodcastCrew迁移
```

### 15.4 参考来源

- [crewAI Official Docs](https://docs.crewai.com/)
- [crewAI GitHub](https://github.com/joaomdmoura/crewAI)
- [crewAI-examples](https://github.com/crewAIInc/crewAI-examples)
- [Azure/multi-agent-content-creation](https://github.com/Azure/multi-agent-content-creation)
- [LangGraph StateGraph Patterns](https://blog.csdn.net/zyctimes/article/details/159043014)
- [LangGraph Checkpoint Deep Dive](https://blog.csdn.net/hou478410969/article/details/159199294)

---

*文档版本: v1.1*
*创建日期: 2026-03-20*
*最后更新: 2026-03-29 (整合行业最佳实践)*
