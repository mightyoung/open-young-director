"""FFmpegAssembler - FFmpeg 视频合成封装

负责将视频片段和音频合成为最终的短剧视频。
支持：
- 视频片段拼接
- 音频混音
- 添加字幕
- 输出多种格式（MP4、WebM）
"""

import subprocess
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from crewai.content.short_drama.short_drama_types import ShortDramaEpisode, Shot

logger = logging.getLogger(__name__)


class FFmpegAssembler:
    """FFmpeg 视频合成器

    封装常用的 FFmpeg 操作，用于：
    1. 拼接视频片段
    2. 混合音频（配音 + 背景音乐）
    3. 添加字幕
    4. 格式转换
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """初始化合成器

        Args:
            ffmpeg_path: ffmpeg 命令路径
            ffprobe_path: ffprobe 命令路径
        """
        self.ffmpeg = ffmpeg_path
        self.ffprobe = ffprobe_path

    def check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否可用

        Returns:
            bool: FFmpeg 是否可用
        """
        try:
            result = subprocess.run(
                [self.ffmpeg, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def concat_videos(
        self,
        video_files: List[str],
        output_file: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        preset: str = "medium",
    ) -> bool:
        """拼接视频片段

        Args:
            video_files: 视频文件路径列表
            output_file: 输出文件路径
            video_codec: 视频编码器
            audio_codec: 音频编码器
            preset: 编码预设

        Returns:
            bool: 是否成功
        """
        if not video_files:
            logger.error("No video files to concatenate")
            return False

        # 过滤不存在的文件
        existing_files = [f for f in video_files if os.path.exists(f)]
        if not existing_files:
            logger.error("No existing video files found")
            return False

        # 如果只有一个文件，直接复制
        if len(existing_files) == 1:
            return self._copy_file(existing_files[0], output_file)

        # 创建临时文件列表
        list_file = output_file + ".concat_list.txt"
        try:
            with open(list_file, "w") as f:
                for video_file in existing_files:
                    f.write(f"file '{video_file}'\n")

            # 执行拼接
            cmd = [
                self.ffmpeg,
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", video_codec,
                "-c:a", audio_codec,
                "-preset", preset,
                "-y",
                output_file,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg concat failed: {result.stderr}")
                return False

            return True

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg concat timed out")
            return False
        except Exception as e:
            logger.error(f"FFmpeg concat error: {e}")
            return False
        finally:
            # 清理临时文件
            if os.path.exists(list_file):
                os.remove(list_file)

    def mix_audio(
        self,
        video_file: str,
        audio_files: List[Dict[str, str]],
        # audio_files: [{"file": "path/to/audio", "volume": 0.8, "start": 0}, ...]
        output_file: str,
    ) -> bool:
        """混合音频到视频

        Args:
            video_file: 视频文件
            audio_files: 音频文件列表（含音量和起始时间）
            output_file: 输出文件

        Returns:
            bool: 是否成功
        """
        if not os.path.exists(video_file):
            logger.error(f"Video file not found: {video_file}")
            return False

        try:
            # 构建 filter_complex
            filter_parts = []
            inputs = ["-i", video_file]
            audio_count = 0

            for audio_info in audio_files:
                audio_file = audio_info["file"]
                if not os.path.exists(audio_file):
                    logger.warning(f"Audio file not found: {audio_file}")
                    continue

                inputs.extend(["-i", audio_file])
                volume = audio_info.get("volume", 1.0)
                start = audio_info.get("start", 0)

                if start > 0:
                    # 带延迟的音频
                    filter_parts.append(
                        f"[{audio_count + 1}:a]adelay={int(start * 1000)}|{int(start * 1000)},volume={volume}[a{audio_count}]"
                    )
                else:
                    filter_parts.append(
                        f"[{audio_count + 1}:a]volume={volume}[a{audio_count}]"
                    )
                audio_count += 1

            if audio_count == 0:
                # 没有音频文件，直接复制
                return self._copy_file(video_file, output_file)

            # 构建混合 filter
            mix_inputs = "".join(f"[a{i}]" for i in range(audio_count))
            filter_parts.append(f"{mix_inputs}amix=inputs={audio_count}:normalize=0[mixed]")
            filter_complex = ";".join(filter_parts) + f";[0:a][mixed]amix=inputs=2:normalize=0[mixed]"

            cmd = [
                self.ffmpeg,
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "0:v",
                "-map", "[mixed]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-y",
                output_file,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg mix_audio failed: {result.stderr}")
                return False

            return True

        except Exception as e:
            logger.error(f"FFmpeg mix_audio error: {e}")
            return False

    def add_subtitles(
        self,
        video_file: str,
        subtitle_file: str,
        output_file: str,
        style: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """添加字幕

        Args:
            video_file: 视频文件
            subtitle_file: 字幕文件（SRT/ASS）
            output_file: 输出文件
            style: 字幕样式

        Returns:
            bool: 是否成功
        """
        if not os.path.exists(video_file):
            logger.error(f"Video file not found: {video_file}")
            return False

        if not os.path.exists(subtitle_file):
            logger.error(f"Subtitle file not found: {subtitle_file}")
            return False

        try:
            cmd = [
                self.ffmpeg,
                "-i", video_file,
                "-vf", f"subtitles='{subtitle_file}'",
                "-c:a", "copy",
                "-y",
                output_file,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg subtitles failed: {result.stderr}")
                return False

            return True

        except Exception as e:
            logger.error(f"FFmpeg subtitles error: {e}")
            return False

    def convert_format(
        self,
        input_file: str,
        output_file: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        crf: int = 23,
        preset: str = "medium",
    ) -> bool:
        """转换视频格式

        Args:
            input_file: 输入文件
            output_file: 输出文件
            video_codec: 视频编码器
            audio_codec: 音频编码器
            crf: 质量参数（越小质量越高）
            preset: 编码预设

        Returns:
            bool: 是否成功
        """
        if not os.path.exists(input_file):
            logger.error(f"Input file not found: {input_file}")
            return False

        try:
            cmd = [
                self.ffmpeg,
                "-i", input_file,
                "-c:v", video_codec,
                "-c:a", audio_codec,
                "-crf", str(crf),
                "-preset", preset,
                "-y",
                output_file,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                logger.error(f"FFmpeg convert failed: {result.stderr}")
                return False

            return True

        except Exception as e:
            logger.error(f"FFmpeg convert error: {e}")
            return False

    def get_duration(self, video_file: str) -> Optional[float]:
        """获取视频时长

        Args:
            video_file: 视频文件

        Returns:
            float: 时长（秒）或 None
        """
        if not os.path.exists(video_file):
            return None

        try:
            cmd = [
                self.ffprobe,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_file,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return float(result.stdout.strip())

        except Exception:
            pass

        return None

    def generate_concat_list(
        self,
        episode: ShortDramaEpisode,
        video_dir: str,
    ) -> List[str]:
        """生成拼接用的视频文件列表

        Args:
            episode: ShortDramaEpisode
            video_dir: 视频文件目录

        Returns:
            list[str]: 视频文件路径列表
        """
        video_files = []

        for scene in episode.scenes:
            for shot in scene.shots:
                # 假设视频文件名格式：episode_{集号}_shot_{镜头号}.mp4
                video_name = f"episode_{episode.episode_num:03d}_shot_{shot.shot_number:03d}.mp4"
                video_path = os.path.join(video_dir, video_name)

                if os.path.exists(video_path):
                    video_files.append(video_path)
                else:
                    logger.warning(f"Video not found: {video_path}")

        return video_files

    def assemble_episode(
        self,
        episode: ShortDramaEpisode,
        video_dir: str,
        output_file: str,
        audio_files: Optional[List[Dict[str, str]]] = None,
    ) -> bool:
        """合成完整剧集

        Args:
            episode: ShortDramaEpisode
            video_dir: 视频文件目录
            output_file: 输出文件
            audio_files: 音频文件列表

        Returns:
            bool: 是否成功
        """
        # 1. 获取视频文件列表
        video_files = self.generate_concat_list(episode, video_dir)

        if not video_files:
            logger.error("No video files found for assembly")
            return False

        # 2. 拼接视频
        temp_video = output_file + ".temp.mp4"
        if not self.concat_videos(video_files, temp_video):
            return False

        # 3. 混合音频（如果有）
        if audio_files:
            if not self.mix_audio(temp_video, audio_files, output_file):
                # 音频混合失败，但视频拼接成功
                logger.warning("Audio mixing failed, using video only")
                return self._copy_file(temp_video, output_file)
        else:
            # 没有音频，直接使用拼接视频
            return self._copy_file(temp_video, output_file)

        # 清理临时文件
        if os.path.exists(temp_video):
            os.remove(temp_video)

        return True

    def _copy_file(self, src: str, dst: str) -> bool:
        """复制文件"""
        import shutil
        try:
            shutil.copy2(src, dst)
            return True
        except Exception as e:
            logger.error(f"Failed to copy file: {e}")
            return False


__all__ = ["FFmpegAssembler"]
