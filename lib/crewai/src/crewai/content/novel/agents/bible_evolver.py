"""BibleEvolver - Extract incremental updates for the Production Bible from chapter content.

This agent runs AFTER a chapter is polished (PostPass) and BEFORE the next chapter starts.
It extracts new character states, items, locations, and events to keep the Bible 'living'.
"""

from typing import Any
from crewai.agent import Agent
from crewai.content.novel.production_bible.bible_types import ProductionBible


class BibleEvolver:
    """Agent for extracting incremental updates for the Production Bible."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说设定编年史专家",
            goal="从小说章节中提取最新的设定变更、角色状态和关键事件，确保设定集永远是最新的。",
            backstory="""你是一个拥有超级记忆力的编辑。你的任务是阅读每一个新章节，
            识别出其中产生的任何‘永久性’变化。例如：
            - 角色获得了新武器或新技能。
            - 角色的修为境界提升了。
            - 出现了之前设定集中没有的新地名或新角色。
            - 角色之间的关系发生了实质性转变（如：从敌人变成了盟友）。
            - 某个角色受了重伤或死亡。
            """,
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def extract_updates(self, chapter_content: str, chapter_num: int, current_bible: ProductionBible) -> dict:
        """Extract incremental updates from chapter content.

        Returns:
            dict: {
                "new_characters": [...],
                "character_updates": {...},
                "new_locations": {...},
                "new_seeds": [{"description": str, "category": str, "chapter": int}],
                "world_rule_additions": [...],
            }
        """
        # 构建当前Bible的简要上下文
        bible_context = self._build_bible_context(current_bible)

        prompt = f"""作为设定编年史专家，请阅读第 {chapter_num} 章的内容，提取设定变更。

【当前设定摘要】：
{bible_context}

【第 {chapter_num} 章内容】：
{chapter_content[:2500]}

请以 JSON 格式输出以下更新：
1. new_characters: 新角色的基本资料。
2. character_updates: 角色状态变更。
3. new_locations: 新地名描述。
4. 【新增：new_seeds】: 
   - 提取文中提到的、作者‘随口一提’但尚未解释的细节。
   - 例如：一个奇怪的道具、墙上的一道裂纹、某个路人的异样眼神、一种未闻过的花香。
   - 格式：[{{"description": "细节描述", "category": "item/environment/npc_behavior", "chapter": {chapter_num}}}]
5. world_rule_additions: 新的世界观规则。

注意：细节收割（Seeds）是神作的关键，请敏锐地捕捉那些可能成为后期伏笔的‘闲笔’。
输出必须是合法的 JSON。"""

        result = self.agent.kickoff(messages=prompt)
        # 简单清理结果
        import json
        import re
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        # 尝试提取 JSON 部分
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return {}
        return {}

    def _build_bible_context(self, bible: ProductionBible) -> str:
        """Build a minimal context of the current bible for the LLM."""
        chars = ", ".join(list(bible.characters.keys())[:10])
        rules = "\n".join(bible.world_rules.world_constraints[:5]) if bible.world_rules else "无"
        return f"已知角色: {chars}\n已知规则: {rules}"
