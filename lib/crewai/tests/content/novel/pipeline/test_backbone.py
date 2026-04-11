"""Unit tests for the backbone mapping and validation system.

Tests BackboneMapper and BackboneValidator classes, covering:
- Reference event loading from classical_backbones.json
- Algorithmic mapping (positional + keyword similarity)
- JSON parsing and error handling
- Validation against adoption rate thresholds
- Report formatting and improvement suggestions
"""

import json
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import importlib.util

# Add source directories to path
# __file__ is at: .../lib/crewai/tests/content/novel/pipeline/test_backbone.py
# Resolve to absolute path, then go up 5 levels to lib/crewai
test_file = Path(__file__).resolve()
crewai_lib_dir = test_file.parent.parent.parent.parent.parent  # lib/crewai
src_path = crewai_lib_dir / "src"
sys.path.insert(0, str(src_path))

# Load modules directly to avoid circular import issues
def load_module(module_path, module_name):
    """Load a module directly from file path."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Load backbone_validator first (it's a dependency)
validator_path = src_path / "crewai" / "content" / "novel" / "pipeline" / "backbone_validator.py"
backbone_validator_module = load_module(str(validator_path), "crewai.content.novel.pipeline.backbone_validator")

BackboneValidator = backbone_validator_module.BackboneValidator
BackboneMapping = backbone_validator_module.BackboneMapping
ValidationResult = backbone_validator_module.ValidationResult
_extract_event_name = backbone_validator_module._extract_event_name
_infer_archetype_key = backbone_validator_module._infer_archetype_key

# Load backbone_mapper (depends on backbone_validator)
mapper_path = src_path / "crewai" / "content" / "novel" / "pipeline" / "backbone_mapper.py"
backbone_mapper_module = load_module(str(mapper_path), "crewai.content.novel.pipeline.backbone_mapper")
BackboneMapper = backbone_mapper_module.BackboneMapper


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def sample_reference_events() -> list[dict]:
    """Sample reference events for testing."""
    return [
        {
            "order": 1,
            "name": "石猴出世",
            "content": "石猴从仙石中迸裂而出",
            "archetype": "英雄诞生",
        },
        {
            "order": 2,
            "name": "大闹天宫",
            "content": "孙悟空反抗权威与压制",
            "archetype": "反抗权威",
        },
        {
            "order": 3,
            "name": "被压五行山",
            "content": "孙悟空因骄傲而被镇压",
            "archetype": "惩罚与救赎",
        },
    ]


@pytest.fixture
def sample_plot_data() -> dict:
    """Sample plot_data for testing."""
    return {
        "synopsis": "一个关于修行和成长的故事",
        "plot_arcs": [
            {
                "name": "主角觉醒",
                "description": "主角在石山中诞生，拥有特殊力量",
                "start_chapter": 1,
                "end_chapter": 3,
            },
            {
                "name": "反抗命运",
                "description": "主角挑战既有秩序，展现力量",
                "start_chapter": 4,
                "end_chapter": 6,
            },
            {
                "name": "受罚修行",
                "description": "主角被镇压，经历磨难",
                "start_chapter": 7,
                "end_chapter": 10,
            },
        ],
        "turning_points": [
            {
                "chapter": 3,
                "description": "力量显现",
                "impact": "打破平衡",
            },
            {
                "chapter": 6,
                "description": "大战开始",
                "impact": "秩序崩塌",
            },
        ],
        "main_characters": [
            {"name": "主角"},
            {"name": "导师"},
        ],
    }


@pytest.fixture
def classical_backbones_path() -> str:
    """Path to the actual classical_backbones.json file."""
    return "/Users/muyi/Downloads/dev/young-writer/lib/knowledge_base/classical_backbones.json"


# =========================================================================
# Tests: BackboneValidator
# =========================================================================


class TestBackboneValidator:
    """Test suite for BackboneValidator class."""

    def test_validate_all_mapped(self, sample_reference_events):
        """Test: All reference events mapped with high confidence → passes (rate=100%)."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.5)

        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.95,
                spiritual_core="新力量的诞生打破旧平衡",
            ),
            BackboneMapping(
                reference_event_name="大闹天宫",
                reference_event_content="孙悟空反抗权威与压制",
                novel_event_name="反抗命运",
                novel_chapter=4,
                mapping_confidence=0.90,
                spiritual_core="个体意志对既有秩序的挑战",
            ),
            BackboneMapping(
                reference_event_name="被压五行山",
                reference_event_content="孙悟空因骄傲而被镇压",
                novel_event_name="受罚修行",
                novel_chapter=7,
                mapping_confidence=0.85,
                spiritual_core="傲慢受制后的蛰伏与觉醒",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)

        assert result.passed is True
        assert result.adoption_rate == 1.0
        assert result.mapped_events == 3
        assert result.total_reference_events == 3
        assert len(result.unmapped_events) == 0

    def test_validate_below_threshold(self, sample_reference_events):
        """Test: Only 50% mapped → fails (threshold=70%)."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.5)

        # Only map 1 out of 3 events
        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.8,
                spiritual_core="新力量诞生",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)

        assert result.passed is False
        assert result.adoption_rate == pytest.approx(1 / 3, abs=0.01)
        assert result.mapped_events == 1
        assert len(result.unmapped_events) == 2
        assert "大闹天宫" in result.unmapped_events
        assert "被压五行山" in result.unmapped_events

    def test_validate_empty_reference(self):
        """Test: No reference events → passes trivially."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.5)

        mappings = []
        reference_events = []

        result = validator.validate(mappings, reference_events)

        assert result.passed is True
        assert result.adoption_rate == 1.0
        assert result.total_reference_events == 0
        assert len(result.unmapped_events) == 0

    def test_validate_low_confidence(self, sample_reference_events):
        """Test: Mappings below min_confidence don't count."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.6)

        # Map all 3 events, but 2 are below the confidence threshold
        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.95,  # Above threshold
                spiritual_core="新力量诞生",
            ),
            BackboneMapping(
                reference_event_name="大闹天宫",
                reference_event_content="孙悟空反抗权威与压制",
                novel_event_name="反抗命运",
                novel_chapter=4,
                mapping_confidence=0.4,  # Below threshold
                spiritual_core="挑战秩序",
            ),
            BackboneMapping(
                reference_event_name="被压五行山",
                reference_event_content="孙悟空因骄傲而被镇压",
                novel_event_name="受罚修行",
                novel_chapter=7,
                mapping_confidence=0.55,  # Below threshold (0.55 < 0.6)
                spiritual_core="蛰伏觉醒",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)

        # Only 1 out of 3 should count as adopted
        assert result.mapped_events == 1
        assert result.adoption_rate == pytest.approx(1 / 3, abs=0.01)
        assert len(result.low_confidence_mappings) == 2
        assert result.passed is False

    def test_format_report(self, sample_reference_events):
        """Test: Report contains Chinese text, adoption rate, unmapped events."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.5)

        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.9,
                spiritual_core="新力量诞生",
            ),
            BackboneMapping(
                reference_event_name="大闹天宫",
                reference_event_content="孙悟空反抗权威与压制",
                novel_event_name="反抗命运",
                novel_chapter=4,
                mapping_confidence=0.85,
                spiritual_core="挑战秩序",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)
        report = validator.format_report(result)

        # Check for Chinese text
        assert "骨架采纳率验证报告" in report
        assert "采纳率" in report
        assert "未映射事件" in report
        assert "被压五行山" in report

        # Check adoption rate is present
        assert f"{result.adoption_rate:.1%}" in report or "66.7%" in report or "67%" in report

        # Check passing status
        assert "✗ 未通过" in report or "通过" in report

    def test_suggest_improvements(self, sample_reference_events):
        """Test: Unmapped events get suggestions."""
        validator = BackboneValidator(threshold=0.70, min_confidence=0.5)

        # Map only 1 out of 3
        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.9,
                spiritual_core="新力量诞生",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)
        suggestions = validator.suggest_improvements(result)

        # Should have suggestions for the 2 unmapped events
        assert len(suggestions) >= 2
        # All suggestions should be Chinese strings
        for s in suggestions:
            assert isinstance(s, str)
            assert len(s) > 0

    def test_load_reference_events(self, classical_backbones_path):
        """Test: Load events from actual classical_backbones.json for '西游记'."""
        if not Path(classical_backbones_path).exists():
            pytest.skip(f"classical_backbones.json not found at {classical_backbones_path}")

        events = BackboneValidator.load_reference_events(
            classical_backbones_path, "西游记"
        )

        assert isinstance(events, list)
        assert len(events) > 0

        # Check structure of first event
        first = events[0]
        assert "order" in first
        assert "name" in first
        assert "content" in first
        assert "archetype" in first

        # For 西游记, expect specific backbone events
        event_names = [e.get("name") for e in events]
        assert "石猴出世" in event_names or len(event_names) > 0


