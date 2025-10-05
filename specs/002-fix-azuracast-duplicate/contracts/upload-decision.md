# Upload Decision Contracts

## Overview

Upload decision logic and caching mechanisms for AzuraCast duplicate detection. Handles the final determination of whether to upload a track, with special handling for ReplayGain conflicts and efficient caching strategies.

---

## 1. should_skip_replaygain_conflict

### Signature

```python
from typing import Optional, Dict, Any

def should_skip_replaygain_conflict(
    azuracast_track: Optional[Dict[str, Any]],
    source_track: Dict[str, Any]
) -> bool:
    """Determine if upload should be skipped due to ReplayGain conflict.

    Args:
        azuracast_track: Track from AzuraCast library (may be None if no duplicate)
            Expected fields:
            - replaygain_track_gain (float, optional): Track gain in dB
            - replaygain_album_gain (float, optional): Album gain in dB

        source_track: Track from source system (Emby/Subsonic)
            Expected fields (Emby format):
            - ReplayGainTrackGain (float, optional): Track gain in dB
            - ReplayGainAlbumGain (float, optional): Album gain in dB

    Returns:
        True if upload should be SKIPPED to preserve AzuraCast's ReplayGain metadata

    Decision Logic:
        IF azuracast_track exists AND has ReplayGain:
            IF source_track does NOT have ReplayGain:
                RETURN True (SKIP upload - preserve AzuraCast's metadata)
        RETURN False (normal duplicate handling)

    Rationale:
        ReplayGain tags are valuable for volume normalization.
        If AzuraCast already has these tags and the source doesn't,
        uploading would REPLACE good metadata with inferior metadata.
        Therefore, we skip the upload to preserve quality.

    Edge Cases:
        - Both have ReplayGain: Allow upload (normal duplicate logic applies)
        - Neither has ReplayGain: Allow upload (no metadata loss)
        - Source has RG, AzuraCast doesn't: Allow upload (improvement)
        - azuracast_track is None: Allow upload (no duplicate)
    """
```

### Example Inputs/Outputs

```python
# Scenario 1: AzuraCast has ReplayGain, source doesn't → SKIP
azuracast_track = {
    "id": "12345",
    "artist": "The Beatles",
    "title": "Come Together",
    "replaygain_track_gain": -3.52,  # dB
    "replaygain_album_gain": -2.81   # dB
}

source_track = {
    "AlbumArtist": "The Beatles",
    "Name": "Come Together"
    # No ReplayGain fields
}

assert should_skip_replaygain_conflict(azuracast_track, source_track) == True

# Scenario 2: Both have ReplayGain → Don't skip (normal duplicate handling)
azuracast_track = {
    "id": "12345",
    "replaygain_track_gain": -3.52
}

source_track = {
    "Name": "Song",
    "ReplayGainTrackGain": -2.10  # Emby format
}

assert should_skip_replaygain_conflict(azuracast_track, source_track) == False

# Scenario 3: Neither has ReplayGain → Don't skip
azuracast_track = {
    "id": "12345",
    "artist": "Artist"
}

source_track = {
    "Name": "Song"
}

assert should_skip_replaygain_conflict(azuracast_track, source_track) == False

# Scenario 4: Source has ReplayGain, AzuraCast doesn't → Don't skip (improvement)
azuracast_track = {
    "id": "12345"
}

source_track = {
    "Name": "Song",
    "ReplayGainTrackGain": -1.5
}

assert should_skip_replaygain_conflict(azuracast_track, source_track) == False

# Scenario 5: No AzuraCast track (no duplicate found) → Don't skip
assert should_skip_replaygain_conflict(None, source_track) == False
```

### Edge Cases

