#!/usr/bin/env python3
"""
AI短剧提示词生成器 - 基于Jinja2模板
固化Prompt生成逻辑，确保格式一致性

用法:
    python prompts/templates_generator.py character --name lin_yi --state normal
    python prompts/templates_generator.py scene --name mine_entrance
    python prompts/templates_generator.py episode --episode 1
    python prompts/templates_generator.py all --project "穿越古代修仙"
"""

import argparse
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ============================================================
# 模板路径
# ============================================================

TEMPLATE_DIR = Path(__file__).parent / "templates"
CHAR_TEMPLATE_DIR = TEMPLATE_DIR / "character"
SCENE_TEMPLATE_DIR = TEMPLATE_DIR / "scene"

# ============================================================
# Jinja2 环境
# ============================================================

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True,
)

# ============================================================
# 负面提示词库
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
# 角色数据类
# ============================================================

@dataclass
class CharacterState:
    """角色状态数据"""
    name: str
    name_en: str
    age: int
    height: str
    height_awakened: Optional[str] = None
    gender: str = "male"
    build: str = ""
    anatomy: str = "natural proportions"
    skin: str = ""
    hair: str = ""
    eyes: str = ""
    eyes_description: str = ""
    gaze: str = ""
    expression: str = ""
    expression_state: str = ""
    special: str = ""
    attire: str = ""
    attire_details: str = ""
    attire_visible: str = ""
    view_front: str = "standing straight"
    view_34: str = "right"
    view_profile: str = "right"
    view_back: str = "worn clothing"
    view_side: str = "right"
    detail_1: str = ""
    detail_2: str = ""
    view_4: str = ""
    lens: int = 50
    aperture: str = "2.8"
    focus: str = "skin texture"
    lighting: str = ""
    atmosphere: str = "dramatic"
    facial_description: str = ""
    eye_state: str = ""
    energy: Optional[str] = None


@dataclass
class Character:
    """完整角色数据"""
    id: str
    states: Dict[str, CharacterState] = field(default_factory=dict)
    
    def get_state(self, state_name: str = "default") -> CharacterState:
        if state_name not in self.states:
            raise ValueError(f"Unknown state: {state_name} for character {self.id}")
        return self.states[state_name]


@dataclass
class SceneData:
    """场景数据"""
    id: str
    name: str
    name_en: str
    shot_type: str = "wide"
    location: str = ""
    location_real: str = ""
    environment: List[str] = field(default_factory=list)
    main_subject: str = ""
    subject_type: str = "monument"
    # 场景模板中没有人物，人物在角色提示词中单独定义
    character_action: str = ""
    lighting: List[str] = field(default_factory=list)
    composition: str = ""
    atmosphere: str = "dramatic"
    template: str = "scene_base"


# ============================================================
# 角色模板渲染
# ============================================================

def render_character(
    char_state: CharacterState,
    template_name: str = "character/character_base.j2",
    include_negative: bool = True
) -> str:
    """渲染角色提示词"""
    template = env.get_template(template_name)
    
    data = asdict(char_state)
    data["negative_prompt"] = CHARACTER_NEGATIVE if include_negative else ""
    
    # 特殊处理觉醒状态的眼睛描述
    if "awakened" in template_name or char_state.energy:
        data["eyes_description"] = char_state.eyes_description or f"eyes with {char_state.eyes} glow"
    
    return template.render(**data)


def render_character_closeup(
    char_state: CharacterState,
    template_name: str = "character/closeup.j2"
) -> str:
    """渲染角色特写提示词"""
    template = env.get_template(template_name)
    
    data = asdict(char_state)
    data["negative_prompt"] = CHARACTER_NEGATIVE
    
    return template.render(**data)


# ============================================================
# 场景模板渲染
# ============================================================

def render_scene(
    scene: SceneData,
    template_name: Optional[str] = None
) -> str:
    """渲染场景提示词"""
    template_name = template_name or f"scene/{scene.template}.j2"
    template = env.get_template(template_name)
    
    data = asdict(scene)
    data["location"] = f"{scene.location} as a real {scene.location_real}" if scene.location_real else scene.location
    data["negative_prompt"] = SCENE_NEGATIVE
    
    return template.render(**data)


