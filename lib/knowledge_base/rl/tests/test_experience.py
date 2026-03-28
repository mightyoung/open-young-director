"""Tests for Experience Module"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from datetime import datetime
from rl.experience import (
    Experience,
    ExperienceBatch,
    ExperienceType,
    StepData,
    TrainingStats,
)


class TestStepData:
    """Test StepData"""

    def test_to_dict(self):
        """Test StepData to_dict"""
        step = StepData(
            step_id=0,
            prompt="Test prompt",
            response="Test response",
            reward=0.5,
            value=0.3,
            log_prob=-1.5,
            advantage=0.2,
        )
        d = step.to_dict()
        assert d["step_id"] == 0
        assert d["prompt"] == "Test prompt"
        assert d["reward"] == 0.5

    def test_from_dict(self):
        """Test StepData from_dict"""
        data = {
            "step_id": 1,
            "prompt": "Test",
            "response": "Response",
            "reward": 0.8,
            "value": 0.5,
            "log_prob": -2.0,
            "advantage": 0.3,
            "metadata": {},
        }
        step = StepData.from_dict(data)
        assert step.step_id == 1
        assert step.reward == 0.8


class TestExperience:
    """Test Experience"""

    def test_create_experience(self):
        """Test Experience creation"""
        exp = Experience(
            id="test-123",
            task_id="task-1",
            task_type="chapter_generation",
            prompt="Write a chapter",
            content="Chapter content here",
            reward=0.7,
        )
        assert exp.id == "test-123"
        assert exp.task_type == "chapter_generation"
        assert exp.reward == 0.7

    def test_num_steps(self):
        """Test num_steps property"""
        exp = Experience(
            id="test",
            task_id="task",
            task_type="test",
            prompt="",
            content="",
        )
        assert exp.num_steps == 0

        exp.steps = [
            StepData(step_id=0, prompt="p1", response="r1"),
            StepData(step_id=1, prompt="p2", response="r2"),
        ]
        assert exp.num_steps == 2

    def test_to_dict(self):
        """Test Experience to_dict"""
        exp = Experience(
            id="test-456",
            task_id="task-2",
            task_type="dialogue",
            prompt="Write dialogue",
            content="Dialogue content",
            reward=0.9,
            advantage=0.5,
        )
        d = exp.to_dict()
        assert d["id"] == "test-456"
        assert d["reward"] == 0.9
        assert d["advantage"] == 0.5

    def test_from_dict(self):
        """Test Experience from_dict"""
        data = {
            "id": "exp-789",
            "task_id": "task-3",
            "task_type": "plot",
            "prompt": "Continue the plot",
            "content": "Plot content",
            "reward": 0.6,
            "total_reward": 0.6,
            "rewards": {"coherence": 0.7},
            "created_at": datetime.now().isoformat(),
            "exp_type": "episode",
            "steps": [],
            "metadata": {},
            "group_id": "group-1",
            "rank": 2,
            "advantage": -0.5,
            "model_name": "gpt-4",
            "temperature": 0.8,
            "generation_params": {},
        }
        exp = Experience.from_dict(data)
        assert exp.id == "exp-789"
        assert exp.rank == 2
        assert exp.advantage == -0.5


class TestExperienceBatch:
    """Test ExperienceBatch"""

    def test_create_batch(self):
        """Test ExperienceBatch creation"""
        batch = ExperienceBatch()
        assert batch.size == 0

        exp1 = Experience(
            id="1", task_id="t", task_type="test", prompt="", content=""
        )
        exp2 = Experience(
            id="2", task_id="t", task_type="test", prompt="", content=""
        )

        batch.add(exp1)
        batch.add(exp2)
        assert batch.size == 2

    def test_get_top_k(self):
        """Test get_top_k"""
        batch = ExperienceBatch(
            experiences=[
                Experience(id=str(i), task_id="t", task_type="test", prompt="", content="", reward=r)
                for i, r in enumerate([0.5, 0.9, 0.3, 0.8])
            ]
        )

        top_2 = batch.get_top_k(2)
        assert len(top_2) == 2
        assert top_2[0].reward == 0.9
        assert top_2[1].reward == 0.8

    def test_get_worst_k(self):
        """Test get_worst_k"""
        batch = ExperienceBatch(
            experiences=[
                Experience(id=str(i), task_id="t", task_type="test", prompt="", content="", reward=r)
                for i, r in enumerate([0.5, 0.9, 0.3, 0.8])
            ]
        )

        worst_2 = batch.get_worst_k(2)
        assert len(worst_2) == 2
        assert worst_2[0].reward == 0.3
        assert worst_2[1].reward == 0.5


class TestTrainingStats:
    """Test TrainingStats"""

    def test_to_dict(self):
        """Test TrainingStats to_dict"""
        stats = TrainingStats(
            step=10,
            policy_loss=0.15,
            value_loss=0.05,
            total_loss=0.20,
            mean_advantage=0.1,
            mean_reward=0.75,
        )
        d = stats.to_dict()
        assert d["step"] == 10
        assert d["policy_loss"] == 0.15
        assert d["mean_reward"] == 0.75
