# -*- encoding: utf-8 -*-
"""MiniMax Media Client - Direct API integration for video, image, audio, and music generation.

This module provides a standalone client for MiniMax's media generation APIs,
independent of ComfyUI's infrastructure.

API Documentation: https://platform.minimaxi.com/docs/api-reference/video-generation-intro

Supported Features:
- Video Generation (T2V, I2V, S2V, Hailuo-02)
- Image Generation (image-01)
- Text-to-Speech (TTS)
- Music Generation (music-2.0)
- Voice Clone & Voice Design

Usage:
    client = MiniMaxMediaClient()

    # Generate video
    result = await client.generate_video(
        prompt="a beautiful landscape",
        model="T2V-01"
    )

    # Generate image
    result = await client.generate_image(
        prompt="a fantasy castle",
        aspect_ratio="16:9"
    )

    # Generate speech
    result = await client.generate_speech(
        text="你好，欢迎来到这个世界",
        voice_id="female-shaonv"
    )

    # Generate music
    result = await client.generate_music(
        prompt="epic orchestral music, dramatic, heroic"
    )
"""

import asyncio
import base64
import io
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import aiohttp

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants
MINIMAX_GLOBAL_HOST = "https://api.minimax.io"
MINIMAX_CHINA_HOST = "https://api.minimaxi.com"

# Polling configuration
T2V_AVERAGE_DURATION = 234
I2V_AVERAGE_DURATION = 114
POLL_INTERVAL = 5
MAX_POLL_ATTEMPTS = 120


class MiniMaxVideoStatus(str, Enum):
    """MiniMax video generation status."""
    QUEUING = "Queueing"
    PREPARING = "Preparing"
    PROCESSING = "Processing"
    SUCCESS = "Success"
    FAIL = "Fail"


class MiniMaxModel(str, Enum):
    """MiniMax available models."""
    # Video models
    T2V_01_Director = "T2V-01-Director"
    I2V_01_Director = "I2V-01-Director"
    S2V_01 = "S2V-01"
    I2V_01 = "I2V-01"
    I2V_01_live = "I2V-01-live"
    T2V_01 = "T2V-01"
    Hailuo_02 = "MiniMax-Hailuo-02"
    # Image model
    IMAGE_01 = "image-01"
    # Music model
    MUSIC_20 = "music-2.0"
    # Speech models
    SPEECH_26_HD = "speech-2.6-hd"
    SPEECH_02_HD = "speech-02-hd"


@dataclass
class VideoGenerationResult:
    """Result of video generation."""
    success: bool
    video_url: Optional[str] = None
    backup_url: Optional[str] = None
    file_id: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ImageGenerationResult:
    """Result of image generation."""
    success: bool
    image_urls: List[str] = None
    error: Optional[str] = None


@dataclass
class SpeechGenerationResult:
    """Result of speech generation."""
    success: bool
    audio_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class MusicGenerationResult:
    """Result of music generation."""
    success: bool
    music_url: Optional[str] = None
    task_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class VoiceCloneResult:
    """Result of voice cloning."""
    success: bool
    voice_id: Optional[str] = None
    demo_audio_url: Optional[str] = None
    error: Optional[str] = None


