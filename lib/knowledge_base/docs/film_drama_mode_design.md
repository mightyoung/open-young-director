# 影视剧模式多智能体小说生成系统设计方案

> **设计灵感来源**: 借鉴 deer-flow (字节跳动) 的 Lead Agent 编排模式和 mightoung 的 AgentFactory 动态Agent管理

## 1. 背景与核心理念

### 当前问题
- 单Director模式：单一LLM同时处理情节推进、角色心理、多线叙事，容易顾此失彼
- 角色同质化：所有角色使用相同的系统prompt，缺乏个性化视角
- 叙事视角混乱：全知视角与角色视角切换生硬
- 世界观一致性问题：修仙体系的境界、功法等描述前后不一致

### 影视戏剧模式的核心思想
**"编剧分工"** vs **"全知全能"**

传统小说生成 = 全知全能导演 → 容易写成流水账
影视戏剧模式 = 专业编剧团队 → 每个角色有专属编剧，导演统筹

---

## 1.5 关键设计模式 (借鉴自 deer-flow & mightoung)

### 1.5.1 Lead Agent 编排模式 (deer-flow)

```
┌─────────────────────────────────────────────────────────────┐
│                    DECOMPOSE → DELEGATE → SYNTHESIZE          │
├─────────────────────────────────────────────────────────────┤
│  1. DECOMPOSE: 将复杂任务拆分为并行子任务                     │
│  2. DELEGATE: 使用 task 工具并行派生多个subagent             │
│  3. SYNTHESIZE: 收集结果并整合为连贯答案                     │
│                                                              │
│  ⛔ HARD CONCURRENCY LIMIT: 每轮最多 N 个 task 调用          │
│     - ≤N 个子任务: 本轮全部启动                              │
│     - >N 个子任务: 分批顺序执行 (每批 ≤N)                    │
└─────────────────────────────────────────────────────────────┘
```

**DeerFlow的关键实现**:
- `_build_subagent_section()`: 动态构建subagent系统提示
- `SubagentLimitMiddleware`: 强制限制每轮最大并发数
- 多批次执行: 超过限制时分批顺序执行

### 1.5.2 AgentFactory 模式 (mightoung)

```
AgentFactory
├── create_agent()         # 根据配置动态创建Agent
├── get_or_create_agent()  # 带缓存的获取
├── reload_agent()         # 配置热重载
└── register_subagent()   # 注册子代理

AgentConfigManager
├── load_from_database()  # 从DB加载配置
├── get_agent_config()    # 带缓存的获取
├── validate_config()     # 配置验证
└── TOOL_REGISTRY        # 工具注册表
```

### 1.5.3 Prompt模板模式 (deer-flow)

```python
SYSTEM_PROMPT_TEMPLATE = """
<role>
You are {agent_name}, an open-source super agent.
</role>

{soul}                    # Agent个性/灵魂
{memory_context}          # 记忆上下文
<thinking_style>...</thinking_style>
<clarification_system>...</clarification_system>
{skills_section}          # 可用技能
{subagent_section}       # 子代理模式
<working_directory>...</working_directory>
<response_style>...</response_style>
<citations>...</citations>
<critical_reminders>...</critical_reminders>
"""
```

### 1.5.4 Middleware链式模式 (deer-flow)

```python
中间件执行顺序 (重要!):
1. SummarizationMiddleware    # 最早 - 减少上下文
2. TodoListMiddleware         # Plan模式任务管理
3. TitleMiddleware            # 生成标题
4. MemoryMiddleware           # 队列记忆更新
5. ViewImageMiddleware        # 注入图像详情
6. DeferredToolFilterMiddleware # 隐藏延迟工具
7. SubagentLimitMiddleware    # 限制并发task调用
8. LoopDetectionMiddleware    # 检测重复循环
9. ClarificationMiddleware    # 最后 - 拦截澄清请求
```

---

## 2. 系统架构

### 2.1 角色分工

