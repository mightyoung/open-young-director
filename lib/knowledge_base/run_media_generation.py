#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""端到端媒体生成测试 - 使用已有 video_prompts 和 podcasts 调用 MiniMax 生成实际媒体资产。

用法:
    python run_media_generation.py              # 生成第1章视频+音频
    python run_media_generation.py --chapter 3  # 生成第3章
    python run_media_generation.py --all        # 生成所有章节
    python run_media_generation.py --audio-only # 仅生成音频
    python run_media_generation.py --video-only # 仅生成视频
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Load .env if present (search script dir, then project root) ───────────────
for _env_path in [
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",  # project root
]:
    if _env_path.exists():
        for line in _env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

# ── Setup paths ──────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
KB_DIR = SCRIPT_DIR

# Add knowledge_base root to path so imports work
sys.path.insert(0, str(KB_DIR))

# ── Logging setup (must be before _resolve_novel_dir) ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("media_gen")

# ── Resolve project-based directory ────────────────────────────────────────────
def _resolve_novel_dir() -> Path:
    """Resolve the correct novel directory from project config.

    Returns the directory containing chapters.
    Chapters are in {NOVEL_DIR}/chapters/
    Scripts (video_prompts, podcasts) are in {SCRIPTS_DIR}/
    """
    try:
        from agents.config_manager import get_config_manager

        config_mgr = get_config_manager()
        if config_mgr.current_project:
            project_title = config_mgr.current_project.title

            # Chapters are stored in novels/{project_title}/chapters/
            novel_dir = Path("lib/knowledge_base/novels") / project_title.replace("/", "-")

            logger.info(f"Using project: {project_title}")
            logger.info(f"NOVEL_DIR resolved to: {novel_dir}")
            return novel_dir
    except Exception as e:
        logger.warning(f"Could not load project config: {e}")

    # Fallback to hardcoded path
    logger.warning("Falling back to default NOVEL_DIR")
    return KB_DIR / "novels" / "太古魔帝传"


def _resolve_scripts_dir() -> Path:
    """Resolve the scripts directory (video_prompts, podcasts).

    Scripts are stored separately from novel chapters.
    """
    try:
        from agents.config_manager import get_config_manager

        config_mgr = get_config_manager()
        if config_mgr.current_project:
            project_title = config_mgr.current_project.title

            # Scripts are stored in generated_scripts/{project_title}/
            scripts_dir = Path("lib/knowledge_base/generated_scripts") / project_title.replace("/", "-")

            logger.info(f"SCRIPTS_DIR resolved to: {scripts_dir}")
            return scripts_dir
    except Exception as e:
        logger.warning(f"Could not load project config: {e}")

    # Fallback to hardcoded path
    logger.warning("Falling back to default SCRIPTS_DIR")
    return KB_DIR / "generated_scripts" / "太古魔帝传"


NOVEL_DIR = _resolve_novel_dir()
SCRIPTS_DIR = _resolve_scripts_dir()

# ── Import MiniMax executor ───────────────────────────────────────────────────
from media.minimax_executor import get_media_executor, MiniMaxMediaExecutor

# ── Import Doubao client for video prompt generation ───────────────────────────
from llm.doubao_client import get_doubao_client

# ── Import Kimi client for enhanced prompt generation ────────────────────────
try:
    from llm.kimi_client import get_kimi_client, KimiClient
    _kimi_client: Optional[KimiClient] = None
except ImportError:
    _kimi_client = None
    logger.warning("KimiClient not available, using template prompts")


def _get_kimi_client() -> Optional[KimiClient]:
    """Get or create KimiClient instance."""
    global _kimi_client
    if _kimi_client is None:
        try:
            _kimi_client = get_kimi_client()
            logger.info("KimiClient initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize KimiClient: {e}")
    return _kimi_client


# ── LLM-enhanced prompt generation ─────────────────────────────────────────────

