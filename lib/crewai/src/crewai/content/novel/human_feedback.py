"""Human Feedback - 人机协作审批模块

提供自然语言反馈解析和审批工作流支持：

1. HumanFeedback: 用户反馈数据结构
2. ApprovalDecision: 审批决策枚举
3. FeedbackParser: 自然语言反馈解析器

使用示例:
    # 用户提交反馈
    feedback = HumanFeedback(
        stage="outline",
        decision=ApprovalDecision.REVISE,
        natural_language="主角韩林的性格太懦弱,改成坚毅果敢;增加女主的戏份"
    )

    # 解析为结构化指令
    parser = FeedbackParser(llm)
    structured = parser.parse(feedback)

    # 应用到生成流程
    revised_outline = apply_feedback(outline, structured)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from crewai.llm import LLM

logger = logging.getLogger(__name__)


class ApprovalDecision(Enum):
    """审批决策类型"""
    APPROVE = "approve"           # 通过，继续下一阶段
    REVISE = "revise"            # 需要修改后重新生成
    REJECT = "reject"            # 拒绝，重新生成
    REINSTRUCT = "reinstruct"    # 重新指令（大幅修改）
    SKIP = "skip"                # 跳过此阶段


@dataclass
class ApprovalRecord:
    """审批记录"""
    stage: str
    decision: str
    natural_language: str
    structured: dict
    timestamp: str = ""
    approved_data: Optional[dict] = None


@dataclass
class HumanFeedback:
    """用户反馈数据

    Attributes:
        stage: 反馈对应的阶段 (outline, volume, summary, writing)
        decision: 审批决策
        natural_language: 用户原始自然语言描述
        structured: 解析后的结构化指令
        chapter_num: 如果是章节级反馈，记录章节号
    """
    stage: str
    decision: ApprovalDecision
    natural_language: str = ""
    structured: dict = field(default_factory=dict)
    chapter_num: Optional[int] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "stage": self.stage,
            "decision": self.decision.value if isinstance(self.decision, ApprovalDecision) else self.decision,
            "natural_language": self.natural_language,
            "structured": self.structured,
            "chapter_num": self.chapter_num,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HumanFeedback":
        """从字典创建"""
        decision = data.get("decision", "approve")
        if isinstance(decision, str):
            decision = ApprovalDecision(decision)
        return cls(
            stage=data.get("stage", ""),
            decision=decision,
            natural_language=data.get("natural_language", ""),
            structured=data.get("structured", {}),
            chapter_num=data.get("chapter_num"),
        )


class FeedbackParser:
    """自然语言反馈解析器

    使用 LLM 将用户的自然语言反馈解析为结构化的修改指令。

    解析策略:
    1. 意图识别 - 判断用户是想通过、修改还是重新生成
    2. 实体提取 - 识别人名、情节、设定等关键实体
    3. 操作映射 - 将描述性语言映射为具体修改操作

    使用示例:
        parser = FeedbackParser(llm)
        feedback = HumanFeedback(
            stage="outline",
            decision=ApprovalDecision.REVISE,
            natural_language="主角韩林的背景改成被逐出宗门的天才"
        )
        structured = await parser.parse(feedback)
    """

    def __init__(self, llm: "LLM" = None):
        """初始化解析器

        Args:
            llm: 可选的 LLM 实例。如果不提供，使用本地解析模式。
        """
        self._llm = llm

    def parse(self, feedback: HumanFeedback) -> dict:
        """解析用户反馈

        Args:
            feedback: 用户反馈对象

        Returns:
            结构化的修改指令字典

        解析结果示例:
        {
            "character_adjustments": [
                {
                    "name": "韩林",
                    "aspect": "背景",
                    "from": "普通弟子",
                    "to": "被逐出宗门的天才"
                }
            ],
            "plot_adjustments": [
                {
                    "element": "开头",
                    "change": "增加冲突",
                    "detail": "韩林在演武场被羞辱"
                }
            ],
            "tone_adjustments": [
                {
                    "element": "整体",
                    "from": "平淡",
                    "to": "紧张激烈"
                }
            ],
            "summary": "需要对主角背景和开头冲突进行调整"
        }
        """
        if not feedback.natural_language:
            return self._default_structured(feedback.decision)

        if self._llm:
            return self._parse_with_llm(feedback)
        else:
            return self._parse_local(feedback)

    def _parse_with_llm(self, feedback: HumanFeedback) -> dict:
        """使用 LLM 解析反馈"""
        chapter_hint = f"（针对第 {feedback.chapter_num} 章）" if feedback.chapter_num else ""

        prompt = f"""你是一个专业的小说编辑，负责将读者的自然语言反馈解析为结构化的修改指令。

【任务】
将下面的读者反馈解析为JSON格式的修改指令。

【读者反馈】
{feedback.natural_language}

【反馈阶段】
{feedback.stage} {chapter_hint}

【支持的修改类型】

