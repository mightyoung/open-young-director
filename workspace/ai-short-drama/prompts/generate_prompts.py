#!/usr/bin/env python3
"""
AI短剧视频提示词生成器

用法:
    python prompts/generate_prompts.py --type character --name lin_yi --state normal
    python prompts/generate_prompts.py --type character --name lin_yi --state awakened
    python prompts/generate_prompts.py --type scene --name mine_awakening
    python prompts/generate_prompts.py --type scene --name sect_entrance
"""

import argparse
import json
from pathlib import Path
from typing import Optional

# ============================================================
# 角色定义
# ============================================================

CHARACTERS = {
    "lin_yi": {
        "name": "林逸",
        "name_en": "Lin Yi",
        "default_age": 15,
        "height": "165cm",
        "height_awakened": "175cm",
        "gender": "male",
        "states": {
            "normal": {
                "description": "矿工少年，普通状态",
                "build": "lean but wiry build from manual labor",
                "skin": "slightly rough skin with small calluses on hands",
                "hair": "messy short black hair with dust particles",
                "eyes": "dark brown irises with determined gaze",
                "expression": "tired but resilient expression",
                "special": "slight dark circles under eyes",
                "attire": "worn and torn coarse brown miner's clothing",
                "attire_details": "patched linen shirt with frayed edges, simple leather belt, torn pants with dirt stains, worn straw sandals",
                "lighting": "natural dim lighting from mine tunnel lamp",
                "lens": "50mm",
                "aperture": "f/2.8",
                "focus": "skin texture",
                "energy": None,
            },
            "awakened": {
                "description": "力量觉醒状态",
                "build": "lean athletic build radiating subtle blue glow",
                "skin": "pale skin with ethereal blue light emanating from within",
                "hair": "short black hair slightly floating as if underwater",
                "eyes": "eyes glowing with intense pale purple-blue iris (still realistic human texture, no cartoon glow)",
                "expression": "cold fierce determined expression",
                "special": "third eye area with faint blue glow",
                "attire": "same worn brown clothes but with blue spiritual energy swirling around body",
                "attire_details": "tattered cloth and hair flowing dramatically without wind, faint blue rune-like patterns appearing on skin",
                "lighting": "blue volumetric lighting from within, dramatic chiaroscuro lighting, smoke effects",
                "lens": "50mm",
                "aperture": "f/2.8",
                "focus": "character with blue volumetric lighting",
                "energy": "blue spiritual energy",
            },
        },
    },
    "yun_qiluo": {
        "name": "云绮罗",
        "name_en": "Yun Qiluo",
        "default_age": 18,
        "height": "168cm",
        "gender": "female",
        "states": {
            "default": {
                "description": "云霄宗仙女",
                "build": "slender graceful build with elegant posture",
                "skin": "flawless porcelain-like pale skin",
                "hair": "long black hair flowing past waist in loose waves",
                "eyes": "large dark brown eyes with cold piercing gaze",
                "expression": "serene expression with slight smile",
                "special": "high cheekbones, elegant eyebrows",
                "attire": "flowing pure white silk gown with subtle silver embroidery",
                "attire_details": "high collar Chinese style, sheer white sash at waist, translucent fabric layers, white jade hair ornament with pearl",
                "lighting": "soft ethereal lighting suggesting white glow, shallow depth of field, dreamy bokeh",
                "lens": "85mm",
                "aperture": "f/1.8",
                "focus": "facial features",
                "energy": "white ethereal glow",
            },
        },
    },
    "su_yao": {
        "name": "苏瑶",
        "name_en": "Su Yao",
        "default_age": 16,
        "height": "163cm",
        "gender": "female",
        "states": {
            "default": {
                "description": "风系天才少女",
                "build": "slim athletic build with graceful movement",
                "skin": "fresh youthful complexion with rosy cheeks",
                "hair": "shoulder-length black hair with wind-swept styling",
                "eyes": "bright lively eyes in warm brown irises",
                "expression": "cheerful smile revealing small dimples",
                "special": "small jade earrings",
                "attire": "light mint green and white Chinese period dress",
                "attire_details": "flowing skirt, fitted jacket with cloud patterns, silk sash, green jade bracelet",
                "lighting": "natural outdoor lighting with soft green tones, wind effects on hair and clothing",
                "lens": "50mm",
                "aperture": "f/2.8",
                "focus": "skin texture",
                "energy": "gentle wind energy",
            },
        },
    },
    "li_tianyang": {
        "name": "李天阳",
        "name_en": "Li Tianyang",
        "default_age": 20,
        "height": "180cm",
        "gender": "male",
        "states": {
            "default": {
                "description": "世家子弟",
                "build": "well-built muscular athletic physique",
                "skin": "fair skin with aristocratic complexion",
                "hair": "styled black hair with expensive jade hairpiece",
                "eyes": "sharp cold eyes in dark brown irises",
                "expression": "arrogant contemptuous expression",
                "special": "slightly thin lips showing disdain",
                "attire": "luxurious purple and gold brocade robes",
                "attire_details": "high collar martial arts tunic, ornate jade belt buckle, expensive leather boots, sword with gold hilts",
                "lighting": "dramatic side lighting creating contrast, rich warm tones",
                "lens": "85mm",
                "aperture": "f/2.8",
                "focus": "facial features",
                "energy": None,
            },
        },
    },
    "mu_feng": {
        "name": "沐风",
        "name_en": "Mu Feng",
        "default_age": 16,
        "height": "172cm",
        "gender": "male",
        "states": {
            "default": {
                "description": "火系热血少年",
                "build": "athletic build with broad chest",
                "skin": "warm-toned skin with slight tan",
                "hair": "short messy red-tinged black hair suggesting fire affinity",
                "eyes": "bright enthusiastic eyes in amber irises",
                "expression": "big cheerful grin showing slightly crooked teeth",
                "special": "small burn scar on cheek from training",
                "attire": "practical red and orange fitted martial arts tunic",
                "attire_details": "leather bracers on forearms, simple but quality dark red pants, fire element embroidery on collar",
                "lighting": "warm orange-red lighting suggesting fire energy",
                "lens": "50mm",
                "aperture": "f/2.8",
                "focus": "skin texture",
                "energy": "warm fire energy",
            },
        },
    },
    "ye_qing": {
        "name": "叶青",
        "name_en": "Ye Qing",
        "default_age": 17,
        "height": "175cm",
        "gender": "male",
        "states": {
            "default": {
                "description": "水系冷静谋士",
                "build": "slim lean build with elegant composure",
                "skin": "pale cool-toned skin",
                "hair": "long black hair tied in high neat bun with blue jade ornament",
                "eyes": "calm calculating eyes in deep blue-black irises",
                "expression": "serene expression barely showing emotion",
                "special": "thin lips",
                "attire": "refined blue and silver Chinese robes with water wave patterns",
                "attire_details": "high collar with silver embroidery, flowing sleeves, blue jade pendant, elegant leather shoes",
                "lighting": "cool blue-toned lighting suggesting water element",
                "lens": "85mm",
                "aperture": "f/1.8",
                "focus": "facial features",
                "energy": "cool water energy",
            },
        },
    },
}