```python
# Only track gain present (no album gain)
azuracast_track = {
    "id": "1",
    "replaygain_track_gain": -3.0
    # No album gain
}
source_track = {"Name": "Song"}
assert should_skip_replaygain_conflict(azuracast_track, source_track) == True

# Only album gain present (no track gain)
azuracast_track = {
    "id": "1",
    "replaygain_album_gain": -2.5
}
source_track = {"Name": "Song"}
assert should_skip_replaygain_conflict(azuracast_track, source_track) == True

# Zero ReplayGain values (valid but unusual)
azuracast_track = {
    "id": "1",
    "replaygain_track_gain": 0.0  # Valid value
}
source_track = {"Name": "Song"}
assert should_skip_replaygain_conflict(azuracast_track, source_track) == True

# Subsonic format (different field names)
azuracast_track = {
    "id": "1",
    "replaygain_track_gain": -3.0
}
source_track = {
    "Name": "Song",
    "replaygain_track_gain": -2.0  # Subsonic format (lowercase)
}
assert should_skip_replaygain_conflict(azuracast_track, source_track) == False

# Invalid ReplayGain values (non-numeric)
azuracast_track = {
    "id": "1",
    "replaygain_track_gain": "invalid"  # Invalid data
}
source_track = {"Name": "Song"}
# Should treat as "has ReplayGain" based on field presence
assert should_skip_replaygain_conflict(azuracast_track, source_track) == True
```

### Implementation Notes

```python
def should_skip_replaygain_conflict(
    azuracast_track: Optional[Dict[str, Any]],
    source_track: Dict[str, Any]
) -> bool:
    # No AzuraCast track → no conflict
    if not azuracast_track:
        return False

    # Check if AzuraCast has ReplayGain (any variant)
    azuracast_has_rg = any([
        "replaygain_track_gain" in azuracast_track,
        "replaygain_album_gain" in azuracast_track,
        "replaygain_track_peak" in azuracast_track,  # Also check peak values
        "replaygain_album_peak" in azuracast_track
    ])

    # Check if source has ReplayGain (multiple formats)
    source_has_rg = any([
        # Emby format (PascalCase)
        "ReplayGainTrackGain" in source_track,
        "ReplayGainAlbumGain" in source_track,
        "ReplayGainTrackPeak" in source_track,
        "ReplayGainAlbumPeak" in source_track,
        # Subsonic format (lowercase)
        "replaygain_track_gain" in source_track,
        "replaygain_album_gain" in source_track,
        "replaygain_track_peak" in source_track,
        "replaygain_album_peak" in source_track,
        # Alternative formats
        "REPLAYGAIN_TRACK_GAIN" in source_track,  # Uppercase variant
        "REPLAYGAIN_ALBUM_GAIN" in source_track
    ])

    # Conflict: AzuraCast has RG, source doesn't
    return azuracast_has_rg and not source_has_rg

# Alternative: Validate ReplayGain values
def has_valid_replaygain(track: Dict[str, Any], field_prefix: str = "") -> bool:
    """Check if track has valid ReplayGain values.

    Args:
        track: Track dictionary
        field_prefix: Optional prefix for field names (e.g., "ReplayGain" for Emby)

    Returns:
        True if track has at least one valid ReplayGain field
    """
    rg_fields = [
        f"{field_prefix}track_gain",
        f"{field_prefix}album_gain",
        f"{field_prefix}track_peak",
        f"{field_prefix}album_peak"
    ]

    for field in rg_fields:
        value = track.get(field) or track.get(field.lower()) or track.get(field.upper())
        if value is not None:
            try:
                float(value)  # Validate it's numeric
                return True
            except (ValueError, TypeError):
                continue

    return False
```

### Logging and Metrics

```python
import logging

logger = logging.getLogger(__name__)

def should_skip_replaygain_conflict_with_logging(
    azuracast_track: Optional[Dict[str, Any]],
    source_track: Dict[str, Any]
) -> bool:
    """Version with detailed logging for debugging."""

    if not azuracast_track:
        return False

    azuracast_has_rg = any([
        "replaygain_track_gain" in azuracast_track,
        "replaygain_album_gain" in azuracast_track
    ])

    source_has_rg = any([
        "ReplayGainTrackGain" in source_track,
        "ReplayGainAlbumGain" in source_track,
        "replaygain_track_gain" in source_track,
        "replaygain_album_gain" in source_track
    ])

    if azuracast_has_rg and not source_has_rg:
        logger.info(
            f"ReplayGain conflict detected: "
            f"AzuraCast track {azuracast_track.get('id')} has ReplayGain "
            f"(track: {azuracast_track.get('replaygain_track_gain')}, "
            f"album: {azuracast_track.get('replaygain_album_gain')}), "
            f"but source track '{source_track.get('Name', 'Unknown')}' does not. "
            f"Skipping upload to preserve metadata."
        )
        return True

    if azuracast_has_rg and source_has_rg:
        logger.debug(
            f"Both tracks have ReplayGain: "
            f"AzuraCast={azuracast_track.get('replaygain_track_gain')}, "
            f"Source={source_track.get('ReplayGainTrackGain')}. "
            f"Normal duplicate handling applies."
        )

    return False
```

