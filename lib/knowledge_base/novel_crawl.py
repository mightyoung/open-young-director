#!/usr/bin/env python3
"""
Direct crawler script using Firecrawl API for Qidian novels.
This script bypasses the Qidian API and directly uses Firecrawl to crawl novels.
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Optional

import requests

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "fc-2ecc789c4a13436aadbd7f8f2a1b4cba")
FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v0/scrape"
OUTPUT_DIR = Path("./novels_output")


def scrape_url(url: str, wait_for: int = 0) -> Optional[dict]:
    """Scrape a URL using Firecrawl API."""
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "url": url,
        "pageOptions": {
            "onlyMainContent": True,
        },
    }

    if wait_for > 0:
        data["firecrawlOptions"] = {"waitFor": wait_for}

    try:
        response = requests.post(
            FIRECRAWL_SCRAPE_URL,
            headers=headers,
            json=data,
            timeout=60,
        )
        result = response.json()
        if result.get("success"):
            return result.get("data")
        else:
            print(f"  Firecrawl error: {result.get('error')}")
            return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None


def extract_novel_info(content: str, url: str) -> dict:
    """Extract novel information from page content."""
    info = {
        "title": "",
        "author": "",
        "genre": "",
        "description": "",
        "url": url,
        "platform": "起点中文网",
        "metadata": {},
    }

    # Extract title
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
    if title_match:
        info["title"] = title_match.group(1).strip()
    else:
        title_match = re.search(r'#\s*([^\n#]+)', content)
        if title_match:
            info["title"] = title_match.group(1).strip()

    # Extract author
    author_match = re.search(r'作者[：:]\s*([^\s\n]+)', content)
    if author_match:
        info["author"] = author_match.group(1).strip()

    # Extract description
    desc_match = re.search(r'([^<\n]{20,}?)(?:\n|$)', content)
    if desc_match:
        info["description"] = desc_match.group(1).strip()

    # Extract genre
    genre_match = re.search(r'类型[：:]\s*([^\s\n]+)', content)
    if genre_match:
        info["genre"] = genre_match.group(1).strip()

    return info


def extract_chapter_title(content: str) -> str:
    """Extract chapter title from chapter page."""
    # Try to find chapter title pattern
    patterns = [
        r'<h3[^>]*>([^<]+)</h3>',
        r'###\s*([^\n]+)',
        r'第[一二三四五六七八九十百千\d]+章\s*([^\n]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()

    return "Unknown Chapter"


def crawl_novel(url: str, max_chapters: int = 10) -> dict:
    """Crawl a novel and its chapters."""
    print(f"\nCrawling: {url}")

    # Extract book ID from URL
    book_id_match = re.search(r'/book/(\d+)/', url)
    book_id = book_id_match.group(1) if book_id_match else ""

    # Scrape main page
    print("  Fetching main page...")
    data = scrape_url(url)
    if not data:
        return {"success": False, "error": "Failed to fetch main page"}

    content = data.get("content", "") or data.get("markdown", "") or ""

    # Extract novel info
    novel_info = extract_novel_info(content, url)
    print(f"  Title: {novel_info['title']}")
    print(f"  Author: {novel_info['author']}")

    # Try to find chapter links from content
    chapters = []

    # Pattern: /chapter/xxxxx/xxxxx/ format
    chapter_pattern = re.compile(r'href=["\'](/chapter/\d+/\d+/)["\'][^>]*>\s*([^<]+)\s*</a>')
    for match in chapter_pattern.finditer(content):
        chapter_url = match.group(1)
        chapter_title = match.group(2).strip()
        if chapter_url not in [c['url'] for c in chapters]:
            full_url = f"https://www.qidian.com{chapter_url}" if chapter_url.startswith("/") else chapter_url
            chapters.append({
                "number": len(chapters) + 1,
                "title": chapter_title,
                "url": full_url,
            })

    print(f"  Found {len(chapters)} chapter links in content")

    # If no chapters found, use verified chapter IDs only
    if not chapters and book_id:
        # Verified chapter IDs for known novels
        verified_chapters = {
            "107580": [  # 凡人修仙传
                (4631519, "第一章 山边小村"),
            ],
            "1209977": [  # 斗破苍穹
                (2337333, "第一章 陨落的天才"),
            ],
            "1890269": [  # 大圣传
                (3880920, "第一章 山村"),
            ],
            "3106580": [  # 我欲封天
                (5876445, "第一章 我欲封天"),
            ],
        }

        chapter_list = verified_chapters.get(book_id, [])
        if chapter_list:
            print(f"  Using verified chapter IDs for book {book_id}")
            for i, (chapter_id, chapter_title) in enumerate(chapter_list[:max_chapters]):
                chapters.append({
                    "number": i + 1,
                    "title": chapter_title,
                    "url": f"https://www.qidian.com/chapter/{book_id}/{chapter_id}/",
                })

    # Crawl chapters
    crawled_chapters = []
    for i, chapter in enumerate(chapters[:max_chapters]):
        print(f"  Crawling chapter {i+1}/{min(len(chapters), max_chapters)}: {chapter['title']}")

        chapter_data = scrape_url(chapter['url'])
        if chapter_data:
            chapter_content = chapter_data.get("content", "") or chapter_data.get("markdown", "") or ""
            # Clean content
            lines = [l.strip() for l in chapter_content.split("\n") if l.strip() and len(l.strip()) > 10]
            cleaned_content = "\n".join(lines[:50])  # First 50 lines as sample

            crawled_chapters.append({
                "number": chapter['number'],
                "title": chapter['title'],
                "url": chapter['url'],
                "content": cleaned_content,
            })

        time.sleep(1)  # Rate limiting

    novel_info["chapters"] = crawled_chapters
    return {"success": True, "novel": novel_info}


def save_novel(novel_info: dict, output_dir: Path = OUTPUT_DIR):
    """Save novel to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create safe filename
    title = novel_info.get("title", "unknown")
    author = novel_info.get("author", "unknown")
    safe_name = f"{title}_{author}".replace("/", "_").replace("\\", "_")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_name}_{timestamp}.json"

    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(novel_info, f, ensure_ascii=False, indent=2)

    print(f"  Saved to: {filepath}")
    return filepath


