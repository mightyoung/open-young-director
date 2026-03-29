# AI短剧视频提示词生成器

> AI短剧视频生成 - 人物与场景提示词标准化生成流程
>
> **版本：v2.0** | 更新：2026-03-29

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    提示词生成系统 v2.0                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ 角色数据库   │    │ 场景数据库   │    │ 五维坐标系统 │   │
│  │ characters/  │    │ scenes/     │    │ 5D-Coords   │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                  │                  │           │
│         └──────────────────┼──────────────────┘           │
│                            ▼                                │
│                  ┌─────────────────┐                       │
│                  │ generate.py     │                       │
│                  │   生成器核心     │                       │
│                  └────────┬────────┘                       │
│                           │                                │
│         ┌─────────────────┼─────────────────┐             │
│         ▼                 ▼                 ▼             │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐    │
│  │ 角色提示词   │   │ 场景提示词   │   │ 组合提示词   │    │
│  │ Character   │   │ Scene       │   │ Combined    │    │
│  └─────────────┘   └─────────────┘   └─────────────┘    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 新增功能（v2.0）

- ✨ **五维坐标系统**：镜头级别精确定义（W1镜头语言/W2情绪/W3光线/W4动势/W5构图）
- ✨ **Camera Language 词库**：完整的摄影术语参考
- ✨ **古装仙侠专用场景**：8个全新场景模板（秘境洞口/宗门大殿/修炼室/古战场/水底遗迹/天劫雷云/洞府福地/幻境迷阵）
- ✨ **示例镜头文档**：`output/examples/` 目录下包含基于《穿越古代修仙》的3个完整示例

---

## 二、目录结构

```
prompts/
├── README.md              # 本文件
├── generate.py           # 主生成器
├── generate_prompts.py   # 备用生成器（简化版）
├── video-prompt-templates.md  # 完整模板参考（含Camera Language）
├── templates/            # 模板文件
│   ├── __init__.py
│   ├── character_template.md
│   └── scene_template.md
├── characters/           # 角色定义
│   ├── __init__.py
│   └── definitions.py
├── scenes/               # 场景定义
│   ├── __init__.py
│   └── definitions.py
└── output/               # 生成输出
    ├── characters/        # 角色提示词
    ├── scenes/           # 场景提示词
    └── examples/         # ✨ 新增：示例镜头
        └── 穿越古代修仙示例镜头.md
```

---

## 三、五维坐标系统（v2.0 新增）

### 坐标定义

每个镜头通过五个维度精确定义：

```
[镜头ID] W1:中景-推 W2:恐惧 W3:幽蓝 W4:静止 W5:纵深
```

| 维度 | 代码 | 说明 | 取值范围 |
|------|------|------|----------|
| W1 镜头语言 | `[景别]-[运动]` | 景别 + 摄影机运动 | 特写/中景/全景/航拍 + 固定/推/拉/摇/移/跟 |
| W2 情绪氛围 | `[情绪]` | 核心情绪基调 | 恐惧/热血/唯美/神秘/黑暗/希望/紧张/温情 |
| W3 光线色调 | `[色调]` | 光源 + 色温 | 晨曦金/暮色橙/幽蓝/暗紫/炽白/阴天灰/月光银 |
| W4 物理动势 | `[动势]` | 主体运动状态 | 静止/缓慢/爆发/飘动/坠落/颤抖 |
| W5 构图结构 | `[构图]` | 画面构成方式 | 中心/三分/对称/框架/纵深/留白/螺旋 |

### 五维 → 提示词映射示例

```python
# 示例：将五维坐标转换为提示词描述
coordinates = {
    "W1": "中景-推",      # medium shot, slow push in
    "W2": "恐惧",         # mysterious, eerie, ominous
    "W3": "幽蓝",         # cold blue bioluminescent glow
    "W4": "静止",         # static, still
    "W5": "留白"          # negative space dominating
}
```

