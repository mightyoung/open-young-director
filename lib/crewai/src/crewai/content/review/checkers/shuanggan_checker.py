"""爽感模式检查器 - 检测爽感类型和密度."""

from typing import Dict, List


class ShuangganPatternChecker:
    """爽感模式检查器.

    检测小说中的爽感类型（打脸、升级、英雄救美等）
    并计算爽感密度，避免套路化。
    """

    # 爽感模式配置
    SHUANGAN_PATTERNS = {
        "daface": {
            "name": "打脸",
            "keywords": [
                "打脸",
                "狠狠打脸",
                "颜面尽失",
                "啪啪打脸",
                "当场打脸",
                "脸被打得啪啪响",
                "羞愧难当",
                "无地自容",
            ],
            "weight": 1.5,
            "description": "主角反杀或证明自己，让对手丢脸",
        },
        "shengji": {
            "name": "升级",
            "keywords": [
                "突破",
                "升级",
                "晋升",
                "进阶",
                "提升",
                "修为大涨",
                "实力倍增",
                "连连突破",
            ],
            "weight": 1.2,
            "description": "主角实力提升、等级突破",
        },
        "yingxiong": {
            "name": "英雄救美",
            "keywords": [
                "英雄救美",
                "挺身而出",
                "及时出现",
                "从天而降",
                "及时雨",
                "护在身前",
                "挡在面前",
            ],
            "weight": 1.0,
            "description": "主角在危难时刻救助他人",
        },
        "juejing": {
            "name": "绝境逢生",
            "keywords": [
                "绝境逢生",
                "置之死地",
                "死里逃生",
                "起死回生",
                "转危为安",
                "绝处逢生",
                "九死一生",
            ],
            "weight": 1.3,
            "description": "主角在绝境中获得转机",
        },
        "fuchen": {
            "name": "复仇",
            "keywords": [
                "复仇",
                "报仇",
                "血债血偿",
                "加倍奉还",
                "以牙还牙",
                "讨回公道",
            ],
            "weight": 1.4,
            "description": "主角向仇人报复",
        },
        "dakuang": {
            "name": "大快人心",
            "keywords": [
                "大快人心",
                "拍手称快",
                "喜大普奔",
                "皆大欢喜",
                "痛快",
                "解气",
            ],
            "weight": 1.1,
            "description": "恶人受到惩罚，主角或读者感到痛快",
        },
        "niuxia": {
            "name": "牛x",
            "keywords": [
                "牛逼",
                "厉害",
                "太强了",
                "不可思议",
                "难以置信",
                "惊呆",
                "震呆",
            ],
            "weight": 0.8,
            "description": "主角表现超乎常人想象",
        },
    }

    def __init__(self, max_density: float = 0.4):
        """初始化爽感模式检查器.

        Args:
            max_density: 最大爽感密度阈值（每千字），超过此值认为过于密集
        """
        self.max_density = max_density

    def check(self, content: str) -> Dict:
        """检测爽感密度和分布.

        Args:
            content: 小说内容

        Returns:
            包含以下键的字典:
                - patterns: 检测到的爽感模式列表
                - total_density: 总爽感密度（每千字）
                - exceeds_limit: 是否超过密度限制
                - suggestions: 改进建议
                - pattern_summary: 各模式统计摘要
        """
        if not content:
            return {
                "patterns": [],
                "total_density": 0.0,
                "exceeds_limit": False,
                "suggestions": [],
                "pattern_summary": {},
            }

        total_words = len(content)
        total_words_1k = total_words / 1000  # 折算成千字
        found_patterns = []
        pattern_summary = {}

        for pattern_id, config in self.SHUANGAN_PATTERNS.items():
            # 统计该模式所有关键词出现次数
            count = sum(content.count(kw) for kw in config["keywords"])

            if count > 0:
                # 计算每千字的爽感密度
                density = count / total_words_1k
                # 加权密度
                weighted_density = density * config["weight"]

                pattern_info = {
                    "type": pattern_id,
                    "name": config["name"],
                    "count": count,
                    "density": round(density, 3),
                    "weighted_density": round(weighted_density, 3),
                    "weight": config["weight"],
                    "description": config["description"],
                }
                found_patterns.append(pattern_info)

                pattern_summary[pattern_id] = {
                    "name": config["name"],
                    "count": count,
                    "density": round(density, 3),
                }

        # 计算总加权爽感密度
        total_density = sum(
            p["density"] * p["weight"] for p in found_patterns
        )

        exceeds_limit = total_density > self.max_density

        # 生成建议
        suggestions = []
        if exceeds_limit:
            suggestions.append(
                f"爽感过于密集（密度：{total_density:.2f}），建议分散布局"
            )

        # 检查是否有单一模式过度使用
        sorted_patterns = sorted(
            found_patterns, key=lambda x: x["weighted_density"], reverse=True
        )
        if sorted_patterns:
            top_pattern = sorted_patterns[0]
            if top_pattern["density"] > self.max_density * 0.6:
                suggestions.append(
                    f"{top_pattern['name']}模式使用过于频繁，"
                    f"建议穿插其他爽感类型"
                )

        return {
            "patterns": found_patterns,
            "total_density": round(total_density, 3),
            "exceeds_limit": exceeds_limit,
            "suggestions": suggestions,
            "pattern_summary": pattern_summary,
            "word_count": total_words,
        }

    def check_by_chapters(
        self, chapter_contents: List[str]
    ) -> List[Dict]:
        """按章节检测爽感密度.

        Args:
            chapter_contents: 章节内容列表

        Returns:
            每个章节的爽感检测结果
        """
        return [self.check(content) for content in chapter_contents]

    def get_pattern_info(self, pattern_type: str) -> Dict:
        """获取特定爽感模式的详细信息.

        Args:
            pattern_type: 模式类型ID

        Returns:
            模式配置信息
        """
        config = self.SHUANGAN_PATTERNS.get(pattern_type, {})
        if not config:
            return {}
        return {
            "name": config["name"],
            "keywords": config["keywords"],
            "weight": config["weight"],
            "description": config["description"],
        }

    def get_all_patterns(self) -> List[Dict]:
        """获取所有爽感模式列表.

        Returns:
            所有爽感模式的配置信息列表
        """
        return [
            {
                "type": pattern_id,
                "name": config["name"],
                "keywords": config["keywords"],
                "weight": config["weight"],
                "description": config["description"],
            }
            for pattern_id, config in self.SHUANGAN_PATTERNS.items()
        ]
