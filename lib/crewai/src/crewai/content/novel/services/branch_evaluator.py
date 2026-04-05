"""BranchEvaluator - Compares multiple narrative paths using ReaderSwarm metrics.

Allows the AI to generate alternative versions of a plot point or chapter
and evaluate which one yields better audience engagement or logic consistency.
"""

from typing import Any, List, Dict
import logging
import json
import re

logger = logging.getLogger(__name__)


class BranchEvaluator:
    """Service for performing A/B testing on different narrative branches."""

    def __init__(self, config: Dict[str, Any], reader_swarm: Any):
        self.config = config
        self.reader_swarm = reader_swarm

    def evaluate_and_choose(self, branches: List[Dict[str, Any]], chapter_num: int) -> Dict[str, Any]:
        """[Legacy] Automated choice logic."""
        evals = self.run_evaluation(branches, chapter_num)
        winner = max(evals, key=lambda x: x['score'])
        return {"winner_id": winner['branch_id'], "comparison_summary": self._generate_comparison_text(evals), "evaluations": evals}

    def run_evaluation(self, branches: List[Dict[str, Any]], chapter_num: int) -> List[Dict[str, Any]]:
        """Run reader swarm on all branches and return raw data."""
        evaluations = []
        for branch in branches:
            logger.info(f"Auditing Branch {branch['id']} for Chapter {chapter_num}...")
            report = self.reader_swarm.evaluate_chapter(branch['content'], chapter_num)
            evaluations.append({
                "branch_id": branch['id'],
                "score": report.get("average_score", 0),
                "highlight": report.get("highlight_moment", "None"),
                "comments": [f"{f['persona']}: {f['comment']}" for f in report.get("feedbacks", [])[:2]],
                "content_preview": branch['content'][:300] + "..."
            })
        return evaluations

    def prepare_choice_ui(self, evaluations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format evaluations for the ask_user choice UI."""
        options = []
        for ev in evaluations:
            options.append({
                "label": f"版本 {ev['branch_id']}",
                "description": f"得分: {ev['score']} | 亮点: {ev['highlight']} | 评价: {'; '.join(ev['comments'])}"
            })
        return options

    def _generate_comparison_text(self, evaluations: List[Dict]) -> str:
        text = "### 剧情分支 A/B 测试报告\n"
        for ev in evaluations:
            text += f"- **版本 {ev['branch_id']}**: 得分 {ev['score']} | 亮点: {ev['highlight']}\n"
        return text
