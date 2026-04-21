#!/usr/bin/env python3
"""Local Streamlit console for novel generation."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import uuid


ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from agents.chapter_manager import ChapterManager, get_chapter_manager  # noqa: E402
from agents.config_manager import get_config_manager  # noqa: E402
from services.longform_run import (  # noqa: E402
    approval_entry_detail_parts as _approval_entry_detail_parts,
    approval_entry_summary as _approval_entry_summary,
    approval_history_summary as _approval_history_summary,
    approval_preview_text as _approval_preview_text,
    compile_chapter_rewrite_guidance,
)
from services.run_storage import (  # noqa: E402
    create_run,
    format_eta,
    latest_run_dir,
    read_log_tail,
    read_status,
)
from writing_options import (  # noqa: E402
    BASE_STYLE_CHOICES,
    STYLE_PRESET_CHOICES,
    WRITING_OPTION_GROUPS,
    normalize_writing_options,
)


RUN_SCRIPT = ROOT_DIR / "run_novel_generation.py"
EXPORT_SUFFIX = ".txt"


PAGE_CSS = """
<style>
  .stApp {
    background:
      radial-gradient(circle at top left, rgba(214, 179, 95, 0.18), transparent 35%),
      radial-gradient(circle at bottom right, rgba(79, 191, 159, 0.12), transparent 40%),
      linear-gradient(180deg, #101214 0%, #15161a 48%, #0f1114 100%);
    color: #f2f2f2;
  }
  .block-container {
    padding-top: 1.5rem;
    max-width: 1280px;
  }
  h1, h2, h3 {
    letter-spacing: -0.02em;
  }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
    border-right: 1px solid rgba(255,255,255,0.08);
  }
  .yw-card {
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    background: rgba(255,255,255,0.03);
    padding: 1rem 1.1rem;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  }
  .yw-muted {
    color: rgba(242, 242, 242, 0.72);
  }
  .yw-title {
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
  }
  .yw-subtitle {
    font-size: 0.95rem;
    color: rgba(242, 242, 242, 0.68);
    margin-bottom: 1rem;
  }
