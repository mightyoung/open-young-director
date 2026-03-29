"""Content quality evaluator for novel generation.

提供两种评估器:
1. RuleBasedEvaluator - 基于规则的内容质量评估
2. LLMasJudgeEvaluator - 可选的 LLM-as-Judge 评估器

评估维度:
- coherence_score: 叙事连贯性
- character_consistency: 人物言行一致性
- dialogue_quality: 对话自然度
- plot_coherence: 情节连贯性
- emotional_depth: 情感深度
- language_quality: 语言质量
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Protocol
from enum import Enum

from .metrics import (
    ContentMetrics,
    ContentReward,
    QualityLevel,
    compute_reward_from_metrics,
)


class EvaluatorType(Enum):
    """评估器类型 (Evaluator type)."""
    RULE_BASED = "rule_based"
    LLM_AS_JUDGE = "llm_as_judge"
    HYBRID = "hybrid"


@dataclass
class EvaluationConfig:
    """评估配置 (Evaluation configuration)."""
    # 质量阈值
    coherence_threshold: float = 0.6
    character_threshold: float = 0.7
    dialogue_threshold: float = 0.6
    plot_threshold: float = 0.6
    emotional_threshold: float = 0.5
    language_threshold: float = 0.6

    # 综合通过阈值
    pass_threshold: float = 0.7

    # 各维度权重
    weights: Dict[str, float] = field(default_factory=lambda: {
        "coherence": 0.20,
        "character_consistency": 0.20,
        "dialogue_quality": 0.15,
        "plot_coherence": 0.20,
        "emotional_depth": 0.10,
        "language_quality": 0.15,
    })

    # 是否启用 LLM 评估
    use_llm_judge: bool = False

    # LLM 评估的配置
    llm_config: Optional[Dict[str, Any]] = None

    # 评估器类型
    evaluator_type: EvaluatorType = EvaluatorType.RULE_BASED


@dataclass
class EvaluationResult:
    """评估结果 (Evaluation result)."""
    # 评估的文本内容
    content: str

    # 评估的元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 内容指标
    metrics: Optional[ContentMetrics] = None

    # 奖励
    reward: Optional[ContentReward] = None

    # 是否通过
    passed: bool = False

    # 评估详情
    details: Dict[str, Any] = field(default_factory=dict)

    # 错误信息
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典 (Convert to dictionary)."""
        return {
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "metadata": self.metadata,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "reward": self.reward.to_dict() if self.reward else None,
            "passed": self.passed,
            "details": self.details,
            "error": self.error,
        }


class ContentEvaluator(Protocol):
    """内容评估器接口 (Content evaluator interface)."""

    def evaluate(self, content: str, **kwargs) -> EvaluationResult:
        """评估内容 (Evaluate content)."""
        ...

    def set_config(self, config: EvaluationConfig) -> None:
        """设置配置 (Set configuration)."""
        ...


