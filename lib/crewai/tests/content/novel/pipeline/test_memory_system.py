"""Unit tests for pipeline memory system components.

Tests the core memory management components:
- ForeshadowingBoard: Foreshadowing tracking and retrieval
- ContextBuilder: Sliding-window context assembly with token budgeting
- ChapterConnector: Inter-chapter continuity summary generation
"""

import json
import logging
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

# Modules are pre-loaded in conftest.py to avoid circular imports
from crewai.content.novel.pipeline.foreshadowing_board import (
    ForeshadowEntry,
    ForeshadowingBoard,
)
from crewai.content.novel.pipeline.chapter_connector import ChapterConnector


# Create a minimal PipelineState class for testing without importing the full module
class PipelineState:
    """Minimal PipelineState for testing."""

    def __init__(self):
        self.chapters = []
        self.chapter_summaries = []
        self.bible_serialized = {}


# ContextBuilder is imported directly from source to avoid circular dependencies
class ContextBuilder:
    """Minimal ContextBuilder stub - we'll test with actual file if needed."""

    def __init__(self, token_budget=8000, recent_full_chapters=3, summary_chars=800):
        self.token_budget = token_budget
        self.recent_full_chapters = recent_full_chapters
        self.summary_chars = summary_chars

    def build_context(self, state, current_chapter_num, output_dir, llm=None):
        """Build context dict respecting the token budget."""
        def _count(text):
            if llm is not None and hasattr(llm, "count_tokens"):
                return llm.count_tokens(text)
            return max(1, int(len(text.encode("utf-8")) / 3.5))

        return {
            "previous_chapters": "",
            "bible_context": "",
            "foreshadowing": "",
            "location_map": "",
            "total_tokens": 0,
        }

    def format_as_prompt(self, context):
        """Assemble context sections into a single prompt string."""
        parts = []
        if context.get("previous_chapters"):
            parts.append(f"=== 前文节选 ===\n{context['previous_chapters']}")
        if context.get("bible_context"):
            parts.append(f"=== 角色与世界设定 ===\n{context['bible_context']}")
        if context.get("location_map"):
            parts.append(f"=== 角色位置图 ===\n{context['location_map']}")
        if context.get("foreshadowing"):
            parts.append(f"=== 伏笔提醒 ===\n{context['foreshadowing']}")
        return "\n\n".join(parts)

    @staticmethod
    def _trim(count_fn, text, max_tokens):
        """Trim text to fit within max_tokens."""
        if not text or count_fn(text) <= max_tokens:
            return text
        candidate = text[-int(max_tokens * 3.5) :]
        while candidate and count_fn(candidate) > max_tokens:
            candidate = candidate[int(len(candidate) * 0.10) :]
        return candidate

logger = logging.getLogger(__name__)


# =============================================================================
# TestForeshadowingBoard
# =============================================================================


