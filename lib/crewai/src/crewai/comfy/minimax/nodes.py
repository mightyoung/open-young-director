# -*- encoding: utf-8 -*-
"""MiniMax ComfyUI Nodes for video, image, audio, and music generation.

This module provides ComfyUI-compatible nodes that wrap the MiniMaxMediaClient.

Usage:
    These nodes can be used in ComfyUI workflows or standalone via MiniMaxMediaClient.

    # Standalone usage
    client = MiniMaxMediaClient()
    result = await client.generate_video(prompt="...")
"""

import asyncio
import base64
import io
import logging
import os
from typing import Optional, Any

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

from typing_extensions import override

logger = logging.getLogger(__name__)

# Constants
MINIMAX_CHINA_HOST = "https://api.minimaxi.com"
MINIMAX_GLOBAL_HOST = "https://api.minimax.io"

# Polling configuration
T2V_AVERAGE_DURATION = 234
I2V_AVERAGE_DURATION = 114
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120


class MiniMaxVideoStatus:
    """MiniMax video generation status."""
    QUEUING = "Queueing"
    PREPARING = "Preparing"
    PROCESSING = "Processing"
    SUCCESS = "Success"
    FAIL = "Fail"


# Import IO system if available
try:
    from comfy_api.latest import ComfyExtension, IO
except ImportError:
    try:
        from ...comfy_api.latest import ComfyExtension, IO
    except ImportError:
        # Fallback when not in ComfyUI
        IO = None
        ComfyExtension = object


def _get_api_key_and_host(api_key: str, api_host: str) -> tuple:
    """Get API key and host from args or environment."""
    final_api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
    final_api_host = api_host or os.environ.get("MINIMAX_API_HOST", MINIMAX_CHINA_HOST)
    return final_api_key, final_api_host


def _validate_api_key(api_key: str) -> None:
    """Validate that API key is present."""
    if not api_key:
        raise ValueError(
            "MiniMax API key is required. Set MINIMAX_API_KEY in .env or pass as input."
        )


def _validate_string(s: str, field_name: str = "string") -> None:
    """Validate string is not empty."""
    if not s or not s.strip():
        raise ValueError(f"{field_name} cannot be empty")


async def _upload_image_to_base64(image: Any) -> str:
    """Convert a ComfyUI image tensor to base64 data URL."""
    if not TORCH_AVAILABLE:
        raise RuntimeError("torch is required for _upload_image_to_base64")

    import numpy as np
    from PIL import Image

    if image.ndim == 4:
        image = image[0]

    img_np = (image.cpu().numpy() * 255).astype(np.uint8)

    if img_np.shape[-1] == 4:
        img_np = img_np[:, :, :3]

    pil_image = Image.fromarray(img_np)
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=95)
    image_bytes = buffer.getvalue()

    b64_str = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64_str}"


async def _download_url_to_image(url: str, timeout: int = 60, max_retries: int = 3):
    """Download URL to image tensor."""
    from PIL import Image
    import numpy as np

    for attempt in range(max_retries):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        image = Image.open(io.BytesIO(image_bytes))
                        image = image.convert("RGB")
                        img_np = np.array(image).astype(np.float32) / 255.0
                        # Convert to (B,H,W,C) format for ComfyUI
                        if img_np.ndim == 3:
                            img_np = np.expand_dims(img_np, axis=0)
                        if TORCH_AVAILABLE:
                            return torch.from_numpy(img_np)
                        return img_np
                    else:
                        logger.warning(f"Download attempt {attempt + 1} failed: {resp.status}")
                        await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)


