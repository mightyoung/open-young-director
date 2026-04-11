"""大纲评估器 (Outline Evaluator)

评估大纲质量，检查世界观一致性、情节完整性、Strand Weave 比例等。
使用 Evaluator-Optimizer 模式：评估不通过时触发修正循环。

使用示例:
    evaluator = OutlineEvaluator()
    result = evaluator.evaluate(world_data, plot_data)
    if not result.passed:
        revised = evaluator.revise(world_data, plot_data, result)
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult

if TYPE_CHECKING:
    from crewai.llm import LLM


class OutlineEvaluator:
    """大纲评估器

    评估维度：
    1. 世界观一致性 - 势力/地点/力量体系无矛盾
    2. 情节完整性 - 主线事件齐全，高潮点分布合理
    3. Strand Weave 比例 - Quest/Fire/Constellation 60±10% / 25±10% / 15±10%
    4. 卷结构合理性 - 每卷有独立弧线，首尾呼应
    5. 伏笔一致性 - Dianting 铺设/回收计划（铺设章节N → 回收 N+5~20）

    使用示例:
        evaluator = OutlineEvaluator()
        result = evaluator.evaluate(world_data, plot_data)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化大纲评估器

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.llm = llm
        self.verbose = verbose
        self.agent: Agent | None = None

    def _get_agent(self) -> Agent:
        """按需初始化评估 Agent，避免在只做本地启发式评估时触发 LLM 依赖。"""
        if self.agent is None:
            self.agent = Agent(
                role="故事架构评审专家",
                goal="确保大纲质量达到专业标准",
                backstory="""你是一个资深的故事架构师，拥有丰富的剧本评审经验。
                你精通叙事结构、世界观构建、情节设计，能够从宏观角度评估故事大纲的质量。
                你尤其擅长发现逻辑漏洞、节奏问题和结构失衡。
                你的评审标准严格但建设性，重在帮助故事达到最佳状态。""",
                verbose=self.verbose,
                llm=self.llm,
            )
        return self.agent

    def check(
        self,
        world_data: dict,
        plot_data: dict,
        context: dict | None = None,
    ) -> ReviewCheckResult:
        """Backward-compatible alias used by service-layer code."""
        return self.evaluate(world_data, plot_data, context)

    def evaluate(
        self,
        world_data: dict,
        plot_data: dict,
        context: dict | None = None,
    ) -> ReviewCheckResult:
        """评估大纲质量

        Args:
            world_data: 世界观数据（包含 factions, key_locations, power_system 等）
            plot_data: 情节规划数据（包含 volumes, main_strand, sub_strands, high_points 等）
            context: 可选的上下文信息

        Returns:
            ReviewCheckResult: 评估结果，包含通过/失败状态、问题列表、修改建议
        """
        result = ReviewCheckResult(check_type="outline", passed=True)

        dimensions = {
            "world_consistency": self._score_world_consistency(world_data),
            "plot_completeness": self._score_plot_completeness(plot_data),
            "strand_weave_ratio": self._score_strand_weave_ratio(plot_data),
            "volume_structure": self._score_volume_structure(plot_data),
            "foreshadowing": self._score_foreshadowing(plot_data),
        }

        issues: list[str] = []
        suggestions: list[str] = []
        scores: list[float] = []
        dimension_breakdown: dict[str, dict[str, object]] = {}

        for name, (score, dimension_issues, dimension_suggestions) in dimensions.items():
            scores.append(score)
            issues.extend(dimension_issues)
            suggestions.extend(dimension_suggestions)
            dimension_breakdown[name] = {
                "score": round(score, 2),
                "issues": dimension_issues,
            }

        result.score = round(sum(scores) / len(scores), 2) if scores else 0.0
        result.issues = issues
        result.suggestions = suggestions

        # Keep the result self-describing for callers that inspect extra attrs.
        result.dimensions = dimension_breakdown  # type: ignore[attr-defined]

        critical = any(score < 5.0 for score in scores)
        result.passed = result.score >= 7.0 and not critical
        return result

    def revise(
        self,
        world_data: dict,
        plot_data: dict,
        evaluation: ReviewCheckResult,
        context: dict | None = None,
    ) -> dict:
        """根据评估反馈修正大纲

        Args:
            world_data: 世界观数据
            plot_data: 情节规划数据
            evaluation: 评估结果（包含问题和建议）
            context: 可选的上下文信息

        Returns:
            dict: 修正后的 plot_data
        """
        prompt = self._build_revision_prompt(world_data, plot_data, evaluation, context)
        response = self._get_agent().kickoff(messages=prompt)
        return self._parse_revision_response(response)

    def evaluate_and_revise(
        self,
        world_data: dict,
        plot_data: dict,
        max_retries: int = 2,
        context: dict | None = None,
    ) -> tuple[ReviewCheckResult, dict]:
        """评估-修正循环（Evaluator-Optimizer Loop）

        Args:
            world_data: 世界观数据
            plot_data: 情节规划数据
            max_retries: 最大修正次数
            context: 可选的上下文信息

        Returns:
            tuple: (最终评估结果, 修正后的 plot_data)
        """
        current_plot = plot_data

        for attempt in range(max_retries + 1):
            evaluation = self.evaluate(world_data, current_plot, context)

            if evaluation.passed:
                return evaluation, current_plot

            if attempt < max_retries:
                # 修正并重试
                current_plot = self.revise(world_data, current_plot, evaluation, context)

        # 最终结果（无论是否通过）
        return evaluation, current_plot

    def _build_evaluation_prompt(
        self,
        world_data: dict,
        plot_data: dict,
        context: dict | None,
    ) -> str:
        """构建评估提示词"""
        world_str = self._format_world(world_data)
        plot_str = self._format_plot(plot_data)

        return f"""请严格评估以下故事大纲的质量。

## 世界观
{world_str}

## 情节规划
{plot_str}

## 评估维度（每项必须检查）

### 1. 世界观一致性
- 势力(factions)之间是否有矛盾？
- 地点(locations)之间是否有逻辑冲突？
- 力量体系(power_system)是否自洽？

### 2. 情节完整性
- 主线(main_strand)事件是否齐全？
- 高潮点(high_points)分布是否合理？（前中后期各至少一个）
- 每卷是否有明确的主题弧线？

### 3. Strand Weave 比例
- Quest/Fire/Constellation 比例是否合理？
  - Quest (主线冲突): 60±10%
  - Fire (情感线): 25±10%
  - Constellation (伏笔线): 15±10%
- 检查 foreshadowing_strands、emotional_strands、main_strand 的分配

### 4. 卷结构合理性
- 每卷是否有独立的起承转合？
- 卷与卷之间是否有呼应？
- 卷的字数分配是否均衡？

### 5. 伏笔一致性（Dianting）
- 检查 foreshadowing_strands 的铺设
- 伏笔铺设章节和回收章节的间隔是否合理？（N 到 N+5~20）
- 是否有明显的伏笔遗漏？

请给出：
- 每项的评分 (1-10)
- 发现的问题列表（具体到哪个势力/地点/章节）
- 通过/失败状态

以JSON格式返回：
{{
    "score": 7.5,
    "passed": true,
    "dimensions": {{
        "world_consistency": {{"score": 8, "issues": []}},
        "plot_completeness": {{"score": 7, "issues": ["高潮点分布偏少"]}},
        "strand_weave_ratio": {{"score": 8, "issues": []}},
        "volume_structure": {{"score": 7, "issues": ["第二卷弧线较弱"]}},
        "foreshadowing": {{"score": 6, "issues": ["第3章伏笔未回收"]}}
    }},
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"]
}}

注意：只有当所有维度都达到6分以上，且没有致命严重问题时，才能返回 passed=true。
如果总分在7分以上，即使个别维度略低，也应返回 passed=true。
评估的目的是帮助改进，而不是阻挡进度。如果大纲整体可用，应返回 passed=true。"""

    def _build_revision_prompt(
        self,
        world_data: dict,
        plot_data: dict,
        evaluation: ReviewCheckResult,
        context: dict | None,
    ) -> str:
        """构建修正提示词"""
        world_str = self._format_world(world_data)
        plot_str = self._format_plot(plot_data)

        issues_str = "\n".join(f"- {issue}" for issue in evaluation.issues)
        suggestions_str = "\n".join(f"- {s}" for s in evaluation.suggestions)

        return f"""根据以下评估反馈，修正故事大纲。

## 当前世界观
{world_str}

## 当前情节规划
{plot_str}

## 评估反馈
问题列表：
{issues_str}

修改建议：
{suggestions_str}

请根据反馈修正情节规划，重点解决以下问题：
1. 修正指出的逻辑矛盾
2. 补充遗漏的情节元素
3. 调整不合理的比例和分布

以JSON格式返回修正后的 plot_data（完整结构，不要省略）：
{{
    "series_overview": "...",
    "total_chapters": ...,
    "volumes": [...],
    "main_strand": {{...}},
    "sub_strands": [...],
    "foreshadowing_strands": [...],
    "emotional_strands": [...],
    "weave_points": [...],
    "high_points": [...]
}}"""

    def _format_world(self, world_data: dict) -> str:
        """格式化世界观数据"""
        import json

        # 截断过长的数据以避免上下文溢出
        def truncate(obj, max_len=500):
            s = json.dumps(obj, ensure_ascii=False, default=str)
            if len(s) > max_len:
                return s[:max_len] + "..."
            return s

        return truncate(world_data)

    def _format_plot(self, plot_data: dict) -> str:
        """格式化情节数据"""
        import json

        # 截断过长的数据以避免上下文溢出
        def truncate(obj, max_len=2000):
            s = json.dumps(obj, ensure_ascii=False, default=str)
            if len(s) > max_len:
                return s[:max_len] + "..."
            return s

        return truncate(plot_data)

    def _score_world_consistency(self, world_data: dict) -> tuple[float, list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        if not world_data:
            return 3.0, ["世界观数据为空"], ["补充世界名称、力量体系、地理与势力设定"]

        score = 10.0
        required_fields = ("name", "description", "world_constraints", "geography", "factions")
        missing = [field for field in required_fields if not world_data.get(field)]
        if missing:
            score -= min(3.0, 0.8 * len(missing))
            issues.append(f"世界观字段缺失: {', '.join(missing)}")
            suggestions.append("补足世界观基础字段，避免设定空洞")

        power_system = world_data.get("power_system") or world_data.get("power_system_name")
        if not power_system:
            score -= 1.5
            issues.append("缺少力量体系或修炼体系名称")
            suggestions.append("补充力量体系与升级规则")

        geography = world_data.get("geography", [])
        factions = world_data.get("factions", [])
        if not geography or not factions:
            score -= 0.5
            issues.append("地理与势力结构不够完整")
            suggestions.append("明确关键地点与势力分布")

        return max(0.0, score), issues, suggestions

    def _score_plot_completeness(self, plot_data: dict) -> tuple[float, list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        if not plot_data:
            return 3.0, ["情节数据为空"], ["补充主线、转折点和角色列表"]

        score = 10.0
        plot_arcs = plot_data.get("plot_arcs", [])
        turning_points = plot_data.get("turning_points", [])
        themes = plot_data.get("themes", [])
        main_characters = plot_data.get("main_characters", [])

        if not plot_arcs:
            score -= 2.0
            issues.append("缺少主线剧情弧 plot_arcs")
            suggestions.append("拆分出至少一条清晰主线")
        if not turning_points:
            score -= 2.0
            issues.append("缺少关键转折点 turning_points")
            suggestions.append("补足前中后期转折点")
        if not main_characters:
            score -= 1.0
            issues.append("缺少主要角色 main_characters")
            suggestions.append("补全角色卡与成长线")
        if not themes:
            score -= 1.0
            issues.append("缺少主题关键词 themes")
            suggestions.append("明确作品主题，以免情节发散")

        return max(0.0, score), issues, suggestions

    def _score_strand_weave_ratio(self, plot_data: dict) -> tuple[float, list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        strands = self._extract_strands(plot_data)
        if not strands:
            return 6.0, ["未能识别 Strand Weave 结构"], ["补充主线/支线/伏笔线索信息"]

        total_events = sum(max(1, len(self._strand_events(strand))) for strand in strands)
        if total_events <= 0:
            return 5.0, ["Strand 数据缺少事件"], ["为每条线索补充 main_events"]

        ratios: dict[str, float] = {}
        for strand in strands:
            strand_type = str(strand.get("strand_type", "main")).lower()
            count = max(1, len(self._strand_events(strand)))
            ratios[strand_type] = ratios.get(strand_type, 0.0) + count / total_events

        main_ratio = ratios.get("main", 0.0)
        emotional_ratio = ratios.get("romance", 0.0) + ratios.get("fire", 0.0)
        foreshadow_ratio = ratios.get("sub", 0.0) + ratios.get("subplot", 0.0) + ratios.get("constellation", 0.0)

        score = 10.0
        if not 0.50 <= main_ratio <= 0.70:
            score -= 2.0
            issues.append(f"主线比例异常: {main_ratio:.0%}")
            suggestions.append("将主线控制在约60%上下")
        if emotional_ratio and not 0.15 <= emotional_ratio <= 0.35:
            score -= 1.0
            issues.append(f"情感线比例异常: {emotional_ratio:.0%}")
            suggestions.append("将情感线控制在约25%上下")
        if foreshadow_ratio and not 0.05 <= foreshadow_ratio <= 0.25:
            score -= 1.0
            issues.append(f"伏笔线比例异常: {foreshadow_ratio:.0%}")
            suggestions.append("将伏笔线控制在约15%上下")

        return max(0.0, score), issues, suggestions

    def _score_volume_structure(self, plot_data: dict) -> tuple[float, list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        volumes = plot_data.get("volumes", []) or plot_data.get("volume_outlines", [])
        if not volumes:
            if plot_data.get("plot_arcs"):
                return 7.0, ["缺少分卷结构 volumes"], ["为主线拆分分卷大纲"]
            return 5.0, ["缺少分卷结构 volumes"], ["为故事添加分卷结构"]

        score = 10.0
        for idx, volume in enumerate(volumes, 1):
            if not isinstance(volume, dict):
                score -= 0.5
                issues.append(f"第{idx}卷结构格式不合法")
                continue

            title = volume.get("title", f"第{idx}卷")
            start = volume.get("start_chapter")
            end = volume.get("end_chapter")
            if start is None or end is None or int(end) < int(start):
                score -= 1.5
                issues.append(f"{title} 章节范围不完整或不合法")
                suggestions.append(f"修正 {title} 的起止章节")
            if not volume.get("chapters_summary") and not volume.get("chapter_summaries"):
                score -= 1.0
                issues.append(f"{title} 缺少章节概要")
                suggestions.append(f"为 {title} 补充章节概要")

        return max(0.0, score), issues, suggestions

    def _score_foreshadowing(self, plot_data: dict) -> tuple[float, list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        foreshadowing = plot_data.get("foreshadowing_strands", [])
        if not foreshadowing:
            if plot_data.get("turning_points"):
                return 6.0, ["缺少伏笔线索 foreshadowing_strands"], ["补充伏笔铺设与回收计划"]
            return 5.0, ["缺少伏笔与转折设计"], ["补充伏笔与回收节点"]

        score = 10.0
        for strand in foreshadowing:
            if not isinstance(strand, dict):
                continue
            setup = strand.get("setup_chapter") or strand.get("planted_chapter") or strand.get("start_chapter")
            payoff = strand.get("payoff_chapter") or strand.get("reveal_chapter") or strand.get("end_chapter")
            if setup and payoff:
                try:
                    gap = int(payoff) - int(setup)
                except Exception:
                    gap = 0
                if gap < 5:
                    score -= 1.0
                    issues.append(f"伏笔回收间隔过短: 第{setup}章 -> 第{payoff}章")
                    suggestions.append("伏笔回收间隔建议保持 N+5~20 章")
            else:
                score -= 0.5
                issues.append("存在缺少铺设/回收章节的伏笔条目")
                suggestions.append("为伏笔补全铺设与回收章节")

        return max(0.0, score), issues, suggestions

    @staticmethod
    def _extract_strands(plot_data: dict) -> list[dict]:
        strands: list[dict] = []
        for key in ("plot_arcs", "strands", "main_strands", "sub_strands", "foreshadowing_strands", "emotional_strands"):
            value = plot_data.get(key)
            if isinstance(value, list):
                strands.extend(item for item in value if isinstance(item, dict))
        return strands

    @staticmethod
    def _strand_events(strand: dict) -> list:
        events = strand.get("main_events")
        if isinstance(events, list):
            return events
        if "description" in strand and strand["description"]:
            return [strand["description"]]
        return []

    def _parse_response(self, response) -> ReviewCheckResult:
        """解析评估响应"""
        import json
        import re

        result = ReviewCheckResult(check_type="outline", passed=False)
        result.score = 7.0  # 默认中等分数

        try:
            raw_text = ""
            if hasattr(response, "raw"):
                raw_text = response.raw
            elif isinstance(response, str):
                raw_text = response
            else:
                raw_text = str(response)

            # 提取JSON
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(raw_text)

            result.score = float(data.get("score", 7.0))
            result.issues = data.get("issues", [])
            result.suggestions = data.get("suggestions", [])

            # 更宽松的通过条件：6分以上且没有致命问题
            fatal_issues = [i for i in result.issues if any(kw in i.lower() for kw in ["致命", "矛盾", "崩塌", "致命矛盾"])]
            if not fatal_issues and (result.score >= 6.0 or data.get("passed", False)):
                result.passed = True
            else:
                result.passed = bool(data.get("passed", False))

        except (json.JSONDecodeError, Exception) as e:
            result.issues.append(f"无法解析评估结果: {str(e)}")
            result.suggestions.append("请人工检查大纲质量")
            result.score = 5.0

        return result

    def _parse_revision_response(self, response) -> dict:
        """解析修正响应"""
        import json
        import re

        try:
            raw_text = ""
            if hasattr(response, "raw"):
                raw_text = response.raw
            elif isinstance(response, str):
                raw_text = response
            else:
                raw_text = str(response)

            # 提取JSON
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                return json.loads(json_match.group())

        except (json.JSONDecodeError, Exception):
            pass

        # 解析失败时返回原始响应
        return {"error": "revision_parse_failed", "raw": str(response)}
