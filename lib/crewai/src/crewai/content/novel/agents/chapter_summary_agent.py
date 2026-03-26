"""章节概要Agent (Chapter Summary Agent)

在章节正文写作之前，生成每个章节的详细概要：
- 章节核心目的（本章在整体故事中的作用）
- 主要事件序列
- 角色出场和弧线
- 伏笔铺设/回收
- 张力节奏
- POV 视角注意

这与章节正文写作是独立的阶段，便于：
1. 在写作前审核章节计划
2. 调整章节顺序或合并/拆分章节
3. 确保伏笔铺设有计划

使用示例:
    agent = ChapterSummaryAgent()
    summaries = agent.generate_batch(volume_outlines, world_data)
"""

from typing import TYPE_CHECKING

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.novel.production_bible.bible_types import BibleSection


class ChapterSummaryAgent:
    """章节概要Agent

    在章节正文写作之前，生成每个章节的详细概要。
    这是一个独立的中间产物层，与正文写作解耦。

    使用示例:
        agent = ChapterSummaryAgent()
        summaries = agent.generate_for_volume(volume_outline, world_data, volume_num)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化章节概要Agent

        Args:
            llm: 可选的语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="章节规划专家",
            goal="设计完整且可执行的章节概要",
            backstory="""你是一个专业的小说大纲设计师，精通故事节奏和章节结构。
            你能在动笔之前精确规划每个章节的核心目的、关键事件、角色弧线和节奏安排。
            你的章节概要既是写作蓝图，也是质量检查清单。""",
            verbose=verbose,
            llm=llm,
        )

    def generate_for_volume(
        self,
        volume_outline: dict,
        world_data: dict,
        volume_num: int,
    ) -> list[dict]:
        """为单个卷生成所有章节概要

        Args:
            volume_outline: 卷大纲（来自 VolumeOutlineAgent）
            world_data: 世界观数据
            volume_num: 卷编号

        Returns:
            list[dict]: 该卷所有章节的概要列表
        """
        prompt = self._build_prompt(volume_outline, world_data, volume_num)
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result, volume_outline)

    def generate_for_volume_with_bible(
        self,
        volume_outline: dict,
        world_data: dict,
        volume_num: int,
        bible_section: "BibleSection",  # Import from production_bible
    ) -> list[dict]:
        """为单个卷生成章节概要（带BibleSection约束）

        BibleSection 包含本卷相关的角色、世界规则、时间线和伏笔信息。
        这些 canonical facts 会注入到 prompt 中，确保生成的章节概要与 bible 一致。

        Args:
            volume_outline: 卷大纲
            world_data: 世界观数据
            volume_num: 卷编号
            bible_section: 本卷相关的 BibleSection

        Returns:
            list[dict]: 该卷所有章节的概要列表
        """
        prompt = self._build_prompt_with_bible(volume_outline, world_data, volume_num, bible_section)
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result, volume_outline)

    def _build_prompt_with_bible(
        self,
        volume_outline: dict,
        world_data: dict,
        volume_num: int,
        bible_section: "BibleSection",
    ) -> str:
        """构建带 BibleSection 约束的章节概要提示词"""
        import json
        from crewai.content.novel.production_bible.bible_types import BibleSection

        world_str = self._format_world(world_data)
        volume_str = json.dumps(volume_outline, ensure_ascii=False, default=str)

        # Build character context from bible
        char_context = ""
        if hasattr(bible_section, 'relevant_characters') and bible_section.relevant_characters:
            for char_name, char in bible_section.relevant_characters.items():
                rel_info = ""
                if hasattr(bible_section, 'relationship_states_at_start') and char_name in bible_section.relationship_states_at_start:
                    rels = bible_section.relationship_states_at_start[char_name]
                    rel_info = "关系：" + "; ".join(f"{k}: {v}" for k, v in rels.items())
                char_context += f"""
- {char.name}（{getattr(char, 'role', '未知角色')}）{getattr(char, 'personality', '')[:50] if getattr(char, 'personality', '') else ''}
  欲望：{getattr(char, 'core_desire', '未知')} | 背景：{getattr(char, 'backstory', '')[:50] if getattr(char, 'backstory', '') else ''}
  {rel_info}
"""
        if not char_context:
            char_context = "无特定角色要求"

        # Build world rules context
        world_rules_context = getattr(bible_section, 'world_rules_summary', '无特殊世界规则') or '无特殊世界规则'

        # Build open foreshadowing
        foreshadowing_context = ""
        if hasattr(bible_section, 'open_foreshadowing') and bible_section.open_foreshadowing:
            for fs in bible_section.open_foreshadowing:
                setup_ch = getattr(fs, 'setup_chapter', '?')
                payoff_ch = getattr(fs, 'payoff_chapter', '?')
                foreshadowing_context += f"""
- 第{setup_ch}卷第{setup_ch}章 伏笔：{getattr(fs, 'setup_description', '未知')}
  需在第{payoff_ch}卷回收：{getattr(fs, 'payoff_description', '未知')}
"""
        if not foreshadowing_context:
            foreshadowing_context = "无进行中的伏笔"

        # Build canonical facts
        facts_context = ""
        if hasattr(bible_section, 'canonical_facts_this_volume') and bible_section.canonical_facts_this_volume:
            facts_context = "必须遵守的事实：\n" + "\n".join(f"• {f}" for f in bible_section.canonical_facts_this_volume)
        else:
            facts_context = "无强制约束事实"

        return f"""为第{volume_num}卷生成详细的章节概要。

