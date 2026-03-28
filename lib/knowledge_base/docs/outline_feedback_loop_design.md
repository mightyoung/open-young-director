# 小说大纲遵循与反馈循环系统设计方案

## 1. 背景与问题

### 当前问题
- 详细大纲文件存在但代码从未加载
- 章节大纲是LLM临时生成的，不是从预存规划读取的
- PlotAnchor只验证不强制
- 一致性检查是"事后"的，非实时的

### 目标
建立**读取→执行→验证→反馈**的闭环，确保生成内容严格遵循预定义大纲。

---

## 2. 系统架构

### 2.1 核心数据流

```
详细大纲文件 (Markdown)
        │
        ▼ 读取
OutlineLoader
        │ 解析 + 缓存
        ▼
结构化Outline数据
{
  "ch001": {
    "title": "魔骨觉醒",
    "realm": "凡人→炼气1层",
    "key_events": ["测灵大典", "伪灵根判定", "柳如烟退婚", "梦中魔帝残魂初现"],
    "demon_emperor_line": "梦境中获得逆天灵根真相"
  },
  ...
}
        │
        ▼ 注入约束
OutlineEnforcer
        │ 验证关键事件
        ▼
VerificationReport
        │ 评分 + 问题列表
        ▼
通过/失败
        │
        ├─ 通过 → 保存到plot_anchors
        │
        └─ 失败 → AdaptiveRewriter (针对性重写)
```

### 2.2 组件清单

| 组件 | 职责 | 文件 |
|------|------|------|
| OutlineLoader | 解析Markdown大纲文件，输出结构化数据 | `outline_loader.py` |
| OutlineEnforcer | 验证生成内容是否遵循大纲约束 | `outline_enforcer.py` |
| AdaptiveRewriter | 根据验证失败原因自适应重写 | 集成到`novel_generator.py` |
| OutlineCache | 缓存解析结果，检测大纲变更 | OutlineLoader内部 |
| FeedbackAccumulator | 积累验证反馈用于后续优化 | `feedback_accumulator.py` |

---

## 3. 详细设计

### 3.1 OutlineLoader

```python
class OutlineLoader:
    """读取并解析Markdown大纲文件"""

    def __init__(self, outline_dir: Path):
        self.outline_dir = outline_dir
        self._cache: Dict[str, dict] = {}
        self._version: str = ""

    def load_chapter_outline(self, chapter_number: int) -> Optional[dict]:
        """读取指定章节的大纲"""
        # 1. 检查缓存
        cache_key = f"ch{chapter_number:03d}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 2. 读取并解析Markdown文件
        # 策略：根据章节号确定所在的幕/卷
        md_file = self._find_outline_file(chapter_number)
        if not md_file:
            return None

        # 3. 解析表格获取章节数据
        chapter_data = self._parse_markdown_table(md_file, chapter_number)

        # 4. 缓存
        self._cache[cache_key] = chapter_data
        return chapter_data

    def load_volume_outline(self, volume: int) -> dict:
        """加载整卷的大纲"""
        # 返回 {ch001: {...}, ch002: {...}, ...}

    def _find_outline_file(self, chapter_number: int) -> Optional[Path]:
        """根据章节号查找对应的大纲文件"""

    def _parse_markdown_table(self, md_file: Path, chapter_number: int) -> dict:
        """解析Markdown表格提取章节数据"""
```

**解析逻辑**:
- 识别 Markdown 表格（| 分割的表格）
- 根据章号列定位目标章节
- 提取标题/境界/核心事件/魔帝线

### 3.2 OutlineEnforcer

```python
class OutlineEnforcer:
    """验证生成内容是否遵循大纲约束"""

    def __init__(self, loader: OutlineLoader):
        self.loader = loader

    def enforce(
        self,
        chapter_number: int,
        generated_content: str,
        plot_summary: dict,
    ) -> VerificationReport:
        """
        验证章节是否遵循大纲

        Returns:
            VerificationReport {
                passed: bool,
                score: float,  # 0-10
                issues: List[Issue],
                coverage: CoverageReport,
            }
        """
        # 1. 获取本章预定义大纲
        outline = self.loader.load_chapter_outline(chapter_number)
        if not outline:
            return VerificationReport(passed=False, score=0, issues=["大纲不存在"])

        # 2. 关键事件覆盖率
        key_events = outline.get("key_events", [])
        event_coverage = self._check_event_coverage(generated_content, key_events)

        # 3. 境界连续性
        realm_check = self._check_realm_consistency(chapter_number, outline, plot_summary)

        # 4. 悬念埋设检查
        suspense_check = self._check_suspense_plots(chapter_number, outline, plot_summary)

        # 5. 角色状态检查
        character_check = self._check_character_states(chapter_number, outline)

        # 综合评分
        score = self._calculate_score(event_coverage, realm_check, suspense_check, character_check)

        issues = []
        if event_coverage["missing_events"]:
            issues.append(Issue(
                type="MISSING_EVENTS",
                details=event_coverage["missing_events"],
                severity="HIGH",
            ))
        # ...

        return VerificationReport(
            passed=score >= 7.0,
            score=score,
            issues=issues,
            coverage={
                "event_coverage": event_coverage["coverage_rate"],
                "realm": realm_check,
                "suspense": suspense_check,
            }
        )

    def _check_event_coverage(self, content: str, key_events: List[str]) -> dict:
        """检查关键事件覆盖率"""
        found_events = []
        missing_events = []
        for event in key_events:
            if event in content:
                found_events.append(event)
            else:
                # 模糊匹配（关键词匹配）
                keywords = event.split("，")
                if all(kw in content for kw in keywords):
                    found_events.append(event)
                else:
                    missing_events.append(event)

        coverage_rate = len(found_events) / len(key_events) if key_events else 1.0
        return {
            "found": found_events,
            "missing": missing_events,
            "coverage_rate": coverage_rate,
        }
```

