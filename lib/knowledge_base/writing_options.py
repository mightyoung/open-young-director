"""Shared writing option presets for CLI, prompt builders, and future UI."""

from typing import Dict, Optional


STYLE_PRESETS = {
    "literary": "偏文学化表达，重氛围、意象和细腻感受。",
    "concise": "表达简洁，段落推进快，信息密度高。",
    "dramatic": "冲突前置，情绪起伏明显，高潮段强调爆发力。",
    "fanren_flow": "参考知识库中的凡人流写法：稳扎稳打、重逻辑与现实感，突出底层成长。",
    "face_slapping": "参考退婚流/打脸流：低谷到反击的节奏鲜明，关键节点强调爽感释放。",
    "cthulhu_mystery": "参考克苏鲁网文写法：神秘感、未知感、层层揭示，理性中带压迫感。",
    "cinematic_youth": "参考《龙族》式电影化青春叙事：镜头感强，场景切换利落，人物带少年气。",
    "epic_rebel": "参考辰东系逆天写法：格局宏大、情绪悲壮、战斗与宿命感并行。",
    "new_wuxia": "参考《雪中悍刀行》式新武侠：烟火气与庙堂江湖并置，人物气口鲜明。",
    "sword_philosophy": "参考《剑来》式剑道流：叙事稳健，兼顾修行思辨、人物成长与人道探讨。",
}

BASE_STYLE_CHOICES = ["literary", "concise", "dramatic"]
STYLE_PRESET_CHOICES = [
    "fanren_flow",
    "face_slapping",
    "cthulhu_mystery",
    "cinematic_youth",
    "epic_rebel",
    "new_wuxia",
    "sword_philosophy",
]

PERSPECTIVE_PRESETS = {
    "third_limited": "第三人称限知，紧贴核心角色感知与判断。",
    "third_omniscient": "第三人称全知，允许必要的全局信息，但避免频繁跳视角。",
    "first_person": "第一人称，强调代入感、主观感受与即时情绪。",
    "dual_perspective": "双视角切换，仅在明确分段时切换，不得混乱。",
    "ensemble": "群像视角，以场景为单位聚焦不同角色，但每段只跟随一个意识中心。",
}

NARRATIVE_MODE_PRESETS = {
    "balanced": "剧情、描写、对白均衡推进。",
    "progressive_upgrade": "强调修炼升级、资源获取、阶段突破的递进感。",
    "low_high_cycle": "采用低谷-蓄力-高潮-回落的网文追更节奏。",
    "multi_line_foreshadowing": "显性情节推进同时埋设暗线与后续伏笔。",
    "character_driven": "由人物欲望、选择与关系变化驱动剧情。",
    "scene_driven": "突出场景调度和事件呈现，保持镜头感和现场感。",
}

PACE_PRESETS = {
    "slow": "节奏从容，给环境、心理和关系变化留出铺陈空间。",
    "medium": "常规商业网文节奏，张弛平衡。",
    "fast": "推进迅速，尽快进入冲突、揭示与转折。",
}

DIALOGUE_DENSITY_PRESETS = {
    "low": "对白克制，以叙述和心理活动为主。",
    "medium": "对白与叙述平衡，用对话推动信息和关系。",
    "high": "对白占比高，句子短促，强调交锋、火花与节奏感。",
}

PROSE_STYLE_PRESETS = {
    "ornate": "修辞更足，句式更有文采，但避免堆砌。",
    "clean": "文字干净克制，少形容词，信息传达明确。",
    "concise_forceful": "简洁有力，短句偏多，适合冲突和打斗。",
    "airy_lyrical": "带诗性和留白，适合情绪、景物和感悟段落。",
}

WORLD_BUILDING_DENSITY_PRESETS = {
    "light": "世界设定点到为止，避免信息压过剧情。",
    "medium": "设定服务剧情，需要时自然嵌入规则与背景。",
    "dense": "增强体系、势力、历史与规则说明，但必须和情节绑定。",
}

EMOTION_INTENSITY_PRESETS = {
    "subtle": "情绪表达含蓄，以动作、停顿和细节侧写为主。",
    "medium": "情绪清晰可感，但不过度宣泄。",
    "high": "情绪浓度高，冲突、热血、悲壮或压迫感都要充分外显。",
}

