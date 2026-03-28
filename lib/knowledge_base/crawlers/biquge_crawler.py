"""Biquge (笔趣阁) crawler implementation for novel platforms."""

import re
from typing import Optional
import logging

from .base_crawler import BaseCrawler, ChapterInfo, NovelInfo
from .firecrawl_crawler import FirecrawlCrawler


class BiqugeCrawler(FirecrawlCrawler):
    """Crawler for Biquge (笔趣阁) novel platforms.

    Supports:
    - https://www.biquge520.com/       (biquge520)
    - https://www.biquge5200.com/      (biquge5200)
    - https://www.biqugezw.com/        (biqugezw)
    """

    PLATFORM_NAME = "笔趣阁"
    BASE_URL = "https://www.biquge520.com"

    # URL patterns for Biquge platforms
    NOVEL_URL_PATTERNS = [
        # biquge520.com patterns (user-specified)
        r"https?://(?:www\.)?biquge520\.com/(\w+)/?",
        r"https?://(?:www\.)?biquge520\.com/\w+/\w+/\?",
        # biquge5200.com patterns
        r"https?://(?:www\.)?biquge5200\.com/(\w+)/?",
        r"https?://(?:www\.)?biquge5200\.com/\d+/\d+/\d+\.html",
        # biqugezw.com patterns
        r"https?://(?:www\.)?biqugezw\.com/(\w+)/?",
        r"https?://(?:www\.)?biqugezw\.com/\d+/\d+/\d+\.html",
    ]

    CHAPTER_URL_PATTERNS = [
        # biquge520.com patterns
        r"https?://(?:www\.)?biquge520\.com/\w+/\w+/(\w+)\.html",
        # biquge5200.com patterns
        r"https?://(?:www\.)?biquge5200\.com/\d+/\d+/(\d+)\.html",
        # biqugezw.com patterns
        r"https?://(?:www\.)?biqugezw\.com/\d+/\d+/(\d+)\.html",
    ]

    # Supported domains
    SUPPORTED_DOMAINS = [
        "biquge520.com",
        "www.biquge520.com",
        "biquge5200.com",
        "www.biquge5200.com",
        "biqugezw.com",
        "www.biqugezw.com",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit_rpm: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Biquge crawler.

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
        """Check if URL is a valid Biquge novel URL."""
        return any(domain in url for domain in self.SUPPORTED_DOMAINS)

    def extract_novel_info(self, url: str) -> Optional[NovelInfo]:
        """
        Extract novel information from Biquge.

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

        # Detect which domain we're using
        domain = self._detect_domain(url)

        novel_info = NovelInfo(
            title=title,
            author=author,
            url=url,
            platform=self.platform_name,
            genre=genre,
            description=description,
            metadata={
                **metadata,
                "source_domain": domain,
            },
        )

        # Extract chapters
        novel_info.chapters = self.extract_chapters(url)

        return novel_info

    def extract_chapters(self, url: str) -> list[ChapterInfo]:
        """
        Extract chapter list from Biquge.

        Args:
            url: URL of the novel's main page

        Returns:
            List of ChapterInfo objects
        """
        response = self.scrape(url)
        if not response.success:
            self.logger.error(f"Failed to scrape chapter list: {response.error}")
            return []

        content = response.content or response.markdown or ""
        return self._parse_chapters_from_content(content, url)

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """
        Extract content from a Biquge chapter.

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

    def _detect_domain(self, url: str) -> str:
        """Detect which Biquge domain the URL is from."""
        for domain in self.SUPPORTED_DOMAINS:
            if domain in url:
                return domain
        return "biquge5200.com"

    def _parse_chapters_from_content(
        self,
        content: str,
        base_url: str,
    ) -> list[ChapterInfo]:
        """
        Parse chapter list from page content.

        Args:
            content: Page content
            base_url: Base URL for constructing chapter URLs

        Returns:
            List of ChapterInfo objects
        """
        chapters = []
        seen_urls = set()

        # Pattern for Biquge chapter links
        # Format: /book_id/chapter_id.html or /book_id/volume_id/chapter_id.html
        chapter_pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']+\.html)["\'][^>]*>([^<]*)</a>',
            re.IGNORECASE,
        )

        # Alternative pattern for list format
        list_pattern = re.compile(
            r'<li[^>]*>.*?<a[^>]+href=["\']([^"\']+\.html)["\'][^>]*>\s*'
            r'(?:第?\s*(\d+)\s*[章话]?\s*)?([^(<\n]+?)(?:\s*\(|\s*<|\s*$)',
            re.IGNORECASE | re.DOTALL,
        )

        # Extract chapters from content
        for match in chapter_pattern.finditer(content):
            href = match.group(1).strip()
            title = match.group(2).strip()

            if href in seen_urls or not href:
                continue

            # Skip non-chapter links
            if any(skip in href.lower() for skip in ["index", "cover", "info", "catalog"]):
                continue

            seen_urls.add(href)

            # Construct full URL
            if href.startswith("http"):
                chapter_url = href
            else:
                domain = self._detect_domain(base_url)
                base = f"https://www.{domain}"
                chapter_url = f"{base.rstrip('/')}/{href.lstrip('/')}"

            # Extract chapter number from URL
            chapter_num_match = re.search(r'/(\d+)\.html$', href)
            chapter_number = int(chapter_num_match.group(1)) if chapter_num_match else len(chapters) + 1

            # Clean title
            title = re.sub(r'^\d+\s*', '', title).strip()
            if not title:
                title = f"Chapter {chapter_number}"

            chapters.append(
                ChapterInfo(
                    number=chapter_number,
                    title=title,
                    url=chapter_url,
                )
            )

        # Also try list pattern for better extraction
        for match in list_pattern.finditer(content):
            href = match.group(1).strip()
            chapter_num = match.group(2)
            title = match.group(3).strip() if match.group(3) else ""

            if href in seen_urls or not href:
                continue

            seen_urls.add(href)

            # Construct full URL
            if href.startswith("http"):
                chapter_url = href
            else:
                domain = self._detect_domain(base_url)
                base = f"https://www.{domain}"
                chapter_url = f"{base.rstrip('/')}/{href.lstrip('/')}"

            chapter_number = int(chapter_num) if chapter_num else len(chapters) + 1

            if not title:
                title = f"Chapter {chapter_number}"

            chapters.append(
                ChapterInfo(
                    number=chapter_number,
                    title=title,
                    url=chapter_url,
                )
            )

        # Sort by chapter number
        chapters.sort(key=lambda x: x.number)

        # Re-number sequentially
        for i, chapter in enumerate(chapters):
            chapter.number = i + 1

        return chapters

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from content."""
        patterns = [
            # Biquge specific patterns
            r'<h1[^>]*>([^<]+)</h1>',
            r'<div[^>]*class=["\'][^"\']*title[^"\']*["\'][^>]*>([^<]+)</div>',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'"bookName":["\']([^"\']+)["\']',
            r'<span[^>]*id=["\'] booktitle["\'][^>]*>([^<]+)</span>',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if title and len(title) < 200:
                    return title

        # Fallback: first non-empty line
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and len(line) > 3:
                return line[:200]

        return "Unknown Title"

    def _extract_author_from_content(self, content: str) -> str:
        """Extract author from content."""
        patterns = [
            # Biquge specific patterns
            r'作者[：:]\s*<a[^>]*>([^<]+)</a>',
            r'作者[：:]\s*([^\n<]+)',
            r'<a[^>]+class=["\'][^"\']*author[^"\']*["\'][^>]*>([^<]+)</a>',
            r'"author":["\']([^"\']+)["\']',
            r'<span[^>]*id=["\'] author["\'][^>]*>([^<]+)</span>',
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
                    return desc[:500]  # Limit length

        return ""

    def _extract_genre_from_content(self, content: str) -> str:
        """Extract genre from content."""
        patterns = [
            r'<a[^>]*class=["\'][^"\']*tag[^"\']*["\'][^>]*>([^<]+)</a>',
            r'类别[：:]\s*([^\n<]+)',
            r'"genre":["\']([^"\']+)["\']',
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
            # Biquge specific noise
            r"(?:笔趣阁|biquge)",
            r"(?:本章|本章内容|本章完毕|下章预告|请阅读|推荐阅读|投票|打赏)",
            r"(?:www\.|http)",
            r"(?:上一页|下一页|返回目录|返回章节|添加书签)",
            r"(?:最新章节|最快更新|最快阅读)",
            r"(?: chapters? )",
            r"(?:如有遗漏|请联系|错误报告)",
            r"(?:一秒记住|记住本站)",
            r"(?:https?://)",
            r"^(?:Chapter|CHATER|第\s*\d+\s*章).*",
        ]

        in_chapter_content = False
        content_start_patterns = [
            r"第\s*\d+\s*[章话]",
            r"^第\d+章",
            r"^[一二三四五六七八九十百千万\d]+[、，,]",  # Chinese numbered paragraphs
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip lines matching skip patterns
            if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                continue

            # Detect start of actual chapter content
            if not in_chapter_content:
                if any(re.match(p, line) for p in content_start_patterns):
                    in_chapter_content = True
                elif len(line) > 20 and self._is_chinese(line[0]):
                    in_chapter_content = True

            if not in_chapter_content:
                continue

            # Skip very short lines (likely navigation or noise)
            if len(line) < 8:
                continue

            # Skip lines that are just numbers or symbols
            if re.match(r"^[\d\s\.\,\。\，]+$", line):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)
