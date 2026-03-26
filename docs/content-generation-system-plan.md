# crewAI 多Agent内容生成系统改造方案

> 创建日期: 2026-03-20
> 更新时间: 2026-03-20 (专家评审后更新)
> 状态: 规划完成 (v2.0 - 专家评审版)

## 一、项目背景

将 crewAI 改造为支持**小说、剧本、博客**三大内容类型的自动生成系统。

### 目标

- 输入：大纲/主题/类型
- 输出：完整的长篇内容（小说/剧本）或结构化文章（博客）
- 核心价值：多Agent协作、内容一致性追踪、多维度质量审查

---

## 二、参考项目分析

### 2.1 webnovel-writer 关键架构

| 组件 | 设计要点 |
|------|----------|
| **双Agent架构** | Context Agent(读) + Data Agent(写) 分离 |
| **六维并行审查** | high_point/consistency/pacing/OOC/continuity/reader_pull |
| **Strand Weave** | Quest(55-65%) + Fire(20-30%) + Constellation(10-20%) |
| **防幻觉三定律** | 大纲即法律、设定即物理、发明需识别 |
| **状态管理** | SQLite(index.db) + JSON(state.json) 双轨 |

### 2.2 agency-agents 关键架构

| 组件 | 设计要点 |
|------|----------|
| **NEXUS编排框架** | 7阶段Pipeline + Quality Gates |
| **Dev↔QA Loop** | 失败重试最多3次，然后升级 |
| **证据驱动验证** | Reality Checker要求截图/测试结果 |
| **Handoff协议** | 标准化Agent间上下文传递格式 |

### 2.3 行业最佳实践

| 场景 | 推荐架构 |
|------|----------|
| **小说** | 结构师→大纲师→写作师→审查师 串行+并行审查 |
| **剧本** | 结构师→场景师→对话师→格式师 分层递进 |
| **博客** | 研究员→大纲师→写作师→SEO优化师→编辑 顺序+反馈 |

---

## 三、目标架构

```
lib/
├── crewai/                    # 核心框架扩展
│   └── src/crewai/
│       ├── content/          # 新增: 内容生成核心
│       │   ├── outline/     # 大纲解析引擎
│       │   ├── memory/      # 实体记忆系统
│       │   ├── continuity/  # 连贯性追踪
│       │   └── review/       # 审查流水线
│       └── agents/           # 扩展现有Agent
│
├── crewai-novel/             # 新增: 小说生成插件
├── crewai-script/            # 新增: 剧本生成插件
└── crewai-blog/             # 新增: 博客生成插件
```

---

## 四、核心Agent设计（专家评审后更新版）

### 4.1 基础Agent (所有内容类型共用)

| Agent | 职责 | Crew归属 |
|-------|------|----------|
| **OutlineAgent** | 展开用户大纲为章纲 | ContentBase |
| **DraftAgent** | 根据章纲生成正文 | All |
| **CritiqueAgent** | 诊断问题（识别症状和根因） | All |
| **RevisionAgent** | 根据诊断开处方（具体修改建议） | All |
| **PolishAgent** | 行级润色（句子节奏、词汇选择） | All |
| **ExportAgent** | 格式规范化（Final Draft/Celtx/HTML） | Script/Blog |

### 4.2 小说专用Agent

| Agent | 职责 | Crew归属 |
|-------|------|----------|
| **WorldAgent** | 构建世界观/角色/设定 | Novel |
| **PlotAgent** | 规划情节节奏(Strand Weave) | Novel |
| **DiantingChecker** | 垫听机制：伏笔回收追踪 | Novel |
| **ChapterEndingChecker** | 章末质量检查（钩子/断章/悬念） | Novel |
| **ShuangganPatternChecker** | 爽感类型检查（打脸/释伏/突破/截胡/收编） | Novel |
| **RepetitivePatternChecker** | 套路重复检测（防止同质化） | Novel |
| **InteriorityChecker** | 内心描写检查（角色心理弧线） | Novel |
| **POVChecker** | 叙事视角规范检查 | Novel |

### 4.3 剧本专用Agent

| Agent | 职责 | Crew归属 |
|-------|------|----------|
| **StructureAgent** | 幕结构、场次列表 | Script |
| **BeatSheetAgent** | 分镜表：场景动作分解（结构→场景过渡） | Script |
| **SceneAgent** | 场景描述（含地点质感） | Script |
| **DialogueAgent** | 角色对话（含潜文本） | Script |
| **CinematographyAgent** | 镜头设计、相机运动、视觉语法 | Script |
| **VisualMotifTracker** | 视觉母题追踪（颜色/意象/构图） | Script |
| **TransitionAgent** | 过渡语法（CUT/DISSOLVE/FADE） | Script |
| **CoveragePlanner** | shot list生成、覆盖选项 | Script |
| **LocationVisionAgent** | 地点质感描述 | Script |
| **VisualFormatAgent** | 宽高比、构图、电影语法导出 | Script |

### 4.4 博客专用Agent

| Agent | 职责 | Crew归属 |
|-------|------|----------|
| **HookAgent** | 生成5-10个钩子变体（Hook优先于Research） | Blog |
| **ResearchAgent** | 搜集背景资料、竞品分析 | Blog |
| **TitleAgent** | CTR优化标题变体 | Blog |
| **ThumbnailConceptAgent** | 视觉钩子描述+文字建议 | Blog |
| **SEOAgent** | 关键词密度/内链/元描述（支持多平台） | Blog |
| **PlatformAdapterAgent** | 内容→平台适配（YouTubeSEO/TikTokSEO） | Blog |

### 4.5 播客专用Agent

| Agent | 职责 | Crew归属 |
|-------|------|----------|
| **PreShowAgent** | Hook脚本(0:00-0:30)、预告、节目描述 | Podcast |
| **IntroAgent** | 主持开场，品牌时刻 | Podcast |
| **SegmentAgent** | 话题设置、深度内容、过渡 | Podcast |
| **InterviewAgent** | 嘉宾介绍、问题准备 | Podcast |
| **AdReadAgent** | 原生广告植入脚本 | Podcast |
| **OutroAgent** | 回顾、CTA、订阅提示 | Podcast |
| **ShowNotesAgent** | 时间戳章节、链接、transcript | Podcast |
| **ColdOpenAgent** | 冷开场脚本（30秒留存法则） | Podcast |

### 4.6 编辑Pipeline Agent

> **专家评审强调**：编辑不是"根据审查意见修改"，而是"诊断+处方+执行"的专业工作流

```
CritiqueAgent (诊断) → RevisionAgent (处方) → PolishAgent (行级润色)
                                                    ↓
                                           CopyEditGate (冻结点)
                                                    ↓
                                              ProofreadGate
```

---

## 五、Crew设计方案（专家评审后更新版）

### 5.1 小说生成 Crew (NovelCrew)

> **专家评审关键修改**：
> - 增加垫听机制（DiantingChecker）追踪伏笔回收
> - 增加章末质量检查（ChapterEndingChecker）
> - 增加爽感类型检查（ShuangganPatternChecker）
> - 增加写作→大纲反馈回路
> - 增加内心描写和POV检查

```
User Input (主题/类型/字数/朝代/风格)
    ↓
[WorldCrew] → 构建世界观、角色卡、力量体系
    ↓
[OutlineCrew] → 生成卷纲→章纲 (Strand Weave)
    ↓
[WritingCrew] 循环 per chapter:
    │   DraftAgent → 输出初稿
    │   ↓
    │   [ReviewCrew 并行]:
    │   │   consistency_checker      # 一致性
    │   │   pacing_checker          # 节奏
    │   │   ooc_checker            # 角色一致性
    │   │   high_point_checker      # 高潮点
    │   │   continuity_checker      # 连贯性
    │   │   reader_pull_checker    # 读者吸引力
    │   │   ─────────────────────────────────
    │   │   dianting_checker        # 垫听：伏笔回收追踪
    │   │   chapter_ending_checker   # 章末断章质量
    │   │   shuanggan_checker       # 爽感类型
    │   │   repetitive_pattern_checker # 套路重复检测
    │   │   interiority_checker     # 内心描写
    │   │   pov_checker            # 视角规范
    │   ↓
    │   [CritiqueAgent] → 诊断问题
    │   ↓
    │   [RevisionAgent] → 开处方
    │   ↓
    │   [PolishAgent] → 行级润色
    │   ↓
    │   **反馈回路**: 若重大剧情偏离 → 更新大纲
    ↓
Final Output (完整小说 + 设定集 + 伏笔追踪报告 + 套路检测报告)
```

