#!/usr/bin/env python3
"""Local novel studio UI."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import gradio as gr
except ModuleNotFoundError as exc:  # pragma: no cover - local setup guard
    raise SystemExit(
        "Gradio 未安装。请先执行 `python3 -m pip install gradio pillow`，然后再运行 gradio_app.py。"
    ) from exc

from agents.config_manager import get_config_manager
from writing_options import (
    DEFAULT_WRITING_OPTIONS,
    STYLE_PRESET_CHOICES,
    BASE_STYLE_CHOICES,
    WRITING_OPTION_GROUPS,
    normalize_writing_options,
)

RUN_SCRIPT = ROOT_DIR / "run_novel_generation.py"
CSS = """
:root {
  --bg: #111111;
  --panel: #181818;
  --panel-2: #1f1f1f;
  --line: #303030;
  --text: #f2f2f2;
  --muted: #b0b0b0;
  --accent: #d6b35f;
  --accent-2: #4fbf9f;
  --danger: #d86969;
}

body, .gradio-container {
  background: var(--bg) !important;
  color: var(--text) !important;
}

#studio-shell {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0));
}

.gradio-container h1, .gradio-container h2, .gradio-container h3, .gradio-container label {
  color: var(--text) !important;
}

.gradio-container .prose, .gradio-container p, .gradio-container span, .gradio-container small {
  color: var(--muted) !important;
}

.gradio-container button {
  border-radius: 6px !important;
}

.gradio-container textarea, .gradio-container input, .gradio-container .wrap {
  border-color: var(--line) !important;
}

