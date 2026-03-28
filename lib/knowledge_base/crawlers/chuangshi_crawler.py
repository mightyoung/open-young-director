"""Chuangshi (创世中文网) crawler implementation."""

import json
import re
from typing import Optional
import logging

from .base_crawler import BaseCrawler, ChapterInfo, NovelInfo
from .firecrawl_crawler import FirecrawlCrawler, FirecrawlResponse


class ChuangshiCrawler(FirecrawlCrawler):
    """Crawler for Chuangshi (创世中文网)."""

    PLATFORM_NAME = "创世中文网"
    BASE_URL = "https://www.chuangshi.com"

    # URL patterns for Chuangshi
    NOVEL_URL_PATTERNS = [
        r"https?://(?:www\.)?chuangshi\.com/(\w+)/?",
        r"https?://(?:book\.chuangshi\.com/(\w+))/?",
        r"https?://(?:m\.chuangshi\.com/(\w+)/book/(\w+))/?",
    ]

    CHAPTER_URL_PATTERNS = [
        r"https?://(?:www\.)?chuangshi\.com/(\w+)/chapter/(\w+)/?",
        r"https?://(?:m\.)?chuangshi\.com/(\w+)/(\w+)/?",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_rpm: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Chuangshi crawler.

        Args:
            api_key: Firecrawl API key (optional)
            rate_limit_rpm: Rate limit requests per minute
            logger: Optional logger instance
        """
        super().__init__(
            platform_name=self.PLATFORM_NAME,
            base_url=self.BASE_URL,
            api_key=api_key,
            rate_limit_rpm=rate_limit_rpm,
            logger=logger,
        )

    def is_valid_novel_url(self, url: str) -> bool:
        """Check if URL is a valid Chuangshi novel URL."""
        return any(re.match(pattern, url) for pattern in self.NOVEL_URL_PATTERNS)

    def extract_novel_info(self, url: str) -> Optional[NovelInfo]:
        """
        Extract novel information from Chuangshi.

        Args:
            url: URL of the novel's main page

        Returns:
            NovelInfo object or None if extraction fails
        """
        response = self.scrape(url)
        if not response.success:
            self.logger.error(f"Failed to scrape novel info: {response.error}")
            return None

        content = response.content or response.markdown or ""
        metadata = response.metadata or {}

        # Extract title
        title = metadata.get("title", "")
        if not title:
            title = self._extract_title_from_content(content)

        # Extract author
        author = metadata.get("author", "")
        if not author:
            author = self._extract_author_from_content(content)

        # Extract description
        description = metadata.get("description", "")
        if not description:
            description = self._extract_description_from_content(content)

        # Extract genre
        genre = self._extract_genre_from_content(content)

        # Get book ID from URL
        book_id = self._extract_book_id_from_url(url)

        novel_info = NovelInfo(
            title=title,
            author=author,
            url=url,
            platform=self.platform_name,
            genre=genre,
            description=description,
            metadata={
                **metadata,
                "book_id": book_id,
            },
        )

        # Extract chapters
        novel_info.chapters = self.extract_chapters(url)

        return novel_info

    def extract_chapters(self, url: str) -> list[ChapterInfo]:
        """
        Extract chapter list from Chuangshi.

        Args:
            url: URL of the novel's main page

        Returns:
            List of ChapterInfo objects
        """
        book_id = self._extract_book_id_from_url(url)
        if not book_id:
            self.logger.warning("Could not extract book ID from URL")
            return []

        # Try to get chapter list via API
        chapters = self._fetch_chapters_via_api(book_id)

        if not chapters:
            # Fallback to scraping the page
            response = self.scrape(url)
            if response.success:
                content = response.content or response.markdown or ""
                chapters = self._parse_chapters_from_content(content, book_id)

        return chapters

    def _fetch_chapters_via_api(self, book_id: str) -> list[ChapterInfo]:
        """
        Fetch chapter list via Chuangshi API.

        Args:
            book_id: Chuangshi book ID

        Returns:
            List of ChapterInfo objects
        """
        # Chuangshi's chapter API endpoint
        api_url = f"https://www.chuangshi.com/api/book/{book_id}/chapters"

        try:
            response = self._make_request(method="GET", url=api_url)
            data = response.json()

            chapters = []
            chapter_list = data.get("data", {}).get("chapters", [])
            for ch in chapter_list:
                chapters.append(
                    ChapterInfo(
                        number=ch.get("chapterIndex", 0),
                        title=ch.get("chapterTitle", ""),
                        url=ch.get("chapterUrl", ""),
                    )
                )

            self.logger.info(f"Fetched {len(chapters)} chapters via API")
            return chapters

        except Exception as e:
            self.logger.warning(f"Failed to fetch chapters via API: {e}")
            return []

    def _parse_chapters_from_content(
        self,
        content: str,
        book_id: str,
    ) -> list[ChapterInfo]:
        """
        Parse chapter list from page content.

        Args:
            content: Page content
            book_id: Book ID for constructing URLs

        Returns:
            List of ChapterInfo objects
        """
        chapters = []

        # Pattern for chapter links on Chuangshi
        chapter_pattern = re.compile(
            r'<a[^>]*href=["\'](/' + book_id + r'/chapter/[\w/]+)["\'][^>]*>\s*'
            r'(?:第?\s*(\d+)\s*[章话]?\s*)?([^(<\n]+?)(?:\s*\(|\s*<|\s*$)',
            re.IGNORECASE,
        )

        seen_urls = set()
        for match in chapter_pattern.finditer(content):
            href = match.group(1)
            chapter_num = match.group(2)
            title = match.group(3).strip() if match.group(3) else ""

            if href in seen_urls:
                continue
            seen_urls.add(href)

            chapter_url = f"https://www.chuangshi.com{href}"
            chapter_number = int(chapter_num) if chapter_num else len(chapters) + 1

            chapters.append(
                ChapterInfo(
                    number=chapter_number,
                    title=title or f"Chapter {chapter_number}",
                    url=chapter_url,
                )
            )

        return chapters

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """
        Extract content from a Chuangshi chapter.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            Chapter content as string or None if extraction fails
        """
        response = self.scrape(chapter_url)
        if not response.success:
            self.logger.error(f"Failed to scrape chapter: {response.error}")
            return None

        content = response.content or response.markdown or ""
        return self._clean_chapter_content(content)

    def _extract_book_id_from_url(self, url: str) -> Optional[str]:
        """Extract book ID from URL."""
        for pattern in self.NOVEL_URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                # Book ID is typically the last group that matched
                for g in reversed(match.groups()):
                    if g:
                        return g
        return None

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from content."""
        patterns = [
            r'<h1[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)</h1>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'data-title=["\']([^"\']+)["\']',
            r'"bookName":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        lines = content.strip().split("\n")
        if lines:
            return lines[0][:200]
        return "Unknown Title"

    def _extract_author_from_content(self, content: str) -> str:
        """Extract author from content."""
        patterns = [
            r'<a[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</a>',
            r'作者[：:]\s*<a[^>]*>([^<]+)</a>',
            r'作者[：:]\s*(\S+)',
            r'"author":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown Author"

    def _extract_description_from_content(self, content: str) -> str:
        """Extract description from content."""
        patterns = [
            r'<p[^>]*class=["\'][^"\']*intro[^"\']*["\'][^>]*>([^<]+)</p>',
            r'<div[^>]*class=["\'][^"\']*description[^"\']*["\'][^>]*>([^<]+)</div>',
            r'简介[：:]\s*([^\n<]+)',
            r'"description":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_genre_from_content(self, content: str) -> str:
        """Extract genre from content."""
        patterns = [
            r'<a[^>]*class=["\'][^"\']*tag[^"\']*["\'][^>]*>([^<]+)</a>',
            r'类别[：:]\s*(\S+)',
            r'"genre":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def _clean_chapter_content(self, content: str) -> str:
        """Clean chapter content."""
        if not content:
            return ""

        lines = content.split("\n")
        cleaned_lines = []
        skip_patterns = [
            r"(?:本章|本章内容|本章完毕|下章预告|请阅读|推荐阅读|投票|打赏)",
            r"(?:www\.|http)",
            r"(?:上一页|下一页|返回目录|返回章节|添加书签)",
            r"(?:最新章节|最快更新)",
            r"(?:创世中文网|创世)",
            r"(?:chapter|Chapter)",
            r"(?:如有遗漏|请联系)",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                continue

            # Skip very short lines
            if len(line) < 10 and not (
                self._is_chinese(line[0]) if line else False
            ):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)
