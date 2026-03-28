"""Novel Reward Functions

适合小说生成的奖励函数模块。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol
from enum import Enum
import re


class RewardSignal(str, Enum):
    """奖励信号类型"""

    # 基础信号
    TASK_COMPLETION = "task_completion"
    EVALUATION = "evaluation"
    EFFICIENCY = "efficiency"

    # 内容质量信号
    COHERENCE = "coherence"
    CHARACTER_CONSISTENCY = "character_consistency"
    DIALOGUE_QUALITY = "dialogue_quality"
    PLOT_PROGRESSION = "plot_progression"
    EMOTIONAL_RESONANCE = "emotional_resonance"

    # 格式信号
    FORMAT = "format"
    LENGTH = "length"

    # 创新信号
    NOVELTY = "novelty"
    SURPRISE = "surprise"


@dataclass
class RewardWeights:
    """奖励权重配置

    用于平衡不同维度的奖励信号。
    """

    # 基础权重
    task_completion: float = 0.25
    evaluation: float = 0.20
    efficiency: float = 0.05

    # 内容质量权重
    coherence: float = 0.15
    character_consistency: float = 0.15
    dialogue_quality: float = 0.10
    plot_progression: float = 0.05
    emotional_resonance: float = 0.05

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "task_completion": self.task_completion,
            "evaluation": self.evaluation,
            "efficiency": self.efficiency,
            "coherence": self.coherence,
            "character_consistency": self.character_consistency,
            "dialogue_quality": self.dialogue_quality,
            "plot_progression": self.plot_progression,
            "emotional_resonance": self.emotional_resonance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "RewardWeights":
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if hasattr(cls, k)})


@dataclass
class RewardResult:
    """奖励计算结果

    包含各维度奖励和总奖励。
    """

    # 各维度奖励
    task_completion: float = 0.0
    evaluation: float = 0.0
    efficiency: float = 0.0
    coherence: float = 0.0
    character_consistency: float = 0.0
    dialogue_quality: float = 0.0
    plot_progression: float = 0.0
    emotional_resonance: float = 0.0

    # 额外奖励
    bonus: float = 0.0
    penalty: float = 0.0

    # 总奖励
    total: float = 0.0

    # 权重
    weights: RewardWeights = field(default_factory=RewardWeights)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def compute_total(self) -> float:
        """计算总奖励"""
        self.total = (
            self.task_completion * self.weights.task_completion
            + self.evaluation * self.weights.evaluation
            + self.efficiency * self.weights.efficiency
            + self.coherence * self.weights.coherence
            + self.character_consistency * self.weights.character_consistency
            + self.dialogue_quality * self.weights.dialogue_quality
            + self.plot_progression * self.weights.plot_progression
            + self.emotional_resonance * self.weights.emotional_resonance
            + self.bonus
            - self.penalty
        )
        return self.total

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_completion": self.task_completion,
            "evaluation": self.evaluation,
            "efficiency": self.efficiency,
            "coherence": self.coherence,
            "character_consistency": self.character_consistency,
            "dialogue_quality": self.dialogue_quality,
            "plot_progression": self.plot_progression,
            "emotional_resonance": self.emotional_resonance,
            "bonus": self.bonus,
            "penalty": self.penalty,
            "total": self.total,
            "weights": self.weights.to_dict(),
            "metadata": self.metadata,
        }


class RewardFunction(Protocol):
    """奖励函数协议"""

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算奖励

        Args:
            content: 生成的内容
            prompt: 提示/指令
            context: 上下文信息

        Returns:
            奖励值 (0.0 - 1.0)
        """
        ...


