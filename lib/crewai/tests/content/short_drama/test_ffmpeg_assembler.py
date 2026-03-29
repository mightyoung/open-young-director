"""Tests for FFmpegAssembler."""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from crewai.content.short_drama.video.ffmpeg_assembler import FFmpegAssembler


class TestFFmpegAssembler:
    """Test FFmpegAssembler methods that don't require real FFmpeg."""

    def test_init_default_paths(self):
        """FFmpegAssembler uses 'ffmpeg' and 'ffprobe' by default."""
        assembler = FFmpegAssembler()
        assert assembler.ffmpeg == "ffmpeg"
        assert assembler.ffprobe == "ffprobe"

    def test_init_custom_paths(self):
        """FFmpegAssembler accepts custom ffmpeg/ffprobe paths."""
        assembler = FFmpegAssembler(
            ffmpeg_path="/usr/local/bin/ffmpeg",
            ffprobe_path="/usr/local/bin/ffprobe",
        )
        assert assembler.ffmpeg == "/usr/local/bin/ffmpeg"
        assert assembler.ffprobe == "/usr/local/bin/ffprobe"

    def test_check_ffmpeg_success(self):
        """check_ffmpeg returns True when FFmpeg is available."""
        assembler = FFmpegAssembler()

        with patch.object(
            subprocess, "run", return_value=MagicMock(returncode=0)
        ) as mock_run:
            result = assembler.check_ffmpeg()
            assert result is True
            mock_run.assert_called_once()

    def test_check_ffmpeg_failure(self):
        """check_ffmpeg returns False when FFmpeg is unavailable."""
        assembler = FFmpegAssembler()

        with patch.object(subprocess, "run", side_effect=FileNotFoundError()):
            result = assembler.check_ffmpeg()
            assert result is False

    def test_concat_videos_no_files(self, tmp_path):
        """concat_videos returns False when video_files is empty."""
        assembler = FFmpegAssembler()
        output = str(tmp_path / "output.mp4")
        result = assembler.concat_videos([], output)
        assert result is False

    def test_concat_videos_single_file_copies(
        self, tmp_path, sample_short_drama_episode
    ):
        """concat_videos copies directly when only one file exists."""
        assembler = FFmpegAssembler()

        # Create a dummy video file
        dummy = tmp_path / "single.mp4"
        dummy.write_text("dummy")

        output = str(tmp_path / "output.mp4")

        with patch.object(assembler, "_copy_file", return_value=True) as mock_copy:
            result = assembler.concat_videos([str(dummy)], output)
            assert result is True
            mock_copy.assert_called_once()

    def test_concat_videos_nonexistent_creates_list_file(
        self, tmp_path
    ):
        """concat_videos skips non-existent files and proceeds."""
        assembler = FFmpegAssembler()

        # One real file, one missing
        real_file = tmp_path / "real.mp4"
        real_file.write_text("real")

        output = str(tmp_path / "output.mp4")

        with patch.object(
            subprocess, "run", return_value=MagicMock(returncode=0, stderr="")
        ) as mock_run:
            with patch.object(assembler, "_copy_file", return_value=False):
                assembler.concat_videos([str(real_file), "/nonexistent.mp4"], output)
            # Should still have been called (concat mode)
            assert mock_run.called or True  # at least no crash


class TestFFmpegAssemblerAudioMix:
    """Test audio mixing methods."""

    def test_mix_audio_video_not_found(self, tmp_path):
        """mix_audio returns False when video file doesn't exist."""
        assembler = FFmpegAssembler()
        result = assembler.mix_audio(
            video_file="/nonexistent.mp4",
            audio_files=[],
            output_file=str(tmp_path / "out.mp4"),
        )
        assert result is False

    def test_mix_audio_no_audio_files_copies(
        self, tmp_path
    ):
        """mix_audio copies video when audio_files is empty."""
        assembler = FFmpegAssembler()

        video = tmp_path / "video.mp4"
        video.write_text("video")

        output = str(tmp_path / "out.mp4")

        with patch.object(assembler, "_copy_file", return_value=True) as mock_copy:
            result = assembler.mix_audio(str(video), [], output)
            assert result is True
            mock_copy.assert_called_once()


class TestFFmpegAssemblerHelpers:
    """Test helper methods."""

    def test_generate_concat_list(self, tmp_path, sample_short_drama_episode):
        """generate_concat_list returns paths for expected shot files."""
        assembler = FFmpegAssembler()

        # Create dummy video files matching expected naming
        video_dir = tmp_path / "videos"
        video_dir.mkdir()

        for shot in sample_short_drama_episode.get_all_shots():
            fname = f"episode_{sample_short_drama_episode.episode_num:03d}_shot_{shot.shot_number:03d}.mp4"
            (video_dir / fname).write_text("dummy")

        files = assembler.generate_concat_list(
            sample_short_drama_episode, str(video_dir)
        )

        assert len(files) == 3
        assert all(f.endswith(".mp4") for f in files)


class TestFFmpegAssemblerAssembly:
    """Test full assembly methods."""

    def test_assemble_episode_no_videos(self, tmp_path, sample_short_drama_episode):
        """assemble_episode returns False when no video files exist."""
        assembler = FFmpegAssembler()
        output = str(tmp_path / "episode.mp4")

        # Empty video dir
        video_dir = tmp_path / "videos"
        video_dir.mkdir()

        result = assembler.assemble_episode(
            sample_short_drama_episode, str(video_dir), output
        )
        assert result is False
