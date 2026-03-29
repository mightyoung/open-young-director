"""Integration tests for ScriptCrew and SceneCrew."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import List

from crewai.content.script.crews.script_crew import ScriptCrew
from crewai.content.script.crews.scene_crew import SceneCrew
from crewai.content.script.script_types import (
    BeatSheet,
    Beat,
    SceneOutput,
    SceneDialogue,
    DialogueBlock,
    ScriptOutput,
    ScriptMetadata,
)


class TestScriptCrew:
    """Test ScriptCrew integration with CinematographyAgent and VisualMotifTracker."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.call = MagicMock(return_value="Mock LLM response")
        llm.call_async = AsyncMock(return_value="Mock LLM async response")
        return llm

    @pytest.fixture
    def script_config(self, mock_llm):
        """Create a minimal script configuration for testing."""
        return {
            "title": "Test Script",
            "logline": "A test story",
            "structure": {
                "acts": [
                    {
                        "name": "Act I",
                        "beats": [
                            {"number": 1, "name": "Opening", "description": "Setup"},
                        ]
                    }
                ]
            },
            "target_runtime": 120,
            "format": "film",
            "genre": "drama",
            "target_audience": "general",
            "rating": "PG-13",
            "default_location": "咖啡馆",
            "default_time": "日",
            "characters": ["角色A", "角色B"],
            "character_backgrounds": {
                "角色A": "背景A",
                "角色B": "背景B",
            },
            "visual_motifs": ["红色", "窗户"],
            "llm": mock_llm,
        }

    def test_script_crew_initialization(self, script_config):
        """Test ScriptCrew can be initialized with config."""
        crew = ScriptCrew(config=script_config)
        assert crew.config == script_config
        assert crew.verbose is True

    def test_script_crew_initialization_verbose_false(self, script_config):
        """Test ScriptCrew can be initialized with verbose=False."""
        crew = ScriptCrew(config=script_config, verbose=False)
        assert crew.verbose is False

    def test_script_crew_kickoff_with_mocks(self, script_config):
        """Test ScriptCrew.kickoff() completes workflow with mocks."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[
                DialogueBlock(
                    speaker="角色A",
                    content="你好。",
                    emotion="平静",
                    subtext="试探性问候",
                )
            ],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        assert result is not None
                        assert isinstance(result.content, ScriptOutput)
                        assert result.tasks_completed is not None
                        assert len(result.tasks_completed) > 0

    def test_script_crew_generates_beat_sheets(self, script_config):
        """Test ScriptCrew generates beat sheets via BeatSheetAgent."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        crew.kickoff()

                        mock_beat_instance.generate_beat_sheet.assert_called_once()

    def test_script_crew_calls_scene_crew(self, script_config):
        """Test ScriptCrew calls SceneCrew for each beat."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        crew.kickoff()

                        assert mock_scene_instance.kickoff.called

    def test_script_crew_calls_dialogue_crew(self, script_config):
        """Test ScriptCrew calls DialogueCrew for dialogues."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        crew.kickoff()

                        assert mock_dialogue_instance.kickoff.called

    def test_script_crew_records_visual_motifs(self, script_config):
        """Test ScriptCrew uses VisualMotifTracker to record motifs."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        crew.kickoff()

                        mock_tracker_instance.define_motifs.assert_called_once_with(["红色", "窗户"])
                        assert mock_tracker_instance.record_occurrence.called

    def test_script_crew_generates_motif_report(self, script_config):
        """Test ScriptCrew calls generate_motif_report() at end of workflow."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        mock_tracker_instance.generate_motif_report.assert_called_once()

    def test_script_crew_returns_correct_output_structure(self, script_config):
        """Test ScriptCrew returns correct output structure."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        assert hasattr(result, "content")
                        assert hasattr(result, "tasks_completed")
                        assert hasattr(result, "execution_time")
                        assert hasattr(result, "metadata")
                        assert isinstance(result.content, ScriptOutput)

    def test_script_crew_motif_report_in_metadata(self, script_config):
        """Test ScriptCrew includes motif_report in metadata."""
        mock_beat_sheets = [
            BeatSheet(
                act="Act I",
                beats=[
                    Beat(
                        number=1,
                        name="Opening",
                        description="Setup scene",
                        scene_purpose="Introduce protagonist",
                        turning_point=False,
                    )
                ],
                total_runtime_estimate=10,
            )
        ]

        scene_output = SceneOutput(
            scene_number=1,
            beat_number=1,
            location="咖啡馆",
            time_of_day="日",
            characters=["角色A", "角色B"],
            action="两人坐在咖啡馆里交谈",
            dialogue_count=0,
            estimated_duration=5,
            visual_notes="",
        )

        dialogue_output = SceneDialogue(
            scene_number=1,
            location="咖啡馆",
            time_of_day="日",
            dialogues=[],
        )

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew") as mock_scene:
                mock_scene_instance = MagicMock()
                mock_scene_instance.kickoff = MagicMock(return_value=MagicMock(content=scene_output))
                mock_scene.return_value = mock_scene_instance

                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew") as mock_dialogue:
                    mock_dialogue_instance = MagicMock()
                    mock_dialogue_instance.kickoff = MagicMock(return_value=MagicMock(content=dialogue_output))
                    mock_dialogue.return_value = mock_dialogue_instance

                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock motif report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        assert "motif_report" in result.metadata
                        assert result.metadata["motif_report"] == "Mock motif report"


class TestSceneCrew:
    """Test SceneCrew with CinematographyAgent integration."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.call = MagicMock(return_value="Mock scene description")
        llm.call_async = AsyncMock(return_value="Mock scene async description")
        return llm

    @pytest.fixture
    def scene_config(self, mock_llm):
        """Create a minimal scene configuration."""
        return {
            "scene_number": 1,
            "beat": {
                "number": 1,
                "name": "Opening",
                "description": "Setup scene",
                "scene_purpose": "Introduce protagonist",
                "turning_point": False,
            },
            "location": "咖啡馆",
            "time_of_day": "日",
            "characters": ["角色A", "角色B"],
            "estimated_duration": 5,
            "llm": mock_llm,
        }

    def test_scene_crew_initialization(self, scene_config):
        """Test SceneCrew can be initialized."""
        crew = SceneCrew(config=scene_config)
        assert crew.config == scene_config

    def test_scene_crew_kickoff_returns_scene_output(self, scene_config):
        """Test SceneCrew.kickoff() returns SceneOutput."""
        crew = SceneCrew(config=scene_config)

        with patch("crewai.content.script.crews.scene_crew.CinematographyAgent") as mock_cine:
            mock_cine_instance = MagicMock()
            mock_cine_instance.generate_visual_guide = MagicMock(return_value={
                "camera_angle": "平视",
                "lens": "中焦",
                "movement": "固定",
                "lighting": "自然光",
                "blocking": "面对面",
                "visual_notes": "咖啡馆场景",
            })
            mock_cine.return_value = mock_cine_instance

            with patch.object(crew, "_create_workflow") as mock_workflow:
                mock_crew = MagicMock()
                mock_crew.kickoff = MagicMock(return_value=MagicMock(
                    string_output="咖啡馆场景描写..."
                ))
                mock_workflow.return_value = mock_crew

                result = crew.kickoff()

                assert result is not None

    def test_scene_crew_uses_cinematography_agent(self, scene_config):
        """Test SceneCrew uses CinematographyAgent for visual guidance."""
        crew = SceneCrew(config=scene_config)

        with patch("crewai.content.script.crews.scene_crew.CinematographyAgent") as mock_cine:
            mock_cine_instance = MagicMock()
            mock_cine_instance.generate_visual_guide = MagicMock(return_value={
                "camera_angle": "平视",
                "lens": "中焦",
                "movement": "固定",
                "lighting": "自然光",
                "blocking": "面对面",
                "visual_notes": "咖啡馆场景",
            })
            mock_cine.return_value = mock_cine_instance

            scene = {
                "location": scene_config["location"],
                "action": scene_config["beat"]["description"],
                "characters": scene_config["characters"],
            }

            visual_guide = crew._get_cinematography_guide(scene)

            mock_cine_instance.generate_visual_guide.assert_called_once()

    def test_scene_crew_incorporates_visual_guide_in_output(self, scene_config):
        """Test SceneCrew incorporates visual guide in scene output."""
        crew = SceneCrew(config=scene_config)

        with patch("crewai.content.script.crews.scene_crew.CinematographyAgent") as mock_cine:
            mock_cine_instance = MagicMock()
            mock_cine_instance.generate_visual_guide = MagicMock(return_value={
                "camera_angle": "平视",
                "lens": "中焦",
                "movement": "固定",
                "lighting": "自然光",
                "blocking": "面对面",
                "visual_notes": "咖啡馆场景",
            })
            mock_cine.return_value = mock_cine_instance

            with patch.object(crew, "_create_workflow") as mock_workflow:
                mock_crew = MagicMock()
                mock_result = MagicMock()
                mock_result.string_output = "咖啡馆场景描写..."
                mock_crew.kickoff = MagicMock(return_value=mock_result)
                mock_workflow.return_value = mock_crew

                result = crew.kickoff()

                assert result.content is not None


