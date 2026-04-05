"""PersonaAgent - Ensures characters stay in character through their dialogue and actions.

Analyzes character-specific linguistic traits and voice samples to polish
chapter content for consistency.
"""

from typing import Any, List
from crewai.agent import Agent
from crewai.content.novel.novel_types import ReviewCheckResult


class PersonaAgent:
    """Agent for enforcing character personality and dialogue consistency."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说角色灵魂塑造师",
            goal="确保每一个角色在每一章的言行都绝对符合其人设，杜绝‘AI腔’对白。",
            backstory="""你是一个顶尖的编剧和台词指导。你非常擅长抓住角色的性格核心。
            你知道一个‘冷傲孤狼’式的反派绝不会说多余的废话，
            你也知道一个‘活泼灵动’的小师妹说话应该带着怎样的节奏。
            你的任务是阅读章节内容，像打磨剧本一样打磨每一个角色的台词。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def check_and_polish(self, content: str, bible_section: Any) -> str:
        """Analyze content and rewrite dialogue that is out of character.

        Args:
            content: The chapter content to be polished.
            bible_section: The bible section containing character profiles.

        Returns:
            str: The content with polished dialogue.
        """
        if not bible_section or not bible_section.relevant_characters:
            return content

        # Build character-specific rules for the prompt
        char_rules = []
        for name, char in bible_section.relevant_characters.items():
            trait_str = ", ".join(getattr(char, 'linguistic_traits', []))
            sample_str = " / ".join(getattr(char, 'voice_samples', []))
            agenda = getattr(char, 'hidden_agenda', '暂无')
            subtext = getattr(char, 'subtext_style', '言不由衷')
            
            char_rules.append(f"【{name}】:")
            char_rules.append(f"  - 性格核心: {char.personality[:100]}")
            char_rules.append(f"  - 隐藏动机 (Hidden Agenda): {agenda}")
            char_rules.append(f"  - 说话风格: {subtext} (即使内心焦急，表面也可能很冷淡)")
            if trait_str: char_rules.append(f"  - 语言口癖: {trait_str}")
            if sample_str: char_rules.append(f"  - 标志性语录: {sample_str}")

        rules_summary = "\n".join(char_rules)

        prompt = f"""请扮演角色灵魂塑造师，对以下章节的‘对白’和‘神态’进行深度润色。

【核心人设与深层动机清单】：
{rules_summary}

【章节原始内容】：
{content[:5000]}

润色目标：
1. 【拒绝直白】神作中的角色很少有话直说。请根据‘隐藏动机’，改写那些太直白的对白，加入‘潜台词’和‘言外之意’。
2. 【声音一致性】确保对白符合角色的性格核心和语言口癖。
3. 【神态补完】通过微表情和细微动作（如：手指微颤、眼神瞬间的黯淡）来表现角色的‘潜台词’。
4. 【张力升级】让角色之间的对话像是在博弈，而不是在读说明书。

直接输出润色后的完整章节内容。"""

        result = self.agent.kickoff(messages=prompt)
        return str(result.raw if hasattr(result, 'raw') else result).strip()
