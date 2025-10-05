# Subsonic API v1.16.1 Integration Research

## Document Information
- **Date**: 2025-10-05
- **Purpose**: Research and analysis for implementing Subsonic API integration into emby-to-m3u
- **Target API Version**: Subsonic v1.16.1 (Subsonic 6.1.4)
- **Performance Target**: Process 5000 tracks in under 60 seconds

---

## 1. Subsonic API v1.16.1 Specification

### 1.1 Authentication Methods

#### Token-Based Authentication (Recommended - Since v1.13.0)
**Decision**: Use token-based authentication as the primary method.

**Rationale**:
- More secure than plaintext password transmission
- Prevents password exposure in logs and network traffic
- Compatible with all modern Subsonic implementations (Navidrome, Airsonic, Gonic)

**Implementation Details**:
```python
import hashlib
import random
import string

def generate_auth_token(password: str, salt: str = None) -> tuple[str, str]:
    """
    Generate Subsonic authentication token.

    Args:
        password: User's password
        salt: Random salt (auto-generated if None)

    Returns:
        Tuple of (token, salt)
    """
    if salt is None:
        salt = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

    token = hashlib.md5(f"{password}{salt}".encode()).hexdigest()
    return token, salt
```

**Required Parameters**:
- `u`: Username (required)
- `t`: Authentication token = md5(password + salt)
- `s`: Random salt string
- `v`: Protocol version (1.16.1)
- `c`: Client application identifier (e.g., "emby-to-m3u")
- `f`: Response format ("json" recommended)

**Alternative**: Legacy Authentication (Pre-1.13.0)
- Clear text password: `p=password`
- Hex-encoded password: `p=enc:HEX(password)`
- **Not recommended** due to security concerns

### 1.2 Key Endpoints for Integration

#### System Endpoints
1. **ping** - Connectivity test
   - Purpose: Validate credentials and server availability
   - Parameters: Authentication only
   - Response: Status and API version
   - Use case: Initial connection validation

2. **getLicense** - Server license info
   - Purpose: Verify server capabilities
   - Optional for basic integration

#### Browsing Endpoints
1. **getMusicDirectory** - Get directory contents
   - Parameters: `id` (directory ID)
   - Returns: Child entries (albums, tracks)
   - Use case: Navigate music hierarchy

2. **getIndexes** - Get artist indexes
   - Returns: Artists organized alphabetically
   - Use case: Discover all artists

#### Search Endpoints
1. **search3** (Recommended - Since v1.8.0)
   - Parameters:
     - `query`: Search query string
     - `artistCount`: Max artists (default: 20)
     - `albumCount`: Max albums (default: 20)
     - `songCount`: Max songs (default: 20)
     - `artistOffset`: Artist result offset
     - `albumOffset`: Album result offset
     - `songOffset`: Song result offset
   - Returns: Structured search results
   - Use case: Find tracks by title, artist, album

2. **search2** (Legacy - v1.4.0+)
   - Simplified version with artist/album/song separation
   - Fallback for older servers

#### Media Retrieval Endpoints
1. **getSongs** - Get songs by criteria
   - Parameters:
     - `type`: "random", "newest", "highest", "frequent", "recent"
     - `size`: Number of songs (default: 10, max: 500)
     - `fromYear`: Filter by year
     - `toYear`: Filter by year
     - `genre`: Filter by genre
     - `musicFolderId`: Limit to folder
   - Use case: Batch track retrieval

2. **getAlbumList2** - Get albums
   - Parameters:
     - `type`: "random", "newest", "alphabeticalByName", etc.
     - `size`: Number of albums (default: 10, max: 500)
     - `offset`: Result offset
   - Use case: Album-based discovery

3. **stream** - Stream audio
   - Parameters:
     - `id`: Track ID (required)
     - `maxBitRate`: Max bitrate in kbps
     - `format`: Target format (transcoding)
     - `timeOffset`: Start position in seconds
   - Returns: Audio file binary stream
   - Use case: Generate streaming URLs for M3U playlists

### 1.3 Pagination Parameters and Limits

**Standard Pagination Pattern**:
- `size` or `count`: Maximum number of results (typically 10-500)
- `offset`: Starting position in result set (0-based)
- Server-imposed limits vary by implementation

**Best Practices**:
```python
DEFAULT_PAGE_SIZE = 500  # Maximum for most endpoints
MAX_RETRIES = 3

async def fetch_all_songs_paginated(client, genre: str = None):
    """Fetch all songs with pagination."""
    offset = 0
    all_songs = []

    while True:
        response = await client.get_songs(
            type="alphabeticalByName",
            size=DEFAULT_PAGE_SIZE,
            offset=offset,
            genre=genre
        )

        songs = response.get('song', [])
        if not songs:
            break

        all_songs.extend(songs)

        # Check if we got fewer results than requested (last page)
        if len(songs) < DEFAULT_PAGE_SIZE:
            break

        offset += DEFAULT_PAGE_SIZE

    return all_songs
```

**Performance Optimization**:
- Use maximum page size (500) to minimize API calls
- Implement parallel pagination for multiple genres/categories
- Cache results to avoid redundant API calls

### 1.4 Response Formats

**JSON Format (Recommended)**:
- Parameter: `f=json`
- Content-Type: `application/json`
- Easier to parse and handle

**XML Format (Default)**:
- Default if `f` parameter not specified
- Content-Type: `text/xml`
- Legacy format, more verbose

**JSONP Format** (Since v1.6.0):
- Parameter: `f=jsonp&callback=functionName`
- For cross-domain browser requests
- Not needed for server-side integration

### 1.5 Error Response Formats

**Error Structure** (JSON):
```json
{
  "subsonic-response": {
    "status": "failed",
    "version": "1.16.1",
    "error": {
      "code": 40,
      "message": "Wrong username or password"
    }
  }
}
```

**Common Error Codes**:
| Code | Description | Retry Strategy |
|------|-------------|----------------|
| 0 | Generic error | Investigate message |
| 10 | Required parameter missing | Fix request |
| 20 | Incompatible client version | Update version param |
| 30 | Incompatible server version | Fallback to older endpoints |
| 40 | Wrong username/password | Re-authenticate, fail after retries |
| 41 | Token authentication not supported | Fallback to legacy auth |
| 50 | User not authorized | Check permissions, fail |
| 60 | Trial period over | Notify user |
| 70 | Requested data not found | Handle gracefully, skip item |

