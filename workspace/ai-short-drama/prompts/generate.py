#!/usr/bin/env python3
"""
AI短剧视频提示词生成器 - 主程序

标准化生成人物与场景的提示词

使用方式:
    python generate.py list                              # 列出所有可用
    python generate.py character --id lin_yi --state normal   # 生成角色
    python generate.py scene --id mine_awakening             # 生成场景
    python generate.py combined --character lin_yi --scene power_burst  # 组合
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

# ============================================================
# 路径配置
# ============================================================

SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
CHARACTERS_OUTPUT = OUTPUT_DIR / "characters"
SCENES_OUTPUT = OUTPUT_DIR / "scenes"

# 创建输出目录
for d in [OUTPUT_DIR, CHARACTERS_OUTPUT, SCENES_OUTPUT]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================
# 数据定义
# ============================================================

@dataclass
class CharacterState:
    """角色状态"""
    description: str
    build: str
    skin: str
    hair: str
    eyes: str
    expression: str
    special: str
    attire: str
    attire_details: str
    lighting: str
    lens: int = 50
    aperture: str = "f/2.8"
    focus: str = "skin texture"
    energy: Optional[str] = None


@dataclass
class Character:
    """角色定义"""
    id: str
    name_zh: str
    name_en: str
    default_age: int
    height: str
    height_awakened: Optional[str] = None
    gender: str = "male"
    states: Dict[str, CharacterState] = field(default_factory=dict)


@dataclass
class Scene:
    """场景定义"""
    id: str
    name_zh: str
    name_en: str
    location: str
    reference: str
    environment: List[str]
    main_subject: str
    character_action: str
    lighting: List[str]
    composition: str
    mood: str


# ============================================================
# 角色数据库
# ============================================================

CHARACTERS: Dict[str, Character] = {
    "lin_yi": Character(
        id="lin_yi",
        name_zh="林逸",
        name_en="Lin Yi",
        default_age=15,
        height="165cm",
        height_awakened="175cm",
        gender="male",
        states={
            "normal": CharacterState(
                description="矿工少年，普通状态",
                build="lean but wiry build from manual labor",
                skin="slightly rough skin with small calluses on hands",
                hair="messy short black hair with dust particles",
                eyes="dark brown irises with determined gaze",
                expression="tired but resilient expression",
                special="slight dark circles under eyes",
                attire="worn and torn coarse brown miner's clothing",
                attire_details="patched linen shirt with frayed edges, simple leather belt, torn pants with dirt stains, worn straw sandals",
                lighting="natural dim lighting from mine tunnel lamp",
            ),
            "awakened": CharacterState(
                description="力量觉醒状态",
                build="lean athletic build radiating subtle blue glow",
                skin="pale skin with ethereal blue light emanating from within",
                hair="short black hair slightly floating as if underwater",
                eyes="eyes glowing with intense pale purple-blue iris (still realistic human texture, no cartoon glow)",
                expression="cold fierce determined expression",
                special="third eye area with faint blue glow",
                attire="same worn brown clothes but with blue spiritual energy swirling around body",
                attire_details="tattered cloth and hair flowing dramatically without wind, faint blue rune-like patterns appearing on skin",
                lighting="blue volumetric lighting from within, dramatic chiaroscuro lighting, smoke effects",
                energy="blue spiritual energy",
            ),
        },
    ),
    "yun_qiluo": Character(
        id="yun_qiluo",
        name_zh="云绮罗",
        name_en="Yun Qiluo",
        default_age=18,
        height="168cm",
        gender="female",
        states={
            "default": CharacterState(
                description="云霄宗仙女",
                build="slender graceful build with elegant posture",
                skin="flawless porcelain-like pale skin",
                hair="long black hair flowing past waist in loose waves",
                eyes="large dark brown eyes with cold piercing gaze",
                expression="serene expression with slight smile",
                special="high cheekbones, elegant eyebrows",
                attire="flowing pure white silk gown with subtle silver embroidery",
                attire_details="high collar Chinese style, sheer white sash at waist, translucent fabric layers, white jade hair ornament with pearl",
                lighting="soft ethereal lighting suggesting white glow, shallow depth of field, dreamy bokeh",
                lens=85,
                aperture="f/1.8",
                focus="facial features",
                energy="white ethereal glow",
            ),
        },
    ),
    "su_yao": Character(
        id="su_yao",
        name_zh="苏瑶",
        name_en="Su Yao",
        default_age=16,
        height="163cm",
        gender="female",
        states={
            "default": CharacterState(
                description="风系天才少女",
                build="slim athletic build with graceful movement",
                skin="fresh youthful complexion with rosy cheeks",
                hair="shoulder-length black hair with wind-swept styling",
                eyes="bright lively eyes in warm brown irises",
                expression="cheerful smile revealing small dimples",
                special="small jade earrings",
                attire="light mint green and white Chinese period dress",
                attire_details="flowing skirt, fitted jacket with cloud patterns, silk sash, green jade bracelet",
                lighting="natural outdoor lighting with soft green tones, wind effects on hair and clothing",
                energy="gentle wind energy",
            ),
        },
    ),
    "li_tianyang": Character(
        id="li_tianyang",
        name_zh="李天阳",
        name_en="Li Tianyang",
        default_age=20,
        height="180cm",
        gender="male",
        states={
            "default": CharacterState(
                description="世家子弟",
                build="well-built muscular athletic physique",
                skin="fair skin with aristocratic complexion",
                hair="styled black hair with expensive jade hairpiece",
                eyes="sharp cold eyes in dark brown irises",
                expression="arrogant contemptuous expression",
                special="slightly thin lips showing disdain",
                attire="luxurious purple and gold brocade robes",
                attire_details="high collar martial arts tunic, ornate jade belt buckle, expensive leather boots, sword with gold hilts",
                lighting="dramatic side lighting creating contrast, rich warm tones",
                lens=85,
                energy=None,
            ),
        },
    ),
    "mu_feng": Character(
        id="mu_feng",
        name_zh="沐风",
        name_en="Mu Feng",
        default_age=16,
        height="172cm",
        gender="male",
        states={
            "default": CharacterState(
                description="火系热血少年",
                build="athletic build with broad chest",
                skin="warm-toned skin with slight tan",
                hair="short messy red-tinged black hair suggesting fire affinity",
                eyes="bright enthusiastic eyes in amber irises",
                expression="big cheerful grin showing slightly crooked teeth",
                special="small burn scar on cheek from training",
                attire="practical red and orange fitted martial arts tunic",
                attire_details="leather bracers on forearms, simple but quality dark red pants, fire element embroidery on collar",
                lighting="warm orange-red lighting suggesting fire energy",
                energy="warm fire energy",
            ),
        },
    ),
    "ye_qing": Character(
        id="ye_qing",
        name_zh="叶青",
        name_en="Ye Qing",
        default_age=17,
        height="175cm",
        gender="male",
        states={
            "default": CharacterState(
                description="水系冷静谋士",
                build="slim lean build with elegant composure",
                skin="pale cool-toned skin",
                hair="long black hair tied in high neat bun with blue jade ornament",
                eyes="calm calculating eyes in deep blue-black irises",
                expression="serene expression barely showing emotion",
                special="thin lips",
                attire="refined blue and silver Chinese robes with water wave patterns",
                attire_details="high collar with silver embroidery, flowing sleeves, blue jade pendant, elegant leather shoes",
                lighting="cool blue-toned lighting suggesting water element",
                lens=85,
                aperture="f/1.8",
                focus="facial features",
                energy="cool water energy",
            ),
        },
    ),
}


# ============================================================
# 场景数据库
# ============================================================

SCENES: Dict[str, Scene] = {
    "mine_awakening": Scene(
        id="mine_awakening",
        name_zh="矿道觉醒",
        name_en="Mine Awakening",
        location="collapsed mine tunnel as a real underground cavern",
        reference="real volcanic cave with mineral deposits",
        environment=[
            "narrow mine shaft carved from dark granite rock, rough hewn walls with tool marks",
            "ancient wooden support beams showing age and decay, some broken and hanging",
            "damp walls glistening with moisture, puddles reflecting dim light",
            "narrow passage barely wide enough for one person, oppressive claustrophobic atmosphere",
        ],
        main_subject="massive deep blue luminescent crystal embedded in cave wall, pulsing with ethereal blue inner light illuminating the entire tunnel",
        character_action="15-year-old boy in torn brown clothes pressed against crystal, face illuminated by blue glow, arms spread as if absorbing energy, hair floating upward",
        lighting=[
            "intense blue bioluminescent glow emanating from crystal",
            "single oil lamp on ground casting warm orange flicker",
            "blue and orange contrast creating dramatic tension",
            "volumetric light rays piercing through cave darkness",
            "dust particles visible in light beams",
        ],
        composition="low-angle shot looking up at crystal from below, boy's silhouette against blue glow, dramatic scale comparison between small human and enormous crystal",
        mood="dramatic, mysterious, tension",
    ),
    "cave_mystery": Scene(
        id="cave_mystery",
        name_zh="灵渊秘境",
        name_en="Spirit Abyss",
        location="ancient temple ruins hidden in misty mountain valley",
        reference="Tang Dynasty ruins overgrown with vegetation",
        environment=[
            "crumbling stone walls covered in thick moss and vine overgrowth",
            "collapsed pagoda roof with broken tiles scattered on ground",
            "weathered stone steps leading up to temple entrance, cracked and uneven",
            "twisted ancient pine trees growing from rock crevices, thick white mist covering valley",
        ],
        main_subject="massive stone archway carved with eroded ancient runes, partially hidden by mist, mysterious darkness beyond",
        character_action="15-year-old boy in simple worn robes standing at temple threshold, small jade pendant in hand glowing faintly, looking into darkness ahead with calm determination",
        lighting=[
            "cold blue-grey morning light filtering through mist",
            "no direct sunlight, overcast diffuse lighting",
            "purple-black darkness emanating from temple interior",
            "subtle ethereal glow from boy's jade pendant",
            "thick volumetric mist creating depth layers",
        ],
        composition="medium shot from inside temple looking out, misty valley behind boy, sense of entering unknown realm",
        mood="mysterious, eerie, foreboding",
    ),
    "sect_entrance": Scene(
        id="sect_entrance",
        name_zh="云霄宗山门",
        name_en="Sect Entrance",
        location="majestic fairy sect mountain peak",
        reference="real World Heritage mountain temple complex",
        environment=[
            "three thousand wide white marble steps carved from natural stone, mineral veins visible, slight weathering",
            "massive stone platform on mountain peak, ancient masonry with moss in crevices",
            "ornate carved stone pillars supporting curved roof, Tang Dynasty architectural style",
            "jade-green roof tiles with gold trim, weathered naturally, mountain backdrop with low-hanging clouds",
        ],
        main_subject="grand hall with towering walls extending into clouds, multiple tiers of traditional architecture built into mountain face",
        character_action="small figure in worn clothes standing at bottom of steps looking up, tiny human before massive structure, sense of overwhelming scale",
        lighting=[
            "early morning golden hour, sun low behind mountain peaks",
            "golden sunlight casting long dramatic shadows across steps",
            "natural morning mist swirling around mountain base",
            "warm gold tones on stone, cool blue tones in shadows",
            "no magical particles or glow effects",
        ],
        composition="low-angle from below steps looking up at grand hall entrance, overwhelming scale, crowds as tiny dots",
        mood="epic, awe-inspiring, grand",
    ),
    "martial_arena": Scene(
        id="martial_arena",
        name_zh="宗门大比",
        name_en="Martial Arena",
        location="outdoor martial arts arena",
        reference="real ancient Chinese coliseum",
        environment=[
            "elevated circular stone platform, 30 meters diameter, weathered granite surface",
            "carved stone railings surrounding arena, dragon motifs",
            "tiered stone seating rising up like amphitheater, thousands of seated figures",
            "tall flagpoles at arena corners with flowing banners, mountain backdrop",
        ],
        main_subject="two young men facing each other on platform center, one in cheap worn clothes, one in luxurious purple robes, tension charged between them",
        character_action="worn-clothes youth standing with martial stance facing wealthy opponent, weapons drawn, crowd watching intensely",
        lighting=[
            "late afternoon sun casting dramatic side lighting",
            "dust particles visible in light beams",
            "warm golden tones, slight orange cast",
            "tension visible in still air",
            "no magical effects",
        ],
        composition="high angle aerial shot looking down at arena, both fighters visible in center, crowd creating circular pattern",
        mood="intense, dramatic, epic",
    ),
    "power_burst": Scene(
        id="power_burst",
        name_zh="力量爆发",
        name_en="Power Burst",
        location="martial arts arena at peak action",
        reference="ruined ancient arena after battle",
        environment=[
            "stone platform now cracked and damaged from battle",
            "debris and broken stone fragments scattered across arena floor",
            "scorch marks and blast craters visible",
            "one fighter thrown backward through air, dust explosion all around",
        ],
        main_subject="young man standing with arm extended, fist glowing with intense blue-white energy, not cartoon glow but realistic light emanation",
        character_action="hair and clothes flowing dramatically from energy release, fierce determination in eyes, loser flying backward with shocked expression",
        lighting=[
            "intense blue-white light emanating from victor",
            "purple-gold residual light from defeated techniques",
            "dust explosion all around arena",
            "dramatic rim lighting on victor from backlight",
            "particles kicked up by energy blast",
        ],
        composition="low-angle close-up on victor's face and extended fist, energy burst in foreground, loser in background, motion blur on debris",
        mood="epic, intense, dramatic",
    ),
    "team_gathering": Scene(
        id="team_gathering",
        name_zh="三人小队集结",
        name_en="Team Gathering",
        location="mountain cliff edge at sunset",
        reference="real Himalayan peaks at golden hour",
        environment=[
            "rocky cliff overlooking vast mountain valley",
            "dramatic peaks disappearing into orange sunset clouds",
            "small twisted pine growing from cliff face",
            "scattered ancient ruins suggesting ancient civilization, mist forming in valley below",
        ],
        main_subject="three young people standing together on cliff edge, shoulder to shoulder, unity visible in poses, wind blowing clothes and hair gently",
        character_action="one boy calm and determined, one girl with bright smile, one boy with enthusiastic grin, all looking at distant mountains with resolve",
        lighting=[
            "dramatic sunset, orange and purple sky gradient",
            "golden rim lighting on figures from setting sun",
            "long shadows stretching across cliff",
            "cool blue shadows with warm highlights",
            "peaceful yet determined mood",
        ],
        composition="medium shot from behind showing silhouettes against sunset sky, valley below, dramatic mountain backdrop",
        mood="adventure, hope, unity",
    ),
    "dark_cave": Scene(
        id="dark_cave",
        name_zh="暗影洞穴",
        name_en="Dark Cave",
        location="dark underground cave",
        reference="real volcanic lava tube cave",
        environment=[
            "massive cave chamber, ceiling invisible in darkness above",
            "ancient stone pillars carved with eroded demonic figures",
            "pools of still black water reflecting nothing",
            "broken chains hanging from walls, ash and char marks covering surfaces",
        ],
        main_subject="oppressive darkness that seems alive, deeper parts with unnatural purple-black tint, faint whispers echoing",
        character_action="15-year-old boy standing firm despite fear, hand on ancient pillar for support, pale face but determined expression, jade pendant glowing slightly as protection",
        lighting=[
            "single torch in boy's hand casting flickering warm light",
            "darkness pushing back against torch light",
            "purple-black shadows in peripheral vision",
            "cold blue mist rising from water pools",
            "sounds of dripping water echoing, sense of evil presence not seen but felt",
        ],
        composition="low-angle shot into cave darkness, boy as small figure of light against vast evil, ominous atmosphere",
        mood="horror, tension, foreboding",
    ),
    "spirit_cave": Scene(
        id="spirit_cave",
        name_zh="秘境洞口",
        name_en="Spirit Cave Entrance",
        location="ancient spirit realm cave entrance hidden in misty mountain cliff",
        reference="real Himalayan cave with mineral deposits",
        environment=[
            "jagged cliff face covered in thick green moss and hanging vines",
            "dark cave mouth framed by weathered stone archway carved with eroded ancient runes",
            "thick white mist flowing continuously from cave interior",
            "twisted ancient pine trees growing horizontally from cliff face",
        ],
        main_subject="mysterious darkness beyond entrance, cold air flowing outward, mysterious purple-blue mist swirling at threshold",
        character_action="young cultivator standing at cave threshold, hand touching carved runes, looking into darkness ahead with calm determination",
        lighting=[
            "cold blue-grey ambient light filtering through mist",
            "no direct sunlight, cave interior in deep shadow",
            "subtle bioluminescent glow from cave depths",
            "thick volumetric mist creating layered depth",
            "cold air condensation visible at cave mouth",
        ],
        composition="medium shot slowly panning across cave entrance, mist flowing outward, sense of unknown danger lurking within",
        mood="mysterious, eerie, foreboding",
    ),
    "sect_hall": Scene(
        id="sect_hall",
        name_zh="宗门大殿",
        name_en="Sect Grand Hall",
        location="grand sect main hall built into mountain peak",
        reference="real World Heritage mountain temple complex, Tang Dynasty architecture",
        environment=[
            "massive wooden hall with curved roof, towering columns carved with dragon motifs",
            "white marble floor polished smooth by centuries of footsteps",
            "ancient bronze incense burners flanking main entrance",
            "silk banners with sect emblems hanging from ceiling",
        ],
        main_subject="imposing grand hall structure dominating entire mountain peak",
        character_action="small figure in worn clothes standing at bottom of steps looking up at towering hall, overwhelmed by scale",
        lighting=[
            "early morning golden sunlight, sun low behind mountains",
            "warm golden rays streaming through hall entrance",
            "long dramatic shadows cast by columns",
            "dust particles visible in light beams",
            "cool blue tones in shadow areas",
        ],
        composition="low angle looking up at hall entrance, sheer scale overwhelming viewer, overwhelming grandeur",
        mood="epic, awe-inspiring, grand",
    ),
    "cultivation_chamber": Scene(
        id="cultivation_chamber",
        name_zh="修炼室",
        name_en="Cultivation Chamber",
        location="ancient underground cultivation chamber inside mountain",
        reference="real Buddhist cave temple with meditation spaces",
        environment=[
            "circular stone chamber carved from solid rock",
            "carved stone platform in center with meditation cushion",
            "walls covered in ancient cultivation diagrams and faded scripture",
            "single shaft of silver moonlight streaming through ceiling opening",
        ],
        main_subject="young cultivator in loose robes seated in meditation posture, energy swirling around body",
        character_action="cultivator sitting cross-legged in deep meditation, subtle energy glow visible, breathing rhythm slow and deep",
        lighting=[
            "cool silver-blue moonlight streaming through opening",
            "no other light sources, deep shadows in corners",
            "subtle cold mist rising from floor",
            "gentle shadows, meditative silence",
            "shallow depth of field, cultivator in sharp focus",
        ],
        composition="medium shot through doorway as natural frame, cultivator centered in moonlight, peaceful ethereal atmosphere",
        mood="ethereal, peaceful, mysterious",
    ),
    "ancient_battlefield": Scene(
        id="ancient_battlefield",
        name_zh="古战场遗迹",
        name_en="Ancient Battlefield",
        location="ancient battlefield ruins after great war",
        reference="real historical battlefield site with archaeological remains",
        environment=[
            "vast plain covered in broken weapons and shattered armor fragments",
            "cracked earth showing ancient spiritual energy blast damage",
            "remnants of stone fortifications overgrown with weeds",
            "scattered ancient wooden stakes and bamboo spike traps",
        ],
        main_subject="evidence of massive spirit beast battle, lingering resentment in air",
        character_action="small figure picking up ancient broken sword, examining battlefield with grim determination",
        lighting=[
            "dark purple overcast sky, ominous light",
            "no direct sunlight, oppressive atmosphere",
            "purple-black shadows hiding details",
            "wind picking up dust and debris",
            "sense of lingering resentment",
        ],
        composition="aerial shot showing scale of battlefield, broken weapons pattern, vast desolation",
        mood="dark, foreboding, somber",
    ),
    "underwater_ruins": Scene(
        id="underwater_ruins",
        name_zh="水底遗迹",
        name_en="Underwater Ruins",
        location="ancient underwater temple ruins",
        reference="real underwater archaeological site, Atlantean architecture",
        environment=[
            "collapsed temple structure submerged in deep water",
            "broken stone pillars covered in coral and seaweed",
            "ancient carved statues half-buried in sand",
            "shafts of blue-green light filtering through water",
        ],
        main_subject="forgotten civilization beneath the waves, mysterious architecture",
        character_action="swimmer floating in water, reaching toward ancient artifact, bubbles rising slowly",
        lighting=[
            "cool blue-green underwater light filtering from above",
            "floating particles and plankton in water column",
            "floating silk fabric from ancient banners",
            "gentle current moving debris",
            "profound silence and age",
        ],
        composition="medium shot slowly pushing through ruins, sense of exploration and discovery, blue-green color grade",
        mood="mysterious, serene, ancient",
    ),
    "tribulation_lightning": Scene(
        id="tribulation_lightning",
        name_zh="天劫雷云",
        name_en="Tribulation Lightning",
        location="mountain peak during cultivation tribulation",
        reference="real supercell thunderstorm with frequent lightning",
        environment=[
            "massive dark thunderclouds swirling in vortex formation",
            "multiple lightning bolts striking mountain peak",
            "ancient stone cultivation platform cracked and glowing",
            "surrounding trees stripped of bark by spiritual energy",
        ],
        main_subject="terrifying natural spiritual energy, tribulation lightning descending",
        character_action="solitary cultivator standing on peak, arms raised toward sky, receiving lightning tribulation",
        lighting=[
            "brilliant white flashes illuminating everything",
            "constant rumble echoing across mountains",
            "purple-white lightning contrast against dark clouds",
            "rain and wind whipping debris",
            "oppressive dread filling the air",
        ],
        composition="low angle looking up at lightning vortex, small figure on peak dwarfed by storm, dramatic scale",
        mood="epic, terrifying, intense",
    ),
    "blessed_cave": Scene(
        id="blessed_cave",
        name_zh="洞府福地",
        name_en="Blessed Cave Dwelling",
        location="blessed cultivation cave dwelling in mountain",
        reference="real natural cave with waterfall, mountainous terrain",
        environment=[
            "small stone cave dwelling furnished with bamboo and wood",
            "hand-carved stone bed and desk",
            "small waterfall outside cave creating mist",
            "spirit herb garden growing near entrance",
        ],
        main_subject="humble but peaceful dwelling, natural blessed location",
        character_action="cultivator tending spirit herbs near waterfall, peaceful daily life scene",
        lighting=[
            "warm golden morning sunlight through waterfall mist",
            "light refracting through waterfall mist creating rainbows",
            "gentle rainbow colors in spray",
            "birds singing outside cave",
            "warm cool contrast between sun and shade",
        ],
        composition="medium shot panning through cave dwelling, peaceful atmosphere, warm golden tones",
        mood="peaceful, warm, hopeful",
    ),
    "illusion_maze": Scene(
        id="illusion_maze",
        name_zh="幻境迷阵",
        name_en="Illusion Formation",
        location="illusion formation trapping cultivator",
        reference="real optical illusion art installation, surrealist artwork",
        environment=[
            "same scene repeating infinitely in all directions",
            "reality flickering between two states",
            "floating ethereal mist distorting reflections",
            "ghostly afterimages following movement",
        ],
        main_subject="impossible geometry, conflicting realities, trapped consciousness",
        character_action="disoriented cultivator reaching toward reflection that moves differently, confused expression",
        lighting=[
            "cold blue-white ethereal light without source",
            "colors shifting between warm and cold",
            "sense of disorientation",
            "time feeling distorted",
            "unsettling calm",
        ],
        composition="close-up on disoriented face, everything else blurred and distorted, surreal atmosphere",
        mood="mysterious, unsettling, surreal",
    ),
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
cross-eyed, minor appearance, 15-year-old if older needed"""

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
# 生成器类
# ============================================================

