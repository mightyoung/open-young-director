# -*- encoding: utf-8 -*-
"""MiniMax Media Executor - Simple interface for media generation.

This module wraps MiniMaxMediaClient from crewai.comfy.minimax to provide
a simpler interface for knowledge_base consumers.

Supported Operations:
- Image generation (image-01)
- Video generation (T2V, I2V, S2V, Hailuo-02)
- Speech synthesis (TTS)
- Music generation

Usage:
    executor = MiniMaxMediaExecutor()

    # Generate image
    image_result = await executor.generate_image(
        prompt="Chinese fantasy landscape with floating islands",
        aspect_ratio="16:9"
    )

    # Generate video
    video_result = await executor.generate_video(
        prompt="A warrior standing on a cliff overlooking a vast canyon"
    )

    # Generate speech
    audio_result = await executor.generate_speech(
        text="韩林眼中闪过一丝惊讶，没有说话",
        voice_id="male-chenl"
    )

    # Generate music
    music_result = await executor.generate_music(
        prompt="Epic orchestral, Chinese xianxia fantasy, dramatic, 2-3 minutes"
    )
"""

import aiohttp
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Add crewai to path if needed
_CREWAI_MINIMAX_PATH = None
# Track if env has been loaded
_ENV_LOADED = False


def _find_crewai_minimax():
    """Find the crewai/comfy/minimax path."""
    global _CREWAI_MINIMAX_PATH
    if _CREWAI_MINIMAX_PATH is not None:
        return _CREWAI_MINIMAX_PATH

    possible_paths = [
        Path(__file__).parent.parent.parent / "crewai" / "src" / "crewai" / "comfy" / "minimax",
        Path(__file__).parent.parent.parent / "crewai" / "comfy" / "minimax",
    ]

    for path in possible_paths:
        if path.exists() and (path / "client.py").exists():
            _CREWAI_MINIMAX_PATH = str(path)
            return _CREWAI_MINIMAX_PATH

    # Try walking up the directory tree
    current = Path(__file__).parent.parent.parent
    for _ in range(5):
        path = current / "crewai" / "src" / "crewai" / "comfy" / "minimax"
        if path.exists() and (path / "client.py").exists():
            _CREWAI_MINIMAX_PATH = str(path)
            return _CREWAI_MINIMAX_PATH
        current = current.parent

    return None


