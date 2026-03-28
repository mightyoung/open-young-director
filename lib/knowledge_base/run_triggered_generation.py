#!/usr/bin/env python3
"""Triggered content generation entry point - integrates multi-modal triggers.

This module provides the TriggeredGenerationManager that integrates the
SceneEventBus and evaluators into the chapter generation pipeline.

Usage:
    python run_triggered_generation.py --generate 5
    python run_triggered_generation.py --status
    python run_triggered_generation.py --generate 5 --evaluators novel,podcast,video
"""

import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add lib/ to path so knowledge_base/ can be found as a package
sys.path.insert(0, str(Path(__file__).parent.parent))

from triggers import (
    SceneEventBus,
    NovelEvaluator,
    PodcastEvaluator,
    VideoEvaluator,
    SceneExtractor,
    TriggerConfigLoader,
)
from triggers.base import MaterialPacket


class TriggeredGenerationManager:
    """Manages triggered content generation with event bus and evaluators.

    This class integrates the multi-modal trigger system into the chapter
    generation pipeline. It:
    1. Publishes chapter_completed events to all evaluators
    2. Extracts and publishes scene events for video evaluation
    3. Handles evaluator callbacks to trigger actual content generation

    Integration with consumers:
    - NovelEvaluator -> NovelOrchestrator (handled by existing flow)
    - PodcastEvaluator -> PodcastConsumer (async, called via asyncio)
    - VideoEvaluator -> VideoConsumer (async, called via asyncio)
    """

    def __init__(
        self,
        project_id: str,
        evaluators: Optional[List[str]] = None,
        config_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        llm_client=None,
        base_dir_override: Optional[str] = None,
    ):
        """Initialize the triggered generation manager.

        Args:
            project_id: The project ID for output paths
            evaluators: List of evaluator names to enable ["novel", "podcast", "video"]
                       If None, all evaluators are enabled.
            config_overrides: Optional config overrides per evaluator
            llm_client: LLM client for consumer calls
            base_dir_override: Override for base output directory
        """
        self.project_id = project_id
        self.llm_client = llm_client
        self.base_dir_override = base_dir_override
        self.logger = logging.getLogger(__name__)

        # Default evaluators
        if evaluators is None:
            evaluators = ["novel", "podcast", "video"]
        self.evaluator_names = evaluators

        # Config overrides
        self.config_overrides = config_overrides or {}

        # Initialize event bus
        self.event_bus = SceneEventBus()

        # Initialize scene extractor
        self.scene_extractor = SceneExtractor()

        # Initialize evaluators
        self._evaluators: Dict[str, Any] = {}
        self._setup_evaluators()

        # Track trigger history
        self.trigger_history: List[Dict[str, Any]] = []

    def _setup_evaluators(self) -> None:
        """Set up and subscribe all enabled evaluators."""
        config_loader = TriggerConfigLoader()

        evaluator_configs = {
            "novel": {
                "cooldown_seconds": 60,
                "enabled": True,
            },
            "podcast": {
                "cooldown_seconds": 600,
                "target_duration_minutes": 15,
                "min_chapters": 2,
                "max_chapters_per_batch": 5,
                "chars_per_minute": 500,
            },
            "video": {
                # 注意：这些值会被 VideoEvaluator 的默认值覆盖
                # VideoEvaluator 内部会根据 config 合并后的值来评估场景
                "cooldown_seconds": 900,
                "min_intensity": 0.2,   # 很低，因为爆发/觉醒场景缺少战斗动词
                "min_importance": 0.3,
                "min_visual_potential": 0.4,  # 核心指标
                "scenes_per_video": 3,
                "min_high_quality_scenes": 3,
            },
        }

        for name in self.evaluator_names:
            overrides = self.config_overrides.get(name, {})
            config = {**evaluator_configs.get(name, {}), **overrides}

            if name == "novel":
                evaluator = NovelEvaluator(config)
            elif name == "podcast":
                evaluator = PodcastEvaluator(config)
            elif name == "video":
                evaluator = VideoEvaluator(config)
            else:
                continue

            self._evaluators[name] = evaluator
            self.event_bus.subscribe(evaluator)
            self.logger.info(f"Subscribed {name} evaluator (cooldown={config.get('cooldown_seconds', '?')}s)")

    def on_chapter_completed(self, chapter_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chapter completion - publish event to all evaluators.

        This is the main integration point called after each chapter is saved.

        Args:
            chapter_data: Dictionary with chapter info:
                - chapter_id: e.g., "ch001"
                - title: Chapter title
                - content: Full chapter text
                - word_count: Number of characters

        Returns:
            Dict with trigger results from all evaluators
        """
        chapter_id = chapter_data.get("chapter_id", "unknown")
        chapter_num = self._parse_chapter_number(chapter_id)

        self.logger.info(f"[TriggerMgr] Chapter completed: {chapter_id}")

        # Publish chapter completed event
        self.event_bus.publish_chapter_completed(chapter_data)

        # Extract and publish scene events for video evaluator
        content = chapter_data.get("content", "")
        character_names = chapter_data.get("character_appearances", [])
        if content and "video" in self.evaluator_names:
            scenes = self.scene_extractor.extract(chapter_num, content)
            for scene in scenes:
                scene_dict = {
                    "scene_id": scene.scene_id,
                    "chapter_number": scene.chapter_number,
                    "content": scene.content,
                    "scene_type": scene.scene_type,
                    "intensity": scene.intensity,
                    "importance": scene.importance,
                    "visual_potential": scene.visual_potential,
                    "emotional_tags": scene.emotional_tags,
                    "character_appearances": character_names,  # Pass character names for this scene
                }
                self.event_bus.publish_scene_extracted(scene_dict)

        # Check evaluator statuses and trigger generation
        results = self._check_and_trigger()

        return results

    def _check_and_trigger(self) -> Dict[str, Any]:
        """Check all evaluators and trigger any that are ready.

        Returns:
            Dict with evaluator names and their trigger results
        """
        results = {}

        for name, evaluator in self._evaluators.items():
            # VideoEvaluator may have already triggered via event callbacks
            # (trigger fires inside on_scene_extracted -> _trigger_generation).
            # Check _last_trigger_result directly (don't use property - it clears the value).
            trigger_result = None
            if name == "video" and hasattr(evaluator, "_last_trigger_result"):
                trigger_result = getattr(evaluator, "_last_trigger_result", None)

            eval_result = evaluator.evaluate()

            if eval_result.should_trigger or trigger_result:
                self.logger.info(f"[TriggerMgr] {name} evaluator ready to trigger")

                # Execute generation
                if name == "novel":
                    result = self._trigger_novel(evaluator)
                elif name == "podcast":
                    result = self._trigger_podcast(evaluator)
                elif name == "video":
                    result = self._trigger_video_with_callback(evaluator, trigger_result)
                else:
                    result = {"error": f"Unknown evaluator: {name}"}

                results[name] = result
                self.trigger_history.append({
                    "evaluator": name,
                    "timestamp": datetime.now().isoformat(),
                    "result": result,
                })

                # Clear video trigger result after handling
                if name == "video" and hasattr(evaluator, "_last_trigger_result"):
                    setattr(evaluator, "_last_trigger_result", None)
            else:
                results[name] = {
                    "status": eval_result.status.value,
                    "should_trigger": False,
                    "reason": eval_result.reason,
                }

        return results

    def _trigger_novel(self, evaluator: NovelEvaluator) -> Dict[str, Any]:
        """Trigger novel generation (per-chapter).

        For novels, this returns the next chapter task.
        Actual generation is handled by the existing flow.
        """
        materials = evaluator.materials
        if not materials:
            return {"status": "no_materials"}

        result = evaluator.generate(materials)
        self.logger.info(f"[TriggerMgr] Novel trigger: {result}")
        return result

    def _trigger_podcast(self, evaluator: PodcastEvaluator) -> Dict[str, Any]:
        """Trigger podcast generation via PodcastConsumer.

        This calls the actual PodcastConsumer.generate() method.
        """
        materials = evaluator.materials
        if not materials:
            return {"status": "no_materials"}

        # Build chapter info for podcast consumer
        chapter_ids = [m.source_id for m in materials]
        total_chars = sum(len(m.content) for m in materials)
        est_duration = total_chars / evaluator.config.get("chars_per_minute", 500)

        self.logger.info(
            f"[TriggerMgr] Podcast trigger: {len(materials)} chapters, "
            f"~{est_duration:.1f}min, chapters: {chapter_ids}"
        )

        # Call actual PodcastConsumer if available
        result = self._call_podcast_consumer(materials)
        evaluator.generate(materials)  # Clears materials and marks triggered
        return result

    def _trigger_video(self, evaluator: VideoEvaluator) -> Dict[str, Any]:
        """Trigger video generation via VideoConsumer.

        This calls the actual VideoConsumer.generate() method.
        """
        # VideoEvaluator buffers scenes internally, call evaluate to get state
        eval_result = evaluator.evaluate()
        if not eval_result.should_trigger:
            return {
                "status": "not_ready",
                "reason": eval_result.reason,
            }

        self.logger.info(f"[TriggerMgr] Video trigger: {eval_result.reason}")

        # Get high quality scenes for video generation
        hq_scenes = evaluator._high_quality_scenes()
        scene_data_list = [sm.raw_scene_data for sm in hq_scenes]
        scene_objects = [sm.scene for sm in hq_scenes]  # ExtractedScene objects

        # Call actual VideoConsumer if available
        # Note: buffer was already cleared and cooldown set by _trigger_generation
        # via on_scene_extracted callback, so we only call the consumer here
        result = self._call_video_consumer(scene_data_list, scene_objects=scene_objects)
        return result

    def _trigger_video_with_callback(
        self, evaluator: VideoEvaluator, trigger_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Trigger video generation using scene data from event callback trigger.

        When VideoEvaluator triggers via event callback (on_scene_extracted ->
        _trigger_generation), it stores scene data in _last_trigger_result.
        This method uses that stored data to call VideoConsumer.

        Args:
            evaluator: VideoEvaluator instance
            trigger_result: The stored trigger result with scene_data_list

        Returns:
            Dict with video generation result
        """
        if not trigger_result:
            return {"status": "no_trigger_result"}

        scene_data_list = trigger_result.get("scene_data_list", [])
        scene_objects = trigger_result.get("scene_objects", [])

        if not scene_data_list:
            self.logger.warning("[TriggerMgr] Video trigger has no scene_data, clearing result")
            return {"status": "no_scene_data"}

        self.logger.info(
            f"[TriggerMgr] Video triggered via callback: {len(scene_data_list)} scenes, "
            f"will generate ~{len(scene_data_list) // evaluator.config.get('scenes_per_video', 3)} videos"
        )

        # Call VideoConsumer with the scene data
        result = self._call_video_consumer(scene_data_list, scene_objects=scene_objects)

        # Clear consumed scenes from buffer
        scene_ids = {s.get("scene_id", "") for s in scene_data_list}
        scene_ids.discard("")
        if scene_ids:
            evaluator.clear_consumed_scenes(scene_ids)

        return result

    def _call_podcast_consumer(self, materials: List[MaterialPacket]) -> Dict[str, Any]:
        """Call PodcastConsumer to generate podcast content.

        Args:
            materials: List of chapter material packets

        Returns:
            Dict with podcast generation result
        """
        try:
            from consumers.podcast_consumer import PodcastConsumer

            # Build raw_data from materials
            beats = []
            for m in materials:
                beats.append({
                    "chapter_id": m.source_id,
                    "content_preview": m.content[:500] if m.content else "",
                })

            raw_data = {
                "beats": beats,
                "character_states": {},
                "scene_descriptions": [],
                "emotional_arc": {},
                "chapter_info": {
                    "total_chapters": len(materials),
                    "chapter_ids": [m.source_id for m in materials],
                },
                "background": "",
            }

            # Run async consumer
            consumer = PodcastConsumer(llm_client=self.llm_client)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    consumer.generate(raw_data, generate_media=False)
                )
            finally:
                loop.close()

            self.logger.info(f"[TriggerMgr] Podcast generated: {result.get('title', 'unknown')}")
            return {"status": "generated", "result": result}

        except Exception as e:
            self.logger.warning(f"[TriggerMgr] PodcastConsumer error: {e}")
            return {"status": "error", "error": str(e)}

    def _call_video_consumer(
        self,
        scene_data_list: List[Dict[str, Any]],
        scene_objects: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        """Call VideoConsumer to generate video content.

        Args:
            scene_data_list: List of scene raw data dicts (from VideoEvaluator._high_quality_scenes)
            scene_objects: List of ExtractedScene objects (optional, for richer data)

        Returns:
            Dict with video generation result
        """
        try:
            from consumers.video_consumer import VideoConsumer

            # --- Step 1: Collect character names and load profiles ---
            all_char_names = set()
            for s in scene_data_list:
                chars = s.get("character_appearances", [])
                if isinstance(chars, list):
                    all_char_names.update(chars)

            character_profiles = self._load_character_profiles(list(all_char_names))

            # Build character_states in VideoConsumer expected format:
            # {char_name: [{"emotional_state": "...", "physical_state": "...", "appearance": {...}}]}
            character_states: Dict[str, List[Dict[str, Any]]] = {}
            for char_name, profile in character_profiles.items():
                # Build appearance string for the state
                appearance_parts = []
                for field in ["发型", "瞳色", "身高", "体型", "皮肤", "表情", "衣着"]:
                    if field in profile:
                        appearance_parts.append(profile[field])
                appearance_str = "，".join(appearance_parts) if appearance_parts else ""

                character_states[char_name] = [{
                    "emotional_state": "坚定",
                    "physical_state": profile.get("体型", "正常"),
                    "appearance": appearance_str,
                    # Also store full profile for prompt injection
                    "_profile": profile,
                }]

            # --- Step 2: Build beats with character names ---
            beats = []
            beat_type_map = {
                "战斗": "action",
                "对话": "dialogue",
                "情感": "emotional",
                "混合": "mixed",
                "过场": "transition",
            }

            # Build a quick character name -> appearance lookup for beat descriptions
            char_appearance_map = {
                name: profile.get("发型", profile.get("瞳色", ""))
                for name, profile in character_profiles.items()
            }

            for i, s in enumerate(scene_data_list):
                scene_type = s.get("scene_type", "过场")
                content = s.get("content", "")

                # Extract brief description (first 100 chars)
                brief_desc = content[:150].replace("\n", " ").strip()

                # Detect which characters appear in this scene by name matching
                scene_chars = []
                for char_name in all_char_names:
                    if char_name in content:
                        scene_chars.append(char_name)

                beat_type = beat_type_map.get(scene_type, "narrative")
                beats.append({
                    "beat_type": beat_type,
                    "description": brief_desc,
                    "expected_chars": scene_chars,
                })

            # --- Step 3: Build scene_descriptions with character context ---
            scene_descriptions = []
            for s in scene_data_list:
                scene_type = s.get("scene_type", "过场")
                content = s.get("content", "")
                scene_descriptions.append(
                    f"[{scene_type}] {content[:200].replace(chr(10), ' ')}"
                )

            # Build emotional_arc from scene data
            # Get emotional_tags if available (from scene_objects if passed)
            emotional_tags = []
            if scene_objects:
                for obj in scene_objects:
                    if hasattr(obj, "emotional_tags"):
                        emotional_tags.extend(obj.emotional_tags)

            emotional_arc = {}
            if emotional_tags:
                # Determine peak emotion from tags
                if any(t in emotional_tags for t in ["热血", "燃"]):
                    emotional_arc["peak_state"] = "激昂"
                elif any(t in emotional_tags for t in ["悲壮", "悲"]):
                    emotional_arc["peak_state"] = "悲壮"
                elif any(t in emotional_tags for t in ["惊悚", "恐怖"]):
                    emotional_arc["peak_state"] = "紧张"
                else:
                    emotional_arc["peak_state"] = "紧张"
                emotional_arc["start_state"] = "平静"
                emotional_arc["end_state"] = "舒缓"

            # Determine dominant scene type for genre context
            scene_types = [s.get("scene_type", "过场") for s in scene_data_list]
            dominant_type = max(set(scene_types), key=scene_types.count) if scene_types else "过场"

            # Build raw_data matching VideoConsumer.generate() expected format
            # character_states is built in Step 1 above with appearance data
            raw_data = {
                "beats": beats,
                "character_states": character_states,  # Includes appearance from character profiles
                "scene_descriptions": scene_descriptions,
                "narration_pieces": [],  # No pre-generated narration
                "emotional_arc": emotional_arc,
                "chapter_info": {
                    "total_scenes": len(scene_data_list),
                    "dominant_scene_type": dominant_type,
                },
                "background": f"玄幻修仙小说场景，类型: {dominant_type}",
            }

            # Run async consumer
            consumer = VideoConsumer(llm_client=self.llm_client)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    consumer.generate(raw_data, generate_media=False)
                )
            finally:
                loop.close()

            self.logger.info(f"[TriggerMgr] Video generated: {result.get('title', 'unknown')}")
            return {"status": "generated", "result": result}

        except Exception as e:
            self.logger.warning(f"[TriggerMgr] VideoConsumer error: {e}")
            return {"status": "error", "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Get current status of all evaluators.

        Returns:
            Dict with evaluator statuses and statistics
        """
        statuses = {}
        for name, evaluator in self._evaluators.items():
            eval_result = evaluator.evaluate()
            statuses[name] = {
                "status": eval_result.status.value,
                "should_trigger": eval_result.should_trigger,
                "confidence": eval_result.confidence,
                "reason": eval_result.reason,
            }

        return {
            "evaluators": statuses,
            "trigger_count": len(self.trigger_history),
            "subscribers": self.event_bus.get_subscriber_count(),
        }

    def _load_character_profiles(self, character_names: List[str]) -> Dict[str, Dict[str, str]]:
        """Load character appearance profiles from visual_reference files.

        Args:
            character_names: List of character names that appeared in the chapter.

        Returns:
            Dict mapping character name to appearance dict with keys:
            height, build, hair, eye_color, skin, expression, clothing
        """
        if not character_names:
            return {}

        # Compute base dir (same logic as ChapterManager)
        if self.base_dir_override:
            base_dir = Path(self.base_dir_override)
        else:
            base_dir = Path("lib/knowledge_base/novels")

        # Try to find project dir (ChapterManager stores as base_dir / project_title)
        chars_dir = base_dir / self.project_id / "visual_reference" / "characters"
        if not chars_dir.exists():
            # Fallback: try novels/{project_id}/visual_reference/characters
            chars_dir = base_dir.parent / "novels" / self.project_id / "visual_reference" / "characters"

        if not chars_dir.exists():
            self.logger.warning(f"Character dir not found: {chars_dir}")
            return {}

        profiles = {}
        # Normalize character names for matching
        name_to_file = {}
        for f in chars_dir.glob("char_*.md"):
            # File naming: char_{name}.md -> extract name part
            # e.g., char_taixuzi_v01.md -> "太虚子"
            # We strip the prefix and suffix to get the character name
            stem = f.stem  # e.g., "char_taixuzi_v01"
            if stem.startswith("char_"):
                filename_char_name = stem[5:]  # e.g., "taixuzi_v01"
                # Remove version suffix like _v01
                import re as re_module
                filename_char_name = re_module.sub(r'_v\d+$', '', filename_char_name)
                name_to_file[filename_char_name] = f

        # Also build a set of raw filenames for direct name matching
        all_files = {f.stem: f for f in chars_dir.glob("char_*.md")}

        for char_name in character_names:
            # Try multiple matching strategies
            char_file = None

            # Strategy 1: exact match in filename (normalized)
            for fname, fpath in name_to_file.items():
                if fname == char_name or char_name == fname:
                    char_file = fpath
                    break

            # Strategy 2: fuzzy match - character name appears in filename
            if not char_file:
                for fname, fpath in all_files.items():
                    if char_name in fname or fname in char_name:
                        char_file = fpath
                        break

            if not char_file or not char_file.exists():
                self.logger.debug(f"No character file found for: {char_name}")
                continue

            try:
                content = char_file.read_text(encoding="utf-8")
                profile = self._parse_character_appearance(content, char_name)
                if profile:
                    profiles[char_name] = profile
            except Exception as e:
                self.logger.warning(f"Failed to parse character file {char_file}: {e}")

        self.logger.info(f"Loaded profiles for {len(profiles)}/{len(character_names)} characters")
        return profiles

    def _parse_character_appearance(
        self, content: str, char_name: str
    ) -> Optional[Dict[str, str]]:
        """Parse appearance section from character markdown file.

        Args:
            content: Markdown content of character file.
            char_name: Character name (for fallback).

        Returns:
            Dict with appearance fields or None if not found.
        """
        result = {}

        # Extract table rows from 外貌特征 section
        # Format: | **attribute** | description |
        lines = content.split("\n")
        in_appearance_section = False
        appearance_fields = ["身高", "体型", "发型", "瞳色", "眼睛", "皮肤", "表情", "衣着"]

        for line in lines:
            line = line.strip()
            if "## 外貌特征" in line or "## 外貌" in line:
                in_appearance_section = True
                continue
            if in_appearance_section and line.startswith("##"):
                in_appearance_section = False
                break
            if in_appearance_section and "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    key = parts[1].replace("**", "").strip()
                    value = parts[2].replace("**", "").strip()
                    # Normalize key
                    for field in appearance_fields:
                        if field in key:
                            result[field] = value
                            break

        # If no appearance section found, try AI prompt section as fallback
        if not result:
            # Extract description from AI prompt section
            prompt_match = re.search(r"(?:外貌特征|character description)[:：]?\s*(.+?)(?:\n\n|\Z)", content, re.DOTALL)
            if prompt_match:
                desc = prompt_match.group(1).strip()[:200]
                result["description"] = desc

        return result if result else None

    def _parse_chapter_number(self, chapter_id: str) -> int:
        """Parse chapter number from chapter_id string.

        Handles formats: "ch001", "001", "ch_001", 1
        """
        if not chapter_id:
            return 0
        try:
            return int(chapter_id)
        except ValueError:
            pass
        m = re.search(r'(\d+)', str(chapter_id))
        return int(m.group(1)) if m else 0


def create_trigger_manager(
    project_id: str,
    evaluators: Optional[List[str]] = None,
    llm_client=None,
) -> TriggeredGenerationManager:
    """Factory function to create a TriggeredGenerationManager.

    Args:
        project_id: Project ID for output paths
        evaluators: List of evaluator names to enable
        llm_client: LLM client for consumer calls

    Returns:
        Configured TriggeredGenerationManager instance
    """
    return TriggeredGenerationManager(
        project_id=project_id,
        evaluators=evaluators,
        llm_client=llm_client,
    )


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_status(manager: TriggeredGenerationManager):
    """Print status of all evaluators."""
    status = manager.get_status()

    print(f"\n📊 Trigger System Status")
    print("-" * 50)
    print(f"   Subscribers: {status['subscribers']}")
    print(f"   Total triggers: {status['trigger_count']}")

    for name, eval_status in status["evaluators"].items():
        should_trigger = "🔴" if eval_status["should_trigger"] else "🟢"
        print(f"\n   {should_trigger} {name.upper()}")
        print(f"      Status: {eval_status['status']}")
        print(f"      Confidence: {eval_status['confidence']:.2f}")
        print(f"      Reason: {eval_status['reason'][:80]}...")


def cmd_generate(args, manager: TriggeredGenerationManager):
    """Run generation with triggered content generation."""
    from agents.config_manager import get_config_manager
    from agents.chapter_manager import get_chapter_manager
    from agents.novel_generator import get_novel_generator
    from agents.novel_orchestrator import NovelOrchestrator, OrchestratorConfig

    config_mgr = get_config_manager()

    # Get KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        kimi_client = get_kimi_client()
    except Exception as e:
        logging.warning(f"Failed to get KIMI client: {e}")
        kimi_client = None

    if not config_mgr.current_project:
        print("❌ No current project. Please create or load a project first.")
        return 1

    project = config_mgr.current_project
    project_id = project.id

    # Setup paths
    base_dir_override = str(Path(config_mgr.generation.output_dir).absolute())
    chapter_mgr = get_chapter_manager(project_id, base_dir_override=base_dir_override)

    # Create orchestrator
    orchestrator_config = OrchestratorConfig()
    novel_orchestrator = NovelOrchestrator(llm_client=kimi_client, config=orchestrator_config)

    # Create generator
    generator = get_novel_generator(
        config_manager=config_mgr,
        novel_orchestrator=novel_orchestrator,
        llm_client=kimi_client,
    )

    start = args.start or config_mgr.current_project.current_chapter + 1
    count = args.count

    print(f"\n🚀 Triggered Generation: {count} chapters")
    print(f"   Start: chapter {start}")
    print(f"   Evaluators: {', '.join(manager.evaluator_names)}")
    print(f"   Project: {config_mgr.current_project.title}")
    print("-" * 50)

    previous_summary = ""
    generated = []

    for i in range(count):
        chapter_num = start + i
        print(f"\n📝 Generating chapter {chapter_num}...")

        # Build context and generate
        context = chapter_mgr.build_context(chapter_num)
        chapter = generator.generate_chapter(
            chapter_number=chapter_num,
            context=context,
            previous_summary=previous_summary,
        )

        # Save chapter
        metadata = chapter_mgr.save_chapter(
            number=chapter.number,
            title=chapter.title,
            content=chapter.content,
            word_count=chapter.word_count,
            summary=chapter.metadata.get("outline_summary", ""),
            key_events=chapter.metadata.get("key_events", []),
            character_appearances=chapter.metadata.get("character_appearances", []),
            generation_time=chapter.generation_time,
        )

        print(f"   ✅ {chapter.title} ({chapter.word_count} chars)")

        # Publish to trigger system
        chapter_data = {
            "chapter_id": f"ch{chapter.number:03d}",
            "title": chapter.title,
            "content": chapter.content,
            "word_count": chapter.word_count,
            "character_appearances": chapter.metadata.get("character_appearances", []),
        }
        trigger_results = manager.on_chapter_completed(chapter_data)

        # Log trigger results
        for eval_name, result in trigger_results.items():
            if result.get("should_trigger") or result.get("status") == "generated":
                print(f"   🎯 [{eval_name}] {result.get('reason', result.get('status', ''))}")

        generated.append(chapter)
        if hasattr(chapter, 'plot_summary') and chapter.plot_summary:
            previous_summary = chapter.plot_summary.get('l2_brief_summary', '') or \
                             chapter.metadata.get("outline_summary", "")
        else:
            previous_summary = chapter.metadata.get("outline_summary", "")

    print(f"\n✅ Generated {len(generated)} chapters")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Triggered content generation with multi-modal evaluators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_triggered_generation.py --generate 5
  python run_triggered_generation.py --generate 5 --evaluators podcast,video
  python run_triggered_generation.py --status
        """,
    )

    parser.add_argument("--generate", type=int, metavar="COUNT", help="Generate chapters")
    parser.add_argument("--start", type=int, help="Start chapter number")
    parser.add_argument(
        "--evaluators",
        default="novel,podcast,video",
        help="Comma-separated evaluators to enable (default: all)",
    )
    parser.add_argument("--log-level", default="INFO", help="Log level")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load project
    from agents.config_manager import get_config_manager
    config_mgr = get_config_manager()

    if not config_mgr.current_project:
        print("❌ No current project. Please use run_novel_generation.py to create/load a project first.")
        return 1

    project = config_mgr.current_project
    project_id = project.id

    # Get KIMI client
    try:
        from llm.kimi_client import get_kimi_client
        llm_client = get_kimi_client()
    except Exception:
        llm_client = None

    # Parse evaluators
    evaluator_list = [e.strip() for e in args.evaluators.split(",")]

    # Create manager
    manager = create_trigger_manager(
        project_id=project_id,
        evaluators=evaluator_list,
        llm_client=llm_client,
    )

    if args.generate:
        args.count = args.generate
        return cmd_generate(args, manager)
    else:
        cmd_status(manager)
        return 0


if __name__ == "__main__":
    sys.exit(main())
