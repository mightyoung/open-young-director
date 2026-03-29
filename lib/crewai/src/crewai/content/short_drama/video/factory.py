"""Video Provider Factory - Create video provider instances.

Usage:
    from crewai.content.short_drama.video.factory import create_video_provider

    # From string name
    provider = create_video_provider("minimax")

    # With config
    provider = create_video_provider("minimax", api_key="xxx", output_dir="./output")

    # Async usage
    result = await provider.generate("a warrior on a cliff", duration=5)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from crewai.content.short_drama.video.base import VideoProviderProtocol

if TYPE_CHECKING:
    pass


def create_video_provider(
    provider: str | None = None,
    **kwargs,
) -> VideoProviderProtocol:
    """Create a video provider instance by name.

    Args:
        provider: Provider name ("minimax", "runway", "kling").
                  Defaults to MINIMAX_VIDEO_PROVIDER env var or "minimax".
        **kwargs: Additional arguments passed to the provider constructor.

    Returns:
        VideoProviderProtocol instance.

    Raises:
        ValueError: If the provider name is not recognized.

    Example:
        ```python
        provider = create_video_provider("minimax")
        result = await provider.generate("A warrior standing on a cliff")
        ```
    """
    # Resolve provider name
    if provider is None:
        provider = os.environ.get("MINIMAX_VIDEO_PROVIDER", "minimax").lower()

    provider = provider.lower()

    if provider == "minimax":
        from crewai.content.short_drama.video.providers.minimax_provider import (
            MiniMaxVideoProvider,
        )

        return MiniMaxVideoProvider(**kwargs)

    elif provider in ("runway", "runwayml"):
        from crewai.content.short_drama.video.providers.runway_provider import (
            RunwayVideoProvider,
        )

        return RunwayVideoProvider(**kwargs)

    elif provider in ("kling", "klingai"):
        from crewai.content.short_drama.video.providers.kling_provider import (
            KlingVideoProvider,
        )

        return KlingVideoProvider(**kwargs)

    else:
        raise ValueError(
            f"Unknown video provider: {provider!r}. "
            f"Supported: minimax, runway, kling"
        )


def list_video_providers() -> list[str]:
    """Return a list of available (installed) video provider names."""
    providers = ["minimax"]

    # Check for optional providers
    try:
        from crewai.content.short_drama.video.providers.runway_provider import (  # noqa: F401
            RunwayVideoProvider
        )
        providers.append("runway")
    except ImportError:
        pass

    try:
        from crewai.content.short_drama.video.providers.kling_provider import (  # noqa: F401
            KlingVideoProvider
        )
        providers.append("kling")
    except ImportError:
        pass

    return providers


__all__ = ["create_video_provider", "list_video_providers"]