class TaskCompletionReward:
    """任务完成奖励

    评估内容是否满足任务要求。
    """

    def __init__(self, min_length: int = 100, max_length: int = 50000):
        self.min_length = min_length
        self.max_length = max_length

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算任务完成奖励"""
        if not content or len(content.strip()) == 0:
            return 0.0

        length = len(content)

        # 长度检查
        if length < self.min_length:
            return length / self.min_length * 0.5  # 0.0 - 0.5
        elif length > self.max_length:
            return max(0.0, 1.0 - (length - self.max_length) / self.max_length)  # 惩罚超长

        # 检查关键内容是否存在
        score = 0.5  # 基础分

        # 检查是否包含必要的叙事元素
        if context.get("requires_dialogue", False):
            if self._has_dialogue(content):
                score += 0.2

        if context.get("requires_description", False):
            if self._has_description(content):
                score += 0.15

        if context.get("requires_action", False):
            if self._has_action(content):
                score += 0.15

        return min(1.0, score)

    def _has_dialogue(self, content: str) -> bool:
        """检查是否有对话"""
        return bool(re.search(r'["""].*?[""".*?]|[^"]*?"[^"]*"', content))

    def _has_description(self, content: str) -> bool:
        """检查是否有描写"""
        desc_patterns = [
            r"他/她/它\s+(跑|走|看|听|想|感觉)",
            r"阳光/风/雨/云",
            r"房间/街道/城市/森林",
        ]
        return any(re.search(p, content) for p in desc_patterns)

    def _has_action(self, content: str) -> bool:
        """检查是否有动作"""
        action_verbs = ["跑", "走", "跳", "飞", "打", "说", "想", "看", "听", "喊"]
        return any(v in content for v in action_verbs)


class EfficiencyReward:
    """效率奖励

    基于生成效率和资源使用。
    """

    def __init__(self, target_tokens_per_second: float = 50.0):
        self.target_tokens_per_second = target_tokens_per_second

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算效率奖励"""
        tokens_per_second = context.get("tokens_per_second", 0)

        if tokens_per_second <= 0:
            return 0.5  # 默认中等分数

        # 与目标比较
        ratio = tokens_per_second / self.target_tokens_per_second

        if ratio >= 1.0:
            return 1.0
        elif ratio >= 0.5:
            return 0.5 + (ratio - 0.5)
        else:
            return max(0.0, ratio)


class CoherenceReward:
    """连贯性奖励

    评估内容的叙事连贯性。
    """

    def __init__(self):
        self.coherence_keywords = [
            "然后", "接着", "之后", "于是",
            "因为", "所以", "但是", "然而",
            "虽然", "尽管", "如果", "当",
        ]

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算连贯性奖励"""
        if not content:
            return 0.0

        score = 0.3  # 基础分

        # 检查过渡词的使用
        transition_count = sum(1 for kw in self.coherence_keywords if kw in content)
        transition_score = min(0.3, transition_count * 0.05)
        score += transition_score

        # 检查段落结构
        paragraphs = content.split("\n\n")
        if len(paragraphs) >= 3:
            score += 0.2

        # 检查句子连贯性（简单检查：是否有完整句子）
        sentences = re.split(r"[。.!?！？]", content)
        complete_sentences = [s for s in sentences if len(s.strip()) > 5]
        if len(complete_sentences) >= 3:
            score += 0.2

        return min(1.0, score)


class CharacterConsistencyReward:
    """人物一致性奖励

    评估生成内容中人物言行的一致性。
    """

    def __init__(self):
        self.character_schemas: Dict[str, Dict[str, Any]] = {}

    def set_schema(self, character_name: str, schema: Dict[str, Any]) -> None:
        """设置人物模式

        Args:
            character_name: 人物名称
            schema: 人物模式 {personality: [...], speech_pattern: [...], ...}
        """
        self.character_schemas[character_name] = schema

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算人物一致性奖励"""
        if not content:
            return 0.5

        # 如果没有设置模式，返回中等分数
        if not self.character_schemas:
            return 0.5

        score = 0.5
        characters_mentioned = context.get("characters", [])

        for char_name in characters_mentioned:
            if char_name not in self.character_schemas:
                continue

            schema = self.character_schemas[char_name]

            # 检查人称代词使用
            if "he_pronouns" in schema and self._contains_pronoun_type(content, char_name, "he"):
                score += 0.1

            if "she_pronouns" in schema and self._contains_pronoun_type(content, char_name, "she"):
                score += 0.1

            # 检查言行一致性
            if "speech_pattern" in schema:
                # 简单检查：是否使用了该人物特有的说话方式
                speech_patterns = schema["speech_pattern"]
                for pattern in speech_patterns:
                    if pattern.lower() in content.lower():
                        score += 0.05

        return min(1.0, score)

    def _contains_pronoun_type(
        self, content: str, char_name: str, pronoun_type: str
    ) -> bool:
        """检查是否使用了特定类型的人称代词"""
        if pronoun_type == "he":
            pattern = char_name + r'[^"]*(?:他|他的)'
            return bool(re.search(pattern, content))
        elif pronoun_type == "she":
            pattern = char_name + r'[^"]*(?:她|她的)'
            return bool(re.search(pattern, content))
        return False


class DialogueQualityReward:
    """对话质量奖励

    评估对话的自然性和表现力。
    """

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算对话质量奖励"""
        if not content:
            return 0.0

        # 提取对话
        dialogues = re.findall(r'"([^"]*)"', content)
        if not dialogues:
            # 尝试中文引号
            dialogues = re.findall(r'「([^」]*)」', content)

        if not dialogues:
            return 0.3  # 无对话，中等分数

        score = 0.3

        # 对话数量适中（不是越多越好）
        if 1 <= len(dialogues) <= 10:
            score += 0.2
        elif len(dialogues) > 10:
            score += 0.1

        # 检查对话长度分布
        lengths = [len(d) for d in dialogues]
        if lengths:
            avg_length = sum(lengths) / len(lengths)
            # 对话长度适中（不是太短也不是太长）
            if 5 <= avg_length <= 200:
                score += 0.2

        # 检查对话是否有多样性（不同长度）
        if max(lengths) / (min(lengths) + 1) > 2:
            score += 0.15

        # 检查是否有情感词
        emotional_words = ["!", "?", "！", "？", "啊", "呢", "吧", "吗"]
        has_emotion = any(any(w in d for w in emotional_words) for d in dialogues)
        if has_emotion:
            score += 0.15

        return min(1.0, score)


class PlotProgressionReward:
    """情节发展奖励

    评估情节是否有进展。
    """

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算情节发展奖励"""
        if not content:
            return 0.0

        score = 0.3

        # 检查是否有情节关键词
        plot_keywords = [
            "突然", "没想到", "于是", "最终", "结果",
            "这时", "突然", "紧接着", "不久",
        ]
        keyword_count = sum(1 for kw in plot_keywords if kw in content)
        score += min(0.2, keyword_count * 0.05)

        # 检查是否有变化
        change_indicators = ["但是", "然而", "出乎意料", "改变"]
        has_change = any(indicator in content for indicator in change_indicators)
        if has_change:
            score += 0.2

        # 检查是否有结果/结论
        conclusion_keywords = ["终于", "最后", "结束", "完成", "成功"]
        has_conclusion = any(kw in content for kw in conclusion_keywords)
        if has_conclusion:
            score += 0.15

        # 检查是否有冲突或悬念
        tension_keywords = ["紧张", "担心", "害怕", "期待", "悬念"]
        has_tension = any(kw in content for kw in tension_keywords)
        if has_tension:
            score += 0.15

        return min(1.0, score)


class EmotionalResonanceReward:
    """情感共鸣奖励

    评估内容的情感表现力。
    """

    def __init__(self):
        self.emotion_keywords = {
            "joy": ["开心", "高兴", "快乐", "兴奋", "喜悦", "欢呼"],
            "sadness": ["悲伤", "难过", "伤心", "痛苦", "哭泣", "沮丧"],
            "anger": ["生气", "愤怒", "恼火", "气愤", "大怒"],
            "fear": ["害怕", "恐惧", "担心", "紧张", "不安", "发抖"],
            "surprise": ["惊讶", "震惊", "意外", "吃惊", "没想到"],
            "love": ["爱", "喜欢", "温柔", "关怀", "心动", "思念"],
        }

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算情感共鸣奖励"""
        if not content:
            return 0.0

        score = 0.3

        # 检查情感词的使用
        emotion_count = 0
        detected_emotions = set()

        for emotion, keywords in self.emotion_keywords.items():
            for kw in keywords:
                if kw in content:
                    emotion_count += 1
                    detected_emotions.add(emotion)

        # 情感词数量适中
        if 1 <= emotion_count <= 5:
            score += 0.3
        elif emotion_count > 5:
            score += 0.2

        # 情感多样性
        if len(detected_emotions) >= 2:
            score += 0.2

        # 检查是否有情感表达的自然方式
        natural_expressions = ["叹气", "微笑", "颤抖", "脸红", "心跳"]
        for expr in natural_expressions:
            if expr in content:
                score += 0.1
                break

        return min(1.0, score)


class NovelRewardFunction:
    """综合小说奖励函数

    整合所有子奖励函数，计算综合奖励。
    """

    def __init__(
        self,
        weights: Optional[RewardWeights] = None,
        include_subscores: bool = True,
    ):
        """初始化奖励函数

        Args:
            weights: 奖励权重配置
            include_subscores: 是否包含各维度分数
        """
        self.weights = weights or RewardWeights()
        self.include_subscores = include_subscores

        # 初始化子奖励函数
        self.task_completion = TaskCompletionReward()
        self.efficiency = EfficiencyReward()
        self.coherence = CoherenceReward()
        self.character_consistency = CharacterConsistencyReward()
        self.dialogue_quality = DialogueQualityReward()
        self.plot_progression = PlotProgressionReward()
        self.emotional_resonance = EmotionalResonanceReward()

    def compute(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> RewardResult:
        """计算综合奖励

        Args:
            content: 生成的内容
            prompt: 提示/指令
            context: 上下文信息

        Returns:
            奖励计算结果
        """
        result = RewardResult(weights=self.weights)

        # 计算各维度奖励
        result.task_completion = self.task_completion.compute(content, prompt, context)
        result.efficiency = self.efficiency.compute(content, prompt, context)
        result.coherence = self.coherence.compute(content, prompt, context)
        result.character_consistency = self.character_consistency.compute(
            content, prompt, context
        )
        result.dialogue_quality = self.dialogue_quality.compute(content, prompt, context)
        result.plot_progression = self.plot_progression.compute(content, prompt, context)
        result.emotional_resonance = self.emotional_resonance.compute(
            content, prompt, context
        )

        # 使用外部评估分数（如果有）
        if "evaluation_score" in context:
            result.evaluation = context["evaluation_score"]
        else:
            result.evaluation = (
                result.coherence
                + result.character_consistency
                + result.dialogue_quality
            ) / 3

        # 计算总奖励
        result.compute_total()

        # 设置元数据
        if self.include_subscores:
            result.metadata = {
                "content_length": len(content),
                "num_paragraphs": len(content.split("\n\n")),
                "num_dialogues": len(re.findall(r'"([^"]*)"', content)),
            }

        return result

    def compute_simple(
        self,
        content: str,
        prompt: str,
        context: Dict[str, Any],
    ) -> float:
        """计算简单奖励（仅返回总奖励值）

        Args:
            content: 生成的内容
            prompt: 提示/指令
            context: 上下文信息

        Returns:
            总奖励值
        """
        return self.compute(content, prompt, context).total


# 便捷函数
def compute_novel_reward(
    content: str,
    prompt: str,
    context: Dict[str, Any],
    weights: Optional[RewardWeights] = None,
) -> float:
    """计算小说奖励的便捷函数

    Args:
        content: 生成的内容
        prompt: 提示/指令
        context: 上下文信息
        weights: 奖励权重配置

    Returns:
        总奖励值
    """
    reward_fn = NovelRewardFunction(weights=weights, include_subscores=False)
    return reward_fn.compute_simple(content, prompt, context)