COMBAT_STYLE_PRESETS = {
    "brief": "战斗描写短促直接，重点写结果和关键变化。",
    "tactical": "强调判断、试探、破局与招式逻辑。",
    "cinematic": "强调镜头感、空间调度、动作连贯性和视觉冲击。",
    "epic": "强调气势、神通、异象和宿命对撞感。",
}

HOOK_STRENGTH_PRESETS = {
    "gentle": "开篇平稳进入，用氛围或细节吸引读者。",
    "medium": "尽早建立悬念、目标或冲突。",
    "strong": "开篇即抛出危机、反差或爆点，强化追读欲。",
}

WRITING_OPTION_GROUPS = {
    "style": STYLE_PRESETS,
    "perspective": PERSPECTIVE_PRESETS,
    "narrative_mode": NARRATIVE_MODE_PRESETS,
    "pace": PACE_PRESETS,
    "dialogue_density": DIALOGUE_DENSITY_PRESETS,
    "prose_style": PROSE_STYLE_PRESETS,
    "world_building_density": WORLD_BUILDING_DENSITY_PRESETS,
    "emotion_intensity": EMOTION_INTENSITY_PRESETS,
    "combat_style": COMBAT_STYLE_PRESETS,
    "hook_strength": HOOK_STRENGTH_PRESETS,
}

DEFAULT_WRITING_OPTIONS = {
    "style": "literary",
    "style_preset": "",
    "perspective": "third_limited",
    "narrative_mode": "balanced",
    "pace": "medium",
    "dialogue_density": "medium",
    "prose_style": "clean",
    "world_building_density": "medium",
    "emotion_intensity": "medium",
    "combat_style": "tactical",
    "hook_strength": "medium",
}


def resolve_option(
    value: Optional[str],
    options: Dict[str, str],
    default_key: str,
    label: str,
) -> str:
    """Resolve a prompt option to a descriptive requirement."""
    key = (value or default_key).strip() if isinstance(value, str) else default_key
    description = options.get(key, options[default_key])
    if key not in options:
        return f"{label}: {key}（自定义） - {description}"
    return f"{label}: {key} - {description}"


def normalize_writing_options(raw_options: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Fill missing writing options with defaults and drop unknown keys."""
    normalized = dict(DEFAULT_WRITING_OPTIONS)
    for key, value in (raw_options or {}).items():
        if key in normalized and value not in (None, ""):
            normalized[key] = value
    return normalized


def build_writing_guidance(options: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build human-readable writing guidance strings from normalized options."""
    normalized = normalize_writing_options(options)
    style_key = normalized.get("style_preset") or normalized["style"]
    requirements = {
        "style": resolve_option(style_key, STYLE_PRESETS, "literary", "风格预设"),
        "perspective": resolve_option(
            normalized["perspective"],
            PERSPECTIVE_PRESETS,
            "third_limited",
            "叙事视角",
        ),
        "details": [
            resolve_option(normalized["narrative_mode"], NARRATIVE_MODE_PRESETS, "balanced", "叙事写法"),
            resolve_option(normalized["pace"], PACE_PRESETS, "medium", "节奏"),
            resolve_option(normalized["dialogue_density"], DIALOGUE_DENSITY_PRESETS, "medium", "对白密度"),
            resolve_option(normalized["prose_style"], PROSE_STYLE_PRESETS, "clean", "行文质感"),
            resolve_option(
                normalized["world_building_density"],
                WORLD_BUILDING_DENSITY_PRESETS,
                "medium",
                "设定密度",
            ),
            resolve_option(
                normalized["emotion_intensity"],
                EMOTION_INTENSITY_PRESETS,
                "medium",
                "情绪强度",
            ),
            resolve_option(normalized["combat_style"], COMBAT_STYLE_PRESETS, "tactical", "战斗写法"),
            resolve_option(normalized["hook_strength"], HOOK_STRENGTH_PRESETS, "medium", "开篇抓力"),
        ],
    }
    requirements["normalized"] = normalized
    return requirements
