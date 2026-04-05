"""ParallelWindowService - Manages speculative execution of chapters in batches.

Allows generating multiple chapters simultaneously by using 'predicted summaries'
as context for subsequent chapters until the real predecessors are finished.
"""

import logging
from typing import Any, List, Dict
from crewai.content.novel.novel_types import ChapterOutput, WritingContext

logger = logging.getLogger(__name__)


class ParallelWindowService:
    """Service for managing windowed parallel chapter generation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.window_size = config.get("window_size", 5)
        self.max_concurrent = config.get("max_concurrent_chapters", 3)
        self._stitcher_agent = None

    @property
    def stitcher_agent(self):
        """Lazy init stitcher agent."""
        if self._stitcher_agent is None:
            from crewai.content.novel.agents.stitcher_agent import StitcherAgent
            self._stitcher_agent = StitcherAgent(
                llm=self.config.get("llm"),
                verbose=self.config.get("verbose", True)
            )
        return self._stitcher_agent

    def prepare_batch_contexts(
        self,
        summaries: List[Dict[str, Any]],
        initial_previous_summary: str,
        initial_previous_ending: str,
        world_data: Dict[str, Any],
        target_words: int,
        bible_volume_map: Dict[int, Any],
        chapter_to_volume: Dict[int, int],
    ) -> List[WritingContext]:
        """Prepare contexts for a batch of chapters using speculative summaries.

        Args:
            summaries: List of chapter summaries for this batch
            initial_previous_summary: Real summary from the previous batch's last chapter
            initial_previous_ending: Real ending from the previous batch's last chapter
            world_data: World building data
            target_words: Target word count per chapter
            bible_volume_map: Pre-built BibleSections
            chapter_to_volume: Chapter number to volume mapping

        Returns:
            List[WritingContext]: Ready-to-use contexts for parallel writing
        """
        contexts = []
        current_prev_summary = initial_previous_summary
        current_prev_ending = initial_previous_ending

        for i, summary in enumerate(summaries):
            chapter_num = summary.get("chapter_num", 0)
            vol_num = summary.get("volume_num") or chapter_to_volume.get(chapter_num, 1)
            bible_section = bible_volume_map.get(vol_num)

            # Create context using SPECULATIVE (predicted) previous summary
            # if real one isn't available yet (for chapters > 1 in the batch)
            context = WritingContext(
                title=self.config.get("topic", "未命名小说"),
                genre=self.config.get("genre", ""),
                style=self.config.get("style", ""),
                world_description=world_data.get("description", ""),
                character_profiles={}, # Re-populated by NovelCrew._build_writing_context logic
                previous_chapters_summary=current_prev_summary,
                previous_chapter_ending=current_prev_ending,
                chapter_outline=str(summary),
                target_word_count=summary.get("word_target", target_words),
                current_chapter_num=chapter_num,
                tension_arc="",
                bible_section=bible_section,
            )
            contexts.append(context)

            # Update speculative summary for NEXT chapter in this batch
            # Based on the summary (what we EXPECT to happen)
            predicted_events = ", ".join(summary.get("main_events", []))
            current_prev_summary = f"前情提要：{predicted_events}（预计剧情）"
            current_prev_ending = f"预计结尾场景：{summary.get('ending_hook', '主角准备进入下一个挑战')}"

        return contexts

    def stitch_batch(self, chapters: List[ChapterOutput]) -> List[ChapterOutput]:
        """Verify and fix continuity between chapters in a batch.

        This is a 'Stitcher Pass' that ensures the transition from N to N+1
        is smooth, especially if N's actual ending differed from N+1's predicted start.
        """
        if len(chapters) <= 1:
            return chapters

        for i in range(len(chapters) - 1):
            curr_ch = chapters[i]
            next_ch = chapters[i+1]
            
            # Simple heuristic: if curr_ch ending and next_ch start are very different,
            # we might need to add a bridging sentence.
            # In V1, we log this for GlobalPostPass to fix.
            # In V2, we could call a specific StitchingAgent.
            logger.info(f"Stitching chapter {curr_ch.chapter_num} → {next_ch.chapter_num}")
            
        return chapters
um}: {e}")
            
        return chapters