# ============================================================
# 内置角色和场景库
# ============================================================

CHARACTERS: Dict[str, Character] = {
    "lin_yi": Character(
        id="lin_yi",
        states={
            "normal": CharacterState(
                name="林逸", name_en="Lin Yi", age=15, height="165cm", gender="male",
                build="lean but wiry build from manual labor",
                anatomy="natural muscle definition",
                skin="slightly rough skin with small calluses on hands, pale complexion",
                hair="messy short black hair with dust particles",
                eyes="dark brown",
                gaze="determined gaze",
                expression="tired but resilient expression, clean forehead showing youth",
                special="slight dark circles under eyes",
                attire="worn and torn coarse brown miner's clothing",
                attire_details="patched linen shirt with frayed edges, simple leather belt, torn pants with dirt stains, worn straw sandals",
                lighting="natural dim lighting from mine tunnel lamp",
                view_front="standing with hands at sides",
            ),
            "awakened": CharacterState(
                name="林逸", name_en="Lin Yi", age=15, height="175cm", gender="male",
                build="lean athletic build with subtle blue energy lines along muscle contours",
                anatomy="natural proportions with faint luminous blue energy",
                skin="pale skin with ethereal blue light emanating from within",
                hair="short black hair slightly floating as if underwater",
                eyes="pale purple-blue",
                eyes_description="eyes glowing with intense pale purple-blue iris (realistic human texture, no cartoon glow)",
                gaze="cold fierce determined gaze",
                expression="shocked amazed expression",
                special="third eye area with faint blue glow, blue luminescent lines visible on forehead",
                attire="worn brown miner's clothes with blue spiritual energy swirling around body",
                attire_details="tattered cloth and hair flowing dramatically without wind, faint blue rune-like patterns on skin",
                lighting="blue volumetric lighting from within body, dramatic chiaroscuro lighting",
                view_front="standing, blue energy radiating",
                view_34="showing energy lines on arms",
                view_back="showing energy emanating from spine",
                energy="blue spiritual energy",
            ),
            "asleep": CharacterState(
                name="林逸", name_en="Lin Yi", age=15, height="165cm", gender="male",
                build="thin pale build lying on simple cot",
                anatomy="natural proportions visible under thin blanket",
                skin="pale complexion from blood loss",
                hair="short black hair spread on pillow",
                eyes="closed",
                eye_state="eyes tightly shut with furrowed brows",
                gaze="unconscious",
                expression="slack features, slightly parted lips",
                special="stress lines on forehead even in sleep",
                attire_visible="simple white medical gown, visible bandaged forearm",
                view_front="lying flat on back",
                view_side="right",
                detail_1="bandaged arm",
                detail_2="pale face",
                view_4="back view on pillow",
                lens=50, aperture="2.8", focus="facial features",
                lighting="soft morning light from window",
                atmosphere="peaceful",
            ),
            "shocked": CharacterState(
                name="林逸", name_en="Lin Yi", age=15, height="165cm", gender="male",
                build="lean wiry build, sitting up abruptly",
                skin="pale complexion, sweat on forehead",
                hair="short black hair disheveled",
                eyes="wide open",
                eye_state="pupils dilated, eyes wide with terror",
                gaze="shocked stare",
                expression="cold sweat on temples and forehead, trembling slightly",
                special="sweat beads on forehead and temples",
                attire_visible="worn brown miner's shirt, visible collarbone",
                view_front="eyes wide with terror",
                view_side="left",
                detail_1="sweat on temple",
                detail_2="open mouth",
                view_4="front view showing chest heaving",
                lens=85, aperture="2.0", focus="eyes and sweat",
                lighting="harsh practical lamp lighting creating dramatic shadows",
                atmosphere="tense",
            ),
            "sect_disciple": CharacterState(
                name="林逸", name_en="Lin Yi", age=15, height="168cm", gender="male",
                build="lean wiry build",
                anatomy="natural proportions",
                skin="clean healthy complexion",
                hair="neat black hair tied at back",
                eyes="dark brown",
                gaze="curious gaze",
                expression="slight nervous smile, determined expression",
                special="fresh clean face",
                attire="new sect disciple robes in fire-red and black",
                attire_details="simple leather belt, cloth shoes, jade pendant at waist",
                view_front="standing straight with hands at sides",
                view_34="showing new robes",
                view_profile="showing hair tie",
                view_back="showing robe back",
                lens=50, aperture="2.8", focus="clean robes",
                lighting="bright natural lighting suggesting morning sun",
                atmosphere="hopeful",
            ),
        }
    ),
    "sun_bo": Character(
        id="sun_bo",
        states={
            "default": CharacterState(
                name="孙伯", name_en="Sun Bo", age=70, height="160cm", gender="male",
                build="hunched posture from age, frail thin build",
                anatomy="weathered wrinkled skin",
                skin="weathered wise face with deep wrinkles",
                hair="white hair balding at temples, white beard stubble on chin",
                eyes="dark brown",
                gaze="warm compassionate eyes with crow's feet",
                expression="kind gentle smile, missing few back teeth visible",
                special="decades of hardship visible on face",
                attire="worn grey cloth robe with patches",
                attire_details="simple cloth shoes, aged wooden walking cane in left hand",
                view_front="standing with cane, gentle smile",
                view_34="showing hunched posture",
                view_profile="showing white hair",
                view_back="showing robe condition and cane",
                lens=50, aperture="2.8", focus="facial expression",
                lighting="warm golden hour lighting suggesting morning mist",
                atmosphere="nostalgic",
            ),
        }
    ),
    "yun_cang": Character(
        id="yun_cang",
        states={
            "default": CharacterState(
                name="云苍", name_en="Yun Cang", age=70, height="175cm", gender="male",
                build="dignified slender build, ethereal presence",
                anatomy="weathered wise skin showing great age",
                skin="high forehead, weathered wise expression",
                hair="white hair in topknot with jade pin, full white beard",
                eyes="dark brown",
                gaze="penetrating wise eyes with slight smile",
                expression="serene dignified expression",
                special="imposing cultivator aura",
                attire="pristine white silk robe embroidered with subtle silver constellations",
                attire_details="white cloth wraps, white fabric shoes, traditional jade ornaments",
                view_front="serene standing pose",
                view_34="showing robe embroidery",
                view_profile="showing beard and hair",
                view_back="showing robe drape",
                lens=50, aperture="2.8", focus="dignified expression",
                lighting="soft warm studio lighting",
                atmosphere="majestic",
            ),
        }
    ),
    "su_yao": Character(
        id="su_yao",
        states={
            "default": CharacterState(
                name="苏瑶", name_en="Su Yao", age=16, height="168cm", gender="female",
                build="slender graceful build with elegant posture",
                anatomy="natural proportions",
                skin="flawless pale complexion",
                hair="long silver-white hair cascading past waist in loose waves",
                eyes="large dark blue",
                gaze="cold piercing gaze",
                expression="serene expression with slight enigmatic smile",
                special="high cheekbones, elegant eyebrows",
                attire="flowing water-blue silk gown with subtle silver embroidery",
                attire_details="high collar Chinese style, translucent sash at waist, white jade hair ornament",
                view_front="elegant standing",
                view_34="showing dress flow",
                view_profile="showing silver hair",
                view_back="showing hair and garment details",
                lens=85, aperture="1.8", focus="facial features",
                lighting="soft ethereal lighting suggesting white glow, shallow depth of field, dreamy bokeh",
                atmosphere="mysterious",
            ),
        }
    ),
    "chen_yulou": Character(
        id="chen_yulou",
        states={
            "default": CharacterState(
                name="陈玉楼", name_en="Chen Yulou", age=17, height="180cm", gender="male",
                build="tall athletic build, handsome proud features",
                anatomy="natural proportions",
                skin="fair complexion",
                hair="neat black hair with side swept bangs",
                eyes="dark brown",
                gaze="arrogant smirk",
                expression="confident smirk, thick eyebrows",
                special="strong jawline, sharp angular features",
                attire="fire-red sect robes with gold trim",
                attire_details="high rank insignia, leather boots, weapon at side",
                view_front="arrogant pose with hands clasped",
                view_34="showing robes",
                view_profile="showing smirk",
                view_back="showing weapon",
                lens=50, aperture="2.8", focus="arrogant expression",
                lighting="warm fire-light suggesting flames",
                atmosphere="intense",
            ),
            "fire_attack": CharacterState(
                name="陈玉楼", name_en="Chen Yulou", age=17, height="180cm", gender="male",
                build="athletic build with hands thrust forward",
                anatomy="natural proportions",
                skin="slight tan",
                hair="neat black hair, sweat on brow",
                eyes="dark brown",
                gaze="intense determined expression, eyes locked on target",
                expression="mouth set in confident smirk, furrowed brows",
                special="flames swirling around fists",
                attire="fire-red sect robes billowing from attack",
                attire_details="gold trim catching flame light",
                view_front="both hands forward with flames",
                view_34="showing robes billowing",
                view_profile="showing attack stance",
                view_back="showing fire trail",
                lens=50, aperture="2.8", focus="flames",
                lighting="orange-red fire lighting on face, dramatic",
                atmosphere="intense",
            ),
        }
    ),
    "su_youwei": Character(
        id="su_youwei",
        states={
            "default": CharacterState(
                name="苏幼薇", name_en="Su Youwei", age=15, height="165cm", gender="female",
                build="slender delicate build, mysterious cold beauty",
                anatomy="natural proportions",
                skin="porcelain pale complexion",
                hair="long black hair flowing past waist",
                eyes="pale lavender-purple",
                gaze="cold aloof expression",
                expression="cold aloof, dark circles suggesting insomnia",
                special="elegant features",
                attire="elegant dark purple silk gown with silver embroidery",
                attire_details="high collar, translucent layers",
                view_front="cold expression",
                view_34="showing hair flow",
                view_profile="showing purple eyes",
                view_back="showing garment detail",
                lens=85, aperture="1.8", focus="eyes",
                lighting="cool studio lighting, shallow depth of field",
                atmosphere="mysterious",
            ),
        }
    ),
    "lao_zhou": Character(
        id="lao_zhou",
        states={
            "default": CharacterState(
                name="老周", name_en="Lao Zhou", age=45, height="175cm", gender="male",
                build="stocky muscular build from physical labor",
                anatomy="natural proportions",
                skin="weathered face showing exhaustion and worry",
                hair="unkempt dark hair",
                eyes="tired red-rimmed eyes",
                gaze="worried bloodshot eyes",
                expression="grim expression, heavy brow, deep nasolabial folds",
                special="stubborn beard",
                attire="dirty dark blue worker's uniform",
                attire_details="oil stains on fabric, work boots caked in mine dust",
                view_front="standing with hands clasped nervously",
                view_34="showing work uniform",
                view_profile="showing tired face",
                view_back="showing dusty clothing",
                lens=50, aperture="2.8", focus="facial expression",
                lighting="harsh overhead fluorescent lighting",
                atmosphere="tense",
            ),
        }
    ),
}


