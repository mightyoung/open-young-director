"""Novel platform crawlers package."""

from .base_crawler import BaseCrawler, ChapterInfo, NovelInfo
from .firecrawl_crawler import FirecrawlCrawler, FirecrawlResponse, FirecrawlBatchCrawler
from .qidian_crawler import QidianCrawler
from .qidian_fanqie import QidianFanqieCrawler
from .qimao_crawler import QimaoCrawler
from .chuangshi_crawler import ChuangshiCrawler
from .biquge_crawler import BiqugeCrawler
from .chuangshi_qq_crawler import ChuangshiqqCrawler


# Registry of available crawlers
CRAWLER_REGISTRY = {
    # Qidian (起点中文网)
    "qidian": QidianCrawler,
    "起点": QidianCrawler,
    "起点中文网": QidianCrawler,
    # Qidian Fanqie (番茄小说网)
    "fanqie": QidianFanqieCrawler,
    "番茄": QidianFanqieCrawler,
    "番茄小说网": QidianFanqieCrawler,
    # Qimao (七猫免费小说)
    "qimao": QimaoCrawler,
    "七猫": QimaoCrawler,
    "七猫免费小说": QimaoCrawler,
    # Chuangshi (创世中文网 - original)
    "chuangshi": ChuangshiCrawler,
    "创世": ChuangshiCrawler,
    "创世中文网": ChuangshiCrawler,
    # Biquge (笔趣阁 - multiple variants)
    "biquge": BiqugeCrawler,
    "笔趣阁": BiqugeCrawler,
    "biquge5200": BiqugeCrawler,
    "biquge520": BiqugeCrawler,
    "笔趣阁520": BiqugeCrawler,
    # Chuangshi QQ (创世中文网 - Tencent)
    "chuangshiqq": ChuangshiqqCrawler,
    "创世QQ": ChuangshiqqCrawler,
    "创世中文网QQ": ChuangshiqqCrawler,
    "chuangshi.qq.com": ChuangshiqqCrawler,
}


def get_crawler(
    platform: str,
    api_key: str | None = None,
    rate_limit_rpm: int = 30,
    logger=None,
):
    """
    Get a crawler instance for the specified platform.

    Args:
        platform: Platform name or key (e.g., "qidian", "fanqie", "qimao", "chuangshi")
        api_key: Firecrawl API key (optional)
        rate_limit_rpm: Rate limit requests per minute
        logger: Optional logger instance

    Returns:
        Crawler instance or None if platform is not supported
    """
    crawler_class = CRAWLER_REGISTRY.get(platform.lower())
    if crawler_class:
        return crawler_class(
            api_key=api_key,
            rate_limit_rpm=rate_limit_rpm,
            logger=logger,
        )
    return None


def list_supported_platforms() -> list[str]:
    """Get list of supported platform names."""
    return list(CRAWLER_REGISTRY.keys())


__all__ = [
    "BaseCrawler",
    "ChapterInfo",
    "NovelInfo",
    "FirecrawlCrawler",
    "FirecrawlResponse",
    "FirecrawlBatchCrawler",
    "QidianCrawler",
    "QidianFanqieCrawler",
    "QimaoCrawler",
    "ChuangshiCrawler",
    "BiqugeCrawler",
    "ChuangshiqqCrawler",
    "CRAWLER_REGISTRY",
    "get_crawler",
    "list_supported_platforms",
]