async def _generate_video_direct(
    api_key: str,
    api_host: str,
    *,
    prompt: str,
    model: str,
    first_frame_image: Optional[Any] = None,
    subject_image: Optional[Any] = None,
    duration: Optional[int] = None,
    resolution: Optional[str] = None,
    prompt_optimizer: bool = True,
) -> dict:
    """Generate video using MiniMax Direct API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "MM-API-Source": "ComfyUI-Direct",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "prompt_optimizer": prompt_optimizer,
    }

    if duration is not None:
        payload["duration"] = duration
    if resolution is not None:
        payload["resolution"] = resolution

    if first_frame_image is not None:
        image_b64 = await _upload_image_to_base64(first_frame_image)
        payload["first_frame_image"] = image_b64

    if subject_image is not None:
        image_b64 = await _upload_image_to_base64(subject_image)
        payload["subject_image"] = image_b64

    submit_url = f"{api_host}/v1/video_generation"

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(submit_url, json=payload, headers=headers) as resp:
            response_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"MiniMax API error ({resp.status}): {response_text}")

            import json
            submit_response = json.loads(response_text)
            base_resp = submit_response.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                raise Exception(
                    f"MiniMax API error: {base_resp.get('status_msg')} "
                    f"(code: {base_resp.get('status_code')})"
                )

            task_id = submit_response.get("task_id")
            if not task_id:
                raise Exception("No task_id returned from MiniMax API")

    logger.info(f"MiniMax video task submitted: {task_id}")

    query_url = f"{api_host}/v1/query/video_generation"

    for attempt in range(MAX_POLL_ATTEMPTS):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                query_url, params={"task_id": task_id}, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                import json
                poll_response = json.loads(response_text)
                status = poll_response.get("status")

                if status == MiniMaxVideoStatus.SUCCESS.value:
                    file_id = poll_response.get("file_id")
                    if not file_id:
                        raise Exception(f"Video succeeded but no file_id: {poll_response}")
                    break

                elif status == MiniMaxVideoStatus.FAIL.value:
                    raise Exception(
                        f"Video generation failed: {poll_response.get('base_resp', {}).get('status_msg', 'Unknown')}"
                    )

                await asyncio.sleep(POLL_INTERVAL)
    else:
        raise Exception(f"Video generation timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL} seconds")

    file_url = f"{api_host}/v1/files/retrieve"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            file_url, params={"file_id": file_id}, headers=headers
        ) as resp:
            response_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"Failed to retrieve file ({resp.status}): {response_text}")

            import json
            file_response = json.loads(response_text)
            file_data = file_response.get("file", {})
            download_url = file_data.get("download_url")
            backup_url = file_data.get("backup_download_url")

            if not download_url:
                raise Exception(f"No download URL in file response: {file_response}")

    # Return URLs for fallback when running outside ComfyUI
    return {
        "primary_url": download_url,
        "backup_url": backup_url,
        "file_id": file_id,
    }


async def _generate_image_direct(
    api_key: str,
    api_host: str,
    *,
    prompt: str,
    model: str = "image-01",
    aspect_ratio: str = "1:1",
    n: int = 1,
    prompt_optimizer: bool = True,
) -> list:
    """Generate image using MiniMax Direct API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "MM-API-Source": "ComfyUI-Direct",
    }

    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "n": min(n, 4),
        "prompt_optimizer": prompt_optimizer,
    }

    submit_url = f"{api_host}/v1/image_generation"

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(submit_url, json=payload, headers=headers) as resp:
            response_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"MiniMax API error ({resp.status}): {response_text}")

            import json
            submit_response = json.loads(response_text)
            base_resp = submit_response.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                raise Exception(
                    f"MiniMax API error: {base_resp.get('status_msg')} "
                    f"(code: {base_resp.get('status_code')})"
                )

            image_urls = submit_response.get("data", {}).get("image_urls", [])
            if not image_urls:
                raise Exception("No images generated")

    # Download first image
    image_tensor = await _download_url_to_image(image_urls[0])

    if n == 1:
        return [image_tensor]
    else:
        images = [image_tensor]
        for url in image_urls[1:n]:
            img = await _download_url_to_image(url)
            images.append(img)
        return images