1. character_adjustments - 角色调整
   - name: 角色名称
   - aspect: 调整方面（背景/性格/能力/境界/关系/戏份/外貌等）
   - from: 原设定（如果知道）
   - to: 新设定

2. plot_adjustments - 情节调整
   - element: 情节元素（开头/冲突/高潮/结尾/转折等）
   - change: 修改类型（增加/删除/修改/强化/弱化）
   - detail: 具体修改内容

3. tone_adjustments - 风格调整
   - element: 元素（整体/对话/描写/节奏/氛围）
   - from: 原风格
   - to: 新风格

4. summary - 修改摘要（必填）
   用一句话概括读者想要的修改方向

【输出格式】
只输出JSON，不要有任何其他文字。格式如下：
{{
    "character_adjustments": [],
    "plot_adjustments": [],
    "tone_adjustments": [],
    "summary": "修改摘要"
}}

【示例】

输入: "主角韩林的性格太懦弱了，改成坚毅果敢一点，女主戏份太少"
输出: {{"character_adjustments": [{{"name": "韩林", "aspect": "性格", "from": "懦弱", "to": "坚毅果敢"}}], "plot_adjustments": [{{"element": "柳如烟", "change": "增加", "detail": "增加戏份"}}], "tone_adjustments": [], "summary": "主角性格改为坚毅果敢，增加女主戏份"}}

输入: "第一章开头太平淡，增加一些冲突，让读者有紧张感"
输出: {{"character_adjustments": [], "plot_adjustments": [{{"element": "开头", "change": "增加", "detail": "增加冲突和紧张感"}}], "tone_adjustments": [{{"element": "整体", "from": "平淡", "to": "紧张激烈"}}], "summary": "开头增加冲突，提升紧张感"}}