### 3.3 AdaptiveRewriter

```python
class AdaptiveRewriter:
    """根据验证失败原因自适应重写"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def rewrite(
        self,
        chapter: GeneratedChapter,
        report: VerificationReport,
        outline: dict,
        previous_chapter: Optional[GeneratedChapter],
    ) -> GeneratedChapter:
        """
        根据验证报告针对性重写

        策略:
        - MISSING_EVENTS: 聚焦补充缺失事件
        - REALM_INCONSISTENCY: 修正境界描述
        - SUSPENSE_MISSING: 添加悬念钩子
        - CHARACTER_INCONSISTENT: 修正角色状态
        """
        # 按严重程度排序
        issues_by_severity = sorted(
            report.issues,
            key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x.severity]
        )

        rewrite_prompt = self._build_rewrite_prompt(
            chapter=chapter,
            issues=issues_by_severity,
            outline=outline,
            previous_chapter=previous_chapter,
        )

        # 调用LLM重写
        response = self.llm.chat(messages=[{"role": "user", "content": rewrite_prompt}])
        new_content = response.content.strip()

        # 更新章节
        chapter.content = new_content
        chapter.word_count = len(new_content.replace("\n", ""))
        chapter.metadata["rewrite_reason"] = [i.type for i in issues_by_severity]

        return chapter

    def _build_rewrite_prompt(
        self,
        chapter: GeneratedChapter,
        issues: List[Issue],
        outline: dict,
        previous_chapter: Optional[GeneratedChapter],
    ) -> str:
        """构建针对性重写Prompt"""
        # 根据问题类型定制指令
        directives = []
        for issue in issues:
            if issue.type == "MISSING_EVENTS":
                directives.append(
                    f"**必须补充以下关键事件**:\n" +
                    "\n".join(f"- {e}" for e in issue.details)
                )
            elif issue.type == "REALM_INCONSISTENCY":
                directives.append(
                    f"**境界修正**: 本章境界为 {outline.get('realm')}，"
                    f"请确保所有境界描述与此一致"
                )
            elif issue.type == "SUSPENSE_MISSING":
                directives.append(
                    f"**必须埋设悬念**: 本章结尾需要引出下一章内容"
                )
        # ...
```

### 3.4 FeedbackAccumulator

```python
class FeedbackAccumulator:
    """积累验证反馈用于后续优化"""

    def __init__(self, storage):
        self.storage = storage  # pgVector

    def record_verification(
        self,
        chapter_number: int,
        report: VerificationReport,
    ):
        """记录验证结果"""
        # 存储到pgVector用于后续分析
        self.storage.upsert(
            collection="verification_feedback",
            record=VectorRecord(
                id=f"ch{chapter_number}",
                vector=self._report_to_vector(report),
                metadata={
                    "chapter": chapter_number,
                    "passed": report.passed,
                    "score": report.score,
                    "common_issues": self._extract_issue_patterns(report.issues),
                }
            )
        )

    def get_chapter_guidance(self, chapter_number: int) -> dict:
        """获取本章的特别指导（基于历史反馈）"""
        # 搜索相似章节的失败模式
        similar = self.storage.search(
            collection="verification_feedback",
            query_vector=self._get_chapter_vector(chapter_number),
            top_k=5,
        )

        guidance = {}
        for result in similar:
            if not result.metadata["passed"]:
                # 记录常见的失败模式
                issues = result.metadata["common_issues"]
                for issue in issues:
                    guidance[issue] = guidance.get(issue, 0) + 1

        return guidance
```

---

## 4. 修改现有代码

### 4.1 novel_generator.py 修改点

