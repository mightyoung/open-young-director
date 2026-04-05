"""情节规划Agent - 使用Strand Weave结构"""

from typing import TYPE_CHECKING, Any, List

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM


class PlotAgent:
    """情节规划Agent - 使用Strand Weave结构

    Strand Weave结构将故事分解为多条交织的情节线：
    - 主线 (Main Strand): 核心冲突和主角成长
    - 副线 (Sub Strands): 支线剧情、角色发展
    - 伏笔 (Foreshadowing Strands): 为后续剧情埋下线索
    - 情感线 (Emotional Strands): 情感纠葛和发展

    每条线有自己的张力曲线，通过交织点(Weave Points)连接。

    使用示例:
        agent = PlotAgent()
        plot = agent.plan(
            theme="逆袭",
            style="xianxia",
            world_data=world_dict,
            num_chapters=30
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化情节规划Agent

        Args:
            llm: 可选的语言模型，默认使用系统配置
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="情节规划专家",
            goal="设计完整的故事结构和张力曲线",
            backstory="""你是一个出色的故事架构师，精通各种叙事结构。
            你擅长使用多线索交织的叙事手法，让故事更加丰富和有深度。
            你对爽点节奏、情感冲突、高潮设计都有独到的见解。""",
            verbose=verbose,
            llm=llm,
        )

    def plan(
        self,
        theme: str,
        style: str,
        world_data: dict,
        num_volumes: int = 3,
        chapters_per_volume: int = 10,
        target_words: int = 300000,
        reference_context: str = "",
    ) -> dict:
        """规划整体情节结构（卷-章结构）

        Args:
            theme: 故事主题
            style: 小说风格
            world_data: 世界观数据
            num_volumes: 卷数量（默认3卷）
            chapters_per_volume: 每卷章节数（默认10章）
            target_words: 目标总字数
            reference_context: 参考骨架上下文（可选）

        Returns:
            dict: 包含卷-章结构的Strand Weave情节规划
        """
        prompt = self._build_planning_prompt(
            theme, style, world_data, num_volumes, chapters_per_volume, target_words, reference_context
        )
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def plan_chapter(
        self,
        chapter_num: int,
        world_data: dict,
        plot_data: dict,
        previous_summary: str,
        target_words: int,
    ) -> dict:
        """规划单个章节的详细情节

        Args:
            chapter_num: 章节编号
            world_data: 世界观数据
            plot_data: 整体情节规划
            previous_summary: 前章概要
            target_words: 目标字数

        Returns:
            dict: 章节情节详情
        """
        prompt = self._build_chapter_prompt(
            chapter_num, world_data, plot_data, previous_summary, target_words
        )
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _build_planning_prompt(
        self,
        theme: str,
        style: str,
        world_data: dict,
        num_volumes: int = 3,
        chapters_per_volume: int = 10,
        target_words: int = 300000,
        reference_context: str = "",
    ) -> str:
        """构建整体情节规划提示词（卷-章结构）"""
        world_str = self._format_world(world_data)
        total_chapters = num_volumes * chapters_per_volume

        reference_section = ""
        if reference_context:
            reference_section = f"\n\n## 参考经典名著骨架\n\n{reference_context}\n\n请在设计情节结构时参考上述经典名著的：\n- 主干情节走向\n- 结构模式（如取经模式、英雄之旅等）\n- 角色成长弧线\n- 高潮设计手法\n\n"

        return f"""为以下主题和世界观设计完整的故事结构，采用卷-章层次结构。{reference_section}

主题: {theme}
风格: {style}
目标字数: {target_words}
卷数: {num_volumes}卷
每卷章节数: {chapters_per_volume}章
总章节数: {total_chapters}章

世界观:
{world_str}

请设计{num_volumes}卷的故事结构，整体采用Strand Weave结构，并融入以下【神作设计准则】：

## 1. 凡人流：资源与逻辑闭环
- 修行资源（灵石、功法、地盘）是稀缺的。
- 角色的每一次跃升必须有明确的代价或博弈过程，禁止无缘无故的奇遇。

## 2. 庆余年流：价值观对撞
- 主角（或核心势力）必须代表一种与世界主流格格不入的【现代性价值观】（如：众生平等、科技强国、逻辑至上）。
- 这种价值观冲突应成为权谋和剧情推进的底层动力。

## 3. 雪中/剑来流：群像与气象
- 每个重要配角（Strand ID: sub_*）必须有独立的、不依赖于主角的生存逻辑和“名场面”规划。
- 设计至少3个足以流传的【名场面 (Stellar Scenes)】，重点在于意境渲染而非数值打斗。

