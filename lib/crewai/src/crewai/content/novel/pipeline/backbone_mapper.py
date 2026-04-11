"""BackboneMapper: map classical literature backbone events to novel events.

Given a reference work (e.g. 西游记) and a novel's plot_data, produces a list of
:class:`BackboneMapping` objects that the :class:`BackboneValidator` can verify.

Two mapping strategies are supported:

1. **LLM-assisted** (default): sends reference events + plot_data to the LLM and
   asks it to produce a structured JSON mapping with ``spiritual_core`` for each.
2. **Algorithmic fallback**: uses positional alignment + keyword-based archetype
   similarity when LLM mapping fails or is unavailable.

Typical usage::

    mapper = BackboneMapper(llm=deepseek_client)
    reference_events = BackboneValidator.load_reference_events(
        backbone_path, "西游记",
    )
    mappings = mapper.map(
        reference_events=reference_events,
        plot_data=state.plot_data,
        mode="strict",
    )
    # → list[BackboneMapping] ready for BackboneValidator.validate()
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from crewai.content.novel.pipeline.backbone_validator import BackboneMapping
from crewai.llm.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Archetype keyword index (Chinese → canonical key)
# ---------------------------------------------------------------------------

_ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "英雄诞生": ["诞生", "出世", "降临", "起源", "觉醒"],
    "反抗权威": ["反抗", "叛逆", "挑战", "大闹", "对抗"],
    "惩罚与救赎": ["惩罚", "镇压", "被困", "入狱", "囚禁", "救赎"],
    "任务开始": ["出发", "使命", "开始", "启程", "下山"],
    "伙伴加入": ["收", "加入", "同伴", "聚义", "结义"],
    "考验与怀疑": ["考验", "试探", "怀疑", "信任", "背叛"],
    "欲望诱惑": ["诱惑", "欲望", "迷惑", "色", "情"],
    "自我克制": ["克制", "忍耐", "放下", "修心"],
    "身份认同": ["身份", "真假", "认同", "自我"],
    "终极挑战": ["终极", "最强", "大战", "决战", "对决"],
    "目标达成": ["达成", "取得", "成功", "完成", "获得"],
    "彻底蜕变": ["蜕变", "圆满", "成佛", "飞升", "突破"],
    "冤案与陷害": ["冤", "陷害", "诬陷", "冤狱"],
    "英雄初现": ["打虎", "成名", "初现", "崭露"],
    "英雄堕落": ["堕落", "犯罪", "杀", "逼上"],
    "团队形成": ["聚义", "结盟", "集结", "排座"],
    "理想妥协": ["招安", "妥协", "投降", "归顺"],
    "英雄末路": ["末路", "陨落", "牺牲", "悲剧"],
    "关键战役": ["大战", "战役", "赤壁", "之战"],
    "权力继承": ["托孤", "继承", "传位", "接班"],
    "历史循环": ["归晋", "统一", "轮回", "循环"],
    "导师出现": ["导师", "师父", "得师", "传授"],
    "命运转机": ["转机", "宝藏", "奇遇", "机缘"],
    "重生与蜕变": ["重生", "越狱", "脱困", "新生"],
    "复仇实施": ["复仇", "报仇", "讨伐", "清算"],
    "救赎与和解": ["和解", "宽恕", "放下", "原谅"],
    "实力提升": ["修炼", "突破", "提升", "升级"],
    "世界扩展": ["闯荡", "探索", "中州", "新世界"],
}


# ---------------------------------------------------------------------------
# BackboneMapper
# ---------------------------------------------------------------------------


@dataclass
class BackboneMapper:
    """Map classical backbone events to novel plot events.

    Args:
        llm:  DeepSeekClient instance for LLM-assisted mapping.  When ``None``,
              only the algorithmic fallback is used.
        fallback_confidence: Default confidence assigned to algorithmic mappings.
    """

    llm: DeepSeekClient | None = None
    fallback_confidence: float = 0.55

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def map(
        self,
        reference_events: list[dict[str, Any]],
        plot_data: dict[str, Any],
        mode: str = "loose",
    ) -> list[BackboneMapping]:
        """Produce backbone mappings from reference events → novel plot events.

        Args:
            reference_events: List of event dicts from ``classical_backbones.json``
                              (keys: order, name, content, archetype).
            plot_data:        Novel outline dict from OutlineStage (keys: plot_arcs,
                              turning_points, main_characters, …).
            mode:             ``"loose"`` (inspiration) or ``"strict"`` (mandatory
                              structural anchors).

        Returns:
            List of :class:`BackboneMapping` objects.  In strict mode the mapper
            tries harder to cover every reference event.
        """
        if not reference_events:
            logger.warning("[backbone_mapper] No reference events; returning empty mappings.")
            return []

        # 1. Try LLM-assisted mapping first
        if self.llm is not None:
            mappings = self._llm_map(reference_events, plot_data, mode)
            if mappings:
                logger.info(
                    "[backbone_mapper] LLM mapping produced %d mappings for %d reference events.",
                    len(mappings),
                    len(reference_events),
                )
                # In strict mode, fill gaps with algorithmic fallback
                if mode == "strict":
                    mappings = self._fill_gaps(mappings, reference_events, plot_data)
                return mappings

        # 2. Algorithmic fallback
        logger.info("[backbone_mapper] Using algorithmic fallback mapping.")
        return self._algorithmic_map(reference_events, plot_data, mode)

    # ------------------------------------------------------------------
    # LLM-assisted mapping
    # ------------------------------------------------------------------

    def _llm_map(
        self,
        reference_events: list[dict[str, Any]],
        plot_data: dict[str, Any],
        mode: str,
    ) -> list[BackboneMapping]:
        """Ask the LLM to semantically map reference events to novel events."""
        assert self.llm is not None

        ref_block = self._format_reference_events(reference_events)
        novel_block = self._format_novel_events(plot_data)

        mode_instruction = (
            "你必须为每一个参考事件都找到对应的小说事件。如果某个参考事件没有直接对应，"
            "请创造性地映射到最相近的情节节点，并说明精神内核的传承关系。mapping_confidence 应反映"
            "映射的紧密程度（1.0 = 完美对应，0.5 = 需要创造性改编，< 0.3 = 勉强关联）。"
            if mode == "strict"
            else "请将参考事件映射到小说中最相关的情节。没有合理对应的事件可以跳过。"
        )

        system_prompt = (
            "你是一位叙事结构分析专家，擅长提取经典文学的叙事骨架并将其映射到新小说。\n"
            "你的任务是将参考骨架事件映射到目标小说的情节节点，并提取每个映射的「精神内核」——\n"
            "即参考事件所承载的叙事功能和主题意义在新语境下的传承。\n\n"
            "输出要求：\n"
            "- 直接输出 JSON 数组，不要包含 markdown 标记或代码块\n"
            "- 每个元素格式：\n"
            "  {\n"
            '    "reference_event_name": "参考事件名",\n'
            '    "reference_event_content": "参考事件描述",\n'
            '    "novel_event_name": "小说中对应事件名",\n'
            '    "novel_chapter": 章节号(整数),\n'
            '    "mapping_confidence": 0.0-1.0,\n'
            '    "spiritual_core": "精神内核描述(20字内)"\n'
            "  }\n"
        )

        user_prompt = (
            "=== 参考骨架事件 ===\n"
            f"{ref_block}\n\n"
            "=== 目标小说情节节点 ===\n"
            f"{novel_block}\n\n"
            f"映射要求：{mode_instruction}\n\n"
            "精神内核提取指导：\n"
            "- 不要简单复述事件内容\n"
            "- 要概括该事件在叙事中承担的结构功能（如：打破旧秩序、暴露隐藏矛盾、确立新盟约等）\n"
            "- 精神内核是跨故事的通用概念，不应包含具体人名或地名\n\n"
            "请输出 JSON 数组。"
        )

        try:
            raw = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=4096,
                temperature=0.4,
            )
            return self._parse_llm_mappings(raw)
        except Exception as exc:
            logger.warning("[backbone_mapper] LLM mapping failed: %s", exc)
            return []

    def _parse_llm_mappings(self, raw: str) -> list[BackboneMapping]:
        """Parse the LLM response into a list of BackboneMapping objects."""
        # Strip <think> blocks
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()

        # Try to extract JSON array
        data = self._extract_json_array(cleaned)
        if data is None:
            logger.warning("[backbone_mapper] Could not parse LLM response as JSON array.")
            return []

        mappings: list[BackboneMapping] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                mapping = BackboneMapping(
                    reference_event_name=str(item.get("reference_event_name", "")),
                    reference_event_content=str(item.get("reference_event_content", "")),
                    novel_event_name=str(item.get("novel_event_name", "")),
                    novel_chapter=int(item.get("novel_chapter", 0)),
                    mapping_confidence=float(item.get("mapping_confidence", 0.0)),
                    spiritual_core=str(item.get("spiritual_core", "")),
                )
                if mapping.reference_event_name and mapping.novel_event_name:
                    mappings.append(mapping)
            except (ValueError, TypeError) as exc:
                logger.debug("[backbone_mapper] Skipping malformed mapping item: %s", exc)
        return mappings

    # ------------------------------------------------------------------
    # Algorithmic fallback mapping
    # ------------------------------------------------------------------

    def _algorithmic_map(
        self,
        reference_events: list[dict[str, Any]],
        plot_data: dict[str, Any],
        mode: str,
    ) -> list[BackboneMapping]:
        """Map reference events to novel events using positional + keyword matching."""
        novel_events = self._extract_novel_events(plot_data)
        if not novel_events:
            logger.warning("[backbone_mapper] No novel events extracted from plot_data.")
            return []

        total_ref = len(reference_events)
        total_novel = len(novel_events)
        mappings: list[BackboneMapping] = []

        for ref_idx, ref_event in enumerate(reference_events):
            ref_name = ref_event.get("name", "")
            ref_content = ref_event.get("content", "")
            ref_archetype = ref_event.get("archetype", "")

            best_score = 0.0
            best_novel = None

            for novel_idx, novel_ev in enumerate(novel_events):
                score = self._similarity_score(
                    ref_name=ref_name,
                    ref_content=ref_content,
                    ref_archetype=ref_archetype,
                    ref_position=ref_idx / max(total_ref - 1, 1),
                    novel_name=novel_ev["name"],
                    novel_description=novel_ev.get("description", ""),
                    novel_position=novel_idx / max(total_novel - 1, 1),
                )
                if score > best_score:
                    best_score = score
                    best_novel = novel_ev

            # In loose mode, skip weak matches
            if mode == "loose" and best_score < 0.25:
                continue

            if best_novel is not None:
                confidence = min(1.0, best_score * 1.2)  # scale up slightly
                spiritual_core = self._infer_spiritual_core(ref_archetype, ref_content)
                mappings.append(
                    BackboneMapping(
                        reference_event_name=ref_name,
                        reference_event_content=ref_content,
                        novel_event_name=best_novel["name"],
                        novel_chapter=best_novel.get("chapter", 1),
                        mapping_confidence=round(confidence, 2),
                        spiritual_core=spiritual_core,
                    )
                )

        logger.info(
            "[backbone_mapper] Algorithmic mapping: %d/%d reference events mapped.",
            len(mappings),
            total_ref,
        )
        return mappings

    def _similarity_score(
        self,
        ref_name: str,
        ref_content: str,
        ref_archetype: str,
        ref_position: float,
        novel_name: str,
        novel_description: str,
        novel_position: float,
    ) -> float:
        """Compute a 0–1 similarity score between a reference event and a novel event.

        Combines three signals:
        - **Keyword overlap** (40%): shared characters/tokens between names+descriptions
        - **Archetype match** (30%): whether the novel event matches archetype keywords
        - **Positional proximity** (30%): how close they are in relative narrative position
        """
        # 1. Keyword overlap (40%)
        ref_tokens = set(ref_name + ref_content)
        novel_tokens = set(novel_name + novel_description)
        common = ref_tokens & novel_tokens - set("，。、的了在是和与不")
        union = ref_tokens | novel_tokens - set("，。、的了在是和与不")
        keyword_score = len(common) / max(len(union), 1)

        # 2. Archetype match (30%)
        archetype_score = 0.0
        if ref_archetype:
            archetype_keywords = _ARCHETYPE_KEYWORDS.get(ref_archetype, [])
            novel_text = novel_name + novel_description
            if any(kw in novel_text for kw in archetype_keywords):
                archetype_score = 1.0
            elif any(kw in novel_text for kw in ref_archetype):
                archetype_score = 0.5

        # 3. Positional proximity (30%)
        positional_score = 1.0 - abs(ref_position - novel_position)

        return 0.4 * keyword_score + 0.3 * archetype_score + 0.3 * positional_score

    # ------------------------------------------------------------------
    # Gap filling (strict mode)
    # ------------------------------------------------------------------

    def _fill_gaps(
        self,
        existing: list[BackboneMapping],
        reference_events: list[dict[str, Any]],
        plot_data: dict[str, Any],
    ) -> list[BackboneMapping]:
        """In strict mode, fill unmapped reference events with algorithmic fallback."""
        mapped_refs = {m.reference_event_name for m in existing}
        unmapped = [ev for ev in reference_events if ev.get("name", "") not in mapped_refs]

        if not unmapped:
            return existing

        logger.info(
            "[backbone_mapper] Strict mode: filling %d unmapped reference events.",
            len(unmapped),
        )
        fallback = self._algorithmic_map(unmapped, plot_data, mode="strict")

        # Reduce confidence for gap-filled mappings
        for m in fallback:
            m.mapping_confidence = round(
                min(m.mapping_confidence, self.fallback_confidence), 2
            )

        return list(existing) + fallback

    # ------------------------------------------------------------------
    # Event extraction helpers
    # ------------------------------------------------------------------

    def _extract_novel_events(self, plot_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract a flat list of events from plot_data for matching.

        Merges events from ``plot_arcs``, ``turning_points``, and
        ``backbone_mappings`` (if already present from a prior LLM pass).
        Each event dict has at minimum ``name``, ``description``, ``chapter``.
        """
        events: list[dict[str, Any]] = []

        # From plot_arcs
        for arc in plot_data.get("plot_arcs", []):
            events.append({
                "name": arc.get("name", ""),
                "description": arc.get("description", ""),
                "chapter": arc.get("start_chapter", 1),
            })

        # From turning_points
        for tp in plot_data.get("turning_points", []):
            events.append({
                "name": tp.get("description", ""),
                "description": tp.get("impact", ""),
                "chapter": tp.get("chapter", 1),
            })

        # From existing backbone_mappings (reuse if present)
        for bm in plot_data.get("backbone_mappings", []):
            events.append({
                "name": bm.get("novel_event", ""),
                "description": "",
                "chapter": bm.get("chapter", 1),
            })

        # Deduplicate by name
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for ev in events:
            key = ev["name"]
            if key and key not in seen:
                seen.add(key)
                unique.append(ev)

        # Sort by chapter
        unique.sort(key=lambda e: e.get("chapter", 0))
        return unique

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    def _format_reference_events(self, events: list[dict[str, Any]]) -> str:
        """Format reference events as numbered text for LLM prompt."""
        lines: list[str] = []
        for ev in events:
            order = ev.get("order", "?")
            name = ev.get("name", "")
            content = ev.get("content", "")
            archetype = ev.get("archetype", "")
            lines.append(f"{order}. {name}（{archetype}）: {content}")
        return "\n".join(lines)

    def _format_novel_events(self, plot_data: dict[str, Any]) -> str:
        """Format novel plot_data events as text for LLM prompt."""
        lines: list[str] = []

        # Synopsis
        synopsis = plot_data.get("synopsis", "")
        if synopsis:
            lines.append(f"故事梗概：{synopsis[:300]}")
            lines.append("")

        # Plot arcs
        for arc in plot_data.get("plot_arcs", []):
            lines.append(
                f"[第{arc.get('start_chapter', '?')}-{arc.get('end_chapter', '?')}章] "
                f"{arc.get('name', '')}: {arc.get('description', '')}"
            )

        # Turning points
        if plot_data.get("turning_points"):
            lines.append("")
            lines.append("关键转折点：")
            for tp in plot_data["turning_points"]:
                lines.append(
                    f"  第{tp.get('chapter', '?')}章: {tp.get('description', '')} "
                    f"→ {tp.get('impact', '')}"
                )

        # Characters (brief)
        chars = plot_data.get("main_characters", [])
        if chars:
            lines.append("")
            char_names = [c.get("name", "?") for c in chars[:6]]
            lines.append(f"主要角色：{'、'.join(char_names)}")

        return "\n".join(lines)

    def _infer_spiritual_core(self, archetype: str, content: str) -> str:
        """Infer a spiritual core string from archetype and content without LLM.

        Returns a short thematic description of the event's narrative function.
        """
        core_map: dict[str, str] = {
            "英雄诞生": "新力量的诞生打破旧平衡",
            "反抗权威": "个体意志对既有秩序的挑战",
            "惩罚与救赎": "傲慢受制后的蛰伏与觉醒",
            "任务开始": "使命召唤下的踏上征程",
            "伙伴加入": "孤独之路上的盟约凝聚",
            "考验与怀疑": "信任体系的动摇与重建",
            "欲望诱惑": "内心欲望对意志的试炼",
            "自我克制": "放下执念才能前行",
            "身份认同": "外在身份与内在自我的冲突",
            "终极挑战": "倾尽全力的生死一搏",
            "目标达成": "长途跋涉后的使命完成",
            "彻底蜕变": "从旧我到新我的质变飞升",
            "冤案与陷害": "无辜者被权力构陷的不公",
            "英雄初现": "隐藏实力的初次展露",
            "英雄堕落": "道德困境中的被迫抉择",
            "团队形成": "散沙凝聚为有组织的力量",
            "理想妥协": "理想主义与现实的痛苦和解",
            "英雄末路": "辉煌之后的悲壮收场",
            "关键战役": "改变格局的决定性冲突",
            "权力继承": "旧时代落幕新时代开启",
            "历史循环": "分合之势的历史必然",
            "导师出现": "智慧传承点燃希望",
            "命运转机": "绝境中出现的改变命运的契机",
            "重生与蜕变": "浴火重生后的全新开始",
            "复仇实施": "正义或执念驱动的清算",
            "救赎与和解": "放下仇恨选择宽恕",
            "实力提升": "量变引发质变的关键突破",
            "世界扩展": "视野从小格局跃升至大舞台",
        }
        return core_map.get(archetype, f"推动叙事发展的关键转折")

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json_array(text: str) -> list[dict[str, Any]] | None:
        """Extract the first JSON array from text, handling code fences."""
        # Strip markdown code fences
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        candidate = match.group(1).strip() if match else text.strip()

        # Try direct parse
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return data
            # Sometimes LLM wraps array in an object
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        return v
        except json.JSONDecodeError:
            pass

        # Fallback: find first [ ... ] balanced block
        start = candidate.find("[")
        if start == -1:
            return None

        depth = 0
        for i, ch in enumerate(candidate[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    block = candidate[start : i + 1]
                    try:
                        data = json.loads(block)
                        return data if isinstance(data, list) else None
                    except json.JSONDecodeError:
                        return None
        return None

    # ------------------------------------------------------------------
    # Convenience: load + map in one call
    # ------------------------------------------------------------------

    def map_from_file(
        self,
        backbone_path: str,
        work_name: str,
        plot_data: dict[str, Any],
        mode: str = "loose",
    ) -> list[BackboneMapping]:
        """Load reference events from file and map them to novel events.

        Convenience method that combines
        :meth:`BackboneValidator.load_reference_events` with :meth:`map`.

        Args:
            backbone_path: Path to ``classical_backbones.json``.
            work_name:     Key inside the JSON (e.g. "西游记").
            plot_data:     Novel outline from OutlineStage.
            mode:          ``"loose"`` or ``"strict"``.

        Returns:
            List of :class:`BackboneMapping` objects.
        """
        with open(backbone_path, "r", encoding="utf-8") as fh:
            kb: dict[str, Any] = json.load(fh)

        work = kb.get(work_name, {})
        reference_events = work.get("backbone_events", [])
        if not reference_events:
            logger.warning(
                "[backbone_mapper] No backbone_events for work=%r in %s",
                work_name,
                backbone_path,
            )
            return []

        return self.map(reference_events, plot_data, mode)
