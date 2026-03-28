# 场景AI绘图提示词模板

> 本模板定义了场景视觉参考的标准结构，用于AI视频生成和场景一致性管理。
>
> **重要更新 (2026-03-24)**: 本模板采用**摄影写实**风格，参考ARRI Alexa拍摄效果，通过引入真实物理特性（风化石材、自然光线、灰尘颗粒）来打破AI模型的"CG游戏场景感"。

## 核心策略

1. **禁用"xianxia/cultivation world"** — 这些词汇会触发游戏CG渲染逻辑
2. **使用"historical site"替代** — 描述为Tang Dynasty palace, ancient historical megalithic site
3. **禁用"glowing/magical particles"** — 用"gold-leaf inlay reflecting light physically"替代
4. **引入物理光学瑕疵** — Tyndall effect, dust particles in light rays, atmospheric haze
5. **禁用分段** — 提示词放在一起，不要按环境/光线/构图分类

---

## 正向提示词模板（单段落）

```
RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, 35mm anamorphic lens, 8k resolution,

location: {location_description} as a real historical {dynasty} {building_type},

environment details:
- {architectural_details_1},
- {architectural_details_2},
- {architectural_details_3},

{the_moment_or_character_focus},

lighting & atmosphere:
- {lighting_conditions},
- {atmospheric_effects},
- {special_light_interactions},
- no magical particles, no digital glow, strictly physical light interaction,

composition: {composition_description},

technical: high dynamic range, film grain, {color_grading}, masterpiece, photorealistic textures
```

## 负面提示词

```
3d render, CGI, unreal engine, video game scenery, mobile game ad, fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights, digital fire, magic aura, bloom effect,
text, words, letters, watermark, signature, logo, UI, navigation bar, character names,
clean geometry, plastic textures, flat lighting, perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors, purple tint, fake mist, 2d elements
```

---

## 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `location_description` | 场景位置描述 | Tai Xu Sect outer court, Liu family ancestral hall |
| `dynasty` | 历史朝代风格 | Tang Dynasty, Han Dynasty |
| `building_type` | 建筑类型 | palace interior, megalithic plaza, ancient library |
| `architectural_details` | 建筑细节 | weathered marble steps with natural erosion, jade pillars with carved dragons |
| `the_moment_or_character_focus` | 人物/时刻焦点 | young cultivator standing alone in center, two figures battling |
| `lighting_conditions` | 光线条件 | authentic golden sunrise, overcast storm light filtering through |
| `atmospheric_effects` | 大气效果 | morning mist, Tyndall effect in dust particles, natural haze |
| `special_light_interactions` | 光线交互 | gold-leaf reflecting sun angle light, volcanic glass catching reflections |
| `composition_description` | 构图描述 | wide angle establishing shot, low-angle dramatic composition |

---

## 物理材质替代对照表

| 修真描述（禁用） | 写实替代（启用） |
|----------------|----------------|
| glowing golden formation patterns | gold-leaf inlay reflecting low-angle morning sun |
| flowing starlight on monument | volcanic glass surface with natural crystalline inclusions reflecting light |
| spirit-testing platform | massive obsidian monolith as real volcanic stone |
| magical mist | natural morning fog with Tyndall effect |
| glowing runes on walls | ancient carved symbols with gold/silver inlay |
| purple-black energy swirling | dust and debris caught in physical air currents |
| floating light particles | dust motes visible in sunbeams |
| ethereal glow | natural reflective surfaces catching ambient light |

---

## 场景类型模板

### 1. 广场/台阶场景

```
location: {sect_name} outer court as a real historical megalithic plaza,

environment details:
- wide marble steps carved from natural stone with realistic mineral veins and slight weathering,
- heavy masonry platform with moss growing in crevices,
- ancient timber structures with weathered wood grain,

{character_focus},

lighting & atmosphere:
- authentic {time_of_day} lighting,
- real Tyndall effect filtering through {weather_condition},
- natural atmospheric haze adding depth,
- no magical particles or digital effects,

composition: epic wide angle shot showing scale of the architecture
```

### 2. 大殿/厅堂场景

```
location: {hall_name} as a real historical Tang Dynasty throne room,

environment details:
- {pillar_description} with natural weathering and moss,
- {floor_description} with visible wear patterns,
- {lighting_fixtures} as aged brass with natural tarnish,

{character_focus_and_activity},

lighting & atmosphere:
- warm {light_source} casting realistic flickering shadows,
- natural depth of field with people at different distances,
- real dust particles in light beams,
- no magical glow, strictly physical light,

composition: wide shot showing grand scale of hall
```

### 3. 山谷/野外场景

```
location: mountain {terrain_type} as a real geological site,

environment details:
- rocky terrain with {erosion_description},
- boulders from {geological_process},
- mountain walls with natural stratified rock layers,

{character_focus_and_action},

lighting & atmosphere:
- dramatic {sky_condition} with {light_color} filtering through clouds,
- real atmospheric haze with dust particles,
- natural shadows casting across terrain,
- no magical energy effects,

composition: wide angle establishing shot
```

### 4. 室内/密室场景

```
location: {room_type} as a real historical Chinese {building_type},

environment details:
- {wall_description} with {material_description},
- {furniture_description} with natural wood grain and wear,
- {light_source_description} with {light_quality},

{character_focus},

lighting & atmosphere:
- {primary_light} creating {shadow_quality},
- {secondary_light} with {color_temperature} tones,
- real dust particles visible in light beams,
- no magical glow, darkness is purely physical absence of light,

composition: cinematic shot showing the {isolation/focus}
```

### 5. 悬崖/峰顶场景

```
location: mountain peak {terrain_type} as a real geological formation,

environment details:
- cliff edge with natural erosion patterns and small plants in cracks,
- {cloud_description} below as real meteorological {phenomenon},
- distant mountains with natural atmospheric perspective,

{character_focus_with_pose},

lighting & atmosphere:
- {sun_position} light creating dramatic {effect},
- real Tyndall effect in the mist below,
- natural atmospheric perspective with haze adding depth,
- no magical glow, purely physical sunlight interaction,

composition: wide angle shot capturing vast landscape scale with figure silhouetted
```

---

## 使用说明

1. **始终使用单段落提示词** — 不要按"环境/光线/构图"分段，整个提示词放在一起
2. **禁用"glowing/magical"词汇** — 用物理反射替代发光效果
3. **引入Tyndall effect** — 灰尘颗粒在光线中形成丁达尔效应
4. **描述建筑物理特性** — "weathered stone, natural erosion, moss in crevices"
5. **禁用"fantasy/cultivation world"** — 描述为真实历史建筑风格
6. **光线必须是物理的** — 阳光反射、烛光、而不是"能量发光"
