# 场景：太虚宗演武场（第31章）

> **scene_id**: `v02_ch031_竞技场`
> **visual_ref**: `v02_ch031_竞技场.md`
> **章节**: 第31章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗演武场 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 激烈、欢呼、热血 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 圆形露天竞技场 |
| **布置** | 花岗岩比武台，阶梯观众席 |
| **光线** | 白天，阳光明媚 |
| **特色** | 座无虚席，观众沸腾 |

## 出现章节

- 第31章：宗门大比，韩林使用"天魔灭世"击败叶尘

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: Tai Xu Sect martial arts arena as a real historical Tang Dynasty amphitheater,

environment details:
- circular stone fighting platform in center, weathered granite with natural erosion patterns and moss growing in cracks,
- tiered spectator seating carved from natural mountain rock, worn smooth by centuries of use,
- dust particles swirling naturally from combat impact and crowd movement,

two cultivators battling, purple energy vs green energy represented as dust clouds and debris,
one in black robes standing victorious,

massive crowd cheering, real people in period costumes filling every seat,

lighting & atmosphere:
- authentic sunny day lighting, dust filtering through sunbeams,
- real Tyndall effect visible in airborne particles,
- natural atmospheric haze with depth,
- no magical particles, no digital glow, strictly physical light and dust interaction,

composition: wide angle establishing shot showing full arena scale with crowd,

technical: high dynamic range, film grain, realistic shadows, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 阳光明媚，战斗激烈 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递热血沸腾的情绪 |
| 色彩 | cinematic color grading | 暖色调为主 |

### 参考形象

```
竞技的热血、观众的热情、胜负已分、剑气纵横、尘土飞扬、欢呼雷动
风格：高度写实（hyperrealistic）
光线：白天阳光
氛围：激烈、欢呼、热血
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v02_hanlin | `visual_reference/characters/v02_hanlin.md` | 韩林 |
| v02_yechen | `visual_reference/characters/v02_yechen.md` | 叶尘 |
| v02_taixuziren | `visual_reference/characters/v02_taixuziren.md` | 太虚真人 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v02_ch031_竞技场"
  visual_ref: "visual_reference/scenes/v02_ch031_竞技场.md"
  characters:
    - id: "v02_hanlin"
      visual_ref: "visual_reference/characters/v02_hanlin.md"
    - id: "v02_yechen"
      visual_ref: "visual_reference/characters/v02_yechen.md"
```
