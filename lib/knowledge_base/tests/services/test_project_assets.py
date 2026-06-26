import json

import pytest

from young_writer.services.project_assets import (
    ProjectAssetValidationError,
    load_project_asset_bundle,
    parse_project_asset_bundle,
)


def test_parse_project_asset_bundle_normalizes_project_fields():
    bundle = parse_project_asset_bundle(
        {
            "schema_version": "project_assets.v1",
            "outline": {
                "premise": "少年在潮汐城邦追查失踪舰队。",
                "major_arcs": ["进入禁航海沟", "揭开家族旧案"],
                "ending_hint": "主角公开潮汐空间真相。",
            },
            "world_setting": {
                "summary": "近未来海上城邦依赖潮汐窗口航行。",
                "rules": ["潮汐窗口每七十二小时开启一次"],
                "locations": ["潮汐港", "禁航海沟"],
            },
            "characters": [
                {
                    "name": "季衡",
                    "role": "声呐译码师",
                    "motivation": "找回姐姐失踪的真相",
                },
                {"name": "苏未", "role": "前搭档"},
            ],
        }
    )

    fields = bundle.to_project_fields()

    assert "少年在潮汐城邦追查失踪舰队" in fields["outline"]
    assert "进入禁航海沟" in fields["outline"]
    assert "潮汐窗口每七十二小时开启一次" in fields["world_setting"]
    assert "季衡: 声呐译码师" in fields["character_intro"]
    assert bundle.to_metadata()["schema_version"] == "project_assets.v1"


def test_parse_project_asset_bundle_requires_character_name():
    with pytest.raises(ProjectAssetValidationError, match="characters"):
        parse_project_asset_bundle(
            {
                "outline": {"premise": "主线"},
                "world_setting": {"summary": "世界"},
                "characters": [{"role": "主角"}],
            }
        )


def test_load_project_asset_bundle_reads_json(tmp_path):
    asset_path = tmp_path / "assets.json"
    asset_path.write_text(
        json.dumps(
            {
                "outline": "一段可导入的大纲。",
                "world_setting": "一段可导入的世界观。",
                "characters": ["林澈: 主角，寻找旧案真相"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_project_asset_bundle(asset_path)

    assert bundle.source_path == str(asset_path)
    assert bundle.outline.premise == "一段可导入的大纲。"
    assert bundle.characters[0].name == "林澈"
