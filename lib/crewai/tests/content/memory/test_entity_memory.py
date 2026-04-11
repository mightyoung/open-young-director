"""Tests for EntityMemory and ContinuityTracker."""

import pytest
import tempfile
import json
from pathlib import Path

from crewai.content.memory.entity_memory import EntityMemory
from crewai.content.memory.continuity_tracker import ContinuityTracker
from crewai.content.memory.memory_types import (
    Entity,
    Relationship,
    Event,
    EntityState,
    ConsistencyIssue,
)


class TestEntityMemory:
    """Tests for EntityMemory."""

    def test_add_entity(self):
        """Test adding an entity."""
        memory = EntityMemory()
        entity = Entity(
            id="char1",
            name="张三",
            type="character",
            description="主角",
        )
        memory.add_entity(entity)

        assert memory.get_entity("char1") == entity
        assert memory.get_entity("张三") == entity

    def test_add_entity_with_aliases(self):
        """Test adding entity with aliases."""
        memory = EntityMemory()
        entity = Entity(
            id="char1",
            name="李四",
            type="character",
            description="反派",
            aliases=["四哥", "李公子"],
        )
        memory.add_entity(entity)

        assert memory.get_entity("char1") == entity
        assert memory.get_entity("李四") == entity
        assert memory.get_entity("四哥") == entity
        assert memory.get_entity("李公子") == entity

    def test_get_entities_by_type(self):
        """Test filtering entities by type."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description=""
        ))
        memory.add_entity(Entity(
            id="char2", name="李四", type="character", description=""
        ))
        memory.add_entity(Entity(
            id="loc1", name="京城", type="location", description=""
        ))

        characters = memory.get_entities_by_type("character")
        assert len(characters) == 2

        locations = memory.get_entities_by_type("location")
        assert len(locations) == 1

    def test_add_relationship(self):
        """Test adding relationships."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description=""
        ))
        memory.add_entity(Entity(
            id="char2", name="李四", type="character", description=""
        ))

        relationship = Relationship(
            target_id="char2",
            relation_type="friend",
            description="好朋友"
        )
        result = memory.add_relationship("char1", relationship)

        assert result is True
        entity = memory.get_entity("char1")
        assert len(entity.relationships) == 1
        assert entity.relationships[0].target_id == "char2"

    def test_update_entity_property(self):
        """Test updating entity properties."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description=""
        ))

        memory.update_entity_property("char1", "level", 10)
        memory.update_entity_property("char1", "realm", "筑基期")

        entity = memory.get_entity("char1")
        assert entity.properties["level"] == 10
        assert entity.properties["realm"] == "筑基期"

    def test_update_character(self):
        """Test update_character convenience method."""
        memory = EntityMemory()
        entity = memory.update_character("张三", {
            "description": "主角",
            "realm": "筑基期",
            "status": "active"
        })

        assert entity.name == "张三"
        assert entity.type == "character"
        assert entity.properties["realm"] == "筑基期"

    def test_search_entities(self):
        """Test entity search."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description="主角"
        ))
        memory.add_entity(Entity(
            id="char2", name="李四", type="character", description="反派"
        ))
        memory.add_entity(Entity(
            id="loc1", name="京城", type="location", description="首都"
        ))

        results = memory.search_entities("主角")
        assert len(results) == 1
        assert results[0].name == "张三"

        results = memory.search_entities("张")
        assert len(results) == 1

    def test_remove_entity(self):
        """Test removing an entity."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description=""
        ))
        memory.add_entity(Entity(
            id="char2", name="李四", type="character", description=""
        ))

        # Add relationship first
        memory.add_relationship("char1", Relationship(
            target_id="char2", relation_type="friend"
        ))

        # Remove char1
        result = memory.remove_entity("char1")
        assert result is True
        assert memory.get_entity("char1") is None

        # char2 should still exist
        assert memory.get_entity("char2") is not None

    def test_check_consistency(self):
        """Test consistency checking."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            properties={"level": 10}
        ))

        # No conflict
        issues = memory.check_consistency("", {
            "char1": {"level": 10}
        })
        assert len(issues) == 0

        # Conflict
        issues = memory.check_consistency("", {
            "char1": {"level": 5}
        })
        assert len(issues) == 1
        assert issues[0].property == "level"

    def test_merge_state(self):
        """Test merging another EntityMemory."""
        memory1 = EntityMemory()
        memory1.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            properties={"level": 10}
        ))

        memory2 = EntityMemory()
        memory2.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            properties={"level": 20, "realm": "筑基期"}
        ))
        memory2.add_entity(Entity(
            id="char2", name="李四", type="character", description=""
        ))

        # Merge with "latest" resolution
        issues = memory1.merge_state(memory2, conflict_resolution="latest")

        # char1 should have updated level
        entity = memory1.get_entity("char1")
        assert entity.properties["level"] == 20
        assert entity.properties["realm"] == "筑基期"

        # char2 should be added
        assert memory1.get_entity("char2") is not None

    def test_get_entity_history(self):
        """Test getting entity history."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            properties={"level": 10}
        ))
        memory.add_relationship("char1", Relationship(
            target_id="char2", relation_type="friend"
        ))

        history = memory.get_entity_history("char1")
        assert len(history) == 2  # 1 property + 1 relationship

    def test_checkpoint_save_load(self):
        """Test checkpoint save and load."""
        memory1 = EntityMemory()
        memory1.add_entity(Entity(
            id="char1", name="张三", type="character", description="主角",
            aliases=["三哥"]
        ))
        memory1.add_relationship("char1", Relationship(
            target_id="char2", relation_type="enemy"
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "checkpoint.json"
            memory1.save_checkpoint(str(path))

            # Load into new instance
            memory2 = EntityMemory()
            result = memory2.load_checkpoint(str(path))
            assert result is True

            entity = memory2.get_entity("char1")
            assert entity is not None
            assert entity.name == "张三"
            assert entity.aliases == ["三哥"]

    def test_get_context_for_chapter(self):
        """Test getting context for a chapter."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            created_at="chapter1"
        ))
        memory.add_entity(Entity(
            id="loc1", name="京城", type="location", description="",
            created_at="chapter1"
        ))

        context = memory.get_context_for_chapter(5)

        assert context["chapter"] == 5
        assert context["entity_count"] == 2
        assert len(context["characters"]) == 1
        assert len(context["locations"]) == 1

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        memory1 = EntityMemory()
        memory1.add_entity(Entity(
            id="char1", name="张三", type="character", description="",
            aliases=["三哥"]
        ))

        data = memory1.to_dict()
        memory2 = EntityMemory.from_dict(data)

        entity = memory2.get_entity("char1")
        assert entity is not None
        assert entity.name == "张三"
        assert entity.aliases == ["三哥"]

    def test_clear(self):
        """Test clearing all entities."""
        memory = EntityMemory()
        memory.add_entity(Entity(
            id="char1", name="张三", type="character", description=""
        ))

        memory.clear()
        assert memory.get_entity_count() == 0


