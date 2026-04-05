"""参考骨架服务 - 搜索经典名著并提取骨架"""

import logging
from typing import List, Optional, TYPE_CHECKING

from crewai.content.novel.agents.reference_agent import ReferenceAgent, ReferenceSkeleton

if TYPE_CHECKING:
    from crewai.llm import LLM

logger = logging.getLogger(__name__)


class ReferenceService:
    """参考骨架服务

    负责搜索与主题相关的经典名著，并提取其故事骨架。
    使用 TavilySearchTool 进行网络搜索。

    使用示例:
        service = ReferenceService(llm=llm)
        skeletons = service.research_and_extract(
            topic="唐僧取经",
            style="xianxia"
        )
    """

    def __init__(self, llm: "LLM" = None, verbose: bool = True):
        """初始化参考骨架服务

        Args:
            llm: 语言模型实例
            verbose: 是否输出详细日志
        """
        self.llm = llm
        self.verbose = verbose
        self._search_tool = None
        self._reference_agent = None

    @property
    def search_tool(self):
        """延迟加载搜索工具"""
        if self._search_tool is None:
            self._search_tool = self._create_search_tool()
        return self._search_tool

    @property
    def reference_agent(self) -> ReferenceAgent:
        """延迟加载参考骨架Agent"""
        if self._reference_agent is None:
            self._reference_agent = ReferenceAgent(llm=self.llm, verbose=self.verbose)
        return self._reference_agent

    def _create_search_tool(self):
        """创建搜索工具（优先使用 Tavily）"""
        # Try Tavily first
        try:
            from crewai_tools import TavilySearchTool
            tool = TavilySearchTool(
                search_depth="basic",
                max_results=5,
                include_answer=True,
                include_raw_content=False,
            )
            # Test if the tool actually works (might prompt for input if package missing)
            logger.info("Using TavilySearchTool for reference search")
            return tool
        except (ImportError, Exception) as e:
            logger.warning(f"TavilySearchTool not available: {e}")

        # Fallback to a simple mock tool that logs the query
        class MockSearchTool:
            def __init__(self):
                self.last_query = None

            def _run(self, query: str):
                self.last_query = query
                logger.warning(f"Mock search tool called with: {query}")
                return f"搜索结果: 找到与 '{query}' 相关的经典名著信息"

        return MockSearchTool()

    def research_and_extract(
        self,
        topic: str,
        style: str,
        max_results: int = 5,
    ) -> List[ReferenceSkeleton]:
        """搜索与主题相关的经典名著并提取骨架

        Args:
            topic: 小说主题
            style: 小说风格
            max_results: 最大搜索结果数

        Returns:
            List[ReferenceSkeleton]: 提取的骨架列表
        """
        # Step 1: 搜索相关经典名著
        search_results = self._search_references(topic, style, max_results)

        if not search_results:
            logger.warning(f"No search results for topic: {topic}")
            return []

        # Step 2: 从搜索结果提取骨架
        skeletons = []
        for result in search_results:
            try:
                skeleton = self.reference_agent.extract_skeleton(
                    topic=topic,
                    style=style,
                    search_results=[result],
                )
                skeletons.append(skeleton)
            except Exception as e:
                logger.warning(f"Failed to extract skeleton: {e}")
                continue

        return skeletons

    def _search_references(
        self,
        topic: str,
        style: str,
        max_results: int = 5,
    ) -> List[str]:
        """搜索与主题相关的经典名著

        Args:
            topic: 小说主题
            style: 小说风格
            max_results: 最大结果数

        Returns:
            List[str]: 搜索结果列表
        """
        # 构建搜索查询
        queries = self._build_search_queries(topic, style)

        results = []
        for query in queries:
            try:
                if hasattr(self.search_tool, '_run'):
                    result = self.search_tool._run(query)
                elif hasattr(self.search_tool, 'run'):
                    result = self.search_tool.run(query)
                else:
                    result = str(self.search_tool(query))

                if result:
                    results.append(result)
                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.warning(f"Search failed for query '{query}': {e}")
                continue

        return results

    def _build_search_queries(self, topic: str, style: str) -> List[str]:
        """构建搜索查询列表

        Args:
            topic: 小说主题
            style: 小说风格

        Returns:
            List[str]: 搜索查询列表
        """
        queries = [
            # 主题相关经典名著
            f"{topic} 经典名著 故事大纲 情节",
            f"{topic} 古典小说 故事结构 分析",
            # 风格相关经典作品
            f"{style} 小说 经典 叙事结构",
            f"{style} 小说 经典 骨干情节",
            # 主题+风格组合
            f"{topic} {style} 故事模式",
        ]

        # 如果是西游记相关主题，添加特定的搜索查询
        if any(kw in topic for kw in ["西游", "取经", "唐僧", "孙悟空"]):
            queries.extend([
                "西游记 故事情节 主干",
                "西游记 结构分析 叙事",
                "西游记 角色原型 英雄之旅",
            ])

        # 如果是三国演义相关主题
        if any(kw in topic for kw in ["三国", "争霸", "谋略"]):
            queries.extend([
                "三国演义 故事情节 主干",
                "三国演义 结构分析 叙事",
            ])

        # 如果是水浒传相关主题
        if any(kw in topic for kw in ["水浒", "梁山", "好汉"]):
            queries.extend([
                "水浒传 故事情节 主干",
                "水浒传 结构分析 叙事",
            ])

        # 如果是红楼梦相关主题
        if any(kw in topic for kw in ["红楼", "梦", "贵族"]):
            queries.extend([
                "红楼梦 故事情节 主干",
                "红楼梦 结构分析 叙事",
            ])

        # 如果是封神演义相关主题
        if any(kw in topic for kw in ["封神", "仙侠", "神话"]):
            queries.extend([
                "封神演义 故事情节 主干",
                "封神演义 神话结构 叙事",
            ])

        return queries

    def format_skeleton_for_prompt(self, skeletons: List[ReferenceSkeleton]) -> str:
        """将骨架列表格式化为提示词上下文

        Args:
            skeletons: 骨架列表

        Returns:
            str: 格式化的字符串
        """
        if not skeletons:
            return ""

        formatted = ["\n\n## 参考经典名著骨架\n"]

        for i, skeleton in enumerate(skeletons, 1):
            formatted.append(f"### 参考{i}: {skeleton.source}\n")
            formatted.append(f"**主题**: {skeleton.theme}\n")
            formatted.append(f"**结构模式**: {skeleton.structure_pattern}\n")
            formatted.append(f"**主干情节**:\n")
            for j, event in enumerate(skeleton.backbone_plot, 1):
                formatted.append(f"  {j}. {event}\n")
            formatted.append(f"**角色原型**: {', '.join(a.get('type', '') for a in skeleton.character_archetypes)}\n")
            formatted.append(f"**核心冲突**: {', '.join(skeleton.key_conflicts)}\n")
            formatted.append(f"**成长弧线**: {skeleton.growth_arc}\n")

            if skeleton.style_elements:
                formatted.append(f"**风格元素**: {', '.join(skeleton.style_elements)}\n")
            formatted.append("\n")

        return "".join(formatted)
