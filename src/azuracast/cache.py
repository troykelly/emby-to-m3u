"""Cache management logic for AzuraCast duplicate detection.

This module provides caching functionality to reduce API calls by storing
known tracks with TTL-based expiration.
"""

import logging
import time
from typing import Any, Callable

from .models import KnownTracksCache

# Module-level logger
logger = logging.getLogger(__name__)

# Global cache instance - start with expired cache (fetched_at=0.0)
_known_tracks_cache = KnownTracksCache(tracks=[], fetched_at=0.0)


def get_cached_known_tracks(
    fetch_fn: Callable[[], list[dict[str, Any]]], force_refresh: bool = False
) -> list[dict[str, Any]]:
    """Retrieve known tracks with automatic cache management.

    Manages the known tracks cache by checking expiration and refreshing when
    necessary. Reduces API calls by serving cached data when still valid.

    Args:
        fetch_fn: Callable that fetches fresh tracks from AzuraCast API
        force_refresh: Skip cache and force API call (default: False)

    Returns:
        List of known tracks (cached or fresh)

    Example:
        >>> def fetch_tracks():
        ...     return [{"id": "1", "title": "Song"}]
        >>> tracks = get_cached_known_tracks(fetch_tracks)
        >>> len(tracks)
        1
    """
    global _known_tracks_cache

    if force_refresh or _known_tracks_cache.is_expired():
        logger.debug(
            f"Refreshing known tracks cache "
            f"(expired: {_known_tracks_cache.is_expired()}, forced: {force_refresh})"
        )
        fresh_tracks = fetch_fn()
        _known_tracks_cache.refresh(fresh_tracks)
    else:
        logger.debug(
            f"Using cached known tracks "
            f"(age: {time.time() - _known_tracks_cache.fetched_at:.1f}s)"
        )

    return _known_tracks_cache.get_tracks()


def should_skip_replaygain_conflict(
    azuracast_track: dict[str, Any], source_track: dict[str, Any]
) -> bool:
    """Check if upload should be skipped due to ReplayGain conflict.

    Placeholder implementation for T010/T011.

    Args:
        azuracast_track: Track dictionary from AzuraCast
        source_track: Track dictionary from Emby/Subsonic

    Returns:
        True if should skip upload due to ReplayGain conflict
    """
    # Placeholder - returns True if AzuraCast has ReplayGain data
    return azuracast_track.get("replaygain_track_gain") is not None
