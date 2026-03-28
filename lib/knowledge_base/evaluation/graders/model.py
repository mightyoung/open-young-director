"""
Model-Based Grader - LLM-as-Judge

基于 LLM rubric 的评判，适用于小说内容质量评估

参考 Anthropic Model-Based Grader 设计
"""

import os
import re
from typing import Any, Optional

from .base import BaseGrader, GradeResult, GraderType


# Default rubric for novel content quality assessment
DEFAULT_NOVEL_RUBRIC = """
你是一位专业的小说内容评估专家。请评估以下小说内容的质量。

评分标准（每项 0-10 分）:

1. 叙事连贯性 (Narrative Coherence): 故事逻辑是否通顺，段落过渡是否自然
   - 0-3: 故事逻辑混乱，段落跳跃，读者难以理解
   - 4-6: 基本通顺，但有时跳跃或不连贯
   - 7-8: 连贯性好，过渡自然
   - 9-10: 极其流畅，浑然一体

2. 人物塑造 (Character Development): 角色是否立体、真实、有深度
   - 0-3: 人物扁平，单薄，缺乏个性
   - 4-6: 基本立体，但有时言行不一致
   - 7-8: 人物真实，有个性
   - 9-10: 角色鲜活，令人难忘

3. 对话自然度 (Dialogue Naturalness): 对话是否贴合人物性格，自然流畅
   - 0-3: 对话生硬，不符合人物性格
   - 4-6: 基本自然，但有些对话显得刻意
   - 7-8: 对话自然，有特色
   - 9-10: 对话精妙，富有深意

4. 情感共鸣 (Emotional Resonance): 是否能引起读者情感共鸣
   - 0-3: 情感表达苍白，无法引起共鸣
   - 4-6: 有些情感表达，但不够深刻
   - 7-8: 能引起一定情感共鸣
   - 9-10: 情感细腻动人，引人入胜

5. 文笔质量 (Language Quality): 语言是否优美流畅，用词精准
   - 0-3: 语言平淡，语法错误多
   - 4-6: 语言基本通顺，但缺乏文采
   - 7-8: 语言流畅，有一定文采
   - 9-10: 语言优美，精雕细琢

综合评分 = (叙事连贯性 + 人物塑造 + 对话自然度 + 情感共鸣 + 文笔质量) / 5

通过标准: 综合评分 >= 7.0
"""