**垫听机制 (DiantingChecker) 实现要求:**
```
伏笔回收率: Chapter N埋钩子 → Chapter N+5~20回收
情绪积累周期: 打压→释放节奏
悬念残留量: 每章结尾未解答问题
```

**章末质量检查要求 (每章最后500字必须满足至少一条):**
```
□ 战斗未决出胜负
□ 信息揭露一半
□ 危机突然降临
□ 身份/秘密即将揭晓
```

### 5.2 剧本生成 Crew (ScriptCrew)

> **专家评审关键修改**：
> - 增加BeatSheet步骤（结构→场景的桥梁）
> - 增加CinematographyAgent处理视觉叙事
> - 增加VisualMotifTracker追踪视觉母题
> - FormatAgent重命名为ExportAgent，新增VisualFormatAgent

```
User Input (题材/时长/集数/格式要求)
    ↓
[ShowBibleCrew] → 构建世界观、角色背景、规则体系
    ↓
[StructureCrew] → 生成季弧、幕结构、场次列表
    ↓
[BeatSheetCrew] → **新增**: 分镜表：场景-动作分解
    ↓
[SceneCrew] → 展开每场:
    │   ├── 场景描述(含地点质感)
    │   ├── 镜头设计 (CinematographyAgent)
    │   ├── 角色动作、情绪弧线
    │   └── 视觉构图意图
    ↓
[VisualMotifTracker] → **新增**: 视觉母题追踪
    ↓
[DialogueCrew] → 角色对话生成 (含潜文本)
    ↓
[TransitionAgent] → **新增**: 过渡语法 (CUT/DISSOLVE/FADE)
    ↓
[CoveragePlanner] → **新增**: shot list生成
    ↓
[ExportCrew]:
    │   ├── ExportAgent → Final Draft/Celtx格式
    │   └── VisualFormatAgent → **新增**: 宽高比/构图/电影语法
    ↓
Final Output (完整剧本 + shot list + 视觉母题报告)
```

**BeatSheet步骤说明:**
```
Beat Sheet = 结构与场景之间的桥梁
├── 识别每个场景的"转折点"(beat)
├── 定义场景目的: 谁想要什么？障碍是什么？
├── 验证场景必要性: 每个场景都推动故事发展吗？
└── 生成场景序列: Act I → 25 beats → Act IIa → ...
```

### 5.3 博客生成 Crew (BlogCrew)

> **专家评审关键修改**：
> - **Hook优先于Research**（30秒法则）
> - 增加TitleAgent、ThumbnailConceptAgent
> - SEOAgent扩展支持多平台(YouTubeSEO/TikTokSEO)

```
User Input (主题/关键词/目标读者/字数)
    ↓
[HookAgent] → **Phase 0**: 生成5-10个钩子变体 ★ 优先于Research
    ↓
[ResearchCrew] → 搜集背景资料、竞品分析
    ↓
[OutlineCrew] → 生成文章大纲 (H1/H2结构)
    ↓
[TitleAgent] → **新增**: CTR优化标题变体
    ↓
[WritingCrew] → 撰写正文 (HBCFC公式: Hook/Bridge/Core/FAQ/CTA)
    ↓
[ThumbnailConceptAgent] → **新增**: 视觉钩子描述+文字建议
    ↓
[SEOCrew]:
    │   ├── SEOAgent → 关键词密度/内链/元描述
    │   └── PlatformAdapterAgent → **新增**: YouTubeSEO/TikTokSEO
    ↓
[CritiqueAgent] → 诊断问题
    ↓
[RevisionAgent] → 开处方
    ↓
[PolishAgent] → 行级润色
    ↓
CopyEditGate → **冻结点**: 此后不再修改内容
    ↓
Final Output (发布就绪的博客 + 标题变体 + 缩略图概念)
```

### 5.4 播客生成 Crew (PodcastCrew)

> **专家评审新增**：播客作为内容类型完全缺失

```
User Input (主题/时长/风格/主持人数量)
    ↓
[PreShowCrew]:
    │   ├── PreShowAgent → Hook脚本(0:00-0:30)、预告
    │   └── ColdOpenAgent → 冷开场脚本
    ↓
[IntroCrew] → 主持开场，品牌时刻，节目描述(150-300词)
    ↓
[SegmentCrew] 循环 per topic:
    │   ├── SegmentAgent → 话题设置→深度内容→过渡
    │   └── TransitionAgent → 片段间过渡
    ↓
[InterviewCrew] (可选) → 嘉宾介绍、问题准备
    ↓
[AdReadCrew] (可选) → 原生广告植入脚本
    ↓
[OutroCrew] → 回顾要点、CTA、订阅提示
    ↓
[ShowNotesCrew]:
    │   ├── 时间戳章节
    │   ├── 链接汇总
    │   └── Transcript生成
    ↓
Final Output (播客脚本 + 时间戳 + 节目描述 +Shownotes)
```

**播客专属元素:**
| 元素 | 作用 | 实现Agent |
|------|------|----------|
| Hook脚本 | 前30秒决定70%留存 | ColdOpenAgent |
| 品牌开场/收尾 | 建立听众期待 | IntroAgent/OutroAgent |
| 话题过渡 | 保持听众注意力 | TransitionAgent |
| 中插广告 | 原生不打断 | AdReadAgent |
| 嘉宾介绍公式 | 专业感 | InterviewAgent |
| 口头CTA | 行动号召 | OutroAgent |
| 章节标记 | 导航便利 | ShowNotesAgent |

### 5.5 编辑Pipeline (所有内容类型共用)

> **专家评审关键修改**：编辑不是"根据审查意见修改"，而是专业诊断+处方+执行

```
[Draft] → CritiqueAgent (诊断)
              ↓
         识别问题类型:
         ├── Developmental (结构/叙事弧线/主题)
         ├── Content/Substantive (论证/场景逻辑/节奏)
         ├── Line Editing (句子节奏/词汇/对话真实感)
         └── Copy Editing (语法/一致性/风格)
              ↓
         [RevisionAgent] (处方)
              ↓
         具体修改建议 + 优先级排序
              ↓
         [PolishAgent] (执行)
              ↓
         CopyEditGate → **冻结点**: 内容锁定
              ↓
         [ProofreadAgent] (最终校对)
              ↓
         [Published]
```

**编辑关卡说明:**
| 关卡 | 职责 | 是否可逆 |
|------|------|----------|
| CritiqueGate | 问题诊断 | 可逆 |
| RevisionGate | 修改处方 | 可逆 |
| PolishGate | 行级润色 | 部分可逆 |
| **CopyEditGate** | **冻结点**: 此后只改错别字 | **不可逆** |
| ProofreadGate | 最终校对 | 不可逆 |

---

## 六、关键实现模块

### 6.1 Outline Engine (大纲解析)

```python
class OutlineEngine:
    """将自由格式大纲转为结构化章纲"""

    def parse(self, outline: str, content_type: ContentType) -> Outline:
        """返回标准化Outline对象"""

    def generate_chapters(self, outline: Outline) -> List[ChapterOutline]:
        """从大纲生成章纲列表"""

    def validate_strand_balance(self, chapters: List[ChapterOutline]) -> StrandReport:
        """验证Strand Weave比例"""
```

### 6.2 Entity Memory (实体记忆)

```python
class EntityMemory:
    """跨章节追踪角色/地点/势力状态"""

    def track(self, chapter_output: ChapterOutput) -> None:
        """从章节输出提取实体更新记忆"""

    def get_context(self, chapter: int) -> Dict[str, Any]:
        """获取指定章节需要的上下文"""

    def check_consistency(self, claim: str) -> ConsistencyResult:
        """检查新内容与已建立设定的一致性"""
```

### 6.3 Review Pipeline (审查流水线 - 专家评审更新版)

