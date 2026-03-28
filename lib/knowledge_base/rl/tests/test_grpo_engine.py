"""Tests for GRPO Engine"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from rl.config import RLConfig, RLMode
from rl.engine import RLEngine
from rl.experience import Experience, ExperienceBatch
from rl.grpo_engine import GRPOEngine, GiGPOEngine


class TestGRPOEngine:
    """Test GRPO Engine"""

    def test_compute_advantages(self):
        """Test advantage computation"""
        config = RLConfig(mode=RLMode.GRPO, group_size=4)
        engine = GRPOEngine(config)

        batch = ExperienceBatch(
            experiences=[
                Experience(id=str(i), task_id="t", task_type="test", prompt="", content="", reward=r)
                for i, r in enumerate([0.5, 0.9, 0.3, 0.8])
            ]
        )

        advantages = engine.compute_advantages(batch)
        assert len(advantages) == 4
        # 最高奖励应该有最高 advantage
        assert advantages[0] > advantages[-1]

    def test_normalize_advantages(self):
        """Test advantage normalization"""
        engine = GRPOEngine(RLConfig())

        advantages = [0.5, 1.0, -0.5, 0.0]
        normalized = engine.normalize_advantages(advantages)

        assert len(normalized) == 4
        # 标准化后应该均值为 0
        assert abs(sum(normalized)) < 1e-6

    def test_compute_grpo_loss(self):
        """Test GRPO loss computation"""
        config = RLConfig(mode=RLMode.GRPO, clip_epsilon=0.2)
        engine = GRPOEngine(config)

        old_log_probs = [-1.0, -2.0, -1.5, -1.8]
        new_log_probs = [-1.1, -1.9, -1.4, -2.0]
        advantages = [0.5, 1.0, -0.5, 0.0]

        loss, clip_fraction = engine.compute_grpo_loss(
            old_log_probs, new_log_probs, advantages, config.clip_epsilon
        )

        assert isinstance(loss, float)
        assert 0.0 <= clip_fraction <= 1.0


class TestGiGPOEngine:
    """Test GiGPO Engine"""

    def test_compute_gae(self):
        """Test GAE computation"""
        config = gigpo_config_for_test()
        engine = GiGPOEngine(config)

        rewards = [0.0, 0.5, 1.0, 0.5]
        values = [0.3, 0.5, 0.7, 0.6]
        next_values = [0.5, 0.7, 0.6, 0.0]
        dones = [False, False, False, True]

        advantages, value_targets = engine.compute_gae(
            rewards, values, next_values, dones
        )

        assert len(advantages) == 4
        assert len(value_targets) == 4

    def test_intrinsic_reward(self):
        """Test intrinsic reward computation"""
        config = gigpo_config_for_test()
        engine = GiGPOEngine(config)

        experiences = [
            Experience(id=str(i), task_id="t", task_type="test", prompt="", content="x" * (100 + i * 50), reward=0.5)
            for i in range(4)
        ]

        intrinsic = engine.compute_intrinsic_reward(experiences[0], experiences)
        assert isinstance(intrinsic, float)
        assert 0.0 <= intrinsic <= 0.2


def gigpo_config_for_test():
    """Helper to create GiGPO config for testing"""
    return RLConfig(
        mode=RLMode.GIGPO,
        group_size=4,
        episode_gae_lambda=0.95,
        step_gae_lambda=0.9,
    )


class TestRLEngine:
    """Test main RL Engine"""

    def test_collection_only_mode(self):
        """Test COLLECTION_ONLY mode"""
        config = RLConfig(mode=RLMode.COLLECTION_ONLY)
        engine = RLEngine(config=config)

        assert engine.mode == RLMode.COLLECTION_ONLY
        assert not engine.is_training_enabled

        # Should be able to collect experience
        exp = engine.collect_experience(
            task_id="test-1",
            content="Test content " * 50,
            prompt="Write something",
            task_type="test",
        )

        assert exp is not None
        assert exp.reward >= 0.0

    def test_grpo_mode(self):
        """Test GRPO mode"""
        config = RLConfig(mode=RLMode.GRPO, group_size=4)
        engine = RLEngine(config=config)

        assert engine.mode == RLMode.GRPO
        assert engine.is_training_enabled

    def test_collect_batch(self):
        """Test batch collection"""
        config = RLConfig(mode=RLMode.COLLECTION_ONLY)
        engine = RLEngine(config=config)

        batch = engine.collect_batch(
            task_id="test-batch",
            contents=["Content 1", "Content 2", "Content 3"],
            rewards=[0.3, 0.7, 0.5],
            task_type="test",
        )

        assert batch.size == 3
        assert batch.group_id is not None

    def test_compute_reward(self):
        """Test reward computation"""
        config = RLConfig()
        engine = RLEngine(config=config)

        content = "他走进房间，然后坐下来。之后，他开始思考。最后，事情解决了。"
        prompt = "写一段小说"

        result = engine.compute_reward(content, prompt, {})
        assert result.total >= 0.0

    def test_get_stats(self):
        """Test stats retrieval"""
        config = RLConfig(mode=RLMode.COLLECTION_ONLY)
        engine = RLEngine(config=config)

        # Collect some experiences
        for i in range(3):
            engine.collect_experience(
                task_id=f"test-{i}",
                content="Test content " * 20,
                prompt="Test",
            )

        stats = engine.get_stats()
        assert "collection_count" in stats
        assert "store_stats" in stats
