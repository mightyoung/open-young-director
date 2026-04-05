"""ScriptCrew - 主编排器，负责整个剧本生成流程"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from crewai.agent import Agent
from crewai.task import Task

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.script.script_types import (
    ScriptOutput,
    ScriptMetadata,
    BeatSheet,
    SceneOutput,
    SceneDialogue,
)
from crewai.content.script.agents import BeatSheetAgent, VisualMotifTracker

if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class ScriptConfig:
    """ScriptCrew configuration."""
    topic: str
    format: str = "film"  # film/tv/web series
    target_runtime: int = 120  # minutes
    num_acts: int = 3
    genre: str = ""
    title: str = ""
    logline: str = ""
    structure: dict = field(default_factory=dict)
    target_audience: str = ""
    rating: str = ""


class ScriptCrew(BaseContentCrew):
    """ScriptCrew - 主编排器

    负责整个剧本生成流程的协调和管理：
    1. 结构分析 → 分镜表
    2. 分镜表 → 场景描写
    3. 场景 → 对白
    4. 整合 → 完整剧本

    使用示例:
        crew = ScriptCrew(config=script_config)
        result = crew.kickoff()
    """

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents"""
        config = self.config

        # 结构分析Agent
        structure_analyst = Agent(
            role="结构分析师",
            goal="分析故事结构，确保符合叙事最佳实践",
            backstory="""你是一位专业的剧本结构分析师，精通各种叙事结构，
            包括三幕结构、英雄之旅、五幕结构等。你能够识别结构问题并提供改进建议。""",
            verbose=self.verbose,
            llm=self._get_llm(),
        )

        # 格式转换Agent
        format_converter = Agent(
            role="格式转换专家",
            goal="将内容转换为标准剧本格式",
            backstory="""你是一位专业的剧本格式专家，熟悉各种剧本格式标准，
            包括好莱坞标准格式、电视剧格式等。你的输出总是精确符合行业规范。""",
            verbose=self.verbose,
            llm=self._get_llm(),
        )

        return {
            "structure_analyst": structure_analyst,
            "format_converter": format_converter,
        }

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks"""
        tasks = {
            "analyze_structure": Task(
                description="分析并优化故事结构",
                agent=self.agents["structure_analyst"],
                expected_output="结构分析报告和改进建议"
            ),
            "convert_format": Task(
                description="将剧本内容转换为标准格式",
                agent=self.agents["format_converter"],
                expected_output="符合格式规范的剧本"
            ),
        }
        return tasks

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai.crew import Crew
        from crewai.process import Process

        crew = Crew(
            agents=list(self.agents.values()),
            tasks=list(self.tasks.values()),
            process=Process.sequential,
            verbose=self.verbose,
        )
        return crew

    def _evaluate_output(self, output: "ScriptOutput") -> "QualityReport":
        """评估ScriptOutput质量

        P2: 统一的 QualityReport 语义。
        - scenes为空 -> is_usable=False
        - dialogues为空 -> requires_manual_review=True
        - output.warnings或metadata中有warnings -> requires_manual_review=True
        """
        from crewai.content.base import QualityReport

        warnings = list(output.warnings) if output.warnings else []
        errors = []

        # 检查场景数
        if not output.scenes:
            errors.append("no_scenes: 场景列表为空")
            return QualityReport(
                is_usable=False,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )

        # 检查对白（可选，但有则检查质量）
        if not output.dialogues:
            warnings.append("no_dialogues: 对白列表为空")

        # 检查metadata中的warnings
        if output.metadata:
            meta_warnings = output.metadata.warnings if hasattr(output.metadata, 'warnings') else []
            if meta_warnings:
                warnings.extend(meta_warnings)

        return QualityReport(
            is_usable=len(errors) == 0,
            requires_manual_review=len(warnings) > 0 or len(errors) > 0,
            warnings=warnings,
            errors=errors,
        )

    def kickoff(self) -> BaseCrewOutput:
        """执行剧本生成"""
        import time
        start = time.time()

        # 使用专门的生成流程
        script_output, motif_tracker = self._generate_script()

        # 生成视觉主题报告
        motif_report = motif_tracker.generate_motif_report()

        execution_time = time.time() - start

        # 将motif报告添加到metadata中
        metadata = self._get_metadata()
        metadata["motif_report"] = motif_report

        return BaseCrewOutput(
            content=script_output,
            tasks_completed=[
                "结构分析",
                "分镜表生成",
                "场景描写",
                "对白生成",
                "格式转换",
                "视觉主题追踪",
            ],
            execution_time=execution_time,
            metadata=metadata,
        )

    def _generate_script(self) -> tuple[ScriptOutput, VisualMotifTracker]:
        """生成完整剧本

        Returns:
            tuple: (ScriptOutput, motif_tracker实例)
        """
        config = self.config

        # 1. 获取或生成结构
        structure = config.get("structure", {})
        target_runtime = config.get("target_runtime", 120)
        script_format = config.get("format", "film")

        # 2. 生成分镜表
        beat_sheets = self._generate_beat_sheets(structure, target_runtime)

        # 3. 生成场景
        scenes = self._generate_scenes(beat_sheets, config)

        # 4. 生成对白
        dialogues, motif_tracker = self._generate_dialogues(scenes, config)

        # 5. 组装输出
        metadata = ScriptMetadata(
            format=script_format,
            genre=config.get("genre", ""),
            target_runtime=target_runtime,
            target_audience=config.get("target_audience", ""),
            rating=config.get("rating", ""),
        )

        script_output = ScriptOutput(
            title=config.get("title", "未命名剧本"),
            logline=config.get("logline", ""),
            beat_sheets=beat_sheets,
            scenes=scenes,
            dialogues=dialogues,
            metadata=metadata,
            warnings=[],
        )

        return script_output, motif_tracker

    def _generate_beat_sheets(
        self,
        structure: dict,
        target_runtime: int,
    ) -> List[BeatSheet]:
        """生成分镜表"""
        beat_agent = BeatSheetAgent(llm=self._get_llm(), verbose=self.verbose)
        return beat_agent.generate_beat_sheet(structure, target_runtime)

    def _generate_scenes(
        self,
        beat_sheets: List[BeatSheet],
        config: dict,
    ) -> List[SceneOutput]:
        """生成场景描写"""
        scenes = []
        scene_number = 1

        for beat_sheet in beat_sheets:
            for beat in beat_sheet.beats:
                # 构建场景配置
                scene_config = {
                    "scene_number": scene_number,
                    "beat": {
                        "number": beat.number,
                        "name": beat.name,
                        "description": beat.description,
                        "scene_purpose": beat.scene_purpose,
                        "turning_point": beat.turning_point,
                    },
                    "location": config.get("default_location", "待定"),
                    "time_of_day": config.get("default_time", "日"),
                    "characters": config.get("characters", []),
                    "estimated_duration": 5,
                    "llm": self._get_llm(),
                }

                # 使用SceneCrew生成场景
                from crewai.content.script.crews.scene_crew import SceneCrew
                scene_crew = SceneCrew(config=scene_config, verbose=self.verbose)
                scene_result = scene_crew.kickoff()

                scene_output = scene_result.content
                if isinstance(scene_result.content, SceneOutput):
                    scenes.append(scene_output)

                scene_number += 1

        return scenes

    def _generate_dialogues(
        self,
        scenes: List[SceneOutput],
        config: dict,
    ) -> tuple[List[SceneDialogue], VisualMotifTracker]:
        """生成对白

        Returns:
            tuple: (dialogues列表, motif_tracker实例)
        """
        dialogues = []

        # 使用VisualMotifTracker追踪视觉主题
        motif_tracker = VisualMotifTracker(llm=self._get_llm())
        if "visual_motifs" in config:
            motif_tracker.define_motifs(config["visual_motifs"])

        for scene in scenes:
            dialogue_config = {
                "scene": {
                    "scene_number": scene.scene_number,
                    "location": scene.location,
                    "time_of_day": scene.time_of_day,
                },
                "characters": scene.characters,
                "character_backgrounds": config.get("character_backgrounds", {}),
                "scene_purpose": scene.beat_number,  # 使用beat编号作为场景目的
                "emotions": config.get("emotions", {}),
                "llm": self._get_llm(),
            }

            from crewai.content.script.crews.dialogue_crew import DialogueCrew
            dialogue_crew = DialogueCrew(config=dialogue_config, verbose=self.verbose)
            dialogue_result = dialogue_crew.kickoff()

            dialogue_output = dialogue_result.content
            if isinstance(dialogue_result.content, SceneDialogue):
                dialogues.append(dialogue_output)

            # 记录视觉主题出现
            for motif in config.get("visual_motifs", []):
                motif_tracker.record_occurrence(
                    motif,
                    f"场景{scene.scene_number}",
                    scene.action[:50] if len(scene.action) > 50 else scene.action
                )

        return dialogues, motif_tracker

    def _get_llm(self):
        """获取LLM实例"""
        if isinstance(self.config, dict):
            return self.config.get("llm")
        return None

    def _get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        if isinstance(self.config, dict):
            return {
                "format": self.config.get("format", "film"),
                "genre": self.config.get("genre", ""),
                "target_runtime": self.config.get("target_runtime", 0),
            }
        return {}


__all__ = ["ScriptCrew"]
