"""Output serialization utilities for content generation."""
import json
from pathlib import Path
from typing import Any


def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json_output(result: Any, output_dir: Path, filename: str) -> None:
    """Save result as JSON file."""
    output_file = output_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)


def save_markdown_output(content: str, output_dir: Path, filename: str) -> None:
    """Save markdown content to output directory."""
    output_file = output_dir / filename
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)


def build_review_markdown(
    *,
    content_type: str,
    topic: str,
    title: str,
    status: str,
    is_usable: bool,
    requires_manual_review: bool,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    next_actions: list[str] | None = None,
    extra_sections: dict[str, list[str] | str] | None = None,
) -> str:
    """Build a compact human-readable review summary."""
    warnings = warnings or []
    errors = errors or []
    next_actions = next_actions or []
    extra_sections = extra_sections or {}

    lines = [
        f"# {content_type} 审阅摘要",
        "",
        f"- 主题: {topic}",
        f"- 标题: {title or '未生成'}",
        f"- 状态: {status}",
        f"- 可直接使用: {'是' if is_usable else '否'}",
        f"- 需要人工审核: {'是' if requires_manual_review else '否'}",
    ]

    if warnings:
        lines.extend(["", "## 警告"])
        lines.extend([f"- {warning}" for warning in warnings])

    if errors:
        lines.extend(["", "## 错误"])
        lines.extend([f"- {error}" for error in errors])

    if next_actions:
        lines.extend(["", "## 建议下一步"])
        lines.extend([f"- {action}" for action in next_actions])

    for section, payload in extra_sections.items():
        if not payload:
            continue
        lines.extend(["", f"## {section}"])
        if isinstance(payload, str):
            lines.append(payload)
        else:
            lines.extend([f"- {item}" for item in payload])

    lines.append("")
    return "\n".join(lines)


def save_podcast_content(content: Any, output_dir: Path) -> None:
    """Save podcast content to output directory."""
    # Save full script (all segments combined)
    script_parts = []
    if content.preshow:
        script_parts.append(f"【预热】\n{content.preshow}")
    if content.intro:
        script_parts.append(f"【开场】\n{content.intro}")
    for i, seg in enumerate(content.segments, 1):
        script_parts.append(f"【第{i}段】\n{seg.content if hasattr(seg, 'content') else str(seg)}")
    if content.interview:
        interview_content = content.interview.content if hasattr(content.interview, 'content') else str(content.interview)
        script_parts.append(f"【访谈】\n{interview_content}")
    if content.ad_reads:
        for ad in content.ad_reads:
            script_parts.append(f"【广告】\n{ad.script if hasattr(ad, 'script') else str(ad)}")
    if content.outro:
        script_parts.append(f"【结尾】\n{content.outro}")

    if script_parts:
        script_file = output_dir / "script.txt"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(script_parts))

    # Save shownotes
    if content.shownotes:
        shownotes_data = content.shownotes.__dict__ if hasattr(content.shownotes, '__dict__') else content.shownotes
        save_json_output(shownotes_data, output_dir, "shownotes.json")


def save_blog_content(post: Any, output_dir: Path) -> None:
    """Save blog content to output directory."""
    # Save per-platform content
    if post.platform_contents:
        for platform, content in post.platform_contents.items():
            platform_dir = output_dir / platform
            platform_dir.mkdir(exist_ok=True)

            if hasattr(content, "title") and content.title:
                title_file = platform_dir / "title.txt"
                with open(title_file, "w", encoding="utf-8") as f:
                    f.write(content.title)

            if hasattr(content, "body") and content.body:
                body_file = platform_dir / "content.txt"
                with open(body_file, "w", encoding="utf-8") as f:
                    f.write(content.body)

            if hasattr(content, "seo_data") and content.seo_data:
                seo_file = platform_dir / "seo.json"
                with open(seo_file, "w", encoding="utf-8") as f:
                    json.dump(content.seo_data, f, ensure_ascii=False, indent=2, default=str)

    # Save hook options
    if post.hooks:
        save_json_output(
            [
                {"variant": h.variant, "hook_text": h.hook_text, "type": h.hook_type, "score": h.engagement_score}
                for h in post.hooks
            ],
            output_dir,
            "hooks.json",
        )

    # Save body
    if post.body:
        body_file = output_dir / "content.txt"
        with open(body_file, "w", encoding="utf-8") as f:
            f.write(post.body)


def save_script_content(content: Any, output_dir: Path) -> None:
    """Save script content to output directory."""
    # Save beat sheets
    if content.beat_sheets:
        save_json_output(
            [
                {
                    "act": beat.act,
                    "beats": [
                        {
                            "number": b.number,
                            "name": b.name,
                            "description": b.description,
                            "scene_purpose": b.scene_purpose,
                            "turning_point": b.turning_point,
                        }
                        for b in beat.beats
                    ],
                }
                for beat in content.beat_sheets
            ],
            output_dir,
            "beat_sheet.json",
        )

    # Save scenes
    if content.scenes:
        scenes_dir = output_dir / "scenes"
        scenes_dir.mkdir(exist_ok=True)
        for i, scene in enumerate(content.scenes):
            scene_file = scenes_dir / f"scene_{i+1}.txt"
            scene_content = scene.content if hasattr(scene, "content") else str(scene)
            with open(scene_file, "w", encoding="utf-8") as f:
                f.write(scene_content)

    # Save dialogues
    if content.dialogues:
        dialogues_dir = output_dir / "dialogues"
        dialogues_dir.mkdir(exist_ok=True)
        for i, dialogue in enumerate(content.dialogues):
            dialogue_file = dialogues_dir / f"dialogue_{i+1}.txt"
            dialogue_content = dialogue.content if hasattr(dialogue, "content") else str(dialogue)
            with open(dialogue_file, "w", encoding="utf-8") as f:
                f.write(dialogue_content)


def save_novel_chapters(novel: Any, output_dir: Path) -> None:
    """Save novel chapters to output directory."""
    if hasattr(novel, "chapters") and novel.chapters:
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        for chapter in novel.chapters:
            chapter_file = chapters_dir / f"chapter_{chapter.chapter_num}.txt"
            content = chapter.content if hasattr(chapter, "content") else str(chapter)
            with open(chapter_file, "w", encoding="utf-8") as f:
                f.write(content)
