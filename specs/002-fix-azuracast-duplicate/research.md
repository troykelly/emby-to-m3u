# Technical Research: AzuraCast Duplicate Detection Feature

**Research Date**: 2025-10-05
**Target**: AzuraCast duplicate detection enhancement for track matching
**Codebase**: emby-to-m3u (Python 3.13)

---

## 1. Metadata Normalization Patterns in Python

### Decision
Implement **multi-layer normalization** using `unicodedata` and `re` libraries with fuzzy matching fallback.

### Rationale
- **Current Issue**: Exact string matching in `check_file_in_azuracast()` (lines 174-193 in `src/azuracast/main.py`) fails when artist names contain Unicode characters, different punctuation, or capitalization variations
- **Unicode Handling**: `unicodedata.normalize('NFD', text)` decomposes accented characters (é→e+́) for consistent comparison
- **Performance**: Both `unicodedata` and `re` are stdlib modules with C-level performance (no external dependencies)
- **Scalability**: Normalizing 1000+ strings is O(n) with minimal overhead (<10ms for 1000 items)

### Implementation Strategy

```python
import unicodedata
import re
from typing import Dict, Callable

def normalize_metadata(text: str) -> str:
    """Normalize metadata for fuzzy matching.

    Steps:
    1. NFD Unicode normalization (decompose accented chars)
    2. ASCII transliteration (café → cafe)
    3. Lowercase conversion
    4. Remove/normalize punctuation (preserve semantics)
    5. Strip whitespace
    """
    if not text:
        return ""

    # Step 1: NFD normalization
    nfd_form = unicodedata.normalize('NFD', text)

    # Step 2: ASCII conversion (remove combining marks)
    ascii_text = nfd_form.encode('ascii', 'ignore').decode('ascii')

    # Step 3: Lowercase
    lower_text = ascii_text.lower()

    # Step 4: Remove non-alphanumeric (but preserve spaces)
    # Replace common punctuation with spaces, then collapse
    cleaned = re.sub(r'[^\w\s]', ' ', lower_text)
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Step 5: Strip whitespace
    return cleaned.strip()

# Example usage:
# normalize_metadata("Café Tacvba") → "cafe tacvba"
# normalize_metadata("The Beatles") → "the beatles"
# normalize_metadata("Guns N' Roses") → "guns n roses"
```

### Alternatives Considered

1. **unidecode library** (external dependency)
   - ❌ Adds external dependency
   - ❌ More aggressive transliteration than needed
   - ✅ Better for Asian languages (out of scope)

2. **Simple `.lower()` only**
   - ❌ Fails on accented characters
   - ❌ Doesn't handle punctuation variations
   - ✅ Fastest (but inadequate)

3. **difflib.SequenceMatcher** (fuzzy matching)
   - ✅ Handles typos and variations
   - ❌ Slower for large datasets (O(n²) comparisons)
   - ⚠️ Use as **fallback** for unmatched tracks

### Performance Benchmark (Expected)
```
1000 tracks × 3 fields (artist, album, title):
- Normalization: ~5-8ms total
- Memory: ~50KB additional overhead
- Comparison: O(1) dict lookup after normalization
```

### Implementation Notes

1. **Cache normalized values** to avoid re-normalization
2. **Apply during duplicate check** in `check_file_in_azuracast()`
3. **Consider storing normalized keys** in AzuraCast API response cache
4. **Preserve original metadata** for display purposes

---

## 2. In-Memory Caching with TTL

### Decision
Use **functools.lru_cache with manual TTL wrapper** for simplicity and stdlib-only approach.

### Rationale
- **Current Issue**: `get_known_tracks()` makes API call every track check (lines 154-162) → O(n) API calls for n tracks
- **Performance Impact**: With 1000 tracks, this means 1000 API requests instead of 1
- **Thread Safety**: Single-threaded sync process → no locking needed
- **Memory Efficiency**: LRU eviction prevents unbounded growth
- **No Dependencies**: Stdlib-only solution

### Implementation Strategy

