"""Command builders for local novel-generation entrypoints."""

from __future__ import annotations

from pathlib import Path


WRITING_OPTION_FLAGS = {
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
    "humanization_level": "--humanization-level",
}


def append_writing_option_flags(cmd: list[str], options: dict[str, str]) -> None:
    for key, value in options.items():
        flag = WRITING_OPTION_FLAGS.get(key)
        if flag and value:
            cmd.extend([flag, value])


def build_generate_command(
    *,
    python_executable: str,
    run_script: str | Path,
    count: int,
    start: int = 0,
    dry_run: bool = False,
    no_auto_feedback: bool = False,
    writing_options: dict[str, str] | None = None,
) -> list[str]:
    cmd = [python_executable, str(run_script), "--generate", str(int(count))]
    if int(start) > 0:
        cmd.extend(["--start", str(int(start))])
    if dry_run:
        cmd.append("--dry-run")
    if no_auto_feedback:
        cmd.append("--no-auto-feedback")
    append_writing_option_flags(cmd, writing_options or {})
    return cmd


def build_full_generate_command(
    *,
    python_executable: str,
    run_script: str | Path,
    chapters_per_volume: int,
    approval_mode: str,
    run_id: str,
    auto_approve: bool = False,
) -> list[str]:
    cmd = [
        python_executable,
        str(run_script),
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
    return cmd