```python
class ReviewPipeline:
    """并行执行多维度审查"""

    async def review(self, draft: str, context: ReviewContext) -> ReviewReport:
        # 基础6维审查
        base_results = await asyncio.gather(
            self.high_point_checker.check(draft),
            self.consistency_checker.check(draft, context),
            self.pacing_checker.check(draft, context),
            self.ooc_checker.check(draft, context),
            self.continuity_checker.check(draft, context),
            self.reader_pull_checker.check(draft, context),
        )

        # 小说专用审查 (新增)
        if context.content_type == ContentType.NOVEL:
            novel_results = await asyncio.gather(
                self.dianting_checker.check(draft, context),      # 垫听：伏笔回收
                self.chapter_ending_checker.check(draft, context), # 章末断章
                self.shuanggan_checker.check(draft, context),     # 爽感类型
                self.interiority_checker.check(draft, context),   # 内心描写
                self.pov_checker.check(draft, context),          # 视角规范
            )
            base_results.extend(novel_results)

        # 剧本专用审查 (新增)
        elif context.content_type == ContentType.SCRIPT:
            script_results = await asyncio.gather(
                self.beat_sheet_checker.check(draft, context),   # 分镜表
                self.cinematography_checker.check(draft, context), # 镜头设计
                self.visual_motif_checker.check(draft, context),  # 视觉母题
                self.transition_checker.check(draft, context),   # 过渡语法
            )
            base_results.extend(script_results)

        return self.aggregate(base_results)
```

### 6.4 DiantingChecker (垫听机制 - 新增)

> **专家评审新增**：追踪伏笔的埋设与回收

```python
class DiantingChecker:
    """垫听机制：伏笔回收追踪"""

    def track_plant(self, chapter: int, hook: str, expected_reveal: str) -> None:
        """记录伏笔埋设"""

    def check_reveal_timing(self, chapter: int, plant_chapter: int) -> TimingResult:
        """检查伏笔回收时机 (应在埋设后5-20章)"""
        gap = chapter - plant_chapter
        if gap < 5:
            return TimingResult.TOO_EARLY  # 回收太早，悬念不足
        elif gap > 20:
            return TimingResult.TOO_LATE   # 回收太晚，读者已遗忘
        return TimingResult.OPTIMAL

    def get_suspense_balance(self) -> float:
        """返回悬念残留量 (每章应有1-3个悬而未决的问题)"""
```

### 6.5 ChapterEndingChecker (章末质量检查 - 新增)

> **专家评审新增**：确保每章结尾留有钩子

```python
class ChapterEndingChecker:
    """章末质量检查：确保日更断章质量"""

    def check_chapter_ending(self, chapter_text: str) -> ChapterEndingReport:
        """检查最后500字是否满足断章要求"""
        last_500 = chapter_text[-500:]

        conditions = {
            "battle_unresolved": self._has_unresolved_battle(last_500),
            "info_half_revealed": self._has_partial_reveal(last_500),
            "crisis_imminent": self._has_imminent_crisis(last_500),
            "secret_about_to_reveal": self._has_pending_reveal(last_500),
        }

        passed = sum(conditions.values())
        return ChapterEndingReport(
            quality_score=passed / len(conditions) * 100,
            conditions_met=conditions,
            suggestion=self._generate_hook_suggestion(last_500) if passed == 0 else None
        )
```

### 6.6 ShuangganPatternChecker (爽感类型检查 - 新增)

> **专家评审新增**：网文爽感类型库

```python
class ShuangganPatternChecker:
    """网文爽感类型检查"""

    PATTERNS = {
        "dalian": {   # 打脸
            "trigger": ["身份反转", "实力碾压", "啪啪打脸"],
            "structure": "打压→反转→爽感释放"
        },
        "shifu": {    # 释伏
            "trigger": ["伏笔揭露", ["真相大白", "原来是他"]],
            "structure": "埋设→积累→揭露→恍然大悟"
        },
        "tupo": {     # 突破
            "trigger": ["修炼升级", "境界突破", "瓶颈克服"],
            "structure": "积累→压力→突破→蜕变"
        },
        "juehu": {    # 截胡
            "trigger": ["抢夺机缘", "被人截胡", "半路杀出"],
            "structure": "目标→阻挠→反转→逆袭"
        },
        "shoubian": { # 收编
            "trigger": ["收服强者", "收为萌宠", "招兵买马"],
            "structure": "展示→征服→收纳→扩充实力"
        }
    }

    def check_patterns(self, chapter_text: str) -> List[PatternMatch]:
        """检查是否触发爽感模式"""
```

### 6.6.5 RepetitivePatternChecker (套路重复检测 - P2新增)

> **专家评审P2新增**：防止套路重复，保持读者新鲜感

```python
class RepetitivePatternChecker:
    """检测并警告套路重复，保持内容新鲜感"""

    # 已知的套路模式库
    PLAGUE_PATTERNS = {
        "修炼突破": {
            "template": "主角遭遇瓶颈→苦修/奇遇→突破→实力暴涨",
            "max_frequency": "每50章不超过3次",
            "variations": ["顿悟", "灌顶", "血炼", "心魔劫"]
        },
        "打脸": {
            "template": "身份反转→实力碾压→对方震惊→爽感释放",
            "max_frequency": "每20章不超过2次",
            "variations": ["当众打脸", "事后打脸", "持续打脸"]
        },
        "英雄救美": {
            "template": "女主遇险→男主恰好出现→轻松化解→芳心暗许",
            "max_frequency": "每100章不超过2次",
            "variations": ["反救", "互救", "救全家"]
        },
        "绝境逢生": {
            "template": "陷入绝境→濒临死亡→意外转机→逃出生天",
            "max_frequency": "每30章不超过1次",
            "variations": ["空间转移", "高人相救", "潜能爆发"]
        },
        "升级换地图": {
            "template": "当前境界圆满→新地图开放→重新开始→身份落差",
            "max_frequency": "每200章不超过1次",
            "variations": ["飞升", "传送", "境界压制"]
        }
    }

    def check_novel_level_patterns(self, full_text: str) -> PatternReport:
        """检测全书级别的套路重复"""
        pattern_counts = self._count_patterns(full_text)

        warnings = []
        for pattern_name, (count, max_freq) in pattern_counts.items():
            if count > max_freq:
                warnings.append(
                    PatternWarning(
                        pattern=pattern_name,
                        occurrences=count,
                        max_allowed=max_freq,
                        severity="HIGH",
                        suggestion=f"考虑用变体或延迟触发"
                    )
                )

        return PatternReport(
            total_patterns=len(pattern_counts),
            warnings=warnings,
            originality_score=self._calculate_originality_score(pattern_counts)
        )

    def check_chapter_level_patterns(self, chapter_text: str,
                                     previous_chapters: List[str]) -> ChapterPatternReport:
        """检测章节级别的重复"""
        # 检查本章使用的模式
        chapter_patterns = self._extract_patterns(chapter_text)

        # 与前5章对比
        recent_patterns = []
        for prev in previous_chapters[-5:]:
            recent_patterns.extend(self._extract_patterns(prev))

        # 检测连续重复
        consecutive_repeats = self._find_consecutive_repeats(chapter_patterns, recent_patterns)

        return ChapterPatternReport(
            patterns_in_chapter=chapter_patterns,
            consecutive_repeats=consecutive_repeats,
            suggestion=self._generate_variation_suggestion(chapter_patterns)
        )

    def _calculate_originality_score(self, pattern_counts: Dict) -> float:
        """计算原创性评分 (0-100)"""
        total_occurrences = sum(count for count, _ in pattern_counts.values())
        unique_patterns = len([c for c, _ in pattern_counts.values() if c > 0])

        if total_occurrences == 0:
            return 100.0

        # 基础分：独特模式越多越高
        base_score = (unique_patterns / len(self.PLAGUE_PATTERNS)) * 50

        # 惩罚分：总触发次数越多越低
        penalty = min(total_occurrences * 2, 50)

        return max(0, base_score + (50 - penalty))
```

### 6.7 CinematographyChecker (镜头设计检查 - 新增)

> **专家评审新增**：剧本视觉叙事

```python
class CinematographyChecker:
    """镜头设计检查"""

    SHOT_TYPES = [
        "establishing",   # 建立镜头
        "medium",         # 中景
        "close_up",       # 特写
        "over_shoulder",  # 过肩
        "POV",            # 主观镜头
        "two_shot",       # 双人镜头
        "insert",         # 插入镜头
    ]

    def check_visual_storytelling(self, scene_text: str) -> VisualReport:
        """检查视觉叙事是否丰富"""
        return VisualReport(
            shot_diversity=self._count_shot_types(scene_text),
            has_establishing=self._has_establishing(scene_text),
            camera_movements=self._extract_movements(scene_text),
            composition_notes=self._extract_composition(scene_text)
        )
```

### 6.8 CritiqueAgent → RevisionAgent → PolishAgent (编辑Pipeline - 新增)

> **专家评审强调**：编辑是诊断+处方+执行，不是简单的"根据意见修改"

