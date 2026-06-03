"""Tests for workspace path resolution."""


from young_writer.services.paths import WorkspacePaths, safe_project_slug


def test_project_paths_default_to_unified_runtime_root(temp_project_dir):
    paths = WorkspacePaths.from_root(temp_project_dir)

    project_paths = paths.project_paths(title="太古 魔帝传", project_id="abc123")

    assert project_paths.layout == "runtime"
    assert project_paths.project_dir == (
        temp_project_dir / "runtime" / "projects" / "太古-魔帝传_abc123"
    ).resolve()
    assert project_paths.scripts_dir == project_paths.project_dir / "derivatives"
    assert project_paths.film_drama_dir == project_paths.project_dir / "film_drama"


def test_project_paths_prefer_existing_legacy_project(temp_project_dir):
    paths = WorkspacePaths.from_root(temp_project_dir)
    legacy_dir = temp_project_dir / "novels" / "旧项目_legacy001"
    legacy_dir.mkdir(parents=True)

    project_paths = paths.project_paths(title="旧项目", project_id="legacy001")

    assert project_paths.layout == "legacy"
    assert project_paths.project_dir == legacy_dir.resolve()
    assert project_paths.scripts_dir == (
        temp_project_dir / "generated_scripts" / "旧项目_legacy001"
    ).resolve()


def test_project_paths_reuse_existing_legacy_derivative_dirs(temp_project_dir):
    paths = WorkspacePaths.from_root(temp_project_dir)
    legacy_novel_dir = temp_project_dir / "novels" / "旧项目"
    legacy_scripts_dir = temp_project_dir / "generated_scripts" / "legacy001"
    legacy_film_drama_dir = temp_project_dir / "film_drama_scripts" / "旧项目"
    legacy_novel_dir.mkdir(parents=True)
    legacy_scripts_dir.mkdir(parents=True)
    legacy_film_drama_dir.mkdir(parents=True)

    project_paths = paths.project_paths(title="旧项目", project_id="legacy001")

    assert project_paths.layout == "legacy"
    assert project_paths.project_dir == legacy_novel_dir.resolve()
    assert project_paths.scripts_dir == legacy_scripts_dir.resolve()
    assert project_paths.film_drama_dir == legacy_film_drama_dir.resolve()


def test_runtime_dir_can_be_overridden(monkeypatch, temp_project_dir):
    runtime_dir = temp_project_dir / "custom-data"
    monkeypatch.setenv("YOUNG_WRITER_DATA_DIR", str(runtime_dir))

    paths = WorkspacePaths.from_root(temp_project_dir)

    assert paths.runtime_dir == runtime_dir.resolve()
    assert paths.projects_dir == runtime_dir.resolve() / "projects"


def test_safe_project_slug_preserves_cjk_and_replaces_separators():
    assert safe_project_slug(" 太古/魔帝 传 ") == "太古-魔帝-传"
