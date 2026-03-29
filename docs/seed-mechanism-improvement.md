# Seed 机制改进设计方案

> 创建日期: 2026-03-29
> 状态: 设计完成

---

## 一、问题总结

### 1.1 现有问题列表

| ID | 问题 | 严重程度 |
|----|------|----------|
| P1 | Seed 验证后重置过于粗暴，丢失所有进度 | 高 |
| P2 | LLM Seed 传递假设过强，无 fallback | 中 |
| P3 | Variant 参数未暴露，无法生成主题变体 | 低 |
| P4 | dirty_chapters 在 seed 不匹配时丢失 | 中 |
| P5 | has_core_content_changed() 未与 seed 验证联动 | 中 |
| P6 | Approval Mode 与 Seed 冲突 | 中 |
| P7 | seed 生成参数未记录，无法验证来源 | 低 |

---

## 二、参考模式

### 2.1 LangGraph Checkpoint 核心原则

```
1. Checkpoint = State 的"可恢复快照"
2. Task = 可缓存执行单元 (memoized execution unit)
3. Replay = 基于 checkpoint 的确定性重放
   - 已完成 Task → 读取缓存结果
   - 未完成 Task → 重新执行
```

**关键洞察**: Seed 不应该控制是否加载状态，而应该控制**哪些阶段需要重新生成**。

### 2.2 改进原则

| 原则 | 描述 |
|------|------|
| **渐进式重置** | 不整体丢弃，而是按阶段选择性重置 |
| **Seed 影响输出** | Seed 控制随机性，不控制状态加载 |
| **变更检测** | 通过 hash 而非 seed 控制是否重新生成 |
| **审批保留** | 审批历史应持久化，不因参数变更丢失 |

---

## 三、改进设计

### 3.1 核心概念重构

#### 旧模型:
```
Seed 验证失败 → 重置整个状态 → 从头开始
```

#### 新模型 (基于 LangGraph):
```
Seed 验证 → 确定重放起点 → 增量生成
       ↓
   world_data 未变 → 保留
   outline 未变 → 保留
   chapters 未变 → 保留
```

### 3.2 Seed 元数据分离

```python
@dataclass
class SeedConfig:
    """Seed 配置 - 记录 seed 的来源和生成参数"""
    seed: str                    # 实际的 seed 值
    topic: str                   # 原始 topic
    genre: str                   # 原始 genre
    style: str                   # 原始 style
    variant: str | None = None   # 变体标识
    version: int = 1             # seed 版本

    def generate_seed() -> str:
        """从参数生成 seed"""
        combined = f"{self.topic}|{self.genre}|{self.style}|{self.variant or 'default'}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]

    def matches(self, other: "SeedConfig") -> bool:
        """检查配置是否兼容（不需要完全相等）"""
        # 核心参数匹配即可
        return (
            self.topic == other.topic and
            self.genre == other.genre and
            self.style == other.style
        )
```

### 3.3 阶段级状态管理

```python
class PipelineState:
    """改进后的 PipelineState"""

    # Seed 元数据
    seed_config: SeedConfig | None = None

    # 阶段级状态
    stage_states: dict[str, StageState] = field(default_factory=dict)

    def get_replay_plan(self, new_seed_config: SeedConfig) -> ReplayPlan:
        """计算重放计划

        基于新旧 seed_config，确定哪些阶段需要重新生成。

        Returns:
            ReplayPlan: 包含需要重新生成的阶段列表
        """
        if not self.seed_config:
            return ReplayPlan(regenerate_all=True)

        # 检查核心参数是否变化
        if not self.seed_config.matches(new_seed_config):
            # 核心参数变化，需要重新生成 world + outline
            return ReplayPlan(
                regenerate_from="world",
                preserve=["chapters"]  # 如果有的话
            )

        # 检查大纲 hash
        if self.has_core_content_changed():
            return ReplayPlan(
                regenerate_from="outline",
                preserve=["chapters"]
            )

        # 检查脏章节
        if self.dirty_chapters:
            return ReplayPlan(
                regenerate_from="chapters",
                dirty_chapters=list(self.dirty_chapters)
            )

        return ReplayPlan(replay_all=False)

    def preserve_approval_history(self) -> dict:
        """保留审批历史用于恢复"""
        return {
            "stage_statuses": self.stage_statuses.copy(),
            "approval_history": self.approval_history.copy(),
        }
```

### 3.4 脏数据追踪改进

