"""WorldStage: world-building pipeline stage.

Pure Python, no CrewAI dependency.  Reads config from PipelineState and
populates ``state.world_data`` with a structured world-building dict.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from crewai.content.novel.pipeline.stage_runner import StageRunner
from crewai.content.novel.pipeline_state import PipelineState

logger = logging.getLogger(__name__)

# Required top-level keys the LLM must return.
_REQUIRED_KEYS = (
    "name",
    "description",
    "power_system_name",
    "cultivation_levels",
    "level_abilities",
    "world_constraints",
    "geography",
    "factions",
    "history",
    "social_rules",
)

# Xianxia genres that need cultivation-specific defaults.
_XIANXIA_GENRES = {"xianxia", "仙侠", "修仙", "玄幻", "cultivation"}


def _default_world(topic: str) -> dict[str, Any]:
    """Return a minimal fallback world dict when all parse attempts fail."""
    return {
        "name": f"{topic}世界",
        "description": f"一个以{topic}为核心的神秘世界",
        "power_system_name": "修炼体系",
        "cultivation_levels": ["凡人", "练气", "筑基", "金丹", "元婴", "化神"],
        "level_abilities": {
            "凡人": ["普通体能"],
            "练气": ["操控灵气", "延年益寿"],
            "筑基": ["御剑飞行", "灵识感知"],
            "金丹": ["神通初现", "空间感知"],
            "元婴": ["元神出窍", "毁天灭地"],
            "化神": ["规则掌控", "长生不死"],
        },
        "world_constraints": [
            "修炼需要灵气，荒芜之地无法突破",
            "每次大境界突破都有雷劫",
            "杀戮过重者会被天道排斥",
        ],
        "geography": [
            {"name": "中州", "description": "大陆中心，灵气最为充沛"},
            {"name": "荒原", "description": "边境荒芜之地，充满危险"},
        ],
        "factions": [
            {"name": "正道联盟", "description": "各大正派组成的联盟"},
            {"name": "魔道", "description": "走偏门功法的修炼者势力"},
        ],
        "history": [
            "万年前上古大战，仙道凋零",
            "三千年前各大宗门兴起",
            "百年前魔道暗中崛起",
        ],
        "social_rules": [
            "弱肉强食，强者为尊",
            "宗门弟子须遵守门规",
            "杀人须有缘由，滥杀无辜者各方共诛之",
        ],
    }


@dataclass
class WorldStage(StageRunner):
    """Generate world-building data and store it in ``state.world_data``.

    Reads from ``state.config``:
        - topic (str): Novel topic / premise
        - genre (str): Novel genre (e.g. "xianxia", "都市")
        - style (str): Writing style
        - num_chapters (int): Total chapter count
        - target_words (int): Target word count

    Writes:
        - state.world_data: Structured world dict with all world-building info
        - state.current_stage: set to "world"
    """

    name: str = "world"

    def validate_input(self, state: PipelineState) -> bool:
        """Require at minimum a non-empty topic in config."""
        return bool(state.config.get("topic", "").strip())

    def run(self, state: PipelineState) -> PipelineState:
        """Execute world-building stage.

        Args:
            state: Current pipeline state.

        Returns:
            Updated PipelineState with world_data populated.
        """
        cfg = state.config
        topic = cfg.get("topic", "").strip()
        genre = cfg.get("genre", cfg.get("style", ""))
        style = cfg.get("style", genre)
        num_chapters = int(cfg.get("num_chapters", 100))
        is_xianxia = genre.lower() in _XIANXIA_GENRES

        logger.info("[world] Building world for topic=%r genre=%r chapters=%d", topic, genre, num_chapters)

        system_prompt, user_prompt = self._build_prompts(
            topic=topic,
            genre=genre,
            style=style,
            num_chapters=num_chapters,
            is_xianxia=is_xianxia,
        )

        raw = self._call_llm(system_prompt, user_prompt, max_tokens=4096, temperature=0.8)
        world_data = self._parse_world_data(raw, topic=topic)

        if not world_data:
            logger.warning("[world] First parse attempt failed, retrying with explicit JSON instructions")
            retry_system = (
                "你是一位世界观构建专家。你必须且只能输出一个合法的 JSON 对象，"
                "不得包含任何 markdown 标记、代码块或额外说明。"
            )
            retry_user = (
                f"请重新为题材「{topic}」（{genre}风格）生成世界观，"
                f"直接输出 JSON，包含字段：{', '.join(_REQUIRED_KEYS)}。"
                f"参考以下原始响应（可能格式有误）：\n\n{raw[:2000]}"
            )
            raw2 = self._call_llm(retry_system, retry_user, max_tokens=4096, temperature=0.5)
            world_data = self._parse_world_data(raw2, topic=topic)

        if not world_data:
            logger.warning("[world] Both parse attempts failed; using default world structure")
            world_data = _default_world(topic)

        # Ensure required keys are present
        world_data = self._fill_missing_keys(world_data, topic=topic, genre=genre, is_xianxia=is_xianxia)

        # Immutable pattern: return new state with updated world_data
        import dataclasses
        new_state = dataclasses.replace(
            state,
            world_data=world_data,
            current_stage="world",
        )
        logger.info("[world] Stage complete. World name: %r", world_data.get("name", ""))
        return new_state

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_prompts(
        self,
        topic: str,
        genre: str,
        style: str,
        num_chapters: int,
        is_xianxia: bool,
    ) -> tuple[str, str]:
        """Build system and user prompts for world generation."""
        try:
            template = self._load_prompt_template("world_stage.txt")
            system_prompt = template.format(
                genre=genre,
                topic=topic,
                style=style,
                num_chapters=num_chapters,
            )
        except (FileNotFoundError, KeyError):
            system_prompt = (
                f"你是一位擅长{genre}的网络文学世界架构师，请为题材「{topic}」"
                f"设计一个完整的小说世界观，以 JSON 格式输出。"
            )

        extra_xianxia = ""
        if is_xianxia:
            extra_xianxia = (
                "\n\n特别要求（修仙/仙侠体系）："
                "\n- cultivation_levels 列表必须包含至少6个境界，从低到高排列"
                "\n- level_abilities 为字典，键为境界名，值为该境界解锁的能力列表"
                "\n- world_constraints 必须包含修炼资源稀缺性、天道规则等约束"
            )

        user_prompt = (
            f"题材：{topic}\n"
            f"风格：{style}\n"
            f"类型：{genre}\n"
            f"总章数：{num_chapters}\n"
            f"{extra_xianxia}\n\n"
            "请直接输出 JSON，不要包含任何 markdown 标记或代码块。"
            "JSON 必须包含以下字段：\n"
            + "\n".join(f"- {k}" for k in _REQUIRED_KEYS)
        )
        return system_prompt, user_prompt

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_world_data(self, text: str, topic: str) -> dict[str, Any] | None:
        """Attempt to parse world data from LLM response text.

        Returns the parsed dict or None if parsing fails.
        """
        import re

        if not text or not text.strip():
            return None

        # Strip <think>...</think> blocks (reasoning model output)
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

        # Try base helper (handles ```json fences)
        try:
            data = self._parse_json_response(cleaned)
            if isinstance(data, dict) and data:
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        # Try extracting first JSON object via brace matching
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
        is_xianxia: bool,
    ) -> dict[str, Any]:
        """Ensure all required keys exist, filling in defaults where absent."""
        defaults = _default_world(topic)
        result = dict(data)

        for key in _REQUIRED_KEYS:
            if key not in result or result[key] is None:
                result[key] = defaults[key]
                logger.debug("[world] Filled missing key %r with default", key)

        # For non-xianxia genres, strip cultivation-specific sections if they
        # were copied from defaults and look odd.
        if not is_xianxia and not data.get("cultivation_levels"):
            result["cultivation_levels"] = []
            result["level_abilities"] = {}
            result["world_constraints"] = data.get("world_constraints") or defaults["world_constraints"]

        return result
