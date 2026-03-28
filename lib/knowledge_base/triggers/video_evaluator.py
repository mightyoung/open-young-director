"""Video content evaluator with scene-based triggering.

This module implements the VideoEvaluator which only triggers video generation
for high-quality scenes (high intensity, importance, visual potential).
It collects scenes from chapters and triggers generation when sufficient
high-quality scenes have accumulated.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base import (
    ContentEvaluator,
    EvaluationResult,
    MaterialPacket,
    TriggerStatus,
)
from .scene_extractor import ExtractedScene, SceneExtractor


@dataclass
class VideoSceneMaterial:
    """A video-relevant material extracted from a chapter."""
    scene: ExtractedScene
    raw_scene_data: Dict[str, Any]


class VideoEvaluator(ContentEvaluator):
    """Video evaluator - triggers on scene quality thresholds.

    Unlike PodcastEvaluator (time-based) or NovelEvaluator (per-chapter),
    VideoEvaluator uses scene-level quality scoring:

    - Collects scenes extracted from each chapter via on_scene_extracted()
    - Maintains a scene buffer with quality scores
    - Triggers when high-quality scenes reach batch threshold
    - Each trigger generates N videos from the best-scored scenes

    Configuration:
        min_intensity: Minimum intensity score (default 0.7)
        min_importance: Minimum importance score (default 0.6)
        min_visual_potential: Minimum visual potential score (default 0.6)
        scenes_per_video: Number of scenes per generated video (default 3)
        cooldown_seconds: Cooldown after trigger (default 900 = 15min)
    """

    def __init__(self, config: Dict[str, Any]):
        default_config = {
            # 视频触发阈值：提高标准，确保只有真正精彩的场景才生成视频
            # 只有宏大、震撼、视觉效果强的场景才值得生成视频
            "min_intensity": 0.3,       # 战斗强度阈值 - 提高到0.3
            "min_importance": 0.4,      # 叙事重要性阈值 - 提高到0.4
            "min_visual_potential": 0.55, # 视觉潜力阈值 - 提高到0.55，确保画面震撼
            "scenes_per_video": 3,       # 每个视频包含的场景数
            "cooldown_seconds": 900,      # 15分钟冷却 - 视频生成成本高
            "min_high_quality_scenes": 2,  # 触发前最少高质量场景数 - 降低到2
        }
        # Merge defaults with provided config
        merged = {**default_config, **config}
        super().__init__(merged)

        self._scene_extractor = SceneExtractor()
        self._scene_buffer: List[VideoSceneMaterial] = []
        self._logger = logging.getLogger(__name__)
        # Track last trigger result so manager can report it after buffer is cleared
        self._last_trigger_result: Optional[Dict[str, Any]] = None

    def on_chapter_completed(self, chapter_data: Dict[str, Any]) -> None:
        """Handle chapter completion - extract scenes and score them."""
        if not self._can_trigger():
            self._logger.debug(
                f"VideoEval in cooldown, ignoring chapter: {chapter_data.get('chapter_id')}"
            )
            return

        chapter_id = chapter_data.get("chapter_id", "0")
        # Parse chapter number from string (e.g., "ch001" -> 1, "1" -> 1)
        import re
        m = re.search(r'(\d+)', str(chapter_id))
        chapter_num = int(m.group(1)) if m else 0
        content = chapter_data.get("content", "")

        if not content:
            return

        # Extract scenes from chapter
        scenes = self._scene_extractor.extract(chapter_num, content)
        self._logger.info(
            f"Extracted {len(scenes)} scenes from ch{chapter_num:03d}"
        )

        for scene in scenes:
            scene_mat = VideoSceneMaterial(
                scene=scene,
                raw_scene_data={
                    "scene_id": scene.scene_id,
                    "chapter_number": scene.chapter_number,
                    "content": scene.content,
                }
            )
            self._scene_buffer.append(scene_mat)
            self._logger.debug(
                f"  scene {scene.scene_id}: type={scene.scene_type}, "
                f"intensity={scene.intensity:.2f}, importance={scene.importance:.2f}, "
                f"visual={scene.visual_potential:.2f}"
            )

        # Check trigger after collecting
        self._check_trigger()

    def on_scene_extracted(self, scene_data: Dict[str, Any]) -> None:
        """Handle pre-extracted scene data (e.g., from LLM scene analysis)."""
        if not self._can_trigger():
            return

        # If scene already has scoring data, use it directly
        if all(k in scene_data for k in ("intensity", "importance", "visual_potential")):
            scene = ExtractedScene(
                scene_id=scene_data.get("scene_id", "unknown"),
                chapter_number=scene_data.get("chapter_number", 0),
                content=scene_data.get("content", ""),
                scene_type=scene_data.get("scene_type", "过场"),
                intensity=float(scene_data.get("intensity", 0)),
                importance=float(scene_data.get("importance", 0)),
                visual_potential=float(scene_data.get("visual_potential", 0)),
                emotional_tags=scene_data.get("emotional_tags", []),
            )
            self._scene_buffer.append(VideoSceneMaterial(
                scene=scene,
                raw_scene_data=scene_data,
            ))
            self._check_trigger()

    def _high_quality_scenes(self) -> List[VideoSceneMaterial]:
        """Return scenes meeting quality thresholds for video generation.

        Quality logic (OR-based, any of these pass):
        1. visual_potential >= min_visual_potential (primary - visually stunning scenes)
        2. intensity >= min_intensity AND importance >= min_importance (action + narrative)
        3. intensity >= 0.5 (pure high-intensity action)
        4. importance >= 0.5 (highly important narrative moments)

        Minimum bar: importance >= 0.2 (has some narrative relevance).
        """
        min_vis = self.config["min_visual_potential"]
        min_int = self.config["min_intensity"]
        min_imp = self.config["min_importance"]

        result = []
        for sm in self._scene_buffer:
            scene = sm.scene
            # Minimum bar: scene has some narrative relevance
            if scene.importance < 0.2:
                continue

            # Primary: visually stunning scenes (no other requirements)
            if scene.visual_potential >= min_vis:
                result.append(sm)
                continue

            # Secondary: good action AND narrative relevance
            if scene.intensity >= min_int and scene.importance >= min_imp:
                result.append(sm)
                continue

            # Tertiary: pure high-intensity action
            if scene.intensity >= 0.5:
                result.append(sm)
                continue

            # Quaternary: highly important narrative moments
            if scene.importance >= 0.5:
                result.append(sm)
                continue

        return result

    def should_trigger(self) -> bool:
        """Trigger when enough high-quality scenes have accumulated."""
        if not self._can_trigger():
            return False
        return len(self._high_quality_scenes()) >= self.config["min_high_quality_scenes"]

    def _check_trigger(self) -> None:
        """Internal check - trigger generation if conditions met."""
        if self.should_trigger():
            self._update_status(TriggerStatus.READY)
            self._trigger_generation()

    def _trigger_generation(self) -> None:
        """Execute video generation from best scenes."""
        self._update_status(TriggerStatus.GENERATING)
        hq_scenes = self._high_quality_scenes()

        if not hq_scenes:
            self._update_status(TriggerStatus.COLLECTING)
            return

        self._logger.info(
            f"VideoEval triggering: {len(hq_scenes)} high-quality scenes, "
            f"will generate ~{len(hq_scenes) // self.config['scenes_per_video']} videos"
        )

        result = self.generate([sm.raw_scene_data for sm in hq_scenes])
        self._logger.info(f"Video generation result: {result}")

        # Store for manager to retrieve (including scene data for actual generation)
        # Note: buffer clearing is delegated to manager after it consumes the scene data
        self._last_trigger_result = {
            "status": "triggered",
            "total_videos": result.get("total_videos", 0),
            "scenes_used": result.get("scenes_used", len(hq_scenes)),
            "videos": result.get("tasks", []),
            # Include scene data list for manager to use
            "scene_data_list": [sm.raw_scene_data for sm in hq_scenes],
            "scene_objects": hq_scenes,  # Keep references to ExtractedScene objects
        }

        # Mark triggered (sets cooldown) but don't clear buffer yet
        # Manager will call clear_consumed_scenes() after consuming
        self._mark_triggered()
        self._update_status(TriggerStatus.COLLECTING)

    def evaluate(self) -> EvaluationResult:
        """Evaluate current scene buffer state."""
        hq = self._high_quality_scenes()

        if not hq:
            return EvaluationResult(
                status=self._status,
                should_trigger=False,
                confidence=0.0,
                materials=self._materials,
                reason=f"No high-quality scenes yet. Need: intensity>={self.config['min_intensity']}, "
                       f"importance>={self.config['min_importance']}, "
                       f"visual>={self.config['min_visual_potential']}",
            )

        avg_intensity = sum(s.scene.intensity for s in hq) / len(hq)
        avg_importance = sum(s.scene.importance for s in hq) / len(hq)
        avg_visual = sum(s.scene.visual_potential for s in hq) / len(hq)

        return EvaluationResult(
            status=self._status,
            should_trigger=self.should_trigger(),
            confidence=(avg_intensity + avg_importance + avg_visual) / 3,
            materials=self._materials,
            reason=f"High-quality scenes: {len(hq)}, "
                   f"avg scores: intensity={avg_intensity:.2f}, "
                   f"importance={avg_importance:.2f}, visual={avg_visual:.2f}. "
                   f"Can generate ~{len(hq) // self.config['scenes_per_video']} videos.",
        )

    @property
    def last_trigger_result(self) -> Optional[Dict[str, Any]]:
        """Return the last trigger result, if any. Cleared after read."""
        result = self._last_trigger_result
        self._last_trigger_result = None
        return result

    def clear_consumed_scenes(self, scene_ids: set) -> None:
        """Clear consumed scenes from buffer after manager has processed them.

        Args:
            scene_ids: Set of scene_ids that have been consumed.
        """
        self._scene_buffer = [
            sm for sm in self._scene_buffer
            if sm.scene.scene_id not in scene_ids
        ]

    def generate(self, scene_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate video content from scene data.

        Args:
            scene_data_list: List of scene data dicts from high-quality scenes.

        Returns:
            Dict with generated video task info.
        """
        self._mark_triggered()

        scenes_per_video = self.config["scenes_per_video"]
        videos_to_generate = []

        # Group scenes into video-sized chunks
        for i in range(0, len(scene_data_list), scenes_per_video):
            chunk = scene_data_list[i:i + scenes_per_video]
            if len(chunk) < scenes_per_video:
                break  # Don't generate partial video

            video_task = {
                "video_id": f"video_batch_{i // scenes_per_video + 1}",
                "scenes": [s.get("scene_id", f"scene_{j}") for j, s in enumerate(chunk)],
                "chapter_numbers": list(set(s.get("chapter_number", 0) for s in chunk)),
                "total_chars": sum(len(s.get("content", "")) for s in chunk),
                "generated_at": datetime.now().isoformat(),
            }
            videos_to_generate.append(video_task)

        # In production: call VideoConsumer or MiniMax API here
        # For now, return the task structure
        self._logger.info(
            f"Queued {len(videos_to_generate)} video tasks for generation"
        )

        return {
            "tasks": videos_to_generate,
            "total_videos": len(videos_to_generate),
            "scenes_used": len(scene_data_list),
            "generated_at": datetime.now().isoformat(),
        }
