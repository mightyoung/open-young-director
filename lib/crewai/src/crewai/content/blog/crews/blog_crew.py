"""BlogCrew - 博客内容生成主编排"""
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)

from crewai.content.base import BaseContentCrew
from crewai.content.blog.agents import (
    BodyAgent,
    HookAgent,
    PlatformAdapterAgent,
    SEOAgent,
    ThumbnailConceptAgent,
    TitleAgent,
)
from crewai.content.blog.blog_types import (
    BlogCrewOutput,
    BlogPost,
    BodyContent,
    ContentStatus,
    HookOption,
    PlatformContent,
    SEOData,
    ThumbnailConcept,
    TitleOption,
    TitleStyle,
)
from crewai.content.exceptions import (
    ContentGenerationError,
)
from crewai.content.types import BlogPlatform, ContentConfig, ContentTypeEnum
from crewai.crew import Crew
from crewai.task import Task


if TYPE_CHECKING:
    from crewai.llm import LLM


@dataclass
class BlogCrewConfig:
    """BlogCrew配置"""
    topic: str
    target_platforms: list[str] = field(default_factory=lambda: ["medium"])
    include_keywords: list[str] = field(default_factory=list)
    language: str = "zh"
    max_words: int | None = None
    target_audience: str | None = None
    title_style: str = "seo"  # seo/sensational/curiosity/list/guide/question/number (clickbait→sensational, technical→list)
    llm: Optional["LLM"] = None

    def to_content_config(self) -> ContentConfig:
        """转换为通用ContentConfig"""
        return ContentConfig(
            content_type=ContentTypeEnum.BLOG,
            platform=BlogPlatform.WECHAT if "wechat" in self.target_platforms else None,
            language=self.language,
            max_words=self.max_words,
            target_audience=self.target_audience,
        )


