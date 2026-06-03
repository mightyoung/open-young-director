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

ACTION_VERB_HINTS = (
    "查",
    "调查",
    "追",
    "追查",
    "逃",
    "守",
    "攻",
    "战",
    "夺",
    "破",
    "潜入",
    "返回",
    "营救",
    "揭开",
    "对抗",
    "达成",
    "阻止",
    "交易",
    "谈判",
    "背叛",
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
            entries.append(
                CharacterEntry(
                    id=_sanitize_id(name or "protagonist", "character"),
                    name=name or "主角",
                    role="protagonist",
                    motivation=protagonist,
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
                entries.append(
                    CharacterEntry(
                        id=_sanitize_id(name or "supporting", "character"),
                        name=name or item_text[:6],
                        role="supporting",
                        motivation=item_text,
                        tags=["supporting"],
                    )
                )
    else:
        for raw_name in re.findall(r"([\u4e00-\u9fff]{2,8})[：:]", text):
            name = _normalize_character_name(raw_name)
            if name:
                entries.append(
                    CharacterEntry(
                        id=_sanitize_id(name, "character"),
                        name=name,
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
    seen: list[str] = []
    for match in re.findall(r"([\u4e00-\u9fff]{2,12}(?:城|站|港|航道|舰队|宗|门|殿|宫|岛|谷|渊))", world_setting or ""):
        if match not in seen:
            seen.append(match)
    return seen[:12]


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


def _chapter_event_has_action(event: str) -> bool:
    return any(verb in str(event or "") for verb in ACTION_VERB_HINTS)


def _derive_seed_goal_lock(title: str, outline_sentences: list[str]) -> str:
    for sentence in outline_sentences:
        candidate = re.split(r"[，,；;。！？!?]", sentence, maxsplit=1)[0].strip()
        if len(candidate) >= 4:
            return candidate[:48]
    clean_title = str(title or "").strip()
    if clean_title:
        return f"推进《{clean_title}》主线"
    return "持续推进主线冲突"


def build_story_input_bundle(
    project: Any,
    *,
    writing_options: dict[str, str] | None = None,
    chapters_per_volume: int = 60,
) -> StoryInputBundle:
    outline_sentences = _split_sentences(getattr(project, "outline", ""))
    world_setting = str(getattr(project, "world_setting", "") or "")
    world_sentences = _split_sentences(world_setting)
    characters = parse_character_entries(str(getattr(project, "character_intro", "") or ""))
    character_names = [entry.name for entry in characters]
    total_chapters = max(int(getattr(project, "total_chapters", 0) or 0), 1)
    chapters_per_volume = max(int(chapters_per_volume or 60), 1)
    seed_goal_lock = _derive_seed_goal_lock(
        str(getattr(project, "title", "") or ""), outline_sentences
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
        locations=_extract_locations(world_setting),
        rules=_extract_rules(world_setting),
        hard_constraints=_extract_rules(world_setting)[:4],
        known_facts=_extract_rules(world_setting)[:6],
    )
    style_profile = StyleProfile(**{k: v for k, v in (writing_options or {}).items() if hasattr(StyleProfile, k)})

    chapter_plans: list[ChapterPlan] = []
    for chapter_number in range(1, total_chapters + 1):
        progress = (chapter_number - 1) / max(total_chapters - 1, 1)
        summary = _select_progressive(
            outline_sentences,
            progress,
            f"围绕{getattr(project, 'title', '主线')}推进本章冲突。",
        )
        world_focus = _select_progressive(world_sentences, progress, world_setting[:80])
        stage = _chapter_stage_label(progress)
        character_slice = character_names[:4]
        key_events = [summary] if summary else []
        if world_focus and world_focus != summary:
            key_events.append(f"在{world_focus}中推进{stage}阶段冲突")
        continuity_in = f"承接上一章局势，继续{stage}阶段推进。"
        continuity_out = f"为下一章保留{stage}阶段后的新压力或新线索。"
        magic_parts = [f"阶段目标：{stage}"]
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
                must_include=[summary] if summary else [],
                character_ids=[entry.id for entry in characters[:4]],
                character_names=character_slice,
                location_ids=[
                    _sanitize_id(location, "location")
                    for location in world_bible.locations[:3]
                ],
                continuity_in=continuity_in,
                continuity_out=continuity_out,
                goal_lock=seed_goal_lock,
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
