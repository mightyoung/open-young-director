"""播客主编排Crew"""

import json
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from crewai.content.base import BaseContentCrew, BaseCrewOutput
from crewai.content.podcast.crews.preshow_crew import PreShowCrew
from crewai.content.podcast.crews.intro_crew import IntroCrew
from crewai.content.podcast.crews.segment_crew import SegmentCrew
from crewai.content.podcast.crews.interview_crew import InterviewCrew
from crewai.content.podcast.crews.ad_read_crew import AdReadCrew
from crewai.content.podcast.crews.outro_crew import OutroCrew
from crewai.content.podcast.crews.shownotes_crew import ShowNotesCrew
from crewai.content.podcast.podcast_types import (
    PodcastOutput,
    SegmentOutput,
    InterviewOutput,
    AdReadOutput,
    ShowNotesOutput,
)

if TYPE_CHECKING:
    from crewai.llm import LLM


class PodcastCrew(BaseContentCrew):
    """播客主编排Crew - 协调所有子Crew生成完整播客内容"""

    def __init__(
        self,
        config: Any,
        llm: "LLM" = None,
        verbose: bool = True,
    ):
        """
        初始化播客主编排

        Args:
            config: 播客配置，包含topic, hosts, format等
            llm: 语言模型
            verbose: 是否输出详细信息
        """
        super().__init__(config=config, verbose=verbose)
        self._llm = llm
        self._sub_crews: Dict[str, BaseContentCrew] = {}

    def _create_agents(self) -> Dict[str, Any]:
        """创建Agents - PodcastCrew本身不直接使用Agent"""
        return {}

    def _create_tasks(self) -> Dict[str, Any]:
        """创建Tasks - PodcastCrew本身不直接使用Task"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        # PodcastCrew不创建Crew，而是协调子Crews
        return None

    def kickoff(self) -> BaseCrewOutput:
        """
        执行播客生成完整工作流

        Returns:
            BaseCrewOutput: 包含完整播客内容的输出
        """
        import time
        start = time.time()

        result = self._generate_podcast()
        execution_time = time.time() - start

        return BaseCrewOutput(
            content=result,
            tasks_completed=[
                "preshow",
                "intro",
                "segments",
                "interview",
                "ad_reads",
                "outro",
                "shownotes",
            ],
            execution_time=execution_time,
            metadata={"config": self.config.__dict__ if hasattr(self.config, "__dict__") else {}},
        )

    def _generate_podcast(self) -> PodcastOutput:
        """生成完整播客内容"""
        topic = self.config.topic
        hosts = getattr(self.config, "hosts", 1)
        hosts_names = getattr(self.config, "hosts_names", [])
        format_type = getattr(self.config, "format_type", "narrative")

        # 1. 生成预热内容
        preshow_result = self._run_preshow(topic, hosts)

        # 2. 生成开场介绍
        intro_result = self._run_intro(topic, hosts, hosts_names, format_type)

        # 3. 生成内容段落
        segments_result = self._run_segments(topic)

        # 4. 生成访谈内容（如果有嘉宾）
        interview_result = None
        if hasattr(self.config, "guest_name") and self.config.guest_name:
            interview_result = self._run_interview(
                topic,
                self.config.guest_name,
                getattr(self.config, "guest_background", ""),
            )

        # 5. 生成广告口播（如果有赞助商）
        ad_reads_result = self._run_ad_reads()

        # 6. 生成结尾总结
        key_takeaways = self._extract_key_takeaways(segments_result)
        outro_result = self._run_outro(topic, key_takeaways, hosts_names)

        # 7. 生成节目笔记
        shownotes_result = self._run_shownotes(
            topic, segments_result, interview_result
        )

        # 计算总时长
        total_duration = self._calculate_duration(
            preshow_result, intro_result, segments_result,
            interview_result, ad_reads_result, outro_result
        )

        # 构建完整输出
        return PodcastOutput(
            title=getattr(self.config, "title", f"关于{topic}的播客"),
            preshow=preshow_result,
            intro=intro_result,
            segments=self._parse_segments(segments_result),
            interview=self._parse_interview(interview_result) if interview_result else None,
            ad_reads=self._parse_ad_reads(ad_reads_result),
            outro=outro_result,
            shownotes=self._parse_shownotes(shownotes_result),
            total_duration_minutes=total_duration,
        )

    def _run_preshow(self, topic: str, hosts: int) -> str:
        """运行预热Crew"""
        from dataclasses import dataclass

        @dataclass
        class PreshowConfig:
            topic: str

        config = PreshowConfig(topic=topic)
        crew = PreShowCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_content(output.content)
        except Exception as e:
            return f"预热内容生成失败: {str(e)}"

    def _run_intro(
        self,
        topic: str,
        hosts: int,
        hosts_names: List[str],
        format_type: str,
    ) -> str:
        """运行开场Crew"""
        from dataclasses import dataclass

        @dataclass
        class IntroConfig:
            topic: str
            hosts: int
            hosts_names: List[str]
            format_type: str

        config = IntroConfig(
            topic=topic,
            hosts=hosts,
            hosts_names=hosts_names,
            format_type=format_type,
        )
        crew = IntroCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_content(output.content)
        except Exception as e:
            return f"开场介绍生成失败: {str(e)}"

    def _run_segments(self, topic: str) -> List[dict]:
        """运行内容段落Crew"""
        from dataclasses import dataclass

        num_segments = getattr(self.config, "num_segments", 3)
        segment_themes = getattr(self.config, "segment_themes", [])
        segment_duration = getattr(self.config, "segment_duration_minutes", 5.0)

        @dataclass
        class SegmentConfig:
            topic: str
            num_segments: int
            segment_themes: List[str]
            segment_duration_minutes: float

        config = SegmentConfig(
            topic=topic,
            num_segments=num_segments,
            segment_themes=segment_themes,
            segment_duration_minutes=segment_duration,
        )

        segments = []
        for i in range(num_segments):
            segment_theme = segment_themes[i] if i < len(segment_themes) else f"第{i+1}个主题"

            @dataclass
            class SingleSegmentConfig:
                topic: str
                segment_num: int
                segment_theme: str

            single_config = SingleSegmentConfig(
                topic=topic,
                segment_num=i + 1,
                segment_theme=segment_theme,
            )

            crew = SegmentCrew(config=single_config, llm=self._llm, verbose=self.verbose)

            try:
                output = crew.kickoff()
                content = self._extract_json_content(output.content)
                if content:
                    segments.append(content)
            except Exception:
                segments.append({
                    "segment_num": i + 1,
                    "title": segment_theme,
                    "content": "内容待生成",
                    "key_points": [],
                })

        return segments

    def _run_interview(
        self,
        topic: str,
        guest_name: str,
        guest_background: str,
    ) -> dict:
        """运行访谈Crew"""
        from dataclasses import dataclass

        @dataclass
        class InterviewConfig:
            topic: str
            guest_name: str
            guest_background: str

        config = InterviewConfig(
            topic=topic,
            guest_name=guest_name,
            guest_background=guest_background,
        )
        crew = InterviewCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_json_content(output.content) or {}
        except Exception as e:
            return {"error": str(e)}

    def _run_ad_reads(self) -> List[dict]:
        """运行广告口播Crews"""
        sponsors = getattr(self.config, "sponsors", [])

        if not sponsors:
            return []

        ad_reads = []
        for sponsor in sponsors:
            from dataclasses import dataclass

            @dataclass
            class AdReadConfig:
                sponsor_name: str
                sponsor_description: str
                ad_type: str
                duration_seconds: int

            config = AdReadConfig(
                sponsor_name=sponsor.get("name", "赞助商"),
                sponsor_description=sponsor.get("description", ""),
                ad_type=sponsor.get("type", "mid_roll"),
                duration_seconds=sponsor.get("duration", 60),
            )

            crew = AdReadCrew(config=config, llm=self._llm, verbose=self.verbose)

            try:
                output = crew.kickoff()
                content = self._extract_json_content(output.content)
                if content:
                    ad_reads.append(content)
            except Exception:
                ad_reads.append({
                    "sponsor_name": sponsor.get("name", "赞助商"),
                    "script": "本节目由赞助商支持",
                    "placement": sponsor.get("type", "mid_roll"),
                    "duration_seconds": sponsor.get("duration", 60),
                })

        return ad_reads

    def _run_outro(
        self,
        topic: str,
        key_takeaways: List[str],
        hosts_names: List[str],
    ) -> str:
        """运行结尾Crew"""
        from dataclasses import dataclass

        @dataclass
        class OutroConfig:
            topic: str
            key_takeaways: List[str]
            hosts_names: List[str]

        config = OutroConfig(
            topic=topic,
            key_takeaways=key_takeaways,
            hosts_names=hosts_names,
        )
        crew = OutroCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_content(output.content)
        except Exception as e:
            return f"结尾总结生成失败: {str(e)}"

    def _run_shownotes(
        self,
        topic: str,
        segments: List[dict],
        interview_result: Optional[dict],
    ) -> dict:
        """运行节目笔记Crew"""
        from dataclasses import dataclass

        guest_name = None
        if interview_result and "guest_intro" in interview_result:
            guest_name = getattr(self.config, "guest_name", None)

        @dataclass
        class ShowNotesConfig:
            topic: str
            segments: List[dict]
            guest_name: Optional[str]

        config = ShowNotesConfig(
            topic=topic,
            segments=segments,
            guest_name=guest_name,
        )
        crew = ShowNotesCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_json_content(output.content) or {}
        except Exception as e:
            return {"error": str(e)}

    def _extract_content(self, content: Any) -> str:
        """提取文本内容"""
        if isinstance(content, str):
            return content
        if hasattr(content, "raw"):
            return str(content.raw)
        if hasattr(content, "text"):
            return str(content.text)
        return str(content)

    def _extract_json_content(self, content: Any) -> Optional[dict]:
        """提取JSON内容"""
        try:
            if isinstance(content, dict):
                return content
            text = self._extract_content(content)
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return None

    def _extract_key_takeaways(self, segments: List[dict]) -> List[str]:
        """从段落中提取关键要点"""
        takeaways = []
        for seg in segments:
            key_points = seg.get("key_points", [])
            if isinstance(key_points, list):
                takeaways.extend(key_points[:2])
        return takeaways[:6]  # 最多6个

    def _calculate_duration(
        self,
        preshow: str,
        intro: str,
        segments: List[dict],
        interview: Optional[dict],
        ad_reads: List[dict],
        outro: str,
    ) -> float:
        """计算总时长（分钟）"""
        # 粗略估算：约150字/分钟
        total_words = 0

        total_words += len(preshow)
        total_words += len(intro)

        for seg in segments:
            total_words += len(seg.get("content", ""))

        if interview:
            total_words += len(interview.get("questions", [])) * 50

        for ad in ad_reads:
            total_words += ad.get("duration_seconds", 60) * 2.5

        total_words += len(outro)

        return max(1.0, total_words / 150)
