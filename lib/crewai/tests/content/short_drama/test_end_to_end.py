"""End-to-end integration tests for the short_drama pipeline.

These tests call the real LLM (or a mock that simulates it closely)
and are marked `slow` to exclude from regular test runs.

Run with: pytest -m slow
"""

import os

import pytest

from crewai.content.short_drama.adapters.novel_adapter import NovelToShortDramaAdapter
from crewai.content.short_drama.bible_builder import ShortDramaBibleBuilder


# ---------------------------------------------------------------------------
# Mark: slow – only run with `pytest -m slow`
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.slow


class TestShortDramaPipeline:
    """Integration tests for the full short_drama pipeline."""

    def test_pipeline_bible_to_outline_dict(self, mock_bible):
        """Bible → ShortDramaBible → outline dict pipeline (no LLM)."""
        builder = ShortDramaBibleBuilder(style="xianxia")
        sd_bible = builder.build(
            bible=mock_bible,
            episode_num=1,
            series_title="仙侠史诗",
            episode_context="上集结尾",
        )

        assert sd_bible.episode_num == 1
        assert len(sd_bible.relevant_characters) > 0
        assert sd_bible.tone in ("古风", "写实")

        d = sd_bible.to_dict()
        assert "relevant_characters" in d
        assert "world_rules_summary" in d


@pytest.mark.slow
class TestShortDramaFullLLMPipeline:
    """Full pipeline tests that call the real LLM API.

    These are skipped unless `-m slow` is passed.
    They require API keys to be set in the environment.
    """

    def test_full_pipeline_real_llm(self, test_novel_project):
        """Run bible → outline → shot decomposition with real LLM.

        Requires MINIMAX_API_KEY or similar environment variable.
        """
        api_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get(
            "DEEPSEEK_API_KEY"
        )
        if not api_key:
            pytest.skip("No LLM API key available")

        from crewai.llm import LLM

        if os.environ.get("MINIMAX_API_KEY"):
            llm = LLM(
                model=os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7-highspeed"),
                api_key=os.environ.get("MINIMAX_API_KEY"),
                base_url=os.environ.get("MINIMAX_BASE_URL"),
            )
        else:
            llm = LLM(model="deepseek/deepseek-chat", api_key=api_key)

        # Load novel project
        adapter = NovelToShortDramaAdapter(test_novel_project)
        bible = adapter.get_production_bible()

        if not bible:
            pytest.skip("Could not load production bible from test project")

        # Verify characters are proper objects (not dicts) before proceeding
        from crewai.content.novel.production_bible.bible_types import CharacterProfile

        sample_char = next(iter(bible.characters.values()))
        if not isinstance(sample_char, CharacterProfile):
            pytest.skip(
                "ProductionBible characters are dicts, not CharacterProfile objects "
                "(likely loaded from incompatible bible.json format)"
            )

        # Build ShortDramaBible
        builder = ShortDramaBibleBuilder(style="xianxia")
        sd_bible = builder.build(
            bible=bible,
            episode_num=1,
            series_title="测试剧",
            episode_context="测试承接",
        )

        # Generate outline
        from crewai.content.short_drama.crews.episode_outline_crew import (
            EpisodeOutlineCrew,
        )

        crew = EpisodeOutlineCrew(config={"llm": llm}, verbose=False)

        try:
            chapter_text = adapter.get_chapter_text(1)
        except Exception:
            pytest.skip("Could not load chapter text from test project")

        outline = crew.generate_outline(
            chapter_text=chapter_text,
            bible=sd_bible,
            episode_num=1,
            series_title="测试剧",
            episode_context="测试承接",
        )

        assert outline.episode_num == 1
        assert len(outline.scene_plan) > 0

        # Decompose to shots
        from crewai.content.short_drama.crews.shot_crew import ShotCrew

        shot_crew = ShotCrew(config={"llm": llm}, verbose=False)
        episode = shot_crew.decompose_episode(outline, sd_bible)

        assert episode.episode_num == 1
        assert len(episode.get_all_shots()) > 0
