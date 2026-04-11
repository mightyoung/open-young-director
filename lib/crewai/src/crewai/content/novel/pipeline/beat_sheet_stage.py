"""BeatSheetStage — Save the Cat 15-beat story structure generator.

Reads:  state.plot_data (required), state.treatment (optional)
Writes: state.beat_sheet — list of 15 beat dicts
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
from typing import Any

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Beat definition — Save the Cat adapted for Chinese novel
# ---------------------------------------------------------------------------

_BEAT_NAMES: tuple[tuple[str, str], ...] = (
    ("开场画面",    "Opening Image"),
    ("主题呈现",    "Theme Stated"),
    ("世界建立",    "Set-Up"),
    ("催化事件",    "Catalyst"),
    ("内心挣扎",    "Debate"),
    ("进入第二幕",  "Break Into Two"),
    ("副线故事",    "B Story"),
    ("承诺兑现",    "Fun and Games"),
    ("中点转折",    "Midpoint"),
    ("危机逼近",    "Bad Guys Close In"),
    ("至暗时刻",    "All Is Lost"),
    ("灵魂黑夜",    "Dark Night of the Soul"),
    ("进入第三幕",  "Break Into Three"),
    ("最终对决",    "Finale"),
    ("终幕画面",    "Final Image"),
)

_SYSTEM_PROMPT = """\
你是一位精通故事结构的网络小说策划专家，深谙"救猫咪"（Save the Cat）故事节拍理论。
你的任务是根据给定的情节规划，为小说设计完整的15个故事节拍。
每个节拍需要明确标注：名称、功能说明、关键事件、预估章节范围、情感基调。
请严格按照要求的JSON数组格式输出，不要添加任何额外文字。
"""

_USER_PROMPT_TEMPLATE = """\
请根据以下小说情节规划，按照"救猫咪"15节拍框架，生成完整的故事节拍表。

## 情节规划
{plot_summary}

{treatment_section}## 节拍框架说明
节拍顺序与中英文名称对照：
{beat_list}

## 输出要求
请输出一个JSON数组，每个元素对应一个节拍，包含以下字段：
- beat_index: 节拍编号（1-15）
- name_zh: 中文节拍名称
- name_en: 英文节拍名称
- description: 本节拍在本故事中的功能说明（50字以内）
- key_event: 本节拍的核心事件（80字以内）
- chapter_range_estimate: 预估章节范围，如 "第1-3章" 或 "第25章左右"
- emotional_tone: 情感基调（20字以内，如"充满希望"、"压抑绝望"等）

严格按照以下JSON数组格式输出：
[
  {{
    "beat_index": 1,
    "name_zh": "开场画面",
    "name_en": "Opening Image",
    "description": "...",
    "key_event": "...",
    "chapter_range_estimate": "第1章",
    "emotional_tone": "..."
  }},
  ...
]

请确保输出恰好15个节拍，顺序与上述框架一致。
"""


@dataclasses.dataclass
class BeatSheetStage(StageRunner):
    """Pipeline stage that generates a 15-beat story structure.

    Uses Save the Cat framework adapted for Chinese web novels.
    This is an optional stage — it enriches ``state.beat_sheet`` but does
    NOT block subsequent stages if skipped.
    """

    name: str = "beat_sheet"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def validate_input(self, state: PipelineState) -> bool:
        """Require non-empty plot_data before running."""
        if not state.plot_data:
            logger.error("[%s] validate_input failed: state.plot_data is empty", self.name)
            return False
        return True

    def run(self, state: PipelineState) -> PipelineState:
        """Generate the beat sheet and return an updated PipelineState.

        Args:
            state: Current pipeline state (not mutated — uses dataclasses.replace).

        Returns:
            New PipelineState with ``beat_sheet`` populated and
            ``current_stage`` set to ``"beat_sheet"``.
        """
        if not self.validate_input(state):
            raise ValueError(
                f"[{self.name}] Input validation failed: plot_data must be non-empty"
            )

        logger.info("[%s] Generating 15-beat story structure …", self.name)

        user_prompt = self._build_prompt(state.plot_data, getattr(state, "treatment", ""))
        raw = self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=4096,
            temperature=0.7,
        )

        beats = self._parse_beats(raw)
        logger.info("[%s] Generated %d beats", self.name, len(beats))

        return dataclasses.replace(state, beat_sheet=beats, current_stage="beat_sheet")

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(self, plot_data: dict, treatment: str) -> str:
        plot_summary = json.dumps(plot_data, ensure_ascii=False, default=str)
        if len(plot_summary) > 2000:
            plot_summary = plot_summary[:2000] + "...(截断)"

        treatment_section = ""
        if treatment and treatment.strip():
            t = treatment.strip()
            if len(t) > 500:
                t = t[:500] + "...(截断)"
            treatment_section = f"## 故事梗概（Treatment）\n{t}\n\n"

        beat_list = "\n".join(
            f"  {i + 1:02d}. {zh}（{en}）"
            for i, (zh, en) in enumerate(_BEAT_NAMES)
        )

        return _USER_PROMPT_TEMPLATE.format(
            plot_summary=plot_summary,
            treatment_section=treatment_section,
            beat_list=beat_list,
        )

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_beats(self, raw: str) -> list[dict[str, Any]]:
        """Extract and validate beat list from LLM response."""
        try:
            data = self._parse_json_array(raw)
            if isinstance(data, list) and data:
                return [self._normalise_beat(b, i + 1) for i, b in enumerate(data) if isinstance(b, dict)]
        except Exception as exc:
            logger.warning("[%s] JSON parse failed (%s); using fallback beats", self.name, exc)

        return self._fallback_beats()

    def _parse_json_array(self, text: str) -> Any:
        """Extract a JSON array from text that may have markdown fences."""
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1).strip())
        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            return json.loads(array_match.group())
        return json.loads(text.strip())

    def _normalise_beat(self, b: dict, fallback_index: int) -> dict[str, Any]:
        """Ensure required keys exist with sensible defaults."""
        idx = int(b.get("beat_index", fallback_index))
        safe_idx = max(1, min(idx, len(_BEAT_NAMES))) - 1
        zh_default, en_default = _BEAT_NAMES[safe_idx]
        return {
            "beat_index": idx,
            "name_zh": str(b.get("name_zh", zh_default)),
            "name_en": str(b.get("name_en", en_default)),
            "description": str(b.get("description", "")),
            "key_event": str(b.get("key_event", "")),
            "chapter_range_estimate": str(b.get("chapter_range_estimate", "")),
            "emotional_tone": str(b.get("emotional_tone", "")),
        }

    def _fallback_beats(self) -> list[dict[str, Any]]:
        """Return skeleton beats when LLM output cannot be parsed."""
        logger.warning("[%s] Generating fallback beat skeletons", self.name)
        return [
            {
                "beat_index": i + 1,
                "name_zh": zh,
                "name_en": en,
                "description": "",
                "key_event": "",
                "chapter_range_estimate": "",
                "emotional_tone": "",
            }
            for i, (zh, en) in enumerate(_BEAT_NAMES)
        ]
