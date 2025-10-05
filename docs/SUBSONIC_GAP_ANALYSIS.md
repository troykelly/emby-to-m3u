# Subsonic API Implementation Gap Analysis

**Date:** 2025-10-05
**API Version Target:** Subsonic API v1.16.1
**Implementation Status:** Partial - Critical Gaps Identified

---

## Executive Summary

### Critical Issues (P0 - Immediate Action Required)

1. **WRONG ENDPOINT FOR FETCHING TRACKS** - Using non-existent `getSongs` endpoint instead of recommended ID3 methods
2. **MISSING DOWNLOAD CAPABILITY** - No implementation of `download` or `stream` endpoints for file retrieval
3. **INCOMPLETE DATA MODEL** - Missing critical fields (albumId, artistId, parent, etc.)
4. **WRONG TRANSFORMATION FUNCTION** - Code references non-existent `transform_to_track` function
5. **NO ID3 BROWSING IMPLEMENTATION** - Not using recommended modern API methods

### Impact Assessment

- **Current State:** Implementation will **FAIL** on all Subsonic/Navidrome servers
- **Risk Level:** HIGH - Core functionality is broken
- **User Impact:** Unable to fetch tracks or download music files
- **Technical Debt:** Significant - requires major refactoring

---

## 1. Missing Endpoints (P0-P2)

### P0: Critical - Required for Basic Functionality

| Endpoint | Status | Documentation | Current Impact |
|----------|--------|---------------|----------------|
| `getArtists` | ❌ Missing | Section 3.1, Line 287-320 | Cannot browse music library by artist |
| `getArtist` | ❌ Missing | Section 3.1, Line 322-360 | Cannot get artist's albums |
| `getAlbum` | ❌ Missing | Section 3.1, Line 362-428 | Cannot get album tracks - **CRITICAL** |
| `download` | ❌ Missing | Section 4.1, Line 758-788 | Cannot download music files - **BLOCKING** |
| `stream` | ❌ Missing | Section 4.2, Line 790-821 | No alternative download method |

**Critical Finding:** The code uses `getSongs` endpoint (line 258 in client.py), which **does not exist** in the Subsonic API specification. This endpoint is not documented anywhere in the official API.

### P1: High Priority - Important Features

| Endpoint | Status | Documentation | Impact |
|----------|--------|---------------|--------|
| `search3` | ❌ Missing | Section 3.2, Line 442-474 | No search capability |
| `getAlbumList2` | ❌ Missing | Section 3.3, Line 477-501 | Cannot get newest/popular albums |
| `getPlaylists` | ❌ Missing | Section 3.5, Line 594-627 | No playlist support |
| `getPlaylist` | ❌ Missing | Section 3.5, Line 629-638 | Cannot read playlists |
| `getCoverArt` | ❌ Missing | Section 3.4, Line 543-562 | No album artwork |
| `getMusicFolders` | ❌ Missing | Section 3.1, Line 263-285 | Cannot filter by library |

### P2: Medium Priority - Enhanced Features

| Endpoint | Status | Documentation | Impact |
|----------|--------|---------------|--------|
| `getStarred2` | ❌ Missing | Section 3.7, Line 706-713 | No favorites support |
| `star/unstar` | ❌ Missing | Section 3.7, Line 715-729 | Cannot favorite tracks |
| `scrobble` | ❌ Missing | Section 3.7, Line 741-750 | No play count tracking |
| `getGenres` | ❌ Missing | Section 3.4, Line 520-540 | Must infer genres from tracks |
| `getScanStatus` | ❌ Missing | Section 3.6, Line 673-693 | No library scan status |

---

## 2. Bad Assumptions

### 2.1 Endpoint Existence (CRITICAL)

**Assumption:** `getSongs` endpoint exists
**Reality:** This endpoint **does not exist** in Subsonic API v1.16.1
**Location:** `/workspaces/emby-to-m3u/src/subsonic/client.py:258`
**Evidence:** Not mentioned anywhere in documentation (searched all 1723 lines)

```python
# WRONG - This will fail
url = self._build_url("getSongs")
params = self._build_params(
    type="alphabeticalByName",  # Invalid parameter
    size=min(size, 500),
    offset=offset,
)
```

