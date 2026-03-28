#!/usr/bin/env python3
"""
Main entry point for the novel knowledge base crawler.

Usage:
    python run.py                           # Crawl all targets from config
    python run.py --url <url>              # Crawl a single novel
    python run.py --platform qidian         # Crawl using specific platform
    python run.py --list-platforms         # List supported platforms
    python run.py --stats                  # Show storage statistics
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add the knowledge_base directory to sys.path for local imports
# This allows running as a script from the knowledge_base directory
_script_dir = Path(__file__).parent.absolute()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from config import get_config, CrawlerConfig, NovelTarget
from crawlers import (
    get_crawler,
    list_supported_platforms,
    BaseCrawler,
    NovelInfo,
)
from storage import NovelStorage, ChapterCache
from research import NovelResearcher, get_researcher


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("novel_crawler")


def crawl_novel(
    url: str,
    platform: str,
    config: CrawlerConfig,
    storage: NovelStorage,
    cache: Optional[ChapterCache] = None,
    max_chapters: Optional[int] = None,
    start_chapter: int = 1,
    save_individually: bool = False,
    use_fallback: bool = True,
) -> bool:
    """
    Crawl a single novel with fallback research.

    Args:
        url: Novel URL
        platform: Platform name
        config: Crawler configuration
        storage: Storage handler
        cache: Optional chapter cache
        max_chapters: Maximum chapters to crawl
        start_chapter: Starting chapter number
        save_individually: Whether to save chapters individually
        use_fallback: Whether to use research fallback if crawl fails

    Returns:
        True if successful (crawl or research), False otherwise
    """
    logger = logging.getLogger("novel_crawler.crawl")

    # Get crawler for platform
    crawler = get_crawler(
        platform=platform,
        api_key=config.firecrawl.api_key,
        rate_limit_rpm=config.firecrawl.rate_limit_requests_per_minute,
        logger=logger,
    )

    if not crawler:
        logger.error(f"Unsupported platform: {platform}")
        logger.info(f"Supported platforms: {list_supported_platforms()}")
        return False

    # Check cache for already crawled chapters
    chapters_to_skip = set()
    if cache:
        chapters = crawler.extract_chapters(url) if hasattr(crawler, 'extract_chapters') else []
        for ch in chapters:
            if cache.has_cached(ch.url):
                chapters_to_skip.add(ch.url)
                logger.debug(f"Skipping cached chapter: {ch.title}")

    # Crawl novel
    logger.info(f"Starting crawl: {url}")
    logger.info(f"Platform: {platform}")
    if max_chapters:
        logger.info(f"Max chapters: {max_chapters}")

    novel_info = crawler.crawl_novel(
        url=url,
        max_chapters=max_chapters,
        start_chapter=start_chapter,
    )

    if not novel_info and use_fallback:
        # Fallback to research mode
        logger.warning("Crawl failed, falling back to research mode")
        return fallback_research(url, platform, storage, logger)

    if not novel_info:
        logger.error("Failed to crawl novel")
        return False

    logger.info(
        f"Crawled: {novel_info.title} by {novel_info.author} "
        f"({len(novel_info.chapters)} chapters)"
    )

    # Cache crawled chapters
    if cache:
        for chapter in novel_info.chapters:
            if chapter.content and chapter.url not in chapters_to_skip:
                cache.cache_chapter(chapter.url, chapter.content)

    # Save novel
    if save_individually:
        saved = storage.save_chapters_individually(novel_info)
        logger.info(f"Saved {saved} chapters individually")
    else:
        storage.save_novel(novel_info)

    return True


def fallback_research(
    url: str,
    platform: str,
    storage: NovelStorage,
    logger: logging.Logger,
) -> bool:
    """
    Fallback to research mode when crawling fails.

    Args:
        url: Novel URL that failed
        platform: Platform name
        storage: Storage handler
        logger: Logger instance

    Returns:
        True if research successful, False otherwise
    """
    logger.info(f"Using research fallback for: {url}")

    # Extract title from URL for research
    title = extract_title_from_url(url)

    researcher = get_researcher()
    research_data = researcher.research_novel(title)

    if research_data.source == "none":
        logger.error(f"No research data available for: {title}")
        return False

    logger.info(f"Research found: {research_data.title} ({research_data.genre})")
    logger.info(f"Writing patterns: {len(research_data.writing_patterns)} patterns")
    logger.info(f"Tropes: {len(research_data.tropes)} tropes")

    # Save research data
    filepath = researcher.save_research(research_data)
    logger.info(f"Saved research to: {filepath}")

    return True


def extract_title_from_url(url: str) -> str:
    """Extract novel title from URL."""
    import re
    # Common patterns: /book/12345/ or /info/12345.html
    patterns = [
        r'/book/(\d+)/',
        r'/info/(\d+)',
        r'/(\d+)/$',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]


def crawl_targets(
    config: CrawlerConfig,
    storage: NovelStorage,
    cache: Optional[ChapterCache] = None,
    max_chapters: Optional[int] = None,
    save_individually: bool = False,
) -> dict:
    """
    Crawl all target novels from config.

    Args:
        config: Crawler configuration
        storage: Storage handler
        cache: Optional chapter cache
        max_chapters: Maximum chapters per novel
        save_individually: Whether to save chapters individually

    Returns:
        Dictionary with crawl results
    """
    logger = logging.getLogger("novel_crawler")

    results = {
        "total": len(config.targets),
        "successful": 0,
        "failed": 0,
        "errors": [],
    }

    for target in config.targets:
        if not target.enabled:
            logger.info(f"Skipping disabled target: {target.title or target.url}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"Crawling: {target.title or target.url} ({target.platform})")
        logger.info(f"{'='*60}")

        try:
            success = crawl_novel(
                url=target.url,
                platform=target.platform,
                config=config,
                storage=storage,
                cache=cache,
                max_chapters=max_chapters or target.chapters,
                save_individually=save_individually,
            )

            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"{target.url}: Crawl failed")

        except Exception as e:
            logger.error(f"Error crawling {target.url}: {e}")
            results["failed"] += 1
            results["errors"].append(f"{target.url}: {str(e)}")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Novel Knowledge Base Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url "https://www.qidian.com/book/12345/" --platform qidian
  %(prog)s --list-platforms
  %(prog)s --stats
  %(prog)s --config config.yaml
        """,
    )

    parser.add_argument(
        "--url",
        type=str,
        help="Novel URL to crawl",
    )
    parser.add_argument(
        "--platform",
        type=str,
        help="Platform to use (qidian, fanqie, qimao, chuangshi)",
    )
    parser.add_argument(
        "--max-chapters",
        type=int,
        help="Maximum number of chapters to crawl",
    )
    parser.add_argument(
        "--start-chapter",
        type=int,
        default=1,
        help="Starting chapter number (default: 1)",
    )
    parser.add_argument(
        "--save-individually",
        action="store_true",
        help="Save each chapter as a separate file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for saved novels",
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (YAML or JSON)",
    )
    parser.add_argument(
        "--list-platforms",
        action="store_true",
        help="List supported platforms",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show storage statistics",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Firecrawl API key (or set FIRECRAWL_API_KEY env var)",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable content deduplication",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear chapter cache before crawling",
    )

    args = parser.parse_args()

    # Set up logging
    logger = setup_logging(args.log_level)

    # Handle list platforms
    if args.list_platforms:
        platforms = list_supported_platforms()
        print("\nSupported platforms:")
        for p in platforms:
            print(f"  - {p}")
        print()
        return 0

    # Load configuration
    config = get_config()

    # Override config with command line arguments
    if args.output_dir:
        config.storage.output_dir = Path(args.output_dir)
    if args.api_key:
        config.firecrawl.api_key = args.api_key
    if args.no_dedup:
        config.storage.dedup_enabled = False
    if args.log_level:
        config.log_level = args.log_level

    # Initialize storage
    storage = NovelStorage(
        output_dir=config.storage.output_dir,
        enable_dedup=config.storage.dedup_enabled,
        dedup_cache_size=config.storage.dedup_cache_size,
        logger=logger,
    )

    # Initialize chapter cache
    cache = ChapterCache()
    if args.clear_cache:
        cleared = cache.clear_cache()
        logger.info(f"Cleared {cleared} cached chapters")

    # Handle stats
    if args.stats:
        stats = storage.get_stats()
        print("\nStorage Statistics:")
        print(f"  Saved novels: {stats['saved_count']}")
        print(f"  Duplicate content skipped: {stats['dedup_count']}")
        print(f"  Total files: {stats['total_files']}")
        print(f"  Total size: {stats['total_size_mb']} MB")
        print(f"  Output directory: {stats['output_dir']}")
        print()
        return 0

    # Validate arguments for single crawl
    if args.url:
        if not args.platform:
            logger.error("--platform is required when using --url")
            return 1

        crawler = get_crawler(args.platform, api_key=config.firecrawl.api_key)
        if not crawler:
            logger.error(f"Unsupported platform: {args.platform}")
            return 1

        success = crawl_novel(
            url=args.url,
            platform=args.platform,
            config=config,
            storage=storage,
            cache=cache,
            max_chapters=args.max_chapters,
            start_chapter=args.start_chapter,
            save_individually=args.save_individually,
        )

        return 0 if success else 1

    # Crawl all targets from config
    if not config.targets:
        logger.error("No targets configured. Set CRAWLER_TARGETS env var or use --url")
        logger.info("Use --list-platforms to see supported platforms")
        return 1

    results = crawl_targets(
        config=config,
        storage=storage,
        cache=cache,
        max_chapters=args.max_chapters,
        save_individually=args.save_individually,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Crawl Summary")
    print("=" * 60)
    print(f"Total targets: {results['total']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    print()

    # Print storage stats
    stats = storage.get_stats()
    print(f"Storage: {stats['saved_count']} novels saved, {stats['dedup_count']} duplicates skipped")
    print(f"Output directory: {stats['output_dir']}")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