class CharacterPromptGenerator:
    """角色提示词生成器"""

    def generate(
        self,
        character_id: str,
        state: str = "default",
        age: Optional[int] = None,
        save: bool = False,
    ) -> str:
        """生成角色提示词"""
        char = CHARACTERS.get(character_id)
        if not char:
            raise ValueError(f"Unknown character: {character_id}")

        state_data = char.states.get(state)
        if not state_data:
            raise ValueError(f"Unknown state '{state}' for character '{character_id}'")

        actual_age = age or char.default_age
        actual_height = char.height_awakened if state == "awakened" else char.height

        # 构建提示词
        prompt = self._build_prompt(
            char=char,
            state=state_data,
            age=actual_age,
            height=actual_height,
        )

        # 保存
        if save:
            output_path = CHARACTERS_OUTPUT / f"{character_id}_{state}.txt"
            output_path.write_text(prompt)
            print(f"✅ 已保存: {output_path}")

        return prompt

    def _build_prompt(
        self,
        char: Character,
        state: CharacterState,
        age: int,
        height: str,
    ) -> str:
        """构建提示词"""
        parts = []

        # 头部
        parts.append(
            "35mm film photography, high ISO, grain texture, authentic RAW photo,\n"
            "character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas,\n"
        )

        # 主体
        parts.append(
            f"subject: a real {age}-year-old East Asian {char.gender} actor, {height} height, "
            f"{state.build}, realistic human anatomy with natural proportions, {state.skin},\n"
        )

        # 面部
        parts.append(
            f"facial features: {state.hair}, {state.eyes}, {state.expression}, {state.special},\n"
        )

        # 服装
        parts.append(f"attire: {state.attire}, {state.attire_details},\n")

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
            f"technical details: shot on ARRI Alexa, {state.lens}mm lens, {state.aperture}, "
            f"sharp focus on {state.focus}, {state.lighting},\n"
        )

        # 背景
        parts.append(
            "background: pure seamless white paper backdrop, absolute blank background, "
            "zero digital artifacts, totally clean background\n\n"
        )

        # 负面
        parts.append(f"negative: {CHARACTER_NEGATIVE}")

        return "".join(parts)

    def list_characters(self) -> List[Dict[str, Any]]:
        """列出所有角色"""
        result = []
        for char_id, char in CHARACTERS.items():
            result.append({
                "id": char.id,
                "name_zh": char.name_zh,
                "name_en": char.name_en,
                "states": list(char.states.keys()),
            })
        return result


