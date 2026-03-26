"""写作Crew"""

from typing import TYPE_CHECKING, Any

from crewai.content.base import BaseContentCrew
from crewai.content.novel.agents.draft_agent import DraftAgent
from crewai.content.novel.novel_types import WritingContext


if TYPE_CHECKING:
    from crewai.content.novel.production_bible.bible_types import BibleSection


class WritingCrew(BaseContentCrew):
    """写作Crew

    负责撰写小说章节初稿：
    - 根据章节大纲撰写内容
    - 使用写作上下文保持一致性
    - 生成符合风格要求的文本

    使用示例:
        crew = WritingCrew(config=ContentConfig(...))
        result = crew.write_chapter(context, outline)
    """

    def __init__(self, config: Any, entity_memory=None, continuity_tracker=None, verbose: bool = True):
        """Initialize WritingCrew.

        Args:
            config: Configuration for the crew
            entity_memory: Optional EntityMemory instance for entity tracking
            continuity_tracker: Optional ContinuityTracker instance for continuity tracking
            verbose: Whether to enable verbose output
        """
        super().__init__(config, verbose=verbose)
        self.entity_memory = entity_memory
        self.continuity_tracker = continuity_tracker

    def _create_agents(self) -> dict[str, Any]:
        """创建Agents"""
        return {
            "draft_writer": DraftAgent(llm=self.config.get("llm")),
        }

    def _create_tasks(self) -> dict[str, Any]:
        """创建Tasks - 动态创建，根据章节数决定"""
        return {}

    def _create_workflow(self) -> Any:
        """创建Crew工作流"""
        from crewai import Crew

        return Crew(
            agents=[self.agents["draft_writer"].agent],
            tasks=[],
            verbose=self.verbose,
        )

    def write_chapter(
        self,
        context: WritingContext,
        chapter_outline: dict,
        bible_section: "BibleSection | None" = None,
    ) -> str:
        """撰写单个章节（完整PostPass流水线）

        Args:
            context: 写作上下文
            chapter_outline: 章节大纲
            bible_section: 可选的 BibleSection，用于约束本章写作与 Production Bible 一致

        Returns:
            str: 润色后的章节内容
        """
        # 1. Generate draft (with optional bible constraint)
        draft = self.agents["draft_writer"].write(context, chapter_outline, bible_section)

        # 2. Build review context
        review_context = self._build_review_context(context, chapter_outline)

        # 3. Run Per-Chapter PostPass
        critique_result, revised_draft, polished_draft = self._run_postpass(draft, review_context)

        # 4. Update entity memory with polished content
        if self.entity_memory is not None:
            self._update_memory_from_draft(polished_draft, context)

        return polished_draft

    def _build_review_context(self, context: WritingContext, chapter_outline: dict):
        """Build ReviewContext for per-chapter PostPass."""
        from crewai.content.review.review_context import ReviewContext

        chapter_title = chapter_outline.get("title", f"第{context.current_chapter_num}章")
        main_events = chapter_outline.get("main_events", [])
        tension_level = chapter_outline.get("tension_level", "")
        climax = chapter_outline.get("climax", "")

        # 构建写作目标
        writing_goals = f"本章标题：{chapter_title}"
        if main_events:
            writing_goals += "\n本章主要事件：\n" + "\n".join(f"- {event}" for event in main_events)
        if climax and climax != tension_level:
            writing_goals += f"\n高潮点：{climax}"

        # 构建节奏笔记
        pacing_notes = f"张力级别：{tension_level}" if tension_level else ""

        return ReviewContext(
            title=context.title,
            genre=context.genre,
            style_guide=context.style,
            previous_chapters_summary=context.previous_chapters_summary,
            chapter_number=context.current_chapter_num,
            word_count_target=context.target_word_count,
            writing_goals=writing_goals,
            pacing_notes=pacing_notes,
        )

    def _run_postpass(self, draft: str, review_context):
        """Run critique→revision→polish pipeline and return all outputs."""
        from crewai.content.review.review_pipeline import ReviewPipeline

        pipeline = ReviewPipeline(llm=self.config.get("llm"))
        result = pipeline.run(draft, review_context)
        return (
            result.get("critique", ""),
            result.get("revised_draft", draft),
            result.get("polished_draft", draft),
        )

    def _update_memory_from_draft(self, draft: str, context: WritingContext) -> None:
        """Update entity memory with characters mentioned in the draft.

        Uses known character names from context.character_profiles as primary source,
        with simple fuzzy matching as a fallback for unnamed characters.

        Args:
            draft: The chapter draft text
            context: Writing context containing known character profiles
        """
        chapter_num = context.current_chapter_num
        seen: set[str] = set()

        # Primary: register all known characters from context
        known_chars = context.character_profiles or {}
        for name in known_chars.keys():
            if name in draft and name not in seen:
                self._upsert_character(name, chapter_num)
                seen.add(name)

        # Fallback: fuzzy match for unnamed characters (2-char Chinese name-like sequences)
        import re
        two_char_pat = re.compile(r'[\u4e00-\u9fa5]{2}')
        for m in two_char_pat.finditer(draft):
            name = m.group()
            if name not in seen and not self._is_common_word(name):
                # Only add if it looks like a real name (not already known char + not in seen)
                self._upsert_character(name, chapter_num)
                seen.add(name)

    def _upsert_character(self, name: str, chapter_num: int) -> None:
        """Add or update a character in entity memory."""
        existing = self.entity_memory.get_entity(name)
        if existing is None:
            from crewai.content.memory.memory_types import Entity
            entity = Entity(
                id=name,
                name=name,
                type="character",
                description=f"在第{chapter_num}章出现",
            )
            self.entity_memory.add_entity(entity)
        self.entity_memory.update_entity_property(name, "last_appearance_chapter", str(chapter_num))

    def _is_common_word(self, word: str) -> bool:
        """Check if a word is a common non-entity word."""
        common_words = {
            "时候", "地方", "这里", "那里", "什么", "怎么",
            "为何", "如何", "因为", "所以", "但是", "然而",
            "于是", "之后", "之前", "左右", "上下", "高低",
            "大小", "长短", "好坏", "多少", "远近", "快慢",
            "今天", "明天", "昨天", "现在", "刚才", "马上",
            "非常", "特别", "极其", "十分", "相当",
            "突然", "渐渐", "慢慢", "逐步", "逐渐",
            "一定", "必须", "应该", "可以", "可能",
        }
        return word in common_words

    def write_chapters(
        self,
        contexts: list[WritingContext],
        outlines: list[dict],
    ) -> list[str]:
        """批量撰写章节

        Args:
            contexts: 写作上下文列表
            outlines: 章节大纲列表

        Returns:
            list[str]: 章节初稿列表
        """
        results = []
        for context, outline in zip(contexts, outlines):
            chapter_draft = self.write_chapter(context, outline)
            results.append(chapter_draft)
        return results

    def write_chapter_group(
        self,
        contexts: list[WritingContext],
        outlines: list[dict],
        max_concurrent: int = 3,
    ) -> list[str]:
        """撰写一组章节（支持并行）

        使用 asyncio.Semaphore 控制并发数，在 IO 等待 LLM 响应时
        让出执行权给其他协程，提升吞吐量。

        改进点：
        - return_exceptions=True：单个失败不影响其他章节
        - 专用线程池：避免耗尽默认线程池
        - 更好的循环检测：使用 get_running_loop()

        Args:
            contexts: 写作上下文列表
            outlines: 章节大纲列表
            max_concurrent: 最大并发数（默认3）

        Returns:
            list[str]: 章节初稿列表（按输入顺序排列）
        """
        import asyncio
        import concurrent.futures
        import logging

        logger = logging.getLogger(__name__)

        if len(contexts) <= 1:
            return [self.write_chapter(c, o) for c, o in zip(contexts, outlines)]

        # Dedicated thread pool to avoid exhausting defaults
        _thread_pool: concurrent.futures.ThreadPoolExecutor | None = None

        def _get_thread_pool() -> concurrent.futures.ThreadPoolExecutor:
            nonlocal _thread_pool
            if _thread_pool is None:
                _thread_pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_concurrent,
                    thread_name_prefix="writing_crew_",
                )
            return _thread_pool

        async def write_one(
            idx: int,
            context: WritingContext,
            outline: dict,
        ) -> tuple[int, str | Exception]:
            nonlocal _thread_pool
            pool = _get_thread_pool()
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    pool, self.write_chapter, context, outline
                )
                return (idx, result)
            except Exception as e:
                logger.warning(f"Chapter {idx} failed: {e}")
                return (idx, e)

        async def gather_all() -> list[tuple[int, str | Exception]]:
            tasks = [
                write_one(i, c, o)
                for i, (c, o) in enumerate(zip(contexts, outlines))
            ]
            # return_exceptions=True: collect all results, don't abort on first failure
            return await asyncio.gather(*tasks, return_exceptions=True)

        try:
            # Detect if we're already in an async context
            try:
                asyncio.get_running_loop()
                # Already in async context: run in a separate thread to avoid nesting
                pool = _get_thread_pool()
                future = concurrent.futures.Future()

                def run_gather():
                    try:
                        result = asyncio.run(gather_all())
                        future.set_result(result)
                    except Exception as e:
                        future.set_exception(e)

                pool.submit(run_gather)
                results_with_idx: list[tuple[int, str | Exception]] = future.result()
            except RuntimeError:
                # No running loop — safe to use run_until_complete
                results_with_idx = asyncio.run(gather_all())
        except Exception as e:
            logger.warning(f"Parallel writing failed, falling back to sequential: {e}")
            # Fallback: sequential on any error
            return [self.write_chapter(c, o) for c, o in zip(contexts, outlines)]
        finally:
            # Shutdown the dedicated thread pool
            if _thread_pool is not None:
                _thread_pool.shutdown(wait=False)
                _thread_pool = None

        # Sort by original index
        results_with_idx.sort(key=lambda x: x[0])

        # Unpack results, log errors for failed ones
        results: list[str] = []
        for idx, result in results_with_idx:
            if isinstance(result, Exception):
                # Return empty draft on failure (allows batch to continue)
                logger.warning(f"Chapter {idx} failed with exception: {result}")
                results.append("")
            else:
                results.append(result)

        return results

    def write_chapter_from_artifact(
        self,
        context: WritingContext,
        chapter_outline: dict,
        resume_from_phase: str = 'draft',
        artifacts: dict[str, Any] | None = None,
    ) -> str:
        """Write chapter, optionally resuming from a saved artifact.

        Args:
            context: Writing context
            chapter_outline: Chapter outline
            resume_from_phase: 'draft', 'critique', 'revised', or 'polished'
            artifacts: Optional dict with saved artifacts {phase: content}

        Returns:
            Chapter content
        """
        if artifacts and resume_from_phase in artifacts:
            # Resume from saved artifact
            if resume_from_phase == 'polished':
                return artifacts['polished']
            if resume_from_phase == 'revised':
                # Run polish only
                from crewai.content.review.review_pipeline import ReviewPipeline
                pipeline = ReviewPipeline(llm=self.config.get("llm"))
                result = pipeline.run(artifacts['revised'], context)
                return result['polished_draft']
            # For draft or critique, fall through to normal flow

        return self.write_chapter(context, chapter_outline)