```python
class CritiqueAgent:
    """诊断问题：识别症状和根因"""

    def diagnose(self, draft: str, context: ReviewContext) -> Diagnosis:
        """返回结构化诊断报告"""
        return Diagnosis(
            issues=[
                Issue(type="developmental", severity="high",
                      description="第三幕节奏拖沓", location="Chapter 15-18"),
                Issue(type="line_editing", severity="medium",
                      description="对话过于冗长", location="Chapter 8"),
            ],
            root_causes=[
                "主角动机不明确导致情节推进无力",
                "反派塑造扁平缺乏威胁感"
            ]
        )

class RevisionAgent:
    """开处方：根据诊断给出具体修改建议"""

    def prescribe(self, diagnosis: Diagnosis) -> Prescription:
        """返回修改处方"""
        return Prescription(
            revisions=[
                Revision(
                    priority=1,
                    action="重写第三幕开篇",
                    detail="增加主角做出关键选择的场景",
                    rationale="明确动机才能推进情节"
                ),
            ]
        )

class PolishAgent:
    """行级润色：句子节奏、词汇选择、对话真实感"""

    def polish(self, draft: str, prescription: Prescription) -> str:
        """执行润色"""
        # 专注于句子级别的改进
        # 不改变内容方向，只优化表达
```

---

## 七、实施路线图（专家评审后更新版）

> **专家评审优先级调整**：
> - P0: 反馈回路、垫听机制、编辑关卡、播客类型
> - P1: BeatSheet、章末检查、爽感类型库、CinematographyAgent
> - P2: Hook优先、多平台SEO

| Phase | 任务 | 依赖 | 优先级 | 专家来源 |
|-------|------|------|--------|----------|
| **0** | 架构设计：ContentType枚举 + BaseCrew + EditPipeline | - | P0 | 基础 |
| **1** | 实现CritiqueAgent + RevisionAgent + PolishAgent | 0 | P0 | 编辑 |
| **2** | 实现DiantingChecker + ChapterEndingChecker | 0 | P0 | 网文作家 |
| **3** | 实现OutlineEngine + 反馈回路机制 | 0 | P0 | 小说家 |
| **4** | 实现EntityMemory (跨章节状态追踪) | 0 | P0 | 基础 |
| **5** | 实现NovelCrew (完整流程，含垫听+章末+爽感) | 1,2,3,4 | P0 | 综合 |
| **6** | 实现PodcastCrew (全新类型) | 0,1 | P0 | 播客制作人 |
| **7** | 实现BeatSheetAgent + CinematographyAgent | 0 | P1 | 编剧/导演 |
| **8** | 实现ScriptCrew (含视觉叙事) | 4,7 | P1 | 综合 |
| **9** | 实现HookAgent + TitleAgent + ThumbnailAgent | 0 | P1 | 视频创作者 |
| **10** | 实现BlogCrew (Hook优先 + 多平台SEO) | 1,9 | P1 | 综合 |
| **11** | CLI集成 + 技能市场集成 | 5,6,8,10 | P2 | 工程 |

**关键里程碑:**

| 里程碑 | 包含内容 | 验证标准 |
|--------|----------|----------|
| **M1: 核心抽象** | ContentType + BaseCrew + EditPipeline | 单元测试通过 |
| **M2: 小说MVP** | NovelCrew + 垫听 + 章末检查 | 能生成10章完整小说 |
| **M3: 播客MVP** | PodcastCrew + 全流程 | 能生成30分钟播客脚本 |
| **M4: 剧本MVP** | ScriptCrew + BeatSheet + Cinematography | 能生成电影剧本 |
| **M5: 博客MVP** | BlogCrew + Hook优先 + SEO | 能生成SEO优化文章 |
| **M6: 技能集成** | 技能市场 + deer-flow skills | npx skills list 可见 |

---

## 八、API接口设计（专家评审后更新版）

```python
# 用户API示例
from crewai.content import NovelCrew, ScriptCrew, BlogCrew, PodcastCrew

# ============ 小说 ============
crew = NovelCrew(
    topic="都市修仙",
    target_words=500000,
    style="爽文",
    enable_dianting=True,       # 垫听机制
    enable_chapter_ending=True,  # 章末检查
    enable_shuanggan=True,       # 爽感类型
    feedback_loop=True,          # 写作→大纲反馈
)
novel = crew.kickoff()
# 输出: (novel_text, outline, dianting_report, chapter_endings)

# ============ 剧本 ============
crew = ScriptCrew(
    genre="悬疑",
    episodes=12,
    format="final_draft",
    include_beat_sheet=True,     # 分镜表
    include_cinematography=True, # 镜头设计
    include_visual_motifs=True, # 视觉母题
)
script = crew.kickoff()
# 输出: (script_text, beat_sheet, shot_list, visual_motifs)

# ============ 博客 ============
crew = BlogCrew(
    topic="AI Agent最佳实践",
    keywords=["multi-agent", "crewAI"],
    target_audience="开发者",
    hook_first=True,            # Hook优先于Research
    title_variants=5,           # 生成5个标题变体
    platform="seo",              # or "youtube", "tiktok"
)
post = crew.kickoff()
# 输出: (blog_text, hook_options, title_variants, thumbnail_concept)

# ============ 播客 (新增) ============
crew = PodcastCrew(
    topic="AI Agent最佳实践",
    duration_minutes=30,
    hosts=2,
    style="conversational",
    include_interview=False,
    include_ads=True,
)
podcast = crew.kickoff()
# 输出: (script, timestamps, shownotes, transcript)

# ============ 编辑Pipeline (新增) ============
from crewai.content.editing import CritiqueAgent, RevisionAgent, PolishAgent

critique = CritiqueAgent()
diagnosis = critique.diagnose(draft_text, context)

revision = RevisionAgent()
prescription = revision.prescribe(diagnosis)

polish = PolishAgent()
final_text = polish.execute(draft_text, prescription)
```

---

## 九、与crewAI现有架构的整合点

| 现有组件 | 整合方式 |
|----------|----------|
| **Flow DSL** | 使用`@start/@listen/@router`组织内容生成流程 |
| **Crew** | 内容Crew继承现有Crew基类，复用task delegation |
| **Agent** | 新Agent类型(OutlineAgent等)继承BaseAgent |
| **Task** | 扩展Task类支持content_type和review维度 |
| **Memory** | 复用现有memory系统存储实体状态 |

---

## 十、可复用的agency-agents最佳实践

### 10.1 NEXUS Pipeline模式

```
Phase 0: Discovery (情报收集) → Quality Gate
Phase 1: Strategy (战略规划) → Quality Gate
Phase 2: Foundation (基础构建) → Quality Gate
Phase 3: Build (开发迭代) → Quality Gate
Phase 4: Harden (质量加固) → Quality Gate
Phase 5: Launch (发布增长) → Quality Gate
Phase 6: Operate (持续运营)
```

### 10.2 Dev↔QA Loop

```
Task Assigned → Developer Implements → QA Tests → PASS?
    ↓ No (attempt < 3)     ↓ Yes
Developer Fixes ← QA Feedback ← Loop back
    ↓ No (attempt >= 3)
Escalate
```

### 10.3 Handoff协议

```markdown
HANDOFF: [From] -> [To]
  PAYLOAD: { field: type, ... }
  SUCCESS RESPONSE: { field: type, ... }
  FAILURE RESPONSE: { error: string, code: string, retryable: bool }
  TIMEOUT: Xs — treated as FAILURE
  ON FAILURE: [recovery action]
```

### 10.4 质量门禁模式

| Gate | Keeper | 决策 | 证据要求 |
|------|--------|------|----------|
| Phase 0 | Executive Summary Generator | GO/NO-GO/PIVOT | 市场数据、用户痛点确认 |
| Phase 1 | Studio Producer + Reality Checker | 批准/拒绝 | 架构覆盖度，品牌系统、预算 |
| Phase 3 | Reality Checker | PASS/FAIL | 截图证据、测试结果 |
| Phase 4 | Reality Checker | READY/NEEDS_WORK | 全链路截图，性能指标 |

---

### 10.5 agency-agents Agent定义复用 (详细模式)

#### Book Co-Author (强复用)

| 模式 | crewAI实现方式 |
|------|----------------|
| **Chapter Blueprint** | `OutlineAgent` 生成结构化章纲 |
| **Versioned Drafts** | `DraftAgent` 输出多个版本供选择 |
| **Editorial Notes** | `ReviewAgent` 输出结构化审查报告 |
| **Voice Protection** | 角色对话使用 `CharacterVoicePillars` 保证一致性 |
| **Feedback Loop** | `EditAgent` 接收审查意见进行修改 |