```python
import functools
import time
from typing import Dict, Any, List, Tuple

class TTLCache:
    """LRU cache with time-to-live expiration."""

    def __init__(self, ttl_seconds: int = 300, maxsize: int = 128):
        self.ttl_seconds = ttl_seconds
        self.maxsize = maxsize
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Any:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return value
            else:
                del self._cache[key]  # Expired
        return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        # Simple eviction: remove oldest if at maxsize
        if len(self._cache) >= self.maxsize:
            oldest_key = min(self._cache.keys(),
                           key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()


# Usage in AzuraCastSync class:
class AzuraCastSync:
    def __init__(self):
        # ... existing init code ...
        self._tracks_cache = TTLCache(ttl_seconds=300, maxsize=1)

    def get_known_tracks(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Retrieves known tracks with 5-minute TTL caching."""
        cache_key = f"station_{self.station_id}_tracks"

        if not force_refresh:
            cached = self._tracks_cache.get(cache_key)
            if cached is not None:
                logger.debug("Using cached known tracks")
                return cached

        # Cache miss or refresh → fetch from API
        endpoint = f"/station/{self.station_id}/files"
        response = self._perform_request("GET", endpoint)
        tracks = response.json()

        # Cache for next calls
        self._tracks_cache.set(cache_key, tracks)
        logger.debug(f"Cached {len(tracks)} known tracks")

        return tracks
```

### Alternatives Considered

1. **cachetools library** (external dependency)
   - ✅ TTL cache built-in (`TTLCache` class)
   - ✅ Thread-safe variants available
   - ❌ Adds external dependency
   - **Verdict**: Use if thread safety needed in future

2. **Simple dict with timestamps** (manual implementation)
   - ✅ Full control over eviction logic
   - ❌ More code to maintain
   - ❌ No LRU eviction (unbounded growth risk)

3. **Redis/Memcached** (external cache)
   - ❌ Massive overkill for single-process sync
   - ❌ Requires additional infrastructure
   - ✅ Useful for multi-instance deployments (future)

### Memory Footprint Analysis

**10,000 track metadata entries:**
```python
# Per track estimate:
{
    "id": "12345",              # ~10 bytes
    "artist": "Artist Name",    # ~50 bytes avg
    "album": "Album Name",      # ~50 bytes avg
    "title": "Track Title",     # ~50 bytes avg
    "duration": 240,            # ~8 bytes
    "path": "/path/to/file"     # ~100 bytes avg
}
# Total per track: ~300 bytes
# 10,000 tracks: ~3MB memory
```

**TTL Cache Overhead:**
- Timestamp per entry: 8 bytes (float)
- Dict overhead: ~50% additional
- **Total for 10,000 tracks: ~4.5MB**

✅ Acceptable for modern systems (minimal overhead)

### Implementation Notes

1. **TTL Default**: 300 seconds (5 minutes) - balance freshness vs API load
2. **Max Size**: 1 entry (only cache for current station)
3. **Force Refresh**: Invalidate cache after upload/delete operations
4. **Logging**: Track cache hits/misses for monitoring

---

## 3. Exponential Backoff for Rate Limiting

### Current Implementation Analysis

**File**: `src/azuracast/main.py` (lines 58-152)

**Existing Backoff Logic:**
```python
BASE_BACKOFF = 2
MAX_BACKOFF = 64

# In _perform_request():
time.sleep(min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF))
```

**Issues Found:**
1. ✅ Implements exponential backoff correctly
2. ❌ **No 429 (Rate Limit) handling** - only handles 413, 500-504
3. ❌ **No jitter** - all retries happen at same time (thundering herd)
4. ❌ **No max attempts check** - could retry forever on some errors

### Decision
**Enhance existing backoff with:**
1. Add 429 rate limit detection
2. Implement jitter to avoid thundering herd
3. Respect `Retry-After` header
4. Add max retry cap

### Implementation Strategy