@dataclass
class RuleBasedEvaluator:
    """基于规则的内容质量评估器 (Rule-based content quality evaluator).

    使用规则和启发式方法评估内容质量，无需外部 LLM。

    评估维度:
    1. 连贯性 (Coherence): 检查段落过渡、逻辑衔接
    2. 人物一致性 (Character Consistency): 检查人物言行是否一致
    3. 对话质量 (Dialogue Quality): 检查对话自然度
    4. 情节连贯性 (Plot Coherence): 检查情节发展是否合理
    5. 情感深度 (Emotional Depth): 检查情感表达是否丰富
    6. 语言质量 (Language Quality): 检查语法、拼写、表达
    """

    def __init__(self, config: Optional[EvaluationConfig] = None):
        self.config = config or EvaluationConfig()
        self._initialize_rules()

    def _initialize_rules(self):
        """初始化评估规则 (Initialize evaluation rules)."""
        # 用于检测对话的引号模式
        self.dialogue_patterns = [
            r'[""'']([^""'']+)[""'']',  # 中文引号
            r'[""]([^"]+)[""]',          # 英文双引号
            r'「([^」]+)」',              # 日式引号
        ]

        # 用于检测人物名称的模式（章节中的主要人物）
        self.character_name_pattern = r'【([^】]+)】'

        # 用于检测段落过渡的连接词
        self.transition_words = {
            "however", "但是", "然而", "不过", "可是",
            "therefore", "因此", "所以", "于是", "从而",
            "meanwhile", "与此同时", "这时候", "这时",
            "suddenly", "突然", "忽然", "猛然", "骤然",
            "finally", "终于", "最终", "最后", "最后",
            "previously", "之前", "此前", "在此之前",
        }

        # 用于检测情感词汇的模式
        self.emotion_words = {
            "positive": ["高兴", "开心", "快乐", "喜悦", "兴奋", "激动", "欣慰", "感动",
                       "爱", "喜欢", "满意", "幸福", "愉快", "欢快", "兴奋"],
            "negative": ["悲伤", "难过", "伤心", "痛苦", "绝望", "失望", "沮丧",
                        "愤怒", "生气", "恼火", "恐惧", "害怕", "担心", "焦虑"],
            "neutral": ["平静", "冷静", "平淡", "中立", "客观"],
        }

        # 用于检测情节转折的关键词
        self.plot_turning_points = [
            "突然", "忽然", "没想到", "出乎意料", "万万没想到",
            "就在这时", "恰在此时", "恰好", "正好", "刚好",
            "然而", "但是", "不过", "可是", "谁知", "竟然",
        ]

        # 用于检测叙述与对话比例的阈值
        self.min_dialogue_ratio = 0.05  # 至少 5% 是对话
        self.max_dialogue_ratio = 0.60  # 最多 60% 是对话

    def evaluate(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> EvaluationResult:
        """评估内容 (Evaluate content).

        Args:
            content: 要评估的内容 (Content to evaluate)
            context: 可选的上下文信息，如人物设定、情节大纲 (Optional context like character profiles, plot outline)

        Returns:
            EvaluationResult 对象 (EvaluationResult object)
        """
        try:
            # 计算各维度分数
            coherence_score = self._evaluate_coherence(content)
            character_score = self._evaluate_character_consistency(content, context)
            dialogue_score = self._evaluate_dialogue_quality(content)
            plot_score = self._evaluate_plot_coherence(content)
            emotional_score = self._evaluate_emotional_depth(content)
            language_score = self._evaluate_language_quality(content)

            # 计算综合分数
            overall_score = self._compute_overall_score(
                coherence_score,
                character_score,
                dialogue_score,
                plot_score,
                emotional_score,
                language_score,
            )

            # 确定质量等级
            quality_level = self._determine_quality_level(overall_score)

            # 构建指标
            metrics = ContentMetrics(
                quality_level=quality_level,
                coherence_score=coherence_score,
                character_consistency_score=character_score,
                dialogue_quality_score=dialogue_score,
                plot_coherence_score=plot_score,
                emotional_depth_score=emotional_score,
                language_quality_score=language_score,
                overall_score=overall_score,
                pass_threshold=self.config.pass_threshold,
            )

            # 计算奖励
            reward = compute_reward_from_metrics(metrics)

            # 检查是否通过
            passed = overall_score >= self.config.pass_threshold

            return EvaluationResult(
                content=content,
                metadata=context or {},
                metrics=metrics,
                reward=reward,
                passed=passed,
                details={
                    "coherence": coherence_score,
                    "character_consistency": character_score,
                    "dialogue_quality": dialogue_score,
                    "plot_coherence": plot_score,
                    "emotional_depth": emotional_score,
                    "language_quality": language_score,
                    "evaluation_method": "rule_based",
                },
            )

        except Exception as e:
            return EvaluationResult(
                content=content,
                error=str(e),
                passed=False,
            )

    def _evaluate_coherence(self, content: str) -> float:
        """评估叙事连贯性 (Evaluate narrative coherence).

        检查:
        1. 段落过渡是否平滑
        2. 逻辑连接词使用是否合理
        3. 时间/空间转换是否清晰
        """
        if not content or len(content.strip()) < 50:
            return 0.0

        # 分割段落
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        if len(paragraphs) < 2:
            # 单一段落，检查句子间连贯性
            return self._evaluate_sentence_coherence(content)

        # 检查段落过渡
        transition_score = 0.0
        for i in range(len(paragraphs) - 1):
            current = paragraphs[i]
            next_p = paragraphs[i + 1]

            # 检查是否有过渡词
            has_transition = self._has_transition_word(current, next_p)
            # 检查时间/空间指示是否清晰
            has_temporal_marker = self._has_temporal_marker(next_p)

            if has_transition:
                transition_score += 0.3
            if has_temporal_marker:
                transition_score += 0.2

        # 归一化分数
        transition_score = min(1.0, transition_score / max(1, len(paragraphs) - 1) * 2)

        # 检查句子连贯性
        sentence_score = self._evaluate_sentence_coherence(content)

        # 综合评分 (段落过渡 40% + 句子连贯 60%)
        return transition_score * 0.4 + sentence_score * 0.6

    def _evaluate_sentence_coherence(self, text: str) -> float:
        """评估句子间的连贯性 (Evaluate coherence between sentences)."""
        # 分割句子（简单按句号、问号、感叹号分割）
        sentences = re.split(r'[。！？；\n]', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            return 0.8 if len(text) > 50 else 0.5

        # 检查句子长度分布
        lengths = [len(s) for s in sentences]
        avg_length = sum(lengths) / len(lengths)

        # 长度过短或过长都扣分
        if avg_length < 10:
            return 0.5
        elif avg_length > 100:
            return 0.7
        else:
            return 0.85

    def _has_transition_word(self, current: str, next_p: str) -> bool:
        """检查两个段落间是否有过渡词 (Check if there's a transition word between paragraphs)."""
        combined = current.lower() + " " + next_p.lower()
        return any(tw.lower() in combined for tw in self.transition_words)

    def _has_temporal_marker(self, text: str) -> bool:
        """检查文本是否有时间标记 (Check if text has temporal markers)."""
        temporal_patterns = [
            r'\d+分钟', r'\d+小时', r'\d+天', r'\d+年',
            r'早上', r'中午', r'下午', r'晚上', r'夜里',
            r'翌日', r'次日', r'之前', r'之后',
            r'片刻', r'须臾', r'转眼',
        ]
        return any(re.search(p, text) for p in temporal_patterns)

    def _evaluate_character_consistency(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> float:
        """评估人物一致性 (Evaluate character consistency).

        检查:
        1. 人物言行是否与设定一致
        2. 同一人物在不同场景的表现是否一致
        3. 人物称谓是否正确
        """
        if not content:
            return 0.0

        # 提取人物名称
        characters = self._extract_characters(content)

        if not characters:
            # 没有明确的人物，检查一般一致性
            return 0.6

        # 检查人物出现次数分布
        char_occurrences = {char: content.count(char) for char in characters}

        # 检查是否有人物被过度使用或使用不足
        total_chars = sum(char_occurrences.values())
        if total_chars == 0:
            return 0.5

        # 计算分布均匀度
        ideal_count = total_chars / len(characters)
        variance = sum(
            abs(count - ideal_count) / max(1, ideal_count)
            for count in char_occurrences.values()
        ) / len(characters)

        # 均匀度得分 (方差越小越好)
        distribution_score = max(0.0, 1.0 - variance * 0.5)

        # 检查人物引号使用（人物对话占比）
        dialogue_mentions = self._count_character_in_dialogue(content, characters)

        # 对话中提到人物的比例
        if total_chars > 0:
            dialogue_score = min(1.0, dialogue_mentions / total_chars * 2)
        else:
            dialogue_score = 0.5

        # 综合评分
        return distribution_score * 0.5 + dialogue_score * 0.5

    def _extract_characters(self, content: str) -> List[str]:
        """提取内容中的人物名称 (Extract character names from content)."""
        # 查找【人物名】格式
        matches = re.findall(self.character_name_pattern, content)
        if matches:
            return list(set(matches))

        # 查找常见的"XXX说"、"XXX道"等对话标签
        speech_pattern = r'([\u4e00-\u9fa5]{2,4})(?:说|道|问|答|喊|叫|叹道|怒道|笑道)'
        matches = re.findall(speech_pattern, content)
        return list(set(matches))

    def _count_character_in_dialogue(self, content: str, characters: List[str]) -> int:
        """统计人物在对话中出现的次数 (Count how many times characters appear in dialogue)."""
        # 提取所有对话
        dialogues = []
        for pattern in self.dialogue_patterns:
            dialogues.extend(re.findall(pattern, content))

        # 统计人物在对话中出现的次数
        count = 0
        for dialogue in dialogues:
            for char in characters:
                if char in dialogue:
                    count += 1

        return count

    def _evaluate_dialogue_quality(self, content: str) -> float:
        """评估对话质量 (Evaluate dialogue quality).

        检查:
        1. 对话占比是否合理
        2. 对话是否有明确归属
        3. 对话是否推动情节/展现人物
        """
        if not content:
            return 0.0

        # 提取对话
        dialogues = []
        for pattern in self.dialogue_patterns:
            dialogues.extend(re.findall(pattern, content))

        if not dialogues:
            # 没有对话，检查叙述质量
            return 0.7

        # 检查对话占比
        total_length = len(content)
        dialogue_length = sum(len(d) for d in dialogues)
        dialogue_ratio = dialogue_length / total_length if total_length > 0 else 0

        # 对话占比评分
        if dialogue_ratio < self.min_dialogue_ratio:
            ratio_score = dialogue_ratio / self.min_dialogue_ratio * 0.5
        elif dialogue_ratio > self.max_dialogue_ratio:
            ratio_score = max(0.0, 1.0 - (dialogue_ratio - self.max_dialogue_ratio) / 0.2)
        else:
            ratio_score = 0.9

        # 检查对话长度分布
        dialogue_lengths = [len(d) for d in dialogues]
        avg_dialogue_len = sum(dialogue_lengths) / len(dialogue_lengths) if dialogues else 0

        # 对话长度评分（太短或太长都不好）
        if avg_dialogue_len < 5:
            length_score = 0.4
        elif avg_dialogue_len > 200:
            length_score = 0.6
        else:
            length_score = 0.85

        # 检查是否有对话标签
        has_speech_tags = bool(re.search(r'[\u4e00-\u9fa5]{2,4}(?:说|道|问|答)', content))
        tag_score = 0.9 if has_speech_tags else 0.6

        # 综合评分
        return ratio_score * 0.3 + length_score * 0.3 + tag_score * 0.4

    def _evaluate_plot_coherence(self, content: str) -> float:
        """评估情节连贯性 (Evaluate plot coherence).

        检查:
        1. 情节是否有明显矛盾
        2. 情节转折是否平滑
        3. 是否有伏笔/呼应
        """
        if not content or len(content.strip()) < 100:
            return 0.5

        # 检测情节转折点
        turning_points = sum(
            1 for tp in self.plot_turning_points
            if tp in content
        )

        # 转折点密度
        turning_density = turning_points / (len(content) / 500)  # 每500字

        # 转折点评分
        if turning_density < 0.5:
            turning_score = 0.6  # 情节太平
        elif turning_density > 5:
            turning_score = 0.5  # 转折太多
        else:
            turning_score = 0.8 + min(0.2, turning_density * 0.05)

        # 检查时间线一致性
        timeline_score = self._evaluate_timeline_consistency(content)

        # 检查因果关系
        cause_effect_score = self._evaluate_cause_effect(content)

        return turning_score * 0.4 + timeline_score * 0.3 + cause_effect_score * 0.3

    def _evaluate_timeline_consistency(self, content: str) -> float:
        """评估时间线一致性 (Evaluate timeline consistency)."""
        # 提取时间表达
        time_patterns = [
            (r'(\d+)年(\d+)月(\d+)日', 'date'),
            (r'(\d+)天', 'day'),
            (r'(\d+)小时', 'hour'),
            (r'早|中|晚|夜', 'time_of_day'),
        ]

        times = []
        for pattern, ptype in time_patterns:
            matches = re.findall(pattern, content)
            if matches:
                times.extend([(m, ptype) for m in matches])

        if not times:
            return 0.7  # 没有明确时间参照，保守评分

        # 检查时间顺序是否有矛盾（简化检查）
        # 这里可以添加更复杂的时间逻辑验证
        return 0.8

    def _evaluate_cause_effect(self, content: str) -> float:
        """评估因果关系 (Evaluate cause-effect relationships)."""
        # 检查因果连接词
        cause_words = ["因为", "由于", "所以", "因此", "导致", "使得", "为了"]
        effect_words = ["于是", "结果", "终于", "最终", "从而", "于是乎"]

        cause_count = sum(1 for w in cause_words if w in content)
        effect_count = sum(1 for w in effect_words if w in content)

        if cause_count == 0 and effect_count == 0:
            return 0.6  # 没有明确的因果连接词
        elif cause_count > 0 and effect_count > 0:
            return 0.85
        else:
            return 0.7

    def _evaluate_emotional_depth(self, content: str) -> float:
        """评估情感深度 (Evaluate emotional depth).

        检查:
        1. 情感词汇密度
        2. 情感变化是否丰富
        3. 情感表达是否细腻
        """
        if not content:
            return 0.0

        # 统计情感词汇
        emotion_count = 0
        for category, words in self.emotion_words.items():
            for word in words:
                emotion_count += content.count(word)

        # 情感词汇密度
        emotion_density = emotion_count / (len(content) / 100)  # 每100字

        # 情感密度评分
        if emotion_density < 0.5:
            density_score = 0.4
        elif emotion_density > 5:
            density_score = 0.6  # 情感词太多显得夸张
        else:
            density_score = 0.7 + min(0.3, emotion_density * 0.1)

        # 检查情感变化（不同情感词的使用）
        unique_emotions = set()
        for category, words in self.emotion_words.items():
            for word in words:
                if word in content:
                    unique_emotions.add(category)

        # 情感多样性评分
        emotion_variety = len(unique_emotions) / 3  # 3种情感类别

        return density_score * 0.6 + emotion_variety * 0.4

    def _evaluate_language_quality(self, content: str) -> float:
        """评估语言质量 (Evaluate language quality).

        检查:
        1. 是否有语法错误
        2. 是否有错别字
        3. 表达是否流畅
        """
        if not content:
            return 0.0

        # 基础评分
        score = 0.8

        # 检查重复词（简单检查连续重复）
        repeated_pattern = r'(.{2,})\1{2,}'
        if re.search(repeated_pattern, content):
            score -= 0.2

        # 检查句子完整性（是否有未完成的句子）
        incomplete_sentences = re.findall(r'[,，](?!\s*但|不过|然而)', content)
        if len(incomplete_sentences) > len(content) / 50:
            score -= 0.1

        # 检查标点使用
        proper_punctuation = bool(re.search(r'[。！？]', content))
        if not proper_punctuation:
            score -= 0.2

        # 检查段落长度（过长或过短都不好）
        paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
        if paragraphs:
            avg_para_len = sum(len(p) for p in paragraphs) / len(paragraphs)
            if avg_para_len < 20:
                score -= 0.1
            elif avg_para_len > 500:
                score -= 0.1

        return max(0.0, min(1.0, score))

    def _compute_overall_score(
        self,
        coherence: float,
        character: float,
        dialogue: float,
        plot: float,
        emotional: float,
        language: float,
    ) -> float:
        """计算综合分数 (Compute overall score)."""
        weights = self.config.weights
        return (
            coherence * weights.get("coherence", 0.20) +
            character * weights.get("character_consistency", 0.20) +
            dialogue * weights.get("dialogue_quality", 0.15) +
            plot * weights.get("plot_coherence", 0.20) +
            emotional * weights.get("emotional_depth", 0.10) +
            language * weights.get("language_quality", 0.15)
        )

    def _determine_quality_level(self, score: float) -> QualityLevel:
        """根据分数确定质量等级 (Determine quality level from score)."""
        if score >= 0.9:
            return QualityLevel.EXCELLENT
        elif score >= 0.8:
            return QualityLevel.GOOD
        elif score >= 0.7:
            return QualityLevel.ACCEPTABLE
        elif score >= 0.5:
            return QualityLevel.POOR
        else:
            return QualityLevel.FAIL

    def set_config(self, config: EvaluationConfig) -> None:
        """设置评估配置 (Set evaluation configuration)."""
        self.config = config


@dataclass
class LLMasJudgeEvaluator:
    """LLM-as-Judge 评估器 (LLM-as-Judge evaluator).

    使用 LLM 来评估内容质量，提供更灵活的评估能力。

    评估维度与 RuleBasedEvaluator 相同，但使用 LLM 进行判断。
    """

    def __init__(
        self,
        llm_client: Any,
        config: Optional[EvaluationConfig] = None
    ):
        """
        Args:
            llm_client: LLM 客户端，需支持 chat/completion 接口
            config: 评估配置
        """
        self.llm_client = llm_client
        self.config = config or EvaluationConfig()
        self.rule_evaluator = RuleBasedEvaluator(config)

    def evaluate(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> EvaluationResult:
        """评估内容 (Evaluate content).

        使用 LLM 进行评估，如果 LLM 调用失败则回退到规则评估。

        Args:
            content: 要评估的内容
            context: 上下文信息
            **kwargs: 其他参数

        Returns:
            EvaluationResult 对象
        """
        try:
            # 首先使用规则评估器进行初步评估
            rule_result = self.rule_evaluator.evaluate(content, context)

            # 构建 LLM 评估提示
            prompt = self._build_evaluation_prompt(content, context, rule_result)

            # 调用 LLM
            response = self._call_llm(prompt)

            # 解析 LLM 响应
            llm_metrics = self._parse_llm_response(response)

            # 合并评估结果
            final_metrics = self._merge_metrics(rule_result.metrics, llm_metrics)

            # 计算奖励
            reward = compute_reward_from_metrics(final_metrics)

            return EvaluationResult(
                content=content,
                metadata=context or {},
                metrics=final_metrics,
                reward=reward,
                passed=final_metrics.overall_score >= self.config.pass_threshold,
                details={
                    "rule_based_scores": rule_result.details,
                    "llm_scores": llm_metrics.to_dict() if llm_metrics else {},
                    "evaluation_method": "llm_as_judge",
                },
            )

        except Exception as e:
            # LLM 评估失败，回退到规则评估
            return self.rule_evaluator.evaluate(content, context)

    def _build_evaluation_prompt(
        self,
        content: str,
        context: Optional[Dict[str, Any]],
        rule_result: EvaluationResult
    ) -> str:
        """构建评估提示 (Build evaluation prompt)."""
        context_str = ""
        if context:
            context_str = f"""
# 上下文信息
角色设定: {context.get('character_profiles', '无')}
情节大纲: {context.get('plot_outline', '无')}
"""

        rule_scores = ""
        if rule_result.details:
            rule_scores = f"""
# 规则评估初步结果
- 连贯性: {rule_result.details.get('coherence', 0):.2f}
- 人物一致性: {rule_result.details.get('character_consistency', 0):.2f}
- 对话质量: {rule_result.details.get('dialogue_quality', 0):.2f}
- 情节连贯性: {rule_result.details.get('plot_coherence', 0):.2f}
- 情感深度: {rule_result.details.get('emotional_depth', 0):.2f}
- 语言质量: {rule_result.details.get('language_quality', 0):.2f}
"""

        return f"""你是一位专业的小说内容评估专家。请评估以下小说内容的质量。

{context_str}
{rule_scores}

# 待评估内容
---
{content[:3000]}  # 限制内容长度
---

# 评估维度（每项 0.0-1.0）
1. 连贯性(coherence): 叙事是否流畅，段落过渡是否自然
2. 人物一致性(character_consistency): 人物言行是否与设定一致
3. 对话质量(dialogue_quality): 对话是否自然、有特色
4. 情节连贯性(plot_coherence): 情节发展是否合理、有逻辑
5. 情感深度(emotional_depth): 情感表达是否细腻、动人
6. 语言质量(language_quality): 语言是否通顺、生动

# 输出格式
请以 JSON 格式输出评估结果：
{{
    "coherence": 0.85,
    "character_consistency": 0.80,
    "dialogue_quality": 0.75,
    "plot_coherence": 0.80,
    "emotional_depth": 0.70,
    "language_quality": 0.85,
    "overall": 0.80,
    "comments": "简要评语"
}}

只输出 JSON，不要有其他内容。
"""

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM (Call LLM)."""
        # 使用配置的 LLM 客户端
        if hasattr(self.llm_client, 'chat'):
            response = self.llm_client.chat(prompt)
        elif hasattr(self.llm_client, 'complete'):
            response = self.llm_client.complete(prompt)
        else:
            raise ValueError("LLM client must have 'chat' or 'complete' method")

        return response

    def _parse_llm_response(self, response: str) -> Optional[ContentMetrics]:
        """解析 LLM 响应 (Parse LLM response)."""
        try:
            # 提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                return None

            data = json.loads(json_match.group())

            return ContentMetrics(
                quality_level=QualityLevel.GOOD,
                coherence_score=data.get("coherence", 0.5),
                character_consistency_score=data.get("character_consistency", 0.5),
                dialogue_quality_score=data.get("dialogue_quality", 0.5),
                plot_coherence_score=data.get("plot_coherence", 0.5),
                emotional_depth_score=data.get("emotional_depth", 0.5),
                language_quality_score=data.get("language_quality", 0.5),
                overall_score=data.get("overall", 0.5),
                pass_threshold=self.config.pass_threshold,
            )

        except (json.JSONDecodeError, KeyError) as e:
            return None

    def _merge_metrics(
        self,
        rule_metrics: ContentMetrics,
        llm_metrics: Optional[ContentMetrics]
    ) -> ContentMetrics:
        """合并规则评估和 LLM 评估结果 (Merge rule-based and LLM evaluation results).

        使用加权平均，LLM 评估权重更高。
        """
        if llm_metrics is None:
            return rule_metrics

        # LLM 权重 0.6，规则评估权重 0.4
        llm_weight = 0.6
        rule_weight = 0.4

        return ContentMetrics(
            quality_level=rule_metrics.quality_level,
            coherence_score=(
                rule_metrics.coherence_score * rule_weight +
                llm_metrics.coherence_score * llm_weight
            ),
            character_consistency_score=(
                rule_metrics.character_consistency_score * rule_weight +
                llm_metrics.character_consistency_score * llm_weight
            ),
            dialogue_quality_score=(
                rule_metrics.dialogue_quality_score * rule_weight +
                llm_metrics.dialogue_quality_score * llm_weight
            ),
            plot_coherence_score=(
                rule_metrics.plot_coherence_score * rule_weight +
                llm_metrics.plot_coherence_score * llm_weight
            ),
            emotional_depth_score=(
                rule_metrics.emotional_depth_score * rule_weight +
                llm_metrics.emotional_depth_score * llm_weight
            ),
            language_quality_score=(
                rule_metrics.language_quality_score * rule_weight +
                llm_metrics.language_quality_score * llm_weight
            ),
            overall_score=(
                rule_metrics.overall_score * rule_weight +
                llm_metrics.overall_score * llm_weight
            ),
            pass_threshold=self.config.pass_threshold,
        )

    def set_config(self, config: EvaluationConfig) -> None:
        """设置评估配置 (Set evaluation configuration)."""
        self.config = config
        self.rule_evaluator.set_config(config)


def create_evaluator(
    config: EvaluationConfig,
    llm_client: Any = None
) -> ContentEvaluator:
    """创建评估器工厂函数 (Evaluator factory function).

    Args:
        config: 评估配置
        llm_client: 可选的 LLM 客户端

    Returns:
        ContentEvaluator 实例
    """
    if config.evaluator_type == EvaluatorType.RULE_BASED:
        return RuleBasedEvaluator(config)
    elif config.evaluator_type == EvaluatorType.LLM_AS_JUDGE:
        if llm_client is None:
            raise ValueError("LLM client is required for LLM-as-Judge evaluator")
        return LLMasJudgeEvaluator(llm_client, config)
    elif config.evaluator_type == EvaluatorType.HYBRID:
        if llm_client is None:
            return RuleBasedEvaluator(config)
        return LLMasJudgeEvaluator(llm_client, config)
    else:
        return RuleBasedEvaluator(config)
