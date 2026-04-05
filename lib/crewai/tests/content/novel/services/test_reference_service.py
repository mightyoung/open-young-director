"""Tests for ReferenceService."""

from unittest.mock import MagicMock, patch

import pytest

from crewai.content.novel.services.reference_service import ReferenceService
from crewai.content.novel.agents.reference_agent import ReferenceSkeleton


class TestReferenceService:
    """Tests for ReferenceService."""

    def test_init_default(self):
        """Test initialization with defaults."""
        service = ReferenceService()
        assert service.llm is None
        assert service.verbose is True
        assert service._search_tool is None
        assert service._reference_agent is None

    def test_init_with_llm(self):
        """Test initialization with custom LLM."""
        mock_llm = MagicMock()
        service = ReferenceService(llm=mock_llm, verbose=False)
        assert service.llm is mock_llm
        assert service.verbose is False

    def test_search_tool_lazy_load(self):
        """Test search tool is lazily loaded."""
        service = ReferenceService()
        # Initially None
        assert service._search_tool is None
        # Accessing property should load it
        tool = service.search_tool
        assert tool is not None
        assert service._search_tool is tool

    def test_reference_agent_lazy_load(self):
        """Test reference agent is lazily loaded."""
        service = ReferenceService()
        # Initially None
        assert service._reference_agent is None
        # Accessing property should load it
        agent = service.reference_agent
        assert agent is not None
        assert service._reference_agent is agent

    def test_build_search_queries_basic(self):
        """Test building search queries for basic topic."""
        service = ReferenceService()
        queries = service._build_search_queries("测试主题", "urban")

        assert len(queries) >= 3
        assert any("测试主题" in q for q in queries)
        assert any("urban" in q for q in queries)

    def test_build_search_queries_xuanhuan(self):
        """Test search queries include specific queries for xuanhuan topics."""
        service = ReferenceService()
        queries = service._build_search_queries("西游记", "xianxia")

        assert len(queries) > 3  # Should have additional xiyouji queries
        # Should have xiyouji specific queries
        assert any("西游" in q for q in queries)

    def test_build_search_queries_sanguo(self):
        """Test search queries include specific queries for sanguo topics."""
        service = ReferenceService()
        queries = service._build_search_queries("三国争霸", "historical")

        assert len(queries) > 3
        assert any("三国" in q for q in queries)

    def test_build_search_queries_shuihu(self):
        """Test search queries include specific queries for shuihu topics."""
        service = ReferenceService()
        queries = service._build_search_queries("梁山好汉", "historical")

        assert len(queries) > 3
        assert any("水浒" in q for q in queries)

    def test_build_search_queries_hongloumeng(self):
        """Test search queries include specific queries for hongloumeng topics."""
        service = ReferenceService()
        queries = service._build_search_queries("红楼梦", "classical")

        assert len(queries) > 3
        assert any("红楼" in q for q in queries)

    def test_build_search_queries_fengshen(self):
        """Test search queries include specific queries for fengshen topics."""
        service = ReferenceService()
        queries = service._build_search_queries("封神演义", "xianxia")

        assert len(queries) > 3
        assert any("封神" in q for q in queries)


class TestReferenceServiceSearch:
    """Tests for ReferenceService search functionality."""

    def test_search_references_with_mock_tool(self):
        """Test search references with mock tool."""
        service = ReferenceService()

        # Create a mock search tool
        mock_tool = MagicMock()
        mock_tool._run = MagicMock(return_value="搜索结果: 找到与 '测试' 相关的经典名著")
        service._search_tool = mock_tool

        results = service._search_references("测试", "urban", max_results=3)

        assert len(results) == 3  # Should return 3 results (each query returns same)
        mock_tool._run.assert_called()

    def test_search_references_empty_results(self):
        """Test search with no results."""
        service = ReferenceService()

        # Create a mock tool that returns empty
        mock_tool = MagicMock()
        mock_tool._run = MagicMock(return_value="")
        service._search_tool = mock_tool

        results = service._search_references("测试", "urban", max_results=3)
        assert len(results) == 0

    def test_search_references_handles_exception(self):
        """Test search handles exceptions gracefully."""
        service = ReferenceService()

        # Create a mock tool that raises exception
        mock_tool = MagicMock()
        mock_tool._run = MagicMock(side_effect=Exception("Search failed"))
        service._search_tool = mock_tool

        results = service._search_references("测试", "urban", max_results=3)
        assert len(results) == 0