**Correct Approach (from docs):**
```python
# Use ID3-based browsing (recommended)
# 1. Get all artists with getArtists
# 2. For each artist, call getArtist to get albums
# 3. For each album, call getAlbum to get songs
```

### 2.2 Response Structure

**Assumption:** Response has `songs.song` structure
**Reality:** Different endpoints have different structures
**Location:** `/workspaces/emby-to-m3u/src/subsonic/client.py:269-276`

**Actual Structures:**
- `getAlbum`: `subsonic-response.album.song[]`
- `search3`: `subsonic-response.searchResult3.song[]`
- `getRandomSongs`: `subsonic-response.randomSongs.song[]`

### 2.3 Download Method (CRITICAL)

**Assumption:** Can stream tracks with `stream` endpoint
**Reality:** Missing implementation entirely - no download capability exists
**Impact:** **Cannot download files for AzuraCast upload** (primary use case per docs)

**Required (from Section 4.1):**
```python
def download_track(self, track_id: str) -> bytes:
    """Download original file without transcoding."""
    url = self._build_url("download")
    params = self._build_params(id=track_id)
    response = self.client.get(url, params=params)

    # Check for JSON error vs binary data
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type or "text/xml" in content_type:
        self._handle_response(response)

    response.raise_for_status()
    return response.content
```

### 2.4 Authentication Token Reuse

**Current:** Generates new token per request ✅ **CORRECT**
**Location:** `/workspaces/emby-to-m3u/src/subsonic/auth.py:90-93`
**Status:** This is actually following best practices (Section 2.1, Line 166-169)

### 2.5 ID Type Handling

**Current:** Treats IDs as strings ✅ **CORRECT**
**Location:** `/workspaces/emby-to-m3u/src/subsonic/models.py:96`
**Status:** Follows documentation warning (Section 5.6.1, Line 1056-1067)

---

## 3. Blind Spots

### 3.1 No Pagination Strategy for Full Library

**Issue:** Code attempts to fetch all songs in one endpoint call
**Reality:** Must paginate through artists → albums → songs hierarchy
**Location:** `/workspaces/emby-to-m3u/src/playlist/main.py:188-206`

**Missing Implementation:**
```python
def fetch_all_tracks_id3(self) -> List[Dict]:
    """Fetch all tracks using ID3 browsing paradigm."""
    all_tracks = []

    # 1. Get all artists
    artists_response = client.get_artists()

    # 2. For each artist, get albums
    for index in artists_response['artists']['index']:
        for artist in index.get('artist', []):
            artist_response = client.get_artist(artist['id'])

            # 3. For each album, get songs
            for album in artist_response['artist'].get('album', []):
                album_response = client.get_album(album['id'])
                all_tracks.extend(album_response['album'].get('song', []))

    return all_tracks
```

### 3.2 Error Detection for Binary Responses

**Issue:** `stream_track` doesn't properly detect error responses
**Location:** `/workspaces/emby-to-m3u/src/subsonic/client.py:376-414`
**Documentation:** Section 4.6, Line 900-917

**Current Code:**
```python
# Incomplete - only checks JSON
if "application/json" in content_type:
    self._handle_response(response)
```

**Should Be:**
```python
# Check both JSON and XML error responses
content_type = response.headers.get("content-type", "")
if content_type.startswith("text/xml") or content_type.startswith("application/json"):
    # This is an error, parse it
    self._handle_response(response)
else:
    # Binary audio data
    response.raise_for_status()
```

### 3.3 Missing Authentication Error Codes

**Issue:** Only handles codes 40-41, missing 42-44
**Location:** `/workspaces/emby-to-m3u/src/subsonic/exceptions.py`
**Documentation:** Section 2.3, Line 233-239

**Missing Error Codes:**
- **42:** Authentication mechanism not supported
- **43:** Multiple conflicting authentication mechanisms
- **44:** Invalid API key (OpenSubsonic)

### 3.4 No Transcoding Control

**Issue:** When downloading, no control over format/bitrate
**Impact:** May receive transcoded files instead of originals
**Solution:** Use `download` endpoint OR `stream` with `format=raw` parameter