# ============================================================
# 场景定义
# ============================================================

SCENES = {
    "mine_awakening": {
        "name": "矿道觉醒",
        "name_en": "Mine Awakening",
        "location": "collapsed mine tunnel as a real underground cavern",
        "environment": [
            "narrow mine shaft carved from dark granite rock, rough hewn walls with tool marks",
            "ancient wooden support beams showing age and decay, some broken and hanging",
            "damp walls glistening with moisture, puddles reflecting dim light",
            "narrow passage barely wide enough for one person, oppressive claustrophobic atmosphere",
        ],
        "main_subject": "massive deep blue luminescent crystal embedded in cave wall, pulsing with ethereal blue inner light illuminating the entire tunnel",
        "character_action": "15-year-old boy in torn brown clothes pressed against crystal, face illuminated by blue glow, arms spread as if absorbing energy, hair floating upward",
        "lighting": [
            "intense blue bioluminescent glow emanating from crystal",
            "single oil lamp on ground casting warm orange flicker",
            "blue and orange contrast creating dramatic tension",
            "volumetric light rays piercing through cave darkness",
            "dust particles visible in light beams",
        ],
        "composition": "low-angle shot looking up at crystal from below, boy's silhouette against blue glow, dramatic scale comparison between small human and enormous crystal",
        "mood": "dramatic, mysterious, tension",
    },
    "cave_mystery": {
        "name": "灵渊秘境",
        "name_en": "Spirit Abyss",
        "location": "ancient temple ruins hidden in misty mountain valley",
        "environment": [
            "crumbling stone walls covered in thick moss and vine overgrowth",
            "collapsed pagoda roof with broken tiles scattered on ground",
            "weathered stone steps leading up to temple entrance, cracked and uneven",
            "twisted ancient pine trees growing from rock crevices, thick white mist covering valley",
        ],
        "main_subject": "massive stone archway carved with eroded ancient runes, partially hidden by mist, mysterious darkness beyond",
        "character_action": "15-year-old boy in simple worn robes standing at temple threshold, small jade pendant in hand glowing faintly, looking into darkness ahead with calm determination",
        "lighting": [
            "cold blue-grey morning light filtering through mist",
            "no direct sunlight, overcast diffuse lighting",
            "purple-black darkness emanating from temple interior",
            "subtle ethereal glow from boy's jade pendant",
            "thick volumetric mist creating depth layers",
        ],
        "composition": "medium shot from inside temple looking out, misty valley behind boy, sense of entering unknown realm",
        "mood": "mysterious, eerie, foreboding",
    },
    "sect_entrance": {
        "name": "云霄宗山门",
        "name_en": "Sect Entrance",
        "location": "majestic fairy sect mountain peak as real World Heritage site",
        "environment": [
            "three thousand wide white marble steps carved from natural stone, mineral veins visible, slight weathering",
            "massive stone platform on mountain peak, ancient masonry with moss in crevices",
            "ornate carved stone pillars supporting curved roof, Tang Dynasty architectural style",
            "jade-green roof tiles with gold trim, weathered naturally, mountain backdrop with low-hanging clouds",
        ],
        "main_subject": "grand hall with towering walls extending into clouds, multiple tiers of traditional architecture built into mountain face",
        "character_action": "small figure in worn clothes standing at bottom of steps looking up, tiny human before massive structure, sense of overwhelming scale",
        "lighting": [
            "early morning golden hour, sun low behind mountain peaks",
            "golden sunlight casting long dramatic shadows across steps",
            "natural morning mist swirling around mountain base",
            "warm gold tones on stone, cool blue tones in shadows",
            "no magical particles or glow effects",
        ],
        "composition": "low-angle from below steps looking up at grand hall entrance, overwhelming scale, crowds as tiny dots",
        "mood": "epic, awe-inspiring, grand",
    },
    "martial_arena": {
        "name": "宗门大比",
        "name_en": "Martial Arena",
        "location": "outdoor martial arts arena as real ancient Chinese coliseum",
        "environment": [
            "elevated circular stone platform, 30 meters diameter, weathered granite surface",
            "carved stone railings surrounding arena, dragon motifs",
            "tiered stone seating rising up like amphitheater, thousands of seated figures",
            "tall flagpoles at arena corners with flowing banners, mountain backdrop",
        ],
        "main_subject": "two young men facing each other on platform center, one in cheap worn clothes, one in luxurious purple robes, tension charged between them",
        "character_action": "worn-clothes youth standing with martial stance facing wealthy opponent, weapons drawn, crowd watching intensely",
        "lighting": [
            "late afternoon sun casting dramatic side lighting",
            "dust particles visible in light beams",
            "warm golden tones, slight orange cast",
            "tension visible in still air",
            "no magical effects",
        ],
        "composition": "high angle aerial shot looking down at arena, both fighters visible in center, crowd creating circular pattern",
        "mood": "intense, dramatic, epic",
    },
    "power_burst": {
        "name": "力量爆发",
        "name_en": "Power Burst",
        "location": "martial arts arena, moment of peak action",
        "environment": [
            "stone platform now cracked and damaged from battle",
            "debris and broken stone fragments scattered across arena floor",
            "scorch marks and blast craters visible",
            "one fighter thrown backward through air, dust explosion all around",
        ],
        "main_subject": "young man standing with arm extended, fist glowing with intense blue-white energy, not cartoon glow but realistic light emanation",
        "character_action": "hair and clothes flowing dramatically from energy release, fierce determination in eyes, loser flying backward with shocked expression",
        "lighting": [
            "intense blue-white light emanating from victor",
            "purple-gold residual light from defeated techniques",
            "dust explosion all around arena",
            "dramatic rim lighting on victor from backlight",
            "particles kicked up by energy blast",
        ],
        "composition": "low-angle close-up on victor's face and extended fist, energy burst in foreground, loser in background, motion blur on debris",
        "mood": "epic, intense, dramatic",
    },
    "team_gathering": {
        "name": "三人小队集结",
        "name_en": "Team Gathering",
        "location": "mountain cliff edge at sunset",
        "environment": [
            "rocky cliff overlooking vast mountain valley",
            "dramatic peaks disappearing into orange sunset clouds",
            "small twisted pine growing from cliff face",
            "scattered ancient ruins suggesting ancient civilization, mist forming in valley below",
        ],
        "main_subject": "three young people standing together on cliff edge, shoulder to shoulder, unity visible in poses, wind blowing clothes and hair gently",
        "character_action": "one boy calm and determined, one girl with bright smile, one boy with enthusiastic grin, all looking at distant mountains with resolve",
        "lighting": [
            "dramatic sunset, orange and purple sky gradient",
            "golden rim lighting on figures from setting sun",
            "long shadows stretching across cliff",
            "cool blue shadows with warm highlights",
            "peaceful yet determined mood",
        ],
        "composition": "medium shot from behind showing silhouettes against sunset sky, valley below, dramatic mountain backdrop",
        "mood": "adventure, hope, unity",
    },
    "dark_cave": {
        "name": "暗影洞穴",
        "name_en": "Dark Cave",
        "location": "dark underground cave as real volcanic lava tube",
        "environment": [
            "massive cave chamber, ceiling invisible in darkness above",
            "ancient stone pillars carved with eroded demonic figures",
            "pools of still black water reflecting nothing",
            "broken chains hanging from walls, ash and char marks covering surfaces",
        ],
        "main_subject": "oppressive darkness that seems alive, deeper parts with unnatural purple-black tint, faint whispers echoing",
        "character_action": "15-year-old boy standing firm despite fear, hand on ancient pillar for support, pale face but determined expression, jade pendant glowing slightly as protection",
        "lighting": [
            "single torch in boy's hand casting flickering warm light",
            "darkness pushing back against torch light",
            "purple-black shadows in peripheral vision",
            "cold blue mist rising from water pools",
            "sounds of dripping water echoing, sense of evil presence not seen but felt",
        ],
        "composition": "low-angle shot into cave darkness, boy as small figure of light against vast evil, ominous atmosphere",
        "mood": "horror, tension, foreboding",
    },
}