class TestReferenceServiceFormat:
    """Tests for ReferenceService formatting."""

    def test_format_skeleton_for_prompt_empty(self):
        """Test formatting with empty skeletons."""
        service = ReferenceService()
        result = service.format_skeleton_for_prompt([])
        assert result == ""

    def test_format_skeleton_for_prompt_single(self):
        """Test formatting single skeleton."""
        service = ReferenceService()
        skeleton = ReferenceSkeleton(
            source="《西游记》",
            source_url="",
            theme="取经",
            backbone_plot=["唐僧取经", "孙悟空大闹天宫"],
            character_archetypes=[{"type": "英雄", "description": "孙悟空"}],
            structure_pattern="取经模式",
            key_conflicts=["妖魔阻挡"],
            growth_arc="从叛逆到皈依",
            style_elements=["仙侠"],
        )

        result = service.format_skeleton_for_prompt([skeleton])

        assert "《西游记》" in result
        assert "取经" in result
        assert "取经模式" in result
        assert "唐僧取经" in result
        assert "孙悟空" in result

    def test_format_skeleton_for_prompt_multiple(self):
        """Test formatting multiple skeletons."""
        service = ReferenceService()
        skeletons = [
            ReferenceSkeleton(
                source="《西游记》",
                source_url="",
                theme="取经",
                backbone_plot=["情节1"],
                character_archetypes=[],
                structure_pattern="取经",
                key_conflicts=[],
                growth_arc="",
                style_elements=[],
            ),
            ReferenceSkeleton(
                source="《三国演义》",
                source_url="",
                theme="争霸",
                backbone_plot=["情节1"],
                character_archetypes=[],
                structure_pattern="争霸",
                key_conflicts=[],
                growth_arc="",
                style_elements=[],
            ),
        ]

        result = service.format_skeleton_for_prompt(skeletons)

        assert "《西游记》" in result
        assert "《三国演义》" in result
        assert "参考1:" in result
        assert "参考2:" in result


class TestReferenceServiceIntegration:
    """Integration tests for ReferenceService."""

    def test_research_and_extract_empty_search(self):
        """Test research with empty search results."""
        service = ReferenceService()

        # Mock search to return empty
        with patch.object(service, '_search_references', return_value=[]):
            skeletons = service.research_and_extract("测试主题", "urban")
            assert skeletons == []

    def test_research_and_extract_with_results(self):
        """Test research with search results."""
        service = ReferenceService()

        # Mock search to return results
        with patch.object(service, '_search_references', return_value=["搜索结果1", "搜索结果2"]):
            # Mock reference agent
            mock_skeleton = ReferenceSkeleton(
                source="《测试》",
                source_url="",
                theme="测试",
                backbone_plot=["情节1"],
                character_archetypes=[],
                structure_pattern="测试",
                key_conflicts=[],
                growth_arc="",
                style_elements=[],
            )

            # Patch the internal _reference_agent
            mock_agent = MagicMock()
            mock_agent.extract_skeleton = MagicMock(return_value=mock_skeleton)
            service._reference_agent = mock_agent

            skeletons = service.research_and_extract("测试", "urban")

            assert len(skeletons) == 2
            mock_agent.extract_skeleton.assert_called()

    def test_research_and_extract_handles_extraction_error(self):
        """Test research handles extraction errors gracefully."""
        service = ReferenceService()

        with patch.object(service, '_search_references', return_value=["结果1", "结果2"]):
            # Patch the internal _reference_agent
            mock_skeleton = ReferenceSkeleton(
                source="《测试》",
                source_url="",
                theme="测试",
                backbone_plot=["情节1"],
                character_archetypes=[],
                structure_pattern="测试",
                key_conflicts=[],
                growth_arc="",
                style_elements=[],
            )
            mock_agent = MagicMock()
            mock_agent.extract_skeleton = MagicMock(return_value=mock_skeleton)
            service._reference_agent = mock_agent

            # Should return skeletons even when extraction might fail
            skeletons = service.research_and_extract("测试", "urban")
            assert len(skeletons) == 2