```
┌─────────────────────────────────────────────────────────────┐
│                    NOVEL_ORCHESTRATOR                        │
│                      (总指挥者)                              │
│  - 协调Director和NovelWriter                                │
│  - 管理生成流程                                               │
│  - 处理大纲验证循环                                           │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   DIRECTOR     │    │  NOVEL_WRITER │    │    OUTLINE    │
│   (导演)       │    │   (小说家)    │    │   LOADER/     │
│               │    │               │    │   ENFORCER     │
│ - 策划剧本主干 │    │ - 汇总润色    │    │               │
│ - 派生角色Agent│    │ - 优化文风    │    │ - 读取大纲    │
│ - 指挥编排     │    │ - 统一视角    │    │ - 验证内容    │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     ▲
        │                     │
        ▼                     │
┌─────────────────────────────────────────────────────────────┐
│                    SUB-AGENTS (演员)                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ 韩林    │ │ 柳如烟  │ │ 魔帝残魂 │ │ 太虚宗主 │ ...      │
│  │ (主角)  │ │ (反派)  │ │ (导师线)│ │ (配角)  │          │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│                                                              │
│  每个Sub-Agent持有:                                          │
│  - 角色背景、性格、目标                                       │
│  - 本章角色视角的经历                                        │
│  - 与其他角色的关系                                           │
│  - 角色专属语言风格                                           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 生成流程

```
CHAPTER_GENERATION_FLOW
═══════════════════════════════════════════════════════════════

STEP 1: 前置准备 (Director + OutlineLoader)
├── 1.1 加载本章预定义大纲
│       outline = OutlineLoader.load_chapter_outline(chapter_num)
├── 1.2 加载前一章状态 (用于连续性)
│       prev_chapter_state = memory.get_recent_chapters(2)
└── 1.3 策划本章剧本主干
        plot_outline = Director.create_plot_outline(outline, prev_state)
        ├── 场景设定 (Scene Setting)
        ├── 主线推进 (Main Plot Progression)
        ├── 张力点 (Tension Points)
        └── 悬念埋设 (Cliffhangers)

STEP 2: 角色分工 (Director spawns Sub-Agents)
├── 2.1 确定本章出场角色
│       characters = Director.determine_cast(plot_outline, outline)
├── 2.2 为每个角色生成角色手册 (Character Bible)
│       for char in characters:
│           char_bible = Director.create_character_bible(char, chapter_context)
├── 2.3 派生角色Agent
│       for char in characters:
│           agent = SubAgentPool.spawn(char.name, char_bible)
└── 2.4 注入世界观上下文
        WorldContext = {
            "realm_system": "炼气→筑基→金丹→...",
            "sect_hierarchy": {...},
            "key_rules": ["不能跨境界战斗", "灵根决定资质", ...]
        }