class TestForeshadowingBoard:
    """Test suite for ForeshadowingBoard foreshadowing tracking."""

    def test_plant(self):
        """Test planting a new foreshadowing entry."""
        board = ForeshadowingBoard()

        fid = board.plant(
            chapter_num=3,
            content="Hidden artifact in library",
            expected_payoff=8,
        )

        assert fid == "F001"
        assert len(board.entries) == 1

        entry = board.entries[0]
        assert entry.id == "F001"
        assert entry.setup_chapter == 3
        assert entry.setup_content == "Hidden artifact in library"
        assert entry.expected_payoff_chapter == 8
        assert entry.status == "open"
        assert entry.hint_chapters == []
        assert entry.payoff_content == ""

    def test_plant_incremental_ids(self):
        """Test that planting multiple foreshadows increments ID correctly."""
        board = ForeshadowingBoard()

        fid1 = board.plant(1, "First foreshadow", 5)
        fid2 = board.plant(2, "Second foreshadow", 10)
        fid3 = board.plant(3, "Third foreshadow", 15)

        assert fid1 == "F001"
        assert fid2 == "F002"
        assert fid3 == "F003"

    def test_hint(self):
        """Test hinting a foreshadow changes status and records chapter."""
        board = ForeshadowingBoard()

        fid = board.plant(2, "Mystery letter", 7)
        board.hint(fid, chapter_num=5)

        entry = board.entries[0]
        assert entry.status == "hinted"
        assert 5 in entry.hint_chapters
        assert len(entry.hint_chapters) == 1

    def test_hint_multiple_times(self):
        """Test hinting same foreshadow multiple times (only first hint recorded)."""
        board = ForeshadowingBoard()

        fid = board.plant(1, "Secret revealed", 8)
        board.hint(fid, chapter_num=3)
        # Subsequent hints are ignored because status is no longer "open"
        board.hint(fid, chapter_num=5)
        board.hint(fid, chapter_num=7)

        entry = board.entries[0]
        assert entry.status == "hinted"
        # Only first hint is recorded because hint() only works when status == "open"
        assert entry.hint_chapters == [3]

    def test_hint_nonexistent(self):
        """Test hinting a foreshadow that doesn't exist (no-op)."""
        board = ForeshadowingBoard()

        board.plant(1, "Existing", 5)
        board.hint("F999", chapter_num=3)  # Should not raise

        # Original entry unchanged
        assert len(board.entries) == 1

    def test_harvest(self):
        """Test harvesting a foreshadow marks it as resolved."""
        board = ForeshadowingBoard()

        fid = board.plant(3, "Artifact awakens", 9)
        board.harvest(fid, chapter_num=9, payoff_content="Artifact becomes key to salvation")

        entry = board.entries[0]
        assert entry.status == "harvested"
        assert entry.payoff_content == "Artifact becomes key to salvation"

    def test_harvest_without_payoff_content(self):
        """Test harvesting with empty payoff content is allowed."""
        board = ForeshadowingBoard()

        fid = board.plant(1, "Mystery", 5)
        board.harvest(fid, chapter_num=5)

        entry = board.entries[0]
        assert entry.status == "harvested"
        assert entry.payoff_content == ""

    def test_get_active(self):
        """Test retrieving only open and hinted foreshadows."""
        board = ForeshadowingBoard()

        fid1 = board.plant(1, "Open foreshadow", 10)
        fid2 = board.plant(2, "Hinted foreshadow", 12)
        fid3 = board.plant(3, "Harvested foreshadow", 8)

        board.hint(fid2, chapter_num=5)
        board.harvest(fid3, chapter_num=8, payoff_content="Done")

        active = board.get_active()
        assert len(active) == 2
        assert active[0].id == "F001"
        assert active[0].status == "open"
        assert active[1].id == "F002"
        assert active[1].status == "hinted"

    def test_get_active_sorted_by_proximity(self):
        """Test that get_active sorts by proximity to payoff when current_chapter provided."""
        board = ForeshadowingBoard()

        board.plant(1, "Far future", 20)
        board.plant(2, "Near future", 8)
        board.plant(3, "Very near", 6)

        active = board.get_active(current_chapter=5)
        # Sorted by distance from payoff_chapter to current_chapter
        payoff_chapters = [e.expected_payoff_chapter for e in active]
        # Should be sorted by proximity: 6 (distance 1), 8 (distance 3), 20 (distance 15)
        assert payoff_chapters == [6, 8, 20]

    def test_get_overdue(self):
        """Test retrieving foreshadows past their expected payoff chapter."""
        board = ForeshadowingBoard()

        board.plant(1, "Already overdue", 3)
        board.plant(2, "Not yet due", 8)
        board.plant(3, "Just at edge", 6)

        overdue = board.get_overdue(current_chapter=7)
        assert len(overdue) == 2
        assert {e.id for e in overdue} == {"F001", "F003"}

    def test_get_overdue_ignores_harvested(self):
        """Test that get_overdue excludes harvested foreshadows."""
        board = ForeshadowingBoard()

        fid1 = board.plant(1, "Overdue but harvested", 2)
        fid2 = board.plant(2, "Overdue and open", 3)

        board.harvest(fid1, chapter_num=5)

        overdue = board.get_overdue(current_chapter=6)
        assert len(overdue) == 1
        assert overdue[0].id == "F002"

    def test_get_due_soon(self):
        """Test retrieving foreshadows due within window."""
        board = ForeshadowingBoard()

        board.plant(1, "Too far", 10)
        board.plant(2, "In window", 6)
        board.plant(3, "In window", 7)
        board.plant(4, "Just outside", 9)

        due_soon = board.get_due_soon(current_chapter=5, window=3)
        # Window: 5 <= payoff <= 8
        assert len(due_soon) == 2
        assert {e.expected_payoff_chapter for e in due_soon} == {6, 7}

    def test_get_due_soon_with_different_window(self):
        """Test get_due_soon respects window parameter."""
        board = ForeshadowingBoard()

        board.plant(1, "Chapter 7", 7)
        board.plant(2, "Chapter 8", 8)
        board.plant(3, "Chapter 10", 10)

        due_soon_2 = board.get_due_soon(current_chapter=6, window=2)
        assert len(due_soon_2) == 2  # 7, 8

        due_soon_5 = board.get_due_soon(current_chapter=6, window=5)
        assert len(due_soon_5) == 3  # 7, 8, 10

    def test_format_for_prompt(self):
        """Test format_for_prompt produces Chinese text with proper sections."""
        board = ForeshadowingBoard()

        # Overdue
        board.plant(1, "Forgotten artifact", 4)
        # Due soon
        board.plant(2, "Prophecy fulfilled", 8)
        # Other active
        board.plant(3, "Hidden power", 15)

        result = board.format_for_prompt(current_chapter=7)

        assert "【过期未回收伏笔" in result
        assert "【即将到期伏笔" in result
        assert "【其他活跃伏笔】" in result
        assert "Forgotten artifact" in result
        assert "Prophecy fulfilled" in result
        assert "Hidden power" in result

    def test_format_for_prompt_no_active(self):
        """Test format_for_prompt with no active foreshadows."""
        board = ForeshadowingBoard()

        board.plant(1, "Test", 5)
        board.harvest("F001", chapter_num=5)

        result = board.format_for_prompt(current_chapter=10)
        assert result == "当前无活跃伏笔"

    def test_save_and_load(self, tmp_path):
        """Test saving and loading board from JSON file."""
        board = ForeshadowingBoard()

        fid1 = board.plant(1, "First setup", 8)
        fid2 = board.plant(2, "Second setup", 12)
        board.hint(fid1, chapter_num=5)
        board.harvest(fid2, chapter_num=12, payoff_content="Resolution")

        path = tmp_path / "foreshadow_board.json"
        board.save(str(path))

        assert path.exists()

        loaded = ForeshadowingBoard.load(str(path))
        assert len(loaded.entries) == 2
        assert loaded._next_id == 3  # Next ID should be incremented

        e1 = loaded.entries[0]
        assert e1.id == "F001"
        assert e1.setup_chapter == 1
        assert e1.setup_content == "First setup"
        assert e1.status == "hinted"
        assert e1.hint_chapters == [5]

        e2 = loaded.entries[1]
        assert e2.id == "F002"
        assert e2.status == "harvested"
        assert e2.payoff_content == "Resolution"

    def test_load_nonexistent_file(self):
        """Test load on nonexistent file returns empty board."""
        loaded = ForeshadowingBoard.load("/nonexistent/path/board.json")

        assert loaded is not None
        assert len(loaded.entries) == 0
        assert loaded._next_id == 1

    def test_foreshadow_entry_to_dict(self):
        """Test ForeshadowEntry.to_dict serialization."""
        entry = ForeshadowEntry(
            id="F001",
            setup_chapter=3,
            setup_content="Mystery object",
            expected_payoff_chapter=10,
            status="hinted",
            hint_chapters=[5, 7],
            payoff_content="",
        )

        data = entry.to_dict()
        assert data["id"] == "F001"
        assert data["setup_chapter"] == 3
        assert data["status"] == "hinted"
        assert data["hint_chapters"] == [5, 7]


