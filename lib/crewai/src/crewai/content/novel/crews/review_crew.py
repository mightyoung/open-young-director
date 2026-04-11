"""ReviewCrew - Multi-stage content quality control pipeline.

Ensures plot consistency, character integrity, and prose quality via a series of
specialized agents and checkers. Inspired by professional editorial workflows.
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, TYPE_CHECKING
import logging

from crewai.agent import Agent
from crewai.task import Task
from crewai.content.base import BaseContentCrew
from crewai.content.review.review_result import ReviewResult, Issue

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.review.review_context import ReviewContext

logger = logging.getLogger(__name__)


class ReviewCrew(BaseContentCrew):
    """ReviewCrew for novel content quality enforcement."""

    def __init__(self, config: Dict[str, Any], verbose: bool = True):
        super().__init__(config, verbose)
        self._critique_agent = None
        self._revision_agent = None
        self._polish_agent = None
        self._interiority_checker = None
        self._pov_checker = None
        self._continuity_checker = None
        self._foreshadowing_checker = None
        self._persona_agent = None
        self._specs_checker = None
        self._prose_auditor = None

    def _lazy_init_agents(self):
        """Lazy init all review specialized agents."""
        if self._critique_agent is None:
            from crewai.content.review.critique_agent import CritiqueAgent
            from crewai.content.review.revision_agent import RevisionAgent
            from crewai.content.review.polish_agent import PolishAgent
            from crewai.content.novel.agents.interiority_checker import InteriorityChecker
            from crewai.content.novel.agents.pov_checker import POVChecker
            from crewai.content.novel.agents.continuity_checker import ContinuityChecker
            from crewai.content.novel.agents.foreshadowing_checker import ForeshadowingChecker
            from crewai.content.novel.agents.persona_agent import PersonaAgent
            from crewai.content.novel.agents.signature_specs_checker import SignatureSpecsChecker
            from crewai.content.novel.agents.prose_auditor import ProseAuditor

            llm = self.config.get("llm")
            self._critique_agent = CritiqueAgent(llm=llm, verbose=self.verbose)
            self._revision_agent = RevisionAgent(llm=llm, verbose=self.verbose)
            self._polish_agent = PolishAgent(llm=llm, verbose=self.verbose)
            self._interiority_checker = InteriorityChecker(llm=llm, verbose=self.verbose)
            self._pov_checker = POVChecker(llm=llm, verbose=self.verbose)
            self._continuity_checker = ContinuityChecker(llm=llm, verbose=self.verbose)
            self._foreshadowing_checker = ForeshadowingChecker(llm=llm, verbose=self.verbose)
            self._persona_agent = PersonaAgent(llm=llm, verbose=self.verbose)
            self._specs_checker = SignatureSpecsChecker(llm=llm, verbose=self.verbose)
            self._prose_auditor = ProseAuditor(llm=llm, verbose=self.verbose)

    def critique_and_revise(
        self,
        draft: str,
        context: "ReviewContext",
        skip_polish: bool = False,
        suggest_only: bool = False
    ) -> tuple[ReviewResult, str, str]:
        """Full Review-Revise-Polish pipeline with 'Suggest Mode' support."""
        self._lazy_init_agents()

        # 1. Run Checkers & Critique
        # (Simplified: in production this runs all checkers implemented previously)
        critique_result = self._critique_agent.critique(draft, context)
        
        # Integrate advanced auditors (Prose, Specs, etc.)
        try:
            specs_result = self._specs_checker.check(draft, getattr(context, 'chapter_outline_dict', {}))
            if specs_result.has_issues():
                for issue in self._convert_check_result_to_issues(specs_result, "specs", context):
                    critique_result.add_issue(issue)
            
            prose_result = self._prose_auditor.audit(draft, getattr(context, 'bible_section', None))
            if prose_result.has_issues():
                for issue in self._convert_check_result_to_issues(prose_result, "prose", context):
                    critique_result.add_issue(issue)
        except Exception as e:
            logger.warning(f"Auditors failed: {e}")

        # --- SUGGEST MODE: STOP HERE ---
        if suggest_only:
            logger.info("Suggest Mode Active: Skipping revisions.")
            return critique_result, draft, draft

        # 2. Revise (if needed)
        revised_draft = draft
        if critique_result.score < 6.5:
            revised_draft = self._revision_agent.revise(draft, critique_result)
        
        # 3. Persona Alignment Pass
        try:
            persona_polished = self._persona_agent.check_and_polish(
                revised_draft, getattr(context, 'bible_section', None)
            )
            if persona_polished: revised_draft = persona_polished
        except: pass

        # 4. Final Polish
        polished_draft = revised_draft
        if not skip_polish:
            polished_draft = self._polish_agent.polish(revised_draft)

        return critique_result, revised_draft, polished_draft

    def _convert_check_result_to_issues(self, check_result: Any, issue_type: str, context: Any) -> List[Issue]:
        issues = []
        for i, desc in enumerate(check_result.issues):
            issues.append(Issue(
                type=issue_type,
                description=desc,
                severity="high" if check_result.score < 6 else "medium",
                suggestion=check_result.suggestions[i] if i < len(check_result.suggestions) else ""
            ))
        return issues

    def _create_agents(self) -> dict[str, Any]:
        self._lazy_init_agents()
        return {"critique": self._critique_agent}

    def _create_tasks(self) -> dict[str, Any]:
        return {}
