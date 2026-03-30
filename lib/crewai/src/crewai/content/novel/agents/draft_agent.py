"""初稿写作Agent"""

from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.content.novel.production_bible.bible_types import BibleSection
    from crewai.llm import LLM


class DraftAgent:
    """初稿写作Agent

    负责根据大纲和上下文撰写小说初稿。
    专注于故事叙述、场景描写、对话等核心写作工作。

    使用示例:
        agent = DraftAgent()
        draft = agent.write(
            context=writing_context,
            chapter_outline=chapter_outline
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化初稿写作Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="小说写作专家",
            goal="创作引人入胜的小说内容",
            backstory="""你是一位才华横溢的小说作家，擅长各种类型的故事创作。
            你的文笔流畅，描写细腻，对话自然。
            你深知如何通过文字传递情感，创造鲜活的角色和动人的场景。
            你对网文节奏和读者爽点有敏锐的把握。""",
            verbose=verbose,
            llm=llm,
        )

    def write(
        self,
        context: "WritingContext",
        chapter_outline: dict,
        bible_section: "BibleSection | None" = None,
    ) -> str:
        """撰写章节初稿

        Args:
            context: 写作上下文
            chapter_outline: 章节大纲
            bible_section: 可选的 BibleSection，用于约束本章写作与 Production Bible 一致

        Returns:
            str: 章节初稿内容
        """
        prompt = self._build_writing_prompt(context, chapter_outline, bible_section)
        result = self.agent.kickoff(messages=prompt)
        return self._extract_content(result)

    def write_chapter(
        self,
        chapter_num: int,
        title: str,
        hook: str,
        main_events: list,
        climax: str,
        ending_hook: str,
        context: "WritingContext",
    ) -> str:
        """直接撰写章节（给定详细参数）

        Args:
            chapter_num: 章节编号
            title: 章节标题
            hook: 开篇钩子
            main_events: 主要事件列表
            climax: 高潮点
            ending_hook: 结尾悬念
            context: 写作上下文

        Returns:
            str: 章节初稿
        """
        prompt = self._build_chapter_prompt(
            chapter_num, title, hook, main_events, climax, ending_hook, context
        )
        result = self.agent.kickoff(messages=prompt)
        return self._extract_content(result)

    def _build_writing_prompt(
        self,
        context: "WritingContext",
        chapter_outline: dict,
        bible_section: "BibleSection | None" = None,
    ) -> str:
        """构建写作提示词"""
        context_str = self._format_context(context, bible_section)

        bible_constraint = self._format_bible_constraint(bible_section) if bible_section else ""

        return f"""请根据以下大纲和上下文撰写第{context.current_chapter_num}章的初稿。

写作上下文:
{context_str}
{bible_constraint}

章节大纲:
{self._format_outline(chapter_outline)}

写作要求:
1. 字数目标: 约{context.target_word_count}字
2. 开篇要有吸引力的钩子
3. 中间事件要层层递进，张力逐渐升级
4. 高潮点要有爆发力
5. 结尾留有悬念，吸引读者继续阅读
6. 注意与前文的连贯性
7. 内心独白要适度，不要过多
8. 保持叙事视角一致

请直接输出章节内容，不需要额外说明。"""

    def _build_chapter_prompt(
        self,
        chapter_num: int,
        title: str,
        hook: str,
        main_events: list,
        climax: str,
        ending_hook: str,
        context: "WritingContext",
    ) -> str:
        """构建详细章节写作提示词"""
        context_str = self._format_context(context)
        events_str = "\n".join(f"{i+1}. {e}" for i, e in enumerate(main_events))

        return f"""请撰写第{chapter_num}章，标题为「{title}」。

写作上下文:
{context_str}

章节结构:
- 开篇钩子: {hook}
- 主要事件:
{events_str}
- 高潮点: {climax}
- 结尾悬念: {ending_hook}

【网络小说写作黄金法则】
1. 字数控制: 标准网文每章2000-2500字，本章目标{context.target_word_count}字，不要超过{context.target_word_count + 500}字
2. 【开头切入】禁止以"早晨/阳光/天亮/醒来"等开篇，从动作/对话/危机/悬念直接切入
3. 【情节连贯 - 最高优先级】本章必须以"前章结尾场景"中描述的具体场景为起点继续写作！
   - 地点：必须与前章结尾相同
   - 人物状态：必须延续前章结尾时的状态
   - 情绪：必须自然延续前章结尾时的情绪
   - 禁止：另起炉灶、时间跳跃、人物状态重置