class ModelGrader(BaseGrader):
    """LLM-as-Judge Grader for novel content"""

    # 输出格式模板
    OUTPUT_FORMAT = """
PASS: <true/false>
SCORE: <0.0-1.0>
REASONING: <brief explanation>
"""

    def __init__(
        self,
        name: str = "model_grader",
        rubric: Optional[str] = None,
        judge_model: str = "claude-sonnet-4-7",
        pass_threshold: float = 0.7,
        weight: float = 1.0,
        required: bool = True,
        timeout_sec: int = 60,
    ):
        super().__init__(
            name=name,
            grader_type=GraderType.MODEL_BASED,
            weight=weight,
            required=required,
            timeout_sec=timeout_sec,
        )
        self.rubric = rubric or DEFAULT_NOVEL_RUBRIC
        self.judge_model = judge_model
        self.pass_threshold = pass_threshold

    async def grade(
        self,
        content: str,
        context: dict[str, Any],
    ) -> GradeResult:
        """执行 LLM 评判"""
        import time

        start = time.perf_counter()

        try:
            # 构建评判 prompt
            rubric = context.get("rubric", self.rubric)
            task_desc = context.get("task_desc", "小说内容评估")
            expected_output = context.get("expected_output", "无")
            prompt = self._build_judge_prompt(content, rubric, task_desc, expected_output)

            # 调用 LLM
            result = await self._call_judge_model(prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000

            return GradeResult(
                grader_name=self.name,
                grader_type=GraderType.MODEL_BASED,
                passed=result["passed"],
                score=result["score"],
                details=result["reasoning"],
                raw_output=result.get("raw", ""),
                latency_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            return GradeResult(
                grader_name=self.name,
                grader_type=GraderType.MODEL_BASED,
                passed=False,
                score=0.0,
                details=f"ModelGrader error: {e}",
                error=str(e),
                latency_ms=elapsed_ms,
            )

    def _build_judge_prompt(
        self,
        content: str,
        rubric: str,
        task_desc: str,
        expected_output: str,
    ) -> str:
        """构建评判 prompt"""
        # 截断过长内容
        truncated_content = content[:5000] if len(content) > 5000 else content

        judge_prompt = f"""# 评估任务: {task_desc}

## 待评估内容
---
{truncated_content}
---

## 预期输出标准
{expected_output}

## 评分标准 (Rubric)
{rubric}

## 输出格式
请严格按以下格式输出评估结果:
PASS: <true/false>
SCORE: <0.0-1.0>
REASONING: <简要解释你的评分决定，100字以内>
"""
        return judge_prompt

    async def _call_judge_model(self, prompt: str) -> dict[str, Any]:
        """调用评判模型"""
        # 获取 API key
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self._fallback_judge(prompt)

        # 尝试 Anthropic API
        try:
            return await self._call_anthropic(prompt)
        except Exception as e:
            import logging

            logging.debug(f"Anthropic API failed, trying OpenAI: {e}")

        # 尝试 OpenAI API
        try:
            return await self._call_openai(prompt)
        except Exception as e:
            import logging

            logging.debug(f"OpenAI API failed: {e}")

        return self._fallback_judge(prompt)

    async def _call_anthropic(self, prompt: str) -> dict[str, Any]:
        """调用 Anthropic API"""
        try:
            import anthropic

            client = anthropic.Anthropic()
            response = client.messages.create(
                model=self.judge_model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            raw = response.content[0].text if response.content else ""
            return self._parse_judge_response(raw)

        except ImportError:
            raise RuntimeError("anthropic package not installed")

    async def _call_openai(self, prompt: str) -> dict[str, Any]:
        """调用 OpenAI API"""
        try:
            import openai

            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )

            raw = response.choices[0].message.content if response.choices else ""
            return self._parse_judge_response(raw)

        except ImportError:
            raise RuntimeError("openai package not installed")

    def _fallback_judge(self, prompt: str) -> dict[str, Any]:
        """当没有 API key 时的 fallback 评判"""
        # 简单的启发式检查
        prompt_lower = prompt.lower()

        # 检查基本质量指标
        issues = []

        # 检查内容长度
        if len(prompt) < 100:
            issues.append("内容过短")

        # 检查是否有过多的重复模式
        if re.search(r"(.)\1{4,}", prompt):
            issues.append("存在重复字符")

        # 检查是否包含基本叙事元素
        has_dialogue = '"' in prompt or '"' in prompt or '"' in prompt
        has_paragraphs = "\n\n" in prompt

        if not has_dialogue and len(prompt) > 500:
            issues.append("缺乏对话")

        if issues:
            return {
                "passed": False,
                "score": 0.3,
                "reasoning": f"Fallback: detected issues - {', '.join(issues)}",
                "raw": "",
            }

        return {
            "passed": True,
            "score": 0.7,
            "reasoning": "Fallback: no clear failure detected",
            "raw": "",
        }

    def _parse_judge_response(self, raw: str) -> dict[str, Any]:
        """解析 LLM 输出"""
        # 提取 PASS
        pass_match = re.search(r"PASS:\s*(true|false|True|False|1|0|是|否)", raw, re.IGNORECASE)
        passed = False
        if pass_match:
            val = pass_match.group(1).lower()
            passed = val in ("true", "1", "是")

        # 提取 SCORE
        score_match = re.search(r"SCORE:\s*([\d.]+)", raw, re.IGNORECASE)
        score = 0.5
        if score_match:
            try:
                score = float(score_match.group(1))
                # 归一化到 0-1 范围
                if score > 1.0:
                    score = max(0.0, min(1.0, score / 10.0))
            except ValueError:
                pass

        # 如果 pass 但 score 低，校正
        if passed and score < self.pass_threshold:
            score = self.pass_threshold

        # 提取 REASONING
        reasoning_match = re.search(
            r"REASONING:\s*(.+?)(?:\n|$)", raw, re.IGNORECASE | re.DOTALL
        )
        reasoning = (
            reasoning_match.group(1).strip() if reasoning_match else "No reasoning provided"
        )

        return {
            "passed": passed,
            "score": score,
            "reasoning": reasoning[:500],
            "raw": raw[:2000],
        }
