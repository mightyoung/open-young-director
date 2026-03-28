# 场景：太虚宗藏经阁（第6章）

> **scene_id**: `v01_ch006_藏经阁`
> **visual_ref**: `v01_ch006_藏经阁.md`
> **章节**: 第6章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗藏经阁 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 古老、神秘、发现、转折 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 古朴建筑，木质结构 |
| **布置** | 书架林立，书架高耸至天花板 |
| **光线** | 阳光透窗，灰尘浮动 |
| **特色** | 古籍厚重，神秘气息 |

## 出现章节

- 第6章：韩林发现藏在角落的太古魔经残卷

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: ancient library interior as a real historical Tang Dynasty archive building,

environment details:
- tall wooden bookshelves reaching to ceiling with natural wood grain and age darkening,
- dusty wooden floors with worn paths between shelves,
- ancient scrolls and books with weathered covers and yellowed pages,
- dust motes visible floating in sunbeams,

young man discovering hidden text on a shelf,

lighting & atmosphere:
- warm golden sunlight streaming through tall window,
- real dust particles visible dancing in the light beams,
- natural Tyndall effect in the dusty air,
- no magical glow, purely physical light scattering,

composition: wide angle shot showing the vast scale of the library with the discoverer as a small figure,

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
| 光线 | dramatic lighting, cinematic | 光束透窗，营造神圣发现感 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递发现秘密的惊喜 |
| 色彩 | cinematic color grading | 暖色调为主，金色阳光 |

### 参考形象

```
古籍的厚重、阳光的斑驳、发现秘密的惊喜、传承的庄严
风格：高度写实（hyperrealistic）
光线：金色阳光透窗
氛围：古老、神秘、发现、转折
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |
| v01_taixuziren_v01 | `visual_reference/characters/v01_taixuziren_v01.md` | 太虚真人 |
| v01_xiaodie | `visual_reference/characters/v01_xiaodie.md` | 小蝶 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch006_藏经阁"
  visual_ref: "visual_reference/scenes/v01_ch006_藏经阁.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
```