**Error Handling Strategy**:
```python
class SubsonicError(Exception):
    """Base exception for Subsonic API errors."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Subsonic Error {code}: {message}")

def handle_subsonic_response(response_data: dict):
    """Parse and handle Subsonic API response."""
    subsonic_response = response_data.get('subsonic-response', {})

    if subsonic_response.get('status') == 'failed':
        error = subsonic_response.get('error', {})
        code = error.get('code', 0)
        message = error.get('message', 'Unknown error')

        # Determine if retryable
        retryable_codes = {0, 30, 40, 70}  # Generic, server version, auth, not found

        raise SubsonicError(code, message)

    return subsonic_response
```

---

## 2. Subsonic Implementation Differences

### 2.1 Navidrome

**Strengths**:
- Full Subsonic API compatibility (v1.16.1)
- Excellent performance with large libraries (100k+ tracks)
- Modern Go implementation with fast metadata reading
- Supports transcoding on-the-fly with Opus support

**Known Quirks**:
- Strict API version checking (must specify v=1.16.1 or compatible)
- Case-sensitive genre matching
- Album/Artist disambiguation by MusicBrainz ID

**Best Practices**:
- Use search3 endpoint for optimal performance
- Leverage MusicBrainz IDs when available
- Enable JSON format (f=json) for faster parsing

### 2.2 Airsonic / Airsonic-Advanced

**Strengths**:
- Full backward compatibility with Subsonic
- Active development (Airsonic-Advanced fork)
- Supports additional metadata fields

**Known Quirks**:
- Some extended endpoints not in official spec
- Genre handling may differ slightly from Subsonic
- Playlist synchronization has specific format requirements

**Best Practices**:
- Test pagination behavior (some versions have different limits)
- Verify genre string format matches server expectations
- Use getAlbumList2/getSongs for batch operations

### 2.3 Gonic

**Strengths**:
- Lightweight, minimal resource usage
- Good for embedded systems
- Compatible with core Subsonic API

**Known Quirks**:
- Limited transcoding support compared to Navidrome
- May not support all extended metadata fields
- Simpler search implementation

**Best Practices**:
- Stick to core API endpoints (ping, search3, stream)
- Don't rely on extended metadata
- Test pagination limits (may be lower than 500)

### 2.4 Multi-Implementation Support Strategy

**Decision**: Design for lowest common denominator with graceful degradation.

**Implementation Approach**:
```python
class SubsonicClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.capabilities = {}

    async def detect_capabilities(self):
        """Detect server capabilities via ping."""
        response = await self.ping()
        version = response.get('version', '1.0.0')
        self.capabilities['version'] = version

        # Test token auth support
        try:
            await self.ping(use_token_auth=True)
            self.capabilities['token_auth'] = True
        except SubsonicError as e:
            if e.code == 41:
                self.capabilities['token_auth'] = False

    async def get_songs_safe(self, **kwargs):
        """Get songs with fallback logic."""
        try:
            return await self.get_songs(**kwargs)
        except SubsonicError as e:
            if e.code == 30:  # Unsupported version
                # Fallback to older endpoint
                return await self.search2(query="*", songCount=500)
            raise
```

**Compatibility Matrix**:
| Feature | Navidrome | Airsonic | Gonic | Strategy |
|---------|-----------|----------|-------|----------|
| Token Auth | ✅ | ✅ | ✅ | Primary |
| JSON Format | ✅ | ✅ | ✅ | Primary |
| search3 | ✅ | ✅ | ✅ | Primary |
| getSongs | ✅ | ✅ | ⚠️ | Use with fallback |
| Transcoding | ✅ Full | ✅ Full | ⚠️ Limited | Detect capabilities |
| MusicBrainz IDs | ✅ | ✅ | ❌ | Optional enhancement |

---

## 3. Metadata Mapping (Subsonic → Track Model)

### 3.1 Field Mapping Table

Based on existing Track model in `/workspaces/emby-to-m3u/src/track/main.py`:

| Emby Field | Subsonic Field | Type | Transformation | Notes |
|------------|---------------|------|----------------|-------|
| Id | id | string | Direct | Unique track identifier |
| Name | title | string | Direct | Track title |
| Album | album | string | Direct | Album name |
| AlbumArtist | artist | string | Direct | Primary artist |
| Genres | genre | string → array | Split by comma/space | Subsonic uses single genre string |
| IndexNumber | track | int | Direct | Track number in album |
| ParentIndexNumber | discNumber | int | Direct (default: 1) | Disc number |
| ProductionYear | year | int | Direct | Release year |
| Path | path | string | Construct from stream URL | Server-specific file path |
| RunTimeTicks | duration | int → ticks | `duration * 10000000` | Subsonic: seconds, Emby: 100ns ticks |
| PremiereDate | created | ISO8601 | Parse to datetime | Track creation date |
| MusicBrainzAlbumId | albumId (if UUID) | string | Direct | Optional |
| MusicBrainzArtistId | artistId (if UUID) | string | Direct | Optional |
| ProviderIds | N/A | dict | Custom mapping | Extended metadata |

### 3.2 Subsonic Song Schema (JSON)

```json
{
  "id": "300",
  "parent": "200",
  "isDir": false,
  "title": "Song Title",
  "album": "Album Name",
  "artist": "Artist Name",
  "track": 5,
  "year": 2008,
  "genre": "Rock",
  "coverArt": "300",
  "size": 8421341,
  "contentType": "audio/mpeg",
  "suffix": "mp3",
  "duration": 235,
  "bitRate": 128,
  "path": "artist/album/05 - Song Title.mp3",
  "albumId": "200",
  "artistId": "100",
  "type": "music",
  "created": "2023-01-15T10:30:00.000Z"
}
```

### 3.3 Required Transformations

#### Genre String → Array Transformation
**Subsonic**: Single string (may contain multiple genres separated by delimiters)
**Emby**: Array of strings

```python
def parse_subsonic_genre(genre_str: str) -> list[str]:
    """
    Parse Subsonic genre string into array.

    Handles multiple formats:
    - "Rock" → ["Rock"]
    - "Rock, Jazz" → ["Rock", "Jazz"]
    - "Rock; Jazz; Blues" → ["Rock", "Jazz", "Blues"]
    - "Rock / Metal" → ["Rock", "Metal"]
    """
    if not genre_str:
        return []

    # Try common delimiters
    for delimiter in [';', ',', '/', '|']:
        if delimiter in genre_str:
            return [g.strip() for g in genre_str.split(delimiter) if g.strip()]

    # Single genre
    return [genre_str.strip()]
```

