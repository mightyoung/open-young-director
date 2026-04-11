"""OutlineStage: plot outline pipeline stage.

Pure Python, no CrewAI dependency.  Reads ``state.world_data`` (produced by
WorldStage) and populates ``state.plot_data`` with a structured outline dict.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Required keys in the plot_data output.
_REQUIRED_KEYS = (
    "title",
    "synopsis",
    "main_characters",
    "plot_arcs",
    "turning_points",
    "themes",
)


def _default_plot(topic: str, genre: str, num_chapters: int) -> dict[str, Any]:
    """Minimal fallback plot dict when all parse attempts fail."""
    return {
        "title": f"{topic}传",
        "synopsis": f"一部以{topic}为核心主题的{genre}小说，全{num_chapters}章。",
        "main_characters": [
            {
                "name": "主角",
                "role": "protagonist",
                "personality": "坚毅果断",
                "core_desire": "超越极限，守护所爱",
                "hidden_agenda": "",
            }
        ],
        "plot_arcs": [
            {
                "name": "起源",
                "description": "主角踏上旅程，初识世界",
                "start_chapter": 1,
                "end_chapter": num_chapters // 3,
            },
            {
                "name": "成长",
                "description": "主角历经磨难，蜕变成长",
                "start_chapter": num_chapters // 3 + 1,
                "end_chapter": num_chapters * 2 // 3,
            },
            {
                "name": "终局",
                "description": "最终决战，命运揭晓",
                "start_chapter": num_chapters * 2 // 3 + 1,
                "end_chapter": num_chapters,
            },
        ],
        "turning_points": [
            {
                "chapter": num_chapters // 4,
                "description": "第一个重大转折",
                "impact": "改变主角命运走向",
            },
            {
                "chapter": num_chapters // 2,
                "description": "中期大反转",
                "impact": "揭示隐藏的真相",
            },
            {
                "chapter": num_chapters * 3 // 4,
                "description": "高潮前夕",
                "impact": "推向最终决战",
            },
        ],
        "themes": ["成长", "牺牲", "友情", "命运"],
    }


def _summarise_world(world_data: dict[str, Any]) -> str:
    """Produce a compact text summary of world_data for injection into prompts."""
    lines: list[str] = []
    if world_data.get("name"):
        lines.append(f"世界名称：{world_data['name']}")
    if world_data.get("description"):
        lines.append(f"概述：{world_data['description']}")
    if world_data.get("power_system_name"):
        lines.append(f"力量体系：{world_data['power_system_name']}")
    if world_data.get("cultivation_levels"):
        levels = world_data["cultivation_levels"]
        if isinstance(levels, list):
            lines.append(f"境界体系：{' → '.join(str(l) for l in levels)}")
    if world_data.get("factions"):
        factions = world_data["factions"]
        if isinstance(factions, list):
            faction_names = [
                f.get("name", str(f)) if isinstance(f, dict) else str(f)
                for f in factions[:5]
            ]
            lines.append(f"主要势力：{'、'.join(faction_names)}")
    if world_data.get("world_constraints"):
        constraints = world_data["world_constraints"]
        if isinstance(constraints, list) and constraints:
            lines.append("世界规则：")
            for c in constraints[:3]:
                lines.append(f"  - {c}")
    return "\n".join(lines) if lines else "（无世界观摘要）"


@dataclass
class OutlineStage(StageRunner):
    """Generate the plot outline and store it in ``state.plot_data``.

    Reads from ``state.world_data`` (must be populated by WorldStage first) and
    ``state.config``:
        - num_chapters (int): Total chapter count
        - genre (str): Novel genre
        - style (str): Writing style
        - reference_backbone (str | None): Optional classic-novel structural guidance
        - backbone_mode (str): "loose" (default, inspiration-only) or "strict"
          (mandatory structural anchors with backbone_mapping output)

    Writes:
        - state.plot_data: Structured outline dict with title, synopsis,
          main_characters, plot_arcs, turning_points, themes
        - state.current_stage: set to "outline"
    """

    name: str = "outline"

    def validate_input(self, state: PipelineState) -> bool:
        """Require world_data to have been generated first."""
        return bool(state.world_data)

    def run(self, state: PipelineState) -> PipelineState:
        """Execute outline generation stage.

        Args:
            state: Current pipeline state (world_data must be populated).

        Returns:
            Updated PipelineState with plot_data populated.
        """
        cfg = state.config
        topic = cfg.get("topic", "").strip()
        genre = cfg.get("genre", cfg.get("style", ""))
        style = cfg.get("style", genre)
        num_chapters = int(cfg.get("num_chapters", 100))
        reference_backbone: str = cfg.get("reference_backbone", "") or ""
        backbone_mode: str = cfg.get("backbone_mode", "loose")  # "loose" or "strict"

        logger.info(
            "[outline] Generating plot outline for topic=%r genre=%r chapters=%d backbone=%s mode=%s",
            topic,
            genre,
            num_chapters,
            "yes" if reference_backbone else "no",
            backbone_mode,
        )

        character_archetypes: list = (
            cfg.get("character_archetypes", [])
            if reference_backbone
            else []
        )

        world_summary = _summarise_world(state.world_data)
        system_prompt, user_prompt = self._build_prompts(
            topic=topic,
            genre=genre,
            style=style,
            num_chapters=num_chapters,
            world_summary=world_summary,
            reference_backbone=reference_backbone,
            backbone_mode=backbone_mode,
            character_archetypes=character_archetypes,
        )

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=6000, temperature=0.8)
        plot_data = self._parse_plot_data(raw, topic=topic)

        if not plot_data:
            logger.warning("[outline] First parse attempt failed, retrying with explicit JSON instructions")
            retry_system = (
                "你是一位网络文学策划师。你必须且只能输出一个合法的 JSON 对象，"
                "不得包含任何 markdown 标记、代码块或额外说明。"
            )
            retry_user = (
                f"请重新为题材「{topic}」（{genre}风格，共{num_chapters}章）生成小说大纲，"
                f"直接输出 JSON，必须包含字段：{', '.join(_REQUIRED_KEYS)}。"
                f"\n\n参考以下原始响应（可能格式有误）：\n\n{raw[:2000]}"
            )
            raw2 = self._call_llm(retry_system, retry_user, max_tokens=6000, temperature=0.5)
            plot_data = self._parse_plot_data(raw2, topic=topic)

        if not plot_data:
            logger.warning("[outline] Both parse attempts failed; using default plot structure")
            plot_data = _default_plot(topic, genre, num_chapters)

        # Ensure all required keys are present
        plot_data = self._fill_missing_keys(plot_data, topic=topic, genre=genre, num_chapters=num_chapters)

        # Carry character archetypes forward for downstream stages
        if character_archetypes:
            plot_data["character_archetypes"] = character_archetypes

        # Annotate strict-mode metadata so downstream stages can inspect it
        if backbone_mode == "strict" and reference_backbone:
            plot_data["backbone_mode"] = "strict"
            # Populate backbone_mappings from LLM output if present; otherwise seed empty list.
            if "backbone_mappings" not in plot_data:
                plot_data["backbone_mappings"] = []

        # Immutable pattern: return new state with updated plot_data
        import dataclasses
        new_state = dataclasses.replace(
            state,
            plot_data=plot_data,
            current_stage="outline",
        )
        logger.info("[outline] Stage complete. Title: %r", plot_data.get("title", ""))
        return new_state

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_backbone_prompt(self, backbone_data: str, mode: str) -> str:
        """Return the backbone prompt section appropriate for the given mode.

        Args:
            backbone_data: Raw backbone text (events/summary from a classic work).
            mode: "loose" — inject as inspiration; "strict" — mandatory anchors.

        Returns:
            A formatted prompt section string.
        """
        if not backbone_data or not backbone_data.strip():
            return "（无参考骨架）"

        if mode == "strict":
            # Parse lines as numbered events; fall back to treating each non-empty
            # line as a separate event.
            lines = [ln.strip() for ln in backbone_data.strip().splitlines() if ln.strip()]
            event_lines = []
            for idx, line in enumerate(lines, 1):
                # Support "Name: content" or plain text lines
                if "：" in line or ":" in line:
                    sep = "：" if "：" in line else ":"
                    parts = line.split(sep, 1)
                    name, content = parts[0].strip(), parts[1].strip()
                else:
                    name, content = f"事件{idx}", line
                event_lines.append(
                    f"{idx}. {name}: {content} → 请映射为本小说中的对应情节"
                )
            events_block = "\n".join(event_lines)
            return (
                "以下参考骨架为强制结构锚点。你必须为每个骨架事件创建对应的小说事件：\n\n"
                "骨架事件列表：\n"
                f"{events_block}\n\n"
                "输出的 plot_arcs 中必须包含 \"backbone_mapping\" 字段，记录每个骨架事件对应的小说事件。\n"
                "backbone_mappings 顶层字段格式：\n"
                "[{\"reference_event\": \"<骨架事件名>\", \"novel_event\": \"<本小说对应情节>\", \"chapter\": <章节号>}, ...]"
            )
        else:
            # loose mode: inspiration only
            return (
                "以下参考骨架仅供灵感启发，你可以自由改编：\n\n"
                + backbone_data.strip()
            )

    def _build_prompts(
        self,
        topic: str,
        genre: str,
        style: str,
        num_chapters: int,
        world_summary: str,
        reference_backbone: str,
        backbone_mode: str = "loose",
        character_archetypes: list | None = None,
    ) -> tuple[str, str]:
        """Build system and user prompts for outline generation."""
        backbone_section = self._build_backbone_prompt(reference_backbone, backbone_mode)

        # Try loading the prompt template; fall back to inline prompt.
        try:
            template = self._load_prompt_template("outline_stage.txt")
            system_prompt = template.format(
                genre=genre,
                num_chapters=num_chapters,
                world_summary=world_summary,
                reference_backbone=backbone_section,
            )
        except (FileNotFoundError, KeyError):
            system_prompt = (
                f"你是一位擅长{genre}的网络文学策划师，"
                f"请根据世界观设定和参考骨架，设计一部{num_chapters}章的小说大纲。"
            )

        archetypes_section = ""
        if character_archetypes:
            archetypes_str = "、".join(str(a) for a in character_archetypes)
            archetypes_section = f"\n=== 参考角色原型 ===\n参考角色原型：{archetypes_str}\n"

        # Extra instruction for strict mode
        strict_extra = ""
        if backbone_mode == "strict" and reference_backbone:
            strict_extra = (
                "\n6. 【强制要求】为每个骨架事件创建对应的小说事件，并在输出 JSON 的顶层加入 "
                "\"backbone_mappings\" 数组，每项包含 reference_event、novel_event、chapter 字段"
            )

        user_prompt = (
            f"题材：{topic}\n"
            f"风格：{style}\n"
            f"类型：{genre}\n"
            f"总章数：{num_chapters}\n\n"
            "=== 世界观摘要 ===\n"
            f"{world_summary}\n\n"
            "=== 参考骨架（如有）===\n"
            f"{backbone_section}\n"
            f"{archetypes_section}\n"
            "请直接输出 JSON，不要包含任何 markdown 标记或代码块。\n"
            "JSON 必须包含以下字段：\n"
            + "\n".join(f"- {k}" for k in _REQUIRED_KEYS)
            + "\n\n"
            "其中 main_characters 每项需包含：name, role, personality, core_desire, hidden_agenda\n"
            "plot_arcs 每项需包含：name, description, start_chapter, end_chapter\n"
            "turning_points 每项需包含：chapter, description, impact\n"
            "themes 为字符串列表\n\n"
            "要求：\n"
            "1. 故事节奏张弛有度，每5-8章有一个小高潮\n"
            "2. 主角成长线清晰，有明确的能力和心理成长\n"
            "3. 反派有独立动机和生存逻辑\n"
            "4. turning_points 至少包含3个关键转折\n"
            "5. 如有参考骨架，请融入其叙事结构和节奏模式"
            + strict_extra
        )
        return system_prompt, user_prompt

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_plot_data(self, text: str, topic: str) -> dict[str, Any] | None:
        """Attempt to parse plot data from LLM response text.

        Returns the parsed dict or None if parsing fails.
        """
        import re

        if not text or not text.strip():
            return None

        # Strip <think>...</think> reasoning blocks
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

        # Try base helper (handles ```json fences)
        try:
            data = self._parse_json_response(cleaned)
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: balanced brace extraction
        obj = self._extract_first_json_object(cleaned)
        if obj:
            return obj

        return None

    def _extract_first_json_object(self, text: str) -> dict[str, Any] | None:
        """Find and return the first balanced JSON object in ``text``."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        return None
        return None

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _fill_missing_keys(
        self,
        data: dict[str, Any],
        topic: str,
        genre: str,
        num_chapters: int,
    ) -> dict[str, Any]:
        """Ensure all required keys exist, filling in sensible defaults."""
        defaults = _default_plot(topic, genre, num_chapters)
        result = dict(data)

        for key in _REQUIRED_KEYS:
            if key not in result or result[key] is None:
                result[key] = defaults[key]
                logger.debug("[outline] Filled missing key %r with default", key)

        # Guarantee list types for collection fields.
        for list_key in ("main_characters", "plot_arcs", "turning_points", "themes"):
            if not isinstance(result.get(list_key), list):
                result[list_key] = defaults[list_key]

        # title and synopsis must be non-empty strings.
        if not result.get("title"):
            result["title"] = defaults["title"]
        if not result.get("synopsis"):
            result["synopsis"] = defaults["synopsis"]

        return result
