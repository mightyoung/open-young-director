"""StitcherAgent - Fixes continuity seams between chapters.

Specially designed for parallel writing pipelines where chapter N+1 might
not perfectly align with the actual ending of chapter N.
"""

from typing import Any
from crewai.agent import Agent


class StitcherAgent:
    """Agent for stitching chapter seams to ensure smooth transitions."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说接缝缝合专家",
            goal="消除章节之间的断层感，确保前一章的结尾与后一章的开头完美衔接。",
            backstory="""你是一个顶尖的小说校对和润色专家。在并行创作流程中，
            章节之间偶尔会出现不连贯的情况（例如：前一章主角受伤了，后一章开头却没提）。
            你的任务是识别这些‘接缝’，并用最少的文字改动实现最丝滑的过渡。
            你擅长通过增加一段环境描写或心理活动，来修补逻辑上的跳跃。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def stitch(self, prev_end: str, next_start: str, next_full_content: str) -> str:
        """Stitch two chapters together by modifying the start of the next chapter.

        Args:
            prev_end: The last ~500 words of the previous chapter.
            next_start: The first ~500 words of the next chapter.
            next_full_content: The full content of the next chapter to be updated.

        Returns:
            str: Updated full content of the next chapter.
        """
        prompt = f"""请检查以下两章之间的衔接是否顺畅。

【前一章结尾】：
...{prev_end}

【当前章节开头】：
{next_start}...

请评估是否存在逻辑、地点、人物状态或情感上的断层。
如果存在断层，请撰写一个‘过渡段落’或‘改写开头’，使其衔接自然。
要求：
1. 保持原有文风。
2. 尽可能少地改动原文。
3. 如果衔接已经很完美，请直接返回‘OK’。

如果没有返回‘OK’，请输出修改后的当前章节开头内容（约300-500字）。"""

        result = self.agent.kickoff(messages=prompt)
        stitch_content = str(result.raw if hasattr(result, 'raw') else result).strip()

        if stitch_content.upper() == "OK" or "OK" in stitch_content[:5]:
            return next_full_content

        # Replace the old start with the stitched content
        # We assume the agent provided a better opening
        updated_content = stitch_content + "\n\n" + next_full_content[len(next_start):]
        return updated_content
