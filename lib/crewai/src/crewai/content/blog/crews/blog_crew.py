"""BlogCrew - 博客内容生成主编排"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from crewai.content.base import BaseContentCrew
from crewai.content.blog.agents import (
    HookAgent,
    PlatformAdapterAgent,
    SEOAgent,
    ThumbnailConceptAgent,
    TitleAgent,
)
from crewai.content.blog.blog_types import (
    BlogCrewOutput,
    BlogPost,
    HookOption,
    PlatformContent,
    SEOData,
    ThumbnailConcept,
    TitleOption,
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


class BlogCrew(BaseContentCrew):
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
        3. 生成正文 (由LLM直接生成，这里简化处理)
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
        title_task = Task(
            description=f"基于钩子为主题 '{self._blog_config.topic}' 生成5个标题",
            expected_output="5个标题变体，包含风格和评分",
            agent=agents["title_agent"].agent,
            context=[hook_task],
            async_execution=False,
        )
        tasks.append(title_task)

        # Task 3: SEO优化
        seo_task = Task(
            description=f"为 '{self._blog_config.topic}' 进行SEO优化",
            expected_output="关键词、Meta描述、标签等SEO数据",
            agent=agents["seo_agent"].agent,
            context=[title_task],
            async_execution=False,
        )
        tasks.append(seo_task)

        # Task 4: 缩略图概念
        thumbnail_task = Task(
            description=f"为 '{self._blog_config.topic}' 生成3个缩略图概念",
            expected_output="3个缩略图视觉概念",
            agent=agents["thumbnail_agent"].agent,
            context=[title_task],
            async_execution=False,
        )
        tasks.append(thumbnail_task)

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
        import time
        start = time.time()

        try:
            crew_output = super().kickoff()
        except Exception as e:
            raise ContentGenerationError(f"BlogCrew执行失败: {e!s}") from e

        execution_time = time.time() - start

        # 构建BlogPost
        post = self._build_blog_post(crew_output.content)

        # 构建最终输出
        return BlogCrewOutput(
            post=post,
            tasks_completed=crew_output.tasks_completed,
            execution_time=execution_time,
            metadata={
                "topic": self._blog_config.topic,
                "target_platforms": self._blog_config.target_platforms,
                "config": self._blog_config.__dict__,
            }
        )

    def _build_blog_post(self, crew_content: Any) -> BlogPost:
        """构建博客文章对象"""
        # 解析crew_content构建post
        # 这里需要根据实际crew输出结构调整
        post = BlogPost(
            original_topic=self._blog_config.topic,
            title="",  # 将在后续从content解析
            hooks=[],
            body="",
        )

        # 如果content是字典或字符串，进行解析
        if isinstance(crew_content, dict):
            post.title = crew_content.get("title", self._blog_config.topic)
            post.body = crew_content.get("body", "")
        elif isinstance(crew_content, str):
            post.title = self._blog_config.topic
            post.body = crew_content

        return post

    def generate_hooks(self) -> list[HookOption]:
        """单独生成钩子（不运行完整Crew）"""
        agent = self._get_hook_agent()
        return agent.generate_hooks(self._blog_config.topic)

    def generate_titles(self, hooks: list[HookOption] = None) -> list[TitleOption]:
        """单独生成标题（不运行完整Crew）"""
        agent = self._get_title_agent()
        hook_texts = "\n".join([h.hook_text for h in hooks]) if hooks else ""
        topic_with_hooks = f"{self._blog_config.topic}\n参考钩子:\n{hook_texts}" if hooks else self._blog_config.topic
        return agent.generate_titles(
            topic=topic_with_hooks,
            include_keywords=self._blog_config.include_keywords
        )

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