### 3.5 Missing Alternative Methods

**Issue:** Only implements `getRandomSongs`, not the full browsing API
**Impact:** Cannot systematically browse entire library
**Required:** Implement ID3 browsing paradigm (Section 1.2, Line 76-82)

---

## 4. Incorrect Usage

### 4.1 Non-Existent Endpoint (CRITICAL)

**File:** `/workspaces/emby-to-m3u/src/subsonic/client.py:258`

```python
# WRONG - getSongs does not exist in Subsonic API
url = self._build_url("getSongs")
params = self._build_params(
    type="alphabeticalByName",  # Not a valid parameter for any endpoint
    size=min(size, 500),
    offset=offset,
)
```

**Correct Replacement:**
```python
# Use getAlbumList2 for paginated track discovery
url = self._build_url("getAlbumList2")
params = self._build_params(
    type="alphabeticalByName",
    size=min(size, 500),
    offset=offset,
)
# Then call getAlbum for each album to get tracks
```

### 4.2 Missing Transform Function (CRITICAL)

**File:** `/workspaces/emby-to-m3u/src/playlist/main.py:174,199`

```python
from subsonic.transform import transform_to_track, is_duplicate
# ...
track = transform_to_track(st, config.url, self)
```

**Issue:** `transform_to_track` function **does not exist**
**Actual Function:** `transform_subsonic_track` in `/workspaces/emby-to-m3u/src/subsonic/transform.py:169`
**Fix Required:** Update import and function call

### 4.3 Stream URL Generation Issues

**File:** `/workspaces/emby-to-m3u/src/subsonic/client.py:416-441`

**Issue:** Generates stream URL but doesn't regenerate token
**Problem:** URL includes authentication that may expire
**Solution:** Document that URLs are single-use or implement token refresh

---

## 5. Missing Features

### 5.1 ID3 Browsing Paradigm (P0)

**Status:** ❌ Not Implemented
**Documentation:** Section 1.2, Lines 76-82
**Impact:** Cannot properly browse music library

**Required Methods:**
- `getArtists()` - Get all artists grouped by index
- `getArtist(id)` - Get artist with albums
- `getAlbum(id)` - Get album with songs
- `getSong(id)` - Get individual song details

**Current:** Only has `getRandomSongs()` which returns random samples

### 5.2 File Download (P0 - BLOCKING)

**Status:** ❌ Not Implemented
**Documentation:** Section 4, Lines 754-929
**Impact:** **Cannot download music files** - this is the primary use case

**Required:**
```python
def download_track(self, track_id: str) -> bytes:
    """Download original audio file."""
    url = self._build_url("download")
    params = self._build_params(id=track_id)
    response = self.client.get(url, params=params)

    # Detect errors vs binary
    content_type = response.headers.get("content-type", "")
    if content_type.startswith(("text/xml", "application/json")):
        self._handle_response(response)

    response.raise_for_status()
    return response.content
```

### 5.3 Search Functionality (P1)

**Status:** ❌ Not Implemented
**Documentation:** Section 3.2, Lines 442-474
**Impact:** No search capability

**Required:**
```python
def search(self, query: str,
           artist_count: int = 20, album_count: int = 20,
           song_count: int = 20) -> Dict:
    """Search for artists, albums, and songs."""
    url = self._build_url("search3")
    params = self._build_params(
        query=query,
        artistCount=artist_count,
        albumCount=album_count,
        songCount=song_count
    )
    response = self.client.get(url, params=params)
    return self._handle_response(response)
```

### 5.4 Playlist Management (P1)

**Status:** ❌ Not Implemented
**Documentation:** Section 3.5, Lines 594-671
**Impact:** Cannot read/create/modify playlists

**Required Methods:**
- `get_playlists()` - List all playlists
- `get_playlist(id)` - Get playlist with tracks
- `create_playlist(name, song_ids)` - Create new playlist
- `update_playlist(id, ...)` - Modify playlist
- `delete_playlist(id)` - Remove playlist

### 5.5 Cover Art (P1)

**Status:** ❌ Not Implemented
**Documentation:** Section 3.4, Lines 543-562
**Impact:** No album artwork retrieval

