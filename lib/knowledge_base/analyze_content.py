#!/usr/bin/env python3
"""使用KIMI模型分析小说内容质量"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from llm.kimi_client import KIMIClient

# 初始化KIMI客户端
client = KIMIClient()

def analyze_chapters():
    """分析小说章节"""
    print("\n" + "="*60)
    print("📚 小说章节分析")
    print("="*60)

    chapters_dir = Path("lib/knowledge_base/novels/太古魔帝传/chapters")
    chapter_files = sorted(chapters_dir.glob("*.md"))[:3]  # 分析前3章

    analysis_prompt = """你是一位资深的网络小说编辑，请分析以下小说章节内容，评估以下五个维度：

1. **剧情连贯性**：情节发展是否自然流畅，前后逻辑是否通顺
2. **人物塑造**：角色性格是否鲜明，行为是否与背景一致
3. **节奏把控**：是否做到张弛有度，高潮与铺垫是否合理
4. **世界观一致性**：修仙设定是否前后一致，没有矛盾
5. **逻辑漏洞**：是否存在明显的不合理或自相矛盾之处

请用专业眼光指出具体的不足之处和具体段落，每条问题请引用原文说明。"""

    for chapter_file in chapter_files:
        print(f"\n--- 分析: {chapter_file.name} ---")
        content = chapter_file.read_text(encoding='utf-8')

        # 截取前2000字进行分析
        if len(content) > 2000:
            content = content[:2000]

        messages = [
            {"role": "user", "content": f"{analysis_prompt}\n\n以下是小说章节内容：\n\n{content}"}
        ]

        try:
            response = client.chat(messages)
            print(f"\n{response.content}")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

def analyze_podcasts():
    """分析播客剧本"""
    print("\n" + "="*60)
    print("🎙️ 播客剧本分析")
    print("="*60)

    podcasts_dir = Path("lib/knowledge_base/novels/太古魔帝传/podcasts")
    podcast_files = sorted(podcasts_dir.glob("*.md"))[:2]  # 分析前2个

    analysis_prompt = """你是一位专业的有声书制作人，请分析以下播客剧本，评估以下五个维度：

1. **旁白对话比例**：旁白与对话的比例是否合适（建议3:7到4:6之间）
2. **音效设计**：是否标注了合适的背景音乐和音效
3. **情感张力**：情感表达是否饱满，能否吸引听众
4. **时长把控**：节奏是否紧凑，不冗长
5. **角色声音特点**：不同角色是否有明显的声音区分设计

请用专业眼光指出具体的不足之处和改进建议。"""

    for podcast_file in podcast_files:
        print(f"\n--- 分析: {podcast_file.name} ---")
        content = podcast_file.read_text(encoding='utf-8')

        # 截取前2000字进行分析
        if len(content) > 2000:
            content = content[:2000]

        messages = [
            {"role": "user", "content": f"{analysis_prompt}\n\n以下是播客剧本内容：\n\n{content}"}
        ]

        try:
            response = client.chat(messages)
            print(f"\n{response.content}")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

def analyze_characters():
    """分析人物描述"""
    print("\n" + "="*60)
    print("👤 人物描述分析")
    print("="*60)

    characters_dir = Path("lib/knowledge_base/novels/太古魔帝传/visual_reference/characters")
    character_files = sorted(characters_dir.glob("*.md"))[:3]  # 分析前3个

    analysis_prompt = """你是一位AI绘画提示词专家和小说人物设计师，请分析以下人物描述，评估以下三个维度：

1. **外貌一致性**：与小说原著中的人物形象是否一致，没有矛盾
2. **性格行为匹配**：外貌和气质是否与人物性格设定相匹配
3. **AI绘图提示词精准度**：描述是否足够精准，能够生成符合要求的AI图片

