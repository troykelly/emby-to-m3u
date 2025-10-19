"""Core data models for AzuraCast duplicate detection.

This module defines the foundational data structures used throughout the duplicate
detection system, including normalized metadata, detection strategies, upload
decisions, and caching mechanisms.

All models use Python dataclasses with full type hints for type safety and clarity.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import time


@dataclass(frozen=True)
class NormalizedMetadata:
    """Normalized track metadata for duplicate detection.

    All text fields are stripped, lowercased, and have special characters normalized.
    This ensures consistent comparison regardless of source formatting.

    Attributes:
        artist: Normalized artist name (lowercased, stripped)
        album: Normalized album title (lowercased, stripped)
        title: Normalized track title (lowercased, stripped)
        duration_seconds: Optional track duration in seconds (±2s tolerance for matching)
        musicbrainz_id: Optional MusicBrainz Track ID (UUID format)

    Example:
        >>> metadata = NormalizedMetadata(
        ...     artist="the beatles",
        ...     album="abbey road",
        ...     title="come together",
        ...     duration_seconds=259,
        ...     musicbrainz_id="7c9be5e1-8a3f-4b15-bebe-8a1a55fa34cc"
        ... )
        >>> metadata.fingerprint()
        'the beatles|abbey road|come together'
    """

    artist: str
    album: str
    title: str
    duration_seconds: Optional[int] = None
    musicbrainz_id: Optional[str] = None

    def fingerprint(self) -> str:
        """Generate unique comparison key from normalized metadata.

        The fingerprint is used for fast duplicate detection by creating a
        deterministic string representation of the track's core identity.

        Returns:
            String in format: "artist|album|title"

        Example:
            >>> metadata = NormalizedMetadata("pink floyd", "wish you were here", "shine on")
            >>> metadata.fingerprint()
            'pink floyd|wish you were here|shine on'
        """
        return f"{self.artist}|{self.album}|{self.title}"


class DetectionStrategy(str, Enum):
    """Strategy used to detect duplicate tracks.

    This enum tracks which detection method successfully identified a duplicate
    (or determined no duplicate exists). Used for audit trails and analytics.

    Attributes:
        MUSICBRAINZ_ID: Matched by MusicBrainz Track ID (highest confidence)
        NORMALIZED_METADATA: Matched by artist+album+title fingerprint
        FILE_PATH: Matched by file path/name
        NONE: No duplicate found, upload allowed

    Example:
        >>> strategy = DetectionStrategy.MUSICBRAINZ_ID
        >>> str(strategy)
        'musicbrainz_id'
        >>> strategy.value
        'musicbrainz_id'
    """

    MUSICBRAINZ_ID = "musicbrainz_id"
    NORMALIZED_METADATA = "normalized_metadata"
    FILE_PATH = "file_path"
    NONE = "none"

    def __str__(self) -> str:
        """Return string representation for logging.

        Returns:
            The enum value as a string
        """
        return self.value


@dataclass(frozen=True)
class UploadDecision:
    """Decision on whether to upload a track to AzuraCast.

    Encapsulates the complete outcome of duplicate detection including reasoning,
    detection method, and references to existing files. Provides full audit trail
    for debugging and analytics.

    Attributes:
        should_upload: True if track should be uploaded, False if duplicate exists
        reason: Human-readable explanation for the decision
        strategy_used: Detection strategy that determined this decision
        azuracast_file_id: Optional ID of existing file in AzuraCast (if duplicate)

    Example:
        >>> decision = UploadDecision(
        ...     should_upload=False,
        ...     reason="Duplicate found by MusicBrainz ID match",
        ...     strategy_used=DetectionStrategy.MUSICBRAINZ_ID,
        ...     azuracast_file_id="67890"
        ... )
        >>> decision.log_message()
        'Skipping: Duplicate found by MusicBrainz ID match [musicbrainz_id] (AzuraCast file: 67890)'
    """

    should_upload: bool
    reason: str
    strategy_used: DetectionStrategy
    azuracast_file_id: Optional[str] = None

    def log_message(self) -> str:
        """Generate formatted log message.

        Creates a human-readable summary of the upload decision suitable for
        logging at INFO level. Includes action, reason, strategy, and file ID.

        Returns:
            Human-readable decision summary

        Example:
            >>> decision = UploadDecision(
            ...     should_upload=True,
            ...     reason="No duplicate found",
            ...     strategy_used=DetectionStrategy.NONE
            ... )
            >>> decision.log_message()
            'Uploading: No duplicate found [none]'
        """
        action = "Uploading" if self.should_upload else "Skipping"
        file_info = f" (AzuraCast file: {self.azuracast_file_id})" if self.azuracast_file_id else ""
        return f"{action}: {self.reason} [{self.strategy_used}]{file_info}"


@dataclass
class KnownTracksCache:
    """Cache for AzuraCast known tracks with expiration.

    Session-level cache that reduces API calls by storing the track list for a
    configurable TTL. Automatically manages expiration and provides methods for
    safe access, refresh, and invalidation.

    Thread-safe for single-threaded execution context (not thread-safe for
    concurrent access).

    Attributes:
        tracks: List of track dictionaries from AzuraCast API
        fetched_at: Unix timestamp when cache was last refreshed
        ttl_seconds: Time-to-live in seconds (default: 300 = 5 minutes)

    Example:
        >>> cache = KnownTracksCache(ttl_seconds=300)
        >>> cache.refresh([{"id": "1", "title": "Song 1"}])
        >>> cache.is_expired()
        False
        >>> tracks = cache.get_tracks()
        >>> len(tracks)
        1
    """

    tracks: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300  # 5 minutes default

    def is_expired(self) -> bool:
        """Check if cache has exceeded TTL.

        Compares current time against fetch timestamp and TTL to determine
        if the cache data is stale.

        Returns:
            True if cache is stale and needs refresh, False if still valid

        Example:
            >>> cache = KnownTracksCache(ttl_seconds=1)
            >>> cache.is_expired()
            False
            >>> import time; time.sleep(1.1)
            >>> cache.is_expired()
            True
        """
        return (time.time() - self.fetched_at) > self.ttl_seconds

    def get_tracks(self) -> list[dict[str, Any]]:
        """Retrieve cached tracks.

        Returns the cached track list if valid (not expired). Raises an error
        if the cache is stale, forcing the caller to refresh.

        Returns:
            List of track dictionaries from AzuraCast

        Raises:
            RuntimeError: If cache is expired (caller should refresh first)

        Example:
            >>> cache = KnownTracksCache()
            >>> cache.refresh([{"id": "1"}])
            >>> tracks = cache.get_tracks()
            >>> len(tracks)
            1
        """
        if self.is_expired():
            age = time.time() - self.fetched_at
            raise RuntimeError(f"Cache expired (age: {age:.1f}s, TTL: {self.ttl_seconds}s)")
        return self.tracks

    def refresh(self, new_tracks: list[dict[str, Any]]) -> None:
        """Update cache with fresh tracks.

        Replaces the cached track list with fresh data from the AzuraCast API
        and resets the fetch timestamp.

        Args:
            new_tracks: Fresh track list from AzuraCast API

        Example:
            >>> cache = KnownTracksCache()
            >>> cache.refresh([{"id": "1"}, {"id": "2"}])
            >>> len(cache.tracks)
            2
        """
        self.tracks = new_tracks
        self.fetched_at = time.time()

    def invalidate(self) -> None:
        """Force cache expiration.

        Clears the cache and sets the fetch timestamp to epoch zero, forcing
        the next access to refresh. Useful for testing or when known tracks
        have been modified.

        Example:
            >>> cache = KnownTracksCache()
            >>> cache.refresh([{"id": "1"}])
            >>> cache.invalidate()
            >>> cache.is_expired()
            True
            >>> len(cache.tracks)
            0
        """
        self.fetched_at = 0.0
        self.tracks = []
