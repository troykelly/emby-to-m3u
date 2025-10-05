# Data Models for AzuraCast Duplicate Detection

## Overview

This document defines the core data models used in the AzuraCast duplicate detection refactoring. All models use Python dataclasses with full type hints for clarity and type safety.

---

## 1. NormalizedMetadata

### Purpose
Canonical form of track metadata for consistent comparison across different sources (Emby/Subsonic).

### Definition

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class NormalizedMetadata:
    """Normalized track metadata for duplicate detection.

    All text fields are stripped, lowercased, and have special characters normalized.
    This ensures consistent comparison regardless of source formatting.
    """
    artist: str
    album: str
    title: str
    duration_seconds: Optional[int] = None
    musicbrainz_id: Optional[str] = None

    def fingerprint(self) -> str:
        """Generate unique comparison key from normalized metadata.

        Returns:
            String in format: "artist|album|title"
        """
        return f"{self.artist}|{self.album}|{self.title}"
```

### Validation Rules

1. **Text Fields** (artist, album, title):
   - Stripped of leading/trailing whitespace
   - Converted to lowercase
   - Special characters normalized (é → e, ñ → n)
   - Multiple spaces collapsed to single space
   - "The" prefix handling for artists

2. **Duration**:
   - Optional integer in seconds
   - Used for additional validation when available
   - Tolerance of ±2 seconds for matching

3. **MusicBrainz ID**:
   - Optional UUID string
   - Highest priority matching signal when present
   - Format: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

### Example Instances

```python
# Example 1: Complete metadata with MusicBrainz ID
metadata1 = NormalizedMetadata(
    artist="the beatles",
    album="abbey road",
    title="come together",
    duration_seconds=259,
    musicbrainz_id="7c9be5e1-8a3f-4b15-bebe-8a1a55fa34cc"
)

# Example 2: Minimal metadata without MusicBrainz ID
metadata2 = NormalizedMetadata(
    artist="pink floyd",
    album="the dark side of the moon",
    title="time",
    duration_seconds=None,  # Duration unknown
    musicbrainz_id=None
)

# Fingerprint comparison
assert metadata1.fingerprint() == "the beatles|abbey road|come together"
```

### Creation Pattern

```python
def create_normalized_metadata(raw_track: Dict[str, Any]) -> NormalizedMetadata:
    """Create NormalizedMetadata from raw track dictionary.

    Args:
        raw_track: Raw track data from Emby/Subsonic API

    Returns:
        NormalizedMetadata instance with normalized fields
    """
    from .normalization import normalize_artist, normalize_string

    return NormalizedMetadata(
        artist=normalize_artist(raw_track.get("AlbumArtist", "")),
        album=normalize_string(raw_track.get("Album", "")),
        title=normalize_string(raw_track.get("Name", "")),
        duration_seconds=raw_track.get("RunTimeTicks") // 10_000_000
            if raw_track.get("RunTimeTicks") else None,
        musicbrainz_id=raw_track.get("ProviderIds", {}).get("MusicBrainzTrack")
    )
```

---

## 2. DetectionStrategy (Enum)

### Purpose
Track which detection method successfully identified a duplicate (or no duplicate found).

### Definition

```python
from enum import Enum

class DetectionStrategy(str, Enum):
    """Strategy used to detect duplicate tracks."""

    MUSICBRAINZ_ID = "musicbrainz_id"      # Matched by MusicBrainz Track ID
    NORMALIZED_METADATA = "normalized_metadata"  # Matched by artist+album+title
    FILE_PATH = "file_path"                # Matched by file path/name
    NONE = "none"                          # No duplicate found, upload allowed

    def __str__(self) -> str:
        return self.value
```

### Usage Context

```python
# Used in UploadDecision to track detection method
decision = UploadDecision(
    should_upload=False,
    reason="Duplicate found by MusicBrainz ID match",
    strategy_used=DetectionStrategy.MUSICBRAINZ_ID,
    azuracast_file_id="12345"
)

# Logging example
logger.info(
    f"Duplicate detected using {decision.strategy_used} strategy",
    extra={"azuracast_file_id": decision.azuracast_file_id}
)
```

---

## 3. UploadDecision

### Purpose
Encapsulates the outcome of duplicate detection with full audit trail including reasoning and detection method.

### Definition

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class UploadDecision:
    """Decision on whether to upload a track to AzuraCast.

    Includes reasoning and detection strategy for audit trail and debugging.
    """
    should_upload: bool
    reason: str
    strategy_used: DetectionStrategy
    azuracast_file_id: Optional[str] = None

    def log_message(self) -> str:
        """Generate formatted log message.

        Returns:
            Human-readable decision summary
        """
        action = "Uploading" if self.should_upload else "Skipping"
        file_info = f" (AzuraCast file: {self.azuracast_file_id})" if self.azuracast_file_id else ""
        return f"{action}: {self.reason} [{self.strategy_used}]{file_info}"
```

### Example Instances

