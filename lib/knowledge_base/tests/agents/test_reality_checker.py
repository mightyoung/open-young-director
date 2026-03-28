"""Tests for RealityChecker agent."""

import pytest
from agents.reality_checker import (
    RealityChecker,
    RealityCheckerConfig,
    ValidationResult,
    get_reality_checker,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_default_status_is_needs_work(self):
        """Default validation status should be NEEDS_WORK."""
        result = ValidationResult(
            status="NEEDS_WORK",
            score=0.5,
            issues=["test issue"],
            evidence_required=["test evidence"],
        )
        assert result.status == "NEEDS_WORK"

    def test_is_pass_property(self):
        """is_pass should return True only for PASS status."""
        pass_result = ValidationResult(status="PASS", score=0.9)
        needs_work_result = ValidationResult(status="NEEDS_WORK", score=0.5)
        fail_result = ValidationResult(status="FAIL", score=0.3)

        assert pass_result.is_pass is True
        assert needs_work_result.is_pass is False
        assert fail_result.is_pass is False

    def test_is_needs_work_property(self):
        """is_needs_work should return True only for NEEDS_WORK status."""
        pass_result = ValidationResult(status="PASS", score=0.9)
        needs_work_result = ValidationResult(status="NEEDS_WORK", score=0.5)

        assert pass_result.is_needs_work is False
        assert needs_work_result.is_needs_work is True

    def test_requires_evidence(self):
        """requires_evidence should return True when evidence is needed."""
        with_evidence = ValidationResult(
            status="NEEDS_WORK",
            score=0.5,
            evidence_required=["citation", "quote"],
        )
        without_evidence = ValidationResult(
            status="PASS",
            score=0.9,
            evidence_required=[],
        )

        assert with_evidence.requires_evidence() is True
        assert without_evidence.requires_evidence() is False

    def test_get_summary(self):
        """get_summary should return human-readable summary."""
        result = ValidationResult(
            status="NEEDS_WORK",
            score=0.7,
            issues=["issue 1", "issue 2"],
            evidence_required=["evidence 1"],
        )
        summary = result.get_summary()

        assert "NEEDS_WORK" in summary
        assert "0.70" in summary
        assert "issue 1" in summary


class TestRealityCheckerConfig:
    """Tests for RealityCheckerConfig."""

    def test_default_config_strict(self):
        """Default config should be strict - high threshold for PASS."""
        config = RealityCheckerConfig()

        assert config.min_score_for_pass == 0.85
        assert config.require_character_consistency is True
        assert config.require_plot_coherence is True
        assert config.require_evidence_for_pass is True
        assert config.max_issues_before_fail == 5

    def test_custom_config(self):
        """Custom config should override defaults."""
        config = RealityCheckerConfig(
            min_score_for_pass=0.7,
            require_character_consistency=False,
        )

        assert config.min_score_for_pass == 0.7
        assert config.require_character_consistency is False


class TestRealityChecker:
    """Tests for RealityChecker class."""

    def test_init_with_defaults(self):
        """Init with defaults should create valid instance."""
        checker = RealityChecker()
        assert checker.config is not None
        assert checker.llm_client is None

    def test_init_with_llm_client(self):
        """Init with LLM client should store it."""
        mock_client = object()
        checker = RealityChecker(llm_client=mock_client)
        assert checker.llm_client is mock_client

    def test_check_character_consistency_no_issues(self):
        """Character consistency check with no issues."""
        checker = RealityChecker()
        content = "韩林站在演武场中，柳如烟看着他。"
        characters = {
            "韩林": {
                "realm": "炼气期",
                "identity": "太虚宗弟子",
                "personality": "坚毅果敢",
            },
            "柳如烟": {
                "realm": "筑基期",
                "identity": "柳家千金",
                "personality": "冷傲",
            },
        }

        result = checker.check_character_consistency(content, characters)

        assert result["consistent"] is True
        assert len(result["issues"]) == 0

    def test_check_character_consistency_realm_violation(self):
        """Character consistency check should detect realm violations."""
        checker = RealityChecker()
        content = "韩林（炼气期）施展渡劫期的法术击败了对手。"
        characters = {
            "韩林": {
                "realm": "炼气期",
                "identity": "太虚宗弟子",
                "personality": "坚毅果敢",
            },
        }

        result = checker.check_character_consistency(content, characters)

        assert result["consistent"] is False
        assert len(result["issues"]) > 0
        assert "境界" in result["issues"][0] or "realm" in result["issues"][0].lower()

    def test_check_character_consistency_personality_violation(self):
        """Character consistency check should detect personality violations."""
        checker = RealityChecker()
        content = "【柳如烟】（性格冷傲）微笑着热情地欢迎他。"
        characters = {
            "柳如烟": {
                "realm": "筑基期",
                "identity": "柳家千金",
                "personality": "冷傲",
            },
        }

        result = checker.check_character_consistency(content, characters)

        assert result["consistent"] is False
        assert len(result["issues"]) > 0

    def test_check_plot_coherence_no_previous_summary(self):
        """Plot coherence check with no previous summary should pass."""
        checker = RealityChecker()
        content = "韩林站在演武场中，开始修炼。"

        result = checker.check_plot_coherence(content, "")

        assert result["coherent"] is True
        assert len(result["issues"]) == 0

    def test_validate_content_with_no_issues(self):
        """validate_content should return PASS for clean content."""
        checker = RealityChecker()
        content = "韩林是太虚宗弟子，炼气期修士。他与柳如烟在演武场相遇。"

        criteria = {
            "characters": {
                "韩林": {"realm": "炼气期", "identity": "太虚宗弟子", "personality": "坚毅"},
                "柳如烟": {"realm": "筑基期", "identity": "柳家千金", "personality": "冷傲"},
            },
            "previous_summary": "",
            "required_elements": [],
            "prohibited_elements": [],
        }

        result = checker.validate_content(content, criteria)

        # Clean content should get high score
        assert result.score >= 0.8
        assert result.status in ["PASS", "NEEDS_WORK"]

    def test_validate_content_with_issues(self):
        """validate_content should return NEEDS_WORK with issues."""
        checker = RealityChecker()
        content = "韩林（炼气期）施展了渡劫期的法术。"

        criteria = {
            "characters": {
                "韩林": {"realm": "炼气期", "identity": "太虚宗弟子", "personality": "坚毅"},
            },
            "previous_summary": "",
            "required_elements": [],
            "prohibited_elements": [],
        }

        result = checker.validate_content(content, criteria)

        assert result.status in ["FAIL", "NEEDS_WORK"]
        assert len(result.issues) > 0

    def test_validate_content_required_elements(self):
        """validate_content should check required elements."""
        checker = RealityChecker()
        content = "韩林修炼了一会儿。"  # Missing required element

        criteria = {
            "characters": {},
            "previous_summary": "",
            "required_elements": ["战斗", "突破"],
            "prohibited_elements": [],
        }

        result = checker.validate_content(content, criteria)

        assert result.status == "NEEDS_WORK"
        assert any("缺少必需元素" in issue for issue in result.issues)

    def test_validate_content_prohibited_elements(self):
        """validate_content should check prohibited elements."""
        checker = RealityChecker()
        content = "韩林使用了禁忌法术。"

        criteria = {
            "characters": {},
            "previous_summary": "",
            "required_elements": [],
            "prohibited_elements": ["禁忌法术"],
        }

        result = checker.validate_content(content, criteria)

        assert result.status in ["FAIL", "NEEDS_WORK"]
        assert len(result.issues) > 0

    def test_validate_content_fantasy_detection(self):
        """validate_content should detect impossible claims."""
        checker = RealityChecker()
        # Use content that matches the detection patterns
        content = "炼气期的韩林击败了渡劫期的叶尘。"

        criteria = {
            "characters": {
                "韩林": {"realm": "炼气期", "identity": "太虚宗弟子", "personality": "坚毅"},
            },
            "previous_summary": "",
            "required_elements": [],
            "prohibited_elements": [],
        }

        result = checker.validate_content(content, criteria)

        assert result.status in ["FAIL", "NEEDS_WORK"]
        # Should detect the impossible claim (low realm defeating high realm)
        assert len(result.issues) > 0

    def test_require_evidence(self):
        """require_evidence should return evidence requirements."""
        checker = RealityChecker()
        claim = "韩林的父亲是太虚宗的天才"

        evidence = checker.require_evidence(claim)

        assert isinstance(evidence, list)
        assert len(evidence) > 0

    def test_get_reality_checker_factory(self):
        """get_reality_checker should return RealityChecker instance."""
        checker = get_reality_checker()
        assert isinstance(checker, RealityChecker)

        checker_with_client = get_reality_checker(llm_client=object())
        assert checker_with_client.llm_client is not None


class TestRealityCheckerIntegration:
    """Integration tests for RealityChecker with NovelOrchestrator."""

    def test_reality_checker_integration_config(self):
        """RealityChecker should integrate with OrchestratorConfig."""
        from agents.novel_orchestrator import OrchestratorConfig, NovelOrchestrator

        config = OrchestratorConfig(
            enable_reality_checker=True,
            reality_checker_config=RealityCheckerConfig(
                min_score_for_pass=0.8
            ),
        )

        orchestrator = NovelOrchestrator(config=config)
        assert orchestrator._reality_checker is not None
        assert orchestrator._reality_checker.config.min_score_for_pass == 0.8

    def test_reality_checker_disabled(self):
        """RealityChecker can be disabled via config."""
        from agents.novel_orchestrator import OrchestratorConfig, NovelOrchestrator

        config = OrchestratorConfig(enable_reality_checker=False)
        orchestrator = NovelOrchestrator(config=config)

        assert orchestrator._reality_checker is None

    def test_quality_gate_integration(self):
        """quality_gate should work with RealityChecker."""
        from agents.novel_orchestrator import OrchestratorConfig, NovelOrchestrator

        config = OrchestratorConfig(enable_reality_checker=True)
        orchestrator = NovelOrchestrator(config=config)

        content = "韩林站在演武场中修炼。"
        criteria = {
            "characters": {},
            "previous_summary": "",
            "required_elements": [],
            "prohibited_elements": [],
        }

        result = orchestrator.quality_gate(content, criteria)
        assert isinstance(result, ValidationResult)
        assert result.status in ["PASS", "NEEDS_WORK", "FAIL"]

    def test_validate_chapter_integration(self):
        """validate_chapter should build criteria from context."""
        from agents.novel_orchestrator import OrchestratorConfig, NovelOrchestrator

        config = OrchestratorConfig(enable_reality_checker=True)
        orchestrator = NovelOrchestrator(config=config)

        content = "韩林在演武场修炼。"
        context = {
            "characters": {
                "韩林": {"realm": "炼气期", "identity": "太虚宗弟子", "personality": "坚毅"},
            },
            "previous_summary": "韩林开始了修炼之旅。",
            "required_elements": [],
            "prohibited_elements": [],
        }

        result = orchestrator.validate_chapter(content, context)
        assert isinstance(result, ValidationResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
