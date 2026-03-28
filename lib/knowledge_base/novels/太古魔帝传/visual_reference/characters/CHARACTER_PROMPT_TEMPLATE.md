# 角色AI绘图提示词模板

> 本模板定义了角色视觉参考的标准结构，用于AI视频生成和角色一致性管理。
>
> **重要更新 (2026-03-24)**: 本模板采用**摄影写实**风格，参考ARRI Alexa拍摄效果，通过引入真实摄影的缺陷感（毛孔、颗粒、飞发）来打破AI模型的"3D动漫感"和"CG假脸"问题。

## 核心策略

1. **禁用"actor"替代cultivator** — 锚定真人感
2. **具体相机型号** — ARRI Alexa, Sony A1, Canon R5 等比泛泛的"35mm"更有效
3. **禁用"glowing"** — 即使是"subtly glowing"也可能触发CGI感，用"faint pattern"替代
4. **保持年龄18+** — 避免审核问题
5. **禁用分段** — 提示词放在一起，不要按视角分段落

---

## 正向提示词模板（单段落）

```
35mm film photography, high ISO, grain texture, authentic RAW photo,
character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,

subject: a real {age}-year-old East Asian {gender} actor, {height}, {body_type}, realistic human anatomy with natural muscle definition, {skin_description} with visible pores and subtle veins,

facial features: {hairstyle_description} with flyaway strands, {eye_description} with realistic intricate iris textures (no glowing effect), {expression}, slight facial imperfections,

attire: {clothing_description}, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks,

views (from left to right):
1. strict front view, standing straight for a screen test,
2. 3/4 front view facing right,
3. strict profile view facing right,
4. full back view showing the hair texture and robe's tailoring,

technical details: shot on ARRI Alexa, 50mm lens, f/2.8, sharp focus on skin texture, realistic subsurface scattering, natural soft lighting from a high-angle studio lamp,

background: pure seamless white paper backdrop, absolute blank background, zero digital artifacts, totally clean background
```

## 四视角分述提示词（用于参考）

如需分4次独立生成，使用以下分述（但在生成脚本中使用单段落版本）：

**1. 正面 (Front View)**
strict front view, standing straight for a screen test

**2. 3/4侧面 (3/4 View)**
3/4 front view facing right, showcasing slender silhouette

**3. 侧面像 (Profile View)**
strict profile view facing right, highlighting posture and silhouette

**4. 背面 (Back View)**
full back view showing the hair texture and robe's tailoring

## 负面提示词

```
3d render, CGI, unreal engine, video game character, avatar, doll,
plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched,
glowing eyes, glowing effect, supernatural glow, magical particles, magic aura,
anime, illustration, drawing, painting, sketch, hyperrealistic,
character reference sheet, turnaround sheet, grid layout, multiple views collage,
text, words, letters, signature, watermark, logo, symbols, annotations,
half body, waist up, portrait, headshot, missing legs, cropped, amputated,
multiple different people, duplicates, bad anatomy, deformed limbs, mutation,
poorly drawn face, disproportionate body, cross-eyed,
15-year-old appearance, 16-year-old appearance, minor,
messy background, busy background, scenery, floor lines, shadows on the background,
any digital pattern
```

---

## 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `age` | 年龄（建议18+避免审核） | 18, 20, 25 |
| `gender` | 性别 | male, female |
| `height` | 身高 | 175cm, 165cm |
| `body_type` | 体型描述 | lean athletic build, slender lean figure |
| `skin_description` | 皮肤描述（带真实感） | pale skin with slight imperfections, fair skin with natural texture |
| `hairstyle_description` | 发型描述（带飞发） | black hair in high ponytail with flyaway hairs |
| `eye_description` | 眼睛描述（禁用glow） | pale purple eyes, icy-blue eyes |
| `forehead_feature` | 额头特征（可选） | clean forehead, subtle faint golden pattern |
| `clothing_description` | 服装描述（物理特性） | heavy linen and textured silk period costume in black and purple |

---

## 场景提示词

场景提示词模板已移至 `SCENE_PROMPT_TEMPLATE.md`

---

## 使用说明

1. **始终使用单段落提示词** — 不要按视角分段落，整个提示词放在一起
2. **四视角信息合并在末尾** — views (from left to right): 1. strict front view... 2. 3/4 front view... 3. strict profile view... 4. full back view...
3. **禁用 Character Reference Sheet** — 这种格式会触发CGI偏向
4. **所有眼睛描述必须加"no glowing effect"** — 即使角色本身有特殊瞳色
5. **服装必须描述面料物理特性** — "weathered fabric, micro-folds and realistic dust, visible stitching and weaving patterns"
6. **加入飞发、毛孔等微小瑕疵** — 这是打破3D感的关键
7. **使用50mm f/2.8标准人像参数** — 替代之前的85mm f/1.8
