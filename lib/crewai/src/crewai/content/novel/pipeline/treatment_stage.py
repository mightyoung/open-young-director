"""TreatmentStage: prose narrative treatment pipeline stage.

Bridges outline and volume by producing a 3-5 page narrative overview
(故事treatment) that covers story conflicts, character arcs, key turning
points, and emotional pacing — in the Hollywood Treatment tradition but
adapted for Chinese web novels.

Reads:  state.plot_data, state.world_data
Writes: state.treatment (str)
"""

from __future__ import annotations

import dataclasses
import logging
import re

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
你是一位资深的中国网络文学创意总监，擅长将结构化大纲转化为流畅的叙事性故事treatment。
Treatment是一种好莱坞行业工具——用散文而非bullet points，生动呈现整个故事的情感体验。
请用第三人称视角，以叙事散文的形式撰写，让读者"感受"到故事，而非仅仅"了解"情节。
不要输出JSON，直接输出中文散文。
"""

_FALLBACK_TEMPLATE = """\
【故事Treatment】

本故事以"{title}"为核心，在{genre}的世界观下展开。

{synopsis}

主角面临的核心挑战将推动整个叙事弧线，经历成长、磨难与最终的蜕变，
在情感与力量的双重维度上完成属于自己的史诗征途。
"""


def _compact_plot(plot_data: dict) -> str:
    """Return a concise text summary of plot_data for the prompt."""
    parts: list[str] = []

    if plot_data.get("title"):
        parts.append(f"标题：{plot_data['title']}")
    if plot_data.get("synopsis"):
        synopsis = str(plot_data["synopsis"])
        parts.append(f"梗概：{synopsis[:500]}")

    chars = plot_data.get("main_characters", [])
    if chars:
        char_lines = []
        for c in chars[:4]:
            if isinstance(c, dict):
                name = c.get("name", "")
                desire = c.get("core_desire", "")
                char_lines.append(f"  · {name}（{desire}）")
        if char_lines:
            parts.append("主要角色：\n" + "\n".join(char_lines))

    arcs = plot_data.get("plot_arcs", [])
    if arcs:
        arc_lines = [
            f"  · {a.get('name', '')}: {a.get('description', '')}"
            for a in arcs[:5]
            if isinstance(a, dict)
        ]
        if arc_lines:
            parts.append("情节弧线：\n" + "\n".join(arc_lines))

    turns = plot_data.get("turning_points", [])
    if turns:
        turn_lines = [
            f"  · 第{t.get('chapter', '?')}章：{t.get('description', '')} → {t.get('impact', '')}"
            for t in turns[:5]
            if isinstance(t, dict)
        ]
        if turn_lines:
            parts.append("关键转折：\n" + "\n".join(turn_lines))

    themes = plot_data.get("themes", [])
    if themes:
        parts.append(f"核心主题：{'、'.join(str(t) for t in themes[:6])}")

    return "\n\n".join(parts) if parts else "（无情节数据）"


def _compact_world(world_data: dict) -> str:
    """Return a concise world summary for the prompt."""
    import json

    text = json.dumps(world_data, ensure_ascii=False, default=str)
    return text[:600] + "...(截断)" if len(text) > 600 else text


@dataclasses.dataclass
class TreatmentStage(StageRunner):
    """Generate a prose narrative treatment and store it in ``state.treatment``.

    Reads from:
        state.plot_data   — structured outline (from OutlineStage)
        state.world_data  — world building data (from WorldStage)

    Writes:
        state.treatment   — 3000-5000字 Chinese prose narrative overview
        state.current_stage — set to "treatment"
    """

    name: str = "treatment"

    def validate_input(self, state: PipelineState) -> bool:
        """Require both plot_data and world_data to be present."""
        if not state.plot_data:
            logger.error("[treatment] validate_input failed: plot_data is empty")
            return False
        if not state.world_data:
            logger.error("[treatment] validate_input failed: world_data is empty")
            return False
        return True

    def run(self, state: PipelineState) -> PipelineState:
        """Generate the treatment and return an updated PipelineState.

        Args:
            state: Current pipeline state (not mutated).

        Returns:
            New PipelineState with ``treatment`` populated and
            ``current_stage`` set to ``"treatment"``.
        """
        cfg = state.config
        topic = cfg.get("topic", "").strip()
        genre = cfg.get("genre", cfg.get("style", ""))
        num_chapters = int(cfg.get("num_chapters", 100))

        logger.info(
            "[treatment] Generating narrative treatment for topic=%r genre=%r chapters=%d",
            topic, genre, num_chapters,
        )

        plot_summary = _compact_plot(state.plot_data)
        world_summary = _compact_world(state.world_data)

        user_prompt = (
            f"题材：{topic}\n"
            f"类型：{genre}\n"
            f"总章数：{num_chapters}\n\n"
            "=== 世界观摘要 ===\n"
            f"{world_summary}\n\n"
            "=== 情节规划 ===\n"
            f"{plot_summary}\n\n"
            "请根据以上信息，撰写一篇3000-5000字的故事treatment（叙事性散文概述），"
            "必须涵盖以下五个维度：\n"
            "1. 【故事核心冲突】主角面临的终极矛盾与驱动力\n"
            "2. 【主角弧线】主角从初始状态到终局的内在成长与转变历程\n"
            "3. 【关键转折点】改变故事走向的3-5个重大事件（叙事性描述，非列表）\n"
            "4. 【情感节奏】整体情绪起伏曲线——张弛、悬念、高潮的分布节奏\n"
            "5. 【故事愿景】读者读完后应有怎样的情感共鸣与精神体验\n\n"
            "要求：\n"
            "· 以散文叙事写作，不用子标题或bullet points\n"
            "· 语言生动有画面感，让读者能'感受'故事而非仅'了解'情节\n"
            "· 保持与世界观和人物设定的一致性\n"
            "· 直接输出treatment正文，不要包含任何说明或前言"
        )

        raw = self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=6000,
            temperature=0.85,
        )

        treatment = self._clean_treatment(raw)

        if not treatment:
            logger.warning("[treatment] LLM returned empty response, using fallback")
            treatment = _FALLBACK_TEMPLATE.format(
                title=state.plot_data.get("title", topic),
                genre=genre,
                synopsis=state.plot_data.get("synopsis", ""),
            )

        new_state = dataclasses.replace(
            state,
            treatment=treatment,
            current_stage="treatment",
        )
        logger.info("[treatment] Stage complete. Treatment length: %d chars", len(treatment))
        return new_state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clean_treatment(self, text: str) -> str:
        """Strip <think> blocks and markdown fences; return clean prose."""
        if not text or not text.strip():
            return ""
        # Remove reasoning blocks (e.g. DeepSeek-R1 style)
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
        # Strip markdown code fences if the LLM wrapped output
        cleaned = re.sub(r"^```[^\n]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
        return cleaned.strip()
