# 场景：藏书阁密室 - 玉佩觉醒（第1章）

> **scene_id**: `v01_ch001_藏书阁密室`
> **visual_ref**: `v01_ch001_藏书阁密室.md`
> **章节**: 第1章结尾
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗藏书阁最底层密室 |
| **时代** | 修真界·太虚宗·深夜 |
| **氛围** | 神秘、命运转折、传承开启 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **位置** | 隐藏在"杂记"类书架之后，需特定法诀开启 |
| **密室** | 不大，石桌一张，长明灯一盏 |
| **墙壁** | 四面刻满密密麻麻刻痕（韩天啸生前调查记录） |
| **石桌** | 中央摆放父亲遗物：漆黑古朴玉佩 |
| **光线** | 昏黄长明灯，暮色四合时最后一缕阳光从透气孔射入 |
| **特色** | 玉佩核心隐约可见黑芒流转，与掌心疤痕呼应 |

## 修真美学设计

| 元素 | 设计 |
|------|------|
| 密室入口 | 暗门隐藏在书架后，需法诀开启 |
| 长明灯 | 昏黄光晕，照亮石桌 |
| 墙壁刻痕 | 韩天啸留下的调查线索 |
| 玉佩 | 通体漆黑，入手冰凉，云纹中央月牙形凹槽 |

## 出现章节

- 第1章结尾：韩林滴血入玉佩，觉醒逆仙传承
- 第2章：逆仙意识出现，传授《逆仙录》

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: hidden secret chamber as a real underground stone room,

environment details:
- ancient stone room, simple and austere,
- one stone table at center with ancient bronze oil lamp with dim yellow flame,
- four walls covered in密密麻麻 carved marks and notes, worn by time,
- tall bookshelf hidden entrance behind,

young man in worn robes sitting cross-legged,
holding pitch-black jade pendant with natural crystalline inclusions catching lamplight,
palm shows crescent-shaped scar,

cold moonlight from small ceiling vent creating sharp diagonal light beams,

lighting & atmosphere:
- warm yellow lamplight contrasting with cool blue moonlight,
- real dust particles visible in the light beams,
- natural shadow play across the carved walls,
- jade pendant reflects light physically, no magical glow,

composition: cinematic shot showing the discoverer in the secret chamber illuminated by lamplight and moonlight,

technical: high dynamic range, film grain, dramatic contrast lighting, masterpiece, photorealistic textures
```

### 玉佩觉醒时刻提示词

```
[基础场景] +
close-up on ancient jade pendant,
pitch-black surface with natural crystalline inclusions,
reflections of lamplight on polished obsidian surface,

palm scar connecting to jade with visible light interaction,
young man's face illuminated by reflected lamplight,

energy represented as dust swirling in the air from the disturbance,

dramatic cinematic moment,
emotional intensity, fate changing
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
| 光线 | dramatic lighting, cinematic | 昏黄长明灯 + 紫黑色玉佩光芒对比 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递命运转折的情绪 |
| 色彩 | cinematic color grading | 冷色调为主，紫色点缀 |

### 参考形象

```
深夜藏书阁密室，昏黄长明灯下，
少年盘坐于石桌前，手托正在龟裂的古朴玉佩。
紫黑色光芒从裂缝中透出，照亮少年坚毅的面容。
墙壁刻痕密密麻麻，记录着父亲的调查。
风格：高度写实（hyperrealistic）
光线：长明灯昏黄 + 玉佩紫黑光芒
氛围：神秘、命运转折、传承开启
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch001_藏书阁密室"
  visual_ref: "visual_reference/scenes/v01_ch001_藏书阁密室.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
```
