"""Outline Loader for parsing novel outlines."""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class OutlineLoader:
    """Loads and parses novel outline files."""

    def __init__(self, outline_dir: str):
        self.outline_dir = Path(outline_dir)
        self.volume_outlines: Dict[int, Path] = {}
        self._scan_outline_files()

    def _scan_outline_files(self):
        """Scan for outline files."""
        if not self.outline_dir.exists():
            return

        for md_file in self.outline_dir.glob("*.md"):
            if "第" in md_file.stem and "卷" in md_file.stem:
                vol_match = re.search(r"第(\d+)卷", md_file.stem)
                if vol_match:
                    vol_num = int(vol_match.group(1))
                    self.volume_outlines[vol_num] = md_file
            elif "详细章节规划" in md_file.stem:
                self.volume_outlines[1] = md_file

    def get_chapter_outline(self, chapter_number: int) -> Optional[Dict[str, Any]]:
        """Get outline for a specific chapter."""
        volume_num = ((chapter_number - 1) // 60) + 1

        outline_file = self.volume_outlines.get(volume_num)
        if not outline_file:
            outline_file = self.volume_outlines.get(1)

        if not outline_file or not outline_file.exists():
            return None

        return self._parse_chapter_outline(outline_file, chapter_number)

    def _parse_chapter_outline(self, outline_file: Path, chapter_number: int) -> Optional[Dict[str, Any]]:
        """Parse chapter outline from markdown file."""
        try:
            content = outline_file.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Try table format first (e.g., "| 001 | 标题 | 境界 | 事件 |")
            for i, line in enumerate(lines):
                if f"| {chapter_number:03d} |" in line or f"| {chapter_number} |" in line:
                    parts = [p.strip() for p in line.split("|")]
                    parts = [p for p in parts if p]

                    if len(parts) >= 5:
                        title = parts[1]
                        realm = parts[2]
                        events = parts[3]
                        magic_line = parts[4] if len(parts) > 4 else ""

                        return {
                            "number": chapter_number,
                            "title": title,
                            "realm": realm,
                            "summary": events,
                            "magic_line": magic_line,
                            "key_events": [e.strip() for e in events.split(",") if e.strip()],
                        }

            # Try markdown header format (e.g., "#### 第4章：外门扬名")
            chapter_pattern = rf"^####\s*第{chapter_number}章[：:]\s*(.+)$"
            for i, line in enumerate(lines):
                match = re.match(chapter_pattern, line.strip())
                if match:
                    title = match.group(1).strip()
                    # Look for nearby content for realm/events
                    summary, key_events = self._extract_chapter_details(lines, i)
                    return {
                        "number": chapter_number,
                        "title": f"第{chapter_number}章：{title}",
                        "realm": "",
                        "summary": summary,
                        "magic_line": "",
                        "key_events": key_events,
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to parse outline for chapter {chapter_number}: {e}")
            return None

    def _extract_chapter_summary(self, lines: List[str], chapter_line: str) -> str:
        """Extract summary for a chapter from surrounding context."""
        try:
            idx = lines.index(chapter_line)
            # Look for content after the chapter header
            summary_parts = []
            for i in range(idx + 1, min(idx + 10, len(lines))):
                line = lines[i].strip()
                if not line:
                    continue
                # Stop at next chapter or section
                if re.match(r"^#{1,4}\s*第\d+章", line):
                    break
                if line.startswith("## "):
                    break
                # Collect paragraph content
                if not line.startswith("|") and not line.startswith("-"):
                    summary_parts.append(line)
                if len(summary_parts) >= 3:
                    break
            return " ".join(summary_parts)[:200] if summary_parts else ""
        except ValueError:
            return ""
        except Exception:
            return ""

    def _extract_chapter_details(self, lines: List[str], chapter_idx: int) -> tuple:
        """Extract both summary and key_events from chapter section.

        Returns:
            tuple: (summary: str, key_events: list)
        """
        try:
            summary = ""
            key_events = []
            events_mode = False
            found_core_event = False

            # Scan lines after the chapter header
            for i in range(chapter_idx + 1, min(chapter_idx + 30, len(lines))):
                line = lines[i].strip()

                # Stop at next chapter
                if re.match(r"^#{1,4}\s*第\d+章", line):
                    break

                # Extract 核心事件 (this is the main summary)
                if "**核心事件**" in line or ("核心事件" in line and "：" in line):
                    # Extract content after the colon
                    if "：" in line:
                        parts = line.split("：")
                        if len(parts) > 1:
                            summary = parts[-1].strip()
                        else:
                            summary = line.replace("**核心事件**", "").replace("核心事件", "").strip()
                    found_core_event = True
                    # Also add as first key event
                    if summary and len(summary) > 2:
                        key_events.append(summary)
                    continue

                # Extract from 内容大纲 bullet points
                if "**内容大纲**" in line or line.startswith("**内容大纲**"):
                    events_mode = True
                    continue

                if events_mode and line.startswith("-"):
                    # Extract bullet point content
                    evt = line.lstrip("-").strip()
                    if evt and len(evt) > 2:
                        key_events.append(evt)
                    continue

            # If no core event summary found, try to build from first bullet point
            if not summary and key_events:
                summary = key_events[0] if key_events else ""

            return summary, key_events

        except Exception as e:
            logger.warning(f"Failed to extract chapter details: {e}")
            return "", []

    def get_volume_outline(self, volume_number: int) -> Optional[Dict[str, Any]]:
        """Get full outline for a volume."""
        outline_file = self.volume_outlines.get(volume_number)
        if not outline_file or not outline_file.exists():
            return None

        return self._parse_volume_outline(outline_file)

    def _parse_volume_outline(self, outline_file: Path) -> Dict[str, Any]:
        """Parse entire volume outline."""
        content = outline_file.read_text(encoding="utf-8")

        return {
            "file": str(outline_file),
            "chapters": [],
        }


class OutlineEnforcer:
    """Ensures generated content follows the outline."""

    def __init__(self, outline_loader: OutlineLoader):
        self.loader = outline_loader

    def get_chapter_outline(self, chapter_number: int) -> Optional[Dict[str, Any]]:
        """Get and validate chapter outline."""
        return self.loader.get_chapter_outline(chapter_number)

    def validate_outline(self, chapter_number: int, content: str) -> Dict[str, Any]:
        """Validate content against outline.

        Checks:
        1. Title appears early in content
        2. All key_events are present in content
        3. magic_line hints appear in content (if present)
        """
        outline = self.get_chapter_outline(chapter_number)

        if not outline:
            return {"valid": True, "issues": []}

        issues = []
        missing_events = []

        # Check title
        if outline.get("title") and outline["title"] not in content[:1000]:
            issues.append(f"Title '{outline['title']}' may not appear early in content")

        # Check key events are mentioned in content
        key_events = outline.get("key_events", [])
        for event in key_events:
            # Extract key phrases (skip very short items)
            if len(event) < 4:
                continue
            # Check if any significant word/phrase from event appears in content
            event_keywords = [w for w in event if len(w) >= 2]
            if not event_keywords:
                continue
            # Simple check: see if event text appears anywhere in content
            if event not in content:
                missing_events.append(event)

        if missing_events:
            issues.append(f"Missing key events: {'; '.join(missing_events[:5])}")
            if len(missing_events) > 5:
                issues.append(f"... and {len(missing_events) - 5} more missing events")

        # Check magic_line hints
        magic_line = outline.get("magic_line", "")
        if magic_line:
            # Extract key phrases from magic line
            magic_keywords = [w for w in magic_line if len(w) >= 2]
            found = any(kw in content for kw in magic_keywords[:5])
            if not found:
                issues.append(f"魔帝线（暗线）未体现: '{magic_line}'")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "missing_events": missing_events,
            "checked_events": len(key_events),
        }
