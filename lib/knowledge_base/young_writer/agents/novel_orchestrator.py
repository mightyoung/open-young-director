"""Novel-first orchestrator for chapter generation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from .reality_checker import RealityChecker, RealityCheckerConfig, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the novel orchestrator."""

    max_subagent_concurrent: int = 5
    max_concurrent_scenes: int = 3
    enable_verification: bool = True
    max_retry: int = 2
    max_verification_retries: int = 3
    mode: str = "STANDARD"
    num_subagents: int = 3
    use_directorial_guidance: bool = False
    enable_plot_evolution: bool = True
    enable_npc_simulation: bool = False
    enable_reality_checker: bool = True
    reality_checker_config: RealityCheckerConfig | None = None


class NovelOrchestrator:
    """Orchestrates novel chapter content without derivative asset generation."""

    def __init__(self, config: OrchestratorConfig | None = None, llm_client=None):
        self.config = config or OrchestratorConfig()
        self.llm_client = llm_client
        self.mode = "STANDARD"
        self.director_agent = None
        self.sub_agent_pool: list[Any] = []
        self.novel_writer_agent = None
        self.message_queue = None
        self._initialized = False
        self._reality_checker: RealityChecker | None = None

        if self.config.enable_reality_checker:
            self._reality_checker = RealityChecker(
                llm_client=llm_client,
                config=self.config.reality_checker_config or RealityCheckerConfig(),
            )
            logger.info("NovelOrchestrator initialized with RealityChecker")

    def setup(self, context: dict[str, Any]) -> bool:
        """Initialize the novel-only orchestration surface."""
        self._initialized = True
        return True

    def orchestrate_chapter(
        self,
        chapter_number: int,
        chapter_outline: str,
        context: dict[str, Any],
        bible_section: Any = None,
    ) -> dict[str, Any]:
        """Build a novel chapter draft packet from outline and context."""
        if not self._initialized:
            self.setup(context)

        characters = self._extract_characters_from_context(context)
        location = self._resolve_location_from_context(context)
        time_of_day = self._resolve_time_of_day_from_context(context)
        previous_summary = str(context.get("previous_summary") or "")

        content_parts = [
            f"第{chapter_number}章",
            "",
            str(chapter_outline or "").strip(),
        ]
        if previous_summary:
            content_parts.extend(["", f"承接前情：{previous_summary}"])
        if location or time_of_day:
            scene_hint = "，".join(part for part in (time_of_day, location) if part)
            content_parts.extend(["", f"场景推进：{scene_hint}。"])
        if characters:
            names = "、".join(characters.keys())
            content_parts.extend(["", f"本章角色：{names}。"])
        if bible_section:
            content_parts.extend(["", f"设定约束：{bible_section}"])

        content = "\n".join(part for part in content_parts if part is not None).strip()
        final_plot = self.assemble_plot([], {"outline": chapter_outline, "context": context})
        return {
            "chapter_number": chapter_number,
            "outline": chapter_outline,
            "plot_outline": {"beats": [chapter_outline]} if chapter_outline else {},
            "cast": [
                {"name": name, **profile}
                for name, profile in characters.items()
            ],
            "scenes": [],
            "final_plot": final_plot or chapter_outline,
            "content": content,
        }

    def orchestrate_scenes(
        self,
        plot_outline: dict[str, Any],
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Scene-level derivative generation is intentionally disabled."""
        return []

    def assemble_plot(
        self,
        scenes: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> str:
        """Assemble a concise plot statement from novel context."""
        outline = str(context.get("outline") or "").strip()
        if outline:
            return outline
        scene_summaries = [str(scene.get("summary") or "") for scene in scenes]
        return "\n".join(summary for summary in scene_summaries if summary)

    def _resolve_location_from_context(self, context: dict[str, Any]) -> str:
        packet = context.get("generation_packet")
        if isinstance(packet, dict):
            plan = packet.get("chapter_plan")
            world = packet.get("world_bible")
            location_ids = plan.get("location_ids", []) if isinstance(plan, dict) else []
            locations = world.get("locations", []) if isinstance(world, dict) else []
            for raw_id in location_ids:
                location_name = str(raw_id).split(":", 1)[-1]
                for location in locations:
                    if location_name and location_name in str(location):
                        return str(location)
                if location_name:
                    return location_name

        outline = str(context.get("generation_outline") or context.get("outline") or "")
        match = re.search(r"(?:在|潜入|抵达|前往)([^，。！？\s]{2,20})", outline)
        return match.group(1) if match else ""

    def _resolve_time_of_day(self, text: str) -> str:
        for keyword in ("凌晨", "清晨", "早晨", "上午", "正午", "午后", "傍晚", "黄昏", "夜晚", "深夜"):
            if keyword in text:
                return keyword
        return ""

    def _resolve_time_of_day_from_context(self, context: dict[str, Any]) -> str:
        packet = context.get("generation_packet")
        if isinstance(packet, dict):
            plan = packet.get("chapter_plan")
            if isinstance(plan, dict):
                explicit = str(plan.get("time_of_day") or plan.get("time") or "")
                if explicit:
                    return explicit
        return self._resolve_time_of_day(
            str(context.get("generation_outline") or context.get("outline") or "")
        )

    def _extract_characters_from_context(self, context: dict[str, Any]) -> dict[str, dict[str, Any]]:
        packet = context.get("generation_packet")
        characters: dict[str, dict[str, Any]] = {}
        if isinstance(packet, dict) and isinstance(packet.get("characters"), list):
            for item in packet["characters"]:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                characters[name] = {
                    "identity": str(item.get("role") or item.get("identity") or "关键角色"),
                    "objective": str(item.get("motivation") or item.get("objective") or ""),
                    "arc": str(item.get("arc") or ""),
                }

        raw_characters = context.get("characters")
        if isinstance(raw_characters, dict):
            for name, profile in raw_characters.items():
                if isinstance(profile, dict):
                    characters.setdefault(str(name), dict(profile))

        for name in context.get("character_names") or []:
            clean_name = str(name).strip()
            if clean_name:
                characters.setdefault(clean_name, {"identity": "关键角色"})
        return characters

    def evaluate_evolution(
        self,
        original_outline: str,
        generated_content: str,
    ) -> dict[str, Any]:
        """Evaluate whether generated content preserves the outline direction."""
        missing_outline = bool(original_outline and original_outline[:12] not in generated_content)
        return {
            "evolved": not missing_outline,
            "issues": ["content does not visibly preserve the outline"] if missing_outline else [],
        }

    def quality_gate(
        self,
        content: str,
        criteria: dict[str, Any],
    ) -> ValidationResult:
        """Run content through RealityChecker quality gate."""
        if not self._reality_checker:
            return ValidationResult(status="PASS", score=1.0)
        return self._reality_checker.validate_content(content, criteria)

    def validate_chapter(
        self,
        chapter_content: str,
        context: dict[str, Any],
    ) -> ValidationResult:
        """Validate generated chapter content."""
        criteria = {
            "characters": context.get("characters", {}),
            "previous_summary": context.get("previous_summary", ""),
            "required_elements": context.get("required_elements", []),
            "prohibited_elements": context.get("prohibited_elements", []),
        }
        return self.quality_gate(chapter_content, criteria)

    def check_character_consistency(
        self,
        content: str,
        characters: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Check character consistency through RealityChecker."""
        if not self._reality_checker:
            return {"consistent": True, "issues": [], "evidence_required": []}
        return self._reality_checker.check_character_consistency(content, characters)

    def check_plot_coherence(
        self,
        content: str,
        previous_summary: str,
    ) -> dict[str, Any]:
        """Check plot coherence through RealityChecker."""
        if not self._reality_checker:
            return {"coherent": True, "issues": [], "evidence_required": []}
        return self._reality_checker.check_plot_coherence(content, previous_summary)

    def get_reality_checker(self) -> RealityChecker | None:
        """Get the RealityChecker instance."""
        return self._reality_checker