# ============================================================
# 负面提示词
# ============================================================

CHARACTER_NEGATIVE = """3d render, CGI, unreal engine, video game character, avatar, doll,
plastic skin, porcelain skin, smooth skin, airbrushed, over-retouched,
glowing eyes, glowing effect, supernatural glow, magical particles, magic aura,
anime, illustration, drawing, painting, sketch, hyperrealistic,
character reference sheet, turnaround sheet, grid layout, multiple views,
text, words, letters, signature, watermark, logo, symbols, annotations,
half body, waist up, portrait, headshot, cropped, missing limbs,
duplicates, bad anatomy, deformed, mutation, disproportionate,
cross-eyed"""

SCENE_NEGATIVE = """3d render, CGI, unreal engine, video game scenery, mobile game ad,
fantasy illustration, digital painting, drawing, cartoon, anime style,
magical glow, glowing runes, floating particles, sparkles, neon lights,
digital fire, magic aura, bloom effect,
text, watermark, signature, logo, UI, navigation bar,
clean geometry, plastic textures, flat lighting,
perfectly symmetrical architecture, brand new stone,
blurry foreground, distorted perspective, oversaturated colors,
purple tint, fake mist, 2d elements"""


# ============================================================
# 生成函数
# ============================================================

def generate_character_prompt(
    character_id: str,
    state: str = "default",
    age: Optional[int] = None,
) -> str:
    """生成角色提示词"""
    char = CHARACTERS.get(character_id)
    if not char:
        raise ValueError(f"Unknown character: {character_id}")

    state_data = char["states"].get(state)
    if not state_data:
        raise ValueError(f"Unknown state: {state} for character: {character_id}")

    actual_age = age or char["default_age"]
    actual_height = char.get("height_awakened") if state == "awakened" else char["height"]

    # 构建提示词
    parts = []

    # 头部说明
    parts.append(
        f"35mm film photography, high ISO, grain texture, authentic RAW photo,\n"
        f"character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,\n"
    )

    # 主体描述
    parts.append(
        f"subject: a real {actual_age}-year-old East Asian {char['gender']} actor, {actual_height} height, "
        f"{state_data['build']}, realistic human anatomy with natural proportions, {state_data['skin']},\n"
    )

    # 面部特征
    parts.append(
        f"facial features: {state_data['hair']}, {state_data['eyes']}, {state_data['expression']}, {state_data['special']},\n"
    )

    # 服装
    parts.append(
        f"attire: {state_data['attire']}, {state_data['attire_details']},\n"
    )

    # 四个角度
    parts.append(
        "views (from left to right):\n"
        "1. strict front view, standing straight,\n"
        "2. 3/4 front view facing right,\n"
        "3. strict profile view facing right,\n"
        "4. full back view showing details,\n"
    )

    # 技术参数
    parts.append(
        f"technical details: shot on ARRI Alexa, {state_data['lens']} lens, {state_data['aperture']}, "
        f"sharp focus on {state_data['focus']}, {state_data['lighting']},\n"
    )

    # 背景
    parts.append(
        "background: pure seamless white paper backdrop, absolute blank background, "
        "zero digital artifacts, totally clean background\n\n"
    )

    # 负面提示词
    parts.append(f"negative: {CHARACTER_NEGATIVE}")

    return "".join(parts)


