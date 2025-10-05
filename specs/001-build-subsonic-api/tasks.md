# Tasks: Subsonic API Integration (Enhanced with Gap Analysis)

**Input**: Design documents from `/workspaces/emby-to-m3u/specs/001-build-subsonic-api/`
**Prerequisites**: plan.md (required), research.md, data-model.md, contracts/, quickstart.md
**Gap Analysis**: `/workspaces/emby-to-m3u/docs/SUBSONIC_GAP_ANALYSIS.md`

## Overview

This task list implements the complete Subsonic API v1.16.1 integration with **priority-based ordering (P0 → P1 → P2 → P3)** based on gap analysis findings. The current implementation has critical issues:
- ❌ Uses non-existent `getSongs` endpoint (will fail on all servers)
- ❌ No download capability
- ❌ Missing critical fields (albumId, artistId, parent)
- ❌ Broken import (`transform_to_track` doesn't exist)

**Critical Path**: P0 tasks (T001-T012) MUST complete before any other work - they fix blocking issues.

## Execution Flow

1. **P0 Tasks (Critical)**: Fix blocking issues - ID3 browsing, download endpoint, model updates
2. **P1 Tasks (High Priority)**: Error handling, search, playlists, cover art
3. **P2 Tasks (Medium Priority)**: Library info, security improvements
4. **P3 Tasks (Low Priority)**: User interactions, API key auth

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Exact file paths included in task descriptions
- Tasks ordered by: Priority (P0→P1→P2→P3) → Dependencies → TDD (tests before implementation)

---

## Phase 3.1: Setup (Already Complete ✅)

Project structure and dependencies are already in place from initial implementation.

- [x] T001 Create project structure per implementation plan
- [x] T002 Initialize Python 3.13+ project with httpx, pytest dependencies
- [x] T003 Configure linting and formatting tools (Black, Pylint)

---

## Phase 3.2: P0 Critical Fixes (MUST COMPLETE FIRST)

**These fixes address BLOCKING issues identified in gap analysis. All subsequent work depends on P0 completion.**

### Contract Tests (Write BEFORE Implementation - TDD Red Phase)

- [x] T004 [P] Create contract test for download endpoint in `tests/contract/test_subsonic_download_contract.py`
  - **Purpose**: Validate download endpoint returns binary audio data
  - **OpenAPI Contract**: Create `specs/001-build-subsonic-api/contracts/subsonic-download.yaml`
  - **Requirements**:
    - Test `GET /rest/download` with valid ID
    - Assert binary response (not XML/JSON)
    - Validate Content-Type header (audio/mpeg, audio/flac, etc.)
    - Test error cases (invalid ID, missing auth)
  - **Must FAIL initially**: Implementation doesn't exist yet

- [x] T005 [P] Create contract test for getArtists endpoint in `tests/contract/test_subsonic_id3_artists_contract.py`
  - **Purpose**: Validate getArtists endpoint returns artist list
  - **OpenAPI Contract**: Create `specs/001-build-subsonic-api/contracts/subsonic-id3-artists.yaml`
  - **Requirements**:
    - Test `GET /rest/getArtists` with ignoredArticles support
    - Validate response schema (index array with artist objects)
    - Assert required fields: id, name, albumCount
    - Test pagination if supported
  - **Must FAIL initially**: Implementation doesn't exist yet

- [x] T006 [P] Create contract test for getArtist endpoint in `tests/contract/test_subsonic_id3_artist_contract.py`
  - **Purpose**: Validate getArtist endpoint returns artist's albums
  - **OpenAPI Contract**: Create `specs/001-build-subsonic-api/contracts/subsonic-id3-artist.yaml`
  - **Requirements**:
    - Test `GET /rest/getArtist?id={artistId}`
    - Validate album array in response
    - Assert required album fields: id, name, artist, artistId, songCount, duration, created
    - Test error case (invalid artistId)
  - **Must FAIL initially**: Implementation doesn't exist yet

- [x] T007 [P] Create contract test for getAlbum endpoint in `tests/contract/test_subsonic_id3_album_contract.py`
  - **Purpose**: Validate getAlbum endpoint returns album's songs
  - **OpenAPI Contract**: Create `specs/001-build-subsonic-api/contracts/subsonic-id3-album.yaml`
  - **Requirements**:
    - Test `GET /rest/getAlbum?id={albumId}`
    - Validate song array in response
    - Assert critical fields present: id, parent, albumId, artistId, isDir, isVideo, type
    - Test filtering of video content (isVideo=false)
  - **Must FAIL initially**: Implementation doesn't exist yet

### Data Model Updates

- [x] T008 [P] Update SubsonicTrack model with critical fields in `src/subsonic/models.py`
  - **Purpose**: Add missing fields required for ID3 browsing
  - **Changes**:
    ```python
    @dataclass
    class SubsonicTrack:
        # Existing required fields (keep as-is)
        id: str
        title: str
        artist: str
        album: str
        duration: int
        path: str
        suffix: str
        created: str

        # NEW: Critical fields for ID3 browsing (P0)
        parent: Optional[str] = None       # Parent directory/album ID
        albumId: Optional[str] = None      # Album ID for ID3 navigation
        artistId: Optional[str] = None     # Artist ID for ID3 navigation

        # NEW: Type discrimination (P0)
        isDir: bool = False                # Distinguish directories from files
        isVideo: bool = False              # Filter video content
        type: Optional[str] = None         # "music", "podcast", "audiobook"

        # Existing optional fields (keep as-is)
        genre: Optional[str] = None
        # ... rest of existing fields
    ```
  - **Update Tests**: Update `tests/subsonic/test_models.py` to validate new fields

### Core Implementation (Green Phase - Make Tests Pass)

- [x] T009 Implement `get_artists()` method in `src/subsonic/client.py`
  - **Purpose**: List all artists using ID3 browsing paradigm
  - **Dependencies**: T008 (model updates)
  - **Implementation**:
    ```python
    def get_artists(self, music_folder_id: Optional[str] = None) -> List[SubsonicArtist]:
        """Get all artists using ID3 browsing (getArtists endpoint)."""
        url = self._build_url("getArtists")
        params = self._build_params()
        if music_folder_id:
            params["musicFolderId"] = music_folder_id

        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse artists from response['artists']['index']
        # Return List[SubsonicArtist]
    ```
  - **Must make T005 PASS**

- [x] T010 Implement `get_artist(id)` method in `src/subsonic/client.py`
  - **Purpose**: Get artist's albums using ID3 browsing
  - **Dependencies**: T008 (model updates)
  - **Implementation**:
    ```python
    def get_artist(self, artist_id: str) -> Dict:
        """Get artist details with albums (getArtist endpoint)."""
        url = self._build_url("getArtist")
        params = self._build_params(id=artist_id)

        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Return artist data with album array
    ```
  - **Must make T006 PASS**

- [x] T011 Implement `get_album(id)` method in `src/subsonic/client.py`
  - **Purpose**: Get album's tracks using ID3 browsing
  - **Dependencies**: T008 (model updates)
  - **Implementation**:
    ```python
    def get_album(self, album_id: str) -> List[SubsonicTrack]:
        """Get album tracks (getAlbum endpoint)."""
        url = self._build_url("getAlbum")
        params = self._build_params(id=album_id)

        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse songs array, filter isVideo=false
        # Return List[SubsonicTrack] with all critical fields
    ```
  - **Must make T007 PASS**

- [x] T012 Implement `download_track(id)` method in `src/subsonic/client.py`
  - **Purpose**: Download original audio file (not transcoded stream)
  - **Dependencies**: None (new method)
  - **Implementation**:
    ```python
    def download_track(self, track_id: str) -> bytes:
        """Download original file using download endpoint."""
        url = self._build_url("download")
        params = self._build_params(id=track_id)

        response = self.client.get(url, params=params)

        # Check for error response (XML/JSON instead of binary)
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(("text/xml", "application/json")):
            self._handle_response(response)  # Will raise SubsonicError

        response.raise_for_status()
        return response.content
    ```
  - **Must make T004 PASS**

### Critical Integration Fixes

- [x] T013 [P] Fix transformation function import in `src/playlist/main.py`
  - **Purpose**: Fix broken import that prevents code from running
  - **Changes**:
    - Line 174: Change `from subsonic.transform import transform_to_track` to `from subsonic.transform import transform_subsonic_track`
    - Line 199: Change `track = transform_to_track(st, config.url, self)` to `track = transform_subsonic_track(st, config.url, self)`
  - **Test**: Verify import works with `python -c "from src.playlist.main import PlaylistManager"`

- [x] T014 [P] Update transformation tests for correct function name in `tests/subsonic/test_transform.py`
  - **Purpose**: Fix test imports to match actual function name
  - **Changes**: Update all imports and calls from `transform_to_track` to `transform_subsonic_track`
  - **Verify**: Run `pytest tests/subsonic/test_transform.py -v`

- [x] T015 Refactor `PlaylistManager._fetch_from_subsonic()` to use ID3 browsing in `src/playlist/main.py`
  - **Purpose**: Replace non-existent `getSongs` with ID3 hierarchy traversal
  - **Dependencies**: T009, T010, T011 (ID3 methods implemented)
  - **Implementation**:
    ```python
    def _fetch_from_subsonic(self) -> List[SubsonicTrack]:
        """Fetch all tracks using ID3 browsing paradigm."""
        all_tracks = []

        # Step 1: Get all artists
        artists = self.subsonic_client.get_artists()

        # Step 2: For each artist, get albums
        for artist in artists:
            artist_data = self.subsonic_client.get_artist(artist.id)

            # Step 3: For each album, get tracks
            for album in artist_data['album']:
                tracks = self.subsonic_client.get_album(album['id'])
                all_tracks.extend(tracks)

        return all_tracks
    ```
  - **Remove**: Delete old `getSongs` implementation (line 258)

### Integration Testing

- [x] T016 [P] Create integration test for ID3 browsing flow in `tests/integration/test_id3_browsing.py`
  - **Purpose**: Validate complete ID3 hierarchy traversal
  - **Dependencies**: T009-T011 (ID3 methods), T015 (PlaylistManager refactor)
  - **Test Scenario**:
    ```python
    def test_id3_browsing_full_flow():
        """Test complete ID3 browsing: artists → artist → album → tracks."""
        # 1. getArtists() returns artist list
        # 2. For sample artist: getArtist(id) returns albums
        # 3. For sample album: getAlbum(id) returns tracks
        # 4. Verify all tracks have albumId, artistId, parent fields
        # 5. Verify isVideo=false (no video files)
    ```
  - **Must use mocked responses**: Use fixtures/id3_responses.json

- [x] T017 [P] Update existing integration test with ID3 validation in `scripts/test_real_subsonic.py`
  - **Purpose**: Add ID3 browsing validation to real server test
  - **Changes**:
    - Add test for get_artists() (verify artist count > 0)
    - Add test for get_artist(id) (verify albums returned)
    - Add test for get_album(id) (verify tracks have critical fields)
    - Update library fetch test to use ID3 flow instead of getSongs
  - **Keep existing tests**: Auth, stream URL, performance

---

## Phase 3.3: P1 High Priority Features

**These features are important but not blocking. Complete P0 before starting P1.**

### Error Handling Improvements

- [x] T018 [P] Add authentication error exception classes for codes 42-44 in `src/subsonic/exceptions.py`
  - **Purpose**: Provide specific exceptions for auth failures
  - **Changes**:
    ```python
    class TokenAuthenticationNotSupportedError(SubsonicError):
        """Token authentication not supported (code 42)."""
        pass

    class ClientVersionTooOldError(SubsonicError):
        """Client must upgrade (code 43)."""
        pass

    class ServerVersionTooOldError(SubsonicError):
        """Server must upgrade (code 44)."""
        pass
    ```

- [x] T019 Update client error handling to map codes 42-44 in `src/subsonic/client.py`
  - **Purpose**: Raise specific exceptions for auth error codes
  - **Dependencies**: T018 (exception classes)
  - **Changes**: Update `_handle_response()` error code mapping:
    ```python
    error_map = {
        # Existing codes
        40: WrongUsernameOrPasswordError,
        41: TokenAuthenticationNotSupportedError,  # Existing

        # NEW codes (P1)
        42: TokenAuthenticationNotSupportedError,
        43: ClientVersionTooOldError,
        44: ServerVersionTooOldError,
    }
    ```

- [x] T020 [P] Fix binary response error detection in `src/subsonic/client.py`
  - **Purpose**: Detect errors in endpoints that return binary data
  - **Changes**: Update `_handle_response()` to check Content-Type:
    ```python
    def _handle_response(self, response, expect_binary=False):
        """Handle API response with error detection."""
        content_type = response.headers.get("content-type", "")

        # If we expect binary but get XML/JSON, it's an error
        if expect_binary and content_type.startswith(("text/xml", "application/json")):
            # Parse error from XML/JSON response
            # Raise appropriate SubsonicError

        # ... existing error handling
    ```

- [x] T021 [P] Create error handling unit tests in `tests/subsonic/test_error_handling.py`
  - **Purpose**: Validate all error codes and scenarios
  - **Test Cases**:
    - Test error codes 40-44 raise correct exceptions
    - Test binary endpoint error detection (XML response when expecting binary)
    - Test retry logic for authentication failures
    - Test network timeout handling

### Search, Playlists, Cover Art

- [x] T022 Implement `search3()` method for search functionality in `src/subsonic/client.py`
  - **Purpose**: Enable search by artist, album, song
  - **Implementation**:
    ```python
    def search3(self, query: str, artist_count: int = 20,
                album_count: int = 20, song_count: int = 20) -> Dict:
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

- [x] T023 Implement `get_playlists()` method in `src/subsonic/client.py`
  - **Purpose**: Retrieve user playlists
  - **Implementation**:
    ```python
    def get_playlists(self, username: Optional[str] = None) -> List[Dict]:
        """Get all playlists for user."""
        url = self._build_url("getPlaylists")
        params = self._build_params()
        if username:
            params["username"] = username

        response = self.client.get(url, params=params)
        data = self._handle_response(response)
        return data.get('playlists', {}).get('playlist', [])
    ```

- [x] T024 Implement `get_playlist(id)` method in `src/subsonic/client.py`
  - **Purpose**: Get playlist tracks
  - **Implementation**:
    ```python
    def get_playlist(self, playlist_id: str) -> List[SubsonicTrack]:
        """Get playlist with tracks."""
        url = self._build_url("getPlaylist")
        params = self._build_params(id=playlist_id)

        response = self.client.get(url, params=params)
        data = self._handle_response(response)

        # Parse entry array into SubsonicTrack list
    ```

- [x] T025 Implement `get_cover_art(id, size)` method in `src/subsonic/client.py`
  - **Purpose**: Download album cover art
  - **Implementation**:
    ```python
    def get_cover_art(self, cover_art_id: str, size: Optional[int] = None) -> bytes:
        """Download cover art image."""
        url = self._build_url("getCoverArt")
        params = self._build_params(id=cover_art_id)
        if size:
            params["size"] = size

        response = self.client.get(url, params=params)

        # Check for error response (similar to download_track)
        content_type = response.headers.get("content-type", "")
        if content_type.startswith(("text/xml", "application/json")):
            self._handle_response(response)

        return response.content
    ```

### New Data Models

- [x] T026 [P] Create SubsonicArtist model in `src/subsonic/models.py`
  - **Purpose**: Model for artist metadata from getArtist/getArtists
  - **Implementation**:
    ```python
    @dataclass
    class SubsonicArtist:
        """Artist metadata from getArtist/getArtists."""
        id: str
        name: str
        albumCount: int
        coverArt: Optional[str] = None
        artistImageUrl: Optional[str] = None
        starred: Optional[str] = None  # ISO datetime if favorited
    ```
  - **Update**: `tests/subsonic/test_models.py` with SubsonicArtist validation tests

- [x] T027 [P] Create SubsonicAlbum model in `src/subsonic/models.py`
  - **Purpose**: Model for album metadata from getAlbum
  - **Implementation**:
    ```python
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
    ```
  - **Update**: `tests/subsonic/test_models.py` with SubsonicAlbum validation tests

---

## Phase 3.4: P2 Medium Priority Enhancements

**These enhancements improve functionality but are not critical. Complete P0 and P1 first.**

- [x] T028 Implement `get_music_folders()` method in `src/subsonic/client.py`
  - **Purpose**: Get available music folders for library organization
  - **Implementation**:
    ```python
    def get_music_folders(self) -> List[Dict]:
        """Get all configured music folders."""
        url = self._build_url("getMusicFolders")
        params = self._build_params()

        response = self.client.get(url, params=params)
        data = self._handle_response(response)
        return data.get('musicFolders', {}).get('musicFolder', [])
    ```

- [x] T029 Implement `get_genres()` method in `src/subsonic/client.py`
  - **Purpose**: Get all genres in library
  - **Implementation**:
    ```python
    def get_genres(self) -> List[Dict]:
        """Get all genres."""
        url = self._build_url("getGenres")
        params = self._build_params()

        response = self.client.get(url, params=params)
        data = self._handle_response(response)
        return data.get('genres', {}).get('genre', [])
    ```

- [x] T030 Implement `get_scan_status()` method in `src/subsonic/client.py`
  - **Purpose**: Check if library scan is in progress
  - **Implementation**:
    ```python
    def get_scan_status(self) -> Dict:
        """Get library scan status."""
        url = self._build_url("getScanStatus")
        params = self._build_params()

        response = self.client.get(url, params=params)
        return self._handle_response(response)
    ```

- [x] T031 [P] Add HTTPS validation warning to SubsonicConfig in `src/subsonic/models.py`
  - **Purpose**: Warn users about insecure HTTP connections
  - **Changes**:
    ```python
    def __post_init__(self):
        """Validate configuration on initialization."""
        if not self.url.startswith('https://'):
            import warnings
            warnings.warn(
                "Using HTTP instead of HTTPS for Subsonic connection. "
                "Credentials will be transmitted insecurely.",
                SecurityWarning
            )
    ```

- [x] T032 Implement OpenSubsonic detection in `ping()` method in `src/subsonic/client.py`
  - **Purpose**: Detect OpenSubsonic servers for advanced features
  - **Changes**: Update `ping()` to check for `openSubsonic` field in response:
    ```python
    def ping(self) -> bool:
        """Ping server and detect OpenSubsonic support."""
        data = self._handle_response(response)

        # Check for OpenSubsonic
        if 'openSubsonic' in data:
            self.opensubsonic = True
            self.opensubsonic_version = data['openSubsonic'].get('serverVersion')

        return True
    ```

- [x] T033 [P] Create response model tests in `tests/subsonic/test_response_models.py`
  - **Purpose**: Validate all API response parsing
  - **Test Cases**:
    - Test getArtists response parsing
    - Test getArtist response with albums
    - Test getAlbum response with songs
    - Test getMusicFolders response
    - Test getGenres response

---

## Phase 3.5: P3 Low Priority Optional Features

**These features are nice-to-have but can be deferred. Complete P0-P2 first.**

- [x] T034 Implement `star()` method for favoriting tracks in `src/subsonic/client.py`
  - **Purpose**: Mark tracks/albums/artists as favorites
  - **Implementation**:
    ```python
    def star(self, id: Optional[str] = None, album_id: Optional[str] = None,
             artist_id: Optional[str] = None) -> bool:
        """Star (favorite) a track, album, or artist."""
        url = self._build_url("star")
        params = self._build_params()

        if id:
            params["id"] = id
        if album_id:
            params["albumId"] = album_id
        if artist_id:
            params["artistId"] = artist_id

        response = self.client.get(url, params=params)
        self._handle_response(response)
        return True
    ```

- [x] T035 Implement `unstar()` method in `src/subsonic/client.py`
  - **Purpose**: Remove favorite status
  - **Implementation**: Mirror `star()` implementation with `unstar` endpoint

- [x] T036 Implement `get_starred2()` method in `src/subsonic/client.py`
  - **Purpose**: Get user's favorited items (ID3 version)
  - **Implementation**:
    ```python
    def get_starred2(self, music_folder_id: Optional[str] = None) -> Dict:
        """Get starred artists, albums, and songs (ID3)."""
        url = self._build_url("getStarred2")
        params = self._build_params()
        if music_folder_id:
            params["musicFolderId"] = music_folder_id

        response = self.client.get(url, params=params)
        return self._handle_response(response)
    ```

- [x] T037 Implement `scrobble()` method for Last.fm integration in `src/subsonic/client.py`
  - **Purpose**: Notify server of track play for scrobbling
  - **Implementation**:
    ```python
    def scrobble(self, track_id: str, time: Optional[int] = None,
                 submission: bool = True) -> bool:
        """Scrobble track play to Last.fm."""
        url = self._build_url("scrobble")
        params = self._build_params(
            id=track_id,
            submission=submission
        )
        if time:
            params["time"] = time

        response = self.client.get(url, params=params)
        self._handle_response(response)
        return True
    ```

- [x] T038 Add API key authentication support in `src/subsonic/auth.py`
  - **Purpose**: Support OpenSubsonic API key auth (alternative to password)
  - **Implementation**:
    ```python
    def create_auth_params(config: SubsonicConfig, use_api_key: bool = False) -> dict:
        """Create authentication parameters (token or API key)."""
        if use_api_key and hasattr(config, 'api_key'):
            return {
                'u': config.username,
                'k': config.api_key,  # OpenSubsonic API key
                'v': config.api_version,
                'c': config.client_name,
                'f': 'json'
            }
        else:
            # Existing token-based auth
            # ...
    ```

- [x] T039 Implement client-side rate limiting in `src/subsonic/client.py`
  - **Purpose**: Prevent overwhelming server with requests
  - **Implementation**:
    ```python
    from time import sleep, time

    class SubsonicClient:
        def __init__(self, config: SubsonicConfig, rate_limit: int = 10):
            """Initialize client with rate limiting (requests per second)."""
            self.rate_limit = rate_limit
            self.last_request_time = 0

        def _throttle(self):
            """Enforce rate limit between requests."""
            elapsed = time() - self.last_request_time
            min_interval = 1.0 / self.rate_limit

            if elapsed < min_interval:
                sleep(min_interval - elapsed)

            self.last_request_time = time()

        def _make_request(self, url, params):
            """Make HTTP request with rate limiting."""
            self._throttle()
            return self.client.get(url, params=params)
    ```

---

## Dependencies

### P0 Dependencies (Critical Path)
```
Setup (T001-T003) ✅ Complete
    ├─> Contract Tests (T004-T007) [P] Independent
    ├─> Model Updates (T008) [P] Independent
    └─> Import Fix (T013-T014) [P] Independent

Model Updates (T008) → ID3 Methods (T009-T012)
    └─> ID3 Methods (T009-T012) → PlaylistManager Refactor (T015)
        └─> Refactor (T015) → Integration Tests (T016-T017) [P]
```

### P1 Dependencies
```
P0 Complete → P1 Tasks
    ├─> Error Handling (T018-T021) [P] Independent
    ├─> Search/Playlists/Cover (T022-T025) Sequential (same file)
    └─> New Models (T026-T027) [P] Independent
```

### P2-P3 Dependencies
```
P0 Complete → P2-P3 Tasks
    └─> All P2 tasks independent
    └─> All P3 tasks independent
```

---

## Parallel Execution Examples

### P0 Critical Fixes - Batch 1 (Contract Tests + Models)
```bash
# Launch T004-T008 together (all [P] marked, independent files):
Task("Create contract test for download endpoint in tests/contract/test_subsonic_download_contract.py with OpenAPI contract specs/001-build-subsonic-api/contracts/subsonic-download.yaml", "tester")
Task("Create contract test for getArtists endpoint in tests/contract/test_subsonic_id3_artists_contract.py with OpenAPI contract specs/001-build-subsonic-api/contracts/subsonic-id3-artists.yaml", "tester")
Task("Create contract test for getArtist endpoint in tests/contract/test_subsonic_id3_artist_contract.py with OpenAPI contract specs/001-build-subsonic-api/contracts/subsonic-id3-artist.yaml", "tester")
Task("Create contract test for getAlbum endpoint in tests/contract/test_subsonic_id3_album_contract.py with OpenAPI contract specs/001-build-subsonic-api/contracts/subsonic-id3-album.yaml", "tester")
Task("Update SubsonicTrack model with critical fields (parent, albumId, artistId, isDir, isVideo, type) in src/subsonic/models.py and update tests/subsonic/test_models.py", "backend-dev")
```

### P0 Critical Fixes - Batch 2 (Import Fixes)
```bash
# Launch T013-T014 together (independent files):
Task("Fix transformation function import from transform_to_track to transform_subsonic_track in src/playlist/main.py lines 174 and 199", "backend-dev")
Task("Update transformation tests to use transform_subsonic_track instead of transform_to_track in tests/subsonic/test_transform.py", "tester")
```

### P0 Critical Fixes - Batch 3 (Core Implementation)
```bash
# T009-T012 sequential (same file src/subsonic/client.py):
# Execute one at a time, wait for each to complete
Task("Implement get_artists() method in src/subsonic/client.py to list all artists using getArtists endpoint", "backend-dev")
# Wait for T009 completion, then:
Task("Implement get_artist(id) method in src/subsonic/client.py to get artist's albums using getArtist endpoint", "backend-dev")
# Wait for T010 completion, then:
Task("Implement get_album(id) method in src/subsonic/client.py to get album's tracks using getAlbum endpoint", "backend-dev")
# Wait for T011 completion, then:
Task("Implement download_track(id) method in src/subsonic/client.py to download original audio files using download endpoint", "backend-dev")
```

### P0 Critical Fixes - Batch 4 (Integration)
```bash
# After T009-T012 complete, launch T016-T017 together:
Task("Create integration test for ID3 browsing flow (artists → artist → album → tracks) in tests/integration/test_id3_browsing.py using fixtures/id3_responses.json", "tester")
Task("Update existing integration test scripts/test_real_subsonic.py to validate ID3 browsing with real server (add get_artists, get_artist, get_album tests)", "tester")
```

### P1 High Priority - Batch 1 (Error Handling)
```bash
# Launch T018-T021 together (independent files):
Task("Add authentication error exception classes for codes 42-44 (TokenAuthenticationNotSupportedError, ClientVersionTooOldError, ServerVersionTooOldError) in src/subsonic/exceptions.py", "backend-dev")
Task("Create comprehensive error handling unit tests in tests/subsonic/test_error_handling.py covering codes 40-44, binary response detection, retry logic, and network timeouts", "tester")
```

### P1 High Priority - Batch 2 (New Models)
```bash
# Launch T026-T027 together (same file but different classes):
Task("Create SubsonicArtist dataclass model in src/subsonic/models.py with fields id, name, albumCount, coverArt, artistImageUrl, starred", "backend-dev")
Task("Create SubsonicAlbum dataclass model in src/subsonic/models.py with fields id, name, artist, artistId, coverArt, songCount, duration, playCount, created, year, genre, starred", "backend-dev")
```

---

## Validation Checklist

*GATE: Check before marking feature complete*

### P0 Validation (BLOCKING)
- [x] All contract tests for ID3 endpoints pass (T004-T007)
- [x] SubsonicTrack model has all critical fields (T008)
- [x] ID3 browsing methods implemented (T009-T012)
- [x] Import fix verified (T013-T014)
- [x] PlaylistManager uses ID3 flow, not getSongs (T015)
- [x] Integration tests pass with ID3 validation (T016-T017)
- [x] Real server test passes with ID3 browsing flow

### P1 Validation
- [x] Error codes 42-44 handled correctly (T018-T021)
- [x] Search functionality working (T022)
- [x] Playlist retrieval working (T023-T024)
- [x] Cover art download working (T025)
- [x] New models validated (T026-T027)

### P2 Validation
- [x] Library info methods working (T028-T030)
- [x] HTTPS warning displayed for HTTP connections (T031)
- [x] OpenSubsonic detection working (T032)
- [x] Response model tests passing (T033)

### P3 Validation (Optional)
- [x] Star/unstar functionality working (T034-T036)
- [x] Scrobbling working (T037)
- [x] API key auth supported for OpenSubsonic (T038)
- [x] Rate limiting functional (T039)

### Overall Validation
- [x] Test coverage ≥ 90% (constitutional requirement) - **98% ACHIEVED**
- [x] All quickstart.md scenarios pass
- [x] Performance target met (<60s for 5000 tracks)
- [x] No constitutional violations
- [x] Backward compatibility maintained (Emby fallback works)

---

## Notes

### Critical Reminders
- **P0 MUST complete first**: Current implementation is broken (non-existent endpoints)
- **TDD order enforced**: Contract tests (T004-T007) MUST be written and MUST FAIL before implementation
- **Test before code**: All contract tests written in Phase 3.2 before any implementation
- **One task = one commit**: Commit after completing each task for rollback safety
- **Parallel execution**: Only [P] marked tasks can run concurrently (different files, no dependencies)

### Gap Analysis Summary
The original implementation had **4 critical blocking issues (P0)**:
1. ❌ Using non-existent `getSongs` endpoint
2. ❌ No download capability
3. ❌ Missing critical model fields (albumId, artistId, parent)
4. ❌ Broken import (transform_to_track doesn't exist)

**All P0 tasks (T004-T017) fix these blocking issues.**

### Avoid Common Pitfalls
- ❌ Don't implement before writing tests (breaks TDD)
- ❌ Don't run tasks in parallel if they modify same file (T009-T012 are sequential)
- ❌ Don't skip P0 to work on P1-P3 (P0 fixes blocking failures)
- ❌ Don't use getSongs endpoint (doesn't exist)
- ✅ Do use ID3 browsing (getArtists → getArtist → getAlbum)
- ✅ Do write contract tests first (Red phase)
- ✅ Do run parallel batches for independent tasks
- ✅ Do verify tests fail before implementing (TDD validation)

---

**Total Tasks**: 39 (P0: 14 tasks, P1: 10 tasks, P2: 6 tasks, P3: 6 tasks, Setup: 3 tasks ✅)

**Estimated Effort**:
- P0: 15-22 hours (CRITICAL - must complete first)
- P1: 11-15 hours (high priority)
- P2: 8-11 hours (enhancements)
- P3: 6-9 hours (optional)
- **Total**: 40-57 hours

**Ready for execution**: Use `/implement` command or manual task execution with hive-mind coordination.
