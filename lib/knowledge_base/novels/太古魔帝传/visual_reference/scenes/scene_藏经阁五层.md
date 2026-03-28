# 场景：藏经阁第五层（第12章）

> **scene_id**: `v01_ch012_藏经阁五层`
> **visual_ref**: `v01_ch012_藏经阁五层.md`
> **章节**: 第12章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗藏经阁第五层 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 神圣、禁忌、发现真相 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 神秘空间，符文密布 |
| **布置** | 古老禁制，符文墙壁 |
| **光线** | 神秘光芒，金紫交织 |
| **特色** | 只有历代掌门才能进入 |

## 出现章节

- 第12章：韩林发现父亲留下的太古魔经完整传承，以及天玄子的秘密

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: mysterious chamber in ancient library as a real underground vault with ancient stonework,

environment details:
- walls covered in ancient carved symbols with gold leaf inlay still catching torch light,
- stone ceiling with natural moisture and moss,
- ancient wooden altar with carved edges,
- dust particles visible in the dim light,

young man discovering ancient secret scrolls,
elderly master standing beside him,

lighting & atmosphere:
- golden light from torches creating warm shadows,
- purple tones from deep shadows and aged stone,
- natural moisture in the air creating slight haze,
- gold inlay reflecting torch light physically, not glowing,
- no magical runes, ancient symbols are carved and inlaid with metal,

composition: cinematic shot showing the secret chamber with discoverer,

technical: high dynamic range, film grain, warm torchlight color grading, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 金紫光芒交织，神圣与神秘 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递发现真相的震撼 |
| 色彩 | cinematic color grading | 金色与紫色交织 |

### 参考形象

```
禁忌的神圣、符文的奥秘、真相的揭露、先祖的庇护
风格：高度写实（hyperrealistic）
光线：金紫交织的神秘光芒
氛围：神圣、禁忌、发现真相
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |
| v01_taixuzi_v01 | `visual_reference/characters/v01_taixuzi_v01.md` | 太虚子 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch012_藏经阁五层"
  visual_ref: "visual_reference/scenes/v01_ch012_藏经阁五层.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
    - id: "v01_taixuzi_v01"
      visual_ref: "visual_reference/characters/v01_taixuzi_v01.md"
```
