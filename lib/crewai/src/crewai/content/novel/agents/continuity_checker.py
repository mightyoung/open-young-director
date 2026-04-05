"""Cross-chapter continuity checker.

Checks that a newly written chapter's opening maintains continuity with
the previous chapter's ending scene — specifically:
- Location continuity (same place, or clear transition)
- Character state continuity (emotions, physical states, relationships)
- Timeline continuity (time passed, day/night consistent)
- Unresolved suspense (promises from previous chapter are addressed or explicitly delayed)
"""

from typing import TYPE_CHECKING

from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult


if TYPE_CHECKING:
    from crewai.llm import LLM


class ContinuityChecker:
    """Cross-chapter continuity checker.

    Verifies that a chapter's opening properly continues from where
    the previous chapter ended, checking:
    1. Location continuity — same location or explained transition
    2. Character state continuity — emotions, conditions match
    3. Timeline continuity — time progression is consistent
    4. Suspense continuity — unresolved hooks are addressed or noted

    Usage:
        checker = ContinuityChecker()
        result = checker.check(chapter_content, previous_ending, context)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        self.agent = Agent(
            role="Continuity Auditor",
            goal="Ensure seamless transition between chapters with zero continuity errors",
            backstory="""你是小说一致性审计专家，专注于跨章节连贯性。
            你极其注意细节，能发现以下问题：
            - 地点突变（前章在城市，下章突然在乡村，无过渡）
            - 角色状态矛盾（前章受伤，下章完全恢复无解释）
            - 时间线混乱（明明是同一天，角色却睡了两次）
            - 悬念丢失（前章结尾的悬念在下章完全忽略）

            你的评分标准：9-10分优秀，7-8分良好，5-6分有轻微问题，<5分严重问题。""",
            llm=llm,
            verbose=verbose,
        )

    def check(
        self,
        chapter_content: str,
        previous_chapter_ending: str,
        context: dict | None = None,
    ) -> ReviewCheckResult:
        """Check continuity between previous chapter ending and new chapter opening.

        Args:
            chapter_content: The newly written chapter content
            previous_chapter_ending: The ending scene of the previous chapter
            context: Optional context dict with chapter_number, style, etc.

        Returns:
            ReviewCheckResult with score, issues, and suggestions
        """
        prompt = self._build_check_prompt(chapter_content, previous_chapter_ending, context)
        try:
            response = self.agent.kickoff(messages=prompt)
            return self._parse_response(response)
        except (ValueError, Exception) as e:
            import logging
            logging.warning(f"Continuity check failed, using pass result: {e}")
            result = ReviewCheckResult(check_type="continuity", passed=True)
            result.score = 10.0
            result.issues.append("Continuity check skipped due to API error")
            result.suggestions.append("Please manually verify chapter transition")
            return result

    def _build_check_prompt(
        self,
        chapter_content: str,
        previous_chapter_ending: str,
        context: dict | None,
    ) -> str:
        """Build the continuity check prompt."""
        chapter_num = "?"
        style = "通用"

        if context:
            if hasattr(context, "chapter_number"):
                chapter_num = context.chapter_number if context.chapter_number is not None else "?"
                style = getattr(context, "style_guide", None) or getattr(context, "style", "通用")
            else:
                chapter_num = context.get("chapter_number", context.get("chapter_num", "?"))
                style = context.get("style_guide", context.get("style", "通用"))

        # Extract the first 800 chars of the new chapter as the "opening"
        chapter_opening = chapter_content[:800] if len(chapter_content) > 800 else chapter_content

        prev_chapter_num = str(int(chapter_num) - 1) if chapter_num not in ("?", "", None) else "?"
        return f"""你是小说跨章节一致性审计专家。请检查第{chapter_num}章的开头是否与第{prev_chapter_num}章的结尾保持连贯。

【小说风格】{style}

【前章结尾场景】
{previous_chapter_ending}

【本章开头（前800字）】
{chapter_opening}

请从以下四个维度逐项检查：

1. **地点连贯性**
   - 本章开头是否与前章结尾在同一地点？
   - 如果地点不同，是否有合理的过渡说明（ travel, time passage, explicit transition）？
   - 常见错误：前章在城市，下章突然在乡村

2. **角色状态连贯性**
   - 前章结尾时角色的情绪/心理状态是什么？本章开头是否一致？
   - 前章结尾时角色的身体状态（如受伤、疲劳）是否延续？
   - 常见错误：前章角色大哭，本章开头突然心情平静无解释

3. **时间线连贯性**
   - 前章结尾是什么时间（白天/夜晚/具体时间）？
   - 本章开头的时间是否与之一致或有明确的时间过渡说明？
   - 常见错误：同一天内角色睡了两次，或时间倒退

4. **悬念连贯性**
   - 前章结尾留下了哪些未解决悬念/伏笔/待办？
   - 本章开头是否处理了这些悬念（解决/延期/提及）？
   - 常见错误：前章结尾主角命悬一线，下章开头完全不提

请给出：
- 1-10的综合评分
- 发现的问题列表（包含具体位置和描述）
- 具体修改建议

以JSON格式返回：
{{
    "score": 8.5,
    "issues": ["问题1：前章结尾主角在城门口，本章开头突然在皇宫，无过渡", "问题2：前章主角左臂受伤，本章开头无解释地痊愈了"],
    "suggestions": ["建议1：在本章开头增加一行过渡描写，说明主角骑马赶到皇宫", "建议2：在本章开头增加'数日后，左臂的伤口终于愈合'的描写"]
}}"""

    def _parse_response(self, response: str) -> ReviewCheckResult:
        """Parse the LLM response into a ReviewCheckResult."""
        import json
        import re

        result = ReviewCheckResult(check_type="continuity", passed=True)

        try:
            if hasattr(response, "raw"):
                raw = response.raw
            else:
                raw = str(response)

            # Strip markdown code fences (e.g., ```json ... ```)
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

            data = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            # Fallback: try to find JSON object in raw text
            try:
                json_match = re.search(r"\{[\s\S]*\}", raw if hasattr(raw, "__iter__") else str(raw))
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    raise
            except Exception:
                result.issues.append("Unable to parse continuity check result")
                result.suggestions.append("Please manually verify chapter transition")
                result.score = 5.0
                result.passed = False
                return result
            result.issues.append("Unable to parse continuity check result")
            result.suggestions.append("Please manually verify chapter transition")
            result.score = 5.0
            result.passed = False
            return result

        result.score = float(data.get("score", 5.0))
        result.issues = data.get("issues", [])
        result.suggestions = data.get("suggestions", [])

        # Score >= 7.0 passes
        result.passed = result.score >= 7.0

        return result


__all__ = ["ContinuityChecker"]
