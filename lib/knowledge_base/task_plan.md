# 任务计划：小说自动生成系统

> 创建时间: 2026-03-21
> 状态: ✅ 生成功能已完成（番茄上传已暂停）

## 目标

~~构建完整的自动化流程：
1. **小说生成** - 使用 KIMI 大模型自动生成小说章节~~ ✅ 已完成
2. **番茄发布** - ~~自动上传到番茄小说网作者后台~~ ❌ 已暂停（Cookie 过期）

**注意**: 用户决定暂停番茄上传功能，仅保留本地小说生成功能。

---

## 阶段一：技术调研 (已完成)

### 1.1 番茄小说网发布方式研究

| 方式 | 可行性 | 说明 |
|------|--------|------|
| 官方 API | ❌ 无公开 API | 番茄小说网未提供作者 API |
| Playwright 自动化 | ✅ 可行 | NovelStream 项目验证可行 |
| Selenium 自动化 | ⚠️ 可行 | 较老方案，需维护 |
| 直接 HTTP 请求 | ⚠️ 需逆向 | 需要解决 a_bogus token |

---

## 阶段二：已验证的 API

### 2.1 工作 API (无需特殊 token)

| API | 端点 | 状态 |
|-----|------|------|
| 用户信息 | `/api/user/info/v2` | ✅ 正常 |
| 作者信息 | `/api/author/account/info/v0/` | ✅ 正常 |
| 作者资格 | `/api/author/inset/qualification/v0` | ✅ 正常 |
| 作品详情 | `/api/author/book/book_detail/v0/` | ✅ 正常 |

### 2.2 受保护 API (需要 a_bogus token)

| API | 端点 | 状态 | 说明 |
|-----|------|------|------|
| 章节列表 | `/apgc/Writer/BookCchapterInfo/getChapterList` | ❌ 403 | 需要 a_bogus |
| 发布章节 | `/apgc/Writer/BookCchapterInfo/compileChapters` | ❌ 403 | 需要 a_bogus |
| 保存章节 | `/apgc/Writer/BookCchapterInfo/saveChapter` | ❌ 403 | 需要 a_bogus |

### 2.3 a_bogus Token 分析

**问题描述**:
- `a_bogus` 是动态生成的防爬虫 token
- 每个请求都有不同的 token
- 由页面 JavaScript 根据 URL 和参数实时生成
- 无法通过简单的 HTTP 请求复现

**捕获的 token 示例**:
```
a_bogus=O7URDHU7Qp/RCpCGmCayCJxlcZjMrPSjVPT2bTsCHNuSP1tbB5...
```

---

## 阶段三：agent-browser 自动化验证 (已完成)

### 3.1 agent-browser 工作流程验证成功

使用 `agent-browser` CLI 工具成功验证了完整的章节创建流程：

| 步骤 | 命令 | 状态 |
|------|------|------|
| 1. 导航到作品页面 | `agent-browser open /main/writer/book-info/{book_id}` | ✅ |
| 2. 点击创建章节 | `agent-browser click link[text=创建章节]` | ✅ |
| 3. 填写章节号 | `agent-browser fill ref=e3 "5"` | ✅ |
| 4. 填写标题 | `agent-browser click ref=e4` + keyboard type | ✅ |
| 5. 填写正文 | Tab 切换到正文 + keyboard type | ✅ |
| 6. 保存草稿 | `agent-browser click button[text=存草稿]` | ✅ |
| 7. 发布/存草稿箱 | 点击"下一步"选择发布方式 | ✅ |

### 3.2 章节创建页面结构

```
URL: https://fanqienovel.com/main/writer/{book_id}/publish/{chapter_id}
元素:
  - ref=e3: 章节号输入框
  - ref=e4: 章节标题输入框
  - 正文: 通过 Tab 切换后使用 keyboard type 输入
  - ref=e1: 存草稿按钮
  - ref=e2: 下一步按钮 (需要正文 ≥1000 字)
```

### 3.3 验证结果

- ✅ 页面导航正常
- ✅ 表单填写正常
- ✅ 草稿保存成功 ("已保存到云端")
- ⚠️ "下一步"需要正文至少 1000 字
- ✅ 浏览器状态已保存到 `./cookies/fanqie_browser_state.json`

---

## 阶段四：已实现功能

### 4.1 已完成功能