**Required:**
```python
def get_cover_art(self, cover_art_id: str, size: Optional[int] = None) -> bytes:
    """Download cover art image."""
    url = self._build_url("getCoverArt")
    params = self._build_params(id=cover_art_id)
    if size:
        params['size'] = str(size)

    response = self.client.get(url, params=params)
    response.raise_for_status()
    return response.content
```

### 5.6 Library Information (P2)

**Status:** ❌ Not Implemented
**Impact:** Cannot get library metadata

**Missing:**
- `getMusicFolders()` - Get available music libraries
- `getGenres()` - Get all genres with counts
- `getScanStatus()` - Check library scan status

### 5.7 User Interactions (P2)

**Status:** ❌ Not Implemented
**Impact:** No user preference tracking

**Missing:**
- `star/unstar` - Favorite tracks/albums/artists
- `getStarred2` - Get user's favorites
- `setRating` - Rate items 1-5
- `scrobble` - Track play counts

---

## 6. Authentication Issues

### 6.1 Current Implementation: ✅ CORRECT

**Token Generation:** Uses MD5(password + salt) correctly
**Salt Generation:** Uses cryptographically secure `secrets.token_hex(8)` ✅
**Token Regeneration:** Generates new token per request ✅
**Location:** `/workspaces/emby-to-m3u/src/subsonic/auth.py`

### 6.2 Missing: API Key Support (P3)

**Status:** ❌ Not Implemented
**Documentation:** Section 2.2, Lines 172-190
**Impact:** Cannot use OpenSubsonic API keys

**Future Enhancement:**
```python
@dataclass
class SubsonicConfig:
    url: str
    username: Optional[str] = None  # Not required with API key
    password: Optional[str] = None  # Not required with API key
    api_key: Optional[str] = None   # Alternative auth method
    # ...

    def __post_init__(self):
        if not self.api_key and (not self.username or not self.password):
            raise ValueError("Either api_key or username+password required")
```

### 6.3 Missing: LDAP Consideration (P3)

**Issue:** No handling for LDAP authentication restrictions
**Documentation:** Section 2.3, Lines 241-246
**Impact:** Token auth fails for LDAP users (error 41)

**Recommendation:** Document limitation or implement fallback to password auth

---

## 7. Download/Streaming Issues

### 7.1 No Download Implementation (P0 - CRITICAL)

**Status:** ❌ BLOCKING
**Current:** `stream_track()` method exists but has issues
**Missing:** `download()` endpoint implementation (recommended)

**Problems with Current `stream_track`:**
1. Uses `stream` endpoint (may transcode)
2. No `format=raw` parameter to prevent transcoding
3. Incomplete error detection (only checks JSON, not XML)

**Required Fix:**
```python
def download_track(self, track_id: str) -> bytes:
    """Download original file using download endpoint (recommended)."""
    url = self._build_url("download")
    params = self._build_params(id=track_id)
    response = self.client.get(url, params=params)

    # Check for error response
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/xml") or content_type.startswith("application/json"):
        self._handle_response(response)

    response.raise_for_status()
    return response.content

def stream_track(self, track_id: str, format: str = "raw") -> bytes:
    """Stream track with optional transcoding."""
    url = self._build_url("stream")
    params = self._build_params(id=track_id)
    if format:
        params['format'] = format  # 'raw' prevents transcoding

    response = self.client.get(url, params=params)

    # Check for error
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("text/xml") or content_type.startswith("application/json"):
        self._handle_response(response)

    response.raise_for_status()
    return response.content
```

### 7.2 Missing Transcoding Control (P1)

**Issue:** No parameters to control audio format/bitrate
**Documentation:** Section 4.2, Lines 795-821
**Impact:** May receive transcoded files instead of originals

**Missing Parameters:**
- `format` - Target format (mp3, ogg, flac, **raw**)
- `maxBitRate` - Maximum bitrate for transcoding

### 7.3 Stream URL Issues (P2)

**File:** `/workspaces/emby-to-m3u/src/subsonic/client.py:416-441`

**Issues:**
1. No documentation that URL is single-use
2. Token in URL may become invalid
3. No HTTPS enforcement warning

**Recommendation:** Add documentation and HTTPS check

---

