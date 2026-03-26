"""对白Crew - 管理对话写作"""

from typing import Dict, List, Any, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew
from crewai.content.script.script_types import DialogueBlock, SceneDialogue

if TYPE_CHECKING:
    from crewai.llm import LLM


class DialogueCrew(BaseContentCrew):
    """对白Crew - 管理对话写作

    负责为场景编写自然、符合角色的对白。

    使用示例:
        crew = DialogueCrew(config=dialogue_config)
        result = crew.kickoff()
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents"""
        dialogue_writer = Agent(
            role="对白作家",
            goal="写出自然、符合角色性格的对白",
            backstory="""你是一位擅长对白写作的剧作家，你的对白简洁有力，
            每句话都有其存在的意义。你深入理解每个角色的背景和动机，
            写出的对白自然地揭示角色性格和推进剧情。""",
            verbose=self.verbose,
            llm=self.config.get("llm") if isinstance(self.config, dict) else None,
        )

        return {"dialogue_writer": dialogue_writer}

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        write_dialogue_task = Task(
            description=self._build_dialogue_prompt(),
            agent=self.agents["dialogue_writer"],
            expected_output="完整的场景对白，包含角色名和对白内容"
        )

        return {"write_dialogue": write_dialogue_task}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai.crew import Crew

        crew = Crew(
            agents=list(self.agents.values()),
            tasks=list(self.tasks.values()),
            verbose=self.verbose,
        )
        return crew

    def _build_dialogue_prompt(self) -> str:
        """构建对白写作提示"""
        config = self.config
        scene = config.get("scene", {})
        scene_number = scene.get("scene_number", 0)
        location = scene.get("location", "待定")
        time_of_day = scene.get("time_of_day", "日")
        characters = config.get("characters", [])

        # 获取角色背景
        character_backgrounds = config.get("character_backgrounds", {})
        background_str = ""
        for char, bg in character_backgrounds.items():
            background_str += f"\n{char}: {bg}"

        # 获取场景目的
        scene_purpose = config.get("scene_purpose", "推进剧情")

        # 获取情绪要求
        emotions = config.get("emotions", {})

        prompt = f"""请为以下场景编写对白：

场景信息:
- 场景编号: {scene_number}
- 场景地点: {location}
- 时间: {time_of_day}
- 场景目的: {scene_purpose}

角色及背景:
{background_str}

情绪要求:
{emotions}

要求:
1. 每句对白都要推动剧情或揭示角色
2. 对白要符合每个角色的背景和性格
3. 注意句子的长短变化，体现说话节奏
4. 可以加入括号标注情绪/动作
5. 对话格式：角色名（大写）- 对白内容

请输出完整的对白："""

        return prompt

    def _parse_output(self, result: Any) -> SceneDialogue:
        """解析Crew输出为SceneDialogue"""
        config = self.config
        scene = config.get("scene", {})

        dialogues = self._extract_dialogue_blocks(str(result))

        return SceneDialogue(
            scene_number=scene.get("scene_number", 0),
            location=scene.get("location", ""),
            time_of_day=scene.get("time_of_day", ""),
            dialogues=dialogues
        )

    def _extract_dialogue_blocks(self, text: str) -> List[DialogueBlock]:
        """从文本中提取对话块"""
        blocks = []
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检测对话格式：角色名 - 对白
            # 支持多种格式：CHARACTER: / CHARACTER - / CHARACTER——
            for sep in [": ", " - ", "——"]:
                if sep in line:
                    parts = line.split(sep, 1)
                    if len(parts) == 2 and parts[0].isupper():
                        speaker = parts[0].strip()
                        content = parts[1].strip()

                        # 提取情绪/动作标注
                        emotion = ""
                        subtext = ""

                        # 处理括号内的内容
                        if "(" in content and ")" in content:
                            paren_start = content.find("(")
                            paren_end = content.find(")")
                            emotion = content[paren_start + 1:paren_end]
                            content = content[:paren_start].strip()

                        blocks.append(DialogueBlock(
                            speaker=speaker,
                            content=content,
                            emotion=emotion,
                            subtext=subtext
                        ))
                        break

        return blocks


__all__ = ["DialogueCrew"]
