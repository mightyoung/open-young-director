# 小说生成系统改进计划

## 需求

1. **调整分卷分章节逻辑** - 当前 `num_chapters = max(1, target_words // 10000)` 过于简单，需要更智能的计算
2. **在规划阶段前增加经典名著搜索** - 每次生成小说前，先搜索符合的经典名著，抽象其主干故事情节用于网络小说规划

---

## 现状分析

### 分卷分章节现状

**NovelConfig** (`lib/crewai/src/crewai/content/novel/config/novel_config.py`):
```python
num_chapters: int = 0  # 0 = auto-calculate
num_volumes: int = 3

# 自动计算逻辑 (line 52-53):
if self.num_chapters <= 0:
    self.num_chapters = max(1, self.target_words // 10000)
```

**问题**:
- 每章固定 10000 字，过于简单
- 卷数硬编码为 3，没有根据总章节数调整
- 没有考虑风格差异（如 xianxia 通常章节更长）

### 世界观/情节规划现状

**OutlineCrew** (`lib/crewai/src/crewai/content/novel/crews/outline_crew.py`):
- 顺序执行: `build_world` → `plan_plot`
- WorldAgent 直接开始构建世界观，没有"借鉴名著"的概念
- PlotAgent 接收 world_data 和基本参数，没有参考骨架

### 搜索工具

已有 TavilySearchTool 可用，支持网络搜索。

---

## 实现计划

### Phase 1: 智能分卷分章节

**目标**: 根据目标字数、风格、卷数自动计算最优章节分配

**修改文件**: `lib/crewai/src/crewai/content/novel/config/novel_config.py`

**新增配置**:
```python
words_per_chapter_target: int = 5000  # 每章目标字数（可配置）
chapter_word_range: tuple = (4000, 8000)  # 章节字数浮动范围
auto_volume_calculation: bool = True  # 自动计算最优卷数
```

**新计算逻辑**:
```python
def _calculate_chapters_and_volumes(self):
    """智能计算章节数和卷数"""
    # 1. 根据目标字数计算章节数
    if self.num_chapters <= 0:
        # 基础计算：目标字数 / 每章目标字数
        base_chapters = max(1, self.target_words // self.words_per_chapter_target)
        # 调整为结构化数字（便于分卷）
        self.num_chapters = self._round_to_structure(base_chapters)

    # 2. 根据总章节数自动计算最优卷数
    if self.auto_volume_calculation:
        self.num_volumes = self._optimal_volumes_for_chapters(self.num_chapters)

    # 3. 计算每卷章节数（尽量均匀）
    self._chapters_per_volume = self.num_chapters // self.num_volumes
    self._remainder_chapters = self.num_chapters % self.num_volumes

def _optimal_volumes_for_chapters(self, total_chapters: int) -> int:
    """根据总章节数计算最优卷数"""
    # 经验规则：
    # - 30章以下: 2-3卷
    # - 30-60章: 3-4卷
    # - 60-120章: 4-6卷
    # - 120-200章: 6-8卷
    # - 200章以上: 8-10卷
    if total_chapters <= 30:
        return max(2, min(3, total_chapters))
    elif total_chapters <= 60:
        return max(3, min(4, total_chapters // 10))
    elif total_chapters <= 120:
        return max(4, min(6, total_chapters // 20))
    elif total_chapters <= 200:
        return max(6, min(8, total_chapters // 25))
    else:
        return max(8, min(10, total_chapters // 30))

def _round_to_structure(self, num: int) -> int:
    """将数字调整为结构化数字（便于分卷）"""
    # 例如 47 -> 45, 73 -> 75
    if num <= 10:
        return num
    # 找到最接近的 5 的倍数
    return round(num / 5) * 5
```

**风格差异调整** (扩展):
```python
# 不同风格的章节字数差异
STYLE_CHAPTER_CONFIG = {
    "xianxia": {"words_per_chapter": 6000, "volume_range": (8, 15)},
    "urban": {"words_per_chapter": 4000, "volume_range": (10, 20)},
    "doushi": {"words_per_chapter": 5000, "volume_range": (8, 15)},
    "modern": {"words_per_chapter": 3500, "volume_range": (12, 25)},
}
```

