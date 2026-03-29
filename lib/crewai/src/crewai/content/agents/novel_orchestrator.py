"""Novel Orchestrator for FILM_DRAMA mode generation."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .film_drama import (
    DirectorAgent,
    DirectorConfig,
    InMemoryMessageQueue,
    CharacterBible,
    AgentRole,
)
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
    mode: str = "FILM_DRAMA"  # FILM_DRAMA or STANDARD
    num_subagents: int = 3
    use_directorial_guidance: bool = True
    enable_plot_evolution: bool = True
    enable_npc_simulation: bool = True
    # RealityChecker integration
    enable_reality_checker: bool = True
    reality_checker_config: RealityCheckerConfig = None


class NovelOrchestrator:
    """Orchestrates novel generation using multi-agent approach.

    FILM_DRAMA mode uses:
    - DirectorAgent: Plans scenes and narrative structure
    - SubAgentPool: Manages character perspectives
    - NovelWriterAgent: Assembles final narrative

    STANDARD mode uses:
    - Single LLM call for content generation

    Quality Gates:
    - RealityChecker: Validates content quality before approval
    - Default status is "NEEDS_WORK" requiring overwhelming evidence to pass
    """

    def __init__(self, config: OrchestratorConfig = None, llm_client=None):
        self.config = config or OrchestratorConfig()
        self.llm_client = llm_client
        self.mode = self.config.mode

        self.director_agent = None
        self.sub_agent_pool = []
        self.novel_writer_agent = None
        self.message_queue = None

        # RealityChecker for quality validation
        self._reality_checker = None
        if self.config.enable_reality_checker:
            checker_config = self.config.reality_checker_config or RealityCheckerConfig()
            self._reality_checker = RealityChecker(
                llm_client=llm_client,
                config=checker_config,
            )

        self._initialized = False

    def setup(self, context: Dict[str, Any]) -> bool:
        """Set up the orchestrator with given context."""
        try:
            if self.mode == "FILM_DRAMA":
                # Initialize FILM_DRAMA components
                self.message_queue = InMemoryMessageQueue()
                director_config = DirectorConfig(
                    enable_npc_simulation=self.config.enable_npc_simulation,
                )
                self.director_agent = DirectorAgent(
                    agent_name="director",
                    llm_client=self.llm_client,
                    config=director_config,
                    message_queue=self.message_queue,
                )
                logger.info("FILM_DRAMA mode: DirectorAgent initialized")

            logger.info("Orchestrator setup complete")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Orchestrator setup failed: {e}")
            return False

    def orchestrate_chapter(
        self,
        chapter_number: int,
        chapter_outline: str,
        context: Dict[str, Any],
        bible_section: Any = None,
    ) -> Dict[str, Any]:
        """Orchestrate chapter generation.

        In FILM_DRAMA mode, uses DirectorAgent for multi-agent scene generation.
        In STANDARD mode, falls back to simple orchestration.

        Args:
            chapter_number: Current chapter number
            chapter_outline: Chapter outline/summary
            context: Additional context dict
            bible_section: Optional BibleSection with world rules and constraints
        """
        if not self._initialized:
            self.setup(context)

        result = {
            "chapter_number": chapter_number,
            "outline": chapter_outline,
            "plot_outline": None,
            "cast": [],
            "scenes": [],
            "final_plot": None,
            "content": None,
        }

        if self.mode == "FILM_DRAMA" and self.director_agent:
            result = self._orchestrate_film_drama(chapter_number, chapter_outline, context, bible_section)

        return result

    def _orchestrate_film_drama(
        self,
        chapter_number: int,
        chapter_outline: str,
        context: Dict[str, Any],
        bible_section: Any = None,
    ) -> Dict[str, Any]:
        """Orchestrate chapter using FILM_DRAMA mode.

        Args:
            chapter_number: Current chapter number
            chapter_outline: Chapter outline/summary
            context: Additional context dict
            bible_section: Optional BibleSection with world rules and constraints
        """
        # Extract character info from context
        characters = self._extract_characters_from_context(context)

        # Extract location and time from outline/context
        location = context.get("location", "太虚宗")
        time_of_day = context.get("time_of_day", "morning")

        # Get previous context for progressive disclosure
        previous_context = context.get("previous_summary", "")

        # P0 FIX: Extract protagonist constraint to prevent protagonist hallucination
        # Dynamically determine protagonist from context or use generic default
        protagonist_constraint = context.get("protagonist_constraint")

        # If no explicit constraint, try to determine protagonist from characters
        if not protagonist_constraint:
            characters = context.get("characters", {})
            protagonist = None
            for name, char_data in characters.items():
                if isinstance(char_data, dict) and char_data.get("role") == "protagonist":
                    protagonist = name
                    break
                # Also check for protagonist field directly
                if isinstance(char_data, dict) and char_data.get("protagonist"):
                    protagonist = name
                    break
            if protagonist:
                protagonist_constraint = f"【强制约束】本章主角：{protagonist}\n" \
                    f"- {protagonist}必须是主角，所有场景以{protagonist}视角展开\n" \
                    f"- 禁止互换角色身份"
            else:
                protagonist_constraint = "【强制约束】请确保叙事视角清晰，以主要角色视角展开" \
                    if protagonist_constraint is None else ""

        # Format bible constraint from bible_section
        bible_constraint = ""
        if bible_section:
            bible_constraint = self._format_bible_constraint(bible_section)

        # Plan scene
        script = self.director_agent.plan_scene(
            chapter_number=chapter_number,
            scene_outline=chapter_outline,
            characters=characters,
            location=location,
            time_of_day=time_of_day,
            previous_context=previous_context,
            protagonist_constraint=protagonist_constraint,
            bible_constraint=bible_constraint,
        )

        # Execute scene
        # Use asyncio.run() which handles event loop properly
        try:
            scene_result = asyncio.run(
                self.director_agent.execute_scene(script)
            )
        except RuntimeError as e:
            # If asyncio.run fails, fall back to getting existing loop
            if "asyncio.run() cannot be called from a running event loop" in str(e):
                loop = asyncio.get_event_loop()
                scene_result = loop.run_until_complete(
                    self.director_agent.execute_scene(script)
                )
            else:
                raise

        # Assemble output using the captured results (instance variables were cleaned after execute_scene)
        final_content = self.director_agent.assemble_scene_output(
            script,
            beat_outputs=scene_result.get("beat_outputs", {}),
            npc_outputs_by_beat=scene_result.get("npc_outputs_by_beat", {}),
        )

        return {
            "chapter_number": chapter_number,
            "outline": chapter_outline,
            "plot_outline": {
                "scene_id": script.scene.scene_id,
                "beats": [
                    {"beat_id": b.beat_id, "type": b.beat_type, "desc": b.description}
                    for b in script.scene.beats
                ],
            },
            "cast": [
                {
                    "name": cb.name,
                    "role": cb.role,
                    "identity": cb.identity,
                    "realm": cb.realm,
                }
                for cb in script.cast
            ],
            "scenes": [script.scene.scene_id],
            "final_plot": script.scene.narration,
            "content": final_content,
        }

    def _extract_characters_from_context(self, context: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract character information from context.

        Supports two formats:
        1. List format: [{"name": "韩林", ...}, ...]
        2. Dict format: {"韩林": {...}, ...}

        Falls back to default characters if no character info available.
        """
        # Try to get characters from knowledge base
        knowledge_chars = context.get("characters", [])

        if knowledge_chars:
            characters = {}
            # Support both list and dict formats
            if isinstance(knowledge_chars, dict):
                # Dict format: {"韩林": {...}} -> convert to list format
                for name, char_data in knowledge_chars.items():
                    if isinstance(char_data, dict):
                        char_data_with_name = {"name": name, **char_data}
                    else:
                        char_data_with_name = {"name": name}
                    name = char_data_with_name.get("name", name)
                    characters[name] = {
                        "identity": char_data_with_name.get("identity", "太虚宗弟子"),
                        "realm": char_data_with_name.get("cultivation_realm", "炼气期"),
                        "personality": char_data_with_name.get("personality", "坚毅果敢"),
                        "speaking_style": char_data_with_name.get("speaking_style", "简洁有力"),
                        "backstory": char_data_with_name.get("backstory", ""),
                        "objective": char_data_with_name.get("objective_this_chapter", ""),
                        "relationships": char_data_with_name.get("relationships", {}),
                    }
            elif isinstance(knowledge_chars, list):
                # List format: [{"name": "韩林", ...}]
                for char in knowledge_chars:
                    name = char.get("name", "未知角色")
                    characters[name] = {
                        "identity": char.get("identity", "太虚宗弟子"),
                        "realm": char.get("cultivation_realm", "炼气期"),
                        "personality": char.get("personality", "坚毅果敢"),
                        "speaking_style": char.get("speaking_style", "简洁有力"),
                        "backstory": char.get("backstory", ""),
                        "objective": char.get("objective_this_chapter", ""),
                        "relationships": char.get("relationships", {}),
                    }
            return characters

        # Default characters for 太古魔帝传
        return {
            "韩林": {
                "identity": "太虚宗外门弟子",
                "realm": "炼气期",
                "personality": "坚毅果敢，隐忍不发",
                "speaking_style": "简洁有力",
                "backstory": "父亲韩啸天曾为太虚宗天才，后被逐出宗门",
                "objective": "三年之约，证明自己",
                "relationships": {"柳如烟": "未婚妻（已退婚）", "叶尘": "情敌"},
            },
            "柳如烟": {
                "identity": "太虚宗第一美人，柳家千金",
                "realm": "炼气期十层",
                "personality": "冷傲，但内心复杂",
                "speaking_style": "清冷犀利",
                "backstory": "玄灵根天才，内门长老弟子",
                "objective": "宗门大比",
                "relationships": {"韩林": "退婚对象", "叶尘": "追求者"},
            },
        }

    def _format_bible_constraint(self, bible_section: Any) -> str:
        """Format BibleSection constraints into a string for prompt injection.

        Args:
            bible_section: BibleSection from crewai's ProductionBible system

        Returns:
            Formatted constraint string for inclusion in prompts
        """
        if not bible_section:
            logger.warning(
                "BibleSection is None, bible constraints will be ignored. "
                "This may cause world rules inconsistency."
            )
            return ""

        lines = []

        # World rules summary
        if hasattr(bible_section, 'world_rules_summary') and bible_section.world_rules_summary:
            lines.append("【世界观规则】")
            lines.append(bible_section.world_rules_summary)
            lines.append("")

        # Canonical facts
        if hasattr(bible_section, 'canonical_facts_this_volume') and bible_section.canonical_facts_this_volume:
            lines.append("【本卷必须遵守的事实】")
            for fact in bible_section.canonical_facts_this_volume:
                lines.append(f"  • {fact}")
            lines.append("")

        # Open foreshadowing
        if hasattr(bible_section, 'open_foreshadowing') and bible_section.open_foreshadowing:
            lines.append("【伏笔约束】（必须正确铺设和回收）")
            for fs in bible_section.open_foreshadowing:
                setup_desc = getattr(fs, 'setup_description', '')
                payoff_desc = getattr(fs, 'payoff_description', '')
                setup_ch = getattr(fs, 'setup_chapter', '?')
                payoff_ch = getattr(fs, 'payoff_chapter', '?')
                if setup_desc and payoff_desc:
                    lines.append(f"  • 第{setup_ch}章埋下伏笔：{setup_desc}")
                    lines.append(f"    → 应在第{payoff_ch}章回收：{payoff_desc}")
            lines.append("")

        # Relationship states at start
        if hasattr(bible_section, 'relationship_states_at_start') and bible_section.relationship_states_at_start:
            lines.append("【开篇角色关系状态】")
            for char, relations in bible_section.relationship_states_at_start.items():
                if isinstance(relations, dict):
                    for other, state in relations.items():
                        lines.append(f"  • {char}与{other}：{state}")
            lines.append("")

        return "\n".join(lines)

    def create_plot_outline(
        self,
        chapter_number: int,
        outline: str,
        previous_summary: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create detailed plot outline for a chapter."""
        if self.mode == "FILM_DRAMA" and self.director_agent:
            # In FILM_DRAMA mode, plan_scene already creates the outline
            characters = self._extract_characters_from_context(context)

            # P0 FIX: Extract protagonist constraint to prevent protagonist hallucination
            # Dynamically determine protagonist from context or use generic default
            protagonist_constraint = context.get("protagonist_constraint")

            # If no explicit constraint, try to determine protagonist from characters
            if not protagonist_constraint:
                characters = context.get("characters", {})
                protagonist = None
                for name, char_data in characters.items():
                    if isinstance(char_data, dict) and char_data.get("role") == "protagonist":
                        protagonist = name
                        break
                    # Also check for protagonist field directly
                    if isinstance(char_data, dict) and char_data.get("protagonist"):
                        protagonist = name
                        break
                if protagonist:
                    protagonist_constraint = f"【强制约束】本章主角：{protagonist}\n" \
                        f"- {protagonist}必须是主角，所有场景以{protagonist}视角展开\n" \
                        f"- 禁止互换角色身份"
                else:
                    protagonist_constraint = "【强制约束】请确保叙事视角清晰，以主要角色视角展开" \
                        if protagonist_constraint is None else ""

            script = self.director_agent.plan_scene(
                chapter_number=chapter_number,
                scene_outline=outline,
                characters=characters,
                location=context.get("location", "太虚宗"),
                time_of_day=context.get("time_of_day", "morning"),
                previous_context=previous_summary,
                protagonist_constraint=protagonist_constraint,
            )
            return {
                "chapter_number": chapter_number,
                "scene_id": script.scene.scene_id,
                "scenes": [
                    {
                        "scene_id": script.scene.scene_id,
                        "location": script.scene.location,
                        "beats": [
                            {
                                "beat_id": b.beat_id,
                                "type": b.beat_type,
                                "description": b.description,
                                "characters": b.expected_chars,
                            }
                            for b in script.scene.beats
                        ],
                    }
                ],
                "narrative_arc": outline,
                "cast": [
                    {
                        "name": cb.name,
                        "realm": cb.realm,
                        "role": cb.role,
                        "objective": cb.objective_this_chapter,
                    }
                    for cb in script.cast
                ],
            }

        return {
            "chapter_number": chapter_number,
            "scenes": [],
            "narrative_arc": outline,
        }

    def determine_cast(
        self,
        chapter_outline: str,
        context: Dict[str, Any],
    ) -> List[str]:
        """Determine character cast for the chapter."""
        characters = self._extract_characters_from_context(context)
        return list(characters.keys())

    def setup_subagents(self, cast: List[str]) -> bool:
        """Set up sub-agents for each character.

        In FILM_DRAMA mode, this is handled by DirectorAgent.
        """
        return True

    def orchestrate_scenes(
        self,
        plot_outline: Dict[str, Any],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Orchestrate scene generation.

        In FILM_DRAMA mode, uses DirectorAgent.execute_scene().
        """
        if self.mode == "FILM_DRAMA" and self.director_agent:
            # scenes are orchestrated by director
            return []

        return []

    def assemble_plot(
        self,
        scenes: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """Assemble scenes into final plot.

        In FILM_DRAMA mode, uses DirectorAgent.assemble_scene_output().
        """
        if self.mode == "FILM_DRAMA" and self.director_agent:
            # Director handles assembly
            return ""

        return ""

    def evaluate_evolution(
        self,
        original_outline: str,
        generated_content: str,
    ) -> Dict[str, Any]:
        """Evaluate if plot evolved significantly from outline."""
        return {
            "evolved": False,
            "changes": [],
            "score": 0.0,
        }

    # ==================== QUALITY GATE ====================

    def quality_gate(
        self,
        content: str,
        criteria: Dict[str, Any],
    ) -> ValidationResult:
        """Run content through RealityChecker quality gate.

        This is the main quality validation method. It returns a ValidationResult
        that indicates whether the content passes or needs more work.

        Default status is "NEEDS_WORK" - only overwhelming evidence earns "PASS".

        Args:
            content: The generated content to validate
            criteria: Validation criteria including:
                - characters: Character profiles for consistency check
                - previous_summary: Previous plot summary for coherence
                - required_elements: List of required plot elements
                - prohibited_elements: List of prohibited content

        Returns:
            ValidationResult with status, score, issues, and evidence requirements
        """
        if not self._reality_checker:
            # RealityChecker disabled - auto-pass
            return ValidationResult(
                status="PASS",
                score=1.0,
                issues=[],
                evidence_required=[],
            )

        result = self._reality_checker.validate_content(content, criteria)
        logger.info(
            f"[QualityGate] status={result.status}, "
            f"score={result.score:.2f}, "
            f"issues={len(result.issues)}, "
            f"evidence_required={len(result.evidence_required)}"
        )
        return result

    def validate_chapter(
        self,
        chapter_content: str,
        context: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a generated chapter against all quality criteria.

        Convenience method that builds criteria from context.

        Args:
            chapter_content: The chapter content to validate
            context: Generation context with characters, previous_summary, etc.

        Returns:
            ValidationResult from RealityChecker
        """
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
        characters: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Check character consistency without full validation.

        Use this for quick character checks during generation.

        Args:
            content: Content to check
            characters: Character profiles

        Returns:
            Dict with consistent, issues, and evidence_required
        """
        if not self._reality_checker:
            return {"consistent": True, "issues": [], "evidence_required": []}

        return self._reality_checker.check_character_consistency(content, characters)

    def check_plot_coherence(
        self,
        content: str,
        previous_summary: str,
    ) -> Dict[str, Any]:
        """Check plot coherence without full validation.

        Use this for quick coherence checks during generation.

        Args:
            content: Content to check
            previous_summary: Previous chapter's summary

        Returns:
            Dict with coherent, issues, and evidence_required
        """
        if not self._reality_checker:
            return {"coherent": True, "issues": [], "evidence_required": []}

        return self._reality_checker.check_plot_coherence(content, previous_summary)

    def get_reality_checker(self) -> Optional[RealityChecker]:
        """Get the RealityChecker instance for direct access.

        Returns:
            RealityChecker instance or None if disabled
        """
        return self._reality_checker
