#!/usr/bin/env python3
"""
Example script demonstrating how to use the novel knowledge base
for AI-powered novel generation.

This script shows how to:
1. Load the knowledge base
2. Query relevant context based on genre/author/style
3. Format context for use by an LLM
"""

import json
from knowledge_base.novel_knowledge_base import NovelKnowledgeBase


def generate_novel_outline(
    kb: NovelKnowledgeBase,
    genre: str = None,
    author: str = None,
    theme: str = None,
    length: str = "medium"
) -> dict:
    """
    Generate a novel outline based on knowledge base examples.

    Args:
        kb: NovelKnowledgeBase instance
        genre: Preferred genre (optional)
        author: Preferred author style (optional)
        theme: Main theme to explore
        length: Expected length (short/medium/long)

    Returns:
        Dictionary with outline and context
    """
    # Determine chunk size based on length
    length_map = {"short": 3, "medium": 5, "long": 10}
    top_k = length_map.get(length, 5)

    # Retrieve relevant context
    context = kb.retrieve_for_generation(
        prompt=theme,
        genre=genre,
        author=author,
        top_k=top_k
    )

    # Analyze style patterns from context
    style_analysis = analyze_style(context)

    # Generate outline structure
    outline = {
        "theme": theme,
        "genre": genre or "综合",
        "style_reference": [ctx["source"] for ctx in context],
        "style_analysis": style_analysis,
        "context_samples": context[:3],  # First 3 as samples
        "word_count_estimate": top_k * 1500
    }

    return outline


def analyze_style(context: list[dict]) -> dict:
    """
    Analyze writing style from retrieved context.

    Args:
        context: List of context dictionaries

    Returns:
        Dictionary with style analysis
    """
    if not context:
        return {}

    # Collect statistics
    total_words = sum(ctx["metadata"]["word_count"] for ctx in context)
    avg_chunk_size = total_words / len(context) if context else 0

    # Analyze content patterns
    content_samples = [ctx["content"] for ctx in context]

    # Look for common patterns
    has_dialogue = any('"' in c or '"' in c for c in content_samples)
    has_narration = any('。' in c for c in content_samples)
    has_action = any(any(kw in c for kw in ['出手', '战斗', '攻击', '闪避']) for c in content_samples)

    return {
        "avg_chunk_size": avg_chunk_size,
        "has_dialogue": has_dialogue,
        "has_narration": has_narration,
        "has_action": has_action,
        "sample_count": len(context)
    }


def main():
    """Main entry point."""
    print("=" * 60)
    print("小说知识库生成示例")
    print("=" * 60)

    # Load knowledge base
    kb = NovelKnowledgeBase(output_dir="./knowledge_base")
    kb.load()

    # Get stats
    stats = kb.get_stats()
    print(f"\n知识库已加载: {stats['total_novels']}本小说, {stats['total_chunks']}个分块")
    print(f"题材类型: {', '.join(stats['genres'])}")
    print()

    # Example 1: Generate outline in 仙侠 genre
    print("示例1: 生成仙侠题材大纲")
    print("-" * 40)
    outline1 = generate_novel_outline(
        kb=kb,
        genre="仙侠",
        theme="凡人流修士的成长历程",
        length="medium"
    )
    print(f"主题: {outline1['theme']}")
    print(f"题材: {outline1['genre']}")
    print(f"参考作品: {[c['novel'] for c in outline1['style_reference']]}")
    print(f"风格分析: {outline1['style_analysis']}")
    print()

    # Example 2: Generate outline in 辰东 style
    print("示例2: 生成辰东风格大纲")
    print("-" * 40)
    outline2 = generate_novel_outline(
        kb=kb,
        author="辰东",
        theme="逆天伐天",
        length="long"
    )
    print(f"主题: {outline2['theme']}")
    print(f"参考作者: {outline2['style_reference'][0]['author'] if outline2['style_reference'] else 'N/A'}")
    print(f"参考作品: {[c['novel'] for c in outline2['style_reference']]}")
    print()

    # Example 3: Show context retrieval
    print("示例3: 检索相关情节上下文")
    print("-" * 40)
    contexts = kb.retrieve_for_generation(
        prompt="修炼 突破 战斗",
        genre="玄幻",
        top_k=2
    )
    for i, ctx in enumerate(contexts, 1):
        print(f"\n上下文 {i}:")
        print(f"  来源: [{ctx['source']['novel']}] 第{ctx['source']['chapter']}章")
        print(f"  内容: {ctx['content'][:150]}...")
    print()

    # Example 4: List all novels by genre
    print("示例4: 题材下的作品列表")
    print("-" * 40)
    for genre in stats["genres"]:
        novels = kb.get_novels_by_genre(genre)
        if novels:
            print(f"\n{genre}:")
            for n in novels[:5]:  # Show first 5
                print(f"  - {n.title} ({n.author}, {n.total_chapters}章)")


if __name__ == "__main__":
    main()
