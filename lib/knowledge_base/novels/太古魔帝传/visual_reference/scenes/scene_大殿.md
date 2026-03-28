# 场景：太虚宗议事大殿（第29章）

> **scene_id**: `v02_ch029_大殿`
> **visual_ref**: `v02_ch029_大殿.md`
> **章节**: 第29章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗议事大殿 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 喜庆、热闹、荣耀 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 金碧辉煌的大殿 |
| **布置** | 张灯结彩，红灯笼高挂 |
| **光线** | 温暖烛光，金色装饰 |
| **特色** | 觥筹交错，笑语不断 |

## 出现章节

- 第29章：庆功宴会，韩林被封为真传弟子，与慕容雪相遇

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: grand throne hall of Tai Xu Sect as a real historical Tang Dynasty palace interior,

environment details:
- red lanterns hanging everywhere with realistic soot patina and slightly uneven surfaces,
- golden decorations as aged brass and gilded wood with natural tarnish,
- walls as weathered painted plaster with visible cracks and age marks,

crowd of celebrants in historically accurate period costumes, layered silk and brocade textures,
young man in white receiving applause from the crowd,
beautiful girl in white dress watching from the side,

lighting & atmosphere:
- warm golden candlelight from multiple sources casting realistic flickering shadows,
- natural depth of field with people at different distances,
- real dust particles visible in light beams,
- no magical glow, strictly physical candlelight interaction,

composition: cinematic wide shot showing grand hall scale with crowd,

technical: high dynamic range, film grain, warm color grading, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 温暖烛光，喜庆氛围 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递荣耀与浪漫 |
| 色彩 | cinematic color grading | 暖色调，金色红色为主 |

### 参考形象

```
灯火阑珊、觥筹交错、喜庆洋洋、荣耀时刻、才子佳人、默契无言
风格：高度写实（hyperrealistic）
光线：温暖烛光
氛围：喜庆、热闹、荣耀
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v02_hanlin | `visual_reference/characters/v02_hanlin.md` | 韩林 |
| v02_murongxue | `visual_reference/characters/v02_murongxue.md` | 慕容雪 |
| v02_taixuziren | `visual_reference/characters/v02_taixuziren.md` | 太虚真人 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v02_ch029_大殿"
  visual_ref: "visual_reference/scenes/v02_ch029_大殿.md"
  characters:
    - id: "v02_hanlin"
      visual_ref: "visual_reference/characters/v02_hanlin.md"
    - id: "v02_murongxue"
      visual_ref: "visual_reference/characters/v02_murongxue.md"
```
