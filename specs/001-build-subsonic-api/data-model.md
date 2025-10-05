# Data Model: Subsonic API Integration

**Feature**: Subsonic API Integration for Music Library Access
**Branch**: `001-build-subsonic-api`
**Date**: 2025-10-05

## Overview

This document defines the data models required for integrating Subsonic API as a music source. The models support authentication, track metadata transformation, and backward compatibility with the existing Track model structure used by playlist generation, Last.fm, AzuraCast, and ReplayGain modules.

## Entity Definitions

### 1. SubsonicConfig

**Purpose**: Configuration for connecting to a Subsonic-compatible server.

**Source**: Environment variables (12-factor configuration)

**Fields**:
```python
@dataclass
class SubsonicConfig:
    """Configuration for Subsonic API client."""

    url: str                    # Base server URL (e.g., "https://music.example.com")
    username: str               # Subsonic username
    password: str               # Subsonic password (hashed before transmission)
    client_name: str = "playlistgen"  # Client identifier for API requests
    api_version: str = "1.16.1"       # Subsonic API version

    def __post_init__(self):
        """Validate configuration on initialization."""
        if not self.url or not self.url.startswith(('http://', 'https://')):
            raise ValueError("url must be a valid HTTP/HTTPS URL")
        if not self.username or not self.password:
            raise ValueError("username and password are required")
```

**Validation Rules**:
- `url`: Must be valid HTTP/HTTPS URL, non-empty
- `username`: Non-empty string
- `password`: Non-empty string
- `client_name`: Defaults to "playlistgen"
- `api_version`: Defaults to "1.16.1"

**Environment Variable Mapping**:
- `SUBSONIC_URL` → `url`
- `SUBSONIC_USER` → `username`
- `SUBSONIC_PASSWORD` → `password`
- `SUBSONIC_CLIENT_NAME` → `client_name` (optional)
- `SUBSONIC_API_VERSION` → `api_version` (optional)

---

### 2. SubsonicAuthToken

**Purpose**: Authentication token for Subsonic API requests using MD5 salt+hash method.

**Lifecycle**: Generate → Use → Refresh on expiry (with retry)

**Fields**:
```python
@dataclass
class SubsonicAuthToken:
    """Authentication token for Subsonic API."""

    token: str          # MD5(password + salt)
    salt: str           # Random salt string
    username: str       # Username for this token
    created_at: datetime  # Token creation timestamp
    expires_at: Optional[datetime] = None  # Optional expiry (if server supports)

    def is_expired(self) -> bool:
        """Check if token has expired."""
        if self.expires_at is None:
            return False  # No expiry set
        return datetime.now(timezone.utc) > self.expires_at

    def to_auth_params(self) -> dict:
        """Convert to authentication query parameters."""
        return {
            'u': self.username,
            't': self.token,
            's': self.salt
        }
```

**State Transitions**:
1. **Generate**: Create new token with random salt, compute MD5(password + salt)
2. **Active**: Token used for API requests
3. **Expired**: Token expiry detected (401 response or time-based)
4. **Retry**: Queue pending requests, generate new token (up to 3 retries)
5. **Failed**: All retries exhausted, raise authentication error

**Validation Rules**:
- `token`: Non-empty 32-character hex string (MD5 hash)
- `salt`: Non-empty random string (6-16 characters)
- `username`: Non-empty string matching SubsonicConfig username
- `created_at`: Valid datetime
- `expires_at`: Optional datetime, must be > created_at if present

---

### 3. SubsonicTrack

**Purpose**: Raw track metadata from Subsonic API response.

**Source**: Subsonic API `getSongs` endpoint response

**Fields**:
```python
@dataclass
class SubsonicTrack:
    """Raw track data from Subsonic API."""

    # Required fields
    id: str                      # Unique track identifier
    title: str                   # Track title
    artist: str                  # Artist name
    album: str                   # Album name
    duration: int                # Duration in seconds
    path: str                    # File path on server
    suffix: str                  # File extension (mp3, flac, etc.)
    created: str                 # Creation timestamp (ISO format)

    # Optional fields
    genre: Optional[str] = None              # Genre (single string)
    track: Optional[int] = None              # Track number
    discNumber: Optional[int] = None         # Disc number
    year: Optional[int] = None               # Release year
    musicBrainzId: Optional[str] = None      # MusicBrainz track ID
    coverArt: Optional[str] = None           # Cover art ID
    size: Optional[int] = None               # File size in bytes
    bitRate: Optional[int] = None            # Bitrate in kbps
    contentType: Optional[str] = None        # MIME type
```

**Relationships**:
- `SubsonicTrack` → `Track` (1:1 transformation via `transform_to_track()`)
- Multiple `SubsonicTrack` instances may map to same logical track (duplicates detected by metadata)

