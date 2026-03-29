"""情节规划Agent - 使用Strand Weave结构"""

from typing import TYPE_CHECKING, List

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
    ) -> dict:
        """规划整体情节结构（卷-章结构）

        Args:
            theme: 故事主题
            style: 小说风格
            world_data: 世界观数据
            num_volumes: 卷数量（默认3卷）
            chapters_per_volume: 每卷章节数（默认10章）
            target_words: 目标总字数

        Returns:
            dict: 包含卷-章结构的Strand Weave情节规划
        """
        prompt = self._build_planning_prompt(
            theme, style, world_data, num_volumes, chapters_per_volume, target_words
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
    ) -> str:
        """构建整体情节规划提示词（卷-章结构）"""
        world_str = self._format_world(world_data)
        total_chapters = num_volumes * chapters_per_volume

        return f"""为以下主题和世界观设计完整的故事结构，采用卷-章层次结构。

主题: {theme}
风格: {style}
目标字数: {target_words}
卷数: {num_volumes}卷
每卷章节数: {chapters_per_volume}章
总章节数: {total_chapters}章

世界观:
{world_str}

请设计{num_volumes}卷的故事结构，每卷包含{chapters_per_volume}章。整体采用Strand Weave结构：

## 整体结构设计
1. 主线 (Main Strand): 核心冲突和主角成长线（贯穿全书）
2. 副线 (Sub Strands): 支线剧情
3. 伏笔 (Foreshadowing Strands): 埋下的线索
4. 情感线 (Emotional Strands): 情感纠葛

## 卷结构要求
每卷需要设计：
- 卷主题/副标题：概括本卷核心内容
- 卷开场钩子：吸引读者继续阅读
- 本卷主要冲突：本卷的核心矛盾
- 本卷关键事件：本卷最重要的3-5个事件
- 卷内张力曲线：[3, 5, 8, 10, 7]表示从低到高的张力变化
- 卷高潮点：是否是本卷的爆发点

## 交织点(Weave Points)
标注各条线在哪些章节交织，说明如何交织。

## 高潮设计
设计全书的{num_volumes}个主要高潮点，分布在前中后期。

请直接返回JSON格式，不要包含任何markdown标记（如```、###等）。只返回纯JSON对象：
{{
    "series_overview": "系列概览，描述全书核心主题和走向",
    "total_chapters": {total_chapters},
    "volumes": [
        {{
            "volume_num": 1,
            "title": "第一卷标题",
            "description": "本卷主题和核心内容概述",
            "hook": "本卷开场钩子",
            "main_conflict": "本卷主要冲突",
            "resolution": "本卷如何收束",
            "word_target": {target_words // num_volumes},
            "key_events": ["关键事件1", "关键事件2", "关键事件3"],
            "tension_arc": [3, 5, 7, 9, 6],
            "climax_point": true,
            "chapters": [
                {{
                    "chapter_num": 1,
                    "title": "章节标题",
                    "hook": "章节开场钩子",
                    "main_events": ["事件1", "事件2"],
                    "character_developments": ["角色发展1"],
                    "tension_level": 5
                }}
            ]
        }}
    ],
    "main_strand": {{
        "name": "主线名称",
        "description": "主线描述",
        "main_events": ["事件1", "事件2", "事件3"],
        "tension_arc": [3, 5, 7, 9, 10, 8]
    }},
    "sub_strands": [
        {{
            "strand_id": "sub_1",
            "name": "副线名称",
            "description": "副线描述",
            "main_events": ["事件1", "事件2"],
            "tension_arc": [2, 4, 6, 8]
        }}
    ],
    "foreshadowing_strands": [...],
    "emotional_strands": [...],
    "weave_points": [
        {{"chapter": 5, "description": "多条线在此交织"}}
    ],
    "high_points": [
        {{"chapter": {total_chapters // 3}, "description": "前期高潮"}},
        {{"chapter": {total_chapters * 2 // 3}, "description": "中期高潮"}},
        {{"chapter": {total_chapters}, "description": "最终高潮"}}
    ]
}}"""

    def _build_chapter_prompt(
        self,
        chapter_num: int,
        world_data: dict,
        plot_data: dict,
        previous_summary: str,
        target_words: int,
    ) -> str:
        """构建章节情节提示词"""
        world_str = self._format_world(world_data)
        plot_str = self._format_plot(plot_data)

        return f"""设计第{chapter_num}章的详细情节。

目标字数: {target_words}

世界观:
{world_str}

整体情节规划:
{plot_str}

前章概要:
{previous_summary}

请设计本章的：
1. 章节标题
2. 开篇钩子 (Hook)
3. 主要情节点 (3-5个)
4. 高潮点
5. 结尾悬念/钩子
6. 角色发展
7. 与其他章节线的交织点

请直接返回JSON格式，不要包含任何markdown标记（如```、###等）。只返回纯JSON对象：
{{
    "chapter_num": {chapter_num},
    "title": "章节标题",
    "hook": "开篇钩子",
    "main_events": ["事件1", "事件2", "事件3"],
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

        # 尝试提取并修复JSON
        try:
            # 查找 JSON 对象
            json_match = re.search(r"\{[\s\S]*\}", cleaned)
            if json_match:
                json_str = json_match.group()
                # 尝试解析
                return json.loads(json_str)
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

            # Remove markdown code block markers if present
            json_text = raw_text.strip()
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
