"""视觉主题追踪器 - 追踪全剧视觉元素的一致性"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class VisualMotif:
    """视觉主题"""
    name: str  # 主题名称，如 "红色"、"镜子"、"窗户"
    description: str  # 描述
    occurrences: List[str] = field(default_factory=list)  # 出现位置
    symbolism: str = ""  # 象征意义
    development: str = ""  # 发展轨迹


class VisualMotifTracker:
    """视觉主题追踪器 - 追踪全剧视觉元素的一致性

    负责识别、追踪和提醒视觉主题（Visual Motifs）的使用，
    确保视觉元素在整个剧本中保持一致性和有意义的发展。

    使用示例:
        tracker = VisualMotifTracker()
        tracker.define_motifs(["红色", "镜子", "窗户"])
        tracker.record_occurrence("红色", "第一幕第一个场景 - 红色外套")
        motifs = tracker.get_all_motifs()
    """

    def __init__(self, llm: "LLM" = None):
        """初始化视觉主题追踪器

        Args:
            llm: 可选的语言模型，用于智能分析
        """
        self.llm = llm
        self._motifs: Dict[str, VisualMotif] = {}
        self._script_length: int = 0  # 剧本长度（页数）

    def define_motifs(self, motif_names: List[str]) -> None:
        """定义视觉主题列表

        Args:
            motif_names: 视觉主题名称列表
        """
        for name in motif_names:
            if name not in self._motifs:
                self._motifs[name] = VisualMotif(
                    name=name,
                    description="",
                    occurrences=[],
                    symbolism="",
                    development=""
                )

    def set_script_length(self, pages: int) -> None:
        """设置剧本长度

        Args:
            pages: 剧本总页数
        """
        self._script_length = pages

    def record_occurrence(
        self,
        motif_name: str,
        location: str,
        description: str = "",
    ) -> None:
        """记录视觉主题出现

        Args:
            motif_name: 主题名称
            location: 出现位置（如"第一幕场景3"）
            description: 描述
        """
        if motif_name not in self._motifs:
            self._motifs[motif_name] = VisualMotif(
                name=motif_name,
                description="",
                occurrences=[],
            )

        occurrence = f"{location}"
        if description:
            occurrence += f": {description}"

        self._motifs[motif_name].occurrences.append(occurrence)

    def update_symbolism(self, motif_name: str, symbolism: str) -> None:
        """更新主题的象征意义

        Args:
            motif_name: 主题名称
            symbolism: 象征意义描述
        """
        if motif_name in self._motifs:
            self._motifs[motif_name].symbolism = symbolism

    def update_development(self, motif_name: str, development: str) -> None:
        """更新主题的发展轨迹

        Args:
            motif_name: 主题名称
            development: 发展轨迹描述
        """
        if motif_name in self._motifs:
            self._motifs[motif_name].development = development

    def get_motif(self, motif_name: str) -> Optional[VisualMotif]:
        """获取指定主题

        Args:
            motif_name: 主题名称

        Returns:
            VisualMotif或None
        """
        return self._motifs.get(motif_name)

    def get_all_motifs(self) -> List[VisualMotif]:
        """获取所有视觉主题

        Returns:
            视觉主题列表
        """
        return list(self._motifs.values())

    def get_motifs_by_frequency(self) -> List[tuple[str, int]]:
        """获取按频率排序的主题

        Returns:
            (主题名, 出现次数)元组列表
        """
        return sorted(
            [(name, len(motif.occurrences)) for name, motif in self._motifs.items()],
            key=lambda x: x[1],
            reverse=True
        )

    def analyze_motif_distribution(self) -> Dict[str, float]:
        """分析主题在剧本中的分布

        Returns:
            主题名到分布比例的映射
        """
        if not self._script_length:
            return {name: 0.0 for name in self._motifs}

        distribution = {}
        for name, motif in self._motifs.items():
            # 计算在剧本前半/后半的出现比例
            first_half = sum(1 for occ in motif.occurrences if self._is_first_half(occ))
            ratio = first_half / len(motif.occurrences) if motif.occurrences else 0
            distribution[name] = ratio

        return distribution

    def _is_first_half(self, location: str) -> bool:
        """判断位置是否在剧本前半"""
        # 简单检查：包含"第一幕"或" Act I"等
        first_half_markers = ["第一幕", "Act I", "act i", "前半"]
        second_half_markers = ["第三幕", "Act III", "act iii", "后半", "结局"]

        for marker in second_half_markers:
            if marker in location:
                return False

        for marker in first_half_markers:
            if marker in location:
                return True

        return True  # 默认前半

    def check_consistency(self) -> List[str]:
        """检查视觉主题一致性

        Returns:
            问题/警告列表
        """
        warnings = []

        for name, motif in self._motifs.items():
            if not motif.occurrences:
                warnings.append(f"主题 '{name}' 定义后未出现")

            # 检查是否每个幕都有出现（对于重要主题）
            if len(motif.occurrences) > 3:
                acts_present = set()
                for occ in motif.occurrences:
                    for act in ["第一幕", "第二幕", "第三幕", "Act I", "Act II", "Act III"]:
                        if act in occ:
                            acts_present.add(act.split()[0] if " " in act else act)
                            break

                if len(acts_present) < 2:
                    warnings.append(
                        f"主题 '{name}' 出现次数较多但分布不均，仅出现在: {acts_present}"
                    )

        return warnings

    def generate_motif_report(self) -> str:
        """生成视觉主题报告

        Returns:
            格式化的报告字符串
        """
        if not self._motifs:
            return "暂无定义的视觉主题"

        lines = ["=" * 50, "视觉主题追踪报告", "=" * 50, ""]

        for name, motif in self._motifs.items():
            lines.append(f"\n主题: {motif.name}")
            lines.append(f"出现次数: {len(motif.occurrences)}")

            if motif.symbolism:
                lines.append(f"象征意义: {motif.symbolism}")

            if motif.development:
                lines.append(f"发展轨迹: {motif.development}")

            if motif.occurrences:
                lines.append("出现位置:")
                for occ in motif.occurrences:
                    lines.append(f"  - {occ}")

        warnings = self.check_consistency()
        if warnings:
            lines.append("\n警告:")
            for warning in warnings:
                lines.append(f"  ! {warning}")

        return "\n".join(lines)


__all__ = ["VisualMotifTracker", "VisualMotif"]