#### Duration → RunTimeTicks Transformation
**Subsonic**: Integer (seconds)
**Emby**: Integer (100-nanosecond ticks)

```python
def duration_to_ticks(duration_seconds: int) -> int:
    """
    Convert Subsonic duration (seconds) to Emby RunTimeTicks.

    1 tick = 100 nanoseconds
    1 second = 10,000,000 ticks
    """
    return duration_seconds * 10_000_000
```

#### Stream URL → Path Construction
**Subsonic**: Stream via API endpoint
**Emby**: Local file path

```python
def construct_stream_path(base_url: str, track_id: str, auth_params: dict) -> str:
    """
    Construct Subsonic stream URL as Path.

    Format: {base_url}/rest/stream?id={id}&u={u}&t={t}&s={s}&v=1.16.1&c=emby-to-m3u&f=raw
    """
    params = {
        'id': track_id,
        'v': '1.16.1',
        'c': 'emby-to-m3u',
        'f': 'raw',  # Raw audio, no transcoding
        **auth_params
    }

    query_string = '&'.join(f"{k}={v}" for k, v in params.items())
    return f"{base_url}/rest/stream?{query_string}"
```

### 3.4 Handling Missing/Optional Fields

**Strategy**: Use sensible defaults and mark as optional

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class SubsonicTrack:
    """Normalized Subsonic track data."""
    id: str
    title: str
    album: str
    artist: str
    duration: int
    genre: list[str]

    # Optional fields with defaults
    track_number: Optional[int] = None
    disc_number: int = 1
    year: Optional[int] = None
    path: Optional[str] = None
    album_id: Optional[str] = None
    artist_id: Optional[str] = None
    cover_art_id: Optional[str] = None
    bitrate: Optional[int] = None
    content_type: Optional[str] = None
    created: Optional[str] = None

    def to_emby_track(self, base_url: str, auth_params: dict) -> dict:
        """Convert to Emby Track format."""
        return {
            'Id': self.id,
            'Name': self.title,
            'Album': self.album,
            'AlbumArtist': self.artist,
            'Genres': self.genre,
            'IndexNumber': self.track_number or 0,
            'ParentIndexNumber': self.disc_number,
            'ProductionYear': self.year,
            'Path': construct_stream_path(base_url, self.id, auth_params),
            'RunTimeTicks': duration_to_ticks(self.duration),
            'PremiereDate': self.created,
            'MusicBrainzAlbumId': self.album_id if self._is_uuid(self.album_id) else None,
            'MusicBrainzArtistId': self.artist_id if self._is_uuid(self.artist_id) else None,
        }

    @staticmethod
    def _is_uuid(value: Optional[str]) -> bool:
        """Check if string is a valid UUID (likely MusicBrainz ID)."""
        if not value:
            return False
        import re
        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
        return bool(uuid_pattern.match(value))
```

---

## 4. Authentication Patterns

### 4.1 MD5 Salt+Hash Token Generation Algorithm

**Implementation**:
```python
import hashlib
import secrets
import string

def generate_salt(length: int = 16) -> str:
    """Generate cryptographically secure random salt."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_auth_token(password: str, salt: str = None) -> tuple[str, str]:
    """
    Create Subsonic authentication token.

    Algorithm:
    1. Generate random salt (if not provided)
    2. Concatenate password + salt
    3. Calculate MD5 hash
    4. Return hex digest as token

    Args:
        password: User's plaintext password
        salt: Optional pre-generated salt

    Returns:
        Tuple of (token, salt)
    """
    if salt is None:
        salt = generate_salt()

    # Subsonic token = md5(password + salt)
    token_input = f"{password}{salt}"
    token = hashlib.md5(token_input.encode('utf-8')).hexdigest()

    return token, salt

# Example usage
password = "mypassword"
token, salt = create_auth_token(password)

# Build auth parameters
auth_params = {
    'u': 'username',
    't': token,
    's': salt,
    'v': '1.16.1',
    'c': 'emby-to-m3u'
}
```

### 4.2 Token vs Legacy Password Methods

**Comparison**:

| Aspect | Token Auth (md5 hash) | Legacy Auth (plaintext) |
|--------|----------------------|-------------------------|
| Security | ✅ Password not transmitted | ❌ Password exposed in transit |
| Logging | ✅ Safe (tokens change per request) | ❌ Passwords in logs |
| Replay Attack | ✅ Harder (unique salt) | ❌ Easy to replay |
| Compatibility | ✅ All modern servers | ⚠️ Some old servers only |
| Implementation | Medium complexity | Simple |

**Decision**: Implement both with token as primary, legacy as fallback.

```python
class SubsonicAuth:
    """Subsonic authentication manager."""

    def __init__(self, username: str, password: str, prefer_token: bool = True):
        self.username = username
        self.password = password
        self.prefer_token = prefer_token
        self.use_token_auth = prefer_token  # Will be updated based on server support

    def get_auth_params(self) -> dict:
        """Get authentication parameters for API request."""
        base_params = {
            'u': self.username,
            'v': '1.16.1',
            'c': 'emby-to-m3u',
            'f': 'json'
        }

        if self.use_token_auth:
            token, salt = create_auth_token(self.password)
            base_params.update({
                't': token,
                's': salt
            })
        else:
            # Legacy authentication
            base_params['p'] = self.password

        return base_params

    def fallback_to_legacy(self):
        """Switch to legacy authentication method."""
        self.use_token_auth = False
```

### 4.3 Retry Strategies for Auth Failures

Based on existing retry pattern in `/workspaces/emby-to-m3u/src/azuracast/main.py`:

```python
import asyncio
from typing import Optional

BASE_BACKOFF = 2
MAX_BACKOFF = 64
MAX_AUTH_RETRIES = 3

class AuthenticationError(Exception):
    """Authentication failed after retries."""
    pass

async def authenticate_with_retry(
    client,
    max_retries: int = MAX_AUTH_RETRIES
) -> dict:
    """
    Authenticate with exponential backoff retry.

    Retry scenarios:
    - 40: Wrong username/password → Retry with re-generated token
    - 41: Token auth not supported → Fallback to legacy auth
    - Network errors → Retry with backoff
    """
    for attempt in range(1, max_retries + 1):
        try:
            # Test authentication with ping
            response = await client.ping()
            return response

        except SubsonicError as e:
            if e.code == 40:  # Wrong credentials
                if attempt < max_retries:
                    # Re-generate token with new salt
                    await asyncio.sleep(min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF))
                    continue
                else:
                    raise AuthenticationError(f"Authentication failed after {max_retries} attempts: {e.message}")

            elif e.code == 41:  # Token auth not supported
                # Fallback to legacy authentication
                client.auth.fallback_to_legacy()
                continue

            else:
                # Other errors, don't retry
                raise

        except (asyncio.TimeoutError, ConnectionError) as e:
            if attempt < max_retries:
                await asyncio.sleep(min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF))
                continue
            raise

    raise AuthenticationError(f"Authentication failed after {max_retries} attempts")
```

### 4.4 Request Queuing for Auth Retry

**Challenge**: Prevent request queue buildup during auth failures.

**Solution**: Circuit breaker pattern with request queue management.

```python
from enum import Enum
from collections import deque
from asyncio import Queue, Lock

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class SubsonicCircuitBreaker:
    """Circuit breaker for Subsonic API with auth retry."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: int = 30,
        max_queue_size: int = 1000
    ):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.request_queue: Queue = Queue(maxsize=max_queue_size)
        self.lock = Lock()
        self.last_failure_time: Optional[float] = None

    async def execute(self, func, *args, **kwargs):
        """Execute request through circuit breaker."""
        async with self.lock:
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                import time
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise Exception("Circuit breaker is OPEN, rejecting request")

        try:
            result = await func(*args, **kwargs)

            async with self.lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                self.failure_count = 0

            return result

        except SubsonicError as e:
            async with self.lock:
                import time
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN

            raise