---

## 2. get_cached_known_tracks

### Signature

```python
from typing import List, Dict, Any, Callable
import logging

logger = logging.getLogger(__name__)

def get_cached_known_tracks(
    fetch_fn: Callable[[], List[Dict[str, Any]]],
    force_refresh: bool = False,
    ttl_seconds: int = 300
) -> List[Dict[str, Any]]:
    """Retrieve known tracks from cache or fetch if expired/missing.

    Args:
        fetch_fn: Callable that fetches fresh tracks from AzuraCast API
            Signature: () -> List[Dict[str, Any]]
            Example: lambda: azuracast_client.get_station_files(station_id)

        force_refresh: Skip cache and force API call
            Use when: Manual refresh requested, after upload operations

        ttl_seconds: Time-to-live for cache in seconds
            Default: 300 (5 minutes)
            Recommended range: 60-600 seconds

    Returns:
        List of track dictionaries from AzuraCast

    Caching Strategy:
        1. Check global cache for existing data
        2. If cache expired or force_refresh:
            a. Call fetch_fn() to get fresh data
            b. Update cache with new data + timestamp
        3. Return cached data

    Thread Safety:
        - Single-threaded execution assumed
        - For multi-threaded: Use threading.Lock around cache access

    Cache Invalidation:
        - Automatic: After TTL expires
        - Manual: Set force_refresh=True
        - On upload: Invalidate cache after successful upload

    Performance:
        - Cache hit: O(1) return
        - Cache miss: O(API_LATENCY) + O(n) for track list
        - Typical API latency: 100-500ms for 10k tracks
    """
```

### Example Usage

```python
from typing import List, Dict, Any
import time

# Define fetch function (talks to AzuraCast API)
def fetch_known_tracks_from_api() -> List[Dict[str, Any]]:
    """Fetch tracks from AzuraCast API."""
    import requests

    response = requests.get(
        "https://azuracast.example.com/api/station/1/files",
        headers={"X-API-Key": "your-api-key"}
    )
    response.raise_for_status()
    return response.json()

# Usage 1: First access (cache miss, fetches from API)
tracks = get_cached_known_tracks(fetch_known_tracks_from_api)
print(f"Fetched {len(tracks)} tracks")  # API call made

# Usage 2: Second access within TTL (cache hit)
tracks = get_cached_known_tracks(fetch_known_tracks_from_api)
print(f"Got {len(tracks)} tracks from cache")  # No API call

# Usage 3: Force refresh (manual invalidation)
tracks = get_cached_known_tracks(
    fetch_known_tracks_from_api,
    force_refresh=True
)
print(f"Forced refresh: {len(tracks)} tracks")  # API call made

# Usage 4: After TTL expires (automatic invalidation)
time.sleep(301)  # Wait past 5-minute TTL
tracks = get_cached_known_tracks(fetch_known_tracks_from_api)
print(f"Cache expired, refetched: {len(tracks)} tracks")  # API call made

# Usage 5: Custom TTL (1 minute for frequently changing library)
tracks = get_cached_known_tracks(
    fetch_known_tracks_from_api,
    ttl_seconds=60
)
```

### Implementation with Global Cache