**State**: Raw → Transformed → Deduplicated → Added to PlaylistManager

---

### 4. Track (Existing Model - No Changes)

**Purpose**: Unified track representation for playlist generation and downstream modules.

**Backward Compatibility**: All existing consumers (Last.fm, AzuraCast, ReplayGain, playlist generation) continue working without changes.

**Fields** (existing structure):
```python
class Track(dict):
    """Represents an audio track with extended functionality."""

    # Core metadata (Emby/Subsonic compatible)
    Id: str                           # Unique identifier
    Name: str                         # Track title
    AlbumArtist: str                  # Artist name
    Album: str                        # Album name
    Genres: List[str]                 # Genre array
    IndexNumber: Optional[int]        # Track number
    ParentIndexNumber: Optional[int]  # Disc number
    ProductionYear: Optional[int]     # Release year
    PremiereDate: str                 # ISO datetime
    RunTimeTicks: int                 # Duration in ticks (10,000,000 = 1 second)
    Path: str                         # File path

    # Provider metadata
    ProviderIds: Dict[str, str]       # External IDs (MusicBrainz, etc.)

    # Extended functionality (existing)
    playlist_manager: PlaylistManager
    azuracast_file_id: Optional[str]
    replaygain_gain: Optional[float]
    replaygain_peak: Optional[float]
    content: Optional[BytesIO]
```

**No modifications required**: Subsonic tracks are transformed to this existing format.

---

## Relationships

```
SubsonicConfig (1) ──┐
                     ├──> SubsonicClient (1)
SubsonicAuthToken (1)┘         │
                               │
                               ├──> SubsonicTrack[] (many, paginated)
                               │
                               └──> Track[] (transformed, deduplicated)
                                        │
                                        └──> PlaylistManager
                                                  │
                                                  ├──> Last.fm API
                                                  ├──> AzuraCast API
                                                  ├──> ReplayGain processing
                                                  └──> M3U playlist generation
```

**Key Relationships**:
1. **SubsonicConfig → SubsonicClient**: 1:1, client initialized with config from env vars
2. **SubsonicAuthToken → SubsonicClient**: 1:1, refreshed automatically on expiry
3. **SubsonicClient → SubsonicTrack[]**: 1:many, paginated fetch (500 tracks/page)
4. **SubsonicTrack → Track**: 1:1 transformation with metadata mapping
5. **Track → PlaylistManager**: many:1, tracks added to manager for playlist generation

---

## State Transitions

### Authentication State Machine

```
[Unauthenticated]
      │
      ├──> authenticate() ──> [Authenticating]
      │                            │
      │                            ├──> success ──> [Authenticated]
      │                            │                      │
      │                            │                      ├──> API request
      │                            │                      │
      │                            │                      ├──> 401 error ──> [Expired]
      │                            │                      │                      │
      │                            │                      │                      ├──> retry (queue requests)
      │                            │                      │                      │         │
      │                            │                      │                      │         └──> [Authenticating] (retry count < 3)
      │                            │                      │                      │
      │                            │                      │                      └──> [Failed] (retry count >= 3)
      │                            │
      │                            └──> failure ──> [Failed]
```

### Library Fetch State Machine

```
[Idle]
   │
   ├──> fetch_library() ──> [Fetching]
                                │
                                ├──> page 1 ──> success ──> [Fetching] (page 2)
                                │                                 │
                                │                                 ├──> page N ──> success ──> [Complete]
                                │                                 │
                                │                                 └──> network failure ──> [Failed]
                                │                                          │
                                │                                          └──> discard partial data
                                │
                                └──> failure ──> [Failed]
```

### Track Processing Pipeline

```
[Raw Subsonic Response]
         │
         ├──> parse JSON ──> [SubsonicTrack]
                                   │
                                   ├──> transform_to_track() ──> [Track (candidate)]
                                                                        │
                                                                        ├──> duplicate check
                                                                        │         │
                                                                        │         ├──> unique ──> [Track (accepted)]
                                                                        │         │                     │
                                                                        │         │                     └──> add_to_playlist_manager()
                                                                        │         │
                                                                        │         └──> duplicate ──> [Track (discarded)]
                                                                        │
                                                                        └──> [Added to PlaylistManager]
```

---

## Transformation Logic

### SubsonicTrack → Track Mapping