## 8. Error Handling Gaps

### 8.1 Missing Error Codes (P1)

**Current:** Only handles 6 error codes
**Missing:** 3 authentication-related codes

| Code | Description | Current Handling |
|------|-------------|------------------|
| 42 | Auth mechanism not supported | ❌ Falls to generic |
| 43 | Multiple conflicting auth | ❌ Falls to generic |
| 44 | Invalid API key | ❌ Falls to generic |

**Fix:** Add to `/workspaces/emby-to-m3u/src/subsonic/exceptions.py`

```python
class SubsonicAuthenticationMechanismError(SubsonicError):
    """Authentication mechanism not supported (error code 42)."""
    pass

class SubsonicConflictingAuthError(SubsonicError):
    """Multiple conflicting authentication mechanisms (error code 43)."""
    pass

class SubsonicInvalidAPIKeyError(SubsonicError):
    """Invalid API key (error code 44)."""
    pass
```

**Update client.py error mapping:**
```python
if code in (40, 41):
    raise SubsonicAuthenticationError(code, message)
elif code == 42:
    raise SubsonicAuthenticationMechanismError(code, message)
elif code == 43:
    raise SubsonicConflictingAuthError(code, message)
elif code == 44:
    raise SubsonicInvalidAPIKeyError(code, message)
# ...
```

### 8.2 Binary Response Error Detection (P1)

**Issue:** Incomplete Content-Type checking
**Location:** `/workspaces/emby-to-m3u/src/subsonic/client.py:405-411`

**Current:**
```python
if "application/json" in content_type:
    self._handle_response(response)
```

**Should Be (per docs):**
```python
content_type = response.headers.get("content-type", "")
if content_type.startswith("text/xml") or content_type.startswith("application/json"):
    # Error response - parse it
    self._handle_response(response)
else:
    # Binary data - just check HTTP status
    response.raise_for_status()
```

---

## 9. Data Model Issues

### 9.1 Missing Critical Fields (P0)

**File:** `/workspaces/emby-to-m3u/src/subsonic/models.py:72-115`

**Documentation Reference:** Section 3.1, Lines 390-428 (getAlbum response)

**Missing Fields:**

| Field | Type | Importance | Usage |
|-------|------|------------|-------|
| `parent` | str | Critical | Parent directory/album ID |
| `albumId` | str | Critical | Album ID for ID3 browsing |
| `artistId` | str | Critical | Artist ID for ID3 browsing |
| `isDir` | bool | High | Distinguish directories from files |
| `isVideo` | bool | Medium | Filter video content |
| `type` | str | Medium | Media type (music/podcast/audiobook) |
| `starred` | str (datetime) | Medium | User favorite status |
| `userRating` | int | Low | User rating 1-5 |
| `averageRating` | float | Low | Community rating |
| `playCount` | int | Low | Play count |

**Fix Required:**
```python
@dataclass
class SubsonicTrack:
    """Raw track metadata from Subsonic API response."""

    # Required fields
    id: str
    title: str
    artist: str
    album: str
    duration: int
    path: str
    suffix: str
    created: str

    # Critical missing fields
    parent: Optional[str] = None  # Parent directory/album
    albumId: Optional[str] = None  # Album ID for ID3
    artistId: Optional[str] = None  # Artist ID for ID3

    # Type information
    isDir: bool = False
    isVideo: bool = False
    type: Optional[str] = None  # "music", "podcast", "audiobook"

    # User interaction
    starred: Optional[str] = None  # ISO datetime if starred
    userRating: Optional[int] = None  # 1-5
    averageRating: Optional[float] = None
    playCount: Optional[int] = None

    # Existing optional fields
    genre: Optional[str] = None
    track: Optional[int] = None
    discNumber: Optional[int] = None
    year: Optional[int] = None
    musicBrainzId: Optional[str] = None
    coverArt: Optional[str] = None
    size: Optional[int] = None
    bitRate: Optional[int] = None
    contentType: Optional[str] = None
```

### 9.2 Missing Response Models (P1)

**Issue:** No models for Artist, Album, Playlist responses
**Impact:** Cannot properly type-check API responses