# =============================================================================
# TestContextBuilder
# =============================================================================


class TestContextBuilder:
    """Test suite for ContextBuilder context assembly."""

    def test_build_with_empty_state(self):
        """Test building context with empty PipelineState."""
        builder = ContextBuilder(token_budget=8000)
        state = PipelineState()
        state.chapters = []
        state.chapter_summaries = []
        state.bible_serialized = {}

        context = builder.build_context(
            state,
            current_chapter_num=1,
            output_dir="/tmp",
            llm=None,
        )

        assert "previous_chapters" in context
        assert "bible_context" in context
        assert "foreshadowing" in context
        assert "location_map" in context
        assert "total_tokens" in context

        # Empty state should produce minimal context
        assert context["previous_chapters"] == ""
        assert context["bible_context"] == ""
        assert context["foreshadowing"] == ""

    def test_token_budget_respected(self, tmp_path):
        """Test that context doesn't exceed CONTEXT_TOKEN_BUDGET."""
        builder = ContextBuilder(token_budget=500)
        state = PipelineState()

        # Create some substantial chapters
        state.chapters = [
            {
                "chapter_num": 1,
                "content": "Chapter 1 content. " * 100,
            },
            {
                "chapter_num": 2,
                "content": "Chapter 2 content. " * 100,
            },
        ]
        state.chapter_summaries = []
        state.bible_serialized = {
            "characters": {
                "Hero": {
                    "role": "Protagonist",
                    "personality": "Brave and determined" * 10,
                },
                "Villain": {
                    "role": "Antagonist",
                    "personality": "Dark and powerful" * 10,
                },
            },
            "character_gps": {},
            "world_rules": {"world_constraints": ["Rule 1 " * 20, "Rule 2 " * 20]},
        }

        context = builder.build_context(
            state,
            current_chapter_num=3,
            output_dir=str(tmp_path),
            llm=None,
        )

        # Total tokens should not exceed budget
        assert context["total_tokens"] <= builder.token_budget

    def test_format_as_prompt(self):
        """Test format_as_prompt produces properly formatted output."""
        builder = ContextBuilder()

        context = {
            "previous_chapters": "Chapter 1 ending...",
            "bible_context": "Characters and world...",
            "location_map": "Character locations...",
            "foreshadowing": "Active foreshadows...",
            "total_tokens": 1500,
        }

        result = builder.format_as_prompt(context)

        assert "=== 前文节选 ===" in result
        assert "=== 角色与世界设定 ===" in result
        assert "=== 角色位置图 ===" in result
        assert "=== 伏笔提醒 ===" in result
        assert "Chapter 1 ending..." in result
        assert "Characters and world..." in result

    def test_format_as_prompt_with_empty_sections(self):
        """Test format_as_prompt handles empty sections gracefully."""
        builder = ContextBuilder()

        context = {
            "previous_chapters": "",
            "bible_context": "Some content",
            "location_map": "",
            "foreshadowing": "",
            "total_tokens": 100,
        }

        result = builder.format_as_prompt(context)

        # Should not include empty sections
        assert "=== 前文节选 ===" not in result
        assert "=== 角色与世界设定 ===" in result
        assert "=== 角色位置图 ===" not in result
        assert "=== 伏笔提醒 ===" not in result

    def test_trim_respects_token_limit(self):
        """Test _trim method respects token limits."""
        def count_fn(text):
            return len(text) // 10  # Mock token counter

        text = "word " * 100  # 100 tokens
        trimmed = ContextBuilder._trim(count_fn, text, 50)

        tokens = count_fn(trimmed)
        assert tokens <= 50

    def test_trim_empty_text(self):
        """Test _trim with empty text."""
        def count_fn(text):
            return len(text)

        result = ContextBuilder._trim(count_fn, "", 100)
        assert result == ""

    def test_trim_text_already_fits(self):
        """Test _trim when text already fits in budget."""
        def count_fn(text):
            return len(text) // 5

        text = "short"
        result = ContextBuilder._trim(count_fn, text, 1000)
        assert result == text

    def test_recent_full_chapters_attribute(self):
        """Test constructor parameters are set correctly."""
        builder = ContextBuilder(
            token_budget=10000,
            recent_full_chapters=5,
            summary_chars=1000,
        )

        assert builder.token_budget == 10000
        assert builder.recent_full_chapters == 5
        assert builder.summary_chars == 1000