def _enhance_prompt_with_llm(scene_description: str, characters: List[str], mood: str) -> str:
    """Generate enhanced video prompt using Kimi LLM.

    Args:
        scene_description: Raw scene text from chapter
        characters: List of character names
        mood: Detected mood

    Returns:
        Enhanced English prompt for video generation
    """
    kimi = _get_kimi_client()
    if not kimi:
        return None  # Will use fallback template

    char_str = "、".join(characters[:3]) if characters else "主角"

    prompt = f"""为以下仙侠小说场景生成一个详细的英文视频生成提示词。

场景描述：
{scene_description[:500]}

出场人物：{char_str}
氛围：{mood}

请生成一个英文视频生成提示词，包含：
1. 具体场景画面描述（摄像机运动、光影效果）
2. 人物外貌特征
3. 色调和氛围
4. 镜头运动方式

只输出英文提示词，不要其他内容。"""

    try:
        messages = [{"role": "user", "content": prompt}]
        result = kimi.generate(messages)
        if result and len(result) > 30:
            return result
    except Exception as e:
        logger.warning(f"LLM prompt enhancement failed: {e}")

    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_video_prompt(chapter: int, scene_index: int = 1) -> Optional[Dict[str, Any]]:
    """Load a video prompt JSON file."""
    path = SCRIPTS_DIR / "video_prompts" / f"ch{chapter:03d}_video_prompt_{scene_index}.json"
    if not path.exists():
        logger.warning(f"Video prompt not found: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_podcast(chapter: int) -> Optional[Dict[str, Any]]:
    """Load a podcast JSON file."""
    path = SCRIPTS_DIR / "podcasts" / f"ch{chapter:03d}_podcast.json"
    if not path.exists():
        logger.warning(f"Podcast not found: {path}")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_output_dir() -> Path:
    """Create output directory for generated media."""
    out = NOVEL_DIR / "generated_media"
    out.mkdir(exist_ok=True)
    return out


# ── Video Generation ─────────────────────────────────────────────────────────

async def generate_video_for_chapter(
    executor: MiniMaxMediaExecutor,
    chapter: int,
    scene_index: int = 1,
    output_dir: Optional[Path] = None,
    duration: int = 60,
) -> Dict[str, Any]:
    """Generate a video prompt for one chapter scene using Doubao Seed 2.0.

    This function generates Seedance 2.0 formatted prompts WITHOUT calling
    the actual video generation API. The prompt is saved to a JSON file.

    Args:
        executor: MiniMax media executor (unused, kept for API compatibility)
        chapter: Chapter number
        scene_index: Which scene (1-3) to use
        output_dir: Directory to save results
        duration: Video duration in seconds (default 60)

    Returns:
        dict with generation result and any saved file paths
    """
    prompt_data = load_video_prompt(chapter, scene_index)
    if not prompt_data:
        return {"success": False, "error": "No video prompt found"}

    # Extract scene info from JSON
    scene_desc = prompt_data.get("scene_description", "")
    characters = prompt_data.get("characters", [])
    mood = prompt_data.get("mood", "dramatic")
    location = prompt_data.get("location", None)

    # Generate Seedance 2.0 prompt using Doubao
    logger.info(f"[Ch{chapter:02d}-S{scene_index}] Generating {duration}s Seedance 2.0 prompt via Doubao...")

    try:
        doubao = get_doubao_client()
        video_prompt = doubao.generate_video_prompt(
            scene_description=scene_desc,
            characters=characters,
            location=location,
            mood=mood,
            duration=duration,
        )
    except Exception as e:
        logger.error(f"[Ch{chapter:02d}-S{scene_index}] Doubao prompt generation failed: {e}")
        return {
            "chapter": chapter,
            "scene_index": scene_index,
            "success": False,
            "error": str(e),
        }

    if not video_prompt or len(video_prompt) < 50:
        logger.error(f"[Ch{chapter:02d}-S{scene_index}] Generated prompt too short")
        return {
            "chapter": chapter,
            "scene_index": scene_index,
            "success": False,
            "error": "Generated prompt too short",
        }

    logger.info(f"[Ch{chapter:02d}-S{scene_index}] Prompt generated ({len(video_prompt)} chars)")

    # Save prompt to file
    out_dir = output_dir or ensure_output_dir()
    saved_path = None
    try:
        meta_path = out_dir / f"ch{chapter:03d}_scene{scene_index}_seedance_prompt.txt"
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(video_prompt)
        saved_path = str(meta_path)
        logger.info(f"[Ch{chapter:02d}-S{scene_index}] Prompt saved to: {meta_path}")

        # Also save structured JSON metadata
        json_meta_path = out_dir / f"ch{chapter:03d}_scene{scene_index}_prompt_meta.json"
        with open(json_meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "chapter": chapter,
                "scene_index": scene_index,
                "duration": duration,
                "scene_description": scene_desc[:200],
                "characters": characters,
                "mood": mood,
                "location": location,
                "prompt_length": len(video_prompt),
                "model": "Seedance 2.0",
                "prompt_file": str(meta_path),
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"[Ch{chapter:02d}-S{scene_index}] Metadata saved to: {json_meta_path}")

    except Exception as e:
        logger.error(f"[Ch{chapter:02d}-S{scene_index}] Failed to save prompt: {e}")

    return {
        "chapter": chapter,
        "scene_index": scene_index,
        "success": True,
        "duration": duration,
        "prompt_length": len(video_prompt),
        "prompt_preview": video_prompt[:200],
        "prompt_file": saved_path,
    }


# ── Audio Generation ─────────────────────────────────────────────────────────

async def generate_audio_for_chapter(
    executor: MiniMaxMediaExecutor,
    chapter: int,
    output_dir: Optional[Path] = None,
    voice_id: str = "female-shaonv",
) -> Dict[str, Any]:
    """Generate audio narration for one chapter using MiniMax TTS.

    Args:
        executor: MiniMax media executor
        chapter: Chapter number
        output_dir: Directory to save results
        voice_id: MiniMax voice ID

    Returns:
        dict with generation result
    """
    podcast_data = load_podcast(chapter)
    if not podcast_data:
        return {"success": False, "error": "No podcast script found"}

    content = podcast_data.get("content", "")
    if not content:
        return {"success": False, "error": "Podcast content is empty"}

    # Truncate to 500 chars for TTS API limit
    text = content[:500]

    # Detect emotion from content
    emotion = "neutral"
    if any(w in text for w in ["战", "愤怒", "激烈"]):
        emotion = "angry"
    elif any(w in text for w in ["悲伤", "痛苦", "泪"]):
        emotion = "sad"
    elif any(w in text for w in ["高潮", "兴奋", "喜悦"]):
        emotion = "happy"

    logger.info(f"[Ch{chapter:02d}] Generating audio (emotion={emotion}, {len(text)} chars)...")

    # Use speech-02-hd (your quota has Text to Speech HD)
    # Note: this model does NOT support emotion parameter
    result = await executor.generate_speech(
        text=text,
        voice_id=voice_id,
        model="speech-02-hd",
        speed=1.0,
    )

    out_dir = output_dir or ensure_output_dir()
    saved_path = None
    if result.get("success") and result.get("audio_url"):
        audio_url = result["audio_url"]
        logger.info(f"[Ch{chapter:02d}] Audio generated: {audio_url}")
        meta_path = out_dir / f"ch{chapter:03d}_audio_result.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({**result, "text_used": text, "voice_id": voice_id, "emotion": emotion}, f, ensure_ascii=False, indent=2)
        saved_path = str(meta_path)
    else:
        error = result.get("error", "Unknown error")
        logger.error(f"[Ch{chapter:02d}] Audio generation failed: {error}")

    return {
        "chapter": chapter,
        "success": result.get("success", False),
        "audio_url": result.get("audio_url"),
        "error": result.get("error"),
        "result_file": saved_path,
    }


# ── Batch Operations ──────────────────────────────────────────────────────────

async def generate_for_chapter(
    executor: MiniMaxMediaExecutor,
    chapter: int,
    output_dir: Optional[Path] = None,
    audio_only: bool = False,
    video_only: bool = False,
    skip_audio: bool = False,
) -> Dict[str, Any]:
    """Generate both video and audio for a single chapter.

    Args:
        executor: MiniMax media executor
        chapter: Chapter number
        output_dir: Output directory
        audio_only: Skip video generation
        video_only: Skip audio generation
        skip_audio: Skip audio generation (for accounts without TTS quota)

    Returns:
        dict with all generation results
    """
    results = {"chapter": chapter}

    if not audio_only:
        # Generate video from scene 1
        video_result = await generate_video_for_chapter(executor, chapter, scene_index=1, output_dir=output_dir)
        results["video"] = video_result

    if not video_only and not skip_audio:
        # Generate audio narration
        audio_result = await generate_audio_for_chapter(executor, chapter, output_dir=output_dir)
        results["audio"] = audio_result

    return results


async def generate_all(
    executor: MiniMaxMediaExecutor,
    output_dir: Optional[Path] = None,
    audio_only: bool = False,
    video_only: bool = False,
    skip_audio: bool = False,
    chapters: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """Generate media for all (or specified) chapters.

    Args:
        executor: MiniMax media executor
        output_dir: Output directory
        audio_only: Skip video generation
        video_only: Skip audio generation
        skip_audio: Skip audio generation (for accounts without TTS quota)
        chapters: Specific chapter numbers to process (default: 1-6)

    Returns:
        List of per-chapter results
    """
    if chapters is None:
        chapters = list(range(1, 7))  # ch001-ch006

    logger.info(f"Starting batch generation for chapters: {chapters}")
    logger.info(f"Mode: audio_only={audio_only}, video_only={video_only}, skip_audio={skip_audio}")

    tasks = [
        generate_for_chapter(executor, ch, output_dir, audio_only, video_only, skip_audio)
        for ch in chapters
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Chapter {chapters[i]} raised exception: {result}")
            processed.append({"chapter": chapters[i], "error": str(result)})
        else:
            processed.append(result)

    return processed


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate media assets via MiniMax API")
    parser.add_argument("--chapter", type=int, default=1, help="Chapter number (1-6)")
    parser.add_argument("--all", action="store_true", help="Generate for all chapters (1-6)")
    parser.add_argument("--chapters", type=str, default="1-6", help="Chapter range, e.g. '1-3' or '1,3,5'")
    parser.add_argument("--audio-only", action="store_true", help="Only generate audio")
    parser.add_argument("--video-only", action="store_true", help="Only generate video")
    parser.add_argument("--skip-audio", action="store_true", help="Skip audio generation (for accounts without TTS quota)")
    parser.add_argument("--scene", type=int, default=1, help="Scene index for video (1-3)")
    parser.add_argument("--voice", type=str, default="female-shaonv", help="MiniMax voice ID")
    parser.add_argument("--output-dir", type=str, help="Custom output directory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated without calling API")

    args = parser.parse_args()

    # Resolve output directory
    output_dir = Path(args.output_dir) if args.output_dir else ensure_output_dir()

    # Resolve chapters to process
    if args.all:
        chapters = list(range(1, 7))
    elif args.chapters != "1-6":
        # Parse range string
        chapters_set = set()
        for part in args.chapters.split(","):
            part = part.strip()
            if "-" in part:
                m = __import__("re").match(r"(\d+)-(\d+)", part)
                if m:
                    chapters_set.update(range(int(m.group(1)), int(m.group(2)) + 1))
            else:
                m = __import__("re").match(r"\d+", part)
                if m:
                    chapters_set.add(int(m.group(0)))
        chapters = sorted(chapters_set) if chapters_set else [args.chapter]
    else:
        chapters = [args.chapter]

    if args.dry_run:
        logger.info("[DRY RUN] Would generate:")
        for ch in chapters:
            if not args.audio_only:
                vp = load_video_prompt(ch, args.scene)
                logger.info(f"  Ch{ch:02d} video: {vp.get('prompt_text', '')[:80] if vp else 'NOT FOUND'}...")
            if not args.video_only and not args.skip_audio:
                pc = load_podcast(ch)
                logger.info(f"  Ch{ch:02d} audio: {pc['content'][:80] if pc else 'NOT FOUND'}...")
        return

    # Check API key
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        logger.error("MINIMAX_API_KEY environment variable is not set!")
        logger.error("Please set it: export MINIMAX_API_KEY=your_key")
        sys.exit(1)

    logger.info(f"MINIMAX_API_KEY found: {'*' * 8}{api_key[:4]}...")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Chapters to process: {chapters}")

    # Get executor
    executor = get_media_executor()

    # Run
    if len(chapters) == 1:
        # Single chapter
        result = asyncio.run(generate_for_chapter(
            executor, chapters[0], output_dir, args.audio_only, args.video_only, args.skip_audio
        ))
        results = [result]
    else:
        # Batch
        results = asyncio.run(generate_all(
            executor, output_dir, args.audio_only, args.video_only, args.skip_audio, chapters
        ))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("GENERATION SUMMARY")
    logger.info("=" * 60)

    video_ok = 0
    audio_ok = 0

    for r in results:
        ch = r.get("chapter", "?")
        v = r.get("video", {})
        a = r.get("audio", {})

        v_ok = v.get("success", False) if v else None
        a_ok = a.get("success", False) if a else None

        if v_ok:
            video_ok += 1
        if a_ok:
            audio_ok += 1

        status = []
        if v_ok:
            status.append(f"video=OK ({v.get('video_url', '')[:60]})")
        elif v and not v_ok:
            status.append(f"video=FAIL ({v.get('error', '?')})")
        if a_ok:
            status.append(f"audio=OK ({a.get('audio_url', '')[:60]})")
        elif a and not a_ok:
            status.append(f"audio=FAIL ({a.get('error', '?')})")

        logger.info(f"  Chapter {ch}: {' | '.join(status) if status else 'NO RESULTS'}")

    logger.info("-" * 60)
    logger.info(f"Video success: {video_ok}/{len(chapters)}")
    logger.info(f"Audio success: {audio_ok}/{len(chapters)}")
    logger.info(f"Results saved to: {output_dir}")

    # Save batch summary
    summary_path = output_dir / "generation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "chapters": chapters,
            "video_success": video_ok,
            "audio_success": audio_ok,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"Summary saved to: {summary_path}")


if __name__ == "__main__":
    main()