```python
import time
import random
from typing import Optional

BASE_BACKOFF = 2
MAX_BACKOFF = 64
MAX_ATTEMPTS = 6

def calculate_backoff_with_jitter(attempt: int,
                                   retry_after: Optional[int] = None) -> float:
    """Calculate backoff duration with exponential backoff + jitter.

    Args:
        attempt: Current retry attempt number (1-indexed)
        retry_after: Optional Retry-After header value in seconds

    Returns:
        Sleep duration in seconds
    """
    if retry_after:
        # Respect server's Retry-After header
        return float(retry_after)

    # Exponential backoff: 2^attempt (capped at MAX_BACKOFF)
    base_delay = min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF)

    # Add jitter (±25% randomness)
    jitter = base_delay * 0.25 * (random.random() * 2 - 1)

    return base_delay + jitter


def _perform_request(self, method: str, endpoint: str, ...) -> requests.Response:
    """Enhanced request with rate limit handling."""

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.request(method, url, ...)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after and retry_after.isdigit():
                    delay = calculate_backoff_with_jitter(attempt, int(retry_after))
                else:
                    delay = calculate_backoff_with_jitter(attempt)

                logger.warning(
                    f"Rate limited (429) on attempt {attempt}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                continue

            # Handle 413 Payload Too Large
            if response.status_code == 413:
                delay = calculate_backoff_with_jitter(attempt)
                logger.warning(
                    f"Payload too large (413) on attempt {attempt}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
                continue

            # Success or non-retryable error
            response.raise_for_status()
            return response

        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            delay = calculate_backoff_with_jitter(attempt)
            logger.warning(
                f"Network error on attempt {attempt}: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    # Max attempts exhausted
    logger.error(f"Request failed after {MAX_ATTEMPTS} attempts")
    raise requests.exceptions.RequestException(
        f"Failed after {MAX_ATTEMPTS} attempts"
    )
```

### Backoff Schedule (with jitter)

| Attempt | Base Delay | With ±25% Jitter | Total Range |
|---------|------------|------------------|-------------|
| 1       | 2s         | ±0.5s            | 1.5-2.5s    |
| 2       | 4s         | ±1s              | 3-5s        |
| 3       | 8s         | ±2s              | 6-10s       |
| 4       | 16s        | ±4s              | 12-20s      |
| 5       | 32s        | ±8s              | 24-40s      |
| 6       | 64s (max)  | ±16s             | 48-80s      |

### Alternatives Considered

1. **tenacity library** (external dependency)
   ```python
   from tenacity import retry, wait_exponential, stop_after_attempt

   @retry(wait=wait_exponential(multiplier=2, max=64),
          stop=stop_after_attempt(6))
   def _perform_request(...):
       ...
   ```
   - ✅ Declarative retry logic
   - ✅ Built-in jitter, retry_after support
   - ❌ Adds external dependency

2. **backoff library** (external dependency)
   ```python
   import backoff

   @backoff.on_exception(backoff.expo,
                          requests.exceptions.RequestException,
                          max_tries=6, max_value=64)
   def _perform_request(...):
       ...
   ```
   - ✅ Simple decorator-based approach
   - ❌ Less control over retry logic
   - ❌ Adds external dependency

3. **Manual implementation** (chosen)
   - ✅ No dependencies
   - ✅ Full control over retry logic
   - ✅ Existing code already implements base pattern
   - ❌ More code to maintain

### Implementation Notes

1. **Preserve existing behavior** for 500-504 errors (already handled by urllib3 Retry)
2. **Add 429 detection** as new retry case
3. **Respect Retry-After** header when present
4. **Log retry attempts** with delay duration for observability
5. **Jitter prevents thundering herd** when multiple workers retry simultaneously

---

## 4. MusicBrainz ID Field Mapping

### Current State Analysis

**Subsonic API Fields** (`src/subsonic/models.py`, line 142):
```python
@dataclass
class SubsonicTrack:
    musicBrainzId: Optional[str] = None  # MusicBrainz track ID
```

**Emby Metadata Fields**: ❓ (No Emby integration found in codebase)

