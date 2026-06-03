"""Base crawler abstract class for novel platforms."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging


@dataclass
class ChapterInfo:
    """Information about a chapter."""
    number: int
    title: str
    url: str
    content: Optional[str] = None
    word_count: int = 0
    crawled_at: Optional[datetime] = None


@dataclass
class NovelInfo:
    """Information about a novel."""
    title: str
    author: str
    url: str
    platform: str
    genre: Optional[str] = None
    description: Optional[str] = None
    total_chapters: int = 0
    chapters: list[ChapterInfo] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    crawled_at: datetime = field(default_factory=datetime.now)
    last_updated: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "author": self.author,
            "url": self.url,
            "platform": self.platform,
            "genre": self.genre,
            "description": self.description,
            "total_chapters": self.total_chapters,
            "chapters": [
                {
                    "number": ch.number,
                    "title": ch.title,
                    "url": ch.url,
                    "content": ch.content,
                    "word_count": ch.word_count,
                    "crawled_at": ch.crawled_at.isoformat() if ch.crawled_at else None,
                }
                for ch in self.chapters
            ],
            "metadata": self.metadata,
            "crawled_at": self.crawled_at.isoformat(),
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
        }


class BaseCrawler(ABC):
    """Abstract base class for novel platform crawlers."""

    def __init__(
        self,
        platform_name: str,
        base_url: str,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the base crawler.

        Args:
            platform_name: Name of the platform (e.g., "起点中文网")
            base_url: Base URL for the platform
            logger: Optional logger instance
        """
        self.platform_name = platform_name
        self.base_url = base_url
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def extract_novel_info(self, url: str) -> Optional[NovelInfo]:
        """
        Extract novel information from the novel's main page.

        Args:
            url: URL of the novel's main page

        Returns:
            NovelInfo object or None if extraction fails
        """
        pass

    @abstractmethod
    def extract_chapters(self, url: str) -> list[ChapterInfo]:
        """
        Extract chapter list from the novel page.

        Args:
            url: URL of the novel's main page

        Returns:
            List of ChapterInfo objects
        """
        pass

    @abstractmethod
    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """
        Extract content from a chapter page.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            Chapter content as string or None if extraction fails
        """
        pass

    def is_valid_novel_url(self, url: str) -> bool:
        """
        Check if the URL is a valid novel URL for this platform.

        Args:
            url: URL to check

        Returns:
            True if the URL is valid, False otherwise
        """
        return self.base_url in url

    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL for this platform.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url

    def count_words(self, text: str) -> int:
        """
        Count words in text (primarily for Chinese text).

        Args:
            text: Text to count words in

        Returns:
            Word count
        """
        if not text:
            return 0
        # For Chinese text, count characters as words
        # For mixed text, count both Chinese chars and English words
        chinese_chars = sum(1 for c in text if self._is_chinese(c))
        english_words = len(text.split())
        return chinese_chars + english_words

    @staticmethod
    def _is_chinese(char: str) -> bool:
        """Check if a character is Chinese."""
        return "\u4e00" <= char <= "\u9fff"

    def crawl_novel(
        self,
        url: str,
        max_chapters: Optional[int] = None,
        start_chapter: int = 1,
    ) -> Optional[NovelInfo]:
        """
        Crawl a complete novel.

        Args:
            url: URL of the novel's main page
            max_chapters: Maximum number of chapters to crawl (None for all)
            start_chapter: Chapter number to start from (1-indexed)

        Returns:
            NovelInfo object or None if crawling fails
        """
        self.logger.info(f"Starting to crawl novel: {url}")

        # Extract novel info
        novel_info = self.extract_novel_info(url)
        if not novel_info:
            self.logger.error(f"Failed to extract novel info from: {url}")
            return None

        self.logger.info(
            f"Found novel: {novel_info.title} by {novel_info.author} "
            f"({len(novel_info.chapters)} chapters)"
        )

        # Extract chapter list if not already populated
        if not novel_info.chapters:
            novel_info.chapters = self.extract_chapters(url)

        novel_info.total_chapters = len(novel_info.chapters)
        self.logger.info(f"Found {novel_info.total_chapters} chapters")

        # Crawl chapters
        chapters_to_crawl = novel_info.chapters[start_chapter - 1:]
        if max_chapters:
            chapters_to_crawl = chapters_to_crawl[:max_chapters]

        self.logger.info(
            f"Crawling chapters {start_chapter} to "
            f"{start_chapter + len(chapters_to_crawl) - 1}"
        )

        for i, chapter in enumerate(chapters_to_crawl):
            try:
                self.logger.debug(f"Crawling chapter {chapter.number}: {chapter.title}")
                content = self.extract_chapter_content(chapter.url)
                if content:
                    chapter.content = content
                    chapter.word_count = self.count_words(content)
                    chapter.crawled_at = datetime.now()
                    self.logger.debug(
                        f"Successfully crawled chapter {chapter.number} "
                        f"({chapter.word_count} words)"
                    )
                else:
                    self.logger.warning(
                        f"Failed to extract content from chapter {chapter.number}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Error crawling chapter {chapter.number}: {e}"
                )
                continue

        novel_info.last_updated = datetime.now()
        return novel_info