## 4. 整体结构要求
- 主线 (Main Strand): 核心冲突和主角成长线。
- 副线 (Sub Strands): 支线剧情，负责补完世界观。
- 伏笔 (Foreshadowing Strands): 必须设计跨度超过30章的深层伏笔。

请直接返回JSON格式，不要包含任何markdown标记。只返回纯JSON对象：
{{
    "series_overview": "全书核心主题、价值观冲突及最终走向",
    "total_chapters": {total_chapters},
    "volumes": [
        {{
            "volume_num": 1,
            "title": "本卷标题",
            "description": "本卷核心冲突与转折点",
            "stellar_scenes": ["名场面1描述", "名场面2描述"],
            "resource_logic": "本卷角色争夺的核心资源及其稀缺性说明",
            "chapters": [...]
        }}
    ],
    "main_strand": {{
        "name": "主线名称",
        "ideological_conflict": "主角代表的价值观 vs 世界规则的冲突点",
        "tension_arc": [3, 5, 7, 9, 10, 8]
    }},
    "sub_strands": [
        {{
            "strand_id": "sub_1",
            "name": "配角线名称",
            "soul_moment": "该配角的高光/悲剧时刻描述"
        }}
    ],
    "foreshadowing_strands": [...],
    "high_points": [...]
}}"""

    def plan_chapter(
        self,
        chapter_num: int,
        world_data: dict,
        plot_data: dict,
        previous_summary: str,
        target_words: int,
        bible: Any = None,
    ) -> dict:
        """规划单个章节的详细情节"""
        prompt = self._build_chapter_prompt(
            chapter_num, world_data, plot_data, previous_summary, target_words, bible
        )
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result)

    def _build_chapter_prompt(
        self,
        chapter_num: int,
        world_data: dict,
        plot_data: dict,
        previous_summary: str,
        target_words: int,
        bible: Any = None,
    ) -> str:
        """构建章节情节提示词"""
        world_str = self._format_world(world_data)
        plot_str = self._format_plot(plot_data)

        # 获取未使用的 Seed Details 供回调使用
        seed_callback_section = ""
        if bible and hasattr(bible, 'seeds_registry') and bible.seeds_registry:
            # 过滤未使用的细节
            unused_seeds = [s for s in bible.seeds_registry if not s.is_used]
            if unused_seeds:
                import random
                # 随机抽取 1-2 个细节进行回调，制造‘神来之笔’
                sample_seeds = random.sample(unused_seeds, min(2, len(unused_seeds)))
                seed_callback_section = "\n【神来之笔：必须回收的即兴细节】：\n"
                for s in sample_seeds:
                    seed_callback_section += f"- 来自第{s.origin_chapter}章的细节：{s.description}\n"
                    # 标记为已使用（暂定逻辑，实际应在 plan 成功后由外部标记）
                    s.is_used = True
                seed_callback_section += "要求：请在本章情节中‘回收’或‘解释’上述细节，使其升华为伏笔。"

        return f"""设计第{chapter_num}章的详细情节。

    目标字数: {target_words}

    世界观:
    {world_str}

    整体情节规划:
    {plot_str}

    前章概要:
    {previous_summary}
    {seed_callback_section}

    请设计本章的：
    ... (rest of the prompt)

2. 开篇钩子 (Hook)
3. 主要情节点 (3-5个)
4. 【核心奇观/独特卖点】(Signature Specs): 本章必须展现出的、区别于普通章节的独特描写细节（如：特定的科技感场景、某种特殊的法术表现、极其独特的环境互动）。
5. 高潮点
6. 结尾悬念/钩子
7. 角色发展
8. 与其他章节线的交织点

