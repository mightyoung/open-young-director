# AI短剧视频生成提示词模板

> 用于 C2.0 / 可灵 / Runway 等视频生成模型的提示词

---

## 目录

1. [角色提示词模板](#角色提示词模板)
2. [场景提示词模板](#场景提示词模板)
3. [生成规则](#生成规则)
4. [负面提示词](#负面提示词)

---

## 角色提示词模板

### 格式说明

```
35mm film photography, high ISO, grain texture, authentic RAW photo,
character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,

subject: [年龄] [种族] [性别] actor, [身高], [体型], realistic human anatomy with [体质描述], [肤色],

facial features: [发型], [瞳色] irises with [眼神描述], [表情], [皮肤状态],

attire: [服装类型] in [颜色] and [颜色], [材质描述], [细节描述],

views (from left to right):
1. strict front view, [姿势],
2. 3/4 front view facing [方向],
3. strict profile view facing [方向],
4. full back view showing [细节],

technical details: shot on ARRI Alexa, [焦距]mm lens, f/[光圈], sharp focus on [焦点], [灯光描述],

background: pure seamless white paper backdrop, absolute blank background, zero digital artifacts, totally clean background

negative: [角色类负面词]
```

### 角色模板速查表

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `[年龄]` | 真实年龄数字 | 15, 16, 17, 18, 20 |
| `[种族]` | East Asian | East Asian |
| `[性别]` | male/female | male, female |
| `[身高]` | 身高cm | 175cm, 168cm |
| `[体型]` | 体型描述 | lean athletic build, slender graceful |
| `[体质描述]` | 身体特征 | natural muscle definition, fit |
| `[肤色]` | 肤色描述 | pale skin, slightly tan skin |
| `[发型]` | 头发描述 | short messy black hair, long flowing black hair |
| `[瞳色]` | 眼睛颜色 | dark brown, pale purple |
| `[眼神描述]` | 眼神特征 | determined gaze, cold piercing look |
| `[表情]` | 面部表情 | fierce expression, serene smile |
| `[服装类型]` | 服装风格 | worn brown robes, flowing white silk gown |
| `[颜色]` | 主色调 | black, purple, white, green |
| `[材质描述]` | 面料质感 | weathered linen, delicate silk |
| `[细节描述]` | 服装细节 | torn edges, embroidery patterns |
| `[方向]` | 面向 | right, left |
| `[焦距]` | 镜头焦距 | 50mm, 85mm |
| `[光圈]` | 光圈值 | 1.8, 2.8 |
| `[焦点]` | 对焦主体 | skin texture, facial features |
| `[灯光描述]` | 光线特点 | natural soft, dramatic side |

### 角色示例

#### 矿工少年（林逸 - 普通状态）
```
subject: a real 15-year-old East Asian male actor, 165cm height, lean but wiry build from manual labor, realistic human anatomy with natural muscle definition, slightly rough skin with small calluses on hands,

facial features: messy short black hair with dust particles, dark brown irises with determined gaze, tired but resilient expression, clean forehead showing youth, slight dark circles under eyes,

attire: worn and torn coarse brown miner's clothing, patched linen shirt with frayed edges, simple leather belt, torn pants with dirt stains, worn straw sandals,

views (from left to right):
1. strict front view, standing straight,
2. 3/4 front view facing right,
3. strict profile view facing right,
4. full back view showing worn clothing,

technical details: shot on ARRI Alexa, 50mm lens, f/2.8, sharp focus on skin texture, realistic subsurface scattering, natural dim lighting from mine tunnel lamp,

background: pure seamless white paper backdrop
```

#### 觉醒状态（林逸 - 力量觉醒）
```
subject: a real 15-year-old East Asian male actor, 175cm height, lean athletic build radiating subtle blue glow, realistic human anatomy with faint luminous blue energy lines along muscles, pale skin with ethereal blue light emanating from within,

facial features: short black hair slightly floating as if underwater, eyes glowing with intense pale purple-blue iris (still realistic human texture, no cartoon glow), cold fierce determined expression, third eye area with faint blue glow,

attire: same worn brown clothes but with blue spiritual energy swirling around body, tattered cloth and hair flowing dramatically without wind, faint blue rune-like patterns appearing on skin,

technical details: shot on ARRI Alexa, 50mm lens, f/2.8, sharp focus with blue volumetric lighting from within, dramatic chiaroscuro lighting, smoke effects,

background: pure seamless white paper backdrop
```

#### 仙女（云绮罗）
```
subject: a real 18-year-old East Asian female actress, 168cm height, slender graceful build with elegant posture, realistic human anatomy with natural proportions, flawless porcelain-like pale skin,

facial features: long black hair flowing past waist in loose waves, large dark brown eyes with cold piercing gaze, serene expression with slight smile, high cheekbones, elegant eyebrows,

attire: flowing pure white silk gown with subtle silver embroidery, high collar Chinese style, sheer white sash at waist, translucent fabric layers, white jade hair ornament with pearl,

technical details: shot on ARRI Alexa, 85mm lens, f/1.8, sharp focus on facial features, soft ethereal lighting suggesting white glow, shallow depth of field, dreamy bokeh,

background: pure seamless white paper backdrop
```

---

## 场景提示词模板

### 格式说明

```
RAW landscape photo, cinematic [shot_type], shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: [地点类型] as [真实参考],

environment details:
- [环境细节1],
- [环境细节2],
- [环境细节3],
- [环境细节4],

[主要元素描述]: [具体描述],

lighting & atmosphere:
- [光线类型], [时间],
- [氛围效果],
- [色调描述],
- [物理效果],

composition: [构图描述],

technical: high dynamic range, film grain, [额外技术描述], photorealistic textures
```

### 场景模板速查表

| 占位符 | 说明 | 示例 |
|--------|------|------|
| `[shot_type]` | 镜头类型 | wide shot, close-up, medium shot |
| `[地点类型]` | 场景类型 | mine tunnel, ancient temple, mountain peak |
| `[真实参考]` | 现实参照 | real volcanic cave, Tang Dynasty architecture |
| `[环境细节N]` | 具体环境 | wooden beams, moss on walls, stone steps |
| `[主要元素]` | 场景主体 | the crystal, the youth, the gate |
| `[光线类型]` | 光源 | early morning golden hour, sunset orange |
| `[时间]` | 时间段 | sun low on horizon, midday sun |
| `[氛围效果]` | 氛围 | mist, fog, haze |
| `[色调描述]` | 色调 | warm gold tones, cool blue tones |
| `[物理效果]` | 视觉效果 | dust particles, lens flare |
| `[构图描述]` | 构图方式 | low-angle, aerial shot, close-up |
| `[额外技术]` | 技术词 | slight lens flare, dramatic rim lighting |

### 场景示例

#### 矿道觉醒
```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: collapsed mine tunnel as a real underground cavern,

environment details:
- narrow mine shaft carved from dark granite rock, rough hewn walls with tool marks,
- ancient wooden support beams showing age and decay, some broken and hanging,
- damp walls glistening with moisture, puddles reflecting dim light,
- narrow passage barely wide enough for one person,

the crystal: massive deep blue luminescent crystal embedded in cave wall, pulsing with ethereal blue inner light illuminating the entire tunnel,

the youth: 15-year-old boy in torn brown clothes pressed against crystal, face illuminated by blue glow, arms spread absorbing energy, hair floating upward,

lighting & atmosphere:
- intense blue bioluminescent glow from crystal,
- single oil lamp on ground casting warm orange flicker,
- blue and orange contrast creating dramatic tension,
- volumetric light rays piercing through darkness,
- dust particles visible in light beams,

composition: low-angle shot looking up at crystal, boy's silhouette against blue glow, dramatic scale comparison,

technical: high dynamic range, film grain, dramatic chiaroscuro lighting, photorealistic textures
```

#### 宗门山门
```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: majestic fairy sect mountain peak as real World Heritage site,

environment details:
- three thousand wide white marble steps, mineral veins visible, slight weathering,
- massive stone platform on mountain peak, ancient masonry with moss,
- ornate carved stone pillars supporting curved roof, Tang Dynasty style,
- jade-green roof tiles with gold trim, weathered naturally,
- mountain backdrop with low-hanging clouds,

the youth: small figure in worn clothes at bottom of steps looking up, tiny human before massive structure,

lighting & atmosphere:
- early morning golden hour, sun low behind peaks,
- golden sunlight casting dramatic shadows across steps,
- natural morning mist around mountain base,
- warm gold on stone, cool blue in shadows,
- no magical effects,

composition: low-angle from below steps looking up at hall, overwhelming scale, crowds as tiny dots,

technical: high dynamic range, film grain, slight lens flare, masterpiece, photorealistic textures
```

---

## 生成规则

### 1. 角色提示词生成规则

#### 必填要素
- [x] 年龄（必须是真实年龄，不能是"young"等模糊词）
- [x] 性别
- [x] 身高
- [x] 体型
- [x] 面部特征（发型、眼睛、表情）
- [x] 服装（类型、颜色、材质）
- [x] 四个角度（正面、3/4侧、正侧、背面）

#### 摄影参数
- 相机：ARRI Alexa
- 镜头：50mm 或 85mm
- 光圈：f/1.8（特写）或 f/2.8（全身）
- 背景：纯白无缝纸

#### 风格一致性
- 保持摄影写实风格
- 避免动漫、插画风格
- 避免过度美化、塑料皮肤
- 避免发光效果（除非是能量觉醒状态）

### 2. 场景提示词生成规则

#### 必填要素
- [x] 镜头类型（wide/medium/close-up）
- [x] 地点类型 + 现实参照
- [x] 环境细节（至少4条）
- [x] 主要元素描述
- [x] 光线氛围（至少4条）
- [x] 构图方式

#### 摄影参数
- 相机：ARRI Alexa
- 镜头：35mm anamorphic
- 分辨率：8k
- 色调：基于时间设定

#### 避免要素
- 避免魔法粒子、发光符文
- 避免卡通、插画风格
- 避免文字、水印
- 避免完美几何造型

### 3. 能量/觉醒效果

#### 正确写法
```
realistic blue spiritual energy emanating from body
faint blue glow along muscles
not cartoon glow but realistic light
```

#### 错误写法
```
glowing eyes
magic aura particles
floating magical symbols
```

### 4. 情绪氛围词

| 氛围 | 可用词 |
|------|--------|
| 神秘 | mysterious, eerie, ominous |
| 热血 | intense, dramatic, epic |
| 唯美 | ethereal, dreamy, soft |
| 紧张 | tension, claustrophobic |
| 黑暗 | oppressive, dark, foreboding |

---

## 负面提示词

### 角色类负面词
```
3d render, CGI, unreal engine, video game character, avatar, doll,
plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched,
glowing eyes, glowing effect, supernatural glow, magical particles, magic aura,
anime, illustration, drawing, painting, sketch, hyperrealistic,
character reference sheet, turnaround sheet, grid layout, multiple views,
text, words, letters, signature, watermark, logo, symbols, annotations,
half body, waist up, portrait, headshot, cropped, missing limbs,
duplicates, bad anatomy, deformed, mutation, disproportionate,
cross-eyed, minor appearance if adult needed, 15-year-old if older needed
```

### 场景类负面词
```
3d render, CGI, unreal engine, video game scenery, mobile game ad,
fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights,
digital fire, magic aura, bloom effect,
text, watermark, signature, logo, UI, navigation bar,
clean geometry, plastic textures, flat lighting,
perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors,
purple tint, fake mist, 2d elements
```

---

## 快速参考

### 角色最简模板
```
[年龄]yo [性别] actor, [身高], [体型],
[发型], [瞳色] eyes, [表情],
[服装],
4 views, ARRI Alexa, [焦距]mm, f/[光圈],
white backdrop

negative: anime, illustration, glowing, text
```

### 场景最简模板
```
RAW photo, cinematic [shot],
[地点],
[4 environment details],
[main subject],
[4 lighting details],
composition: [angle],
technical: HDR, film grain, photorealistic

negative: 3d, cartoon, glow, text
```

---

*最后更新：2026-03-29*
