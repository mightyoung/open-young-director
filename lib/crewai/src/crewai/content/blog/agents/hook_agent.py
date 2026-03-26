"""钩子生成Agent"""
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from crewai.agent import Agent


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class HookOption:
    """钩子选项"""
    variant: int
    hook_text: str
    hook_type: str  # question, statement, statistic, story, etc.
    engagement_score: float  # 预估参与度 (1-10)


class HookAgent:
    """钩子生成Agent - 创作高吸引力前30秒钩子"""

    def __init__(self, llm: "LLM" = None):
        self.agent = Agent(
            role="钩子创作专家",
            goal="生成5-10个高吸引力钩子变体，每个都能在前30秒抓住读者注意力",
            backstory="""你是一位内容营销大师，擅长创作前30秒抓住读者注意力的钩子。
            你深谙各种钩子类型：问题式、数据式、故事式、声明式、对比式、挑衅式。
            你的目标是让读者无法停止阅读。""",
            llm=llm,
            verbose=False
        )

    def generate_hooks(self, topic: str, count: int = 5) -> list[HookOption]:
        """生成钩子变体

        Args:
            topic: 主题
            count: 生成数量

        Returns:
            钩子选项列表
        """
        prompt = f"""为以下主题生成{count}个钩子变体，每个都必须能在前30秒抓住注意力。

主题: {topic}

要求:
1. 每个钩子必须能在前30秒抓住注意力
2. 变体类型多样: 问题、数据、故事、声明、对比、挑衅
3. 每个钩子标注预估参与度(1-10)

请以JSON格式输出，格式如下:
{{
    "hooks": [
        {{
            "variant": 1,
            "hook_text": "钩子文本",
            "hook_type": "question/statistic/story/statement/contrast/provocation",
            "engagement_score": 8.5
        }}
    ]
}}
"""
        result = self.agent.run(prompt)
        return self._parse_result(result)

    def _parse_result(self, result) -> list[HookOption]:
        """解析Agent输出"""
        hooks = []
        try:
            # 尝试提取JSON
            text = str(result)
            # 查找JSON块
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]

            data = json.loads(text)
            for h in data.get("hooks", []):
                hooks.append(HookOption(
                    variant=h["variant"],
                    hook_text=h["hook_text"],
                    hook_type=h["hook_type"],
                    engagement_score=float(h["engagement_score"])
                ))
        except (json.JSONDecodeError, KeyError, ValueError):
            # 解析失败，返回原始文本
            hooks.append(HookOption(
                variant=1,
                hook_text=str(result),
                hook_type="statement",
                engagement_score=5.0
            ))
        return hooks


__all__ = ["HookAgent", "HookOption"]