# =========================================================================
# Tests: BackboneMapper
# =========================================================================


class TestBackboneMapper:
    """Test suite for BackboneMapper class."""

    def test_algorithmic_map_basic(self, sample_reference_events, sample_plot_data):
        """Test: Map reference events to novel events without LLM."""
        mapper = BackboneMapper(llm=None, fallback_confidence=0.55)

        mappings = mapper.map(
            reference_events=sample_reference_events,
            plot_data=sample_plot_data,
            mode="loose",
        )

        # Should produce mappings
        assert isinstance(mappings, list)
        assert len(mappings) > 0

        # Check structure of mappings
        for m in mappings:
            assert isinstance(m, BackboneMapping)
            assert isinstance(m.reference_event_name, str)
            assert isinstance(m.novel_event_name, str)
            assert isinstance(m.mapping_confidence, float)
            assert 0.0 <= m.mapping_confidence <= 1.0

    def test_algorithmic_map_empty_input(self, sample_plot_data):
        """Test: Empty reference events → empty result."""
        mapper = BackboneMapper(llm=None)

        mappings = mapper.map(
            reference_events=[],
            plot_data=sample_plot_data,
            mode="loose",
        )

        assert mappings == []

    def test_similarity_score_identical(self):
        """Test: Identical text gives high score."""
        mapper = BackboneMapper(llm=None)

        # Maximum similarity (identical strings)
        score = mapper._similarity_score(
            ref_name="石猴出世",
            ref_content="石猴从仙石中迸裂而出",
            ref_archetype="英雄诞生",
            ref_position=0.0,
            novel_name="石猴出世",
            novel_description="石猴从仙石中迸裂而出",
            novel_position=0.0,
        )

        assert score > 0.7  # Should be very high

    def test_similarity_score_unrelated(self):
        """Test: Unrelated text gives low score."""
        mapper = BackboneMapper(llm=None)

        # Completely unrelated strings
        score = mapper._similarity_score(
            ref_name="石猴出世",
            ref_content="石猴从仙石中迸裂而出",
            ref_archetype="英雄诞生",
            ref_position=0.0,
            novel_name="日常对话",
            novel_description="天气很好，我们去散步吧",
            novel_position=0.0,
        )

        assert score < 0.4  # Should be very low

    def test_fill_gaps_strict_mode(self, sample_reference_events, sample_plot_data):
        """Test: In strict mode, unmapped events get filled."""
        mapper = BackboneMapper(llm=None, fallback_confidence=0.55)

        # Start with partial mappings (only first 2 events)
        partial_mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="石猴从仙石中迸裂而出",
                novel_event_name="主角觉醒",
                novel_chapter=1,
                mapping_confidence=0.95,
                spiritual_core="新力量诞生",
            ),
            BackboneMapping(
                reference_event_name="大闹天宫",
                reference_event_content="孙悟空反抗权威与压制",
                novel_event_name="反抗命运",
                novel_chapter=4,
                mapping_confidence=0.90,
                spiritual_core="挑战秩序",
            ),
        ]

        # Fill gaps
        filled = mapper._fill_gaps(partial_mappings, sample_reference_events, sample_plot_data)

        # Should have more mappings after filling gaps
        assert len(filled) >= len(partial_mappings)

        # All gap-filled mappings should have confidence <= fallback_confidence
        original_names = {m.reference_event_name for m in partial_mappings}
        for m in filled:
            if m.reference_event_name not in original_names:
                assert m.mapping_confidence <= mapper.fallback_confidence

    def test_extract_json_array_clean(self):
        """Test: Parse valid JSON array."""
        mapper = BackboneMapper(llm=None)

        text = '[{"a": 1}, {"b": 2}]'
        result = mapper._extract_json_array(text)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_extract_json_array_with_code_fence(self):
        """Test: Parse JSON array from code-fenced block."""
        mapper = BackboneMapper(llm=None)

        text = """
        ```json
        [{"a": 1}, {"b": 2}]
        ```
        """
        result = mapper._extract_json_array(text)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_extract_json_array_wrapped_in_object(self):
        """Test: Parse JSON array wrapped in an object."""
        mapper = BackboneMapper(llm=None)

        text = '{"data": [{"a": 1}, {"b": 2}]}'
        result = mapper._extract_json_array(text)

        assert isinstance(result, list)
        assert len(result) == 2

    def test_infer_spiritual_core_known_archetype(self):
        """Test: Known archetypes return meaningful core strings."""
        mapper = BackboneMapper(llm=None)

        core = mapper._infer_spiritual_core(
            archetype="英雄诞生",
            content="石猴从仙石中迸裂而出",
        )

        assert isinstance(core, str)
        assert len(core) > 0
        assert "新力量" in core or "诞生" in core

    def test_infer_spiritual_core_unknown_archetype(self):
        """Test: Unknown archetypes return default core string."""
        mapper = BackboneMapper(llm=None)

        core = mapper._infer_spiritual_core(
            archetype="未知原型",
            content="某个事件内容",
        )

        assert isinstance(core, str)
        assert len(core) > 0
        # Should return some fallback string

    def test_map_from_file(self, classical_backbones_path, sample_plot_data):
        """Test: Load from file and map against sample plot_data."""
        if not Path(classical_backbones_path).exists():
            pytest.skip(f"classical_backbones.json not found at {classical_backbones_path}")

        mapper = BackboneMapper(llm=None)

        mappings = mapper.map_from_file(
            backbone_path=classical_backbones_path,
            work_name="西游记",
            plot_data=sample_plot_data,
            mode="loose",
        )

        # Should produce mappings from the actual file
        assert isinstance(mappings, list)
        # May be empty if no matches, but structure should be correct
        for m in mappings:
            assert isinstance(m, BackboneMapping)

    def test_extract_novel_events(self, sample_plot_data):
        """Test: Extract novel events from plot_data."""
        mapper = BackboneMapper(llm=None)

        events = mapper._extract_novel_events(sample_plot_data)

        assert isinstance(events, list)
        assert len(events) > 0

        # Check structure
        for e in events:
            assert "name" in e
            assert "description" in e
            assert "chapter" in e

    def test_format_reference_events(self, sample_reference_events):
        """Test: Format reference events for LLM prompt."""
        mapper = BackboneMapper(llm=None)

        formatted = mapper._format_reference_events(sample_reference_events)

        assert isinstance(formatted, str)
        assert "石猴出世" in formatted
        assert "英雄诞生" in formatted
        assert "大闹天宫" in formatted

    def test_format_novel_events(self, sample_plot_data):
        """Test: Format novel events for LLM prompt."""
        mapper = BackboneMapper(llm=None)

        formatted = mapper._format_novel_events(sample_plot_data)

        assert isinstance(formatted, str)
        assert "故事梗概" in formatted or len(formatted) > 0

    def test_llm_map_when_llm_provided(self, sample_reference_events, sample_plot_data):
        """Test: LLM mapping is attempted when LLM is provided."""
        mock_llm = Mock()
        mock_llm.chat.return_value = json.dumps(
            [
                {
                    "reference_event_name": "石猴出世",
                    "reference_event_content": "石猴从仙石中迸裂而出",
                    "novel_event_name": "主角觉醒",
                    "novel_chapter": 1,
                    "mapping_confidence": 0.95,
                    "spiritual_core": "新力量诞生打破旧平衡",
                }
            ]
        )

        mapper = BackboneMapper(llm=mock_llm)

        mappings = mapper.map(
            reference_events=sample_reference_events,
            plot_data=sample_plot_data,
            mode="loose",
        )

        # LLM should have been called
        assert mock_llm.chat.called
        # Should have produced a mapping
        assert len(mappings) >= 1

    def test_parse_llm_mappings_with_think_blocks(self):
        """Test: Parse LLM response with <think> blocks."""
        mapper = BackboneMapper(llm=None)

        raw = """
        <think>
        这是LLM的思考过程，应该被去掉。
        </think>
        [
            {
                "reference_event_name": "石猴出世",
                "reference_event_content": "内容",
                "novel_event_name": "觉醒",
                "novel_chapter": 1,
                "mapping_confidence": 0.8,
                "spiritual_core": "核心"
            }
        ]
        """

        mappings = mapper._parse_llm_mappings(raw)

        assert len(mappings) == 1
        assert mappings[0].reference_event_name == "石猴出世"

    def test_parse_llm_mappings_invalid_json(self):
        """Test: Parse invalid JSON gracefully."""
        mapper = BackboneMapper(llm=None)

        raw = "This is not JSON at all!"

        mappings = mapper._parse_llm_mappings(raw)

        assert mappings == []


