"""Tests for Rewards Module"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from rl.rewards import (
    CoherenceReward,
    DialogueQualityReward,
    EfficiencyReward,
    EmotionalResonanceReward,
    NovelRewardFunction,
    PlotProgressionReward,
    RewardResult,
    RewardWeights,
    TaskCompletionReward,
    compute_novel_reward,
)


class TestTaskCompletionReward:
    """Test TaskCompletionReward"""

    def test_short_content(self):
        """Test short content gets low reward"""
        reward_fn = TaskCompletionReward(min_length=100)
        result = reward_fn.compute("Short", "", {})
        assert result < 0.5

    def test_normal_content(self):
        """Test normal content gets reasonable reward"""
        reward_fn = TaskCompletionReward(min_length=50, max_length=5000)
        content = "这是一个测试内容。" * 10  # 约 150 字
        result = reward_fn.compute(content, "", {})
        assert 0.4 <= result <= 1.0


class TestCoherenceReward:
    """Test CoherenceReward"""

    def test_coherent_content(self):
        """Test coherent content gets high reward"""
        reward_fn = CoherenceReward()
        content = "他走进房间，然后坐下来。之后，他开始思考。然而，事情并没有那么简单。"
        result = reward_fn.compute(content, "", {})
        assert result > 0.3

    def test_incoherent_content(self):
        """Test incoherent content gets low reward"""
        reward_fn = CoherenceReward()
        content = "Test"
        result = reward_fn.compute(content, "", {})
        assert result < 0.5


class TestDialogueQualityReward:
    """Test DialogueQualityReward"""

    def test_with_dialogue(self):
        """Test content with dialogue"""
        reward_fn = DialogueQualityReward()
        content = '"你好！"他说。"你今天怎么样？"'
        result = reward_fn.compute(content, "", {})
        assert result > 0.3

    def test_without_dialogue(self):
        """Test content without dialogue"""
        reward_fn = DialogueQualityReward()
        content = "这是一段没有对话的叙述文字。"
        result = reward_fn.compute(content, "", {})
        assert result == 0.3


class TestPlotProgressionReward:
    """Test PlotProgressionReward"""

    def test_progression_keywords(self):
        """Test content with plot progression keywords"""
        reward_fn = PlotProgressionReward()
        content = "突然，天空变暗了。然后，雨开始下了。最后，他们决定回家。"
        result = reward_fn.compute(content, "", {})
        assert result > 0.3


class TestNovelRewardFunction:
    """Test NovelRewardFunction"""

    def test_compute_reward(self):
        """Test compute reward"""
        reward_fn = NovelRewardFunction()
        content = "他走进房间，然后坐下来。她微笑着说：「你好！」突然，事情发生了变化。"
        prompt = "写一段小说"
        context = {"requires_dialogue": True}

        result = reward_fn.compute(content, prompt, context)
        assert isinstance(result, RewardResult)
        assert 0.0 <= result.total <= 1.5

    def test_compute_simple(self):
        """Test compute simple"""
        reward_fn = NovelRewardFunction()
        content = "测试内容 " * 50
        prompt = "写小说"
        context = {}

        reward = reward_fn.compute_simple(content, prompt, context)
        assert isinstance(reward, float)
        assert 0.0 <= reward <= 1.0


class TestComputeNovelReward:
    """Test compute_novel_reward function"""

    def test_compute_novel_reward(self):
        """Test convenience function"""
        content = "这是一个测试内容。" * 20
        prompt = "写小说"
        context = {}

        reward = compute_novel_reward(content, prompt, context)
        assert isinstance(reward, float)
        assert 0.0 <= reward <= 1.0
