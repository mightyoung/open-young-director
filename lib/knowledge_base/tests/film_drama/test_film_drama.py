"""Tests for FILM_DRAMA mode components."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock

from agents.film_drama import (
    DirectorAgent,
    DirectorConfig,
    CharacterAgent,
    CharacterBible,
    CharacterMemoryQueue,
    MiddlewareChain,
    EmotionalStateMiddleware,
    ClarificationMiddleware,
    MemoryQueueMiddleware,
    MiddlewareResult,
    HandoffMessage,
    PlotBeat,
    Scene,
    InMemoryMessageQueue,
    MessageType,
    AgentRole,
    SceneStatus,
    BeatType,
)


class TestEnums:
    """Test enum values."""

    def test_message_types(self):
        assert MessageType.HANDOFF.value == "handoff"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.CLARIFY.value == "clarify"
        assert MessageType.NPC_SIMULATE.value == "npc_simulate"

    def test_agent_roles(self):
        assert AgentRole.DIRECTOR.value == "director"
        assert AgentRole.MAIN_CHARACTER.value == "main_character"
        assert AgentRole.NPC_SIMULATED.value == "npc_simulated"

    def test_scene_status(self):
        assert SceneStatus.PENDING.value == "pending"
        assert SceneStatus.IN_PROGRESS.value == "in_progress"
        assert SceneStatus.COMPLETED.value == "completed"

    def test_beat_types(self):
        assert BeatType.OPENING.value == "opening"
        assert BeatType.CONFLICT.value == "conflict"
        assert BeatType.CLIMAX.value == "climax"
        assert BeatType.RESOLUTION.value == "resolution"


class TestHandoffMessage:
    """Test HandoffMessage dataclass."""

    def test_message_creation(self):
        msg = HandoffMessage(
            id="test_123",
            msg_type=MessageType.HANDOFF.value,
            sender="director",
            recipient="韩林",
            scene_id="scene_1",
            content="请回应这个场景",
        )
        assert msg.id == "test_123"
        assert msg.sender == "director"
        assert msg.recipient == "韩林"
        assert msg.msg_type == "handoff"

    def test_message_to_dict(self):
        msg = HandoffMessage(
            id="test_123",
            msg_type=MessageType.RESPONSE.value,
            sender="韩林",
            recipient="director",
            scene_id="scene_1",
            content="我的回应",
        )
        d = msg.to_dict()
        assert d["id"] == "test_123"
        assert d["sender"] == "韩林"
        assert "timestamp" in d


class TestPlotBeat:
    """Test PlotBeat dataclass."""

    def test_beat_creation(self):
        beat = PlotBeat(
            beat_id="beat_001",
            beat_type=BeatType.OPENING.value,
            description="开场白",
            expected_chars=["韩林", "柳如烟"],
            sequence=0,
        )
        assert beat.beat_id == "beat_001"
        assert beat.beat_type == "opening"
        assert beat.should_participate("韩林")
        assert not beat.should_participate("叶尘")


class TestScene:
    """Test Scene dataclass."""

    def test_scene_creation(self):
        scene = Scene(
            scene_id="scene_001",
            chapter=1,
            location="太虚宗演武场",
            time_of_day="morning",
        )
        assert scene.scene_id == "scene_001"
        assert scene.status == "pending"
        assert scene.current_beat_index == 0

    def test_advance_beat(self):
        beats = [
            PlotBeat(beat_id="b1", beat_type="opening", description="", sequence=0),
            PlotBeat(beat_id="b2", beat_type="development", description="", sequence=1),
        ]
        scene = Scene(
            scene_id="scene_001",
            chapter=1,
            location="test",
            beats=beats,
        )
        assert scene.get_current_beat().beat_id == "b1"
        assert scene.advance_beat()
        assert scene.get_current_beat().beat_id == "b2"
        assert not scene.advance_beat()  # No more beats


class TestCharacterBible:
    """Test CharacterBible dataclass."""

    def test_bible_creation(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="太虚宗弟子",
            realm="炼气期",
            personality="坚毅果敢",
            speaking_style="简洁有力",
            backstory="父亲是宗门天才",
            objective_this_chapter="证明自己",
        )
        assert bible.name == "韩林"
        assert bible.realm == "炼气期"

    def test_to_system_prompt(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="太虚宗弟子",
            realm="炼气期",
            personality="坚毅果敢",
            speaking_style="简洁有力",
            relationships={"柳如烟": "未婚妻"},
        )
        prompt = bible.to_system_prompt("太古魔帝传")
        assert "韩林" in prompt
        assert "太古魔帝传" in prompt
        assert "坚毅果敢" in prompt


class TestInMemoryMessageQueue:
    """Test InMemoryMessageQueue."""

    @pytest.mark.asyncio
    async def test_send_receive(self):
        queue = InMemoryMessageQueue()
        msg = HandoffMessage(
            id="msg_1",
            msg_type=MessageType.HANDOFF.value,
            sender="director",
            recipient="韩林",
            scene_id="scene_1",
            content="测试消息",
        )

        await queue.send(msg)
        received = await queue.receive("韩林", timeout=1.0)

        assert received is not None
        assert received.id == "msg_1"
        assert received.content == "测试消息"

    @pytest.mark.asyncio
    async def test_broadcast(self):
        queue = InMemoryMessageQueue()
        msg = HandoffMessage(
            id="msg_2",
            msg_type=MessageType.SETUP.value,
            sender="director",
            recipient="broadcast",
            scene_id="scene_1",
            content="广播消息",
        )

        await queue.send(msg)
        received = await queue.receive("韩林", timeout=1.0)

        assert received is not None
        assert received.content == "广播消息"


class TestCharacterMemoryQueue:
    """Test CharacterMemoryQueue."""

    def test_record_state(self):
        queue = CharacterMemoryQueue()

        queue.record_state(
            character_name="韩林",
            beat_id="beat_1",
            emotions={"愤怒": True},
            conflict_active=True,
            tension_level=0.7,
            summary="韩林感到愤怒",
        )

        context = queue.get_context_for_character("韩林")
        assert context["character_name"] == "韩林"
        assert context["current_emotions"]["愤怒"]
        assert context["conflict_active"]
        assert context["tension_level"] == 0.7

    def test_global_tension(self):
        queue = CharacterMemoryQueue()

        queue.update_global_tension(0.3)
        assert queue.get_global_tension() == 0.3

        queue.update_global_tension(0.2)
        assert queue.get_global_tension() == 0.5

        queue.update_global_tension(-0.3)
        assert queue.get_global_tension() == 0.2

    def test_scene_summary(self):
        queue = CharacterMemoryQueue()
        queue.record_state("韩林", "beat_1", {"愤怒": True}, tension_level=0.6)
        queue.record_state("柳如烟", "beat_1", {}, tension_level=0.3)

        summary = queue.get_scene_summary()
        assert "global_tension" in summary
        assert "character_states" in summary
        assert "韩林" in summary["character_states"]


class TestMiddlewareChain:
    """Test MiddlewareChain."""

    @pytest.mark.asyncio
    async def test_chain_processing(self):
        chain = MiddlewareChain()

        # Custom test middleware
        class TestMiddleware:
            name = "test"
            async def process(self, character_name, beat, output, context):
                return MiddlewareResult(modified_output=output + "_modified")

        chain.add(TestMiddleware())

        beat = PlotBeat(beat_id="b1", beat_type="opening", description="test")
        result = await chain.process("韩林", beat, "原始输出", {})

        assert result.modified_output == "原始输出_modified"

    @pytest.mark.asyncio
    async def test_skip_agent(self):
        chain = MiddlewareChain()

        class SkipMiddleware:
            name = "skip"
            async def process(self, character_name, beat, output, context):
                return MiddlewareResult(skip_agent=True, modified_output="skipped")

        chain.add(SkipMiddleware())

        beat = PlotBeat(beat_id="b1", beat_type="opening", description="test")
        result = await chain.process("韩林", beat, "原始输出", {})

        assert result.skip_agent
        assert result.modified_output == "skipped"


class TestEmotionalStateMiddleware:
    """Test EmotionalStateMiddleware."""

    @pytest.mark.asyncio
    async def test_process(self):
        mw = EmotionalStateMiddleware()
        beat = PlotBeat(beat_id="b1", beat_type=BeatType.CONFLICT.value, description="冲突")

        context = {
            "memory": {
                "current_emotions": {"愤怒": True},
                "conflict_active": False,
            }
        }

        result = await mw.process("韩林", beat, "韩林愤怒地回应", context)

        assert result.modified_output == "韩林愤怒地回应"
        assert "conflict_active" in result.metadata


class TestClarificationMiddleware:
    """Test ClarificationMiddleware."""

    @pytest.mark.asyncio
    async def test_ambiguous_detection(self):
        mw = ClarificationMiddleware()
        beat = PlotBeat(beat_id="b1", beat_type=BeatType.DEVELOPMENT.value, description="发展")

        # Output with ambiguous phrase
        result = await mw.process("韩林", beat, "也许...可能...不确定", {})

        assert result.metadata["clarification_needed"]

    @pytest.mark.asyncio
    async def test_clear_contradiction(self):
        mw = ClarificationMiddleware()
        beat = PlotBeat(beat_id="b1", beat_type=BeatType.DEVELOPMENT.value, description="发展")

        context = {
            "previous_outputs": {
                "韩林": ["我同意这个决定"],
            }
        }

        # Contradictory output
        result = await mw.process("韩林", beat, "不，我不同意", context)

        assert result.metadata.get("clarification_needed")


class TestMemoryQueueMiddleware:
    """Test MemoryQueueMiddleware."""

    @pytest.mark.asyncio
    async def test_records_emotions(self):
        queue = CharacterMemoryQueue()
        mw = MemoryQueueMiddleware(queue)

        beat = PlotBeat(beat_id="b1", beat_type=BeatType.CONFLICT.value, description="冲突")

        result = await mw.process("韩林", beat, "韩林愤怒地喊道：该死！", {})

        assert result.metadata["emotions_recorded"]["愤怒"]
        assert result.metadata["tension_recorded"] > 0

    @pytest.mark.asyncio
    async def test_no_memory_queue(self):
        mw = MemoryQueueMiddleware(None)

        beat = PlotBeat(beat_id="b1", beat_type=BeatType.OPENING.value, description="开场")
        result = await mw.process("韩林", beat, "开场白", {})

        # Should not fail, just pass through
        assert result.modified_output == "开场白"


class TestDirectorAgent:
    """Test DirectorAgent."""

    def test_plan_scene(self):
        agent = DirectorAgent()
        characters = {
            "韩林": {
                "identity": "太虚宗弟子",
                "realm": "炼气期",
                "personality": "坚毅果敢",
                "speaking_style": "简洁有力",
            }
        }

        script = agent.plan_scene(
            chapter_number=1,
            scene_outline="韩林与柳如烟相遇",
            characters=characters,
            location="太虚宗",
            time_of_day="morning",
        )

        assert script.scene.chapter == 1
        assert script.scene.location == "太虚宗"
        assert len(script.cast) == 1
        assert script.cast[0].name == "韩林"

    @pytest.mark.asyncio
    async def test_execute_scene_with_mock_llm(self):
        agent = DirectorAgent()
        agent.llm_client = Mock()

        # Mock LLM response
        async def mock_generate(prompt):
            return "这是模拟的回应"

        agent._default_llm_call = mock_generate

        characters = {
            "韩林": {
                "identity": "太虚宗弟子",
                "realm": "炼气期",
                "personality": "坚毅果敢",
                "speaking_style": "简洁有力",
            }
        }

        script = agent.plan_scene(
            chapter_number=1,
            scene_outline="韩林修炼",
            characters=characters,
            location="杂役院",
        )

        result = await agent.execute_scene(script)

        assert result["status"] == SceneStatus.COMPLETED.value
        # beat_outputs is {beat_id: {char_name: output}}
        assert any("韩林" in beat_dict for beat_dict in result["beat_outputs"].values())

    def test_assemble_scene_output(self):
        agent = DirectorAgent()

        # Create a script with some outputs
        characters = {
            "韩林": {
                "identity": "太虚宗弟子",
                "realm": "炼气期",
                "personality": "坚毅果敢",
                "speaking_style": "简洁有力",
            }
        }

        script = agent.plan_scene(
            chapter_number=1,
            scene_outline="韩林出场",
            characters=characters,
            location="太虚宗",
        )

        # Add some mock outputs
        agent._character_outputs = {
            "韩林": ["韩林说：我要修炼"]
        }

        output = agent.assemble_scene_output(script)
        assert len(output) > 0


class TestCharacterAgent:
    """Test CharacterAgent."""

    def test_agent_creation(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="太虚宗弟子",
            realm="炼气期",
            personality="坚毅果敢",
            speaking_style="简洁有力",
        )

        agent = CharacterAgent(
            name="韩林",
            character_bible=bible,
        )

        assert agent.name == "韩林"
        assert agent.role == AgentRole.MAIN_CHARACTER.value

    @pytest.mark.asyncio
    async def test_receive_message(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="弟子",
            realm="炼气期",
            personality="坚毅",
            speaking_style="简洁",
        )

        agent = CharacterAgent(name="韩林", character_bible=bible)

        msg = HandoffMessage(
            id="msg_1",
            msg_type=MessageType.HANDOFF.value,
            sender="director",
            recipient="韩林",
            scene_id="scene_1",
            content="请回应",
        )

        await agent.receive_message(msg)
        pending = await agent.get_next_message()

        assert pending is not None
        assert pending.id == "msg_1"

    def test_get_state(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="弟子",
            realm="炼气期",
            personality="坚毅",
            speaking_style="简洁",
        )

        agent = CharacterAgent(name="韩林", character_bible=bible)

        state = agent.get_state()
        assert state["name"] == "韩林"
        assert state["pending_handoffs"] == 0
        assert state["response_count"] == 0

    def test_reset(self):
        bible = CharacterBible(
            name="韩林",
            role=AgentRole.MAIN_CHARACTER.value,
            identity="弟子",
            realm="炼气期",
            personality="坚毅",
            speaking_style="简洁",
        )

        agent = CharacterAgent(name="韩林", character_bible=bible)
        agent._emotional_state = {"愤怒": True}
        agent._completed_beats = ["beat_1"]

        agent.reset()

        assert agent._emotional_state == {}
        assert agent._completed_beats == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