请用专业眼光指出具体的不足之处和改进建议。对于AI绘图部分，请指出哪些描述可能导致生成图片与预期不符。"""

    for character_file in character_files:
        print(f"\n--- 分析: {character_file.name} ---")
        content = character_file.read_text(encoding='utf-8')

        # 截取前2000字进行分析
        if len(content) > 2000:
            content = content[:2000]

        messages = [
            {"role": "user", "content": f"{analysis_prompt}\n\n以下是人人物描述内容：\n\n{content}"}
        ]

        try:
            response = client.chat(messages)
            print(f"\n{response.content}")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

def analyze_scenes():
    """分析场景描述"""
    print("\n" + "="*60)
    print("🎬 场景描述分析")
    print("="*60)

    scenes_dir = Path("lib/knowledge_base/novels/太古魔帝传/visual_reference/scenes")
    scene_files = sorted(scenes_dir.glob("*.md"))[:3]  # 分析前3个

    analysis_prompt = """你是一位AI绘画场景设计专家和影视美术设计师，请分析以下场景描述，评估以下三个维度：

1. **时代背景一致性**：场景风格是否符合玄幻修仙题材的设定
2. **光线氛围**：光线、色彩、氛围描述是否协调统一
3. **AI绘图可执行性**：描述是否足够具体，AI能否根据描述生成一致的场景

请用专业眼光指出具体的不足之处和改进建议。对于AI绘图部分，请指出哪些描述可能导致生成图片效果不理想。"""

    for scene_file in scene_files:
        print(f"\n--- 分析: {scene_file.name} ---")
        content = scene_file.read_text(encoding='utf-8')

        # 截取前2000字进行分析
        if len(content) > 2000:
            content = content[:2000]

        messages = [
            {"role": "user", "content": f"{analysis_prompt}\n\n以下是场景描述内容：\n\n{content}"}
        ]

        try:
            response = client.chat(messages)
            print(f"\n{response.content}")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

def analyze_video_prompts():
    """分析视频提示词"""
    print("\n" + "="*60)
    print("🎥 视频提示词分析")
    print("="*60)

    video_prompts_dir = Path("lib/knowledge_base/novels/太古魔帝传/video_prompts")
    video_prompt_files = sorted(video_prompts_dir.glob("*.md"))[:2]  # 分析前2个

    analysis_prompt = """你是一位专业的视频制作人和AI视频生成专家，请分析以下视频提示词，评估以下五个维度（参考五维权重体系）：

1. **主体 (Subject) - 权重30%**：主体描述是否清晰、准确、有特色
2. **动作/场景 (Action/Scene) - 权重25%**：动作设计和场景转换是否流畅自然
3. **环境 (Environment) - 权重20%**：背景、环境描写是否与主体协调
4. **风格 (Style) - 权重15%**：整体风格是否统一、符合题材
5. **技术规格 (Technical) - 权重10%**：镜头语言、画幅、时长等技术参数是否合理

请用专业眼光指出具体的不足之处和改进建议。"""

    for video_file in video_prompt_files:
        print(f"\n--- 分析: {video_file.name} ---")
        content = video_file.read_text(encoding='utf-8')

        # 截取前3000字进行分析
        if len(content) > 3000:
            content = content[:3000]

        messages = [
            {"role": "user", "content": f"{analysis_prompt}\n\n以下是视频提示词内容：\n\n{content}"}
        ]

        try:
            response = client.chat(messages)
            print(f"\n{response.content}")
        except Exception as e:
            print(f"❌ 分析失败: {e}")

def main():
    print("🚀 开始使用KIMI模型分析小说内容...")
    print(f"📍 API配置: {client.base_url}")
    print(f"🤖 模型: {client.model_name}")

    try:
        # 测试连接
        test_response = client.chat([
            {"role": "user", "content": "你好，请回复'连接成功'"}
        ])
        print(f"✅ KIMI连接测试: {test_response.content[:50]}...")
    except Exception as e:
        print(f"❌ KIMI连接失败: {e}")
        return

    # 执行各项分析
    analyze_chapters()
    analyze_podcasts()
    analyze_characters()
    analyze_scenes()
    analyze_video_prompts()

    print("\n" + "="*60)
    print("✅ 内容分析完成")
    print("="*60)

    client.close()

if __name__ == "__main__":
    main()
