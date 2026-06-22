"""Packaging smoke tests for the migrated young_writer distribution."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest


@pytest.mark.slow
def test_built_wheel_exposes_primary_and_compatibility_imports(tmp_path: Path) -> None:
    package_root = Path(__file__).resolve().parents[1]
    dist_dir = tmp_path / "dist"
    venv_dir = tmp_path / "venv"

    build = subprocess.run(
        ["uv", "build", "--out-dir", str(dist_dir)],
        cwd=package_root,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        output = f"{build.stdout}\n{build.stderr}"
        if "Operation not permitted" in output or "Failed to fetch" in output:
            pytest.skip(f"uv build unavailable in this environment: {output}")
        build.check_returncode()

    wheel_path = next(dist_dir.glob("young_writer-*.whl"))
    with ZipFile(wheel_path) as wheel:
        names = wheel.namelist()
    assert not any(name.startswith("young_writer/config/") for name in names)
    assert not any(name.startswith("young_writer/runtime/") for name in names)

    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    python_bin = venv_dir / ("Scripts" if sys.platform == "win32" else "bin") / "python"
    subprocess.run(
        [str(python_bin), "-m", "pip", "install", str(wheel_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    smoke = subprocess.run(
        [
            str(python_bin),
            "-c",
            (
                "from young_writer.agents.config_manager import ConfigManager;"
                "import young_writer.agents.config_manager as canonical_agents_config;"
                "from young_writer.services.paths import WorkspacePaths;"
                "from knowledge_base.agents.config_manager import ConfigManager as LegacyConfigManager;"
                "import knowledge_base.services.paths as legacy_services_paths;"
                "from knowledge_base.services.paths import WorkspacePaths as LegacyWorkspacePaths;"
                "from agents.config_manager import ConfigManager as ShimConfigManager;"
                "import agents.config_manager as shim_agents_config;"
                "assert ConfigManager.__name__ == 'ConfigManager';"
                "assert canonical_agents_config is shim_agents_config;"
                "assert WorkspacePaths.__name__ == 'WorkspacePaths';"
                "assert LegacyConfigManager.__name__ == 'ConfigManager';"
                "assert LegacyWorkspacePaths.__name__ == 'WorkspacePaths';"
                "assert legacy_services_paths is __import__('young_writer.services.paths', fromlist=['paths']);"
                "assert ShimConfigManager.__name__ == 'ConfigManager';"
                "import importlib.util;"
                "assert importlib.util.find_spec('cr' + 'ewai') is None;"
                "print('wheel-import-smoke-ok')"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wheel-import-smoke-ok" in smoke.stdout
