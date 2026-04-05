"""MarketLoader - Dynamic Agent Profile System.

Inspired by marketplace ecosystems. Allows loading specialized agent personas
(e.g., 'Mao Ni Style', 'Logic Nut') from external YAML files to override
default behaviors in the novel pipeline.
"""

from typing import Any, Dict, Optional
import os
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MarketLoader:
    """Service for loading and merging external agent profiles."""

    def __init__(self, market_dir: str = "market/agents"):
        self.market_dir = Path(market_dir)
        self.market_dir.mkdir(parents=True, exist_ok=True)

    def load_profile(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Load an agent profile by ID (e.g., 'maoni')."""
        path = self.market_dir / f"{agent_id}.yaml"
        if not path.exists():
            logger.warning(f"Market Profile '{agent_id}' not found at {path}")
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_all_load(f) if hasattr(yaml, 'safe_all_load') else yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to parse market profile '{agent_id}': {e}")
            return None

    def override_agent_config(self, default_config: Dict[str, Any], market_profile: Dict[str, Any]) -> Dict[str, Any]:
        """Merge market profile into existing agent config."""
        new_config = default_config.copy()
        if not market_profile: return new_config
        
        # Override core fields if present in market profile
        for key in ["role", "goal", "backstory", "style_hints"]:
            if key in market_profile:
                new_config[key] = market_profile[key]
        
        return new_config