```

---

## 5. Integration Analysis (Existing Codebase)

### 5.1 Current Emby Integration Pattern

**Location**: `/workspaces/emby-to-m3u/src/playlist/main.py`

**Key Observations**:

1. **Synchronous HTTP Client** (requests library):
   ```python
   def _get_emby_data(self, endpoint: str) -> Dict[str, Any]:
       url = f'{emby_server_url}{endpoint}&api_key={emby_api_key}'
       response = requests.get(url)
       response.raise_for_status()
       return response.json()
   ```

2. **Batch Fetching**:
   - Single API call to fetch all audio items
   - Fields specified in query parameters
   - Sorted results (SortName, Ascending)

3. **Track Model**:
   - Dictionary-based with typed extensions
   - Lazy loading (download on-demand)
   - Memory management (clear_content method)

### 5.2 Track Model Structure

**Location**: `/workspaces/emby-to-m3u/src/track/main.py`

**Current Implementation**:
```python
class Track(dict):
    """Represents an audio track with extended functionality."""

    def __init__(self, track_data: dict, playlist_manager: 'PlaylistManager'):
        super().__init__(track_data)
        self.playlist_manager = playlist_manager
        self.azuracast_file_id: Optional[str] = None
        self.replaygain_gain: Optional[float] = None
        self.replaygain_peak: Optional[float] = None
        self.content: Optional[BytesIO] = None

    def download(self) -> bytes:
        """Downloads track binary content from Emby server."""
        track_id = self['Id']
        download_url = f"{emby_server_url}/Items/{track_id}/File?api_key={emby_api_key}"
        response = requests.get(download_url, stream=True)
        # ... ReplayGain processing ...
        return data
```

**Subsonic Adaptation Requirements**:
1. Replace Emby download URL with Subsonic stream endpoint
2. Maintain dict-based structure for compatibility
3. Add Subsonic-specific metadata fields
4. Handle streaming URL construction with auth params

### 5.3 Source Selection Mechanism

**Current Pattern** (env var precedence):
```python
# In main.py or config
SOURCE_TYPE = os.getenv('SOURCE_TYPE', 'emby')  # 'emby' or 'subsonic'
```

**Proposed Enhancement**:
```python
from enum import Enum

class MusicSource(Enum):
    EMBY = "emby"
    SUBSONIC = "subsonic"
    NAVIDROME = "navidrome"  # Alias for subsonic
    AIRSONIC = "airsonic"    # Alias for subsonic

def get_playlist_manager(source: MusicSource) -> PlaylistManager:
    """Factory pattern for playlist managers."""
    if source == MusicSource.EMBY:
        return EmbyPlaylistManager()
    elif source in [MusicSource.SUBSONIC, MusicSource.NAVIDROME, MusicSource.AIRSONIC]:
        return SubsonicPlaylistManager()
    else:
        raise ValueError(f"Unsupported source: {source}")
```

**Environment Variables**:
```bash
# Emby configuration (existing)
EMBY_SERVER_URL=http://localhost:8096
EMBY_API_KEY=your_api_key

# Subsonic configuration (new)
SUBSONIC_SERVER_URL=http://localhost:4533
SUBSONIC_USERNAME=admin
SUBSONIC_PASSWORD=password
SUBSONIC_USE_TOKEN_AUTH=true  # true/false, default: true
SOURCE_TYPE=subsonic  # emby/subsonic/navidrome/airsonic
```

### 5.4 Integration Architecture

**Proposed Structure**:
```
src/
├── playlist/
│   ├── main.py              # Base PlaylistManager (abstract)
│   ├── emby_manager.py      # Emby implementation (refactored)
│   └── subsonic_manager.py  # Subsonic implementation (new)
├── client/
│   ├── subsonic_client.py   # Subsonic API client (new)
│   └── subsonic_auth.py     # Authentication logic (new)
├── track/
│   └── main.py              # Track model (update for Subsonic)
└── ...
```

**Subsonic PlaylistManager Pseudocode**:
```python
class SubsonicPlaylistManager(PlaylistManager):
    """Subsonic-specific playlist manager."""

    def __init__(self, report: PlaylistReport):
        super().__init__(report)
        self.client = SubsonicClient(
            base_url=os.getenv('SUBSONIC_SERVER_URL'),
            username=os.getenv('SUBSONIC_USERNAME'),
            password=os.getenv('SUBSONIC_PASSWORD')
        )

    async def fetch_tracks(self) -> None:
        """Fetch all tracks from Subsonic server."""
        # Detect server capabilities
        await self.client.detect_capabilities()

        # Strategy 1: Use getSongs with pagination
        all_songs = await self._fetch_all_songs_paginated()

        # Strategy 2: Fallback to search if getSongs unavailable
        # all_songs = await self._fetch_via_search()

        # Convert to Track objects
        from track.main import Track
        self.tracks = [
            Track(song.to_emby_track(self.client.base_url, self.client.auth.get_auth_params()), self)
            for song in all_songs
        ]

    async def _fetch_all_songs_paginated(self) -> list[SubsonicTrack]:
        """Fetch all songs with pagination."""
        all_songs = []
        offset = 0
        page_size = 500

        while True:
            response = await self.client.get_songs(
                type='alphabeticalByName',
                size=page_size,
                offset=offset
            )

            songs = response.get('song', [])
            if not songs:
                break

            all_songs.extend([SubsonicTrack.from_api_response(s) for s in songs])

            if len(songs) < page_size:
                break

            offset += page_size

        return all_songs