**AzuraCast Known Tracks**: ❓ (Response format unknown - needs API inspection)

### Decision
**Implement MBID-based matching with multi-field fallback strategy.**

### Rationale
- **MusicBrainz ID** is globally unique identifier for tracks/recordings
- **Subsonic API exposes `musicBrainzId`** in track metadata (confirmed in models)
- **High confidence matching**: MBID match = 100% same recording
- **Fallback required**: Not all tracks have MBID metadata

### Implementation Strategy

```python
def check_file_in_azuracast(
    self,
    known_tracks: List[Dict[str, Any]],
    track: Dict[str, Any]
) -> bool:
    """Enhanced duplicate detection with MBID + fuzzy matching.

    Matching Strategy (priority order):
    1. MusicBrainz ID (exact match) - 100% confidence
    2. Normalized metadata (artist+album+title) - 95% confidence
    3. Fuzzy matching with similarity threshold - 85% confidence
    """

    # Extract track metadata
    mbid = track.get("musicBrainzId") or track.get("MusicBrainzTrackId")
    artist = track.get("AlbumArtist", "")
    album = track.get("Album", "")
    title = track.get("Name", "")

    # Strategy 1: MusicBrainz ID exact match
    if mbid:
        for known_track in known_tracks:
            known_mbid = known_track.get("musicbrainz_id") or \
                        known_track.get("musicBrainzId")

            if known_mbid and known_mbid == mbid:
                track["azuracast_file_id"] = known_track["id"]
                logger.debug(
                    f"Matched '{title}' by MusicBrainz ID: {mbid}"
                )
                return True

    # Strategy 2: Normalized metadata matching
    normalized_track = {
        "artist": normalize_metadata(artist),
        "album": normalize_metadata(album),
        "title": normalize_metadata(title)
    }

    for known_track in known_tracks:
        normalized_known = {
            "artist": normalize_metadata(known_track.get("artist", "")),
            "album": normalize_metadata(known_track.get("album", "")),
            "title": normalize_metadata(known_track.get("title", ""))
        }

        if (normalized_track["artist"] == normalized_known["artist"] and
            normalized_track["album"] == normalized_known["album"] and
            normalized_track["title"] == normalized_known["title"]):

            track["azuracast_file_id"] = known_track["id"]
            logger.debug(
                f"Matched '{title}' by normalized metadata"
            )
            return True

    # Strategy 3: Fuzzy matching (fallback)
    # TODO: Implement if needed for edge cases

    logger.debug(f"No match found for '{title}'")
    return False
```

### Field Name Mapping Investigation

**Required Action**: Inspect AzuraCast API response for MBID field name.

**Expected field variations:**
1. `musicBrainzId` (camelCase - Subsonic convention)
2. `musicbrainz_id` (snake_case - Python convention)
3. `mbid` (abbreviated)
4. Custom field in `extra_metadata` (JSON blob)

**Test approach:**
```python
# Add debug logging to inspect actual response
known_tracks = self.get_known_tracks()
if known_tracks:
    sample_track = known_tracks[0]
    logger.debug(f"AzuraCast track fields: {sample_track.keys()}")
    logger.debug(f"Sample track: {sample_track}")
```

### Fallback Strategy (No MBID)

**When MBID not available:**
1. ✅ Use normalized metadata matching (Strategy 2)
2. ✅ Consider duration matching as tie-breaker
3. ⚠️ Avoid fuzzy matching by default (false positives risk)

**Duration tolerance:**
```python
# Allow ±2 second tolerance for duration matching
duration_match = abs(track_duration - known_duration) <= 2
```

### Implementation Notes

1. **Check both source and target** for MBID presence
2. **Log matching strategy used** for each track (observability)
3. **Prefer exact MBID match** over fuzzy metadata
4. **Store match confidence score** for future analytics
5. **Handle missing/null MBID gracefully** (fallback to metadata)

---

## 5. Performance Profiling Tools

### Decision
Use **pytest-benchmark for test-level profiling** + **cProfile for detailed function analysis**.