```python
def transform_subsonic_to_track(subsonic_track: SubsonicTrack, subsonic_url: str) -> Track:
    """Transform Subsonic track to unified Track model."""

    return Track({
        # Core fields
        'Id': subsonic_track.id,
        'Name': subsonic_track.title,
        'AlbumArtist': subsonic_track.artist,
        'Album': subsonic_track.album,

        # Genre transformation (string → array)
        'Genres': [subsonic_track.genre] if subsonic_track.genre else [],

        # Track/disc numbers
        'IndexNumber': subsonic_track.track,
        'ParentIndexNumber': subsonic_track.discNumber,

        # Year/date
        'ProductionYear': subsonic_track.year,
        'PremiereDate': subsonic_track.created,  # ISO datetime

        # Duration transformation (seconds → ticks)
        'RunTimeTicks': subsonic_track.duration * 10_000_000,

        # File path
        'Path': subsonic_track.path,

        # Provider IDs
        'ProviderIds': {
            'MusicBrainzTrack': subsonic_track.musicBrainzId
        } if subsonic_track.musicBrainzId else {},

        # Subsonic-specific metadata (for streaming)
        '_subsonic_url': subsonic_url,  # For stream endpoint construction
        '_subsonic_id': subsonic_track.id,
        '_subsonic_suffix': subsonic_track.suffix,
    }, playlist_manager)
```

**Key Transformations**:
1. **Genre**: `"Rock"` (string) → `["Rock"]` (array)
2. **Duration**: `180` (seconds) → `1_800_000_000` (ticks)
3. **MusicBrainzId**: Preserved in `ProviderIds['MusicBrainzTrack']`
4. **Subsonic metadata**: Added as `_subsonic_*` private fields for streaming

### Duplicate Detection

```python
def is_duplicate(track: Track, existing_tracks: List[Track]) -> bool:
    """Check if track is a duplicate based on metadata."""

    for existing in existing_tracks:
        if (track['Name'] == existing['Name'] and
            track['AlbumArtist'] == existing['AlbumArtist'] and
            track['Album'] == existing['Album']):
            # Same metadata, different IDs → duplicate
            return True

    return False
```

**Duplicate Handling**: Keep first occurrence, silently discard subsequent duplicates (per clarification).

---

## Validation Rules

### SubsonicConfig Validation
- ✅ URL must be valid HTTP/HTTPS
- ✅ Username and password non-empty
- ✅ Client name defaults to "playlistgen"
- ✅ API version defaults to "1.16.1"

### SubsonicAuthToken Validation
- ✅ Token is 32-character hex string (MD5)
- ✅ Salt is random string (6-16 chars)
- ✅ Created timestamp is valid
- ✅ Expires timestamp > created (if present)

### SubsonicTrack Validation
- ✅ Required fields: id, title, artist, album, duration, path, suffix, created
- ✅ Optional fields: genre, track, discNumber, year, musicBrainzId
- ✅ Duration > 0
- ✅ Created is valid ISO datetime

### Track Validation (Existing)
- ✅ All existing validation rules preserved
- ✅ Backward compatibility maintained
- ✅ No changes to downstream consumers

---

## Performance Considerations

### Memory Efficiency
- **Streaming processing**: Tracks processed incrementally, not all loaded at once
- **Lazy transformation**: SubsonicTrack → Track only when needed
- **Duplicate detection**: O(n) scan per track (acceptable for 10K tracks)

### Scalability
- **Pagination**: 500 tracks per page (Subsonic API limit)
- **Parallel fetching**: Pages fetched concurrently with semaphore (10 concurrent)
- **Target**: 5000 tracks in < 60 seconds (83.3 tracks/sec minimum)

### Database Considerations
- **Current**: In-memory storage in PlaylistManager
- **Future**: Database-backed storage for very large libraries (>50K tracks)

---

## Migration Notes

### Backward Compatibility
- ✅ Existing Track model unchanged
- ✅ Emby integration continues working when SUBSONIC_URL not set
- ✅ Last.fm, AzuraCast, ReplayGain modules unaffected
- ✅ M3U playlist generation continues working

### Source Precedence
- **Subsonic configured** (SUBSONIC_URL set): Use Subsonic exclusively, ignore Emby
- **Subsonic not configured**: Fall back to Emby (existing behavior)

### Testing Strategy
- **Unit tests**: Each entity validated independently
- **Integration tests**: Full transformation pipeline (SubsonicTrack → Track)
- **Contract tests**: API response schemas validated
- **Performance tests**: 5000 tracks in < 60 seconds

---

## Summary

This data model provides:
1. ✅ **Clean separation**: Subsonic-specific models (Config, AuthToken, Track) separate from unified Track model
2. ✅ **Backward compatibility**: Existing Track model unchanged, all consumers continue working
3. ✅ **Source-agnostic design**: Track model supports both Emby and Subsonic sources
4. ✅ **Type safety**: Dataclasses with type hints for all entities
5. ✅ **Validation**: Comprehensive validation rules for all fields
6. ✅ **Performance**: Designed for 10K+ track libraries with efficient pagination
7. ✅ **Testability**: Clear state transitions and transformation logic for testing

**Next Steps**: Create API contracts (Phase 1) → Generate tasks (Phase 2) → Implement (Phase 3)
