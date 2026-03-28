"""Chuangshi QQ (创世中文网QQ) crawler implementation for Tencent's platform."""

import re
import json
from typing import Optional
import logging

from .base_crawler import BaseCrawler, ChapterInfo, NovelInfo
from .firecrawl_crawler import FirecrawlCrawler


class ChuangshiqqCrawler(FirecrawlCrawler):
    """Crawler for Chuangshi QQ (创世中文网) - Tencent's novel platform.

    URL format: https://chuangshi.qq.com/
    """

    PLATFORM_NAME = "创世中文网(QQ)"
    BASE_URL = "https://chuangshi.qq.com"

    # URL patterns for Chuangshi QQ
    NOVEL_URL_PATTERNS = [
        # chuangshi.qq.com patterns
        r"https?://chuangshi\.qq\.com/(\w+)/?(?:index\.htm)?",
        r"https?://chuangshi\.qq\.com/(\w+)/(\w+)/?(?:index\.htm)?",
        r"https?://book\.chuangshi\.qq\.com/(\w+)/?(?:index\.htm)?",
    ]

    CHAPTER_URL_PATTERNS = [
        r"https?://chuangshi\.qq\.com/(\w+)/(\w+)/(\w+)\.htm",
        r"https?://book\.chuangshi\.qq\.com/(\w+)/(\w+)/(\w+)\.htm",
    ]

    # API endpoints
    BOOK_INFO_API = "https://chuangshi.qq.com/api/book/{book_id}"
    CHAPTER_LIST_API = "https://chuangshi.qq.com/api/book/{book_id}/chapters"
    CHAPTER_CONTENT_API = "https://chuangshi.qq.com/api/chapter/{book_id}/{chapter_id}"

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_rpm: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Chuangshi QQ crawler.

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
        """Check if URL is a valid Chuangshi QQ novel URL."""
        return "chuangshi.qq.com" in url or "book.chuangshi.qq.com" in url

    def extract_novel_info(self, url: str) -> Optional[NovelInfo]:
        """
        Extract novel information from Chuangshi QQ.

        Args:
            url: URL of the novel's main page

        Returns:
            NovelInfo object or None if extraction fails
        """
        book_id = self._extract_book_id_from_url(url)
        if not book_id:
            self.logger.error(f"Could not extract book ID from URL: {url}")
            return None

        # Try to get book info via API first
        book_info = self._fetch_book_info_via_api(book_id)

        if book_info:
            novel_info = NovelInfo(
                title=book_info.get("bookName", ""),
                author=book_info.get("author", {}).get("authorName", "") if isinstance(book_info.get("author"), dict) else book_info.get("author", ""),
                url=url,
                platform=self.platform_name,
                genre=book_info.get("categoryName", ""),
                description=book_info.get("description", ""),
                metadata={
                    "book_id": book_id,
                    "word_count": book_info.get("wordCount", 0),
                    "status": book_info.get("status", ""),
                    "update_time": book_info.get("updateTime", ""),
                    "cover_url": book_info.get("coverUrl", ""),
                },
            )
        else:
            # Fallback to page scraping
            response = self.scrape(url)
            if not response.success:
                self.logger.error(f"Failed to scrape novel info: {response.error}")
                return None

            content = response.content or response.markdown or ""
            metadata = response.metadata or {}

            novel_info = NovelInfo(
                title=metadata.get("title", "") or self._extract_title_from_content(content),
                author=metadata.get("author", "") or self._extract_author_from_content(content),
                url=url,
                platform=self.platform_name,
                genre=self._extract_genre_from_content(content),
                description=self._extract_description_from_content(content),
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
        Extract chapter list from Chuangshi QQ.

        Args:
            url: URL of the novel's main page

        Returns:
            List of ChapterInfo objects
        """
        book_id = self._extract_book_id_from_url(url)
        if not book_id:
            self.logger.warning("Could not extract book ID from URL")
            return []

        # Try API first
        chapters = self._fetch_chapters_via_api(book_id)

        if not chapters:
            # Fallback to page scraping
            response = self.scrape(url)
            if response.success:
                content = response.content or response.markdown or ""
                chapters = self._parse_chapters_from_content(content, book_id)

        return chapters

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """
        Extract content from a Chuangshi QQ chapter.

        Args:
            chapter_url: URL of the chapter page

        Returns:
            Chapter content as string or None if extraction fails
        """
        chapter_info = self._extract_chapter_info_from_url(chapter_url)
        if not chapter_info:
            self.logger.error(f"Could not extract chapter info from URL: {chapter_url}")
            return None

        book_id = chapter_info.get("book_id")
        chapter_id = chapter_info.get("chapter_id")

        # Try API first
        content = self._fetch_chapter_content_via_api(book_id, chapter_id)

        if content:
            return self._clean_chapter_content(content)

        # Fallback to page scraping
        response = self.scrape(chapter_url)
        if not response.success:
            self.logger.error(f"Failed to scrape chapter: {response.error}")
            return None

        content = response.content or response.markdown or ""
        return self._clean_chapter_content(content)

    def _fetch_book_info_via_api(self, book_id: str) -> Optional[dict]:
        """Fetch book information via Chuangshi QQ API."""
        api_url = self.BOOK_INFO_API.format(book_id=book_id)

        try:
            response = self._make_request(method="GET", url=api_url)
            data = response.json()

            if data.get("code") == 0 or data.get("result") == 0:
                return data.get("data", {})
            else:
                self.logger.warning(f"API returned error: {data.get('msg', 'Unknown error')}")
                return None

        except Exception as e:
            self.logger.warning(f"Failed to fetch book info via API: {e}")
            return None

    def _fetch_chapters_via_api(self, book_id: str) -> list[ChapterInfo]:
        """Fetch chapter list via Chuangshi QQ API."""
        api_url = self.CHAPTER_LIST_API.format(book_id=book_id)

        try:
            response = self._make_request(method="GET", url=api_url)
            data = response.json()

            chapters = []
            if data.get("code") == 0 or data.get("result") == 0:
                chapter_list = data.get("data", {}).get("chapters", [])
                if not chapter_list:
                    chapter_list = data.get("data", [])

                for ch in chapter_list:
                    chapter_id = ch.get("chapterId", "") or ch.get("id", "")
                    chapters.append(
                        ChapterInfo(
                            number=ch.get("chapterIndex", 0) or ch.get("index", len(chapters) + 1),
                            title=ch.get("chapterTitle", "") or ch.get("title", f"Chapter {len(chapters) + 1}"),
                            url=ch.get("chapterUrl", "") or self._build_chapter_url(book_id, chapter_id),
                        )
                    )

                self.logger.info(f"Fetched {len(chapters)} chapters via API")

        except Exception as e:
            self.logger.warning(f"Failed to fetch chapters via API: {e}")

        return chapters

    def _fetch_chapter_content_via_api(self, book_id: str, chapter_id: str) -> Optional[str]:
        """Fetch chapter content via Chuangshi QQ API."""
        api_url = self.CHAPTER_CONTENT_API.format(book_id=book_id, chapter_id=chapter_id)

        try:
            response = self._make_request(method="GET", url=api_url)
            data = response.json()

            if data.get("code") == 0 or data.get("result") == 0:
                content = data.get("data", {}).get("content", "")
                if content:
                    return content

        except Exception as e:
            self.logger.warning(f"Failed to fetch chapter content via API: {e}")

        return None

    def _parse_chapters_from_content(
        self,
        content: str,
        book_id: str,
    ) -> list[ChapterInfo]:
        """Parse chapter list from page content."""
        chapters = []
        seen_urls = set()

        # Pattern for Chuangshi QQ chapter links
        chapter_pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']+\.htm)["\'][^>]*>\s*'
            r'(?:第?\s*(\d+)\s*[章话]?\s*)?([^(<\n]+?)(?:\s*\(|\s*<|\s*$)',
            re.IGNORECASE,
        )

        # Alternative pattern for JSON-like chapter lists
        json_pattern = re.compile(
            r'"chapterId"\s*:\s*"?(\d+)"?.*?"chapterTitle"\s*:\s*"?([^",}]+)',
            re.IGNORECASE,
        )

        # Try JSON pattern first (more reliable)
        for match in json_pattern.finditer(content):
            chapter_id = match.group(1)
            title = match.group(2).strip()

            if chapter_id in seen_urls:
                continue
            seen_urls.add(chapter_id)

            chapters.append(
                ChapterInfo(
                    number=len(chapters) + 1,
                    title=title,
                    url=self._build_chapter_url(book_id, chapter_id),
                )
            )

        # Then try HTML pattern
        for match in chapter_pattern.finditer(content):
            href = match.group(1).strip()
            chapter_num = match.group(2)
            title = match.group(3).strip() if match.group(3) else ""

            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Extract chapter ID from URL
            chapter_id_match = re.search(r'/(\w+)\.htm$', href)
            if not chapter_id_match:
                continue
            chapter_id = chapter_id_match.group(1)

            chapter_number = int(chapter_num) if chapter_num else len(chapters) + 1
            if not title:
                title = f"Chapter {chapter_number}"

            chapters.append(
                ChapterInfo(
                    number=chapter_number,
                    title=title,
                    url=self._build_chapter_url(book_id, chapter_id),
                )
            )

        # Sort and re-number
        chapters.sort(key=lambda x: x.number)
        for i, chapter in enumerate(chapters):
            chapter.number = i + 1

        return chapters

    def _build_chapter_url(self, book_id: str, chapter_id: str) -> str:
        """Build chapter URL from book ID and chapter ID."""
        return f"https://chuangshi.qq.com/{book_id}/{chapter_id}.htm"

    def _extract_book_id_from_url(self, url: str) -> Optional[str]:
        """Extract book ID from URL."""
        for pattern in self.NOVEL_URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                # Book ID is typically the first captured group
                for g in match.groups():
                    if g and g not in ["index.htm", "index.html"]:
                        return g
        return None

    def _extract_chapter_info_from_url(self, url: str) -> Optional[dict]:
        """Extract book ID and chapter ID from chapter URL."""
        match = re.search(r"chuangshi\.qq\.com/(\w+)/(\w+)\.htm", url)
        if match:
            return {
                "book_id": match.group(1),
                "chapter_id": match.group(2),
            }
        return None

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from content."""
        patterns = [
            r'<h1[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)</h1>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'"bookName":["\']([^"\']+)["\']',
            r'<title>([^<]+)</title>',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if title and len(title) < 200:
                    return title

        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) > 3:
                return line[:200]

        return "Unknown Title"

    def _extract_author_from_content(self, content: str) -> str:
        """Extract author from content."""
        patterns = [
            r'<a[^>]+class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</a>',
            r'作者[：:]\s*<a[^>]*>([^<]+)</a>',
            r'作者[：:]\s*([^\n<]+)',
            r'"author":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                author = match.group(1).strip()
                if author and author not in ["Unknown", "未知"]:
                    return author

        return "Unknown Author"

    def _extract_description_from_content(self, content: str) -> str:
        """Extract description from content."""
        patterns = [
            r'<div[^>]*class=["\'][^"\']*intro[^"\']*["\'][^>]*>([^<]+)</div>',
            r'<div[^>]*class=["\'][^"\']*description[^"\']*["\'][^>]*>([^<]+)</div>',
            r'<p[^>]*class=["\'][^"\']*intro[^"\']*["\'][^>]*>([^<]+)</p>',
            r'简介[：:]\s*([^\n<]+)',
            r'"description":["\']([^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                desc = match.group(1).strip()
                if desc:
                    return desc[:500]

        return ""

    def _extract_genre_from_content(self, content: str) -> str:
        """Extract genre from content."""
        patterns = [
            r'<a[^>]*class=["\'][^"\']*tag[^"\']*["\'][^>]*>([^<]+)</a>',
            r'类别[：:]\s*([^\n<]+)',
            r'"categoryName":["\']([^"\']+)["\']',
            r'分类[：:]\s*([^\n<]+)',
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
            r"(?: chuangshi|创世中文网)",
            r"(?:如有遗漏|请联系)",
            r"(?:chapter|Chapter)",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                continue

            # Skip very short lines
            if len(line) < 10 and not (self._is_chinese(line[0]) if line else False):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)