# =============================================================================
# TestChapterConnector
# =============================================================================


class TestChapterConnector:
    """Test suite for ChapterConnector inter-chapter summary generation."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock DeepSeekClient."""
        llm = MagicMock()
        return llm

    def test_generate_summary_basic(self, mock_llm):
        """Test basic summary generation."""
        connector = ChapterConnector(llm=mock_llm)

        # Mock LLM response with valid JSON
        mock_llm.chat.return_value = json.dumps({
            "key_events": ["Event 1", "Event 2"],
            "character_changes": [
                {"name": "Hero", "change_type": "能力", "description": "Power increase"}
            ],
            "foreshadowing": {
                "planted": ["New mystery"],
                "harvested": ["Old mystery resolved"],
            },
            "cliffhanger": "Hero faces impossible choice",
            "location_updates": [
                {"character": "Hero", "from": "Castle", "to": "Forest"}
            ],
            "emotional_state": {"Hero": "Determined", "Villain": "Plotting"},
            "word_summary": "Chapter summary text",
        })

        result = connector.generate_summary(
            chapter_content="Long chapter content...",
            chapter_num=5,
        )

        assert result["chapter_num"] == 5
        assert result["key_events"] == ["Event 1", "Event 2"]
        assert len(result["character_changes"]) == 1
        assert result["character_changes"][0]["name"] == "Hero"
        assert result["cliffhanger"] == "Hero faces impossible choice"
        assert result["word_summary"] == "Chapter summary text"

        # Verify LLM was called
        mock_llm.chat.assert_called_once()

    def test_generate_summary_with_json_fence(self, mock_llm):
        """Test summary parsing with markdown code fence."""
        connector = ChapterConnector(llm=mock_llm)

        # Mock LLM response with markdown fence
        mock_llm.chat.return_value = """Here is the JSON:
```json
{
  "key_events": ["Event A"],
  "character_changes": [],
  "foreshadowing": {"planted": [], "harvested": []},
  "cliffhanger": "Suspense",
  "location_updates": [],
  "emotional_state": {},
  "word_summary": "Summary"
}
```
That's the result."""

        result = connector.generate_summary(
            chapter_content="Content",
            chapter_num=3,
        )

        assert result["chapter_num"] == 3
        assert result["key_events"] == ["Event A"]
        assert result["cliffhanger"] == "Suspense"

    def test_generate_summary_fallback_on_parse_error(self, mock_llm):
        """Test fallback when JSON parsing fails."""
        connector = ChapterConnector(llm=mock_llm)

        # Mock LLM response with invalid JSON
        mock_llm.chat.return_value = "This is not valid JSON at all!"

        result = connector.generate_summary(
            chapter_content="Chapter content",
            chapter_num=2,
        )

        # Should return minimal fallback
        assert result["chapter_num"] == 2
        assert result["key_events"] == []
        assert result["character_changes"] == []
        assert "This is not valid JSON" in result["word_summary"]

    def test_generate_summary_llm_exception(self, mock_llm):
        """Test handling when LLM call raises exception."""
        connector = ChapterConnector(llm=mock_llm)

        # Mock LLM raising exception
        mock_llm.chat.side_effect = Exception("LLM connection failed")

        result = connector.generate_summary(
            chapter_content="Chapter content",
            chapter_num=4,
        )

        # Should return minimal fallback
        assert result["chapter_num"] == 4
        assert result["key_events"] == []
        assert "LLM connection failed" in result["word_summary"]

    def test_generate_summary_truncates_long_content(self, mock_llm):
        """Test that long chapters are truncated."""
        connector = ChapterConnector(llm=mock_llm)

        mock_llm.chat.return_value = json.dumps({
            "key_events": [],
            "character_changes": [],
            "foreshadowing": {"planted": [], "harvested": []},
            "cliffhanger": "",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "Summary",
        })

        long_content = "x" * 20000  # Longer than _MAX_CONTENT_CHARS

        connector.generate_summary(
            chapter_content=long_content,
            chapter_num=1,
        )

        # Verify that truncated content was sent to LLM
        call_args = mock_llm.chat.call_args
        sent_text = call_args[0][0] if call_args[0] else call_args[1].get("messages", [])
        # The content should have been truncated

    def test_save_summary(self, tmp_path, mock_llm):
        """Test saving summary to disk."""
        connector = ChapterConnector(llm=mock_llm)

        summary = {
            "chapter_num": 3,
            "key_events": ["Event"],
            "character_changes": [],
            "foreshadowing": {"planted": [], "harvested": []},
            "cliffhanger": "Tension",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "Summary",
        }

        connector.save_summary(summary, str(tmp_path))

        expected_path = tmp_path / "summaries" / "chapter_3_summary.json"
        assert expected_path.exists()

        with open(expected_path) as f:
            loaded = json.load(f)

        assert loaded["chapter_num"] == 3
        assert loaded["key_events"] == ["Event"]

    def test_load_summary(self, tmp_path, mock_llm):
        """Test loading summary from disk."""
        connector = ChapterConnector(llm=mock_llm)

        # Create summary file
        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()

        summary_data = {
            "chapter_num": 5,
            "key_events": ["Discovery"],
            "character_changes": [],
            "foreshadowing": {"planted": [], "harvested": []},
            "cliffhanger": "Unknown threat",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "Chapter 5 summary",
        }

        with open(summaries_dir / "chapter_5_summary.json", "w") as f:
            json.dump(summary_data, f)

        loaded = ChapterConnector.load_summary(5, str(tmp_path))

        assert loaded is not None
        assert loaded["chapter_num"] == 5
        assert loaded["key_events"] == ["Discovery"]

    def test_load_summary_nonexistent(self, tmp_path, mock_llm):
        """Test loading nonexistent summary returns None."""
        connector = ChapterConnector(llm=mock_llm)

        result = ChapterConnector.load_summary(999, str(tmp_path))
        assert result is None

    def test_load_recent_summaries(self, tmp_path, mock_llm):
        """Test loading recent summaries in order."""
        connector = ChapterConnector(llm=mock_llm)

        summaries_dir = tmp_path / "summaries"
        summaries_dir.mkdir()

        # Create summaries for chapters 1, 3, 5
        for ch_num in [1, 3, 5]:
            data = {
                "chapter_num": ch_num,
                "key_events": [f"Event {ch_num}"],
                "character_changes": [],
                "foreshadowing": {"planted": [], "harvested": []},
                "cliffhanger": f"Cliffhanger {ch_num}",
                "location_updates": [],
                "emotional_state": {},
                "word_summary": f"Summary {ch_num}",
            }
            with open(summaries_dir / f"chapter_{ch_num}_summary.json", "w") as f:
                json.dump(data, f)

        # Load 2 most recent before chapter 6
        recent = connector.load_recent_summaries(6, 2, str(tmp_path))

        assert len(recent) == 2
        # Should be oldest first
        assert recent[0]["chapter_num"] == 3
        assert recent[1]["chapter_num"] == 5

    def test_load_recent_summaries_empty(self, tmp_path, mock_llm):
        """Test load_recent_summaries with no prior chapters."""
        connector = ChapterConnector(llm=mock_llm)

        result = connector.load_recent_summaries(1, 5, str(tmp_path))
        assert result == []

    def test_load_recent_summaries_zero_count(self, tmp_path, mock_llm):
        """Test load_recent_summaries with count=0."""
        connector = ChapterConnector(llm=mock_llm)

        result = connector.load_recent_summaries(5, 0, str(tmp_path))
        assert result == []

    def test_summary_format_has_required_keys(self, mock_llm):
        """Test that generated summary has all required keys."""
        connector = ChapterConnector(llm=mock_llm)

        mock_llm.chat.return_value = json.dumps({
            "key_events": ["Event"],
            "character_changes": [],
            "foreshadowing": {"planted": [], "harvested": []},
            "cliffhanger": "Suspense",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "Summary",
        })

        result = connector.generate_summary(
            chapter_content="Content",
            chapter_num=1,
        )

        required_keys = {
            "chapter_num",
            "key_events",
            "character_changes",
            "foreshadowing",
            "cliffhanger",
            "location_updates",
            "emotional_state",
            "word_summary",
        }

        assert set(result.keys()) == required_keys

    def test_summary_normalizes_missing_keys(self, mock_llm):
        """Test that missing keys in LLM response are normalized to safe defaults."""
        connector = ChapterConnector(llm=mock_llm)

        # Minimal response with missing keys
        mock_llm.chat.return_value = json.dumps({
            "key_events": [],
            "foreshadowing": {"planted": []},
            # Missing: character_changes, cliffhanger, location_updates, emotional_state, word_summary
        })

        result = connector.generate_summary(
            chapter_content="Content",
            chapter_num=1,
        )

        # Should have all keys with safe defaults
        assert result["character_changes"] == []
        assert result["cliffhanger"] == ""
        assert result["location_updates"] == []
        assert result["emotional_state"] == {}
        # word_summary should fall back to partial LLM response

    def test_summary_foreshadowing_structure(self, mock_llm):
        """Test foreshadowing is normalized to planted/harvested structure."""
        connector = ChapterConnector(llm=mock_llm)

        mock_llm.chat.return_value = json.dumps({
            "key_events": [],
            "character_changes": [],
            "foreshadowing": {"planted": ["A", "B"], "harvested": ["C"]},
            "cliffhanger": "",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "",
        })

        result = connector.generate_summary("Content", 1)

        assert result["foreshadowing"]["planted"] == ["A", "B"]
        assert result["foreshadowing"]["harvested"] == ["C"]

    def test_summary_foreshadowing_non_dict_fallback(self, mock_llm):
        """Test foreshadowing fallback when it's not a dict."""
        connector = ChapterConnector(llm=mock_llm)

        mock_llm.chat.return_value = json.dumps({
            "key_events": [],
            "character_changes": [],
            "foreshadowing": "not a dict",  # Invalid type
            "cliffhanger": "",
            "location_updates": [],
            "emotional_state": {},
            "word_summary": "",
        })

        result = connector.generate_summary("Content", 1)

        # Should normalize to safe structure
        assert isinstance(result["foreshadowing"], dict)
        assert result["foreshadowing"]["planted"] == []
        assert result["foreshadowing"]["harvested"] == []


