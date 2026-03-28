# 场景：后山悬崖（第8章）

> **scene_id**: `v01_ch008_后山悬崖`
> **visual_ref**: `v01_ch008_后山悬崖.md`
> **章节**: 第8章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗后山悬崖 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 孤寂、豪迈、突破在即 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 无（自然悬崖） |
| **布置** | 悬崖边缘，云海翻涌 |
| **光线** | 日出/日落，光线壮丽 |
| **特色** | 一览众山小，视野开阔 |

## 出现章节

- 第8章：韩林在悬崖边突破境界，太古魔经第一重圆满

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: cliff edge on mountain peak as a real geological formation with weathered granite,

environment details:
- cliff edge with natural erosion patterns and small plants growing from cracks,
- vast sea of clouds below as real meteorological fog layer,
- ancient pine trees clinging to the rock face,
- distant mountains with natural atmospheric perspective,

young cultivator in black robes standing with arms spread,
dramatic wind causing natural fabric movement in robes,

lighting & atmosphere:
- golden sunrise light creating dramatic backlight and long shadows,
- real Tyndall effect in the mist below,
- natural atmospheric haze adding depth to distant mountains,
- no magical effects, purely physical light and weather,

composition: wide angle shot capturing the vast scale of the landscape with figure silhouetted against the sunrise,

technical: high dynamic range, film grain, warm golden color grading, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 日出光线壮丽，逆光剪影 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递突破的豪迈与孤独 |
| 色彩 | cinematic color grading | 暖色调为主，金色日出 |

### 参考形象

```
一览众山小、修炼的孤寂、云海的壮阔、突破的豪迈
风格：高度写实（hyperrealistic）
光线：日出金光
氛围：孤寂、豪迈、突破在即
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |
| v01_qingming | `visual_reference/characters/v01_qingming.md` | 青冥长老 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch008_后山悬崖"
  visual_ref: "visual_reference/scenes/v01_ch008_后山悬崖.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
```
