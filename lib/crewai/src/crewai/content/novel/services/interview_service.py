"""InterviewService - Deep Director's Interview for Novel Engineering.

Orchestrates a 4-stage interview to define:
1. World Tone & Rules
2. Power Balance & Constraints
3. Character Arcs & Moral Compass
4. Narrative Tropes & Plot Drive

Ensures the generated novel is 100% aligned with user vision.
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class InterviewService:
    """Service for conducting per-novel deep interviews."""

    def run_deep_interview(self) -> Dict[str, Any]:
        """Conduct a comprehensive 6-stage interview to define the entire novel framework."""
        from crewai.utilities.playback import ask_user
        
        results = {}
        
        # 1. 题材与基调
        ans1 = ask_user(questions=[{
            "header": "1/6 题材与基调",
            "question": "请确定小说的核心底色：",
            "type": "choice",
            "options": [
                {"label": "经典仙侠", "description": "传统、硬核、注重修心与境界"},
                {"label": "都市修仙", "description": "现代环境、异能觉醒、日常冲突"},
                {"label": "赛博玄幻", "description": "高科技与修行的畸形碰撞"},
                {"label": "诡秘史诗", "description": "不可名状的恐怖、解谜与宏大叙事"}
            ]
        }])
        results["tone"] = ans1["answers"]["0"]

        # 2. 社会与文明规则
        ans2 = ask_user(questions=[{
            "header": "2/6 社会规则",
            "question": "这个世界的社会运行逻辑是？",
            "type": "choice",
            "options": [
                {"label": "丛林法则", "description": "弱肉强食，秩序混乱，实力代表一切"},
                {"label": "阶级森严", "description": "血统或境界决定社会地位，极难逾越"},
                {"label": "现代契约", "description": "受法律或契约约束，表面平和"}
            ]
        }])
        results["social"] = ans2["answers"]["0"]

        # 3. 力量体系逻辑
        ans3 = ask_user(questions=[{
            "header": "3/6 力量逻辑",
            "question": "力量的本质与限制是？",
            "type": "choice",
            "options": [
                {"label": "严格等价交换", "description": "动用力量必有巨大损耗或反噬"},
                {"label": "资源驱动", "description": "修行即是财富与地盘的博弈"},
                {"label": "心境感悟", "description": "侧重于顿悟与瞬间的爆发"}
            ]
        }])
        results["power"] = ans3["answers"]["0"]

        # 4. 主角灵魂核
        ans4 = ask_user(questions=[{
            "header": "4/6 主角塑造",
            "question": "主角的核心性格偏向是？",
            "type": "choice",
            "options": [
                {"label": "精致利己", "description": "绝对冷静，一切为了生存与变强"},
                {"label": "孤高剑客", "description": "信守某种偏执的道，不为外物所动"},
                {"label": "现代穿越者", "description": "自带现代价值观，对世界进行降维思考"}
            ]
        }])
        results["hero"] = ans4["answers"]["0"]

        # 5. 剧情禁忌 (Taboos)
        ans5 = ask_user(questions=[{
            "header": "5/6 创作红线",
            "question": "你最反感的网文桥段是（Agent 将极力避免）？",
            "type": "choice",
            "options": [
                {"label": "降智打脸", "description": "反派无脑挑衅，主角无脑反杀"},
                {"label": "后宫注水", "description": "女性角色沦为挂件，剧情拖沓"},
                {"label": "机械降神", "description": "关键时刻强行靠奇遇化解危机"}
            ]
        }])
        results["taboo"] = ans5["answers"]["0"]

        # 6. 结局与命运走向
        ans6 = ask_user(questions=[{
            "header": "6/6 最终走向",
            "question": "全书最终的情感基调是？",
            "type": "choice",
            "options": [
                {"label": "王道圆满", "description": "主角登顶，一切遗憾得到弥补"},
                {"label": "缺憾史诗", "description": "获得了力量，但失去了最初的纯真或爱人"},
                {"label": "黑暗循环", "description": "屠龙者终成恶龙，世界进入下一个轮回"}
            ]
        }])
        results["ending"] = ans6["answers"]["0"]

        return results

    def synthesize_to_writer_md(self, results: Dict[str, str]) -> str:
        """Generate a deterministic WRITER.md based on interview results."""
        tone = results.get("tone", "经典仙侠")
        social = results.get("social", "阶级森严")
        power = results.get("power", "严格等价交换")
        hero = results.get("hero", "精致利己")
        taboo = results.get("taboo", "降智打脸")
        ending = results.get("ending", "王道圆满")

        content = f"""# 本小说专属创作宪法 (Project-Specific WRITER.md)

## 1. 核心框架
- **题材底色**: {tone}
- **社会制度**: {social}
- **力量逻辑**: {power}
- **结局导向**: {ending}

## 2. 角色灵魂锁定: {hero}
- 主角行为必须符合 {hero} 的底层动机。
- 严禁出现与此人设矛盾的情感波动。

## 3. 绝对禁忌 (Red Lines)
- 严厉拦截所有关于“{taboo}”的情节。
- 反派必须拥有独立的、合理的生存逻辑。

## 4. 力量平衡红线
- 修行提升必须伴随“{power}”所规定的代价描写。
- 严禁出现无缘无故的境界突破。

## 5. 语言审美与输出限制
- 严禁AI腔、极其、非常、仿佛、似乎。
- 物理化每一个感官描写。
- 严禁任何 meta-talk，禁止解释创作过程。
"""
        return content
