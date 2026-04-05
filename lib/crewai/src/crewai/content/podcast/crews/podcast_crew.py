"""播客主编排Crew"""

import json
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from crewai.content.base import BaseContentCrew, BaseCrewOutput, QualityReport
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

        # P2: 统一 quality_report 语义
        quality_report = self._evaluate_output(result)
        output_status = "success"
        if not quality_report.is_usable:
            output_status = "failed"
        elif quality_report.errors:
            output_status = "failed"
        elif quality_report.requires_manual_review:
            output_status = "partial"
        elif quality_report.warnings:
            output_status = "warning"

        # 构建 metadata，包含统一的 quality_report
        metadata = dict(result.metadata) if result.metadata else {}
        metadata["quality_report"] = {
            "is_usable": quality_report.is_usable,
            "requires_manual_review": quality_report.requires_manual_review,
            "output_status": output_status,
            "warnings": quality_report.warnings,
            "errors": quality_report.errors,
        }
        metadata["output_status"] = output_status

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
            metadata=metadata,
        )

    def _evaluate_output(self, output: PodcastOutput) -> QualityReport:
        """评估PodcastOutput质量

        P2: 统一的 QualityReport 语义。
        - failed_sections 存在 -> requires_manual_review=True, is_usable=False
        - status=complete -> is_usable=True
        - status=partial -> requires_manual_review=True
        - status=failed -> is_usable=False
        """
        warnings = []
        errors = []

        # 检查 failed_sections
        failed_sections = output.metadata.get("failed_sections", {}) if output.metadata else {}
        if failed_sections:
            for section, err in failed_sections.items():
                errors.append(f"{section}: {err}")

        # 根据 status 判断 is_usable 和 requires_manual_review
        status = output.status
        if status == "failed":
            return QualityReport(
                is_usable=False,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors or ["整体生成失败"],
            )
        elif status == "partial":
            return QualityReport(
                is_usable=True,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )
        else:  # complete
            return QualityReport(
                is_usable=True,
                requires_manual_review=False,
                warnings=warnings,
                errors=errors,
            )

    def _generate_podcast(self) -> PodcastOutput:
        """生成完整播客内容"""
        topic = self.config.topic
        hosts = getattr(self.config, "hosts", 1)
        hosts_names = getattr(self.config, "hosts_names", [])
        format_type = getattr(self.config, "format_type", "narrative")
        failed_sections: dict[str, str] = {}

        # 1. 生成预热内容
        preshow_content, preshow_err = self._run_preshow(topic, hosts)
        if preshow_err:
            failed_sections["preshow"] = preshow_err
        preshow_result = preshow_content or ""

        # 2. 生成开场介绍
        intro_content, intro_err = self._run_intro(topic, hosts, hosts_names, format_type)
        if intro_err:
            failed_sections["intro"] = intro_err
        intro_result = intro_content or ""

        # 3. 生成内容段落
        segments_result, segment_errors = self._run_segments(topic)
        failed_sections.update(segment_errors)

        # 4. 生成访谈内容（如果启用了include_interview）
        interview_result = None
        include_interview = getattr(self.config, "include_interview", False)
        if include_interview:
            guest_name = getattr(self.config, "guest_name", "") or f"待定嘉宾"
            interview_result = self._run_interview(
                topic,
                guest_name,
                getattr(self.config, "guest_background", ""),
            )
            if isinstance(interview_result, dict) and "error" in interview_result:
                failed_sections["interview"] = interview_result["error"]
                interview_result = None

        # 5. 生成广告口播（如果启用了include_ads）
        ad_reads_result = []
        include_ads = getattr(self.config, "include_ads", False)
        if include_ads:
            ad_reads_result, ad_errors = self._run_ad_reads()
            failed_sections.update(ad_errors)

        # 6. 生成结尾总结
        key_takeaways = self._extract_key_takeaways(segments_result)
        outro_content, outro_err = self._run_outro(topic, key_takeaways, hosts_names)
        if outro_err:
            failed_sections["outro"] = outro_err
        outro_result = outro_content or ""

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
        metadata: dict[str, Any] = {"config": self.config.__dict__ if hasattr(self.config, "__dict__") else {}}
        if failed_sections:
            metadata["failed_sections"] = failed_sections

        # Determine overall status
        if failed_sections:
            output_status = "partial"
        elif not segments_result:
            output_status = "failed"
        else:
            output_status = "complete"

        return PodcastOutput(
            title=getattr(self.config, "title", f"关于{topic}的播客"),
            status=output_status,
            preshow=preshow_result if preshow_content else None,
            intro=intro_result if intro_content else None,
            segments=self._parse_segments(segments_result),
            interview=self._parse_interview(interview_result) if interview_result else None,
            ad_reads=self._parse_ad_reads(ad_reads_result) if ad_reads_result else [],
            outro=outro_result if outro_content else None,
            shownotes=self._parse_shownotes(shownotes_result),
            total_duration_minutes=total_duration,
            metadata=metadata,
        )

    def _run_preshow(self, topic: str, hosts: int) -> tuple[Optional[str], Optional[str]]:
        """运行预热Crew

        Returns:
            tuple: (content, error_message) - error_message is None on success
        """
        from dataclasses import dataclass

        @dataclass
        class PreshowConfig:
            topic: str

        config = PreshowConfig(topic=topic)
        crew = PreShowCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_content(output.content), None
        except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
            return None, f"预热内容生成失败: {str(e)}"

    def _run_intro(
        self,
        topic: str,
        hosts: int,
        hosts_names: List[str],
        format_type: str,
    ) -> tuple[Optional[str], Optional[str]]:
        """运行开场Crew

        Returns:
            tuple: (content, error_message) - error_message is None on success
        """
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
            return self._extract_content(output.content), None
        except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
            return None, f"开场介绍生成失败: {str(e)}"

    def _run_segments(self, topic: str) -> tuple[List[Optional[dict]], dict[str, str]]:
        """运行内容段落Crew

        Returns:
            tuple: (segments_list, errors_dict) - errors_dict maps segment key to error message
        """
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
        segment_errors: dict[str, str] = {}
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
                else:
                    segments.append(None)
            except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
                segment_errors[f"segment_{i+1}"] = str(e)
                segments.append(None)

        return segments, segment_errors

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
        except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
            return {"error": str(e)}

    def _run_ad_reads(self) -> tuple[List[Optional[dict]], dict[str, str]]:
        """运行广告口播Crews

        Returns:
            tuple: (ad_reads_list, errors_dict) - errors_dict maps sponsor key to error message
        """
        sponsors = getattr(self.config, "sponsors", [])

        if not sponsors:
            return [], {}

        ad_reads = []
        ad_errors: dict[str, str] = {}
        for i, sponsor in enumerate(sponsors):
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
                else:
                    ad_reads.append(None)
            except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
                ad_errors[f"ad_read_{i+1}"] = str(e)
                ad_reads.append(None)

        return ad_reads, ad_errors

    def _run_outro(
        self,
        topic: str,
        key_takeaways: List[str],
        hosts_names: List[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """运行结尾Crew

        Returns:
            tuple: (content, error_message) - error_message is None on success
        """
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
            return self._extract_content(output.content), None
        except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
            return None, f"结尾总结生成失败: {str(e)}"

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

        # Filter out None entries (failed segments) before passing to crew
        valid_segments = [s for s in segments if s is not None]

        @dataclass
        class ShowNotesConfig:
            topic: str
            segments: List[dict]
            guest_name: Optional[str]

        config = ShowNotesConfig(
            topic=topic,
            segments=valid_segments,
            guest_name=guest_name,
        )
        crew = ShowNotesCrew(config=config, llm=self._llm, verbose=self.verbose)

        try:
            output = crew.kickoff()
            return self._extract_json_content(output.content) or {}
        except (RuntimeError, TimeoutError, IOError, ValueError, TypeError) as e:
            return {"error": str(e)}

    def _parse_segments(self, segments: List[dict]) -> List[SegmentOutput]:
        """Parse segment list into SegmentOutput objects, skipping None entries.

        None entries indicate failed segments and are excluded from output.
        """
        result = []
        for seg in segments:
            if seg is None:
                continue
            result.append(SegmentOutput(
                segment_num=seg.get("segment_num", 0),
                title=seg.get("title", ""),
                content=seg.get("content", ""),
                duration_minutes=seg.get("duration_minutes", 0.0),
                key_points=seg.get("key_points", []),
                timestamp_start=seg.get("timestamp_start"),
                timestamp_end=seg.get("timestamp_end"),
                speaker_notes=seg.get("speaker_notes"),
                talking_style=seg.get("talking_style", ""),
                energy_level=seg.get("energy_level", "medium"),
                guest_interaction=seg.get("guest_interaction"),
                background_music_suggestion=seg.get("background_music_suggestion", ""),
                audience_engagement_tips=seg.get("audience_engagement_tips", []),
            ))
        return result

    def _parse_interview(self, interview: dict) -> InterviewOutput:
        """Parse interview dict into InterviewOutput."""
        if not interview or interview.get("error"):
            return InterviewOutput()
        return InterviewOutput(
            guest_intro=interview.get("guest_intro", ""),
            questions=interview.get("questions", []),
            talking_points=interview.get("talking_points", []),
            conclusion=interview.get("conclusion", ""),
            guest_name=interview.get("guest_name"),
            guest_background=interview.get("guest_background"),
        )

    def _parse_ad_reads(self, ad_reads: List[dict]) -> List[AdReadOutput]:
        """Parse ad reads list into AdReadOutput objects."""
        result = []
        for ad in ad_reads:
            if ad is None:
                continue
            result.append(AdReadOutput(
                sponsor_name=ad.get("sponsor_name", ""),
                script=ad.get("script", ""),
                duration_seconds=ad.get("duration_seconds", 0),
                placement=ad.get("placement", ""),
            ))
        return result

    def _parse_shownotes(self, shownotes: dict) -> ShowNotesOutput:
        """Parse shownotes dict into ShowNotesOutput."""
        if shownotes is None or shownotes.get("error"):
            return ShowNotesOutput()
        return ShowNotesOutput(
            title=shownotes.get("title", ""),
            description=shownotes.get("description", ""),
            timestamps=shownotes.get("timestamps", []),
            guest_info=shownotes.get("guest_info"),
            links=shownotes.get("links", []),
            social_media=shownotes.get("social_media", []),
        )

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
        """从段落中提取关键要点，忽略None条目"""
        takeaways = []
        for seg in segments:
            if seg is None:
                continue
            key_points = seg.get("key_points", [])
            if isinstance(key_points, list):
                takeaways.extend(key_points[:2])
        return takeaways[:6]  # 最多6个

    def _calculate_duration(
        self,
        preshow: Optional[str],
        intro: Optional[str],
        segments: List[dict],
        interview: Optional[dict],
        ad_reads: List[dict],
        outro: Optional[str],
    ) -> float:
        """计算总时长（分钟）"""
        # 粗略估算：约150字/分钟
        total_words = 0

        total_words += len(preshow) if preshow else 0
        total_words += len(intro) if intro else 0

        for seg in segments:
            if seg is None:
                continue
            total_words += len(seg.get("content", ""))

        if interview:
            total_words += len(interview.get("questions", [])) * 50

        for ad in ad_reads:
            if ad is None:
                continue
            total_words += ad.get("duration_seconds", 60) * 2.5

        total_words += len(outro) if outro else 0

        return max(1.0, total_words / 150)