class ScenePromptGenerator:
    """场景提示词生成器"""

    def generate(self, scene_id: str, save: bool = False) -> str:
        """生成场景提示词"""
        scene = SCENES.get(scene_id)
        if not scene:
            raise ValueError(f"Unknown scene: {scene_id}")

        prompt = self._build_prompt(scene)

        if save:
            output_path = SCENES_OUTPUT / f"{scene_id}.txt"
            output_path.write_text(prompt)
            print(f"✅ 已保存: {output_path}")

        return prompt

    def _build_prompt(self, scene: Scene) -> str:
        """构建提示词"""
        parts = []

        # 头部
        parts.append(
            "RAW landscape photo, cinematic wide shot, shot on ARRI Alexa, "
            "35mm anamorphic lens, 8k resolution,\n\n"
        )

        # 地点
        parts.append(f"location: {scene.location},\n\n")

        # 环境
        parts.append("environment details:\n")
        for env in scene.environment:
            parts.append(f"- {env},\n")
        parts.append("\n")

        # 主体
        parts.append(f"the subject: {scene.main_subject},\n\n")

        # 人物
        parts.append(f"the youth: {scene.character_action},\n\n")

        # 光线
        parts.append("lighting & atmosphere:\n")
        for light in scene.lighting:
            parts.append(f"- {light},\n")
        parts.append("\n")

        # 构图
        parts.append(f"composition: {scene.composition},\n\n")

        # 技术
        parts.append(
            f"technical: high dynamic range, film grain, {scene.mood} atmosphere, "
            "photorealistic textures\n\n"
        )

        # 负面
        parts.append(f"negative: {SCENE_NEGATIVE}")

        return "".join(parts)

    def list_scenes(self) -> List[Dict[str, Any]]:
        """列出所有场景"""
        result = []
        for scene_id, scene in SCENES.items():
            result.append({
                "id": scene.id,
                "name_zh": scene.name_zh,
                "name_en": scene.name_en,
            })
        return result