#### Narratologist (强复用)

| 框架 | 应用场景 |
|------|----------|
| **Vogler's Hero's Journey** | 剧本/小说主线结构 |
| **Propp's 31 Functions** | 民间故事/奇幻小说 |
| **Campbell's Monomyth** | 史诗/奇幻/冒险故事 |
| **McKee's Story Structure** | 剧本对话/场景设计 |

```python
class NarrativeFramework(Enum):
    VOGLER_HERO_JOURNEY = "hero_journey"
    PROPP_FUNCTIONS = "propp_31"
    CAMPBELL_MONOMYTH = "monomyth"
    MCKEE_STRUCTURE = "mckee"
```

#### Narrative Designer (游戏叙事，可借鉴)

| 模式 | 内容生成应用 |
|------|--------------|
| **Character Voice Pillars** | 角色语言风格一致性检查 |
| **Dialogue Node Format** | 对话场景结构化输出 |
| **Lore Tier Architecture** | 世界观设定分层管理 |
| **Branching Narrative** | 博客/剧本的多结局分支 |

#### SEO Specialist (博客专用)

| 组件 | 描述 |
|------|------|
| **Technical SEO Audit** | 页面结构、加载速度、移动端 |
| **Keyword Strategy Document** | 关键词密度、LSI词簇 |
| **On-Page Optimization Checklist** | H1/H2、meta描述、内链 |
| **Content Gap Analysis** | 竞品内容覆盖度分析 |

```python
class SEOChecklist:
    title_optimization = ["keyword_at_start", "length_50_60"]
    meta_description = ["keyword_included", "length_150_160"]
    heading_structure = ["single_h1", "logical_h2_h3"]
    internal_linking = ["2_4_links_per_1000_words"]
    keyword_density = ["1_2_percent_optimal"]
```

### 10.6 推荐复用优先级

| 优先级 | Agent/模式 | 复用理由 |
|--------|------------|----------|
| **P0** | Book Co-Author | 完整的工作流模式 |
| **P0** | Narratologist | 小说/剧本结构框架 |
| **P1** | SEO Specialist | 博客生成必需 |
| **P1** | Narrative Designer | 角色一致性检查 |
| **P2** | Content Creator | 多平台适配 |

### 10.7 crewAI Agent实现映射

```
crewai/src/crewai/agents/
├── content/
│   ├── outline_agent.py      # 复用 Book Co-Author 的 Blueprint 模式
│   ├── world_agent.py        # 复用 Narrative Designer 的 Lore Tier
│   ├── plot_agent.py         # 复用 Narratologist 的结构框架
│   ├── draft_agent.py        # 复用 Book Co-Author 的 Versioned Drafts
│   ├── review_agent.py       # 复用六维审查 + Editorial Notes
│   ├── edit_agent.py         # 复用 Feedback Loop
│   ├── seo_agent.py          # 直接复用 SEO Specialist
│   └── format_agent.py       # 复用 Dialogue Node Format
```

---

## 十二、Awesome Skills 仓库研究 (额外发现)

### 12.1 VoltAgent/awesome-agent-skills 关键发现

| 类别 | 技能 | crewAI整合价值 |
|------|------|----------------|
| **文档生成** | docx, pptx, xlsx, pdf | 输出格式多样化 |
| **Canvas设计** | canvas-design | 视觉内容生成 |
| **Web构建** | web-artifacts-builder | 交互式内容展示 |
| **MCP Builder** | mcp-builder | API集成模式 |

### 12.2 ComposioHQ/awesome-claude-skills 关键发现

#### Skill Anatomy (三层渐进式加载)
```
SKILL.md 三层结构:
├── Layer 1: Metadata (始终加载, ~100词)
│   └── name + description + TRIGGER/DO NOT TRIGGER
├── Layer 2: SKILL.md body (技能触发时加载, <5k词)
│   └── 核心过程知识
└── Layer 3: scripts/ + references/ + assets/ (按需加载)
```

#### content-research-writer 工作流
1. Collaborative Outlining (协作大纲)
2. Research Assistance (研究协助)
3. Hook Improvement (钩子优化)
4. Section Feedback (分段反馈)
5. Voice Preservation (声音保持)
6. Citation Management (引用管理)
7. Iterative Refinement (迭代优化)

### 12.3 openclaw/skills 关键发现

#### SEO Content Engine (HBCFC公式)
```
H — Hook (前100字)
B — Bridge (问题引入)
C — Core Content (核心内容)
F — FAQ Section
C — Conclusion + CTA
```

#### Content Scoring Rubric (100分制)
| 维度 | 分值 |
|------|------|
| Keyword optimization | /15 |
| Content depth | /20 |
| Readability | /15 |
| Practical value | /15 |
| Structure | /10 |
| Internal links | /5 |
| External links | /5 |
| Media | /5 |
| Meta tags | /5 |
| CTA clarity | /5 |

#### Agent Debate Pattern (多Agent辩论)
```
Single Round: 3 agents, one round, synthesis (~5 min)
Two Round: Position + rebuttal + synthesis (~10 min)
Red Team: Builder + attacker adversarial review
```

#### QA Engine Release Readiness Score
| 维度 | 权重 |
|------|------|
| Test coverage | 25% |
| Bug status | 25% |
| Performance | 20% |
| Security | 20% |
| Operational | 10% |

**Ship threshold**: >= 80 overall, no dimension below 60

### 12.4 find-skills 高价值技能推荐

#### Tier 1: 核心技能 (优先安装)

| 类别 | 技能 | 安装量 | 问题解决 | crewAI整合 |
|------|------|--------|----------|------------|
| **World-Building** | `junaid18183/novel-architect-skills@novel-architect` | 640 | 综合小说世界观构建 | World Architect Agent |
| **Story Planning** | `jwynia/agent-skills@story-coach` | 290 | 叙事结构、情节发展 | Plot Agent |
| **Story Coherence** | `jwynia/agent-skills@story-sense` | 180 | 跨章节叙事一致性 | QA Agent |
| **Blog/SEO** | `langchain-ai/deepagents@blog-post` | 433 | 完整博客生成 | BlogCrew Primary |

#### Tier 2: 专业内容技能

| 类别 | 技能 | 安装量 | 问题解决 |
|------|------|--------|----------|
| **SEO Writing** | `blink-new/claude@seo-article-writing` | 13 | 搜索优化内容 |
| **Blog Generation** | `kostja94/marketing-skills@blog-page-generator` | 175 | 营销导向博客 |
| **Copy Editing** | `openclaudia/openclaudia-skills@copy-editing` | 51 | 润色和语法精修 |
| **Character/World** | `jwynia/agent-skills@worldbuilding` | 145 | 深度角色和设定创建 |
| **Systemic World** | `jwynia/agent-skills@systemic-worldbuilding` | 117 | 经济/政治/社会系统 |

#### Tier 3: 质量保证技能

| 类别 | 技能 | 安装量 | 问题解决 |
|------|------|--------|----------|
| **QA Agent** | `first-fluke/oh-my-ag@qa-agent` | 43 | 自动化质量检查 |
| **Doc Review** | `vladm3105/aidoc-flow-framework@doc-ears-reviewer` | 25 | 审核和反馈循环 |
| **Requirements** | `vladm3105/aidoc-flow-framework@doc-req-reviewer` | 24 | 内容规格验证 |

#### Tier 4: 多Agent协调

| 类别 | 技能 | 安装量 | 问题解决 |
|------|------|--------|----------|
| **Orchestration** | `yonatangross/orchestkit@multi-agent-orchestration` | 13 | 多Agent协调 |
| **Team Coord** | `hkuds/clawteam@clawteam-multi-agent-coordination` | 9 | Agent间任务传递 |
| **Agent-Agent** | `ruvnet/claude-flow@agent-agent` | 27 | Agent间协作模式 |

### 12.5 推荐crewAI Pipeline架构 (更新版)

```
[Research] → [World Building] → [Plot Planning] → [Content Generation] → [QA Review] → [SEO Optimization] → [Final Polish]
    ↓              ↓                    ↓                  ↓                    ↓              ↓                ↓
 crewAI      junaid18183/        jwynia/           langchain-ai/        first-fluke/   blink-new/     openclaudia/
 Researcher  novel-architect     story-coach        deepagents            qa-agent       seo-article    copy-editing
                                                    blog-post                                           writing
```