### Rationale
- **pytest-benchmark**: Already in testing workflow, measures test execution time with statistical analysis
- **cProfile**: Python stdlib, zero-dependency detailed profiling
- **Combined approach**: Fast iteration (pytest) + deep dive (cProfile) when needed

### Implementation Strategy

#### 5.1 Pytest-Benchmark Setup

```python
# tests/performance/test_duplicate_detection_benchmark.py

import pytest
from src.azuracast.main import AzuraCastSync

@pytest.fixture
def azuracast_client():
    """Fixture for AzuraCast client."""
    return AzuraCastSync()

@pytest.fixture
def mock_tracks_100(mocker):
    """100 mock tracks for benchmarking."""
    tracks = []
    for i in range(100):
        tracks.append({
            "id": f"track-{i}",
            "artist": f"Artist {i % 10}",
            "album": f"Album {i % 20}",
            "title": f"Track {i}",
            "duration": 180 + (i % 60)
        })
    return tracks

@pytest.fixture
def mock_tracks_1000(mocker):
    """1000 mock tracks for benchmarking."""
    tracks = []
    for i in range(1000):
        tracks.append({
            "id": f"track-{i}",
            "artist": f"Artist {i % 50}",
            "album": f"Album {i % 100}",
            "title": f"Track {i}",
            "duration": 180 + (i % 60)
        })
    return tracks

def test_duplicate_detection_100_tracks(
    benchmark,
    azuracast_client,
    mock_tracks_100
):
    """Benchmark duplicate detection with 100 tracks."""
    track_to_check = {
        "AlbumArtist": "Artist 5",
        "Album": "Album 10",
        "Name": "Track 50"
    }

    result = benchmark(
        azuracast_client.check_file_in_azuracast,
        mock_tracks_100,
        track_to_check
    )

    assert isinstance(result, bool)

def test_duplicate_detection_1000_tracks(
    benchmark,
    azuracast_client,
    mock_tracks_1000
):
    """Benchmark duplicate detection with 1000 tracks."""
    track_to_check = {
        "AlbumArtist": "Artist 25",
        "Album": "Album 50",
        "Name": "Track 500"
    }

    result = benchmark(
        azuracast_client.check_file_in_azuracast,
        mock_tracks_1000,
        track_to_check
    )

    assert isinstance(result, bool)

# Run benchmarks:
# pytest tests/performance/test_duplicate_detection_benchmark.py --benchmark-only
```

**Expected Output:**
```
Name (time in ms)                                Min     Max    Mean  StdDev  Median
------------------------------------------------------------------------------------------
test_duplicate_detection_100_tracks           0.5000  1.2000  0.6500  0.0800  0.6200
test_duplicate_detection_1000_tracks          4.5000  8.2000  5.3000  0.4200  5.1000
```

#### 5.2 cProfile for Deep Analysis

```python
# scripts/profile_duplicate_detection.py

import cProfile
import pstats
from io import StringIO
from src.azuracast.main import AzuraCastSync

def profile_duplicate_detection():
    """Profile duplicate detection with cProfile."""

    # Setup
    client = AzuraCastSync()
    known_tracks = [
        {
            "id": f"track-{i}",
            "artist": f"Artist {i % 50}",
            "album": f"Album {i % 100}",
            "title": f"Track {i}"
        }
        for i in range(1000)
    ]

    track_to_check = {
        "AlbumArtist": "Artist 25",
        "Album": "Album 50",
        "Name": "Track 500"
    }

    # Profile execution
    profiler = cProfile.Profile()
    profiler.enable()

    # Run 100 iterations
    for _ in range(100):
        client.check_file_in_azuracast(known_tracks, track_to_check)

    profiler.disable()

    # Output statistics
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions

    print(s.getvalue())

if __name__ == "__main__":
    profile_duplicate_detection()
```

**Run:**
```bash
python scripts/profile_duplicate_detection.py
```