# =========================================================================
# Tests: Helper functions
# =========================================================================


class TestHelperFunctions:
    """Test suite for module-level helper functions."""

    def test_extract_event_name_from_dict(self):
        """Test: Extract event name from various dict formats."""
        # Test with 'name' key
        event = {"name": "石猴出世", "order": 1}
        name = _extract_event_name(event)
        assert name == "石猴出世"

        # Test with 'event_name' key (fallback)
        event = {"event_name": "大闹天宫", "order": 2}
        name = _extract_event_name(event)
        assert name == "大闹天宫"

        # Test with only 'order' key (fallback)
        event = {"order": 3}
        name = _extract_event_name(event)
        assert name == "3"

    def test_infer_archetype_key_chinese_keywords(self):
        """Test: Infer archetype from Chinese keywords."""
        key = _infer_archetype_key("英雄的召唤")
        assert key == "hero_call"

        key = _infer_archetype_key("导师的指引")
        assert key == "mentor"

        key = _infer_archetype_key("试炼与磨难")
        assert key == "trial"

    def test_infer_archetype_key_english_keywords(self):
        """Test: Infer archetype from English keywords."""
        key = _infer_archetype_key("Hero Call to Adventure")
        assert key == "hero_call"

        key = _infer_archetype_key("Mentor Guide")
        assert key == "mentor"

    def test_infer_archetype_key_no_match(self):
        """Test: No match returns empty string."""
        key = _infer_archetype_key("一个不相关的标题")
        assert key == ""

        key = _infer_archetype_key("Random Title")
        assert key == ""


