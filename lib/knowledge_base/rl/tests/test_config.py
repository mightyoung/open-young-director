"""Tests for RL Config Module"""

import pytest
import sys
from pathlib import Path
# Add lib/knowledge_base to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rl.config import (
    RLConfig,
    RLMode,
    RewardWeights,
    default_rl_config,
    grpo_config,
    gigpo_config,
)


class TestRLConfig:
    """Test RLConfig"""

    def test_default_config(self):
        """Test default config"""
        config = RLConfig()
        assert config.enabled is True
        assert config.mode == RLMode.COLLECTION_ONLY
        assert config.group_size == 4
        assert config.learning_rate == 1e-5
        assert config.clip_epsilon == 0.2

    def test_grpo_config(self):
        """Test GRPO config"""
        config = grpo_config()
        assert config.mode == RLMode.GRPO
        assert config.group_size == 4

    def test_gigpo_config(self):
        """Test GiGPO config"""
        config = gigpo_config()
        assert config.mode == RLMode.GIGPO
        assert config.episode_gae_lambda == 0.95
        assert config.step_gae_lambda == 0.9


class TestRewardWeights:
    """Test RewardWeights"""

    def test_default_weights(self):
        """Test default weights sum to 1"""
        weights = RewardWeights()
        total = (
            weights.task_completion
            + weights.evaluation
            + weights.efficiency
            + weights.coherence
            + weights.character_consistency
            + weights.dialogue_quality
            + weights.plot_progression
            + weights.emotional_resonance
        )
        assert abs(total - 1.0) < 1e-6

    def test_to_dict(self):
        """Test to_dict"""
        weights = RewardWeights()
        d = weights.to_dict()
        assert isinstance(d, dict)
        assert "task_completion" in d
        assert "coherence" in d

    def test_from_dict(self):
        """Test from_dict"""
        data = {
            "task_completion": 0.3,
            "evaluation": 0.2,
            "efficiency": 0.05,
            "coherence": 0.15,
            "character_consistency": 0.15,
            "dialogue_quality": 0.1,
            "plot_progression": 0.03,
            "emotional_resonance": 0.02,
        }
        weights = RewardWeights.from_dict(data)
        assert weights.task_completion == 0.3