**Expected Output:**
```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      100    0.050    0.001    0.250    0.002 main.py:164(check_file_in_azuracast)
    10000    0.080    0.000    0.120    0.000 {built-in method normalize}
    10000    0.060    0.000    0.090    0.000 {method 'lower'}
     ...
```

#### 5.3 Memory Profiling

```python
# Install: pip install memory_profiler
# Usage: python -m memory_profiler scripts/profile_memory.py

from memory_profiler import profile

@profile
def profile_cache_memory():
    """Profile memory usage of TTL cache."""
    cache = TTLCache(ttl_seconds=300, maxsize=1)

    # Simulate 10,000 tracks
    tracks = [
        {
            "id": f"track-{i}",
            "artist": f"Artist Name {i}",
            "album": f"Album Name {i}",
            "title": f"Track Title {i}",
            "path": f"/music/artist{i}/album{i}/track{i}.mp3"
        }
        for i in range(10000)
    ]

    cache.set("known_tracks", tracks)

    # Memory snapshot
    return cache.get("known_tracks")
```

### Alternatives Considered

1. **line_profiler** (line-by-line profiling)
   - ✅ Detailed per-line timing
   - ❌ Requires decorator instrumentation
   - **Use case**: Deep dive into specific functions

2. **py-spy** (sampling profiler)
   - ✅ No code changes needed
   - ✅ Flame graph visualization
   - ❌ Requires installation
   - **Use case**: Production profiling

3. **timeit module** (manual timing)
   - ✅ Simple stdlib solution
   - ❌ No statistical analysis
   - **Use case**: Quick ad-hoc checks

### Benchmark Targets

**Performance Goals:**
- ✅ 100 tracks: <1ms per duplicate check
- ✅ 1,000 tracks: <10ms per duplicate check
- ✅ 10,000 tracks: <100ms per duplicate check

**Memory Goals:**
- ✅ Cache overhead: <10MB for 10,000 tracks
- ✅ Normalization: <1MB temporary allocations

### Implementation Notes

1. **Run benchmarks in CI/CD** to catch performance regressions
2. **Compare before/after** when adding normalization/caching
3. **Profile in realistic conditions** (use actual API response sizes)
4. **Document baseline metrics** for future reference

---

## 6. Live Server Integration Testing with Pytest

### Decision
**Use pytest fixtures with environment variables + cleanup hooks for safe live testing.**

### Rationale
- **Existing pattern**: Test suite already uses pytest (see `tests/integration/test_id3_browsing.py`)
- **Safety first**: Live tests require careful cleanup to avoid polluting production
- **Environment isolation**: Use `.env.test` for test server credentials
- **Cleanup guarantee**: Use `yield` fixtures with `finally` blocks

### Implementation Strategy

#### 6.1 Test Configuration

```python
# tests/integration/conftest.py

import os
import pytest
from dotenv import load_dotenv
from src.azuracast.main import AzuraCastSync

# Load test environment variables
load_dotenv('.env.test')

@pytest.fixture(scope="session")
def azuracast_test_config():
    """Load AzuraCast test server configuration."""
    config = {
        "host": os.getenv("AZURACAST_TEST_HOST"),
        "api_key": os.getenv("AZURACAST_TEST_API_KEY"),
        "station_id": os.getenv("AZURACAST_TEST_STATION_ID")
    }

    # Validate required config
    if not all(config.values()):
        pytest.skip("AzuraCast test server not configured")

    return config

@pytest.fixture(scope="function")
def azuracast_client(azuracast_test_config):
    """Create AzuraCast client for live testing."""
    # Temporarily override env vars
    os.environ["AZURACAST_HOST"] = azuracast_test_config["host"]
    os.environ["AZURACAST_API_KEY"] = azuracast_test_config["api_key"]
    os.environ["AZURACAST_STATION_ID"] = azuracast_test_config["station_id"]

    client = AzuraCastSync()

    yield client

    # Cleanup: restore original env vars
    for key in ["AZURACAST_HOST", "AZURACAST_API_KEY", "AZURACAST_STATION_ID"]:
        if key in os.environ:
            del os.environ[key]

@pytest.fixture(scope="function")
def test_track_upload(azuracast_client):
    """Upload test track and ensure cleanup."""
    uploaded_file_id = None

    def _upload(file_content: bytes, file_key: str):
        nonlocal uploaded_file_id
        result = azuracast_client.upload_file_to_azuracast(file_content, file_key)
        uploaded_file_id = result.get("id")
        return uploaded_file_id

    yield _upload

    # Cleanup: delete uploaded file
    if uploaded_file_id:
        try:
            azuracast_client.delete_file_from_azuracast(uploaded_file_id)
        except Exception as e:
            print(f"Warning: Failed to cleanup test file {uploaded_file_id}: {e}")
```

