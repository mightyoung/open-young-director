"""SummaryStage — generates detailed chapter summaries from volume outlines.

Reads: state.volume_outlines (from VolumeStage)
Writes: state.chapter_summaries
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一位专业的小说章节规划师，擅长在正文写作前设计完整、可执行的章节概要。
你能根据分卷大纲，为每个章节规划核心目的、关键事件、角色出场、张力节奏和悬念钩子。
请严格按照要求的JSON格式输出，不要添加额外的解释文字。
"""

# Default tension level when LLM does not supply a valid integer
_DEFAULT_TENSION = 5


@dataclasses.dataclass
class SummaryStage(StageRunner):
    """Pipeline stage that generates detailed per-chapter summaries.

    Processes volumes sequentially; within each volume a single LLM call
    generates all chapter summaries for that volume in one batch.
    """

    name: str = "summary"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, state: PipelineState) -> PipelineState:
        """Generate chapter summaries for every volume and return updated state.

        Args:
            state: Current pipeline state (not mutated).

        Returns:
            New PipelineState with ``chapter_summaries`` populated and
            ``current_stage`` set to ``"summary"``.
        """
        logger.info("[SummaryStage] Starting chapter summary generation")

        all_summaries: list[dict] = []

        for volume in state.volume_outlines:
            volume_num = int(volume.get("volume_num", 1))
            logger.info("[SummaryStage] Generating summaries for volume %d", volume_num)

            summaries = self._generate_volume_summaries(volume, state.config)
            all_summaries.extend(summaries)

            logger.info(
                "[SummaryStage] Volume %d: generated %d chapter summaries",
                volume_num,
                len(summaries),
            )

        # Sort globally by (volume_num, chapter_num)
        all_summaries.sort(key=lambda s: (s.get("volume_num", 0), s.get("chapter_num", 0)))

        new_state = dataclasses.replace(
            state,
            chapter_summaries=all_summaries,
            current_stage="summary",
        )
        logger.info(
            "[SummaryStage] Total chapter summaries generated: %d", len(all_summaries)
        )
        return new_state

    def validate_input(self, state: PipelineState) -> bool:
        """Require at least one volume outline before generating summaries."""
        if not state.volume_outlines:
            logger.error("[SummaryStage] validate_input failed: volume_outlines is empty")
            return False
        return True

    # ------------------------------------------------------------------
    # Per-volume generation
    # ------------------------------------------------------------------

    def _generate_volume_summaries(
        self,
        volume: dict,
        config: dict,
    ) -> list[dict]:
        """Ask the LLM to generate all chapter summaries for one volume.

        Returns a list of chapter summary dicts sorted by chapter_num.
        """
        volume_num = int(volume.get("volume_num", 1))
        user_prompt = self._build_prompt(volume, config)

        raw = self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8192,
            temperature=0.7,
        )

        summaries = self._parse_summary_response(raw, volume)
        summaries.sort(key=lambda s: s.get("chapter_num", 0))
        return summaries

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, volume: dict, config: dict) -> str:
        volume_num = int(volume.get("volume_num", 1))
        start_ch = int(volume.get("start_chapter", 1))
        end_ch = int(volume.get("end_chapter", start_ch))
        chapter_count = end_ch - start_ch + 1

        volume_str = json.dumps(volume, ensure_ascii=False, default=str)
        if len(volume_str) > 2000:
            volume_str = volume_str[:2000] + "...(截断)"

        style = (config.get("style") or config.get("genre", "urban")).lower()
        word_target_per_chapter = 6000 if style in ("xianxia", "xuanhuan", "wuxia") else 4000

        pov_character = config.get("protagonist", "主角")

        return f"""\
请为第{volume_num}卷的所有章节生成详细概要。

## 本卷大纲
{volume_str}

## 生成要求
- 本卷共 {chapter_count} 章 (第{start_ch}章 ~ 第{end_ch}章)
- 每章目标字数: {word_target_per_chapter}字
- 主视角角色: {pov_character}

## 每章概要需包含以下字段
1. **chapter_num**: 本章全局章节编号（从{start_ch}开始）
2. **volume_num**: 卷号 = {volume_num}
3. **title**: 章节标题（10~20字，富有吸引力）
4. **main_events**: 本章2~4个主要事件列表（每条30~60字）
5. **character_appearances**: 本章出场角色名称列表
6. **tension_level**: 本章张力等级（整数1~10，1=平静，10=最高潮）
7. **pov_character**: 本章视角角色名称
8. **ending_hook**: 本章结尾悬念钩子（20~50字，让读者迫不及待读下一章）

## 输出格式
严格按照JSON数组格式输出（共 {chapter_count} 个对象），不要添加任何额外文字：
[
  {{
    "chapter_num": {start_ch},
    "volume_num": {volume_num},
    "title": "章节标题",
    "main_events": ["事件1", "事件2", "事件3"],
    "character_appearances": ["主角", "配角A"],
    "tension_level": 7,
    "pov_character": "{pov_character}",
    "ending_hook": "结尾悬念描述"
  }},
  ...
]

注意事项：
- chapter_num 必须从 {start_ch} 连续编号到 {end_ch}
- 章节间要有逻辑连贯性，前章悬念在后章得到回应
- tension_level 要呈现合理起伏，高潮集中在卷末
- 共输出 {chapter_count} 个章节概要
"""

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_summary_response(self, raw: str, volume: dict) -> list[dict]:
        """Parse LLM output into a list of chapter summary dicts.

        Falls back to minimal skeletons derived from volume.chapters_summary
        when the LLM output is malformed.
        """
        try:
            data = self._parse_json_array(raw)
            if isinstance(data, list) and data:
                validated = [
                    self._normalise_summary(item, volume)
                    for item in data
                    if isinstance(item, dict)
                ]
                if validated:
                    return validated
        except Exception as exc:
            logger.warning("[SummaryStage] JSON parse failed (%s), using fallback", exc)

        return self._fallback_summaries(volume)

    def _parse_json_array(self, text: str) -> list:
        """Extract a JSON array from text that may contain markdown fences."""
        # Try markdown fence first
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1).strip())

        # Try bare JSON array
        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            return json.loads(array_match.group())

        return json.loads(text.strip())

    def _normalise_summary(self, item: dict, volume: dict) -> dict:
        """Coerce a parsed dict into the canonical chapter summary shape."""
        volume_num = int(volume.get("volume_num", 1))

        tension_raw = item.get("tension_level", _DEFAULT_TENSION)
        try:
            tension = max(1, min(10, int(tension_raw)))
        except (TypeError, ValueError):
            tension = _DEFAULT_TENSION

        return {
            "chapter_num": int(item.get("chapter_num", 0)),
            "volume_num": int(item.get("volume_num", volume_num)),
            "title": str(item.get("title", f"第{item.get('chapter_num', '?')}章")),
            "main_events": list(item.get("main_events", [])),
            "character_appearances": list(item.get("character_appearances", [])),
            "tension_level": tension,
            "pov_character": str(item.get("pov_character", "主角")),
            "ending_hook": str(item.get("ending_hook", "")),
            "character_archetypes": list(volume.get("character_archetypes", [])),
        }

    def _fallback_summaries(self, volume: dict) -> list[dict]:
        """Generate minimal chapter summary skeletons from volume data."""
        logger.warning(
            "[SummaryStage] Generating fallback summaries for volume %d",
            volume.get("volume_num", "?"),
        )
        volume_num = int(volume.get("volume_num", 1))
        start_ch = int(volume.get("start_chapter", 1))
        end_ch = int(volume.get("end_chapter", start_ch))
        chapters_summary: list[str] = volume.get("chapters_summary", [])

        archetypes = list(volume.get("character_archetypes", []))
        summaries: list[dict] = []
        for i, ch_num in enumerate(range(start_ch, end_ch + 1)):
            brief = chapters_summary[i] if i < len(chapters_summary) else f"第{ch_num}章: 待规划"
            summaries.append({
                "chapter_num": ch_num,
                "volume_num": volume_num,
                "title": brief[:20] if brief else f"第{ch_num}章",
                "main_events": [brief] if brief else [],
                "character_appearances": [],
                "tension_level": _DEFAULT_TENSION,
                "pov_character": "主角",
                "ending_hook": "",
                "character_archetypes": archetypes,
            })
        return summaries