| 功能 | 文件 | 状态 |
|------|------|------|
| Cookie 认证 | `fanqie_publisher.py` | ✅ 完成 |
| 用户信息获取 | `fanqie_publisher.py` | ✅ 完成 |
| 作者信息获取 | `fanqie_publisher.py` | ✅ 完成 |
| 作品信息获取 | `fanqie_publisher.py` | ✅ 完成 |
| 配置管理 | `config_manager.py` | ✅ 完成 |
| KIMI 生成 | `novel_generator.py` | ✅ 完成 |
| 本地存储 | `chapter_manager.py` | ✅ 完成 |
| agent-browser 章节创建 | - | ✅ 验证通过 |

### 4.2 待实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| ~~agent-browser 自动化封装~~ | ⏸️ 已暂停 | Cookie 过期，待重新授权 |
| ~~批量上传~~ | ⏸️ 已暂停 | Cookie 过期，待重新授权 |
| 章节内容 ≥1000 字 | ✅ | KIMI 生成每章 3000+ 字 |

---

## 阶段四：解决方案

### 方案 A：Playwright 完整自动化 (推荐)

使用 Playwright 直接操作页面元素，模拟用户操作上传章节。

**优点**:
- 不需要理解 token 生成机制
- 稳定性高
- 符合番茄作家后台的使用方式

**缺点**:
- 需要页面加载时间
- 可能需要处理页面弹窗

### 方案 B：反向工程 a_bogus

分析 JavaScript 代码，找出 token 生成算法。

**优点**:
- 速度快
- 可以直接 HTTP 调用

**缺点**:
- 反爬虫机制可能随时变化
- 法律风险

### 方案 C：借助外部工具

使用 BrowserPass 等工具在 HTTP 请求层面注入 token。

---

## 测试结果

### API 测试 (2026-03-21)

```bash
# 用户信息
✅ GET /api/user/info/v2 -> 200
   用户: Young墨

# 作者信息
✅ GET /api/author/account/info/v0/ -> 200
   作者名: Young墨, 成长分: 200

# 作品详情
✅ GET /api/author/book/book_detail/v0/ -> 200
   书名: 太古魔帝传, 章节数: 0

# 章节列表
❌ POST /apgc/Writer/BookCchapterInfo/getChapterList -> 403
   错误: Forbidden (需要 a_bogus)

# 章节上传
❌ POST /apgc/Writer/BookCchapterInfo/compileChapters -> 403
   错误: Forbidden (需要 a_bogus)
```

---

## 番茄配置

| 配置项 | 值 |
|--------|-----|
| 书号 (BOOK_ID) | 7619636788579027993 |
| 卷号 (VOLUME_ID) | 7619636788579027993 |
| 上传延迟 | 5秒 |
| Cookie 数量 | 19 |

---

## 已创建的文件

```
knowledge_base/
├── agents/
│   ├── __init__.py
│   ├── config_manager.py    # ✅ 配置管理
│   ├── novel_generator.py   # ✅ 小说生成器
│   ├── chapter_manager.py   # ✅ 章节管理
│   └── fanqie_publisher.py # ⚠️ 部分完成
├── cookies/                  # ✅ Cookie 存储
│   ├── fanqie_cookies.json
│   ├── fanqie_session_storage.json
│   └── fanqie_local_storage.json
├── run_novel_generation.py  # ✅ 主入口
└── .env                     # ✅ FANQIE配置
```

---

## 下一步计划

~~1. **短期**: 使用 Playwright 完整自动化方案实现章节上传~~ ⏸️ 已暂停
~~2. **中期**: 优化上传流程，支持批量上传~~ ⏸️ 已暂停
~~3. **长期**: 探索 a_bogus 生成算法~~ ⏸️ 已暂停

**当前状态**: 仅小说生成功能可用。如需恢复上传功能：
1. 重新登录番茄作家后台获取新的 Cookies
2. 更新 `cookies/fanqie_cookies.json`
3. 重新运行上传测试

---

## 状态：✅ 小说生成功能已完成，番茄上传已暂停

用户已确认：
- ✅ 开发顺序 A (先完成生成部分)
- ✅ 已有番茄账号和作品 (书号: 7619636788579027993)
- ✅ 授权确认
- ✅ KIMI 生成功能已测试通过 (每章 3000+ 字)
- ✅ 部分 API 验证通过
- ✅ agent-browser 章节创建流程验证通过
- ⏸️ 番茄上传已暂停（Cookie 过期）

### 最新发现

通过 agent-browser 验证，发现：
1. **章节创建页面**: `https://fanqienovel.com/main/writer/{book_id}/publish/`
2. **正文输入**: 通过 Tab 键切换到正文输入框，使用 `keyboard type` 输入
3. **最低字数要求**: 正文至少 1000 字 (KIMI 生成的 3000+ 字满足要求)
4. **发布流程**: 存草稿 → 下一步 → 选择发布方式 (立即发布/存草稿箱)
