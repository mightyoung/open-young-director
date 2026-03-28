#!/usr/bin/env python3
"""分析《太古魔帝传》大纲冲突并生成改进建议报告"""

import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from llm.kimi_client import KIMIClient

# 文件路径
OUTLINE_DIR = Path(__file__).parent / "novels" / "太古魔帝传" / "outline"
CHAPTER_DIR = Path(__file__).parent / "novels" / "太古魔帝传" / "chapters"

# 读取文件
def read_file(path: Path) -> str:
    """读取文件内容"""
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ""

# 主分析函数
def main():
    print("=" * 80)
    print("《太古魔帝传》大纲冲突分析报告生成器")
    print("=" * 80)

    # 初始化KIMI客户端
    print("\n[1/5] 初始化KIMI客户端...")

    # 确保.env文件被加载
    from pathlib import Path
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print(f"    加载环境变量: {env_path}")

    client = KIMIClient(timeout=300.0, retry_max_retries=5)
    print(f"    API: {client.base_url}")
    print(f"    Model: {client.model_name}")

    # 读取原大纲文件
    print("\n[2/5] 读取原大纲文件...")
    volume1_outline = read_file(OUTLINE_DIR / "大纲_第1卷.md")
    volume2_outline = read_file(OUTLINE_DIR / "大纲_第2卷.md")
    slow_plan = read_file(OUTLINE_DIR / "境界放缓方案.md")
    print(f"    第一卷大纲: {len(volume1_outline)} 字符")
    print(f"    第二卷大纲: {len(volume2_outline)} 字符")
    print(f"    境界放缓方案: {len(slow_plan)} 字符")

    # 读取metadata
    print("\n[3/5] 读取已生成章节信息...")
    metadata_path = Path(__file__).parent / "novels" / "太古魔帝传" / "metadata.json"
    metadata = json.loads(read_file(metadata_path)) if metadata_path.exists() else {}
    print(f"    已生成章节数: {len(metadata.get('chapters', []))}")

    # 读取ch012作为示例
    print("\n[4/5] 读取已生成章节示例 (ch012)...")
    ch012_path = CHAPTER_DIR / "ch012_魔窟惊变.md"
    ch012_content = read_file(ch012_path)[:3000]  # 只读取前3000字符作为示例
    print(f"    ch012 长度: {len(ch012_content)} 字符")

    # 构建分析prompt
    print("\n[5/5] 调用KIMI API进行分析...")

    system_prompt = """你是一位资深的修仙小说大纲专家，精通中国网文的创作套路和架构。你需要分析两份大纲文件之间的冲突，并提出具体的改进建议。

分析要点：
1. 主线冲突分析：两条故事线的核心矛盾
2. 境界进度矛盾：原大纲vs已生成章节的境界差异
3. 角色体系冲突：原大纲角色vs魔帝传承体系角色
4. 方案对比：废弃/修改/融合三条路的优劣
5. 推荐方案：具体的融合方案

请用中文输出详细的分析报告，格式清晰，包含具体的章节调整建议。"""

    user_prompt = f"""## 需要分析的文件内容

### 第一卷大纲（原文50%摘录）
{volume1_outline[:8000]}

### 第二卷大纲（原文50%摘录）
{volume2_outline[:8000]}

### 境界放缓方案
{slow_plan[:5000]}

### metadata.json（已生成章节状态）
{json.dumps(metadata, ensure_ascii=False, indent=2)[:5000]}

### ch012章节内容示例
{ch012_content}

---

## 请分析以下问题：

### 1. 主线冲突分析
当前故事线（原大纲60章体系）与已生成章节（魔帝传承体系）存在哪些核心冲突？

### 2. 境界进度矛盾
- 原大纲：ch1-60是炼气期，ch61-120是筑基期
- 已生成章节：ch12已经是金丹期，ch18在对抗化神期
- 如何融合两条线？

### 3. 角色体系冲突
- 原大纲角色：韩林（废物逆袭）、柳如烟（退婚对象）、叶尘（宿敌）、太虚子（师父）
- 已生成章节角色：魔帝残魂、魔将赤魇、血河老祖、幽冥子
- 两种体系如何融合？

### 4. 具体改进建议
- 方案A：完全废弃已生成章节，从头开始
- 方案B：保留已生成章节，但需要大规模修改
- 方案C：将两条线融合（魔帝传承作为暗线，原大纲剧情作为主线）
- 请分析每个方案的优劣

### 5. 推荐方案
请给出具体的融合方案，包括：
- 境界体系的统一方案
- 角色体系的统一方案
- 剧情线的统一方案
- 后续章节生成的具体调整建议

### 6. 具体章节调整建议
请给出ch1-ch60每章的大纲要点，包括：
- 境界进度（应该到哪个境界）
- 核心事件
- 需要修改的已生成章节如何调整

请生成一份详细的分析报告。"""

    print("\n" + "=" * 80)
    print("正在等待KIMI API响应...")
    print("=" * 80 + "\n")

    try:
        response = client.chat(
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=16000
        )

        print("\n" + "=" * 80)
        print("KIMI API 分析结果")
        print("=" * 80)
        print(response.content)

        # 保存结果
        output_path = Path(__file__).parent / "novels" / "太古魔帝传" / "outline" / "大纲冲突分析报告.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response.content, encoding='utf-8')
        print(f"\n报告已保存至: {output_path}")

        print("\n" + "=" * 80)
        print("Token 使用统计")
        print("=" * 80)
        print(f"Usage: {response.usage}")

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        client.close()

if __name__ == "__main__":
    main()
