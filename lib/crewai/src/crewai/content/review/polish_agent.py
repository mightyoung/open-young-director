from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from crewai.agent.core import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class PolishAgent:
    """润色Agent - 语言优化

    这个Agent负责提升内容的语言质量，包括句式多样化、用词精准、
    节奏感和可读性。它是在修改后的草稿基础上进行最后的润色。

    使用示例:
        agent = PolishAgent()
        polished = agent.polish(draft="修改后的草稿...")
    """

    def __init__(self, llm: Optional["LLM"] = None, verbose: bool = True):
        """初始化润色Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="语言润色专家",
            goal="提升语言质量，使内容更加流畅、精炼、有感染力",
            backstory="""你是一个的语言润色专家，对文字有着敏锐的感知力。
            你的专长是将平淡的文字变得生动有力。你的润色原则是：
            1. 保持作者的原意和风格
            2. 提升语言的感染力和表现力
            3. 优化句式结构，避免单调
            4. 精炼用词，去除冗余
            5. 增强节奏感和可读性

            你深知好的润色是让内容更出彩，而不是改变内容本身。""",
            verbose=verbose,
            llm=llm,
        )

    def polish(self, draft: str, focus_areas: Optional[list[str]] = None) -> str:
        """润色草稿

        Args:
            draft: 要润色的草稿内容
            focus_areas: 可选的润色重点领域，如["句式", "用词", "节奏"]

        Returns:
            str: 润色后的内容
        """
        prompt = self._build_polish_prompt(draft, focus_areas)
        response = self.agent.kickoff(messages=prompt)
        return self._extract_polished_content(response, draft)

    def _build_polish_prompt(self, draft: str, focus_areas: Optional[list[str]] = None) -> str:
        """构建润色提示词"""
        focus_text = ""
        if focus_areas:
            focus_list = ", ".join(focus_areas)
            focus_text = f"\n\n重点关注: {focus_list}"

        return f"""请润色以下内容，提升语言质量：

{draft}

润色方向:
1. 句式多样化 - 避免重复句式，使用长短句结合
2. 用词精准 - 选择更准确、更有表现力的词汇
3. 节奏感强 - 注意段落起伏和阅读节奏
4. 可读性高 - 是内容易于理解和阅读{focus_text}

请直接输出润色后的完整内容，不要说明修改了什么。"""
        return prompt

    def _extract_polished_content(self, response: str, original: str) -> str:
        """从响应中提取润色后的内容，并剔除思维链标签 <think>...</think>"""
        import re

        # 提取文本内容（处理 LiteAgentOutput 对象）
        if hasattr(response, 'raw'):
            response_text = response.raw
        elif hasattr(response, 'content'):
            response_text = str(response.content)
        elif isinstance(response, str):
            response_text = response
        else:
            response_text = str(response)

        # 1. 剔除 <think>...</think> 标签及其内部内容
        response_text = re.sub(r'<think>[\s\S]*?</think>', '', response_text).strip()

        # 2. 尝试提取markdown代码块中的内容
        # 查找 ```开头和```结尾之间的内容
        code_block_match = re.search(r"```[\w]*\n(.*?)```", response_text, re.DOTALL)
        if code_block_match:
            return code_block_match.group(1).strip()

        # 查找"润色后:"或"优化版:"之后的内容
        polished_match = re.search(
            r"(?:润色后|优化版|润色版)[：:]\s*\n?(.*)",
            response_text,
            re.DOTALL
        )
        if polished_match:
            return polished_match.group(1).strip()

        # 如果响应比原文短很多或长很多，可能只是说明，返回原文
        if len(response_text) < len(original) * 0.3 or len(response_text) > len(original) * 2:
            return original

        # 否则返回完整响应
        return response_text.strip()
