"""EvaluateStage — single-pass outline quality evaluation."""

import json
import logging
from dataclasses import dataclass

from crewai.content.novel.pipeline_state import PipelineState

from .stage_runner import StageRunner

logger = logging.getLogger(__name__)

# Criteria evaluated and the weight each carries in the composite score.
_CRITERIA: tuple[str, ...] = (
    "plot_coherence",
    "character_development",
    "pacing",
    "originality",
)

_PASS_THRESHOLD: float = 6.5

_SYSTEM_PROMPT = """\
You are an expert literary editor with deep experience evaluating novel outlines.
Your task is to assess the quality of the provided outline across four dimensions.
Respond ONLY with a single JSON object — no prose, no markdown fences.
"""

_USER_PROMPT_TEMPLATE = """\
Please evaluate the following novel outline and return a JSON object with this exact shape:

{{
  "plot_coherence": <integer 0-10>,
  "character_development": <integer 0-10>,
  "pacing": <integer 0-10>,
  "originality": <integer 0-10>,
  "comments": {{
    "plot_coherence": "<one sentence rationale>",
    "character_development": "<one sentence rationale>",
    "pacing": "<one sentence rationale>",
    "originality": "<one sentence rationale>"
  }}
}}

Scoring guide:
  0-4  : Poor — significant structural or creative problems
  5-6  : Adequate — workable but needs improvement
  7-8  : Good — solid craft with minor issues
  9-10 : Excellent — exceptional quality

--- OUTLINE START ---
{outline_json}
--- OUTLINE END ---
"""


@dataclass
class EvaluateStage(StageRunner):
    """Evaluate outline quality with a single LLM pass.

    Reads:  ``state.plot_data`` (populated by OutlineStage)
    Writes: ``state.outline_evaluation`` — full evaluation dict
            ``state.evaluation_passed``  — True iff average score >= 6.5
    """

    name: str = "evaluate"

    def validate_input(self, state: PipelineState) -> bool:
        """Require non-empty plot_data before running."""
        if not state.plot_data:
            logger.error("[%s] validate_input failed: state.plot_data is empty", self.name)
            return False
        return True

    def run(self, state: PipelineState) -> PipelineState:
        """Perform a single evaluation pass and annotate *state* with results.

        This method intentionally does NOT loop or retry — it evaluates once,
        records the result, and returns the updated state regardless of whether
        the outline passes the threshold.
        """
        if not self.validate_input(state):
            raise ValueError(
                f"[{self.name}] Input validation failed: plot_data must be non-empty"
            )

        outline_json = json.dumps(state.plot_data, ensure_ascii=False, indent=2)
        user_prompt = _USER_PROMPT_TEMPLATE.format(outline_json=outline_json)

        logger.info("[%s] Requesting outline evaluation from LLM …", self.name)
        raw_response = self._call_llm(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.3,  # low temperature for deterministic scoring
        )

        evaluation = self._parse_evaluation(raw_response)
        scores = self._extract_scores(evaluation)
        average = sum(scores.values()) / len(scores) if scores else 0.0
        passed = average >= _PASS_THRESHOLD

        evaluation["average_score"] = round(average, 2)
        evaluation["passed"] = passed
        evaluation["pass_threshold"] = _PASS_THRESHOLD

        self._log_evaluation(evaluation, scores, average, passed)

        # Use PipelineState's own helper so stage bookkeeping stays consistent.
        state.set_evaluation_result(evaluation, passed)
        return state

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_evaluation(self, raw: str) -> dict:
        """Parse LLM response into an evaluation dict, with graceful fallback."""
        try:
            return self._parse_json_response(raw)
        except Exception as exc:
            logger.warning(
                "[%s] Failed to parse LLM response as JSON (%s). "
                "Storing raw response under 'raw_response' key.",
                self.name,
                exc,
            )
            return {"raw_response": raw, "parse_error": str(exc)}

    def _extract_scores(self, evaluation: dict) -> dict[str, float]:
        """Pull per-criterion numeric scores out of the evaluation dict."""
        scores: dict[str, float] = {}
        for criterion in _CRITERIA:
            value = evaluation.get(criterion)
            if isinstance(value, (int, float)):
                scores[criterion] = float(value)
            else:
                logger.warning(
                    "[%s] Missing or non-numeric score for criterion '%s' (got %r); defaulting to 0",
                    self.name,
                    criterion,
                    value,
                )
                scores[criterion] = 0.0
        return scores

    def _log_evaluation(
        self,
        evaluation: dict,
        scores: dict[str, float],
        average: float,
        passed: bool,
    ) -> None:
        """Emit structured log lines for the evaluation results."""
        logger.info(
            "[%s] Evaluation complete — average: %.2f / 10.0 — %s (threshold %.1f)",
            self.name,
            average,
            "PASSED" if passed else "FAILED",
            _PASS_THRESHOLD,
        )
        for criterion, score in scores.items():
            comment = (evaluation.get("comments") or {}).get(criterion, "")
            logger.info(
                "[%s]   %-25s %4.1f/10  %s",
                self.name,
                criterion + ":",
                score,
                comment,
            )