## 本卷大纲
{volume_str}

## 世界观
{world_str}

## 角色约束（来自 Production Bible）
以下角色必须按照以下设定出现，不得改变其核心性格：
{char_context}

## 世界规则约束
{world_rules_context}

## 进行中的伏笔（必须在适当章节回收）
{foreshadowing_context}

## Canonical Facts（必须遵守）
{facts_context}

## 任务要求
基于本卷大纲和Bible约束，为每个章节生成详细概要。章节概要应该：

1. **章节目的 (Purpose)**: 本章在卷中的作用
2. **关键事件 (Key Events)**: 2-4个本章最重要的情节点，必须与Bible中的角色设定一致
3. **角色弧线 (Character Arcs)**: 本章中角色的心理/关系变化，遵循Bible中的角色设定
4. **张力节奏 (Tension Rhythm)**: 开场→发展→高潮→结尾的张力分布
5. **伏笔安排 (Foreshadowing)**: 本章是否包含Bible中列出的伏笔setup
6. **POV 注意**: 视角注意事项

## 格式要求
每个章节概要格式：
{{
    "chapter_num": 1,
    "volume_num": {volume_num},
    "title": "章节标题",
    "purpose": "本章核心目的",
    "summary_paragraph": "200-300字的章节概要",
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": {{
        "角色名": "本章中该角色的变化"
    }},
    "tension_arc": {{
        "opening": 3,
        "development": 5,
        "climax": 8,
        "resolution": 6
    }},
    "foreshadowing": [
        {{"setup": "铺设内容", "payoff_chapter": "第X章回收"}}
    ],
    "pov_notes": "视角注意事项",
    "word_target": 3000
}}

以JSON数组格式返回本卷所有章节概要。"""

    def generate_batch(
        self,
        volume_outlines: list[dict],
        world_data: dict,
    ) -> list[dict]:
        """批量生成所有卷的章节概要

        Args:
            volume_outlines: 所有卷的大纲列表
            world_data: 世界观数据

        Returns:
            list[dict]: 所有章节概要（按卷和章节编号排序）
        """
        all_summaries = []
        for volume_outline in volume_outlines:
            volume_num = volume_outline.get("volume_num", 1)
            chapter_summaries = self.generate_for_volume(volume_outline, world_data, volume_num)
            all_summaries.extend(chapter_summaries)
        return all_summaries

    def _build_prompt(
        self,
        volume_outline: dict,
        world_data: dict,
        volume_num: int,
    ) -> str:
        """构建章节概要提示词"""
        import json

        world_str = self._format_world(world_data)

        return f"""为第{volume_num}卷生成详细的章节概要。

## 本卷大纲
{json.dumps(volume_outline, ensure_ascii=False, default=str)}

## 世界观
{world_str}

## 任务要求
基于本卷大纲，为每个章节生成详细概要。章节概要应该：

1. **章节目的 (Purpose)**: 本章在卷中的作用，是推进主线、副线还是伏笔
2. **关键事件 (Key Events)**: 2-4个本章最重要的情节点
3. **角色弧线 (Character Arcs)**: 本章中角色的心理/关系变化
4. **张力节奏 (Tension Rhythm)**: 开场→发展→高潮→结尾的张力分布
5. **伏笔安排 (Foreshadowing)**: 本章铺设的伏笔（如果有），以及回收时机
6. **视角注意 (POV Notes)**: 视角切换、内心访问权限等注意事项

## 格式要求
每个章节概要格式：
{{
    "chapter_num": 1,
    "volume_num": {volume_num},
    "title": "章节标题",
    "purpose": "本章核心目的，一句话描述",
    "summary_paragraph": "200-300字的章节概要，描述本章发生了什么",
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": {{
        "角色名": "本章中该角色的变化"
    }},
    "tension_arc": {{
        "opening": 3,
        "development": 5,
        "climax": 8,
        "resolution": 6
    }},
    "foreshadowing": [
        {{"setup": "铺设内容", "payoff_chapter": "第X章回收"}}
    ],
    "pov_notes": "视角注意事项",
    "word_target": 3000
}}

以JSON数组格式返回本卷所有章节概要：
[
    {{...}},  # 第1章
    {{...}},  # 第2章
    ...
]

请确保章节概要之间有逻辑连贯性，前一章的悬念能在后续得到回应或推进。"""

    def _format_world(self, world_data: dict) -> str:
        """格式化世界观数据"""
        import json
        s = json.dumps(world_data, ensure_ascii=False, default=str)
        if len(s) > 800:
            return s[:800] + "..."
        return s

    def _parse_result(self, result, volume_outline: dict) -> list[dict]:
        """解析结果"""
        import json
        import re

        raw_text = ""
        if hasattr(result, "raw"):
            raw_text = result.raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)

        # 尝试提取JSON数组
        try:
            json_match = re.search(r"\[[\s\S]*\]", raw_text)
            if json_match:
                summaries = json.loads(json_match.group())
                return summaries
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: 从 volume_outline 提取 chapters_summary
        return volume_outline.get("chapters_summary", [])