请解析读者的反馈："""

        try:
            response = self._llm.call(prompt)
            import json
            # 尝试解析 JSON
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            result = json.loads(response.strip())

            # 确保 summary 字段存在
            if "summary" not in result or not result["summary"]:
                result["summary"] = feedback.natural_language[:100]

            return result
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}, falling back to local parsing")
            return self._parse_local(feedback)

    def _parse_local(self, feedback: HumanFeedback) -> dict:
        """本地解析（无 LLM 时使用简单模式）"""
        text = feedback.natural_language

        adjustments = {
            "character_adjustments": [],
            "plot_adjustments": [],
            "tone_adjustments": [],
            "summary": text[:100] if len(text) > 100 else text,
        }

        # 简单模式匹配
        import re

        # 角色修改模式: "XX的YY改成ZZ" / "XX改成YY" / "把XX的YY改掉"
        char_patterns = [
            r'([^\s，,。]+)改成([^\s，,。]+)',  # "韩林改成坚毅果敢"
            r'把([^\s，,。]+)改成',  # "把韩林改成..."
            r'([^\s，,。]+)的(背景|性格|能力|境界|关系|戏份|外貌|语气|说话方式)(?:改成|改成|改成)([^\s，,。]+)',  # "韩林的背景改成..."
            r'([^\s，,。]+)(?:性格|背景|能力)(?:太|很)?([^\s，,。]+)',  # "韩林性格太懦弱"
        ]

        for pattern in char_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 2:
                    if len(match) == 2:
                        # "XX改成YY" 模式
                        name_or_from, to = match
                        adjustments["character_adjustments"].append({
                            "name": name_or_from,
                            "aspect": "待识别",
                            "from": "",
                            "to": to,
                        })
                    elif len(match) == 3:
                        # "XX的YY改成ZZ" 模式
                        name, aspect, to = match
                        adjustments["character_adjustments"].append({
                            "name": name,
                            "aspect": aspect,
                            "from": "",
                            "to": to,
                        })

        # 情节修改模式: "增加XX" "删除XX" "改成XX" "第X章"
        plot_keywords = []
        if "增加" in text:
            plot_keywords.append("增加")
        if "删除" in text or "删掉" in text:
            plot_keywords.append("删除")
        if "修改" in text:
            plot_keywords.append("修改")
        if "强化" in text:
            plot_keywords.append("强化")
        if "弱化" in text:
            plot_keywords.append("弱化")

        if plot_keywords:
            # 提取第X章的引用
            chapter_match = re.search(r'第([一二三四五六七八九十百0-9]+)章', text)
            element = f"第 {chapter_match.group(0)}" if chapter_match else "待识别"

            adjustments["plot_adjustments"].append({
                "element": element,
                "change": " / ".join(plot_keywords),
                "detail": text,
            })

        # 风格/氛围调整
        tone_keywords = []
        if "紧张" in text:
            tone_keywords.append("紧张")
        if "平淡" in text:
            tone_keywords.append("平淡")
        if "激烈" in text:
            tone_keywords.append("激烈")
        if "压抑" in text:
            tone_keywords.append("压抑")
        if "轻松" in text:
            tone_keywords.append("轻松")

        if len(tone_keywords) >= 2:
            adjustments["tone_adjustments"].append({
                "element": "整体",
                "from": tone_keywords[0],
                "to": tone_keywords[1],
            })
        elif tone_keywords:
            adjustments["tone_adjustments"].append({
                "element": "整体",
                "from": "普通",
                "to": tone_keywords[0],
            })

        return adjustments

    def _default_structured(self, decision: ApprovalDecision) -> dict:
        """默认结构化结果（无反馈内容时）"""
        if decision == ApprovalDecision.APPROVE:
            return {
                "character_adjustments": [],
                "plot_adjustments": [],
                "tone_adjustments": [],
                "summary": "用户批准，无修改",
            }
        elif decision == ApprovalDecision.SKIP:
            return {
                "character_adjustments": [],
                "plot_adjustments": [],
                "tone_adjustments": [],
                "summary": "用户跳过此阶段",
            }
        else:
            return {
                "character_adjustments": [],
                "plot_adjustments": [],
                "tone_adjustments": [],
                "summary": "需要修改但未提供具体指示",
            }


class ApprovalWorkflow:
    """审批工作流管理器

    负责在流水线各阶段管理审批状态和用户反馈。

    使用示例:
        workflow = ApprovalWorkflow(pipeline_state)

        # 检查是否需要审批
        if workflow.needs_approval("outline"):
            output = workflow.get_approval_content("outline")
            # 显示给用户

        # 提交反馈
        workflow.submit_feedback(feedback)
    """

    def __init__(self, pipeline_state, llm: "LLM" = None):
        """初始化审批工作流

        Args:
            pipeline_state: PipelineState 实例
            llm: 可选的 LLM 用于解析反馈
        """
        self._state = pipeline_state
        self._llm = llm
        self._parser = FeedbackParser(llm)

        # 审批阶段列表
        self._approval_stages = ["outline", "volume", "summary"]

    def needs_approval(self, stage: str) -> bool:
        """检查是否需要审批

        Args:
            stage: 阶段名

        Returns:
            是否需要审批
        """
        if stage not in self._approval_stages:
            return False

        # 检查阶段是否完成且尚未审批
        stage_status = self._state.stage_statuses.get(stage, "pending")
        return stage_status in ("pending", "approved", "needs_revision")

    def get_approval_content(self, stage: str) -> dict:
        """获取待审批的内容

        Args:
            stage: 阶段名

        Returns:
            包含待审批内容的字典
        """
        if stage == "outline":
            return {
                "stage": stage,
                "world_data": self._state.world_data,
                "plot_data": self._state.plot_data,
                "evaluation": self._state.outline_evaluation,
            }
        elif stage == "volume":
            return {
                "stage": stage,
                "volume_outlines": self._state.volume_outlines,
            }
        elif stage == "summary":
            return {
                "stage": stage,
                "chapter_summaries": self._state.chapter_summaries,
            }
        else:
            return {"stage": stage}

    def submit_feedback(self, feedback: HumanFeedback) -> None:
        """提交用户反馈

        Args:
            feedback: 用户反馈对象
        """
        # 解析自然语言
        if feedback.natural_language and not feedback.structured:
            feedback.structured = self._parser.parse(feedback)

        # 更新状态
        self._state.stage_statuses[feedback.stage] = feedback.decision.value

        # 添加到历史
        record = ApprovalRecord(
            stage=feedback.stage,
            decision=feedback.decision.value,
            natural_language=feedback.natural_language,
            structured=feedback.structured,
        )
        self._state.approval_history.append(asdict(record))

        # 保存反馈到待处理
        self._state.pending_feedback = feedback.to_dict()

        logger.info(f"Feedback submitted for stage '{feedback.stage}': {feedback.decision.value}")

    def get_pending_approval(self) -> Optional[str]:
        """获取待审批的阶段

        Returns:
            待审批的阶段名，或 None
        """
        for stage in self._approval_stages:
            status = self._state.stage_statuses.get(stage, "pending")
            if status == "pending":
                return stage
        return None

    def is_approved(self, stage: str) -> bool:
        """检查阶段是否已批准

        Args:
            stage: 阶段名

        Returns:
            是否已批准
        """
        return self._state.stage_statuses.get(stage) == "approve"


# 便捷函数
def create_approval_feedback(
    stage: str,
    decision: str,
    natural_language: str = "",
    chapter_num: Optional[int] = None,
) -> HumanFeedback:
    """创建审批反馈的便捷函数

    Args:
        stage: 阶段名
        decision: 决策字符串 (approve/revise/reject/reinstruct/skip)
        natural_language: 自然语言反馈
        chapter_num: 章节号（可选）

    Returns:
        HumanFeedback 对象
    """
    return HumanFeedback(
        stage=stage,
        decision=ApprovalDecision(decision),
        natural_language=natural_language,
        chapter_num=chapter_num,
    )