</style>
"""


def _require_streamlit() -> Any:
    try:  # pragma: no cover - optional runtime dependency for app launch
        import streamlit as streamlit_module
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard only
        raise SystemExit(
            "Streamlit 未安装。请先执行 `python -m pip install streamlit`, 然后再运行 streamlit_app.py。"
        ) from exc
    return streamlit_module


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _project_choices() -> list[str]:
    config_dir = ROOT_DIR / "config"
    if not config_dir.exists():
        return []
    return sorted(file.stem.replace("project_", "") for file in config_dir.glob("project_*.json"))


def _project_root() -> Path | None:
    config_mgr = get_config_manager()
    if config_mgr.current_project and getattr(config_mgr.generation, "output_dir", ""):
        return Path(config_mgr.generation.output_dir)
    return None


def _runs_root() -> Path | None:
    root = _project_root()
    return root / "runs" if root else None


def _metadata_file() -> Path | None:
    root = _project_root()
    return root / "metadata.json" if root else None


def _load_project_metadata() -> dict[str, Any]:
    meta_path = _metadata_file()
    if not meta_path:
        return {"chapters": []}
    data = _read_json(meta_path)
    data.setdefault("chapters", [])
    return data


def _chapter_index() -> list[dict[str, Any]]:
    data = _load_project_metadata()
    chapters = list(data.get("chapters", []))
    if chapters:
        return sorted(chapters, key=lambda item: item.get("number", 0))

    root = _project_root()
    if not root:
        return []

    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        return []

    rows: list[dict[str, Any]] = []
    for chapter_file in sorted(chapters_dir.glob("ch*.md")):
        content = chapter_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), chapter_file.stem)
        summary_match = next((line.split("**本章概要**:", 1)[1].strip() for line in lines if "**本章概要**:" in line), "")
        word_match = next((line for line in lines if "字数:" in line), "")
        number = int(chapter_file.stem[2:5]) if len(chapter_file.stem) >= 5 and chapter_file.stem[2:5].isdigit() else 0
        rows.append(
            {
                "number": number,
                "title": title,
                "word_count": int(word_match.split("字数:", 1)[1].split("|", 1)[0].strip()) if "字数:" in word_match else len(content),
                "summary": summary_match,
                "key_events": [],
                "character_appearances": [],
                "file_path": str(chapter_file),
                "created_at": chapter_file.stat().st_mtime,
            }
        )
    return sorted(rows, key=lambda item: item.get("number", 0))


def _active_project_status() -> str:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return "当前没有已加载项目。"

    project = config_mgr.current_project
    options = normalize_writing_options(project.metadata.get("writing_options", {}))
    lines = [
        f"### {project.title}",
        f"- 项目ID: `{project.id}`",
        f"- 作者: `{project.author}`",
        f"- 题材: `{project.genre}`",
        f"- 进度: `{project.current_chapter}/{project.total_chapters}`",
        f"- 更新时间: `{project.updated_at}`",
        f"- 当前模型: `{config_mgr.generation.active_provider}:{config_mgr.generation.model_name}`",
        "",
        "#### 写作参数",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in options.items() if value)
    return "\n".join(lines)


def _writing_values() -> dict[str, str]:
    config_mgr = get_config_manager()
    metadata = {}
    if config_mgr.current_project:
        metadata = config_mgr.current_project.metadata.get("writing_options", {})
    return normalize_writing_options(metadata)


def _provider_snapshot() -> dict[str, dict[str, Any]]:
    config_mgr = get_config_manager()
    snapshot: dict[str, dict[str, Any]] = {}
    for provider_name in sorted(config_mgr.generation.providers.keys()):
        snapshot[provider_name] = config_mgr.get_provider_payload(provider_name)
    return snapshot


def _provider_status_lines() -> list[str]:
    config_mgr = get_config_manager()
    lines = ["### Provider 配置"]
    for provider_name, payload in _provider_snapshot().items():
        marker = "active" if provider_name == config_mgr.generation.active_provider else "standby"
        lines.append(
            f"- `{provider_name}` · `{marker}` · model=`{payload.get('model_name', '')}` · enabled=`{payload.get('enabled', True)}`"
        )
    return lines


def _chapter_choices() -> list[tuple[str, str]]:
    return [
        (f"{item['number']:03d} · {item['title']}", str(item["number"]))
        for item in _chapter_index()
    ]


def _chapter_rows() -> list[list[Any]]:
    rows: list[list[Any]] = []
    for item in _chapter_index():
        created = item.get("created_at")
        created_text = datetime.fromtimestamp(created).strftime("%m-%d %H:%M") if isinstance(created, (int, float)) else ""
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
    matches = sorted((root / "chapters").glob(f"ch{number:03d}_*.md"))
    return matches[0] if matches else None


def _chapter_detail(number: int) -> tuple[str, str, str, str]:
    chapter_file = _chapter_file(number)
    if not chapter_file:
        return "章节不存在。", "", "", ""

    content = chapter_file.read_text(encoding="utf-8")
    lines = content.splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), chapter_file.stem)
    summary = next((line.split("**本章概要**:", 1)[1].strip() for line in lines if "**本章概要**:" in line), "")
    key_events = next((line.split("**关键事件**:", 1)[1].strip() for line in lines if "**关键事件**:" in line), "")
    report = _read_json(chapter_file.parent.parent / "consistency_reports" / f"ch{number:03d}_consistency.json")
    plot_summary = _read_json(chapter_file.parent.parent / "plot_summaries" / f"ch{number:03d}_summary.json")

    detail_lines = [
        f"### 第{number}章 · {title}",
        f"- 文件: `{chapter_file}`",
        f"- 概要: {summary or '无'}",
        f"- 关键事件: {key_events or '无'}",
        "",
        "#### 正文",
        content,
    ]

    report_text = json.dumps(report, ensure_ascii=False, indent=2) if report else "无一致性报告"
    plot_text = json.dumps(plot_summary, ensure_ascii=False, indent=2) if plot_summary else "无章节概要"
    return "\n".join(detail_lines), plot_text, report_text, content


def _derivative_summary() -> tuple[str, list[list[Any]]]:
    root = _project_root()
    if not root:
        return "当前没有已加载项目。", []

    config_mgr = get_config_manager()
    scripts_dir = Path(config_mgr.generation.scripts_dir)
    film_drama_dir = Path(config_mgr.generation.film_drama_dir)
    rows: list[list[Any]] = []
    if scripts_dir.exists():
        rows.extend(
            [file.parent.name, file.name, file.stat().st_size, str(file)]
            for file in sorted(scripts_dir.rglob("*"))
            if file.is_file()
        )
    if film_drama_dir.exists():
        rows.extend(
            ["film_drama", file.name, file.stat().st_size, str(file)]
            for file in sorted(film_drama_dir.glob("*.json"))
            if file.is_file()
        )

    text = [
        "### 衍生内容",
        f"- 脚本目录: `{scripts_dir}`",
        f"- 剧情目录: `{film_drama_dir}`",
        f"- 文件数: `{len(rows)}`",
    ]
    return "\n".join(text), rows


def _load_chapter_manager() -> ChapterManager | None:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return None
    output_dir = getattr(config_mgr.generation, "output_dir", None)
    base_dir_override = str(Path(output_dir).resolve()) if output_dir else None
    return get_chapter_manager(config_mgr.current_project.id, base_dir_override=base_dir_override)


def create_project_action(
    title: str,
    genre: str,
    outline: str,
    world: str,
    characters: str,
    author: str,
    chapters: int,
) -> str:
    config_mgr = get_config_manager()
    llm_client = None
    try:
        llm_client = config_mgr.build_generation_llm_client()
    except Exception:
        llm_client = None
    config_mgr.create_project(
        title=title.strip(),
        author=author.strip() or "AI Author",
        genre=genre.strip(),
        outline=outline.strip(),
        world_setting=world.strip(),
        character_intro=characters.strip(),
        total_chapters=int(chapters),
        llm_client=llm_client,
    )
    return _active_project_status()


def load_project_action(project_id: str) -> str:
    config_mgr = get_config_manager()
    if not project_id:
        return _active_project_status()
    project = config_mgr.load_project(project_id)
    if not project:
        return f"项目不存在: {project_id}"
    return _active_project_status()


def save_writing_options_action(options: dict[str, str]) -> str:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return "请先创建或加载项目。"
    normalized = normalize_writing_options(options)
    config_mgr.current_project.metadata["writing_options"] = normalized
    config_mgr._save_project(config_mgr.current_project)
    return "已保存写作参数。\n\n" + _active_project_status()


def save_provider_settings_action(active_provider: str, provider_updates: dict[str, dict[str, Any]]) -> str:
    config_mgr = get_config_manager()
    config_mgr.update_generation_config(
        active_provider=active_provider,
        provider_updates=provider_updates,
        persist=True,
    )
    return "已保存 Provider 配置。\n\n" + "\n".join(_provider_status_lines())


def _append_writing_option_flags(cmd: list[str], options: dict[str, str]) -> None:
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


def run_generation_action(
    count: int,
    start: int,
    dry_run: bool,
    no_auto_feedback: bool,
    options: dict[str, str],
) -> dict[str, str]:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return {"message": "请先创建或加载项目。"}

    normalized = normalize_writing_options(options)
    config_mgr.current_project.metadata["writing_options"] = normalized
    config_mgr._save_project(config_mgr.current_project)
    project_dir = Path(config_mgr.generation.output_dir).resolve()
    run_id = str(uuid.uuid4())

    cmd = [sys.executable, str(RUN_SCRIPT), "--generate", str(int(count))]
    if int(start) > 0:
        cmd.extend(["--start", str(int(start))])
    if dry_run:
        cmd.append("--dry-run")
    if no_auto_feedback:
        cmd.append("--no-auto-feedback")
    _append_writing_option_flags(cmd, normalized)

    run_dir = create_run(
        project_dir=project_dir,
        run_id=run_id,
        project_id=config_mgr.current_project.id,
        command=cmd[1:],
    )
    cmd.extend(["--run-id", run_id, "--run-dir", str(run_dir)])
    _launch_cli_process(run_dir, cmd)

    return {
        "message": f"任务已启动，Run ID: `{run_id}`",
        "run_id": run_id,
        "run_dir": str(run_dir),
    }


def _launch_cli_process(run_dir: Path, cmd: list[str]) -> None:
    with (run_dir / "stdout.log").open("a", encoding="utf-8") as stdout_file, (
        run_dir / "stderr.log"
    ).open("a", encoding="utf-8") as stderr_file:
        subprocess.Popen(  # noqa: S603
            cmd,
            cwd=str(ROOT_DIR),
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
        )


def run_full_novel_action(chapters_per_volume: int, approval_mode: str, auto_approve: bool) -> dict[str, str]:
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        return {"message": "请先创建或加载项目。"}

    project_dir = Path(config_mgr.generation.output_dir).resolve()
    run_id = str(uuid.uuid4())
    cmd = [
        sys.executable,
        str(RUN_SCRIPT),
        "--generate-full",
        "--chapters-per-volume",
        str(int(chapters_per_volume)),
        "--approval-mode",
        approval_mode,
        "--run-id",
        run_id,
    ]
    if auto_approve:
        cmd.append("--auto-approve")

    run_dir = create_run(
        project_dir=project_dir,
        run_id=run_id,
        project_id=config_mgr.current_project.id,
        command=cmd[1:],
    )
    cmd.extend(["--run-dir", str(run_dir)])
    _launch_cli_process(run_dir, cmd)
    return {
        "message": f"长篇任务已启动，Run ID: `{run_id}`",
        "run_id": run_id,
        "run_dir": str(run_dir),
    }


def _approval_payload_file(run_dir: Path, payload: dict[str, Any]) -> Path:
    payload_path = run_dir / f"approval_payload_{uuid.uuid4().hex[:8]}.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload_path


def resume_longform_action(run_dir: Path, pending_state_path: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, str]:
    status = read_status(run_dir)
    run_id = status.get("run_id") or run_dir.name
    cmd = [
        sys.executable,
        str(RUN_SCRIPT),
        "--generate-full",
        "--run-id",
        str(run_id),
        "--run-dir",
        str(run_dir),
        "--resume-state",
        pending_state_path,
        "--submit-approval",
        action,
    ]
    if payload:
        payload_path = _approval_payload_file(run_dir, payload)
        cmd.extend(["--approval-payload", str(payload_path)])
    _launch_cli_process(run_dir, cmd)
    return {
        "message": f"已提交 `{action}`，正在恢复长篇任务。",
        "run_id": str(run_id),
        "run_dir": str(run_dir),
    }


def export_text_action(start: int, end: int | None = None) -> str:
    config_mgr = get_config_manager()
    chapter_mgr = _load_chapter_manager()
    if not config_mgr.current_project or chapter_mgr is None:
        return "请先创建或加载项目。"

    output_dir = Path(config_mgr.generation.output_dir) if getattr(config_mgr.generation, "output_dir", "") else Path(ROOT_DIR / "novels")
    safe_title = config_mgr.current_project.title.replace("/", "-").strip()
    output_path = output_dir / f"{safe_title}_{config_mgr.current_project.id}{EXPORT_SUFFIX}"
    count = chapter_mgr.export_to_text(str(output_path), start=start, end=end)
    if count == 0:
        return "当前没有可导出的章节。"
    return f"已导出 {count} 行到 `{output_path}`"


def switch_active_run_action(run_id: str) -> dict[str, str]:
    runs_root = _runs_root()
    if not runs_root or not run_id:
        return {"message": "没有可切换的运行任务。", "run_id": "", "run_dir": ""}
    run_dir = runs_root / run_id
    if not run_dir.exists():
        return {"message": f"运行任务不存在: {run_id}", "run_id": "", "run_dir": ""}
    return {
        "message": f"已切换到运行任务 `{run_id}`。",
        "run_id": run_id,
        "run_dir": str(run_dir),
    }


def _active_run_id_from_state() -> str:
    try:
        import streamlit as st_mod
        return str(st_mod.session_state.get("yw_active_run_id", "") or "")
    except ModuleNotFoundError:
        return ""


def _pause_reason_label(reason: str) -> str:
    mapping = {
        "outline_review": "大纲审批",
        "volume_review": "分卷审批",
        "risk_review": "风险复核",
        "chapter_review": "章节复核",
    }
    return mapping.get(str(reason or "").strip(), str(reason or "").strip())


def _run_status_label(status: str) -> str:
    mapping = {
        "queued": "排队中",
        "running": "运行中",
        "paused": "已暂停",
        "succeeded": "已完成",
        "failed": "失败",
    }
    return mapping.get(str(status or "").strip(), str(status or "").strip())


def _run_stage_label(stage: str) -> str:
    mapping = {
        "init": "初始化",
        "outline.generate": "生成大纲",
        "outline.review": "大纲审批",
        "volume.write": "分卷写作",
        "volume.review": "分卷审批",
        "risk.review": "风险复核",
        "chapter.review": "章节复核",
        "chapter.generate": "章节生成",
    }
    return mapping.get(str(stage or "").strip(), str(stage or "").strip())


def _recent_run_preview(run_id: str) -> dict[str, str | bool]:
    runs_root = _runs_root()
    if not runs_root or not run_id:
        return {
            "stdout": "",
            "stderr": "",
            "run_dir": "",
            "status": "",
            "pause_reason": "",
            "has_pending_review": False,
            "latest_approval": "",
            "approval_history": "",
        }
    run_dir = runs_root / run_id
    if not run_dir.exists():
        return {
            "stdout": "",
            "stderr": "",
            "run_dir": "",
            "status": "",
            "pause_reason": "",
            "has_pending_review": False,
            "latest_approval": "",
            "approval_history": "",
        }
    status = read_status(run_dir)
    state = _read_json(Path(str(status.get("longform_state_path", "") or "")))
    approval_summary = _approval_history_summary(state, limit=1)
    approval_history = _approval_history_summary(state, limit=3)
    return {
        "stdout": read_log_tail(run_dir, "stdout", max_chars=1200),
        "stderr": read_log_tail(run_dir, "stderr", max_chars=800),
        "run_dir": str(run_dir),
        "status": _run_status_label(str(status.get("status", "") or "")),
        "pause_reason": _pause_reason_label(str(status.get("pause_reason", "") or "")),
        "has_pending_review": bool(status.get("pending_state_path")),
        "latest_approval": approval_summary,
        "approval_history": approval_history,
    }


def _render_project_sidebar(st_mod: Any) -> None:
    config_mgr = get_config_manager()
    st_mod.sidebar.markdown("## 项目")
    choices = _project_choices()
    current_value = config_mgr.current_project.id if config_mgr.current_project else None
    selected_project = st_mod.sidebar.selectbox(
        "加载项目",
        options=["", *choices],
        index=(["", *choices]).index(current_value) if current_value in choices else 0,
        key="yw_project_selector",
    )
    if st_mod.sidebar.button("加载项目", use_container_width=True):
        st_mod.session_state["yw_status"] = load_project_action(selected_project)
        st_mod.rerun()

    with st_mod.sidebar.form("create_project_form", border=True):
        st_mod.write("### 新建项目")
        title = st_mod.text_input("标题", value=config_mgr.current_project.title if config_mgr.current_project else "太古魔帝传")
        author = st_mod.text_input("作者", value=config_mgr.current_project.author if config_mgr.current_project else "AI Author")
        genre = st_mod.text_input("题材", value=config_mgr.current_project.genre if config_mgr.current_project else "玄幻修仙")
        chapters = st_mod.number_input("计划章节数", min_value=1, max_value=2000, value=config_mgr.current_project.total_chapters if config_mgr.current_project else 240, step=1)
        outline = st_mod.text_area(
            "大纲",
            value=config_mgr.current_project.outline if config_mgr.current_project else "",
            height=120,
            help="留空则自动生成",
        )
        world = st_mod.text_area(
            "世界观",
            value=config_mgr.current_project.world_setting if config_mgr.current_project else "",
            height=80,
            help="留空则自动生成",
        )
        characters = st_mod.text_area(
            "人物设定",
            value=config_mgr.current_project.character_intro if config_mgr.current_project else "",
            height=80,
            help="留空则自动生成",
        )
        if st_mod.form_submit_button("创建项目", use_container_width=True):
            st_mod.session_state["yw_status"] = create_project_action(title, genre, outline, world, characters, author, chapters)
            st_mod.rerun()

    st_mod.sidebar.markdown("### 当前项目")
    st_mod.sidebar.markdown(_active_project_status())


def _render_writing_tab(st_mod: Any) -> None:
    values = _writing_values()
    st_mod.markdown("### 写作参数")
    st_mod.markdown("保存后会写入当前项目 metadata, 并在生成时透传到 CLI。")

    with st_mod.form("writing_options_form", border=True):
        cols = st_mod.columns(2)
        option_order = [
            ("style", "基础风格", BASE_STYLE_CHOICES),
            ("style_preset", "风格预设", ["", *STYLE_PRESET_CHOICES]),
            ("perspective", "叙事视角", sorted(WRITING_OPTION_GROUPS["perspective"].keys())),
            ("narrative_mode", "叙事写法", sorted(WRITING_OPTION_GROUPS["narrative_mode"].keys())),
            ("pace", "节奏", sorted(WRITING_OPTION_GROUPS["pace"].keys())),
            ("dialogue_density", "对白密度", sorted(WRITING_OPTION_GROUPS["dialogue_density"].keys())),
            ("prose_style", "行文质感", sorted(WRITING_OPTION_GROUPS["prose_style"].keys())),
            ("world_building_density", "设定密度", sorted(WRITING_OPTION_GROUPS["world_building_density"].keys())),
            ("emotion_intensity", "情绪强度", sorted(WRITING_OPTION_GROUPS["emotion_intensity"].keys())),
            ("combat_style", "战斗写法", sorted(WRITING_OPTION_GROUPS["combat_style"].keys())),
            ("hook_strength", "开篇抓力", sorted(WRITING_OPTION_GROUPS["hook_strength"].keys())),
        ]
        collected: dict[str, str] = {}
        for idx, (key, label, options) in enumerate(option_order):
            with cols[idx % 2]:
                current_value = values.get(key, "")
                option_index = options.index(current_value) if current_value in options else 0
                collected[key] = st_mod.selectbox(label, options=options, index=option_index, key=f"yw_{key}")

        if st_mod.form_submit_button("保存写作参数", use_container_width=True, type="primary"):
            st_mod.session_state["yw_status"] = save_writing_options_action(collected)
            st_mod.rerun()

    st_mod.markdown(st_mod.session_state.get("yw_status", ""))


def _render_provider_tab(st_mod: Any) -> None:
    config_mgr = get_config_manager()
    providers = _provider_snapshot()
    provider_names = list(providers.keys())
    active_provider = config_mgr.generation.active_provider if config_mgr.generation.active_provider in provider_names else provider_names[0]

    st_mod.markdown("### LLM Provider")
    st_mod.markdown("这里配置生成主链路使用的文本模型，同时保留 Doubao 的视频提示词增强配置。")

    with st_mod.form("provider_settings_form", border=True):
        selected_active = st_mod.selectbox(
            "默认文本 Provider",
            options=provider_names,
            index=provider_names.index(active_provider),
            format_func=lambda value: f"{value} · {providers[value].get('model_name', '')}",
        )
        updates: dict[str, dict[str, Any]] = {}
        for provider_name in provider_names:
            payload = providers[provider_name]
            with st_mod.expander(f"{provider_name} 配置", expanded=provider_name == selected_active):
                enabled = st_mod.checkbox(
                    "启用",
                    value=bool(payload.get("enabled", True)),
                    key=f"yw_provider_enabled_{provider_name}",
                )
                label = st_mod.text_input(
                    "显示名称",
                    value=str(payload.get("label", provider_name)),
                    key=f"yw_provider_label_{provider_name}",
                )
                model_name = st_mod.text_input(
                    "模型名",
                    value=str(payload.get("model_name", "")),
                    key=f"yw_provider_model_{provider_name}",
                )
                api_key = st_mod.text_input(
                    "API Key",
                    value=str(payload.get("api_key", "")),
                    type="password",
                    key=f"yw_provider_key_{provider_name}",
                )
                base_url = st_mod.text_input(
                    "Base URL",
                    value=str(payload.get("base_url", "")),
                    key=f"yw_provider_base_url_{provider_name}",
                )
                api_host = st_mod.text_input(
                    "API Host",
                    value=str(payload.get("api_host", "")),
                    key=f"yw_provider_api_host_{provider_name}",
                )
                temperature = st_mod.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.5,
                    value=float(payload.get("temperature", 0.7)),
                    step=0.1,
                    key=f"yw_provider_temperature_{provider_name}",
                )
                max_tokens = st_mod.number_input(
                    "Max Tokens",
                    min_value=256,
                    max_value=65536,
                    value=int(payload.get("max_tokens", 8192)),
                    step=256,
                    key=f"yw_provider_max_tokens_{provider_name}",
                )
                use_cli = st_mod.checkbox(
                    "优先使用 CLI",
                    value=bool(payload.get("use_cli", False)),
                    key=f"yw_provider_use_cli_{provider_name}",
                    disabled=provider_name != "kimi",
                )
                system_prompt = st_mod.text_area(
                    "System Prompt",
                    value=str(payload.get("system_prompt", "")),
                    height=120,
                    key=f"yw_provider_system_prompt_{provider_name}",
                )
                updates[provider_name] = {
                    "provider": provider_name,
                    "label": label,
                    "enabled": enabled,
                    "api_key": api_key.strip(),
                    "base_url": base_url.strip(),
                    "api_host": api_host.strip(),
                    "model_name": model_name.strip(),
                    "temperature": float(temperature),
                    "max_tokens": int(max_tokens),
                    "use_cli": bool(use_cli),
                    "system_prompt": system_prompt.strip(),
                }

        if st_mod.form_submit_button("保存 Provider 配置", use_container_width=True, type="primary"):
            st_mod.session_state["yw_status"] = save_provider_settings_action(selected_active, updates)
            st_mod.rerun()

    st_mod.markdown("\n".join(_provider_status_lines()))
    st_mod.markdown(st_mod.session_state.get("yw_status", ""))


def _render_generation_tab(st_mod: Any) -> None:
    config_mgr = get_config_manager()
    st_mod.markdown("### 生成控制台")
    if not config_mgr.current_project:
        st_mod.info("先在侧边栏创建或加载项目。")
        return

    left, right = st_mod.columns([1, 1])
    with left:
        count = st_mod.number_input("生成章节数", min_value=1, max_value=20, value=1, step=1)
        start = st_mod.number_input("起始章节", min_value=1, max_value=2000, value=max(config_mgr.current_project.current_chapter + 1, 1), step=1)
        dry_run = st_mod.checkbox("Dry-run", value=False)
        no_auto_feedback = st_mod.checkbox("禁用自动反馈", value=False)
        if st_mod.button("开始生成", type="primary", use_container_width=True):
            launch = run_generation_action(
                int(count),
                int(start),
                dry_run,
                no_auto_feedback,
                _writing_values(),
            )
            st_mod.session_state["yw_generation_log"] = launch.get("message", "")
            st_mod.session_state["yw_active_run_id"] = launch.get("run_id")
            st_mod.session_state["yw_active_run_dir"] = launch.get("run_dir")
            st_mod.rerun()
    with right:
        summary = config_mgr.get_project_summary()
        st_mod.metric("当前章节", f"{summary.get('current_chapter', 0)} / {summary.get('total_chapters', 0)}")
        st_mod.metric("完成度", f"{summary.get('progress_percent', 0):.1f}%")
        st_mod.markdown(st_mod.session_state.get("yw_generation_log", ""))
        with st_mod.expander("整本长篇生成", expanded=False):
            chapters_per_volume = st_mod.number_input(
                "每卷章节数",
                min_value=1,
                max_value=200,
                value=60,
                step=1,
                key="yw_longform_chapters_per_volume",
            )
            approval_mode = st_mod.selectbox(
                "审批节点",
                options=["outline+volume", "outline", "volume", "none"],
                index=0,
                key="yw_longform_approval_mode",
            )
            auto_approve = st_mod.checkbox("自动跳过审批", value=False, key="yw_longform_auto_approve")
            if st_mod.button("启动整本生成", use_container_width=True, key="yw_start_longform"):
                launch = run_full_novel_action(int(chapters_per_volume), approval_mode, auto_approve)
                st_mod.session_state["yw_generation_log"] = launch.get("message", "")
                st_mod.session_state["yw_active_run_id"] = launch.get("run_id")
                st_mod.session_state["yw_active_run_dir"] = launch.get("run_dir")
                st_mod.rerun()
        _render_run_monitor(st_mod)
        _render_pending_review(st_mod)
        recent_rows = _recent_run_rows()
        if recent_rows:
            st_mod.markdown("#### 最近运行")
            st_mod.dataframe(
                recent_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    0: "当前",
                    1: "Run ID",
                    2: "状态",
                    3: "阶段",
                    4: "进度",
                    5: "排队指令首行",
                    6: "最近审批",
                },
            )
            run_ids = [row[1] for row in recent_rows]
            active_run_id = _active_run_id_from_state()
            selected_run_id = st_mod.selectbox(
                "切换查看运行任务",
                options=run_ids,
                index=run_ids.index(active_run_id) if active_run_id in run_ids else 0,
                key="yw_recent_run_selector",
            )
            preview = _recent_run_preview(selected_run_id)
            if preview["run_dir"]:
                st_mod.caption(f"所选运行目录: `{preview['run_dir']}`")
                status_line = f"状态: {preview['status'] or 'unknown'}"
                if preview["pause_reason"]:
                    status_line += f" | 暂停原因: {preview['pause_reason']}"
                if preview["has_pending_review"]:
                    status_line += " | 存在待审批节点"
                st_mod.caption(status_line)
                if preview["latest_approval"]:
                    st_mod.caption(f"最近审批: {preview['latest_approval'].splitlines()[0]}")
                if preview["approval_history"]:
                    st_mod.code(preview["approval_history"], language="text")
                st_mod.text_area("所选运行 stdout 预览", value=preview["stdout"], height=120)
                if preview["stderr"]:
                    st_mod.text_area("所选运行 stderr 预览", value=preview["stderr"], height=80)
            if st_mod.button("切换到所选运行", use_container_width=True, key="yw_switch_recent_run"):
                result = switch_active_run_action(selected_run_id)
                st_mod.session_state["yw_generation_log"] = result["message"]
                if result["run_id"]:
                    st_mod.session_state["yw_active_run_id"] = result["run_id"]
                    st_mod.session_state["yw_active_run_dir"] = result["run_dir"]
                st_mod.rerun()


def _resolve_active_run_dir() -> Path | None:
    session_run_dir = st_state = None
    try:
        import streamlit as st_mod
        st_state = st_mod.session_state
    except ModuleNotFoundError:
        st_state = None

    if st_state:
        session_run_dir = st_state.get("yw_active_run_dir")
        if session_run_dir:
            return Path(session_run_dir)

    root = _project_root()
    if not root:
        return None
    return latest_run_dir(root)


def _run_monitor_payload(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {
            "status": {},
            "stdout": "",
            "stderr": "",
            "run_dir": None,
            "is_active": False,
            "queued_volume_guidance": "",
        }
    status = read_status(run_dir)
    run_status = status.get("status")
    return {
        "status": status,
        "stdout": read_log_tail(run_dir, "stdout"),
        "stderr": read_log_tail(run_dir, "stderr"),
        "run_dir": str(run_dir),
        "is_active": run_status in {"queued", "running"},
        "queued_volume_guidance": str(status.get("queued_volume_guidance", "") or ""),
    }


def _recent_run_rows(limit: int = 5) -> list[list[str]]:
    runs_root = _runs_root()
    if not runs_root or not runs_root.exists():
        return []

    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    run_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    active_run_id = _active_run_id_from_state()

    rows: list[list[str]] = []
    for run_dir in run_dirs[:limit]:
        status = read_status(run_dir)
        if not status:
            continue
        guidance = str(status.get("queued_volume_guidance", "") or "").strip()
        guidance_head = guidance.splitlines()[0] if guidance else ""
        state = _read_json(Path(str(status.get("longform_state_path", "") or "")))
        approval_summary = _approval_history_summary(state, limit=1)
        approval_head = approval_summary.splitlines()[0] if approval_summary else ""
        rows.append(
            [
                "当前" if run_dir.name == active_run_id else "",
                run_dir.name,
                _run_status_label(str(status.get("status", "unknown"))),
                _run_stage_label(str(status.get("current_stage", "init"))),
                f"{status.get('chapters_completed', 0)} / {status.get('chapters_total', 0)}",
                guidance_head,
                approval_head,
            ]
        )
    return rows


def _pending_review_payload(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {}
    status = read_status(run_dir)
    pending_state_path = status.get("pending_state_path")
    if not pending_state_path:
        return {}
    payload = _read_json(Path(pending_state_path))
    if not payload:
        return {}
    payload["pending_state_path"] = pending_state_path
    return payload


def _non_empty_lines(values: list[str]) -> str:
    items = [str(item).strip() for item in values if str(item).strip()]
    return "\n".join(f"- {item}" for item in items)


def _chapter_review_structured_sections(review_payload: dict[str, Any]) -> list[tuple[str, str]]:
    issue_types = [str(item).strip() for item in review_payload.get("issue_types", []) if str(item).strip()]
    warning_issues = [str(item).strip() for item in review_payload.get("warning_issues", []) if str(item).strip()]
    rewrite_plan = review_payload.get("rewrite_plan", {}) or {}
    issue_categories = [
        str(item).strip() for item in rewrite_plan.get("issue_categories", []) if str(item).strip()
    ]

    sections: list[tuple[str, str]] = []
    if issue_types:
        sections.append(("问题类型", _non_empty_lines(issue_types)))
    if issue_categories:
        sections.append(("问题分类", _non_empty_lines(issue_categories)))
    if warning_issues:
        sections.append(("语义告警", _non_empty_lines(warning_issues)))
    return sections


def _chapter_review_evidence(review_payload: dict[str, Any]) -> list[tuple[str, str]]:
    anti_drift = review_payload.get("anti_drift_details", {}) or {}
    chapter_intent_contract = review_payload.get("chapter_intent_contract", {}) or {}
    semantic_review = review_payload.get("semantic_review", {}) or {}
    rewrite_plan = review_payload.get("rewrite_plan", {}) or {}

    sections: list[tuple[str, str]] = []

    goal_lock = str(anti_drift.get("goal_lock", "") or "").strip()
    if goal_lock:
        lines = [f"- 当前目标锁: {goal_lock}"]
        if anti_drift.get("summary_alignment") is not None:
            lines.append(f"- 摘要对齐: {bool(anti_drift.get('summary_alignment'))}")
        if anti_drift.get("body_alignment") is not None:
            lines.append(f"- 正文对齐: {bool(anti_drift.get('body_alignment'))}")
        goal_terms = [str(item).strip() for item in anti_drift.get("goal_terms", []) if str(item).strip()]
        if goal_terms:
            lines.append(f"- 命中词: {' / '.join(goal_terms[:6])}")
        matched_fragments = [str(item).strip() for item in anti_drift.get("matched_fragments", []) if str(item).strip()]
        if matched_fragments:
            lines.append("- 已命中片段:")
            lines.extend(f"  - {item}" for item in matched_fragments[:3])
        unaligned_fragments = [str(item).strip() for item in anti_drift.get("unaligned_fragments", []) if str(item).strip()]
        if unaligned_fragments:
            lines.append("- 未对齐片段:")
            lines.extend(f"  - {item}" for item in unaligned_fragments[:3])
        sections.append(("目标锁证据", "\n".join(lines)))

    bridge_results = anti_drift.get("bridge_results", []) or []
    if bridge_results:
        lines = [
            f"- 新设定预算: {anti_drift.get('budget', 0)}",
            f"- 引入片段数: {anti_drift.get('intro_count', 0)}",
        ]
        unbridged_fragments = [str(item).strip() for item in anti_drift.get("unbridged_fragments", []) if str(item).strip()]
        if unbridged_fragments:
            lines.append("- 未桥接新设定:")
            lines.extend(f"  - {item}" for item in unbridged_fragments[:3])
        sections.append(("结构漂移证据", "\n".join(lines)))

    if chapter_intent_contract:
        lines = []
        planned_action = str(chapter_intent_contract.get("planned_action", "") or "").strip()
        if planned_action:
            lines.append(f"- 本章计划动作: {planned_action}")
        contract_goal_lock = str(chapter_intent_contract.get("goal_lock", "") or "").strip()
        if contract_goal_lock:
            lines.append(f"- 合同目标锁: {contract_goal_lock}")
        success_checks = [
            str(item).strip() for item in chapter_intent_contract.get("success_checks", []) if str(item).strip()
        ]
        if success_checks:
            lines.append("- 执行合同:")
            lines.extend(f"  - {item}" for item in success_checks[:4])
        sections.append(("生成前执行合同", "\n".join(lines)))

    semantic_issues = semantic_review.get("issues", []) or []
    if semantic_issues:
        lines = [f"- warning_only: {bool(semantic_review.get('warning_only'))}"]
        for item in semantic_issues[:4]:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "") or "").strip()
            message = str(item.get("message", "") or "").strip()
            if category or message:
                lines.append(f"- {category or 'issue'}: {message}")
        sections.append(("语义复核", "\n".join(lines)))

    if rewrite_plan:
        lines = []
        must_keep = [str(item).strip() for item in rewrite_plan.get("must_keep", []) if str(item).strip()]
        fixes = [str(item).strip() for item in rewrite_plan.get("fixes", []) if str(item).strip()]
        success_criteria = [
            str(item).strip() for item in rewrite_plan.get("success_criteria", []) if str(item).strip()
        ]
        operations = [item for item in rewrite_plan.get("operations", []) if isinstance(item, dict)]
        if must_keep:
            lines.append("- 保留要求:")
            lines.extend(f"  - {item}" for item in must_keep[:3])
        if fixes:
            lines.append("- 本次修复:")
            lines.extend(f"  - {item}" for item in fixes[:4])
        if success_criteria:
            lines.append("- 验收条件:")
            lines.extend(f"  - {item}" for item in success_criteria[:4])
        if operations:
            lines.append("- Patch 操作:")
            for item in operations[:4]:
                phase = str(item.get("phase", "") or "").strip()
                action = str(item.get("action", "") or "").strip()
                target = str(item.get("target", "") or "").strip()
                instruction = str(item.get("instruction", "") or "").strip()
                header = " / ".join(part for part in (phase, action, target) if part)
                if header and instruction:
                    lines.append(f"  - {header}: {instruction}")
                elif instruction:
                    lines.append(f"  - {instruction}")
        sections.append(("结构化重写方案", "\n".join(lines)))

    return sections


def _chapter_review_resume_payload(review_payload: dict[str, Any], extra_notes: str) -> dict[str, Any]:
    rewrite_plan = dict(review_payload.get("rewrite_plan", {}) or {})
    notes = str(extra_notes or "").strip()
    if not rewrite_plan:
        return {"chapter_rewrite_guidance": notes}
    guidance = compile_chapter_rewrite_guidance(rewrite_plan, extra_notes=notes)
    payload: dict[str, Any] = {
        "chapter_rewrite_guidance": guidance or notes,
    }
    if rewrite_plan:
        payload["chapter_rewrite_plan"] = rewrite_plan
    if notes:
        payload["notes"] = notes
    return payload


def _risk_review_summary(payload: dict[str, Any]) -> str:
    review_payload = payload.get("review_payload", {})
    lines = [
        f"风险等级: {review_payload.get('risk_level', 'unknown')}",
        f"卷范围: {review_payload.get('volume_start_chapter', 0)}-{review_payload.get('volume_end_chapter', 0)}",
        f"低分章节数: {review_payload.get('low_score_chapter_count', 0)}",
        f"缺失关键事件数: {review_payload.get('total_missing_events', 0)}",
        "",
        review_payload.get("summary", "未提供风险摘要。"),
    ]
    for item in review_payload.get("at_risk_chapters", [])[:5]:
        recommendations = "；".join(item.get("recommendations", [])[:2]) or "无额外建议"
        lines.append(
            f"- 第 {item.get('chapter_number', 0)} 章 · 分数 {item.get('overall_score', 0)} · "
            f"缺失事件 {item.get('missing_events_count', 0)} · {recommendations}"
        )
    return "\n".join(lines)


def _volume_review_summary(payload: dict[str, Any]) -> str:
    review_payload = payload.get("review_payload", {})
    lines = [
        f"卷范围: {review_payload.get('volume_start_chapter', 0)}-{review_payload.get('volume_end_chapter', 0)}",
        f"已生成章节: {review_payload.get('generated_chapter_count', 0)} / {review_payload.get('planned_chapter_count', 0)}",
        f"总字数: {review_payload.get('total_word_count', 0)}",
    ]
    registry_summary = str(review_payload.get("cross_volume_registry_summary", "") or "").strip()
    if registry_summary:
        lines.extend(["", "跨卷状态:", registry_summary])
    opening_summary = str(review_payload.get("opening_summary", "")).strip()
    closing_summary = str(review_payload.get("closing_summary", "")).strip()
    if opening_summary:
        lines.extend(["", f"卷开篇摘要: {opening_summary}"])
    if closing_summary and closing_summary != opening_summary:
        lines.append(f"卷收束摘要: {closing_summary}")
    for item in review_payload.get("chapter_highlights", [])[:8]:
        key_events = "；".join(item.get("key_events", [])[:3]) or "无关键事件摘要"
        chapter_summary = item.get("summary", "") or "暂无章节摘要"
        lines.append(
            f"- 第 {item.get('chapter_number', 0)} 章《{item.get('title', '')}》 · "
            f"{item.get('word_count', 0)} 字 · {chapter_summary} · 关键事件: {key_events}"
        )
    return "\n".join(lines)


def _volume_registry_defaults(review_payload: dict[str, Any]) -> dict[str, str]:
    registry = review_payload.get("cross_volume_registry", {}) or {}
    return {
        "unresolved_goals": "\n".join(
            str(item).strip() for item in registry.get("unresolved_goals", []) if str(item).strip()
        ),
        "open_promises": "\n".join(
            str(item).strip() for item in registry.get("open_promises", []) if str(item).strip()
        ),
        "dangling_settings": "\n".join(
            str(item).strip() for item in registry.get("dangling_settings", []) if str(item).strip()
        ),
    }


def _volume_guidance_draft(review_payload: dict[str, Any]) -> dict[str, str]:
    registry = review_payload.get("cross_volume_registry", {}) or {}
    highlights = review_payload.get("chapter_highlights", []) or []

    unresolved_goals = [str(item).strip() for item in registry.get("unresolved_goals", []) if str(item).strip()]
    open_promises = [str(item).strip() for item in registry.get("open_promises", []) if str(item).strip()]
    dangling_settings = [str(item).strip() for item in registry.get("dangling_settings", []) if str(item).strip()]

    must_recover_candidates = open_promises[:2] or unresolved_goals[:1]
    relationship_focus = ""
    tone_target = ""
    extra_notes = ""

    for item in highlights:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary", "") or "").strip()
        title = str(item.get("title", "") or "").strip()
        if summary and not extra_notes:
            extra_notes = f"延续本卷收束态势，优先接住《{title or '本卷后段'}》里形成的局势：{summary[:80]}"
        key_events = [str(event).strip() for event in item.get("key_events", []) if str(event).strip()]
        if key_events and not relationship_focus:
            relationship_focus = "围绕本卷后段关键事件继续施压相关人物关系：" + "；".join(key_events[:2])
        if summary and not tone_target:
            if any(marker in summary for marker in ("反转", "危机", "死守", "追击", "冲突", "压迫")):
                tone_target = "延续高压推进，避免松散转场"
            elif any(marker in summary for marker in ("收束", "余波", "恢复", "修整")):
                tone_target = "保持收束后的余波感，避免突然换档"

    must_avoid_parts: list[str] = []
    if dangling_settings:
        must_avoid_parts.append("不要扩写尚未桥接的新设定")
    if unresolved_goals:
        must_avoid_parts.append("不要让支线闲笔冲散当前目标锁")

    return {
        "must_recover": "；".join(must_recover_candidates),
        "relationship_focus": relationship_focus,
        "must_avoid": "；".join(must_avoid_parts),
        "tone_target": tone_target,
        "extra_notes": extra_notes,
    }


def _queued_guidance_summary(status: dict[str, Any]) -> str:
    queued_guidance = str(status.get("queued_volume_guidance", "") or "").strip()
    if queued_guidance:
        return queued_guidance
    longform_state_path = status.get("longform_state_path")
    if not longform_state_path:
        return ""
    state = _read_json(Path(longform_state_path))
    guidance = str(state.get("next_volume_guidance", "")).strip()
    if not guidance:
        return ""
    return guidance


def _longform_control_panel_sections(status: dict[str, Any]) -> list[tuple[str, str]]:
    longform_state_path = status.get("longform_state_path")
    if not longform_state_path:
        return []

    state = _read_json(Path(longform_state_path))
    if not state:
        return []

    sections: list[tuple[str, str]] = []

    payload = state.get("next_volume_guidance_payload", {}) or {}
    payload_lines: list[str] = []
    goal_lock = str(payload.get("goal_lock", "") or "").strip()
    if goal_lock:
        payload_lines.append(f"- 当前 goal_lock: {goal_lock}")
    for label, key in (
        ("必须回收", "must_recover"),
        ("人物关系", "relationship_focus"),
        ("明确避免", "must_avoid"),
        ("目标基调", "tone_target"),
        ("新设定预算", "new_setting_budget"),
        ("防漂移备注", "anti_drift_notes"),
        ("补充说明", "extra_notes"),
    ):
        value = str(payload.get(key, "") or "").strip()
        if value:
            payload_lines.append(f"- {label}: {value}")
    if payload_lines:
        sections.append(("卷级控制面板", "\n".join(payload_lines)))

    registry = state.get("cross_volume_registry", {}) or {}
    registry_lines: list[str] = []
    for label, key in (
        ("跨卷未完成目标", "unresolved_goals"),
        ("尚未回收承诺/伏笔", "open_promises"),
        ("已引入但未桥接设定", "dangling_settings"),
    ):
        values = [str(item).strip() for item in registry.get(key, []) if str(item).strip()]
        if values:
            registry_lines.append(f"- {label}: {'；'.join(values[:5])}")
    if registry_lines:
        sections.append(("跨卷状态", "\n".join(registry_lines)))

    approval_history_summary = _approval_history_summary(state)
    if approval_history_summary:
        sections.append(("审批轨迹", approval_history_summary))

    pending_state_path = status.get("pending_state_path")
    if pending_state_path:
        pending_payload = _read_json(Path(pending_state_path))
        review_payload = pending_payload.get("review_payload", {}) if isinstance(pending_payload, dict) else {}
        checkpoint_type = str(pending_payload.get("checkpoint_type", "") or "").strip()
        pending_lines = []
        if checkpoint_type:
            pending_lines.append(f"- 待处理节点: {checkpoint_type}")
        summary = str(review_payload.get("summary", "") or "").strip()
        if summary:
            pending_lines.append(f"- 摘要: {summary}")
        issue_types = [str(item).strip() for item in review_payload.get("issue_types", []) if str(item).strip()]
        if issue_types:
            pending_lines.append(f"- 问题类型: {' / '.join(issue_types[:4])}")
        blocking_issues = [str(item).strip() for item in review_payload.get("blocking_issues", []) if str(item).strip()]
        if blocking_issues:
            pending_lines.append(f"- 首条阻断: {blocking_issues[0]}")
        if pending_lines:
            sections.append(("最近待审批", "\n".join(pending_lines)))

    return sections


def _render_run_status_summary(st_mod: Any, payload: dict[str, Any]) -> None:
    status = payload["status"]
    if not status:
        st_mod.info("暂无运行中的生成任务。")
        return

    metric_cols = st_mod.columns(4)
    metric_cols[0].metric("任务状态", status.get("status", "unknown"))
    metric_cols[1].metric("当前阶段", status.get("current_stage", "init"))
    metric_cols[2].metric(
        "章节进度",
        f"{status.get('chapters_completed', 0)} / {status.get('chapters_total', 0)}",
    )
    metric_cols[3].metric("预计剩余", format_eta(status.get("eta_seconds")))

    total = int(status.get("chapters_total") or 0)
    completed = int(status.get("chapters_completed") or 0)
    progress = (completed / total) if total > 0 else 0.0
    st_mod.progress(min(max(progress, 0.0), 1.0), text=status.get("current_step", "等待启动"))

    if status.get("failed_stage") or status.get("error_message"):
        st_mod.error(
            f"失败阶段: {status.get('failed_stage') or 'unknown'}\n\n"
            f"{status.get('error_message') or '无错误详情'}"
        )
    elif status.get("status") == "paused":
        pause_reason = _pause_reason_label(status.get("pause_reason") or "") or status.get("current_stage")
        st_mod.warning(f"任务已暂停: {pause_reason}")
    elif status.get("status") == "succeeded":
        st_mod.success("本次生成任务已完成。")

    queued_guidance = _queued_guidance_summary(status)
    if queued_guidance:
        st_mod.info(f"下一卷排队指令:\n{queued_guidance}")

    control_sections = _longform_control_panel_sections(status)
    if control_sections:
        st_mod.markdown("**Longform Control Panel**")
        cols = st_mod.columns(len(control_sections))
        for column, (label, body) in zip(cols, control_sections):
            with column:
                st_mod.markdown(f"**{label}**")
                st_mod.code(body, language="text")

    if payload.get("run_dir"):
        st_mod.caption(f"运行目录: `{payload['run_dir']}`")


def _render_run_monitor(st_mod: Any) -> None:
    st_mod.markdown("#### 任务运行状态")
    if st_mod.button("刷新运行状态", use_container_width=True, key="yw_refresh_run_state"):
        st_mod.rerun()

    @st_mod.fragment(run_every=2)
    def _auto_refresh_panel() -> None:
        payload = _run_monitor_payload(_resolve_active_run_dir())
        _render_run_status_summary(st_mod, payload)
        st_mod.text_area("stdout.log", value=payload["stdout"], height=220)
        st_mod.text_area("stderr.log", value=payload["stderr"], height=140)

    _auto_refresh_panel()


def _render_pending_review(st_mod: Any) -> None:
    run_dir = _resolve_active_run_dir()
    payload = _pending_review_payload(run_dir)
    if not run_dir or not payload:
        return

    checkpoint_type = payload.get("checkpoint_type")
    review_payload = payload.get("review_payload", {})
    st_mod.markdown("#### 待审批节点")
    st_mod.caption(f"`{checkpoint_type}`")

    if checkpoint_type == "outline_review":
        with st_mod.form("yw_outline_review_form", border=True):
            outline = st_mod.text_area("大纲", value=review_payload.get("outline", ""), height=140)
            world_setting = st_mod.text_area("世界观", value=review_payload.get("world_setting", ""), height=120)
            character_intro = st_mod.text_area("人物设定", value=review_payload.get("character_intro", ""), height=120)
            approve = st_mod.form_submit_button("批准并继续", use_container_width=True, type="primary")
            revise = st_mod.form_submit_button("保存修改后继续", use_container_width=True)
            if approve or revise:
                action = "revise" if revise else "approve"
                result = resume_longform_action(
                    run_dir,
                    payload["pending_state_path"],
                    action,
                    {
                        "outline": outline,
                        "world_setting": world_setting,
                        "character_intro": character_intro,
                    },
                )
                st_mod.session_state["yw_generation_log"] = result["message"]
                st_mod.rerun()
        return

    if checkpoint_type == "volume_review":
        volume_index = review_payload.get("volume_index", payload.get("current_volume", 0))
        st_mod.markdown(f"第 `{volume_index}` 卷已完成。")
        st_mod.info(_volume_review_summary(payload))
        guidance_draft = _volume_guidance_draft(review_payload)
        registry_defaults = _volume_registry_defaults(review_payload)
        must_recover = st_mod.text_area(
            "必须回收的伏笔/问题",
            value=guidance_draft["must_recover"],
            height=90,
            key="yw_volume_must_recover",
        )
        relationship_focus = st_mod.text_area(
            "需要强化的人物关系",
            value=guidance_draft["relationship_focus"],
            height=90,
            key="yw_volume_relationship_focus",
        )
        must_avoid = st_mod.text_area(
            "明确避免的方向",
            value=guidance_draft["must_avoid"],
            height=90,
            key="yw_volume_must_avoid",
        )
        tone_target = st_mod.text_input("目标基调", value=guidance_draft["tone_target"], key="yw_volume_tone_target")
        extra_notes = st_mod.text_area(
            "补充说明",
            value=guidance_draft["extra_notes"],
            height=90,
            key="yw_volume_extra_notes",
            help="这些结构化指令会被整理后传入下一卷生成提示词。",
        )
        unresolved_goals = st_mod.text_area(
            "跨卷未完成目标",
            value=registry_defaults["unresolved_goals"],
            height=90,
            key="yw_volume_unresolved_goals",
            help="每行一条。留空并提交会显式清空该 bucket。",
        )
        open_promises = st_mod.text_area(
            "尚未回收承诺/伏笔",
            value=registry_defaults["open_promises"],
            height=90,
            key="yw_volume_open_promises",
            help="每行一条。留空并提交会显式清空该 bucket。",
        )
        dangling_settings = st_mod.text_area(
            "已引入但未桥接设定",
            value=registry_defaults["dangling_settings"],
            height=90,
            key="yw_volume_dangling_settings",
            help="每行一条。留空并提交会显式清空该 bucket。",
        )
        guidance_payload = {
            "must_recover": must_recover,
            "relationship_focus": relationship_focus,
            "must_avoid": must_avoid,
            "tone_target": tone_target,
            "extra_notes": extra_notes,
            "unresolved_goals": [line.strip() for line in unresolved_goals.splitlines() if line.strip()],
            "open_promises": [line.strip() for line in open_promises.splitlines() if line.strip()],
            "dangling_settings": [line.strip() for line in dangling_settings.splitlines() if line.strip()],
        }
        preview_lines = [
            f"- 必须回收的伏笔/问题: {must_recover}",
            f"- 需要强化的人物关系: {relationship_focus}",
            f"- 明确避免的方向: {must_avoid}",
            f"- 目标基调: {tone_target}",
            f"- 补充说明: {extra_notes}",
            f"- 跨卷未完成目标: {'；'.join(guidance_payload['unresolved_goals'])}",
            f"- 尚未回收承诺/伏笔: {'；'.join(guidance_payload['open_promises'])}",
            f"- 已引入但未桥接设定: {'；'.join(guidance_payload['dangling_settings'])}",
        ]
        if any(value.strip() if isinstance(value, str) else bool(value) for value in guidance_payload.values()):
            st_mod.caption("下一卷指令预览")
            st_mod.code(
                "\n".join(
                    line
                    for line, value in zip(preview_lines, guidance_payload.values())
                    if (value.strip() if isinstance(value, str) else bool(value))
                ),
                language="text",
            )
        cols = st_mod.columns(2)
        if cols[0].button("批准并进入下一卷", use_container_width=True, type="primary", key="yw_volume_approve"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "approve",
                guidance_payload,
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        if cols[1].button("带备注继续", use_container_width=True, key="yw_volume_revise"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "revise",
                guidance_payload,
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        return

    if checkpoint_type == "risk_review":
        st_mod.error(_risk_review_summary(payload))
        notes = st_mod.text_area("风险复核备注", value="", height=120, key="yw_risk_review_notes")
        cols = st_mod.columns(3)
        if cols[0].button("确认继续", use_container_width=True, type="primary", key="yw_risk_approve"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "approve",
                {"notes": notes},
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        if cols[1].button("记录备注后继续", use_container_width=True, key="yw_risk_revise"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "revise",
                {"notes": notes},
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        if cols[2].button("保持暂停", use_container_width=True, key="yw_risk_reject"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "reject",
                {"notes": notes},
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        return

    if checkpoint_type == "chapter_review":
        chapter_number = review_payload.get("chapter_number", 0)
        title = review_payload.get("title", "")
        st_mod.error(review_payload.get("summary", "章节未通过质量闸门。"))
        st_mod.markdown(f"第 `{chapter_number}` 章《{title}》未通过自动质量门。")
        blocking_issues = review_payload.get("blocking_issues", [])
        if blocking_issues:
            st_mod.code("\n".join(f"- {item}" for item in blocking_issues), language="text")
        structured_sections = _chapter_review_structured_sections(review_payload)
        if structured_sections:
            cols = st_mod.columns(len(structured_sections))
            for column, (label, body) in zip(cols, structured_sections):
                with column:
                    st_mod.markdown(f"**{label}**")
                    st_mod.code(body, language="text")
        for label, body in _chapter_review_evidence(review_payload):
            with st_mod.expander(label, expanded=label in {"结构化重写方案", "目标锁证据"}):
                st_mod.code(body, language="text")
        guidance = st_mod.text_area(
            "追加重写指令",
            value="",
            height=120,
            key="yw_chapter_review_notes",
            help="这些备注会附加到后续重试提示词中，用于重新生成当前章节。",
        )
        resume_payload = _chapter_review_resume_payload(review_payload, guidance)
        cols = st_mod.columns(3)
        if cols[0].button("按当前规则重试", use_container_width=True, type="primary", key="yw_chapter_approve"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "approve",
                resume_payload,
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        if cols[1].button("带备注重试", use_container_width=True, key="yw_chapter_revise"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "revise",
                resume_payload,
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        if cols[2].button("保持暂停", use_container_width=True, key="yw_chapter_reject"):
            result = resume_longform_action(
                run_dir,
                payload["pending_state_path"],
                "reject",
                resume_payload,
            )
            st_mod.session_state["yw_generation_log"] = result["message"]
            st_mod.rerun()
        return


def _render_chapters_tab(st_mod: Any) -> None:
    st_mod.markdown("### 章节列表与预览")
    choices = _chapter_choices()
    if not choices:
        st_mod.info("当前没有章节。")
        return

    chapter_labels = [label for label, _ in choices]
    label_to_number = {label: int(number) for label, number in choices}
    current_number = st_mod.session_state.get("yw_selected_chapter")
    current_label = next((label for label, number in choices if int(number) == current_number), chapter_labels[0])
    selected_label = st_mod.selectbox("选择章节", options=chapter_labels, index=chapter_labels.index(current_label), key="yw_chapter_selector")
    selected_number = label_to_number[selected_label]
    st_mod.session_state["yw_selected_chapter"] = selected_number

    detail, plot_text, report_text, body_text = _chapter_detail(selected_number)
    left, right = st_mod.columns([1.4, 1])
    with left:
        st_mod.markdown(detail)
    with right:
        st_mod.text_area("章节概要 JSON", value=plot_text, height=180)
        st_mod.text_area("一致性报告 JSON", value=report_text, height=180)
    st_mod.text_area("正文", value=body_text, height=320)
    st_mod.dataframe(_chapter_rows(), use_container_width=True, hide_index=True)


def _render_export_tab(st_mod: Any) -> None:
    st_mod.markdown("### 导出与衍生内容")
    config_mgr = get_config_manager()
    if not config_mgr.current_project:
        st_mod.info("先创建或加载项目。")
        return

    cols = st_mod.columns(3)
    with cols[0]:
        start = st_mod.number_input("导出起始章", min_value=1, max_value=2000, value=1, step=1, key="yw_export_start")
    with cols[1]:
        end = st_mod.number_input("导出结束章", min_value=1, max_value=2000, value=max(config_mgr.current_project.current_chapter, 1), step=1, key="yw_export_end")
    with cols[2]:
        if st_mod.button("导出文本", use_container_width=True):
            st_mod.session_state["yw_export_message"] = export_text_action(int(start), int(end))
            st_mod.rerun()

    st_mod.markdown(st_mod.session_state.get("yw_export_message", ""))
    derivative_text, derivative_rows = _derivative_summary()
    st_mod.markdown(derivative_text)
    st_mod.dataframe(derivative_rows, use_container_width=True, hide_index=True)


def build_app() -> None:
    """Render the Streamlit application."""
    st_mod = _require_streamlit()
    st_mod.set_page_config(page_title="小说生成工作台", page_icon="✍", layout="wide")
    st_mod.markdown(PAGE_CSS, unsafe_allow_html=True)

    st_mod.markdown('<div class="yw-title">小说生成工作台</div>', unsafe_allow_html=True)
    st_mod.markdown(
        '<div class="yw-subtitle">项目创建 · 写作参数 · 章节生成 · 章节预览 · 导出文本</div>',
        unsafe_allow_html=True,
    )

    _render_project_sidebar(st_mod)

    tabs = st_mod.tabs(["生成控制台", "写作参数", "模型配置", "章节阅读", "导出与衍生"])
    with tabs[0]:
        _render_generation_tab(st_mod)
    with tabs[1]:
        _render_writing_tab(st_mod)
    with tabs[2]:
        _render_provider_tab(st_mod)
    with tabs[3]:
        _render_chapters_tab(st_mod)
    with tabs[4]:
        _render_export_tab(st_mod)


def main() -> None:
    """CLI entrypoint for `python streamlit_app.py`."""
    build_app()


if __name__ == "__main__":  # pragma: no cover - manual launch path
    main()