# ============================================================
# 主程序
# ============================================================

def cmd_list():
    """列出所有可用选项"""
    char_gen = CharacterPromptGenerator()
    scene_gen = ScenePromptGenerator()

    print("\n📋 可用角色:")
    for char in char_gen.list_characters():
        states = ", ".join(char["states"])
        print(f"  {char['id']:15} {char['name_zh']} ({char['name_en']}) - {states}")

    print("\n🎬 可用场景:")
    for scene in scene_gen.list_scenes():
        print(f"  {scene['id']:15} {scene['name_zh']} ({scene['name_en']})")

    print()


def cmd_character(args):
    """生成角色提示词"""
    gen = CharacterPromptGenerator()
    try:
        prompt = gen.generate(
            character_id=args.id,
            state=args.state,
            age=args.age,
            save=args.save,
        )
        if not args.save:
            print(prompt)
    except ValueError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


def cmd_scene(args):
    """生成场景提示词"""
    gen = ScenePromptGenerator()
    try:
        prompt = gen.generate(
            scene_id=args.id,
            save=args.save,
        )
        if not args.save:
            print(prompt)
    except ValueError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)


def cmd_combined(args):
    """生成组合提示词"""
    char_gen = CharacterPromptGenerator()
    scene_gen = ScenePromptGenerator()

    try:
        char_prompt = char_gen.generate(
            character_id=args.character,
            state=args.char_state,
            age=args.age,
        )
        scene_prompt = scene_gen.generate(scene_id=args.scene)
    except ValueError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

    combined = f"{char_prompt}\n\n---\n\n{scene_prompt}"
    
    if args.save:
        output_path = OUTPUT_DIR / f"combined_{args.character}_{args.scene}.txt"
        output_path.write_text(combined)
        print(f"✅ 已保存: {output_path}")
    else:
        print(combined)


