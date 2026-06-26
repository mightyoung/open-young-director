"""Novel Generator using multi-agent orchestration."""

from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
import re
from typing import Any

from young_writer.agents.writer_rules import (
    check_writer_rules,
    compact_writer_rule_summary,
)
from young_writer.services.narrative_driver import finalize_chapter_driver_context
from young_writer.services.story_graph.diff import build_graph_diff_details
from young_writer.writing_options import (
    build_writing_guidance,
    normalize_writing_options,
)


logger = logging.getLogger(__name__)

ABRUPT_TRANSITION_MARKERS = (
    "翌日",
    "次日",
    "第二天",
    "第三天",
    "三天后",
    "几天后",
    "数日后",
    "几日后",
    "半月后",
    "半个月后",
    "一月后",
    "一个月后",
    "数月后",
    "半年后",
    "一年后",
    "转眼",
    "另一边",
    "另一处",
    "与此同时",
)

TRANSITION_BRIDGE_SIGNALS = (
    "赶往",
    "来到",
    "返回",
    "回到",
    "抵达",
    "进入",
    "踏入",
    "走进",
    "推开",
    "穿过",
    "奔赴",
    "路上",
    "沿途",
    "于是",
    "因此",
    "随后",
    "不久",
    "与此同时",
    "一路",
)

HARD_GATE_ISSUE_TYPES = {
    "missing_key_events",
    "scene_or_timeline_disconnect",
    "world_fact_violation",
    "structure_drift_risk",
    "goal_lock_false_inheritance",
}

def classify_hard_gate_issue_types(issue_types: list[str]) -> list[str]:
    """Return deterministic issue types that are allowed to hard-block a chapter."""
    return [item for item in issue_types if item in HARD_GATE_ISSUE_TYPES]

HIGH_CONFIDENCE_LOCATION_SUFFIXES = (
    "实验室",
    "监测中心",
    "控制中心",
    "监控室",
    "声呐室",
    "控制室",
    "城邦",
    "海沟",
    "边界",
    "基地",
    "中心",
    "监测站",
    "舰桥",
    "指挥舱",
    "舱室",
    "城",
    "镇",
    "站",
    "街",
    "巷",
    "村",
    "山",
    "峰",
    "谷",
    "崖",
    "洞",
    "林",
    "湖",
    "河",
    "海",
    "岛",
    "区",
    "宫",
    "殿",
    "阁",
    "楼",
    "院",
    "府",
    "宅",
    "门",
    "宗",
    "台",
    "营",
    "关",
    "坊",
    "园",
    "寨",
    "栈",
    "庙",
    "厅",
    "室",
    "舱",
    "牢",
    "邦",
    "沟",
)

CONSEQUENCE_MARKERS = (
    "追杀",
    "追兵",
    "重伤",
    "伤势",
    "危机",
    "爆炸",
    "昏迷",
    "决裂",
    "生死",
    "濒死",
    "逃亡",
    "反噬",
    "崩塌",
    "暴露",
    "通缉",
    "血战",
)

CONSEQUENCE_ACKNOWLEDGEMENT_MARKERS = (
    "余波",
    "后遗症",
    "疗伤",
    "包扎",
    "恢复",
    "风波",
    "残局",
    "代价",
    "尚未",
    "仍在",
    "未散",
)

SUMMARY_CONSEQUENCE_CONTEXT_MARKERS = (
    "上一章结尾",
    "上一章末尾",
    "上一章最后",
    "还没来得及",
    "尚未",
    "仍在",
    "必须",
    "只能",
    "正要",
    "未能",
)

CONSEQUENCE_CLAUSE_PATTERNS = (
    re.compile(r"(必须在[^。！？\n]{0,40}之间做出选择)"),
    re.compile(r"([^。！？\n]{0,24}(?:逼近|警报|裂缝|中断|撤离|下探)[^。！？\n]{0,24})"),
)

OPENING_LOCATION_PREFIX_MARKERS = (
    "晨雾笼罩",
    "夜色笼罩",
    "暮色笼罩",
    "薄雾笼罩",
    "雾气笼罩",
    "雨幕笼罩",
    "风雪笼罩",
    "钟声回荡在",
    "灯火照着",
)
LOW_CONFIDENCE_LOCATION_ANCHORS = {
    "那扇门",
    "这扇门",
    "一扇门",
    "木门",
    "铁门",
    "石门",
    "房门",
    "舱门",
}
LOW_CONFIDENCE_LOCATION_PARTS = {
    "窗口",
    "信号",
    "图谱",
    "记录",
    "数据流",
    "波形",
    "警报",
}
NON_BRIDGE_TRANSITION_PATTERNS = (
    r"准备进入[\u4e00-\u9fff]{2,16}",
    r"必须进入[\u4e00-\u9fff]{2,16}",
    r"计划进入[\u4e00-\u9fff]{2,16}",
    r"打算进入[\u4e00-\u9fff]{2,16}",
    r"将进入[\u4e00-\u9fff]{2,16}",
    r"要求[\u4e00-\u9fff]{0,8}进入[\u4e00-\u9fff]{2,16}",
)
EVENT_ACTION_KEYWORDS = (
    "归来",
    "返回",
    "抵达",
    "进入",
    "验证",
    "调查",
    "追查",
    "查清",
    "确认",
    "协助",
    "救回",
    "拯救",
    "公开",
    "守住",
    "击败",
    "现身",
    "闯入",
    "夺取",
    "截获",
    "逃离",
    "突破",
    "寻找",
    "潜入",
    "破解",
)
EVENT_ACTION_SYNONYMS = {
    "归来": ("归来", "回来", "回到", "返回", "抵达"),
    "返回": ("返回", "回到", "归来", "回来", "折返"),
    "抵达": ("抵达", "到达", "赶到", "来到"),
    "进入": ("进入", "踏入", "冲入", "闯入", "潜入"),
    "验证": ("验证", "核实", "确认", "证实", "查验", "校验"),
    "调查": ("调查", "查探", "探查", "追查"),
    "追查": ("追查", "调查", "查探", "追索"),
    "查清": ("查清", "查明", "弄清", "摸清"),
    "确认": ("确认", "证实", "核实"),
    "协助": ("协助", "帮忙", "帮助", "配合", "支援", "帮我", "帮他", "帮她"),
    "救回": ("救回", "救出", "救下", "营救", "带回"),
    "拯救": ("拯救", "救下", "救出", "救回"),
    "公开": ("公开", "公布", "揭开", "揭露"),
    "守住": ("守住", "守下", "保住", "顶住"),
    "击败": ("击败", "打败", "战胜", "击倒"),
    "现身": ("现身", "出现", "露面"),
    "闯入": ("闯入", "冲进", "潜入", "进入"),
    "夺取": ("夺取", "夺下", "拿下", "抢下"),
    "截获": ("截获", "拦截", "收到", "捕获"),
    "逃离": ("逃离", "逃出", "脱身", "离开"),
    "突破": ("突破", "冲破", "打破", "突围"),
    "寻找": ("寻找", "找寻", "搜寻", "查找"),
    "潜入": ("潜入", "闯入", "混入", "进入"),
    "破解": ("破解", "解开", "破译", "拆解"),
}
EVENT_SPLIT_PATTERNS = re.compile(
    r"(?:带着|携带|拿着|并且|并|与|和|前往|进入|返回|归来|验证|调查|追查|查清|确认|协助|救回|拯救|公开|守住|击败|现身|闯入|夺取|截获|逃离|突破|寻找|潜入|破解|争取|请求|寻求|以及|然后|随后|为了|必须|正在|已经|开始|继续|尝试|的|了|在)"
)
EVENT_NOISE_TERMS = {
    "阶段目标",
    "设定约束",
    "重点人物",
    "开场",
    "推进",
    "承压",
    "转折",
    "升级",
    "收束",
    "当众",
}
COMPOUND_GOAL_CONNECTOR_PATTERN = re.compile(
    r"[、；;]|(?:并且|并|同时|随后|然后|再去|再向|并向|并找|并请|并争取)"
)
ANCHOR_LEADING_NOISE_PATTERN = re.compile(
    r"^(?:途中|此时|这时|随后|然后|继续|仍要|仍需|需要|必须|先|首先|立即|赶紧|设法|尝试|他|她|它|主角)+"
)
ORCHESTRATOR_DISABLE_THRESHOLD = 2
ORCHESTRATOR_MIN_CONTENT_CHARS = 800
ORCHESTRATOR_MAX_CONTENT_THRESHOLD = 1200

DISMISSIVE_CONTINUITY_MARKERS = (
    "从未发生",
    "像没发生",
    "仿佛没发生",
    "从来没有经历过",
    "若无其事",
    "全然不顾",
    "抛在脑后",
)

MOTION_CONTINUITY_MARKERS = (
    "离开",
    "摆脱",
    "准备",
    "赶往",
    "赶到",
    "前往",
    "转移",
    "连夜",
    "一路",
)
DEATH_MARKERS = ("死亡", "死去", "身亡", "陨落", "断气", "气绝", "毙命")
ITEM_LOSS_MARKERS = (
    "碎裂",
    "破碎",
    "耗尽",
    "用尽",
    "燃尽",
    "消散",
    "遗失",
    "丢失",
    "毁掉",
    "损毁",
)
ITEM_REAPPEAR_MARKERS = ("重新", "再次", "依然", "仍然", "又", "再度")
ANTI_DRIFT_BRIDGE_CONNECTORS = (
    "为了",
    "因此",
    "所以",
    "必须",
    "要想",
    "才能",
    "目标是",
    "于是",
    "借此",
    "好让",
)
GOAL_LOCK_NEGATION_MARKERS = (
    "没有再提",
    "不再提",
    "只是想起",
    "只是提到",
    "仅是提到",
    "口头提到",
    "嘴上提到",
    "却只是",
    "却只是在",
    "并未",
    "未能",
    "没能",
    "无暇",
)
ANTI_DRIFT_GOAL_STOPWORDS = {
    "当前",
    "阶段",
    "主线",
    "目标",
    "继续",
    "推进",
    "问题",
    "事情",
    "这个",
    "那个",
    "自己",
    "他们",
    "我们",
    "已经",
    "必须要",
}
ANTI_DRIFT_SETTING_NOUNS = (
    "势力",
    "门派",
    "体系",
    "境界",
    "规则",
    "秘境",
    "神器",
    "法则",
    "系统",
    "序列",
    "途径",
    "血脉",
    "传承",
    "阵营",
    "宗门",
    "王朝",
    "组织",
    "禁地",
    "遗迹",
)
ANTI_DRIFT_INTRO_CUES = (
    "新的",
    "新出现的",
    "又一",
    "突然出现的",
    "传说中的",
    "从未听闻的",
    "陌生的",
)
ANTI_DRIFT_INTRO_PATTERN = re.compile(
    r"("
    + "|".join(re.escape(cue) for cue in ANTI_DRIFT_INTRO_CUES)
    + r")[\u4e00-\u9fff]{0,8}("
    + "|".join(re.escape(noun) for noun in ANTI_DRIFT_SETTING_NOUNS)
    + r")"
)


@dataclass
class GeneratedChapter:
    """Represents a generated chapter."""

    number: int
    title: str
    content: str
    word_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    plot_summary: dict[str, Any] | None = None
    consistency_report: dict[str, Any] | None = None
    generation_time: str = ""
    # Optional novel orchestrator diagnostics.
    orchestrator_result: dict[str, Any] | None = None