SCENES: Dict[str, SceneData] = {
    "mine_dormitory": SceneData(
        id="mine_dormitory",
        name="矿山宿舍",
        name_en="Mine Dormitory",
        shot_type="interior",
        location="collapsed mine dormitory as a real underground cave dwelling",
        environment=[
            "rough hewn stone walls with water stains and mineral deposits",
            "crude wooden bed frame with rope lashing, thin straw mattress",
            "single oil lamp on rough wooden table providing warm flicker",
            "mining tools piled in corner, pickaxes and baskets",
            "small window letting in faint grey dawn light",
        ],
        main_subject="cramped underground shelter, roughly 15 square meters, earthen floor",
        subject_type="space",
            lighting=[
            "dim oil lamp providing warm orange point source",
            "cold blue pre-dawn light seeping through cracks",
            "high contrast between lamp glow and dark corners",
            "visible dust motes in light beams",
            "oppressive damp atmosphere",
        ],
        composition="wide shot showing cramped living conditions and interior layout",
        atmosphere="oppressive",
        template="interior",
    ),
    "linyuan_town_street": SceneData(
        id="linyuan_town_street",
        name="临渊镇街道",
        name_en="Linyuan Town Street",
        shot_type="wide",
        location="ancient Chinese mountain town street as a real UNESCO heritage village",
        environment=[
            "narrow flagstone path covered in morning dew",
            "weathered wooden shop fronts with hand-painted signs",
            "crumbling stone walls with moss and lichen",
            "morning mist hanging low, limiting visibility to 20 meters",
            "distant mine entrance visible as dark silhouette on hillside",
        ],
        main_subject="cobblestone lane barely wide enough for two people",
        subject_type="street",
            lighting=[
            "soft golden morning sun filtering through mist",
            "cool blue shadows in shop doorways",
            "warm backlight creating silhouettes",
            "mist creating soft volumetric atmosphere",
            "early morning quiet, no people yet",
        ],
        composition="wide establishing shot looking down the misty street",
        atmosphere="peaceful",
    ),
    "mine_entrance": SceneData(
        id="mine_entrance",
        name="矿山入口",
        name_en="Mine Entrance",
        shot_type="wide",
        location="mine tunnel entrance as a real historical mining site",
        environment=[
            "black granite mountain face with dark cave mouth",
            "rough timber support frame at entrance, weathered and ancient",
            "scattered ore carts on rusted tracks, mine equipment piled nearby",
            "dark mine tunnel disappearing into the mountain",
        ],
        main_subject="gaping dark opening 3 meters high, cold air flowing out",
        subject_type="entrance",
            lighting=[
            "flat grey overcast sky, no sun visible",
            "cold ambient light with no direction",
            "dark entrance creating ominous black void",
            "dark cave mouth looming ahead",
            "oppressive atmosphere, sense of impending danger",
        ],
        composition="wide shot showing scale of the mine entrance",
        atmosphere="oppressive",
    ),
    "sect_medical": SceneData(
        id="sect_medical",
        name="矿区医务室",
        name_en="Mine Medical Station",
        shot_type="interior",
        location="mine site medical station as a real rural clinic",
        environment=[
            "whitewashed concrete walls with yellowed patches",
            "simple metal frame hospital bed with thin mattress",
            "rusted metal IV stand beside bed",
            "small window with grimy glass letting in grey light",
            "worn wooden floor with scuff marks",
        ],
        main_subject="sparse medical room, approximately 20 square meters",
        subject_type="space",
            lighting=[
            "flat grey ambient light from window",
            "no warm light sources, cold clinical feeling",
            "high contrast shadows in corners",
            "sense of abandonment and neglect",
            "quiet except for distant machinery",
        ],
        composition="medium shot showing medical equipment and interior",
        atmosphere="clinical",
        template="interior",
    ),
    "mine_dusk": SceneData(
        id="mine_dusk",
        name="矿区黄昏",
        name_en="Mine at Dusk",
        shot_type="wide",
        location="mine site at dusk as a real industrial zone",
        environment=[
            "setting sun creating orange red sky",
            "black mine headframes silhouetted against sunset",
            "rusted ore carts on tracks",
            "workers heading home in distance",
            "low industrial buildings",
        ],
        main_subject="sprawling mine complex at shift change",
        subject_type="site",
            lighting=[
            "warm orange sunset backlighting",
            "long shadows stretching across ground",
            "dust particles in evening air",
            "industrial sounds fading",
            "oppressive grey atmosphere mixed with sunset warmth",
        ],
        composition="wide establishing shot showing scale of the mining complex",
        atmosphere="melancholic",
    ),
    "collapsed_mine": SceneData(
        id="collapsed_mine",
        name="矿区废墟",
        name_en="Collapsed Mine",
        shot_type="wide",
        location="collapsed mine tunnel as a real underground cavern after cave-in",
        environment=[
            "massive granite boulders blocking passage",
            "broken wooden support beams scattered",
            "dust and debris covering everything",
            "single shaft of morning light piercing through gap",
            "mining tools partially buried",
        ],
        main_subject="chaotic destruction, sense of recent disaster",
        subject_type="space",
            lighting=[
            "dramatic shaft of light through rubble",
            "deep shadows in corners",
            "dust motes visible in light beam",
            "cold air in cave",
            "aftermath of tragedy",
        ],
        composition="wide shot showing destruction and debris",
        atmosphere="dramatic",
    ),
    "spirit_abyss": SceneData(
        id="spirit_abyss",
        name="灵渊裂隙",
        name_en="Spirit Abyss",
        shot_type="wide",
        location="mystical void space as a real dimensional rift",
        environment=[
            "void of infinite darkness with no visible boundaries",
            "golden spiritual energy flowing like rivers in air",
            "dark purple-black malevolent energy coiling",
            "ancient runes floating in space",
            "sense of vast depth and cosmic scale",
        ],
        main_subject="portal between realms, ancient and powerful",
        subject_type="rift",
            lighting=[
            "golden light from spiritual energy",
            "purple-black darkness surrounding",
            "swirling energy patterns",
            "cosmic mysterious atmosphere",
            "deafening silence",
        ],
        composition="wide shot showing cosmic scale",
        atmosphere="cosmic",
    ),
    "xingchen_academy": SceneData(
        id="xingchen_academy",
        name="星辰学院",
        name_en="Xingchen Academy",
        shot_type="wide",
        location="grand immortal sect mountain compound as a real ancient Chinese architecture",
        environment=[
            "three thousand white marble steps leading up",
            "massive stone platform at summit",
            "ornate carved stone pillars supporting curved roof",
            "jade-green roof tiles with gold trim",
            "clouds swirling around mountain peak",
        ],
        main_subject="imposing magnificent cultivation academy",
        subject_type="sect",
            lighting=[
            "golden morning sunlight, sun behind peaks",
            "long shadows across steps",
            "morning mist around base",
            "warm gold on stone, cool blue in shadows",
            "epic grand atmosphere",
        ],
        composition="low angle looking up at entrance",
        atmosphere="epic",
        template="architecture",
    ),
    "academy_main_hall": SceneData(
        id="academy_main_hall",
        name="星辰学院主殿",
        name_en="Academy Main Hall",
        shot_type="wide",
        location="grand immortal sect main hall as a real ancient Chinese palace",
        environment=[
            "massive wooden hall with curved roof",
            "white marble floor stretching expanse",
            "bronze incense burners flanking entrance",
            "silk banners hanging from ceiling",
            "disciples in rows practicing",
        ],
        main_subject="imposing center of academy",
        subject_type="hall",
            lighting=[
            "bright morning sun from windows",
            "long shadows from pillars",
            "warm golden light inside",
            "incense smoke visible in light beams",
            "serious disciplined atmosphere",
        ],
        composition="wide shot showing grand scale",
        atmosphere="disciplined",
        template="architecture",
    ),
    "east_dormitory": SceneData(
        id="east_dormitory",
        name="东苑宿舍",
        name_en="East Dormitory",
        shot_type="medium",
        location="sect disciple quarters as a real traditional Chinese courtyard",
        environment=[
            "small courtyard with ancient scholar tree",
            "simple stone bench under tree",
            "white wall with grey tile roof",
            "bamboo groves in corner",
            "peaceful quiet setting",
        ],
        main_subject="humble simple dwelling",
        subject_type="quarters",
            lighting=[
            "afternoon golden sunlight",
            "tree shadows creating patterns",
            "warm peaceful atmosphere",
            "bamboo rustling in breeze",
            "solitude contemplation",
        ],
        composition="medium shot showing peaceful corner",
        atmosphere="peaceful",
    ),
    "spirit_bamboo_forest": SceneData(
        id="spirit_bamboo_forest",
        name="灵竹林",
        name_en="Spirit Bamboo Forest",
        shot_type="wide",
        location="spirit bamboo grove as a real ancient bamboo forest",
        environment=[
            "tall bamboo stalks 20 meters high",
            "pale blue-green luminescence on bamboo",
            "moonlight filtering through canopy",
            "fallen bamboo leaves on ground",
            "ancient stone marker half-hidden",
        ],
        main_subject="cultivation sacred ground",
        subject_type="grove",
            lighting=[
            "silver moonlight",
            "blue-green bioluminescent glow",
            "cool mysterious atmosphere",
            "silent except wind",
            "spiritual energy present",
        ],
        composition="wide shot showing towering bamboo",
        atmosphere="mysterious",
    ),
    "ranking_arena": SceneData(
        id="ranking_arena",
        name="排位赛广场",
        name_en="Ranking Arena",
        shot_type="wide",
        location="sect arena as a real ancient Chinese fighting arena",
        environment=[
            "circular stone platform raised 2 meters",
            "stone steps leading up on all sides",
            "disciples seated on tiered stone benches",
            "colored banners flying from poles",
            "sect elders on elevated platform",
        ],
        main_subject="center of competition",
        subject_type="arena",
            lighting=[
            "bright afternoon sun overhead",
            "harsh shadows on stone",
            "energetic atmosphere",
            "distant sounds of end shift",
            "anticipation tension",
        ],
        composition="wide shot showing circular arena",
        atmosphere="intense",
        template="architecture",
    ),
    "battle_platform": SceneData(
        id="battle_platform",
        name="擂台战斗",
        name_en="Battle Platform",
        shot_type="medium",
        location="arena combat platform as a real stone fighting stage",
        environment=[
            "cracked stone platform from battle damage",
            "combat arena prepared for duel",
            "fire and blue light clashing in center",
            "tiered seating empty and waiting",
            "dust being kicked up from impacts",
        ],
        main_subject="battlefield",
        subject_type="stage",
            lighting=[
            "fire orange light clashing with blue",
            "dramatic shadows",
            "energy crackling in air",
            "tense frozen moment",
            "epic battle atmosphere",
        ],
        composition="medium shot showing clash",
        atmosphere="dramatic",
    ),
}


