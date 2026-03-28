# 场景：太虚宗外门广场 - 测灵大典（第1章）

> **scene_id**: `v01_ch001_测灵大典`
> **visual_ref**: `v01_ch001_测灵大典.md`
> **章节**: 第1章
> **一一对应**: 视频Prompt引用此场景时必须使用此ID

## 场景概述

| 属性 | 描述 |
|------|------|
| **位置** | 太虚宗外门广场·测灵台 |
| **时代** | 修真界·太虚宗·暮春 |
| **氛围** | 人声鼎沸、嘲讽、轻蔑、命运转折点 |

## 环境特征

| 属性 | 描述 |
|------|------|
| **建筑** | 三千级白玉台阶蜿蜒而下，每级镌刻繁复阵纹 |
| **测灵台** | 九十九级台阶之上，测灵碑矗立 |
| **测灵碑** | 三丈高玄黑色石碑，表面流转星辰般微光，触手温润如生命搏动 |
| **布置** | 广场黑压压站满人，世家子弟锦缎华服，寒门少年粗布麻衣 |
| **光线** | 朝阳初升，金色光晕，暮春晨雾未散尽 |
| **特色** | 测灵碑炸裂异象：星光骤然炸裂，化作漫天光点 |

## 修真美学设计

| 元素 | 设计 |
|------|------|
| 白玉台阶 | 金色阵纹随朝阳亮起，万年宗门底蕴 |
| 测灵碑 | 玄黑如墨，星光流转，上古仙人遗留 |
| 广场人群 | 三千弟子+各方宾客，阶层分明 |
| 光效 | 朝阳金色+测灵碑星光+爆炸时的黑芒 |

## 出现章节

- 第1章：测灵大典，韩林测出"伪灵根"，柳如烟当众退婚

## 光线设计

```
暮春晨曦光线方案：
- 时间：辰时初刻，朝阳初升
- 主光：金色晨光从山门方向照射
- 补光：测灵碑自身散发的星辰微光
- 氛围：温暖金色调，但广场充满冷漠嘲讽气氛
```

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: Tai Xu Sect outer court as a real historical megalithic site inspired by Tang Dynasty architecture,

environment details:
- three thousand wide marble steps carved from natural white stone, featuring realistic mineral veins, slight weathering, and erosion on the edges,
- intricate patterns on the steps are deep-set gold-leaf inlays reflecting the low-angle morning sun, not glowing,
- the massive 99-step platform is constructed from heavy weathered masonry with realistic mortar lines and moss in the crevices,

the monument: a massive obsidian monolith, real volcanic glass texture, semi-translucent edges with natural crystalline inclusions, reflecting the golden sunrise with physical accuracy,

the crowd: thousands of real people in historically accurate period costumes, layered hemp and silk textures, natural fabric folding and swaying, forming a dense sea of people across the plaza,

lighting & atmosphere:
- authentic early morning golden hour, sun low on the horizon behind the mountain gates,
- real Tyndall effect filtering through heavy morning mist and airborne dust particles,
- natural atmospheric haze, realistic soft shadows stretching across the plaza,
- no magical particles, no digital glow, strictly physical light interaction,

single figure in worn robes standing alone before the monument, looking up with calm defiance,

composition: low-angle shot from below platform looking up towards the monolith, showcasing the overwhelming magnitude of the architecture,

technical: high dynamic range, film grain, slight lens flare from the sun, masterpiece, photorealistic textures
```

### 测灵时刻提示词（韩林按碑时）

```
[基础场景] +
close-up on worn-robed youth pressing palm to obsidian monument,
golden morning light contrasting with purple-black energy burst reflected naturally from the volcanic glass surface,
crowd gasping in background,

explosion of light particles visible as dust kicked up by energy,

三个古篆大字浮现碑面：伪灵根,

expression on youth face: not despair, but hidden knowing,
fist slowly clenching,

dramatic rim lighting from the sun, emotional intensity,
cinematic slow motion effect
```

### 负面提示词

```
3d render, CGI, unreal engine, video game scenery, mobile game ad, fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights, digital fire, magic aura, bloom effect,
text, words, letters, watermark, signature, logo, UI, navigation bar, character names,
clean geometry, plastic textures, flat lighting, perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors, purple tint, fake mist, 2d elements
```

### 分镜建议

| 分镜 | 描述 | 提示词要点 |
|------|------|-----------|
| establishing shot | 全景广场 | 三千台阶, 人潮, 晨雾, 测灵台 |
| medium shot | 人群反应 | 各色表情, 嘲讽目光 |
| close-up | 韩林按碑 | 星光炸裂, 少年坚定眼神 |

## 角色视觉锚点

```
韩林：
- 服装：洗得发白的青色弟子服
- 状态：身形单薄，面色苍白
- 表情：沉静如深潭，不见波澜

柳如烟：
- 服装：月白色长裙，银丝绣流云纹
- 位置：广场东侧高台
- 状态：即将退婚

叶尘：
- 服装：玄色锦袍
- 位置：内门长老席
```

## 场景ID索引

| 角色ID | 视觉参考文件 | 说明 |
|--------|--------------|------|
| v01_hanlin | `visual_reference/characters/v01_hanlin.md` | 韩林主角 |
| v01_liuruyan | `visual_reference/characters/v01_liuruyan.md` | 柳如烟 |

## 视频Prompt引用

```yaml
scene_001:
  id: "v01_ch001_测灵大典"
  visual_ref: "visual_reference/scenes/v01_ch001_测灵大典.md"
  characters:
    - id: "v01_hanlin"
      visual_ref: "visual_reference/characters/v01_hanlin.md"
    - id: "v01_liuruyan"
      visual_ref: "visual_reference/characters/v01_liuruyan.md"
```