class NovelGeneratorAgent:
    """Agent for generating novel chapters using orchestration."""

    def __init__(
        self,
        config_manager,
        novel_orchestrator=None,
        llm_client=None,
        allow_fallback: bool = True,
    ):
        self.config_manager = config_manager
        self.orchestrator = novel_orchestrator
        self.llm_client = llm_client
        self.allow_fallback = allow_fallback
        self._orchestrator_consecutive_failures = 0
        self._orchestrator_disabled_for_run = False

        self.outline_loader = None
        self.outline_enforcer = None

        self._load_outline_loader()

    def _load_outline_loader(self):
        """Load outline loader and enforcer."""
        try:
            from young_writer.agents.outline_loader import (
                OutlineEnforcer,
                OutlineLoader,
            )

            project = self.config_manager.current_project
            if project:
                output_dir = getattr(self.config_manager.generation, "output_dir", "")
                if output_dir:
                    outline_dir = Path(output_dir).resolve() / "outline"
                else:
                    project_paths = self.config_manager.paths.project_paths(
                        title=project.title,
                        project_id=project.id,
                    )
                    outline_dir = project_paths.project_dir / "outline"
                self.outline_loader = OutlineLoader(str(outline_dir))
                self.outline_enforcer = OutlineEnforcer(self.outline_loader)
                logger.info("OutlineLoader initialized for novel generation")
        except Exception as e:
            logger.warning(f"Could not initialize OutlineLoader: {e}")

    def generate_chapter(
        self,
        chapter_number: int,
        context: dict[str, Any],
        previous_summary: str = "",
        writing_options: dict[str, str] | None = None,
    ) -> GeneratedChapter:
        """Generate a single chapter."""
        packet_plan = self._packet_plan(context)
        outline_info = None
        if packet_plan:
            outline_info = {
                "title": packet_plan.get("title", f"第{chapter_number}章"),
                "summary": packet_plan.get("summary", ""),
                "key_events": list(packet_plan.get("key_events", []) or []),
                "magic_line": packet_plan.get("magic_line", ""),
                "goal_lock": packet_plan.get("goal_lock", ""),
                "continuity_in": packet_plan.get("continuity_in", ""),
                "continuity_out": packet_plan.get("continuity_out", ""),
            }
        if not outline_info:
            outline_info = self._get_chapter_outline(chapter_number)

        if not outline_info:
            logger.warning(f"No outline found for chapter {chapter_number}")
            outline_info = self._fallback_outline_summary(chapter_number, context)

        title = outline_info.get("title", f"第{chapter_number}章")
        outline_summary = outline_info.get("summary", "")
        continuity_in = str(outline_info.get("continuity_in", "") or "").strip()
        continuity_out = str(outline_info.get("continuity_out", "") or "").strip()
        if continuity_in:
            outline_summary = f"{continuity_in}\n{outline_summary}"
        if continuity_out:
            outline_summary = f"{outline_summary}\n收束要求：{continuity_out}"
        # P0 FIX: Include magic_line (魔帝线) in the outline so it's not lost
        magic_line = outline_info.get("magic_line", "")
        if magic_line:
            outline_summary = f"{outline_summary}；【暗线】{magic_line}"

        # Get target word count from config
        target_word_count = self._get_target_word_count()
        min_word_count = int(target_word_count * 0.8)  # Allow 20% tolerance

        generation_context = dict(context or {})
        finalize_chapter_driver_context(generation_context)
        generation_context["chapter_intent_contract"] = (
            self._build_chapter_intent_contract(
                outline=outline_summary,
                context=generation_context,
                chapter_guidance=str(
                    generation_context.get("chapter_guidance", "") or ""
                ).strip(),
            )
        )
        generation_context["chapter_intent_check"] = self._check_chapter_intent(
            outline=outline_summary,
            context=generation_context,
        )
        generation_context["generation_outline"] = str(
            generation_context["chapter_intent_check"].get("rewritten_outline", "")
            or outline_summary
        )
        effective_previous_summary = str(
            previous_summary or generation_context.get("previous_summary", "") or ""
        )

        rewrite_history: list[dict[str, Any]] = []
        result = self._generate_candidate(
            chapter_number=chapter_number,
            title=title,
            outline=generation_context["generation_outline"],
            previous_summary=effective_previous_summary,
            context=generation_context,
            writing_options=writing_options,
            target_word_count=target_word_count,
            min_word_count=min_word_count,
        )
        chapter = self._create_chapter(
            chapter_number=chapter_number,
            title=title,
            content=result["content"],
            outline_summary=outline_summary,
            outline_info=outline_info,
            magic_line=magic_line,
            context=generation_context,
            writing_options=writing_options,
            orchestrator_result=result.get("orchestrator_result"),
            generation_trace=result.get("generation_trace"),
        )

        chapter.consistency_report = self._check_consistency(
            chapter, effective_previous_summary, generation_context
        )
        if chapter.consistency_report.get("invalid"):
            rewrite_history.append(
                {
                    "attempt": 0,
                    "mode": "initial",
                    "invalid": True,
                    "issue_types": list(
                        chapter.consistency_report.get("issue_types", [])
                    ),
                    "blocking_issues": list(
                        chapter.consistency_report.get("blocking_issues", [])
                    ),
                    "generated_at": datetime.now().isoformat(),
                }
            )
            chapter = self._rewrite_invalid_chapter(
                chapter=chapter,
                previous_summary=effective_previous_summary,
                context=generation_context,
                writing_options=writing_options,
                outline_summary=outline_summary,
                outline_info=outline_info,
                magic_line=magic_line,
                target_word_count=target_word_count,
                min_word_count=min_word_count,
                rewrite_history=rewrite_history,
            )
        else:
            chapter.consistency_report["rewrite_attempted"] = False
            chapter.consistency_report["rewrite_succeeded"] = False
        chapter.metadata["rewrite_history"] = list(rewrite_history)
        chapter.consistency_report["rewrite_history"] = list(rewrite_history)
        chapter.consistency_report["chapter_intent_contract"] = dict(
            generation_context.get("chapter_intent_contract", {}) or {}
        )
        chapter.consistency_report["chapter_driver_packet"] = dict(
            generation_context.get("chapter_driver_packet", {}) or {}
        )
        chapter.consistency_report["chapter_driver_summary"] = str(
            generation_context.get("chapter_driver_summary", "") or ""
        )
        chapter.consistency_report["chapter_driver_validation"] = list(
            generation_context.get("chapter_driver_validation", []) or []
        )

        return chapter

    def _get_target_word_count(self) -> int:
        """Get target word count from config."""
        try:
            if self.config_manager and self.config_manager.generation:
                return self.config_manager.generation.chapter_word_count
        except Exception:
            pass
        return 3000  # Default fallback

    def _min_orchestrator_content_chars(self, target_word_count: int) -> int:
        """Return the minimum assembled orchestrator output to accept."""
        return max(
            ORCHESTRATOR_MIN_CONTENT_CHARS,
            min(ORCHESTRATOR_MAX_CONTENT_THRESHOLD, max(target_word_count // 3, 0)),
        )

    def _record_orchestrator_failure(
        self, failure_reasons: list[str]
    ) -> dict[str, Any]:
        """Track orchestrator failures and disable it for the remainder of the run."""
        self._orchestrator_consecutive_failures += 1
        disabled_now = False
        if self._orchestrator_consecutive_failures >= ORCHESTRATOR_DISABLE_THRESHOLD:
            self._orchestrator_disabled_for_run = True
            disabled_now = True
        logger.warning(
            "[Generator] Orchestrator attempt rejected: %s (consecutive failures=%s, disabled=%s)",
            ",".join(failure_reasons),
            self._orchestrator_consecutive_failures,
            self._orchestrator_disabled_for_run,
        )
        return {
            "consecutive_failures": self._orchestrator_consecutive_failures,
            "disabled_for_run": self._orchestrator_disabled_for_run,
            "disabled_now": disabled_now,
        }

    def _build_orchestrator_diagnostics(
        self,
        orchestrator_result: dict[str, Any] | None,
        context: dict[str, Any],
        target_word_count: int,
    ) -> dict[str, Any]:
        """Evaluate whether orchestrator output is strong enough to keep."""
        result = orchestrator_result or {}
        plot_outline = result.get("plot_outline") or {}
        beats = list(plot_outline.get("beats") or [])
        cast = list(result.get("cast") or [])
        content = str(result.get("content") or "")
        min_content_chars = self._min_orchestrator_content_chars(target_word_count)

        failure_reasons: list[str] = []
        if not beats:
            failure_reasons.append("beat_parse_failed")
        if not cast:
            failure_reasons.append("character_plan_empty")
        if len(content) < min_content_chars:
            failure_reasons.append("scene_assembly_too_short")

        return {
            "attempted": True,
            "accepted": not failure_reasons,
            "failure_reasons": failure_reasons,
            "beat_count": len(beats),
            "cast_count": len(cast),
            "content_chars": len(content),
            "min_content_chars": min_content_chars,
            "chapter_number": context.get("chapter_number"),
        }

    def _orchestrator_preflight(self, context: dict[str, Any] | None) -> dict[str, Any]:
        """Check whether the orchestrator has enough structured input to run."""
        ctx = context or {}
        character_source = ctx.get("characters")
        if isinstance(character_source, dict) and character_source:
            character_count = len(
                [name for name in character_source.keys() if str(name or "").strip()]
            )
        elif isinstance(character_source, list):
            character_count = len(
                [
                    item
                    for item in character_source
                    if isinstance(item, dict) and str(item.get("name", "") or "").strip()
                ]
            )
        else:
            packet_characters = self._packet_characters(ctx)
            if packet_characters:
                character_count = len(
                    [
                        item
                        for item in packet_characters
                        if str(item.get("name", "") or "").strip()
                    ]
                )
            else:
                character_count = len(
                    [
                        name
                        for name in ctx.get("character_names", [])
                        if str(name or "").strip()
                    ]
                )

        failure_reasons: list[str] = []
        if character_count <= 0:
            failure_reasons.append("orchestrator_preflight_no_characters")
        return {
            "passed": not failure_reasons,
            "failure_reasons": failure_reasons,
            "character_count": character_count,
        }

    def _resolve_known_char_names(
        self, context: dict[str, Any] | None = None
    ) -> list[str]:
        """Resolve character anchors from the real generation context."""
        ctx = context or {}
        packet_characters = self._packet_characters(ctx)
        if packet_characters:
            packet_names = [
                str(character.get("name", "") or "").strip()
                for character in packet_characters
                if str(character.get("name", "") or "").strip()
            ]
            if packet_names:
                return packet_names[:8]
        names = list(ctx.get("known_char_names") or ctx.get("character_names") or [])
        if names:
            return [str(name) for name in names if str(name or "").strip()]

        raw_character_intro = str(ctx.get("character_intro", "") or "")
        extracted = [
            name.strip()
            for name in re.findall(r"([\u4e00-\u9fff]{2,6})[：:]", raw_character_intro)
        ]
        if extracted:
            return extracted[:8]

        return ["韩林", "柳如烟", "叶尘"]

    def _generation_packet(self, context: dict[str, Any] | None) -> dict[str, Any]:
        return dict((context or {}).get("generation_packet", {}) or {})

    def _packet_plan(self, context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._generation_packet(context).get("chapter_plan", {}) or {})

    def _packet_world(self, context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._generation_packet(context).get("world_bible", {}) or {})

    def _packet_project(self, context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._generation_packet(context).get("project_bible", {}) or {})

    def _packet_characters(self, context: dict[str, Any] | None) -> list[dict[str, Any]]:
        return list(self._generation_packet(context).get("characters", []) or [])

    def _packet_runtime(self, context: dict[str, Any] | None) -> dict[str, Any]:
        return dict(self._generation_packet(context).get("runtime_overrides", {}) or {})

    def _fallback_outline_summary(
        self, chapter_number: int, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        project_packet = self._packet_project(context)
        world_packet = self._packet_world(context)
        packet_characters = self._packet_characters(context)
        project_outline = str(
            project_packet.get("synopsis", "")
            or project_packet.get("premise", "")
            or (context or {}).get("project_outline", "")
            or getattr(self.config_manager.current_project, "outline", "")
            or ""
        ).strip()
        world_setting = str(
            world_packet.get("summary", "")
            or (context or {}).get("world_setting", "")
            or getattr(self.config_manager.current_project, "world_setting", "")
            or ""
        ).strip()
        if packet_characters:
            character_intro = "\n".join(
                f"{str(character.get('name', '') or '').strip()}："
                f"{str(character.get('motivation', '') or character.get('role', '') or '关键角色').strip()}"
                for character in packet_characters
                if str(character.get("name", "") or "").strip()
            ).strip()
        else:
            character_intro = str(
                (context or {}).get("character_intro", "")
                or getattr(self.config_manager.current_project, "character_intro", "")
                or ""
            ).strip()
        fallback_summary_parts = [
            part for part in (project_outline, world_setting, character_intro) if part
        ]
        return {
            "title": f"第{chapter_number}章",
            "summary": "\n".join(fallback_summary_parts),
            "key_events": [],
        }

    def _get_chapter_outline(self, chapter_number: int) -> dict[str, Any] | None:
        """Get chapter outline from loader."""
        if not self.outline_enforcer:
            return None

        try:
            return self.outline_enforcer.get_chapter_outline(chapter_number)
        except Exception as e:
            logger.warning(f"Could not get chapter outline: {e}")
            return None

    def _generate_candidate(
        self,
        *,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        context: dict[str, Any],
        writing_options: dict[str, str] | None,
        target_word_count: int,
        min_word_count: int,
        rewrite_guidance: str = "",
        force_direct_llm: bool = False,
    ) -> dict[str, Any]:
        """Generate a candidate chapter with retry on low word count."""
        max_retries = 2
        content = ""
        orchestrator_result = None
        generation_trace: dict[str, Any] | None = None

        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.info(
                    "[Generator] Retry %s/%s for chapter %s, previous word count was too low",
                    attempt,
                    max_retries,
                    chapter_number,
                )

            result = self._generate_content(
                chapter_number=chapter_number,
                title=title,
                outline=outline,
                previous_summary=previous_summary,
                context=context,
                retry_attempt=attempt,
                writing_options=writing_options,
                rewrite_guidance=rewrite_guidance,
                force_direct_llm=force_direct_llm,
            )

            content = result["content"]
            if attempt == 0 and result.get("orchestrator_result"):
                orchestrator_result = result["orchestrator_result"]
            if result.get("generation_trace") is not None:
                generation_trace = result["generation_trace"]

            word_count = self._count_words(content)
            logger.info(
                "[Generator] Chapter %s attempt %s: %s chars (target: %s)",
                chapter_number,
                attempt + 1,
                word_count,
                target_word_count,
            )

            if word_count >= min_word_count:
                logger.info(
                    "[Generator] Word count %s meets target %s",
                    word_count,
                    target_word_count,
                )
                break
            if attempt < max_retries:
                logger.warning(
                    "[Generator] Word count %s below target %s, will retry",
                    word_count,
                    target_word_count,
                )

        return {
            "content": content,
            "orchestrator_result": orchestrator_result,
            "generation_trace": generation_trace or {},
        }

    def _create_chapter(
        self,
        *,
        chapter_number: int,
        title: str,
        content: str,
        outline_summary: str,
        outline_info: dict[str, Any],
        magic_line: str,
        context: dict[str, Any] | None,
        writing_options: dict[str, str] | None,
        orchestrator_result: dict[str, Any] | None,
        generation_trace: dict[str, Any] | None,
    ) -> GeneratedChapter:
        """Create a GeneratedChapter object from raw content."""
        goal_lock = self._extract_goal_lock(context)
        goal_terms = self._goal_terms(goal_lock)
        return GeneratedChapter(
            number=chapter_number,
            title=title,
            content=content,
            word_count=self._count_words(content),
            metadata={
                "outline_summary": outline_summary,
                "key_events": outline_info.get("key_events", []),
                "magic_line": magic_line,
                "character_appearances": outline_info.get("characters", []),
                "writing_options": normalize_writing_options(writing_options),
                "generation_time": datetime.now().isoformat(),
                "goal_lock": goal_lock,
                "goal_terms": goal_terms,
                "goal_lock_resolution": dict(
                    (context or {}).get("goal_lock_resolution", {}) or {}
                ),
                "generation_trace": dict(generation_trace or {}),
                "chapter_intent_contract": dict(
                    (context or {}).get("chapter_intent_contract", {}) or {}
                ),
            },
            plot_summary={
                "l1_one_line_summary": outline_summary[:100] if outline_summary else "",
                "l2_brief_summary": outline_summary,
                "l3_key_plot_points": outline_info.get("key_events", []),
                "magic_line": magic_line,
                "goal_lock": goal_lock,
                "goal_terms": goal_terms,
            },
            generation_time=datetime.now().isoformat(),
            orchestrator_result=orchestrator_result,
        )

    def _rewrite_invalid_chapter(
        self,
        *,
        chapter: GeneratedChapter,
        previous_summary: str,
        context: dict[str, Any],
        writing_options: dict[str, str] | None,
        outline_summary: str,
        outline_info: dict[str, Any],
        magic_line: str,
        target_word_count: int,
        min_word_count: int,
        rewrite_history: list[dict[str, Any]],
    ) -> GeneratedChapter:
        """Run one targeted full-chapter rewrite for invalid output."""
        report = chapter.consistency_report or {}
        repair_plan = self._build_chapter_repair_plan(
            report=report,
            outline_summary=outline_summary,
            context=context,
        )
        guidance = self._format_rewrite_guidance(repair_plan)
        generation_outline = str(
            context.get("generation_outline", "") or outline_summary
        )
        rewrite_context = dict(context)
        rewrite_context["chapter_repair_plan"] = repair_plan
        result = self._generate_candidate(
            chapter_number=chapter.number,
            title=chapter.title,
            outline=self._compose_rewrite_outline(
                outline=generation_outline,
                repair_plan=repair_plan,
            ),
            previous_summary=previous_summary,
            context=rewrite_context,
            writing_options=writing_options,
            target_word_count=target_word_count,
            min_word_count=min_word_count,
            rewrite_guidance=guidance,
        )
        rewritten = self._create_chapter(
            chapter_number=chapter.number,
            title=chapter.title,
            content=result["content"],
            outline_summary=outline_summary,
            outline_info=outline_info,
            magic_line=magic_line,
            context=rewrite_context,
            writing_options=writing_options,
            orchestrator_result=result.get("orchestrator_result"),
            generation_trace=result.get("generation_trace"),
        )
        rewritten.consistency_report = self._check_consistency(
            rewritten, previous_summary, rewrite_context
        )
        rewritten.consistency_report["rewrite_attempted"] = True
        rewritten.consistency_report[
            "rewrite_succeeded"
        ] = not rewritten.consistency_report.get("invalid", False)
        rewrite_history.append(
            {
                "attempt": 1,
                "mode": "targeted_full_rewrite",
                "invalid": bool(rewritten.consistency_report.get("invalid")),
                "issue_types": list(
                    rewritten.consistency_report.get("issue_types", [])
                ),
                "blocking_issues": list(
                    rewritten.consistency_report.get("blocking_issues", [])
                ),
                "repair_plan": repair_plan,
                "guidance": guidance,
                "generated_at": datetime.now().isoformat(),
            }
        )
        return rewritten

    def _build_chapter_repair_plan(
        self,
        *,
        report: dict[str, Any],
        outline_summary: str,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        repair_plan = self._build_rewrite_plan(report)
        anti_drift = dict(report.get("anti_drift_details", {}) or {})
        blocking_issues = [
            str(item).strip()
            for item in report.get("blocking_issues", [])
            if str(item).strip()
        ]
        missing_events = [
            str(item).strip()
            for item in report.get("missing_events", [])
            if str(item).strip()
        ]
        goal_lock = str(anti_drift.get("goal_lock", "") or "").strip()
        goal_subgoals = self._split_compound_goal_fragments(goal_lock)
        ordered_beats: list[dict[str, Any]] = []
        continuity_anchor_contract: dict[str, str] = {}
        if report.get("continuity_issues"):
            ordered_beats.append(
                {
                    "phase": "opening",
                    "required_action": "承接上一章残留后果或地点/时间切换",
                    "evidence": list(report.get("continuity_issues", []))[:2],
                }
            )
        for item in report.get("smoothness_details", []) or []:
            if not isinstance(item, dict):
                continue
            if str(item.get("category", "") or "").strip() != "地点跳切无承接":
                continue
            previous_anchor = str(item.get("previous_evidence", "") or "").strip()
            current_anchor = str(item.get("current_evidence", "") or "").strip()
            if previous_anchor and current_anchor:
                continuity_anchor_contract = {
                    "previous_anchor": previous_anchor,
                    "current_anchor": current_anchor,
                    "instruction": (
                        f"开篇先接住「{previous_anchor}」；如需切到「{current_anchor}」，"
                        f"必须写出路径、抵达动作或切换原因，不得直接在「{current_anchor}」重开。"
                    ),
                }
                break
        if missing_events:
            ordered_beats.append(
                {
                    "phase": "development",
                    "required_action": "覆盖必须发生的关键事件",
                    "must_include": missing_events,
                }
            )
        if goal_lock:
            ordered_beats.append(
                {
                    "phase": "conflict",
                    "required_action": "把关键行动、选择或结果重新对准目标锁",
                    "goal_lock": goal_lock,
                    "goal_subgoals": goal_subgoals,
                    "matched_fragments": list(anti_drift.get("matched_fragments", []))[:2],
                }
            )
        ordered_beats.append(
            {
                "phase": "resolution",
                "required_action": "用本章结果自然引出下一章压力，不留无解释跳切",
                "continuity_out": str(
                    ((context or {}).get("chapter_plan", {}) or {}).get("continuity_out", "")
                ).strip(),
            }
        )
        repair_plan.update(
            {
                "rewrite_mode": "plan_first_full_rewrite",
                "outline_summary": outline_summary,
                "goal_lock": goal_lock,
                "goal_subgoals": goal_subgoals,
                "opening_bridge": list(report.get("continuity_issues", []))[:2],
                "must_include_events": missing_events,
                "continuity_anchor_contract": continuity_anchor_contract,
                "failure_evidence": {
                    "issue_types": list(report.get("issue_types", [])),
                    "blocking_issues": blocking_issues[:4],
                    "anti_drift_details": anti_drift,
                },
                "ordered_beats": ordered_beats,
            }
        )
        return repair_plan

    def _compose_rewrite_outline(
        self,
        *,
        outline: str,
        repair_plan: dict[str, Any],
    ) -> str:
        lines = [str(outline or "").strip()]
        opening_bridge = [
            str(item).strip() for item in repair_plan.get("opening_bridge", []) if str(item).strip()
        ]
        must_include_events = [
            str(item).strip()
            for item in repair_plan.get("must_include_events", [])
            if str(item).strip()
        ]
        goal_lock = str(repair_plan.get("goal_lock", "") or "").strip()
        goal_subgoals = [
            str(item).strip()
            for item in repair_plan.get("goal_subgoals", [])
            if str(item).strip()
        ]
        continuity_anchor_contract = (
            repair_plan.get("continuity_anchor_contract", {})
            if isinstance(repair_plan.get("continuity_anchor_contract", {}), dict)
            else {}
        )
        ordered_beats = [
            item for item in repair_plan.get("ordered_beats", []) if isinstance(item, dict)
        ]
        lines.append("【重写执行蓝图】")
        if opening_bridge:
            lines.append("开场先承接：")
            lines.extend(f"- {item}" for item in opening_bridge[:2])
        if continuity_anchor_contract:
            instruction = str(continuity_anchor_contract.get("instruction", "") or "").strip()
            if instruction:
                lines.append("场景锚点硬约束：")
                lines.append(f"- {instruction}")
        if must_include_events:
            lines.append("必须落实事件：")
            lines.extend(f"- {item}" for item in must_include_events[:3])
        if goal_lock:
            lines.append(f"主线目标锁：{goal_lock}")
        if len(goal_subgoals) > 1:
            lines.append("目标锁必须逐项落地：")
            lines.extend(f"- {item}" for item in goal_subgoals[:4])
        if ordered_beats:
            lines.append("重写节拍：")
            for index, beat in enumerate(ordered_beats[:4], start=1):
                phase = str(beat.get("phase", "") or "").strip()
                action = str(beat.get("required_action", "") or "").strip()
                if phase and action:
                    lines.append(f"{index}. {phase}: {action}")
        return "\n".join(part for part in lines if str(part).strip())

    def _generate_content(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        context: dict[str, Any],
        retry_attempt: int = 0,
        writing_options: dict[str, str] | None = None,
        rewrite_guidance: str = "",
        force_direct_llm: bool = False,
    ) -> dict[str, Any]:
        """Generate chapter content using LLM or orchestrator.

        Returns:
            Dict with:
                - content: str - the generated chapter content
                - orchestrator_result: Optional[Dict] - full result from the novel orchestrator
        """
        default_result = {
            "content": "",
            "orchestrator_result": None,
            "generation_trace": {"path": "uninitialized"},
        }

        if not self.llm_client:
            if not self.allow_fallback:
                raise RuntimeError("LLM client unavailable and fallback disabled")
            content = self._generate_fallback_content(
                chapter_number, title, outline, previous_summary, context
            )
            return {
                "content": content,
                "orchestrator_result": None,
                "generation_trace": {
                    "path": "fallback_content",
                    "reason": "llm_client_unavailable",
                },
            }

        project = self.config_manager.current_project
        genre = (
            str((context or {}).get("genre", "") or "").strip()
            or (project.genre if project else "")
            or "长篇小说"
        )
        target_word_count = self._get_target_word_count()

        orchestrator_trace: dict[str, Any] = {
            "attempted": False,
            "accepted": False,
            "failure_reasons": [],
            "consecutive_failures": self._orchestrator_consecutive_failures,
            "disabled_for_run": self._orchestrator_disabled_for_run,
        }
        chapter_repair_plan = dict((context or {}).get("chapter_repair_plan", {}) or {})
        prefer_orchestrator_rewrite = (
            bool(chapter_repair_plan)
            and str(chapter_repair_plan.get("rewrite_mode", "") or "").strip()
            == "plan_first_full_rewrite"
        )

        # P2 FIX: use orchestrator only while it clears deterministic quality checks
        if (
            self.orchestrator is not None
            and retry_attempt == 0
            and not force_direct_llm
            and not self._orchestrator_disabled_for_run
            and (not rewrite_guidance or prefer_orchestrator_rewrite)
        ):
            # Only use orchestrator on first attempt
            preflight = self._orchestrator_preflight(context)
            if not preflight["passed"]:
                orchestrator_trace.update(
                    {
                        "attempted": False,
                        "accepted": False,
                        "failure_reasons": list(preflight["failure_reasons"]),
                        "preflight": preflight,
                    }
                )
                logger.info(
                    "[Generator] Skipping orchestrator for chapter %s: %s",
                    chapter_number,
                    ",".join(preflight["failure_reasons"]),
                )
            else:
                try:
                    logger.info(
                        f"[Generator] Using orchestrator for chapter {chapter_number}"
                    )
                    orchestrator_result = self.orchestrator.orchestrate_chapter(
                        chapter_number=chapter_number,
                        chapter_outline=outline,
                        context=context,
                    )
                    orchestrator_trace = self._build_orchestrator_diagnostics(
                        orchestrator_result=orchestrator_result,
                        context=context,
                        target_word_count=target_word_count,
                    )
                    if orchestrator_trace["accepted"]:
                        self._orchestrator_consecutive_failures = 0
                        content = str(orchestrator_result.get("content") or "")
                        logger.info(
                            "[Generator] Orchestrator accepted for chapter %s: %s chars, %s beats, %s cast",
                            chapter_number,
                            len(content),
                            orchestrator_trace["beat_count"],
                            orchestrator_trace["cast_count"],
                        )
                        return {
                            "content": content,
                            "orchestrator_result": orchestrator_result,
                            "generation_trace": {
                                "path": "orchestrator_rewrite"
                                if prefer_orchestrator_rewrite
                                else "orchestrator",
                                "orchestrator": orchestrator_trace,
                            },
                        }
                    orchestrator_trace.update(
                        self._record_orchestrator_failure(
                            list(orchestrator_trace["failure_reasons"])
                        )
                    )
                except Exception as e:
                    orchestrator_trace = {
                        "attempted": True,
                        "accepted": False,
                        "failure_reasons": ["orchestrator_exception"],
                        "error": str(e),
                    }
                    orchestrator_trace.update(
                        self._record_orchestrator_failure(["orchestrator_exception"])
                    )
                    logger.warning(
                        f"[Generator] Orchestrator failed, falling back to direct LLM: {e}"
                    )
        elif self._orchestrator_disabled_for_run and retry_attempt == 0:
            orchestrator_trace = {
                "attempted": False,
                "accepted": False,
                "failure_reasons": ["orchestrator_backoff_active"],
                "consecutive_failures": self._orchestrator_consecutive_failures,
                "disabled_for_run": True,
            }

        # Fallback: direct LLM generation
        # Extract previous chapters from context
        previous_chapters = context.get("previous_chapters", [])
        chapter_dir = context.get("chapter_dir", "")
        world_name = context.get("world_name", "")
        character_names = context.get("character_names", [])
        packet_world = self._packet_world(context)
        packet_characters = self._packet_characters(context)
        packet_plan = self._packet_plan(context)
        if not world_name:
            locations = packet_world.get("locations", []) if isinstance(packet_world, dict) else []
            if locations:
                world_name = str(locations[0] or "").strip()
        if not character_names and packet_characters:
            character_names = [
                str(character.get("name", "") or "").strip()
                for character in packet_characters
                if str(character.get("name", "") or "").strip()
            ][:8]
        if not world_name:
            world_name = str((context or {}).get("world_setting", "") or "").strip()[:120]
        if not character_names:
            character_names = self._resolve_known_char_names(context)[:8]
        protagonist_constraint = context.get("protagonist_constraint", "")
        volume_guidance = self._compose_volume_guidance(context)
        goal_lock_guidance = self._build_goal_lock_guidance(context)
        context = context or {}
        chapter_guidance = str(context.get("chapter_guidance", "") or "").strip()
        finalize_chapter_driver_context(context)
        if not (context or {}).get("chapter_intent_contract"):
            context["chapter_intent_contract"] = self._build_chapter_intent_contract(
                outline=outline,
                context=context,
                chapter_guidance=chapter_guidance,
            )
        chapter_intent_contract = self._format_chapter_intent_contract(
            (context or {}).get("chapter_intent_contract")
        )
        if packet_plan.get("must_include"):
            chapter_intent_contract = "\n".join(
                part
                for part in [
                    chapter_intent_contract,
                    "附加强制输入: 必须覆盖 "
                    + " / ".join(str(item) for item in packet_plan.get("must_include", []) if item),
                ]
                if str(part or "").strip()
            )

        prompt = self._build_generation_prompt(
            chapter_number,
            title,
            outline,
            previous_summary,
            genre,
            previous_chapters=previous_chapters,
            chapter_dir=chapter_dir,
            world_name=world_name,
            character_names=character_names,
            target_word_count=target_word_count,
            retry_attempt=retry_attempt,
            protagonist_constraint=protagonist_constraint,
            volume_guidance=volume_guidance,
            goal_lock_guidance=goal_lock_guidance,
            chapter_intent_contract=chapter_intent_contract,
            chapter_guidance=chapter_guidance,
            writing_options=writing_options,
            rewrite_guidance=rewrite_guidance,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            # Increase max_tokens for retry to allow longer output
            max_tokens = 15000 if retry_attempt > 0 else 12000
            content = self.llm_client.generate(
                messages, temperature=0.8, max_tokens=max_tokens
            )

            if len(content) < 500:
                if not self.allow_fallback:
                    raise RuntimeError(
                        f"LLM output too short ({len(content)} chars) and fallback disabled"
                    )
                logger.warning(
                    f"Generated content too short ({len(content)} chars), using fallback"
                )
                content = self._generate_fallback_content(
                    chapter_number, title, outline, previous_summary, context
                )

            return {
                "content": content,
                "orchestrator_result": None,
                "generation_trace": {
                    "path": "direct_llm",
                    "orchestrator": orchestrator_trace,
                },
            }

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            if not self.allow_fallback:
                raise RuntimeError("LLM generation failed and fallback disabled") from e
            content = self._generate_fallback_content(
                chapter_number, title, outline, previous_summary, context
            )
            return {
                "content": content,
                "orchestrator_result": None,
                "generation_trace": {
                    "path": "fallback_content",
                    "reason": "llm_generation_failed",
                    "orchestrator": orchestrator_trace,
                },
            }

    def _build_generation_prompt(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        genre: str,
        previous_chapters: list[dict] = None,
        chapter_dir: str = "",
        world_name: str = "",
        character_names: list[str] = None,
        target_word_count: int = 3000,
        retry_attempt: int = 0,
        protagonist_constraint: str = "",
        volume_guidance: str = "",
        goal_lock_guidance: str = "",
        chapter_intent_contract: str = "",
        chapter_guidance: str = "",
        writing_options: dict[str, str] | None = None,
        rewrite_guidance: str = "",
    ) -> str:
        """Build generation prompt for kimi-cli (coding agent style).

        kimi-cli is a coding agent, not a pure text generator.
        We need to frame the request like a code generation task.

        Uses progressive disclosure to provide previous chapter information:
        - Level 1: Brief summary (always included)
        - Level 2: Key events and character states (if available)
        - Level 3: File path for kimi-cli to read actual content (for chapters 1-2 back)
        """
        previous_chapters = previous_chapters or []
        character_names = character_names or []
        guidance = build_writing_guidance(writing_options)
        normalized_options = guidance["normalized"]
        try:
            writer_rule_summary = compact_writer_rule_summary()
        except Exception as exc:
            logger.warning("Could not load writer rules for prompt: %s", exc)
            writer_rule_summary = ""

        # Build previous chapters context with progressive disclosure
        prev_context = self._build_previous_chapters_context(
            previous_chapters, chapter_dir, chapter_number
        )

        # Build world constraints section
        world_constraints = ""
        if world_name:
            world_constraints += f"\n- 主要舞台: {world_name}（若本章发生在此处，名称必须保持一致）"
        if character_names:
            world_constraints += f"\n- 主要人物: {', '.join(character_names)}"

        # Add retry warning if this is a retry due to insufficient word count
        retry_warning = ""
        if retry_attempt > 0:
            retry_warning = f"""
【重要提醒 - 第{retry_attempt + 1}次生成】
上次生成的字数不足！本次生成必须确保输出中文字数达到 {target_word_count} 字以上。
请务必：
1. 充分展开情节细节，使用丰富的场景描写
2. 让人物有足够的对话和心理描写
3. 不跳过任何重要的情节点
字数要求：最少 {target_word_count} 字！
"""
        else:
            retry_warning = f"""
【字数要求】
本章必须达到 {target_word_count} 字以上。
请确保：
1. 充足的情节展开和场景描写
2. 生动的人物对话和内心活动
3. 完整的起承转合结构
"""

        prompt = f"""你是一个专业的中文长篇小说写作助手。请根据以下信息创作小说章节。

## 章节信息
- 章节号: 第{chapter_number}章
- 标题: {title}
- 目标字数: {target_word_count}+字（必须达到）
- 题材: {genre}
{world_constraints}
{retry_warning}

## 本章大纲
{outline}

## 前情提要（渐进式披露）
{prev_context}

## 主角身份强制约束
{protagonist_constraint}

**【重要】** 上述约束必须严格遵守，不得违反。

## 当前主线目标锁（稳定继承）
{goal_lock_guidance or "无结构化目标锁，按既有大纲与前文自然推进。"}

## 本章执行合同
{chapter_intent_contract or "无额外执行合同，默认要求开头尽快承接上一章并保持主线一致。"}

## 本卷修订指令
{volume_guidance or "无额外修订指令，按既有大纲与前文自然推进。"}

## 本章附加指令
{chapter_guidance or "无额外章节附加指令。"}

## 质量纠偏指令
{rewrite_guidance or "无额外纠偏要求。"}

## WRITER.md 宪法摘录
{writer_rule_summary or "未加载结构化写作规则，仍需遵守仓库 WRITER.md。"}

## 写作要求
1. {guidance["perspective"]}
2. 情节必须与前文连贯，承接"前情提要"中的具体细节
3. 详细的心理描写
4. 自然的人物对话，符合角色性格
5. 环境描写营造氛围
6. 高潮部分要有冲击力
7. **重要**: 如果"详细前文"中提到了具体物品、地点、人物关系，创作时必须保持一致
8. **重要**: 必须保持上述场景名称、人物名称与既有设定一致，不得凭空替换或引入题材错位设定

## 风格参数
- 基础风格: {normalized_options["style"]}
- {guidance["style"]}
{chr(10).join(f"- {item}" for item in guidance["details"])}

## 输出格式
直接输出小说正文，不输出任何问题或解释。开头格式：{title}

"""
        return prompt

    def _build_previous_chapters_context(
        self,
        previous_chapters: list[dict],
        chapter_dir: str,
        current_chapter: int,
    ) -> str:
        """Build progressive disclosure context for previous chapters.

        Level 1: Key events + character states (always included directly)
        Level 2: Immediate previous chapter FULL content (for natural continuation)
        Level 3: Earlier chapters' paths (for reference if needed)
        """
        if not previous_chapters:
            return "(无前文，这是第一章)"

        lines = []
        lines.append("=" * 60)
        lines.append("【前情提要 - 渐进式披露机制】")
        lines.append("=" * 60)

        # Process chapters in reverse order (most recent first)
        prev_chapters_reversed = list(reversed(previous_chapters))

        for idx, prev in enumerate(prev_chapters_reversed):
            ch_num = prev.get("number", 0)
            title = prev.get("title", f"第{ch_num}章")
            content = prev.get("content", "")
            key_events = prev.get("key_events", [])
            character_states = prev.get("character_states", {})
            file_path = prev.get("file_path", "")

            is_immediate_prev = idx == 0  # Most recent chapter

            lines.append(f"\n【第{ch_num}章 · {title}】")
            lines.append("-" * 50)

            if is_immediate_prev:
                # Level 2: Include FULL content for immediate previous chapter
                lines.append("【完整内容 - 请务必阅读以确保情节连贯】")
                # Extract just the novel body (skip header/metadata)
                body_content = self._extract_chapter_body(content)
                lines.append(body_content[:3000])  # First 3000 chars
                if len(body_content) > 3000:
                    lines.append(f"\n... (内容过长，请阅读完整文件: {file_path})")

            # Level 1: Key events (for all chapters)
            if key_events:
                lines.append("\n关键事件:")
                for evt in key_events[:8]:
                    lines.append(f"  • {evt}")

            # Level 1: Character states
            if character_states:
                lines.append("\n角色状态:")
                for char, state in list(character_states.items())[:5]:
                    lines.append(f"  • {char}: {state}")

            # Level 3: Reference for earlier chapters
            if not is_immediate_prev and file_path:
                lines.append(f"\n[参考文件] {file_path}")

        lines.append("\n" + "=" * 60)
        lines.append("【情节连贯性检查清单】")
        lines.append("=" * 60)
        lines.append(
            """
在创作本章前，请确认你已:
□ 阅读了第{}章的完整内容
□ 理解了上章结尾时主角的具体位置、状态、情绪
□ 清楚了本章大纲中要求的关键情节点
□ 记住了人物关系和已发生事件的时间顺序

创作要求:
1. 本章开头必须精确承接上章结尾场景，禁止跳过或改变上章结局
2. 人物状态、物品归属、修为等级必须与前文完全一致
3. 如需引入新物品/人物，必须在情节中合理铺垫其来源
4. 禁止在没有任何铺垫的情况下改变主角已建立的特性
""".format(previous_chapters[-1].get("number", "N") if previous_chapters else "N")
        )

        return "\n".join(lines)

    def _extract_chapter_body(self, content: str) -> str:
        """Extract just the novel body from chapter content, skipping metadata."""
        import re

        lines = content.split("\n")
        body_lines = []
        in_body = False

        # Patterns that indicate prompt meta-text (should skip even after ---)
        # Only match complete prompt instruction lines, not normal text
        prompt_meta_patterns = [
            r"^我已经阅读了",
            r"^现在我将根据",
            r"^我将根据",
            r"^承接第.*章",
            r"^衔接上文",
            r"^根据前情提要创作",
            r"^根据上文创作",
        ]

        for line in lines:
            # Skip header and metadata
            if line.startswith("---") and not in_body:
                in_body = True
                continue
            if line.startswith("*（本章完）*"):
                break
            if not in_body and line.startswith("#"):
                continue
            if not in_body and line.startswith(">"):
                continue
            if not in_body and line.startswith("**"):
                continue

            # Skip prompt meta-text lines even after --- separator
            if in_body and any(
                re.match(pattern, line.strip()) for pattern in prompt_meta_patterns
            ):
                continue

            if in_body or not line.startswith("#"):
                body_lines.append(line)

        return "\n".join(body_lines).strip()

    def _generate_fallback_content(
        self,
        chapter_number: int,
        title: str,
        outline: str,
        previous_summary: str,
        context: dict[str, Any],
    ) -> str:
        """Generate fallback content when LLM is unavailable."""
        return f"""
# {title}

这一章的场景正在构思中。

## 情节概要
{outline}

## 备注
自动生成内容占位符，实际内容需要通过API生成。
""".strip()

    def _count_words(self, content: str) -> int:
        """Count Chinese characters as words."""
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
        return chinese_chars

    def _normalize_text_for_match(self, text: str) -> str:
        """Normalize text for lightweight deterministic matching."""
        return re.sub(r"\s+", "", text or "")

    def _clean_anchor_candidate(self, text: str) -> str:
        """Trim common connective noise from deterministic match anchors."""
        candidate = str(text or "").strip("：:，,；;。！？!?\n ")
        while True:
            trimmed = ANCHOR_LEADING_NOISE_PATTERN.sub("", candidate).strip(
                "：:，,；;。！？!?\n "
            )
            if trimmed == candidate:
                break
            candidate = trimmed
        return candidate

    def _split_compound_goal_fragments(self, text: str) -> list[str]:
        """Split compound goals/events into ordered deterministic sub-goals."""
        normalized = str(text or "").strip()
        if not normalized:
            return []

        fragments: list[str] = []
        for raw_part in COMPOUND_GOAL_CONNECTOR_PATTERN.split(normalized):
            candidate = self._clean_anchor_candidate(raw_part)
            if len(candidate) < 2 or candidate in fragments:
                continue
            fragments.append(candidate)
        return fragments[:4]

    def _extract_previous_chapter_tail(self, context: dict[str, Any] | None) -> str:
        """Return the tail of the previous chapter when available."""
        if not context:
            return ""

        previous_chapters = context.get("previous_chapters", []) or []
        if not previous_chapters:
            return ""

        previous_content = str(previous_chapters[-1].get("content", "") or "")
        return previous_content[-400:]

    def _extract_event_keywords(
        self, event: str, context: dict[str, Any] | None = None
    ) -> list[str]:
        """Extract deterministic anchors for one key event."""
        normalized_event = str(event or "").strip()
        if not normalized_event:
            return []

        keywords: list[str] = []
        seen: set[str] = set()

        for name in self._resolve_known_char_names(context):
            candidate = str(name or "").strip()
            if len(candidate) >= 2 and candidate in normalized_event and candidate not in seen:
                keywords.append(candidate)
                seen.add(candidate)

        for action in EVENT_ACTION_KEYWORDS:
            if action not in normalized_event:
                continue
            if action not in seen:
                keywords.append(action)
                seen.add(action)
            action_index = normalized_event.find(action)
            subject = normalized_event[max(0, action_index - 4) : action_index].strip()
            subject = re.sub(r"[^\u4e00-\u9fff]", "", subject)[-4:]
            subject = self._clean_anchor_candidate(subject)
            if (
                len(subject) >= 2
                and subject not in EVENT_NOISE_TERMS
                and subject not in seen
            ):
                keywords.append(subject)
                seen.add(subject)
            subject_tail = re.sub(r"^(?:争取|请求|寻求|获得|得到|请|让)", "", subject)
            subject_tail = self._clean_anchor_candidate(subject_tail[-4:])
            if (
                len(subject_tail) >= 2
                and subject_tail not in EVENT_NOISE_TERMS
                and subject_tail not in seen
            ):
                keywords.append(subject_tail)
                seen.add(subject_tail)
            object_tail = normalized_event[action_index + len(action) :].strip()
            object_tail = re.sub(r"^(?:在|于|向|对|把|将|从|往|朝)", "", object_tail)
            object_tail = re.split(r"[，。；、：:！!？?\s/]+", object_tail, maxsplit=1)[0]
            object_tail = self._clean_anchor_candidate(object_tail[:8])
            if (
                len(object_tail) >= 2
                and object_tail not in EVENT_NOISE_TERMS
                and object_tail not in seen
            ):
                keywords.append(object_tail)
                seen.add(object_tail)

        for part in EVENT_SPLIT_PATTERNS.split(normalized_event):
            candidate = self._clean_anchor_candidate(part)
            if (
                len(candidate) >= 2
                and candidate not in EVENT_NOISE_TERMS
                and candidate not in seen
            ):
                keywords.append(candidate)
                seen.add(candidate)

        return keywords[:6]

    def _event_fragment_is_covered(
        self, event_fragment: str, content: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Return True when one event fragment is deterministically grounded in content."""
        normalized_event = str(event_fragment or "").strip()
        if len(normalized_event) < 2:
            return True
        if normalized_event in content:
            return True

        keywords = self._extract_event_keywords(normalized_event, context)
        if not keywords:
            return False

        action_keywords = [
            action for action in EVENT_ACTION_KEYWORDS if action in normalized_event
        ]
        matched_keywords: set[str] = {
            keyword for keyword in keywords if keyword in content
        }
        matched_action_keywords = {
            action
            for action in action_keywords
            if any(
                alias in content
                for alias in EVENT_ACTION_SYNONYMS.get(action, (action,))
            )
        }
        if action_keywords and not matched_action_keywords:
            return False
        for keyword in keywords:
            if keyword in matched_keywords:
                continue
            if keyword.endswith(("真假", "真伪")) and any(
                marker in content for marker in ("真假", "真伪", "是真是假")
            ):
                matched_keywords.add(keyword)
        matched_keywords.update(matched_action_keywords)
        required_matches = 1 if len(keywords) == 1 else 2
        return len(matched_keywords) >= required_matches

    def _event_is_covered(
        self, event: str, content: str, context: dict[str, Any] | None = None
    ) -> bool:
        """Return True when a key event is deterministically grounded in content."""
        normalized_event = str(event or "").strip()
        if len(normalized_event) < 2:
            return True
        subgoals = self._split_compound_goal_fragments(normalized_event)
        if len(subgoals) > 1 and all(
            self._event_fragment_is_covered(subgoal, content, context)
            for subgoal in subgoals
        ):
            return True
        return self._event_fragment_is_covered(normalized_event, content, context)

    def _extract_location_anchor(self, text: str) -> str:
        """Extract a conservative location anchor from the provided text."""
        raw_text = text or ""
        normalized = self._normalize_text_for_match(raw_text)
        if not normalized:
            return ""

        suffix_pattern = "|".join(
            re.escape(item)
            for item in sorted(
                HIGH_CONFIDENCE_LOCATION_SUFFIXES, key=len, reverse=True
            )
        )
        nested_scene_match = re.search(
            rf"(?:在|于)[\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern})的([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))(?:内|中|里|上|前)?",
            normalized,
        )
        if nested_scene_match:
            nested_candidate = nested_scene_match.group(1)
            if not self._is_low_confidence_location_anchor(nested_candidate):
                return nested_candidate
        candidates: list[tuple[int, int, str]] = []
        for prefix in OPENING_LOCATION_PREFIX_MARKERS:
            match = re.search(
                rf"{re.escape(prefix)}([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
                normalized,
            )
            if match:
                candidate = match.group(1)
                if self._is_low_confidence_location_anchor(candidate):
                    continue
                candidates.append((match.start(1), -len(candidate), candidate))
        patterns = (
            rf"^(?:[\u4e00-\u9fff]{{1,4}}的)?([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))(?:内|中|外|上|下|前|里)",
            rf"(?:回到|返回|抵达|来到|赶到|赶往|奔赴|进入|踏入|冲进|冲出|躲进|潜入|驶入|驶向|退回)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"(?:走进|推开|穿过[\u4e00-\u9fff]{0,8}后进入)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"(?:在|于)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"(?:这里仍是|仍是|依旧是)([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))",
            rf"^([\u4e00-\u9fff]{{2,12}}(?:{suffix_pattern}))(?:内|中|外|上|下|前|里)",
        )
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                candidate = match.group(1)
                if self._is_low_confidence_location_anchor(candidate):
                    continue
                candidates.append((match.start(1), -len(candidate), candidate))
        if not candidates:
            return ""
        candidates.sort()
        return candidates[0][2]

    def _is_low_confidence_location_anchor(self, candidate: str) -> bool:
        """Reject prop-like or operational fragments that are not stable scenes."""
        if not candidate:
            return True
        if candidate in LOW_CONFIDENCE_LOCATION_ANCHORS:
            return True
        return any(part in candidate for part in LOW_CONFIDENCE_LOCATION_PARTS)

    def _extract_narrative_opening(self, content: str) -> str:
        """Strip markdown prelude and return the actual narrative opening window."""
        raw_text = str(content or "")
        if not raw_text:
            return ""
        narrative = raw_text
        if "◆开场" in narrative:
            narrative = narrative.split("◆开场", 1)[1]
        elif "\n---" in narrative:
            narrative = narrative.split("\n---", 1)[1]
        return self._normalize_text_for_match(narrative[:600])

    def _location_anchors_conflict(
        self, previous_anchor: str, current_anchor: str
    ) -> bool:
        """Check whether two extracted anchors represent different scenes."""
        if not previous_anchor or not current_anchor:
            return False
        if previous_anchor == current_anchor:
            return False
        if previous_anchor in current_anchor or current_anchor in previous_anchor:
            return False
        return True

    def _summary_prepares_current_location(
        self, previous_summary: str, current_anchor: str
    ) -> bool:
        """Check whether the prior summary already establishes the upcoming destination."""
        normalized_summary = self._normalize_text_for_match(previous_summary)
        if not normalized_summary or not current_anchor:
            return False
        return current_anchor in normalized_summary and any(
            marker in normalized_summary for marker in MOTION_CONTINUITY_MARKERS
        )

    def _has_bridge_signal(self, opening: str) -> bool:
        """Detect whether the opening already contains an explicit transition bridge."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        for pattern in NON_BRIDGE_TRANSITION_PATTERNS:
            normalized = re.sub(pattern, "", normalized)
        return any(marker in normalized for marker in TRANSITION_BRIDGE_SIGNALS)

    def _extract_time_jump_marker(self, opening: str) -> str:
        """Return the first strong time-jump marker found in the opening."""
        normalized = self._normalize_text_for_match(opening)
        for marker in ABRUPT_TRANSITION_MARKERS:
            if marker in normalized:
                return marker
        return ""

    def _extract_consequence_marker(self, previous_context: str) -> str:
        """Return the first strong unresolved consequence marker from prior context."""
        normalized = self._normalize_text_for_match(previous_context)
        for marker in CONSEQUENCE_MARKERS:
            if marker in normalized:
                return marker
        return ""

    def _extract_consequence_clause(self, text: str) -> str:
        """Return a stronger carry-over clause when a single keyword is not enough."""
        raw_text = str(text or "")
        if not raw_text:
            return ""
        for pattern in CONSEQUENCE_CLAUSE_PATTERNS:
            matches: list[str] = []
            for match in pattern.finditer(raw_text):
                clause = str(match.group(1) or "").strip(" ，,；;。！？\n")
                if clause:
                    matches.append(clause)
            if matches:
                return matches[-1]
        return ""

    def _extract_consequence_evidence(
        self, previous_summary: str, previous_tail: str
    ) -> str:
        """Prefer the real previous chapter tail over template-like summary fallbacks."""
        previous_tail = str(previous_tail or "")
        tail_marker = self._extract_consequence_marker(previous_tail)
        if tail_marker:
            return tail_marker
        tail_clause = self._extract_consequence_clause(previous_tail)
        if tail_clause:
            return tail_clause

        # When the previous chapter text exists, do not let macro/template summaries
        # override the actual chapter ending with stale background accidents.
        if previous_tail.strip():
            return ""

        normalized_summary = self._normalize_text_for_match(previous_summary)
        if not normalized_summary or not any(
            marker in normalized_summary
            for marker in SUMMARY_CONSEQUENCE_CONTEXT_MARKERS
        ):
            return ""

        summary_marker = self._extract_consequence_marker(previous_summary)
        if summary_marker:
            return summary_marker
        return self._extract_consequence_clause(previous_summary)

    def _opening_acknowledges_consequence(
        self, opening: str, consequence_marker: str
    ) -> bool:
        """Check whether the current opening acknowledges the prior consequence."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        if consequence_marker and consequence_marker in normalized:
            return True
        if (
            consequence_marker in {"追兵", "追杀", "逃亡"}
            and self._has_bridge_signal(normalized)
            and any(marker in normalized for marker in MOTION_CONTINUITY_MARKERS)
        ):
            return True
        return any(
            marker in normalized for marker in CONSEQUENCE_ACKNOWLEDGEMENT_MARKERS
        )

    def _opening_dismisses_prior_consequence(self, opening: str) -> bool:
        """Detect shallow mention patterns that explicitly dismiss prior consequences."""
        normalized = self._normalize_text_for_match(opening)
        if not normalized:
            return False
        return any(marker in normalized for marker in DISMISSIVE_CONTINUITY_MARKERS)

    def _build_smoothness_issue(
        self,
        category: str,
        previous_evidence: str,
        current_evidence: str,
        missing_link: str,
    ) -> dict[str, str]:
        """Create a stable issue payload for blocking smoothness failures."""
        return {
            "category": category,
            "previous_evidence": previous_evidence,
            "current_evidence": current_evidence,
            "missing_transition_or_causal_link": missing_link,
            "message": (
                f"顺畅性问题[{category}] 上一章线索「{previous_evidence or '无'}」"
                f" 与当前开篇「{current_evidence or '无'}」之间缺少{missing_link}。"
            ),
        }

    def _check_transition_continuity(
        self,
        content: str,
        previous_summary: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """Check deterministic chapter-to-chapter smoothness boundaries."""
        opening = self._extract_narrative_opening(content)
        previous_tail = self._extract_previous_chapter_tail(context)
        previous_context = self._normalize_text_for_match(
            f"{previous_summary}\n{previous_tail}"
        )

        # Chapter 1 or empty prior context: skip continuity gate.
        if not previous_context:
            return []

        issues: list[dict[str, str]] = []
        has_bridge_signal = self._has_bridge_signal(opening)
        previous_anchor = self._extract_location_anchor(
            previous_tail
        ) or self._extract_location_anchor(previous_summary)
        current_anchor = self._extract_location_anchor(opening)

        if (
            previous_anchor
            and current_anchor
            and self._location_anchors_conflict(previous_anchor, current_anchor)
            and not self._summary_prepares_current_location(
                previous_summary, current_anchor
            )
            and not has_bridge_signal
        ):
            issues.append(
                self._build_smoothness_issue(
                    category="地点跳切无承接",
                    previous_evidence=previous_anchor,
                    current_evidence=current_anchor,
                    missing_link="地点转换或行动路径交代",
                )
            )

        time_jump_marker = self._extract_time_jump_marker(opening)
        if time_jump_marker and not has_bridge_signal:
            issues.append(
                self._build_smoothness_issue(
                    category="时间跳跃无锚点",
                    previous_evidence=previous_anchor or previous_summary[:40],
                    current_evidence=time_jump_marker,
                    missing_link="时间变化后的状态承接",
                )
            )

        consequence_marker = self._extract_consequence_evidence(
            previous_summary,
            previous_tail,
        )
        consequence_dismissed = self._opening_dismisses_prior_consequence(opening)
        consequence_acknowledged = self._opening_acknowledges_consequence(
            opening, consequence_marker
        )
        if consequence_marker and (
            not consequence_acknowledged or consequence_dismissed
        ):
            issues.append(
                self._build_smoothness_issue(
                    category="上一章后果未被承接",
                    previous_evidence=consequence_marker,
                    current_evidence=opening[:40],
                    missing_link="上一章后果的回应或延续",
                )
            )

        issue_categories = {issue["category"] for issue in issues}
        if len(issue_categories) >= 2 or consequence_dismissed:
            issues.append(
                self._build_smoothness_issue(
                    category="表面流畅但因果断裂",
                    previous_evidence=" / ".join(sorted(issue_categories))
                    or "表面承接但实质跳过前情",
                    current_evidence=opening[:40],
                    missing_link="地点/时间/后果之间的因果桥接",
                )
            )

        return issues

    def _build_rewrite_guidance(self, report: dict[str, Any]) -> str:
        """Build focused rewrite guidance for smoothness-related failures."""
        return self._format_rewrite_guidance(self._build_rewrite_plan(report))

    def _append_rewrite_operation(
        self,
        rewrite_plan: dict[str, Any],
        *,
        phase: str,
        action: str,
        target: str,
        instruction: str,
        rationale: str,
        success_signal: str,
    ) -> None:
        """Append a machine-readable rewrite operation without duplicating equivalent steps."""
        instruction = str(instruction or "").strip()
        if not instruction:
            return

        operations = rewrite_plan.setdefault("operations", [])
        signature = (phase, action, target, instruction)
        for existing in operations:
            if not isinstance(existing, dict):
                continue
            existing_signature = (
                str(existing.get("phase", "") or "").strip(),
                str(existing.get("action", "") or "").strip(),
                str(existing.get("target", "") or "").strip(),
                str(existing.get("instruction", "") or "").strip(),
            )
            if existing_signature == signature:
                return

        operations.append(
            {
                "phase": phase,
                "action": action,
                "target": target,
                "instruction": instruction,
                "rationale": str(rationale or "").strip(),
                "success_signal": str(success_signal or "").strip(),
            }
        )

    def _build_rewrite_plan(self, report: dict[str, Any]) -> dict[str, Any]:
        """Build a structured rewrite plan while preserving string guidance compatibility."""
        smoothness_details = (
            report.get("smoothness_details", []) if isinstance(report, dict) else []
        )
        smoothness_categories: list[str] = []
        for item in smoothness_details:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "") or "").strip()
            if category and category not in smoothness_categories:
                smoothness_categories.append(category)
        guidance_plan: dict[str, Any] = {
            "schema_version": "rewrite_plan.v2",
            "strategy": "targeted_patch",
            "issue_types": list(report.get("issue_types", []))
            if isinstance(report, dict)
            else [],
            "issue_categories": smoothness_categories,
            "must_keep": [
                "保留本章既有关键事件，不要靠删除冲突来伪造顺畅。",
                "开头前 2-3 句必须尽快交代谁、在哪、何时，并补上与上一章的承接。",
            ],
            "fixes": [],
            "success_criteria": [],
            "operations": [],
        }
        blocking_issues = (
            report.get("blocking_issues", []) if isinstance(report, dict) else []
        )
        anti_drift = (
            report.get("anti_drift_details", {}) if isinstance(report, dict) else {}
        )
        goal_lock = str(anti_drift.get("goal_lock", "") or "").strip()
        budget = anti_drift.get("budget", 1)
        joined_issues = " ".join(str(item) for item in blocking_issues)

        if (
            "地点跳切无承接" in smoothness_categories
            or "地点跳切无承接" in joined_issues
        ):
            guidance_plan["fixes"].append("补足地点变化的过渡动作、路径或抵达说明。")
            guidance_plan["success_criteria"].append(
                "开场地点变化必须带过渡动作或抵达锚点，不能直接切场。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="opening",
                action="bridge_transition",
                target="scene_entry",
                instruction="补足地点变化的过渡动作、路径或抵达说明。",
                rationale="地点跳切无承接",
                success_signal="开场地点变化必须带过渡动作或抵达锚点，不能直接切场。",
            )
        for item in smoothness_details:
            if not isinstance(item, dict):
                continue
            if str(item.get("category", "") or "").strip() != "地点跳切无承接":
                continue
            previous_anchor = str(item.get("previous_evidence", "") or "").strip()
            current_anchor = str(item.get("current_evidence", "") or "").strip()
            if not previous_anchor or not current_anchor:
                continue
            instruction = (
                f"若上一章已落在「{previous_anchor}」，本章前两句必须先承接该场景后果；"
                f"若切到「{current_anchor}」，必须明确写出从「{previous_anchor}」到「{current_anchor}」的路径、抵达或切换原因，不得在「{current_anchor}」直接重开故事。"
            )
            success_signal = (
                f"开篇场景必须先承接「{previous_anchor}」，或显式完成到「{current_anchor}」的过桥，不能直接回到其他起始场景。"
            )
            if instruction not in guidance_plan["fixes"]:
                guidance_plan["fixes"].append(instruction)
            if success_signal not in guidance_plan["success_criteria"]:
                guidance_plan["success_criteria"].append(success_signal)
            self._append_rewrite_operation(
                guidance_plan,
                phase="opening",
                action="lock_scene_anchor",
                target="scene_entry",
                instruction=instruction,
                rationale="地点跳切无承接",
                success_signal=success_signal,
            )
        if (
            "时间跳跃无锚点" in smoothness_categories
            or "时间跳跃无锚点" in joined_issues
        ):
            guidance_plan["fixes"].append(
                "交代时间跨度后的状态变化、缺失时段影响或切换原因。"
            )
            guidance_plan["success_criteria"].append(
                "若发生时间跳跃，正文必须解释时间跨度带来的状态变化。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="opening",
                action="anchor_time_jump",
                target="time_transition",
                instruction="交代时间跨度后的状态变化、缺失时段影响或切换原因。",
                rationale="时间跳跃无锚点",
                success_signal="若发生时间跳跃，正文必须解释时间跨度带来的状态变化。",
            )
        if (
            "上一章后果未被承接" in smoothness_categories
            or "上一章后果未被承接" in joined_issues
        ):
            guidance_plan["fixes"].append(
                "明确回应上一章遗留的危机、伤势、追击或未完成动作。"
            )
            guidance_plan["success_criteria"].append(
                "开头必须接住上一章的后果，不能让危机凭空消失。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="opening",
                action="restore_carryover",
                target="carryover_consequence",
                instruction="明确回应上一章遗留的危机、伤势、追击或未完成动作。",
                rationale="上一章后果未被承接",
                success_signal="开头必须接住上一章的后果，不能让危机凭空消失。",
            )
        if (
            "表面流畅但因果断裂" in smoothness_categories
            or "表面流畅但因果断裂" in joined_issues
        ):
            guidance_plan["fixes"].append(
                "把事件顺序改写为因果推进，避免只用时间顺序硬接。"
            )
            guidance_plan["success_criteria"].append(
                "关键情节必须形成因果链，而不是只维持表面顺接。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="restore_causality",
                target="causal_chain",
                instruction="把事件顺序改写为因果推进，避免只用时间顺序硬接。",
                rationale="表面流畅但因果断裂",
                success_signal="关键情节必须形成因果链，而不是只维持表面顺接。",
            )
        if "missing_key_events" in guidance_plan["issue_types"]:
            missing_events = [
                str(item)
                for item in report.get("missing_events", [])
                if str(item).strip()
            ]
            if missing_events:
                guidance_plan["fixes"].append(
                    f"把缺失关键事件补回正文推进链：{'；'.join(missing_events[:3])}"
                )
                guidance_plan["success_criteria"].append(
                    "大纲中的关键事件必须真实发生，而不是只留在摘要里。"
                )
                self._append_rewrite_operation(
                    guidance_plan,
                    phase="body",
                    action="restore_outline_event",
                    target="key_event_chain",
                    instruction=f"把缺失关键事件补回正文推进链：{'；'.join(missing_events[:3])}",
                    rationale="missing_key_events",
                    success_signal="大纲中的关键事件必须真实发生，而不是只留在摘要里。",
                )
        if "world_fact_violation" in guidance_plan["issue_types"]:
            guidance_plan["fixes"].append(
                "回收或改写与既有世界事实冲突的描写，保持人物、生死与物件状态一致。"
            )
            guidance_plan["success_criteria"].append(
                "重写后不得出现与前文既定事实直接冲突的设定。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="reconcile_canon_fact",
                target="world_fact_conflict",
                instruction="回收或改写与既有世界事实冲突的描写，保持人物、生死与物件状态一致。",
                rationale="world_fact_violation",
                success_signal="重写后不得出现与前文既定事实直接冲突的设定。",
            )
        if (
            "structure_drift_risk" in guidance_plan["issue_types"]
            or "结构漂移风险[" in joined_issues
        ):
            if goal_lock:
                guidance_plan["fixes"].append(f"先推进主线目标锁：{goal_lock}。")
                self._append_rewrite_operation(
                    guidance_plan,
                    phase="body",
                    action="advance_goal_lock",
                    target="main_plot_progression",
                    instruction=f"先推进主线目标锁：{goal_lock}。",
                    rationale="structure_drift_risk",
                    success_signal=f"新增设定必须明确服务目标锁：{goal_lock}"
                    if goal_lock
                    else "任何新增设定都必须在近邻段落中桥接回主线目标。",
                )
            guidance_plan["fixes"].append(
                "新设定若非服务主线，则降权/延后，只保留最小必要信息，不扩写体系/规则/势力细节。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="trim_new_setting",
                target="new_setting_intro",
                instruction="新设定若非服务主线，则降权/延后，只保留最小必要信息，不扩写体系/规则/势力细节。",
                rationale="structure_drift_risk",
                success_signal="任何新增设定都必须在近邻段落中桥接回主线目标。",
            )
            if isinstance(budget, int) and budget >= 0:
                guidance_plan["fixes"].append(
                    f"中后期新设定预算={budget}：本章不得引入超过预算的强设定，必要时合并或后置。"
                )
                self._append_rewrite_operation(
                    guidance_plan,
                    phase="body",
                    action="enforce_budget",
                    target="new_setting_budget",
                    instruction=f"中后期新设定预算={budget}：本章不得引入超过预算的强设定，必要时合并或后置。",
                    rationale="structure_drift_risk",
                    success_signal="任何新增设定都必须在近邻段落中桥接回主线目标。",
                )
            guidance_plan["fixes"].append(
                "引入新设定后 1-2 段内，用“为了/因此/所以/必须/要想/才能/目标是/于是”等桥接词说明其如何推动主线目标。"
            )
            guidance_plan["success_criteria"].append(
                "任何新增设定都必须在近邻段落中桥接回主线目标。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="bridge_to_goal_lock",
                target="goal_lock_bridge",
                instruction="引入新设定后 1-2 段内，用“为了/因此/所以/必须/要想/才能/目标是/于是”等桥接词说明其如何推动主线目标。",
                rationale="structure_drift_risk",
                success_signal="任何新增设定都必须在近邻段落中桥接回主线目标。",
            )
            if goal_lock:
                guidance_plan["success_criteria"].append(
                    f"新增设定必须明确服务目标锁：{goal_lock}"
                )
        if (
            "goal_lock_false_inheritance" in guidance_plan["issue_types"]
            or "目标锁假继承[" in joined_issues
        ):
            guidance_plan["fixes"].append(
                "不要只改摘要、开头一句或宣言式台词来制造对齐。"
            )
            guidance_plan["fixes"].append(
                "必须把正文关键事件、冲突选择与行动结果改写为持续推进主线目标。"
            )
            guidance_plan["fixes"].append(
                "与主线无关的段落降权或后置，避免正文主体被支线闲笔冲散。"
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="rewrite_body_progression",
                target="main_plot_progression",
                instruction="必须把正文关键事件、冲突选择与行动结果改写为持续推进主线目标。",
                rationale="goal_lock_false_inheritance",
                success_signal=f"摘要和正文都必须真实推进目标锁：{goal_lock}"
                if goal_lock
                else "摘要和正文都必须真实推进当前主线目标。",
            )
            self._append_rewrite_operation(
                guidance_plan,
                phase="body",
                action="demote_side_track",
                target="off_goal_paragraphs",
                instruction="与主线无关的段落降权或后置，避免正文主体被支线闲笔冲散。",
                rationale="goal_lock_false_inheritance",
                success_signal=f"摘要和正文都必须真实推进目标锁：{goal_lock}"
                if goal_lock
                else "摘要和正文都必须真实推进当前主线目标。",
            )
            if goal_lock:
                guidance_plan["fixes"].append(
                    f"重写时围绕目标锁重组正文推进链：{goal_lock}"
                )
                guidance_plan["success_criteria"].append(
                    f"摘要和正文都必须真实推进目标锁：{goal_lock}"
                )
                self._append_rewrite_operation(
                    guidance_plan,
                    phase="body",
                    action="rebuild_goal_lock_chain",
                    target="goal_lock_progression",
                    instruction=f"重写时围绕目标锁重组正文推进链：{goal_lock}",
                    rationale="goal_lock_false_inheritance",
                    success_signal=f"摘要和正文都必须真实推进目标锁：{goal_lock}",
                )

        guidance_plan["fixes"] = [item for item in guidance_plan["fixes"] if item]
        guidance_plan["success_criteria"] = [
            item for item in guidance_plan["success_criteria"] if item
        ]
        return guidance_plan

    def _format_rewrite_guidance(self, rewrite_plan: dict[str, Any]) -> str:
        """Format structured rewrite instructions into the legacy string field."""
        sections: list[str] = []
        for label, key in (
            ("失败证据", "blocking_issues"),
            ("开篇补桥", "opening_bridge"),
            ("必须覆盖事件", "must_include_events"),
            ("保留要求", "must_keep"),
            ("本次修复", "fixes"),
            ("验收条件", "success_criteria"),
        ):
            source = rewrite_plan.get(key, [])
            if key == "blocking_issues" and not source:
                source = (rewrite_plan.get("failure_evidence", {}) or {}).get(
                    "blocking_issues", []
                )
            items = [str(item).strip() for item in source if str(item).strip()]
            if not items:
                continue
            numbered = " ".join(
                f"{index + 1}. {item}" for index, item in enumerate(items)
            )
            sections.append(f"【{label}】{numbered}")
        goal_lock = str(rewrite_plan.get("goal_lock", "") or "").strip()
        if goal_lock:
            sections.append(f"【目标锁】{goal_lock}")
        goal_subgoals = [
            str(item).strip()
            for item in rewrite_plan.get("goal_subgoals", [])
            if str(item).strip()
        ]
        if len(goal_subgoals) > 1:
            numbered = " ".join(
                f"{index + 1}. {item}" for index, item in enumerate(goal_subgoals[:4])
            )
            sections.append(f"【目标锁分项】{numbered}")
        ordered_beats = [
            item for item in rewrite_plan.get("ordered_beats", []) if isinstance(item, dict)
        ]
        if ordered_beats:
            beat_lines: list[str] = []
            for index, beat in enumerate(ordered_beats, start=1):
                phase = str(beat.get("phase", "") or "").strip() or f"phase_{index}"
                action = str(beat.get("required_action", "") or "").strip()
                suffix_parts = [
                    str(beat.get("goal_lock", "") or "").strip(),
                    str(beat.get("continuity_out", "") or "").strip(),
                ]
                suffix = "；".join(part for part in suffix_parts if part)
                entry = f"{index}. {phase}: {action}".strip()
                if suffix:
                    entry += f"（{suffix}）"
                beat_lines.append(entry)
            sections.append(f"【重写节拍】{' '.join(beat_lines)}")
        return " ".join(sections).strip()

    def _extract_goal_lock(self, context: dict[str, Any] | None) -> str:
        """Extract the active goal lock from structured or freeform guidance."""
        if not context:
            return ""
        resolution = context.get("goal_lock_resolution")
        if isinstance(resolution, dict):
            value = str(resolution.get("effective_goal_lock", "") or "").strip()
            if value:
                return value
        plan = self._packet_plan(context)
        plan_value = str(plan.get("goal_lock", "") or "").strip()
        if plan_value:
            return plan_value
        payload = self._volume_guidance_payload(context)
        value = str(payload.get("goal_lock", "") or "").strip()
        if value:
            return value
        contract = context.get("chapter_intent_contract")
        if isinstance(contract, dict):
            value = str(contract.get("goal_lock", "") or "").strip()
            if value:
                return value
        return str(context.get("goal_lock", "") or "").strip()

    def _build_goal_lock_guidance(self, context: dict[str, Any] | None) -> str:
        """Build the stable goal-lock prompt block from the volume-level source of truth."""
        goal_lock = self._extract_goal_lock(context)
        if not goal_lock:
            return ""
        return "\n".join(
            [
                f"- 当前主线目标锁: {goal_lock}",
                "- 本章核心推进、关键冲突和行动结果都必须持续服务这个目标锁。",
                "- 摘要、关键事件和正文主体必须共享同一目标锁语义，不能只在摘要或宣言句里假对齐。",
                "- 若引入新设定，必须立即说明它如何帮助推进该目标锁。",
            ]
        )

    def _summarize_outline_focus(self, outline: str) -> str:
        """Extract a compact planned action from the outline text."""
        for chunk in re.split(r"[\n；;]+", str(outline or "")):
            cleaned = re.sub(r"^[\s\-*•\d.、:：【】]+", "", chunk).strip()
            if cleaned:
                return cleaned[:80]
        return ""

    def _build_chapter_intent_contract(
        self,
        *,
        outline: str,
        context: dict[str, Any] | None,
        chapter_guidance: str = "",
    ) -> dict[str, Any]:
        """Build a stable execution contract that keeps goal_lock above one-shot guidance."""
        goal_lock = self._extract_goal_lock(context)
        planned_action = self._summarize_outline_focus(outline)
        goal_subgoals = self._split_compound_goal_fragments(goal_lock)
        chapter_graph_packet = dict(
            (context or {}).get("chapter_graph_packet", {}) or {}
        )
        chapter_driver_packet = dict(
            (context or {}).get("chapter_driver_packet", {}) or {}
        )
        contract: dict[str, Any] = {
            "goal_lock": goal_lock,
            "goal_subgoals": goal_subgoals,
            "planned_action": planned_action,
            "chapter_goal": str(chapter_graph_packet.get("chapter_goal", "") or "").strip(),
            "required_bridge": str(
                chapter_graph_packet.get("required_bridge", "") or ""
            ).strip(),
            "success_evidence": list(
                chapter_graph_packet.get("success_evidence", []) or []
            ),
            "chapter_guidance_scope": "additive_only"
            if chapter_guidance.strip()
            else "none",
            "new_setting_budget": self._extract_new_setting_budget(context)
            if goal_lock
            else None,
            "opening_bridge_required": str(
                chapter_graph_packet.get("opening_bridge_required", "") or ""
            ).strip(),
            "target_destinations": list(
                chapter_graph_packet.get("target_destinations", []) or []
            ),
            "completed_goal_subgoals": list(
                chapter_graph_packet.get("completed_goal_subgoals", []) or []
            ),
            "prohibited_inheritance": list(
                chapter_graph_packet.get("prohibited_inheritance", []) or []
            ),
            "scene_beats": list(
                chapter_driver_packet.get("scene_beats", []) or []
            ),
            "cast_objectives": list(chapter_driver_packet.get("cast", []) or []),
            "emotional_arc": list(
                chapter_driver_packet.get("emotional_arc", []) or []
            ),
            "tension_points": list(
                chapter_driver_packet.get("tension_points", []) or []
            ),
            "cliffhanger": str(
                chapter_driver_packet.get("cliffhanger", "") or ""
            ).strip(),
            "driver_notes": list(chapter_driver_packet.get("driver_notes", []) or []),
            "success_checks": [],
        }
        if goal_lock:
            contract["success_checks"].extend(
                [
                    "开头前两段必须说明本章如何承接上一章局势，并迅速落回当前主线目标锁。",
                    f"正文至少一个关键行动、冲突选择或结果必须直接推进目标锁：{goal_lock}",
                    "摘要、关键事件和正文主体必须共享同一推进方向，不能只在摘要或宣言句里假对齐。",
                    "若引入新设定，必须在 1-2 段内解释它为什么服务主线目标，而不是平行扩写支线。",
                ]
            )
            if len(goal_subgoals) > 1:
                contract["success_checks"].append(
                    "复合目标锁必须逐项落地，不能只覆盖其中一个子目标。"
                )
        else:
            contract["success_checks"].append(
                "本章开头必须尽快承接上一章状态，避免无锚点跳切。"
            )
        if chapter_guidance.strip():
            contract["success_checks"].append(
                "章节附加指令只能补充执行方式，不得覆盖或改写卷级主线目标锁。"
            )
        if contract["chapter_goal"]:
            contract["success_checks"].append(
                f"本章至少一处关键行动必须服务当前章节目标：{contract['chapter_goal']}"
            )
        if contract["required_bridge"]:
            contract["success_checks"].append(contract["required_bridge"])
        if contract["success_evidence"]:
            contract["success_checks"].extend(
                str(item).strip()
                for item in contract["success_evidence"][:3]
                if str(item).strip()
            )
        if contract["opening_bridge_required"]:
            contract["success_checks"].append(
                contract["opening_bridge_required"]
            )
        if contract["prohibited_inheritance"]:
            contract["success_checks"].extend(
                str(item).strip()
                for item in contract["prohibited_inheritance"][:2]
                if str(item).strip()
            )
        for beat in contract["scene_beats"][:4]:
            if not isinstance(beat, dict):
                continue
            evidence = str(beat.get("success_evidence", "") or "").strip()
            if evidence:
                contract["success_checks"].append(evidence)
        if contract["cliffhanger"]:
            contract["success_checks"].append(
                f"结尾必须回应或制造余波：{contract['cliffhanger']}"
            )
        return contract

    def _format_chapter_intent_contract(self, contract: dict[str, Any] | None) -> str:
        """Render the chapter intent contract into a prompt-friendly text block."""
        if not isinstance(contract, dict) or not contract:
            return ""
        lines: list[str] = []
        planned_action = str(contract.get("planned_action", "") or "").strip()
        if planned_action:
            lines.append(f"- 本章计划动作: {planned_action}")
        goal_lock = str(contract.get("goal_lock", "") or "").strip()
        if goal_lock:
            lines.append(f"- 不可偏离的主线目标锁: {goal_lock}")
        chapter_goal = str(contract.get("chapter_goal", "") or "").strip()
        if chapter_goal:
            lines.append(f"- 当前章节目标: {chapter_goal}")
        goal_subgoals = [
            str(item).strip()
            for item in contract.get("goal_subgoals", [])
            if str(item).strip()
        ]
        if len(goal_subgoals) > 1:
            lines.append("- 复合目标锁分项落地:")
            lines.extend(f"  - {item}" for item in goal_subgoals[:4])
        completed_goal_subgoals = [
            str(item).strip()
            for item in contract.get("completed_goal_subgoals", [])
            if str(item).strip()
        ]
        if completed_goal_subgoals:
            lines.append(
                "- 已完成分项(避免假继承): "
                + " / ".join(completed_goal_subgoals[:4])
            )
        target_destinations = [
            str(item).strip()
            for item in contract.get("target_destinations", [])
            if str(item).strip()
        ]
        if target_destinations:
            lines.append("- 本章目标地点: " + " / ".join(target_destinations[:3]))
        opening_bridge_required = str(
            contract.get("opening_bridge_required", "") or ""
        ).strip()
        if opening_bridge_required:
            lines.append(f"- 开篇承接要求: {opening_bridge_required}")
        required_bridge = str(contract.get("required_bridge", "") or "").strip()
        if required_bridge:
            lines.append(f"- 必补桥段: {required_bridge}")
        success_evidence = [
            str(item).strip()
            for item in contract.get("success_evidence", [])
            if str(item).strip()
        ]
        if success_evidence:
            lines.append("- 成功证据:")
            lines.extend(f"  - {item}" for item in success_evidence[:4])
        scene_beats = [
            item for item in contract.get("scene_beats", []) if isinstance(item, dict)
        ]
        if scene_beats:
            lines.append("- 叙事驱动场景节拍:")
            for beat in scene_beats[:4]:
                action = str(beat.get("action", "") or "").strip()
                turn = str(beat.get("turn", "") or "").strip()
                evidence = str(beat.get("success_evidence", "") or "").strip()
                rendered = action
                if turn:
                    rendered += f"；转折: {turn}"
                if evidence:
                    rendered += f"；验收: {evidence}"
                if rendered:
                    lines.append(f"  - {rendered}")
        cast_objectives = [
            item
            for item in contract.get("cast_objectives", [])
            if isinstance(item, dict)
        ]
        if cast_objectives:
            lines.append("- 角色驱动目标:")
            for item in cast_objectives[:5]:
                name = str(item.get("name", "") or "").strip()
                objective = str(item.get("objective", "") or "").strip()
                pressure = str(item.get("pressure", "") or "").strip()
                if name:
                    lines.append(
                        f"  - {name}: {objective or '服务本章目标'}"
                        + (f"；压力: {pressure}" if pressure else "")
                    )
        emotional_arc = [
            str(item).strip()
            for item in contract.get("emotional_arc", [])
            if str(item).strip()
        ]
        if emotional_arc:
            lines.append("- 情绪弧: " + " -> ".join(emotional_arc[:4]))
        tension_points = [
            str(item).strip()
            for item in contract.get("tension_points", [])
            if str(item).strip()
        ]
        if tension_points:
            lines.append("- 压力点: " + "；".join(tension_points[:4]))
        cliffhanger = str(contract.get("cliffhanger", "") or "").strip()
        if cliffhanger:
            lines.append(f"- 结尾钩子: {cliffhanger}")
        driver_notes = [
            str(item).strip()
            for item in contract.get("driver_notes", [])
            if str(item).strip()
        ]
        if driver_notes:
            lines.append("- 叙事执行提示: " + "；".join(driver_notes[:4]))
        scope = str(contract.get("chapter_guidance_scope", "") or "").strip()
        if scope == "additive_only":
            lines.append("- 本章附加指令定位: 只补充执行方式，不覆盖主线目标锁。")
        budget = contract.get("new_setting_budget")
        if budget is not None and goal_lock:
            lines.append(f"- 新设定预算提醒: {budget}")
        checks = [
            str(item).strip()
            for item in contract.get("success_checks", [])
            if str(item).strip()
        ]
        for index, item in enumerate(checks, start=1):
            lines.append(f"{index}. {item}")
        return "\n".join(lines).strip()

    def _check_chapter_intent(
        self,
        *,
        outline: str,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Check whether the chapter plan is aligned before generation and rewrite it if needed."""
        context = context or {}
        goal_lock = self._extract_goal_lock(context)
        chapter_guidance = str(context.get("chapter_guidance", "") or "").strip()
        intent_text = "\n".join(
            part for part in [outline, chapter_guidance] if str(part or "").strip()
        )
        goal_terms = self._goal_terms(goal_lock)
        intro_fragments = self._extract_new_setting_intros(intent_text)
        budget = self._extract_new_setting_budget(context)
        matched_terms = self._find_goal_lock_matches(intent_text, goal_terms)
        has_goal_bridge = self._has_goal_bridge(intent_text, goal_lock)
        has_goal_signal = self._has_goal_lock_signal(intent_text, goal_lock, goal_terms)
        unbridged_fragments: list[str] = []
        for fragment in intro_fragments:
            window, _ = self._bridge_window(intent_text, fragment)
            if not self._has_goal_bridge(window, goal_lock):
                unbridged_fragments.append(fragment)

        result: dict[str, Any] = {
            "goal_lock": goal_lock,
            "goal_terms": goal_terms,
            "original_outline": str(outline or "").strip(),
            "chapter_guidance": chapter_guidance,
            "outline_matches": matched_terms,
            "has_goal_signal": has_goal_signal,
            "has_goal_bridge": has_goal_bridge,
            "new_setting_budget": budget,
            "new_setting_intro_fragments": intro_fragments[:5],
            "unbridged_new_setting_fragments": unbridged_fragments[:5],
            "issues": [],
            "rewritten_outline": str(outline or "").strip(),
            "passed": True,
        }
        if not str(outline or "").strip():
            result["skipped_reason"] = "missing_outline"
            return result
        if not goal_lock:
            result["skipped_reason"] = "missing_goal_lock"
            return result

        if not has_goal_signal and not has_goal_bridge:
            result["issues"].append("goal_lock_missing_from_plan")
        if intro_fragments and len(intro_fragments) > budget and unbridged_fragments:
            result["issues"].append("unbridged_new_setting_in_plan")

        result["passed"] = not result["issues"]
        if result["passed"]:
            return result

        planned_action = str(
            (context.get("chapter_intent_contract", {}) or {}).get("planned_action", "")
            or self._summarize_outline_focus(outline)
        ).strip()
        revised_lines = [
            f"原始大纲：{str(outline or '').strip()}",
            f"执行重写：开场先承接上一章局势，再把关键行动、冲突选择和结果对准主线目标锁：{goal_lock}",
        ]
        if planned_action:
            revised_lines.append(
                f"保留本章计划动作，但改写为直接服务目标锁：{planned_action}"
            )
        if unbridged_fragments:
            revised_lines.append(
                "以下新设定只能保留最小必要信息，并在同段或下一段桥接回主线："
                + " / ".join(unbridged_fragments[:2])
            )
        if chapter_guidance:
            revised_lines.append(
                f"附加指令仅作为补充执行方式，不得覆盖主线：{chapter_guidance}"
            )
        revised_lines.append(
            "正文摘要、关键事件和主体推进必须共享同一目标方向，禁止只在摘要里假对齐。"
        )
        result["rewritten_outline"] = "\n".join(revised_lines)
        return result

    def _compose_volume_guidance(self, context: dict[str, Any] | None) -> str:
        """Merge structured volume guidance payload with chapter-specific notes."""
        context = context or {}
        raw_guidance = str(context.get("volume_guidance", "") or "").strip()
        payload = self._volume_guidance_payload(context)
        if not payload:
            return raw_guidance

        labels = {
            "must_recover": "必须回收的伏笔/问题",
            "relationship_focus": "需要强化的人物关系",
            "must_avoid": "明确避免的方向",
            "tone_target": "目标基调",
            "goal_lock": "当前主线目标锁",
            "new_setting_budget": "新设定预算",
            "anti_drift_notes": "结构防漂移备注",
            "extra_notes": "补充说明",
        }
        structured_lines = [
            f"- {labels[key]}: {str(value).strip()}"
            for key, value in payload.items()
            if key in labels and str(value).strip()
        ]
        structured_guidance = "\n".join(structured_lines).strip()
        if not structured_guidance:
            return raw_guidance
        if not raw_guidance:
            return structured_guidance
        return f"{structured_guidance}\n{raw_guidance}"

    def _goal_terms(self, goal_lock: str) -> list[str]:
        """Split the goal lock into stable matching terms."""
        terms: list[str] = []
        normalized_goal = str(goal_lock or "").strip()
        for fragment in self._split_compound_goal_fragments(normalized_goal):
            if fragment not in terms:
                terms.append(fragment)
        for chunk in re.split(r"[，。；、：:！!？?\s/]+", normalized_goal):
            term = self._clean_anchor_candidate(chunk)
            if len(term) < 2 or term in ANTI_DRIFT_GOAL_STOPWORDS or term in terms:
                continue
            terms.append(term)
            if len(terms) >= 8:
                break
        for action in sorted(EVENT_ACTION_KEYWORDS, key=len, reverse=True):
            if action not in normalized_goal:
                continue
            if action not in terms:
                terms.append(action)
            action_index = normalized_goal.find(action)
            subject = normalized_goal[max(0, action_index - 4) : action_index].strip()
            subject = re.sub(r"[^\u4e00-\u9fff]", "", subject)[-4:]
            if len(subject) >= 2 and subject not in ANTI_DRIFT_GOAL_STOPWORDS and subject not in terms:
                terms.append(subject)
            object_tail = normalized_goal[action_index + len(action) :].strip()
            object_tail = re.sub(r"^(?:在|于|向|对|把|将|从|往|朝)", "", object_tail)
            object_tail = re.split(r"[，。；、：:！!？?\s/]+", object_tail, maxsplit=1)[0]
            object_tail = object_tail[:8].strip()
            if len(object_tail) >= 2 and object_tail not in ANTI_DRIFT_GOAL_STOPWORDS and object_tail not in terms:
                terms.append(object_tail)
            if len(terms) >= 8:
                break
        return terms

    def _extract_new_setting_intros(self, text: str) -> list[str]:
        """Extract high-confidence new-setting introduction fragments."""
        fragments: list[str] = []
        for sentence in re.split(r"[。！？!?]\s*|\n+", text):
            cleaned = sentence.strip()
            if not cleaned:
                continue
            match = ANTI_DRIFT_INTRO_PATTERN.search(cleaned)
            if not match:
                continue
            fragment = cleaned[:60]
            if fragment not in fragments:
                fragments.append(fragment)
        return fragments

    def _bridge_window(self, text: str, intro_fragment: str) -> tuple[str, bool]:
        """Return the bridge-check window and its mode."""
        paragraphs = [
            item.strip() for item in re.split(r"\n{2,}|\n", text) if item.strip()
        ]
        for index, paragraph in enumerate(paragraphs):
            if intro_fragment in paragraph:
                start = max(0, index - 1)
                end = min(len(paragraphs), index + 2)
                return "\n".join(paragraphs[start:end]), False
        return text[:900], True

    def _has_goal_bridge(self, text: str, goal_lock: str) -> bool:
        """Check whether a nearby window bridges the new setting back to the goal."""
        terms = self._goal_terms(goal_lock)
        if not text or not terms:
            return False
        hits_goal_term = any(term in text for term in terms)
        hits_connector = any(
            connector in text for connector in ANTI_DRIFT_BRIDGE_CONNECTORS
        )
        return hits_goal_term and hits_connector

    def _build_goal_lock_windows(self, content: str) -> list[str]:
        """Build deterministic body windows for goal-lock alignment checks."""
        paragraphs = [
            item.strip() for item in re.split(r"\n{2,}|\n", content) if item.strip()
        ]
        if len(paragraphs) >= 2:
            return paragraphs[:8]

        sentences = [
            item.strip() for item in re.split(r"[。！？!?]\s*", content) if item.strip()
        ]
        if not sentences:
            return [content[:220]] if content else []

        windows: list[str] = []
        for index in range(0, len(sentences), 2):
            window = "。".join(sentences[index : index + 2]).strip()
            if window:
                windows.append(window[:220])
        return windows[:8]

    def _find_goal_lock_matches(self, text: str, goal_terms: list[str]) -> list[str]:
        """Return the goal terms present in a text snippet in stable order."""
        matches: list[str] = []
        for term in goal_terms:
            if term in text and term not in matches:
                matches.append(term)
        return matches

    def _has_goal_lock_signal(
        self, text: str, goal_lock: str, goal_terms: list[str]
    ) -> bool:
        """Allow lightweight shorthand matching for pre-generation intent checks."""
        if not text or not goal_lock:
            return False
        if goal_lock in text or self._find_goal_lock_matches(text, goal_terms):
            return True
        normalized_text = self._normalize_text_for_match(text)
        normalized_goal = self._normalize_text_for_match(goal_lock)
        if len(normalized_goal) < 4:
            return False
        grams: list[str] = []
        for index in range(len(normalized_goal) - 1):
            gram = normalized_goal[index : index + 2]
            if len(gram) == 2 and gram not in grams:
                grams.append(gram)
        overlap = sum(1 for gram in grams if gram in normalized_text)
        return overlap >= 2

    def _window_negates_goal_lock(self, window: str) -> bool:
        """Detect goal mentions that explicitly do not advance the target."""
        return any(marker in window for marker in GOAL_LOCK_NEGATION_MARKERS)

    def _summary_text_for_goal_lock(self, chapter: GeneratedChapter) -> str:
        """Collect summary-like fields that should share the goal-lock anchor."""
        plot_summary = (
            chapter.plot_summary if isinstance(chapter.plot_summary, dict) else {}
        )
        summary_parts = [
            str(plot_summary.get("l2_brief_summary", "") or "").strip(),
            str(plot_summary.get("brief_summary", "") or "").strip(),
            str(plot_summary.get("l1_one_line_summary", "") or "").strip(),
            str(plot_summary.get("one_line_summary", "") or "").strip(),
            str(chapter.metadata.get("outline_summary", "") or "").strip(),
        ]
        return "\n".join(part for part in summary_parts if part)

    def _check_goal_lock_alignment(
        self,
        chapter: GeneratedChapter,
        context: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Detect false inheritance where the summary aligns but the body does not."""
        goal_lock = self._extract_goal_lock(context)
        goal_terms = self._goal_terms(goal_lock)
        goal_subgoals = self._split_compound_goal_fragments(goal_lock)
        details: dict[str, Any] = {
            "goal_lock": goal_lock,
            "goal_terms": goal_terms,
            "goal_subgoals": goal_subgoals,
            "covered_subgoals": [],
            "missing_subgoals": [],
            "summary_alignment": False,
            "body_alignment": False,
            "summary_matches": [],
            "body_matches": [],
            "checked_windows": [],
            "matched_fragments": [],
            "unaligned_fragments": [],
        }
        if not goal_lock:
            details["alignment_skipped_reason"] = "missing_goal_lock"
            return [], details

        summary_text = self._summary_text_for_goal_lock(chapter)
        summary_matches = self._find_goal_lock_matches(summary_text, goal_terms)
        details["summary_matches"] = summary_matches
        details["summary_alignment"] = bool(
            summary_matches or goal_lock in summary_text
        )

        body_matches: list[dict[str, Any]] = []
        covered_subgoals: set[str] = set()
        for window in self._build_goal_lock_windows(chapter.content):
            matched_terms = self._find_goal_lock_matches(window, goal_terms)
            covered_window_subgoals = [
                subgoal
                for subgoal in goal_subgoals
                if self._event_fragment_is_covered(subgoal, window, context)
            ]
            details["checked_windows"].append(window[:140])
            if not matched_terms and not covered_window_subgoals:
                continue
            negated = self._window_negates_goal_lock(window)
            aligned = not negated and (
                goal_lock in window
                or any(
                    connector in window for connector in ANTI_DRIFT_BRIDGE_CONNECTORS
                )
                or len(matched_terms) >= 2
                or (
                    bool(covered_window_subgoals)
                    and (len(goal_subgoals) <= 1 or len(covered_window_subgoals) == len(goal_subgoals))
                )
            )
            fragment = window[:140]
            body_matches.append(
                {
                    "fragment": fragment,
                    "matched_terms": matched_terms,
                    "covered_subgoals": covered_window_subgoals,
                    "negated": negated,
                    "aligned": aligned,
                }
            )
            if not negated:
                covered_subgoals.update(covered_window_subgoals)
            if aligned:
                details["body_alignment"] = True
            else:
                details["unaligned_fragments"].append(fragment)

        if len(goal_subgoals) > 1:
            overall_covered_subgoals = {
                subgoal
                for subgoal in goal_subgoals
                if self._event_fragment_is_covered(subgoal, chapter.content, context)
            }
            if overall_covered_subgoals:
                covered_subgoals.update(overall_covered_subgoals)

        if goal_subgoals and len(covered_subgoals) == len(goal_subgoals):
            details["body_alignment"] = True
        details["covered_subgoals"] = list(covered_subgoals)
        details["missing_subgoals"] = [
            item for item in goal_subgoals if item not in covered_subgoals
        ]
        details["body_matches"] = body_matches[:5]
        details["matched_fragments"] = [item["fragment"] for item in body_matches[:3]]

        if details["summary_alignment"] and not details["body_alignment"]:
            issue = {
                "category": "goal_lock_false_inheritance",
                "message": (
                    f"目标锁假继承[摘要命中但正文掉锚]: "
                    f"goal_lock={goal_lock}，摘要已对齐，但正文关键段落未围绕该目标推进。"
                ),
            }
            return [issue], details

        return [], details

    def _volume_guidance_payload(
        self, context: dict[str, Any] | None
    ) -> dict[str, Any]:
        runtime = self._packet_runtime(context)
        payload = runtime.get("volume_guidance_payload") if runtime else None
        if not isinstance(payload, dict):
            payload = context.get("volume_guidance_payload") if context else None
        return payload if isinstance(payload, dict) else {}

    def _parse_stage_gate_ratio(self, context: dict[str, Any] | None) -> float:
        payload = self._volume_guidance_payload(context)
        try:
            value = float(payload.get("anti_drift_start_ratio", 0.5))
        except (TypeError, ValueError):
            return 0.5
        if 0.0 <= value <= 1.0:
            return value
        return 0.5

    def _parse_stage_gate_min_chapter(self, context: dict[str, Any] | None) -> int:
        payload = self._volume_guidance_payload(context)
        try:
            value = int(payload.get("anti_drift_min_chapter", 30))
        except (TypeError, ValueError):
            return 30
        return value if value >= 1 else 30

    def _goal_lock_false_inheritance_mode(self, context: dict[str, Any] | None) -> str:
        payload = self._volume_guidance_payload(context)
        mode = (
            str(payload.get("goal_lock_false_inheritance_mode", "block") or "block")
            .strip()
            .lower()
        )
        return mode if mode in {"block", "warn"} else "block"

    def _resolve_stage_gate(
        self, context: dict[str, Any] | None
    ) -> tuple[bool, str, str | None]:
        """Resolve whether the current chapter is in the mid/late-stage anti-drift window."""
        context = context or {}
        chapter_number = int(context.get("chapter_number") or 0)
        total_chapters = int(context.get("total_chapters") or 0)
        if chapter_number <= 0:
            return False, "ratio", "missing_chapter_number"
        if total_chapters > 0:
            return (
                (chapter_number / total_chapters)
                >= self._parse_stage_gate_ratio(context),
                "ratio",
                None,
            )
        return (
            chapter_number >= self._parse_stage_gate_min_chapter(context),
            "fixed_threshold_degraded",
            None,
        )

    def _extract_new_setting_budget(self, context: dict[str, Any] | None) -> int:
        """Extract the structured budget for new-setting introductions."""
        payload = self._volume_guidance_payload(context)
        if payload:
            raw_budget = payload.get("new_setting_budget", "")
            try:
                return max(int(raw_budget), 0)
            except (TypeError, ValueError):
                pass
        return 1

    def _check_structure_drift(
        self,
        content: str,
        previous_summary: str,
        context: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Detect mid/late-stage structure drift caused by unbridged new settings."""
        del previous_summary
        goal_lock = self._extract_goal_lock(context)
        details: dict[str, Any] = {
            "goal_lock": goal_lock,
            "goal_terms": self._goal_terms(goal_lock),
            "budget": self._extract_new_setting_budget(context),
            "anti_drift_start_ratio": self._parse_stage_gate_ratio(context),
            "anti_drift_min_chapter": self._parse_stage_gate_min_chapter(context),
            "counted_intro_fragments": [],
            "intro_count": 0,
            "bridge_results": [],
            "bridge_window_fallback_used": False,
        }
        if not goal_lock:
            details["skipped_reason"] = "missing_goal_lock"
            return [], details

        is_mid_late, stage_gate_mode, skipped_reason = self._resolve_stage_gate(context)
        details["stage_gate_mode"] = stage_gate_mode
        if not is_mid_late:
            details["skipped_reason"] = skipped_reason or "not_mid_late_stage"
            return [], details

        intro_fragments = self._extract_new_setting_intros(content)
        details["counted_intro_fragments"] = intro_fragments[:8]
        details["intro_count"] = len(intro_fragments)
        if not intro_fragments:
            return [], details

        fallback_used = False
        unbridged_fragments: list[str] = []
        bridge_results: list[dict[str, Any]] = []
        for fragment in intro_fragments:
            window, used_fallback = self._bridge_window(content, fragment)
            has_bridge = self._has_goal_bridge(window, goal_lock)
            bridge_results.append({"fragment": fragment, "has_bridge": has_bridge})
            if used_fallback:
                fallback_used = True
            if not has_bridge:
                unbridged_fragments.append(fragment)
        details["bridge_results"] = bridge_results
        details["bridge_window_fallback_used"] = fallback_used
        details["unbridged_fragments"] = unbridged_fragments[:5]

        budget = int(details["budget"])
        if len(intro_fragments) <= budget or not unbridged_fragments:
            return [], details

        evidence_terms = "、".join(details["goal_terms"][:3]) or "无"
        evidence_fragments = " / ".join(unbridged_fragments[:2])
        issue = {
            "category": "structure_drift_risk",
            "message": (
                f"结构漂移风险[主线目标锁被新设定冲散]: "
                f"budget={budget}，goal_terms={evidence_terms}，"
                f"未桥接新设定={evidence_fragments}"
            ),
        }
        return [issue], details

    def _build_semantic_warning_review(
        self,
        *,
        chapter: GeneratedChapter,
        context: dict[str, Any] | None,
        anti_drift_details: dict[str, Any],
        goal_lock_alignment_issues: list[dict[str, Any]],
        structure_drift_issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build warning-only semantic review signals without affecting blocking gates."""
        del chapter
        context = context or {}
        warning_issues: list[dict[str, Any]] = []
        chapter_intent_check = dict(context.get("chapter_intent_check", {}) or {})
        goal_lock = str(anti_drift_details.get("goal_lock", "") or "").strip()

        if chapter_intent_check and not chapter_intent_check.get("passed", True):
            warning_issues.append(
                {
                    "category": "chapter_intent_rewrite_applied",
                    "severity": "warning",
                    "message": "生成前意图检查已重写章节大纲，本章虽继续生成，但建议观察是否出现计划层掉锚复发。",
                    "evidence": {
                        "issues": list(chapter_intent_check.get("issues", [])),
                        "rewritten_outline": str(
                            chapter_intent_check.get("rewritten_outline", "") or ""
                        ).strip()[:220],
                    },
                }
            )

        body_matches = list(anti_drift_details.get("body_matches", []) or [])
        unaligned_fragments = list(
            anti_drift_details.get("unaligned_fragments", []) or []
        )
        if (
            goal_lock
            and not goal_lock_alignment_issues
            and anti_drift_details.get("summary_alignment")
            and anti_drift_details.get("body_alignment")
            and len(body_matches) == 1
            and unaligned_fragments
        ):
            warning_issues.append(
                {
                    "category": "goal_lock_semantic_risk",
                    "severity": "warning",
                    "message": f"目标锁当前未触发硬阻断，但正文只有少量片段显式推进 `{goal_lock}`，仍有语义层掉锚风险。",
                    "evidence": {
                        "body_match_count": len(body_matches),
                        "matched_fragment": str(
                            body_matches[0].get("fragment", "") or ""
                        ).strip(),
                        "unaligned_fragments": unaligned_fragments[:2],
                    },
                }
            )

        intro_count = int(anti_drift_details.get("intro_count", 0) or 0)
        budget = int(anti_drift_details.get("budget", 0) or 0)
        unbridged_fragments = list(
            anti_drift_details.get("unbridged_fragments", []) or []
        )
        bridge_results = list(anti_drift_details.get("bridge_results", []) or [])
        if (
            goal_lock
            and not structure_drift_issues
            and intro_count > 0
            and bridge_results
        ):
            warning_issues.append(
                {
                    "category": "structure_drift_watch",
                    "severity": "warning",
                    "message": "本章引入了新设定，虽然尚未触发结构漂移阻断，但建议继续观察后续章节是否持续桥接主线。",
                    "evidence": {
                        "intro_count": intro_count,
                        "budget": budget,
                        "unbridged_fragments": unbridged_fragments[:2],
                        "bridge_results": bridge_results[:2],
                    },
                }
            )

        return {
            "enabled": True,
            "warning_only": True,
            "issue_count": len(warning_issues),
            "issues": warning_issues,
            "summary": "；".join(issue["message"] for issue in warning_issues[:2]),
        }

    def _run_semantic_advisory(
        self,
        *,
        chapter: GeneratedChapter,
        previous_summary: str,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Run optional LLM semantic advisory without affecting hard gates."""
        context = context or {}
        if not context.get("semantic_advisory_enabled"):
            return {
                "enabled": False,
                "warning_only": True,
                "status": "skipped",
                "reason": "not_configured",
            }
        if self.llm_client is None or not hasattr(self.llm_client, "generate"):
            return {
                "enabled": True,
                "warning_only": True,
                "status": "skipped",
                "reason": "provider_unavailable",
            }
        prompt = (
            "请以 JSON 评审本章语义质量，字段为 overall_score(0-1), "
            "mainline_progress, character_motivation, causal_continuity, style_drift, "
            "warnings(list)。只输出 JSON。\n\n"
            f"前情摘要:\n{previous_summary[:800]}\n\n"
            f"本章正文:\n{chapter.content[:3000]}"
        )
        try:
            raw = self.llm_client.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1000,
            )
            payload = json.loads(str(raw))
            if not isinstance(payload, dict):
                raise ValueError("semantic advisory response must be a JSON object")
            score = float(payload.get("overall_score", 0.0) or 0.0)
            score = max(0.0, min(score, 1.0))
            raw_warnings = payload.get("warnings", []) or []
            if not isinstance(raw_warnings, list):
                raw_warnings = [raw_warnings]
            warnings = [
                str(item)
                for item in raw_warnings
                if str(item).strip()
            ]
        except Exception as exc:
            return {
                "enabled": True,
                "warning_only": True,
                "status": "error",
                "reason": str(exc),
            }
        return {
            "enabled": True,
            "warning_only": True,
            "status": "completed",
            "overall_score": score,
            "scores": {
                "mainline_progress": payload.get("mainline_progress"),
                "character_motivation": payload.get("character_motivation"),
                "causal_continuity": payload.get("causal_continuity"),
                "style_drift": payload.get("style_drift"),
            },
            "warnings": warnings,
        }

    def _check_consistency(
        self,
        chapter: GeneratedChapter,
        previous_summary: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check consistency of generated chapter and auto-extract character states."""
        content = chapter.content
        character_states = {}
        character_consistency = []
        plot_consistency = []
        recommendations = []

        # P2 FIX: Auto-extract character states from content
        # Match actual content format: quoted dialogue + attribution, or narration with character name
        import re

        # P1 FIX: Dynamic character names from context (fallback to minimal set)
        known_char_names = self._resolve_known_char_names(context)

        # P1 FIX: Extended dialogue suffixes (all common Chinese dialogue verbs)
        dialogue_suffixes = r"(?:的|声音|说道|问道|回答|喊道|轻声道|冷笑道|怒道|叹道|低声道|低语道|喃喃道|沉声道|厉声道|朗声道|颤声道|哽咽道|哭诉道|怒吼道|暴喝道|冷声道|淡声道|平静道|缓缓道|郑重道|轻叹道|悲叹道|惨笑道|嗤笑道|高声道|扬声道|宣判道|陈述道|补充道|提醒道|告诫道|警告道|解释道|说明道|断言道|坚称道|声称道|争辩道|抗辩道|认命道|绝望道|茫然道|恍惚道|清醒道|断续道)"

        # Extended suffix pattern for char name extraction
        char_name_suffix_pattern = r"([\u4e00-\u9fff]{2,4})" + dialogue_suffixes

        # Pattern 1a: Double quotes "" (non-greedy) followed by attribution
        # e.g., "好。"测灵台上的声音 -> dialogue="好", attribution="测灵台上的声音"
        quoted_dialogue_pattern = re.compile(
            r'"([^"]+?)"\s*([\u4e00-\u9fff]{2,20}?' + dialogue_suffixes + r")",
            re.DOTALL,
        )
        # Pattern 1b: Chinese corner brackets 『』
        quoted_dialogue_pattern_alt1 = re.compile(
            r"『([^』]+?)』\s*([\u4e00-\u9fff]{2,20}?" + dialogue_suffixes + r")",
            re.DOTALL,
        )
        # Pattern 1c: Chinese corner brackets 「」
        quoted_dialogue_pattern_alt2 = re.compile(
            r"「([^」]+?)」\s*([\u4e00-\u9fff]{2,20}?" + dialogue_suffixes + r")",
            re.DOTALL,
        )
        # Pattern 1d: Dash-bounded dialogue "——对话——"
        quoted_dialogue_pattern_dash = re.compile(
            r'[""'
            ']?——([^——]+?)——[""'
            "]?(?:\\s)*([\u4e00-\u9fff]{2,20}?" + dialogue_suffixes + r")?",
            re.DOTALL,
        )
        # Pattern 1e: Colon format "角色："对话"" or 角色："对话"
        quoted_dialogue_pattern_colon = re.compile(
            r'([\u4e00-\u9fff]{2,4})[：:]"([^"]+?)"\s*([\u4e00-\u9fff]{2,20}?'
            + dialogue_suffixes
            + r")?",
            re.DOTALL,
        )

        for pattern in [
            quoted_dialogue_pattern,
            quoted_dialogue_pattern_alt1,
            quoted_dialogue_pattern_alt2,
        ]:
            for match in pattern.finditer(content):
                dialogue = match.group(1)[:40]
                attribution = match.group(2)
                char_match = re.search(char_name_suffix_pattern, attribution)
                if char_match:
                    char_name = char_match.group(1)
                    if (
                        char_name in known_char_names
                        and char_name not in character_states
                    ):
                        character_states[char_name] = f"「{dialogue}」"

        # Pattern 1d: Dash-bounded
        for match in quoted_dialogue_pattern_dash.finditer(content):
            dialogue = match.group(1)[:40]
            attribution = match.group(2) if match.group(2) else ""
            if attribution:
                char_match = re.search(char_name_suffix_pattern, attribution)
                if char_match:
                    char_name = char_match.group(1)
                    if (
                        char_name in known_char_names
                        and char_name not in character_states
                    ):
                        character_states[char_name] = f"「{dialogue}」"
            else:
                # Try to find character name before the dash
                start = max(0, match.start() - 10)
                prefix = content[start : match.start()]
                for char_name in known_char_names:
                    if char_name in prefix and char_name not in character_states:
                        character_states[char_name] = f"「{dialogue}」"
                        break

        # Pattern 1e: Colon format
        for match in quoted_dialogue_pattern_colon.finditer(content):
            char_name = match.group(1)
            dialogue = match.group(2)[:40]
            if char_name in known_char_names and char_name not in character_states:
                character_states[char_name] = f"「{dialogue}」"

        # Pattern 2: Character name followed by narration (with extended verb/action list)
        # e.g., 韩林深吸一口气，迈步走向...
        # e.g., 柳如烟当众撕毁婚书...
        char_action_pattern = re.compile(
            r"([\u4e00-\u9fff]{2,4})(?:深吸一口气|缓步|缓缓|目光|看着|听着|心中|说道|问道|回答|喊道|轻声|冷笑|怒视|转身|停下|抬起头|低下头|握紧|松开|举起|放下|迈步|抬眸|皱眉|微笑|叹息|摇头|点头|睁大|眯起|愣住|回过神来|颤了颤|咬紧|跪下|站起身|坐起身|躺下|闭上眼|睁开眼|转过身|回过头|垂下头|昂起头|板着脸|沉下脸|挤出笑|冷冷地|缓缓地|静静地|默默地|呆呆地|悄悄|轻声|高声|低声|朗声|沉声|厉声|哽咽|颤抖|平静|从容|镇定|冷笑|轻笑|大笑|苦笑|傻笑|狞笑|微笑|暗笑|讨好|赔笑|皮笑肉不笑)",
            re.DOTALL,
        )
        for match in char_action_pattern.finditer(content):
            char_name = match.group(1)
            if char_name in known_char_names and char_name not in character_states:
                start = max(0, match.start() - 5)
                end = min(len(content), match.end() + 30)
                snippet = content[start:end].replace("\n", " ").strip()
                character_states[char_name] = snippet[:80]

        # Pattern 3: Find known character names that appear in content
        for char_name in known_char_names:
            if char_name not in character_states and char_name in content:
                occurrences = list(re.finditer(re.escape(char_name), content))
                if occurrences:
                    for occ in occurrences[:3]:
                        start = max(0, occ.start() - 10)
                        end = min(len(content), occ.end() + 20)
                        snippet = content[start:end].replace("\n", " ").strip()
                        if len(snippet) > 3 and not snippet.startswith(("...", "……")):
                            character_states[char_name] = snippet[:80]
                            break

        # Check outline key events against content
        key_events = chapter.metadata.get("key_events", [])
        outline_summary = chapter.metadata.get("outline_summary", "")
        magic_line = chapter.metadata.get("magic_line", "")

        missing_events = []
        for event in key_events:
            if len(event) < 4:
                continue
            if not self._event_is_covered(event, content, context):
                missing_events.append(event)

        # Score based on completeness
        event_score = (
            1.0
            if len(missing_events) == 0
            else max(0, 1.0 - len(missing_events) / max(len(key_events), 1))
        )
        char_score = min(1.0, len(character_states) / 3) if character_states else 0.5
        overall_score = round((event_score * 0.6 + char_score * 0.4) * 10, 1)

        if missing_events:
            recommendations.append(f"缺少关键事件: {'; '.join(missing_events[:3])}")

        if not character_states:
            recommendations.append("未能提取角色状态，请检查角色对话格式")
            overall_score = max(overall_score, 5.0)

        continuity_issues = self._check_transition_continuity(
            content=content,
            previous_summary=previous_summary,
            context=context,
        )
        world_fact_issues = self._check_world_fact_consistency(
            content=content,
            previous_summary=previous_summary,
            previous_chapters=context.get("previous_chapters", []) if context else [],
        )
        blocking_issues = []
        issue_types = []
        if missing_events:
            blocking_issues.append(f"缺少关键事件: {'; '.join(missing_events[:3])}")
            issue_types.append("missing_key_events")
        if continuity_issues:
            blocking_issues.extend(
                issue["message"] if isinstance(issue, dict) else str(issue)
                for issue in continuity_issues
            )
            issue_types.append("scene_or_timeline_disconnect")
        if world_fact_issues:
            blocking_issues.extend(world_fact_issues)
            issue_types.append("world_fact_violation")
        goal_lock_alignment_issues, goal_lock_details = self._check_goal_lock_alignment(
            chapter=chapter,
            context=context,
        )
        structure_drift_issues, anti_drift_details = self._check_structure_drift(
            content=content,
            previous_summary=previous_summary,
            context=context,
        )
        try:
            writer_rule_warnings = check_writer_rules(content)
        except Exception as exc:
            logger.warning("Could not evaluate writer rules: %s", exc)
            writer_rule_warnings = []
        anti_drift_details = {
            **anti_drift_details,
            **goal_lock_details,
        }
        goal_lock_mode = self._goal_lock_false_inheritance_mode(context)
        anti_drift_details["goal_lock_false_inheritance_mode"] = goal_lock_mode
        goal_lock_safety_backstop = any(
            bool(item.get("negated"))
            for item in anti_drift_details.get("body_matches", []) or []
            if isinstance(item, dict)
        ) or bool(structure_drift_issues)
        anti_drift_details["goal_lock_false_inheritance_backstop"] = (
            goal_lock_safety_backstop
        )
        goal_lock_event_backstop = (
            bool(goal_lock_alignment_issues)
            and not missing_events
            and not continuity_issues
            and not world_fact_issues
            and not structure_drift_issues
            and bool(anti_drift_details.get("summary_alignment"))
            and not goal_lock_safety_backstop
        )
        anti_drift_details["goal_lock_event_backstop"] = goal_lock_event_backstop
        goal_lock_blocks = (
            goal_lock_mode == "block" or goal_lock_safety_backstop
        ) and not goal_lock_event_backstop
        if goal_lock_alignment_issues:
            if goal_lock_blocks:
                blocking_issues.extend(
                    issue["message"] for issue in goal_lock_alignment_issues
                )
                issue_types.append("goal_lock_false_inheritance")
        if structure_drift_issues:
            blocking_issues.extend(issue["message"] for issue in structure_drift_issues)
            issue_types.append("structure_drift_risk")
        smoothness_details = (
            continuity_issues
            if continuity_issues and isinstance(continuity_issues[0], dict)
            else []
        )
        continuity_messages = [
            issue["message"] if isinstance(issue, dict) else str(issue)
            for issue in continuity_issues
        ]
        if (
            continuity_messages
            or world_fact_issues
            or missing_events
            or structure_drift_issues
        ):
            overall_score = min(overall_score, 4.8)
        if continuity_messages:
            recommendations.extend(continuity_messages)

        semantic_review = self._build_semantic_warning_review(
            chapter=chapter,
            context=context,
            anti_drift_details=anti_drift_details,
            goal_lock_alignment_issues=goal_lock_alignment_issues,
            structure_drift_issues=structure_drift_issues,
        )
        semantic_advisory = self._run_semantic_advisory(
            chapter=chapter,
            previous_summary=previous_summary,
            context=context,
        )
        semantic_review["llm_advisory"] = semantic_advisory
        if semantic_advisory.get("status") == "completed":
            score = semantic_advisory.get("overall_score", 1.0)
            if score < 0.6:
                semantic_review.setdefault("issues", []).append(
                    {
                        "category": "semantic_advisory_low_score",
                        "severity": "warning",
                        "message": f"LLM 语义 advisory 分数偏低: {score:.2f}",
                        "evidence": semantic_advisory,
                    }
                )
                semantic_review["issue_count"] = len(
                    semantic_review.get("issues", [])
                )
                semantic_review["summary"] = "；".join(
                    str(item.get("message", "") or "")
                    for item in semantic_review.get("issues", [])[:2]
                )
        warning_issues = [
            str(item.get("message", "") or "").strip()
            for item in semantic_review.get("issues", [])
        ]
        if goal_lock_alignment_issues and not goal_lock_blocks:
            warning_issues.extend(
                issue["message"] for issue in goal_lock_alignment_issues
            )
            semantic_review.setdefault("issues", []).extend(
                {
                    "category": "goal_lock_false_inheritance",
                    "severity": "warning",
                    "message": issue["message"],
                    "evidence": anti_drift_details,
                }
                for issue in goal_lock_alignment_issues
            )
            semantic_review["issue_count"] = len(semantic_review.get("issues", []))
            semantic_review["summary"] = "；".join(
                str(item.get("message", "") or "")
                for item in semantic_review.get("issues", [])[:2]
            )
        recommendations.extend(
            f"语义复核告警: {item}" for item in warning_issues if item
        )
        writer_rule_messages = [
            (
                f"{item.get('category')}: 命中 {'、'.join(item.get('matches', [])[:4])}; "
                f"{item.get('guidance', '')}"
            )
            for item in writer_rule_warnings
        ]
        recommendations.extend(
            f"WRITER.md 告警: {item}" for item in writer_rule_messages if item
        )
        hard_gate_issue_types = classify_hard_gate_issue_types(issue_types)
        graph_diff_details = build_graph_diff_details(
            chapter_number=chapter.number,
            context=context,
            missing_events=missing_events,
            continuity_issues=continuity_issues,
            world_fact_issues=world_fact_issues,
            anti_drift_details=anti_drift_details,
            hard_gate_issue_types=hard_gate_issue_types,
        )

        rewrite_guidance = ""
        rewrite_plan: dict[str, Any] = {}
        if hard_gate_issue_types:
            rewrite_source = {
                "blocking_issues": blocking_issues,
                "missing_events": missing_events,
                "smoothness_details": smoothness_details,
                "anti_drift_details": anti_drift_details,
                "issue_types": hard_gate_issue_types,
            }
            rewrite_plan = self._build_rewrite_plan(rewrite_source)
            rewrite_guidance = self._format_rewrite_guidance(rewrite_plan)
            recommendations.append(f"重写建议: {rewrite_guidance}")

        return {
            "character_consistency": character_consistency,
            "character_states": character_states,
            "plot_consistency": plot_consistency,
            "missing_events": missing_events,
            "continuity_issues": continuity_messages,
            "world_fact_issues": world_fact_issues,
            "blocking_issues": blocking_issues,
            "issue_types": issue_types,
            "hard_gate_issue_types": hard_gate_issue_types,
            "invalid": bool(hard_gate_issue_types),
            "overall_score": overall_score,
            "recommendations": recommendations,
            "smoothness_details": smoothness_details,
            "anti_drift_details": anti_drift_details,
            "warning_issues": warning_issues,
            "semantic_review": semantic_review,
            "writer_rule_warnings": writer_rule_warnings,
            "chapter_intent_contract": dict(
                (context or {}).get("chapter_intent_contract", {}) or {}
            ),
            "chapter_intent_check": dict(
                (context or {}).get("chapter_intent_check", {}) or {}
            ),
            "chapter_driver_packet": dict(
                (context or {}).get("chapter_driver_packet", {}) or {}
            ),
            "chapter_driver_summary": str(
                (context or {}).get("chapter_driver_summary", "") or ""
            ),
            "chapter_driver_validation": list(
                (context or {}).get("chapter_driver_validation", []) or []
            ),
            "chapter_graph_packet": dict(
                (context or {}).get("chapter_graph_packet", {}) or {}
            ),
            "graph_diff_details": graph_diff_details,
            "rewrite_plan": rewrite_plan,
            "rewrite_guidance": rewrite_guidance,
            "summary": "；".join(blocking_issues[:3])
            if blocking_issues
            else "章节满足当前质量闸门。",
        }

    def _check_world_fact_consistency(
        self,
        *,
        content: str,
        previous_summary: str,
        previous_chapters: list[dict[str, Any]],
    ) -> list[str]:
        """Detect obvious violations of established world facts."""
        recent_context = [previous_summary]
        if previous_chapters:
            recent_context.append(str(previous_chapters[-1].get("content", ""))[-1200:])
        recent_text = "\n".join(part for part in recent_context if part)
        if not recent_text:
            return []

        issues: list[str] = []
        for subject in self._extract_resolved_subjects(recent_text, DEATH_MARKERS):
            if subject in content and re.search(
                rf"{re.escape(subject)}.*?(说|问|笑|走|站|出手|现身)", content
            ):
                issues.append(
                    f"前文已明确 {subject} 退场或死亡，但本章再次将其作为活跃对象使用。"
                )

        for item in self._extract_resolved_subjects(recent_text, ITEM_LOSS_MARKERS):
            if item in content and any(
                marker in content for marker in ITEM_REAPPEAR_MARKERS
            ):
                issues.append(
                    f"前文已明确 {item} 不可再用或已消失，但本章出现了无铺垫的重新出现。"
                )

        return issues

    def _extract_resolved_subjects(
        self, text: str, markers: tuple[str, ...]
    ) -> list[str]:
        """Extract named subjects marked as gone, dead, or consumed in prior text."""
        if not text:
            return []
        subjects: list[str] = []
        marker_pattern = "|".join(re.escape(marker) for marker in markers)
        pattern = re.compile(
            rf"(?:^|[，。；、\s])([\u4e00-\u9fff]{{2,8}}?)(?:{marker_pattern})"
        )
        for match in pattern.finditer(text):
            subject = match.group(1).strip()
            for prefix in (
                "上一章",
                "上章",
                "此前",
                "之前",
                "曾经",
                "已经",
                "那件",
                "那把",
                "那枚",
            ):
                if subject.startswith(prefix):
                    subject = subject[len(prefix) :]
            for suffix in ("也", "已", "曾", "又", "再"):
                if subject.endswith(suffix):
                    subject = subject[: -len(suffix)]
            if subject and subject not in subjects:
                subjects.append(subject)
        return subjects[:6]


def get_novel_generator(
    config_manager,
    novel_orchestrator=None,
    llm_client=None,
    allow_fallback: bool = True,
) -> NovelGeneratorAgent:
    """Get a NovelGeneratorAgent instance."""
    return NovelGeneratorAgent(
        config_manager=config_manager,
        novel_orchestrator=novel_orchestrator,
        llm_client=llm_client,
        allow_fallback=allow_fallback,
    )