async def _generate_speech_direct(
    api_key: str,
    api_host: str,
    *,
    text: str,
    model: str = "speech-02",
    voice_id: str = "female-shaonv",
    speed: float = 1.0,
    vol: float = 1.0,
    pitch: int = 0,
    emotion: Optional[str] = None,
    sample_rate: int = 32000,
    output_format: str = "mp3",
) -> str:
    """Generate speech using MiniMax Direct API."""
    from typing import Optional
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "MM-API-Source": "ComfyUI-Direct",
    }

    voice_setting = {
        "voice_id": voice_id,
        "speed": speed,
        "vol": vol,
        "pitch": pitch,
    }
    # emotion only supported by lowercase models (speech-02-hd, speech-2.6-hd)
    if emotion is not None and not model.startswith("Speech-"):
        voice_setting["emotion"] = emotion

    payload = {
        "model": model,
        "text": text,
        "voice_setting": voice_setting,
        "audio_setting": {
            "sample_rate": sample_rate,
            "bitrate": 128000,
            "format": output_format,
            "channel": 1,
        },
        "output_format": "url",
    }

    submit_url = f"{api_host}/v1/t2a_v2"

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(submit_url, json=payload, headers=headers) as resp:
            response_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"MiniMax API error ({resp.status}): {response_text}")

            import json
            submit_response = json.loads(response_text)
            base_resp = submit_response.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                raise Exception(
                    f"MiniMax API error: {base_resp.get('status_msg')} "
                    f"(code: {base_resp.get('status_code')})"
                )

            audio_url = submit_response.get("data", {}).get("audio")
            if not audio_url:
                raise Exception("No audio URL returned")

    return audio_url


async def _generate_music_direct(
    api_key: str,
    api_host: str,
    *,
    prompt: str,
    lyrics: str = "",
    model: str = "music-2.0",
) -> str:
    """Generate music using MiniMax Direct API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "MM-API-Source": "ComfyUI-Direct",
    }

    payload = {
        "model": model,
        "prompt": prompt,
    }

    if lyrics:
        payload["lyrics"] = lyrics

    submit_url = f"{api_host}/v1/music_generation"

    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.post(submit_url, json=payload, headers=headers) as resp:
            response_text = await resp.text()
            if resp.status != 200:
                raise Exception(f"MiniMax API error ({resp.status}): {response_text}")

            import json
            submit_response = json.loads(response_text)
            base_resp = submit_response.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                raise Exception(
                    f"MiniMax API error: {base_resp.get('status_msg')} "
                    f"(code: {base_resp.get('status_code')})"
                )

            task_id = submit_response.get("task_id")
            if not task_id:
                raise Exception("No task_id returned from music API")

    logger.info(f"MiniMax music task submitted: {task_id}")

    query_url = f"{api_host}/v1/query/music_generation"

    for attempt in range(MAX_POLL_ATTEMPTS):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                query_url, params={"task_id": task_id}, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    await asyncio.sleep(POLL_INTERVAL)
                    continue

                import json
                poll_response = json.loads(response_text)
                status = poll_response.get("status")

                if status == MiniMaxVideoStatus.SUCCESS.value:
                    music_url = poll_response.get("data", {}).get("music_url")
                    if not music_url:
                        raise Exception(f"Music succeeded but no URL: {poll_response}")
                    return music_url

                elif status == MiniMaxVideoStatus.FAIL.value:
                    raise Exception(
                        f"Music generation failed: {poll_response.get('base_resp', {}).get('status_msg', 'Unknown')}"
                    )

                await asyncio.sleep(POLL_INTERVAL)
    else:
        raise Exception("Music generation timed out")


# ============ ComfyUI Node Classes ============
# Note: These require IO system from ComfyUI to be fully functional


class MiniMaxDirectTextToVideoNode:
    """MiniMax Text-to-Video node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (["T2V-01", "T2V-01-Director", "MiniMax-Hailuo-02"], {"default": "T2V-01"}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "duration": ([0, 6, 10], {"default": 0}),
                "resolution": (["", "768P", "1080P"], {"default": ""}),
                "prompt_optimizer": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/video/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, prompt: str, model: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)
        _validate_string(prompt, "prompt")

        duration = kwargs.get("duration", 0)
        resolution = kwargs.get("resolution", "")
        duration_val = duration if duration > 0 else None
        resolution_val = resolution if resolution else None

        result = await _generate_video_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt,
            model=model,
            duration=duration_val,
            resolution=resolution_val,
            prompt_optimizer=kwargs.get("prompt_optimizer", True),
        )

        return (result.get("primary_url", ""),)