4. 【场景控制】每章不超过3个场景，场景切换用过渡句连接
5. 【节奏公式】对话3成 + 情节叙述3成 + 描写3成
6. 【打斗描写】七分铺垫，三分打斗
7. 【高潮设计】每章至少一个小爽点或打脸时刻
8. 【悬念结尾】章节末尾停在疑问/高潮/转折处，留钩子吸引追读
9. 【禁止堆砌】开篇300字内必须出现主角，3章内出第一个矛盾冲突
10. 适度描写内心，但不要过多；保持叙事视角一致

请直接输出章节内容。"""

    def _format_context(self, context: "WritingContext", bible_section: "BibleSection | None" = None) -> str:
        """格式化写作上下文"""
        lines = []
        lines.append(f"小说标题: {context.title}")
        lines.append(f"类型: {context.genre}")
        lines.append(f"风格: {context.style}")

        lines.append(f"\n世界观:\n{context.world_description}")

        if context.character_profiles:
            lines.append("\n角色设定:")
            for name, profile in context.character_profiles.items():
                lines.append(f"  - {name}: {profile}")

        # 【关键】前章结尾场景 - 必须从此场景继续，不得另起炉灶
        if context.previous_chapter_ending:
            lines.append(f"\n{'='*60}")
            lines.append(f"【前章结尾场景】（本章必须以此场景为起点继续写作）:")
            lines.append(f"{context.previous_chapter_ending}")
            lines.append(f"{'='*60}")

        if context.previous_chapters_summary:
            lines.append(f"\n前章概要:\n{context.previous_chapters_summary}")

        if context.tension_arc:
            lines.append(f"\n张力曲线:\n{context.tension_arc}")

        # Add bible characters to context if available
        if bible_section and hasattr(bible_section, 'relevant_characters') and bible_section.relevant_characters:
            lines.append("\n【本书角色设定】（必须遵守）:")
            for char_name, char in bible_section.relevant_characters.items():
                role = getattr(char, 'role', '未知')
                personality = getattr(char, 'personality', '')[:60]
                core_desire = getattr(char, 'core_desire', '')
                backstory = getattr(char, 'backstory', '')[:80]
                lines.append(f"  - {char_name}（{role}）: {personality}")
                if core_desire:
                    lines.append(f"    核心欲望: {core_desire}")
                if backstory:
                    lines.append(f"    背景: {backstory}...")

        return "\n".join(lines)

    def _format_bible_constraint(self, bible_section: "BibleSection | None") -> str:
        """格式化 Bible 约束信息到 prompt 中"""
        if not bible_section:
            return ""

        lines = ["\n【世界观规则】（必须遵守）:"]
        if hasattr(bible_section, 'world_rules_summary') and bible_section.world_rules_summary:
            lines.append(f"  {bible_section.world_rules_summary}")

        if hasattr(bible_section, 'canonical_facts_this_volume') and bible_section.canonical_facts_this_volume:
            lines.append("\n【本卷必须遵守的事实】:")
            for fact in bible_section.canonical_facts_this_volume:
                lines.append(f"  • {fact}")

        if hasattr(bible_section, 'open_foreshadowing') and bible_section.open_foreshadowing:
            lines.append("\n【伏笔约束】（必须正确铺设和回收）:")
            for fs in bible_section.open_foreshadowing:
                setup_desc = getattr(fs, 'setup_description', '')
                payoff_desc = getattr(fs, 'payoff_description', '')
                setup_ch = getattr(fs, 'setup_chapter', '?')
                payoff_ch = getattr(fs, 'payoff_chapter', '?')
                if setup_desc and payoff_desc:
                    lines.append(f"  • 伏笔：{setup_desc}")
                    lines.append(f"    → 需在第{payoff_ch}章回收：{payoff_desc}")

        return "\n".join(lines)

    def _format_outline(self, outline: dict) -> str:
        """格式化章节大纲"""
        lines = []
        lines.append(f"章节: 第{outline.get('chapter_num', '?')}章")
        lines.append(f"标题: {outline.get('title', '待定')}")

        if outline.get("hook"):
            lines.append(f"开篇钩子: {outline['hook']}")

        if outline.get("main_events"):
            lines.append("主要事件:")
            for e in outline["main_events"]:
                lines.append(f"  - {e}")

        if outline.get("climax"):
            lines.append(f"高潮点: {outline['climax']}")

        if outline.get("ending_hook"):
            lines.append(f"结尾悬念: {outline['ending_hook']}")

        if outline.get("character_developments"):
            lines.append("角色发展:")
            for cd in outline["character_developments"]:
                lines.append(f"  - {cd}")

        return "\n".join(lines)

    def _extract_content(self, result) -> str:
        """从LLM输出中提取内容"""
        if hasattr(result, "raw"):
            return result.raw.strip()
        return str(result).strip()
