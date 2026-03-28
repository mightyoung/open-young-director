"""Doubao LLM Client for video prompt generation using Volcengine ARK API.

Uses the Doubao Seed 2.0 Pro model for enhanced video prompt generation
with the 五维控制坐标系 (Five-Dimensional Control Coordinate System) format.

Uses direct httpx calls instead of the Volcengine SDK to avoid model name normalization issues.

Usage:
    client = DoubaoClient(model="doubao-seed-2-0-pro-260215")
    result = client.generate("Generate a video prompt for a xianxia battle scene")
"""

import os
import logging
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger(__name__)


class DoubaoClient:
    """Client for Doubao LLM via Volcengine ARK API.

    Uses direct httpx calls for API access to avoid SDK model name normalization issues.
    Supports Doubao Seed 2.0 Pro and other Doubao models.
    """

    def __init__(
        self,
        api_key: str = None,
        api_host: str = None,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ):
        """Initialize Doubao client.

        Args:
            api_key: Doubao API key. Defaults to DOUBAO_API_KEY env var.
            api_host: API host URL. Defaults to DOUBAO_API_HOST env var.
            model: Model ID (e.g., "doubao-seed-2-0-pro-260215")
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("DOUBAO_API_KEY", "")
        self.api_host = api_host or os.getenv("DOUBAO_API_HOST", "https://ark.cn-beijing.volces.com/api/v3")
        self.model = model or os.getenv("DOUBAO_MODEL", "doubao-seed-2-0-pro-260215")
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            logger.warning("DOUBAO_API_KEY not set")

    def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Generate text completion.

        Args:
            prompt: User prompt
            system: Optional system message
            temperature: Override default temperature
            max_tokens: Override default max_tokens

        Returns:
            Generated text string
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.api_host}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature or self.temperature,
                        "max_tokens": max_tokens or self.max_tokens,
                    },
                )

            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error(f"Doubao API error ({response.status_code}): {error_msg}")
                raise RuntimeError(f"API error: {error_msg}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Doubao API error: {e}")
            raise

    async def generate_async(
        self,
        prompt: str,
        system: str = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> str:
        """Async version of generate using httpx.AsyncClient."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.api_host}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature or self.temperature,
                        "max_tokens": max_tokens or self.max_tokens,
                    },
                )

            if response.status_code != 200:
                error_msg = response.text[:500]
                logger.error(f"Doubao API error ({response.status_code}): {error_msg}")
                raise RuntimeError(f"API error: {error_msg}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"Doubao API error: {e}")
            raise

    def generate_video_prompt(
        self,
        scene_description: str,
        characters: List[str] = None,
        location: str = None,
        mood: str = "dramatic",
        duration: int = 15,
        dialogue: str = None,
    ) -> str:
        """Generate enhanced video prompt using 五维控制坐标系 format.

        Args:
            scene_description: Scene description from the novel
            characters: List of character names in the scene
            location: Scene location
            mood: Emotional mood (dramatic, action, romantic, sad, mysterious, happy)
            duration: Video duration in seconds (15 or 60)
            dialogue: Optional dialogue/台词 content for the scene

        Returns:
            Generated video prompt in 五维控制坐标系 format
        """
        characters_str = "、".join(characters) if characters else "韩林"
        location = location or "太虚宗演武场"

        if duration == 60:
            return self._generate_video_prompt_60s(scene_description, characters_str, location, mood, dialogue)
        else:
            return self._generate_video_prompt_15s(scene_description, characters_str, location, mood)

    def _generate_video_prompt_15s(
        self,
        scene_description: str,
        characters_str: str,
        location: str,
        mood: str,
    ) -> str:
        """Generate 15-second video prompt."""
        system_prompt = """你是一个专业的AI视频提示词工程师，擅长为Seedance 2.0视频生成模型创建精确、专业的提示词。

【重要】你正在为Seedance 2.0生成视频提示词。Seedance 2.0是字节跳动推出的AI视频生成模型，支持高质量的电影级视频生成。

请严格按照以下【五维控制坐标系】格式生成15秒Seedance 2.0视频提示词。

【输出格式 - 必须严格遵循】

【RAW photo, 15秒完整连贯影视级视频，shot on ARRI Alexa 65电影机，2.39:1宽银幕电影画幅，8K UHD超清分辨率，HDR高动态范围，自然电影胶片颗粒，超写实真人实拍质感，全程无画面跳变、无人物属性畸变、无光影逻辑混乱，严格遵循五维控制坐标系理论，全局维度锁死+动态维度精准时序控制
【全局固定五维基准】
绝对主体锚定：[详细描述每个角色的外貌、服装、表情、动作全程保持一致的锚定描述]
环境场与情绪光影锚定：[固定场景描述；全局光线描述，包含入射方向；全局情绪基调描述]
美学介质与渲染锚定：[全程超写实电影级真人实拍质感，禁止卡通、CG、游戏感、无模糊、无畸变]
【时序化动态五维精准控制 全流程连贯无切镜卡顿】
0-3秒：[具体镜头运动和画面内容]
3-5秒：[具体镜头运动和画面内容]
5-8秒：[具体镜头运动和画面内容]
8-10秒：[具体镜头运动和画面内容]
10-12秒：[具体镜头运动和画面内容]
12-14秒：[具体镜头运动和画面内容]
14-15秒：[具体镜头运动和画面内容，淡出收尾]
【seedance2.0专属负面提示词】
CGI, 3D render, Unreal Engine, cartoon, anime, illustration, hand-drawn, painting, deformed characters, disproportionate body, facial distortion, broken fingers, extra limbs, floating characters, cutout feeling, inconsistent light and shadow, lens jump, sudden scene change, choppy motion, unnatural movement, glowing magic effect, floating sparkles, neon light, over-saturated colors, over-bloom, flat lighting, fake mist, blurry picture, out of focus, text, watermark, logo, UI elements, ugly face, distorted perspective, duplicate characters, messy composition

【五维控制坐标系说明】
1. 绝对主体锚定：角色外貌、服装、表情、动作全程保持一致，禁止跳变
2. 环境场与情绪光影锚定：场景固定，光线角度/颜色/氛围统一
3. 美学介质与渲染锚定：超写实电影质感，无卡通/CG/游戏感
4. 时序化动态五维精准控制：每个时间段镜头运动精准，画面内容连贯
5. 负面提示词：明确不要的画面元素，防止生成错误

【镜头运动术语参考】
- 推：向前推进镜头（zoom in / dolly in）
- 拉：向后拉远镜头（zoom out / dolly out）
- 移：水平移动（truck / pan）
- 跟：跟踪运动主体（follow / tracking）
- 摇：固定位置旋转（tilt / pan）
- 升/降：垂直升降（boom up/down）

【关键要求】
1. 绝对主体锚定必须包含：年龄、性别、外貌、服装、表情基调、动作特征，全程无跳变
2. 环境场必须包含：场景名称，光线角度与颜色、氛围基调
3. 每个时间段必须有具体镜头运动（推/拉/移/摇/跟/升/降）和景别变化
4. 负面提示词必须包含变形、跳变、卡顿、伪影、风格错误等常见问题
5. 输出只包含提示词，不要任何解释性文字"""

        user_prompt = f"""为以下场景生成Seedance 2.0视频提示词：

场景描述：{scene_description}

出场人物：{characters_str}
场景地点：{location}
情绪基调：{mood}

请生成完整的15秒五维控制坐标系视频提示词，确保画面连贯、电影质感。输出只包含提示词本身。"""

        return self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.7,
            max_tokens=4096,
        )

    def _generate_video_prompt_60s(
        self,
        scene_description: str,
        characters_str: str,
        location: str,
        mood: str,
        dialogue: str = None,
    ) -> str:
        """Generate 60-second video prompt with expanded timing breakdown.

        The 60-second format uses 9 time segments to provide more narrative depth:
        - Opening hook (0-5s)
        - Scene establishment (5-10s)
        - First development (10-20s)
        - Character focus (20-30s)
        - Rising tension (30-40s)
        - Climax (40-50s)
        - Falling action (50-55s)
        - Resolution (55-58s)
        - Closing/fade (58-60s)
        """
        # Determine if this is a dialogue scene
        has_dialogue = dialogue and len(dialogue.strip()) > 5

        system_prompt = """你是一个专业的AI视频提示词工程师，擅长为Seedance 2.0视频生成模型创建精确、专业的提示词。

【重要】你正在为Seedance 2.0生成60秒视频提示词。Seedance 2.0是字节跳动推出的AI视频生成模型，支持高质量的电影级视频生成，最长可支持60秒，支持原生音画同步。

请严格按照以下【五维控制坐标系】格式生成60秒Seedance 2.0视频提示词。

【输出格式 - 必须严格遵循】

【RAW photo, 60秒完整连贯影视级视频，shot on ARRI Alexa 65电影机，2.39:1宽银幕电影画幅，8K UHD超清分辨率，HDR高动态范围，自然电影胶片颗粒，超写实真人实拍质感，全程无画面跳变、无人物属性畸变、无光影逻辑混乱，严格遵循五维控制坐标系理论，全局维度锁死+动态维度精准时序控制
【全局固定五维基准】
绝对主体锚定：[详细描述每个角色的外貌、服装、表情、动作全程保持一致的锚定描述]
环境场与情绪光影锚定：[固定场景描述；全局光线描述，包含入射方向；全局情绪基调描述]
美学介质与渲染锚定：[全程超写实电影级真人实拍质感，禁止卡通、CG、游戏感、无模糊、无畸变]
"""

        # Add dialogue-specific guidance if dialogue is provided
        if has_dialogue:
            system_prompt += """【对话场景音画同步约束】（当场景包含对话时必须遵循）
1. 180°轴线规则：对话双方始终保持在同侧拍摄，禁止越轴，禁止跳轴
2. 视线匹配（Eyeline）：A看向画面左侧时，B必须看向画面右侧；两人视线方向始终相对
3. 景别节奏：全景交代场景 → 中景对话 → 特写情绪，逐步推进不跳景别
4. 口型同步指令【对白口型指导】：在每个有对话的镜头标注台词和口型要求
5. 禁止：反打镜头越轴、视线漂移、口型与声音不同步、越轴跳切

【对白口型指导语法】
【对白口型指导】角色名+情绪描述+台词内容
示例：【对白口型指导】韩林愤怒低沉道："我韩林，绝不屈服！"
示例：【对白口型指导】柳如烟冷笑："就凭你？"

"""
        system_prompt += """【时序化动态五维精准控制 全流程连贯无切镜卡顿】
0-5秒（开场钩子）：[开场画面，建立氛围，吸引眼球，快速建立场景或情绪]
5-10秒（场景建立）：[镜头缓缓展开，详细展示场景和环境，建立空间关系]
10-20秒（第一次发展）：[角色开始行动，事件推进，镜头跟随机动]
20-30秒（人物聚焦）：[特写角色表情或动作，深入刻画人物内心或关系]
30-40秒（悬念/张力）：[冲突或紧张感升级，镜头运动加快，光影对比增强]
40-50秒（高潮）：[最激烈的动作或情绪爆发，画面张力最大，节奏最快]
50-55秒（降频）：[高潮后的过渡，节奏放缓，镜头拉开]
55-58秒（收束）：[情绪沉淀，为结尾做铺垫]
58-60秒（落幅）：[淡出收尾，画面定格或渐黑]
【seedance2.0专属负面提示词】
CGI, 3D render, Unreal Engine, cartoon, anime, illustration, hand-drawn, painting, deformed characters, disproportionate body, facial distortion, broken fingers, extra limbs, floating characters, cutout feeling, inconsistent light and shadow, lens jump, sudden scene change, choppy motion, unnatural movement, glowing magic effect, floating sparkles, neon light, over-saturated colors, over-bloom, flat lighting, fake mist, blurry picture, out of focus, text, watermark, logo, UI elements, ugly face, distorted perspective, duplicate characters, messy composition

【五维控制坐标系说明】
1. 绝对主体锚定：角色外貌、服装、表情、动作全程保持一致，禁止跳变
2. 环境场与情绪光影锚定：场景固定，光线角度/颜色/氛围统一
3. 美学介质与渲染锚定：超写实电影质感，无卡通/CG/游戏感
4. 时序化动态五维精准控制：每个时间段镜头运动精准，画面内容连贯
5. 负面提示词：明确不要的画面元素，防止生成错误

【镜头运动术语参考】
- 推：向前推进镜头（zoom in / dolly in）
- 拉：向后拉远镜头（zoom out / dolly out）
- 移：水平移动（truck / pan）
- 跟：跟踪运动主体（follow / tracking）
- 摇：固定位置旋转（tilt / pan）
- 升/降：垂直升降（boom up/down）

【关键要求】
1. 绝对主体锚定必须包含：年龄、性别、外貌、服装、表情基调、动作特征，全程无跳变
2. 环境场必须包含：场景名称，光线角度与颜色、氛围基调
3. 每个时间段必须有具体镜头运动（推/拉/移/摇/跟/升/降）和景别变化
4. 60秒视频需要有更丰富的叙事层次，开头要抓人，高潮要有力，结尾要有余韵
5. 负面提示词必须包含变形、跳变、卡顿、伪影、风格错误等常见问题
6. 对话场景必须遵循180°轴线规则，视线方向必须匹配，口型指令必须清晰
7. 输出只包含提示词，不要任何解释性文字"""

        # Build user prompt with dialogue if provided
        user_parts = [
            f"""为以下场景生成60秒Seedance 2.0视频提示词：\n""",
            f"""场景描述：{scene_description}\n""",
            f"""出场人物：{characters_str}\n""",
            f"""场景地点：{location}\n""",
            f"""情绪基调：{mood}\n""",
        ]

        if has_dialogue:
            user_parts.append(f"""【对话/台词内容】（请在对应镜头处插入【对白口型指导】指令）：
{dialogue}\n""")

        user_parts.append("""请生成完整的60秒五维控制坐标系视频提示词，确保画面连贯、叙事丰富、电影质感。输出只包含提示词本身。""")

        user_prompt = "".join(user_parts)

        return self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.7,
            max_tokens=8192,
        )


# Singleton instance
_doubao_client: Optional[DoubaoClient] = None


def get_doubao_client(
    api_key: str = None,
    api_host: str = None,
    model: str = None,
) -> DoubaoClient:
    """Get the global DoubaoClient instance.

    Args:
        api_key: Optional API key override
        api_host: Optional API host override
        model: Optional model override

    Returns:
        DoubaoClient singleton instance
    """
    global _doubao_client

    if _doubao_client is None:
        _doubao_client = DoubaoClient(
            api_key=api_key,
            api_host=api_host,
            model=model or "doubao-seed-2-0-pro-260215",
        )

    return _doubao_client