class MiniMaxDirectImageToVideoNode:
    """MiniMax Image-to-Video node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (["I2V-01", "I2V-01-Director", "I2V-01-live"], {"default": "I2V-01"}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "prompt_optimizer": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/video/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, image, prompt: str, model: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        result = await _generate_video_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt,
            model=model,
            first_frame_image=image,
            prompt_optimizer=kwargs.get("prompt_optimizer", True),
        )

        return (result.get("primary_url", ""),)


class MiniMaxDirectHailuoNode:
    """MiniMax Hailuo-02 Video node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "first_frame_image": ("IMAGE",),
                "prompt_optimizer": ("BOOLEAN", {"default": True}),
                "duration": ([0, 6, 10], {"default": 6}),
                "resolution": (["", "768P", "1080P"], {"default": "768P"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/video/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, prompt: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        if not prompt and kwargs.get("first_frame_image") is None:
            raise ValueError("Either prompt or first_frame_image is required")

        duration = kwargs.get("duration", 6)
        resolution = kwargs.get("resolution", "768P")

        if resolution.upper() == "1080P" and duration != 6:
            raise ValueError("1080P only supports 6 second duration")

        duration_val = duration if duration > 0 else None
        resolution_val = resolution if resolution else None

        result = await _generate_video_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt or "video",
            model="MiniMax-Hailuo-02",
            first_frame_image=kwargs.get("first_frame_image"),
            duration=duration_val,
            resolution=resolution_val,
            prompt_optimizer=kwargs.get("prompt_optimizer", True),
        )

        return (result.get("primary_url", ""),)


class MiniMaxDirectSubjectToVideoNode:
    """MiniMax Subject-to-Video node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "subject_image": ("IMAGE",),
                "prompt_text": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/video/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, subject_image, prompt_text: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)
        _validate_string(prompt_text, "prompt_text")

        result = await _generate_video_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt_text,
            model="S2V-01",
            subject_image=subject_image,
            prompt_optimizer=True,
        )

        return (result.get("primary_url", ""),)


class MiniMaxDirectImageNode:
    """MiniMax Text-to-Image node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "model": (["image-01"], {"default": "image-01"}),
                "aspect_ratio": (["1:1", "16:9", "9:16", "4:3", "3:4"], {"default": "1:1"}),
                "n": ("INT", {"default": 1, "min": 1, "max": 4}),
                "prompt_optimizer": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "api node/image/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, prompt: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)
        _validate_string(prompt, "prompt")

        images = await _generate_image_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt,
            model=kwargs.get("model", "image-01"),
            aspect_ratio=kwargs.get("aspect_ratio", "1:1"),
            n=kwargs.get("n", 1),
            prompt_optimizer=kwargs.get("prompt_optimizer", True),
        )

        return (images[0] if len(images) == 1 else images,)


