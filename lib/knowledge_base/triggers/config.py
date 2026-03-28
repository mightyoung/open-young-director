"""Configuration loader for trigger system.

This module provides the TriggerConfigLoader class for loading and
validating trigger configuration from various sources.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class EvaluatorConfig:
    """Configuration for a specific evaluator type.

    Attributes:
        evaluator_type: Type of evaluator ("novel", "podcast", "video").
        enabled: Whether the evaluator is enabled.
        cooldown_seconds: Cooldown period after triggering.
        min_materials: Minimum materials before evaluation.
        custom_settings: Additional evaluator-specific settings.
    """
    evaluator_type: str
    enabled: bool = True
    cooldown_seconds: int = 300
    min_materials: int = 1
    custom_settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggerConfig:
    """Root configuration for the trigger system.

    Attributes:
        evaluators: Map of evaluator name to EvaluatorConfig.
        event_bus: Event bus configuration.
        logging_level: Logging level (default: INFO).
    """
    evaluators: Dict[str, EvaluatorConfig] = field(default_factory=dict)
    event_bus: Dict[str, Any] = field(default_factory=dict)
    logging_level: str = "INFO"


class TriggerConfigLoader:
    """Loads and validates trigger configuration.

    The TriggerConfigLoader can load configuration from:
    - JSON files
    - Python dictionaries
    - Environment variables (with prefix)

    Example:
        >>> loader = TriggerConfigLoader()
        >>> config = loader.load_file("/path/to/config.json")
        >>> novel_config = loader.get_evaluator_config("novel")
    """

    DEFAULT_CONFIG = {
        "novel": {
            "enabled": True,
            "cooldown_seconds": 60,  # 1 min - triggers per chapter
            "trigger_type": "per_chapter",
        },
        "podcast": {
            "enabled": True,
            "cooldown_seconds": 600,          # 10 min
            "trigger_type": "duration_based",
            "target_duration_minutes": 15,
            "min_chapters": 2,
            "max_chapters_per_batch": 5,
            "chars_per_minute": 500,
        },
        "video": {
            "enabled": True,
            "cooldown_seconds": 900,          # 15 min
            "trigger_type": "scene_evaluation",
            "min_intensity": 0.2,    # 很低，因为爆发/觉醒场景缺少战斗动词但视觉很强
            "min_importance": 0.3,
            "min_visual_potential": 0.4,  # 核心指标
            "scenes_per_video": 3,
            "min_high_quality_scenes": 3,
        },
    }

    def __init__(self):
        """Initialize the config loader."""
        self._logger = logging.getLogger(__name__)
        self._config: Optional[TriggerConfig] = None

    def load_file(self, path: str) -> TriggerConfig:
        """Load configuration from a JSON file.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            Loaded TriggerConfig object.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            json.JSONDecodeError: If the config file is not valid JSON.
        """
        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._config = self._parse_config(data)
        self._logger.info(f"Loaded config from {path}")
        return self._config

    def load_dict(self, config: Dict[str, Any]) -> TriggerConfig:
        """Load configuration from a dictionary.

        Args:
            config: Configuration dictionary.

        Returns:
            Loaded TriggerConfig object.
        """
        self._config = self._parse_config(config)
        self._logger.info("Loaded config from dictionary")
        return self._config

    def load_defaults(self) -> TriggerConfig:
        """Load default configuration.

        Returns:
            TriggerConfig with default values.
        """
        self._config = self._parse_config(self.DEFAULT_CONFIG)
        self._logger.info("Loaded default config")
        return self._config

    def get_evaluator_config(self, evaluator_type: str) -> Dict[str, Any]:
        """Get configuration for a specific evaluator type.

        Args:
            evaluator_type: Type of evaluator ("novel", "podcast", "video").

        Returns:
            Configuration dictionary for the evaluator.

        Raises:
            ValueError: If evaluator type is unknown and no defaults available.
        """
        if self._config is None:
            self.load_defaults()

        if evaluator_type in self._config.evaluators:
            eval_config = self._config.evaluators[evaluator_type]
            return {
                "cooldown_seconds": eval_config.cooldown_seconds,
                "min_materials": eval_config.min_materials,
                **eval_config.custom_settings,
            }

        # Return defaults if available
        if evaluator_type in self.DEFAULT_CONFIG:
            return self.DEFAULT_CONFIG[evaluator_type].copy()

        raise ValueError(f"Unknown evaluator type: {evaluator_type}")

    @property
    def config(self) -> Optional[TriggerConfig]:
        """Get the current configuration.

        Returns:
            Current TriggerConfig or None if not loaded.
        """
        return self._config

    def _parse_config(self, data: Dict[str, Any]) -> TriggerConfig:
        """Parse configuration data into TriggerConfig object.

        Args:
            data: Raw configuration dictionary.

        Returns:
            Parsed TriggerConfig object.
        """
        evaluators = {}

        for eval_name, eval_data in data.items():
            if eval_name == "event_bus" or eval_name == "logging_level":
                continue

            if isinstance(eval_data, dict):
                evaluators[eval_name] = EvaluatorConfig(
                    evaluator_type=eval_name,
                    enabled=eval_data.get("enabled", True),
                    cooldown_seconds=eval_data.get("cooldown_seconds", 300),
                    min_materials=eval_data.get("min_materials", 1),
                    custom_settings={
                        k: v for k, v in eval_data.items()
                        if k not in ("enabled", "cooldown_seconds", "min_materials")
                    },
                )

        return TriggerConfig(
            evaluators=evaluators,
            event_bus=data.get("event_bus", {}),
            logging_level=data.get("logging_level", "INFO"),
        )