```python
class DirtyTracker:
    """追踪数据变更"""

    def __init__(self):
        self.dirty_fields: dict[str, bool] = {}  # field -> is_dirty
        self.original_values: dict[str, Any] = {}

    def mark_dirty(self, field: str) -> None:
        """标记字段为脏"""
        if field not in self.original_values:
            self.original_values[field] = self._get_current_value(field)
        self.dirty_fields[field] = True

    def get_dirty_fields(self) -> list[str]:
        """获取所有脏字段"""
        return [f for f, is_dirty in self.dirty_fields.items() if is_dirty]

    def is_dirty(self, field: str) -> bool:
        return self.dirty_fields.get(field, False)
```

### 3.5 LLM Seed 处理改进

```python
def set_llm_seed(llm, seed: str) -> bool:
    """设置 LLM seed，支持 fallback

    Returns:
        bool: 是否成功设置 seed
    """
    if not llm:
        return False

    # 方法1: 直接属性
    if hasattr(llm, 'seed'):
        try:
            llm_seed = int(seed, 16) % (2**32)
            llm.seed = llm_seed
            logger.info(f"LLM seed set via attribute: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via attribute: {e}")

    # 方法2: 方法调用
    if hasattr(llm, 'set_seed'):
        try:
            llm_seed = int(seed, 16) % (2**32)
            llm.set_seed(llm_seed)
            logger.info(f"LLM seed set via method: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via method: {e}")

    # 方法3: 配置参数 (需要在调用前设置)
    if hasattr(llm, 'config'):
        try:
            llm_seed = int(seed, 16) % (2**32)
            llm.config["seed"] = llm_seed
            logger.info(f"LLM seed set via config: {llm_seed}")
            return True
        except Exception as e:
            logger.warning(f"Failed to set seed via config: {e}")

    logger.warning(f"LLM does not support seed setting")
    return False
```

---

## 四、重放算法

### 4.1 ReplayPlan 定义

```python
@dataclass
class ReplayPlan:
    """重放计划"""
    regenerate_all: bool = False      # 是否全部重新生成
    replay_all: bool = False         # 是否全部重放（使用缓存）
    regenerate_from: str | None = None  # 从哪个阶段开始重新生成
    preserve: list[str] = None       # 保留的阶段数据
    dirty_chapters: list[int] = None  # 需要重新生成的章节

    def should_regenerate_world(self) -> bool:
        return self.regenerate_all or self.regenerate_from == "world"

    def should_regenerate_outline(self) -> bool:
        return self.regenerate_all or self.regenerate_from in ("world", "outline")

    def should_regenerate_chapters(self) -> bool:
        if self.regenerate_all or self.regenerate_from in ("world", "outline", "chapters"):
            return True
        return bool(self.dirty_chapters)

    def get_chapters_to_regenerate(self) -> list[int] | None:
        if self.regenerate_all or not self.dirty_chapters:
            return None
        return self.dirty_chapters
```

### 4.2 重放执行流程

```python
def kickoff_with_replay(
    self,
    new_seed_config: SeedConfig,
    pipeline_state_path: str | None = None
) -> BaseCrewOutput:
    """带重放功能的 kickoff"""

    # 1. 加载或创建状态
    if pipeline_state_path and os.path.exists(pipeline_state_path):
        state = PipelineState.load(pipeline_state_path)
    else:
        state = PipelineState()

    # 2. 计算重放计划
    replay_plan = state.get_replay_plan(new_seed_config)

    # 3. 记录原始审批历史
    approval_preserve = state.preserve_approval_history() if not replay_plan.regenerate_all else {}

    # 4. 执行重放
    if replay_plan.regenerate_all:
        state = self._regenerate_all(new_seed_config)
    elif replay_plan.should_regenerate_world():
        state = self._regenerate_from_world(state, new_seed_config)
    elif replay_plan.should_regenerate_outline():
        state = self._regenerate_from_outline(state, new_seed_config)
    elif replay_plan.should_regenerate_chapters():
        state = self._regenerate_chapters(state, new_seed_config, replay_plan.dirty_chapters)
    else:
        logger.info("No regeneration needed, using cached state")

    # 5. 恢复审批历史
    if approval_preserve:
        state.stage_statuses = approval_preserve["stage_statuses"]
        state.approval_history = approval_preserve["approval_history"]

    # 6. 保存状态
    state.seed_config = new_seed_config
    if pipeline_state_path:
        state.save(pipeline_state_path)

    # 7. 返回结果
    return self._build_output(state)
```

---

## 五、API 改进

### 5.1 新的 kickoff 签名

```python
def kickoff(
    self,
    stop_at: str | None = None,
    pipeline_state_path: str | None = None,
    review_each_chapter: bool = False,
    approval_mode: bool = False,
    seed: str | None = None,
    variant: str | None = None,  # 新增
) -> BaseCrewOutput:
    """执行完整的小说创作流程

    新增参数:
        variant: 可选的变体标识，用于生成同一主题的不同变体。
                 例如: variant="horror" 会生成恐怖主题变体。
    """
```

