"""Test script to generate Chapter 1 using FILM_DRAMA mode."""

import asyncio
import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent dir to path
sys.path.insert(0, '/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base')

from agents.film_drama import (
    DirectorAgent,
    DirectorConfig,
    InMemoryMessageQueue,
    CharacterMemoryQueue,
    MiddlewareChain,
    MemoryQueueMiddleware,
    EmotionalStateMiddleware,
    ClarificationMiddleware,
)
from llm.kimi_client import KimiClient


async def generate_chapter_1():
    """Generate Chapter 1 using FILM_DRAMA mode."""
    logger.info("=" * 60)
    logger.info("Starting FILM_DRAMA Chapter 1 Generation")
    logger.info("=" * 60)

    # Initialize LLM client
    llm_client = KimiClient(use_cli=True)

    # Check if LLM is available
    if not llm_client._cli_available and not llm_client.api_key:
        logger.error("No LLM client available! Using mock mode.")
        return None

    # Create middleware chain
    memory_queue = CharacterMemoryQueue()
    middleware_chain = MiddlewareChain()
    middleware_chain.add(MemoryQueueMiddleware(memory_queue))
    middleware_chain.add(EmotionalStateMiddleware())
    middleware_chain.add(ClarificationMiddleware())

    # Create DirectorAgent
    director_config = DirectorConfig(
        max_concurrent_character_agents=3,
        enable_npc_simulation=True,
    )

    director = DirectorAgent(
        agent_name="director",
        llm_client=llm_client,
        config=director_config,
        memory_queue=memory_queue,
        middleware_chain=middleware_chain,
    )

    # Define characters for Chapter 1
    characters = {
        "韩林": {
            "identity": "太虚宗弟子，韩长老遗孤",
            "realm": "凡人（测灵前）",
            "personality": "坚毅果敢、隐忍不发、沉稳内敛",
            "speaking_style": "简洁有力，不喜多言",
            "backstory": "父亲韩啸天为救宗门而死，母亲三年前病逝，孤身入宗修炼",
            "objective": "测灵大典上证明自己",
            "relationships": {
                "柳如烟": "有婚约，但柳家欲退婚",
                "赵元启": "外门长老，对韩林不屑",
                "韩啸天": "父亲，已故",
            },
        },
        "柳如烟": {
            "identity": "太虚宗第一美人，柳家千金",
            "realm": "炼气期（玄灵根）",
            "personality": "冷傲，但内心复杂",
            "speaking_style": "清冷犀利，言辞尖锐",
            "backstory": "玄灵根天才，内门长老弟子，柳家千金",
            "objective": "在测灵大典上退婚",
            "relationships": {
                "韩林": "有婚约，欲退婚",
                "叶尘": "追求者",
            },
        },
        "赵元启": {
            "identity": "太虚宗外门长老",
            "realm": "筑基期",
            "personality": "傲慢、势利",
            "speaking_style": "冷漠、不耐烦",
            "backstory": "外门长老，负责测灵大典",
            "objective": "维持秩序",
            "relationships": {
                "韩林": "轻视",
            },
        },
    }

    # Chapter 1 outline
    chapter_outline = """
    场景：太虚宗测灵大典，万人瞩目

    主要情节：
    1. 开场：介绍太虚宗和测灵大典的背景
    2. 发展：韩林登场，曾被寄予厚望的天才少年
    3. 冲突：测灵结果 - 伪灵根，满堂哗然
    4. 回忆：韩啸天被逐出宗门的往事
    5. 高潮：柳如烟登场，当众退婚，言语尖锐
    6. 解决：韩林的反应出人意料的平静
    7. 伏笔：韩林注意到柳如烟退婚时手指微微颤抖
    8. 过渡：众人嘲讽，韩林默默离开
    """

    logger.info(f"Planning scene for Chapter 1...")
    script = director.plan_scene(
        chapter_number=1,
        scene_outline=chapter_outline,
        characters=characters,
        location="太虚宗演武场",
        time_of_day="清晨",
        previous_context="无前文，这是第一章",
    )

    logger.info(f"Scene planned: {script.scene.scene_id}")
    logger.info(f"Cast: {[c.name for c in script.cast]}")
    logger.info(f"Beats: {len(script.scene.beats)}")

    for i, beat in enumerate(script.scene.beats):
        logger.info(f"  Beat {i+1}: {beat.beat_type} - {beat.description[:50]}...")

    # Execute scene
    logger.info("=" * 60)
    logger.info("Executing scene...")
    logger.info("=" * 60)

    result = await director.execute_scene(script)

    logger.info(f"Execution complete. Status: {result['status']}")
    logger.info(f"Beat outputs: {list(result.get('beat_outputs', {}).keys())}")

    # Check memory state
    scene_summary = result.get('scene_summary', {})
    logger.info(f"Global tension: {scene_summary.get('global_tension', 0):.2f}")

    # Assemble final output
    logger.info("=" * 60)
    logger.info("Assembling final output...")
    logger.info("=" * 60)

    output = director.assemble_scene_output(script)

    # Save output
    output_path = "/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/novels/太古魔帝传/chapters/ch001_test_film_drama.md"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# 第1章：废物少年（FILM_DRAMA模式测试）\n\n")
        f.write(f"> 第1章 | 生成时间: {datetime.now().isoformat()}\n\n")
        f.write(f"**本章概要**: 测灵大典，韩林被测为伪灵根，柳如烟当众退婚\n\n")
        f.write("---\n\n")
        f.write(output)
        f.write("\n\n*（本章完）*\n")

    logger.info(f"Output saved to: {output_path}")

    # Print first 2000 chars for preview
    logger.info("=" * 60)
    logger.info("PREVIEW (first 2000 chars):")
    logger.info("=" * 60)
    print(output[:2000])
    print("...")

    return output


if __name__ == "__main__":
    result = asyncio.run(generate_chapter_1())
    if result:
        print("\n" + "=" * 60)
        print("FILM_DRAMA Chapter 1 Generation COMPLETE!")
        print("=" * 60)
    else:
        print("Generation failed - check logs")