```python
# Scenario 1: Skip due to MusicBrainz ID match
skip_decision = UploadDecision(
    should_upload=False,
    reason="Duplicate found by MusicBrainz ID match",
    strategy_used=DetectionStrategy.MUSICBRAINZ_ID,
    azuracast_file_id="67890"
)

# Scenario 2: Skip due to normalized metadata match
skip_metadata = UploadDecision(
    should_upload=False,
    reason="Duplicate found: artist='the beatles' album='abbey road' title='come together'",
    strategy_used=DetectionStrategy.NORMALIZED_METADATA,
    azuracast_file_id="54321"
)

# Scenario 3: Upload allowed - no duplicate found
upload_decision = UploadDecision(
    should_upload=True,
    reason="No duplicate found in AzuraCast library",
    strategy_used=DetectionStrategy.NONE,
    azuracast_file_id=None
)

# Scenario 4: Upload allowed - ReplayGain conflict
upload_replaygain = UploadDecision(
    should_upload=True,
    reason="AzuraCast track has ReplayGain, source does not - preferring existing",
    strategy_used=DetectionStrategy.NORMALIZED_METADATA,
    azuracast_file_id="11111"
)

# Logging usage
for decision in [skip_decision, upload_decision]:
    logger.info(decision.log_message())
# Output:
# Skipping: Duplicate found by MusicBrainz ID match [musicbrainz_id] (AzuraCast file: 67890)
# Uploading: No duplicate found in AzuraCast library [none]
```

---

## 4. KnownTracksCache

### Purpose
Session-level cache for AzuraCast known tracks with TTL-based expiration to reduce API calls.

### Definition

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any
import time

@dataclass
class KnownTracksCache:
    """Cache for AzuraCast known tracks with expiration.

    Reduces API calls by caching track list for a configurable TTL.
    Thread-safe for single-threaded execution context.
    """
    tracks: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: float = field(default_factory=time.time)
    ttl_seconds: int = 300  # 5 minutes default

    def is_expired(self) -> bool:
        """Check if cache has exceeded TTL.

        Returns:
            True if cache is stale and needs refresh
        """
        return (time.time() - self.fetched_at) > self.ttl_seconds

    def get_tracks(self) -> List[Dict[str, Any]]:
        """Retrieve cached tracks.

        Returns:
            List of track dictionaries from AzuraCast

        Raises:
            RuntimeError: If cache is expired (caller should refresh)
        """
        if self.is_expired():
            raise RuntimeError(
                f"Cache expired (age: {time.time() - self.fetched_at:.1f}s, "
                f"TTL: {self.ttl_seconds}s)"
            )
        return self.tracks

    def refresh(self, new_tracks: List[Dict[str, Any]]) -> None:
        """Update cache with fresh tracks.

        Args:
            new_tracks: Fresh track list from AzuraCast API
        """
        self.tracks = new_tracks
        self.fetched_at = time.time()

    def invalidate(self) -> None:
        """Force cache expiration."""
        self.fetched_at = 0.0
        self.tracks = []
```

### Cache Invalidation Logic

```python
# Global cache instance (module-level)
_known_tracks_cache = KnownTracksCache()