### 12.6 效率提升预期

| 阶段 | 技能 | 预期效率提升 |
|------|------|-------------|
| World-building | `novel-architect` (640 installs) | 60-70% 时间节省 |
| Plot planning | `story-coach` (290 installs) | 50% 更快结构创建 |
| Content generation | `blog-post` (433 installs) | 40-50% 初稿生成加速 |
| QA | `qa-agent` (43 installs) | 30% 减少修订轮次 |
| SEO | `seo-article-writing` (13 installs) | 20-30% 搜索排名优化提升 |

### 12.7 安装命令

```bash
# 核心内容生成
npx skills add junaid18183/novel-architect-skills@novel-architect
npx skills add jwynia/agent-skills@story-coach
npx skills add langchain-ai/deepagents@blog-post

# QA和审核
npx skills add first-fluke/oh-my-ag@qa-agent
npx skills add openclaudia/openclaudia-skills@copy-editing

# SEO优化
npx skills add blink-new/claude@seo-article-writing
```

---

## 十四、deer-flow 项目深度分析

### 14.1 项目架构

**类型**: 基于 LangGraph 的超级 Agent Harness，支持沙箱执行、记忆和可扩展技能

**技术栈**:
- Backend: Python 3.12+, LangGraph SDK, LangChain Core
- Frontend: Next.js 16, React 19, TypeScript 5.8, Tailwind CSS 4
- Orchestration: LangGraph for agent runtime, FastAPI Gateway

**目录结构**:
```
deer-flow/
├── backend/packages/harness/deerflow/
│   ├── agents/              # Lead agent + middleware chain
│   ├── subagents/           # Sub-agent delegation system
│   ├── sandbox/             # Sandbox execution (local/Docker/K8s)
│   ├── tools/               # Built-in tools
│   ├── skills/              # Skills loading/parsing
│   ├── memory/              # Memory system
│   └── models/              # Model factory
├── frontend/                 # Next.js web interface
└── skills/public/           # Public skills (markdown-based)
```

### 14.2 可复用组件

#### Lead Agent 模式
```python
# /backend/packages/harness/deerflow/agents/lead_agent/agent.py
def make_lead_agent(config: RunnableConfig):
    # 动态模型选择 (thinking/vision support)
    # 工具加载 via get_available_tools()
    # System prompt generated by apply_prompt_template()
```

#### ThreadState 状态管理
```python
class ThreadState(AgentState):
    sandbox: SandboxState
    thread_data: ThreadDataState
    title: str
    artifacts: list[str]  # Deduplicated
    todos: list
    uploaded_files: list[dict]
    viewed_images: dict[str, ViewedImageData]
```

#### Subagent Executor (双线程池架构)
```python
class SubagentExecutor:
    _scheduler_pool = ThreadPoolExecutor(max_workers=3)  # Task scheduling
    _execution_pool = ThreadPoolExecutor(max_workers=3)  # Actual execution

    def execute_async(self, task: str, task_id: str | None = None) -> str:
        # Returns task_id for polling
        # Events: task_started, task_running, task_completed/failed/timed_out
```

### 14.3 内容生成技能 (直接复用)

| 技能 | 路径 | 描述 |
|------|------|------|
| **podcast-generation** | `skills/public/podcast-generation/` | 双host对话式播客生成 |
| **ppt-generation** | `skills/public/ppt-generation/` | AI图片幻灯片 → PPTX |
| **chart-visualization** | `skills/public/chart-visualization/` | 26种图表类型 |
| **image-generation** | `skills/public/image-generation/` | 结构化提示词 → 图片 |
| **data-analysis** | `skills/public/data-analysis/` | DuckDB SQL分析 |
| **deep-research** | `skills/public/deep-research/` | 多阶段网络研究 |

#### Podcast Generation Pattern (JSON格式)
```json
{
  "locale": "en",
  "lines": [
    {"speaker": "male", "paragraph": "dialogue"},
    {"speaker": "female", "paragraph": "dialogue"}
  ]
}
```
Workflow: Create JSON → Execute `generate.py` → Output MP3 + transcript

#### PPT Generation Pattern (视觉一致性)
```json
{
  "title": "Presentation Title",
  "style": "glassmorphism",
  "slides": [
    { "type": "title", "title": "...", "visual_description": "..." },
    { "type": "content", "key_points": [...], "visual_description": "..." }
  ]
}
```
**关键**: 幻灯片**顺序生成**，使用前一张作为参考保证视觉一致性

### 14.4 Middleware Chain (可借鉴)

**11个中间件按顺序执行**:
1. **ThreadDataMiddleware** - 创建per-thread目录
2. **UploadsMiddleware** - 跟踪新上传文件
3. **SandboxMiddleware** - 获取沙箱
4. **DanglingToolCallMiddleware** - 修补缺失的tool响应
5. **SummarizationMiddleware** - Token限制时上下文缩减
6. **TodoListMiddleware** - 任务追踪
7. **TitleMiddleware** - 自动生成线程标题
8. **MemoryMiddleware** - 异步记忆更新队列
9. **ViewImageMiddleware** - 注入base64图像数据
10. **SubagentLimitMiddleware** - 强制MAX_CONCURRENT_SUBAGENTS
11. **ClarificationMiddleware** - 拦截clarification请求

### 14.5 可借鉴的最佳实践

| 模式 | crewAI整合价值 |
|------|----------------|
| **渐进式加载** | Skills三层加载机制 (metadata → body → resources) |
| **隔离上下文** | Subagent独立运行防止干扰 |
| **视觉一致性** | PPT顺序生成+参考链 |
| **结构化输出** | JSON Schema用于内容生成 |
| **Middleware组合** | 责任链模式处理横切关注点 |
| **线程池模式** | 分离调度和执行的异步任务处理 |
| **沙箱抽象** | Sandbox接口统一本地/Docker/K8s执行 |

### 14.6 crewAI整合建议

```
crewAI 可从 deer-flow 借鉴:
├── 复用 deer-flow skills/
│   ├── podcast-generation/    → ScriptCrew 音频输出
│   ├── ppt-generation/        → ScriptCrew 演示输出
│   └── deep-research/        → ResearchCrew 研究流程
├── 借鉴 Subagent Executor 模式
│   └── 实现 crewAI 的 task delegation with timeout
├── 借鉴 Middleware Chain
│   └── 为 Crew 添加 cross-cutting concerns
└── 借鉴 Memory System
    └── 增强 crewAI 的实体记忆系统
```

### 14.7 关键文件路径

| 组件 | 路径 |
|------|------|
| Lead Agent | `deer-flow/backend/packages/harness/deerflow/agents/lead_agent/agent.py` |
| Thread State | `deer-flow/backend/packages/harness/deerflow/agents/thread_state.py` |
| Subagent Executor | `deer-flow/backend/packages/harness/deerflow/subagents/executor.py` |
| Task Tool | `deer-flow/backend/packages/harness/deerflow/tools/builtins/task_tool.py` |
| Sandbox Tools | `deer-flow/backend/packages/harness/deerflow/sandbox/tools.py` |
| Skills System | `deer-flow/backend/packages/harness/deerflow/skills/` |
| Memory Updater | `deer-flow/backend/packages/harness/deerflow/agents/memory/updater.py` |
| Clarification Middleware | `deer-flow/backend/packages/harness/deerflow/agents/middlewares/clarification_middleware.py` |
| Podcast Skill | `deer-flow/skills/public/podcast-generation/SKILL.md` |
| PPT Skill | `deer-flow/skills/public/ppt-generation/SKILL.md` |
| Deep Research Skill | `deer-flow/skills/public/deep-research/SKILL.md` |

---

## 十六、专业评审团审查意见

### 16.1 小说家评审 (World-Class Novelist)

**核心问题**: 技术满分，创作理解零分

| 维度 | 评分 | 问题 |
|------|------|------|
| 技术架构 | 9/10 | 多Agent设计合理 |
| 写作工艺捕获 | 2/10 | 流水式生成，无迭代反馈 |
| 六维审查 | 4/10 | 缺少：内心描写、潜文本、感官细节 |
| Strand Weave | 3/10 | Fire混淆情感峰值与动作高潮 |
| 主题表达 | 2/10 | 百分比预设扼杀自然涌现 |

**关键缺失:**
- 角色内心世界 (Interiority)
- 叙事视角规范 (POV、叙事距离)
- 类型契约 (Genre Contract)
- 伏笔与回收追踪
- 结尾质量评估门控
- **反馈回路**: 写作过程中应允许大纲演进