def generate_scene_prompt(scene_id: str) -> str:
    """生成场景提示词"""
    scene = SCENES.get(scene_id)
    if not scene:
        raise ValueError(f"Unknown scene: {scene_id}")

    parts = []

    # 头部说明
    parts.append(
        f"RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, "
        f"35mm anamorphic lens, 8k resolution,\n\n"
    )

    # 地点
    parts.append(f"location: {scene['location']},\n\n")

    # 环境细节
    parts.append("environment details:\n")
    for env in scene["environment"]:
        parts.append(f"- {env},\n")
    parts.append("\n")

    # 主要元素
    parts.append(f"the subject: {scene['main_subject']},\n\n")

    # 人物动作
    parts.append(f"the youth: {scene['character_action']},\n\n")

    # 光线氛围
    parts.append("lighting & atmosphere:\n")
    for light in scene["lighting"]:
        parts.append(f"- {light},\n")
    parts.append("\n")

    # 构图
    parts.append(f"composition: {scene['composition']},\n\n")

    # 技术参数
    parts.append(
        "technical: high dynamic range, film grain, "
        f"{scene['mood']} atmosphere, photorealistic textures\n\n"
    )

    # 负面提示词
    parts.append(f"negative: {SCENE_NEGATIVE}")

    return "".join(parts)


