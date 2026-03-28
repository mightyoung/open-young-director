# 场景：柳家大厅 - 退婚大典（第3章）

> **scene_id**: `v01_ch003_柳家大厅`
> **visual_ref**: `v01_ch003_柳家大厅.md`
> **章节**: 第3章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 柳家府邸·正厅 |
| **时代** | 修真界·柳家 |
| **氛围** | 紧张、屈辱、悲壮、命运转折、三年之约 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 三十六根盘龙玉柱撑起穹顶 |
| **地面** | 温玉砖，价值数万灵石 |
| **照明** | 夜明珠将大厅照得如白昼 |
| **布置** | 两侧长老席列阵，宾客席后方约三十人 |
| **光线** | 雷暴天，阴沉天光，闪电间隙照亮殿门 |
| **特色** | 殿外雷云翻涌，压抑氛围 |

## 修真美学设计

| 元素 | 原世俗设计 | 修真化设计 |
|------|-----------|-----------|
| 支柱 | 金色灯笼 | 盘龙玉柱，符文流转微光 |
| 地面 | 红毯 | 温玉砖，阵法纹路 |
| 照明 | 红灯笼 | 夜明珠 + 灵石微光 |
| 装饰 | 俗艳金色 | 银蓝符纹，道韵色彩 |

## 空间布局

```
柳家议事大殿空间布局：
- 纵深：约15米
- 玉阶：九级，每级高约20cm
- 韩林位置：殿中央，距大门8米
- 柳如烟位置：玉阶之上，族徽阵图前
- 长老席：两侧各5席
- 宾客席：后方，约30人
- 叶尘位置：右侧首位贵客席
- 柳如海位置：主位正中
```

## 出现章节

- 第3章：退婚大典，韩林立下"三年之约"誓言

## 光线设计（雷暴天光线方案）

```
雷暴天光线方案：
- 主光源：阴沉天光（冷灰蓝，5500K以下）
- 戏剧光源：闪电瞬间的冷白爆裂光（10000K+，硬光）
- 环境补光：室内灵石/法器微光（冷青，神秘感）
- 情绪：压抑→爆发（闪电时）
```

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW photo, cinematic, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: Liu family ancestral hall as a real historical Tang Dynasty throne room,

environment details:
- 36 jade pillars with coiling dragon carvings, weathered stone bases with natural moss,
- floor made of polished warm jade tiles with visible natural veining and slight wear patterns,
- pearl lights illuminating hall naturally, not glowing but reflecting ambient light,

stormy overcast daylight filtering through entrance, purple-gold lightning flash casting dramatic shadows,

grand ceremony atmosphere, hundreds of people in historically accurate period costumes watching,

center of hall:
young man in worn white cotton robes standing alone,
back straight like a sword, facing elevated platform,
expression: calm defiance, eyes showing inner fire,

on platform:
beautiful girl in flowing ice-blue cloud silk dress,
forehead mark is a subtle golden religious pattern visible in certain lighting angles,
cold expression hiding complex emotions,

low camera angle looking up at young man,
dramatic rim lighting from lightning flash,
cinematic composition, emotional tension,

lighting & atmosphere:
- authentic storm lighting, sun blocked by dark clouds outside,
- cool blue ambient light mixing with warm interior lighting,
- natural atmospheric haze inside the hall,
- no magical glow, no digital effects, strictly physical light interaction,

technical: high dynamic range, film grain, realistic shadows, masterpiece, photorealistic textures
```

### 三年之约时刻提示词

```
[基础场景] +
young man tearing退婚书 in two,
paper scraps falling like snow,
his voice rising with determination,

"三年后的今日，太虚宗'升仙大会'，我会亲自上门，正式解除婚约！",

standing alone in hall center,
back straight, head raised,
facing all the contemptuous stares,

dramatic wind from opening door,
storm light casting dramatic shadows,
single beam of light from lightning illuminating his face,

expression: not anger, but calm determination,
slight smile at corner of lips,

crowd shocked into silence,
beautiful girl on platform showing rare emotion fluctuation,

cinematic slow motion,
emotional climax moment
```

### 负面提示词

```
3d render, CGI, unreal engine, video game scenery, mobile game ad, fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights, digital fire, magic aura, bloom effect,
text, words, letters, watermark, signature, logo, UI, navigation bar, character names,
clean geometry, plastic textures, flat lighting, perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors, purple tint, fake mist, 2d elements
```

### 角色位置关系图

```
                    【柳如烟】
                   玉阶之上
               眉心灵纹，流云纱裙

    【长老席】                    【长老席】
        ↑                            ↑
    （注视）                      （注视）

              ↑韩林独自站立↑
            洗白发白棉麻长衫
              脊背如剑

【宾客席】←【柳如海主位】→【叶尘贵客席】
  30人      紫金长袍         玄色锦袍

              ↑大门↓
            雷云翻涌
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |
| v01_liuruyan | `visual_reference/characters/v01_liuruyan.md` | 柳如烟 |
| v01_yechen | `visual_reference/characters/v01_yechen.md` | 叶尘 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch003_柳家大厅"
  visual_ref: "visual_reference/scenes/v01_ch003_柳家大厅.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
    - id: "v01_liuruyan"
      visual_ref: "visual_reference/characters/v01_liuruyan.md"
    - id: "v01_yechen"
      visual_ref: "visual_reference/characters/v01_yechen.md"
```
