# 角色：青冥（第一卷）

> **visual_ref**: `v01_qingming.md`
> **章节引用**: ch003, ch004, ch008
> **一致性来源**: 角色视觉参考是视频生成和播客制作的唯一真实来源

## 基本信息

| 属性 | 描述 |
|------|------|
| **修为** | 金丹期 |
| **身份** | 天玄宗核心长老 |
| **功法** | 天玄真经 |
| **武器** | 幽冥剑（剑鞘黑色，剑柄有暗色宝石） |

## 外貌特征

| 属性 | 描述 |
|------|------|
| **身高** | 约178cm |
| **体型** | 高大威严，战士体型 |
| **发型** | 灰白长发，束成中式高髻（fa ji） |
| **瞳色** | 深绿色，锐利凝视 |
| **皮肤** | 古铜肤色 |
| **表情** | 平静面容，眼神阴鸷（平静下隐藏阴狠） |

## 衣着服饰

| 场景 | 服饰描述 |
|------|----------|
| **日常** | 玄色礼服外层，暗纹内衬，道袍风格 |
| **战斗** | 黑色战甲 |
| **监视** | 深色斗篷 |

## 性格气质

| 属性 | 描述 |
|------|------|
| **核心** | 表面公正，实则阴险（伪善型反派） |
| **表现** | 站姿挺拔如松，维持长老威严 |
| **情感** | 对天玄子绝对忠诚 |
| **任务** | 执行天玄子命令，追杀韩林 |

## 标志性动作

- **阴谋时**：手指轻抚剑柄，思索诡计
- **出手时**：眼神阴鸷，毫不留情
- **得意时**：嘴角勾起一抹冷笑

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
35mm film photography, high ISO, grain texture, authentic RAW photo,
character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,

subject: a real 45-year-old East Asian male actor, 178cm height, tall dignified build, realistic human anatomy with natural muscle definition, bronze tan skin with natural texture, slight imperfections,

facial features: gray-white hair tied in chinese-style topknot with flyaway strands, dark green irises with realistic intricate iris textures (no glowing effect), sharp sinister gaze, slight facial imperfections,

attire: layered black daopao with subtle cloud embroidery in dark gray, inner garment in deep indigo visible at collar, jade pendant with tianxuan sect symbol, leather sword belt with sheathed sword, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks,

views (from left to right):
1. strict front view, standing straight for a screen test,
2. 3/4 front view facing right,
3. strict profile view facing right,
4. full back view showing the hair texture and robe's tailoring,

technical details: shot on ARRI Alexa, 50mm lens, f/2.8, sharp focus on skin texture, realistic subsurface scattering, natural soft lighting from a high-angle studio lamp,

background: pure seamless white paper backdrop, absolute blank background, zero digital artifacts, totally clean background
```

### 负面提示词

```
3d render, CGI, unreal engine, video game character, avatar, doll, plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched, glowing eyes, glowing effect, supernatural glow, magical particles, magic aura, anime, illustration, drawing, painting, sketch, hyperrealistic, character reference sheet, turnaround sheet, grid layout, multiple views collage, text, words, letters, signature, watermark, logo, symbols, annotations, half body, waist up, portrait, headshot, missing legs, cropped, amputated, multiple different people, duplicates, bad anatomy, deformed limbs, mutation, poorly drawn face, disproportionate body, cross-eyed, 15-year-old appearance, 16-year-old appearance, minor, messy background, busy background, scenery, floor lines
```

### 分视角生成策略

| 视角 | 生成指令 | 说明 |
|------|---------|------|
| 正面 | front view, facing camera | 面部表情（阴狠藏于平静）、五官 |
| 侧面 | strict profile view, facing left | 发型（灰白高髻）、侧脸轮廓、身材 |
| 3/4侧 | 3/4 view, facing right | 综合展现，重要参考角度 |
| 背面 | back view | 发型背面、黑袍背面 |

**重要提示**：
1. 需分4次独立生成，每次固定seed确保一致性
2. "阴狠"通过**眼神和表情张力**而非外露特征表现

### 幽冥剑详细描述

```
幽冥剑:
- 剑鞘：黑色皮质，刻有幽冥纹路
- 剑柄：黑色，镶嵌暗色宝石（深紫色）
- 剑身：出鞘时剑气为灰白色
- 长度：约三尺七寸
```

## 视觉参考ID索引

| 场景ID | 视觉参考文件 | 章节 |
|--------|--------------|------|
| v01_ch003_柳家大厅 | `visual_reference/scenes/v01_ch003_柳家大厅.md` | 第3章 |
| v01_ch004_竞技场 | `visual_reference/scenes/v01_ch004_竞技场.md` | 第4章 |
| v01_ch008_后山悬崖 | `visual_reference/scenes/v01_ch008_后山悬崖.md` | 第8章 |
