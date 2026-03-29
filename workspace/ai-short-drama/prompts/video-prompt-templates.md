# AI短剧视频生成提示词模板

> 用于 C2.0 / 可灵 / Runway 等视频生成模型的提示词
>
> **版本：v2.0** | 更新：2026-03-29

---

## 目录

1. [五维坐标系统](#五维坐标系统)
2. [角色提示词模板](#角色提示词模板)
3. [场景提示词模板](#场景提示词模板)
4. [Camera Language 词库](#camera-language-词库)
5. [古装仙侠专用场景](#古装仙侠专用场景)
6. [生成规则](#生成规则)
7. [负面提示词](#负面提示词)

---

## 五维坐标系统

每个镜头通过五个维度精确定义，确保风格一致性和叙事连贯性。

| 维度 | 说明 | 取值范围 |
|------|------|----------|
| **W1 - 镜头语言** | 景别 + 运动 | 特写/中景/全景/航拍 + 推/拉/摇/移 |
| **W2 - 情绪氛围** | 核心情绪色调 | 恐惧/热血/唯美/神秘/黑暗/希望 |
| **W3 - 光线色调** | 光源 + 色温 | 晨曦金/暮色橙/幽蓝/暗紫/炽白 |
| **W4 - 物理动势** | 主体运动状态 | 静止/缓慢/爆发/飘动/坠落 |
| **W5 - 构图结构** | 画面构成方式 | 中心/三分/对称/框架/纵深 |

### 五维坐标标记法

在剧本中用坐标标记每个镜头：
```
[镜头ID] W1:中景-推 W2:恐惧 W3:幽蓝 W4:静止 W5:纵深
```

### 五维坐标 → 提示词映射

#### W1 镜头语言 → 摄影机调度
| 坐标 | 描述 | 英文 |
|------|------|------|
| 特写-推 | 面部/局部特写，缓慢推进 | close-up, slow push in |
| 中景-固定 | 人物完整，摄影机静止 | medium shot, static |
| 全景-摇 | 展示全貌，缓慢摇镜 | wide shot, slow pan |
| 航拍俯视 | 高空俯瞰，大局观 | aerial shot, bird's eye |
| 跟拍 | 跟随主体运动 | tracking shot, follow |
| 横移 | 侧向移动展示 | dolly shot, lateral |
| 低角度仰拍 | 仰视主体，强调威严 | low angle, looking up |
| 仰拍-推 | 低角度推进，强调压迫感 | low angle push in |

#### W2 情绪氛围 → 氛围词
| 坐标 | 关键词 |
|------|--------|
| 恐惧 | mysterious, eerie, ominous, dread, horror |
| 热血 | intense, dramatic, epic, powerful, fierce |
| 唯美 | ethereal, dreamy, soft, poetic, serene |
| 神秘 | enigmatic, cryptic, arcane, occult |
| 黑暗 | oppressive, dark, foreboding, sinister |
| 希望 | hopeful, warm, uplifting, bright |
| 紧张 | tension, claustrophobic, urgent |
| 温情 | warm, tender, affectionate |

#### W3 光线色调 → 光线描述
| 坐标 | 光源 | 色温 |
|------|------|------|
| 晨曦金 | 早晨阳光，低角度 | warm golden, amber |
| 暮色橙 | 黄昏，橙红天空 | sunset orange, warm |
| 幽蓝 | 冷调，神秘感 | cold blue, teal |
| 暗紫 | 夜晚，魔法感 | dark purple, violet |
| 炽白 | 爆发，高光 | intense white, HDR |
| 阴天灰 | 散射光，无方向 | overcast, flat grey |
| 烛光暖 | 室内，温暖集中 | candlelight, warm amber |
| 月光银 | 夜晚户外，清冷 | moonlight, silver blue |

#### W4 物理动势 → 主体运动
| 坐标 | 描述 |
|------|------|
| 静止 | 静态站立，凝视 |
| 缓慢 | 行走、呼吸、沉思 |
| 爆发 | 能量释放、冲击、爆炸 |
| 飘动 | 衣物/头发/粒子飘动 |
| 坠落 | 下落、跌倒、失控 |
| 颤抖 | 恐惧、寒冷、虚弱 |

#### W5 构图结构 → 画面构成
| 坐标 | 构图方式 |
|------|----------|
| 中心 | 主体置于画面正中 |
| 三分 | 遵循三分法，主体在交叉点 |
| 对称 | 中轴对称，庄严感 |
| 框架 | 利用门窗框住主体 |
| 纵深 | 前中后景层次分明 |
| 留白 | 大量负空间，情绪表达 |
| 螺旋 | 旋转构图，动感 |

---

## 角色提示词模板

### 格式说明

```
RAW photo, character turnaround sheet, four full body shots on white canvas,

subject: [年龄] [种族] [性别] actor, [身高], [体型], realistic human anatomy with [体质描述], [肤色],

facial features: [发型], [瞳色] irises with [眼神描述], [表情], [皮肤状态],

attire: [服装类型] in [颜色] and [颜色], [材质描述], [细节描述],

views (from left to right):
1. strict front view, [姿势],
2. 3/4 front view facing [方向],
3. strict profile view facing [方向],
4. full back view showing [细节],

technical: shot on ARRI Alexa, [焦距]mm lens, f/[光圈], sharp focus on [焦点], [灯光描述],

background: pure seamless white paper backdrop

negative: [角色类负面词]
```

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
subject: a real 18-year-old East Asian female actresses, 168cm height, slender graceful build with elegant posture, realistic human anatomy with natural proportions, flawless porcelain-like pale skin,

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

## Camera Language 词库

### 镜头运动（Camera Movement）

| 中文 | 英文 | 说明 |
|------|------|------|
| 推 | Push In / Zoom In | 摄影机前进或zoom in，聚焦主体，制造紧张感 |
| 拉 | Pull Out / Zoom Out | 摄影机后退，揭示更多环境，释放压力 |
| 摇 | Pan | 水平旋转摄影机，展示横向空间 |
| 倾斜 | Tilt | 垂直旋转摄影机，上下运动 |
| 移 | Tracking / Dolly | 摄影机横向跟随主体移动 |
| 跟 | Follow | 跟随主体运动，保持距离恒定 |
| 升降 | Crane / Jib | 摄影机垂直上升或下降 |
| 环绕 | Orbit / Revolve | 绕主体旋转拍摄 |
| 手持 | Handheld | 轻微晃动，制造紧张/真实感 |
| 固定 | Static / Locked Off | 摄影机静止，依赖主体运动 |
| 航拍 | Aerial / Drone | 从高空俯瞰，大局展示 |
|POV主观镜头 | POV Shot | 角色视角，身临其境 |
| 斯坦尼康 | Steadicam | 平滑移动，跟随穿越空间 |
| 变速 | Speed Ramp | 速度变化，慢动作或快进 |

### 景别（Shot Size）

| 中文 | 英文 | 适用场景 |
|------|------|----------|
| 大特写 | Extreme Close-up (ECU) | 眼睛、嘴唇、手部特写，强调细节 |
| 特写 | Close-up (CU) | 面部表情，角色情绪 |
| 中特写 | Medium Close-up (MCU) | 颈部到腰部，上半身 |
| 中景 | Medium Shot (MS) | 膝盖以上，角色完整+部分环境 |
| 中远景 | Medium Long Shot (MLS) | 脚部以上，环境开始占主导 |
| 全景 | Long Shot / Wide Shot (WS) | 人物全身+完整环境 |
| 大远景 | Extreme Long Shot (ELS) | 风景全貌，人物如蚂蚁 |
| 两人镜头 | Two Shot | 两个角色同框 |
| 群像镜头 | Group Shot | 三人及以上 |

### 角度（Camera Angle）

| 中文 | 英文 | 效果 |
|------|------|------|
| 平视 | Eye Level | 客观、中性 |
| 仰视 | Low Angle | 主体显得高大、威严、有力 |
| 俯视 | High Angle | 主体显得渺小、脆弱、被压制 |
| 鸟瞰 | Bird's Eye | 顶视，全局概览 |
| 倾斜 | Dutch Angle / Canted | 不平衡、紧张、混乱 |
| 过肩 | Over the Shoulder (OTS) | 两人对话，代入感 |
| 主观 | POV | 观众替代角色视角 |
| 蚂蚁视角 | Worm's Eye | 超低角度仰视 |

### 焦点（Focus）

| 类型 | 英文 | 说明 |
|------|------|------|
| 浅景深 | Shallow Depth of Field | 主体清晰，背景虚化 |
| 深景深 | Deep Focus | 前后都清晰 |
| 焦平面 | Focal Plane | 单点清晰，范围外虚化 |
| 跟焦 | Rack Focus | 焦点在主体间切换 |
| 虚化 | Bokeh | 散景效果，梦幻感 |
| 全焦 | Pan Focus | 全部区域清晰 |

### 转场（Transition）

| 类型 | 说明 |
|------|------|
| 切 | Cut - 硬切，快节奏 |
| 叠化 | Dissolve - 柔过渡，时间流逝 |
| 淡入淡出 | Fade In/Out - 开始/结束 |
| 划入划出 | Wipe - 漫画式过渡 |
| 推拉转场 | Push Transition - 推入黑/拉出 |
| 旋转转场 | Spin Transition - 旋转过渡 |

### 电影摄影术语

| 术语 | 说明 |
|------|------|
| Chiaroscuro | 明暗对比，戏剧性光影 |
| Rim Light | 轮廓光，分离主体与背景 |
| Key Light | 主光源，定义形态 |
| Fill Light | 补光，减少阴影 |
| Practical Light | 场景内实际光源（蜡烛、灯笼） |
| Volumetric Light | 体积光，尘埃/雾气中可见光柱 |
| Film Grain | 胶片颗粒，写实质感 |
| Letterbox | 遮幅，宽银幕比例 |
| Anamorphic | 变形宽银幕镜头，横向拉伸 |
| Color Grading | 调色，色调统一 |
| Motivated Lighting | 有来源的光源（符合逻辑） |

---

## 古装仙侠专用场景

### 场景模板 A：秘境洞口

**五维坐标**: W1:全景-摇 W2:神秘 W3:幽蓝 W4:缓慢 W5:纵深

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: ancient spirit realm cave entrance hidden in misty mountain cliff,

environment details:
- jagged cliff face covered in thick green moss and hanging vines,
- dark cave mouth framed by weathered stone archway carved with eroded ancient runes,
- thick white mist flowing continuously from cave interior,
- twisted ancient pine trees growing horizontally from cliff face,
- faint ethereal glow emanating from deep within cave,

the cave: mysterious darkness beyond entrance, cold air flowing outward,
mysterious purple-blue mist swirling at threshold,

lighting & atmosphere:
- cold blue-grey ambient light filtering through mist,
- no direct sunlight, cave interior in deep shadow,
- subtle bioluminescent glow from cave depths,
- thick volumetric mist creating layered depth,
- cold air condensation visible at cave mouth,

composition: medium shot slowly panning across cave entrance, mist flowing outward,
sense of unknown danger lurking within,

technical: high dynamic range, film grain, mysterious atmosphere, volumetric mist, photorealistic textures

negative: 3d render, cartoon, anime, magical particles, glowing runes, text
```

### 场景模板 B：宗门大殿

**五维坐标**: W1:全景-仰拍 W2:热血 W3:晨曦金 W4:静止 W5:对称

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: grand sect main hall built into mountain peak,

environment details:
- massive wooden hall with curved roof, towering columns carved with dragon motifs,
- white marble floor polished smooth by centuries of footsteps,
- ancient bronze incense burners flanking main entrance,
- silk banners with sect emblems hanging from ceiling,
- thousands of white marble steps leading up to hall entrance,
- low-hanging clouds surrounding mountain peak,

the hall: imposing structure dominating entire mountain peak,

lighting & atmosphere:
- early morning golden sunlight, sun low behind mountains,
- warm golden rays streaming through hall entrance,
- long dramatic shadows cast by columns,
- dust particles visible in light beams,
- cool blue tones in shadow areas,

composition: low angle looking up at hall entrance, sheer scale overwhelming viewer,

technical: high dynamic range, film grain, epic grand atmosphere, photorealistic textures

negative: 3d render, cartoon, anime, magical glow, text, watermark
```

### 场景模板 C：修炼室

**五维坐标**: W1:中景-固定 W2:唯美 W3:月光银 W4:缓慢 W5:框架

```
RAW landscape photo, cinematic medium shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: ancient cultivation chamber inside mountain,

environment details:
- circular stone chamber carved from solid rock,
- carved stone platform in center with meditation cushion,
- walls covered in ancient cultivation diagrams and faded scripture,
- single shaft of silver moonlight streaming through ceiling opening,
- small jade talismans hanging from ceiling, slightly swaying,
- cold mist pooling on floor,

the cultivator: young person in loose robes seated in meditation posture,

lighting & atmosphere:
- cool silver-blue moonlight streaming through opening,
- no other light sources, deep shadows in corners,
- subtle cold mist rising from floor,
- gentle shadows, meditative silence,
- shallow depth of field, cultivator in focus,

composition: medium shot through doorway as natural frame, cultivator centered in moonlight,

technical: high dynamic range, film grain, ethereal peaceful atmosphere, bokeh, photorealistic textures

negative: 3d render, cartoon, anime, magical particles, glowing effects, text
```

### 场景模板 D：古战场遗迹

**五维坐标**: W1:全景-航拍 W2:黑暗 W3:暗紫 W4:静止 W5:三分

```
RAW landscape photo, cinematic aerial wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: ancient battlefield ruins,

environment details:
- vast plain covered in broken weapons and shattered armor fragments,
- cracked earth showing ancient spiritual energy blast damage,
- remnants of stone fortifications overgrown with weeds,
- scattered ancient wooden stakes and bamboo spike traps,
- dark purple storm clouds gathering overhead,

the ruins: evidence of massive spirit beast battle,

lighting & atmosphere:
- dark purple overcast sky, ominous light,
- no direct sunlight, oppressive atmosphere,
- purple-black shadows hiding details,
- wind picking up dust and debris,
- sense of lingering resentment,

composition: aerial shot showing scale of battlefield, broken weapons pattern,

technical: high dynamic range, film grain, dark foreboding atmosphere, desaturated tones, photorealistic textures

negative: 3d render, cartoon, anime, colorful, magical particles, text
```

### 场景模板 E：水底遗迹

**五维坐标**: W1:中景-推 W2:神秘 W3:幽蓝 W4:飘动 W5:纵深

```
RAW landscape photo, cinematic medium shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: ancient underwater ruins,

environment details:
- collapsed temple structure submerged in deep water,
- broken stone pillars covered in coral and seaweed,
- ancient carved statues half-buried in sand,
- shafts of blue-green light filtering through water,
- bubbles rising slowly from disturbed sediment,

the ruins: forgotten civilization beneath the waves,

lighting & atmosphere:
- cool blue-green underwater light filtering from above,
- floating particles and plankton in water column,
- floating silk fabric from ancient banners,
- gentle current moving debris,
- sense of profound silence and age,

composition: medium shot slowly pushing through ruins, sense of exploration,

technical: high dynamic range, film grain, underwater caustics, blue-green color grade, photorealistic textures

negative: 3d render, cartoon, anime, magical glow, bright colors, text
```

### 场景模板 F：天劫雷云

**五维坐标**: W1:全景-仰拍 W2:恐惧 W3:炽白 W4:爆发 W5:中心

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: mountain peak during tribulation lightning,

environment details:
- massive dark thunderclouds swirling in vortex formation,
- multiple lightning bolts striking mountain peak,
- ancient stone cultivation platform cracked and glowing,
- surrounding trees stripped of bark by spiritual energy,
- purple-black smoke and debris being lifted by updraft,

the lightning: terrifying natural spiritual energy,

lighting & atmosphere:
- brilliant white flashes illuminating everything,
- constant rumble echoing across mountains,
- purple-white lightning contrast against dark clouds,
- rain and wind whipping debris,
- oppressive dread filling the air,

composition: low angle looking up at lightning vortex, small figure on peak,

technical: high dynamic range, film grain, dramatic lightning, photorealistic textures

negative: 3d render, cartoon, anime, comic book lightning, text
```

### 场景模板 G：洞府福地

**五维坐标**: W1:中景-横移 W2:唯美 W3:晨曦金 W4:缓慢 W5:框架

```
RAW landscape photo, cinematic medium shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: blessed cultivation cave dwelling,

environment details:
- small stone cave dwelling furnished with bamboo and wood,
- hand-carved stone bed and desk,
- small waterfall outside cave creating mist,
- spirit herb garden growing near entrance,
- carved protective talismans on cave walls,
- sunlight streaming through waterfall mist creating rainbows,

the dwelling: humble but peaceful,

lighting & atmosphere:
- warm golden morning sunlight,
- light refracting through waterfall mist,
- gentle rainbow colors in spray,
- birds singing outside,
- warm cool contrast between sun and shade,

composition: medium shot panning through cave dwelling, peaceful atmosphere,

technical: high dynamic range, film grain, warm peaceful atmosphere, lens flare through mist, photorealistic textures

negative: 3d render, cartoon, anime, magical glow, text
```

### 场景模板 H：幻境迷阵

**五维坐标**: W1:特写-推 W2:神秘 W3:幽蓝 W4:飘动 W5:留白

```
RAW landscape photo, cinematic close-up shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: illusion formation trapping cultivator,

environment details:
- same scene repeating infinitely in all directions,
- reality flickering between two states,
- floating ethereal mist distorting reflections,
- ghostly afterimages following movement,
- floor surface uncertain, could be stone or void,

the illusion: impossible geometry, conflicting realities,

lighting & atmosphere:
- cold blue-white ethereal light without source,
- colors shifting between warm and cold,
- sense of disorientation,
- tinnitus ringing in ears,
- time feeling distorted,

composition: close-up on disoriented face, everything else blurred and distorted,

technical: high dynamic range, film grain, surreal distortion, shallow focus, photorealistic textures

negative: 3d render, cartoon, anime, clear sharp, text
```

---

## 生成规则

### 1. 角色提示词生成规则

#### 必填要素
- [x] 年龄（必须是真实年龄数字）
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
| 希望 | hopeful, warm, uplifting |
| 恐惧 | horror, dread, terror |
| 温情 | tender, affectionate, warm |

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
cross-eyed, minor appearance, 15-year-old if older needed
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

### 五维坐标速查

```
[镜头ID] W1:中景-推 W2:热血 W3:晨曦金 W4:爆发 W5:对称
```

| 维度 | 速查码 |
|------|--------|
| W1 | 特写/中景/全景/航拍 + 固定/推/拉/摇/移/跟 |
| W2 | 恐惧/热血/唯美/神秘/黑暗/希望/紧张/温情 |
| W3 | 晨曦金/暮色橙/幽蓝/暗紫/炽白/阴天灰/月光银 |
| W4 | 静止/缓慢/爆发/飘动/坠落/颤抖 |
| W5 | 中心/三分/对称/框架/纵深/留白/螺旋 |

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

*最后更新：2026-03-29 | v2.0*