class MiniMaxMediaClient:
    """Standalone MiniMax media generation client.

    This client provides direct access to MiniMax APIs for generating
    videos, images, audio (TTS), and music without requiring ComfyUI.

    Args:
        api_key: MiniMax API key. If not provided, reads from MINIMAX_API_KEY env.
        api_host: API host URL. Use MINIMAX_CHINA_HOST for China, MINIMAX_GLOBAL_HOST for global.
            If not provided, reads from MINIMAX_API_HOST env or defaults to China host.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_host: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY", "")
        self.api_host = api_host or os.environ.get(
            "MINIMAX_API_HOST", MINIMAX_CHINA_HOST
        )

        if not self.api_key:
            logger.warning(
                "MiniMax API key not provided. Set MINIMAX_API_KEY environment variable."
            )

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "MM-API-Source": "young-writer-direct",
        }

    def _validate_api_key(self) -> None:
        """Validate that API key is present."""
        if not self.api_key:
            raise ValueError(
                "MiniMax API key is required. Set MINIMAX_API_KEY environment variable "
                "or pass api_key parameter."
            )

    # ============ Video Generation ============

    async def generate_video(
        self,
        prompt: str,
        model: str = "T2V-01",
        first_frame_image: Optional[Any] = None,
        subject_image: Optional[Any] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
        prompt_optimizer: bool = True,
    ) -> VideoGenerationResult:
        """Generate video from text or image.

        Args:
            prompt: Text description of the video.
            model: Video model to use (T2V-01, T2V-01-Director, MiniMax-Hailuo-02, etc.).
            first_frame_image: Optional first frame image for I2V models.
            subject_image: Optional subject image for S2V models.
            duration: Video duration in seconds (6 or 10).
            resolution: Video resolution (768P or 1080P).
            prompt_optimizer: Whether to use prompt optimization.

        Returns:
            VideoGenerationResult with video URL or error.
        """
        self._validate_api_key()

        headers = self._get_headers()
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "prompt_optimizer": prompt_optimizer,
        }

        if duration is not None:
            payload["duration"] = duration
        if resolution is not None:
            payload["resolution"] = resolution

        # Handle first frame image
        if first_frame_image is not None:
            if TORCH_AVAILABLE and isinstance(first_frame_image, torch.Tensor):
                first_frame_image = await self._image_tensor_to_base64(first_frame_image)
            payload["first_frame_image"] = first_frame_image

        # Handle subject image
        if subject_image is not None:
            if TORCH_AVAILABLE and isinstance(subject_image, torch.Tensor):
                subject_image = await self._image_tensor_to_base64(subject_image)
            payload["subject_image"] = subject_image

        # Submit generation request
        submit_url = f"{self.api_host}/v1/video_generation"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                submit_url, json=payload, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return VideoGenerationResult(
                        success=False,
                        error=f"MiniMax API error ({resp.status}): {response_text}"
                    )

                import json
                submit_response = json.loads(response_text)
                base_resp = submit_response.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return VideoGenerationResult(
                        success=False,
                        error=f"API error: {base_resp.get('status_msg')} "
                              f"(code: {base_resp.get('status_code')})"
                    )

                task_id = submit_response.get("task_id")
                if not task_id:
                    return VideoGenerationResult(
                        success=False,
                        error="No task_id returned from MiniMax API"
                    )

        logger.info(f"MiniMax video task submitted: {task_id}")

        # Poll for completion
        query_url = f"{self.api_host}/v1/query/video_generation"
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
                            return VideoGenerationResult(
                                success=False,
                                error=f"Video succeeded but no file_id: {poll_response}"
                            )
                        break

                    elif status == MiniMaxVideoStatus.FAIL.value:
                        return VideoGenerationResult(
                            success=False,
                            error=f"Video generation failed: {poll_response.get('base_resp', {}).get('status_msg', 'Unknown')}"
                        )

                    await asyncio.sleep(POLL_INTERVAL)
        else:
            return VideoGenerationResult(
                success=False,
                error=f"Video generation timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL} seconds"
            )

        # Get download URL
        file_url = f"{self.api_host}/v1/files/retrieve"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                file_url, params={"file_id": file_id}, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return VideoGenerationResult(
                        success=False,
                        error=f"Failed to retrieve file ({resp.status}): {response_text}"
                    )

                import json
                file_response = json.loads(response_text)
                file_data = file_response.get("file", {})
                download_url = file_data.get("download_url")
                backup_url = file_data.get("backup_download_url")

                if not download_url:
                    return VideoGenerationResult(
                        success=False,
                        error=f"No download URL in file response: {file_response}"
                    )

        return VideoGenerationResult(
            success=True,
            video_url=download_url,
            backup_url=backup_url,
            file_id=file_id,
            task_id=task_id,
        )

    async def generate_video_sync(
        self,
        prompt: str,
        model: str = "T2V-01",
        first_frame_image: Optional[Any] = None,
        subject_image: Optional[Any] = None,
        duration: Optional[int] = None,
        resolution: Optional[str] = None,
        prompt_optimizer: bool = True,
    ) -> VideoGenerationResult:
        """Synchronous version of video generation."""
        return await self.generate_video(
            prompt=prompt,
            model=model,
            first_frame_image=first_frame_image,
            subject_image=subject_image,
            duration=duration,
            resolution=resolution,
            prompt_optimizer=prompt_optimizer,
        )

    # ============ Image Generation ============

    async def generate_image(
        self,
        prompt: str,
        model: str = "image-01",
        aspect_ratio: str = "1:1",
        n: int = 1,
        prompt_optimizer: bool = True,
    ) -> ImageGenerationResult:
        """Generate image from text.

        Args:
            prompt: Text description of the image.
            model: Image model to use (image-01).
            aspect_ratio: Image aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4).
            n: Number of images to generate (1-4).
            prompt_optimizer: Whether to use prompt optimization.

        Returns:
            ImageGenerationResult with image URLs or error.
        """
        self._validate_api_key()

        headers = self._get_headers()
        payload = {
            "model": model,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "n": min(n, 4),  # API limit
            "prompt_optimizer": prompt_optimizer,
        }

        submit_url = f"{self.api_host}/v1/image_generation"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                submit_url, json=payload, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return ImageGenerationResult(
                        success=False,
                        error=f"MiniMax API error ({resp.status}): {response_text}"
                    )

                import json
                submit_response = json.loads(response_text)
                base_resp = submit_response.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return ImageGenerationResult(
                        success=False,
                        error=f"API error: {base_resp.get('status_msg')} "
                              f"(code: {base_resp.get('status_code')})"
                    )

                image_urls = submit_response.get("data", {}).get("image_urls", [])
                if not image_urls:
                    return ImageGenerationResult(
                        success=False,
                        error="No images generated"
                    )

        return ImageGenerationResult(
            success=True,
            image_urls=image_urls,
        )

    async def download_image(self, url: str) -> Optional[Any]:
        """Download image from URL and return as tensor.

        Args:
            url: Image URL to download.

        Returns:
            Image tensor or None if download fails.
        """
        if not TORCH_AVAILABLE:
            logger.warning("torch not available, download_image returns None")
            return None

        try:
            from PIL import Image
            import numpy as np

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    image_bytes = await resp.read()
                    image = Image.open(io.BytesIO(image_bytes))
                    image = image.convert("RGB")
                    img_np = np.array(image).astype(np.float32) / 255.0
                    # Convert to (B,H,W,C) format for ComfyUI
                    if img_np.ndim == 3:
                        img_np = np.expand_dims(img_np, axis=0)
                    return torch.from_numpy(img_np)
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None

    # ============ Audio/Speech Generation ============

    async def generate_speech(
        self,
        text: str,
        model: str = "speech-02",
        voice_id: str = "female-shaonv",
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
        emotion: Optional[str] = None,
        sample_rate: int = 32000,
        output_format: str = "mp3",
    ) -> SpeechGenerationResult:
        """Generate speech from text (TTS).

        Args:
            text: Text to convert to speech.
            model: Speech model (speech-02, speech-02-hd, speech-2.6-hd, etc.).
            voice_id: Voice identifier.
            speed: Speech speed (0.5-2.0).
            vol: Volume level (0-10).
            pitch: Pitch adjustment (-12 to 12).
            emotion: Emotional tone (happy, sad, angry, fearful, disgusted, surprised, neutral).
                      Only supported by older models (speech-02-hd, speech-2.6-hd).
                      Do NOT use with Speech-2.6-HD or Speech-02-HD.
            sample_rate: Audio sample rate.
            output_format: Output format (mp3, wav, pcm).

        Returns:
            SpeechGenerationResult with audio URL or error.
        """
        self._validate_api_key()

        headers = self._get_headers()
        voice_setting = {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch,
        }
        # emotion is only supported by lowercase model names (speech-02-hd, speech-2.6-hd)
        # New uppercase models (Speech-02-HD, Speech-2.6-HD) do NOT support emotion
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

        submit_url = f"{self.api_host}/v1/t2a_v2"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                submit_url, json=payload, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return SpeechGenerationResult(
                        success=False,
                        error=f"MiniMax API error ({resp.status}): {response_text}"
                    )

                import json
                submit_response = json.loads(response_text)
                base_resp = submit_response.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return SpeechGenerationResult(
                        success=False,
                        error=f"API error: {base_resp.get('status_msg')} "
                              f"(code: {base_resp.get('status_code')})"
                    )

                audio_url = submit_response.get("data", {}).get("audio")
                if not audio_url:
                    return SpeechGenerationResult(
                        success=False,
                        error="No audio URL returned"
                    )

        return SpeechGenerationResult(
            success=True,
            audio_url=audio_url,
        )

    async def download_audio(self, url: str) -> Optional[bytes]:
        """Download audio from URL.

        Args:
            url: Audio URL to download.

        Returns:
            Audio bytes or None if download fails.
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.read()
        except Exception as e:
            logger.error(f"Failed to download audio: {e}")
            return None

    # ============ Music Generation ============

    async def generate_music(
        self,
        prompt: str,
        lyrics: str = "",
        model: str = "music-2.0",
    ) -> MusicGenerationResult:
        """Generate music from text prompt.

        Args:
            prompt: Music description (style, mood, instruments, etc.).
            lyrics: Optional song lyrics.
            model: Music model (music-2.0).

        Returns:
            MusicGenerationResult with music URL or error.
        """
        self._validate_api_key()

        headers = self._get_headers()
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }

        if lyrics:
            payload["lyrics"] = lyrics

        submit_url = f"{self.api_host}/v1/music_generation"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                submit_url, json=payload, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return MusicGenerationResult(
                        success=False,
                        error=f"MiniMax API error ({resp.status}): {response_text}"
                    )

                import json
                submit_response = json.loads(response_text)
                base_resp = submit_response.get("base_resp", {})
                if base_resp.get("status_code") != 0:
                    return MusicGenerationResult(
                        success=False,
                        error=f"API error: {base_resp.get('status_msg')} "
                              f"(code: {base_resp.get('status_code')})"
                    )

                task_id = submit_response.get("task_id")
                if not task_id:
                    return MusicGenerationResult(
                        success=False,
                        error="No task_id returned from music API"
                    )

        logger.info(f"MiniMax music task submitted: {task_id}")

        # Poll for completion
        query_url = f"{self.api_host}/v1/query/music_generation"
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
                            return MusicGenerationResult(
                                success=False,
                                error=f"Music succeeded but no URL: {poll_response}"
                            )
                        return MusicGenerationResult(
                            success=True,
                            music_url=music_url,
                            task_id=task_id,
                        )

                    elif status == MiniMaxVideoStatus.FAIL.value:
                        return MusicGenerationResult(
                            success=False,
                            error=f"Music generation failed: {poll_response.get('base_resp', {}).get('status_msg', 'Unknown')}"
                        )

                    await asyncio.sleep(POLL_INTERVAL)
        else:
            return MusicGenerationResult(
                success=False,
                error="Music generation timed out"
            )

    # ============ Voice Clone ============

    async def clone_voice(
        self,
        audio_data: bytes,
        voice_id: str,
        text: str = "",
    ) -> VoiceCloneResult:
        """Clone a voice from audio sample.

        Args:
            audio_data: Audio file bytes to clone voice from.
            voice_id: Identifier for the cloned voice.
            text: Optional demo text.

        Returns:
            VoiceCloneResult with voice_id and demo audio URL or error.
        """
        self._validate_api_key()

        import mimetypes

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "MM-API-Source": "young-writer-direct",
        }

        # Upload audio file first
        mime_type = mimetypes.guess_type("audio.mp3")[0] or "audio/mpeg"
        files = {"file": ("audio.mp3", audio_data, mime_type)}
        data = {"purpose": "voice_clone"}

        upload_url = f"{self.api_host}/v1/files/upload"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                upload_url, data=data, files=files, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return VoiceCloneResult(
                        success=False,
                        error=f"Failed to upload audio ({resp.status}): {response_text}"
                    )

                import json
                upload_response = json.loads(response_text)
                file_id = upload_response.get("file", {}).get("file_id")
                if not file_id:
                    return VoiceCloneResult(
                        success=False,
                        error=f"No file_id in upload response: {upload_response}"
                    )

        # Clone voice
        payload: Dict[str, Any] = {"file_id": file_id, "voice_id": voice_id}
        if text:
            payload["text"] = text
            payload["model"] = "speech-2.6-hd"

        clone_url = f"{self.api_host}/v1/voice_clone"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                clone_url, json=payload, headers=headers
            ) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return VoiceCloneResult(
                        success=False,
                        error=f"Voice clone failed ({resp.status}): {response_text}"
                    )

                import json
                clone_response = json.loads(response_text)
                demo_audio = clone_response.get("demo_audio")

                return VoiceCloneResult(
                    success=True,
                    voice_id=voice_id,
                    demo_audio_url=demo_audio or "",
                )

    async def list_voices(
        self,
        voice_type: str = "all",
    ) -> Dict[str, List[str]]:
        """List available voices.

        Args:
            voice_type: Type of voices to list (all, system, voice_cloning).

        Returns:
            Dict with system_voices and voice_cloning lists.
        """
        self._validate_api_key()

        headers = self._get_headers()
        payload = {"voice_type": voice_type}
        url = f"{self.api_host}/v1/get_voice"

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

        return {
            "system_voices": system_list,
            "voice_cloning": cloning_list,
        }

    async def create_voice_design(
        self,
        prompt: str,
        preview_text: str,
        voice_id: str = "",
    ) -> VoiceCloneResult:
        """Create a custom voice from text prompt (Voice Design).

        Args:
            prompt: Voice description (e.g., 'young female, soft tone, emotional range').
            preview_text: Preview text to hear the voice.
            voice_id: Optional voice ID to overwrite.

        Returns:
            VoiceCloneResult with voice_id and trial audio path or error.
        """
        self._validate_api_key()

        headers = self._get_headers()
        payload: Dict[str, Any] = {"prompt": prompt, "preview_text": preview_text}
        if voice_id:
            payload["voice_id"] = voice_id

        url = f"{self.api_host}/v1/voice_design"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                response_text = await resp.text()
                if resp.status != 200:
                    return VoiceCloneResult(
                        success=False,
                        error=f"Voice design failed ({resp.status}): {response_text}"
                    )

                import json
                response = json.loads(response_text)

        generated_voice_id = response.get("voice_id", "")
        trial_audio_hex = response.get("trial_audio", "")

        # Convert hex to audio if available
        audio_url = ""
        if trial_audio_hex:
            try:
                audio_bytes = bytes.fromhex(trial_audio_hex)
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(audio_bytes)
                    audio_url = f.name
            except Exception:
                pass

        return VoiceCloneResult(
            success=True,
            voice_id=generated_voice_id,
            demo_audio_url=audio_url,
        )

    # ============ Helper Methods ============

    async def _image_tensor_to_base64(self, image: Any) -> str:
        """Convert image tensor to base64 data URL."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch is required for _image_tensor_to_base64")

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


# Singleton instance
_client_instance: Optional[MiniMaxMediaClient] = None


def get_minimax_media_client(
    api_key: Optional[str] = None,
    api_host: Optional[str] = None,
) -> MiniMaxMediaClient:
    """Get the global MiniMaxMediaClient instance.

    Args:
        api_key: Optional API key override.
        api_host: Optional API host override.

    Returns:
        MiniMaxMediaClient singleton instance.
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = MiniMaxMediaClient(api_key=api_key, api_host=api_host)

    return _client_instance