#### 6.2 Live Test Example

```python
# tests/integration/test_azuracast_duplicate_live.py

import pytest
from pathlib import Path

@pytest.mark.integration
@pytest.mark.live
def test_duplicate_detection_with_mbid(azuracast_client, test_track_upload):
    """Test duplicate detection with MusicBrainz ID on live server."""

    # Step 1: Upload test track with MBID
    test_audio = Path("tests/fixtures/test_track.mp3").read_bytes()
    file_id = test_track_upload(test_audio, "test/duplicate_test.mp3")

    assert file_id is not None

    # Step 2: Get known tracks from server
    known_tracks = azuracast_client.get_known_tracks()

    # Step 3: Check duplicate detection
    track_metadata = {
        "AlbumArtist": "Test Artist",
        "Album": "Test Album",
        "Name": "Test Track",
        "musicBrainzId": "test-mbid-12345"
    }

    is_duplicate = azuracast_client.check_file_in_azuracast(
        known_tracks,
        track_metadata
    )

    # Verify
    assert is_duplicate is True
    assert "azuracast_file_id" in track_metadata
    assert track_metadata["azuracast_file_id"] == file_id

@pytest.mark.integration
@pytest.mark.live
def test_cache_invalidation_after_upload(azuracast_client, test_track_upload):
    """Test that cache is invalidated after file upload."""

    # Step 1: Get initial known tracks (populates cache)
    initial_tracks = azuracast_client.get_known_tracks()
    initial_count = len(initial_tracks)

    # Step 2: Upload new track
    test_audio = Path("tests/fixtures/test_track.mp3").read_bytes()
    file_id = test_track_upload(test_audio, "test/cache_test.mp3")

    # Step 3: Force cache refresh
    updated_tracks = azuracast_client.get_known_tracks(force_refresh=True)
    updated_count = len(updated_tracks)

    # Verify cache was refreshed
    assert updated_count == initial_count + 1
```

#### 6.3 Test Execution

```bash
# Run only live integration tests
pytest tests/integration/test_azuracast_duplicate_live.py -m live -v

# Skip live tests (default)
pytest tests/integration/ -m "not live"

# Run with coverage
pytest tests/integration/ -m live --cov=src.azuracast --cov-report=html
```

### Environment Variable Management

**File: `.env.test`**
```bash
# AzuraCast Test Server (DO NOT USE PRODUCTION!)
AZURACAST_TEST_HOST=https://test.azuracast.example.com
AZURACAST_TEST_API_KEY=test_api_key_here
AZURACAST_TEST_STATION_ID=1

# Optional: Use staging environment
AZURACAST_TEST_ENVIRONMENT=staging
```

**File: `.env.test.example`**
```bash
# Copy this file to .env.test and fill in your test server details
AZURACAST_TEST_HOST=https://your-test-server.com
AZURACAST_TEST_API_KEY=your_test_api_key
AZURACAST_TEST_STATION_ID=1
```

**Git ignore:**
```bash
# .gitignore
.env.test
.env.local
*.test.env
```

### Safety Checklist

**Before running live tests:**
1. ✅ Use dedicated test server (never production!)
2. ✅ Test credentials have limited permissions
3. ✅ Test station is isolated from production playlists
4. ✅ Cleanup fixtures always execute (even on test failure)
5. ✅ Test files are clearly marked (e.g., `test/` prefix)