.gradio-container .tab-nav button[aria-selected="true"] {
  border-bottom-color: var(--accent) !important;
  color: var(--text) !important;
}
"""


def _project_choices() -> List[str]:
    config_dir = ROOT_DIR / "config"
    return sorted(file.stem.replace("project_", "") for file in config_dir.glob("project_*.json"))


def _project_root() -> Path | None:
    config_mgr = get_config_manager()
    if config_mgr.current_project and getattr(config_mgr.generation, "output_dir", ""):
        return Path(config_mgr.generation.output_dir)
    return None


def _metadata_file() -> Path | None:
    root = _project_root()
    return root / "metadata.json" if root else None


def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_writing_metadata(metadata: Dict | None) -> Dict[str, str]:
    return normalize_writing_options(metadata or {})


def _active_project_info() -> Dict[str, str]:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return {
            "title": "未加载项目",
            "status": "当前没有已加载项目",
            "project_id": "",
        }

    project = config_mgr.current_project
    writing_options = _normalize_writing_metadata(project.metadata.get("writing_options", {}))
    lines = [
        f"### {project.title}",
        f"- 项目ID: `{project.id}`",
        f"- 题材: `{project.genre}`",
        f"- 进度: `{project.current_chapter}/{project.total_chapters}`",
        f"- 更新时间: `{project.updated_at}`",
        "",
        "#### 写作参数",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in writing_options.items() if value)
    return {
        "title": project.title,
        "status": "\n".join(lines),
        "project_id": project.id,
    }


def _load_project_metadata() -> Dict:
    meta_path = _metadata_file()
    if not meta_path:
        return {"chapters": []}
    data = _read_json(meta_path)
    data.setdefault("chapters", [])
    return data


def _chapter_index() -> List[Dict]:
    data = _load_project_metadata()
    chapters = data.get("chapters", [])
    if chapters:
        return sorted(chapters, key=lambda item: item.get("number", 0))

    root = _project_root()
    if not root:
        return []

    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        return []

    rows = []
    for chapter_file in sorted(chapters_dir.glob("ch*.md")):
        match = re.match(r"ch(\d{3})_(.*)\.md$", chapter_file.name)
        number = int(match.group(1)) if match else 0
        title = match.group(2).replace("_", " ") if match else chapter_file.stem
        content = chapter_file.read_text(encoding="utf-8")
        summary_match = re.search(r"\*\*本章概要\*\*:\s*(.*)", content)
        word_match = re.search(r"字数:\s*(\d+)", content)
        rows.append(
            {
                "number": number,
                "title": title,
                "word_count": int(word_match.group(1)) if word_match else 0,
                "summary": summary_match.group(1).strip() if summary_match else "",
                "file_path": str(chapter_file),
                "created_at": chapter_file.stat().st_mtime,
            }
        )
    return sorted(rows, key=lambda item: item.get("number", 0))


def _chapter_choices() -> List[Tuple[str, str]]:
    choices = []
    for item in _chapter_index():
        choices.append((f"{item['number']:03d} · {item['title']}", str(item["number"])))
    return choices


def _chapter_rows() -> List[List[str]]:
    rows = []
    for item in _chapter_index():
        created = item.get("created_at")
        created_text = (
            datetime.fromtimestamp(created).strftime("%m-%d %H:%M")
            if isinstance(created, (int, float))
            else ""
        )
        rows.append(
            [
                item.get("number", 0),
                item.get("title", ""),
                item.get("word_count", 0),
                item.get("summary", ""),
                created_text,
            ]
        )
    return rows


def _chapter_file(number: int) -> Path | None:
    root = _project_root()
    if not root:
        return None
    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        return None
    matches = sorted(chapters_dir.glob(f"ch{number:03d}_*.md"))
    return matches[0] if matches else None


def _read_chapter_detail(number: int) -> Tuple[str, str, str, str]:
    chapter_file = _chapter_file(number)
    if not chapter_file:
        return "未找到章节。", "", "", ""

    content = chapter_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    title = lines[0].lstrip("# ").strip() if lines else f"第{number}章"

    summary_match = re.search(r"\*\*本章概要\*\*:\s*(.*)", content)
    key_events_match = re.search(r"\*\*关键事件\*\*:\s*(.*)", content)
    body = content.split("---", 1)[-1].strip()

    summary = summary_match.group(1).strip() if summary_match else ""
    key_events = key_events_match.group(1).strip() if key_events_match else ""
    report = _read_json((chapter_file.parent.parent / "consistency_reports" / f"ch{number:03d}_consistency.json"))
    plot_summary = _read_json((chapter_file.parent.parent / "plot_summaries" / f"ch{number:03d}_summary.json"))

    detail_lines = [
        f"### 第{number}章 · {title}",
        f"- 文件: `{chapter_file}`",
        f"- 概要: {summary or '无'}",
        f"- 关键事件: {key_events or '无'}",
        "",
        "#### 正文",
        body,
    ]

    report_text = json.dumps(report, ensure_ascii=False, indent=2) if report else "无一致性报告"
    plot_text = json.dumps(plot_summary, ensure_ascii=False, indent=2) if plot_summary else "无章节概要"
    return "\n".join(detail_lines), plot_text, report_text, content


def _derivative_summary() -> Tuple[str, List[List[str]]]:
    root = _project_root()
    if not root:
        return "当前没有已加载项目。", []

    scripts_dir = Path(get_config_manager().generation.scripts_dir)
    film_drama_dir = Path(get_config_manager().generation.film_drama_dir)
    rows: List[List[str]] = []
    if scripts_dir.exists():
        for file in sorted(scripts_dir.rglob("*")):
            if file.is_file():
                rows.append([file.parent.name, file.name, file.stat().st_size, str(file)])
    if film_drama_dir.exists():
        for file in sorted(film_drama_dir.glob("*.json")):
            if file.is_file():
                rows.append(["film_drama", file.name, file.stat().st_size, str(file)])

    text = [
        "### 衍生内容",
        f"- 脚本目录: `{scripts_dir}`",
        f"- 剧情目录: `{film_drama_dir}`",
        f"- 文件数: `{len(rows)}`",
    ]
    return "\n".join(text), rows


def _writing_values_from_project() -> Tuple[str, ...]:
    config_mgr = get_config_manager()
    metadata = {}
    if config_mgr.current_project:
        metadata = config_mgr.current_project.metadata.get("writing_options", {})
    options = _normalize_writing_metadata(metadata)
    return tuple(options[key] for key in DEFAULT_WRITING_OPTIONS)


def _project_dropdown_update() -> gr.Update:
    current = get_config_manager().current_project
    return gr.update(
        choices=_project_choices(),
        value=current.id if current else None,
    )


def create_project(
    title: str,
    genre: str,
    outline: str,
    world: str,
    characters: str,
    author: str,
    chapters: int,
) -> Tuple[str, gr.Update, gr.Update, List[List[str]], str, str, str, str, str]:
    config_mgr = get_config_manager()
    config_mgr.create_project(
        title=title.strip(),
        author=author.strip() or "AI Author",
        genre=genre.strip(),
        outline=outline.strip(),
        world_setting=world.strip(),
        character_intro=characters.strip(),
        total_chapters=int(chapters),
    )
    status = _active_project_info()["status"]
    chapter_update = gr.update(choices=_chapter_choices(), value=None)
    derivative_text, derivative_rows = _derivative_summary()
    return status, _project_dropdown_update(), chapter_update, _chapter_rows(), "", "", "", "", derivative_text


def load_project(project_id: str) -> Tuple[str, gr.Update, gr.Update, List[List[str]], str, str, str, str, str]:
    config_mgr = get_config_manager()
    if not project_id:
        status = _active_project_info()["status"]
        derivative_text, _ = _derivative_summary()
        return status, _project_dropdown_update(), gr.update(choices=_chapter_choices(), value=None), _chapter_rows(), "", "", "", "", derivative_text

    project = config_mgr.load_project(project_id)
    if not project:
        return (
            f"### 项目不存在: `{project_id}`",
            _project_dropdown_update(),
            gr.update(choices=[], value=None),
            [],
            "",
            "",
            "",
            "",
            "",
        )

    status = _active_project_info()["status"]
    choices = _chapter_choices()
    chapter_update = gr.update(choices=choices, value=choices[0][1] if choices else None)
    derivative_text, _ = _derivative_summary()
    if choices:
        detail, plot_text, report_text, body_text = _read_chapter_detail(int(choices[0][1]))
    else:
        detail, plot_text, report_text, body_text = "", "", "", ""
    return status, _project_dropdown_update(), chapter_update, _chapter_rows(), detail, plot_text, report_text, body_text, derivative_text


def save_writing_options(*values: str) -> str:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return "请先创建或加载项目。"

    options = normalize_writing_options(dict(zip(DEFAULT_WRITING_OPTIONS.keys(), values)))
    config_mgr.current_project.metadata["writing_options"] = options
    config_mgr._save_project(config_mgr.current_project)
    return "已保存写作参数。\n\n" + _active_project_info()["status"]


def refresh_chapter_view(chapter_number: str | None) -> Tuple[str, str, str, str]:
    if not chapter_number:
        return "请选择章节。", "", "", ""
    return _read_chapter_detail(int(chapter_number))


def run_generation(
    count: int,
    start: int,
    dry_run: bool,
    no_auto_feedback: bool,
    *writing_values: str,
) -> Tuple[str, List[List[str]], str]:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return "请先创建或加载项目。", [], _derivative_summary()[0]

    options = normalize_writing_options(dict(zip(DEFAULT_WRITING_OPTIONS.keys(), writing_values)))
    config_mgr.current_project.metadata["writing_options"] = options
    config_mgr._save_project(config_mgr.current_project)

    cmd = [sys.executable, str(RUN_SCRIPT), "--generate", str(int(count))]
    if int(start) > 0:
        cmd.extend(["--start", str(int(start))])
    if dry_run:
        cmd.append("--dry-run")
    if no_auto_feedback:
        cmd.append("--no-auto-feedback")

    cli_flag_map = {
        "style": "--style",
        "style_preset": "--style-preset",
        "perspective": "--perspective",
        "narrative_mode": "--narrative-mode",
        "pace": "--pace",
        "dialogue_density": "--dialogue-density",
        "prose_style": "--prose-style",
        "world_building_density": "--world-building-density",
        "emotion_intensity": "--emotion-intensity",
        "combat_style": "--combat-style",
        "hook_strength": "--hook-strength",
    }
    for key, value in options.items():
        if key in cli_flag_map and value:
            cmd.extend([cli_flag_map[key], value])

    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    output = result.stdout.strip() or result.stderr.strip() or "无输出"
    if result.returncode != 0:
        output = f"[exit={result.returncode}]\n{output}"

    _, derivative_rows = _derivative_summary()
    return output, _chapter_rows(), _active_project_info()["status"]


def refresh_all_state() -> Tuple[str, gr.Update, gr.Update, List[List[str]], str, str, str, str, str]:
    status = _active_project_info()["status"]
    choices = _chapter_choices()
    first = choices[0][1] if choices else None
    chapter_update = gr.update(choices=choices, value=first)
    if first:
        detail = _read_chapter_detail(int(first))
    else:
        detail = ("", "", "", "")
    derivative_text, _ = _derivative_summary()
    return status, _project_dropdown_update(), chapter_update, _chapter_rows(), *detail, derivative_text


def _build_banner() -> object:
    try:
        from PIL import Image, ImageDraw

        width, height = 1200, 360
        image = Image.new("RGB", (width, height), (17, 17, 17))
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, width - 40, height - 40), outline=(214, 179, 95), width=3)
        draw.rectangle((60, 60, width - 60, height - 60), outline=(79, 191, 159), width=1)
        draw.text((92, 92), "小说生成工作台", fill=(242, 242, 242))
        draw.text((92, 150), "项目管理 · 写作参数 · 章节生成 · 衍生内容", fill=(176, 176, 176))
        draw.text((92, 214), "直接从项目状态进入生成和阅读，不需要记命令。", fill=(176, 176, 176))
        return image
    except Exception:
        return None


def build_app() -> gr.Blocks:
    banner = _build_banner()
    initial_values = _writing_values_from_project()
    status_markdown = _active_project_info()["status"]
    chapter_choices = _chapter_choices()
    first_chapter = chapter_choices[0][1] if chapter_choices else None
    first_detail = _read_chapter_detail(int(first_chapter)) if first_chapter else ("", "", "", "")
    derivative_text, derivative_rows = _derivative_summary()

    with gr.Blocks(title="小说生成工作台", css=CSS, elem_id="studio-shell") as demo:
        gr.Markdown("# 小说生成工作台")
        if banner is not None:
            gr.Image(value=banner, label="", interactive=False, show_label=False)
        gr.Markdown("项目、参数、生成、章节和衍生内容放在同一处，按项目状态直接操作。")

        with gr.Tab("项目"):
            with gr.Row():
                with gr.Column():
                    project_title = gr.Textbox(label="标题")
                    genre = gr.Textbox(label="题材", value="玄幻修仙")
                    author = gr.Textbox(label="作者", value="AI Author")
                    chapters = gr.Number(label="计划章节数", value=100, precision=0)
                    outline = gr.Textbox(label="大纲", lines=4, placeholder="留空则自动生成")
                    world = gr.Textbox(label="世界观", lines=4, placeholder="留空则自动生成")
                    characters = gr.Textbox(label="人物设定", lines=4, placeholder="留空则自动生成")
                    create_btn = gr.Button("创建项目", variant="primary")
                with gr.Column():
                    project_selector = gr.Dropdown(
                        label="加载项目",
                        choices=_project_choices(),
                        value=get_config_manager().current_project.id if get_config_manager().current_project else None,
                        allow_custom_value=True,
                    )
                    load_btn = gr.Button("加载项目")
                    refresh_btn = gr.Button("刷新状态")
                    project_status = gr.Markdown(value=status_markdown)

        with gr.Tab("写作参数"):
            gr.Markdown("保存后会成为当前项目默认值，生成时也会直接透传。")
            with gr.Row():
                with gr.Column():
                    style = gr.Dropdown(BASE_STYLE_CHOICES, label="基础风格", value=initial_values[0])
                    style_preset = gr.Dropdown([""] + STYLE_PRESET_CHOICES, label="风格预设", value=initial_values[1])
                    perspective = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["perspective"].keys()), label="叙事视角", value=initial_values[2])
                    narrative_mode = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["narrative_mode"].keys()), label="叙事写法", value=initial_values[3])
                    pace = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["pace"].keys()), label="节奏", value=initial_values[4])
                    dialogue_density = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["dialogue_density"].keys()), label="对白密度", value=initial_values[5])
                with gr.Column():
                    prose_style = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["prose_style"].keys()), label="行文质感", value=initial_values[6])
                    world_building_density = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["world_building_density"].keys()), label="设定密度", value=initial_values[7])
                    emotion_intensity = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["emotion_intensity"].keys()), label="情绪强度", value=initial_values[8])
                    combat_style = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["combat_style"].keys()), label="战斗写法", value=initial_values[9])
                    hook_strength = gr.Dropdown(sorted(WRITING_OPTION_GROUPS["hook_strength"].keys()), label="开篇抓力", value=initial_values[10])
                    save_writing_btn = gr.Button("保存为项目默认参数", variant="primary")
                    writing_status = gr.Markdown()

        with gr.Tab("生成"):
            with gr.Row():
                with gr.Column():
                    gen_count = gr.Number(label="生成章节数", value=1, precision=0)
                    gen_start = gr.Number(label="起始章节", value=1, precision=0)
                    dry_run = gr.Checkbox(label="Dry-run", value=False)
                    no_auto_feedback = gr.Checkbox(label="禁用自动反馈", value=False)
                    generate_btn = gr.Button("开始生成", variant="primary")
                with gr.Column():
                    generation_log = gr.Textbox(label="生成日志", lines=24, max_lines=32)

        with gr.Tab("章节"):
            chapter_selector = gr.Dropdown(
                label="章节",
                choices=chapter_choices,
                value=first_chapter,
            )
            chapter_refresh = gr.Button("刷新章节")
            with gr.Row():
                with gr.Column():
                    chapter_detail = gr.Markdown(value=first_detail[0] or "选择章节后显示正文。")
                    chapter_body = gr.Textbox(label="正文", lines=24, max_lines=40, value=first_detail[3], interactive=False)
                with gr.Column():
                    chapter_plot = gr.Textbox(label="章节概要 JSON", lines=18, value=first_detail[1], interactive=False)
                    chapter_report = gr.Textbox(label="一致性报告 JSON", lines=18, value=first_detail[2], interactive=False)
            chapter_table = gr.Dataframe(
                headers=["章节号", "标题", "字数", "概要", "创建时间"],
                value=_chapter_rows(),
                interactive=False,
                wrap=True,
            )

        with gr.Tab("衍生内容"):
            derivative_status = gr.Markdown(value=derivative_text)
            derivative_table = gr.Dataframe(
                headers=["分类", "文件名", "大小", "路径"],
                value=derivative_rows,
                interactive=False,
                wrap=True,
            )

        create_btn.click(
            create_project,
            inputs=[project_title, genre, outline, world, characters, author, chapters],
            outputs=[project_status, project_selector, chapter_selector, chapter_table, chapter_detail, chapter_plot, chapter_report, chapter_body, derivative_status],
        )
        load_btn.click(
            load_project,
            inputs=project_selector,
            outputs=[project_status, project_selector, chapter_selector, chapter_table, chapter_detail, chapter_plot, chapter_report, chapter_body, derivative_status],
        )
        refresh_btn.click(
            refresh_all_state,
            inputs=[],
            outputs=[project_status, project_selector, chapter_selector, chapter_table, chapter_detail, chapter_plot, chapter_report, chapter_body, derivative_status],
        )
        save_writing_btn.click(
            save_writing_options,
            inputs=[style, style_preset, perspective, narrative_mode, pace, dialogue_density, prose_style, world_building_density, emotion_intensity, combat_style, hook_strength],
            outputs=writing_status,
        )
        generate_btn.click(
            run_generation,
            inputs=[gen_count, gen_start, dry_run, no_auto_feedback, style, style_preset, perspective, narrative_mode, pace, dialogue_density, prose_style, world_building_density, emotion_intensity, combat_style, hook_strength],
            outputs=[generation_log, chapter_table, project_status],
        )
        chapter_selector.change(
            refresh_chapter_view,
            inputs=chapter_selector,
            outputs=[chapter_detail, chapter_plot, chapter_report, chapter_body],
        )
        chapter_refresh.click(
            refresh_all_state,
            inputs=[],
            outputs=[project_status, project_selector, chapter_selector, chapter_table, chapter_detail, chapter_plot, chapter_report, chapter_body, derivative_status],
        )

    return demo


if __name__ == "__main__":
    build_app().launch(server_name="127.0.0.1", server_port=7860)