请直接返回JSON格式，不要包含任何markdown标记（如```、###等）。只返回纯JSON对象：
{{
    "chapter_num": {chapter_num},
    "title": "章节标题",
    "hook": "开篇钩子",
    "main_events": ["事件1", "事件2", "事件3"],
    "signature_specs": ["独特细节1", "独特细节2"],
    "climax": "高潮点描述",
    "ending_hook": "结尾悬念",
    "character_developments": ["角色发展1", "角色发展2"],
    "weave_connections": ["与第X章的连接点"]
}}"""

    def _format_world(self, world_data: dict) -> str:
        """格式化世界观数据"""
        lines = []
        lines.append(f"世界名称: {world_data.get('name', '未知')}")
        lines.append(f"描述: {world_data.get('description', '')}")
        lines.append(f"主要冲突: {world_data.get('main_conflict', '')}")

        if world_data.get("factions"):
            lines.append("\n势力:")
            for f in world_data["factions"]:
                lines.append(f"  - {f.get('name', '')}: {f.get('description', '')}")

        if world_data.get("key_locations"):
            lines.append("\n关键地点:")
            for l in world_data["key_locations"]:
                lines.append(f"  - {l.get('name', '')}: {l.get('description', '')}")

        if world_data.get("power_system"):
            ps = world_data["power_system"]
            lines.append(f"\n力量体系: {ps.get('name', '')}")
            lines.append(f"等级: {', '.join(ps.get('levels', []))}")

        return "\n".join(lines)

    def _format_plot(self, plot_data: dict) -> str:
        """格式化情节数据"""
        lines = []

        if plot_data.get("main_strand"):
            ms = plot_data["main_strand"]
            lines.append(f"主线: {ms.get('name', '')}")
            lines.append(f"描述: {ms.get('description', '')}")
            lines.append(f"主要事件: {', '.join(ms.get('main_events', []))}")

        if plot_data.get("high_points"):
            lines.append("\n高潮点:")
            for hp in plot_data["high_points"]:
                lines.append(f"  - 第{hp.get('chapter', '')}章: {hp.get('description', '')}")

        return "\n".join(lines)

    def _normalize_chinese_keys(self, data: dict) -> dict:
        """将中文键名映射为英文键名"""
        if not isinstance(data, dict):
            return data

        # 顶层键映射
        key_map = {
            "卷数": "volume_num",
            "卷": "volume",
            "章节": "chapter",
            "章节数": "chapter_num",
            "主线": "main_strand",
            "副线": "sub_strands",
            "伏笔": "foreshadowing_strands",
            "情感线": "emotional_strands",
            "张力曲线": "tension_arc",
            "交织点": "weave_points",
            "高潮点": "high_points",
        }

        result = {}
        for k, v in data.items():
            new_key = key_map.get(k, k)
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

    def _try_parse_json(self, json_text: str) -> dict | None:
        """尝试解析JSON，处理不完整或损坏的JSON"""
        import json
        import re

        # 尝试直接解析
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

        # 移除 markdown 格式
        cleaned = json_text.strip()

        # 处理 markdown 代码块
        if "```" in cleaned:
            lines = cleaned.split("\n")
            # 找到 JSON 代码块的开始和结束
            in_code_block = False
            code_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    if not in_code_block:
                        in_code_block = True
                        continue
                    else:
                        break
                elif in_code_block:
                    code_lines.append(line)
            if code_lines:
                cleaned = "\n".join(code_lines)

        # 移除 markdown 标题（### 开头）
        lines = cleaned.split("\n")
        non_header_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            non_header_lines.append(line)
        cleaned = "\n".join(non_header_lines).strip()

        # 尝试直接解析清理后的文本
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 尝试提取并修复JSON - use balanced brace approach
        try:
            result = self._extract_json_object(cleaned)
            if result:
                return result
        except (json.JSONDecodeError, Exception):
            pass

        # 尝试提取 volumes 数组（用于volumes）
        try:
            # 查找 volumes 数组
            volumes_match = re.search(r'"volumes"\s*:\s*\[([\s\S]*)\]', cleaned)
            if volumes_match:
                volumes_str = "[" + volumes_match.group(1) + "]"
                # 尝试找到完整的数组
                bracket_count = 1
                start = volumes_match.start(1)
                end = start
                for i, c in enumerate(volumes_str[1:], 1):
                    if c == '[':
                        bracket_count += 1
                    elif c == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end = i + 1
                            break
                volumes_str = volumes_str[:end]
                volumes = json.loads(volumes_str)
                return {"volumes": volumes}
        except (json.JSONDecodeError, Exception):
            pass

        return None

    def _parse_result(self, result) -> dict:
        """解析LLM输出"""
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

            # 尝试解析JSON
            data = self._try_parse_json(json_text)
            if data is None:
                raise ValueError("Failed to parse JSON")

            # 规范化中文键名
            data = self._normalize_chinese_keys(data)

        except (json.JSONDecodeError, Exception):
            return {
                "main_strand": {
                    "name": "主线",
                    "description": "待规划",
                    "main_events": [],
                    "tension_arc": [],
                },
                "sub_strands": [],
                "foreshadowing_strands": [],
                "emotional_strands": [],
                "weave_points": [],
                "high_points": [],
                "volumes": [],
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
