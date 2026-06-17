"""Tests for CLI command builders used by thin UI entrypoints."""

from young_writer.services.cli_commands import (
    build_full_generate_command,
    build_generate_command,
)


def test_build_generate_command_includes_options_and_control_flags():
    cmd = build_generate_command(
        python_executable="python",
        run_script="run_novel_generation.py",
        count=2,
        start=5,
        dry_run=True,
        no_auto_feedback=True,
        sync_derivatives_after_generate=True,
        writing_options={"style": "快节奏", "unknown": "ignored"},
    )

    assert cmd == [
        "python",
        "run_novel_generation.py",
        "--generate",
        "2",
        "--start",
        "5",
        "--dry-run",
        "--no-auto-feedback",
        "--sync-derivatives-after-generate",
        "--style",
        "快节奏",
    ]


def test_build_full_generate_command_preserves_run_tracking_args():
    cmd = build_full_generate_command(
        python_executable="python",
        run_script="run_novel_generation.py",
        chapters_per_volume=60,
        approval_mode="outline+volume",
        run_id="run-001",
        auto_approve=True,
    )

    assert cmd == [
        "python",
        "run_novel_generation.py",
        "--generate-full",
        "--chapters-per-volume",
        "60",
        "--approval-mode",
        "outline+volume",
        "--run-id",
        "run-001",
        "--auto-approve",
    ]