**Required Models:**
```python
@dataclass
class SubsonicArtist:
    """Artist metadata from getArtist/getArtists."""
    id: str
    name: str
    albumCount: int
    coverArt: Optional[str] = None
    artistImageUrl: Optional[str] = None
    starred: Optional[str] = None

@dataclass
class SubsonicAlbum:
    """Album metadata from getAlbum."""
    id: str
    name: str
    artist: str
    artistId: str
    coverArt: Optional[str] = None
    songCount: int
    duration: int
    playCount: Optional[int] = None
    created: str
    year: Optional[int] = None
    genre: Optional[str] = None
    starred: Optional[str] = None

@dataclass
class SubsonicPlaylist:
    """Playlist metadata from getPlaylists/getPlaylist."""
    id: str
    name: str
    owner: str
    public: bool
    songCount: int
    duration: int
    created: str
    changed: str
    comment: Optional[str] = None
    coverArt: Optional[str] = None
```

---

## 10. Best Practices Violations

### 10.1 Not Using ID3 Browsing (P0)

**Violation:** Using non-existent endpoint instead of recommended ID3 methods
**Documentation:** Section 1.2, Lines 76-82

**Current Approach:** Tries to get all songs in one call
**Recommended Approach:** Browse artists → albums → songs

**Impact:** Code will fail on all Subsonic servers

### 10.2 No HTTPS Enforcement (P1)

**Violation:** No warning or check for HTTP vs HTTPS
**Documentation:** Section 2.1, Line 169; Section 2.4, Line 211

**Security Risk:** Credentials sent in plain text over HTTP
**Fix:** Add warning in config validation

```python
def __post_init__(self):
    if not self.url.startswith("https://"):
        logger.warning(
            "Using HTTP instead of HTTPS - credentials will be sent in plain text! "
            "This is a security risk. Please use HTTPS in production."
        )
```

### 10.3 Not Checking OpenSubsonic Support (P2)

**Issue:** No detection of OpenSubsonic extensions
**Documentation:** Not explicitly in docs, but mentioned throughout

**Enhancement:**
```python
def ping(self) -> Dict[str, Any]:
    """Test connectivity and detect server capabilities."""
    response = self.client.get(self._build_url("ping"), params=self._build_params())
    data = self._handle_response(response)

    # Check for OpenSubsonic support
    if data.get('openSubsonic'):
        logger.info(f"Server supports OpenSubsonic extensions")
        self._supports_opensonic = True

    return data
```

### 10.4 No Rate Limiting (P3)

**Issue:** No client-side rate limiting
**Documentation:** Section 5.4, Lines 1011-1022

**Recommendation:** Implement rate limiting for batch operations

```python
from time import sleep

class SubsonicClient:
    def __init__(self, config: SubsonicConfig, max_requests_per_second: int = 10):
        # ...
        self.rate_limit_delay = 1.0 / max_requests_per_second
        self._last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        now = time.time()
        time_since_last = now - self._last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep(self.rate_limit_delay - time_since_last)
        self._last_request_time = time.time()
```

### 10.5 Mixing Paradigms (P2)

**Issue:** Code attempts to use both file-structure and ID3 methods
**Documentation:** Section 5.6.2, Lines 1069-1084