# ============================================================
# CLI 接口
# ============================================================

def list_available():
    """列出所有可用的角色和场景"""
    print("\n📋 可用角色:")
    for char_id, char in CHARACTERS.items():
        states = ", ".join(char.states.keys())
        print(f"  - {char_id}: {char.states[list(char.states.keys())[0]].name} ({states})")

    print("\n🎬 可用场景:")
    for scene_id, scene in SCENES.items():
        print(f"  - {scene_id}: {scene.name}")


def generate_character(
    name: str,
    state: str = "default",
    template: str = "character/character_base.j2",
    output: Optional[str] = None
) -> str:
    """生成角色提示词"""
    char = CHARACTERS.get(name)
    if not char:
        raise ValueError(f"Unknown character: {name}")
    
    char_state = char.get_state(state)
    prompt = render_character(char_state, template)
    
    if output:
        Path(output).write_text(prompt)
        print(f"✅ 已保存到: {output}")
    
    return prompt


def generate_scene(
    name: str,
    output: Optional[str] = None
) -> str:
    """生成场景提示词"""
    scene = SCENES.get(name)
    if not scene:
        raise ValueError(f"Unknown scene: {name}")
    
    prompt = render_scene(scene)
    
    if output:
        Path(output).write_text(prompt)
        print(f"✅ 已保存到: {output}")
    
    return prompt