```python
import time
from typing import List, Dict, Any, Callable, Optional
from dataclasses import dataclass, field

@dataclass
class KnownTracksCache:
    """Global cache for known tracks."""
    tracks: List[Dict[str, Any]] = field(default_factory=list)
    fetched_at: float = 0.0
    ttl_seconds: int = 300

    def is_expired(self) -> bool:
        """Check if cache has exceeded TTL."""
        return (time.time() - self.fetched_at) > self.ttl_seconds

    def refresh(self, new_tracks: List[Dict[str, Any]]) -> None:
        """Update cache with fresh tracks."""
        self.tracks = new_tracks
        self.fetched_at = time.time()

    def invalidate(self) -> None:
        """Force cache expiration."""
        self.fetched_at = 0.0

# Global cache instance
_cache = KnownTracksCache()

def get_cached_known_tracks(
    fetch_fn: Callable[[], List[Dict[str, Any]]],
    force_refresh: bool = False,
    ttl_seconds: int = 300
) -> List[Dict[str, Any]]:
    global _cache

    # Update TTL if different
    if _cache.ttl_seconds != ttl_seconds:
        _cache.ttl_seconds = ttl_seconds

    # Check if refresh needed
    needs_refresh = force_refresh or _cache.is_expired() or not _cache.tracks

    if needs_refresh:
        logger.info(
            f"Refreshing known tracks cache "
            f"(expired: {_cache.is_expired()}, "
            f"forced: {force_refresh}, "
            f"empty: {not _cache.tracks})"
        )

        # Fetch fresh data
        start_time = time.time()
        fresh_tracks = fetch_fn()
        fetch_duration = time.time() - start_time

        # Update cache
        _cache.refresh(fresh_tracks)

        logger.info(
            f"Cache refreshed: {len(fresh_tracks)} tracks "
            f"fetched in {fetch_duration:.2f}s"
        )
    else:
        cache_age = time.time() - _cache.fetched_at
        logger.debug(
            f"Using cached known tracks "
            f"({len(_cache.tracks)} tracks, age: {cache_age:.1f}s)"
        )

    return _cache.tracks

# Manual cache management
def invalidate_known_tracks_cache() -> None:
    """Manually invalidate cache (call after uploads)."""
    global _cache
    _cache.invalidate()
    logger.info("Known tracks cache invalidated")

def get_cache_status() -> Dict[str, Any]:
    """Get current cache status for monitoring."""
    global _cache

    return {
        "track_count": len(_cache.tracks),
        "fetched_at": _cache.fetched_at,
        "age_seconds": time.time() - _cache.fetched_at,
        "ttl_seconds": _cache.ttl_seconds,
        "is_expired": _cache.is_expired()
    }
```

### Integration with Upload Workflow

```python
def upload_track_to_azuracast(track: Dict[str, Any]) -> bool:
    """Upload track and invalidate cache."""
    # Upload logic...
    success = perform_upload(track)

    if success:
        # Invalidate cache after successful upload
        invalidate_known_tracks_cache()
        logger.info(
            f"Track uploaded successfully, cache invalidated: "
            f"{track.get('Name', 'Unknown')}"
        )

    return success

def sync_library_batch(
    source_tracks: List[Dict[str, Any]],
    batch_size: int = 100
) -> Dict[str, int]:
    """Sync library in batches with cache management."""
    stats = {"uploaded": 0, "skipped": 0}

    # Fetch known tracks once at start
    known_tracks = get_cached_known_tracks(
        fetch_known_tracks_from_api,
        force_refresh=True  # Fresh data for batch sync
    )

    for i in range(0, len(source_tracks), batch_size):
        batch = source_tracks[i:i+batch_size]

        for track in batch:
            decision = check_file_in_azuracast(known_tracks, track)

            if decision.should_upload:
                upload_track_to_azuracast(track)
                stats["uploaded"] += 1
            else:
                stats["skipped"] += 1

        # Refresh cache every batch (picks up newly uploaded tracks)
        if i + batch_size < len(source_tracks):
            known_tracks = get_cached_known_tracks(
                fetch_known_tracks_from_api,
                force_refresh=True
            )

    logger.info(f"Batch sync complete: {stats}")
    return stats
```

### Error Handling

