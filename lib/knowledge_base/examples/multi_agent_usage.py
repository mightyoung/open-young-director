"""多Agent角色模拟生成示例.

展示如何使用 MultiAgentNarrativeGenerator 生成小说章节。

Usage:
    python examples/multi_agent_usage.py
"""

from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.multi_agent_narrative import (
    MultiAgentNarrativeGenerator,
    CharacterConfig,
)


def create_example_generator():
    """创建示例生成器"""

    # 世界观设定
    world_setting = """
太古时期，魔族肆虐，天道崩坏。修仙者以逆天之力对抗魔族，
守护人间安宁。修仙体系分为：炼气、筑基、金丹、元婴、化神、大乘、渡劫。

太虚宗：正道修仙门派之首，坐落于太虚山脉。
天玄宗：正道第二大派，与太虚宗亦敌亦友。
鬼冥宗：邪道门派，与魔族有勾结。
"""

    # 角色配置
    characters = [
        CharacterConfig(
            name="韩林",
            role="主角",
            realm="炼气期",
            identity="太虚宗外门弟子",
            personality="坚毅果敢、重情重义、沉默寡言",
            goals="完成三年之约，为父报仇，揭露天玄宗阴谋",
            relationships="柳如烟（恋人）、太虚子（师父）、叶尘（宿敌）",
            secrets="体内封印魔帝残魂",
            catchphrases=["三年之约，必不相负！"],
        ),
        CharacterConfig(
            name="柳如烟",
            role="女主角",
            realm="筑基期",
            identity="太虚宗内门弟子",
            personality="温柔坚定、聪慧机敏、外柔内刚",
            goals="等待韩林完成约定，同时暗中调查叶家阴谋",
            relationships="韩林（恋人）、叶尘（警惕）",
            secrets="疑似太古时期某大能转世",
            catchphrases=["我等你，无论多久。"],
        ),
        CharacterConfig(
            name="叶尘",
            role="反派",
            realm="筑基中期",
            identity="叶家少爷、天玄宗内应",
            personality="阴险狡诈、心狠手辣、野心勃勃",
            goals="除掉韩林，夺取柳如烟，掌控太虚宗",
            relationships="韩林（宿敌）、柳如烟（觊觎）",
            secrets="体内有血河老祖注入的魔功残片",
            catchphrases=["韩林，你不过是蝼蚁之辈。"],
        ),
    ]

    # 这里需要实际的LLM客户端
    # from llm.kimi_client import get_kimi_client
    # llm_client = get_kimi_client()

    # 暂时返回None，实际使用时需要传入真实的LLM客户端
    return None, world_setting, characters


def example_usage():
    """示例用法"""

    generator, world_setting, characters = create_example_generator()

    if generator is None:
        print("=" * 60)
        print("多Agent角色模拟生成系统")
        print("=" * 60)
        print("\n【系统说明】")
        print("""
本系统通过多个LLM Agent模拟角色，让角色自主决定说什么、怎么做，
由真实的角色互动来推动剧情发展。

【核心组件】

1. DirectorAgent（导演Agent）
   - 设定场景和情境
   - 控制叙事节奏（铺垫→冲突→高潮→解决）
   - 引导角色互动

2. CharacterAgent（角色Agent）
   - 模拟单个角色的言行
   - 根据角色设定和当前情境决定行动
   - 保持角色一致性

3. CharacterMemory（角色记忆）
   - 追踪角色状态变化
   - 记录角色历史动作
   - 为后续情节提供上下文

4. PlotAnchor（情节锚点）
   - 确保关键事件按时发生
   - 防止角色行动破坏主线

【使用流程】

1. 初始化生成器，传入LLM客户端和角色配置
2. 调用 generate_chapter() 生成章节
3. 系统自动：
   - 导演Agent设定场景
   - 角色Agent轮流发言
   - 记忆系统追踪状态
   - 情节锚点保证主线

【示例代码】

```python
from agents.multi_agent_narrative import (
    MultiAgentNarrativeGenerator,
    CharacterConfig,
)
from llm.kimi_client import get_kimi_client

# 创建角色配置
characters = [
    CharacterConfig(
        name="韩林",
        role="主角",
        realm="炼气期",
        identity="太虚宗外门弟子",
        personality="坚毅果敢",
        goals="完成三年之约",
        relationships="柳如烟（恋人）",
        secrets="体内封印魔帝残魂",
    ),
    # ... 更多角色
]

# 初始化生成器
generator = MultiAgentNarrativeGenerator(
    config_manager=config_manager,
    llm_client=get_kimi_client(),
    world_setting="太古修仙世界观设定...",
    characters=characters,
)

# 生成章节
result = generator.generate_chapter(
    chapter_num=1,
    chapter_outline={
        "summary": "测灵大典开始",
        "key_events": ["测灵大典", "韩林被判定为伪灵根", "柳如烟退婚"],
        "goal": "完成测灵大典场景",
    },
    previous_summary="",
)

print(result["content"])  # 输出章节正文
print(result["plot_summary"])  # 输出情节摘要
```
""")
        return

    # 章节大纲
    chapter_outline = {
        "summary": "测灵大典上，韩林被判定为伪灵根，遭众人嘲笑。",
        "key_events": [
            "测灵大典开始",
            "韩林上台测灵",
            "被判定为伪灵根",
            "柳如烟出现宣布退婚",
            "叶尘嘲讽韩林",
            "韩林立下三年之约",
        ],
        "goal": "完成测灵大典场景，展现韩林的坚韧性格",
    }

    # 生成章节
    result = generator.generate_chapter(
        chapter_num=1,
        chapter_outline=chapter_outline,
        previous_summary="",
    )

    # 输出结果
    print("=" * 60)
    print(f"第{result['chapter_num']}章 · {result['scene_name']}")
    print("=" * 60)
    print(result["content"])
    print("\n情节摘要：")
    print(f"L1: {result['plot_summary']['l1_one_line_summary']}")
    print(f"L2: {result['plot_summary']['l2_brief_summary']}")
    print(f"L3: {result['plot_summary']['l3_key_plot_points']}")


if __name__ == "__main__":
    example_usage()
