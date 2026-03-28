"""FeedbackApplier - 基于用户反馈重新生成内容

根据用户反馈（自然语言 + 结构化指令）调整生成参数并重新生成内容。

使用示例:
    applier = FeedbackApplier(llm)
    new_outline = applier.apply_outline_feedback(
        original_outline=outline_data,
        feedback=structured_feedback,
    )
"""

import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM

logger = logging.getLogger(__name__)


class FeedbackApplier:
    """基于用户反馈调整和重新生成内容"""

    def __init__(self, llm: "LLM" = None):
        """初始化 FeedbackApplier

        Args:
            llm: LLM 实例，用于生成修改后的内容
        """
        self._llm = llm

    def apply_outline_feedback(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """根据反馈调整大纲

        Args:
            original_outline: 原始大纲 {world, plot}
            feedback: 结构化反馈，包含 character_adjustments, plot_adjustments 等

        Returns:
            调整后的大纲
        """
        if not feedback:
            return original_outline

        char_adj = feedback.get("character_adjustments", [])
        plot_adj = feedback.get("plot_adjustments", [])
        tone_adj = feedback.get("tone_adjustments", [])
        summary = feedback.get("summary", "")

        # 如果反馈为空，直接返回原大纲
        if not any([char_adj, plot_adj, tone_adj]) or not summary:
            logger.info("No specific adjustments found, returning original outline")
            return original_outline

        # 使用 LLM 根据反馈调整大纲
        if self._llm:
            return self._apply_feedback_with_llm(original_outline, feedback)
        else:
            return self._apply_feedback_local(original_outline, feedback)

    def _apply_feedback_with_llm(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """使用 LLM 根据反馈调整大纲"""
        prompt = f"""你是一个小说大纲调整助手。

原始大纲:
{self._format_dict(original_outline)}

用户反馈:
{feedback.get('summary', '')}

具体调整:
{self._format_feedback(feedback)}

请根据用户反馈修改大纲，返回调整后的完整大纲（JSON格式）。
只返回 JSON，不要解释。"""

        try:
            response = self._llm.call(prompt)
            import json
            import re

            # 提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM feedback application failed: {e}")

        return original_outline

    def _apply_feedback_local(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """本地模式：简单调整大纲（不调用 LLM）"""
        char_adj = feedback.get("character_adjustments", [])

        # 本地模式只能处理简单的角色调整
        world_data = original_outline.get("world", {}).copy()
        plot_data = original_outline.get("plot", {}).copy()

        for adj in char_adj:
            name = adj.get("name", "")
            aspect = adj.get("aspect", "")
            to_value = adj.get("to", "")

            if not name or not aspect:
                continue

            # 在 world_data 中查找并修改角色
            characters = world_data.get("characters", [])
            for char in characters:
                if char.get("name") == name:
                    if aspect in char:
                        char[aspect] = to_value
                        logger.info(f"Adjusted {name}.{aspect} to '{to_value}'")

        return {
            "world": world_data,
            "plot": plot_data,
        }

    def apply_volume_feedback(
        self,
        original_volumes: list,
        feedback: dict,
    ) -> list:
        """根据反馈调整分卷大纲

        Args:
            original_volumes: 原始分卷大纲列表
            feedback: 结构化反馈

        Returns:
            调整后的分卷大纲
        """
        if not feedback:
            return original_volumes

        if self._llm:
            return self._apply_volume_feedback_with_llm(original_volumes, feedback)
        else:
            return self._apply_volume_feedback_local(original_volumes, feedback)

    def _apply_volume_feedback_with_llm(
        self,
        original_volumes: list,
        feedback: dict,
    ) -> list:
        """使用 LLM 根据反馈调整分卷大纲"""
        prompt = f"""你是一个小说分卷大纲调整助手。

原始分卷大纲:
{self._format_dict({'volumes': original_volumes})}

用户反馈:
{feedback.get('summary', '')}

具体调整:
{self._format_feedback(feedback)}

请根据用户反馈修改分卷大纲，返回调整后的完整分卷大纲（JSON格式）。
只返回 JSON，不要解释。"""

        try:
            response = self._llm.call(prompt)
            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("volumes", original_volumes)
        except Exception as e:
            logger.warning(f"LLM volume feedback application failed: {e}")

        return original_volumes

    def _apply_volume_feedback_local(
        self,
        original_volumes: list,
        feedback: dict,
    ) -> list:
        """本地模式：简单调整分卷大纲"""
        plot_adj = feedback.get("plot_adjustments", [])
        # 本地模式暂时不做处理
        return original_volumes

    def apply_chapter_summary_feedback(
        self,
        original_summaries: list,
        feedback: dict,
        chapter_num: int | None = None,
    ) -> list:
        """根据反馈调整章节概要

        Args:
            original_summaries: 原始章节概要列表
            feedback: 结构化反馈
            chapter_num: 可选，指定要修改的章节号（从 1 开始）

        Returns:
            调整后的章节概要
        """
        if not feedback:
            return original_summaries

        if self._llm:
            return self._apply_summary_feedback_with_llm(original_summaries, feedback, chapter_num)
        else:
            return self._apply_summary_feedback_local(original_summaries, feedback, chapter_num)

    def _apply_summary_feedback_with_llm(
        self,
        original_summaries: list,
        feedback: dict,
        chapter_num: int | None = None,
    ) -> list:
        """使用 LLM 根据反馈调整章节概要"""
        target = None
        if chapter_num and 1 <= chapter_num <= len(original_summaries):
            target = original_summaries[chapter_num - 1]

        prompt = f"""你是一个小说章节概要调整助手。

{'目标章节概要（只需修改这一个）：' if target else '所有章节概要：'}
{self._format_dict({'summaries': original_summaries}) if not target else self._format_dict(target)}

用户反馈:
{feedback.get('summary', '')}

具体调整:
{self._format_feedback(feedback)}

{'请根据用户反馈只修改第 ' + str(chapter_num) + ' 章的概要，返回调整后的完整概要（JSON格式）。' if target else '请根据用户反馈修改所有章节概要，返回调整后的完整概要（JSON格式）。'}
只返回 JSON，不要解释。"""

        try:
            response = self._llm.call(prompt)
            import json
            import re

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                summaries = result.get("summaries", result.get("summary", original_summaries))
                if isinstance(summaries, list):
                    return summaries
        except Exception as e:
            logger.warning(f"LLM summary feedback application failed: {e}")

        return original_summaries

    def _apply_summary_feedback_local(
        self,
        original_summaries: list,
        feedback: dict,
        chapter_num: int | None = None,
    ) -> list:
        """本地模式：简单调整章节概要"""
        return original_summaries

    def _format_dict(self, d: dict) -> str:
        """格式化字典为字符串"""
        import json
        return json.dumps(d, ensure_ascii=False, indent=2)

    def _format_feedback(self, feedback: dict) -> str:
        """格式化反馈为可读字符串"""
        parts = []

        char_adj = feedback.get("character_adjustments", [])
        if char_adj:
            parts.append("角色调整:")
            for adj in char_adj:
                parts.append(f"  - {adj.get('name', '')}: {adj.get('aspect', '')} → {adj.get('to', '')}")

        plot_adj = feedback.get("plot_adjustments", [])
        if plot_adj:
            parts.append("情节调整:")
            for adj in plot_adj:
                parts.append(f"  - {adj.get('element', '')}: {adj.get('change', '')} - {adj.get('detail', '')}")

        tone_adj = feedback.get("tone_adjustments", [])
        if tone_adj:
            parts.append("风格调整:")
            for adj in tone_adj:
                parts.append(f"  - {adj.get('element', '')}: {adj.get('from', '')} → {adj.get('to', '')}")

        return "\n".join(parts) if parts else "无具体调整指令"

    def revise_chapter_content(
        self,
        original_content: str,
        chapter_outline: dict,
        feedback: dict,
        world_data: dict | None = None,
    ) -> str:
        """根据用户反馈修改章节内容

        Args:
            original_content: 原始章节内容
            chapter_outline: 章节大纲
            feedback: 结构化反馈（或自然语言反馈）
            world_data: 可选，世界观数据

        Returns:
            修改后的章节内容
        """
        if not feedback:
            return original_content

        # 如果 feedback 是字符串（自然语言），先尝试解析
        if isinstance(feedback, str):
            feedback_text = feedback
            feedback = {
                "summary": feedback_text,
                "character_adjustments": [],
                "plot_adjustments": [],
                "tone_adjustments": [],
            }

        summary = feedback.get("summary", "")

        # 如果没有具体调整指令，直接返回原内容
        if not summary and not any([feedback.get("character_adjustments"), feedback.get("plot_adjustments"), feedback.get("tone_adjustments")]):
            return original_content

        if self._llm:
            return self._revise_with_llm(original_content, chapter_outline, feedback, world_data)
        else:
            return self._revise_local(original_content, feedback)

    def _revise_with_llm(
        self,
        original_content: str,
        chapter_outline: dict,
        feedback: dict,
        world_data: dict | None = None,
    ) -> str:
        """使用 LLM 根据反馈修改章节内容"""
        chapter_title = chapter_outline.get("title", "未知章节")
        key_events = chapter_outline.get("main_events", [])
        events_str = "\n".join([f"- {e}" for e in key_events]) if key_events else "无"

        prompt = f"""你是一个小说编辑，负责根据读者反馈修改章节内容。

章节标题: {chapter_title}
章节大纲:
{events_str}

读者反馈:
{feedback.get('summary', '')}

{self._format_feedback(feedback)}

当前章节内容:
---
{original_content[:2000]}{'...' if len(original_content) > 2000 else ''}
---

请根据读者反馈修改章节内容。要求:
1. 保持章节标题和主要情节点不变
2. 只修改读者指出的问题
3. 保持原有的文风和节奏
4. 如果涉及角色调整，确保与其他角色互动一致

直接输出修改后的完整章节内容，不要有其他解释。"""

        try:
            response = self._llm.call(prompt)
            if isinstance(response, str):
                return response.strip()
            elif hasattr(response, 'raw'):
                return str(response.raw).strip()
            return str(response).strip()
        except Exception as e:
            logger.warning(f"LLM chapter revision failed: {e}")
            return original_content

    def _revise_local(
        self,
        original_content: str,
        feedback: dict,
    ) -> str:
        """本地模式：简单修改章节内容（不调用 LLM）"""
        # 本地模式只能做非常简单的替换
        summary = feedback.get("summary", "")
        if not summary:
            return original_content

        # 简单的关键词替换
        char_adj = feedback.get("character_adjustments", [])
        for adj in char_adj:
            name = adj.get("name", "")
            to_val = adj.get("to", "")
            if name and to_val:
                # 简单替换（实际应用中需要更智能的处理）
                original_content = original_content.replace(name, to_val)

        return original_content

    def revise_outline(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """根据反馈调整章节大纲

        Args:
            original_outline: 原始章节大纲
            feedback: 结构化反馈

        Returns:
            调整后的章节大纲
        """
        if not feedback:
            return original_outline

        if self._llm:
            return self._revise_outline_with_llm(original_outline, feedback)
        else:
            return self._revise_outline_local(original_outline, feedback)

    def _revise_outline_with_llm(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """使用 LLM 根据反馈调整章节大纲"""
        prompt = f"""你是一个小说大纲调整助手。

原始大纲:
{self._format_dict(original_outline)}

用户反馈:
{feedback.get('summary', '')}

具体调整:
{self._format_feedback(feedback)}

请根据用户反馈修改大纲，返回调整后的完整大纲（JSON格式）。
只返回 JSON，不要解释。"""

        try:
            response = self._llm.call(prompt)
            import json
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM outline revision failed: {e}")

        return original_outline

    def _revise_outline_local(
        self,
        original_outline: dict,
        feedback: dict,
    ) -> dict:
        """本地模式：简单调整大纲"""
        char_adj = feedback.get("character_adjustments", [])
        for adj in char_adj:
            name = adj.get("name", "")
            aspect = adj.get("aspect", "")
            to_val = adj.get("to", "")
            if name and aspect and to_val:
                main_events = original_outline.get("main_events", [])
                for i, event in enumerate(main_events):
                    if name in event:
                        main_events[i] = event.replace(name, to_val)
                original_outline["main_events"] = main_events
        return original_outline