```python
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def get_cached_known_tracks_safe(
    fetch_fn: Callable[[], List[Dict[str, Any]]],
    force_refresh: bool = False,
    ttl_seconds: int = 300,
    fallback_on_error: bool = True
) -> List[Dict[str, Any]]:
    """Version with error handling and fallback logic.

    Args:
        fallback_on_error: If True, return stale cache on fetch error
    """
    global _cache

    needs_refresh = force_refresh or _cache.is_expired() or not _cache.tracks

    if needs_refresh:
        try:
            fresh_tracks = fetch_fn()
            _cache.refresh(fresh_tracks)
            return _cache.tracks
        except Exception as e:
            logger.error(f"Failed to fetch known tracks: {e}")

            if fallback_on_error and _cache.tracks:
                logger.warning(
                    f"Using stale cache as fallback "
                    f"({len(_cache.tracks)} tracks, "
                    f"age: {time.time() - _cache.fetched_at:.1f}s)"
                )
                return _cache.tracks
            else:
                # No fallback, re-raise error
                raise

    return _cache.tracks

# Circuit breaker pattern for API failures
class CacheCircuitBreaker:
    """Prevent repeated API calls when service is down."""

    def __init__(self, failure_threshold: int = 3, timeout_seconds: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.last_failure_time: Optional[float] = None
        self.is_open = False

    def record_failure(self) -> None:
        """Record API failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(
                f"Circuit breaker OPEN after {self.failure_count} failures. "
                f"Blocking API calls for {self.timeout_seconds}s"
            )

    def record_success(self) -> None:
        """Record successful API call."""
        self.failure_count = 0
        self.is_open = False

    def can_attempt(self) -> bool:
        """Check if API call is allowed."""
        if not self.is_open:
            return True

        # Check if timeout has passed
        if self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.timeout_seconds:
                logger.info("Circuit breaker timeout expired, allowing retry")
                self.is_open = False
                return True

        return False

# Global circuit breaker
_circuit_breaker = CacheCircuitBreaker()

def get_cached_known_tracks_with_circuit_breaker(
    fetch_fn: Callable[[], List[Dict[str, Any]]],
    force_refresh: bool = False,
    ttl_seconds: int = 300
) -> List[Dict[str, Any]]:
    """Version with circuit breaker for API resilience."""
    global _cache, _circuit_breaker

    needs_refresh = force_refresh or _cache.is_expired() or not _cache.tracks

    if needs_refresh:
        if not _circuit_breaker.can_attempt():
            logger.warning("Circuit breaker OPEN, using stale cache")
            return _cache.tracks

        try:
            fresh_tracks = fetch_fn()
            _cache.refresh(fresh_tracks)
            _circuit_breaker.record_success()
            return _cache.tracks
        except Exception as e:
            logger.error(f"API fetch failed: {e}")
            _circuit_breaker.record_failure()

            if _cache.tracks:
                logger.warning("Falling back to stale cache")
                return _cache.tracks
            else:
                raise

    return _cache.tracks
```

---

## Performance Optimization

### Cache Warming

```python
def warm_cache_on_startup() -> None:
    """Pre-populate cache on application startup."""
    logger.info("Warming known tracks cache...")

    try:
        tracks = get_cached_known_tracks(
            fetch_known_tracks_from_api,
            force_refresh=True
        )
        logger.info(f"Cache warmed: {len(tracks)} tracks loaded")
    except Exception as e:
        logger.error(f"Cache warming failed: {e}")

# Call during app initialization
if __name__ == "__main__":
    warm_cache_on_startup()
    # ... rest of app
```

### Metrics and Monitoring

