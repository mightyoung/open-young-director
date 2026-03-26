"""Result caching for ComfyUI workflow execution.

This module provides caching to avoid duplicate generations based on:
- Prompt hash
- Generation parameters (steps, cfg, seed, etc.)
- Model name

Usage:
    from crewai.comfy.cache import GenerationCache, get_cache

    cache = get_cache()
    result = cache.get(prompt="...", params={...})
    if result is None:
        result = executor.execute(workflow)
        cache.set(prompt, params, result)
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for the generation cache."""

    enabled: bool = True
    cache_dir: str = ".crewai_comfy_cache"
    max_entries: int = 1000
    ttl_seconds: int = 3600 * 24 * 7  # 7 days
    hash_prompts: bool = True


@dataclass
class CacheEntry:
    """A cached generation result."""

    key: str
    prompt: str
    params: dict[str, Any]
    result: dict[str, Any]
    created_at: float
    access_count: int = 0
    last_accessed: float = 0


class GenerationCache:
    """Cache for workflow generation results.

    This cache:
    - Stores results by prompt + parameters hash
    - Supports TTL expiration
    - Thread-safe operations
    - Persists to disk for reuse across sessions
    """

    def __init__(self, config: Optional[CacheConfig] = None):
        """Initialize the cache.

        Args:
            config: Cache configuration
        """
        self.config = config or CacheConfig()
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

        if self.config.enabled:
            self._load_from_disk()

    def _make_key(self, prompt: str, params: dict[str, Any]) -> str:
        """Generate a cache key from prompt and parameters.

        Args:
            prompt: Generation prompt
            params: Generation parameters

        Returns:
            Cache key string
        """
        # Normalize params
        normalized_params = {}
        for k, v in sorted(params.items()):
            if v is not None:
                normalized_params[k] = v

        # Create deterministic dict
        cache_dict = {
            "prompt": prompt.strip().lower(),
            "params": normalized_params,
        }

        # Hash it
        cache_str = json.dumps(cache_dict, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:32]

    def get(self, prompt: str, params: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Get a cached result.

        Args:
            prompt: Generation prompt
            params: Generation parameters

        Returns:
            Cached result or None if not found
        """
        if not self.config.enabled:
            return None

        key = self._make_key(prompt, params)

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                logger.debug(f"Cache miss: {key[:8]}...")
                return None

            # Update access stats
            import time
            entry.access_count += 1
            entry.last_accessed = time.time()

            self._hits += 1
            logger.debug(f"Cache hit: {key[:8]}... (access #{entry.access_count})")

            return entry.result

    def set(self, prompt: str, params: dict[str, Any], result: dict[str, Any]) -> None:
        """Store a result in the cache.

        Args:
            prompt: Generation prompt
            params: Generation parameters
            result: Generation result to cache
        """
        if not self.config.enabled:
            return

        key = self._make_key(prompt, params)

        with self._lock:
            # Evict old entries if needed
            if len(self._cache) >= self.config.max_entries:
                self._evict_oldest()

            import time
            entry = CacheEntry(
                key=key,
                prompt=prompt,
                params=params,
                result=result,
                created_at=time.time(),
                last_accessed=time.time(),
            )

            self._cache[key] = entry
            logger.debug(f"Cache set: {key[:8]}...")

        # Persist async
        self._save_to_disk_async()

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if not self._cache:
            return

        # Find entry with oldest last_accessed
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].last_accessed,
        )

        del self._cache[oldest_key]
        logger.debug(f"Cache evicted: {oldest_key[:8]}...")

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        cache_path = Path(self.config.cache_dir)
        if not cache_path.exists():
            return

        index_file = cache_path / "index.json"
        if not index_file.exists():
            return

        try:
            with open(index_file, "r") as f:
                data = json.load(f)

            import time
            current_time = time.time()

            for key, entry_data in data.items():
                # Check TTL
                if current_time - entry_data["created_at"] > self.config.ttl_seconds:
                    continue

                self._cache[key] = CacheEntry(
                    key=key,
                    prompt=entry_data["prompt"],
                    params=entry_data["params"],
                    result=entry_data["result"],
                    created_at=entry_data["created_at"],
                    access_count=entry_data.get("access_count", 0),
                    last_accessed=entry_data.get("last_accessed", entry_data["created_at"]),
                )

            logger.info(f"Cache loaded: {len(self._cache)} entries")

        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def _save_to_disk_async(self) -> None:
        """Save cache to disk (call from background thread)."""
        thread = threading.Thread(target=self._save_to_disk, daemon=True)
        thread.start()

    def _save_to_disk(self) -> None:
        """Save cache to disk."""
        cache_path = Path(self.config.cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

        index_file = cache_path / "index.json"

        data = {}
        for key, entry in self._cache.items():
            data[key] = {
                "prompt": entry.prompt,
                "params": entry.params,
                "result": entry.result,
                "created_at": entry.created_at,
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed,
            }

        try:
            with open(index_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

        # Remove disk cache
        cache_path = Path(self.config.cache_dir)
        index_file = cache_path / "index.json"
        if index_file.exists():
            index_file.unlink()

        logger.info("Cache cleared")

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, size, hit_rate
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_entries": self.config.max_entries,
            "hit_rate": hit_rate,
            "enabled": self.config.enabled,
        }


# Global cache instance
_global_cache: Optional[GenerationCache] = None
_cache_lock = threading.Lock()


def get_cache(config: Optional[CacheConfig] = None) -> GenerationCache:
    """Get the global cache instance.

    Args:
        config: Optional cache configuration

    Returns:
        Global GenerationCache instance
    """
    global _global_cache

    with _cache_lock:
        if _global_cache is None:
            _global_cache = GenerationCache(config)
        return _global_cache


def reset_cache() -> None:
    """Reset the global cache instance."""
    global _global_cache

    with _cache_lock:
        if _global_cache is not None:
            _global_cache.clear()
            _global_cache = None


class CachedComfyWorkflowExecutor:
    """A ComfyWorkflowExecutor wrapper with caching.

    Usage:
        from crewai.comfy.cache import CachedComfyWorkflowExecutor

        executor = CachedComfyWorkflowExecutor()
        result = executor.execute_with_cache(workflow, prompt="...", params={...})
    """

    def __init__(
        self,
        executor: Any = None,
        cache_config: Optional[CacheConfig] = None,
    ):
        """Initialize the cached executor.

        Args:
            executor: Optional underlying executor
            cache_config: Cache configuration
        """
        self._executor = executor
        self._cache = get_cache(cache_config)

    @property
    def executor(self) -> Any:
        """Lazy-load the underlying executor."""
        if self._executor is None:
            from crewai.comfy import ComfyWorkflowExecutor
            self._executor = ComfyWorkflowExecutor()
        return self._executor

    def execute_with_cache(
        self,
        workflow: dict[str, Any],
        prompt: str = "",
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute workflow with caching.

        Args:
            workflow: Workflow to execute
            prompt: Prompt for cache key
            params: Parameters for cache key

        Returns:
            Execution result (from cache or fresh)
        """
        params = params or {}

        # Check cache
        cached = self._cache.get(prompt, params)
        if cached is not None:
            logger.info("Using cached result")
            return cached

        # Execute fresh
        result = self.executor.execute(workflow)

        # Store in cache
        self._cache.set(prompt, params, result)

        return result
