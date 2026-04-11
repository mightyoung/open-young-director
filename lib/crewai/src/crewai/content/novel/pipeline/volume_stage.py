"""VolumeStage — divides the novel into volumes with structured outlines.

Reads: state.plot_data, state.world_data, state.config
Writes: state.volume_outlines
"""

from __future__ import annotations

import dataclasses
import json
import logging
from typing import Any

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Genre-specific defaults
# ---------------------------------------------------------------------------

_CHAPTERS_PER_VOLUME: dict[str, int] = {
    "xianxia": 30,
    "xuanhuan": 30,
    "wuxia": 30,
    "urban": 20,
    "romance": 20,
    "fantasy": 25,
    "historical": 25,
}
_DEFAULT_CHAPTERS_PER_VOLUME = 25

_SYSTEM_PROMPT = """\
你是一位资深的网络小说策划编辑，专注于分卷大纲设计。
你能根据整体情节规划，合理地将故事划分为多个完整的卷，
每卷都有清晰的主题、弧线、关键事件和角色焦点。
请严格按照要求的JSON格式输出，不要添加额外的解释文字。
"""


@dataclasses.dataclass
class VolumeStage(StageRunner):
    """Pipeline stage that divides the novel into volumes.

    For each volume the LLM is asked to generate a structured outline
    containing: title, theme, chapter range, key events, character focus,
    tension arc, and brief per-chapter descriptions.
    """

    name: str = "volume"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, state: PipelineState) -> PipelineState:
        """Compute volume outlines and return an updated PipelineState.

        Args:
            state: Current pipeline state (not mutated).

        Returns:
            New PipelineState with ``volume_outlines`` populated and
            ``current_stage`` set to ``"volume"``.
        """
        logger.info("[VolumeStage] Starting volume division")

        plot_data = state.plot_data
        world_data = state.world_data
        config = state.config

        total_chapters = self._resolve_total_chapters(plot_data, config)
        chapters_per_volume = self._resolve_chapters_per_volume(config)
        num_volumes = max(1, round(total_chapters / chapters_per_volume))

        logger.info(
            "[VolumeStage] total_chapters=%d, chapters_per_volume=%d, num_volumes=%d",
            total_chapters,
            chapters_per_volume,
            num_volumes,
        )

        character_archetypes: list = plot_data.get("character_archetypes", [])

        volume_outlines = self._generate_all_volumes(
            plot_data=plot_data,
            world_data=world_data,
            total_chapters=total_chapters,
            num_volumes=num_volumes,
            character_archetypes=character_archetypes,
        )

        new_state = dataclasses.replace(
            state,
            volume_outlines=volume_outlines,
            current_stage="volume",
        )
        logger.info("[VolumeStage] Generated %d volume outlines", len(volume_outlines))
        return new_state

    def validate_input(self, state: PipelineState) -> bool:
        """Require plot_data to be populated."""
        if not state.plot_data:
            logger.error("[VolumeStage] validate_input failed: plot_data is empty")
            return False
        return True

    # ------------------------------------------------------------------
    # Volume generation
    # ------------------------------------------------------------------

    def _generate_all_volumes(
        self,
        *,
        plot_data: dict,
        world_data: dict,
        total_chapters: int,
        num_volumes: int,
        character_archetypes: list | None = None,
    ) -> list[dict]:
        """Ask the LLM to generate outlines for all volumes at once."""
        user_prompt = self._build_prompt(
            plot_data=plot_data,
            world_data=world_data,
            total_chapters=total_chapters,
            num_volumes=num_volumes,
            character_archetypes=character_archetypes or [],
        )

        raw = self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8192,
            temperature=0.75,
        )

        volumes = self._parse_volume_response(raw, plot_data, total_chapters, num_volumes)

        # Propagate archetypes into every volume dict for downstream stages
        if character_archetypes:
            for vol in volumes:
                vol["character_archetypes"] = character_archetypes

        return volumes

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        *,
        plot_data: dict,
        world_data: dict,
        total_chapters: int,
        num_volumes: int,
        character_archetypes: list | None = None,
    ) -> str:
        world_summary = self._summarise_world(world_data)
        plot_summary = json.dumps(plot_data, ensure_ascii=False, default=str)
        if len(plot_summary) > 2000:
            plot_summary = plot_summary[:2000] + "...(截断)"

        # Compute chapter boundaries for each volume
        base = total_chapters // num_volumes
        remainder = total_chapters % num_volumes
        boundaries: list[tuple[int, int]] = []
        start = 1
        for i in range(num_volumes):
            end = start + base - 1 + (1 if i < remainder else 0)
            boundaries.append((start, end))
            start = end + 1

        boundaries_str = "\n".join(
            f"  第{i + 1}卷: 第{s}章 ~ 第{e}章 (共{e - s + 1}章)"
            for i, (s, e) in enumerate(boundaries)
        )

        archetypes_section = ""
        if character_archetypes:
            archetypes_str = "、".join(str(a) for a in character_archetypes)
            archetypes_section = f"\n## 角色原型参考\n角色原型参考：{archetypes_str}\n"

        return f"""\
请为以下小说生成详细的分卷大纲。

## 世界观摘要
{world_summary}

## 整体情节规划
{plot_summary}{archetypes_section}

## 分卷参数
- 总章节数: {total_chapters}
- 分卷数量: {num_volumes}
- 建议章节分配:
{boundaries_str}

## 任务要求
请为每一卷生成包含以下信息的详细大纲：
1. **volume_num**: 卷号（从1开始）
2. **title**: 卷标题（富有诗意，体现本卷核心主题）
3. **theme**: 本卷核心主题（50字以内）
4. **start_chapter**: 起始章节号
5. **end_chapter**: 结束章节号
6. **key_events**: 本卷3~6个关键情节事件列表（每条50字以内）
7. **character_focus**: 本卷重点刻画的角色列表（1~4位）
8. **tension_arc**: 本卷张力走势描述（opening/rising/climax/resolution四阶段，各15字以内）
9. **chapters_summary**: 本卷每个章节的简要描述列表（每条20~40字，按章节顺序）

## 输出格式
严格按照以下JSON数组格式输出，不要添加任何额外文字：
[
  {{
    "volume_num": 1,
    "title": "卷标题",
    "theme": "本卷核心主题",
    "start_chapter": 1,
    "end_chapter": 30,
    "key_events": ["事件1", "事件2", "事件3"],
    "character_focus": ["主角", "反派"],
    "tension_arc": {{
      "opening": "平静中暗流涌动",
      "rising": "矛盾逐渐激化",
      "climax": "生死决战",
      "resolution": "暂时的平衡"
    }},
    "chapters_summary": [
      "第1章：主角初登场，展示特殊能力",
      "第2章：遭遇第一个挑战",
      "..."
    ]
  }}
]

请确保：
- 各卷章节范围连续不重叠
- 每卷的chapters_summary条数与(end_chapter - start_chapter + 1)一致
- 情节弧线完整，高潮分布合理
- 共输出 {num_volumes} 卷
"""

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    def _parse_volume_response(
        self,
        raw: str,
        plot_data: dict,
        total_chapters: int,
        num_volumes: int,
    ) -> list[dict]:
        """Parse LLM output into a list of volume outline dicts.

        Falls back to a minimal skeleton if parsing fails.
        """
        try:
            data = self._parse_json_array(raw)
            if isinstance(data, list) and data:
                validated = [self._normalise_volume(v) for v in data if isinstance(v, dict)]
                if validated:
                    return validated
        except Exception as exc:
            logger.warning("[VolumeStage] JSON parse failed (%s), using fallback", exc)

        return self._fallback_volumes(plot_data, total_chapters, num_volumes)

    def _parse_json_array(self, text: str) -> Any:
        """Extract a JSON array from text that may have markdown fences."""
        import re

        # Try markdown fence first
        fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if fence_match:
            return json.loads(fence_match.group(1).strip())

        # Try bare JSON array
        array_match = re.search(r"\[[\s\S]*\]", text)
        if array_match:
            return json.loads(array_match.group())

        return json.loads(text.strip())

    def _normalise_volume(self, v: dict) -> dict:
        """Ensure required keys exist with sensible defaults."""
        return {
            "volume_num": int(v.get("volume_num", 1)),
            "title": str(v.get("title", f"第{v.get('volume_num', 1)}卷")),
            "theme": str(v.get("theme", "")),
            "start_chapter": int(v.get("start_chapter", 1)),
            "end_chapter": int(v.get("end_chapter", 1)),
            "key_events": list(v.get("key_events", [])),
            "character_focus": list(v.get("character_focus", [])),
            "tension_arc": dict(v.get("tension_arc", {})),
            "chapters_summary": list(v.get("chapters_summary", [])),
        }

    def _fallback_volumes(
        self,
        plot_data: dict,
        total_chapters: int,
        num_volumes: int,
    ) -> list[dict]:
        """Build a minimal volume list when LLM output cannot be parsed."""
        logger.warning("[VolumeStage] Generating fallback volume skeletons")
        base = total_chapters // num_volumes
        remainder = total_chapters % num_volumes
        volumes: list[dict] = []
        start = 1
        for i in range(num_volumes):
            end = start + base - 1 + (1 if i < remainder else 0)
            chapters_summary = [
                f"第{ch}章: 待规划"
                for ch in range(start, end + 1)
            ]
            volumes.append({
                "volume_num": i + 1,
                "title": f"第{i + 1}卷",
                "theme": "",
                "start_chapter": start,
                "end_chapter": end,
                "key_events": [],
                "character_focus": [],
                "tension_arc": {},
                "chapters_summary": chapters_summary,
            })
            start = end + 1
        return volumes

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def _resolve_total_chapters(self, plot_data: dict, config: dict) -> int:
        """Determine total chapter count from config or plot_data."""
        # Explicit config override takes priority
        if config.get("total_chapters"):
            return int(config["total_chapters"])

        # Pull from plot_data if the author specified it there
        if plot_data.get("total_chapters"):
            return int(plot_data["total_chapters"])

        # Count from volumes list if already partitioned
        volumes = plot_data.get("volumes", [])
        if volumes:
            total = sum(
                v.get("chapter_count", 0) or (
                    int(v.get("end_chapter", 0)) - int(v.get("start_chapter", 1)) + 1
                )
                for v in volumes
            )
            if total > 0:
                return total

        # Derive from word target and chapter length
        word_target = config.get("word_target") or plot_data.get("word_target", 0)
        style = (config.get("style") or config.get("genre", "urban")).lower()
        words_per_chapter = 6000 if style in ("xianxia", "xuanhuan", "wuxia") else 4000
        if word_target:
            return max(1, int(word_target) // words_per_chapter)

        return 100  # sensible default

    def _resolve_chapters_per_volume(self, config: dict) -> int:
        """Look up the chapters-per-volume setting for the given style/genre."""
        if config.get("chapters_per_volume"):
            return int(config["chapters_per_volume"])
        style = (config.get("style") or config.get("genre", "urban")).lower()
        return _CHAPTERS_PER_VOLUME.get(style, _DEFAULT_CHAPTERS_PER_VOLUME)

    # ------------------------------------------------------------------
    # World summary helper
    # ------------------------------------------------------------------

    def _summarise_world(self, world_data: dict) -> str:
        """Return a concise string representation of world_data."""
        if not world_data:
            return "（无世界观数据）"
        text = json.dumps(world_data, ensure_ascii=False, default=str)
        if len(text) > 800:
            text = text[:800] + "...(截断)"
        return text
