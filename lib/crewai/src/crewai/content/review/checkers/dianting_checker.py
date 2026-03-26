"""垫听检查器 - 检测章节结尾是否有效铺垫下一章."""

from typing import Dict, List


class DiantingChecker:
    """垫听检查器 - 检测章节结尾铺垫.

    垫听是指在章节结尾处设置悬念或情节钩子，
    让读者期待下一章的内容。
    """

    PLAGUE_THRESHOLD = 0.6

    # 悬念词库
    SUSPENSE_WORDS = [
        "然而",
        "但是",
        "没想到",
        "突然",
        "就在这时",
        "谁知",
        "却不料",
        "出人意料",
        "刹那间",
        "霎时间",
    ]

    # 情节钩子词库
    HOOK_PHRASES = [
        "正在这时",
        "突然",
        "却不料",
        "谁知",
        "就在此时",
        "忽听",
        "只见",
        "但见",
        "忽然",
        "猛然",
    ]

    def __init__(self, threshold: float = 0.6):
        """初始化垫听检查器.

        Args:
            threshold: 垫听评分阈值，高于此值认为有效铺垫
        """
        self.threshold = threshold

    def check(self, chapter_end: str, next_chapter_start: str = "") -> Dict:
        """检查章节结尾是否有效铺垫下一章.

        Args:
            chapter_end: 章节结尾内容
            next_chapter_start: 下一章开头内容（可选）

        Returns:
            包含以下键的字典:
                - score: 垫听评分 (0-1)
                - has_dianting: 是否有效铺垫
                - suggestions: 改进建议列表
                - suspense_found: 检测到的悬念词
                - hooks_found: 检测到的情节钩子
        """
        if not chapter_end:
            return {
                "score": 0.0,
                "has_dianting": False,
                "suggestions": ["章节结尾为空"],
                "suspense_found": [],
                "hooks_found": [],
            }

        # 检测悬念词
        suspense_found = [
            word for word in self.SUSPENSE_WORDS if word in chapter_end
        ]

        # 检测情节钩子
        hooks_found = [hook for hook in self.HOOK_PHRASES if hook in chapter_end]

        # 计算悬念得分
        suspense_score = len(suspense_found) / max(len(self.SUSPENSE_WORDS), 1) * 2
        suspense_score = min(suspense_score, 0.6)

        # 计算钩子得分
        hook_score = len(hooks_found) / max(len(self.HOOK_PHRASES), 1) * 2
        hook_score = min(hook_score, 0.4)

        # 综合评分
        score = suspense_score + hook_score
        score = max(0.0, min(1.0, score))

        has_dianting = score >= self.threshold

        # 生成建议
        suggestions = []
        if not has_dianting:
            if len(suspense_found) == 0:
                suggestions.append("建议添加悬念词，如：然而、但是、没想到、突然等")
            if len(hooks_found) == 0:
                suggestions.append("建议添加情节钩子，如：正在这时、谁知、却不料等")

        return {
            "score": round(score, 3),
            "has_dianting": has_dianting,
            "suggestions": suggestions,
            "suspense_found": suspense_found,
            "hooks_found": hooks_found,
        }

    def check_batch(self, chapter_endings: List[str]) -> List[Dict]:
        """批量检查多个章节结尾.

        Args:
            chapter_endings: 章节结尾内容列表

        Returns:
            每个章节结尾的检查结果列表
        """
        return [self.check(end) for end in chapter_endings]
