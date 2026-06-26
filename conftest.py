"""Root pytest configuration for the young-writer workspace."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from dotenv import load_dotenv


load_dotenv(Path(__file__).parent / ".env.test", override=True)
load_dotenv(override=True)


@pytest.fixture(autouse=True, scope="function")
def setup_test_environment() -> Generator[None, None, None]:
    """Provide isolated local runtime storage for tests."""

    with TemporaryDirectory() as temp_dir:
        runtime_dir = Path(temp_dir) / "young_writer_test_runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        os.environ["YOUNG_WRITER_RUNTIME_DIR"] = str(runtime_dir)
        os.environ["YOUNG_WRITER_TESTING"] = "true"
        try:
            yield
        finally:
            os.environ.pop("YOUNG_WRITER_RUNTIME_DIR", None)
            os.environ.pop("YOUNG_WRITER_TESTING", None)
