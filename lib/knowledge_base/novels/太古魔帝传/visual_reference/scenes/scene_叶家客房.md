# 场景：叶家客房（第32章）

> **scene_id**: `v02_ch032_叶家客房`
> **visual_ref**: `v02_ch032_叶家客房.md`
> **章节**: 第32章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 叶家客房 |
| **时代** | 修真界·叶家 |
| **氛围** | 阴森、恐怖、死亡 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 简洁客房 |
| **布置** | 简单家具，窗户透光 |
| **光线** | 深夜，月光苍白，烛光摇曳 |
| **特色** | 鬼冥宗刺客潜入 |

## 出现章节

- 第32章：叶尘被鬼冥宗灭口，在恐惧中死去

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: guest room in Ye family estate as a real historical Chinese bedroom,

environment details:
- simple wooden furniture with dark lacquer showing age,
- moonlight streaming through window casting blue-white light,
- candlelight creating warm orange tones,

bandaged young man lying in bed with terrified expression,
dark shadow figure standing in doorway partially illuminated by moonlight,

lighting & atmosphere:
- cold blue moonlight from window contrasting with warm flickering candlelight,
- deep shadows creating natural horror atmosphere,
- real dust particles visible in the light beams,
- no ghostly flames, darkness is purely physical absence of light,

composition: cinematic horror shot showing the terrified figure with shadow figure looming in doorway,

technical: high dynamic range, film grain, high contrast lighting, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 冷月光与摇曳烛光对比，阴森 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递恐怖与死亡的情绪 |
| 色彩 | cinematic color grading | 冷色调为主，幽绿点缀 |

### 参考形象

```
深夜的寂静、烛光的摇曳、月光的苍白、恐惧的眼神、鬼火的幽绿、死亡的降临
风格：高度写实（hyperrealistic）
光线：深夜冷月光
氛围：阴森、恐怖、死亡
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v02_yechen | `visual_reference/characters/v02_yechen.md` | 叶尘 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v02_ch032_叶家客房"
  visual_ref: "visual_reference/scenes/v02_ch032_叶家客房.md"
  characters:
    - id: "v02_yechen"
      visual_ref: "visual_reference/characters/v02_yechen.md"
```