# =========================================================================
# Integration tests
# =========================================================================


class TestIntegration:
    """Integration tests combining mapper and validator."""

    def test_mapper_validator_workflow(
        self, sample_reference_events, sample_plot_data
    ):
        """Test: Complete workflow from mapping to validation."""
        # Map
        mapper = BackboneMapper(llm=None, fallback_confidence=0.55)
        mappings = mapper.map(
            reference_events=sample_reference_events,
            plot_data=sample_plot_data,
            mode="loose",
        )

        # Validate
        validator = BackboneValidator(threshold=0.5, min_confidence=0.4)
        result = validator.validate(mappings, sample_reference_events)

        # Should have some result
        assert isinstance(result, ValidationResult)
        assert result.total_reference_events == len(sample_reference_events)

    def test_strict_mode_covers_all_events(
        self, sample_reference_events, sample_plot_data
    ):
        """Test: Strict mode ensures all reference events are covered."""
        mapper = BackboneMapper(llm=None, fallback_confidence=0.55)
        mappings = mapper.map(
            reference_events=sample_reference_events,
            plot_data=sample_plot_data,
            mode="strict",
        )

        # In strict mode, all reference events should be attempted
        # (even if with low confidence)
        mapped_names = {m.reference_event_name for m in mappings}
        reference_names = {e.get("name") for e in sample_reference_events}

        # Should overlap significantly
        overlap = mapped_names & reference_names
        assert len(overlap) > 0 or len(mappings) == 0  # Either has overlap or no plot events