class TestCinematographyAgentIntegration:
    """Test CinematographyAgent integration into SceneCrew workflow."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock()
        llm.call = MagicMock(return_value="Mock visual guide")
        return llm

    def test_cinematography_agent_generates_visual_guide(self, mock_llm):
        """Test CinematographyAgent.generate_visual_guide() works."""
        from crewai.content.script.agents.cinematography_agent import CinematographyAgent

        with patch.object(CinematographyAgent, "__init__", lambda self, **kwargs: None):
            agent = CinematographyAgent()
            agent.agent = MagicMock()
            agent.agent.run = MagicMock(return_value="""摄影机角度: 平视
镜头选择: 中焦
镜头运动: 固定
光影设计: 自然光
演员走位: 面对面""")

            scene = {
                "location": "咖啡馆",
                "action": "两人对话",
                "characters": ["角色A", "角色B"],
            }

            result = agent.generate_visual_guide(scene)

            assert "camera_angle" in result
            assert agent.agent.run.called

    def test_scene_crew_passes_visual_guide_to_output(self, mock_llm):
        """Test SceneCrew passes visual guide to output."""
        from crewai.content.script.crews.scene_crew import SceneCrew

        scene_config = {
            "scene_number": 1,
            "beat": {
                "number": 1,
                "name": "Opening",
                "description": "Setup",
                "scene_purpose": "Introduce",
                "turning_point": False,
            },
            "location": "咖啡馆",
            "time_of_day": "日",
            "characters": ["角色A"],
            "estimated_duration": 5,
            "llm": mock_llm,
        }

        crew = SceneCrew(config=scene_config)

        with patch("crewai.content.script.crews.scene_crew.CinematographyAgent") as mock_cinematography:
            mock_agent_instance = MagicMock()
            mock_agent_instance.generate_visual_guide = MagicMock(return_value={
                "camera_angle": "平视",
                "lens": "中焦",
                "movement": "固定",
                "lighting": "自然光",
                "blocking": "面对面",
                "visual_notes": "咖啡馆场景",
            })
            mock_cinematography.return_value = mock_agent_instance

            with patch.object(crew, "_create_workflow") as mock_workflow:
                mock_crew_instance = MagicMock()
                mock_crew_instance.kickoff = MagicMock(return_value=MagicMock(
                    string_output="咖啡馆场景..."
                ))
                mock_workflow.return_value = mock_crew_instance

                result = crew.kickoff()

                assert mock_agent_instance.generate_visual_guide.called


class TestVisualMotifTrackerIntegration:
    """Test VisualMotifTracker.generate_motif_report() integration."""

    def test_generate_motif_report_called_at_end_of_workflow(self):
        """Test generate_motif_report() is called at end of ScriptCrew workflow."""
        script_config = {
            "title": "Test Script",
            "logline": "A test story",
            "structure": {"acts": []},
            "target_runtime": 120,
            "format": "film",
            "visual_motifs": ["红色", "窗户"],
            "llm": MagicMock(),
        }

        mock_beat_sheets = []

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew"):
                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew"):
                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value="Mock report")
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        mock_tracker_instance.generate_motif_report.assert_called_once()

    def test_motif_report_included_in_final_output(self):
        """Test motif report is included in final ScriptOutput or metadata."""
        script_config = {
            "title": "Test Script",
            "logline": "A test story",
            "structure": {"acts": []},
            "target_runtime": 120,
            "format": "film",
            "visual_motifs": ["红色"],
            "llm": MagicMock(),
        }

        mock_report = "视觉主题追踪报告\n主题: 红色\n出现次数: 3"
        mock_beat_sheets = []

        with patch("crewai.content.script.crews.script_crew.BeatSheetAgent") as mock_beat:
            mock_beat_instance = MagicMock()
            mock_beat_instance.generate_beat_sheet = MagicMock(return_value=mock_beat_sheets)
            mock_beat.return_value = mock_beat_instance

            with patch("crewai.content.script.crews.scene_crew.SceneCrew"):
                with patch("crewai.content.script.crews.dialogue_crew.DialogueCrew"):
                    with patch("crewai.content.script.crews.script_crew.VisualMotifTracker") as mock_tracker:
                        mock_tracker_instance = MagicMock()
                        mock_tracker_instance.define_motifs = MagicMock()
                        mock_tracker_instance.record_occurrence = MagicMock()
                        mock_tracker_instance.generate_motif_report = MagicMock(return_value=mock_report)
                        mock_tracker.return_value = mock_tracker_instance

                        crew = ScriptCrew(config=script_config)
                        result = crew.kickoff()

                        assert mock_tracker_instance.generate_motif_report.called