def generate_episode_prompts(
    episode: int,
    project_dir: Path,
    output_format: str = "md"
) -> Dict[str, Path]:
    """生成整集的提示词文件"""
    # 根据剧集确定需要的角色和场景
    if episode == 1:
        chars = [
            ("lin_yi", "normal", "日常矿工"),
            ("lin_yi", "asleep", "沉睡"),
            ("lin_yi", "shocked", "惊醒"),
            ("sun_bo", "default", "孙伯"),
        ]
        scenes = [
            ("mine_dormitory", "矿山宿舍"),
            ("linyuan_town_street", "临渊镇街道"),
            ("mine_entrance", "矿山入口"),
        ]
    elif episode == 2:
        chars = [
            ("lin_yi", "asleep", "昏迷"),
            ("lin_yi", "awakened", "蓝光爆发"),
            ("lao_zhou", "default", "老周"),
        ]
        scenes = [
            ("sect_medical", "医务室"),
            ("mine_dusk", "矿区黄昏"),
        ]
    elif episode == 3:
        chars = [
            ("lin_yi", "awakened", "蓝光觉醒"),
            ("yun_cang", "default", "云苍"),
            ("su_yao", "default", "苏瑶"),
        ]
        scenes = [
            ("collapsed_mine", "矿区废墟"),
            ("spirit_abyss", "灵渊裂隙"),
            ("xingchen_academy", "星辰学院"),
        ]
    elif episode == 4:
        chars = [
            ("lin_yi", "sect_disciple", "学院新生"),
            ("su_youwei", "default", "苏幼薇"),
            ("chen_yulou", "default", "陈玉楼"),
        ]
        scenes = [
            ("academy_main_hall", "星辰学院主殿"),
            ("east_dormitory", "东苑宿舍"),
            ("spirit_bamboo_forest", "灵竹林"),
        ]
    elif episode == 5:
        chars = [
            ("lin_yi", "awakened", "蓝光觉醒"),
            ("chen_yulou", "fire_attack", "火球攻击"),
        ]
        scenes = [
            ("ranking_arena", "排位赛广场"),
            ("battle_platform", "擂台战斗"),
        ]
    else:
        raise ValueError(f"Unknown episode: {episode}")
    
    # 创建输出目录
    episode_dir = project_dir / f"第{episode}集"
    episode_dir.mkdir(parents=True, exist_ok=True)
    
    outputs = {}
    
    # 生成角色提示词
    char_prompts = []
    for char_id, state, desc in chars:
        prompt = generate_character(char_id, state)
        char_prompts.append(f"## {desc}\n\n{prompt}\n")
    
    char_file = episode_dir / "角色Prompt.md"
    char_file.write_text("\n".join(char_prompts))
    outputs["角色Prompt.md"] = char_file
    
    # 生成场景提示词
    scene_prompts = []
    for scene_id, desc in scenes:
        prompt = generate_scene(scene_id)
        scene_prompts.append(f"## {desc}\n\n{prompt}\n")
    
    scene_file = episode_dir / "场景Prompt.md"
    scene_file.write_text("\n".join(scene_prompts))
    outputs["场景Prompt.md"] = scene_file
    
    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="AI短剧提示词生成器 - 基于Jinja2模板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有可用角色和场景
  python templates_generator.py --list
  
  # 生成角色提示词
  python templates_generator.py character --name lin_yi --state normal
  
  # 生成场景提示词
  python templates_generator.py scene --name mine_entrance
  
  # 生成整集提示词
  python templates_generator.py episode --episode 1 --project "穿越古代修仙"
  
  # 生成所有集
  python templates_generator.py all --project "穿越古代修仙"
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true", help="列出所有可用角色和场景")
    
    subparsers = parser.add_subparsers(dest="type", help="生成类型")
    
    # character 子命令
    char_parser = subparsers.add_parser("character", help="生成角色提示词")
    char_parser.add_argument("--name", "-n", required=True, help="角色ID")
    char_parser.add_argument("--state", "-s", default="default", help="角色状态")
    char_parser.add_argument("--template", "-t", default="character/character_base.j2", help="模板文件")
    char_parser.add_argument("--output", "-o", help="输出文件")
    
    # scene 子命令
    scene_parser = subparsers.add_parser("scene", help="生成场景提示词")
    scene_parser.add_argument("--name", "-n", required=True, help="场景ID")
    scene_parser.add_argument("--output", "-o", help="输出文件")
    
    # episode 子命令
    ep_parser = subparsers.add_parser("episode", help="生成整集提示词")
    ep_parser.add_argument("--episode", "-e", type=int, required=True, help="集数")
    ep_parser.add_argument("--project", "-p", default=".", help="项目目录")
    
    # all 子命令
    all_parser = subparsers.add_parser("all", help="生成所有集的提示词")
    all_parser.add_argument("--project", "-p", default=".", help="项目目录")
    
    args = parser.parse_args()
    
    if args.list:
        list_available()
        return
    
    if not args.type:
        parser.print_help()
        list_available()
        return
    
    if args.type == "character":
        prompt = generate_character(args.name, args.state, args.template, args.output)
        if not args.output:
            print(prompt)
    
    elif args.type == "scene":
        prompt = generate_scene(args.name, args.output)
        if not args.output:
            print(prompt)
    
    elif args.type == "episode":
        project_dir = Path(args.project)
        outputs = generate_episode_prompts(args.episode, project_dir)
        print(f"\n✅ 第{args.episode}集提示词已生成:")
        for name, path in outputs.items():
            print(f"  - {path}")
    
    elif args.type == "all":
        project_dir = Path(args.project)
        for ep in range(1, 6):
            outputs = generate_episode_prompts(ep, project_dir)
            print(f"✅ 第{ep}集完成")


if __name__ == "__main__":
    main()