```

---

## 6. Retry and Error Handling

### 6.1 Exponential Backoff Patterns in Python

**Existing Pattern** (from `/workspaces/emby-to-m3u/src/azuracast/main.py`):
```python
BASE_BACKOFF = 2
MAX_BACKOFF = 64

for attempt in range(1, max_attempts + 1):
    try:
        # Perform request
        response = session.request(...)
        return response
    except (SSLError, ConnectionError, Timeout) as e:
        time.sleep(min(BASE_BACKOFF * (2 ** attempt), MAX_BACKOFF))
```

**Enhanced for Subsonic**:
```python
import asyncio
from typing import TypeVar, Callable
from functools import wraps

T = TypeVar('T')

def async_retry_with_backoff(
    max_retries: int = 3,
    base_backoff: float = 2.0,
    max_backoff: float = 64.0,
    retryable_exceptions: tuple = (asyncio.TimeoutError, ConnectionError)
):
    """Decorator for async functions with exponential backoff retry."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    if attempt == max_retries:
                        raise

                    wait_time = min(base_backoff * (2 ** attempt), max_backoff)
                    await asyncio.sleep(wait_time)
                except SubsonicError as e:
                    # Handle Subsonic-specific errors
                    if e.code in [0, 70]:  # Generic error, not found - retryable
                        if attempt == max_retries:
                            raise
                        wait_time = min(base_backoff * (2 ** attempt), max_backoff)
                        await asyncio.sleep(wait_time)
                    else:
                        # Auth errors, version mismatch - not retryable
                        raise
        return wrapper
    return decorator

# Usage
@async_retry_with_backoff(max_retries=3, base_backoff=2.0)
async def fetch_songs(client, **params):
    return await client.get_songs(**params)
```

### 6.2 httpx Retry Mechanisms

**Current Stack**: `requests` library (synchronous)
**Proposed**: `httpx` library (async support)

**Dependencies** (existing in requirements.txt):
```
httpx==0.28.1
httpcore==1.0.9
anyio==4.11.0
```

**httpx Client Configuration**:
```python
import httpx
from httpx import Timeout, Limits

class SubsonicHttpClient:
    """HTTP client for Subsonic API with retry logic."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url

        # Transport with connection pooling
        transport = httpx.AsyncHTTPTransport(
            limits=Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=5.0
            ),
            retries=3  # Automatic retries for network errors
        )

        # Client configuration
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=Timeout(
                connect=10.0,  # Connection timeout
                read=30.0,     # Read timeout
                write=10.0,    # Write timeout
                pool=5.0       # Pool acquisition timeout
            ),
            transport=transport,
            follow_redirects=True,
            http2=True  # Enable HTTP/2 for better performance
        )

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict = None,
        **kwargs
    ) -> httpx.Response:
        """Make HTTP request with automatic retries."""
        url = f"/rest/{endpoint}"
        response = await self.client.request(method, url, params=params, **kwargs)
        response.raise_for_status()
        return response

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
```

### 6.3 Error Scenarios

**Comprehensive Error Handling**:

| Error Type | Code | Scenario | Strategy |
|------------|------|----------|----------|
| **Authentication** | 40 | Wrong credentials | Retry with new token (max 3), then fail |
| **Authentication** | 41 | Token not supported | Fallback to legacy auth |
| **Authorization** | 50 | User unauthorized | Log and skip resource, don't retry |
| **Not Found** | 70 | Resource missing | Log warning, continue with next item |
| **Network** | N/A | Timeout | Retry with exponential backoff (max 3) |
| **Network** | N/A | Connection reset | Retry with exponential backoff (max 3) |
| **Server** | 0 | Generic server error | Retry once, then log and continue |
| **Client** | 10 | Missing parameter | Fix and retry immediately |
| **Version** | 30 | Incompatible server | Fallback to older endpoint |

**Implementation**:
```python
class SubsonicErrorHandler:
    """Centralized error handling for Subsonic API."""

    def __init__(self, logger):
        self.logger = logger
        self.error_stats = {
            'auth_failures': 0,
            'not_found': 0,
            'network_errors': 0,
            'server_errors': 0
        }

    async def handle_error(
        self,
        error: Exception,
        context: str,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> bool:
        """
        Handle Subsonic API error.

        Returns:
            bool: True if should retry, False otherwise
        """
        if isinstance(error, SubsonicError):
            if error.code == 40:  # Auth failure
                self.error_stats['auth_failures'] += 1
                if retry_count < max_retries:
                    self.logger.warning(
                        f"Auth failure in {context}, attempt {retry_count + 1}/{max_retries}"
                    )
                    return True  # Retry
                else:
                    self.logger.error(f"Auth failed after {max_retries} attempts in {context}")
                    raise AuthenticationError("Authentication failed")

            elif error.code == 70:  # Not found
                self.error_stats['not_found'] += 1
                self.logger.warning(f"Resource not found in {context}: {error.message}")
                return False  # Don't retry, skip item

            elif error.code == 0:  # Generic server error
                self.error_stats['server_errors'] += 1
                if retry_count < 1:  # Only retry once for server errors
                    self.logger.warning(f"Server error in {context}, retrying once")
                    return True
                return False

            else:
                # Other Subsonic errors (version mismatch, etc.)
                self.logger.error(f"Subsonic error {error.code} in {context}: {error.message}")
                raise

        elif isinstance(error, (asyncio.TimeoutError, httpx.TimeoutException)):
            self.error_stats['network_errors'] += 1
            if retry_count < max_retries:
                self.logger.warning(f"Timeout in {context}, attempt {retry_count + 1}/{max_retries}")
                return True  # Retry
            else:
                self.logger.error(f"Timeout after {max_retries} attempts in {context}")
                raise

        elif isinstance(error, (ConnectionError, httpx.ConnectError)):
            self.error_stats['network_errors'] += 1
            if retry_count < max_retries:
                self.logger.warning(f"Connection error in {context}, attempt {retry_count + 1}/{max_retries}")
                return True  # Retry
            else:
                self.logger.error(f"Connection failed after {max_retries} attempts in {context}")
                raise

        else:
            # Unknown error
            self.logger.error(f"Unexpected error in {context}: {error}")
            raise

        return False

    def get_error_summary(self) -> dict:
        """Get error statistics summary."""
        return self.error_stats.copy()
```

### 6.4 Request Queuing for Auth Retry

**Challenge**: During auth failures, prevent request buildup and ensure orderly retry.

**Solution**: Async queue with priority and circuit breaker.

```python
import asyncio
from asyncio import PriorityQueue
from dataclasses import dataclass, field
from typing import Any, Callable

@dataclass(order=True)
class PrioritizedRequest:
    priority: int
    request_func: Callable = field(compare=False)
    args: tuple = field(default_factory=tuple, compare=False)
    kwargs: dict = field(default_factory=dict, compare=False)
    future: asyncio.Future = field(default_factory=asyncio.Future, compare=False)

class SubsonicRequestQueue:
    """Request queue with priority and circuit breaker integration."""

    def __init__(
        self,
        circuit_breaker: SubsonicCircuitBreaker,
        max_concurrent: int = 10,
        queue_size: int = 1000
    ):
        self.queue: PriorityQueue = PriorityQueue(maxsize=queue_size)
        self.circuit_breaker = circuit_breaker
        self.max_concurrent = max_concurrent
        self.workers: list[asyncio.Task] = []
        self.running = False

    async def start(self):
        """Start queue workers."""
        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_concurrent)
        ]

    async def stop(self):
        """Stop queue workers."""
        self.running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

    async def enqueue(
        self,
        request_func: Callable,
        *args,
        priority: int = 5,
        **kwargs
    ) -> Any:
        """Enqueue request with priority (lower number = higher priority)."""
        future = asyncio.Future()
        request = PrioritizedRequest(
            priority=priority,
            request_func=request_func,
            args=args,
            kwargs=kwargs,
            future=future
        )

        await self.queue.put(request)
        return await future

    async def _worker(self, worker_id: int):
        """Queue worker to process requests."""
        while self.running:
            try:
                # Get request from queue with timeout
                request = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=1.0
                )

                try:
                    # Execute through circuit breaker
                    result = await self.circuit_breaker.execute(
                        request.request_func,
                        *request.args,
                        **request.kwargs
                    )
                    request.future.set_result(result)

                except Exception as e:
                    request.future.set_exception(e)

                finally:
                    self.queue.task_done()

            except asyncio.TimeoutError:
                # No requests in queue, continue
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")

