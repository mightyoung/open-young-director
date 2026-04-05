"""ProseStylist - Sudowrite-inspired sensory expansion and prose micro-tuning.

Provides tools to 'Describe', 'Expand', and 'Rewrite' specific text segments 
using high-density sensory details and specific literary styles.
"""

from typing import Any, List, Dict
from crewai.agent import Agent


class ProseStylist:
    """Agent for fine-grained prose enhancement and sensory grounding."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="文笔匠人",
            goal="通过极致的感官细节描写，将平庸的文字转化为富有感染力的文学名场面。",
            backstory="""你是一个追求极致美感的文学修辞家。
            你认为‘他走进了雨里’这句话是死板的，
            而‘冰冷的雨丝如细小的刀锋，划破了深秋残留的暖意，渗进他洗得发白的领口’才是鲜活的。
            你精通五感描写，擅长通过‘通感’手法让读者身临其境。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def describe_sensory(self, snippet: str, sense: str = "all") -> str:
        """Expand a snippet with intense sensory details."""
        prompt = f"""请作为文笔匠人，对以下文本片段进行【{sense}】维度的感官增强。

【原始片段】：{snippet}

任务：
1. 保持原意和叙事视角。
2. 注入极致的细节：{'视觉（光影、色彩）、听觉（远近、质感）、嗅觉、触觉' if sense == 'all' else sense}。
3. 遵循 Show, Don't Tell 原则。

直接输出增强后的文本（控制在 300 字以内）。"""
        
        result = self.agent.kickoff(messages=prompt)
        return str(result.raw if hasattr(result, 'raw') else result).strip()

    def rewrite_style(self, snippet: str, style_description: str) -> str:
        """Rewrite a snippet in a specific literary style."""
        prompt = f"""请将以下文本重写为【{style_description}】风格。

【原始片段】：{snippet}

要求：
1. 严禁改动核心剧情。
2. 彻底转换词汇习惯、句子节奏和语调。

直接输出重写后的结果。"""
        
        result = self.agent.kickoff(messages=prompt)
        return str(result.raw if hasattr(result, 'raw') else result).strip()