class TestContinuityTracker:
    """Tests for ContinuityTracker."""

    def test_add_event(self):
        """Test adding an event."""
        tracker = ContinuityTracker()
        event = Event(
            id="event1",
            timestamp="第1章",
            description="张三来到京城",
            involved_entities=["char1", "loc1"],
            chapter=1
        )
        tracker.add_event(event)

        assert tracker.get_total_events() == 1
        assert len(tracker.get_events_at_chapter(1)) == 1

    def test_update_entity_state(self):
        """Test updating entity state."""
        tracker = ContinuityTracker()
        tracker.update_entity_state("char1", {
            "location": "京城",
            "status": "active"
        })

        state = tracker.get_entity_state("char1")
        assert state["location"] == "京城"
        assert state["status"] == "active"

    def test_get_entity_state_at_chapter(self):
        """Test getting entity state at specific chapter."""
        tracker = ContinuityTracker()

        tracker.update_entity_state("char1", {"level": 1})
        tracker.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="升级",
            involved_entities=["char1"],
            chapter=1
        ))

        tracker.update_entity_state("char1", {"level": 2})
        tracker.add_event(Event(
            id="event2",
            timestamp="第2章",
            description="再升级",
            involved_entities=["char1"],
            chapter=2
        ))

        state = tracker.get_entity_state_at_chapter("char1", 1)
        assert state is not None
        assert state.properties["level"] == 1

    def test_check_continuity_deceased_entity(self):
        """Test detecting continuity issue with deceased entity."""
        tracker = ContinuityTracker()
        tracker.update_entity_state("char1", {"status": "deceased"})

        # Try to involve deceased entity in new event
        event = Event(
            id="event1",
            timestamp="第5章",
            description="张三参与战斗",
            involved_entities=["char1"],
            chapter=5
        )

        issues = tracker.check_continuity(event)
        assert len(issues) == 1
        assert issues[0].issue_type == "state_conflict"
        assert issues[0].severity == "high"

    def test_get_relevant_context(self):
        """Test getting relevant context for an entity."""
        tracker = ContinuityTracker()
        tracker.update_entity_state("char1", {"location": "京城"})

        tracker.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="张三在京城",
            involved_entities=["char1"],
            chapter=1
        ))

        tracker.update_entity_state("char1", {"location": "边境"})

        tracker.add_event(Event(
            id="event2",
            timestamp="第3章",
            description="张三去边境",
            involved_entities=["char1"],
            chapter=3
        ))

        context = tracker.get_relevant_context("char1", 5)

        assert len(context["past_events"]) == 2
        assert context["current_state"]["location"] == "边境"

    def test_get_entity_timeline(self):
        """Test getting entity timeline."""
        tracker = ContinuityTracker()
        tracker.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="事件1",
            involved_entities=["char1"],
            chapter=1
        ))
        tracker.add_event(Event(
            id="event2",
            timestamp="第2章",
            description="事件2",
            involved_entities=["char1", "char2"],
            chapter=2
        ))
        tracker.add_event(Event(
            id="event3",
            timestamp="第3章",
            description="事件3",
            involved_entities=["char2"],
            chapter=3
        ))

        timeline = tracker.get_entity_timeline("char1")
        assert len(timeline) == 2

        timeline = tracker.get_entity_timeline("char2")
        assert len(timeline) == 2

    def test_get_events_by_chapter_range(self):
        """Test getting events by chapter range."""
        tracker = ContinuityTracker()
        for i in range(1, 6):
            tracker.add_event(Event(
                id=f"event{i}",
                timestamp=f"第{i}章",
                description=f"事件{i}",
                involved_entities=["char1"],
                chapter=i
            ))

        events = tracker.get_events_by_chapter_range(2, 4)
        assert len(events) == 3

    def test_checkpoint_save_load(self):
        """Test checkpoint save and load."""
        tracker1 = ContinuityTracker()
        tracker1.update_entity_state("char1", {"level": 10})
        tracker1.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="事件1",
            involved_entities=["char1"],
            chapter=1
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tracker.json"
            tracker1.save_checkpoint(str(path))

            tracker2 = ContinuityTracker()
            result = tracker2.load_checkpoint(str(path))
            assert result is True
            assert tracker2.get_total_events() == 1
            assert tracker2.get_entity_state("char1")["level"] == 10

    def test_validate_timeline(self):
        """Test timeline validation."""
        tracker = ContinuityTracker()
        tracker.add_event(Event(
            id="event1",
            timestamp="第2章",
            description="事件1",
            involved_entities=["char1"],
            chapter=2
        ))
        tracker.add_event(Event(
            id="event2",
            timestamp="第1章",  # Out of order!
            description="事件2",
            involved_entities=["char1"],
            chapter=1
        ))

        issues = tracker.validate_timeline()
        assert len(issues) >= 1

    def test_to_dict_from_dict(self):
        """Test serialization round-trip."""
        tracker1 = ContinuityTracker()
        tracker1.update_entity_state("char1", {"level": 10})
        tracker1.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="事件1",
            involved_entities=["char1"],
            chapter=1
        ))

        data = tracker1.to_dict()
        tracker2 = ContinuityTracker.from_dict(data)

        assert tracker2.get_total_events() == 1
        assert tracker2.get_entity_state("char1")["level"] == 10

    def test_clear(self):
        """Test clearing all data."""
        tracker = ContinuityTracker()
        tracker.add_event(Event(
            id="event1",
            timestamp="第1章",
            description="事件1",
            involved_entities=["char1"],
            chapter=1
        ))
        tracker.update_entity_state("char1", {"level": 1})

        tracker.clear()
        assert tracker.get_total_events() == 0
        assert tracker.get_entity_state("char1") == {}

    def test_get_plot_threads_summarizes_future_events(self):
        """Test get_plot_threads groups future hooks, conflicts, and reveals."""
        tracker = ContinuityTracker()
        tracker.add_event(Event(
            id="past",
            timestamp="第1章",
            description="前章已经落幕",
            involved_entities=["char0"],
            chapter=1,
        ))
        tracker.add_event(Event(
            id="hook",
            timestamp="第3章",
            description="主角发现城墙下的神秘符号？",
            involved_entities=["char1"],
            chapter=3,
            metadata={"thread_type": "hook"},
        ))
        tracker.add_event(Event(
            id="conflict",
            timestamp="第4章",
            description="双方冲突升级，追杀正式开始",
            involved_entities=["char1", "char2"],
            chapter=4,
            metadata={"thread_type": "conflict"},
        ))
        tracker.add_event(Event(
            id="reveal",
            timestamp="第5章",
            description="真相即将揭晓，幕后黑手浮出水面",
            involved_entities=["char2"],
            chapter=5,
            metadata={"thread_type": "reveal"},
        ))

        threads = tracker.get_plot_threads(2)

        assert threads["active_hooks"]
        assert threads["active_hooks"][0].startswith("第3章")
        assert threads["unresolved_conflicts"]
        assert threads["pending_reveals"]
        assert threads["entities_in_play"] == ["char1", "char2"]