# Usage example
async def main():
    circuit_breaker = SubsonicCircuitBreaker()
    request_queue = SubsonicRequestQueue(circuit_breaker)
    await request_queue.start()

    try:
        # High priority auth request
        auth_result = await request_queue.enqueue(
            client.ping,
            priority=1
        )

        # Normal priority song fetch
        songs = await request_queue.enqueue(
            client.get_songs,
            type='random',
            size=500,
            priority=5
        )

    finally:
        await request_queue.stop()
```

---

## 7. Performance Optimization

### 7.1 Pagination Strategies for 10K+ Tracks

**Challenge**: Efficiently fetch large music libraries without memory exhaustion or timeout.

**Strategy 1: Parallel Pagination by Genre**
```python
async def fetch_all_tracks_by_genre_parallel(
    client: SubsonicClient,
    genres: list[str],
    max_concurrent: int = 5
) -> list[SubsonicTrack]:
    """Fetch tracks in parallel by genre."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_genre(genre: str) -> list[SubsonicTrack]:
        async with semaphore:
            return await fetch_all_songs_paginated(client, genre=genre)

    # Parallel fetch across genres
    results = await asyncio.gather(*[
        fetch_genre(genre) for genre in genres
    ])

    # Flatten results
    all_tracks = []
    for genre_tracks in results:
        all_tracks.extend(genre_tracks)

    return all_tracks
```

**Strategy 2: Adaptive Page Size**
```python
async def fetch_with_adaptive_pagination(
    client: SubsonicClient,
    initial_page_size: int = 500
) -> list[SubsonicTrack]:
    """Adaptively adjust page size based on response time."""
    all_tracks = []
    offset = 0
    page_size = initial_page_size

    while True:
        start_time = asyncio.get_event_loop().time()

        try:
            response = await client.get_songs(
                type='alphabeticalByName',
                size=page_size,
                offset=offset
            )

            songs = response.get('song', [])
            if not songs:
                break

            all_tracks.extend([SubsonicTrack.from_api_response(s) for s in songs])

            # Adjust page size based on response time
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > 2.0 and page_size > 100:
                page_size = max(100, page_size // 2)  # Decrease page size
            elif elapsed < 0.5 and page_size < 1000:
                page_size = min(1000, page_size * 2)  # Increase page size

            if len(songs) < page_size:
                break

            offset += len(songs)

        except asyncio.TimeoutError:
            # Timeout, reduce page size and retry
            page_size = max(50, page_size // 2)
            continue

    return all_tracks
```

**Strategy 3: Streaming Iterator (Memory Efficient)**
```python
async def iter_all_tracks(
    client: SubsonicClient,
    page_size: int = 500
) -> AsyncIterator[SubsonicTrack]:
    """Stream tracks without loading all into memory."""
    offset = 0

    while True:
        response = await client.get_songs(
            type='alphabeticalByName',
            size=page_size,
            offset=offset
        )

        songs = response.get('song', [])
        if not songs:
            break

        for song in songs:
            yield SubsonicTrack.from_api_response(song)

        if len(songs) < page_size:
            break

        offset += page_size

# Usage
async for track in iter_all_tracks(client):
    # Process track immediately, minimal memory usage
    process_track(track)
```

### 7.2 Async/Await Patterns with httpx

**Pattern 1: Concurrent Requests with Semaphore**
```python
async def fetch_songs_concurrent(
    client: SubsonicClient,
    queries: list[dict],
    max_concurrent: int = 10
) -> list[list[SubsonicTrack]]:
    """Fetch multiple song queries concurrently."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(query: dict):
        async with semaphore:
            response = await client.get_songs(**query)
            return [SubsonicTrack.from_api_response(s) for s in response.get('song', [])]

    return await asyncio.gather(*[fetch_with_limit(q) for q in queries])
