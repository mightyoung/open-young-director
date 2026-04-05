"""世界观构建Agent"""

from typing import TYPE_CHECKING

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class WorldAgent:
    """负责构建小说世界观

    这个Agent专注于创建独特且一致的世界观设定，包括：
    - 世界/位面名称和概述
    - 主要势力及关系
    - 关键地点
    - 力量体系/社会规则
    - 主要冲突核心

    使用示例:
        agent = WorldAgent()
        world = agent.build(topic="修仙", style="xianxia")
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化世界观构建Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="世界观构建专家",
            goal="创建独特且一致的世界观设定",
            backstory="""你是一位资深奇幻/都市小说作家，擅长构建完整的世界观。
            你对各种小说风格都有深入研究，包括修仙、都市、科幻、悬疑等。
            你的世界观设定逻辑自洽，细节丰富，能为故事提供坚实的舞台。""",
            verbose=verbose,
            llm=llm,
        )

    def build(self, topic: str, style: str, reference_context: str = "", global_rules: str = "") -> dict:
        """构建世界观"""
        prompt = self._build_prompt(topic, style, reference_context, global_rules)
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _build_prompt(self, topic: str, style: str, reference_context: str = "", global_rules: str = "") -> str:
        """构建提示词"""
        reference_section = ""
        if reference_context:
            reference_section = f"\n\n## 参考经典名著骨架\n\n{reference_context}\n\n"

        constitution_section = ""
        if global_rules:
            constitution_section = f"\n\n## 项目宪法约束 (必须严格执行)\n\n{global_rules}\n\n"

        return f"""为小说主题'{topic}'构建完整世界观。
风格: {style}
{reference_section}{constitution_section}
请严格输出一个 JSON 对象，不要输出多余解释、Markdown 或代码块。JSON 结构如下：
{{
  "name": "世界名称",
  "description": "背景设定概述",
  "main_conflict": "主要冲突",
  "factions": [
    {{
      "name": "势力名称",
      "description": "势力描述",
      "relationship": "与主角或其他势力的关系"
    }}
  ],
  "key_locations": [
    {{
      "name": "地点名称",
      "description": "地点描述",
      "significance": "该地点的重要性"
    }}
  ],
  "power_system": {{
    "name": "力量体系名称",
    "description": "力量体系说明",
    "rules": ["规则1", "规则2"]
  }}
}}

要求：
1. 设定必须与主题和风格一致。
2. 世界观要自洽，避免互相冲突的规则。
3. 优先保留可用于后续章节展开的具体细节。
4. 如果参考骨架或项目宪法存在约束，必须严格遵守。"""

    def _normalize_chinese_keys(self, data: dict) -> dict:
        """将中文键名映射为英文键名，保持向后兼容"""
        if not isinstance(data, dict):
            return data

        # 顶层键映射
        key_map = {
            "世界名称": "name",
            "世界名称:": "name",
            "背景设定": "description",
            "描述": "description",
            "主要冲突": "main_conflict",
            "势力": "factions",
            "地点": "key_locations",
            "关键地点": "key_locations",
            "力量体系": "power_system",
        }

        result = {}
        for k, v in data.items():
            # 映射键名
            new_key = key_map.get(k, k)
            # 递归处理嵌套字典
            if isinstance(v, dict):
                result[new_key] = self._normalize_chinese_keys(v)
            elif isinstance(v, list):
                result[new_key] = [
                    self._normalize_chinese_keys(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                result[new_key] = v

        return result

    def _parse_result(self, result) -> dict:
        """解析LLM输出为字典"""
        import json
        import re

        try:
            raw_text = ""
            if hasattr(result, "raw"):
                raw_text = result.raw
            elif isinstance(result, str):
                raw_text = result
            else:
                raw_text = str(result)

            # Strip thinking prefix (<think>...</think>) as LLM outputs thinking before actual content
            json_text = raw_text.strip()
            json_text = re.sub(r"<think>[\s\S]*?</think>", "", json_text)

            # Remove markdown code block markers if present
            if json_text.startswith("```"):
                # Extract content from markdown code block
                lines = json_text.split("\n")
                # Skip first line (```json or ```)
                start_idx = 1 if lines[0].strip().startswith("```") else 0
                # Find closing ```
                end_idx = len(lines)
                for i in range(len(lines) - 1, -1, -1):
                    if lines[i].strip().endswith("```"):
                        end_idx = i
                        break
                json_text = "\n".join(lines[start_idx:end_idx])

            json_text = json_text.strip()

            # Extract world name from markdown title if present (e.g., "# 世界观: 极维界")
            extracted_name = None
            title_match = re.search(r"#.*世界观[：:]\s*(.+?)(?:\n|$)", json_text)
            if title_match:
                extracted_name = title_match.group(1).strip()

            # Try to find properly closed JSON object in text
            # Use a regex that matches balanced braces
            json_match = re.search(r"\{[\s\S]*\}", json_text)
            if json_match:
                # Verify the matched string has balanced braces
                candidate = json_match.group()
                if self._is_balanced_json(candidate):
                    data = json.loads(candidate)
                else:
                    # Try to find JSON by looking for opening { and searching for closing }
                    data = self._extract_json_object(json_text)
            else:
                data = json.loads(json_text)

            # Use extracted name if JSON doesn't have one
            if extracted_name and ("name" not in data or not data["name"]):
                data["name"] = extracted_name

            # 规范化中文键名
            data = self._normalize_chinese_keys(data)

            # 确保必要字段存在
            if "name" not in data or not data["name"]:
                data["name"] = "默认世界"
            if "description" not in data:
                data["description"] = "一个神秘的世界"
            if "main_conflict" not in data:
                data["main_conflict"] = "待定"
            if "factions" not in data:
                data["factions"] = []
            if "key_locations" not in data:
                data["key_locations"] = []
            if "power_system" not in data:
                data["power_system"] = None

        except (json.JSONDecodeError, Exception) as e:
            # Fallback to default structure
            return {
                "name": "默认世界",
                "description": "一个神秘的世界",
                "main_conflict": "待定",
                "factions": [],
                "key_locations": [],
                "power_system": None,
            }

        return data

    def _is_balanced_json(self, json_str: str) -> bool:
        """Check if a JSON string has balanced braces."""
        count = 0
        for c in json_str:
            if c == '{':
                count += 1
            elif c == '}':
                count -= 1
            if count < 0:
                return False
        return count == 0

    def _extract_json_object(self, text: str) -> dict:
        """Extract a properly closed JSON object from text."""
        import json
        import re

        # Find the first opening brace
        start = text.find('{')
        if start == -1:
            return {}

        # Try to extract JSON object starting from each brace position
        for i in range(start, len(text)):
            if text[i] != '{':
                continue
            # Try progressively larger substrings
            for j in range(i + 1, len(text) + 1):
                candidate = text[i:j]
                if self._is_balanced_json(candidate):
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
        return {}
