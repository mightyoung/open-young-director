"""Firecrawl-based crawler implementation with fallback support."""

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
import logging

import requests

from .base_crawler import BaseCrawler, ChapterInfo, NovelInfo


@dataclass
class FirecrawlResponse:
    """Response from Firecrawl API."""
    success: bool
    content: Optional[str] = None
    markdown: Optional[str] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None


class FirecrawlCrawler(BaseCrawler):
    """Crawler implementation using Firecrawl API with fallback scraping."""

    def __init__(
        self,
        platform_name: str,
        base_url: str,
        api_key: Optional[str] = None,
        rate_limit_rpm: int = 30,
        timeout: int = 60,
        max_retries: int = 3,
        retry_delay: int = 5,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the Firecrawl crawler.

        Args:
            platform_name: Name of the platform
            base_url: Base URL for the platform
            api_key: Firecrawl API key (optional)
            rate_limit_rpm: Rate limit requests per minute
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            logger: Optional logger instance
        """
        super().__init__(platform_name, base_url, logger)
        self.api_key = api_key
        self.rate_limit_rpm = rate_limit_rpm
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start_time = time.time()

        # Firecrawl API endpoints
        self._firecrawl_scrape_url = "https://api.firecrawl.dev/v0/scrape"
        self._firecrawl_batch_url = "https://api.firecrawl.dev/v0/batch/scrape"

    def _rate_limit(self) -> None:
        """Apply rate limiting."""
        current_time = time.time()

        # Reset counter if minute has passed
        if current_time - self._minute_start_time >= 60:
            self._request_count = 0
            self._minute_start_time = current_time

        # Check if we've hit the rate limit
        if self._request_count >= self.rate_limit_rpm:
            sleep_time = 60 - (current_time - self._minute_start_time)
            if sleep_time > 0:
                self.logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self._request_count = 0
                self._minute_start_time = time.time()

        # Minimum delay between requests
        min_delay = 60.0 / self.rate_limit_rpm
        time_since_last = current_time - self._last_request_time
        if time_since_last < min_delay:
            time.sleep(min_delay - time_since_last)

        self._last_request_time = time.time()
        self._request_count += 1

    def _make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> requests.Response:
        """
        Make an HTTP request with rate limiting and retries.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails after retries
        """
        self._rate_limit()

        headers = kwargs.pop("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        kwargs["headers"] = headers

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt < self.max_retries - 1:
                    self.logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    raise

    def scrape_firecrawl(self, url: str) -> FirecrawlResponse:
        """
        Scrape a URL using Firecrawl API.

        Args:
            url: URL to scrape

        Returns:
            FirecrawlResponse object
        """
        if not self.api_key:
            self.logger.debug("No Firecrawl API key, using fallback")
            return FirecrawlResponse(success=False, error="No API key")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "url": url,
            "pageOptions": {
                "onlyMainContent": True,
            },
        }

        try:
            response = self._make_request(
                method="POST",
                url=self._firecrawl_scrape_url,
                headers=headers,
                json=data,
            )
            result = response.json()

            if result.get("success"):
                return FirecrawlResponse(
                    success=True,
                    content=result.get("data", {}).get("content", ""),
                    markdown=result.get("data", {}).get("markdown", ""),
                    metadata=result.get("data", {}).get("metadata", {}),
                )
            else:
                return FirecrawlResponse(
                    success=False,
                    error=result.get("error", "Unknown error"),
                )

        except requests.RequestException as e:
            self.logger.warning(f"Firecrawl request failed: {e}")
            return FirecrawlResponse(success=False, error=str(e))

    def scrape_direct(self, url: str) -> FirecrawlResponse:
        """
        Fallback direct scraping when Firecrawl is unavailable.

        Args:
            url: URL to scrape

        Returns:
            FirecrawlResponse object
        """
        try:
            response = self._make_request(method="GET", url=url)
            html = response.text

            # Extract main content using basic HTML parsing
            content = self._extract_content_from_html(html)

            return FirecrawlResponse(
                success=True,
                content=content,
                markdown=content,
                metadata={"source": "direct_scrape"},
            )
        except requests.RequestException as e:
            self.logger.warning(f"Direct scrape failed: {e}")
            return FirecrawlResponse(success=False, error=str(e))

    def scrape(self, url: str) -> FirecrawlResponse:
        """
        Scrape a URL using Firecrawl with fallback to direct scraping.

        Args:
            url: URL to scrape

        Returns:
            FirecrawlResponse object
        """
        # Try Firecrawl first
        response = self.scrape_firecrawl(url)
        if response.success:
            return response

        # Fallback to direct scraping
        self.logger.info(f"Falling back to direct scraping for: {url}")
        return self.scrape_direct(url)

    def _extract_content_from_html(self, html: str) -> str:
        """
        Extract clean text content from HTML.

        Args:
            html: HTML content

        Returns:
            Extracted text content
        """
        # Remove script and style tags
        html = re.sub(
            r"<(script|style)[^>]*>.*?</\1>",
            "",
            html,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove HTML comments
        html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

        # Replace block elements with newlines
        html = re.sub(r"<(div|p|br|h[1-6]|li|tr)[^>]*>", "\n", html, flags=re.IGNORECASE)

        # Remove remaining HTML tags
        text = re.sub(r"<[^>]+>", "", html)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()

        return text

    def extract_novel_info(self, url: str) -> Optional[NovelInfo]:
        """Extract novel information using Firecrawl."""
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

        return NovelInfo(
            title=title,
            author=author,
            url=url,
            platform=self.platform_name,
            metadata=metadata,
        )

    def extract_chapters(self, url: str) -> list[ChapterInfo]:
        """Extract chapter list using Firecrawl."""
        response = self.scrape(url)
        if not response.success:
            self.logger.error(f"Failed to scrape chapter list: {response.error}")
            return []

        content = response.content or response.markdown or ""
        return self._extract_chapters_from_content(content, url)

    def extract_chapter_content(self, chapter_url: str) -> Optional[str]:
        """Extract chapter content using Firecrawl."""
        response = self.scrape(chapter_url)
        if not response.success:
            self.logger.error(f"Failed to scrape chapter: {response.error}")
            return None

        content = response.content or response.markdown or ""
        return self._clean_chapter_content(content)

    def _extract_title_from_content(self, content: str) -> str:
        """Extract title from content (fallback)."""
        lines = content.strip().split("\n")
        if lines:
            return lines[0][:200]
        return "Unknown Title"

    def _extract_author_from_content(self, content: str) -> str:
        """Extract author from content (fallback)."""
        # Look for common author patterns
        patterns = [
            r"作者[：:]\s*(\S+)",
            r"作者\s*[:-]?\s*(.+?)(?:\n|$)",
            r"Author[：:]\s*(\S+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown Author"

    def _extract_chapters_from_content(
        self,
        content: str,
        base_url: str,
    ) -> list[ChapterInfo]:
        """
        Extract chapter list from content (platform-specific implementation).

        Args:
            content: Page content
            base_url: Base URL for constructing chapter URLs

        Returns:
            List of ChapterInfo objects
        """
        # Default implementation - should be overridden by platform-specific crawlers
        chapters = []

        # Look for chapter links
        chapter_pattern = re.compile(
            r'(?:第?\s*(\d+)\s*[章话集部]|chapter|chap|章节)[：:\s]*'
            r'["\']?([^<"\']+)["\']?\s*[:：]?\s*["\']?(https?://[^"\'\s]+|[/\w]+)["\']?',
            re.IGNORECASE,
        )

        for i, line in enumerate(content.split("\n")):
            match = chapter_pattern.search(line)
            if match:
                chapter_num = int(match.group(1)) if match.group(1) else i + 1
                chapter_title = match.group(2).strip() if match.group(2) else f"Chapter {chapter_num}"
                chapter_url = match.group(3).strip() if match.group(3) else ""

                if chapter_url and not chapter_url.startswith("http"):
                    chapter_url = base_url.rstrip("/") + "/" + chapter_url.lstrip("/")

                chapters.append(
                    ChapterInfo(
                        number=chapter_num,
                        title=chapter_title,
                        url=chapter_url,
                    )
                )

        return chapters

    def _clean_chapter_content(self, content: str) -> str:
        """
        Clean chapter content by removing headers, footers, and noise.

        Args:
            content: Raw chapter content

        Returns:
            Cleaned content
        """
        if not content:
            return ""

        lines = content.split("\n")
        cleaned_lines = []
        skip_patterns = [
            r"(?:本章|本章内容|本章完毕|下章预告|请阅读|推荐阅读|投票|打赏)",
            r"(?:www\.|http)",
            r"(?:上一页|下一页|返回目录|返回章节|添加书签)",
            r"(?:最新章节|最快更新)",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip lines matching skip patterns
            if any(re.search(p, line, re.IGNORECASE) for p in skip_patterns):
                continue

            # Skip very short lines that are likely noise
            if len(line) < 10 and not self._is_chinese(line[0] if line else ""):
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)


class FirecrawlBatchCrawler(FirecrawlCrawler):
    """Firecrawl crawler with batch scraping support."""

    def scrape_batch(self, urls: list[str]) -> list[FirecrawlResponse]:
        """
        Scrape multiple URLs using Firecrawl batch API.

        Args:
            urls: List of URLs to scrape

        Returns:
            List of FirecrawlResponse objects
        """
        if not self.api_key:
            self.logger.debug("No Firecrawl API key, using sequential fallback")
            return [self.scrape_direct(url) for url in urls]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "urls": urls,
            "pageOptions": {
                "onlyMainContent": True,
            },
        }

        try:
            response = self._make_request(
                method="POST",
                url=self._firecrawl_batch_url,
                headers=headers,
                json=data,
            )
            result = response.json()

            responses = []
            for url_data in result.get("data", []):
                if url_data.get("success"):
                    responses.append(
                        FirecrawlResponse(
                            success=True,
                            content=url_data.get("content", ""),
                            markdown=url_data.get("markdown", ""),
                            metadata=url_data.get("metadata", {}),
                        )
                    )
                else:
                    responses.append(
                        FirecrawlResponse(
                            success=False,
                            error=url_data.get("error", "Unknown error"),
                        )
                    )

            return responses

        except requests.RequestException as e:
            self.logger.warning(f"Firecrawl batch request failed: {e}")
            return [FirecrawlResponse(success=False, error=str(e)) for _ in urls]
