"""Tests for the migrated young_writer package and compatibility shims."""


def test_young_writer_package_imports_primary_modules():
    from young_writer.agents.config_manager import ConfigManager
    from young_writer.services.paths import WorkspacePaths

    assert ConfigManager.__name__ == "ConfigManager"
    assert WorkspacePaths.__name__ == "WorkspacePaths"


def test_compatibility_packages_still_resolve():
    import agents.config_manager as legacy_agents_config
    import knowledge_base.services.paths as legacy_services_paths
    import young_writer.agents.config_manager as canonical_agents_config
    import young_writer.services.paths as canonical_services_paths
    from agents.config_manager import ConfigManager as LegacyConfigManager

    from knowledge_base.services.paths import WorkspacePaths as LegacyWorkspacePaths

    assert legacy_agents_config is canonical_agents_config
    assert legacy_services_paths is canonical_services_paths
    assert LegacyConfigManager.__name__ == "ConfigManager"
    assert LegacyWorkspacePaths.__name__ == "WorkspacePaths"