def list_available():
    """列出所有可用的角色和场景"""
    print("\n📋 可用角色:")
    for char_id, char in CHARACTERS.items():
        states = ", ".join(char["states"].keys())
        print(f"  - {char_id}: {char['name']} ({states})")

    print("\n🎬 可用场景:")
    for scene_id, scene in SCENES.items():
        print(f"  - {scene_id}: {scene['name']}")


def main():
    parser = argparse.ArgumentParser(description="AI短剧视频提示词生成器")
    parser.add_argument(
        "--type", "-t",
        choices=["character", "scene"],
        help="生成类型: character 或 scene"
    )
    parser.add_argument(
        "--name", "-n",
        help="角色ID或场景ID"
    )
    parser.add_argument(
        "--state", "-s",
        default="default",
        help="角色状态 (如: normal, awakened)"
    )
    parser.add_argument(
        "--age", "-a",
        type=int,
        help="角色年龄覆盖"
    )
    parser.add_argument(
        "--output", "-o",
        help="输出文件路径"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有可用的角色和场景"
    )

    args = parser.parse_args()

    if args.list:
        list_available()
        return

    if not args.type or not args.name:
        print("请指定 --type 和 --name，或使用 --list 查看可用选项")
        list_available()
        return

    # 生成提示词
    if args.type == "character":
        prompt = generate_character_prompt(args.name, args.state, args.age)
    else:
        prompt = generate_scene_prompt(args.name)

    # 输出
    if args.output:
        Path(args.output).write_text(prompt)
        print(f"✅ 已保存到: {args.output}")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
