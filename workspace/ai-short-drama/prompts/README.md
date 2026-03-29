# 人物场景提示词生成器

> AI短剧视频生成 - 人物与场景提示词标准化生成流程

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    提示词生成系统                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │ 角色数据库   │    │ 场景数据库   │    │ 模板库      │   │
│  │ characters/  │    │ scenes/     │    │ templates/  │   │
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
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐      │
│  │ 角色提示词   │   │ 场景提示词   │   │ 组合提示词   │      │
│  │ Character   │   │ Scene       │   │ Combined    │      │
│  └─────────────┘   └─────────────┘   └─────────────┘      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
prompts/
├── README.md              # 本文件
├── generate.py           # 主生成器
├── templates/            # 模板文件
│   ├── __init__.py
│   ├── character_template.md    # 角色模板
│   └── scene_template.md       # 场景模板
├── characters/           # 角色定义
│   ├── __init__.py
│   └── definitions.py    # 角色数据结构
├── scenes/              # 场景定义
│   ├── __init__.py
│   └── definitions.py    # 场景数据结构
└── output/              # 生成输出
    ├── characters/       # 角色提示词
    └── scenes/          # 场景提示词
```

---

## 三、角色模板（固定格式）

### 3.1 模板结构

```markdown
## 角色名 [角色ID]

### 基础信息
- 中文名：
- 英文名：
- 年龄：
- 性别：
- 身高：
- 体型：

### 外观特征
- 头发：
- 眼睛：
- 肤色：
- 特殊标记：

### 服装描述
- 主服装：
- 材质：
- 颜色：
- 细节：

### 表情/气质
- 默认表情：
- 气质类型：
- 能量效果：

### 四个角度定义
| 角度 | 姿势 | 说明 |
|------|------|------|
| 正面 | 站立直视 | 展示全貌 |
| 3/4侧 | 侧身30° | 展示轮廓 |
| 正侧 | 侧身90° | 展示侧面 |
| 背面 | 转身 | 展示背部 |

### 摄影参数
- 镜头：
- 光圈：
- 焦距：
- 灯光：
```

### 3.2 生成输出格式

```
35mm film photography, high ISO, grain texture, authentic RAW photo,
character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,

subject: a real [年龄]-year-old East Asian [性别] actor, [身高] height, [体型], realistic human anatomy with natural proportions, [肤色],

facial features: [头发], [眼睛] with [眼神描述], [表情], [特殊标记],

attire: [主服装], [材质], [颜色], [细节],

views (from left to right):
1. strict front view, [姿势],
2. 3/4 front view facing [方向],
3. strict profile view facing [方向],
4. full back view showing [细节],

technical details: shot on ARRI Alexa, [镜头]mm lens, f/[光圈], sharp focus on [焦点], [灯光],

background: pure seamless white paper backdrop, absolute blank background, zero digital artifacts, totally clean background

negative: [负面词]
```

---

## 四、场景模板（固定格式）

### 4.1 模板结构

```markdown
## 场景名 [场景ID]

### 基础信息
- 中文名：
- 英文名：
- 类型：
- 时代：

### 环境描述
- 地点类型：
- 现实参照：
- 建筑风格：
- 时间设定：

### 环境细节清单
1. [环境细节1]
2. [环境细节2]
3. [环境细节3]
4. [环境细节4]

### 主要元素
- 主体：
- 配角：
- 道具：

### 光线氛围
- 时间：
- 光源：
- 色调：
- 特效：

### 构图方式
- 镜头类型：
- 角度：
- 景深：
```

### 4.2 生成输出格式

```
RAW landscape photo, cinematic [镜头类型], shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: [地点类型] as a [现实参照],

environment details:
- [环境细节1],
- [环境细节2],
- [环境细节3],
- [环境细节4],

the subject: [主体描述],

the youth: [人物动作描述],

lighting & atmosphere:
- [光线描述],
- [氛围描述],
- [色调描述],
- [特效描述],
- [物理效果],

composition: [构图描述],

technical: high dynamic range, film grain, [氛围词], photorealistic textures

negative: [负面词]
```

---

## 五、生成器使用流程

### 5.1 命令行使用

```bash
# 生成角色提示词
python generate.py character --id lin_yi --state normal
python generate.py character --id lin_yi --state awakened

# 生成场景提示词
python generate.py scene --id mine_awakening
python generate.py scene --id sect_entrance

# 生成组合提示词（角色+场景）
python generate.py combined --character lin_yi --state awakened --scene power_burst

# 列出所有可用
python generate.py list
```

### 5.2 API调用

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

---

## 六、数据定义规范

### 6.1 角色定义规范

```python
# characters/definitions.py

CHARACTER_SCHEMA = {
    "id": "string",           # 唯一标识，如 "lin_yi"
    "name_zh": "string",      # 中文名
    "name_en": "string",      # 英文名
    "age": "number",          # 默认年龄
    "gender": "enum",         # male/female
    "height": "string",       # 身高，如 "175cm"
    "states": {
        "state_name": {       # 状态名，如 "normal", "awakened"
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

### 6.2 场景定义规范

```python
# scenes/definitions.py

SCENE_SCHEMA = {
    "id": "string",           # 唯一标识
    "name_zh": "string",
    "name_en": "string", 
    "location": "string",      # 地点类型
    "reference": "string",     # 现实参照
    "environment": [           # 环境细节列表
        "string",
        "string",
        "string",
        "string",
    ],
    "main_subject": "string",
    "character_action": "string",
    "lighting": [              # 光线氛围列表
        "string",
        "string",
        "string",
        "string",
        "string",
    ],
    "composition": "string",
    "mood": "string",
}
```

---

## 七、负面提示词标准

### 7.1 角色类负面词

```
3d render, CGI, unreal engine, video game character, avatar, doll,
plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched,
glowing eyes, glowing effect, supernatural glow, magical particles, magic aura,
anime, illustration, drawing, painting, sketch, hyperrealistic,
character reference sheet, turnaround sheet, grid layout, multiple views,
text, words, letters, signature, watermark, logo, symbols, annotations,
half body, waist up, portrait, headshot, cropped, missing limbs,
duplicates, bad anatomy, deformed, mutation, disproportionate,
cross-eyed, minor if adult needed, 15-year-old if older needed
```

### 7.2 场景类负面词

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

## 八、质量标准

### 8.1 角色提示词检查清单

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

### 8.2 场景提示词检查清单

- [ ] 地点类型明确
- [ ] 现实参照具体
- [ ] 环境细节≥4条
- [ ] 主要元素描述清晰
- [ ] 光线氛围≥4条
- [ ] 构图方式明确
- [ ] 氛围词准确
- [ ] 负面词覆盖完整

---

*固化时间：2026-03-29*