def main():
    """Main entry point."""
    novels = [
        # Already crawled: 凡人修仙传, 斗破苍穹, 大圣传, 我欲封天
        # Adding new high-quality novels from research
        {
            "title": "诡秘之主",
            "url": "https://www.qidian.com/book/1047152376/",
            "author": "爱潜水的乌贼",
            "genre": "克苏鲁/玄幻",
        },
        {
            "title": "神墓",
            "url": "https://www.qidian.com/book/63856/",
            "author": "辰东",
            "genre": "玄幻",
        },
        {
            "title": "遮天",
            "url": "https://www.qidian.com/book/1735921/",
            "author": "辰东",
            "genre": "仙侠",
        },
        {
            "title": "雪中悍刀行",
            "url": "https://www.qidian.com/book/1003766218/",
            "author": "烽火戏诸侯",
            "genre": "武侠",
        },
        {
            "title": "剑来",
            "url": "https://www.qidian.com/book/1021131762/",
            "author": "烽火戏诸侯",
            "genre": "仙侠",
        },
    ]

    max_chapters = 5
    results = []

    print("=" * 60)
    print("Qidian Novel Crawler using Firecrawl API")
    print("=" * 60)

    for novel in novels:
        print(f"\n[{novel['title']}]")
        try:
            result = crawl_novel(novel["url"], max_chapters=max_chapters)
            if result.get("success"):
                novel_info = result["novel"]
                # Update with known info
                novel_info["title"] = novel["title"]
                novel_info["author"] = novel["author"]
                novel_info["genre"] = novel["genre"]

                filepath = save_novel(novel_info)
                results.append({
                    "title": novel["title"],
                    "success": True,
                    "filepath": str(filepath),
                    "chapters": len(novel_info.get("chapters", [])),
                })
            else:
                results.append({
                    "title": novel["title"],
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                })
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                "title": novel["title"],
                "success": False,
                "error": str(e),
            })

        time.sleep(2)  # Rate limiting between novels

    # Print summary
    print("\n" + "=" * 60)
    print("Crawl Summary")
    print("=" * 60)
    successful = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    print(f"Total: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\nFailed novels:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['title']}: {r.get('error', 'Unknown error')}")

    print(f"\nOutput directory: {OUTPUT_DIR.absolute()}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())