class MiniMaxMediaExecutor:
    """Executor for MiniMax media generation APIs.

    This class provides a simplified interface for generating images, videos,
    audio, and music using MiniMax's APIs. It wraps MiniMaxMediaClient from
    crewai.comfy.minimax.

    Attributes:
        api_key: MiniMax API key
        api_host: API host URL
        output_dir: Directory to save generated media files
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize the executor.

        Args:
            api_key: MiniMax API key. Defaults to MINIMAX_API_KEY env var.
            api_host: API host. Defaults to MINIMAX_API_HOST env var.
            output_dir: Directory to save generated files. Defaults to ./output/media.
        """
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_host = api_host or os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com")
        self.output_dir = Path(output_dir or "./output/media")
        self._client = None

        # Load .env file once at initialization (not per-call)
        global _ENV_LOADED
        if not _ENV_LOADED:
            env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
            load_dotenv(env_path)
            _ENV_LOADED = True

    def _get_client(self):
        """Get or create the MiniMaxMediaClient instance."""
        if self._client is not None:
            return self._client

        minimax_path = _find_crewai_minimax()
        if not minimax_path:
            raise RuntimeError("MiniMax media client not found in crewai/comfy/minimax/")

        # Use importlib to load the module directly from file path,
        # bypassing the crewai package __init__ which triggers heavy dependencies.
        import importlib.util
        client_file = Path(minimax_path) / "client.py"
        spec = importlib.util.spec_from_file_location("_minimax_client", str(client_file))
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["_minimax_client"] = module
            spec.loader.exec_module(module)
            MiniMaxMediaClient = module.MiniMaxMediaClient
        else:
            raise RuntimeError(f"Could not load MiniMaxMediaClient from {client_file}")

        self._client = MiniMaxMediaClient(
            api_key=self.api_key,
            api_host=self.api_host,
        )
        return self._client

    # ============ File Download ============

    async def download_file(self, url: str, local_path: Union[str, Path]) -> Dict[str, Any]:
        """Download a file from URL to local path.

        Args:
            url: URL to download from
            local_path: Local file path to save to

        Returns:
            dict with keys:
                - success: bool
                - local_path: str or None
                - error: str or None
        """
        try:
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return {
                            "success": False,
                            "local_path": None,
                            "error": f"HTTP {resp.status}",
                        }
                    content = await resp.read()

            # Use asyncio.to_thread to avoid blocking event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, local_path.write_bytes, content)
            return {
                "success": True,
                "local_path": str(local_path),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "local_path": None,
                "error": str(e),
            }

    # ============ Image Generation ============

    async def generate_image(
        self,
        prompt: str,
        model: str = "image-01",
        aspect_ratio: str = "1:1",
        resolution: Optional[int] = None,
        prompt_optimizer: bool = True,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generate an image from text prompt.

        Args:
            prompt: Text description of the image
            model: Image model to use (image-01, image-01-pro)
            aspect_ratio: Aspect ratio (1:1, 16:9, 9:16, etc.)
            resolution: Optional explicit resolution (deprecated, not used)
            prompt_optimizer: Whether to optimize the prompt
            output_path: Optional local path to save the image file

        Returns:
            dict with keys:
                - success: bool
                - image_url: str or None
                - local_path: str or None (if output_path was provided)
                - error: str or None
        """
        client = self._get_client()

        result = await client.generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            prompt_optimizer=prompt_optimizer,
        )

        response = {
            "success": result.success,
            "image_url": result.image_urls[0] if result.image_urls else None,
            "image_urls": result.image_urls,
            "error": result.error,
            "local_path": None,
        }

        # Download to local if output_path provided and generation succeeded
        if output_path and result.success and result.image_urls:
            image_url = result.image_urls[0]
            # Determine file extension from URL or default to .jpg
            suffix = Path(image_url.split("?")[0]).suffix or ".jpg"
            local_path = Path(output_path)
            if local_path.suffix == "":
                local_path = local_path.with_suffix(suffix)

            download_result = await self.download_file(image_url, local_path)
            response["local_path"] = download_result["local_path"]
            if not download_result["success"]:
                response["error"] = f"Download failed: {download_result['error']}"

        return response

    # ============ Video Generation ============

    async def generate_video(
        self,
        prompt: str,
        model: str = "T2V-01",
        first_frame_image: Optional[str] = None,
        subject_image: Optional[str] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
        wait_for_completion: bool = True,
        poll_interval: int = 5,
        max_polls: int = 120,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generate a video from text or image.

        Args:
            prompt: Text description of the video
            model: Video model (T2V-01, T2V-01-Director, MiniMax-Hailuo-02, I2V-01, etc.)
            first_frame_image: URL or path to first frame image for I2V
            subject_image: URL or path to subject image for S2V
            duration: Video duration in seconds
            resolution: Video resolution (768P, 1080P)
            wait_for_completion: If True, wait for video to complete (client polls internally)
            poll_interval: Ignored — client uses internal POLL_INTERVAL=5
            max_polls: Ignored — client uses internal MAX_POLL_ATTEMPTS=120
            output_path: Optional local path to save the video file

        Returns:
            dict with keys:
                - success: bool
                - video_url: str or None
                - local_path: str or None (if output_path was provided)
                - task_id: str or None
                - error: str or None
        """
        client = self._get_client()

        # Note: client.generate_video handles polling internally (POLL_INTERVAL=5, MAX_POLL=120)
        result = await client.generate_video(
            prompt=prompt,
            model=model,
            first_frame_image=first_frame_image,
            subject_image=subject_image,
            duration=duration,
            resolution=resolution,
        )

        response = {
            "success": result.success,
            "video_url": result.video_url,
            "backup_url": result.backup_url,
            "task_id": result.task_id,
            "error": result.error,
            "local_path": None,
        }

        # Download to local if output_path provided and generation succeeded
        if output_path and result.success and result.video_url:
            video_url = result.video_url
            suffix = ".mp4"  # MiniMax returns mp4
            local_path = Path(output_path)
            if local_path.suffix == "":
                local_path = local_path.with_suffix(suffix)

            download_result = await self.download_file(video_url, local_path)
            response["local_path"] = download_result["local_path"]
            if not download_result["success"]:
                response["error"] = f"Download failed: {download_result['error']}"

        return response

    async def generate_video_from_image(
        self,
        prompt: str,
        image_path: str,
        model: str = "I2V-01",
        duration: Optional[int] = None,
        wait_for_completion: bool = True,
        output_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        """Generate video from a source image (I2V).

        Args:
            prompt: Text description of the video
            image_path: Local path or URL to source image
            model: Video model (I2V-01, I2V-01-Director, etc.)
            duration: Video duration in seconds
            wait_for_completion: If True, wait for video to complete
            output_path: Optional local path to save the video file

        Returns:
            dict with keys:
                - success: bool
                - video_url: str or None
                - local_path: str or None (if output_path was provided)
                - error: str or None
        """
        # For local images, we need to upload or encode them
        image_url = image_path
        if not image_path.startswith(("http://", "https://")):
            # For local files, we'd need to upload or use base64
            # For now, just pass the path
            image_url = image_path

        return await self.generate_video(
            prompt=prompt,
            model=model,
            first_frame_image=image_url,
            duration=duration,
            wait_for_completion=wait_for_completion,
            output_path=output_path,
        )

    # ============ Speech Generation ============

    async def generate_speech(
        self,
        text: str,
        voice_id: str = "female-shaonv",
        model: str = "speech-02-hd",
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: float = 0.0,
        emotion: Optional[str] = None,
        sample_rate: int = 32000,
        output_format: str = "mp3",
    ) -> Dict[str, Any]:
        """Generate speech from text (TTS).

        Args:
            text: Text to convert to speech
            voice_id: Voice ID (female-shaonv, male-chenl, etc.)
            model: Speech model (speech-02-hd, speech-2.6-hd, etc.)
            speed: Speech speed (0.5-2.0)
            vol: Volume (0-10)
            pitch: Pitch adjustment (-12 to 12)
            emotion: Emotion (happy, sad, angry, fearful, disgusted, surprised, neutral).
                     Only supported by older models (speech-02-hd, speech-2.6-hd).
                     Do NOT use with Speech-2.6-HD or Speech-02-HD (uppercase).
            sample_rate: Audio sample rate
            output_format: Output format (mp3, wav, pcm)

        Returns:
            dict with keys:
                - success: bool
                - audio_url: str or None
                - error: str or None
        """
        client = self._get_client()

        # Only pass emotion for lowercase models that support it
        speech_kwargs = {
            "text": text,
            "voice_id": voice_id,
            "model": model,
            "speed": speed,
            "vol": vol,
            "pitch": int(pitch),
            "sample_rate": sample_rate,
            "output_format": output_format,
        }
        if emotion is not None and not model.startswith("Speech-"):
            speech_kwargs["emotion"] = emotion
        result = await client.generate_speech(**speech_kwargs)

        return {
            "success": result.success,
            "audio_url": result.audio_url,
            "error": result.error,
        }

    # ============ Lyrics Generation ============

    async def generate_lyrics(
        self,
        topic: str,
        genre: str = "xianxia",
        mood: str = "epic",
        style: str = "poetic",
        structure: str = "verse_chorus",
        language: str = "zh",
    ) -> Dict[str, Any]:
        """Generate structured lyrics using MiniMax text model.

        Uses the MiniMax text model to generate song lyrics with proper
        structure tags for MiniMax Music 2.5 paragraph-level control.

        Args:
            topic: Topic/theme for the lyrics
            genre: Music genre (xianxia, wuxia, fantasy, modern, epic)
            mood: Emotional mood (epic, romantic, sad, action)
            style: Lyrics style (poetic, narrative)
            structure: Song structure (verse_chorus, verse_only, with_bridge)
            language: Language (zh, en, mixed)

        Returns:
            dict with keys:
                - success: bool
                - lyrics: str or None
                - error: str or None
        """
        import json

        # Structure tags for MiniMax Music 2.5
        structure_prompts = {
            "verse_chorus": "[Intro]\n[Verse 1]\n...\n[Chorus]\n...\n[Verse 2]\n...\n[Chorus]\n...\n[Outro]",
            "verse_only": "[Intro]\n[Verse 1]\n...\n[Verse 2]\n...\n[Verse 3]\n...\n[Outro]",
            "with_bridge": "[Intro]\n[Verse 1]\n...\n[Pre-Chorus]\n...\n[Chorus]\n...\n[Verse 2]\n...\n[Chorus]\n...\n[Bridge]\n...\n[Final Chorus]\n...\n[Outro]",
            "abab": "[Intro]\n[A段 Verse 1]\n...\n[B段 Pre-Chorus]\n...\n[A段 Chorus]\n...\n[B段 Verse 2]\n...\n[A段 Chorus]\n...\n[Bridge]\n...\n[A段 Final]\n...\n[Outro]",
        }

        genre_context = {
            "xianxia": "仙侠玄幻风格，涉及修仙、秘境、剑侠、丹药、阵法",
            "wuxia": "武侠风格，涉及江湖、侠客、恩怨、武功秘籍",
            "fantasy": "奇幻风格，涉及魔法、异世界、英雄、巨龙",
            "modern": "现代风格，涉及都市、情感、梦想、奋斗",
            "epic": "史诗风格，涉及战争、命运、荣耀、王朝",
        }

        style_instructions = {
            "poetic": "古典诗词风格，押韵，意境优美，情景交融，每句5-7字为主",
            "narrative": "叙事风格，有故事感，情感递进清晰，每句7-10字",
        }

        structure_str = structure_prompts.get(structure, structure_prompts["verse_chorus"])
        genre_text = genre_context.get(genre, genre_context["xianxia"])
        style_text = style_instructions.get(style, style_instructions["poetic"])

        system_prompt = f"""你是一个资深词作者，擅长创作古风歌曲歌词。

请严格按照以下【五维歌词坐标系】格式生成歌词。

【输出格式 - 必须严格遵循】

【全局固定基准】
情绪光影锚定：{mood}，全局情绪基调统一
语言风格：{style_text}
【时序化结构控制 - MiniMax Music 2.5段落标签】
{structure_str}

【MiniMax Music 2.5专属参数】
流派标签：{genre_text}
情绪标签：{mood}

【关键要求】
1. 歌词应为中文，简洁优美
2. 每段4-8句，每句5-10字
3. 必须包含Hook记忆点（副歌重复）
4. 歌词结构必须包含：前奏、主歌、副歌、结尾
5. 输出只包含歌词，不要任何解释"""

        user_prompt = f"""为以下主题生成歌词：

主题：{topic}
流派：{genre}
情绪：{mood}

请生成完整的五维歌词坐标系歌词，确保歌词结构完整、情感饱满。"""

        try:
            # Use the MiniMax text API via crewAI LLM
            from crewai.lkg.base import LLMGenerator

            # Prepare messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Call via the crewai LLM if available
            if hasattr(self, 'llm') and self.llm:
                result = self.llm.generate(messages)
                return {
                    "success": True,
                    "lyrics": result.strip(),
                    "error": None,
                }

            # Fallback: direct API call
            return await self._generate_lyrics_direct(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

        except Exception as e:
            logger.warning(f"Lyrics generation failed: {e}")
            return {
                "success": False,
                "lyrics": None,
                "error": str(e),
            }

    async def _generate_lyrics_direct(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Dict[str, Any]:
        """Direct API call for lyrics generation."""
        import json

        # Note: load_dotenv is called once in __init__ to avoid repeated file I/O

        api_key = os.environ.get("MINIMAX_API_KEY")
        api_host = os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com")

        if not api_key:
            return {
                "success": False,
                "lyrics": None,
                "error": "MINIMAX_API_KEY not set",
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "MiniMax-M2.7",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 1024,
            "temperature": 0.7,
        }

        chat_url = f"{api_host}/v1/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(chat_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return {
                        "success": False,
                        "lyrics": None,
                        "error": f"API error: {response_text[:200]}",
                    }

                result_data = json.loads(response_text)
                base_resp = result_data.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return {
                        "success": False,
                        "lyrics": None,
                        "error": f"API error: {base_resp.get('status_msg')}",
                    }

                choices = result_data.get("choices", [])
                if not choices:
                    return {
                        "success": False,
                        "lyrics": None,
                        "error": "No response from model",
                    }

                lyrics = choices[0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "lyrics": lyrics.strip(),
                    "error": None,
                }

    # ============ Music Generation ============

    async def generate_music(
        self,
        prompt: str,
        lyrics: str = "",
        model: str = "music-2.5",
        wait_for_completion: bool = True,
        poll_interval: int = 10,
        max_polls: int = 60,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate music from text prompt.

        Args:
            prompt: Text description of the music
            lyrics: Song lyrics (if generating singing music)
            model: Music model (music-2.5)
            wait_for_completion: If True, wait for generation to complete
            poll_interval: Seconds between status polls
            max_polls: Maximum number of polls before timeout
            output_path: Optional path to save the audio file

        Returns:
            dict with keys:
                - success: bool
                - music_url: str or None
                - local_path: str or None
                - task_id: str or None
                - error: str or None
        """
        # Find .env file once during instance init, not per-call
        # Note: load_dotenv is called once in __init__ to avoid repeated file I/O

        api_key = os.environ.get("MINIMAX_API_KEY")
        api_host = os.environ.get("MINIMAX_API_HOST", "https://api.minimaxi.com")

        if not api_key:
            return {"success": False, "error": "MINIMAX_API_KEY not set", "music_url": None, "local_path": None, "task_id": None}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        if lyrics:
            payload["lyrics"] = lyrics

        submit_url = f"{api_host}/v1/music_generation"

        async with aiohttp.ClientSession() as session:
            async with session.post(submit_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return {"success": False, "error": f"API error: {response_text}", "music_url": None, "local_path": None, "task_id": None}

                result_data = json.loads(response_text)
                base_resp = result_data.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return {"success": False, "error": f"API error: {base_resp.get('status_msg')}", "music_url": None, "local_path": None, "task_id": None}

                # Check if audio is returned directly (hex encoded)
                data = result_data.get("data", {})
                if "audio" in data:
                    # Direct response with hex-encoded audio
                    audio_hex = data.get("audio", "")
                    audio_bytes = bytes.fromhex(audio_hex)

                    if output_path:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        # Use asyncio.to_thread to avoid blocking event loop
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, output_path.write_bytes, audio_bytes)

                    return {
                        "success": True,
                        "music_url": None,
                        "local_path": str(output_path) if output_path else None,
                        "task_id": result_data.get("task_id"),
                        "error": None,
                    }

                # Otherwise, poll for completion
                task_id = result_data.get("task_id")
                if not task_id:
                    return {"success": False, "error": "No task_id returned", "music_url": None, "local_path": None, "task_id": None}

        # Poll for completion
        query_url = f"{api_host}/v1/query/music_generation"
        for attempt in range(max_polls):
            async with aiohttp.ClientSession() as session:
                async with session.get(query_url, params={"task_id": task_id}, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        poll_data = json.loads(await resp.text())
                        status = poll_data.get("status")

                        if status == 2:  # SUCCESS
                            music_url = poll_data.get("data", {}).get("music_url")
                            return {
                                "success": True,
                                "music_url": music_url,
                                "local_path": None,
                                "task_id": task_id,
                                "error": None,
                            }
                        elif status == 3:  # FAIL
                            return {"success": False, "error": "Music generation failed", "music_url": None, "local_path": None, "task_id": task_id}

            await asyncio.sleep(poll_interval)

        return {"success": False, "error": "Music generation timed out", "music_url": None, "local_path": None, "task_id": task_id}

    # ============ Voice Clone ============

    async def clone_voice(
        self,
        audio_url: str,
        voice_name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Clone a voice from audio sample.

        Args:
            audio_url: URL to audio file (English, 30s-10min, WAV/MP3)
            voice_name: Name for the cloned voice
            description: Optional description

        Returns:
            dict with keys:
                - success: bool
                - voice_id: str or None
                - demo_audio_url: str or None
                - error: str or None
        """
        client = self._get_client()

        result = await client.clone_voice(
            audio_url=audio_url,
            voice_name=voice_name,
            description=description,
        )

        return {
            "success": result.success,
            "voice_id": result.voice_id,
            "demo_audio_url": result.demo_audio_url,
            "error": result.error,
        }

    async def list_voices(self) -> Dict[str, Any]:
        """List available voices.

        Returns:
            dict with keys:
                - success: bool
                - voices: list of voice dicts
                - error: str or None
        """
        client = self._get_client()

        result = await client.list_voices()

        return {
            "success": result.success,
            "voices": result.voices if hasattr(result, 'voices') else [],
            "error": result.error if hasattr(result, 'error') else None,
        }

    # ============ Batch Operations ============

    async def generate_scene_media(
        self,
        scene_data: Dict[str, Any],
        generate_images: bool = True,
        generate_speech: bool = True,
        generate_music: bool = False,
    ) -> Dict[str, Any]:
        """Generate all media for a scene.

        Args:
            scene_data: Scene data dict containing:
                - description: Scene description
                - narration: Scene narration text
                - characters: List of character names
                - location: Scene location
                - emotional_arc: Emotional arc dict
            generate_images: Whether to generate scene image
            generate_speech: Whether to generate narration speech
            generate_music: Whether to generate background music

        Returns:
            dict with generated media URLs and status
        """
        results = {
            "success": True,
            "image": None,
            "speech": None,
            "music": None,
            "errors": [],
        }

        # Generate image
        if generate_images:
            try:
                scene_desc = scene_data.get("description", "")
                characters = scene_data.get("characters", [])
                location = scene_data.get("location", "")

                prompt = f"Chinese fantasy novel scene"
                if characters:
                    prompt += f", featuring {', '.join(characters)}"
                if location:
                    prompt += f", in {location}"
                prompt += f", {scene_desc[:100]}"

                img_result = await self.generate_image(prompt=prompt)
                results["image"] = img_result
                if not img_result["success"]:
                    results["success"] = False
                    results["errors"].append(f"Image: {img_result.get('error')}")
            except Exception as e:
                logger.error(f"Image generation failed: {e}")
                results["success"] = False
                results["errors"].append(f"Image: {str(e)}")

        # Generate speech
        if generate_speech:
            try:
                narration = scene_data.get("narration", "")
                if narration:
                    speech_result = await self.generate_speech(
                        text=narration[:500],  # Limit text length
                        voice_id="female-shaonv",
                        emotion=self._detect_emotion(scene_data.get("emotional_arc", {})),
                    )
                    results["speech"] = speech_result
                    if not speech_result["success"]:
                        results["success"] = False
                        results["errors"].append(f"Speech: {speech_result.get('error')}")
            except Exception as e:
                logger.error(f"Speech generation failed: {e}")
                results["success"] = False
                results["errors"].append(f"Speech: {str(e)}")

        # Generate music
        if generate_music:
            try:
                emotional_arc = scene_data.get("emotional_arc", {})
                mood = self._determine_mood_from_arc(emotional_arc)

                music_prompt = f"Chinese xianxia fantasy, {mood}, cinematic soundtrack, 2-3 minutes"
                music_result = await self.generate_music(prompt=music_prompt)
                results["music"] = music_result
                if not music_result["success"]:
                    results["success"] = False
                    results["errors"].append(f"Music: {music_result.get('error')}")
            except Exception as e:
                logger.error(f"Music generation failed: {e}")
                results["success"] = False
                results["errors"].append(f"Music: {str(e)}")

        return results

    def _detect_emotion(self, emotional_arc: Dict[str, Any]) -> str:
        """Detect emotion from emotional arc."""
        if not emotional_arc:
            return "neutral"

        peak = emotional_arc.get("peak_state", "")
        if not peak:
            return "neutral"

        if any(t in peak for t in ["紧张", "危机", "战斗"]):
            return "angry"
        elif any(t in peak for t in ["悲伤", "痛苦", "失落"]):
            return "sad"
        elif any(t in peak for t in ["高潮", "兴奋", "喜悦"]):
            return "happy"
        elif any(t in peak for t in ["平静", "舒缓"]):
            return "calm"

        return "neutral"

    def _determine_mood_from_arc(self, emotional_arc: Dict[str, Any]) -> str:
        """Determine music mood from emotional arc."""
        if not emotional_arc:
            return "epic, dramatic"

        peak = emotional_arc.get("peak_state", "")
        if not peak:
            return "epic, dramatic"

        if any(t in peak for t in ["紧张", "战斗", "危机"]):
            return "tense, action, dramatic"
        elif any(t in peak for t in ["悲伤", "低沉"]):
            return "sad, melancholic"
        elif any(t in peak for t in ["高潮", "激昂"]):
            return "epic, uplifting, powerful"
        elif any(t in peak for t in ["平静", "舒缓"]):
            return "peaceful, serene"

        return "epic, cinematic"


# Singleton instance
_executor_instance: Optional[MiniMaxMediaExecutor] = None


def get_media_executor(
    api_key: Optional[str] = None,
    api_host: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> MiniMaxMediaExecutor:
    """Get the global MiniMaxMediaExecutor instance.

    Args:
        api_key: Optional API key override
        api_host: Optional API host override
        output_dir: Optional output directory override

    Returns:
        MiniMaxMediaExecutor singleton instance
    """
    global _executor_instance

    if _executor_instance is None:
        _executor_instance = MiniMaxMediaExecutor(
            api_key=api_key,
            api_host=api_host,
            output_dir=output_dir,
        )

    return _executor_instance