def get_cached_known_tracks(
    fetch_fn: callable,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """Retrieve known tracks with automatic cache management.

    Args:
        fetch_fn: Callable that fetches fresh tracks from AzuraCast
        force_refresh: Skip cache and force API call

    Returns:
        List of known tracks (cached or fresh)
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
```

### Usage Example

```python
import logging

logger = logging.getLogger(__name__)

# Initialize cache
cache = KnownTracksCache(ttl_seconds=300)

# First access - cache empty, fetch required
def fetch_from_api():
    logger.info("Fetching tracks from AzuraCast API...")
    return [{"id": "1", "title": "Song 1"}, {"id": "2", "title": "Song 2"}]

if cache.is_expired():
    cache.refresh(fetch_from_api())

tracks1 = cache.get_tracks()  # Returns cached data
logger.info(f"Retrieved {len(tracks1)} tracks from cache")

# After 6 minutes (TTL exceeded)
time.sleep(360)

try:
    tracks2 = cache.get_tracks()  # Raises RuntimeError
except RuntimeError as e:
    logger.warning(f"Cache expired: {e}")
    cache.refresh(fetch_from_api())
    tracks2 = cache.get_tracks()

# Force invalidation
cache.invalidate()
assert cache.is_expired() == True
```

---

## Data Model Relationships

### Flow Diagram

```
Raw Track Dict (from Emby/Subsonic)
         │
         ▼
create_normalized_metadata()
         │
         ▼
   NormalizedMetadata ──────┐
         │                  │
         ▼                  │
check_file_in_azuracast()   │
         │                  │
         ├─► KnownTracksCache
         │         │
         │         ▼
         │   get_cached_known_tracks()
         │         │
         ▼         ▼
   Detection Strategies:
   1. check_file_exists_by_musicbrainz()
   2. check_file_exists_by_metadata()
   3. check_file_exists_by_path()
         │
         ▼
   UploadDecision ◄─── DetectionStrategy
         │
         ▼
   Upload or Skip Action
```

### Integration Points

1. **Input**: Raw track dictionary from Emby/Subsonic API
2. **Normalization**: `create_normalized_metadata()` → `NormalizedMetadata`
3. **Caching**: `KnownTracksCache` provides known tracks list
4. **Detection**: Multi-strategy check → `UploadDecision` with `DetectionStrategy`
5. **Action**: Use `UploadDecision.should_upload` to determine action

---

## Type Safety Benefits

### mypy Validation

```python
# Type-safe function signatures
def process_track(track: Dict[str, Any]) -> UploadDecision:
    metadata: NormalizedMetadata = create_normalized_metadata(track)
    decision: UploadDecision = check_file_in_azuracast(metadata)
    return decision

# Compile-time enum validation
strategy: DetectionStrategy = DetectionStrategy.MUSICBRAINZ_ID
# strategy = "invalid"  # mypy error: incompatible type

# Immutable dataclasses prevent mutation
metadata = NormalizedMetadata(artist="test", album="album", title="song")
# metadata.artist = "changed"  # AttributeError: can't set attribute
```

### Runtime Validation

```python
from typing import get_type_hints
import dataclasses

# Validate dataclass fields at runtime
hints = get_type_hints(NormalizedMetadata)
assert hints["artist"] == str
assert hints["duration_seconds"] == Optional[int]

# Ensure frozen dataclasses
assert dataclasses.fields(NormalizedMetadata)[0].frozen == True
assert dataclasses.fields(UploadDecision)[0].frozen == True
```

---

## Performance Considerations

### Memory Efficiency

- **NormalizedMetadata**: ~200 bytes per instance (frozen, efficient)
- **KnownTracksCache**: Configurable TTL prevents unbounded growth
- **UploadDecision**: Immutable, minimal overhead (~150 bytes)

### Cache Performance

```python
# Scenario: 10,000 tracks, 5-minute TTL
cache_size = 10_000 * 500  # ~5 MB for track dicts
api_calls_per_hour = 60 / 5  # 12 calls without cache → 1 call with cache

# Performance gain: 91.7% reduction in API calls
```

### Optimization Notes

1. **Frozen Dataclasses**: Enable hashability and prevent accidental mutation
2. **Cache TTL**: Balance freshness vs. API load (default 5 min is optimal)
3. **Fingerprint Method**: O(1) string concatenation vs. O(n) field comparison
4. **Enum String Values**: Efficient serialization for logging/JSON

---

## Testing Considerations

### Unit Test Coverage

```python
# Test normalized metadata creation
def test_normalized_metadata_creation():
    raw_track = {
        "AlbumArtist": "  The Beatles  ",
        "Album": "Abbey Road",
        "Name": "Come Together",
        "RunTimeTicks": 2590000000,  # 259 seconds
        "ProviderIds": {"MusicBrainzTrack": "abc-123"}
    }

    metadata = create_normalized_metadata(raw_track)
    assert metadata.artist == "the beatles"  # normalized
    assert metadata.duration_seconds == 259
    assert metadata.fingerprint() == "the beatles|abbey road|come together"

# Test cache expiration
def test_cache_expiration():
    cache = KnownTracksCache(ttl_seconds=1)
    cache.refresh([{"id": "1"}])

    time.sleep(1.5)
    assert cache.is_expired() == True

    with pytest.raises(RuntimeError):
        cache.get_tracks()

# Test upload decision logic
def test_upload_decision_logging():
    decision = UploadDecision(
        should_upload=False,
        reason="Duplicate found",
        strategy_used=DetectionStrategy.MUSICBRAINZ_ID,
        azuracast_file_id="123"
    )

    log_msg = decision.log_message()
    assert "Skipping" in log_msg
    assert "musicbrainz_id" in log_msg
    assert "123" in log_msg
```

---

## Migration Path

### From Current Implementation

```python
# OLD: Dictionary-based approach
track_info = {
    "artist": track["AlbumArtist"].lower(),
    "album": track["Album"].lower(),
    "title": track["Name"].lower(),
    "duplicate": False
}

# NEW: Type-safe dataclass approach
metadata = create_normalized_metadata(track)
decision = check_file_in_azuracast(metadata)

if not decision.should_upload:
    logger.info(decision.log_message())
    skip_track(track, reason=decision.reason)
else:
    upload_track(track)
```

### Backward Compatibility

All new models are additive and don't break existing API contracts. The refactoring can be done incrementally:

1. Introduce models in new module (`models.py`)
2. Update detection logic to use models
3. Deprecate old dictionary-based approach
4. Remove legacy code after validation

---

## Summary

### Key Design Principles

1. **Immutability**: Frozen dataclasses prevent accidental state mutation
2. **Type Safety**: Full type hints enable static analysis and IDE support
3. **Auditability**: `UploadDecision` includes complete reasoning trail
4. **Performance**: Caching with TTL reduces API load by >90%
5. **Testability**: Pure functions and isolated models simplify testing

### Files to Create

```
src/azuracast/
├── models.py              # All dataclass definitions
├── normalization.py       # String normalization utilities
├── detection.py           # Duplicate detection strategies
└── cache.py              # Cache management logic
```

This design provides a robust foundation for accurate duplicate detection with clear separation of concerns and comprehensive audit trails.