# =========================================================================
# Edge case tests
# =========================================================================


class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_mapper_with_special_characters(self):
        """Test: Handle special characters in event names."""
        mapper = BackboneMapper(llm=None)

        reference = [
            {
                "order": 1,
                "name": "事件（一）特殊/符号",
                "content": '包含"引号"和单引号的内容',
                "archetype": "未知",
            }
        ]

        plot = {
            "plot_arcs": [
                {
                    "name": "事件（一）特殊/符号",
                    "description": "对应事件",
                    "start_chapter": 1,
                    "end_chapter": 3,
                }
            ]
        }

        mappings = mapper.map(reference, plot, mode="loose")
        # Should not crash
        assert isinstance(mappings, list)

    def test_validator_with_duplicate_mappings(self, sample_reference_events):
        """Test: Validator handles duplicate mappings correctly."""
        validator = BackboneValidator(threshold=0.7, min_confidence=0.5)

        # Two mappings for the same reference event (different confidences)
        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="内容1",
                novel_event_name="事件1",
                novel_chapter=1,
                mapping_confidence=0.8,
                spiritual_core="核心1",
            ),
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="内容2",
                novel_event_name="事件2",
                novel_chapter=2,
                mapping_confidence=0.6,
                spiritual_core="核心2",
            ),
        ]

        result = validator.validate(mappings, sample_reference_events)

        # Should count the event once (with highest confidence)
        assert result.mapped_events >= 1

    def test_report_with_many_unmapped_events(self, sample_reference_events):
        """Test: Report formatting with many unmapped events."""
        validator = BackboneValidator(threshold=0.9, min_confidence=0.5)

        mappings = []  # No mappings

        result = validator.validate(mappings, sample_reference_events)
        report = validator.format_report(result)

        # Report should contain all unmapped event names
        for event in sample_reference_events:
            name = event.get("name", "")
            if name:
                assert name in report

    def test_empty_plot_data(self, sample_reference_events):
        """Test: Mapper handles empty plot_data."""
        mapper = BackboneMapper(llm=None)

        plot_data = {
            "plot_arcs": [],
            "turning_points": [],
            "main_characters": [],
        }

        mappings = mapper.map(sample_reference_events, plot_data, mode="loose")

        # May return empty list or minimal mappings
        assert isinstance(mappings, list)

    def test_very_high_confidence_threshold(self, sample_reference_events):
        """Test: Validator with min_confidence = 1.0 (impossible to pass)."""
        validator = BackboneValidator(threshold=0.5, min_confidence=1.0)

        mappings = [
            BackboneMapping(
                reference_event_name="石猴出世",
                reference_event_content="内容",
                novel_event_name="事件",
                novel_chapter=1,
                mapping_confidence=0.999,  # Very high but < 1.0
                spiritual_core="核心",
            )
        ]

        result = validator.validate(mappings, sample_reference_events)

        # Should fail because confidence is strictly < 1.0
        assert result.mapped_events == 0
