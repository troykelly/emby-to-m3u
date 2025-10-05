# SubsonicClient Implementation

## Overview

The `SubsonicClient` class provides a synchronous HTTP client for the Subsonic API v1.16.1. It implements secure token-based authentication, comprehensive error handling, and efficient connection pooling.

## Architecture

### Components

1. **SubsonicClient** (`/workspaces/emby-to-m3u/src/subsonic/client.py`)
   - Main HTTP client for Subsonic API
   - Handles authentication, requests, and response parsing
   - Uses httpx for HTTP/2 support and connection pooling

2. **Authentication** (`/workspaces/emby-to-m3u/src/subsonic/auth.py`)
   - Token generation using MD5(password + salt)
   - Implements Subsonic API v1.13.0+ authentication

3. **Models** (`/workspaces/emby-to-m3u/src/subsonic/models.py`)
   - `SubsonicConfig`: Server configuration
   - `SubsonicAuthToken`: Authentication token data
   - `SubsonicTrack`: Track metadata

4. **Exceptions** (`/workspaces/emby-to-m3u/src/subsonic/exceptions.py`)
   - Typed exceptions for all Subsonic error codes
   - Enables precise error handling

### HTTP Configuration

```python
# Connection pooling
max_connections=100           # Total connections
max_keepalive_connections=20  # Persistent connections
keepalive_expiry=5.0         # Keep alive for 5s

# Timeouts
connect=30.0s  # Connection timeout
read=60.0s     # Read timeout (for large responses)
write=30.0s    # Write timeout
pool=5.0s      # Pool acquisition timeout

# Features
http2=True           # HTTP/2 enabled
follow_redirects=True
retries=3            # Automatic network error retries
```

## Usage

### Basic Usage

```python
from src.subsonic import SubsonicClient, SubsonicConfig

# Configure connection
config = SubsonicConfig(
    url="https://music.mctk.co",
    username="your_username",
    password="your_password",
    client_name="emby-to-m3u",
    api_version="1.16.1"
)

# Create client
client = SubsonicClient(config)

# Test connection
if client.ping():
    print("Connected!")

# Fetch tracks
tracks = client.get_all_songs(offset=0, size=500)
print(f"Found {len(tracks)} tracks")

# Get stream URL
url = client.get_stream_url(tracks[0].id)
print(f"Stream URL: {url}")

# Download audio
audio_data = client.stream_track(tracks[0].id)
with open("track.mp3", "wb") as f:
    f.write(audio_data)

# Clean up
client.close()
```

### Context Manager

```python
with SubsonicClient(config) as client:
    if client.ping():
        tracks = client.get_all_songs(size=100)
        # Client automatically closed on exit
```

### Pagination

```python
def fetch_all_tracks(client):
    """Fetch all tracks from library using pagination."""
    all_tracks = []
    offset = 0
    page_size = 500

    while True:
        tracks = client.get_all_songs(offset=offset, size=page_size)

        if not tracks:
            break

        all_tracks.extend(tracks)

        # Check if we got fewer results than requested (last page)
        if len(tracks) < page_size:
            break

        offset += page_size

    return all_tracks

# Usage
all_tracks = fetch_all_tracks(client)
print(f"Total tracks: {len(all_tracks)}")
```

## API Methods

### ping() -> bool

Test server connectivity and authentication.

**Returns**: `True` if successful

**Raises**:
- `SubsonicAuthenticationError`: Invalid credentials
- `SubsonicVersionError`: API version incompatible
- `httpx.HTTPError`: Network/HTTP errors

### get_all_songs(offset=0, size=500) -> List[SubsonicTrack]

Fetch songs with pagination support.

**Parameters**:
- `offset` (int): Starting position (0-based)
- `size` (int): Maximum songs to return (max: 500)

**Returns**: List of `SubsonicTrack` objects

**Raises**:
- `SubsonicAuthenticationError`: Invalid credentials
- `SubsonicParameterError`: Invalid parameters
- `httpx.HTTPError`: Network/HTTP errors

### stream_track(track_id: str) -> bytes

Download audio file for a track.

**Parameters**:
- `track_id` (str): Unique track identifier

**Returns**: Raw audio file bytes

**Raises**:
- `SubsonicNotFoundError`: Track not found
- `SubsonicAuthenticationError`: Invalid credentials
- `httpx.HTTPError`: Network/HTTP errors

### get_stream_url(track_id: str) -> str

Generate streaming URL with authentication.

