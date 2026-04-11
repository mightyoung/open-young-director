"""BibleUpdater — per-chapter Production Bible updater.

After each chapter is written, this class:
  1. Calls the LLM (single call, temperature=0.3) to extract world-state changes
     from the chapter text.
  2. Applies those changes immutably, returning a new ProductionBible.

No agent/crew imports — pure Python + DeepSeekClient.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from dataclasses import dataclass, field, replace

from crewai.content.novel.production_bible.bible_types import (
    ForeshadowingEntry,
    LocationState,
    PacingState,
    ProductionBible,
    RelationshipState,
    TimelineEvent,
)
from crewai.llm.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
你是小说连续性编辑。分析以下章节，提取世界状态变化。

请严格以 JSON 格式输出，不要有任何额外文字，格式如下：
{
  "location_changes": [
    {
      "character_name": "角色名",
      "place_name": "地点名",
      "status": "present|traveling|hidden"
    }
  ],
  "relationship_changes": [
    {
      "character_name": "角色名",
      "target_name": "目标角色名",
      "emotional_value_delta": 10,
      "recent_interaction_summary": "简短描述"
    }
  ],
  "foreshadowing_updates": [
    {
      "id": "现有伏笔ID（若为新伏笔则留空）",
      "action": "harvest|plant",
      "description": "伏笔内容描述",
      "payoff_chapter": 0
    }
  ],
  "new_events": [
    {
      "description": "事件描述",
      "involved_entities": ["实体1", "实体2"],
      "impact": "影响说明"
    }
  ],
  "tension_level": 5
}

规则：
- tension_level 为 1-10 的整数（1=极度平静，10=白热化冲突）
- emotional_value_delta 为正数表示关系改善，负数表示关系恶化，范围 -20 到 +20
- 若某字段无内容，输出空列表 []
- 只提取本章节真正发生的变化，不要推测
"""

_USER_TEMPLATE = """\
## 第 {chapter_num} 章内容

{chapter_content}

{summary_hint}
"""


# ---------------------------------------------------------------------------
# BibleUpdater
# ---------------------------------------------------------------------------


