#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
"""Generate character reference images using MiniMax API.

Usage:
    python generate_character_images.py           # Generate all characters
    python generate_character_images.py --test   # Quick test with single prompt
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Add knowledge_base to path
KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

from media.minimax_executor import get_media_executor

# Character prompts (extracted from visual_reference/characters/)
# 采用摄影写实风格，参考ARRI Alexa拍摄效果，单段落格式
CHARACTER_PROMPTS = {
    "hanlin": {
        "name": "韩林",
        "prompt": "35mm film photography, high ISO, grain texture, authentic RAW photo, character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas, subject: a real 20-year-old East Asian male actor, 175cm height, lean athletic build, realistic human anatomy with natural muscle definition, pale skin with slight skin imperfections, natural T-zone oiliness, facial features: black hair in high ponytail with flyaway strands at temples, pale purple irises with realistic intricate iris textures (no glowing effect), cold determined gaze, clean forehead, slight facial imperfections, attire: heavy linen and textured silk period costume in black and purple, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks, views (from left to right): 1. strict front view standing straight for a screen test, 2. 3/4 front view facing right, 3. strict profile view facing right, 4. full back view showing the hair texture and robe's tailoring, technical details: shot on ARRI Alexa 50mm lens f/2.8 sharp focus on skin texture realistic subsurface scattering natural soft lighting from a high-angle studio lamp, background: pure seamless white paper backdrop absolute blank background zero digital artifacts totally clean background"
    },
    "liuruyan": {
        "name": "柳如烟",
        "prompt": "35mm film photography, high ISO, grain texture, authentic RAW photo, character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas, subject: a real 18-year-old East Asian female actor, 165cm height, slender lean figure, realistic human anatomy with natural muscle definition, fair skin with natural texture, slight imperfections on cheeks, natural skin texture variation, facial features: long flowing jet black hair with flyaway strands falling naturally down back, almond-shaped eyes with realistic intricate iris textures (no glowing effect), cool gaze aloof expression, forehead center: faint subtle golden pattern, slight facial imperfections, attire: heavy textured silk period costume in moon-white with silver thread cloud patterns, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks, views (from left to right): 1. strict front view standing straight for a screen test, 2. 3/4 front view facing right, 3. strict profile view facing right, 4. full back view showing the hair texture and robe's tailoring, technical details: shot on ARRI Alexa 50mm lens f/2.8 sharp focus on skin texture realistic subsurface scattering natural soft lighting from a high-angle studio lamp, background: pure seamless white paper backdrop absolute blank background zero digital artifacts totally clean background"
    },
    "yechen": {
        "name": "叶尘",
        "prompt": "35mm film photography, high ISO, grain texture, authentic RAW photo, character turnaround sheet for cinematic period film, four separate full body shots on a single white canvas, subject: a real 25-year-old East Asian male actor, 175cm height, slender lean figure with slightly effeminate build, realistic human anatomy with natural muscle definition, pale skin with visible pores, slight skin imperfections, facial features: green long hair with flyaway strands slightly messy, green irises with realistic intricate iris textures (no glowing effect), arrogant expression, slight facial imperfections, attire: heavy linen and textured silk period costume in green with gold embroidery, weathered fabric with micro-folds and realistic dust, visible stitching and weaving patterns, traditional leather martial arts boots with scuff marks, views (from left to right): 1. strict front view standing straight for a screen test, 2. 3/4 front view facing right, 3. strict profile view facing right, 4. full back view showing the hair texture and robe's tailoring, technical details: shot on ARRI Alexa 50mm lens f/2.8 sharp focus on skin texture realistic subsurface scattering natural soft lighting from a high-angle studio lamp, background: pure seamless white paper backdrop absolute blank background zero digital artifacts totally clean background"
    }
}

OUTPUT_DIR = Path(__file__).resolve().parent / "novels" / "太古魔帝传" / "generated_media" / "characters"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def generate_character_image(character_id: str, dry_run: bool = False) -> dict:
    """Generate a character reference image."""
    executor = get_media_executor()
    char_data = CHARACTER_PROMPTS[character_id]
    name = char_data["name"]
    prompt = char_data["prompt"]

    print(f"\n{'='*60}")
    print(f"Generating image for {name} ({character_id})")
    print(f"{'='*60}")
    print(f"Prompt preview: {prompt[:100]}...")

    if dry_run:
        print("[DRY RUN] Skipping actual generation")
        return {"success": True, "character_id": character_id, "name": name, "dry_run": True}

    result = await executor.generate_image(
        prompt=prompt,
        model="image-01",
        aspect_ratio="16:9",
        prompt_optimizer=False,  # Use exact prompt without optimization
        output_path=OUTPUT_DIR / character_id,  # Save image to local file
    )

    output = {
        "success": result["success"],
        "character_id": character_id,
        "name": name,
        "image_url": result.get("image_url"),
        "local_path": result.get("local_path"),
        "error": result.get("error"),
    }

    if result["success"] and result.get("local_path"):
        print(f"✓ Successfully generated {name}")
        print(f"  Image saved to: {result['local_path']}")

        # Save result to JSON
        result_file = OUTPUT_DIR / f"{character_id}_result.json"
        result_file.write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"  Result saved to: {result_file}")
    else:
        print(f"✗ Failed to generate {name}")
        print(f"  Error: {result.get('error')}")

    return output


async def generate_all_characters(dry_run: bool = False) -> list:
    """Generate images for all characters."""
    print(f"\nMiniMax Image Generation")
    print(f"{'='*60}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Characters: {list(CHARACTER_PROMPTS.keys())}")

    results = []
    for character_id in CHARACTER_PROMPTS:
        result = await generate_character_image(character_id, dry_run=dry_run)
        results.append(result)
        # Small delay between requests to avoid rate limits
        if not dry_run:
            await asyncio.sleep(2)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Generate character reference images")
    parser.add_argument("--dry-run", action="store_true", help="Test without calling API")
    parser.add_argument("--character", choices=list(CHARACTER_PROMPTS.keys()), help="Generate specific character")
    args = parser.parse_args()

    if args.character:
        result = await generate_character_image(args.character, dry_run=args.dry_run)
        print(f"\nResult: {json.dumps(result, ensure_ascii=False, indent=2)}")
    else:
        results = await generate_all_characters(dry_run=args.dry_run)
        print(f"\n{'='*60}")
        print("Generation Summary:")
        print(f"{'='*60}")
        for r in results:
            status = "✓" if r["success"] else "✗"
            print(f"  {status} {r['name']}: {'Success' if r['success'] else r.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())