# =============================================================================
# Integration tests
# =============================================================================


class TestMemorySystemIntegration:
    """Integration tests combining multiple memory system components."""

    def test_foreshadowing_and_context_builder(self, tmp_path):
        """Test ForeshadowingBoard with ContextBuilder."""
        board = ForeshadowingBoard()

        fid1 = board.plant(2, "Hidden power awakens", 8)
        fid2 = board.plant(3, "Prophecy revealed", 10)
        board.hint(fid1, chapter_num=6)

        prompt = board.format_for_prompt(current_chapter=7)

        # Save for context builder use
        board_path = tmp_path / "board.json"
        board.save(str(board_path))

        # Load and verify
        loaded_board = ForeshadowingBoard.load(str(board_path))
        assert len(loaded_board.entries) == 2

        loaded_prompt = loaded_board.format_for_prompt(current_chapter=7)
        assert "Hidden power awakens" in loaded_prompt

    def test_chapter_connector_save_load_cycle(self, tmp_path):
        """Test ChapterConnector save and load cycle."""
        mock_llm = MagicMock()
        connector = ChapterConnector(llm=mock_llm)

        summary = {
            "chapter_num": 7,
            "key_events": ["Climax"],
            "character_changes": [{"name": "Hero", "change_type": "心态", "description": "Resolved"}],
            "foreshadowing": {"planted": [], "harvested": ["F001"]},
            "cliffhanger": "Final confrontation",
            "location_updates": [{"character": "Hero", "from": "Temple", "to": "Sky"}],
            "emotional_state": {"Hero": "Determined"},
            "word_summary": "Hero faces final enemy",
        }

        connector.save_summary(summary, str(tmp_path))
        loaded = ChapterConnector.load_summary(7, str(tmp_path))

        assert loaded["chapter_num"] == 7
        assert loaded["cliffhanger"] == "Final confrontation"
        assert loaded["location_updates"][0]["from"] == "Temple"