详见：[video-prompt-templates.md - 五维坐标系统](#video-prompt-templatesmd-五维坐标系统)

---

## 四、Camera Language 词库（v2.0 新增）

完整的摄影术语参考，详见：
**[video-prompt-templates.md - Camera Language 词库](#video-prompt-templatesmd-camera-language-词库)**

包含：
- **镜头运动**：推/拉/摇/倾斜/移/跟/升降/环绕/手持/固定/航拍/POV
- **景别**：大特写/特写/中特写/中景/中远景/全景/大远景/两人镜头/群像
- **角度**：平视/仰视/俯视/鸟瞰/倾斜/过肩/主观/蚂蚁视角
- **焦点**：浅景深/深景深/跟焦/虚化/全焦
- **转场**：切/叠化/淡入淡出/划入划出/推拉转场/旋转转场
- **电影术语**：Chiaroscuro/Rim Light/Key Light/Volumetric Light/Film Grain

---

## 五、古装仙侠专用场景（v2.0 新增）

8个全新场景模板，支持仙侠/玄幻题材：

| 场景ID | 名称 | 五维坐标 | 适用情境 |
|--------|------|----------|----------|
| spirit_cave | 秘境洞口 | W1:全景-摇 W2:神秘 W3:幽蓝 W4:缓慢 W5:纵深 | 发现秘境入口 |
| sect_hall | 宗门大殿 | W1:全景-仰拍 W2:热血 W3:晨曦金 W4:静止 W5:对称 | 宗门盛典、强者登场 |
| cultivation_chamber | 修炼室 | W1:中景-固定 W2:唯美 W3:月光银 W4:缓慢 W5:框架 | 闭关修炼、顿悟 |
| ancient_battlefield | 古战场遗迹 | W1:全景-航拍 W2:黑暗 W3:暗紫 W4:静止 W3:三分 | 探查古战场 |
| underwater_ruins | 水底遗迹 | W1:中景-推 W2:神秘 W3:幽蓝 W4:飘动 W5:纵深 | 探索水下秘境 |
| tribulation_lightning | 天劫雷云 | W1:全景-仰拍 W2:恐惧 W3:炽白 W4:爆发 W5:中心 | 渡劫场景 |
| blessed_cave | 洞府福地 | W1:中景-横移 W2:唯美 W3:晨曦金 W4:缓慢 W5:框架 | 主角洞府 |
| illusion_maze | 幻境迷阵 | W1:特写-推 W2:神秘 W3:幽蓝 W4:飘动 W5:留白 | 阵法困局 |

详见：[video-prompt-templates.md - 古装仙侠专用场景](#video-prompt-templatesmd-古装仙侠专用场景)

---

## 六、生成器使用流程

### 6.1 命令行使用

```bash
# 列出所有可用角色和场景
python generate.py list

# 生成角色提示词
python generate.py character --id lin_yi --state normal
python generate.py character --id lin_yi --state awakened

# 生成场景提示词
python generate.py scene --id mine_awakening
python generate.py scene --id sect_entrance

# 生成组合提示词（角色+场景）
python generate.py combined --character lin_yi --state awakened --scene power_burst

# 保存到文件
python generate.py character --id lin_yi --state awakened --save
python generate.py scene --id sect_entrance --save
```

### 6.2 API调用

```python
from prompts import CharacterPromptGenerator, ScenePromptGenerator

# 生成角色
gen = CharacterPromptGenerator()
prompt = gen.generate("lin_yi", state="awakened")

# 生成场景
scene_gen = ScenePromptGenerator()
prompt = scene_gen.generate("mine_awakening")

# 生成组合
combined = gen.generate_combined(
    character_id="lin_yi",
    state="awakened",
    scene_id="power_burst"
)
```

### 6.3 五维坐标剧本标记示例

在剧本中用坐标标记每个镜头：

```markdown
### 镜头1：噩梦深渊
[镜头1] W1:特写-推 W2:恐惧 W3:幽蓝 W4:静止 W5:留白

| 属性 | 内容 |
|------|------|
| 镜头类型 | 大特写 |
| 动作描述 | 黑暗中，幽蓝光芒跃动，苍老声音响起 |
| 出场角色 | 林逸 |
| 情绪 | 恐惧 |
| 时长 | 5秒 |
```

---

## 七、示例镜头（v2.0 新增）

基于《穿越古代修仙》第1集剧本生成的3个完整示例：

| 示例 | 镜头 | 五维坐标 | 文件位置 |
|------|------|----------|----------|
| 示例一 | 噩梦深渊 | W1:特写-推 W2:恐惧 W3:幽蓝 W4:静止 W5:留白 | output/examples/ |
| 示例二 | 猛然惊醒 | W1:中景-推 W2:紧张 W3:阴天灰 W4:爆发 W5:中心 | output/examples/ |
| 示例三 | 晨雾送别 | W1:中景-横移 W2:温情 W3:晨曦金 W4:缓慢 W5:三分 | output/examples/ |

详见：`output/examples/穿越古代修仙示例镜头.md`

---

## 八、数据定义规范

### 8.1 角色定义规范

```python
CHARACTER_SCHEMA = {
    "id": "string",           # 唯一标识
    "name_zh": "string",      # 中文名
    "name_en": "string",      # 英文名
    "age": "number",          # 默认年龄
    "gender": "enum",         # male/female
    "height": "string",       # 身高
    "height_awakened": "string|null",  # 觉醒后身高
    "states": {
        "state_name": {
            "build": "string",
            "skin": "string",
            "hair": "string",
            "eyes": "string",
            "expression": "string",
            "special": "string",
            "attire": "string",
            "attire_details": "string",
            "lighting": "string",
            "lens": "number",
            "aperture": "string",
            "focus": "string",
            "energy": "string|null",
        }
    }
}
```

### 8.2 场景定义规范

```python
SCENE_SCHEMA = {
    "id": "string",
    "name_zh": "string",
    "name_en": "string",
    "location": "string",
    "reference": "string",
    "environment": ["string", ...],  # ≥4条
    "main_subject": "string",
    "character_action": "string",
    "lighting": ["string", ...],     # ≥4条
    "composition": "string",
    "mood": "string",
}
```

---

## 九、负面提示词标准

### 角色类负面词

```
3d render, CGI, unreal engine, video game character, avatar, doll,
plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched,
glowing eyes, glowing effect, supernatural glow, magical particles, magic aura,
anime, illustration, drawing, painting, sketch, hyperrealistic,
character reference sheet, turnaround sheet, grid layout, multiple views,
text, words, letters, signature, watermark, logo, symbols, annotations,
half body, waist up, portrait, headshot, cropped, missing limbs,
duplicates, bad anatomy, deformed, mutation, disproportionate,
cross-eyed, minor appearance, 15-year-old if older needed
```

### 场景类负面词

```
3d render, CGI, unreal engine, video game scenery, mobile game ad,
fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights,
digital fire, magic aura, bloom effect,
text, watermark, signature, logo, UI, navigation bar,
clean geometry, plastic textures, flat lighting,
perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors,
purple tint, fake mist, 2d elements
```

---

## 十、质量标准

### 10.1 角色提示词检查清单

- [ ] 年龄明确（数字，非"young"等模糊词）
- [ ] 性别明确
- [ ] 身高准确
- [ ] 体型描述清晰
- [ ] 发型发色描述
- [ ] 眼睛颜色/特征描述
- [ ] 表情/气质描述
- [ ] 服装类型/颜色/材质
- [ ] 四个角度完整
- [ ] 摄影参数正确
- [ ] 负面词覆盖完整

### 10.2 场景提示词检查清单

- [ ] 地点类型明确
- [ ] 现实参照具体
- [ ] 环境细节≥4条
- [ ] 主要元素描述清晰
- [ ] 光线氛围≥4条
- [ ] 构图方式明确
- [ ] 氛围词准确
- [ ] 负面词覆盖完整

### 10.3 五维坐标检查清单

- [ ] W1 镜头语言：景别 + 运动方式匹配
- [ ] W2 情绪氛围：与剧本情绪一致
- [ ] W3 光线色调：符合场景时间设定
- [ ] W4 物理动势：与角色动作一致
- [ ] W5 构图结构：符合叙事目的

---

*固化时间：2026-03-29 | v2.0*