```python
# 新增导入
from .outline_loader import OutlineLoader
from .outline_enforcer import OutlineEnforcer
from .feedback_accumulator import FeedbackAccumulator

class NovelGeneratorAgent:
    def __init__(self, ...):
        # 新增组件
        self._outline_loader = OutlineLoader(outline_dir=self._get_outline_dir())
        self._enforcer = OutlineEnforcer(self._outline_loader)
        self._feedback = FeedbackAccumulator(storage)

    def generate_chapter(self, chapter_number, ...):
        # 1. 读取预定义大纲
        predefined_outline = self._outline_loader.load_chapter_outline(chapter_number)

        if predefined_outline:
            # 有预定义大纲 → 直接使用
            outline_data = predefined_outline
            # 扩展细节用LLM
        else:
            # 无预定义大纲 → LLM临时生成
            outline_data = self._generate_outline_with_llm(...)

        # 2. 生成正文（使用outline_data作为约束）

        # 3. 验证
        report = self._enforcer.enforce(chapter_number, content, plot_summary)

        # 4. 处理验证结果
        if not report.passed:
            chapter = self._adaptive_rewrite.rewrite(chapter, report, outline_data, prev_chapter)

        # 5. 记录反馈
        self._feedback.record_verification(chapter_number, report)

        return chapter
```

### 4.2 multi_agent_narrative.py 修改点

```python
# 在PlotAnchor中增加强制机制
class PlotAnchor:
    def validate_action(self, action: dict, character: str) -> tuple[bool, str]:
        # ... 现有逻辑 ...

        # 新增：如果关键事件被跳过，强制重试
        for event in self.key_events:
            if event.lower() in action_text.lower() and not self._event_triggered(event):
                self._mark_event_triggered(event)
                return True, "OK"  # 放行，但标记事件已触发

        # 检查是否有关键事件被完全遗漏
        if self._all_events_completed():
            # 场景可以结束
            pass
```

---

## 5. 数据格式

### 5.1 解析后的大纲格式

```json
{
  "ch001": {
    "title": "魔骨觉醒",
    "realm": "凡人→炼气1层",
    "key_events": ["测灵大典", "伪灵根判定", "柳如烟退婚", "梦中魔帝残魂初现"],
    "demon_emperor_line": "梦境中获得逆天灵根真相",
    "act": "第一幕：废物与屈辱",
    "arc": "测灵大典，退婚之辱，逆天觉醒"
  },
  "ch002": {
    "title": "逆骨",
    "realm": "炼气1层",
    "key_events": ["逆仙录入门", "确认逆天灵根", "魔帝低语"],
    "demon_emperor_line": "体内封印开始松动"
  }
}
```

### 5.2 验证报告格式

```json
{
  "chapter": 1,
  "passed": true,
  "score": 8.5,
  "issues": [
    {
      "type": "MISSING_EVENTS",
      "details": ["梦中魔帝残魂初现"],
      "severity": "MEDIUM"
    }
  ],
  "coverage": {
    "event_coverage": 0.75,
    "realm_consistent": true,
    "suspense_planted": true,
    "character_consistent": true
  },
  "timestamp": "2026-03-22T..."
}
```

---

## 6. 实施计划

### Phase 1: OutlineLoader (独立组件)
- [ ] 创建 `agents/outline_loader.py`
- [ ] 实现Markdown表格解析
- [ ] 实现缓存机制
- [ ] 测试解析准确性

### Phase 2: OutlineEnforcer (验证组件)
- [ ] 创建 `agents/outline_enforcer.py`
- [ ] 实现事件覆盖率检查
- [ ] 实现境界连续性检查
- [ ] 实现悬念埋设检查

### Phase 3: 集成到生成流程
- [ ] 修改 `novel_generator.py` 集成OutlineLoader
- [ ] 修改一致性检查集成OutlineEnforcer
- [ ] 实现AdaptiveRewriter

### Phase 4: 反馈循环
- [ ] 创建 `agents/feedback_accumulator.py`
- [ ] 实现pgVector存储验证结果
- [ ] 实现历史反馈查询

---

## 7. 验证标准

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| 大纲遵循率 | ≥95% | 关键事件覆盖率 |
| 验证通过率 | ≥90% | 首次验证通过 |
| 平均验证评分 | ≥8.0 | 10分制评分 |
| Rewrite次数 | ≤1.5次/章 | 统计rewrite_history |

---

## 8. 风险与缓解

| 风险 | 缓解方案 |
|------|---------|
| Markdown格式变化 | 增加格式容错，fallback到模糊匹配 |
| 大纲文件缺失 | 保留LLM临时生成作为fallback |
| 验证过于严格 | 评分阈值可调整(默认7.0) |
| 性能开销 | OutlineLoader结果缓存 |
