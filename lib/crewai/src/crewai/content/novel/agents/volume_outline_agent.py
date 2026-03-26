"""分卷大纲Agent (Volume Outline Agent)

将整体 plot_data 拆分为独立的卷大纲，每卷有完整的：
- 卷主题弧线
- 本卷核心冲突和解决
- 章节目程安排（但不包含章节正文）
- 卷内张力曲线
- 卷间伏笔连接

使用示例:
    agent = VolumeOutlineAgent()
    volume_outlines = agent.generate(plot_data, world_data)
"""

from typing import TYPE_CHECKING

from crewai.agent import Agent

if TYPE_CHECKING:
    from crewai.llm import LLM
    from crewai.content.novel.production_bible.bible_types import BibleSection


class VolumeOutlineAgent:
    """分卷大纲Agent

    将整体情节规划拆分为独立的卷大纲。

    每卷大纲包含：
    - 卷主题弧线（起承转合）
    - 本卷核心冲突和解决
    - 主要事件序列
    - 角色弧线设计
    - 张力曲线
    - 与其他卷的伏笔连接

    使用示例:
        agent = VolumeOutlineAgent()
        outlines = agent.generate(plot_data, world_data)
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化分卷大纲Agent

        Args:
            llm: 可选的语言模型
            verbose: 是否输出详细日志
        """
        self.agent = Agent(
            role="分卷大纲规划专家",
            goal="设计完整且独立的卷大纲",
            backstory="""你是一个资深的小说架构师，精通长篇叙事结构。
            你擅长将复杂的整体故事拆分为若干卷，每卷有独立的起承转合，
            同时卷与卷之间通过伏笔和人物弧线紧密相连。
            你的卷大纲设计既考虑单卷的完整性，也考虑全书的整体性。""",
            verbose=verbose,
            llm=llm,
        )

    def generate(
        self,
        plot_data: dict,
        world_data: dict,
        num_volumes: int | None = None,
    ) -> list[dict]:
        """生成分卷大纲

        Args:
            plot_data: 整体情节规划（包含 volumes 数组）
            world_data: 世界观数据
            num_volumes: 可选，覆盖 plot_data 中的卷数

        Returns:
            list[dict]: 分卷大纲列表，每卷包含完整的章节安排
        """
        prompt = self._build_prompt(plot_data, world_data, num_volumes)
        result = self.agent.kickoff(messages=prompt)
        return self._parse_result(result, plot_data, num_volumes)

    def generate_for_volume(
        self,
        volume_outline: dict,
        plot_data: dict,
        world_data: dict,
        volume_num: int,
    ) -> dict:
        """为单个卷生成大纲（支持并行调用）

        Args:
            volume_outline: 单卷的大纲模板（包含 volume_num, title 等）
            plot_data: 整体情节规划
            world_data: 世界观数据
            volume_num: 卷编号

        Returns:
            dict: 该卷的详细大纲
        """
        prompt = self._build_prompt_for_volume(volume_outline, plot_data, world_data, volume_num)
        result = self.agent.kickoff(messages=prompt)
        parsed = self._parse_result_for_volume(result, volume_outline, volume_num)
        return parsed if parsed else volume_outline

    def generate_for_volume_with_bible(
        self,
        volume_outline: dict,
        plot_data: dict,
        world_data: dict,
        volume_num: int,
        bible_section: "BibleSection",
    ) -> dict:
        """为单个卷生成大纲（使用BibleSection约束，支持并行调用）

        Args:
            volume_outline: 单卷的大纲模板（包含 volume_num, title 等）
            plot_data: 整体情节规划
            world_data: 世界观数据
            volume_num: 卷编号
            bible_section: 该卷的 BibleSection，包含 canonical facts

        Returns:
            dict: 该卷的详细大纲
        """
        prompt = self._build_prompt_for_volume_with_bible(
            volume_outline, plot_data, world_data, volume_num, bible_section
        )
        result = self.agent.kickoff(messages=prompt)
        parsed = self._parse_result_for_volume(result, volume_outline, volume_num)
        return parsed if parsed else volume_outline

    def _build_prompt_for_volume_with_bible(
        self,
        volume_outline: dict,
        plot_data: dict,
        world_data: dict,
        volume_num: int,
        bible_section: "BibleSection",
    ) -> str:
        """构建带BibleSection的单卷大纲提示词"""
        import json

        world_str = self._format_world(world_data)
        volume_str = json.dumps(volume_outline, ensure_ascii=False, default=str)

        # 获取其他卷的信息（用于卷间伏笔）
        all_volumes = plot_data.get("volumes", [])
        other_volumes = [v for v in all_volumes if v.get("volume_num") != volume_num]
        other_str = json.dumps(other_volumes, ensure_ascii=False, default=str) if other_volumes else "无"

        # Format bible section
        bible_str = ""
        if bible_section:
            bible_chars = getattr(bible_section, 'relevant_characters', {})
            if bible_chars:
                chars_list = [f"  - {cp.name}: {cp.role}" for cp in bible_chars.values()]
                bible_str += f"\n## 本卷角色 (from Production Bible)\n" + "\n".join(chars_list)

            bible_rules = getattr(bible_section, 'world_rules_summary', '')
            if bible_rules:
                bible_str += f"\n## 世界规则约束\n{bible_rules}"

            open_fs = getattr(bible_section, 'open_foreshadowing', [])
            if open_fs:
                bible_str += f"\n## 本卷伏笔 (必须包含)\n"
                for fs in open_fs:
                    bible_str += f"  - [{fs.get('setup_chapter', '?')}] {fs.get('setup_description', '')}\n"

        return f"""为第{volume_num}卷生成详细的大纲。

## 本卷基本信息
{volume_str}

## 世界观
{world_str}

## 其他卷的信息（用于伏笔连接）
{other_str}

{bible_str}

## 主线信息
main_strand: {plot_data.get("main_strand", {})}
sub_strands: {plot_data.get("sub_strands", [])}
foreshadowing_strands: {plot_data.get("foreshadowing_strands", [])}

## 本卷大纲要求
请为第{volume_num}卷生成完整大纲，包含：

###
{{
    "volume_num": {volume_num},
    "title": "卷标题",
    "subtitle": "卷副标题（可选）",
    "theme_arc": "本卷主题弧线描述",
    "opening_hook": "本卷开场钩子",
    "closing_hook": "本卷结尾悬念",
    "main_conflict": "本卷核心冲突",
    "resolution": "本卷冲突如何解决",
    "word_target": 本卷目标字数,
    "tension_arc": [3, 5, 7, 9, 6],
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": {{
        "主角": "本章弧线描述"
    }},
    "foreshadowing_planned": [
        {{"chapter": 3, "setup": "伏笔内容", "payoff_chapter": 15}}
    ],
    "chapters_summary": [
        {{
            "chapter_num": 1,
            "title": "章节标题",
            "purpose": "本章在卷中的作用",
            "key_events": ["事件1", "事件2"],
            "tension_level": 5,
            "pov_note": "视角注意"
        }}
    ],
    "connection_to_next": "本章如何连接下一卷"
}}

请以JSON格式返回本卷的完整大纲。"""

    def _build_prompt_for_volume(
        self,
        volume_outline: dict,
        plot_data: dict,
        world_data: dict,
        volume_num: int,
    ) -> str:
        """构建单卷大纲提示词"""
        import json

        world_str = self._format_world(world_data)
        volume_str = json.dumps(volume_outline, ensure_ascii=False, default=str)

        # 获取其他卷的信息（用于卷间伏笔）
        all_volumes = plot_data.get("volumes", [])
        other_volumes = [v for v in all_volumes if v.get("volume_num") != volume_num]
        other_str = json.dumps(other_volumes, ensure_ascii=False, default=str) if other_volumes else "无"

        return f"""为第{volume_num}卷生成详细的大纲。

## 本卷基本信息
{volume_str}

## 世界观
{world_str}

## 其他卷的信息（用于伏笔连接）
{other_str}

## 主线信息
main_strand: {plot_data.get("main_strand", {})}
sub_strands: {plot_data.get("sub_strands", [])}
foreshadowing_strands: {plot_data.get("foreshadowing_strands", [])}

## 本卷大纲要求
请为第{volume_num}卷生成完整大纲，包含：

###
{{
    "volume_num": {volume_num},
    "title": "卷标题",
    "subtitle": "卷副标题（可选）",
    "theme_arc": "本卷主题弧线描述",
    "opening_hook": "本卷开场钩子",
    "closing_hook": "本卷结尾悬念",
    "main_conflict": "本卷核心冲突",
    "resolution": "本卷冲突如何解决",
    "word_target": 本卷目标字数,
    "tension_arc": [3, 5, 7, 9, 6],
    "key_events": ["事件1", "事件2", "事件3"],
    "character_arcs": {{
        "主角": "本章弧线描述"
    }},
    "foreshadowing_planned": [
        {{"chapter": 3, "setup": "伏笔内容", "payoff_chapter": 15}}
    ],
    "chapters_summary": [
        {{
            "chapter_num": 1,
            "title": "章节标题",
            "purpose": "本章在卷中的作用",
            "key_events": ["事件1", "事件2"],
            "tension_level": 5,
            "pov_note": "视角注意"
        }}
    ],
    "connection_to_next": "本章如何连接下一卷"
}}

请以JSON格式返回本卷的完整大纲。"""

    def _parse_result_for_volume(self, result, volume_outline: dict, volume_num: int) -> dict | None:
        """解析单卷结果"""
        import json
        import re

        raw_text = ""
        if hasattr(result, "raw"):
            raw_text = result.raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)

        try:
            json_match = re.search(r"\{[\s\S]*\}", raw_text)
            if json_match:
                volume = json.loads(json_match.group())
                if volume.get("volume_num") == volume_num:
                    return volume
                # Try to fix if numbers don't match
                volume["volume_num"] = volume_num
                return volume
        except (json.JSONDecodeError, Exception):
            pass

        return None

    def _build_prompt(
        self,
        plot_data: dict,
        world_data: dict,
        num_volumes: int | None,
    ) -> str:
        """构建分卷大纲提示词"""
        import json

        world_str = self._format_world(world_data)

        # 提取 volumes 信息
        volumes = plot_data.get("volumes", [])
        if num_volumes and num_volumes != len(volumes):
            volumes = volumes[:num_volumes]

        volumes_str = json.dumps(volumes, ensure_ascii=False, default=str)

        return f"""为以下整体故事规划设计详细的分卷大纲。

## 世界观
{world_str}

## 整体情节规划（卷-章结构）
{volumes_str}

## 主线信息
main_strand: {plot_data.get("main_strand", {})}
sub_strands: {plot_data.get("sub_strands", [])}
foreshadowing_strands: {plot_data.get("foreshadowing_strands", [])}
emotional_strands: {plot_data.get("emotional_strands", [])}

## 整体结构要求
- 每卷需要独立的起承转合
- 卷与卷之间通过伏笔和角色弧线紧密相连
- 每卷结束时留下悬念，引导读者进入下一卷
- 每卷的字数分配应均衡

请为每一卷生成详细大纲，包含：

### 每卷大纲结构
{{
    "volume_num": 1,
    "title": "卷标题",
    "subtitle": "卷副标题（可选）",
    "theme_arc": "本卷主题弧线描述",
    "opening_hook": "本卷开场钩子",
    "closing_hook": "本卷结尾悬念",
    "main_conflict": "本卷核心冲突",
    "resolution": "本卷冲突如何解决",
    "word_target": 本卷目标字数,
    "tension_arc": [3, 5, 7, 9, 6],  # 本卷张力曲线
    "key_events": ["事件1", "事件2", "事件3"],  # 本卷关键事件
    "character_arcs": {{
        "主角": "本章弧线描述"
    }},
    "foreshadowing_planned": [
        {{"chapter": 3, "setup": "伏笔内容", "payoff_chapter": 15}}
    ],
    "chapters_summary": [
        {{
            "chapter_num": 1,
            "title": "章节标题",
            "purpose": "本章在卷中的作用",
            "key_events": ["事件1", "事件2"],
            "tension_level": 5,
            "pov_note": "视角注意"
        }}
    ],
    "connection_to_next": "本章如何连接下一卷"
}}

以JSON数组格式返回所有卷的大纲：
[
    {{...}},  # 第1卷
    {{...}},  # 第2卷
    ...
]

确保每个卷的大纲都是完整的，能够独立指导后续的章节概要生成。"""

    def _format_world(self, world_data: dict) -> str:
        """格式化世界观数据"""
        import json
        s = json.dumps(world_data, ensure_ascii=False, default=str)
        if len(s) > 1000:
            return s[:1000] + "..."
        return s

    def _parse_result(self, result, plot_data: dict, num_volumes: int | None) -> list[dict]:
        """解析结果"""
        import json
        import re

        raw_text = ""
        if hasattr(result, "raw"):
            raw_text = result.raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)

        # 尝试提取JSON数组
        try:
            # Find JSON array
            json_match = re.search(r"\[[\s\S]*\]", raw_text)
            if json_match:
                volumes = json.loads(json_match.group())
                return volumes
        except (json.JSONDecodeError, Exception):
            pass

        # Fallback: 使用 plot_data 中的 volumes
        volumes = plot_data.get("volumes", [])
        if num_volumes:
            volumes = volumes[:num_volumes]
        return volumes