class BlogCrew(BaseContentCrew[BlogPost]):
    """博客内容生成Crew (Facade模式)

    使用流程:
    1. 创建BlogCrew实例
    2. 调用 kickoff() 执行
    3. 获取 BlogCrewOutput 结果

    示例:
        config = BlogCrewConfig(topic="Python异步编程指南")
        crew = BlogCrew(config=config)
        result = crew.kickoff()
        print(result.post.title)
    """

    def __init__(
        self,
        config: BlogCrewConfig,
        verbose: bool = True
    ):
        self._blog_config = config  # 保存BlogCrewConfig到独立属性
        self._verbose = verbose
        self._body_agent: BodyAgent | None = None
        self._hook_agent: HookAgent | None = None
        self._title_agent: TitleAgent | None = None
        self._thumbnail_agent: ThumbnailConceptAgent | None = None
        self._seo_agent: SEOAgent | None = None
        self._platform_agent: PlatformAdapterAgent | None = None

        super().__init__(
            config=config.to_content_config(),
            verbose=verbose
        )

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents"""
        llm = self._blog_config.llm

        return {
            "body_agent": BodyAgent(llm=llm),
            "hook_agent": HookAgent(llm=llm),
            "title_agent": TitleAgent(llm=llm),
            "thumbnail_agent": ThumbnailConceptAgent(llm=llm),
            "seo_agent": SEOAgent(llm=llm),
            "platform_agent": PlatformAdapterAgent(llm=llm),
        }

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks - BlogCrew使用sequential流程"""
        # BlogCrew采用sequential流程: Hook -> Title -> Body -> SEO -> Thumbnail -> Platform
        return {}

    def _create_workflow(self) -> Crew:
        """创建Crew工作流

        BlogCrew采用sequential流程:
        1. HookAgent - 生成钩子变体
        2. TitleAgent - 基于选定钩子生成标题
        3. BodyAgent - 生成博客正文
        4. SEOAgent - SEO优化
        5. ThumbnailAgent - 缩略图概念
        6. PlatformAgent - 平台适配
        """
        agents = self.agents

        # 创建sequential流程的tasks
        tasks = []

        # Task 1: 生成钩子
        hook_task = Task(
            description=f"为主题 '{self._blog_config.topic}' 生成5个高吸引力钩子",
            expected_output="5个钩子变体，包含类型和参与度评分",
            agent=agents["hook_agent"].agent,
            async_execution=False,
        )
        tasks.append(hook_task)

        # Task 2: 基于钩子生成标题
        title_style_note = f"（标题风格偏好: {self._blog_config.title_style}）" if self._blog_config.title_style and self._blog_config.title_style != TitleStyle.SEO.value else ""
        title_task = Task(
            description=f"基于钩子为主题 '{self._blog_config.topic}' 生成5个标题{title_style_note}。优先生成符合该风格的标题。",
            expected_output="5个标题变体，包含风格和评分，优先匹配指定风格",
            agent=agents["title_agent"].agent,
            context=[hook_task],
            async_execution=False,
        )
        tasks.append(title_task)

        # Task 3: 生成博客正文
        target_words = self._blog_config.max_words or 2000
        keywords_note = f"（必须包含关键词: {', '.join(self._blog_config.include_keywords)}）" if self._blog_config.include_keywords else ""
        body_task = Task(
            description=f"基于钩子和标题为主题 '{self._blog_config.topic}' 生成约{target_words}字博客正文{keywords_note}",
            expected_output="完整博客正文，包含结构化章节",
            agent=agents["body_agent"].agent,
            context=[hook_task, title_task],
            async_execution=False,
        )
        tasks.append(body_task)

        # Task 4: SEO优化
        seo_keywords_note = f"（目标关键词: {', '.join(self._blog_config.include_keywords)}）" if self._blog_config.include_keywords else ""
        seo_task = Task(
            description=f"为 '{self._blog_config.topic}' 进行SEO优化{seo_keywords_note}",
            expected_output="关键词、Meta描述、标签等SEO数据",
            agent=agents["seo_agent"].agent,
            context=[body_task],
            async_execution=False,
        )
        tasks.append(seo_task)

        # Task 5: 缩略图概念
        thumbnail_task = Task(
            description=f"为 '{self._blog_config.topic}' 生成3个缩略图概念",
            expected_output="3个缩略图视觉概念",
            agent=agents["thumbnail_agent"].agent,
            context=[title_task],
            async_execution=False,
        )
        tasks.append(thumbnail_task)

        # Task 6: 平台适配 - 基于正文和SEO数据进行多平台适配
        platform_task = Task(
            description=f"将博客内容适配到以下平台: {', '.join(self._blog_config.target_platforms)}",
            expected_output=f"各平台的适配内容（标题、正文、标签、摘要）",
            agent=agents["platform_agent"].agent,
            context=[body_task, seo_task],
            async_execution=False,
        )
        tasks.append(platform_task)

        # 创建Crew - 提取实际的Agent对象而非wrapper
        crew = Crew(
            agents=[agent_obj.agent for agent_obj in agents.values()],
            tasks=tasks,
            verbose=self._verbose,
            process="sequential",
        )

        return crew

    def kickoff(self) -> BlogCrewOutput:
        """执行BlogCrew并返回博客内容输出

        Returns:
            BlogCrewOutput: 包含完整博客内容的输出对象
        """
        try:
            crew_output = super().kickoff()
        except Exception as e:
            raise ContentGenerationError(f"BlogCrew执行失败: {e!s}") from e

        execution_time = crew_output.execution_time

        # 从 metadata 获取统一的 quality_report
        quality_report_meta = crew_output.metadata.get("quality_report", {})
        output_status = quality_report_meta.get("output_status", "success")

        # 构建最终输出 - 使用统一的 quality_report
        post = crew_output.content  # content 已经是 BlogPost，由 _parse_output 返回

        return BlogCrewOutput(
            post=post,
            tasks_completed=crew_output.tasks_completed,
            execution_time=execution_time,
            metadata={
                "topic": self._blog_config.topic,
                "target_platforms": self._blog_config.target_platforms,
                "config": self._blog_config.__dict__,
                "quality_report": quality_report_meta,
                "output_status": output_status,
            },
            is_usable=quality_report_meta.get("is_usable", True),
            requires_manual_review=quality_report_meta.get("requires_manual_review", False),
        )

    def _parse_output(self, result: Any) -> BlogPost:
        """解析Crew输出为BlogPost

        替代父类默认实现，直接返回BlogPost对象。
        """
        # result 是 CrewOutput，直接调用 _build_blog_post 解析
        return self._build_blog_post(result)

    def _evaluate_output(self, output: BlogPost) -> "QualityReport":
        """评估BlogPost质量

        P2: 统一的 QualityReport 语义。
        body 解析失败 = 必须人工介入 (requires_manual_review=True, is_usable=False)。
        """
        from crewai.content.base import QualityReport

        warnings = list(output.warnings) if hasattr(output, 'warnings') else []
        errors = []

        # body 解析失败 = 必须人工介入
        if not output.body:
            errors.append("body_parse_failed: 正文解析失败，内容为空")
            return QualityReport(
                is_usable=False,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )

        # status 非 SUCCESS = 需要人工审核
        if output.status != ContentStatus.SUCCESS:
            warnings.append(f"content_status={output.status.value}")
            return QualityReport(
                is_usable=True,
                requires_manual_review=True,
                warnings=warnings,
                errors=errors,
            )

        return QualityReport(
            is_usable=True,
            requires_manual_review=False,
            warnings=warnings,
            errors=errors,
        )

    def _build_blog_post(self, crew_output: Any) -> BlogPost:
        """从CrewOutput.tasks_output构建博客文章对象.

        tasks_output 顺序: [hook_task, title_task, body_task, seo_task, thumbnail_task, platform_task]
        每个 TaskOutput 包含 .raw (str) 或 .json_dict (dict) 输出。
        """
        # Import here to avoid circular reference at module level
        from crewai.tasks.task_output import TaskOutput

        post = BlogPost(
            original_topic=self._blog_config.topic,
            title=self._blog_config.topic,
            hooks=[],
            body="",
        )

        # Extract task outputs - handle both CrewOutput object and raw crew result
        tasks_output: list[TaskOutput] = []
        if hasattr(crew_output, "tasks_output"):
            tasks_output = crew_output.tasks_output or []
        elif isinstance(crew_output, list):
            tasks_output = crew_output

        # Task 0: Hook output - parse JSON hooks
        if len(tasks_output) > 0:
            raw = tasks_output[0].raw if hasattr(tasks_output[0], "raw") else str(tasks_output[0])
            post.hooks = self._parse_hooks(raw)

        # Task 1: Title output - parse JSON titles or use raw, then filter by title_style
        if len(tasks_output) > 1:
            raw = tasks_output[1].raw if hasattr(tasks_output[1], "raw") else str(tasks_output[1])
            title_data = self._parse_titles(raw)
            if title_data:
                # Filter titles by title_style (same logic as generate_titles())
                style = self._blog_config.title_style
                if style and style != TitleStyle.SEO.value:
                    style_map = {
                        "clickbait": TitleStyle.SENSATIONAL.value,
                        "technical": TitleStyle.LIST.value,
                        TitleStyle.SEO.value: None,
                        TitleStyle.SENSATIONAL.value: TitleStyle.SENSATIONAL.value,
                        TitleStyle.CURIOSITY.value: TitleStyle.CURIOSITY.value,
                        TitleStyle.LIST.value: TitleStyle.LIST.value,
                        TitleStyle.GUIDE.value: TitleStyle.GUIDE.value,
                        TitleStyle.QUESTION.value: TitleStyle.QUESTION.value,
                        TitleStyle.NUMBER.value: TitleStyle.NUMBER.value,
                    }
                    target = style_map.get(style, style)
                    if target:
                        filtered = [t for t in title_data if t.style == target]
                        if filtered:
                            title_data = filtered
                post.title = title_data[0].title if title_data else self._blog_config.topic
                if title_data and len(title_data) > 0:
                    post.selected_hook = post.hooks[0] if post.hooks else None

        # Task 2: Body output - parse JSON body content
        if len(tasks_output) > 2:
            raw = tasks_output[2].raw if hasattr(tasks_output[2], "raw") else str(tasks_output[2])
            body_data = self._parse_body(raw)
            if body_data:
                post.body = body_data.body

        # Task 3: SEO output - parse SEO data
        if len(tasks_output) > 3:
            raw = tasks_output[3].raw if hasattr(tasks_output[3], "raw") else str(tasks_output[3])
            post.seo = self._parse_seo(raw)

        # Task 4: Thumbnail output - parse thumbnail concepts
        if len(tasks_output) > 4:
            raw = tasks_output[4].raw if hasattr(tasks_output[4], "raw") else str(tasks_output[4])
            post.thumbnail_concepts = self._parse_thumbnails(raw)

        # Task 5: Platform output - parse platform content
        if len(tasks_output) > 5:
            raw = tasks_output[5].raw if hasattr(tasks_output[5], "raw") else str(tasks_output[5])
            platform_contents = self._parse_platform_output(raw)
            if platform_contents:
                post.platform_contents = platform_contents
            elif raw.strip():
                # Platform parsing failed but we got non-empty raw output
                post.warnings.append(f"平台适配输出解析失败，使用原始输出（长度: {len(raw)}）")

        # Track parsing issues for explicit status
        parsing_issues: list[str] = []

        # Fallback: if body is still empty, do NOT substitute title content as body
        # That would create "fake success" where result has content but it's semantically wrong
        if not post.body:
            parsing_issues.append("body_parse_failed")
            post.warnings.append("正文解析失败，内容为空，请手动补充正文")

        # Track platform parsing failures
        if not post.platform_contents and len(tasks_output) > 5:
            raw = tasks_output[5].raw if hasattr(tasks_output[5], "raw") else ""
            if raw.strip():
                parsing_issues.append("platform_parse_failed")

        # Set explicit status based on parsing outcomes
        if "body_parse_failed" in parsing_issues:
            post.status = ContentStatus.PARTIAL
        elif "platform_parse_failed" in parsing_issues:
            post.status = ContentStatus.PARTIAL

        return post

    def _parse_hooks(self, raw: str) -> list[HookOption]:
        """Parse hook output from raw string."""
        import json
        hooks = []
        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)
            hooks.extend(HookOption(
                variant=h.get("variant", 1),
                hook_text=h.get("hook_text", ""),
                hook_type=h.get("hook_type", "statement"),
                engagement_score=float(h.get("engagement_score", 5.0)),
            ) for h in data.get("hooks", []))
        except (json.JSONDecodeError, ValueError):
            hooks.append(HookOption(
                variant=1,
                hook_text=str(raw)[:200],
                hook_type="statement",
                engagement_score=5.0,
            ))
        return hooks

    def _parse_titles(self, raw: str) -> list[TitleOption]:
        """Parse title output from raw string."""
        import json
        titles = []
        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)
            titles.extend(TitleOption(
                variant=t.get("variant", 1),
                title=t.get("title", ""),
                style=t.get("style", "curiosity"),
                click_score=float(t.get("click_score", 5.0)),
                seo_score=float(t.get("seo_score", 5.0)),
            ) for t in data.get("titles", []))
        except (json.JSONDecodeError, ValueError):
            titles.append(TitleOption(
                variant=1,
                title=str(raw)[:100],
                style="curiosity",
                click_score=5.0,
                seo_score=5.0,
            ))
        return titles

    def _parse_body(self, raw: str) -> "BodyContent":
        """Parse body output from raw string."""
        import json
        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)
            return BodyContent(
                body=data.get("body", str(raw)),
                word_count=int(data.get("word_count", len(str(raw)) // 4)),
                outline=data.get("outline", []),
                sections=data.get("sections", []),
            )
        except (json.JSONDecodeError, ValueError):
            return BodyContent(
                body=str(raw),
                word_count=len(str(raw)) // 4,
                outline=[],
                sections=[],
            )

    def _parse_seo(self, raw: str) -> SEOData | None:
        """Parse SEO output from raw string."""
        import json
        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)
            return SEOData(
                keywords=data.get("keywords", []),
                meta_description=data.get("meta_description", ""),
                tags=data.get("tags", []),
                reading_time_minutes=int(data.get("reading_time_minutes", 5)),
                word_count=int(data.get("word_count", 0)),
            )
        except (json.JSONDecodeError, ValueError, KeyError):
            return None

    def _parse_thumbnails(self, raw: str) -> list[ThumbnailConcept]:
        """Parse thumbnail output from raw string."""
        import json
        thumbnails = []
        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)
            thumbnails.extend(ThumbnailConcept(
                variant=t.get("variant", 1),
                concept=t.get("concept", ""),
                suggested_elements=t.get("suggested_elements", []),
                color_scheme=t.get("color_scheme", ""),
                text_overlay=t.get("text_overlay"),
            ) for t in data.get("thumbnails", []))
        except (json.JSONDecodeError, ValueError):
            thumbnails.append(ThumbnailConcept(
                variant=1,
                concept=str(raw)[:200],
                suggested_elements=[],
                color_scheme="",
            ))
        return thumbnails

    def _parse_platform_output(self, raw: str) -> dict[str, PlatformContent]:
        """Parse platform adaptation output from raw string."""
        import json
        import logging
        platform_contents = {}
        logger = logging.getLogger(__name__)

        try:
            text = str(raw)
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "{" in text:
                start = text.find("{")
                end = text.rfind("}") + 1
                text = text[start:end]
            data = json.loads(text)

            # Handle both dict format ({"wechat": {...}, "medium": {...}}) and array format
            if isinstance(data, dict):
                for platform_name, platform_data in data.items():
                    if isinstance(platform_data, dict):
                        platform_contents[platform_name] = PlatformContent(
                            platform=platform_data.get("platform", platform_name),
                            title=platform_data.get("title", ""),
                            body=platform_data.get("body", ""),
                            excerpt=platform_data.get("excerpt"),
                            tags=platform_data.get("tags", []),
                            category=platform_data.get("category"),
                            cover_image_suggestion=platform_data.get("cover_image_suggestion"),
                        )
            elif isinstance(data, list):
                # Some agents return a list of platform contents
                for item in data:
                    if isinstance(item, dict) and "platform" in item:
                        platform_name = item["platform"]
                        platform_contents[platform_name] = PlatformContent(
                            platform=platform_name,
                            title=item.get("title", ""),
                            body=item.get("body", ""),
                            excerpt=item.get("excerpt"),
                            tags=item.get("tags", []),
                            category=item.get("category"),
                            cover_image_suggestion=item.get("cover_image_suggestion"),
                        )
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"平台适配输出解析失败: {e}, raw length: {len(raw)}")
        return platform_contents

    def generate_hooks(self) -> list[HookOption]:
        """单独生成钩子（不运行完整Crew）"""
        agent = self._get_hook_agent()
        return agent.generate_hooks(self._blog_config.topic)

    def generate_titles(self, hooks: list[HookOption] = None) -> list[TitleOption]:
        """单独生成标题（不运行完整Crew）

        Filters results by self._blog_config.title_style if set.
        """
        agent = self._get_title_agent()
        hook_texts = "\n".join([h.hook_text for h in hooks]) if hooks else ""
        topic_with_hooks = f"{self._blog_config.topic}\n参考钩子:\n{hook_texts}" if hooks else self._blog_config.topic
        all_titles = agent.generate_titles(
            topic=topic_with_hooks,
            include_keywords=self._blog_config.include_keywords
        )

        # Filter by title_style if specified and not default
        style = self._blog_config.title_style
        if style and style != TitleStyle.SEO.value:
            # Map CLI style names to TitleOption.style values
            style_map = {
                "clickbait": TitleStyle.SENSATIONAL.value,
                "technical": TitleStyle.LIST.value,
                TitleStyle.SEO.value: None,
                TitleStyle.SENSATIONAL.value: TitleStyle.SENSATIONAL.value,
                TitleStyle.CURIOSITY.value: TitleStyle.CURIOSITY.value,
                TitleStyle.LIST.value: TitleStyle.LIST.value,
                TitleStyle.GUIDE.value: TitleStyle.GUIDE.value,
                TitleStyle.QUESTION.value: TitleStyle.QUESTION.value,
                TitleStyle.NUMBER.value: TitleStyle.NUMBER.value,
            }
            target = style_map.get(style, style)
            if target:
                filtered = [t for t in all_titles if t.style == target]
                if filtered:
                    return filtered
        return all_titles

    def optimize_seo(
        self,
        title: str,
        body: str = ""
    ) -> SEOData:
        """单独进行SEO优化"""
        agent = self._get_seo_agent()
        return agent.optimize(
            topic=self._blog_config.topic,
            title=title,
            body=body,
            target_keywords=self._blog_config.include_keywords,
            platform=self._blog_config.target_platforms[0] if self._blog_config.target_platforms else "general"
        )

    def generate_thumbnails(
        self,
        title: str
    ) -> list[ThumbnailConcept]:
        """单独生成缩略图概念"""
        agent = self._get_thumbnail_agent()
        return agent.generate_concepts(
            topic=self._blog_config.topic,
            title=title
        )

    def adapt_platforms(
        self,
        title: str,
        body: str,
        seo_tags: list[str] = None
    ) -> dict[str, PlatformContent]:
        """单独进行平台适配"""
        agent = self._get_platform_agent()
        return agent.adapt_multiple(
            topic=self._blog_config.topic,
            title=title,
            body=body,
            platforms=self._blog_config.target_platforms,
            seo_tags=seo_tags or self._blog_config.include_keywords
        )

    def _get_hook_agent(self) -> HookAgent:
        if self._hook_agent is None:
            agents = self.agents
            self._hook_agent = agents["hook_agent"]
        return self._hook_agent

    def _get_title_agent(self) -> TitleAgent:
        if self._title_agent is None:
            agents = self.agents
            self._title_agent = agents["title_agent"]
        return self._title_agent

    def _get_thumbnail_agent(self) -> ThumbnailConceptAgent:
        if self._thumbnail_agent is None:
            agents = self.agents
            self._thumbnail_agent = agents["thumbnail_agent"]
        return self._thumbnail_agent

    def _get_seo_agent(self) -> SEOAgent:
        if self._seo_agent is None:
            agents = self.agents
            self._seo_agent = agents["seo_agent"]
        return self._seo_agent

    def _get_platform_agent(self) -> PlatformAdapterAgent:
        if self._platform_agent is None:
            agents = self.agents
            self._platform_agent = agents["platform_agent"]
        return self._platform_agent

    @property
    def agents_dict(self) -> dict[str, Any]:
        """获取Agents字典（兼容属性）"""
        return self.agents


__all__ = ["BlogCrew", "BlogCrewConfig"]
