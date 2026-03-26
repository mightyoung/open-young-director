"""Workflow builders for ComfyUI.

Provides convenient builders for common workflow types:
- Image generation (text-to-image, img2img)
- Audio generation (text-to-audio, audiobook)
- Video generation (text-to-video, image-to-video)
"""

from __future__ import annotations

import random
from typing import Any
from dataclasses import dataclass


class ImageWorkflowBuilder:
    """Builder for image generation workflows.

    Usage:
        builder = ImageWorkflowBuilder()
        workflow = builder.build_text_to_image(
            prompt="a beautiful landscape",
            negative="blurry, low quality",
            width=1024,
            height=1024,
        )
    """

    DEFAULT_MODEL = "sd_xl_base_1.0.safetensors"
    DEFAULT_CLIP = "clip_g.safetensors"
    DEFAULT_VAE = "ae.safetensors"
    DEFAULT_SAMPLER = "euler"
    DEFAULT_STEPS = 20
    DEFAULT_CFG = 8.0

    def build_text_to_image(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        batch_size: int = 1,
        steps: int = DEFAULT_STEPS,
        cfg: float = DEFAULT_CFG,
        sampler_name: str = DEFAULT_SAMPLER,
        scheduler: str = "normal",
        seed: int | None = None,
        model: str = DEFAULT_MODEL,
        clip: str = DEFAULT_CLIP,
        vae: str = DEFAULT_VAE,
        denoise: float = 1.0,
    ) -> dict[str, dict[str, Any]]:
        """Build a text-to-image workflow.

        Args:
            prompt: Positive prompt describing the desired image
            negative: Negative prompt describing what to avoid
            width: Image width in pixels
            height: Image height in pixels
            batch_size: Number of images to generate
            steps: Number of sampling steps
            cfg: CFG scale for guidance strength
            sampler_name: Sampler algorithm name
            scheduler: Scheduler name
            seed: Random seed (random if None)
            model: Model checkpoint filename
            clip: CLIP model filename
            vae: VAE model filename
            denoise: Denoise strength (0-1)

        Returns:
            Workflow dict ready for execution
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            # Checkpoint Loader (Model)
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model,
                },
            },
            # CLIP Text Encode (Positive)
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 0],
                },
            },
            # CLIP Text Encode (Negative)
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["1", 0],
                },
            },
            # Empty Latent Image
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": batch_size,
                },
            },
            # KSampler
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler,
                    "denoise": denoise,
                },
            },
            # VAE Decode
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 1],
                },
            },
            # SaveImage
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["6", 0],
                    "filename_prefix": "novel_illustration",
                },
            },
        }

        return workflow

    def build_text_to_image_with_vae(
        self,
        prompt: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        batch_size: int = 1,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
        model: str = DEFAULT_MODEL,
        clip: str = DEFAULT_CLIP,
        vae: str = DEFAULT_VAE,
    ) -> dict[str, dict[str, Any]]:
        """Build a text-to-image workflow with explicit VAE.

        Uses a separate VAE loader instead of using the VAE from checkpoint.

        Args:
            Same as build_text_to_image plus:
            vae: Standalone VAE model filename

        Returns:
            Workflow dict with separate VAE loader
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            # Checkpoint Loader (Model without VAE)
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model,
                },
            },
            # VAE Loader
            "2": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": vae,
                },
            },
            # CLIP Text Encode (Positive)
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 0],
                },
            },
            # CLIP Text Encode (Negative)
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["1", 0],
                },
            },
            # Empty Latent Image
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": batch_size,
                },
            },
            # KSampler
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            # VAE Decode
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["2", 0],
                },
            },
            # SaveImage
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["7", 0],
                    "filename_prefix": "novel_illustration",
                },
            },
        }

        return workflow

    def build_image_to_image(
        self,
        prompt: str,
        input_image: str,
        negative: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 8.0,
        denoise: float = 0.7,
        seed: int | None = None,
        model: str = DEFAULT_MODEL,
    ) -> dict[str, dict[str, Any]]:
        """Build an image-to-image (img2img) workflow.

        Args:
            prompt: Positive prompt
            input_image: Path to input image or image node output
            negative: Negative prompt
            width: Target width
            height: Target height
            steps: Sampling steps
            cfg: CFG scale
            denoise: Denoise strength (lower = more original image preserved)
            seed: Random seed
            model: Model checkpoint

        Returns:
            Workflow dict for img2img
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            # LoadImage node
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": input_image,
                },
            },
            # Checkpoint Loader
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model,
                },
            },
            # CLIP Text Encode (Positive)
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["2", 0],
                },
            },
            # CLIP Text Encode (Negative)
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["2", 0],
                },
            },
            # VAE Encode (for img2img)
            "5": {
                "class_type": "VAEEncode",
                "inputs": {
                    "pixels": ["1", 0],
                    "vae": ["2", 1],
                },
            },
            # KSampler
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["2", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": denoise,
                },
            },
            # VAE Decode
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["2", 1],
                },
            },
            # SaveImage
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["7", 0],
                    "filename_prefix": "novel_img2img",
                },
            },
        }

        return workflow


class AudioWorkflowBuilder:
    """Builder for audio generation workflows.

    Supports:
    - Text-to-speech (TTS)
    - Audiobook generation
    - Sound effects
    - Background music
    """

    DEFAULT_AUDIO_MODEL = "audio_model.safetensors"
    DEFAULT_TTS_MODEL = "tts_model.safetensors"
    DEFAULT_SFX_MODEL = "sfx_model.safetensors"
    DEFAULT_BGM_MODEL = "bgm_model.safetensors"

    def build_text_to_audio(
        self,
        text: str,
        duration: int = 30,
        model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build a text-to-speech or audio generation workflow.

        Note: Requires appropriate audio nodes to be available.

        Args:
            text: Text to convert to audio
            duration: Maximum duration in seconds
            model: Audio model filename

        Returns:
            Workflow dict for audio generation
        """
        model = model or self.DEFAULT_AUDIO_MODEL

        workflow = {
            "1": {
                "class_type": "EmptyLatentAudio",
                "inputs": {
                    "seconds": duration,
                },
            },
            "2": {
                "class_type": "TextEncodeAudio",
                "inputs": {
                    "text": text,
                },
            },
            "3": {
                "class_type": "AudioSampler",
                "inputs": {
                    "model": model,
                    "conditioning": ["2", 0],
                    "latent_audio": ["1", 0],
                },
            },
            "4": {
                "class_type": "AudioDecode",
                "inputs": {
                    "samples": ["3", 0],
                },
            },
            "5": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["4", 0],
                    "filename_prefix": "novel_audiobook",
                },
            },
        }

        return workflow

    def build_audiobook(
        self,
        text: str,
        voice_model: str = "default_voice.safetensors",
        duration: int = 300,
        narrator: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Build an audiobook generation workflow.

        Args:
            text: Full text to convert to audiobook
            voice_model: Voice model for TTS
            duration: Maximum audio duration in seconds
            narrator: Whether to include narration markers

        Returns:
            Workflow dict for audiobook generation
        """
        # Split text into chunks for longer content
        chunk_size = 500  # characters per chunk
        text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

        workflow = {
            "1": {
                "class_type": "EmptyLatentAudio",
                "inputs": {
                    "seconds": duration,
                },
            },
            "2": {
                "class_type": "TextEncodeAudio",
                "inputs": {
                    "text": text[:chunk_size],
                },
            },
            "3": {
                "class_type": "AudioSampler",
                "inputs": {
                    "model": voice_model,
                    "conditioning": ["2", 0],
                    "latent_audio": ["1", 0],
                },
            },
            "4": {
                "class_type": "AudioDecode",
                "inputs": {
                    "samples": ["3", 0],
                },
            },
            "5": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["4", 0],
                    "filename_prefix": "novel_audiobook",
                },
            },
        }

        return workflow

    def build_sound_effect(
        self,
        description: str,
        duration: int = 5,
        model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build a sound effects generation workflow.

        Args:
            description: Description of the sound effect
            duration: Duration in seconds
            model: SFX model filename

        Returns:
            Workflow dict for sound effect generation
        """
        model = model or self.DEFAULT_SFX_MODEL

        workflow = {
            "1": {
                "class_type": "EmptyLatentAudio",
                "inputs": {
                    "seconds": duration,
                },
            },
            "2": {
                "class_type": "TextEncodeAudio",
                "inputs": {
                    "text": description,
                },
            },
            "3": {
                "class_type": "AudioSampler",
                "inputs": {
                    "model": model,
                    "conditioning": ["2", 0],
                    "latent_audio": ["1", 0],
                },
            },
            "4": {
                "class_type": "AudioDecode",
                "inputs": {
                    "samples": ["3", 0],
                },
            },
            "5": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["4", 0],
                    "filename_prefix": "novel_sfx",
                },
            },
        }

        return workflow

    def build_background_music(
        self,
        mood: str,
        duration: int = 60,
        model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build background music generation workflow.

        Args:
            mood: Mood/style description (e.g., "epic", "peaceful", "tense")
            duration: Duration in seconds
            model: BGM model filename

        Returns:
            Workflow dict for background music generation
        """
        model = model or self.DEFAULT_BGM_MODEL

        workflow = {
            "1": {
                "class_type": "EmptyLatentAudio",
                "inputs": {
                    "seconds": duration,
                },
            },
            "2": {
                "class_type": "TextEncodeAudio",
                "inputs": {
                    "text": f"background music, {mood} mood",
                },
            },
            "3": {
                "class_type": "AudioSampler",
                "inputs": {
                    "model": model,
                    "conditioning": ["2", 0],
                    "latent_audio": ["1", 0],
                },
            },
            "4": {
                "class_type": "AudioDecode",
                "inputs": {
                    "samples": ["3", 0],
                },
            },
            "5": {
                "class_type": "SaveAudio",
                "inputs": {
                    "audio": ["4", 0],
                    "filename_prefix": "novel_bgm",
                },
            },
        }

        return workflow

    def build_audio_mix(
        self,
        audio_sources: list[str],
        mix_type: str = "overlay",
    ) -> dict[str, dict[str, Any]]:
        """Build an audio mixing workflow.

        Args:
            audio_sources: List of audio file paths to mix
            mix_type: Type of mixing ("overlay", "sequence", "crossfade")

        Returns:
            Workflow dict for audio mixing
        """
        workflow = {}
        node_id = 1

        for i, audio_path in enumerate(audio_sources):
            workflow[str(node_id)] = {
                "class_type": "LoadAudio",
                "inputs": {
                    "audio": audio_path,
                },
            }
            node_id += 1

        # Add mixer node
        workflow[str(node_id)] = {
            "class_type": "AudioMix",
            "inputs": {
                "sources": [[str(i+1), 0] for i in range(len(audio_sources))],
                "mix_type": mix_type,
            },
        }
        node_id += 1

        # Save output
        workflow[str(node_id)] = {
            "class_type": "SaveAudio",
            "inputs": {
                "audio": [str(node_id - 1), 0],
                "filename_prefix": "novel_mix",
            },
        }

        return workflow


class VideoWorkflowBuilder:
    """Builder for video generation workflows.

    Supports:
    - Text-to-video (T2V)
    - Image-to-video (I2V)
    - Video-to-video (V2V)
    - Video editing and composition
    """

    DEFAULT_VIDEO_MODEL = "sv3d.safetensors"
    DEFAULT_I2V_MODEL = "i2v_model.safetensors"

    def build_text_to_video(
        self,
        prompt: str,
        negative: str = "",
        width: int = 512,
        height: int = 512,
        frames: int = 24,
        duration: int = 2,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
        model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build a text-to-video workflow.

        Args:
            prompt: Positive prompt describing the video
            negative: Negative prompt
            width: Frame width
            height: Frame height
            frames: Number of frames
            duration: Duration in seconds
            steps: Sampling steps
            cfg: CFG scale
            seed: Random seed
            model: Video model filename

        Returns:
            Workflow dict for text-to-video generation
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        model = model or self.DEFAULT_VIDEO_MODEL

        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model,
                },
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["1", 0],
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["1", 0],
                },
            },
            "4": {
                "class_type": "EmptyLatentVideo",
                "inputs": {
                    "width": width,
                    "height": height,
                    "frames": frames,
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 1],
                },
            },
            "7": {
                "class_type": "SaveVideo",
                "inputs": {
                    "images": ["6", 0],
                    "filename_prefix": "novel_video",
                    "fps": frames // duration if duration > 0 else 12,
                },
            },
        }

        return workflow

    def build_image_to_video(
        self,
        prompt: str,
        input_image: str,
        negative: str = "",
        frames: int = 24,
        duration: int = 2,
        steps: int = 20,
        cfg: float = 8.0,
        seed: int | None = None,
        model: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build an image-to-video workflow.

        Args:
            prompt: Positive prompt describing the video
            input_image: Path to input image
            negative: Negative prompt
            frames: Number of frames
            duration: Duration in seconds
            steps: Sampling steps
            cfg: CFG scale
            seed: Random seed
            model: I2V model filename

        Returns:
            Workflow dict for image-to-video generation
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        model = model or self.DEFAULT_I2V_MODEL

        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": input_image,
                },
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": model,
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["2", 0],
                },
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["2", 0],
                },
            },
            "5": {
                "class_type": "EmptyLatentVideo",
                "inputs": {
                    "width": 512,
                    "height": 512,
                    "frames": frames,
                },
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["2", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                },
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["2", 1],
                },
            },
            "8": {
                "class_type": "SaveVideo",
                "inputs": {
                    "images": ["7", 0],
                    "filename_prefix": "novel_i2v",
                    "fps": frames // duration if duration > 0 else 12,
                },
            },
        }

        return workflow

    def build_video_to_video(
        self,
        prompt: str,
        input_video: str,
        negative: str = "",
        strength: float = 0.5,
        frames: int = 24,
        seed: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build a video-to-video (style transfer) workflow.

        Args:
            prompt: Style prompt
            input_video: Path to input video
            negative: Negative prompt
            strength: Transformation strength (0-1)
            frames: Number of frames to process
            seed: Random seed

        Returns:
            Workflow dict for video style transfer
        """
        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        workflow = {
            "1": {
                "class_type": "LoadVideo",
                "inputs": {
                    "video": input_video,
                },
            },
            "2": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": "sv3d.safetensors",
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["2", 0],
                },
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative if negative else "",
                    "clip": ["2", 0],
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["2", 0],
                    "positive": ["3", 0],
                    "negative": ["4", 0],
                    "latent_image": ["1", 0],
                    "seed": seed,
                    "steps": 20,
                    "cfg": 8.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": strength,
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["2", 1],
                },
            },
            "7": {
                "class_type": "SaveVideo",
                "inputs": {
                    "images": ["6", 0],
                    "filename_prefix": "novel_v2v",
                    "fps": 12,
                },
            },
        }

        return workflow

    def build_video_compose(
        self,
        video_sources: list[str],
        transition: str = "cut",
        duration: int | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build a video composition workflow.

        Args:
            video_sources: List of video paths to compose
            transition: Transition type ("cut", "fade", "dissolve", "slide")
            duration: Total output duration (auto if None)

        Returns:
            Workflow dict for video composition
        """
        workflow = {}
        node_id = 1

        for i, video_path in enumerate(video_sources):
            workflow[str(node_id)] = {
                "class_type": "LoadVideo",
                "inputs": {
                    "video": video_path,
                },
            }
            node_id += 1

        # Add compositor node
        source_refs = [[str(i+1), 0] for i in range(len(video_sources))]
        workflow[str(node_id)] = {
            "class_type": "VideoCompositor",
            "inputs": {
                "sources": source_refs,
                "transition": transition,
            },
        }
        node_id += 1

        # Save output
        workflow[str(node_id)] = {
            "class_type": "SaveVideo",
            "inputs": {
                "images": [str(node_id - 1), 0],
                "filename_prefix": "novel_composite",
                "fps": 24,
            },
        }

        return workflow

    def build_video_with_audio(
        self,
        video_workflow: dict[str, Any],
        audio_path: str,
        audio_offset: float = 0.0,
        audio_volume: float = 1.0,
    ) -> dict[str, dict[str, Any]]:
        """Combine a video workflow with audio.

        Args:
            video_workflow: Existing video generation workflow
            audio_path: Path to audio file
            audio_offset: Audio start offset in seconds
            audio_volume: Audio volume (0-2)

        Returns:
            Combined workflow dict
        """
        workflow = dict(video_workflow)
        max_node = max(int(k) for k in workflow.keys() if k.isdigit())
        node_id = max_node + 1

        # Add audio
        workflow[str(node_id)] = {
            "class_type": "LoadAudio",
            "inputs": {
                "audio": audio_path,
            },
        }
        node_id += 1

        # Add muxer
        workflow[str(node_id)] = {
            "class_type": "VideoAudioMux",
            "inputs": {
                "video": [str(max_node), 0],
                "audio": [str(node_id - 1), 0],
                "offset": audio_offset,
                "volume": audio_volume,
            },
        }
        node_id += 1

        # Save final output
        workflow[str(node_id)] = {
            "class_type": "SaveVideo",
            "inputs": {
                "images": [str(node_id - 1), 0],
                "filename_prefix": "novel_final",
                "fps": 24,
            },
        }

        return workflow


class WorkflowBuilder:
    """Generic workflow builder with common patterns."""

    def __init__(self):
        self.image = ImageWorkflowBuilder()
        self.audio = AudioWorkflowBuilder()
        self.video = VideoWorkflowBuilder()

    @staticmethod
    def make_connection(
        source_node: str,
        source_output: int,
        target_node: str,
        target_input: str,
    ) -> list:
        """Create a node connection reference.

        Args:
            source_node: Source node ID
            source_output: Output index on source node
            target_node: Target node ID
            target_input: Input name on target node

        Returns:
            Connection tuple for use in workflow inputs
        """
        return [source_node, source_output]
