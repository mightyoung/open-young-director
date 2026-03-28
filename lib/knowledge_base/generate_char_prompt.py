#!/usr/bin/env python3
import sys
sys.path.insert(0, 'lib/knowledge_base')
from pathlib import Path

# Load .env
for _env_path in [
    Path('lib/knowledge_base/.env'),
    Path('.env'),
]:
    if _env_path.exists():
        for line in _env_path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                import os
                os.environ.setdefault(k.strip(), v.strip())

from llm.doubao_client import DoubaoClient

client = DoubaoClient()

prompt = """为仙侠小说《太古魔帝传》中的角色赵元启，按照以下模板格式生成完整的角色AI绘图提示词文件内容。

## 已知角色设定：
- 赵元启，23岁男性
- 身份：世家子弟，太虚宗弟子
- 性格：倨傲张扬、仗势欺人、飞扬跋扈
- 外貌：面如冠玉、眼尾微挑、高挺鼻梁、薄唇
- 发型：墨色长发用羊脂玉冠束起
- 服装：绣暗云银纹玄色锦袍，腰系镶和田白玉鎏金腰带
- 常有动作：单手负于身后，另一手把玩腰间玉佩
- 表情：下颌微抬，嘴角常带嘲讽嗤笑，眼神满是不屑
- 武器：青云剑（家传）

## 请按照以下模板格式生成完整内容：

# 角色：赵元启（第一卷）

> **visual_ref**: `v01_zhaoyuanqi.md`
> **章节引用**: ch001, ch002
> **一致性来源**: 角色视觉参考是视频生成和播客制作的唯一真实来源

## 基本信息

| 属性 | 描述 |
|------|------|
| **修为** | 炼气巅峰 |
| **身份** | 赵家嫡子，太虚宗内门弟子 |
| **武器** | 青云剑（家传） |

## 外貌特征

| 属性 | 描述 |
|------|------|
| **身高** | 约180cm |
| **体型** | 挺拔高大，肩宽腰细 |
| **发型** | 墨色长发用羊脂玉冠整齐束起 |
| **瞳色** | 深墨色 |
| **皮肤** | 白皙无瑕 |
| **表情** | 倨傲张扬，下颌常微抬 |

## 衣着服饰

| 场景 | 服饰描述 |
|------|----------|
| **测灵大典** | 绣暗云银纹玄色锦袍，鎏金玉腰带 |
| **日常** | 玄色长袍，束金冠 |
| **战斗** | 玄青战甲，暗纹护肩 |

## 性格气质

| 属性 | 描述 |
|------|------|
| **核心** | 倨傲张扬，仗势欺人 |
| **表现** | 飞扬跋扈，目中无人 |
| **情感** | 对柳如烟有倾慕之意 |

## 标志性动作

- **挑衅时**：单手负于身后，另一手把玩腰间玉佩
- **嘲讽时**：下颌微抬，嘴角勾起嗤笑
- **战斗时**：剑指对方，气势凌人

## AI绘图提示词

### 正向提示词（摄影写实风格，单段落）

```
35mm film photography, high ISO, grain texture, authentic RAW photo,
character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,

subject: a real 23-year-old East Asian male actor, 180cm height, tall athletic build with broad shoulders and narrow waist, realistic human anatomy with natural muscle definition, fair skin with natural texture, slight imperfections,

facial features: jet black hair neatly tied in a topknot secured with a white jade hair crown, flyaway strands at temples, deep black eyes with realistic intricate iris textures (no glowing effect), arrogant expression with slightly raised chin, thin lips with a hint of disdainful smile, slight facial imperfections,

attire: heavy textured silk period costume in black with subtle silver cloud pattern embroidery, gold jade belt at waist with white jade pendant, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks,

views (from left to right):
1. strict front view, standing straight for a screen test,
2. 3/4 front view facing right,
3. strict profile view facing right,
4. full back view showing the hair texture and robe's tailoring,

technical details: shot on ARRI Alexa, 50mm lens, f/2.8, sharp focus on skin texture, realistic subsurface scattering, natural soft lighting from a high-angle studio lamp,

background: pure seamless white paper backdrop, absolute blank background, zero digital artifacts, totally clean background
```

### 场景提示词

**测灵大典场景**
```
RAW photo, shot on ARRI Alexa, 85mm lens, f/1.8, high ISO film grain, 23-year-old East Asian male actor, full body, wearing heavy textured silk period costume in black with subtle silver cloud embroidery, gold jade belt with white jade pendant, tall athletic build, arrogant expression with slightly raised chin, standing on elevated platform俯瞰众人, grand hall background with jade pillars, dramatic lighting from above, sharp focus, depth of field, skin oiliness, flyaway hairs, skin texture imperfections, 8k, photorealistic, cinematic, masterpiece
```

**挑衅韩林场景**
```
RAW photo, shot on ARRI Alexa, 50mm lens, f/2.8, high ISO film grain, 23-year-old East Asian male actor, full body, wearing绣暗云银纹玄色锦袍, one hand behind back, the other hand twirling jade pendant at waist, arrogant smirk, chin raised slightly, standing before a young cultivator in plain robes, outdoor martial arts arena at dawn, golden morning mist, dramatic side lighting, sharp focus, depth of field, skin oiliness, flyaway hairs, skin texture imperfections, 8k, photorealistic, cinematic, masterpiece
```

### 负面提示词

```
3d render, CGI, unreal engine, video game character, avatar, doll, plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched, glowing eyes, glowing effect, supernatural glow, magical particles, magic aura, anime, illustration, drawing, painting, sketch, hyperrealistic, character reference sheet, turnaround sheet, grid layout, multiple views collage, text, words, letters, signature, watermark, logo, symbols, annotations, half body, waist up, portrait, headshot, missing legs, cropped, amputated, multiple different people, duplicates, bad anatomy, deformed limbs, mutation, poorly drawn face, disproportionate body, cross-eyed, 15-year-old appearance, 16-year-old appearance, minor, messy background, busy background, scenery, floor lines
```

---

请根据以上设定，填充完整的内容。输出完整可用的角色文件Markdown内容。"""

result = client.generate(prompt=prompt, temperature=0.7, max_tokens=3000)
print(result)
print("\n\n---FULL FILE CONTENT ABOVE---\n")
print("To save: redirect to char_zhaoyuanqi.md")