**评语**: "技术正确但没有生命" — 无法优化到情感共鸣层面

---

### 16.2 网文作家评审 (Web Novel Specialist)

**核心问题**: 完全不理解网文产品逻辑

| 维度 | 评分 | 问题 |
|------|------|------|
| 网文节奏理解 | 2/10 | 不理解日更、章末断章 |
| 爽感机制 | 3/10 | high_point是空壳 |
| 垫听机制 | 0/10 | 完全没有伏笔追踪 |
| 网文元素覆盖 | 1/10 | 修炼/金手指/打脸全无 |
| 商业化考量 | 1/10 | 付费读者心理完全没考虑 |

**关键缺失:**
```
垫听机制 (dianting_checker):
├── 伏笔回收率 (Chapter N埋钩子 → Chapter N+5~20回收)
├── 情绪积累周期 (打压→释放节奏)
└── 悬念残留量 (每章结尾未解答问题)

网文爽感类型库:
├── 打脸 (身份反转打脸)
├── 释伏 (伏笔揭露)
├── 突破 (修炼升级)
├── 截胡 (抢夺机缘)
└── 收编 (收服强者/萌宠)

章末质量检查 (chapter_ending_quality_checker):
└── 每章最后500字必须:
    ├── 战斗未决出胜负
    ├── 信息揭露一半
    ├── 危机突然降临
    └── 身份/秘密即将揭晓
```

**商业化缺失:**
- 作者人格化模块 (模拟特定作者风格)
- 套路重复检测器
- 读者反馈闭环 (评论→情绪分析→内容调整)
- 惊喜度评估

---

### 16.3 影视编剧评审 (Film/TV Screenwriter)

**核心问题**: Pipeline颠倒现实工作流

**现实编剧室流程:**
```
Show Bible → Season Arc → Episode Beat Sheet → Step Outline → Full Draft → Notes → Revision → Polish
```

**方案Pipeline (错误):**
```
StructureCrew → SceneCrew → DialogueCrew → FormatCrew
```

**关键问题:**
1. **缺少 Beat Sheet 步骤** — 结构与场景之间应有场景-动作分解
2. **场景与对话不是顺序关系** — 两者互相依赖
3. **FormatAgent是输出工具不是质量门控** — 格式好≠剧本好

**缺失元素:**
- 分镜表 (Beat Sheet)
- 场景目的验证 (谁想要什么？障碍是什么？)
- 对话功能 (揭示角色？推进剧情？制造张力？)
- 潜文本检查

---

### 16.4 视频创作者评审 (Video Content Creator)

**核心问题**: Pipeline倒置，内容=文本优先

**正确创作者工作流:**
```
Hook/Angle → Outline → Script → Thumbnail/Title → Publish
```

**方案Pipeline (倒置):**
```
Research → Outline → Writing → SEO → Edit
```

**缺失元素:**
| 元素 | 作用 |
|------|------|
| **HookAgent** | 生成5-10个钩子变体 |
| **ThumbnailConceptAgent** | 视觉钩子描述+文字建议 |
| **TitleAgent** | CTR优化标题变体 |
| **PlatformAdapterCrew** | 内容→平台适配格式 |

**SEO认知过于狭隘:**
- 仅关注博客SEO
- 缺少YouTube SEO (CTR、观看时长、互动率)
- 缺少TikTok SEO (完播率、互动速度)

---

### 16.5 播客制作人评审 (Podcast Producer)

**核心问题**: 播客作为内容类型完全缺失

**播客ScriptCrew应有的结构:**
```
[PreShowCrew] → Hook脚本 (0:00-0:30)、预告、节目描述
[IntorCrew] → 主持开场、品牌时刻
[SegmentCrew循环] → 话题设置→深度内容→过渡
[InterviewCrew] → 嘉宾介绍、问题准备
[AdReadCrew] → 原生广告植入脚本
[OutroCrew] → 回顾、CTA、订阅提示
[ShowNotesCrew] → 时间戳章节、链接、 transcript
```

**播客专属元素缺失:**
- Hook脚本 (前30秒决定70%留存)
- 冷开场 (Cold Open)
- 品牌开场/收尾
- 片段过渡
- 中插广告
- 嘉宾介绍公式
- 回调/回顾
- 口头CTA
- 章节标记
- 节目描述 (150-300词)

**30秒法则**: 前30秒不能解释"为什么应该留下"，就会失去听众

---

### 16.6 电影导演评审 (Film Director)

**核心问题**: ScriptCrew只处理对话，视觉叙事为零

**当前SceneCrew (弱):**
```
SceneCrew → 场景描述、角色动作、情绪弧线
```

**导演需要的SceneCrew (强):**
```
SceneCrew → 场景描述(含地点质感)、镜头设计、
           角色动作、情绪弧线、视觉构图意图、过渡方式
```

**缺失元素:**
| 元素 | 导演为什么需要 |
|------|----------------|
| **Coverage Planning** | 场景需要多机位，覆盖风格 |
| **Shot List Integration** | 脚本应输出shot list |
| **Visual Motif Tracker** | 追踪视觉母题、颜色、意象 |
| **Transition Agent** | CUT vs DISSOLVE vs FADE是语法 |
| **Screen Geography** | 180度规则、左右观众定位 |
| **Runtime Modeling** | 每场景估计时长 vs 实际运行时 |

**FormatAgent是类型错误:**
- 当前: 处理Final Draft格式 = 排版Agent
- 应该: 改名ExportAgent，新增VisualFormatAgent处理宽高比、构图、电影语法

**需要新增Agent:**
- `CinematographyAgent` — 镜头设计、相机运动、视觉语法
- `VisualMotifTracker` — 视觉母题追踪
- `TransitionAgent` — 过渡语法
- `CoveragePlanner` — shot list生成、覆盖选项
- `LocationVisionAgent` — 地点质感描述

---

### 16.7 资深编辑评审 (Professional Editor)

**核心问题**: ReviewAgent/EditAgent过于机械，编辑是诊断+处方+重写

**编辑工作光谱:**
| 编辑类型 | 职责 | 时机 |
|----------|------|------|
| **Developmental Editing** | 结构、叙事弧线、主题一致性 | 大纲、早期草稿 |
| **Content/Substantive** | 论证结构、场景逻辑、节奏 | 草稿阶段 |
| **Line Editing** | 句子节奏、词汇选择、对话真实感 | 草稿润色 |
| **Copy Editing** | 语法、一致性、风格指南 | 出版前 |
| **Proofreading** | 错别字、格式、最终错误 | 最终通过 |

**当前方案问题:**
- ReviewAgent识别问题但不解决问题
- EditAgent根据审查意见修改 ≠ 编辑实际工作

**正确模型:**
```
CritiqueAgent (诊断) → RevisionAgent (处方) → PolishAgent (行级润色)
```

**六维审查问题:**
- `consistency_checker` vs `continuity_checker` — 重复检查同一事物
- `reader_pull_checker` — 不可量化，可能产生虚假自信
- 缺少场景目的评估 — 每个场景应有明确存在理由

**缺少的编辑关卡:**
- 事实核查 (时间线、人物细节、世界规则)
- 敏感性阅读 (代表性、文化准确性)
- 抄袭检测
- 可读性评分 (超越Flesch-Kincaid)
- 朗读测试 (默读好的文章朗读可能拗口)

**Pipeline应有的编辑阶段:**
```
大纲阶段 → 发展性反馈
草稿阶段1 → 内容编辑
草稿阶段2 → 行级编辑
副本编辑门控 → 冻结点
副本编辑 → 机械修正
预发布 → 校对
```

---

### 16.8 评审综合问题清单

| 优先级 | 问题 | 来源 |
|--------|------|------|
| **P0** | 缺少反馈回路 (写作可反向影响大纲) | 小说家 |
| **P0** | 网文垫听机制完全缺失 | 网文作家 |
| **P0** | 无编辑关卡 (无冻结点) | 编辑 |
| **P0** | 播客作为内容类型完全缺失 | 播客制作人 |
| **P1** | 章末质量检查缺失 (日更断章) | 网文作家 |
| **P1** | 爽感类型库缺失 | 网文作家 |
| **P1** | Beat Sheet步骤缺失 | 编剧 |
| **P1** | Hook优先于Research | 视频创作者 |
| **P1** | CinematographyAgent缺失 | 导演 |
| ~~P2~~ ✅ | FormatAgent应改名 | 导演 | → ExportAgent + VisualFormatAgent |
| ~~P2~~ ✅ | 套路重复检测器 | 网文作家 | → RepetitivePatternChecker 已实现 |
| ~~P2~~ ✅ | PlatformAdapterCrew | 视频创作者 | → PlatformAdapterAgent 已实现 |
| ~~P2~~ ✅ | SEOAgent过于狭隘 | 视频创作者 | → 多平台SEO支持已实现 |

