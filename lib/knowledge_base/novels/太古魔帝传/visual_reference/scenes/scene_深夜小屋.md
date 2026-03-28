# 场景：韩林居所 - 深夜小屋（第2章）

> **scene_id**: `v01_ch002_深夜小屋`
> **visual_ref**: `v01_ch002_深夜小屋.md`
> **章节**: 第2章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗外门弟子居所·韩林住处 |
| **时代** | 修真界·太虚宗·深夜 |
| **氛围** | 神秘、紧张、战斗、命运转折 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 简陋小屋，木质结构 |
| **布置** | 窗前、简陋家具 |
| **光线** | 月光透过窗棂，室内昏暗 |
| **特色** | 逆仙诀修炼时周身萦绕淡淡黑气 |

## 出现章节

- 第2章：叶尘派人暗杀韩林
- 第2章：柳如烟深夜来访，揭示真相
- 第2章：韩林修炼逆仙诀至第二重"逆脉"境界

## 光线设计

```
深夜月光光线方案：
- 主光源：月光（冷蓝，苍白）
- 补光：屋内黑暗，只有窗外月光
- 氛围：紧张、危机四伏
```

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: small简陋小屋 as a real peasant dwelling in rural China, late night,

environment details:
- simple wooden furniture with natural wood grain and wear marks,
- walls with cracked plaster showing lath underneath,
- worn straw mats on dirt floor,
- moonlight streaming through wooden window frames casting sharp shadows,

young man in worn robes sitting cross-legged by window,

lighting & atmosphere:
- cold moonlight in blue-white tones creating strong contrast,
- deep shadows hiding details of the room,
- real dust particles visible in the moonbeam,
- no purple glow, darkness is purely physical absence of light,

composition: cinematic shot showing the isolation of the figure in the moonlit room,

technical: high dynamic range, film grain, cold color grading, masterpiece, photorealistic textures
```

### 叶尘暗杀场景提示词

```
[基础场景] +
black-clad figure crashing through window,
sword glinting in moonlight as it strikes,
young cultivator dodging with fast reflexes,

contact clash creating sparks and debris,
debris flying across the room,

dramatic combat composition,
cinematic action scene
```

### 柳如烟来访场景提示词

```
[基础场景 - no combat] +
moonlight flooding room through window,
white-robed figure stepping through window,

young man looking up with complex emotions,
two characters facing each other in the moonlight,

atmosphere: mysterious, emotional,
quiet tension between the two figures,

cinematic romantic tension
```

### 负面提示词

```
3d render, CGI, unreal engine, video game scenery, mobile game ad, fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights, digital fire, magic aura, bloom effect,
text, words, letters, watermark, signature, logo, UI, navigation bar, character names,
clean geometry, plastic textures, flat lighting, perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors, purple tint, fake mist, 2d elements
```

### 高度写实风格说明

| 元素 | 要求 | 说明 |
|------|------|------|
| 光线 | dramatic lighting, cinematic | 月光冷蓝 + 紫黑色修炼光芒对比 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递神秘、战斗、情感冲突的情绪 |
| 色彩 | cinematic color grading | 冷色调为主，紫光点缀 |

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch002_深夜小屋"
  visual_ref: "visual_reference/scenes/v01_ch002_深夜小屋.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
```