```

**Pattern 2: Task Groups (Python 3.11+)**
```python
async def fetch_all_data_concurrent(client: SubsonicClient):
    """Fetch different data types concurrently using task groups."""
    async with asyncio.TaskGroup() as group:
        songs_task = group.create_task(fetch_all_songs_paginated(client))
        albums_task = group.create_task(fetch_all_albums(client))
        artists_task = group.create_task(fetch_all_artists(client))

    return {
        'songs': songs_task.result(),
        'albums': albums_task.result(),
        'artists': artists_task.result()
    }
```

**Pattern 3: Connection Pooling**
```python
class SubsonicClientPool:
    """Pool of Subsonic clients for high concurrency."""

    def __init__(
        self,
        base_url: str,
        auth: SubsonicAuth,
        pool_size: int = 10
    ):
        self.clients = [
            SubsonicClient(base_url, auth)
            for _ in range(pool_size)
        ]
        self.semaphore = asyncio.Semaphore(pool_size)
        self.client_queue = asyncio.Queue()

        # Pre-populate queue
        for client in self.clients:
            self.client_queue.put_nowait(client)

    async def acquire(self) -> SubsonicClient:
        """Acquire client from pool."""
        await self.semaphore.acquire()
        return await self.client_queue.get()

    def release(self, client: SubsonicClient):
        """Release client back to pool."""
        self.client_queue.put_nowait(client)
        self.semaphore.release()

    async def execute(self, func, *args, **kwargs):
        """Execute function with pooled client."""
        client = await self.acquire()
        try:
            return await func(client, *args, **kwargs)
        finally:
            self.release(client)
```

### 7.3 Memory Efficiency Considerations

**Challenge**: Process 10K+ tracks without excessive memory usage.

**Strategies**:

1. **Streaming Processing** (as shown in 7.1)
2. **Batch Processing with Cleanup**:
```python
async def process_tracks_in_batches(
    track_iterator: AsyncIterator[SubsonicTrack],
    batch_size: int = 1000,
    processor: Callable = None
):
    """Process tracks in batches to limit memory usage."""
    batch = []

    async for track in track_iterator:
        batch.append(track)

        if len(batch) >= batch_size:
            # Process batch
            await processor(batch)

            # Clear batch to free memory
            batch.clear()

            # Optional: Force garbage collection
            import gc
            gc.collect()

    # Process remaining tracks
    if batch:
        await processor(batch)
```

3. **Lazy Loading Track Content**:
```python
class SubsonicTrack:
    """Track with lazy content loading."""

    def __init__(self, data: dict):
        self._data = data
        self._content: Optional[bytes] = None

    async def load_content(self, client: SubsonicClient):
        """Load audio content on-demand."""
        if self._content is None:
            self._content = await client.stream(self.id)
        return self._content

    def clear_content(self):
        """Free memory by clearing content."""
        self._content = None
```

4. **Database-Backed Track Storage** (for very large libraries):
```python
import aiosqlite