### 16.9 方案修改建议总结

**NovelCrew 需修改:**
1. ✅ 增加 垫听机制 (dianting_checker) - 已实现
2. ✅ 增加 章末质量检查 (chapter_ending_quality_checker) - 已实现
3. ✅ 增加 网文爽感类型库 (打脸/释伏/突破/截胡/收编) - 已实现
4. ✅ 允许 写作→大纲 的反馈回路 - 已实现
5. ✅ 增加 套路重复检测器 (RepetitivePatternChecker) - 已实现
6. ✅ 增加 心理学/内心 检查器 (InteriorityChecker) - 已实现
7. ✅ 增加 叙事视角规范步骤 (POVChecker) - 已实现
8. ✅ 替换Fire为分开的情感弧线检查和动作高潮检查 - 已实现

**ScriptCrew 需修改:**
1. ✅ 在StructureCrew和SceneCrew之间增加 BeatSheet步骤 - BeatSheetAgent 已实现
2. ✅ 增加 CinematographyAgent - 已实现
3. ✅ 增加 VisualMotifTracker - 已实现
4. ✅ 重命名FormatAgent为ExportAgent，新增VisualFormatAgent - 已实现
5. ✅ 增加 CoveragePlanner - 已实现
6. ✅ 增加 视觉叙事检查点 - CinematographyChecker 已实现

**BlogCrew 需修改:**
1. ✅ 改为 Hook优先 (Phase 0) - HookAgent 已实现
2. ✅ 增加 TitleAgent - 已实现
3. ✅ 增加 ThumbnailConceptAgent - 已实现
4. ✅ 扩展SEOAgent为平台专用变体 (YouTubeSEO/TikTokSEO) - PlatformAdapterAgent 已实现

**新增 PodcastCrew:**
1. ✅ PreShowCrew (Hook脚本、预告) - PreShowAgent + ColdOpenAgent 已实现
2. ✅ IntroCrew/OutroCrew (品牌时刻) - IntroAgent + OutroAgent 已实现
3. ✅ SegmentCrew (话题深度) - SegmentAgent 已实现
4. ✅ TransitionAgent (过渡) - 已实现
5. ✅ AdReadCrew (原生广告) - AdReadAgent 已实现
6. ✅ ShowNotesCrew (时间戳、链接) - ShowNotesAgent 已实现

**编辑Pipeline重构:**
1. ✅ CritiqueAgent (诊断) - 已实现
2. ✅ RevisionAgent (处方) - 已实现
3. ✅ PolishAgent (行级润色) - 已实现
4. ✅ CopyEditGate (冻结点) - 已实现
5. ✅ ProofreadGate - 已实现

---

## 十六、v2.0 更新日志（专家评审后）

### 更新内容

| 章节 | 更新内容 | 专家来源 |
|------|----------|----------|
| **Section 4** | 核心Agent设计全面重构 | 综合 |
| | - 新增小说专用Agent: DiantingChecker, ChapterEndingChecker, ShuangganPatternChecker, InteriorityChecker, POVChecker | 网文作家 |
| | - 新增剧本专用Agent: BeatSheetAgent, CinematographyAgent, VisualMotifTracker, TransitionAgent, CoveragePlanner, LocationVisionAgent, VisualFormatAgent | 编剧/导演 |
| | - 新增博客专用Agent: HookAgent, TitleAgent, ThumbnailConceptAgent, PlatformAdapterAgent | 视频创作者 |
| | - 新增播客专用Agent: PreShowAgent, IntroAgent, SegmentAgent, InterviewAgent, AdReadAgent, OutroAgent, ShowNotesAgent, ColdOpenAgent | 播客制作人 |
| | - 重构编辑Pipeline: ReviewAgent→CritiqueAgent, EditAgent→RevisionAgent+PolishAgent | 编辑 |
| | - FormatAgent重命名为ExportAgent | 导演 |
| **Section 5** | Crew设计方案全面更新 | |
| | - NovelCrew: 增加垫听机制、章末检查、爽感类型、反馈回路 | 网文作家 |
| | - ScriptCrew: 增加BeatSheet、Cinematography、VisualMotif | 编剧/导演 |
| | - BlogCrew: Hook优先、TitleAgent、ThumbnailAgent | 视频创作者 |
| | - **新增 PodcastCrew**: 完整播客生成流程 | 播客制作人 |
| | - **新增编辑Pipeline**: Critique→Revision→Polish→CopyEditGate→ProofreadGate | 编辑 |
| **Section 6** | 关键实现模块新增 | |
| | - DiantingChecker (垫听机制) | 网文作家 |
| | - ChapterEndingChecker (章末检查) | 网文作家 |
| | - ShuangganPatternChecker (爽感类型) | 网文作家 |
| | - **RepetitivePatternChecker (套路重复检测)** | 网文作家 |
| | - CinematographyChecker (镜头设计) | 导演 |
| | - CritiqueAgent + RevisionAgent + PolishAgent | 编辑 |
| **Section 7** | 实施路线图优先级调整 | |
| | - Phase 0-4: 核心架构 + 反馈回路 | 基础 |
| | - Phase 1: CritiqueAgent优先实现 | 编辑 |
| | - Phase 2: DiantingChecker优先实现 | 网文作家 |
| | - Phase 6: PodcastCrew全新独立Phase | 播客制作人 |
| | - 新增里程碑: M1-M6 | 综合 |
| **Section 8** | API接口更新 | |
| | - 所有Crew支持新参数 | |
| | - PodcastCrew API | |
| | - 编辑Pipeline API | |

### 解决的问题

| P0问题 | 状态 | 解决方案 |
|--------|------|----------|
| 缺少反馈回路 | ✅ 已解决 | OutlineEngine增加反馈机制，写作可反向影响大纲 |
| 网文垫听机制缺失 | ✅ 已解决 | DiantingChecker实现，追踪伏笔回收 |
| 无编辑关卡 | ✅ 已解决 | CopyEditGate冻结点，内容不可无限修改 |
| 播客类型缺失 | ✅ 已解决 | PodcastCrew完整实现 |

| P1问题 | 状态 | 解决方案 |
|--------|------|----------|
| 章末质量检查 | ✅ 已解决 | ChapterEndingChecker |
| 爽感类型库 | ✅ 已解决 | ShuangganPatternChecker |
| Beat Sheet步骤 | ✅ 已解决 | BeatSheetAgent |
| Hook优先 | ✅ 已解决 | HookAgent作为BlogCrew Phase 0 |
| CinematographyAgent | ✅ 已解决 | 新增Agent |

| P2问题 | 状态 | 解决方案 |
|--------|------|----------|
| FormatAgent改名 | ✅ 已解决 | → ExportAgent + VisualFormatAgent |
| 套路重复检测器 | ✅ 已解决 | RepetitivePatternChecker |
| PlatformAdapterCrew | ✅ 已解决 | PlatformAdapterAgent |
| SEOAgent过于狭隘 | ✅ 已解决 | 多平台SEO支持 |

---

## 十五、Sources

- [Build a Multi-Agent Book Writer - Lightning AI](https://lightning.ai/akshay-ddods/studios/build-a-multi-agent-book-writer)
- [Multi-Agent AI Content Writing with CrewAI](https://kshitijkutumbe.medium.com/multi-agent-ai-mastery-building-content-writing-ai-system-with-crewai-3c63df57e607)
- [StoryWriter: Multi-Agent Framework for Long Story Generation (arXiv)](https://arxiv.org/pdf/2506.16445)
- [AI Storytelling with Multi-Agent LLMs](https://blog.apiad.net/p/ai-storytelling-1)
- [7 Proven Strategies for SEO Content Creation with Multiple AI Agents](https://www.trysight.ai/blog/seo-content-creation-with-multiple-ai-agents)
- [CrewAI Blog Automation with Multi-Agent](https://christianmendieta.ca/crewai-blog-automation-building-a-multi-agent-content-creation-system-with-python/)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills)
- [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)
- [openclaw/skills](https://github.com/openclaw/skills)
- [deer-flow](https://github.com/agentdesk/deer-flow)