@dataclass
class BibleUpdater:
    """Updates the Production Bible after each chapter is written.

    Attributes:
        llm: Shared DeepSeekClient used for the extraction call.
        max_content_chars: Characters of chapter content sent to the LLM.
            Long chapters are truncated to keep the prompt within token limits.
        recent_tension_window: How many chapters of tension history to retain
            in PacingState.recent_tension_levels.
    """

    llm: DeepSeekClient
    max_content_chars: int = 6000
    recent_tension_window: int = 5

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_after_chapter(
        self,
        bible: ProductionBible,
        chapter_content: str,
        chapter_num: int,
        chapter_summary: dict | None = None,
    ) -> ProductionBible:
        """Extract updates from chapter content and apply to the bible.

        The original *bible* is never mutated — a new ProductionBible is
        returned with all updates applied.

        Updates applied:
          1. Character GPS (location changes)
          2. Relationship emotional values (conflicts, alliances)
          3. Foreshadowing status (planted / harvested)
          4. Timeline events
          5. Pacing state (tension level)

        Args:
            bible: Current Production Bible (not mutated).
            chapter_content: Full text of the chapter just written.
            chapter_num: The absolute chapter number (1-based).
            chapter_summary: Optional pre-computed summary dict with keys such
                as ``title``, ``summary``, ``key_events``.  When supplied, a
                condensed hint is appended to the LLM prompt to improve
                extraction accuracy.

        Returns:
            A new ProductionBible with all extracted updates applied.
        """
        extraction = self._extract_updates(chapter_content, chapter_num, chapter_summary)
        if extraction is None:
            return bible

        return self._apply_all(bible, extraction, chapter_num)

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    def _extract_updates(
        self,
        chapter_content: str,
        chapter_num: int,
        chapter_summary: dict | None,
    ) -> dict | None:
        """Call LLM to extract world-state changes.  Returns parsed dict or None."""
        truncated = chapter_content[: self.max_content_chars]
        if len(chapter_content) > self.max_content_chars:
            truncated += "\n[...内容已截断...]"

        summary_hint = ""
        if chapter_summary:
            title = chapter_summary.get("title", "")
            summary_text = chapter_summary.get("summary", "")
            if title or summary_text:
                summary_hint = f"## 章节摘要参考\n标题：{title}\n摘要：{summary_text}"

        user_message = _USER_TEMPLATE.format(
            chapter_num=chapter_num,
            chapter_content=truncated,
            summary_hint=summary_hint,
        )

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            raw = self.llm.chat(messages, max_tokens=1500, temperature=0.3)
        except Exception as exc:
            logger.warning(
                "BibleUpdater: LLM call failed for chapter %d (%s) — bible unchanged.",
                chapter_num,
                exc,
            )
            return None

        return self._parse_json(raw, chapter_num)

    def _parse_json(self, raw: str, chapter_num: int) -> dict | None:
        """Extract and parse the JSON block from the LLM response."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        # Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1:
            logger.warning(
                "BibleUpdater: No JSON object found in LLM response for chapter %d.",
                chapter_num,
            )
            return None

        json_str = cleaned[start : end + 1]
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.warning(
                "BibleUpdater: JSON parse error for chapter %d (%s) — bible unchanged.",
                chapter_num,
                exc,
            )
            return None

        if not isinstance(data, dict):
            logger.warning(
                "BibleUpdater: Unexpected JSON type %s for chapter %d.",
                type(data).__name__,
                chapter_num,
            )
            return None

        return data

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def _apply_all(
        self,
        bible: ProductionBible,
        extraction: dict,
        chapter_num: int,
    ) -> ProductionBible:
        """Apply all extracted updates, returning a new ProductionBible."""
        new_characters = copy.deepcopy(bible.characters)
        new_foreshadowing = copy.deepcopy(bible.foreshadowing_registry)
        new_timeline = list(bible.timeline)

        new_characters = self._update_gps_on_characters(
            new_characters,
            extraction.get("location_changes", []),
            chapter_num,
        )
        new_gps = self._build_new_gps(
            bible.character_gps,
            extraction.get("location_changes", []),
            chapter_num,
        )
        new_characters = self._update_relationships(
            new_characters,
            extraction.get("relationship_changes", []),
        )
        new_foreshadowing = self._update_foreshadowing(
            new_foreshadowing,
            extraction.get("foreshadowing_updates", []),
            chapter_num,
        )
        new_timeline = self._update_timeline(
            new_timeline,
            extraction.get("new_events", []),
            chapter_num,
        )
        new_pacing = self._update_pacing(
            bible.pacing_state,
            extraction.get("tension_level"),
        )

        return replace(
            bible,
            characters=new_characters,
            character_gps=new_gps,
            foreshadowing_registry=new_foreshadowing,
            timeline=new_timeline,
            pacing_state=new_pacing,
        )

    # ------------------------------------------------------------------
    # Individual update helpers (all return new objects, never mutate)
    # ------------------------------------------------------------------

    def _build_new_gps(
        self,
        current_gps: dict[str, LocationState],
        location_changes: list[dict],
        chapter_num: int,
    ) -> dict[str, LocationState]:
        """Return a new character_gps dict with location changes applied."""
        if not location_changes:
            return current_gps

        new_gps = dict(current_gps)
        for change in location_changes:
            if not isinstance(change, dict):
                continue
            char_name = str(change.get("character_name", "")).strip()
            place_name = str(change.get("place_name", "")).strip()
            if not char_name or not place_name:
                continue
            status = str(change.get("status", "present")).strip()
            if status not in ("present", "traveling", "hidden"):
                status = "present"

            existing = current_gps.get(char_name)
            if existing is not None:
                new_gps[char_name] = replace(
                    existing,
                    place_name=place_name,
                    arrival_chapter=chapter_num,
                    status=status,
                )
            else:
                new_gps[char_name] = LocationState(
                    place_name=place_name,
                    arrival_chapter=chapter_num,
                    status=status,
                )

        return new_gps

    def _update_gps_on_characters(
        self,
        characters: dict,
        location_changes: list[dict],
        chapter_num: int,
    ) -> dict:
        """Characters dict is passed through unchanged here; GPS is separate."""
        # character_gps is a top-level field on ProductionBible; nothing to do
        # on the CharacterProfile itself for location.
        return characters

    def _update_relationships(
        self,
        characters: dict,
        relationship_changes: list[dict],
    ) -> dict:
        """Return a new characters dict with relationship emotional values adjusted."""
        if not relationship_changes:
            return characters

        new_characters = dict(characters)
        for change in relationship_changes:
            if not isinstance(change, dict):
                continue
            char_name = str(change.get("character_name", "")).strip()
            target_name = str(change.get("target_name", "")).strip()
            if not char_name or not target_name:
                continue

            char = new_characters.get(char_name)
            if char is None:
                logger.debug(
                    "BibleUpdater: relationship change references unknown character %r — skipping.",
                    char_name,
                )
                continue

            delta = change.get("emotional_value_delta", 0)
            try:
                delta = int(delta)
            except (TypeError, ValueError):
                delta = 0
            delta = max(-20, min(20, delta))

            summary = str(change.get("recent_interaction_summary", "")).strip()

            existing_rel = char.relationships.get(target_name)
            if existing_rel is not None:
                new_value = max(-100, min(100, existing_rel.emotional_value + delta))
                updated_rel = replace(
                    existing_rel,
                    emotional_value=new_value,
                    recent_interaction_summary=summary or existing_rel.recent_interaction_summary,
                )
            else:
                new_value = max(-100, min(100, delta))
                updated_rel = RelationshipState(
                    target_name=target_name,
                    emotional_value=new_value,
                    bond_type="unknown",
                    recent_interaction_summary=summary,
                )

            new_relationships = {**char.relationships, target_name: updated_rel}
            # Replace the character with updated relationships (dataclass copy)
            new_char = replace(char, relationships=new_relationships)
            new_characters[char_name] = new_char

        return new_characters

    def _update_foreshadowing(
        self,
        registry: dict[str, ForeshadowingEntry],
        foreshadowing_updates: list[dict],
        chapter_num: int,
    ) -> dict[str, ForeshadowingEntry]:
        """Return a new foreshadowing registry with updates applied."""
        if not foreshadowing_updates:
            return registry

        new_registry = dict(registry)
        for update in foreshadowing_updates:
            if not isinstance(update, dict):
                continue
            action = str(update.get("action", "")).strip().lower()
            entry_id = str(update.get("id", "")).strip()
            description = str(update.get("description", "")).strip()

            if action == "harvest":
                if entry_id and entry_id in new_registry:
                    existing = new_registry[entry_id]
                    new_registry[entry_id] = replace(
                        existing,
                        is_active=False,
                        was_successful=True,
                        payoff_chapter=chapter_num,
                        payoff_description=description or existing.payoff_description,
                    )
                else:
                    logger.debug(
                        "BibleUpdater: harvest action references unknown foreshadowing id %r — skipping.",
                        entry_id,
                    )

            elif action == "plant":
                payoff_ch = update.get("payoff_chapter", 0)
                try:
                    payoff_ch = int(payoff_ch)
                except (TypeError, ValueError):
                    payoff_ch = 0

                # Generate a unique id if not provided
                new_id = entry_id if entry_id and entry_id not in new_registry else (
                    f"fs_ch{chapter_num}_{len(new_registry)}"
                )
                new_registry[new_id] = ForeshadowingEntry(
                    id=new_id,
                    setup_chapter=chapter_num,
                    setup_description=description,
                    payoff_chapter=payoff_ch,
                    payoff_description="",
                    is_active=True,
                    was_successful=False,
                )
            else:
                logger.debug(
                    "BibleUpdater: unknown foreshadowing action %r — skipping.",
                    action,
                )

        return new_registry

    def _update_timeline(
        self,
        timeline: list[TimelineEvent],
        new_events: list[dict],
        chapter_num: int,
    ) -> list[TimelineEvent]:
        """Return a new timeline list with appended events."""
        if not new_events:
            return timeline

        appended = list(timeline)
        for i, event_data in enumerate(new_events):
            if not isinstance(event_data, dict):
                continue
            description = str(event_data.get("description", "")).strip()
            if not description:
                continue

            involved = event_data.get("involved_entities", [])
            if not isinstance(involved, list):
                involved = []
            involved = [str(e) for e in involved if e]

            impact = str(event_data.get("impact", "")).strip()
            event_id = f"ch{chapter_num}_event{i}"

            appended.append(
                TimelineEvent(
                    id=event_id,
                    chapter=chapter_num,
                    volume=0,  # volume context not available here; caller may patch
                    description=description,
                    involved_entities=involved,
                    impact=impact,
                )
            )

        return appended

    def _update_pacing(
        self,
        pacing: PacingState,
        tension_level: int | float | None,
    ) -> PacingState:
        """Return a new PacingState with the latest tension level incorporated."""
        if tension_level is None:
            return pacing

        try:
            level = int(tension_level)
        except (TypeError, ValueError):
            return pacing

        level = max(1, min(10, level))

        # Keep only the most recent N entries
        updated_levels = list(pacing.recent_tension_levels)[-( self.recent_tension_window - 1):] + [level]

        # Recalculate fatigue: high tension accumulates; relief dissipates slowly
        avg_tension = sum(updated_levels) / max(1, len(updated_levels))
        fatigue_delta = (avg_tension - 5.0) / 50.0  # +0.1 per chapter at max tension
        new_fatigue = max(0.0, min(1.0, pacing.accumulated_fatigue + fatigue_delta))

        # Recommend next tone based on current fatigue and latest tension
        if new_fatigue > 0.7 or level >= 8:
            next_tone = "breather"
        elif level <= 3:
            next_tone = "buildup"
        else:
            next_tone = "balanced"

        return replace(
            pacing,
            recent_tension_levels=updated_levels,
            accumulated_fatigue=new_fatigue,
            next_recommended_tone=next_tone,
        )