### 5.2 新的工厂方法

```python
@classmethod
def from_seed(cls, seed: str) -> "NovelCrew":
    """从已存在的 seed 创建 NovelCrew（用于恢复）"""
    # 从 seed 反推 SeedConfig（不完美，但可用）
    seed_config = SeedConfig(seed=seed, topic="", genre="", style="")
    return cls(seed_config=seed_config)
```

---

## 六、向后兼容性

### 6.1 旧状态迁移

```python
def migrate_legacy_state(state_data: dict) -> PipelineState:
    """迁移旧格式的 PipelineState

    旧格式只有 seed 字符串，没有 seed_config。
    """
    legacy_seed = state_data.get("seed", "")

    # 尝试从 metadata 反推
    metadata = state_data.get("metadata", {})
    seed_config = SeedConfig(
        seed=legacy_seed,
        topic=metadata.get("topic", ""),
        genre=metadata.get("genre", ""),
        style=metadata.get("style", ""),
    )

    # 创建新状态
    state = PipelineState(**state_data)
    state.seed_config = seed_config

    return state
```

### 6.2 渐进式迁移

```python
# 在 load() 中
@classmethod
def load(cls, path: str) -> "PipelineState":
    data = json.load(open(path))

    # 检查是否是旧格式
    if "seed" in data and "seed_config" not in data:
        logger.info("Migrating legacy PipelineState format")
        return cls.migrate_legacy_state(data)

    return cls(**data)
```

---

## 七、测试用例

### 7.1 SeedConfig 测试

```python
def test_seed_config_matches():
    """测试配置兼容性判断"""
    config1 = SeedConfig(
        seed="abc123",
        topic="修仙",
        genre="xianxia",
        style="epic",
        variant="default"
    )

    config2 = SeedConfig(
        seed="def456",  # 不同的 seed
        topic="修仙",
        genre="xianxia",
        style="epic",
        variant="horror"  # 不同的 variant
    )

    # 核心参数相同，视为匹配
    assert config1.matches(config2) == True

def test_seed_config_different_core():
    """核心参数不同"""
    config1 = SeedConfig(
        seed="abc123",
        topic="修仙",
        genre="xianxia",
        style="epic"
    )

    config2 = SeedConfig(
        seed="def456",
        topic="都市",  # 不同的 topic
        genre="urban",
        style="epic"
    )

    assert config1.matches(config2) == False
```

### 7.2 重放计划测试

```python
def test_replay_plan_regenerate_world():
    """核心参数变化时，从 world 重新生成"""
    state = PipelineState(...)
    state.seed_config = SeedConfig(topic="修仙", genre="xianxia", style="epic")

    new_config = SeedConfig(topic="都市", genre="urban", style="epic")

    plan = state.get_replay_plan(new_config)

    assert plan.should_regenerate_world() == True
    assert plan.preserve == ["chapters"]

def test_replay_plan_regenerate_chapters_only():
    """只有脏章节时，只重新生成章节"""
    state = PipelineState(...)
    state.seed_config = SeedConfig(topic="修仙", genre="xianxia", style="epic")
    state.mark_chapters_dirty([2, 5])

    new_config = SeedConfig(topic="修仙", genre="xianxia", style="epic")

    plan = state.get_replay_plan(new_config)

    assert plan.should_regenerate_chapters() == True
    assert plan.dirty_chapters == [2, 5]
```

---

## 八、实现计划

| 阶段 | 任务 | 优先级 |
|------|------|--------|
| 1 | 创建 `SeedConfig` dataclass | P0 |
| 2 | 创建 `ReplayPlan` dataclass | P0 |
| 3 | 修改 `PipelineState.get_replay_plan()` | P0 |
| 4 | 改进 `NovelCrew.kickoff()` 重放逻辑 | P0 |
| 5 | 添加 `DirtyTracker` 类 | P1 |
| 6 | 添加 `preserve_approval_history()` 方法 | P1 |
| 7 | 改进 `set_llm_seed()` fallback 逻辑 | P1 |
| 8 | 添加 `variant` 参数支持 | P2 |
| 9 | 添加旧状态迁移逻辑 | P2 |
| 10 | 编写完整测试用例 | P0 |

---

## 九、预期效果

### 9.1 改进前

```
用户修改 style → seed 变化 → 整个状态重置 → 丢失所有进度
```

### 9.2 改进后

```
用户修改 style → seed 变化 → 重放计划计算
                                    ↓
                    world + outline 重新生成
                                    ↓
                    chapters 保留（如果有的话）
                                    ↓
                    审批历史保留
```

---

*文档版本: v1.0*
*创建日期: 2026-03-29*
