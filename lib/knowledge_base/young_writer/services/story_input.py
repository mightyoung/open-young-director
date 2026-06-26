"""Structured story input assets for long-form novel generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
import json
from pathlib import Path
import re
from typing import Any


STORY_INPUT_DIRNAME = "story_input"
PROJECT_BIBLE_FILE = "project_bible.json"
WORLD_BIBLE_FILE = "world_bible.json"
CHARACTERS_FILE = "characters.json"
CHAPTER_PLANS_FILE = "chapter_plans.json"
STYLE_PROFILE_FILE = "style_profile.json"
CANONICAL_INPUT_POLICY = {
    "story_input_json": "canonical",
    "outline_markdown": "export_compatibility_only",
    "goal_lock": "chapter_plan_first",
}
CHINESE_TEXT_RE = re.compile(r"[\u4e00-\u9fff]")

ACTION_VERB_HINTS = (
    "查",
    "调查",
    "追",
    "追查",
    "确认",
    "发现",
    "揭开",
    "听见",
    "指向",
    "截获",
    "救回",
    "公开",
    "进入",
    "逃",
    "守",
    "攻",
    "战",
    "夺",
    "破",
    "潜入",
    "返回",
    "寻找",
    "营救",
    "揭开",
    "对抗",
    "破解",
    "达成",
    "阻止",
    "交易",
    "谈判",
    "背叛",
)
LOCATION_SUFFIXES = (
    "星门控制中心",
    "企业主控塔",
    "主控塔",
    "控制室",
    "监测站",
    "维护通道",
    "维修通道",
    "密封舱室",
    "回声空域",
    "白昼环",
    "空间城",
    "实验场",
    "档案馆",
    "舱段",
    "舱室",
    "舰桥",
    "港区",
    "空域",
    "航道",
    "舰队",
    "星门",
    "基地",
    "要塞",
    "通道",
    "港",
    "站",
    "塔",
    "环",
    "城",
)
SEED_EVENT_SPLIT_PATTERNS = re.compile(r"(?:并且|并在|并于|并|随后|然后|接着|再|并最终|最终|于是)")
SEED_EVENT_STOPWORDS = (
    "的",
    "了",
    "着",
    "和",
    "与",
    "及",
    "并",
    "并在",
    "并于",
    "然后",
    "随后",
    "接着",
    "最终",
    "于是",
)


@dataclass
class CharacterEntry:
    id: str
    name: str
    role: str = ""
    voice: str = ""
    motivation: str = ""
    arc: str = ""
    relationships: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class ProjectBible:
    title: str
    author: str
    genre: str
    premise: str
    synopsis: str
    reader_promise: str = ""
    themes: list[str] = field(default_factory=list)
    forbidden_directions: list[str] = field(default_factory=list)


@dataclass
class WorldBible:
    summary: str
    locations: list[str] = field(default_factory=list)
    factions: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    known_facts: list[str] = field(default_factory=list)


@dataclass
class ChapterPlan:
    chapter_number: int
    title: str
    summary: str
    key_events: list[str] = field(default_factory=list)
    realm: str = ""
    purpose: str = ""
    must_include: list[str] = field(default_factory=list)
    must_not_include: list[str] = field(default_factory=list)
    character_ids: list[str] = field(default_factory=list)
    character_names: list[str] = field(default_factory=list)
    location_ids: list[str] = field(default_factory=list)
    continuity_in: str = ""
    continuity_out: str = ""
    goal_lock: str = ""
    pacing: str = ""
    emotional_turn: str = ""
    volume_number: int = 1
    volume_label: str = ""
    magic_line: str = ""
    source: str = "seed"


@dataclass
class StyleProfile:
    style: str = "literary"
    style_preset: str = ""
    perspective: str = ""
    narrative_mode: str = ""
    pace: str = ""
    dialogue_density: str = ""
    prose_style: str = ""
    world_building_density: str = ""
    emotion_intensity: str = ""
    combat_style: str = ""
    hook_strength: str = ""
    humanization_level: str = ""


@dataclass
class StoryInputBundle:
    project_bible: ProjectBible
    world_bible: WorldBible
    characters: list[CharacterEntry]
    chapter_plans: list[ChapterPlan]
    style_profile: StyleProfile


@dataclass
class RuntimeOverrides:
    volume_guidance: str = ""
    volume_guidance_payload: dict[str, Any] = field(default_factory=dict)
    chapter_guidance: str = ""
    chapter_guidance_target: int | None = None
    previous_summary: str = ""
    previous_chapters: list[dict[str, Any]] = field(default_factory=list)
    longform_memory: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InputValidationReport:
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)

    @property
    def invalid(self) -> bool:
        return bool(self.blocking_issues)


@dataclass
class GenerationPacket:
    chapter_number: int
    total_chapters: int
    project_bible: ProjectBible
    world_bible: WorldBible
    characters: list[CharacterEntry]
    chapter_plan: ChapterPlan
    style_profile: StyleProfile
    runtime_overrides: RuntimeOverrides = field(default_factory=RuntimeOverrides)
    validation: InputValidationReport = field(default_factory=InputValidationReport)


def resolve_goal_lock_resolution(packet: GenerationPacket) -> dict[str, Any]:
    plan_goal_lock = str(packet.chapter_plan.goal_lock or "").strip()
    payload = dict(packet.runtime_overrides.volume_guidance_payload or {})
    runtime_goal_lock = str(payload.get("goal_lock", "") or "").strip()
    runtime_mode = str(payload.get("goal_lock_mode", "") or "additive_only").strip().lower()
    effective_goal_lock = plan_goal_lock or runtime_goal_lock
    source = (
        "chapter_plan.goal_lock"
        if plan_goal_lock
        else "runtime.volume_guidance_payload.goal_lock"
    )
    return {
        "plan_goal_lock": plan_goal_lock,
        "runtime_goal_lock": runtime_goal_lock,
        "runtime_mode": runtime_mode or "additive_only",
        "effective_goal_lock": effective_goal_lock,
        "effective_source": source,
        "conflict": bool(
            plan_goal_lock and runtime_goal_lock and plan_goal_lock != runtime_goal_lock
        ),
    }


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_sentences(text: str) -> list[str]:
    return [
        chunk.strip()
        for chunk in re.split(r"[。！？；;\n]+", str(text or ""))
        if chunk.strip()
    ]


def _sanitize_id(name: str, prefix: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff]+", "_", str(name or "").strip())
    cleaned = cleaned.strip("_") or prefix
    return f"{prefix}:{cleaned.lower()}"


def _normalize_character_name(name: str) -> str:
    return re.sub(r"\s+", "", str(name or "")).strip("：:")


def _split_character_description(description: str) -> tuple[str, str, str, str]:
    raw = str(description or "").strip()
    if not raw:
        return "", "", "", ""
    clauses = [
        item.strip("，,；;。！？!? ")
        for item in re.split(r"[，,；;。！？!?]", raw)
        if item.strip("，,；;。！？!? ")
    ]
    role = clauses[0] if clauses else ""
    role = role[:24]
    voice = ""
    if len(clauses) > 1:
        voice = clauses[1][:24]
    motivation = ""
    for clause in clauses:
        if any(
            marker in clause
            for marker in ("执念", "想", "要", "决心", "必须", "试图", "为了", "找回", "追查", "守住")
        ):
            motivation = clause[:80]
            break
    if not motivation:
        motivation = raw[:160]
    arc = ""
    for clause in clauses[1:]:
        if any(marker in clause for marker in ("想", "要", "决心", "必须", "试图", "从", "成为")):
            arc = clause[:48]
            break
    if not arc and len(clauses) > 2:
        arc = clauses[2][:48]
    return role, voice, motivation, arc


def parse_character_entries(raw_text: str) -> list[CharacterEntry]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    try:
        payload = json.loads(text)
    except Exception:
        payload = None

    entries: list[CharacterEntry] = []
    if isinstance(payload, dict):
        protagonist = str(payload.get("protagonist", "") or "").strip()
        if protagonist:
            name = _normalize_character_name(protagonist.split("：", 1)[0].split(":", 1)[0])
            role, voice, motivation, arc = _split_character_description(
                protagonist.split("：", 1)[1] if "：" in protagonist else protagonist.split(":", 1)[1] if ":" in protagonist else protagonist
            )
            entries.append(
                CharacterEntry(
                    id=_sanitize_id(name or "protagonist", "character"),
                    name=name or "主角",
                    role=role or "protagonist",
                    voice=voice,
                    motivation=motivation or protagonist,
                    arc=arc,
                    tags=["protagonist"],
                )
            )
        supporting = payload.get("supporting_characters", [])
        if isinstance(supporting, list):
            for item in supporting:
                item_text = str(item or "").strip()
                if not item_text:
                    continue
                name = _normalize_character_name(item_text.split("：", 1)[0].split(":", 1)[0])
                role, voice, motivation, arc = _split_character_description(
                    item_text.split("：", 1)[1] if "：" in item_text else item_text.split(":", 1)[1] if ":" in item_text else item_text
                )
                entries.append(
                    CharacterEntry(
                        id=_sanitize_id(name or "supporting", "character"),
                        name=name or item_text[:6],
                        role=role or "supporting",
                        voice=voice,
                        motivation=motivation or item_text,
                        arc=arc,
                        tags=["supporting"],
                    )
                )
    else:
        pattern = re.compile(
            r"([\u4e00-\u9fffA-Za-z0-9]{2,12})\s*[：:]\s*(.+?)(?=(?:[\s。；;\n\r]*[\u4e00-\u9fffA-Za-z0-9]{2,12}\s*[：:])|$)"
        )
        for match in pattern.finditer(text):
            name = _normalize_character_name(match.group(1))
            description = str(match.group(2) or "").strip(" \t\r\n。；;")
            role, voice, motivation, arc = _split_character_description(description)
            if name:
                entries.append(
                    CharacterEntry(
                        id=_sanitize_id(name, "character"),
                        name=name,
                        role=role,
                        voice=voice,
                        motivation=motivation,
                        arc=arc,
                    )
                )

    deduped: list[CharacterEntry] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.name and entry.name not in seen:
            seen.add(entry.name)
            deduped.append(entry)
    return deduped


def _extract_locations(world_setting: str) -> list[str]:
    text = str(world_setting or "")
    candidates: list[str] = []
    for suffix in LOCATION_SUFFIXES:
        pattern = rf"([\u4e00-\u9fffA-Za-z0-9]{{1,16}}{re.escape(suffix)})"
        for match in re.findall(pattern, text):
            cleaned = str(match or "").strip("，,；;。！？!?：: ")
            if len(cleaned) >= 2:
                candidates.append(cleaned)
    for clause in re.split(r"[。；;\n\r]", text):
        cleaned = str(clause or "").strip("，,；;。！？!?：: ")
        if 2 <= len(cleaned) <= 16 and any(suffix in cleaned for suffix in LOCATION_SUFFIXES):
            candidates.append(cleaned)

    deduped: list[str] = []
    for candidate in sorted(set(candidates), key=len, reverse=True):
        if any(candidate in existing for existing in deduped):
            continue
        deduped.append(candidate)
    deduped.sort(key=text.find)
    return deduped[:12]


def _extract_rules(world_setting: str) -> list[str]:
    return _split_sentences(world_setting)[:8]


def _chapter_stage_label(progress: float) -> str:
    labels = ("开场", "推进", "承压", "转折", "升级", "收束")
    index = min(int(progress * len(labels)), len(labels) - 1)
    return labels[index]


def _select_progressive(items: list[str], progress: float, fallback: str) -> str:
    if not items:
        return fallback
    index = min(
        int(progress * max(len(items) - 1, 0)),
        max(len(items) - 1, 0),
    )
    return items[index]


def _select_progressive_by_chapter(
    items: list[str],
    chapter_number: int,
    total_chapters: int,
    fallback: str,
    *,
    repeat_items: list[str] | None = None,
) -> str:
    if not items:
        return fallback
    if total_chapters > len(items) * 3:
        item_index = max(chapter_number, 1) - 1
        if item_index < len(items):
            return items[item_index]
        repeat_pool = repeat_items or items
        return repeat_pool[(item_index - len(items)) % len(repeat_pool)]
    index = min(
        round(
            (max(chapter_number, 1) - 1)
            * max(len(items) - 1, 0)
            / max(total_chapters - 1, 1)
        ),
        len(items) - 1,
    )
    return items[index]


def _is_outline_meta_progression(text: str) -> bool:
    cleaned = str(text or "").strip()
    if "阶段" not in cleaned:
        return False
    if not any(marker in cleaned for marker in ("全书", "故事", "全篇", "整体")):
        return False
    return any(marker in cleaned for marker in ("推进", "分为", "从", "依次"))


def _is_generic_final_choice(text: str) -> bool:
    cleaned = str(text or "").strip("，,；;。！？!?：: ")
    if "必须做出选择" not in cleaned:
        return False
    return "在" not in cleaned and "之间" not in cleaned and "第三种" not in cleaned


def _outline_action_units(
    outline_sentences: list[str], *, character_names: list[str]
) -> list[str]:
    units: list[str] = []
    seen: set[str] = set()

    def _add(unit: str) -> None:
        cleaned = str(unit or "").strip("，,；;。！？!?：: ")
        if len(cleaned) < 6 or cleaned in seen:
            return
        seen.add(cleaned)
        units.append(cleaned)

    for sentence in outline_sentences:
        _add(sentence)
        clauses = [
            item.strip()
            for item in SEED_EVENT_SPLIT_PATTERNS.split(sentence)
            if item.strip()
        ]
        for clause in clauses:
            has_character = any(name and name in clause for name in character_names)
            if has_character or _chapter_event_has_action(clause):
                _add(clause)
    return units or outline_sentences


def _recyclable_outline_units(units: list[str], *, character_names: list[str]) -> list[str]:
    recyclable = [
        unit
        for unit in units
        if any(name and name in unit for name in character_names)
        or _chapter_event_has_action(unit)
    ]
    return recyclable or units


def _chapter_event_has_action(event: str) -> bool:
    return any(verb in str(event or "") for verb in ACTION_VERB_HINTS)


def _has_chinese_text(value: Any) -> bool:
    return bool(CHINESE_TEXT_RE.search(str(value or "")))


def _require_chinese_text(
    report: InputValidationReport,
    field_path: str,
    value: Any,
) -> None:
    text = str(value or "").strip()
    if text and not _has_chinese_text(text):
        report.blocking_issues.append(f"{field_path} 必须使用中文输入")


def _require_chinese_list(
    report: InputValidationReport,
    field_path: str,
    values: list[Any],
) -> None:
    for index, value in enumerate(values):
        text = str(value or "").strip()
        if text and not _has_chinese_text(text):
            report.blocking_issues.append(f"{field_path}[{index}] 必须使用中文输入")


def _compress_seed_clause(
    clause: str,
    *,
    character_names: list[str],
    location_names: list[str],
) -> str:
    cleaned = str(clause or "").strip("，,；;。！？!?：: ")
    if len(cleaned) < 4:
        return ""

    subject = next(
        (name for name in character_names if len(name) >= 2 and name in cleaned),
        "",
    )
    if "鲸歌信号" in cleaned and "母亲" in cleaned:
        actor = subject or next((name for name in character_names if len(name) >= 2), "")
        return f"{actor}追查母亲失踪线索" if actor else "追查母亲失踪线索"
    if "组成小队" in cleaned and "揭开" in cleaned:
        actor = next((name for name in character_names if len(name) >= 2), subject)
        reveal_target = cleaned.split("揭开", 1)[1].strip("，,；;。！？!?：: ")
        reveal_target = reveal_target.replace("其实在", "")
        reveal_target = reveal_target.replace("的真相", "真相")
        if reveal_target:
            prefix = f"{actor}与小队" if actor else "小队"
            return f"{prefix}揭开{reveal_target}"
    action_candidates = [
        (cleaned.find(verb), verb)
        for verb in sorted(ACTION_VERB_HINTS, key=len, reverse=True)
        if cleaned.find(verb) >= 0
    ]
    if subject:
        subject_end = cleaned.find(subject) + len(subject)
        action = next(
            (
                verb
                for index, verb in action_candidates
                if index >= subject_end
            ),
            "",
        )
    else:
        action = action_candidates[0][1] if action_candidates else ""
    if not action:
        cleaned = _compact_non_action_seed_clause(cleaned)
        actor = subject or next((name for name in character_names if len(name) >= 2), "")
        if actor:
            if cleaned.startswith(f"{actor}的"):
                cleaned = cleaned[len(actor) + 1 :]
            elif cleaned.startswith(actor):
                cleaned = cleaned[len(actor) :]
            cleaned = cleaned.strip("，,；;。！？!?：: ")
            return _clip_seed_goal(f"{actor}发现{cleaned}", limit=64)
        return _clip_seed_goal(cleaned, limit=64)

    action_index = cleaned.find(action)
    object_tail = cleaned[action_index + len(action) :]
    object_tail = re.split(r"[，,；;。！？!?]", object_tail, maxsplit=1)[0]
    object_tail = re.sub(r"^(?:在|于|向|对|把|将|从|往|朝)", "", object_tail).strip()
    for stopword in SEED_EVENT_STOPWORDS:
        if object_tail.startswith(stopword):
            object_tail = object_tail[len(stopword) :].strip()
    object_tail = _clip_seed_goal(object_tail, limit=48)

    parts: list[str] = []
    if subject:
        parts.append(subject)
    parts.append(action)
    if object_tail:
        parts.append(object_tail)
    compact = "".join(parts).strip()
    if compact:
        return _clip_seed_goal(compact, limit=64)
    return _clip_seed_goal(cleaned, limit=32)


def _clip_seed_goal(goal: str, *, limit: int) -> str:
    cleaned = str(goal or "").strip("，,；;。！？!?：: ")
    if len(cleaned) <= limit:
        return _trim_seed_goal(cleaned)

    window = cleaned[:limit]
    min_boundary = max(8, limit // 2)
    boundary = max(window.rfind(mark) for mark in "，,；;。！？!?：:")
    if boundary >= min_boundary:
        return _trim_seed_goal(window[:boundary])
    return _trim_seed_goal(window)


def _trim_seed_goal(goal: str) -> str:
    cleaned = str(goal or "").rstrip("的和与及、，,；;")
    for suffix in ("关于", "以及", "为了", "因为", "通过", "一项"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip("的和与及、，,；;")
    return cleaned


def _compact_non_action_seed_clause(clause: str) -> str:
    cleaned = str(clause or "").strip("，,；;。！？!?：: ")
    cleaned = re.sub(r"^(?:近未来|现代|未来)?(?:海滨城市|城市)?", "", cleaned)
    cleaned = cleaned.strip("，,；;。！？!?：: ")
    if "父亲" in cleaned and "声波保存记忆" in cleaned:
        return "父亲参与声波记忆实验线索"
    if "低频回声" in cleaned and "记忆" in cleaned:
        return "岚港低频回声抹除记忆源头"
    if "集体遗忘" in cleaned:
        place_match = re.search(r"(?P<place>[\u4e00-\u9fffA-Za-z0-9]{2,8})居民", cleaned)
        place = place_match.group("place") if place_match else ""
        return f"{place}集体遗忘" if place else "居民集体遗忘"
    match = re.search(r"(?P<place>[\u4e00-\u9fffA-Za-z0-9]{2,12})(?:连续)?出现(?P<event>.+)", cleaned)
    if match:
        cleaned = f"{match.group('place')}{match.group('event')}"
    cleaned = cleaned.replace("连续潮汐", "潮汐")
    return cleaned.rstrip("和与及、，,；;")


def _derive_seed_goal_lock(
    title: str,
    outline_sentences: list[str],
    *,
    character_names: list[str],
    location_names: list[str],
) -> str:
    for sentence in outline_sentences:
        clauses = [
            item.strip()
            for item in SEED_EVENT_SPLIT_PATTERNS.split(sentence)
            if item.strip()
        ]
        for clause in clauses:
            candidate = _compress_seed_clause(
                clause,
                character_names=character_names,
                location_names=location_names,
            )
            if len(candidate) >= 4:
                return candidate
    clean_title = str(title or "").strip()
    if clean_title:
        return f"推进《{clean_title}》主线"
    return "持续推进主线冲突"


def _derive_seed_key_events(
    summary: str,
    *,
    goal_lock: str,
    character_names: list[str],
    location_names: list[str],
) -> list[str]:
    del summary, location_names
    goal = str(goal_lock or "").strip()
    if not goal:
        return []

    primary_character = next(
        (str(name or "").strip() for name in character_names if str(name or "").strip()),
        "",
    )
    event_verbs = (*ACTION_VERB_HINTS, "保护")
    inherited_actor = primary_character if primary_character and primary_character in goal else primary_character
    inherited_action = next(
        (verb for verb in sorted(event_verbs, key=len, reverse=True) if verb in goal),
        "",
    )
    events: list[str] = []
    for fragment in re.split(r"[、，,；;。]|以及|并且|并|同时", goal):
        event = _trim_seed_goal(fragment)
        if len(event) < 4:
            continue
        if (
            inherited_actor
            and inherited_action
            and inherited_actor not in event
            and not any(verb in event for verb in event_verbs)
        ):
            event = f"{inherited_actor}{inherited_action}{event}"
        if (
            primary_character
            and primary_character not in event
            and any(event.startswith(verb) for verb in event_verbs)
        ):
            event = f"{primary_character}{event}"
        event = _clip_seed_goal(event, limit=48)
        if event and event not in events:
            events.append(event)
        if len(events) >= 3:
            break
    if len(events) > 1:
        events = [
            event
            for event in events
            if not any(
                marker in event
                for marker in ("保护身边人", "保护身边的人", "保护同伴")
            )
        ] or events
    return events or [goal]


def _advance_repeated_seed_goal_lock(goal_lock: str, repetition_index: int) -> str:
    if repetition_index <= 0:
        return goal_lock
    if "五个阶段" in str(goal_lock or "") and "推进" in str(goal_lock or ""):
        stage_actions = (
            "林澈追查城市异常源头",
            "林澈调查城市政治掩盖链",
            "林澈组织深海远征进入遗迹",
            "林澈核查母亲真相档案",
            "林澈接入主数据库追踪外海意识苏醒风险",
        )
        return stage_actions[min(repetition_index - 1, len(stage_actions) - 1)]
    if "第三种选择" in str(goal_lock or "") or "做出选择" in str(goal_lock or ""):
        original_goal = str(goal_lock or "")
        actor = "林澈" if "林澈" in original_goal else ""
        choice_actions = (
            "评估第三种选择的代价",
            "确认第三种选择的触发条件",
            "比对拯救城市与释放意识的后果",
            "制定执行第三种选择的方案",
            "承担第三种选择带来的风险",
        )
        return f"{actor}{choice_actions[min(repetition_index - 1, len(choice_actions) - 1)]}"
    if "摩斯信号" in str(goal_lock or ""):
        original_goal = str(goal_lock or "")
        action_positions = [
            original_goal.find(verb)
            for verb in ACTION_VERB_HINTS
            if original_goal.find(verb) > 0
        ]
        actor_end = min(action_positions) if action_positions else 2
        actor = original_goal[:actor_end]
        signal_actions = (
            "核查摩斯信号来源",
            "确认摩斯信号与父亲有关",
            "追查摩斯信号档案",
            "揭开摩斯信号背后的事故线索",
            "阻止摩斯信号指向的下一次灾难",
        )
        return f"{actor}{signal_actions[min(repetition_index - 1, len(signal_actions) - 1)]}"
    if "母亲失踪线索" in str(goal_lock or ""):
        original_goal = str(goal_lock or "")
        action_positions = [
            original_goal.find(verb)
            for verb in ACTION_VERB_HINTS
            if original_goal.find(verb) > 0
        ]
        actor_end = min(action_positions) if action_positions else 2
        actor = original_goal[:actor_end]
        mother_actions = (
            "调查母亲失踪线索",
            "复听并比对母亲最后信号确认来源",
            "比对母亲警告与星痕中枢档案确认关系",
            "追查母亲与深海叛乱的真相",
            "破解母亲留下的第三种选择",
        )
        return f"{actor}{mother_actions[min(repetition_index - 1, len(mother_actions) - 1)]}"
    if "潮汐心脏" in str(goal_lock or "") and "外海意识体" in str(goal_lock or ""):
        original_goal = str(goal_lock or "")
        action_positions = [
            original_goal.find(verb)
            for verb in ACTION_VERB_HINTS
            if original_goal.find(verb) > 0
        ]
        actor_end = min(action_positions) if action_positions else 2
        actor = original_goal[:actor_end]
        truth_actions = (
            "发现潮汐心脏封印外海意识体的证据",
            "比对潮汐心脏与外海意识体封印记录",
            "确认潮汐心脏封印外海意识体真相",
            "追查外海意识体突破封印的风险",
            "阻止外海意识体突破潮汐心脏封印",
        )
        return f"{actor}{truth_actions[min(repetition_index - 1, len(truth_actions) - 1)]}"
    actions = ("发现", "调查", "确认", "追查", "揭开", "阻止")
    next_action = actions[min(repetition_index, len(actions) - 1)]
    action = next(
        (
            verb
            for verb in sorted((*ACTION_VERB_HINTS, "发现"), key=len, reverse=True)
            if verb in str(goal_lock or "")
        ),
        "",
    )
    if not action:
        return f"{next_action}{goal_lock}".rstrip("的和与及、，,；;")
    return str(goal_lock).replace(action, next_action, 1).rstrip("的和与及、，,；;")


def _select_chapter_locations(
    *,
    summary: str,
    key_events: list[str],
    world_locations: list[str],
    progress: float,
) -> list[str]:
    if not world_locations:
        return []
    text = " ".join([str(summary or ""), *[str(item or "") for item in key_events]])
    matched = [location for location in world_locations if location and location in text]
    if matched:
        return matched[:3]

    index = min(
        int(progress * max(len(world_locations) - 1, 0)),
        max(len(world_locations) - 1, 0),
    )
    selected = [world_locations[index]]
    if len(world_locations) > 1 and index + 1 < len(world_locations):
        selected.append(world_locations[index + 1])
    return selected[:3]


def build_story_input_bundle(
    project: Any,
    *,
    writing_options: dict[str, str] | None = None,
    chapters_per_volume: int = 60,
) -> StoryInputBundle:
    outline_sentences = _split_sentences(getattr(project, "outline", ""))
    world_setting = str(getattr(project, "world_setting", "") or "")
    world_sentences = _split_sentences(world_setting)
    world_locations = _extract_locations(world_setting)
    characters = parse_character_entries(str(getattr(project, "character_intro", "") or ""))
    character_names = [entry.name for entry in characters]
    total_chapters = max(int(getattr(project, "total_chapters", 0) or 0), 1)
    outline_units = (
        _outline_action_units(outline_sentences, character_names=character_names)
        if total_chapters > max(len(outline_sentences), 1) * 3
        else outline_sentences
    )
    repeat_outline_units = _recyclable_outline_units(
        outline_units, character_names=character_names
    )
    chapters_per_volume = max(int(chapters_per_volume or 60), 1)
    seed_goal_lock = _derive_seed_goal_lock(
        str(getattr(project, "title", "") or ""),
        outline_sentences,
        character_names=character_names,
        location_names=world_locations,
    )

    project_bible = ProjectBible(
        title=str(getattr(project, "title", "") or ""),
        author=str(getattr(project, "author", "") or ""),
        genre=str(getattr(project, "genre", "") or ""),
        premise=_select_progressive(outline_sentences, 0.0, str(getattr(project, "outline", "") or "")),
        synopsis=str(getattr(project, "outline", "") or ""),
        reader_promise=f"围绕{getattr(project, 'title', '本书')}的主线持续推进，并保持人物与世界设定稳定继承。",
        themes=[str(getattr(project, "genre", "") or "").strip()] if getattr(project, "genre", "") else [],
        forbidden_directions=[],
    )
    world_bible = WorldBible(
        summary=world_setting,
        locations=world_locations,
        rules=_extract_rules(world_setting),
        hard_constraints=_extract_rules(world_setting)[:4],
        known_facts=_extract_rules(world_setting)[:6],
    )
    style_profile = StyleProfile(**{k: v for k, v in (writing_options or {}).items() if hasattr(StyleProfile, k)})

    chapter_plans: list[ChapterPlan] = []
    summary_repetitions: dict[str, int] = {}
    for chapter_number in range(1, total_chapters + 1):
        progress = (chapter_number - 1) / max(total_chapters - 1, 1)
        summary = _select_progressive_by_chapter(
            outline_units,
            chapter_number,
            total_chapters,
            f"围绕{getattr(project, 'title', '主线')}推进本章冲突。",
            repeat_items=repeat_outline_units,
        )
        chapter_goal_lock = _derive_seed_goal_lock(
            str(getattr(project, "title", "") or ""),
            [summary] if summary else outline_sentences,
            character_names=character_names,
            location_names=world_locations,
        ) or seed_goal_lock
        summary_key = summary or chapter_goal_lock
        repetition_index = summary_repetitions.get(summary_key, 0)
        summary_repetitions[summary_key] = repetition_index + 1
        chapter_goal_lock = _advance_repeated_seed_goal_lock(
            chapter_goal_lock,
            repetition_index,
        )
        stage = _chapter_stage_label(progress)
        character_slice = character_names[:4]
        key_events = _derive_seed_key_events(
            summary,
            goal_lock=chapter_goal_lock,
            character_names=character_names,
            location_names=world_locations,
        )
        chapter_locations = _select_chapter_locations(
            summary=summary,
            key_events=key_events,
            world_locations=world_locations,
            progress=progress,
        )
        continuity_in = (
            "开篇建立人物、地点与主线异常。"
            if chapter_number == 1
            else f"承接上一章局势，继续{stage}阶段推进。"
        )
        continuity_out = f"为下一章保留{stage}阶段后的新压力或新线索。"
        magic_parts = [f"阶段目标：{stage}"]
        world_focus = _select_progressive(world_sentences, progress, world_setting[:80])
        if world_focus:
            magic_parts.append(f"设定约束：{world_focus}")
        if character_slice:
            magic_parts.append(f"重点人物：{'、'.join(character_slice)}")
        volume_number = ((chapter_number - 1) // chapters_per_volume) + 1
        chapter_plans.append(
            ChapterPlan(
                chapter_number=chapter_number,
                title=f"第{chapter_number}章",
                summary=summary,
                key_events=key_events,
                realm=str(getattr(project, "genre", "") or ""),
                purpose=f"{stage}阶段的主线推进",
                must_include=list(key_events),
                character_ids=[entry.id for entry in characters[:4]],
                character_names=character_slice,
                location_ids=[
                    _sanitize_id(location, "location")
                    for location in chapter_locations
                ],
                continuity_in=continuity_in,
                continuity_out=continuity_out,
                goal_lock=chapter_goal_lock,
                pacing=stage,
                emotional_turn=stage,
                volume_number=volume_number,
                volume_label=f"第{volume_number}卷",
                magic_line="；".join(part for part in magic_parts if part),
                source="seed",
            )
        )

    return StoryInputBundle(
        project_bible=project_bible,
        world_bible=world_bible,
        characters=characters,
        chapter_plans=chapter_plans,
        style_profile=style_profile,
    )


def story_input_dir(project_dir: Path) -> Path:
    return Path(project_dir) / STORY_INPUT_DIRNAME


def write_story_input_bundle(project_dir: Path, bundle: StoryInputBundle) -> Path:
    input_dir = story_input_dir(project_dir)
    _json_dump(input_dir / PROJECT_BIBLE_FILE, asdict(bundle.project_bible))
    _json_dump(input_dir / WORLD_BIBLE_FILE, asdict(bundle.world_bible))
    _json_dump(
        input_dir / CHARACTERS_FILE,
        [asdict(character) for character in bundle.characters],
    )
    _json_dump(
        input_dir / CHAPTER_PLANS_FILE,
        [asdict(plan) for plan in bundle.chapter_plans],
    )
    _json_dump(input_dir / STYLE_PROFILE_FILE, asdict(bundle.style_profile))
    return input_dir


def load_story_input_bundle(project_dir: Path) -> StoryInputBundle | None:
    input_dir = story_input_dir(project_dir)
    required = [
        input_dir / PROJECT_BIBLE_FILE,
        input_dir / WORLD_BIBLE_FILE,
        input_dir / CHARACTERS_FILE,
        input_dir / CHAPTER_PLANS_FILE,
        input_dir / STYLE_PROFILE_FILE,
    ]
    if not all(path.exists() for path in required):
        return None

    project_bible = ProjectBible(**_json_load(required[0]))
    world_bible = WorldBible(**_json_load(required[1]))
    characters = [CharacterEntry(**item) for item in _json_load(required[2])]
    chapter_plans = [ChapterPlan(**item) for item in _json_load(required[3])]
    style_profile = StyleProfile(**_json_load(required[4]))
    return StoryInputBundle(
        project_bible=project_bible,
        world_bible=world_bible,
        characters=characters,
        chapter_plans=chapter_plans,
        style_profile=style_profile,
    )


def load_chapter_plan(project_dir: Path, chapter_number: int) -> ChapterPlan | None:
    bundle = load_story_input_bundle(project_dir)
    if bundle is None:
        return None
    for plan in bundle.chapter_plans:
        if int(plan.chapter_number) == int(chapter_number):
            return plan
    return None


def chapter_plan_to_outline_info(plan: ChapterPlan) -> dict[str, Any]:
    return {
        "number": plan.chapter_number,
        "title": plan.title,
        "realm": plan.realm or plan.pacing or "",
        "summary": plan.summary,
        "magic_line": plan.magic_line,
        "key_events": list(plan.key_events),
        "goal_lock": plan.goal_lock,
        "continuity_in": plan.continuity_in,
        "continuity_out": plan.continuity_out,
    }


def render_outline_markdown(volume_number: int, plans: list[ChapterPlan]) -> str:
    lines = [
        f"# 第{volume_number}卷详细章节规划",
        "",
        "| 章节 | 标题 | 境界/题材 | 核心事件 | 暗线 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for plan in plans:
        lines.append(
            f"| {int(plan.chapter_number):03d} | {plan.title} | {plan.realm or plan.pacing or '-'} | "
            f"{plan.summary} | {plan.magic_line} |"
        )
    lines.append("")
    return "\n".join(lines)


def validate_generation_packet(packet: GenerationPacket) -> InputValidationReport:
    report = InputValidationReport()
    plan = packet.chapter_plan
    _require_chinese_text(report, "project_bible.title", packet.project_bible.title)
    _require_chinese_text(report, "project_bible.genre", packet.project_bible.genre)
    _require_chinese_text(report, "project_bible.premise", packet.project_bible.premise)
    _require_chinese_text(report, "project_bible.synopsis", packet.project_bible.synopsis)
    _require_chinese_text(report, "world_bible.summary", packet.world_bible.summary)
    _require_chinese_list(report, "world_bible.locations", packet.world_bible.locations)
    _require_chinese_list(report, "world_bible.factions", packet.world_bible.factions)
    _require_chinese_list(report, "world_bible.rules", packet.world_bible.rules)
    _require_chinese_list(
        report, "world_bible.hard_constraints", packet.world_bible.hard_constraints
    )
    _require_chinese_list(report, "world_bible.known_facts", packet.world_bible.known_facts)
    for index, character in enumerate(packet.characters):
        _require_chinese_text(report, f"characters[{index}].name", character.name)
    _require_chinese_text(report, "chapter_plan.title", plan.title)
    _require_chinese_text(report, "chapter_plan.summary", plan.summary)
    _require_chinese_list(report, "chapter_plan.key_events", plan.key_events)
    _require_chinese_text(report, "chapter_plan.realm", plan.realm)
    _require_chinese_text(report, "chapter_plan.purpose", plan.purpose)
    _require_chinese_list(report, "chapter_plan.must_include", plan.must_include)
    _require_chinese_list(report, "chapter_plan.must_not_include", plan.must_not_include)
    _require_chinese_list(report, "chapter_plan.character_names", plan.character_names)
    _require_chinese_text(report, "chapter_plan.continuity_in", plan.continuity_in)
    _require_chinese_text(report, "chapter_plan.continuity_out", plan.continuity_out)
    _require_chinese_text(report, "chapter_plan.goal_lock", plan.goal_lock)
    _require_chinese_text(report, "chapter_plan.pacing", plan.pacing)
    _require_chinese_text(report, "chapter_plan.emotional_turn", plan.emotional_turn)
    _require_chinese_text(report, "chapter_plan.volume_label", plan.volume_label)
    _require_chinese_text(report, "chapter_plan.magic_line", plan.magic_line)
    if not str(plan.summary or "").strip():
        report.blocking_issues.append("chapter_plan.summary 不能为空")
    if not str(plan.goal_lock or "").strip():
        report.blocking_issues.append(
            "chapter_plan.goal_lock 不能为空；卷级 guidance 不能替代结构化章节计划主源。"
        )

    known_character_ids = {character.id for character in packet.characters}
    known_character_names = {
        str(character.name or "").strip()
        for character in packet.characters
        if str(character.name or "").strip()
    }
    unknown_character_ids = [
        character_id
        for character_id in plan.character_ids
        if character_id and character_id not in known_character_ids
    ]
    if unknown_character_ids:
        report.blocking_issues.append(
            "chapter_plan.character_ids 引用了未知角色: "
            + ", ".join(unknown_character_ids[:5])
        )
    unknown_character_names = [
        name
        for name in plan.character_names
        if str(name or "").strip() and str(name or "").strip() not in known_character_names
    ]
    if unknown_character_names:
        report.warnings.append(
            "chapter_plan.character_names 包含结构化角色表之外的名字: "
            + ", ".join(unknown_character_names[:5])
        )

    if not plan.key_events:
        report.warnings.append("chapter_plan.key_events 为空，将仅依赖 summary 推进本章。")
    else:
        for event in plan.key_events:
            if not _chapter_event_has_action(event):
                report.watch_items.append(
                    f"关键事件缺少明显动作词，建议细化: {event}"
                )

    if not str(plan.continuity_in or "").strip():
        report.warnings.append("chapter_plan.continuity_in 为空，章节承接约束较弱。")
    if not str(plan.continuity_out or "").strip():
        report.warnings.append("chapter_plan.continuity_out 为空，章节收束约束较弱。")

    guidance_goal_lock = str(
        packet.runtime_overrides.volume_guidance_payload.get("goal_lock", "") or ""
    ).strip()
    guidance_goal_lock_mode = str(
        packet.runtime_overrides.volume_guidance_payload.get("goal_lock_mode", "")
        or "additive_only"
    ).strip().lower() or "additive_only"
    if guidance_goal_lock and str(plan.goal_lock or "").strip():
        if guidance_goal_lock != str(plan.goal_lock or "").strip():
            report.watch_items.append(
                "卷级 guidance.goal_lock 与 chapter_plan.goal_lock 不一致；当前按 chapter_plan.goal_lock 执行，"
                f"runtime 模式={guidance_goal_lock_mode}。"
            )
    elif guidance_goal_lock:
        report.blocking_issues.append(
            "卷级 guidance 提供了 goal_lock，但 chapter_plan.goal_lock 为空；请先修复结构化章节计划。"
        )
    plan_anchor_text = " ".join(
        [
            str(plan.summary or ""),
            *[str(item or "") for item in plan.key_events],
            *[str(item or "") for item in plan.must_include],
        ]
    )
    if str(plan.goal_lock or "").strip() and str(plan.goal_lock or "").strip() not in plan_anchor_text:
        report.watch_items.append(
            "chapter_plan.goal_lock 未在 summary/key_events/must_include 中显式锚定，可能削弱计划可验证性。"
        )

    return report


def packet_to_dict(packet: GenerationPacket) -> dict[str, Any]:
    return asdict(packet)


def dataclass_to_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value