**Parameters**:
- `track_id` (str): Unique track identifier

**Returns**: Complete streaming URL

## Error Handling

### Exception Hierarchy

```
SubsonicError (base)
├── SubsonicAuthenticationError (codes 40, 41)
├── SubsonicAuthorizationError (code 50)
├── SubsonicNotFoundError (code 70)
├── SubsonicVersionError (codes 20, 30)
├── SubsonicParameterError (code 10)
└── SubsonicTrialError (code 60)
```

### Error Codes

| Code | Exception | Description | Retry? |
|------|-----------|-------------|--------|
| 0 | SubsonicError | Generic error | ❌ |
| 10 | SubsonicParameterError | Missing parameter | ❌ |
| 20 | SubsonicVersionError | Client incompatible | ❌ |
| 30 | SubsonicVersionError | Server incompatible | ❌ |
| 40 | SubsonicAuthenticationError | Wrong credentials | ❌ |
| 41 | SubsonicAuthenticationError | Token auth not supported | ❌ |
| 50 | SubsonicAuthorizationError | Not authorized | ❌ |
| 60 | SubsonicTrialError | Trial expired | ❌ |
| 70 | SubsonicNotFoundError | Resource not found | ❌ |

### Example Error Handling

```python
from src.subsonic.exceptions import (
    SubsonicAuthenticationError,
    SubsonicNotFoundError,
    SubsonicError
)

try:
    client = SubsonicClient(config)

    if not client.ping():
        print("Failed to connect")
        return

    tracks = client.get_all_songs()

    for track in tracks:
        try:
            url = client.get_stream_url(track.id)
            # Use URL...
        except SubsonicNotFoundError:
            print(f"Track {track.id} not found, skipping")
            continue

except SubsonicAuthenticationError as e:
    print(f"Authentication failed: {e.message}")
    print("Please check your username and password")

except SubsonicError as e:
    print(f"Subsonic API error {e.code}: {e.message}")

except httpx.HTTPError as e:
    print(f"Network error: {e}")

finally:
    client.close()
```

## Testing

### Integration Tests

Test with real server at `https://music.mctk.co`:

```bash
# Set credentials
export SUBSONIC_URL="https://music.mctk.co"
export SUBSONIC_USERNAME="your_username"
export SUBSONIC_PASSWORD="your_password"

# Run tests
pytest tests/subsonic/test_client_integration.py -v

# Or run manually
python tests/subsonic/test_client_integration.py
```

### Test Coverage

The integration test suite covers:
- ✅ Successful authentication (ping)
- ✅ Invalid credentials handling
- ✅ Pagination (get_all_songs)
- ✅ Stream URL generation
- ✅ Audio download (stream_track)
- ✅ Context manager usage

## Performance

### Benchmarks

For a library with 5000 tracks:

```python
import time

start = time.time()
all_tracks = []
offset = 0

while True:
    tracks = client.get_all_songs(offset=offset, size=500)
    if not tracks:
        break
    all_tracks.extend(tracks)
    if len(tracks) < 500:
        break
    offset += 500

elapsed = time.time() - start
print(f"Fetched {len(all_tracks)} tracks in {elapsed:.2f}s")
# Expected: < 60s for 5000 tracks
```

### Optimization Tips

1. **Use maximum page size**: `size=500` minimizes API calls
2. **Connection pooling**: Reuse client for multiple requests
3. **Parallel processing**: Fetch multiple pages concurrently (if needed)
4. **Stream URLs vs Downloads**: Use `get_stream_url()` for M3U playlists instead of downloading

## File Locations

All files organized in appropriate directories (not root):

- `/workspaces/emby-to-m3u/src/subsonic/client.py` - Main client implementation
- `/workspaces/emby-to-m3u/src/subsonic/auth.py` - Authentication utilities
- `/workspaces/emby-to-m3u/src/subsonic/models.py` - Data models
- `/workspaces/emby-to-m3u/src/subsonic/exceptions.py` - Exception classes
- `/workspaces/emby-to-m3u/src/subsonic/__init__.py` - Module exports
- `/workspaces/emby-to-m3u/tests/subsonic/test_client_integration.py` - Integration tests
- `/workspaces/emby-to-m3u/docs/subsonic-client.md` - This documentation

## Next Steps

1. Add unit tests for individual methods
2. Implement async version (AsyncSubsonicClient)
3. Add more endpoints (search, playlists, albums)
4. Add retry logic with exponential backoff
5. Add response caching for repeated requests