```python
from dataclasses import dataclass
import time

@dataclass
class CacheMetrics:
    """Track cache performance metrics."""
    hits: int = 0
    misses: int = 0
    refreshes: int = 0
    errors: int = 0
    total_fetch_time: float = 0.0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_fetch_time(self) -> float:
        return (
            self.total_fetch_time / self.refreshes
            if self.refreshes > 0 else 0.0
        )

# Global metrics
_metrics = CacheMetrics()

def get_cached_known_tracks_with_metrics(
    fetch_fn: Callable[[], List[Dict[str, Any]]],
    force_refresh: bool = False,
    ttl_seconds: int = 300
) -> List[Dict[str, Any]]:
    """Version with performance metrics."""
    global _cache, _metrics

    needs_refresh = force_refresh or _cache.is_expired() or not _cache.tracks

    if needs_refresh:
        _metrics.misses += 1
        _metrics.refreshes += 1

        start_time = time.time()
        try:
            fresh_tracks = fetch_fn()
            fetch_duration = time.time() - start_time

            _metrics.total_fetch_time += fetch_duration
            _cache.refresh(fresh_tracks)

            logger.info(
                f"Cache miss: fetched {len(fresh_tracks)} tracks in {fetch_duration:.2f}s. "
                f"Hit rate: {_metrics.hit_rate:.2%}"
            )
        except Exception as e:
            _metrics.errors += 1
            logger.error(f"Fetch error: {e}")
            raise
    else:
        _metrics.hits += 1
        logger.debug(
            f"Cache hit: {len(_cache.tracks)} tracks. "
            f"Hit rate: {_metrics.hit_rate:.2%}"
        )

    return _cache.tracks

def get_cache_metrics() -> Dict[str, Any]:
    """Get current cache performance metrics."""
    global _metrics

    return {
        "hits": _metrics.hits,
        "misses": _metrics.misses,
        "hit_rate": f"{_metrics.hit_rate:.2%}",
        "refreshes": _metrics.refreshes,
        "errors": _metrics.errors,
        "avg_fetch_time_seconds": round(_metrics.avg_fetch_time, 2)
    }
```

---

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
import time

class TestUploadDecision:
    def test_replaygain_conflict_skip(self):
        azuracast = {"id": "1", "replaygain_track_gain": -3.5}
        source = {"Name": "Song"}

        assert should_skip_replaygain_conflict(azuracast, source) == True

    def test_both_have_replaygain_no_skip(self):
        azuracast = {"id": "1", "replaygain_track_gain": -3.5}
        source = {"Name": "Song", "ReplayGainTrackGain": -2.0}

        assert should_skip_replaygain_conflict(azuracast, source) == False

    def test_cache_hit(self):
        mock_fetch = Mock(return_value=[{"id": "1"}])

        # First call - miss
        tracks1 = get_cached_known_tracks(mock_fetch)
        assert mock_fetch.call_count == 1

        # Second call - hit
        tracks2 = get_cached_known_tracks(mock_fetch)
        assert mock_fetch.call_count == 1  # No additional call
        assert tracks1 == tracks2

    def test_cache_expiration(self):
        mock_fetch = Mock(side_effect=[
            [{"id": "1"}],
            [{"id": "2"}]
        ])

        # First call
        tracks1 = get_cached_known_tracks(mock_fetch, ttl_seconds=1)

        # Wait for expiration
        time.sleep(1.1)

        # Second call - expired, refetch
        tracks2 = get_cached_known_tracks(mock_fetch, ttl_seconds=1)

        assert mock_fetch.call_count == 2
        assert tracks1 != tracks2

    def test_force_refresh(self):
        mock_fetch = Mock(side_effect=[
            [{"id": "1"}],
            [{"id": "2"}]
        ])

        tracks1 = get_cached_known_tracks(mock_fetch)
        tracks2 = get_cached_known_tracks(mock_fetch, force_refresh=True)

        assert mock_fetch.call_count == 2
        assert tracks1 != tracks2

class TestCircuitBreaker:
    def test_opens_after_threshold(self):
        breaker = CacheCircuitBreaker(failure_threshold=3, timeout_seconds=10)

        assert breaker.can_attempt() == True

        # Record failures
        for _ in range(3):
            breaker.record_failure()

        assert breaker.can_attempt() == False  # Circuit open

    def test_recovers_after_timeout(self):
        breaker = CacheCircuitBreaker(failure_threshold=2, timeout_seconds=1)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.can_attempt() == False

        time.sleep(1.1)
        assert breaker.can_attempt() == True  # Timeout expired
```

---

## Summary

### Key Contracts

1. **should_skip_replaygain_conflict**: ReplayGain metadata preservation logic
2. **get_cached_known_tracks**: Efficient caching with TTL and manual invalidation

### Design Principles

- **Metadata Preservation**: Never replace good metadata with inferior metadata
- **Performance**: Reduce API calls by 90%+ with caching
- **Resilience**: Circuit breaker pattern for API failures
- **Observability**: Comprehensive metrics and logging

### Files to Create

```
src/azuracast/
├── upload_decision.py      # Upload logic and caching
├── cache.py               # Cache implementation
└── test_upload_decision.py # Test suite
```
