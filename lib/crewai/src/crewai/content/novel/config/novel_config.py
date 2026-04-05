"""Novel generation typed configuration."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NovelConfig:
    """小说生成的显式类型配置。

    替代隐式 dict 配置，提供强类型检查和清晰的接口契约。
    """

    # Required fields
    topic: str = ""

    # Style and genre
    style: str = "urban"  # urban/xianxia/doushi/modern
    genre: str = ""  # Defaults to style if empty

    # Word count and chapters
    target_words: int = 100000
    num_chapters: int = 0  # 0 = auto-calculate based on target_words

    # Volume configuration
    num_volumes: int = 0  # 0 = auto-calculate based on chapters
    chapters_per_volume: int = 0  # 0 = auto-calculate
    max_concurrent_volumes: int = 3

    # Chapter word count targets
    words_per_chapter_target: int = 5000  # 每章目标字数
    words_per_chapter_min: int = 3000  # 每章最低字数
    words_per_chapter_max: int = 8000  # 每章最高字数

    # LLM configuration
    llm: Optional[Any] = None

    # Output
    output_dir: str = "./novel_output"

    # Writing modes
    use_orchestrator: bool = True
    max_subagent_concurrent: int = 5
    max_concurrent_scenes: int = 3

    # Feature flags
    enable_verification: bool = True
    enable_evolution: bool = True
    review_each_chapter: bool = False
    approval_mode: bool = False

    # Seed for deterministic replay
    seed: Optional[str] = None
    seed_variant: Optional[str] = None

    # Style-specific chapter configurations (words_per_chapter by style)
    _STYLE_CHAPTER_CONFIGS: dict = field(default_factory=lambda: {
        "xianxia": {"words_per_chapter_target": 6000, "words_per_chapter_min": 4000, "words_per_chapter_max": 10000},
        "urban": {"words_per_chapter_target": 4000, "words_per_chapter_min": 2500, "words_per_chapter_max": 6000},
        "doushi": {"words_per_chapter_target": 5000, "words_per_chapter_min": 3500, "words_per_chapter_max": 8000},
        "modern": {"words_per_chapter_target": 3500, "words_per_chapter_min": 2000, "words_per_chapter_max": 5000},
    }, repr=False)

    def __post_init__(self):
        """Post-initialization processing with smart chapter/volume calculation."""
        # Apply style-specific chapter word count configs
        style_config = self._STYLE_CHAPTER_CONFIGS.get(self.style, {})
        if style_config and self.words_per_chapter_target == 5000:  # Only override if still default
            self.words_per_chapter_target = style_config.get("words_per_chapter_target", 5000)
        if self.words_per_chapter_min == 3000:
            self.words_per_chapter_min = style_config.get("words_per_chapter_min", 3000)
        if self.words_per_chapter_max == 8000:
            self.words_per_chapter_max = style_config.get("words_per_chapter_max", 8000)

        # Auto-calculate num_chapters if not set
        if self.num_chapters <= 0:
            self.num_chapters = self._calculate_chapters()

        # Auto-calculate num_volumes if not set
        if self.num_volumes <= 0:
            self.num_volumes = self._optimal_volumes_for_chapters(self.num_chapters)

        # Auto-calculate chapters_per_volume if not set
        if self.chapters_per_volume <= 0:
            self.chapters_per_volume = self.num_chapters // self.num_volumes

        # Default genre to style if empty
        if not self.genre:
            self.genre = self.style

    def _calculate_chapters(self) -> int:
        """根据目标字数和风格自动计算章节数。

        Returns:
            int: 计算出的章节数
        """
        if self.target_words <= 0:
            return 10  # Default fallback

        # 基础计算：目标字数 / 每章目标字数
        base_chapters = max(1, self.target_words // self.words_per_chapter_target)

        # 调整为结构化数字（便于分卷）
        return self._round_to_structure(base_chapters)

    def _optimal_volumes_for_chapters(self, total_chapters: int) -> int:
        """根据总章节数计算最优卷数。

        经验规则：
        - 30章以下: 2-3卷
        - 30-60章: 3-4卷
        - 60-120章: 4-6卷
        - 120-200章: 6-8卷
        - 200章以上: 8-10卷

        Args:
            total_chapters: 总章节数

        Returns:
            int: 最优卷数
        """
        if total_chapters <= 30:
            return max(2, min(3, total_chapters // 10 + 1))
        elif total_chapters <= 60:
            return max(3, min(4, total_chapters // 15 + 1))
        elif total_chapters <= 120:
            return max(4, min(6, total_chapters // 20 + 2))
        elif total_chapters <= 200:
            return max(6, min(8, total_chapters // 25 + 3))
        else:
            return max(8, min(10, total_chapters // 30 + 4))

    def _round_to_structure(self, num: int) -> int:
        """将数字调整为结构化数字（便于分卷）。

        例如 47 -> 45, 73 -> 75

        Args:
            num: 原始数字

        Returns:
            int: 调整后的数字
        """
        if num <= 10:
            return max(1, num)

        # 找到最接近的 5 的倍数
        return max(1, round(num / 5) * 5)

    def get_volume_distribution(self) -> list[int]:
        """获取各卷章节分布（尽量均匀）。

        Returns:
            list[int]: 每卷的章节数列表
        """
        base = self.num_chapters // self.num_volumes
        remainder = self.num_chapters % self.num_volumes

        distribution = []
        for i in range(self.num_volumes):
            # 前 remainder 卷多分配 1 章
            chapters = base + (1 if i < remainder else 0)
            distribution.append(chapters)

        return distribution

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于 NovelCrew 兼容）。

        Returns:
            dict: 兼容 NovelCrew 的配置字典
        """
        return {
            "topic": self.topic,
            "style": self.style,
            "genre": self.genre,
            "target_words": self.target_words,
            "num_chapters": self.num_chapters,
            "num_volumes": self.num_volumes,
            "chapters_per_volume": self.chapters_per_volume,
            "words_per_chapter_target": self.words_per_chapter_target,
            "max_concurrent_volumes": self.max_concurrent_volumes,
            "llm": self.llm,
            "output_dir": self.output_dir,
            "use_orchestrator": self.use_orchestrator,
            "max_subagent_concurrent": self.max_subagent_concurrent,
            "max_concurrent_scenes": self.max_concurrent_scenes,
            "enable_verification": self.enable_verification,
            "enable_evolution": self.enable_evolution,
            "review_each_chapter": self.review_each_chapter,
            "approval_mode": self.approval_mode,
            "seed": self.seed,
            "seed_variant": self.seed_variant,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NovelConfig":
        """从字典创建配置。

        Args:
            data: 配置字典

        Returns:
            NovelConfig: 实例
        """
        return cls(
            topic=data.get("topic", ""),
            style=data.get("style", "urban"),
            genre=data.get("genre", data.get("style", "")),
            target_words=data.get("target_words", 100000),
            num_chapters=data.get("num_chapters", 0),
            num_volumes=data.get("num_volumes", 0),  # 0 = auto-calculate
            chapters_per_volume=data.get("chapters_per_volume", 0),  # 0 = auto-calculate
            words_per_chapter_target=data.get("words_per_chapter_target", 5000),
            max_concurrent_volumes=data.get("max_concurrent_volumes", 3),
            llm=data.get("llm"),
            output_dir=data.get("output_dir", "./novel_output"),
            use_orchestrator=data.get("use_orchestrator", True),
            max_subagent_concurrent=data.get("max_subagent_concurrent", 5),
            max_concurrent_scenes=data.get("max_concurrent_scenes", 3),
            enable_verification=data.get("enable_verification", True),
            enable_evolution=data.get("enable_evolution", True),
            review_each_chapter=data.get("review_each_chapter", False),
            approval_mode=data.get("approval_mode", False),
            seed=data.get("seed"),
            seed_variant=data.get("seed_variant"),
        )