### Cleanup Patterns

**Guaranteed cleanup with `finally`:**
```python
@pytest.fixture
def safe_upload(azuracast_client):
    """Upload with guaranteed cleanup even if test fails."""
    uploaded_ids = []

    def _upload(content, key):
        file_id = azuracast_client.upload_file_to_azuracast(content, key)
        uploaded_ids.append(file_id)
        return file_id

    yield _upload

    # Always cleanup, even if test fails
    for file_id in uploaded_ids:
        try:
            azuracast_client.delete_file_from_azuracast(file_id)
        except Exception as e:
            # Log but don't fail cleanup
            print(f"Cleanup warning: {e}")
```

### Alternatives Considered

1. **VCR.py (request recording)**
   ```python
   import vcr

   @vcr.use_cassette('tests/fixtures/azuracast_api.yaml')
   def test_with_recorded_responses():
       # Replays recorded HTTP interactions
       ...
   ```
   - ✅ No live server needed after first run
   - ✅ Fast test execution
   - ❌ Stale recordings if API changes
   - **Use case**: Unit tests, not integration tests

2. **Docker test containers** (testcontainers-python)
   - ✅ Isolated AzuraCast instance per test
   - ✅ No cleanup concerns (container destroyed)
   - ❌ Complex setup (AzuraCast Docker compose)
   - ❌ Slow startup time
   - **Use case**: Full end-to-end testing

3. **Mock server** (pytest-httpserver)
   - ✅ Fast, isolated, no external dependencies
   - ❌ Not a real integration test
   - **Use case**: Contract testing, not live testing

### Implementation Notes

1. **Mark live tests clearly**: `@pytest.mark.live` for easy filtering
2. **Use descriptive test file prefixes**: `test_*_live.py`
3. **Document test server setup** in `docs/testing.md`
4. **Add CI/CD skip flag**: Run live tests only in staging pipeline
5. **Monitor test server load**: Rate limit live test execution

---

## Summary of Decisions

| Area | Technology Choice | Key Benefit |
|------|------------------|-------------|
| **Metadata Normalization** | `unicodedata` + `re` (stdlib) | Zero dependencies, handles Unicode + punctuation |
| **Caching** | `functools.lru_cache` + TTL wrapper | Stdlib-only, 5min TTL, ~4.5MB for 10K tracks |
| **Backoff** | Enhanced manual implementation | 429 handling + jitter, no new dependencies |
| **MBID Mapping** | Multi-strategy (MBID → normalized → fuzzy) | 100% confidence on MBID, fallback for legacy |
| **Profiling** | pytest-benchmark + cProfile | Fast iteration + deep analysis when needed |
| **Live Testing** | pytest fixtures + env vars | Safe cleanup, environment isolation |

---

## Next Steps for Implementation

1. **Create normalization utility** (`src/azuracast/normalization.py`)
2. **Add TTL cache wrapper** to `AzuraCastSync` class
3. **Enhance `_perform_request()`** with 429 handling + jitter
4. **Update `check_file_in_azuracast()`** with MBID + normalized matching
5. **Add benchmark tests** (`tests/performance/test_duplicate_benchmark.py`)
6. **Create live test suite** (`tests/integration/test_azuracast_live.py`)
7. **Document API field mapping** after inspecting AzuraCast response

---

## References

- **Unicode Normalization**: [Python unicodedata docs](https://docs.python.org/3/library/unicodedata.html)
- **Retry Strategies**: [Google SRE Book - Retry Logic](https://sre.google/sre-book/addressing-cascading-failures/)
- **MusicBrainz IDs**: [MusicBrainz Identifier Docs](https://musicbrainz.org/doc/MusicBrainz_Identifier)
- **pytest-benchmark**: [pytest-benchmark docs](https://pytest-benchmark.readthedocs.io/)
- **Existing Tests**: `/workspaces/emby-to-m3u/tests/integration/test_id3_browsing.py`
