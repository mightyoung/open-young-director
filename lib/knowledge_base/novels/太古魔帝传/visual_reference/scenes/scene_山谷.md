# 场景：太虚宗外围山谷（第24章）

> **scene_id**: `v02_ch024_山谷`
> **visual_ref**: `v02_ch024_山谷.md`
> **章节**: 第24章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗外围山谷 |
| **时代** | 修真界·太虚宗 |
| **氛围** | 紧张、危急、战斗激烈 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 无（自然山谷） |
| **布置** | 乱石嶙峋，地面被战斗破坏 |
| **光线** | 天色剧变，紫绿交织 |
| **特色** | 战场废墟，山壁陡峭 |

## 出现章节

- 第24章：韩林召唤太古魔帝虚影，使用"天魔乱舞"对抗冷无心

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: mountain valley battlefield as a real geological site with ancient weathering,

environment details:
- rocky terrain with deep cracks from natural seismic activity and erosion,
- boulders scattered from ancient landslides, some covered in moss and lichen,
- mountain walls on both sides with natural stratified rock layers,

two figures battling in the center, dust and debris flying from combat,

lighting & atmosphere:
- dramatic overcast sky with purple and green light filtering through clouds,
- real atmospheric haze with dust particles visible in the air,
- natural shadows casting across the battlefield,
- no magical energy effects, dust and debris are purely physical,

composition: wide angle establishing shot showing full valley battlefield with combatants,

technical: high dynamic range, film grain, dramatic shadows, masterpiece, photorealistic textures
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
| 光线 | dramatic lighting, cinematic | 紫绿光芒交织，战斗激烈 |
| 构图 | close-up friendly | 便于后期切近景/特写 |
| 氛围 | emotional atmosphere | 场景需传递紧张危急的战斗情绪 |
| 色彩 | cinematic color grading | 紫色与绿色对比 |

### 参考形象

```
战场的荒芜、剑气的纵横、魔气的翻涌、紧张的战斗氛围、紫色与绿色的对决
风格：高度写实（hyperrealistic）
光线：紫绿交织的戏剧光线
氛围：紧张、危急、战斗激烈
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v02_hanlin | `visual_reference/characters/v02_hanlin.md` | 韩林 |
| v02_lengwuxin | `visual_reference/characters/v02_lengwuxin.md` | 冷无心 |
| v02_taixuzi | `visual_reference/characters/v02_taixuzi.md` | 太虚子 |
| v02_murongxue | `visual_reference/characters/v02_murongxue.md` | 慕容雪 |
| v02_taixuziren | `visual_reference/characters/v02_taixuziren.md` | 太虚真人 |
| v02_tianxuanzi | `visual_reference/characters/v02_tianxuanzi.md` | 天玄子 |
| v02_yechen | `visual_reference/characters/v02_yechen.md` | 叶尘 |
| v02_modi | `visual_reference/characters/v02_modi.md` | 太古魔帝 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v02_ch024_山谷"
  visual_ref: "visual_reference/scenes/v02_ch024_山谷.md"
  characters:
    - id: "v02_hanlin"
      visual_ref: "visual_reference/characters/v02_hanlin.md"
    - id: "v02_lengwuxin"
      visual_ref: "visual_reference/characters/v02_lengwuxin.md"
```
