"""章节结尾质量检查器."""

from typing import Dict, List, Optional


class ChapterEndingChecker:
    """章节结尾质量检查器.

    验证章节结尾质量，包括字数、结尾类型、钩子检测等。
    """

    def __init__(
        self,
        min_words: int = 500,
        max_words: int = 5000,
    ):
        """初始化章节结尾检查器.

        Args:
            min_words: 章节最小字数
            max_words: 章节最大字数
        """
        self.min_words = min_words
        self.max_words = max_words

        # 结尾类型和质量指标词
        self.QUALITY_INDICATORS = {
            "cliffhanger": {
                "name": "悬念式结尾",
                "keywords": [
                    "就在此时",
                    "突然",
                    "然而",
                    "但是",
                    "没想到",
                    "谁知",
                    "却不料",
                    "就在这时",
                    "刹那间",
                    "霎时间",
                ],
                "weight": 1.0,
            },
            "reflection": {
                "name": "反思式结尾",
                "keywords": [
                    "心想",
                    "思考",
                    "回忆",
                    "想着",
                    "不由得",
                    "暗自",
                    "心中暗想",
                ],
                "weight": 0.9,
            },
            "action": {
                "name": "行动式结尾",
                "keywords": [
                    "冲向",
                    "转身",
                    "猛然",
                    "立刻",
                    "当即",
                    "飞身",
                    "纵身",
                    "拔剑",
                ],
                "weight": 0.85,
            },
            "summary": {
                "name": "总结式结尾",
                "keywords": [
                    "最终",
                    "于是",
                    "经过",
                    "最终",
                    "这一天",
                    "从此",
                ],
                "weight": 0.7,
            },
            "tension": {
                "name": "张力式结尾",
                "keywords": [
                    "危机",
                    "危险",
                    "死亡",
                    "威胁",
                    "困境",
                    "绝望",
                    "悬念",
                ],
                "weight": 0.95,
            },
        }

    def check(
        self,
        chapter_content: str,
        ending_type: Optional[str] = None,
    ) -> Dict:
        """检查章节结尾质量.

        Args:
            chapter_content: 完整章节内容
            ending_type: 期望的结尾类型，可选值:
                - 'cliffhanger': 悬念式
                - 'reflection': 反思式
                - 'action': 行动式
                - 'summary': 总结式
                - 'tension': 张力式
                如果为None，则自动检测

        Returns:
            包含以下键的字典:
                - score: 章节结尾质量评分 (0-1)
                - word_count: 字数
                - ending_type: 实际结尾类型
                - has_good_ending: 是否有良好结尾
                - issue: 问题描述（如果有）
                - suggestions: 改进建议
                - quality_score: 各维度质量评分
        """
        if not chapter_content:
            return {
                "score": 0.0,
                "word_count": 0,
                "ending_type": "unknown",
                "has_good_ending": False,
                "issue": "章节内容为空",
                "suggestions": ["请提供章节内容"],
                "quality_score": {},
            }

        word_count = len(chapter_content)
        quality_scores = {}
        found_indicators = {}

        # 检查每个结尾类型
        for ending_type_id, config in self.QUALITY_INDICATORS.items():
            keywords = config["keywords"]
            # 取最后200字进行检测
            ending_text = chapter_content[-200:] if len(chapter_content) > 200 else chapter_content

            found = [kw for kw in keywords if kw in ending_text]
            count = len(found)

            # 计算该类型的质量得分
            type_score = min(count / 3, 1.0) * config["weight"]
            quality_scores[ending_type_id] = {
                "score": round(type_score, 3),
                "found_count": count,
                "found_keywords": found,
            }
            found_indicators[ending_type_id] = found

        # 确定实际结尾类型（得分最高的）
        best_type = max(quality_scores.items(), key=lambda x: x[1]["score"])
        actual_ending_type = best_type[0]

        # 检查字数问题
        issue = None
        suggestions = []
        word_score = 1.0

        if word_count < self.min_words:
            word_score = 0.3
            issue = f"章节过短（{word_count}字），建议至少{self.min_words}字"
            suggestions.append(f"增加内容至{self.min_words}字以上")
        elif word_count > self.max_words:
            word_score = 0.5
            issue = f"章节过长（{word_count}字），建议控制在{self.max_words}字以内"
            suggestions.append(f"拆分章节或精简内容至{self.max_words}字以内")

        # 如果指定了结尾类型，检查是否符合
        if ending_type and ending_type != actual_ending_type:
            suggestions.append(
                f"期望的结尾类型是{self.QUALITY_INDICATORS[ending_type]['name']}，"
                f"但实际是{self.QUALITY_INDICATORS[actual_ending_type]['name']}"
            )

        # 计算综合得分
        base_ending_score = best_type[1]["score"]
        score = (base_ending_score * 0.7 + word_score * 0.3)
        score = max(0.0, min(1.0, score))

        has_good_ending = (
            score >= 0.6
            and len(found_indicators.get(actual_ending_type, [])) > 0
        )

        if not has_good_ending and not issue:
            suggestions.append("建议在结尾处添加明确的结尾类型特征词")

        return {
            "score": round(score, 3),
            "word_count": word_count,
            "ending_type": actual_ending_type,
            "ending_type_name": self.QUALITY_INDICATORS[actual_ending_type]["name"],
            "has_good_ending": has_good_ending,
            "issue": issue,
            "suggestions": suggestions,
            "quality_score": quality_scores,
        }

    def check_multiple_endings(
        self,
        chapter_contents: List[str],
        ending_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """批量检查多个章节结尾.

        Args:
            chapter_contents: 章节内容列表
            ending_types: 对应的期望结尾类型列表（可选）

        Returns:
            每个章节的检查结果列表
        """
        results = []
        for i, content in enumerate(chapter_contents):
            ending_type = ending_types[i] if ending_types and i < len(ending_types) else None
            results.append(self.check(content, ending_type))
        return results

    def get_supported_ending_types(self) -> List[str]:
        """获取支持的结尾类型列表.

        Returns:
            支持的结尾类型ID列表
        """
        return list(self.QUALITY_INDICATORS.keys())

    def get_ending_type_name(self, ending_type: str) -> str:
        """获取结尾类型的中文名称.

        Args:
            ending_type: 结尾类型ID

        Returns:
            中文名称，如果类型不存在则返回"未知"
        """
        return self.QUALITY_INDICATORS.get(ending_type, {}).get("name", "未知")
