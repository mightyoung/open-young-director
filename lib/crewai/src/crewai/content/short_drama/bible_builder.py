"""ShortDramaBibleBuilder - 从 ProductionBible 构建 ShortDramaBible

将完整的小说 ProductionBible 转换为短剧专用的 ShortDramaBible：
- 只提取本集相关的角色
- 简化世界观规则
- 提取本集的剧情承接
"""

from crewai.content.novel.production_bible.bible_types import (
    CharacterProfile,
    ProductionBible,
    WorldRules,
)
from crewai.content.short_drama.short_drama_types import (
    ShortDramaBible,
)


class ShortDramaBibleBuilder:
    """从 ProductionBible 构建 ShortDramaBible

    负责从完整的小说 ProductionBible 中提取本集所需的信息，
    构建适合短剧生成的 ShortDramaBible。
    """

    # 视觉风格映射
    VISUAL_STYLE_MAP = {
        "xianxia": "古风仙侠",
        "doushi": "都市异能",
        "科幻": "未来科幻",
        "modern": "现代都市",
        "fantasy": "西方奇幻",
    }

    # 基调映射
    TONE_MAP = {
        "xianxia": "古风",
        "doushi": "现代",
        "科幻": "科幻",
        "modern": "现代",
        "fantasy": "奇幻",
    }

    def __init__(self, style: str = "xianxia"):
        """初始化 Builder

        Args:
            style: 小说风格 (xianxia, doushi, modern, etc.)
        """
        self.style = style

    def build(
        self,
        bible: ProductionBible,
        episode_num: int,
        series_title: str,
        episode_context: str = "",
        characters_in_episode: list[str] = None,
    ) -> ShortDramaBible:
        """构建短剧圣经

        Args:
            bible: 完整的 ProductionBible
            episode_num: 目标集号
            series_title: 系列标题
            episode_context: 本集剧情承接描述
            characters_in_episode: 本集出场的角色名列表（可选）

        Returns:
            ShortDramaBible: 短剧专用圣经
        """
        # 提取相关角色
        relevant_characters = self._extract_relevant_characters(
            bible, episode_num, characters_in_episode
        )

        # 提取世界观摘要
        world_rules_summary = self._summarize_world_rules(bible.world_rules)

        # 确定视觉风格
        visual_style = self._determine_visual_style(bible)

        # 确定基调
        tone = self._determine_tone(bible)

        return ShortDramaBible(
            episode_num=episode_num,
            series_title=series_title,
            relevant_characters=relevant_characters,
            world_rules_summary=world_rules_summary,
            episode_context=episode_context,
            visual_style=visual_style,
            tone=tone,
        )

    def _extract_relevant_characters(
        self,
        bible: ProductionBible,
        episode_num: int,
        characters_in_episode: list[str] = None,
    ) -> dict[str, CharacterProfile]:
        """提取本集相关角色

        Args:
            bible: 完整 ProductionBible
            episode_num: 目标集号
            characters_in_episode: 如果提供，只返回这些角色

        Returns:
            dict[str, CharacterProfile]: 角色名 → 角色档案
        """
        if characters_in_episode:
            # 如果提供了角色列表，只返回这些角色
            return {
                name: bible.get_character(name)
                for name in characters_in_episode
                if bible.get_character(name)
            }

        # 否则从 timeline 中推断本集角色
        relevant: dict[str, CharacterProfile] = {}

        # 查找本集的事件
        for event in bible.timeline:
            if event.chapter_range[0] <= episode_num <= event.chapter_range[1]:
                for char_name in event.involved_characters:
                    char = bible.get_character(char_name)
                    if char and char_name not in relevant:
                        relevant[char_name] = char

        # 确保主角一定在列表中
        for name, char in bible.characters.items():
            if char.role == "protagonist" and name not in relevant:
                relevant[name] = char

        return relevant

    def _summarize_world_rules(self, world_rules: WorldRules | None) -> str:
        """生成简化版世界观规则

        Args:
            world_rules: 世界规则

        Returns:
            str: 格式化的世界规则摘要
        """
        if not world_rules:
            return "无特殊世界规则限制"

        parts = []

        # 力量体系
        if world_rules.power_system_name:
            parts.append(f"力量体系：{world_rules.power_system_name}")

        # 等级
        if world_rules.cultivation_levels:
            levels_str = " → ".join(world_rules.cultivation_levels[:5])
            if len(world_rules.cultivation_levels) > 5:
                levels_str += f"（共{len(world_rules.cultivation_levels)}级）"
            parts.append(f"等级：{levels_str}")

        # 地理
        if world_rules.geography:
            locations = list(world_rules.geography.keys())[:3]
            if locations:
                parts.append(f"主要地点：{', '.join(locations)}")

        # 约束
        if world_rules.world_constraints:
            constraints = "；".join(world_rules.world_constraints[:2])
            parts.append(f"基本规则：{constraints}")

        return "；".join(parts) if parts else "无特殊限制"

    def _determine_visual_style(self, bible: ProductionBible) -> str:
        """确定视觉风格

        Args:
            bible: ProductionBible

        Returns:
            str: 视觉风格描述
        """
        # 优先使用 bible 中的风格标记
        if hasattr(bible, 'visual_style') and bible.visual_style:
            return bible.visual_style

        # 从风格映射获取
        style_lower = self.style.lower()
        for key, style in self.VISUAL_STYLE_MAP.items():
            if key in style_lower:
                return style

        # 默认返回风格
        return self.TONE_MAP.get(style_lower, "写实风格")

    def _determine_tone(self, bible: ProductionBible) -> str:
        """确定整体基调

        Args:
            bible: ProductionBible

        Returns:
            str: 基调描述
        """
        # 优先使用 bible 中的基调
        if hasattr(bible, 'tone') and bible.tone:
            return bible.tone

        # 从风格映射获取
        style_lower = self.style.lower()
        for key, tone in self.TONE_MAP.items():
            if key in style_lower:
                return tone

        return "写实"


__all__ = ["ShortDramaBibleBuilder"]