class TrackDatabase:
    """SQLite-backed track storage for memory efficiency."""

    def __init__(self, db_path: str = ':memory:'):
        self.db_path = db_path
        self.conn = None

    async def init(self):
        """Initialize database."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS tracks (
                id TEXT PRIMARY KEY,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration INTEGER,
                data BLOB
            )
        ''')
        await self.conn.commit()

    async def store_track(self, track: SubsonicTrack):
        """Store track in database."""
        import pickle
        await self.conn.execute(
            'INSERT OR REPLACE INTO tracks VALUES (?, ?, ?, ?, ?, ?)',
            (
                track.id,
                track.title,
                track.artist,
                track.album,
                track.duration,
                pickle.dumps(track._data)
            )
        )
        await self.conn.commit()

    async def iter_tracks(self) -> AsyncIterator[SubsonicTrack]:
        """Iterate over stored tracks."""
        import pickle
        async with self.conn.execute('SELECT data FROM tracks') as cursor:
            async for row in cursor:
                data = pickle.loads(row[0])
                yield SubsonicTrack(data)
```

### 7.4 Benchmarking Approach for 5000 Tracks in 60s

**Target**: Fetch and process 5000 tracks in under 60 seconds.

**Calculations**:
- 5000 tracks / 60 seconds = 83.3 tracks/second
- With page size 500: 10 pages required
- 60 seconds / 10 pages = 6 seconds/page (acceptable)

**Benchmark Implementation**:
```python
import time
from dataclasses import dataclass
from typing import List

@dataclass
class BenchmarkResults:
    total_tracks: int
    total_time: float
    tracks_per_second: float
    api_calls: int
    avg_response_time: float
    memory_peak_mb: float

async def benchmark_subsonic_fetch(
    client: SubsonicClient,
    target_tracks: int = 5000
) -> BenchmarkResults:
    """Benchmark track fetching performance."""
    import tracemalloc

    # Start memory tracking
    tracemalloc.start()

    start_time = time.time()
    api_calls = 0
    total_tracks = 0
    response_times = []

    offset = 0
    page_size = 500

    while total_tracks < target_tracks:
        req_start = time.time()

        response = await client.get_songs(
            type='alphabeticalByName',
            size=page_size,
            offset=offset
        )

        req_time = time.time() - req_start
        response_times.append(req_time)
        api_calls += 1

        songs = response.get('song', [])
        if not songs:
            break

        total_tracks += len(songs)
        offset += len(songs)

        if len(songs) < page_size:
            break

    total_time = time.time() - start_time

    # Get peak memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return BenchmarkResults(
        total_tracks=total_tracks,
        total_time=total_time,
        tracks_per_second=total_tracks / total_time if total_time > 0 else 0,
        api_calls=api_calls,
        avg_response_time=sum(response_times) / len(response_times) if response_times else 0,
        memory_peak_mb=peak / 1024 / 1024
    )

# Performance test
async def run_performance_test():
    client = SubsonicClient(
        base_url='http://localhost:4533',
        username='admin',
        password='password'
    )

    results = await benchmark_subsonic_fetch(client, target_tracks=5000)

    print(f"Performance Benchmark Results:")
    print(f"  Total tracks: {results.total_tracks}")
    print(f"  Total time: {results.total_time:.2f}s")
    print(f"  Tracks/second: {results.tracks_per_second:.1f}")
    print(f"  API calls: {results.api_calls}")
    print(f"  Avg response time: {results.avg_response_time:.3f}s")
    print(f"  Peak memory: {results.memory_peak_mb:.1f} MB")

    # Validate target
    if results.total_time <= 60:
        print("✅ Target achieved: 5000 tracks in under 60 seconds")
    else:
        print(f"❌ Target missed by {results.total_time - 60:.1f} seconds")
```

**Optimization Checklist**:
- [ ] Use httpx with HTTP/2 for connection reuse
- [ ] Enable connection pooling (20+ connections)
- [ ] Implement concurrent pagination (5-10 parallel requests)
- [ ] Use maximum page size (500)
- [ ] Minimize JSON parsing overhead (use orjson if needed)
- [ ] Lazy load track content (don't fetch audio during cataloging)
- [ ] Stream processing to avoid memory buildup
- [ ] Cache auth tokens to avoid regeneration

---

## 8. Recommendations and Next Steps

### 8.1 Implementation Priorities

**Phase 1: Core Integration (Week 1)**
1. ✅ Research complete
2. Implement SubsonicClient with httpx
3. Implement authentication (token + legacy fallback)
4. Implement basic endpoints (ping, getSongs, stream)
5. Create SubsonicTrack model and mapping

**Phase 2: Playlist Manager (Week 2)**
1. Implement SubsonicPlaylistManager
2. Add pagination strategies
3. Implement error handling and retry logic
4. Add source selection mechanism (env vars)

**Phase 3: Optimization (Week 3)**
1. Implement async/await patterns
2. Add connection pooling
3. Implement parallel pagination
4. Memory optimization and streaming

**Phase 4: Testing & Polish (Week 4)**
1. Unit tests for all components
2. Integration tests with Navidrome/Airsonic/Gonic
3. Performance benchmarking (5000 tracks < 60s)
4. Documentation and examples

### 8.2 Key Decision Summary

| Decision Point | Choice | Rationale |
|---------------|--------|-----------|
| HTTP Client | httpx (async) | Better performance, async support, HTTP/2 |
| Authentication | Token primary, legacy fallback | Security + compatibility |
| Pagination | 500 items/page with parallel | Balance speed and reliability |
| Error Handling | Circuit breaker + retry | Resilience with graceful degradation |
| Memory Strategy | Streaming + lazy loading | Handle 10K+ tracks efficiently |
| Compatibility | Multi-implementation support | Works with Navidrome, Airsonic, Gonic |

### 8.3 Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| API incompatibilities | High | Detect capabilities, fallback endpoints |
| Performance issues | High | Benchmark early, optimize pagination |
| Memory exhaustion | Medium | Streaming processing, lazy loading |
| Auth failures | Medium | Circuit breaker, comprehensive error handling |
| Network timeouts | Low | Retry logic, adaptive page sizes |

### 8.4 Open Questions

1. **Track Deduplication**: How to handle duplicate tracks from different endpoints?
   - **Answer**: Use Subsonic track ID as primary key, validate in PlaylistManager

2. **Offline Support**: Should we cache track metadata?
   - **Answer**: Optional SQLite cache for large libraries (10K+ tracks)

3. **Transcoding**: Do we support transcoded streams?
   - **Answer**: Phase 2 feature, use `format` parameter in stream endpoint

4. **Cover Art**: How to handle album artwork?
   - **Answer**: Use `coverArt` endpoint, cache locally with track metadata

5. **Playlists**: Sync with Subsonic server playlists?
   - **Answer**: Future feature, focus on genre/artist/album playlists first

---

## 9. References

### 9.1 Documentation
- [Subsonic API v1.16.1 Specification](http://www.subsonic.org/pages/api.jsp)
- [Navidrome Documentation](https://www.navidrome.org/docs/)
- [Airsonic GitHub](https://github.com/airsonic/airsonic)
- [Gonic GitHub](https://github.com/sentriz/gonic)

### 9.2 Related Code
- `/workspaces/emby-to-m3u/src/playlist/main.py` - Current Emby integration
- `/workspaces/emby-to-m3u/src/track/main.py` - Track model
- `/workspaces/emby-to-m3u/src/azuracast/main.py` - HTTP retry patterns

### 9.3 Dependencies
- httpx==0.28.1 (async HTTP client)
- httpcore==1.0.9 (HTTP/2 support)
- anyio==4.11.0 (async compatibility layer)

---

## Appendix A: Example API Requests

### A.1 Authentication (Token-based)
```bash
# Generate auth token
password="mypassword"
salt="abc123xyz"
token=$(echo -n "${password}${salt}" | md5sum | cut -d' ' -f1)

# Ping request
curl "http://localhost:4533/rest/ping?u=admin&t=${token}&s=${salt}&v=1.16.1&c=emby-to-m3u&f=json"
```

### A.2 Get Songs (Paginated)
```bash
# Fetch 500 songs, offset 0
curl "http://localhost:4533/rest/getSongs?type=alphabeticalByName&size=500&offset=0&u=admin&t=${token}&s=${salt}&v=1.16.1&c=emby-to-m3u&f=json"
```

### A.3 Stream Audio
```bash
# Stream track by ID
curl "http://localhost:4533/rest/stream?id=300&u=admin&t=${token}&s=${salt}&v=1.16.1&c=emby-to-m3u&f=raw" > track.mp3
```

### A.4 Search for Tracks
```bash
# Search for "Beatles"
curl "http://localhost:4533/rest/search3?query=Beatles&songCount=100&u=admin&t=${token}&s=${salt}&v=1.16.1&c=emby-to-m3u&f=json"
```

---

## Appendix B: Performance Benchmarks (Expected)

| Scenario | Target | Expected Result |
|----------|--------|-----------------|
| 5000 tracks fetch | < 60s | 45-55s with parallel pagination |
| Single page (500 tracks) | < 5s | 2-4s typical |
| Authentication | < 1s | 100-300ms |
| Stream URL generation | < 10ms | 1-5ms (no network) |
| Memory usage (10K tracks) | < 500MB | 200-400MB with streaming |

---

**Research completed**: 2025-10-05
**Next step**: Begin implementation of SubsonicClient (Phase 1)