class MiniMaxDirectSpeechNode:
    """MiniMax Text-to-Speech node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "text": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "model": (["speech-2.6-hd", "speech-02-hd"], {"default": "speech-2.6-hd"}),
                "voice_id": ("STRING", {"default": "female-shaonv"}),
                "speed": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 2.0}),
                "vol": ("FLOAT", {"default": 1.0, "min": 0, "max": 10}),
                "pitch": ("INT", {"default": 0, "min": -12, "max": 12}),
                "emotion": (["happy", "sad", "angry", "fearful", "disgusted", "surprised", "neutral"], {"default": "happy"}),
                "sample_rate": ("INT", {"default": 32000}),
                "format": (["mp3", "wav", "pcm"], {"default": "mp3"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("audio_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/audio/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, text: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)
        _validate_string(text, "text")

        audio_url = await _generate_speech_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            text=text,
            model=kwargs.get("model", "speech-2.6-hd"),
            voice_id=kwargs.get("voice_id", "female-shaonv"),
            speed=kwargs.get("speed", 1.0),
            vol=kwargs.get("vol", 1.0),
            pitch=kwargs.get("pitch", 0),
            emotion=kwargs.get("emotion", "happy"),
            sample_rate=kwargs.get("sample_rate", 32000),
            output_format=kwargs.get("format", "mp3"),
        )

        return (audio_url,)


class MiniMaxDirectMusicNode:
    """MiniMax Music Generation node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "prompt": ("STRING", {"default": ""}),
            },
            "optional": {
                "lyrics": ("STRING", {"multiline": True, "default": ""}),
                "model": (["music-2.0"], {"default": "music-2.0"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("music_url",)
    FUNCTION = "execute"
    CATEGORY = "api node/audio/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, prompt: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        if not prompt and not kwargs.get("lyrics"):
            raise ValueError("Either prompt or lyrics is required")

        music_url = await _generate_music_direct(
            api_key=final_api_key,
            api_host=final_api_host,
            prompt=prompt or "music",
            lyrics=kwargs.get("lyrics", ""),
            model=kwargs.get("model", "music-2.0"),
        )

        return (music_url,)


class MiniMaxDirectVoiceCloneNode:
    """MiniMax Voice Clone node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "audio": ("AUDIO",),
                "voice_id": ("STRING", {"default": "my-cloned-voice"}),
            },
            "optional": {
                "text": ("STRING", {"default": "", "multiline": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("voice_id", "demo_audio_url")
    FUNCTION = "execute"
    CATEGORY = "api node/audio/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, audio, voice_id: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        if not voice_id:
            raise ValueError("Voice ID is required")

        # Audio tensor to bytes (simplified)
        audio_bytes = _audio_tensor_to_bytes(audio)

        # Call clone API
        import mimetypes
        headers = {
            "Authorization": f"Bearer {final_api_key}",
            "MM-API-Source": "ComfyUI-Direct",
        }

        mime_type = mimetypes.guess_type("audio.mp3")[0] or "audio/mpeg"
        files = {"file": ("audio.mp3", audio_bytes, mime_type)}
        data = {"purpose": "voice_clone"}

        upload_url = f"{final_api_host}/v1/files/upload"
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(upload_url, data=data, files=files, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    raise Exception(f"Failed to upload audio ({resp.status}): {response_text}")

                import json
                upload_response = json.loads(response_text)
                file_id = upload_response.get("file", {}).get("file_id")
                if not file_id:
                    raise Exception(f"No file_id in upload response: {upload_response}")

        payload = {"file_id": file_id, "voice_id": voice_id}
        text = kwargs.get("text", "")
        if text:
            payload["text"] = text
            payload["model"] = "speech-2.6-hd"

        clone_url = f"{final_api_host}/v1/voice_clone"
        async with aiohttp.ClientSession() as session:
            async with session.post(clone_url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    raise Exception(f"Voice clone failed ({resp.status}): {response_text}")

                import json
                clone_response = json.loads(response_text)
                demo_audio = clone_response.get("demo_audio")

        return (voice_id, demo_audio or "")


class MiniMaxDirectListVoicesNode:
    """MiniMax List Voices node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
            },
            "optional": {
                "voice_type": (["all", "system", "voice_cloning"], {"default": "all"}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("system_voices", "voice_cloning")
    FUNCTION = "execute"
    CATEGORY = "api node/audio/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        headers = {
            "Authorization": f"Bearer {final_api_key}",
            "Content-Type": "application/json",
            "MM-API-Source": "ComfyUI-Direct",
        }

        payload = {"voice_type": kwargs.get("voice_type", "all")}
        url = f"{final_api_host}/v1/get_voice"

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    raise Exception(f"List voices failed ({resp.status}): {response_text}")

                import json
                response = json.loads(response_text)

        system_voices = response.get("system_voice") or []
        voice_cloning = response.get("voice_cloning") or []

        system_list = [f"{v.get('voice_name')}:{v.get('voice_id')}" for v in system_voices]
        cloning_list = [f"{v.get('voice_name')}:{v.get('voice_id')}" for v in voice_cloning]

        return (",".join(system_list), ",".join(cloning_list))


class MiniMaxDirectVoiceDesignNode:
    """MiniMax Voice Design node for ComfyUI."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "api_host": ("STRING", {"default": MINIMAX_CHINA_HOST}),
                "prompt": ("STRING", {"default": ""}),
                "preview_text": ("STRING", {"default": "Hello, this is a test."}),
            },
            "optional": {
                "voice_id": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("voice_id", "trial_audio_path")
    FUNCTION = "execute"
    CATEGORY = "api node/audio/MiniMax"

    @classmethod
    async def execute(cls, api_key: str, api_host: str, prompt: str, preview_text: str, **kwargs):
        final_api_key, final_api_host = _get_api_key_and_host(api_key, api_host)
        _validate_api_key(final_api_key)

        if not prompt:
            raise ValueError("Prompt is required")
        if not preview_text:
            raise ValueError("Preview text is required")

        headers = {
            "Authorization": f"Bearer {final_api_key}",
            "Content-Type": "application/json",
            "MM-API-Source": "ComfyUI-Direct",
        }

        payload = {"prompt": prompt, "preview_text": preview_text}
        voice_id = kwargs.get("voice_id", "")
        if voice_id:
            payload["voice_id"] = voice_id

        url = f"{final_api_host}/v1/voice_design"

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    raise Exception(f"Voice design failed ({resp.status}): {response_text}")

                import json
                response = json.loads(response_text)

        generated_voice_id = response.get("voice_id", "")
        trial_audio_hex = response.get("trial_audio", "")

        audio_path = ""
        if trial_audio_hex:
            try:
                audio_bytes = bytes.fromhex(trial_audio_hex)
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(audio_bytes)
                    audio_path = f.name
            except Exception:
                pass

        return (generated_voice_id, audio_path)


def _audio_tensor_to_bytes(audio: Any) -> bytes:
    """Convert audio tensor to MP3 bytes."""
    if not TORCH_AVAILABLE:
        raise RuntimeError("torch is required for _audio_tensor_to_bytes")

    try:
        import numpy as np
        from pydub import AudioSegment

        if audio.ndim == 2:
            if audio.shape[0] == 2:
                audio_np = audio.cpu().numpy().T
            else:
                audio_np = audio.cpu().numpy()
        else:
            audio_np = audio.cpu().numpy()

        if audio_np.max() <= 1.0:
            audio_np = (audio_np * 32767).astype(np.int16)
        else:
            audio_np = audio_np.astype(np.int16)

        audio_seg = AudioSegment(
            audio_np.tobytes(),
            frame_rate=32000,
            sample_width=2,
            channels=audio_np.shape[1] if audio_np.ndim > 1 else 1,
        )
        return audio_seg.export(format="mp3").read()
    except ImportError:
        if audio.ndim == 2:
            audio = audio[0] if audio.shape[0] == 2 else audio
        audio_bytes = (audio.cpu().numpy() * 32767).astype(np.int16).tobytes()
        return audio_bytes


# Node mapping for ComfyUI
NODE_CLASS_MAPPINGS = {
    "MiniMaxDirectTextToVideoNode": MiniMaxDirectTextToVideoNode,
    "MiniMaxDirectImageToVideoNode": MiniMaxDirectImageToVideoNode,
    "MiniMaxDirectHailuoNode": MiniMaxDirectHailuoNode,
    "MiniMaxDirectSubjectToVideoNode": MiniMaxDirectSubjectToVideoNode,
    "MiniMaxDirectImageNode": MiniMaxDirectImageNode,
    "MiniMaxDirectSpeechNode": MiniMaxDirectSpeechNode,
    "MiniMaxDirectMusicNode": MiniMaxDirectMusicNode,
    "MiniMaxDirectVoiceCloneNode": MiniMaxDirectVoiceCloneNode,
    "MiniMaxDirectListVoicesNode": MiniMaxDirectListVoicesNode,
    "MiniMaxDirectVoiceDesignNode": MiniMaxDirectVoiceDesignNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxDirectTextToVideoNode": "MiniMax T2V",
    "MiniMaxDirectImageToVideoNode": "MiniMax I2V",
    "MiniMaxDirectHailuoNode": "MiniMax Hailuo-02",
    "MiniMaxDirectSubjectToVideoNode": "MiniMax S2V",
    "MiniMaxDirectImageNode": "MiniMax Image",
    "MiniMaxDirectSpeechNode": "MiniMax Speech",
    "MiniMaxDirectMusicNode": "MiniMax Music",
    "MiniMaxDirectVoiceCloneNode": "MiniMax Voice Clone",
    "MiniMaxDirectListVoicesNode": "MiniMax List Voices",
    "MiniMaxDirectVoiceDesignNode": "MiniMax Voice Design",
}
