"""ArtDirector - Translates textual bible facts into high-quality AI art prompts.

Synthesizes character appearances, environment anchors, and volume themes
into detailed prompts for Midjourney, Stable Diffusion, or ComfyUI.
"""

from typing import Any, List, Dict
import json
import re
from crewai.agent import Agent


class ArtDirector:
    """Agent for synthesizing visual concepts and art prompts."""

    def __init__(self, llm: Any = None, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agent = Agent(
            role="小说艺术总监",
            goal="将文字设定完美转化为顶级的视觉资产提示词，为每一个角色和关键场景设计最具冲击力的画面。",
            backstory="""你是一个拥有顶级审美的视觉设计师。你擅长捕捉文字中的色彩、光影和构图。
            你可以根据‘冷酷剑修’的性格，自动推断出他的服装细节（如：流云纹、玄色长衫）
            以及周围的环境氛围（如：肃杀的寒风、残阳如血）。
            你输出的提示词是专业级别的，能直接用于最先进的图像生成模型。""",
            llm=self.llm,
            verbose=self.verbose,
            allow_delegation=False,
        )

    def generate_character_prompt(self, character: Any) -> Dict[str, str]:
        """Synthesize a character visual prompt."""
        prompt = f"""请作为艺术总监，为以下角色设计视觉形象提示词。

【角色名字】：{character.name}
【身份/人设】：{character.role} / {character.personality}
【外貌描述】：{character.appearance}
【武器/标志物】：{getattr(character, 'linguistic_traits', [])}

任务：
1. 扩展视觉细节：发型、瞳孔、肤质、服装材质、站姿。
2. 设计构图与光影：根据性格选择合适的色调。
3. 输出中英文双语提示词。

请以 JSON 格式输出：
{{
    "subject": "{character.name}",
    "positive_prompt": "英文提示词, masterwork, high quality, ...",
    "chinese_description": "中文视觉描述",
    "negative_prompt": "low quality, bad anatomy, ..."
}}"""
        result = self.agent.kickoff(messages=prompt)
        return self._parse_json(result)

    def generate_volume_cover_prompt(self, volume_data: Dict[str, Any], world_rules: Any) -> Dict[str, str]:
        """Design an exquisite epic cover concept for a novel volume."""
        prompt = f"""请作为顶级艺术总监，为小说分卷设计【电影级】封面视觉方案。

【卷名】：{volume_data.get('title')}
【本卷核心冲突】：{volume_data.get('description')}
【核心奇观】：{volume_data.get('stellar_scenes', '暂无')}
【世界观基调】：{world_rules.power_system_name if world_rules else '默认'}

任务：
1. 【构图设计】：设计一个极具视觉冲击力的构图（如：三分法、对角线构图、微距特写或宏大远景）。
2. 【光影与色彩】：指定专业级光影参数（如：丁达尔效应、逆光、赛博朋克霓虹色调、水墨留白）。
3. 【艺术风格】：融合特定艺术家风格（如：新海诚的清透、天野喜孝的空灵、或极致写实的 3D 渲染）。
4. 【高质量咒语】：包含专业 AI 绘画后缀（如：unreal engine 5 render, volumetric lighting, 8k resolution, masterpiece）。

请以 JSON 格式输出：
{{
    "subject": "Volume Cover",
    "positive_prompt": "Epic book cover art, (masterpiece:1.2), (ultra-detailed:1.3), ...",
    "chinese_description": "封面视觉构思详细说明（含象征意义）",
    "negative_prompt": "text, watermark, messy, low quality, blurry, distorted"
}}"""
        result = self.agent.kickoff(messages=prompt)
        return self._parse_json(result)

    def _parse_json(self, result: Any) -> Dict:
        content = str(result.raw if hasattr(result, 'raw') else result).strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                return {}
        return {}
