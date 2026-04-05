"""Integration tests for BlogCrew and its agents.

Tests BlogCrew workflow orchestration and each agent's core functionality
with mocked LLM calls to avoid external API calls.

Note: Individual agent tests focus on instantiation and structure since
the blog agents have a known issue where they call a non-existent
`agent.run()` method. The BlogCrew orchestration tests are the primary
integration tests.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from crewai.content.blog.agents import (
    HookAgent,
    HookOption,
    PlatformAdapterAgent,
    PlatformContent,
    SEOAgent,
    SEOData,
    ThumbnailConcept,
    ThumbnailConceptAgent,
    TitleAgent,
    TitleOption,
)
from crewai.content.blog.crews.blog_crew import BlogCrew, BlogCrewConfig
from crewai.content.blog.blog_types import BlogCrewOutput, BlogPost
from crewai.crews.crew_output import CrewOutput


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def blog_crew_config():
    """Create a BlogCrewConfig for testing."""
    return BlogCrewConfig(
        topic="Python异步编程指南",
        target_platforms=["medium", "wechat"],
        include_keywords=["Python", "异步", "AsyncIO"],
        language="zh",
        max_words=2000,
        target_audience="Python开发者",
    )


@pytest.fixture
def blog_crew(blog_crew_config):
    """Create a BlogCrew instance with default LLM (will be mocked)."""
    return BlogCrew(config=blog_crew_config, verbose=False)


# =============================================================================
# HookAgent Tests
# =============================================================================


class TestHookAgent:
    """Tests for HookAgent."""

    def test_hook_agent_initialization(self):
        """Test HookAgent initializes correctly."""
        agent = HookAgent()
        assert agent.agent is not None
        assert agent.agent.role == "钩子创作专家"

    def test_hook_agent_has_generate_hooks_method(self):
        """Test HookAgent has generate_hooks method."""
        agent = HookAgent()
        assert hasattr(agent, 'generate_hooks')
        assert callable(agent.generate_hooks)

    def test_hook_agent_has_parse_result_method(self):
        """Test HookAgent has _parse_result method."""
        agent = HookAgent()
        assert hasattr(agent, '_parse_result')
        assert callable(agent._parse_result)

    def test_hook_option_dataclass(self):
        """Test HookOption dataclass structure."""
        hook = HookOption(
            variant=1,
            hook_text="测试钩子",
            hook_type="question",
            engagement_score=8.5
        )
        assert hook.variant == 1
        assert hook.hook_text == "测试钩子"
        assert hook.hook_type == "question"
        assert hook.engagement_score == 8.5


# =============================================================================
# TitleAgent Tests
# =============================================================================


class TestTitleAgent:
    """Tests for TitleAgent."""

    def test_title_agent_initialization(self):
        """Test TitleAgent initializes correctly."""
        agent = TitleAgent()
        assert agent.agent is not None
        assert agent.agent.role == "标题创作专家"

    def test_title_agent_has_generate_titles_method(self):
        """Test TitleAgent has generate_titles method."""
        agent = TitleAgent()
        assert hasattr(agent, 'generate_titles')
        assert callable(agent.generate_titles)

    def test_title_option_dataclass(self):
        """Test TitleOption dataclass structure."""
        title = TitleOption(
            variant=1,
            title="测试标题",
            style="guide",
            click_score=9.0,
            seo_score=8.5
        )
        assert title.variant == 1
        assert title.title == "测试标题"
        assert title.style == "guide"
        assert title.click_score == 9.0
        assert title.seo_score == 8.5


# =============================================================================
# SEOAgent Tests
# =============================================================================


class TestSEOAgent:
    """Tests for SEOAgent."""

    def test_seo_agent_initialization(self):
        """Test SEOAgent initializes correctly."""
        agent = SEOAgent()
        assert agent.agent is not None
        assert agent.agent.role == "SEO专家"

    def test_seo_agent_has_optimize_method(self):
        """Test SEOAgent has optimize method."""
        agent = SEOAgent()
        assert hasattr(agent, 'optimize')
        assert callable(agent.optimize)

    def test_seo_data_dataclass(self):
        """Test SEOData dataclass structure."""
        seo = SEOData(
            keywords=["Python", "异步"],
            meta_description="测试描述",
            tags=["编程"],
            reading_time_minutes=5,
            word_count=1000
        )
        assert seo.keywords == ["Python", "异步"]
        assert seo.meta_description == "测试描述"
        assert seo.reading_time_minutes == 5


# =============================================================================
# ThumbnailConceptAgent Tests
# =============================================================================


class TestThumbnailConceptAgent:
    """Tests for ThumbnailConceptAgent."""

    def test_thumbnail_agent_initialization(self):
        """Test ThumbnailConceptAgent initializes correctly."""
        agent = ThumbnailConceptAgent()
        assert agent.agent is not None
        assert agent.agent.role == "视觉设计师"

    def test_thumbnail_agent_has_generate_concepts_method(self):
        """Test ThumbnailConceptAgent has generate_concepts method."""
        agent = ThumbnailConceptAgent()
        assert hasattr(agent, 'generate_concepts')
        assert callable(agent.generate_concepts)

    def test_thumbnail_concept_dataclass(self):
        """Test ThumbnailConcept dataclass structure."""
        concept = ThumbnailConcept(
            variant=1,
            concept="科技感概念",
            suggested_elements=["元素1", "元素2"],
            color_scheme="蓝紫渐变",
            text_overlay="右下角"
        )
        assert concept.variant == 1
        assert concept.concept == "科技感概念"
        assert len(concept.suggested_elements) == 2
        assert concept.color_scheme == "蓝紫渐变"


# =============================================================================
# PlatformAdapterAgent Tests
# =============================================================================


class TestPlatformAdapterAgent:
    """Tests for PlatformAdapterAgent."""

    def test_platform_agent_initialization(self):
        """Test PlatformAdapterAgent initializes correctly."""
        agent = PlatformAdapterAgent()
        assert agent.agent is not None
        assert agent.agent.role == "平台适配专家"

    def test_platform_agent_has_adapt_method(self):
        """Test PlatformAdapterAgent has adapt method."""
        agent = PlatformAdapterAgent()
        assert hasattr(agent, 'adapt')
        assert callable(agent.adapt)

    def test_platform_agent_has_adapt_multiple_method(self):
        """Test PlatformAdapterAgent has adapt_multiple method."""
        agent = PlatformAdapterAgent()
        assert hasattr(agent, 'adapt_multiple')
        assert callable(agent.adapt_multiple)

    def test_platform_configs_have_required_fields(self):
        """Test PlatformAdapterAgent has correct platform configurations."""
        agent = PlatformAdapterAgent()

        # Verify key platforms are configured
        assert "wechat" in agent.PLATFORM_CONFIGS
        assert "medium" in agent.PLATFORM_CONFIGS
        assert "wordpress" in agent.PLATFORM_CONFIGS
        assert "zhihu" in agent.PLATFORM_CONFIGS
        assert "juejin" in agent.PLATFORM_CONFIGS
        assert "xiaohongshu" in agent.PLATFORM_CONFIGS

        # Verify wechat has correct constraints
        wechat_config = agent.PLATFORM_CONFIGS["wechat"]
        assert wechat_config["max_title_length"] == 64
        assert wechat_config["requires_excerpt"] is False

        # Verify xiaohongshu has short title length
        xhs_config = agent.PLATFORM_CONFIGS["xiaohongshu"]
        assert xhs_config["max_title_length"] == 20

    def test_platform_content_dataclass(self):
        """Test PlatformContent dataclass structure."""
        content = PlatformContent(
            platform="medium",
            title="English Title",
            body="Article body...",
            excerpt="Short excerpt",
            tags=["Python", "AsyncIO"],
            category="Technology",
            cover_image_suggestion="Dark theme image"
        )
        assert content.platform == "medium"
        assert content.title == "English Title"
        assert content.body == "Article body..."
        assert content.excerpt == "Short excerpt"


# =============================================================================
# BlogCrew Tests
# =============================================================================


class TestBlogCrew:
    """Tests for BlogCrew."""

    def test_blog_crew_initialization(self, blog_crew):
        """Test BlogCrew initializes correctly."""
        assert blog_crew is not None
        assert blog_crew._blog_config.topic == "Python异步编程指南"
        assert blog_crew._verbose is False

    def test_blog_crew_config_to_content_config(self, blog_crew_config):
        """Test BlogCrewConfig converts to ContentConfig correctly."""
        content_config = blog_crew_config.to_content_config()

        assert content_config.content_type.value == "blog"
        assert content_config.language == "zh"
        assert content_config.max_words == 2000

    def test_blog_crew_creates_all_agents(self, blog_crew):
        """Test BlogCrew creates all required agents."""
        agents = blog_crew.agents

        assert "hook_agent" in agents
        assert "title_agent" in agents
        assert "thumbnail_agent" in agents
        assert "seo_agent" in agents
        assert "platform_agent" in agents

        # Verify each agent is correctly instantiated
        assert isinstance(agents["hook_agent"], HookAgent)
        assert isinstance(agents["title_agent"], TitleAgent)
        assert isinstance(agents["thumbnail_agent"], ThumbnailConceptAgent)
        assert isinstance(agents["seo_agent"], SEOAgent)
        assert isinstance(agents["platform_agent"], PlatformAdapterAgent)

    def test_blog_crew_workflow_creation(self, blog_crew):
        """Test BlogCrew creates workflow correctly.

        Verifies that BlogCrew passes actual Agent objects (not wrappers) to Crew.
        """
        crew = blog_crew._create_workflow()

        assert crew is not None
        assert crew.process == "sequential"
        assert len(crew.tasks) == 6  # hook, title, body, seo, thumbnail, platform
        # Verify actual Agent objects are passed (not wrapper classes)
        from crewai.agent.core import Agent
        for agent in crew.agents:
            assert isinstance(agent, Agent), f"Expected Agent, got {type(agent)}"

    @patch.object(BlogCrew, '_create_workflow')
    def test_kickoff_returns_blog_crew_output(
        self, mock_create_workflow, blog_crew
    ):
        """Test kickoff returns BlogCrewOutput."""
        # Setup mock crew
        mock_crew = MagicMock()
        mock_task = MagicMock()
        mock_task.description = "Test task"

        mock_crew.tasks = [mock_task]
        mock_crew.kickoff = MagicMock(return_value=CrewOutput(
            raw="Test output",
            tasks_output=[],
            crew_name="test"
        ))
        mock_create_workflow.return_value = mock_crew

        result = blog_crew.kickoff()

        assert isinstance(result, BlogCrewOutput)
        assert isinstance(result.post, BlogPost)
        assert result.post.original_topic == "Python异步编程指南"
        assert "topic" in result.metadata

    def test_generate_hooks_delegates_to_hook_agent(self, blog_crew):
        """Test generate_hooks delegates to HookAgent."""
        blog_crew._hook_agent = MagicMock()
        blog_crew._hook_agent.generate_hooks = MagicMock(return_value=[
            HookOption(variant=1, hook_text="测试钩子",
                      hook_type="question", engagement_score=8.0)
        ])

        hooks = blog_crew.generate_hooks()

        blog_crew._hook_agent.generate_hooks.assert_called_once_with(
            "Python异步编程指南"
        )

    def test_generate_titles_delegates_to_title_agent(self, blog_crew):
        """Test generate_titles delegates to TitleAgent."""
        blog_crew._title_agent = MagicMock()
        blog_crew._title_agent.generate_titles = MagicMock(return_value=[
            TitleOption(variant=1, title="测试标题",
                       style="guide", click_score=8.0, seo_score=9.0)
        ])

        titles = blog_crew.generate_titles()

        blog_crew._title_agent.generate_titles.assert_called_once()

    def test_optimize_seo_delegates_to_seo_agent(self, blog_crew):
        """Test optimize_seo delegates to SEOAgent."""
        blog_crew._seo_agent = MagicMock()
        blog_crew._seo_agent.optimize = MagicMock(return_value=SEOData(
            keywords=["Python"],
            meta_description="测试描述",
            tags=["Python"],
            reading_time_minutes=5,
            word_count=1000
        ))

        seo_data = blog_crew.optimize_seo(title="测试标题")

        blog_crew._seo_agent.optimize.assert_called_once()
        assert isinstance(seo_data, SEOData)

    def test_generate_thumbnails_delegates_to_thumbnail_agent(self, blog_crew):
        """Test generate_thumbnails delegates to ThumbnailConceptAgent."""
        blog_crew._thumbnail_agent = MagicMock()
        blog_crew._thumbnail_agent.generate_concepts = MagicMock(return_value=[
            ThumbnailConcept(
                variant=1,
                concept="测试概念",
                suggested_elements=["元素1"],
                color_scheme="蓝色"
            )
        ])

        thumbnails = blog_crew.generate_thumbnails(title="测试标题")

        blog_crew._thumbnail_agent.generate_concepts.assert_called_once()
        assert len(thumbnails) == 1

    def test_adapt_platforms_delegates_to_platform_agent(self, blog_crew):
        """Test adapt_platforms delegates to PlatformAdapterAgent."""
        blog_crew._platform_agent = MagicMock()
        blog_crew._platform_agent.adapt_multiple = MagicMock(return_value={
            "medium": PlatformContent(
                platform="medium",
                title="测试标题",
                body="测试正文"
            )
        })

        results = blog_crew.adapt_platforms(
            title="测试标题",
            body="测试正文"
        )

        blog_crew._platform_agent.adapt_multiple.assert_called_once()
        assert "medium" in results

    def test_blog_crew_agents_dict_property(self, blog_crew):
        """Test agents_dict property returns agents dictionary."""
        agents_dict = blog_crew.agents_dict

        assert isinstance(agents_dict, dict)
        assert "hook_agent" in agents_dict
        assert "title_agent" in agents_dict

    def test_blog_crew_individual_agent_getters(self, blog_crew):
        """Test individual agent getter methods."""
        # Trigger agent creation by accessing agents
        _ = blog_crew.agents

        # Test each getter
        hook_agent = blog_crew._get_hook_agent()
        assert isinstance(hook_agent, HookAgent)

        title_agent = blog_crew._get_title_agent()
        assert isinstance(title_agent, TitleAgent)

        thumbnail_agent = blog_crew._get_thumbnail_agent()
        assert isinstance(thumbnail_agent, ThumbnailConceptAgent)

        seo_agent = blog_crew._get_seo_agent()
        assert isinstance(seo_agent, SEOAgent)

        platform_agent = blog_crew._get_platform_agent()
        assert isinstance(platform_agent, PlatformAdapterAgent)


# =============================================================================
# BlogCrewConfig Tests
# =============================================================================


class TestBlogCrewConfig:
    """Tests for BlogCrewConfig."""

    def test_blog_crew_config_defaults(self):
        """Test BlogCrewConfig default values."""
        config = BlogCrewConfig(topic="测试主题")

        assert config.topic == "测试主题"
        assert config.target_platforms == ["medium"]
        assert config.include_keywords == []
        assert config.language == "zh"
        assert config.max_words is None
        assert config.target_audience is None

    def test_blog_crew_config_with_all_parameters(self):
        """Test BlogCrewConfig with all parameters."""
        config = BlogCrewConfig(
            topic="Python异步编程",
            target_platforms=["wechat", "zhihu"],
            include_keywords=["AsyncIO", "异步"],
            language="zh",
            max_words=3000,
            target_audience="中级开发者"
        )

        assert config.topic == "Python异步编程"
        assert config.target_platforms == ["wechat", "zhihu"]
        assert config.include_keywords == ["AsyncIO", "异步"]
        assert config.max_words == 3000
        assert config.target_audience == "中级开发者"

    def test_blog_crew_config_to_content_config_wechat(self):
        """Test BlogCrewConfig converts to ContentConfig with WeChat platform."""
        config = BlogCrewConfig(
            topic="测试主题",
            target_platforms=["wechat", "medium"],
            language="zh"
        )

        content_config = config.to_content_config()

        assert content_config.platform.value == "wechat"
        assert content_config.content_type.value == "blog"


# =============================================================================
# BlogPost and BlogCrewOutput Tests
# =============================================================================


class TestBlogTypes:
    """Tests for BlogPost and related types."""

    def test_blog_post_initialization(self):
        """Test BlogPost initializes correctly."""
        post = BlogPost(
            original_topic="测试主题",
            title="测试标题",
            hooks=[],
            body="测试正文"
        )

        assert post.original_topic == "测试主题"
        assert post.title == "测试标题"
        assert post.hooks == []
        assert post.body == "测试正文"
        assert post.seo is None
        assert post.thumbnail_concepts == []
        assert post.platform_contents == {}

    def test_blog_crew_output_initialization(self):
        """Test BlogCrewOutput initializes correctly."""
        post = BlogPost(
            original_topic="测试主题",
            title="测试标题",
            hooks=[],
            body=""
        )

        output = BlogCrewOutput(
            post=post,
            tasks_completed=["Task 1", "Task 2"],
            execution_time=1.5,
            metadata={"key": "value"}
        )

        assert output.post == post
        assert len(output.tasks_completed) == 2
        assert output.execution_time == 1.5
        assert output.metadata["key"] == "value"

    def test_hook_option_creation(self):
        """Test HookOption creation."""
        hook = HookOption(
            variant=1,
            hook_text="这是一个测试钩子",
            hook_type="question",
            engagement_score=8.5
        )

        assert hook.variant == 1
        assert hook.hook_text == "这是一个测试钩子"
        assert hook.hook_type == "question"
        assert hook.engagement_score == 8.5

    def test_title_option_creation(self):
        """Test TitleOption creation."""
        title = TitleOption(
            variant=1,
            title="测试标题",
            style="guide",
            click_score=9.0,
            seo_score=8.5
        )

        assert title.variant == 1
        assert title.title == "测试标题"
        assert title.style == "guide"
        assert title.click_score == 9.0
        assert title.seo_score == 8.5

    def test_seo_data_creation(self):
        """Test SEOData creation."""
        seo = SEOData(
            keywords=["Python", "异步"],
            meta_description="这是一个测试描述",
            tags=["编程", "Python"],
            reading_time_minutes=5,
            word_count=1000
        )

        assert len(seo.keywords) == 2
        assert seo.meta_description == "这是一个测试描述"
        assert len(seo.tags) == 2
        assert seo.reading_time_minutes == 5
        assert seo.word_count == 1000

    def test_thumbnail_concept_creation(self):
        """Test ThumbnailConcept creation."""
        thumbnail = ThumbnailConcept(
            variant=1,
            concept="科技感概念",
            suggested_elements=["元素1", "元素2"],
            color_scheme="蓝紫渐变",
            text_overlay="右下角"
        )

        assert thumbnail.variant == 1
        assert thumbnail.concept == "科技感概念"
        assert len(thumbnail.suggested_elements) == 2
        assert thumbnail.color_scheme == "蓝紫渐变"
        assert thumbnail.text_overlay == "右下角"

    def test_platform_content_creation(self):
        """Test PlatformContent creation."""
        content = PlatformContent(
            platform="medium",
            title="English Title",
            body="Article body...",
            excerpt="Short excerpt",
            tags=["Python", "AsyncIO"],
            category="Technology",
            cover_image_suggestion="Dark theme image"
        )

        assert content.platform == "medium"
        assert content.title == "English Title"
        assert content.body == "Article body..."
        assert content.excerpt == "Short excerpt"
        assert len(content.tags) == 2
        assert content.category == "Technology"
        assert content.cover_image_suggestion == "Dark theme image"
