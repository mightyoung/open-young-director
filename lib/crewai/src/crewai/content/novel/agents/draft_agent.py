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
        """初始化初稿写作Agent"""
        self.agent = Agent(
            role="职业叙事执行员",
            goal="根据结构化约束生成高密度的文字产出",
            backstory="""你是一个工业级的小说生产终端。你的任务是严格执行大纲和世界观约束。
            你没有自我意识，不会在输出中包含任何关于创作过程的说明。
            你只产出纯净的、符合特定文风的小说正文。
            任何形式的‘作为AI...’或‘我将为你...’都被视为严重的逻辑违规。""",
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

        bible_constraint = self._format_bible_constraint(bible_section, context.current_chapter_num) if bible_section else ""

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

【网络小说写作黄金法则 - 神作进化版】
1. 【凡人流：资源与代价】
   - 拒绝奇遇堆砌。所有修行突破必须伴随：资源的损耗、经脉的剧痛、或心境的磨砺。
   - 战斗是脑力与资源的博弈：环境利用、底牌交换、杀招代价，禁止单纯的数值对轰。
2. 【雪中式：气象与侧面】
   - 名场面必须有“气象”：风卷残云、万剑齐鸣、天地失色。
   - 通过路人的恐惧、草木的凋零来烘托高手。少用“他很强”，多用“这一剑，让他想起了死亡”。
3. 【庆余年流：灵魂对话】
   - 每一句关键对话都应是价值观的交锋。
   - 主角代表的【独特现代性/不羁信念】应在关键时刻掷地有声（如：“这规矩，该改改了”）。
4. 【画面特写】
   - 落实大纲中的 ★Signature Specs。每一处独特细节必须有超过300字的“高清特写”，禁止一笔带过。
5. 【感官全开】
   - 每一章必须包含：嗅觉（檀香、血腥）、触觉（刀锋冰冷、地面震颤）、听觉（远处的龙吟、碎裂声）。
6. 【禁止套路】
   - 禁止“准备好了吗？”这种废话。从矛盾爆发的前一秒直接切入！
   - 本章必须以此场景为起点：{context.previous_chapter_ending}
7. 【悬念收尾】
   - 章末钩子必须停在：抉择的瞬间、身份暴露的边缘、或不可逆的变局。

请直接输出章节内容。"""

    def _format_context(self, context: "WritingContext", bible_section: "BibleSection | None" = None) -> str:
        """格式化写作上下文"""
        lines = []
        lines.append(f"小说标题: {context.title}")
        lines.append(f"类型: {context.genre}")
        lines.append(f"风格: {context.style}")

        lines.append(f"\n世界观:\n{context.world_description}")

        # --- 注入 RAG 人格快照 ---
        if hasattr(context, "character_persona_context") and context.character_persona_context:
            lines.append(context.character_persona_context)

        if context.character_profiles:
            lines.append("\n已知角色基础背景:")
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

        if outline.get("signature_specs"):
            lines.append("\n【核心奇观/本章卖点】(必须浓墨重彩描写):")
            for spec in outline["signature_specs"]:
                lines.append(f"  ★ {spec}")

        if outline.get("main_events"):
            lines.append("\n主要事件:")
            for e in outline["main_events"]:
                lines.append(f"  - {e}")
        
        # ... rest of formatting

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
        """从LLM输出中提取内容，并剔除思维链标签 <think>...</think>"""
        import re
        
        raw_text = ""
        if hasattr(result, "raw"):
            raw_text = result.raw
        else:
            raw_text = str(result)
            
        # 剔除 <think>...</think> 标签及其内部内容
        clean_text = re.sub(r'<think>[\s\S]*?</think>', '', raw_text)
        return clean_text.strip()