def main():
    parser = argparse.ArgumentParser(
        description="AI短剧视频提示词生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate.py list
  python generate.py character --id lin_yi --state normal
  python generate.py character --id lin_yi --state awakened --save
  python generate.py scene --id mine_awakening
  python generate.py scene --id sect_entrance --save
  python generate.py combined --character lin_yi --scene power_burst
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list 命令
    subparsers.add_parser("list", help="列出所有可用的角色和场景")

    # character 命令
    char_parser = subparsers.add_parser("character", help="生成角色提示词")
    char_parser.add_argument("--id", "-i", required=True, help="角色ID")
    char_parser.add_argument("--state", "-s", default="default", help="角色状态")
    char_parser.add_argument("--age", "-a", type=int, help="覆盖年龄")
    char_parser.add_argument("--save", action="store_true", help="保存到文件")

    # scene 命令
    scene_parser = subparsers.add_parser("scene", help="生成场景提示词")
    scene_parser.add_argument("--id", "-i", required=True, help="场景ID")
    scene_parser.add_argument("--save", action="store_true", help="保存到文件")

    # combined 命令
    comb_parser = subparsers.add_parser("combined", help="生成组合提示词")
    comb_parser.add_argument("--character", "-c", required=True, help="角色ID")
    comb_parser.add_argument("--scene", "-s", required=True, help="场景ID")
    comb_parser.add_argument("--char-state", default="default", help="角色状态")
    comb_parser.add_argument("--age", type=int, help="覆盖年龄")
    comb_parser.add_argument("--save", action="store_true", help="保存到文件")

    args = parser.parse_args()

    if not args.command or args.command == "list":
        cmd_list()
    elif args.command == "character":
        cmd_character(args)
    elif args.command == "scene":
        cmd_scene(args)
    elif args.command == "combined":
        cmd_combined(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