STEP 3: 角色演绎 (Sub-Agents improvise)
├── 3.1 Director向各角色Agent发送场景任务
│       task = "韩林在测灵大典上被判定为伪灵根时的反应"
├── 3.2 各角色Agent基于角色视角演绎
│       response = agent.act(task)  # 返回角色视角内容
├── 3.3 Director收集并评估各角色反应
│       char_outputs = Director.collect_responses(agents)
└── 3.4 Director编排整合 (Director's Assembly)
        integrated_plot = Director.assemble_scene(char_outputs)

STEP 4: 小说化 (NovelWriter)
├── 4.1 NovelWriter接收整合后的情节骨架
│       raw_content = integrated_plot
├── 4.2 小说家进行文学化处理
│       novelized = NovelWriter.novelize(raw_content)
│       ├── 视角统一 (统一为第三人称限知视角)
│       ├── 场景描写 (环境、氛围)
│       ├── 心理描写 (角色内心活动)
│       ├── 文字润色 (修仙小说文风)
│       └── 过渡衔接 (章节之间)
└── 4.3 输出完整章节初稿
        chapter_draft = novelized

STEP 5: 验证循环 (OutlineEnforcer)
├── 5.1 验证章节内容
│       report = OutlineEnforcer.enforce(chapter_num, chapter_draft, ...)
├── 5.2 判断验证结果
│       if not report.passed:
│           ├── 分析问题类型
│           ├── if 问题在大纲设计:
│           │       → 大纲修改建议
│           └── elif 问题在生成质量:
│                   → 针对性重写
└── 5.3 循环直到通过或达到最大重写次数

STEP 6: 定稿
├── 6.1 最终润色
└── 6.2 保存到章节文件
```

---

## 3. 核心组件设计 (融合项目模式)

### 3.0 基础架构 (融合 deer-flow + mightoung)

```python
class NovelOrchestrator:
    """
    小说生成总指挥 - 融合 deer-flow Lead Agent 模式

    职责:
    1. 管理生成流程状态
    2. 协调 Director 和 NovelWriter
    3. 处理大纲验证循环
    4. 管理章节上下文
    """

    # 最大并发子代理限制 (借鉴 deer-flow SubagentLimitMiddleware)
    MAX_CONCURRENT_SUBAGENTS = 3

    def __init__(self, outline_loader, outline_enforcer, llm_client):
        self.outline_loader = outline_loader
        self.outline_enforcer = outline_enforcer
        self.llm_client = llm_client

        # 子代理池 (借鉴 mightoung AgentFactory)
        self._subagent_pool: Dict[str, CharacterSubAgent] = {}

        # 章节上下文
        self._chapter_context: Optional[ChapterContext] = None

        # 中间件链 (借鉴 deer-flow MiddlewareChain)
        self._middleware_chain: List[Middleware] = []

    def generate_chapter(self, chapter_number: int) -> str:
        """主生成流程"""
        # Step 1-6 见下方流程
        ...
```

### 3.1 Director Agent (场景导演)

```python
class DirectorAgent:
    """
    导演Agent - 核心协调者 (融合 deer-flow Lead Agent 模式)

    借鉴 deer-flow 的关键设计:
    1. DECOMPOSE → DELEGATE → SYNTHESIZE 流程
    2. 最大并发限制 (MAX_CONCURRENT_SUBAGENTS)
    3. 多批次执行 (>N个子任务时分批)
    4. Prompt模板化 (role, soul, memory, skills)
    """

    # 最大并发子代理限制 (借鉴 deer-flow)
    MAX_CONCURRENT_SUBAGENTS = 3

    def create_plot_outline(self, chapter_outline, prev_state):
        """创建本章剧本主干

        输出:
        {
            "scene_setting": "太虚宗测灵大典现场",
            "main_plot": [
                {"beat": "开场", "content": "韩林紧张等待灵根判定"},
                {"beat": "冲突", "content": "判定结果宣布：伪灵根"},
                {"beat": "转折", "content": "柳如烟当场退婚"},
                ...
            ],
            "tension_points": ["韩林的屈辱感", "柳如烟的嘲讽", "..."],
            "suspense": "梦中魔帝残魂初现，暗示韩林身世不凡"
        }
        """

    def determine_cast(self, plot_outline, chapter_outline):
        """确定本章出场角色

        规则:
        - 主要角色：在大纲中有明确戏份
        - 次要角色：根据场景需要
        - 群演：泛化处理
        """

    def create_character_bible(self, character, chapter_context):
        """为角色创建角色手册 (借鉴 mightoung AgentConfigManager)

        包含:
        - 基础信息：姓名、身份、境界
        - 性格特点：性格关键词、说话风格
        - 本章目标：该角色本章想要达成什么
        - 本章经历：该角色在本章中的关键事件
        - 关系网络：与其他角色的关系
        - 专属视角：该角色观察世界的方式
        """

    def orchestrate_characters(self, cast: List[CharacterBible], scene: PlotBeat) -> Dict[str, str]:
        """
        编排角色演绎 (核心方法 - 融合 deer-flow 编排模式)

        流程:
        1. DECOMPOSE: 将场景拆分为各角色的子任务
        2. DELEGATE: 并行派生角色Agent执行
        3. SYNTHESIZE: 整合各角色输出

        借鉴 deer-flow:
        - 计数子任务: "I have N sub-tasks"
        - 计划批次: if N > MAX, 分批执行
        - 严格限制每轮最多 MAX 个 task 调用
        """
        sub_tasks = []
        for char in cast:
            if char.should_participate_in(scene):
                sub_tasks.append({
                    "character": char.name,
                    "task": self._create_character_task(char, scene)
                })

        # 多批次执行 (借鉴 deer-flow 多批次模式)
        results = {}
        for i in range(0, len(sub_tasks), self.MAX_CONCURRENT_SUBAGENTS):
            batch = sub_tasks[i:i + self.MAX_CONCURRENT_SUBAGENTS]
            batch_results = self._execute_batch_parallel(batch)
            results.update(batch_results)

        return results

    def _execute_batch_parallel(self, batch: List[Dict]) -> Dict[str, str]:
        """并行执行一批子任务 (asyncio.gather)"""
        responses = await asyncio.gather(
            *[self._call_character_agent(task["character"], task["task"])
              for task in batch]
        )
        return dict(zip([t["character"] for t in batch], responses))

    def _create_character_task(self, char: CharacterBible, scene: PlotBeat) -> str:
        """创建角色任务描述"""
        return f"""场景: {scene.description}
角色: {char.name}
目标: {char.objective_this_chapter}
关键事件: {', '.join(char.key_moments_this_chapter)}

请以{char.name}的视角描述这个场景。"""
```

### 3.1.1 并行执行策略 (关键优化)

```python
class ParallelExecutor:
    """
    并行执行器 - 最大化并发效率

    借鉴 deer-flow 的多批次执行模式
    """

    @staticmethod
    async def execute_parallel(tasks: List[Task], max_concurrent: int = 3) -> List[Result]:
        """
        并行执行任务 (有界并发)

        Args:
            tasks: 任务列表
            max_concurrent: 最大并发数 (Semaphore限制)

        流程:
        1. 创建 Semaphore 限制并发数
        2. 为每个任务创建 asyncio.Task
        3. asyncio.gather 等待所有任务完成
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_task(task):
            async with semaphore:
                return await task.execute()

        # 并发执行所有任务
        return await asyncio.gather(*[bounded_task(t) for t in tasks])

    @staticmethod
    async def execute_batches(tasks: List[Task], batch_size: int = 3) -> List[Result]:
        """
        分批并行执行 (当任务数 > batch_size 时)

        借鉴 deer-flow 的多批次执行:
        - Turn 1: 执行第一批 (batch_size个)
        - Turn 2: 执行下一批
        - ...
        - Final: 汇总所有结果
        """
        results = []
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            batch_results = await ParallelExecutor.execute_parallel(batch, max_concurrent=batch_size)
            results.extend(batch_results)
        return results
```

**可并行化的任务**:
1. **角色演绎** - 同一场景中多个角色同时演绎
2. **场景生成** - 不同场景的初始描写可以并行
3. **大纲验证** - 多个验证项可以并行检查

**必须串行的任务**:
1. **整合** - 必须等所有角色演绎完成后
2. **小说化** - 必须等整合完成后
3. **验证** - 必须等小说化完成后

    def send_scene_task(self, agent, scene_description):
        """向角色Agent发送场景任务

        Prompt模板:
        '''
        你正在演绎角色【{char_name}】。
        角色背景：{char_background}
        本章目标：{char_objective}
        当前场景：{scene_description}

        请以{char_name}的视角描述这个场景。
        关注：{char_name}看到了什么、感受到了什么、如何反应。
        '''
        """

    def assemble_scene(self, char_outputs):
        """整合各角色输出为统一情节骨架

        输出: {
            "narration": "全场景的客观描述(导演视角)",
            "character_moments": {
                "韩林": "韩林的内心独白和反应",
                "柳如烟": "柳如烟的内心独白和反应",
                ...
            },
            "scene_transitions": "场景过渡描述"
        }
        """
```

### 3.2 NovelWriter Agent

```python
class NovelWriterAgent:
    """小说家Agent - 文学化处理"""

    def novelize(self, director_output):
        """将导演的骨架转化为完整小说章节

        处理步骤:
        1. 确定叙事视角 (推荐: 第三人称限知视角)
        2. 添加场景描写
        3. 融入角色心理
        4. 统一文字风格
        5. 确保悬念连贯
        """

    def unify_viewpoint(self, content, main_viewpoint_char):
        """统一为限知视角

        规则:
        - 以main_viewpoint_char的眼睛看世界
        - 其他角色的心理只能通过外在表现推测
        - 保持悬念：不完全揭示所有信息
        """

    def add_scene_description(self, content, scene_type):
        """根据场景类型添加环境描写

        scene_types:
        - 测灵大典: 庄严、肃穆、人声鼎沸
        - 深山老林: 幽静、神秘、灵气充沛
        - 魔界裂缝: 阴森、危险、魔气弥漫
        """

    def polish_prose(self, content):
        """修仙小说文风润色

        特点:
        - 古风与现代结合
        - 修士专用词汇 (灵根、筑基、丹田等)
        - 战斗描写注重招式和心理
        - 情感描写含蓄而深沉
        """
```

### 3.3 Sub-Agent (角色演员)

```python
class CharacterSubAgent:
    """角色Agent - 演员"""

    # 角色专属系统Prompt模板
    SYSTEM_PROMPT = """你正在演绎修仙小说《{book_title}》中的角色【{char_name}】。

    角色基础信息:
    - 姓名: {char_name}
    - 身份: {char_identity}
    - 境界: {char_realm}
    - 性格: {char_personality}
    - 说话风格: {char_speaking_style}

    角色背景故事:
    {char_backstory}

    本章目标:
    {char_objective_in_chapter}

    与其他角色的关系:
    {char_relationships}

    演绎要求:
    1. 始终以{char_name}的视角回应
    2. 体现角色的独特性格和说话方式
    3. 关注角色的内心感受和外在表现
    4. 不超出角色当前境界的知识和认知
    """

    def act(self, scene_task):
        """执行场景演绎

        输入: 场景描述
        输出: 角色视角的描写

        示例:
        Input: "韩林在测灵大典上被判定为伪灵根"
        Output: "那一刻，我觉得整个世界都崩塌了。伪灵根...竟然是我..."

        Input: "柳如烟看着韩林的判定结果"
        Output: "哼，果然是废物一个。这样的男人，也配娶我？..."
        """
```

### 3.4 Sub-Agent Pool

```python
class SubAgentPool:
    """角色Agent池 - 管理生命周期"""

    def __init__(self, max_concurrent=5):
        self.agents = {}
        self.max_concurrent = max_concurrent

    def spawn(self, character_name, character_bible):
        """为角色派生专属Agent"""
        agent = CharacterSubAgent(
            name=character_name,
            system_prompt=CharacterSubAgent.SYSTEM_PROMPT.format(
                book_title="太古魔帝传",
                char_name=character_name,
                **character_bible
            )
        )
        self.agents[character_name] = agent
        return agent

    def release(self, character_name):
        """释放Agent资源"""
        if character_name in self.agents:
            del self.agents[character_name]

    def collect_responses(self, scene_task):
        """并发收集所有角色的响应"""
        # 使用asyncio或线程池并发执行
        responses = await asyncio.gather(
            *[agent.act(scene_task) for agent in self.agents.values()]
        )
        return dict(zip(self.agents.keys(), responses))
```

---

## 4. 数据结构

### 4.1 PlotOutline (剧本主干)

```python
@dataclass
class PlotOutline:
    chapter: int
    scene_setting: str  # 场景设定

    # 剧本节拍
    beats: List[PlotBeat]  # [
    #     Beat(type="开场", description="...", expected_chars=["韩林"]),
    #     Beat(type="发展", description="...", expected_chars=["韩林", "柳如烟"]),
    #     ...
    # ]

    # 张力点
    tension_points: List[str]

    # 悬念钩子
    suspense: str  # 本章结尾悬念

    # 关键事件 (来自大纲)
    key_events: List[str]

    # 世界观上下文
    world_context: WorldContext

    def to_prompt(self) -> str:
        """转化为导演Prompt"""
        ...
```

### 4.2 CharacterBible (角色手册)

```python
@dataclass
class CharacterBible:
    name: str
    identity: str
    realm: str

    # 性格与风格
    personality: str  # "内向但倔强，城府深"
    speaking_style: str  # "简洁有力，偶带嘲讽"

    # 背景
    backstory: str

    # 本章相关
    objective_this_chapter: str
    key_moments_this_chapter: List[str]

    # 关系
    relationships: Dict[str, str]  # {"柳如烟": "退婚对象，厌恶", "魔帝残魂": "梦中导师"}

    def to_subagent_system_prompt(self) -> str:
        ...
```

### 4.3 ChapterContext (章节上下文)

```python
@dataclass
class ChapterContext:
    """贯穿整个生成流程的上下文"""

    chapter: int
    outline: ChapterOutlineData
    plot_outline: PlotOutline

    # 角色
    cast: List[CharacterBible]
    sub_agents: Dict[str, SubAgent]

    # 场景输出
    scene_outputs: Dict[str, str]  # {char_name: output}

    # 整合输出
    assembled_plot: AssembledPlot

    # 最终输出
    draft: str
    verification_report: VerificationReport

    # 前一章状态 (用于连续性)
    prev_chapter_state: Optional[PrevChapterState]
```

---

## 5. Prompt工程

### 5.1 Director系统Prompt

```
# 角色定义
你是一部修仙小说《太古魔帝传》的导演。你的职责是：
1. 解读本章大纲要求
2. 设计场景和节拍
3. 指挥多个角色Agent的演绎
4. 整合各角色输出为统一情节

# 核心能力
- 理解修仙小说的叙事节奏
- 把握角色心理和关系
- 合理分配场景节拍
- 埋设悬念和呼应

# 输出格式
每当你接到生成任务时，按以下格式输出：

【场景规划】
<场景设定>
<节拍列表>

【角色分工】
<各角色任务>

【统编指导】
<如何整合角色输出>
```

### 5.2 NovelWriter系统Prompt

```
# 角色定义
你是修仙小说《太古魔帝传》的小说家。你的职责是：
1. 将导演的情节骨架转化为文学性强的正文
2. 统一文字风格和叙事视角
3. 添加场景描写和心理描写
4. 确保文字流畅优美

# 文字风格
- 古风与现代结合，典雅而流畅
- 修仙术语准确运用 (灵根、筑基、丹田、元婴等)
- 战斗描写：招式 + 心理 + 结果
- 情感描写：含蓄深沉，避免直白

# 叙事视角
推荐使用第三人称限知视角，以主角韩林的视角为主线

# 输出格式
直接输出小说正文，不需要额外格式
```

### 5.3 角色Agent系统Prompt (示例：韩林)

```
你正在演绎修仙小说《太古魔帝传》的男主角【韩林】。

# 角色基础信息
- 姓名: 韩林
- 身份: 太虚宗外门弟子 (测灵前) → 伪灵根废物 (测灵后)
- 性格: 外表沉默寡言，内心倔强坚韧，城府深
- 说话风格: 简洁有力，很少废话，情绪激动时言语锋利

# 角色背景
韩林出身寒微，父母早亡，被太虚宗长老偶然发现带入宗门。
测灵大典之前，他以为自己能改变命运，却因伪灵根被判定为废物。
柳如烟的退婚是他人生的奇耻大辱，但也激发了他内心深处的傲骨。
在最低谷的时刻，他开始频繁做奇怪的梦...

# 本章目标
测灵大典上，韩林的目标是：
1. 正常完成测灵仪式
2. 面对判定结果 (虽然他不知道会是伪灵根)
3. 应对柳如烟的退婚

# 与其他角色的关系
- 柳如烟：曾有婚约，现在是被退婚的对象，充满屈辱和愤怒
- 太虚宗长老：引他入宗的贵人，他心怀感激
- 魔帝残魂：梦中出现的神秘存在，给他暗示

# 演绎要求
1. 以韩林的第一人称视角回应场景
2. 体现他沉默外表下的内心波涛
3. 展现他面对屈辱时的复杂情绪
4. 不说超出他认知的话

# 当前场景
{scene_description}

请以韩林的视角描述这个场景，重点关注他的内心感受。
```

---

## 6. 验证与反馈循环

### 6.1 三层验证

```
┌─────────────────────────────────────────────────────────────┐
│                    三层验证机制                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 1: 大纲验证 (OutlineEnforcer)                        │
│  ─────────────────────────────────────────                  │
│  检查:                                                       │
│  ✓ 关键事件是否覆盖                                          │
│  ✓ 境界描述是否一致                                          │
│  ✓ 悬念是否埋设                                             │
│  ✓ 角色状态是否合理                                         │
│                                                              │
│  → 失败 → 触发rewrite循环                                   │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 2: 世界观一致性验证                                   │
│  ─────────────────────────────────────────                  │
│  检查:                                                       │
│  ✓ 修仙术语使用是否准确                                      │
│  ✓ 境界体系是否自洽                                         │
│  ✓ 功法、技能描述是否一致                                    │
│  ✓ 地理、宗门设置是否连贯                                    │
│                                                              │
│  → 失败 → 针对性修正                                        │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 3: 文学质量验证                                       │
│  ─────────────────────────────────────────                  │
│  检查:                                                       │
│  ✓ 文字流畅度                                               │
│  ✓ 场景描写质量                                             │
│  ✓ 人物塑造立体度                                           │
│  ✓ 情感感染力                                               │
│                                                              │
│  → 失败 → NovelWriter重润色                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 大纲修改判定

当OutlineEnforcer验证失败时，需要判断是**生成问题**还是**大纲问题**：

```python
def evaluate_failure(report: VerificationReport) -> str:
    """判断失败原因"""

    # 类型1: 生成遗漏
    # - 事件有覆盖但表达不充分 → 重写
    # - 角色行为OOC → 重写

    # 类型2: 大纲问题
    # - 事件在逻辑上无法在同一场景发生 → 大纲修改
    # - 两个关键事件冲突 → 大纲修改
    # - 境界递进不合理 → 大纲修改

    if is大纲问题(report):
        return "MODIFY_OUTLINE"
    else:
        return "REGENERATE"
```

---

## 7. 实施计划

### Phase 1: 核心架构 (1-2天)
- [ ] 创建DirectorAgent类
- [ ] 创建NovelWriterAgent类
- [ ] 创建CharacterSubAgent基类
- [ ] 创建SubAgentPool管理类

### Phase 2: 流程集成 (1天)
- [ ] 修改novel_generator.py接入新流程
- [ ] 实现STEP 1-6的完整流程
- [ ] 添加流程状态管理

### Phase 3: Prompt优化 (1天)
- [ ] 编写各角色Agent的系统Prompt模板
- [ ] 优化Director的场景分解能力
- [ ] 优化NovelWriter的文学化能力

### Phase 4: 验证循环 (1天)
- [ ] 实现三层验证机制
- [ ] 实现大纲修改判定逻辑
- [ ] 实现自动rewrite循环

### Phase 5: 测试与调优 (2天)
- [ ] 生成测试章节
- [ ] 人工评估质量
- [ ] 根据反馈迭代优化

---

## 8. 与原系统的对比

| 维度 | 原系统 (单Director) | 新系统 (影视戏剧模式) |
|------|-------------------|---------------------|
| 叙事视角 | 混乱，全知视角 | 限知视角，主角为核心 |
| 角色塑造 | 同质化 | 个性化，有专属视角 |
| 情节编排 | 单一Agent决策 | 多Agent协作 |
| 世界观一致性 | 难以保证 | 角色视角互相印证 |
| 生成质量 | 流水账风险 | 专业分工，互为补充 |
| 计算成本 | 较低 | 较高 (多Agent) |
| 调试复杂度 | 较低 | 较高 |

---

## 9. 建议的过渡策略

考虑到实现的复杂性，建议分阶段实施：

### 阶段A: 最小可行版本
- 保留现有单Director模式作为fallback
- 只对关键章节 (如ch001, ch010, ch020) 使用新模式
- 逐步积累角色Prompt和场景模板

### 阶段B: 扩展应用
- 对所有章节应用新模式
- 完善角色库和场景库
- 优化Agent协作效率

### 阶段C: 高级特性
- 引入角色成长记忆
- 实现跨章节剧情呼应
- 添加自动Prompt优化