**Current:** Uses non-ID3 approach (getSongs - which doesn't exist)
**Should:** Stick exclusively to ID3 methods (getArtists, getArtist, getAlbum)

---

## Action Items

### Phase 1: Critical Fixes (P0 - Immediate)

1. **Replace `getSongs` with ID3 browsing**
   - Implement `get_artists()` endpoint
   - Implement `get_artist(id)` endpoint
   - Implement `get_album(id)` endpoint
   - Refactor `fetch_tracks()` to use ID3 hierarchy
   - **Estimated Effort:** 8-12 hours

2. **Implement file download**
   - Add `download_track(track_id)` method using `download` endpoint
   - Fix error detection (check both XML and JSON)
   - Add `format=raw` support to `stream_track()`
   - **Estimated Effort:** 4-6 hours

3. **Fix transformation function**
   - Correct import from `transform_to_track` to `transform_subsonic_track`
   - Update function signature if needed
   - **Estimated Effort:** 1 hour

4. **Update SubsonicTrack model**
   - Add critical fields: `parent`, `albumId`, `artistId`
   - Add type fields: `isDir`, `isVideo`, `type`
   - Update transformation logic
   - **Estimated Effort:** 2-3 hours

### Phase 2: High Priority (P1 - Next Sprint)

5. **Implement search functionality**
   - Add `search3()` endpoint
   - Support pagination parameters
   - **Estimated Effort:** 3-4 hours

6. **Add playlist support**
   - Implement `get_playlists()`
   - Implement `get_playlist(id)`
   - Add SubsonicPlaylist model
   - **Estimated Effort:** 4-6 hours

7. **Cover art retrieval**
   - Implement `get_cover_art(id, size)`
   - Handle binary image data
   - **Estimated Effort:** 2-3 hours

8. **Complete error handling**
   - Add error codes 42, 43, 44
   - Fix binary response detection
   - **Estimated Effort:** 2 hours

### Phase 3: Medium Priority (P2 - Future)

9. **Library information endpoints**
   - Implement `get_music_folders()`
   - Implement `get_genres()`
   - Implement `get_scan_status()`
   - **Estimated Effort:** 3-4 hours

10. **Add missing response models**
    - Create SubsonicArtist model
    - Create SubsonicAlbum model
    - Update type hints
    - **Estimated Effort:** 2-3 hours

11. **Security enhancements**
    - Add HTTPS warning
    - Implement rate limiting
    - Add OpenSubsonic detection
    - **Estimated Effort:** 3-4 hours

### Phase 4: Low Priority (P3 - Optional)

12. **User interaction features**
    - Implement star/unstar
    - Implement get_starred2
    - Implement scrobble
    - **Estimated Effort:** 4-6 hours

13. **API key authentication**
    - Add api_key to SubsonicConfig
    - Update authentication logic
    - **Estimated Effort:** 2-3 hours

---

## Testing Requirements

### Unit Tests Needed

1. **ID3 browsing flow**
   - Test getArtists → getArtist → getAlbum → songs
   - Test pagination at each level
   - Test empty responses

2. **Download functionality**
   - Test download endpoint
   - Test stream with format=raw
   - Test error detection (XML vs JSON vs binary)
   - Test transcoding parameters

3. **Error handling**
   - Test all error codes (0, 10, 20, 30, 40-44, 50, 60, 70)
   - Test Content-Type detection
   - Test malformed responses

4. **Authentication**
   - Test token generation
   - Test salt uniqueness
   - Test token verification

### Integration Tests Needed

1. **Full library fetch**
   - Test against Navidrome demo server
   - Verify complete artist/album/track hierarchy
   - Test with large libraries (1000+ tracks)

2. **Download workflow**
   - Download tracks from various formats (MP3, FLAC, OGG)
   - Verify file integrity
   - Test with transcoding disabled

3. **Error scenarios**
   - Test with invalid credentials
   - Test with non-existent IDs
   - Test network failures

---

## References

- **Subsonic API Documentation:** `/workspaces/emby-to-m3u/subsonic.md`
- **Implementation Files:**
  - Client: `/workspaces/emby-to-m3u/src/subsonic/client.py`
  - Auth: `/workspaces/emby-to-m3u/src/subsonic/auth.py`
  - Models: `/workspaces/emby-to-m3u/src/subsonic/models.py`
  - Transform: `/workspaces/emby-to-m3u/src/subsonic/transform.py`
  - Exceptions: `/workspaces/emby-to-m3u/src/subsonic/exceptions.py`
  - Integration: `/workspaces/emby-to-m3u/src/playlist/main.py`

---

## Conclusion

The current Subsonic API implementation has **critical gaps** that prevent it from functioning with any Subsonic-compatible server. The most critical issue is the use of a non-existent `getSongs` endpoint.

**Immediate action required:**
1. Implement ID3 browsing (getArtists/getArtist/getAlbum)
2. Implement download endpoint
3. Fix transformation function import
4. Update data models

**Estimated total effort for Phase 1 (critical fixes):** 15-22 hours

Once Phase 1 is complete, the implementation will be functional for basic use cases (browsing and downloading music). Phases 2-4 add important but non-blocking features.
