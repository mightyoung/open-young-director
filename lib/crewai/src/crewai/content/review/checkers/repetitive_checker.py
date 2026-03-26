"""套路重复检查器 - 检测重复的剧情模式."""

from typing import Dict, List, Optional


class RepetitivePatternChecker:
    """套路重复检查器.

    检测小说中的重复剧情模式（如修炼突破、打脸、绝境逢生等），
    避免套路化使用过于频繁。
    """

    # 套路模式配置
    PLAGUE_PATTERNS = {
        "xiuxian": {
            "name": "修炼突破",
            "max_frequency": 3,  # 每50章不超过3次
            "keywords": [
                "修炼",
                "突破",
                "功法",
                "境界",
                "闭关",
                "顿悟",
                "领悟",
            ],
            "chapter_ratio": 50,  # 基准章节数
            "description": "主角通过修炼获得实力提升的剧情",
        },
        "daface": {
            "name": "打脸",
            "max_frequency": 2,  # 每20章不超过2次
            "keywords": [
                "打脸",
                "狠狠打脸",
                "颜面尽失",
                "啪啪打脸",
                "当场打脸",
                "羞愧难当",
                "无地自容",
            ],
            "chapter_ratio": 20,
            "description": "主角反杀或证明自己，让对手丢脸的剧情",
        },
        "yingxiong": {
            "name": "英雄救美",
            "max_frequency": 2,  # 每100章不超过2次
            "keywords": [
                "英雄救美",
                "挺身而出",
                "及时出现",
                "从天而降",
                "护在身前",
            ],
            "chapter_ratio": 100,
            "description": "主角在危难时刻救助他人的剧情",
        },
        "juejing": {
            "name": "绝境逢生",
            "max_frequency": 1,  # 每30章不超过1次
            "keywords": [
                "绝境逢生",
                "置之死地",
                "死里逃生",
                "起死回生",
                "绝处逢生",
                "九死一生",
            ],
            "chapter_ratio": 30,
            "description": "主角在绝境中获得转机的剧情",
        },
        "shengji": {
            "name": "升级换地图",
            "max_frequency": 1,  # 每200章不超过1次
            "keywords": [
                "飞升",
                "穿越",
                "进入新世界",
                "打开新世界",
                "新的世界",
                "境界飞升",
            ],
            "chapter_ratio": 200,
            "description": "主角突破到新境界或进入新世界的剧情",
        },
        "fuchen": {
            "name": "复仇",
            "max_frequency": 2,  # 每50章不超过2次
            "keywords": [
                "复仇",
                "报仇",
                "血债血偿",
                "加倍奉还",
                "以牙还牙",
            ],
            "chapter_ratio": 50,
            "description": "主角向仇人报复的剧情",
        },
        "tufei": {
            "name": "退婚废柴流",
            "max_frequency": 1,  # 每100章不超过1次
            "keywords": [
                "退婚",
                "废物",
                "天才",
                "废柴",
                "觉醒",
                "血脉",
            ],
            "chapter_ratio": 100,
            "description": "主角从被轻视到证明自己的经典开局模式",
        },
        "tianjia": {
            "name": "舔狗舔到一无所有",
            "max_frequency": 1,  # 每80章不超过1次
            "keywords": [
                "舔狗",
                "备胎",
                "付出一切",
                "一无所有",
                "被抛弃",
            ],
            "chapter_ratio": 80,
            "description": "负面情感模式，主角过度付出后觉醒",
        },
    }

    def __init__(self):
        """初始化套路重复检查器."""
        pass

    def check(self, content: str, chapter_num: int) -> Dict:
        """检测套路重复.

        Args:
            content: 小说内容
            chapter_num: 当前章节数（用于计算允许频率）

        Returns:
            包含以下键的字典:
                - has_repetitive: 是否存在套路重复问题
                - warnings: 警告列表
                - summary: 总结信息
                - pattern_stats: 各模式统计
        """
        if not content:
            return {
                "has_repetitive": False,
                "warnings": [],
                "summary": "内容为空，无法检测",
                "pattern_stats": {},
            }

        warnings = []
        pattern_stats = {}

        for pattern_id, config in self.PLAGUE_PATTERNS.items():
            # 统计该模式所有关键词出现次数
            count = sum(content.count(kw) for kw in config["keywords"])

            if count > 0:
                # 根据章节数计算允许的最大频率
                max_allowed = (chapter_num / config["chapter_ratio"]) * config["max_frequency"]

                # 计算超标程度
                if count > max_allowed:
                    severity = "high" if count > max_allowed * 1.5 else "medium"
                    overuse_ratio = (count - max_allowed) / max_allowed * 100 if max_allowed > 0 else float("inf")

                    warnings.append({
                        "pattern_id": pattern_id,
                        "pattern": config["name"],
                        "count": count,
                        "max_allowed": round(max_allowed, 1),
                        "severity": severity,
                        "overuse_ratio": round(overuse_ratio, 1),
                        "suggestion": self._generate_suggestion(
                            config["name"], count, max_allowed
                        ),
                        "description": config["description"],
                    })

                pattern_stats[pattern_id] = {
                    "name": config["name"],
                    "count": count,
                    "max_allowed": round(max_allowed, 1),
                    "within_limit": count <= max_allowed,
                }

        # 按严重程度排序
        warnings.sort(key=lambda x: (
            0 if x["severity"] == "high" else 1,
            -x["overuse_ratio"]
        ))

        return {
            "has_repetitive": len(warnings) > 0,
            "warnings": warnings,
            "summary": f"检测到{len(warnings)}种套路问题" if warnings else "无套路问题",
            "pattern_stats": pattern_stats,
            "chapter_num": chapter_num,
        }

    def check_multiple_chapters(
        self, chapter_contents: List[str], start_chapter: int = 1
    ) -> List[Dict]:
        """按章节检测套路重复.

        Args:
            chapter_contents: 章节内容列表
            start_chapter: 起始章节号

        Returns:
            每个章节的套路检测结果
        """
        results = []
        for i, content in enumerate(chapter_contents):
            chapter_num = start_chapter + i
            results.append(self.check(content, chapter_num))
        return results

    def check_full_novel(
        self, full_content: str, total_chapters: int
    ) -> Dict:
        """检测整本小说的套路问题.

        Args:
            full_content: 完整小说内容
            total_chapters: 总章节数

        Returns:
            包含整体和分段分析的检测结果
        """
        # 整体检测
        overall_result = self.check(full_content, total_chapters)

        # 按模式分组统计
        pattern_overview = {}
        for pattern_id, config in self.PLAGUE_PATTERNS.items():
            count = sum(full_content.count(kw) for kw in config["keywords"])
            expected_count = (total_chapters / config["chapter_ratio"]) * config["max_frequency"]

            pattern_overview[pattern_id] = {
                "name": config["name"],
                "actual_count": count,
                "expected_count": round(expected_count, 1),
                "ratio": round(count / expected_count, 2) if expected_count > 0 else 0,
                "status": "excessive" if count > expected_count else "normal",
            }

        overall_result["pattern_overview"] = pattern_overview

        # 计算套路化指数（越高表示套路化越严重）
        total_overuse = sum(
            w["overuse_ratio"] for w in overall_result["warnings"]
        )
        overuse_index = min(total_overuse / 100, 1.0)  # 归一化到0-1
        overall_result["overuse_index"] = round(overuse_index, 3)
        overall_result["overuse_level"] = (
            "严重" if overuse_index > 0.8
            else "较重" if overuse_index > 0.5
            else "一般" if overuse_index > 0.2
            else "正常"
        )

        return overall_result

    def _generate_suggestion(
        self, pattern_name: str, count: int, max_allowed: float
    ) -> str:
        """生成改进建议.

        Args:
            pattern_name: 模式名称
            count: 实际出现次数
            max_allowed: 最大允许次数

        Returns:
            改进建议字符串
        """
        if count > max_allowed * 2:
            return (
                f"{pattern_name}出现{count}次，严重超过允许值，"
                f"建议删除或大幅减少该模式的使用"
            )
        elif count > max_allowed:
            return (
                f"{pattern_name}出现{count}次，超过允许值，"
                f"建议适当减少"
            )
        return f"{pattern_name}出现{count}次，在允许范围内"

    def get_pattern_info(self, pattern_id: str) -> Optional[Dict]:
        """获取特定套路模式的详细信息.

        Args:
            pattern_id: 模式ID

        Returns:
            模式配置信息，如果不存在返回None
        """
        config = self.PLAGUE_PATTERNS.get(pattern_id, {})
        if not config:
            return None
        return {
            "id": pattern_id,
            "name": config["name"],
            "keywords": config["keywords"],
            "max_frequency": config["max_frequency"],
            "chapter_ratio": config["chapter_ratio"],
            "description": config["description"],
        }

    def get_all_patterns(self) -> List[Dict]:
        """获取所有套路模式列表.

        Returns:
            所有套路模式的配置信息列表
        """
        return [
            {
                "id": pattern_id,
                "name": config["name"],
                "keywords": config["keywords"],
                "max_frequency": config["max_frequency"],
                "chapter_ratio": config["chapter_ratio"],
                "description": config["description"],
            }
            for pattern_id, config in self.PLAGUE_PATTERNS.items()
        ]