---

### Phase 2: 经典名著搜索骨架

**目标**: 在世界观构建前，先搜索经典名著，抽象其主干情节作为参考

**新增文件**:
1. `lib/crewai/src/crewai/content/novel/agents/reference_agent.py` - 参考骨架提取 Agent
2. `lib/crewai/src/crewai/content/novel/services/reference_service.py` - 名著搜索与骨架提取服务

**修改文件**:
1. `lib/crewai/src/crewai/content/novel/crews/outline_crew.py` - 在 build_world 前增加 research 步骤
2. `lib/crewai/src/crewai/content/novel/pipeline_state.py` - 增加 reference_data 存储

**参考骨架数据结构**:
```python
@dataclass
class ReferenceSkeleton:
    """经典名著骨架"""
    source: str                    # 名著名称 (如《西游记》)
    source_url: str                # 参考来源 URL
    theme: str                     # 主题提炼
    backbone_plot: list[str]       # 主干情节列表
    character_archetypes: list[dict]  # 角色原型
    structure_pattern: str          # 结构模式 (如"取经模式")
    key_conflicts: list[str]       # 核心冲突
    growth_arc: str                # 成长弧线
```

**ReferenceAgent prompt**:
```
你是一个故事分析专家。请根据搜索到的资料，提取以下经典名著的故事骨架：

1. 主干情节（按顺序列出核心事件，3-7个）
2. 角色原型（主角类型、配角类型）
3. 结构模式（如：英雄之旅、取经模式、复仇模式）
4. 核心冲突（贯穿全书的主要矛盾）
5. 成长弧线（主角如何成长）

返回 JSON 格式：
{
    "source": "《XXX》",
    "theme": "主题描述",
    "backbone_plot": ["事件1", "事件2", ...],
    "character_archetypes": [...],
    "structure_pattern": "模式名称",
    "key_conflicts": [...],
    "growth_arc": "成长描述"
}
```

**OutlineCrew 改造**:
```python
class OutlineCrew:
    def _create_tasks(self) -> Dict[str, Any]:
        return {
            "research_reference": Task(
                description=f"搜索'{topic}'主题相关的经典名著，提取故事骨架",
                agent=self.agents["reference_agent"].agent,
                expected_output="经典名著故事骨架JSON",
            ),
            "build_world": Task(
                description=f"为'{topic}'主题构建世界观（可参考已有骨架）",
                agent=self.agents["world_builder"].agent,
                expected_output="完整世界观设定JSON",
            ),
            "plan_plot": Task(
                description=f"设计情节结构（融入经典骨架元素）",
                agent=self.agents["plot_planner"].agent,
                expected_output="完整情节规划JSON",
                context=["research_reference", "build_world"],  # 依赖 research
            ),
        }
```

**搜索策略**:
```python
def _search_references(topic: str, style: str) -> list[dict]:
    """搜索相关经典名著"""
    search_queries = [
        f"{topic} 经典名著 故事大纲",
        f"{style} 小说 经典结构 分析",
        f"{topic} 叙事结构 骨干情节",
    ]

    results = []
    for query in search_queries:
        search_results = tavily_search(query, max_results=3)
        results.extend(search_results)

    return results  # 返回给 ReferenceAgent 处理
```

---

### Phase 3: 集成测试

**测试用例**:
1. `test_novel_config_chapter_calculation.py` - 测试智能分卷计算
2. `test_reference_agent.py` - 测试名著骨架提取
3. 端到端测试：生成带参考骨架的小说

---

## 实现顺序

1. **Phase 1a**: 修改 `NovelConfig` 分卷分章计算逻辑
2. **Phase 1b**: 更新相关文档
3. **Phase 2a**: 创建 `ReferenceAgent`
4. **Phase 2b**: 创建 `ReferenceService`
5. **Phase 2c**: 修改 `OutlineCrew` 集成 research 步骤
6. **Phase 2d**: 更新 `PipelineState` 支持 reference_data
7. **Phase 3**: 集成测试
8. **Phase 4**: 端到端测试

---

## 预计工作量

- Phase 1: ~2 小时
- Phase 2: ~4 小时
- Phase 3: ~2 小时
- **总计**: ~8 小时
