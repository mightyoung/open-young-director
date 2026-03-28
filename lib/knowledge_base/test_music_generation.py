#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""Test music generation with proper hex decoding and lyrics support."""

import asyncio
from pathlib import Path
import sys

# Add knowledge_base to path
KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

from media.minimax_executor import get_media_executor

OUTPUT_DIR = KB_DIR / "novels" / "太古魔帝传" / "generated_media" / "music"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def test_music_with_lyrics():
    """Test music generation with vocals."""
    executor = get_media_executor()

    lyrics = """明月几时有，把酒问青天，
不知天上宫阙，今夕是何年，
我欲乘风归去，又恐琼楼玉宇，
高处不胜寒，起舞弄清影，何似在人间"""

    output_file = OUTPUT_DIR / "song_with_lyrics.mp3"

    print("="*60)
    print("Generating music with singing vocals...")
    print("="*60)
    print(f"Prompt: 古风中国音乐，优雅的女声演唱，笛子伴奏")
    print(f"Lyrics:\n{lyrics}")
    print("="*60)

    result = await executor.generate_music(
        prompt="古风中国音乐，优雅的女声演唱，笛子伴奏，月光意境",
        lyrics=lyrics,
        output_path=output_file,
    )

    print(f"\nResult:")
    print(f"  Success: {result['success']}")
    print(f"  Error: {result.get('error')}")
    print(f"  Local path: {result.get('local_path')}")
    print(f"  Music URL: {result.get('music_url')}")

    if result.get("local_path"):
        f = Path(result["local_path"])
        print(f"  File size: {f.stat().st_size / 1024:.1f} KB")

        # Verify file type
        import subprocess
        result_file = subprocess.run(["file", str(f)], capture_output=True, text=True)
        print(f"  File type: {result_file.stdout.strip()}")


if __name__ == "__main__":
    asyncio.run(test_music_with_lyrics())
